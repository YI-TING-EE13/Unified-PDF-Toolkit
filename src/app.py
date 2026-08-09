import os
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import Dict, Optional

try:
    from tkinterdnd2 import TkinterDnD
except ImportError:
    TkinterDnD = None  # type: ignore[assignment]

# Ensure src is in path if running directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.base.tool import BaseTool
from src.tools.batch_queue.tool import BatchQueueTool
from src.tools.compressor.tool import CompressorTool
from src.tools.converter.tool import ConverterTool
from src.tools.diagnostics.tool import DiagnosticsTool
from src.tools.document_ocr.tool import DocumentOcrTool
from src.tools.image2pdf.tool import Image2PDFTool
from src.tools.merger.tool import MergerTool
from src.tools.page_manager.tool import PageManagerTool
from src.tools.pdf2word.tool import PDFToWordTool
from src.tools.settings.tool import SettingsTool
from src.tools.splitter.tool import SplitterTool
from src.ui.motion import MotionController, WindowMotion
from src.ui.navigation import NavigationRail
from src.ui.components import ScrollablePanel, responsive_wraplength
from src.ui.theme import FONT_FAMILY, PALETTE, configure_theme


_BaseTk = TkinterDnD.Tk if TkinterDnD else tk.Tk

GUI_STARTUP_ERROR_MESSAGE = (
    "Unified PDF Toolkit could not start because the desktop Tk/Tcl runtime "
    "is unavailable or misconfigured. Reinstall the packaged app, or run from "
    "a Python environment with working Tk support."
)


@dataclass(frozen=True)
class ToolPresentation:
    group: str
    description: str


TOOL_PRESENTATIONS: dict[str, ToolPresentation] = {
    "Compress PDF/Image": ToolPresentation(
        "Organize",
        "Reduce PDF and image size with clear presets or detailed image controls.",
    ),
    "Merge PDFs": ToolPresentation(
        "Organize",
        "Combine PDFs in a chosen order and preview the merged page sequence.",
    ),
    "Split PDF": ToolPresentation(
        "Organize",
        "Select page ranges visually and export focused PDF files.",
    ),
    "Page Manager": ToolPresentation(
        "Organize",
        "Reorder, rotate, insert, delete, or extract pages before saving.",
    ),
    "PDF to Image": ToolPresentation(
        "Convert & extract",
        "Render PDF pages to PNG or JPEG at the resolution you choose.",
    ),
    "PDF to Word": ToolPresentation(
        "Convert & extract",
        "Create editable, image-faithful, or OCR-assisted Word documents.",
    ),
    "Document OCR": ToolPresentation(
        "Convert & extract",
        "Extract local text from PDFs and images with an available OCR provider.",
    ),
    "Image to PDF": ToolPresentation(
        "Convert & extract",
        "Turn ordered images into one PDF with optional compression.",
    ),
    "Batch Queue": ToolPresentation(
        "Workspace",
        "Run repeatable mixed jobs and export structured completion reports.",
    ),
    "Diagnostics": ToolPresentation(
        "Workspace",
        "Check the local runtime, dependencies, OCR, and output folders.",
    ),
    "Settings / Recent": ToolPresentation(
        "Workspace",
        "Manage output behavior, local OCR options, and recent activity.",
    ),
    "[Dev] Document OCR Shell": ToolPresentation(
        "Development",
        "Exercise the deterministic development-only OCR shell.",
    ),
}
NAVIGATION_GROUPS = ("Organize", "Convert & extract", "Workspace", "Development")


def presentation_for(tool_name: str) -> ToolPresentation:
    """Return maintained navigation copy for every registered tool."""

    try:
        return TOOL_PRESENTATIONS[tool_name]
    except KeyError as exc:
        raise KeyError(f"Missing UI presentation metadata for {tool_name!r}.") from exc


def gui_startup_error_message() -> str:
    """Return a user-safe GUI startup failure message without local paths."""

    return GUI_STARTUP_ERROR_MESSAGE


def developer_tools_enabled() -> bool:
    """Return true only when developer-only tools are explicitly enabled."""

    return os.environ.get("PDF_TOOLKIT_ENABLE_DEV_TOOLS", "").lower() in {
        "1",
        "true",
        "yes",
    }


def build_tools_list() -> list[BaseTool]:
    """Build tool instances, including developer-only tools when enabled."""

    tools_list: list[BaseTool] = [
        CompressorTool(),
        MergerTool(),
        SplitterTool(),
        ConverterTool(),
        PDFToWordTool(),
        DocumentOcrTool(),
        Image2PDFTool(),
        PageManagerTool(),
        BatchQueueTool(),
        DiagnosticsTool(),
        SettingsTool(),
    ]

    if developer_tools_enabled():
        from src.tools.ai_ocr_test.tool import DevDocumentOcrTool

        tools_list.append(DevDocumentOcrTool())

    return tools_list


class PDFToolkitApp(_BaseTk):
    """Main window, presentation system, navigation, and cached tool views."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Unified PDF Toolkit")
        self._configure_window_geometry()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._init_styles()
        self._motion = MotionController(self)
        self._window_motion = WindowMotion(self, enabled=self._motion.enabled)
        self._closing = False
        self._init_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Configure>", self._on_window_configure)
        self.after_idle(self._window_motion.show)

    def _configure_window_geometry(self) -> None:
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(1360, max(780, screen_width - 72))
        height = min(880, max(660, screen_height - 96))
        self.geometry(f"{width}x{height}")
        self.minsize(min(960, width), min(700, height))

    def _init_styles(self) -> None:
        self.style = configure_theme(self)

    def _init_ui(self) -> None:
        self.sidebar = tk.Frame(
            self,
            background=PALETTE.sidebar,
            width=244,
            highlightthickness=0,
        )
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand = tk.Frame(self.sidebar, background=PALETTE.sidebar)
        brand.pack(fill="x", padx=20, pady=(24, 12))
        tk.Label(
            brand,
            text="PDF TOOLKIT",
            background=PALETTE.sidebar,
            foreground="#FFFFFF",
            font=(FONT_FAMILY, 15, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            brand,
            text="Local document workspace",
            background=PALETTE.sidebar,
            foreground="#8E9AAF",
            font=(FONT_FAMILY, 9),
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        self.main_area = ttk.Frame(self, style="Main.TFrame")
        self.main_area.grid(row=0, column=1, sticky="nsew")

        self.tools: Dict[str, BaseTool] = {}
        self.tool_views: Dict[str, ttk.Frame] = {}
        self.tool_scrollers: Dict[str, ScrollablePanel] = {}
        self.nav_buttons: Dict[str, tk.Button] = {}
        self.current_tool: Optional[str] = None
        self._tool_order: list[str] = []
        self._register_tools()

        self.navigation = NavigationRail(
            self.sidebar,
            on_select=self.switch_view,
            motion=self._motion,
        )
        self.navigation.pack(fill="both", expand=True)
        self._build_navigation()
        self.nav_buttons = self.navigation.buttons

        footer = tk.Frame(self.sidebar, background=PALETTE.sidebar)
        footer.pack(fill="x", padx=20, pady=(10, 18))
        tk.Label(
            footer,
            text="●  LOCAL-FIRST",
            background=PALETTE.sidebar,
            foreground="#5ED4AE",
            font=(FONT_FAMILY, 8, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            footer,
            text="Files stay on this device",
            background=PALETTE.sidebar,
            foreground="#8E9AAF",
            font=(FONT_FAMILY, 8),
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        self.status_bar = ttk.Frame(self, style="Status.TFrame", padding=(18, 8))
        self.status_bar.grid(row=1, column=1, sticky="ew")
        self.status_lbl = ttk.Label(
            self.status_bar,
            text="Ready",
            style="StatusStrong.TLabel",
        )
        self.status_lbl.pack(side="left")
        ttk.Label(
            self.status_bar,
            text="●",
            style="Success.TLabel",
        ).pack(side="left", padx=(0, 7), before=self.status_lbl)

        if TkinterDnD:
            self.drop_lbl = ttk.Label(
                self.status_bar,
                text="Drop files or folders onto any file list",
                style="Status.TLabel",
            )
            self.drop_lbl.pack(side="right")

        if self._tool_order:
            self.switch_view(self._tool_order[0], animate=False)

    def _register_tools(self) -> None:
        for tool in build_tools_list():
            presentation_for(tool.name)
            self.tools[tool.name] = tool

    def _build_navigation(self) -> None:
        for group in NAVIGATION_GROUPS:
            group_tools = [
                name
                for name in self.tools
                if presentation_for(name).group == group
            ]
            if not group_tools:
                continue
            self.navigation.add_section(group)
            for tool_name in group_tools:
                self.navigation.add_item(tool_name, tool_name)
                self._tool_order.append(tool_name)

    def _create_tool_view(self, tool_id: str) -> ttk.Frame:
        tool = self.tools[tool_id]
        presentation = presentation_for(tool_id)
        container = ttk.Frame(self.main_area, style="View.TFrame")

        header = ttk.Frame(
            container,
            style="ToolHeader.TFrame",
            padding=(30, 17, 30, 12),
        )
        header.pack(fill="x")
        ttk.Label(
            header,
            text=f"WORKSPACE  /  {presentation.group.upper()}",
            style="Eyebrow.TLabel",
        ).pack(anchor="w")
        ttk.Label(header, text=tool.name, style="Header.TLabel").pack(
            anchor="w", pady=(5, 2)
        )
        ttk.Label(
            header,
            text=presentation.description,
            style="Subheader.TLabel",
            wraplength=responsive_wraplength(self),
        ).pack(anchor="w")

        body_border = tk.Frame(
            container,
            background=PALETTE.border,
            highlightthickness=0,
            padx=1,
            pady=1,
        )
        body_border.pack(fill="both", expand=True, padx=28, pady=(0, 22))
        scroller = ScrollablePanel(
            body_border,
            padding=(20, 13),
        )
        scroller.pack(fill="both", expand=True)
        tool.render(scroller.content)
        scroller.bind_mousewheel_tree()
        scroller.after_idle(scroller.refresh)
        self.tool_scrollers[tool_id] = scroller
        self.tool_views[tool_id] = container
        return container

    def switch_view(self, tool_id: str, *, animate: bool = True) -> None:
        """Show one cached tool view with a cancellable enter/exit transition."""

        if tool_id not in self.tools:
            raise KeyError(f"Unknown tool: {tool_id}")
        if self.current_tool == tool_id:
            return

        self._motion.cancel("view-switch")
        previous_id = self.current_tool
        previous_view = self.tool_views.get(previous_id) if previous_id else None
        incoming = self.tool_views.get(tool_id) or self._create_tool_view(tool_id)

        for name, view in self.tool_views.items():
            if name not in {previous_id, tool_id}:
                view.place_forget()

        old_index = self._tool_order.index(previous_id) if previous_id else 0
        new_index = self._tool_order.index(tool_id)
        direction = 1 if new_index >= old_index else -1
        if previous_view:
            previous_view.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=1.0)
        incoming.place(
            relx=0.034 * direction if previous_view and animate else 0.0,
            rely=0.0,
            relwidth=1.0,
            relheight=1.0,
        )
        incoming.lift()

        self.current_tool = tool_id
        self.navigation.select(tool_id, animate=animate)
        self.status_lbl.configure(text=f"Ready  ·  {tool_id}")

        def update(value: float) -> None:
            if previous_view:
                previous_view.place_configure(relx=-0.018 * direction * value)
            incoming.place_configure(relx=0.034 * direction * (1.0 - value))

        def complete() -> None:
            if previous_view:
                previous_view.place_forget()
            incoming.place_configure(relx=0.0)

        self._motion.animate(
            "view-switch",
            190 if animate else 0,
            update,
            on_complete=complete,
        )

    def _on_window_configure(self, event) -> None:
        if event.widget is not self or not hasattr(self, "drop_lbl"):
            return
        if event.width < 1000 and self.drop_lbl.winfo_manager():
            self.drop_lbl.pack_forget()
        elif event.width >= 1000 and not self.drop_lbl.winfo_manager():
            self.drop_lbl.pack(side="right")

    def _on_close(self) -> None:
        """Stop optional managed workers, then perform a short exit transition."""

        if self._closing:
            return
        self._closing = True
        self._motion.cancel_all()
        try:
            from src.ocr.deployment.providers import (
                shutdown_managed_unlimited_ocr_provider,
            )
            from src.ui.unlimited_ocr_setup import cancel_active_setups

            cancel_active_setups()
            shutdown_managed_unlimited_ocr_provider()
        finally:
            self._window_motion.close(on_complete=self.destroy)

    def destroy(self) -> None:
        self._motion.cancel_all()
        self._window_motion.controller.cancel_all()
        # Every tool shares this Tcl interpreter.  Cancel its remaining polling
        # callbacks before widget commands disappear, otherwise Tk can report
        # stale ``*_process_queue`` commands during an animated shutdown.
        widgets = [self]
        for widget in widgets:
            widgets.extend(widget.winfo_children())
        command_owners = {
            command: widget
            for widget in widgets
            for command in (getattr(widget, "_tclCommands", None) or ())
        }
        try:
            pending_callbacks = self.tk.call("after", "info")
        except tk.TclError:
            pending_callbacks = ()
        for callback_id in pending_callbacks:
            try:
                callback_info = self.tk.call("after", "info", callback_id)
                command = str(callback_info[0]).split(maxsplit=1)[0]
                owner = command_owners.get(command)
                if owner is None:
                    self.tk.call("after", "cancel", callback_id)
                else:
                    owner.after_cancel(callback_id)
            except tk.TclError:
                pass
        super().destroy()


def main() -> int:
    """Start the GUI and avoid printing raw Tk/Tcl tracebacks to users."""

    try:
        app = PDFToolkitApp()
    except tk.TclError:
        print(gui_startup_error_message(), file=sys.stderr)
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
