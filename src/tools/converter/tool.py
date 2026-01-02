import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz
import threading
import os
import queue
import time
from typing import Optional, Dict, Any, Tuple

from ...base.tool import BaseTool

class ConverterTool(BaseTool):
    """
    GUI Tool for converting PDF pages to Images (PNG/JPG).
    
    Features:
    - Batch conversion of all pages.
    - Customizable DPI (Resolution).
    - Throttled UI updates for performance.
    """
    name: str = "PDF to Image"
    icon: str = "🖼️"
    
    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.last_input: str = ""
        self.last_output: str = ""
    
    def render(self, parent: ttk.Frame) -> None:
        """
        Renders the Converter UI.
        
        Layout:
        1. Source PDF selection.
        2. Image Settings (DPI, Format).
        3. Output Folder selection.
        4. Progress Monitoring.
        """
        # 1. Input
        input_frame = ttk.LabelFrame(parent, text="Source PDF", padding=10)
        input_frame.pack(fill="x", pady=5)
        
        self.input_entry = ttk.Entry(input_frame)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        if self.last_input: self.input_entry.insert(0, self.last_input)

        ttk.Button(input_frame, text="Select PDF", command=self._browse_input).pack(side="right")
        
        # 2. Settings (DPI, Format)
        opts_frame = ttk.LabelFrame(parent, text="Image Settings", padding=10)
        opts_frame.pack(fill="x", pady=5)
        
        ttk.Label(opts_frame, text="DPI (Resolution):").pack(side="left")
        self.dpi_var = tk.IntVar(value=150)
        ttk.Spinbox(opts_frame, from_=72, to=600, textvariable=self.dpi_var, width=10).pack(side="left", padx=10)
        
        ttk.Label(opts_frame, text="Format:").pack(side="left", padx=(20, 0))
        self.fmt_var = tk.StringVar(value="png")
        ttk.Combobox(opts_frame, textvariable=self.fmt_var, values=["png", "jpg"], state="readonly", width=10).pack(side="left", padx=10)
        
        # 3. Output
        out_frame = ttk.LabelFrame(parent, text="Output Folder", padding=10)
        out_frame.pack(fill="x", pady=5)
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        if self.last_output: self.output_entry.insert(0, self.last_output)
        
        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(side="right")

        # 4. Action
        self.btn = ttk.Button(parent, text="Convert to Images", command=self.execute)
        self.btn.pack(pady=20)
        
        self.status = ttk.Progressbar(parent, mode='determinate')
        self.status.pack(fill="x", padx=10)
        self.status_lbl = ttk.Label(parent, text="Ready.")
        self.status_lbl.pack()
        
        self._process_queue()

    def _process_queue(self) -> None:
        """
        Polls queue for progress updates.
        Throttle: Only processes small batch at a time to prevent blocking main thread
        if the queue fills up too fast.
        """
        BATCH_SIZE = 10 
        processed = 0
        try:
            while processed < BATCH_SIZE:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    pct, msg = data
                    self.status['value'] = pct
                    self.status_lbl.config(text=msg)
                elif msg_type == "success":
                    self.status_lbl.config(text=data)
                    self.btn.config(state="normal")
                    self.status['value'] = 100
                    messagebox.showinfo("Success", "Conversion Complete!")
                elif msg_type == "error":
                    self.status_lbl.config(text="Error occurred.")
                    self.btn.config(state="normal")
                    messagebox.showerror("Error", data)
                processed += 1
        except queue.Empty:
            pass
        
        if hasattr(self, 'status_lbl') and self.status_lbl.winfo_exists():
            self.status_lbl.after(50, self._process_queue)

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Validates input and starts conversion thread."""
        input_path = self.input_entry.get()
        out_dir = self.output_entry.get()
        
        self.last_input = input_path
        self.last_output = out_dir
        
        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Error", "Invalid Input File")
            return
        if not out_dir:
            out_dir = os.path.dirname(input_path)

        dpi = self.dpi_var.get()
        fmt = self.fmt_var.get()
        
        self.status_lbl.config(text="Converting...")
        self.btn.config(state="disabled")
        threading.Thread(target=self._run_convert, args=(input_path, out_dir, dpi, fmt)).start()

    def _run_convert(self, input_path: str, out_dir: str, dpi: int, fmt: str) -> None:
        """
        Worker thread for conversion.
        Includes simple throttling logic to avoid flooding the GUI queue.
        """
        try:
            doc = fitz.open(input_path)
            total = len(doc)
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            
            last_update = 0.0
            
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=dpi)
                out_name = f"{base_name}_page_{i+1}.{fmt}"
                out_path = os.path.join(out_dir, out_name)
                pix.save(out_path)
                
                # Rate Limiting: Only update GUI every 0.1s or on last page
                now = time.time()
                if now - last_update > 0.1 or i == total - 1:
                    pct = ((i + 1) / total) * 100
                    self.queue.put(("progress", (pct, f"Saved page {i+1}/{total}")))
                    last_update = now
            
            doc.close()
            self.queue.put(("success", "Done."))
            
        except Exception as e:
            self.queue.put(("error", str(e)))
