import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
from pathlib import Path
from typing import List, Optional, Tuple, Any, Dict

from ...base.tool import BaseTool
from ...core.processor import BatchProcessor

class CompressorTool(BaseTool):
    """
    GUI Tool for compressing PDF and Image files.
    
    Features:
    - Multi-file and Folder selection.
    - Asynchronous processing via background thread.
    - Live progress updates using a thread-safe Queue.
    """
    name: str = "Compress PDF/Image"
    icon: str = "📉"
    
    def __init__(self) -> None:
        """Initialize the Compressor tool state."""
        self.processor = BatchProcessor()
        self.queue: queue.Queue = queue.Queue()
        self.input_items: List[str] = [] # Stores paths of selected files/folders

    def render(self, parent: ttk.Frame) -> None:
        """
        Builds the UI Layout.
        
        Layout sections:
        1. Input Selection (Listbox + Toolbar).
        2. Settings (Compression Level).
        3. Output Configuration.
        4. Progress Monitoring.
        
        Args:
            parent (ttk.Frame): The parent container.
        """
        # --- 1. Input Selection Area ---
        io_frame = ttk.LabelFrame(parent, text="Input Selection", padding=10)
        io_frame.pack(fill="both", expand=True, pady=5)
        
        # Toolbar (Buttons)
        toolbar = ttk.Frame(io_frame)
        toolbar.pack(fill="x", pady=(0, 5))
        
        ttk.Button(toolbar, text="📂 Add File(s)", command=self._add_files).pack(side="left", padx=(0, 5))
        ttk.Button(toolbar, text="📁 Add Folder", command=self._add_folder).pack(side="left", padx=(0, 5))
        ttk.Button(toolbar, text="❌ Clear", command=self._clear_inputs).pack(side="left", padx=(0, 5))
        
        # Listbox with Scrollbar
        list_container = ttk.Frame(io_frame)
        list_container.pack(fill="both", expand=True)
        
        self.listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED, height=6)
        self.listbox.pack(side="left", fill="both", expand=True)
        
        # Restore items (if tool was previously used)
        for item in self.input_items:
            self.listbox.insert(tk.END, item)
            
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # --- 2. Settings & Output ---
        opts_frame = ttk.LabelFrame(parent, text="Settings & Output", padding=10)
        opts_frame.pack(fill="x", pady=5)
        
        # Compression Level
        ttk.Label(opts_frame, text="Compression Level:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.level_var = tk.StringVar(value="Medium")
        ttk.Combobox(opts_frame, textvariable=self.level_var, values=["Low", "Medium", "High"], state="readonly", width=10).grid(row=0, column=1, sticky="w")
        
        # Output Directory
        ttk.Label(opts_frame, text="Output Folder:").grid(row=0, column=2, sticky="w", padx=(20, 10))
        self.output_entry = ttk.Entry(opts_frame, width=40)
        self.output_entry.grid(row=0, column=3, sticky="ew")
        ttk.Button(opts_frame, text="Browse", command=self._browse_output).grid(row=0, column=4, padx=5)
        
        opts_frame.columnconfigure(3, weight=1)
        
        # --- 3. Action Buttons ---
        self.start_btn = ttk.Button(parent, text="Start Compression", command=self.execute)
        self.start_btn.pack(pady=10)
        
        # --- 4. Progress Log ---
        log_frame = ttk.LabelFrame(parent, text="Progress Log", padding=10)
        log_frame.pack(fill="x", expand=False)

        self.progress = ttk.Progressbar(log_frame, mode='determinate')
        self.progress.pack(fill="x", pady=(0, 5))
        
        self.status_lbl = ttk.Label(log_frame, text="Ready.")
        self.status_lbl.pack(anchor="w")

        # Start background polling for queue messages
        self._process_queue()

    def _add_files(self) -> None:
        """Opens file dialog to add multiple files to the list."""
        files = filedialog.askopenfilenames(title="Select Files")
        for f in files:
            if f not in self.input_items:
                self.input_items.append(f)
                self.listbox.insert(tk.END, f)
                
    def _add_folder(self) -> None:
        """Opens directory dialog to add a folder to the list."""
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            if folder not in self.input_items:
                self.input_items.append(folder)
                self.listbox.insert(tk.END, folder)

    def _clear_inputs(self) -> None:
        """Clears all input selections."""
        self.input_items = []
        self.listbox.delete(0, tk.END)

    def _browse_output(self) -> None:
        """Opens directory dialog for output path."""
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def update_progress(self, current: int, total: int, msg: str) -> None:
        """
        Callback bound to BatchProcessor to receive updates from the worker thread.
        
        Args:
            current (int): Current items processed.
            total (int): Total items.
            msg (str): Status message.
        """
        self.queue.put(("progress", (current, total, msg)))

    def _process_queue(self) -> None:
        """
        Polls the thread-safe queue for messages and updates the GUI.
        Run periodically via `after()`.
        """
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    curr, total, status = data
                    if total > 0:
                        pct = (curr / total) * 100
                        self.progress['value'] = pct
                    self.status_lbl.config(text=f"[{curr}/{total}] {status}")
                elif msg_type == "done":
                    self.start_btn.config(state="normal")
                    self.progress['value'] = 100
                    self.status_lbl.config(text="Processing Complete.")
                    messagebox.showinfo("Done", "Processing Complete!")
                elif msg_type == "error":
                    self.start_btn.config(state="normal")
                    messagebox.showerror("Error", data)
        except queue.Empty:
            pass
        
        # Re-schedule poller if the view is still active
        if hasattr(self, 'start_btn') and self.start_btn.winfo_exists():
            self.start_btn.after(100, self._process_queue)

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Starts the compression process in a background thread.
        """
        if not self.input_items:
            messagebox.showwarning("Warning", "No files selected!")
            return
            
        output_dir = self.output_entry.get()
        level = self.level_var.get()
        
        # Lock UI
        self.start_btn.config(state="disabled")
        self.status_lbl.config(text="Scanning files...")
        self.progress['value'] = 0
        
        # Start Thread
        thread = threading.Thread(target=self._run_compression, args=(list(self.input_items), output_dir, level))
        thread.start()

    def _run_compression(self, input_paths: List[str], output_dir: str, level: str) -> None:
        """
        Worker thread logic. Expands folders and invokes BatchProcessor.
        """
        try:
            # 1. Expand Folders using glob
            all_files = []
            for path_str in input_paths:
                p = Path(path_str)
                if p.is_dir():
                     # Recursive scan for all files in folder
                     all_files.extend([str(x) for x in p.rglob("*") if x.is_file()])
                else:
                    all_files.append(str(p))
            
            if not all_files:
                self.queue.put(("error", "No files found in selection."))
                return

            # 2. Process
            self.processor.process_files(
                all_files, 
                output_dir if output_dir else None,
                level,
                progress_callback=self.update_progress
            )
            
            self.queue.put(("done", True))
        except Exception as e:
            self.queue.put(("error", str(e)))
