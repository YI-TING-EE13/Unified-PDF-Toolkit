import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz
import threading
import queue
from pathlib import Path
from typing import List, Optional, Any, Dict

from ...base.tool import BaseTool

class MergerTool(BaseTool):
    """
    GUI Tool for merging multiple PDF files.
    
    Features:
    - List-based file ordering.
    - Drag-and-remove functionality.
    - Recursive folder adding.
    """
    name: str = "Merge PDFs"
    icon: str = "📑"
    
    def __init__(self) -> None:
        self.files: List[str] = []
        self.queue: queue.Queue = queue.Queue()
    
    def render(self, parent: ttk.Frame) -> None:
        """
        Renders the Merger UI: A robust file list with ordering controls.
        """
        # 1. File List Area
        list_frame = ttk.LabelFrame(parent, text="Files to Merge (Ordered)", padding=10)
        list_frame.pack(fill="both", expand=True, pady=5)
        
        # Listbox with Scrollbar
        self.listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, height=10)
        self.listbox.pack(side="left", fill="both", expand=True)
        
        # Restore state if files exist (persistence)
        if self.files:
            for f in self.files:
                self.listbox.insert(tk.END, f)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # 2. Controls (Add, Remove, Up, Down)
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(fill="x", pady=5)
        
        ttk.Button(ctrl_frame, text="📂 Add Files", command=self._add_files).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="📁 Add Folder", command=self._add_folder).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="Remove Selected", command=self._remove_files).pack(side="left", padx=5)
        ttk.Button(ctrl_frame, text="Clear All", command=self._clear_all).pack(side="left", padx=5)
        
        ttk.Button(ctrl_frame, text="Move Down ▼", command=self._move_down).pack(side="right", padx=5)
        ttk.Button(ctrl_frame, text="Move Up ▲", command=self._move_up).pack(side="right", padx=5)
        
        # 3. Output & Execute
        action_frame = ttk.LabelFrame(parent, text="Output", padding=10)
        action_frame.pack(fill="x", pady=10)
        
        self.merge_btn = ttk.Button(action_frame, text="Merge & Save As...", command=self.execute)
        self.merge_btn.pack(fill="x", padx=20)
        
        self.status_lbl = ttk.Label(parent, text="Ready to merge.")
        self.status_lbl.pack(anchor="w")
        
        # Start Polling
        self._process_queue()

    def _process_queue(self) -> None:
        """Polls the queue for updates."""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "status":
                    self.status_lbl.config(text=data)
                elif msg_type == "success":
                    self.merge_btn.config(state="normal")
                    self.status_lbl.config(text=f"Saved to {data}")
                    messagebox.showinfo("Success", "Merge Complete!")
                elif msg_type == "error":
                    self.merge_btn.config(state="normal")
                    self.status_lbl.config(text="Error occurred.")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass
        
        if hasattr(self, 'status_lbl') and self.status_lbl.winfo_exists():
            self.status_lbl.after(100, self._process_queue)

    def _add_files(self) -> None:
        """Add individual files."""
        paths = filedialog.askopenfilenames(title="Select PDFs", filetypes=[("PDF Files", "*.pdf")])
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.listbox.insert(tk.END, p)

    def _add_folder(self) -> None:
        """Recursively add all Pdfs from a folder."""
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            p = Path(folder)
            # Recursive sort ensures consistent order
            pdfs = sorted([str(x) for x in p.rglob("*.pdf") if x.is_file()])
            for f in pdfs:
                if f not in self.files:
                    self.files.append(f)
                    self.listbox.insert(tk.END, f)

    def _remove_files(self) -> None:
        """Remove selected items from list and backend storage."""
        selection = self.listbox.curselection()
        # Remove from backend list in reverse order to maintain indices
        for idx in reversed(selection):
            del self.files[idx]
            self.listbox.delete(idx)

    def _clear_all(self) -> None:
        self.files = []
        self.listbox.delete(0, tk.END)

    def _move_up(self) -> None:
        """Swaps selected item with the one above it."""
        selection = self.listbox.curselection()
        if not selection: return
        for idx in selection:
            if idx == 0: continue
            # Swap data
            self.files[idx], self.files[idx-1] = self.files[idx-1], self.files[idx]
            # Update View
            text = self.listbox.get(idx)
            self.listbox.delete(idx)
            self.listbox.insert(idx-1, text)
            self.listbox.selection_set(idx-1)

    def _move_down(self) -> None:
        """Swaps selected item with the one below it."""
        selection = self.listbox.curselection()
        if not selection: return
        # Process in reverse to avoid index shifting
        for idx in reversed(selection):
            if idx == len(self.files) - 1: continue
            self.files[idx], self.files[idx+1] = self.files[idx+1], self.files[idx]
            text = self.listbox.get(idx)
            self.listbox.delete(idx)
            self.listbox.insert(idx+1, text)
            self.listbox.selection_set(idx+1)

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Starts the merge operation."""
        if not self.files:
            messagebox.showwarning("Warning", "No files selected!")
            return
            
        output_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not output_path:
            return

        self.status_lbl.config(text="Merging...")
        self.merge_btn.config(state="disabled")
        
        # Run in thread
        threading.Thread(target=self._run_merge, args=(output_path,)).start()

    def _run_merge(self, output_path: str) -> None:
        """Worker thread for merging."""
        try:
            doc = fitz.open()
            for pdf_path in self.files:
                with fitz.open(pdf_path) as src:
                    doc.insert_pdf(src)
            doc.save(output_path)
            doc.close()
            
            # Safe Update
            self.queue.put(("success", output_path))
        except Exception as e:
            self.queue.put(("error", str(e)))
