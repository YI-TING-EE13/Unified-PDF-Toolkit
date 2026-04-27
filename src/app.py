import tkinter as tk
from tkinter import ttk
import sys
import os
from typing import Dict, Optional

# Ensure src is in path if running directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.base.tool import BaseTool

# Dynamic Tool Loading
from src.tools.compressor.tool import CompressorTool
from src.tools.merger.tool import MergerTool
from src.tools.splitter.tool import SplitterTool
from src.tools.converter.tool import ConverterTool
from src.tools.image2pdf.tool import Image2PDFTool
from src.tools.page_manager.tool import PageManagerTool

class PDFToolkitApp(tk.Tk):
    """
    The Main Application Shell for the Unified PDF Toolkit.
    
    This class manages:
    1. The main window lifecycle (Tkinter root).
    2. Global styling and themes.
    3. Navigation sidebar and switching between different Tool views.
    4. View persistence (caching frames to preserve state).
    """

    def __init__(self) -> None:
        """Initialize the main application window and UI components."""
        super().__init__()
        
        self.title("Unified PDF Toolkit")
        self.geometry("1000x700")
        
        # Configure Grid Layout (Sidebar:Main = Fixed:Flexible)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._init_styles()
        self._init_ui()
        
    def _init_styles(self) -> None:
        """Initialize custom ttk styles and color palette."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Modern Color Palette
        bg_dark = "#2c3e50"     # Sidebar Background
        bg_main = "#ecf0f1"     # Main Content Background
        bg_active = "#34495e"   # Active/Hover State
        accent = "#3498db"      # Accent Color (Blue)
        text_light = "#ffffff"  # Light Text
        
        style.configure("Sidebar.TFrame", background=bg_dark)
        style.configure("Main.TFrame", background=bg_main)
        
        # Default Navigation Button
        style.configure("Nav.TButton", 
                        background=bg_dark, 
                        foreground=text_light, 
                        borderwidth=0, 
                        font=("Segoe UI", 11), 
                        anchor="w", 
                        padding=(20, 10))
                        
        style.map("Nav.TButton", 
                  background=[('active', bg_active)], 
                  foreground=[('active', 'white')])

        # Active Navigation Button (Selected State)
        style.configure("Active.Nav.TButton", 
                        background=bg_active, 
                        foreground=accent,
                        borderwidth=0,
                        font=("Segoe UI", 11, "bold"),
                        anchor="w",
                        padding=(20, 10))

        # Header Label Style
        style.configure("Header.TLabel", 
                        font=("Segoe UI", 20, "bold"), 
                        background=bg_main, 
                        foreground="#2c3e50")

    def _init_ui(self) -> None:
        """Build the core UI skeleton: Sidebar and Main Content Area."""
        # 1. Sidebar (Navigation)
        self.sidebar = ttk.Frame(self, style="Sidebar.TFrame", width=240)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False) # Enforce fixed width
        
        # App Title
        title_lbl = tk.Label(self.sidebar, text="PDF Toolkit", bg="#2c3e50", fg="white", font=("Segoe UI", 18, "bold"), pady=30, anchor="w")
        title_lbl.pack(fill="x", padx=20)
        
        # 2. Main Content Area
        self.main_area = ttk.Frame(self, style="Main.TFrame")
        self.main_area.grid(row=0, column=1, sticky="nsew")
        
        # State Management Containers
        self.tools: Dict[str, BaseTool] = {}
        self.tool_views: Dict[str, ttk.Frame] = {} # Cache for rendered frames
        self.nav_buttons: Dict[str, ttk.Button] = {} # Cache for sidebar buttons
        self.current_tool: Optional[str] = None
        
        self._register_tools()
        
        # Render Sidebar Buttons
        for tool_id, tool_instance in self.tools.items():
            btn = ttk.Button(self.sidebar, 
                             text=f"{tool_instance.icon}   {tool_instance.name}", 
                             style="Nav.TButton",
                             command=lambda t=tool_id: self.switch_view(t))
            btn.pack(fill="x", pady=2)
            self.nav_buttons[tool_id] = btn

        # Status Bar
        self.status_bar = ttk.Frame(self, relief=tk.SUNKEN, padding=(10, 2))
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.status_lbl = ttk.Label(self.status_bar, text="Ready", font=("Segoe UI", 9))
        self.status_lbl.pack(side="left")

        # Select first tool by default
        if self.tools:
            first_tool = list(self.tools.keys())[0]
            self.switch_view(first_tool)

    def _register_tools(self) -> None:
        """Instantiates and registers all available tools."""
        tools_list = [
            CompressorTool(),
            MergerTool(),
            SplitterTool(),
            ConverterTool(),
            Image2PDFTool(),
            PageManagerTool(),
        ]
        
        for tool in tools_list:
            self.tools[tool.name] = tool

    def switch_view(self, tool_id: str) -> None:
        """
        Switches the main view to the selected tool.
        
        Implements lazy loading (only renders the tool when first requested)
        and frame persistence (hides rather than destroys previous frames).

        Args:
            tool_id (str): The unique name/ID of the tool to switch to.
        """
        if self.current_tool == tool_id:
            return
            
        # 1. Hide current view
        if self.current_tool:
            self.tool_views[self.current_tool].pack_forget()
            # Reset previous button to default style
            self.nav_buttons[self.current_tool].configure(style="Nav.TButton")

        # 2. Prepare new view
        tool = self.tools[tool_id]
        
        if tool_id not in self.tool_views:
            # Lazy Load: Create container frame if it doesn't exist
            container = ttk.Frame(self.main_area, style="Main.TFrame")
            
            # Application Header within the view
            header = ttk.Label(container, text=tool.name, style="Header.TLabel")
            header.pack(anchor="w", padx=30, pady=(30, 20))
            
            # Content Area (Tool Render Target)
            content = ttk.Frame(container, style="Main.TFrame")
            content.pack(fill="both", expand=True, padx=30, pady=(0, 30))
            
            tool.render(content)
            self.tool_views[tool_id] = container
        
        # 3. Show new view
        self.tool_views[tool_id].pack(fill="both", expand=True)
        self.nav_buttons[tool_id].configure(style="Active.Nav.TButton")
        
        self.current_tool = tool_id
        self.status_lbl.config(text=f"Active: {tool.name}")

if __name__ == "__main__":
    app = PDFToolkitApp()
    app.mainloop()
