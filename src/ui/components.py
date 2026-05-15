"""
Reusable UI components for the PDF Toolkit.

This module provides shared, standardized widgets used across all tools
to keep file selection and output actions consistent.
"""

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Optional, Tuple


DisplayFormatter = Callable[[str], str]


class FileListWidget(ttk.Frame):
    """
    A reusable file-list widget with optional ordering controls.

    The widget stores full file paths internally while optionally showing a
    friendlier label in the listbox.
    """

    def __init__(
        self,
        parent: ttk.Frame,
        label: str = "Selected Files",
        filetypes: Optional[List[Tuple[str, str]]] = None,
        show_ordering: bool = True,
        select_mode: str = tk.EXTENDED,
        display_formatter: Optional[DisplayFormatter] = None,
    ) -> None:
        super().__init__(parent)

        self._files: List[str] = []
        self._filetypes = filetypes or [("All Files", "*.*")]
        self._show_ordering = show_ordering
        self._select_mode = select_mode
        self._display_formatter = display_formatter

        self._build_ui(label)

    def get_files(self) -> List[str]:
        """Returns a copy of the current ordered file list."""
        return list(self._files)

    def get_selected_file(self) -> Optional[str]:
        """Returns the selected full path, or None when nothing is selected."""
        selection = self.listbox.curselection()
        if selection:
            return self._files[selection[0]]
        return None

    def clear(self) -> None:
        """Removes all files from the list."""
        self._files.clear()
        self.listbox.delete(0, tk.END)

    def set_files(self, files: List[str]) -> None:
        """Replaces the entire file list."""
        self.clear()
        for file_path in files:
            self._append_file(file_path)

    def bind_select(self, callback) -> None:
        """Binds a callback to the ListboxSelect event."""
        self.listbox.bind("<<ListboxSelect>>", callback)

    def _build_ui(self, label: str) -> None:
        frame = ttk.LabelFrame(self, text=label, padding=10)
        frame.pack(fill="both", expand=True)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 5))

        ttk.Button(toolbar, text="Add Files", command=self._add_files).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(toolbar, text="Add Folder", command=self._add_folder).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(
            toolbar, text="Remove Selected", command=self._remove_selected
        ).pack(side="left", padx=(0, 5))
        ttk.Button(toolbar, text="Clear All", command=self.clear).pack(
            side="left", padx=(0, 5)
        )

        if self._show_ordering:
            ttk.Button(toolbar, text="Move Down", command=self._move_down).pack(
                side="right", padx=5
            )
            ttk.Button(toolbar, text="Move Up", command=self._move_up).pack(
                side="right", padx=5
            )

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

    def _display_text(self, file_path: str) -> str:
        if self._display_formatter:
            try:
                return self._display_formatter(file_path)
            except Exception:
                return file_path
        return file_path

    def _append_file(self, file_path: str) -> None:
        if file_path not in self._files:
            self._files.append(file_path)
            self.listbox.insert(tk.END, self._display_text(file_path))

    def _add_files(self) -> None:
        """Opens a file dialog to add individual files."""
        paths = filedialog.askopenfilenames(
            title="Select Files", filetypes=self._filetypes
        )
        for path in paths:
            self._append_file(path)

    def _add_folder(self) -> None:
        """Recursively adds all matching files from a chosen folder."""
        folder = filedialog.askdirectory(title="Select Folder")
        if not folder:
            return

        extensions = set()
        for _, pattern in self._filetypes:
            for part in pattern.split():
                ext = part.replace("*", "").lower()
                if ext:
                    extensions.add(ext)

        folder_path = Path(folder)
        found = sorted(str(path) for path in folder_path.rglob("*") if path.is_file())

        for file_path in found:
            if extensions and Path(file_path).suffix.lower() not in extensions:
                continue
            self._append_file(file_path)

    def _remove_selected(self) -> None:
        """Removes selected items from the list."""
        selection = self.listbox.curselection()
        for idx in reversed(selection):
            del self._files[idx]
            self.listbox.delete(idx)

    def _move_up(self) -> None:
        """Swaps selected items with the item above them."""
        selection = self.listbox.curselection()
        if not selection:
            return
        self.listbox.selection_clear(0, tk.END)
        for idx in selection:
            if idx == 0:
                self.listbox.selection_set(idx)
                continue
            self._files[idx], self._files[idx - 1] = (
                self._files[idx - 1],
                self._files[idx],
            )
            text = self.listbox.get(idx)
            self.listbox.delete(idx)
            self.listbox.insert(idx - 1, text)
            self.listbox.selection_set(idx - 1)

    def _move_down(self) -> None:
        """Swaps selected items with the item below them."""
        selection = self.listbox.curselection()
        if not selection:
            return
        self.listbox.selection_clear(0, tk.END)
        for idx in reversed(selection):
            if idx >= len(self._files) - 1:
                self.listbox.selection_set(idx)
                continue
            self._files[idx], self._files[idx + 1] = (
                self._files[idx + 1],
                self._files[idx],
            )
            text = self.listbox.get(idx)
            self.listbox.delete(idx)
            self.listbox.insert(idx + 1, text)
            self.listbox.selection_set(idx + 1)


class OutputActions(ttk.Frame):
    """Small result toolbar for opening the output folder or copying the path."""

    def __init__(self, parent: ttk.Frame) -> None:
        super().__init__(parent)
        self._path = ""

        self.open_btn = ttk.Button(
            self, text="Open Output Folder", command=self._open_output, state="disabled"
        )
        self.open_btn.pack(side="left", padx=(0, 5))

        self.copy_btn = ttk.Button(
            self, text="Copy Path", command=self._copy_path, state="disabled"
        )
        self.copy_btn.pack(side="left")

    def set_path(self, path: str) -> None:
        self._path = path
        state = "normal" if path else "disabled"
        self.open_btn.config(state=state)
        self.copy_btn.config(state=state)

    def clear(self) -> None:
        self.set_path("")

    def _open_output(self) -> None:
        if not self._path:
            return

        target = self._path if os.path.isdir(self._path) else os.path.dirname(self._path)
        if not target:
            target = os.getcwd()

        try:
            if sys.platform.startswith("win"):
                os.startfile(target)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open output folder: {exc}")

    def _copy_path(self) -> None:
        if not self._path:
            return
        self.clipboard_clear()
        self.clipboard_append(self._path)
        messagebox.showinfo("Copied", "Output path copied to clipboard.")
