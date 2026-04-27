"""
Reusable UI Components for the PDF Toolkit.

This module provides shared, standardized widgets used across all tools
to ensure a consistent user experience.
"""

import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
from typing import List, Optional, Tuple


class FileListWidget(ttk.Frame):
    """
    A reusable file-list widget with ordering controls.

    Provides the standard "Merge-style" file selection UI:
    - Listbox with vertical scrollbar showing selected files.
    - Toolbar: Add Files, Add Folder, Remove Selected, Clear All.
    - Ordering: Move Up / Move Down buttons.
    - Configurable file type filters.

    This widget encapsulates all file-list state and exposes a clean
    public API for parent tools to interact with.

    Args:
        parent (ttk.Frame): The parent container.
        label (str): The LabelFrame title text (e.g., "Files to Merge").
        filetypes (List[Tuple[str, str]]): File dialog filter
            (e.g., [("PDF Files", "*.pdf")]).
        show_ordering (bool): Whether to show Move Up/Down buttons.
            Defaults to True.
        select_mode (str): Listbox selection mode.
            Defaults to tk.EXTENDED.
    """

    def __init__(
        self,
        parent: ttk.Frame,
        label: str = "Selected Files",
        filetypes: Optional[List[Tuple[str, str]]] = None,
        show_ordering: bool = True,
        select_mode: str = tk.EXTENDED,
    ) -> None:
        """Initialize the FileListWidget with controls and an empty list."""
        super().__init__(parent)

        self._files: List[str] = []
        self._filetypes = filetypes or [("All Files", "*.*")]
        self._show_ordering = show_ordering
        self._select_mode = select_mode

        self._build_ui(label)

    # ── Public API ──────────────────────────────────────────────────

    def get_files(self) -> List[str]:
        """Returns a copy of the current ordered file list."""
        return list(self._files)

    def get_selected_file(self) -> Optional[str]:
        """
        Returns the path of the currently selected (highlighted) file,
        or None if nothing is selected.
        """
        selection = self.listbox.curselection()
        if selection:
            return self._files[selection[0]]
        return None

    def clear(self) -> None:
        """Removes all files from the list."""
        self._files.clear()
        self.listbox.delete(0, tk.END)

    def set_files(self, files: List[str]) -> None:
        """
        Replaces the entire file list (e.g., for restoring state).

        Args:
            files (List[str]): List of file paths.
        """
        self.clear()
        for f in files:
            self._files.append(f)
            self.listbox.insert(tk.END, f)

    def bind_select(self, callback) -> None:
        """
        Binds a callback to the ListboxSelect event.

        The callback will receive the standard Tkinter event object.
        Useful for tools that need to react to file selection (e.g., Splitter preview).

        Args:
            callback: A function accepting one event argument.
        """
        self.listbox.bind("<<ListboxSelect>>", callback)

    # ── UI Construction ─────────────────────────────────────────────

    def _build_ui(self, label: str) -> None:
        """Assembles the widget layout."""
        # Main LabelFrame container
        frame = ttk.LabelFrame(self, text=label, padding=10)
        frame.pack(fill="both", expand=True)

        # ── Toolbar (Add / Remove buttons) ──
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 5))

        ttk.Button(toolbar, text="📂 Add Files", command=self._add_files).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(toolbar, text="📁 Add Folder", command=self._add_folder).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(
            toolbar, text="Remove Selected", command=self._remove_selected
        ).pack(side="left", padx=(0, 5))
        ttk.Button(toolbar, text="Clear All", command=self.clear).pack(
            side="left", padx=(0, 5)
        )

        if self._show_ordering:
            ttk.Button(toolbar, text="Move Down ▼", command=self._move_down).pack(
                side="right", padx=5
            )
            ttk.Button(toolbar, text="Move Up ▲", command=self._move_up).pack(
                side="right", padx=5
            )

        # ── Listbox with Scrollbar ──
        list_container = ttk.Frame(frame)
        list_container.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            list_container, selectmode=self._select_mode, height=8
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            list_container, orient="vertical", command=self.listbox.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

    # ── Private Methods ─────────────────────────────────────────────

    def _add_files(self) -> None:
        """Opens a file dialog to add individual files."""
        paths = filedialog.askopenfilenames(
            title="Select Files", filetypes=self._filetypes
        )
        for p in paths:
            if p not in self._files:
                self._files.append(p)
                self.listbox.insert(tk.END, p)

    def _add_folder(self) -> None:
        """Recursively adds all matching files from a chosen folder."""
        folder = filedialog.askdirectory(title="Select Folder")
        if not folder:
            return

        # Build a set of allowed extensions from the filetypes config
        extensions = set()
        for _, pattern in self._filetypes:
            for part in pattern.split():
                # e.g., "*.pdf" -> ".pdf"
                ext = part.replace("*", "").lower()
                if ext:
                    extensions.add(ext)

        folder_path = Path(folder)
        # Recursive sort ensures consistent ordering
        found = sorted(str(x) for x in folder_path.rglob("*") if x.is_file())

        for f in found:
            # If extensions are specified, filter by them
            if extensions:
                if Path(f).suffix.lower() not in extensions:
                    continue
            if f not in self._files:
                self._files.append(f)
                self.listbox.insert(tk.END, f)

    def _remove_selected(self) -> None:
        """Removes selected items from the list."""
        selection = self.listbox.curselection()
        # Remove in reverse to maintain valid indices
        for idx in reversed(selection):
            del self._files[idx]
            self.listbox.delete(idx)

    def _move_up(self) -> None:
        """Swaps the selected item with the one above it."""
        selection = self.listbox.curselection()
        if not selection:
            return
        for idx in selection:
            if idx == 0:
                continue
            # Swap in data
            self._files[idx], self._files[idx - 1] = (
                self._files[idx - 1],
                self._files[idx],
            )
            # Swap in view
            text = self.listbox.get(idx)
            self.listbox.delete(idx)
            self.listbox.insert(idx - 1, text)
            self.listbox.selection_set(idx - 1)

    def _move_down(self) -> None:
        """Swaps the selected item with the one below it."""
        selection = self.listbox.curselection()
        if not selection:
            return
        for idx in reversed(selection):
            if idx >= len(self._files) - 1:
                continue
            self._files[idx], self._files[idx + 1] = (
                self._files[idx + 1],
                self._files[idx],
            )
            text = self.listbox.get(idx)
            self.listbox.delete(idx)
            self.listbox.insert(idx + 1, text)
            self.listbox.selection_set(idx + 1)
