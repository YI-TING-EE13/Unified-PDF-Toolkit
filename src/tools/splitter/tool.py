import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz
import threading
import os
import queue
from PIL import Image, ImageTk
from typing import List, Tuple, Optional, Any, Dict

from ...base.tool import BaseTool

class SplitterTool(BaseTool):
    """
    GUI Tool for splitting PDF files.
    
    Features:
    - Interactive PreviewPane (thumbnails of pages).
    - Slider interaction to select start/end pages.
    - Mouse wheel and drag navigation.
    """
    name: str = "Split PDF"
    icon: str = "✂️"
    
    def __init__(self) -> None:
        self.queue: queue.Queue = queue.Queue()
        self.doc: Optional[fitz.Document] = None
        self.total_pages: int = 0
        self.preview_img: Optional[ImageTk.PhotoImage] = None # Keep reference to prevent GC

    def render(self, parent: ttk.Frame) -> None:
        """
        Builds the UI with a PanedWindow (Split View).
        Left: Controls (File input, Range Sliders).
        Right: Preview (Image Canvas).
        """
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill="both", expand=True, pady=5)
        
        # --- Left Pane: Controls ---
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        # 1. File Input
        top_frame = ttk.LabelFrame(left_frame, text="Source", padding=5)
        top_frame.pack(fill="x", pady=5)
        
        self.input_entry = ttk.Entry(top_frame)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(top_frame, text="Open PDF", command=self._browse_input).pack(side="right")

        # 2. Range Slider Area
        range_frame = ttk.LabelFrame(left_frame, text="Select Range", padding=10)
        range_frame.pack(fill="x", pady=5)
        
        # Sliders
        self.val_min_var = tk.IntVar(value=1)
        self.val_max_var = tk.IntVar(value=1)
        
        # Start Slider
        ttk.Label(range_frame, text="Start Page:").pack(anchor="w")
        self.scale_min = ttk.Scale(range_frame, from_=1, to=1, variable=self.val_min_var, command=lambda v: self._on_range_change("min"))
        self.scale_min.pack(fill="x", pady=(0, 10))
        
        # End Slider
        ttk.Label(range_frame, text="End Page:").pack(anchor="w")
        self.scale_max = ttk.Scale(range_frame, from_=1, to=1, variable=self.val_max_var, command=lambda v: self._on_range_change("max"))
        self.scale_max.pack(fill="x", pady=(0, 10))
        
        # Manual Text Entry
        ttk.Label(range_frame, text="Range Text (e.g., 1-5):").pack(anchor="w")
        self.range_entry = ttk.Entry(range_frame)
        self.range_entry.pack(fill="x")
        
        # 3. Output
        out_frame = ttk.LabelFrame(left_frame, text="Output", padding=10)
        out_frame.pack(fill="x", pady=5)
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(out_frame, text="Browse", command=self._browse_output).pack(side="right")
        
        # 4. Action
        self.btn = ttk.Button(left_frame, text="Split PDF", command=self.execute, state="disabled")
        self.btn.pack(pady=20, fill="x")
        self.status_lbl = ttk.Label(left_frame, text="Open a PDF to start.")
        self.status_lbl.pack()

        # --- Right Pane: Preview ---
        right_frame = ttk.LabelFrame(paned, text="Page Preview", padding=10)
        paned.add(right_frame, weight=3) # Give more space to preview
        
        # Nav Controls (Above Image)
        nav_frame = ttk.Frame(right_frame)
        nav_frame.pack(fill="x", pady=(0, 5))
        
        self.page_lbl = ttk.Label(nav_frame, text="Page: -/-")
        self.page_lbl.pack(side="left")
        
        self.preview_var = tk.IntVar(value=1)
        self.preview_scale = ttk.Scale(nav_frame, from_=1, to=1, variable=self.preview_var, command=self._on_preview_change)
        self.preview_scale.pack(side="right", fill="x", expand=True, padx=10)
        
        # Image Host
        self.preview_container = ttk.Frame(right_frame)
        self.preview_container.pack(fill="both", expand=True)
        
        self.preview_lbl = ttk.Label(self.preview_container, text="No PDF loaded", anchor="center")
        self.preview_lbl.pack(fill="both", expand=True)
        
        # Bindings for Mouse Navigation
        self.preview_lbl.bind("<MouseWheel>", self._on_mouse_wheel)
        self.preview_lbl.bind("<Button-4>", self._on_mouse_wheel) # Linux scroll up
        self.preview_lbl.bind("<Button-5>", self._on_mouse_wheel) # Linux scroll down
        
        # Drag Logic State
        self.last_y = 0
        self.preview_lbl.bind("<Button-1>", self._on_drag_start)
        self.preview_lbl.bind("<B1-Motion>", self._on_drag_motion)
        
        self._process_queue()

    def _on_range_change(self, source: str) -> None:
        """
        Handles Start/End slider movements.
        Ensures Start <= End.
        Updates the text entry and preview.
        """
        start = self.val_min_var.get()
        end = self.val_max_var.get()
        if start > end:
            if source == "min": end = start # Push end
            else: start = end # Pull start
            self.val_min_var.set(start)
            self.val_max_var.set(end)
            
        self.range_entry.delete(0, tk.END)
        self.range_entry.insert(0, f"{start}-{end}")
        
        # Jump preview to the adjusted handle
        target_page = start if source == "min" else end
        self.preview_var.set(target_page)
        self._update_preview(target_page - 1)

    def _on_preview_change(self, event: Any) -> None:
        """Callback for the specific Preview-only slider."""
        pg = int(float(event))
        self._update_preview(pg - 1)

    def _on_mouse_wheel(self, event: Any) -> None:
        """Handles Mouse Wheel to scroll pages."""
        if self.total_pages == 0: return
        
        # Delta analysis
        delta = 0
        if event.num == 5 or event.delta < 0:
            delta = 1 # Next page
        elif event.num == 4 or event.delta > 0:
            delta = -1 # Prev page
            
        new_pg = self.preview_var.get() + delta
        new_pg = max(1, min(self.total_pages, new_pg))
        
        self.preview_var.set(new_pg)
        self._update_preview(new_pg - 1)

    def _on_drag_start(self, event: Any) -> None:
        """Capture Y position on click."""
        self.last_y = event.y

    def _on_drag_motion(self, event: Any) -> None:
        """Calculates vertical drag distance to emulate scrolling."""
        if self.total_pages == 0: return
        
        diff = event.y - self.last_y
        if abs(diff) > 20: # Threshold for page flip
            delta = -1 if diff > 0 else 1 # Drag down -> Move up (Prev)
            
            new_pg = self.preview_var.get() + delta
            new_pg = max(1, min(self.total_pages, new_pg))
            
            if new_pg != self.preview_var.get():
                self.preview_var.set(new_pg)
                self._update_preview(new_pg - 1)
                self.last_y = event.y

    def _process_queue(self) -> None:
        """GUI Update Loop."""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "status":
                    self.status_lbl.config(text=data)
                elif msg_type == "success":
                    self.status_lbl.config(text=data)
                    self.btn.config(state="normal")
                    messagebox.showinfo("Success", data)
                elif msg_type == "error":
                    self.status_lbl.config(text="Error occurred.")
                    self.btn.config(state="normal")
                    messagebox.showerror("Error", data)
                elif msg_type == "preview":
                    # Update Image
                    img = data
                    self.preview_lbl.config(image=img, text="")
                    self.preview_img = img # Keep ref
        except queue.Empty:
            pass
        
        if hasattr(self, 'status_lbl') and self.status_lbl.winfo_exists():
            self.status_lbl.after(100, self._process_queue)

    def _browse_input(self) -> None:
        """Opens file dialog and loads the PDF."""
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, path)
            self._load_pdf(path)

    def _load_pdf(self, path: str) -> None:
        """
        Loads PDF metadata and renders the first page preview.
        """
        try:
            if self.doc: self.doc.close()
            self.doc = fitz.open(path)
            self.total_pages = len(self.doc)
            
            # Configure Sliders
            self.scale_min.config(to=self.total_pages, value=1)
            self.scale_max.config(to=self.total_pages, value=self.total_pages)
            
            # Configure Preview Scale
            self.preview_scale.config(to=self.total_pages)
            self.preview_var.set(1)
            
            # Reset Range Text
            self.range_entry.delete(0, tk.END)
            self.range_entry.insert(0, f"1-{self.total_pages}")
            
            self.btn.config(state="normal")
            self.status_lbl.config(text=f"Loaded {self.total_pages} pages.")
            
            # Show Page 1
            self._update_preview(0)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load PDF: {e}")

    def _update_preview(self, page_num: int) -> None:
        """
        Generates a thumbnail for the specified page number.
        Uses Pillow to convert PyMuPDF Pixmap to Tkinter PhotoImage.
        """
        if not self.doc or page_num < 0 or page_num >= self.total_pages:
            return

        # Update text indicator
        self.page_lbl.config(text=f"Page: {page_num + 1}/{self.total_pages}")
            
        try:
            page = self.doc[page_num]
            # DPI 100 provides a good balance of speed vs quality for preview
            pix = page.get_pixmap(dpi=100)
            
            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            
            # Resize to fit within 500px high
            base_height = 500
            aspect = img.width / img.height
            new_w = int(base_height * aspect)
            
            img = img.resize((new_w, base_height), Image.Resampling.LANCZOS)
            tk_img = ImageTk.PhotoImage(img)
            
            self.queue.put(("preview", tk_img))
        except Exception:
            pass

    def _browse_output(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def execute(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Validates inputs and starts splitting thread."""
        input_path = self.input_entry.get()
        out_dir = self.output_entry.get()
        ranges_str = self.range_entry.get()
        
        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Error", "Invalid Input File")
            return
        if not out_dir:
            out_dir = os.path.dirname(input_path)

        self.status_lbl.config(text="Splitting...")
        self.btn.config(state="disabled")
        threading.Thread(target=self._run_split, args=(input_path, out_dir, ranges_str)).start()

    def _parse_ranges(self, range_str: str, total_pages: int) -> List[Tuple[int, int]]:
        """
        Parses range string (e.g., '1-3, 5') into list of tuples.
        Returns 0-indexed values.
        """
        if not range_str.strip():
            return [(i, i) for i in range(total_pages)]
        ranges = []
        parts = range_str.split(',')
        for p in parts:
            p = p.strip()
            if '-' in p:
                start, end = map(int, p.split('-'))
                ranges.append((start-1, end-1))
            else:
                idx = int(p)
                ranges.append((idx-1, idx-1))
        return ranges

    def _run_split(self, input_path: str, out_dir: str, ranges_str: str) -> None:
        """Worker thread logic for PDF splitting."""
        try:
            # Re-open doc in thread (PyMuPDF objects are not thread-safe across threads generally)
            doc = fitz.open(input_path)
            total = len(doc)
            
            try:
                page_ranges = self._parse_ranges(ranges_str, total)
            except ValueError:
                self.queue.put(("error", "Invalid Range Format"))
                return

            base_name = os.path.splitext(os.path.basename(input_path))[0]
            count = 0
            for start, end in page_ranges:
                if start < 0 or end >= total: continue
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=start, to_page=end)
                out_name = f"{base_name}_{start+1}-{end+1}.pdf"
                new_doc.save(os.path.join(out_dir, out_name))
                new_doc.close()
                count += 1
            
            doc.close()
            self.queue.put(("success", f"Created {count} files."))
        except Exception as e:
            self.queue.put(("error", str(e)))
