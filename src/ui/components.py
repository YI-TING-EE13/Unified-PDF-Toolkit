"""
Reusable UI components for the PDF Toolkit.

This module provides shared, standardized widgets used across all tools
to keep file selection and output actions consistent.
"""

import os
import shutil
# Used only with fixed OS opener executables resolved to absolute paths.
import subprocess  # nosec B404
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Optional, Tuple

try:
    from tkinterdnd2 import DND_FILES
except ImportError:
    DND_FILES = None

from ..utils.settings import add_recent_path
from ..utils.workflow import remember_output
from .motion import MotionController
from .theme import FONT_FAMILY, PALETTE


DisplayFormatter = Callable[[str], str]
ChangeCallback = Callable[[List[str]], None]


def responsive_wraplength(widget, *, maximum: int = 600, minimum: int = 280) -> int:
    """Return a readable line length that remains safe at the minimum width."""

    window_width = widget.winfo_toplevel().winfo_width()
    return max(minimum, min(maximum, window_width - 320))


class ScrollablePanel(ttk.Frame):
    """Give an arbitrary tool layout vertical overflow without changing its interface."""

    def __init__(self, parent, *, padding=(0, 0)) -> None:
        super().__init__(parent, style="ToolBody.TFrame")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self,
            background=PALETTE.surface,
            borderwidth=0,
            highlightthickness=0,
            yscrollincrement=28,
        )
        self.scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.content = ttk.Frame(
            self.canvas,
            style="ToolBody.TFrame",
            padding=padding,
        )
        self._window_id = self.canvas.create_window(
            0,
            0,
            anchor="nw",
            window=self.content,
        )
        self.content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def refresh(self) -> None:
        self.update_idletasks()
        canvas_height = max(1, self.canvas.winfo_height())
        requested_height = self.content.winfo_reqheight()
        self.canvas.itemconfigure(
            self._window_id,
            height=max(canvas_height, requested_height),
        )
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        if requested_height > canvas_height:
            self.scrollbar.grid()
        else:
            self.scrollbar.grid_remove()

    def bind_mousewheel_tree(self) -> None:
        """Bind scrolling only where a tool has not claimed wheel navigation."""

        def visit(widget) -> None:
            scrollable_widget = isinstance(
                widget,
                (
                    tk.Canvas,
                    tk.Listbox,
                    tk.Text,
                    ttk.Combobox,
                    ttk.Spinbox,
                    ttk.Treeview,
                ),
            )
            if not scrollable_widget and not widget.bind("<MouseWheel>"):
                widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
            if not scrollable_widget and not widget.bind("<Button-4>"):
                widget.bind("<Button-4>", self._on_mousewheel, add="+")
            if not scrollable_widget and not widget.bind("<Button-5>"):
                widget.bind("<Button-5>", self._on_mousewheel, add="+")
            for child in widget.winfo_children():
                visit(child)

        visit(self.content)

    def _on_content_configure(self, _event) -> None:
        self.after_idle(self.refresh)

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self._window_id, width=max(1, event.width))
        self.after_idle(self.refresh)

    def _on_mousewheel(self, event):
        if not self.scrollbar.winfo_ismapped():
            return None
        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            direction = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(direction * 3, "units")
        return "break"


class ResponsiveSplit(ttk.Frame):
    """Switch primary/secondary content between tabs and a two-pane layout."""

    def __init__(
        self,
        parent: ttk.Frame,
        *,
        primary_label: str = "Controls",
        secondary_label: str = "Preview",
        compact_below: int = 1040,
    ) -> None:
        super().__init__(parent)
        self._compact_below = compact_below
        self._selected = "primary"
        self.compact = False
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.tab_bar = ttk.Frame(self)
        self.primary_button = ttk.Button(
            self.tab_bar,
            text=primary_label,
            command=lambda: self.select("primary"),
            style="Accent.TButton",
        )
        self.primary_button.pack(side="left", padx=(0, 5))
        self.secondary_button = ttk.Button(
            self.tab_bar,
            text=secondary_label,
            command=lambda: self.select("secondary"),
            style="Quiet.TButton",
        )
        self.secondary_button.pack(side="left")

        self.primary = ttk.Frame(self, padding=(0, 4))
        self.secondary = ttk.LabelFrame(
            self,
            text=secondary_label,
            padding=10,
        )

        top_level = parent.winfo_toplevel()
        top_level.update_idletasks()
        self._apply_mode(top_level.winfo_width() < self._compact_below)
        top_level.bind("<Configure>", self._on_window_configure, add="+")

    def select(self, pane: str) -> None:
        """Show one compact pane; wide layouts continue to show both."""

        if pane not in {"primary", "secondary"}:
            raise ValueError(f"Unknown responsive pane: {pane}")
        self._selected = pane
        self.primary_button.configure(
            style="Accent.TButton" if pane == "primary" else "Quiet.TButton"
        )
        self.secondary_button.configure(
            style="Accent.TButton" if pane == "secondary" else "Quiet.TButton"
        )
        if self.compact:
            self.primary.grid_remove()
            self.secondary.grid_remove()
            selected = self.primary if pane == "primary" else self.secondary
            selected.grid(row=1, column=0, sticky="nsew")

    def reflow(self, window_width: int) -> None:
        """Apply the layout that corresponds to an application width."""

        self._apply_mode(window_width < self._compact_below)

    def _on_window_configure(self, event) -> None:
        if event.widget is self.winfo_toplevel():
            self.reflow(event.width)

    def _apply_mode(self, compact: bool) -> None:
        if compact == self.compact and self.primary.winfo_manager():
            return
        self.compact = compact
        self.primary.grid_forget()
        self.secondary.grid_forget()
        if compact:
            self.columnconfigure(0, weight=1)
            self.columnconfigure(1, weight=0)
            self.tab_bar.grid(row=0, column=0, sticky="w", pady=(0, 8))
            self.select(self._selected)
            return

        self.tab_bar.grid_remove()
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)
        self.primary.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.secondary.grid(row=1, column=1, sticky="nsew")


class FileListWidget(ttk.Frame):
    """
    A reusable file-list widget with optional ordering controls.

    The widget stores full file paths internally while optionally showing a
    friendlier label in the listbox. Tools can subscribe to `on_change` when
    they need previews or derived state to follow the current file order.
    """

    def __init__(
        self,
        parent: ttk.Frame,
        label: str = "Selected Files",
        filetypes: Optional[List[Tuple[str, str]]] = None,
        show_ordering: bool = True,
        select_mode: str = tk.EXTENDED,
        display_formatter: Optional[DisplayFormatter] = None,
        on_change: Optional[ChangeCallback] = None,
    ) -> None:
        super().__init__(parent)

        self._motion = MotionController(self)
        self._files: List[str] = []
        self._filetypes = filetypes or [("All Files", "*.*")]
        self._show_ordering = show_ordering
        self._select_mode = select_mode
        self._display_formatter = display_formatter
        self._on_change = on_change

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
        self._notify_change()

    def set_files(self, files: List[str]) -> None:
        """Replaces the entire file list."""
        self._files.clear()
        self.listbox.delete(0, tk.END)
        for file_path in files:
            self._append_file(file_path, notify=False)
        self._notify_change()

    def bind_select(self, callback) -> None:
        """Binds a callback to the ListboxSelect event."""
        self.listbox.bind("<<ListboxSelect>>", callback)

    def _build_ui(self, label: str) -> None:
        frame = ttk.LabelFrame(self, text=label, padding=12)
        frame.pack(fill="both", expand=True)

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 9))

        ttk.Button(
            toolbar, text="Add Files", command=self._add_files, style="Quiet.TButton"
        ).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(
            toolbar, text="Add Folder", command=self._add_folder, style="Quiet.TButton"
        ).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(
            toolbar,
            text="Remove Selected",
            command=self._remove_selected,
            style="Quiet.TButton",
        ).pack(side="left", padx=(0, 5))
        ttk.Button(
            toolbar, text="Clear All", command=self.clear, style="Quiet.TButton"
        ).pack(
            side="left", padx=(0, 5)
        )

        self.count_label = ttk.Label(toolbar, text="0 files", style="Muted.TLabel")
        self.count_label.pack(side="right", padx=(8, 0))

        if self._show_ordering:
            ttk.Button(
                toolbar,
                text="Move Down",
                command=self._move_down,
                style="Quiet.TButton",
            ).pack(
                side="right", padx=5
            )
            ttk.Button(
                toolbar,
                text="Move Up",
                command=self._move_up,
                style="Quiet.TButton",
            ).pack(
                side="right", padx=5
            )

        list_container = ttk.Frame(frame)
        list_container.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            list_container, selectmode=self._select_mode, height=6
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        empty_text = (
            "Drop files here\nor use Add Files"
            if DND_FILES
            else "No files selected\nUse Add Files to begin"
        )
        self.empty_label = tk.Label(
            list_container,
            text=empty_text,
            background=PALETTE.surface,
            foreground=PALETTE.text_muted,
            font=(FONT_FAMILY, 10),
            justify="center",
            padx=16,
            pady=10,
        )

        scrollbar = ttk.Scrollbar(
            list_container, orient="vertical", command=self.listbox.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        self._enable_drag_drop()
        self.after_idle(lambda: self._sync_list_state(animate=False))

    def _enable_drag_drop(self) -> None:
        if not DND_FILES or not hasattr(self.listbox, "drop_target_register"):
            return
        self.listbox.drop_target_register(DND_FILES)
        self.listbox.dnd_bind("<<Drop>>", self._on_drop)
        if hasattr(self.empty_label, "drop_target_register"):
            self.empty_label.drop_target_register(DND_FILES)
            self.empty_label.dnd_bind("<<Drop>>", self._on_drop)

    def _matching_files_from_folder(self, folder: str) -> List[str]:
        extensions = self._allowed_extensions()
        folder_path = Path(folder)
        found = sorted(str(path) for path in folder_path.rglob("*") if path.is_file())
        if not extensions:
            return found
        return [
            file_path
            for file_path in found
            if Path(file_path).suffix.lower() in extensions
        ]

    def _allowed_extensions(self) -> set:
        extensions = set()
        for _, pattern in self._filetypes:
            for part in pattern.split():
                if part in {"*", "*.*"}:
                    return set()
                ext = part.replace("*", "").lower()
                if ext and ext not in {".", ".*"}:
                    extensions.add(ext)
        return extensions

    def _on_drop(self, event) -> None:
        changed = False
        for raw_path in self.tk.splitlist(event.data):
            path = str(Path(raw_path))
            if Path(path).is_dir():
                for file_path in self._matching_files_from_folder(path):
                    changed = self._append_file(file_path, notify=False) or changed
            elif Path(path).is_file():
                extensions = self._allowed_extensions()
                if extensions and Path(path).suffix.lower() not in extensions:
                    continue
                changed = self._append_file(path, notify=False) or changed
        if changed:
            self._notify_change()

    def _display_text(self, file_path: str) -> str:
        if self._display_formatter:
            try:
                return self._display_formatter(file_path)
            except Exception:
                return file_path
        return file_path

    def _notify_change(self) -> None:
        self._sync_list_state()
        if self._on_change:
            self._on_change(self.get_files())

    def _sync_list_state(self, *, animate: bool = True) -> None:
        count = len(self._files)
        self.count_label.configure(text=f"{count} file" if count == 1 else f"{count} files")
        visible = bool(self.empty_label.place_info())
        if count == 0:
            if not visible:
                self.empty_label.place(relx=0.5, rely=0.47, anchor="center")
                self.empty_label.lift()
            self._motion.animate(
                "empty-state",
                150 if animate else 0,
                lambda value: self.empty_label.place_configure(
                    rely=0.47 + 0.03 * value
                ),
            )
            return
        if not visible:
            return

        self._motion.animate(
            "empty-state",
            110 if animate else 0,
            lambda value: self.empty_label.place_configure(
                rely=0.5 - 0.025 * value
            ),
            on_complete=self.empty_label.place_forget,
        )

    def _append_file(self, file_path: str, notify: bool = True) -> bool:
        if file_path not in self._files:
            self._files.append(file_path)
            self.listbox.insert(tk.END, self._display_text(file_path))
            add_recent_path("recent.inputs", file_path)
            if notify:
                self._notify_change()
            return True
        return False

    def _add_files(self) -> None:
        """Opens a file dialog to add individual files."""
        paths = filedialog.askopenfilenames(
            title="Select Files", filetypes=self._filetypes
        )
        changed = False
        for path in paths:
            changed = self._append_file(path, notify=False) or changed
        if changed:
            self._notify_change()

    def _add_folder(self) -> None:
        """Recursively adds all matching files from a chosen folder."""
        folder = filedialog.askdirectory(title="Select Folder")
        if not folder:
            return

        changed = False
        for file_path in self._matching_files_from_folder(folder):
            changed = self._append_file(file_path, notify=False) or changed
        if changed:
            self._notify_change()

    def _remove_selected(self) -> None:
        """Removes selected items from the list."""
        selection = self.listbox.curselection()
        if not selection:
            return
        for idx in reversed(selection):
            del self._files[idx]
            self.listbox.delete(idx)
        self._notify_change()

    def _move_up(self) -> None:
        """Swaps selected items with the item above them."""
        selection = self.listbox.curselection()
        if not selection:
            return
        changed = False
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
            changed = True
        if changed:
            self._notify_change()

    def _move_down(self) -> None:
        """Swaps selected items with the item below them."""
        selection = self.listbox.curselection()
        if not selection:
            return
        changed = False
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
            changed = True
        if changed:
            self._notify_change()


class OutputActions(ttk.Frame):
    """Small result toolbar for opening the output folder or copying the path."""

    def __init__(self, parent: ttk.Frame) -> None:
        super().__init__(parent)
        self._motion = MotionController(self)
        self._path = ""

        self.open_btn = ttk.Button(
            self,
            text="Open Output Folder",
            command=self._open_output,
            state="disabled",
            style="Quiet.TButton",
        )
        self.open_btn.pack(side="left", padx=(0, 5))

        self.copy_btn = ttk.Button(
            self,
            text="Copy Path",
            command=self._copy_path,
            state="disabled",
            style="Quiet.TButton",
        )
        self.copy_btn.pack(side="left")
        self.ready_label = ttk.Label(
            self, text="✓ Output ready", style="Success.TLabel"
        )

    def set_path(self, path: str) -> None:
        had_path = bool(self._path)
        self._path = path
        if path:
            remember_output(path)
        state = "normal" if path else "disabled"
        self.open_btn.config(state=state)
        self.copy_btn.config(state=state)
        has_path = bool(path)
        if has_path == had_path:
            return
        if has_path:
            self.ready_label.pack(side="left", padx=(0, 0))
            self._motion.animate(
                "output-ready",
                140,
                lambda value: self.ready_label.pack_configure(
                    padx=(round(10 * value), 0)
                ),
            )
            return
        if self.ready_label.winfo_manager():
            self._motion.animate(
                "output-ready",
                100,
                lambda value: self.ready_label.pack_configure(
                    padx=(round(10 * (1.0 - value)), 0)
                ),
                on_complete=self.ready_label.pack_forget,
            )

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
                os.startfile(target)  # type: ignore[attr-defined]  # nosec B606
            elif sys.platform == "darwin":
                opener = shutil.which("open")
                if not opener:
                    raise FileNotFoundError("The macOS 'open' command was not found.")
                subprocess.Popen([opener, target])  # nosec B603
            else:
                opener = shutil.which("xdg-open")
                if not opener:
                    raise FileNotFoundError("The 'xdg-open' command was not found.")
                subprocess.Popen([opener, target])  # nosec B603
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open output folder: {exc}")

    def _copy_path(self) -> None:
        if not self._path:
            return
        self.clipboard_clear()
        self.clipboard_append(self._path)
        messagebox.showinfo("Copied", "Output path copied to clipboard.")
