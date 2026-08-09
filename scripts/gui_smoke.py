"""Headed GUI smoke test for local desktop release checks."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if "--reduce-motion" in sys.argv:
    os.environ["PDF_TOOLKIT_REDUCE_MOTION"] = "1"

import tkinter as tk  # noqa: E402

from src.app import PDFToolkitApp, gui_startup_error_message  # noqa: E402
from src.ui.advanced_ocr_consent import AdvancedOcrConsentDialog  # noqa: E402
from src.ui.components import ResponsiveSplit  # noqa: E402


def pump_events(app: PDFToolkitApp, seconds: float) -> None:
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        app.update_idletasks()
        app.update()
        time.sleep(0.01)


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def main() -> int:
    try:
        app = PDFToolkitApp()
    except tk.TclError:
        print("[ERROR] GUI unavailable")
        print(gui_startup_error_message())
        return 2
    try:
        pump_events(app, 0.22)
        if "--reduce-motion" in sys.argv and app._motion.enabled:
            raise RuntimeError("Reduced-motion mode did not disable application tweens.")
        for tool_id in list(app.tools.keys()):
            app.switch_view(tool_id)
            pump_events(app, 0.23)
            if app.current_tool != tool_id:
                raise RuntimeError(f"View switch did not settle on {tool_id}.")
            if not app.tool_views[tool_id].winfo_ismapped():
                raise RuntimeError(f"View was not visible after switching to {tool_id}.")

            responsive_splits = [
                widget
                for widget in descendants(app.tool_views[tool_id])
                if isinstance(widget, ResponsiveSplit)
            ]
            for split in responsive_splits:
                if split.compact:
                    split.select("secondary")
                    pump_events(app, 0.03)
                    if not split.secondary.winfo_ismapped():
                        raise RuntimeError("Could not show compact secondary pane.")
                    split.select("primary")
                    pump_events(app, 0.03)
                    if not split.primary.winfo_ismapped():
                        raise RuntimeError("Could not restore compact primary pane.")

            scroller = app.tool_scrollers[tool_id]
            if scroller.scrollbar.winfo_ismapped():
                scroller.canvas.yview_moveto(1.0)
                pump_events(app, 0.03)
                if scroller.canvas.yview()[1] < 0.99:
                    raise RuntimeError(f"Could not reach the bottom of {tool_id}.")
                scroller.canvas.yview_moveto(0.0)
            print(f"[OK] Rendered {tool_id}")

        tool_ids = list(app.tools)
        for tool_id in tool_ids:
            app.switch_view(tool_id)
        pump_events(app, 0.28)
        final_tool = tool_ids[-1]
        visible = [
            tool_id
            for tool_id, view in app.tool_views.items()
            if view.winfo_ismapped()
        ]
        if app.current_tool != final_tool or app.navigation.active_item != final_tool:
            raise RuntimeError("Rapid switching left navigation and content out of sync.")
        if visible != [final_tool]:
            raise RuntimeError(f"Rapid switching left unexpected visible views: {visible}")
        if "view-switch" in app._motion.active_keys:
            raise RuntimeError("View animation did not settle after rapid switching.")
        print("[OK] Rapid view switching cancelled superseded animations")

        all_splits = [
            widget for widget in descendants(app) if isinstance(widget, ResponsiveSplit)
        ]
        for split in all_splits:
            split.reflow(1100)
        if any(
            split.compact
            or split.primary.winfo_manager() != "grid"
            or split.secondary.winfo_manager() != "grid"
            for split in all_splits
        ):
            states = [
                (split.compact, split.primary.winfo_manager(), split.secondary.winfo_manager())
                for split in all_splits
            ]
            raise RuntimeError(
                f"Responsive split did not expose both wide panes: {states}"
            )
        for split in all_splits:
            split.reflow(780)
        if any(
            not split.compact
            or split.primary.winfo_manager() != "grid"
            or split.secondary.winfo_manager()
            for split in all_splits
        ):
            raise RuntimeError("Responsive split did not return to compact tabs.")
        print(f"[OK] Responsive reflow for {len(all_splits)} split layouts")

        consent_dialog = AdvancedOcrConsentDialog(app)
        pump_events(app, 0.22)
        if float(consent_dialog.attributes("-alpha")) < 0.99:
            raise RuntimeError("Consent dialog entrance animation did not settle.")
        consent_dialog._cancel()
        pump_events(app, 0.16)
        if consent_dialog.winfo_exists():
            raise RuntimeError("Consent dialog exit animation did not destroy the window.")
        print("[OK] Consent dialog entrance and exit")

        print(
            f"[OK] Responsive shell {app.winfo_width()}x{app.winfo_height()} "
            f"with {len(app.navigation.buttons)} navigation items"
        )
        mode = "reduced" if not app._motion.enabled else "animated"
        print(f"[OK] Motion mode: {mode}")
        print(f"[OK] Rendered {len(app.tools)} tools")

        app._on_close()
        try:
            pump_events(app, 0.2)
        except tk.TclError:
            pass
        try:
            window_exists = bool(app.winfo_exists())
        except tk.TclError:
            window_exists = False
        if window_exists:
            raise RuntimeError("Application exit animation did not destroy the window.")
        print("[OK] Application exit animation")
        return 0
    finally:
        try:
            if app.winfo_exists():
                app.destroy()
        except tk.TclError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
