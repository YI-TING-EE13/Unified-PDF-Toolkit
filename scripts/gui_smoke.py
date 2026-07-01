"""Headed GUI smoke test for local desktop release checks."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tkinter as tk

from src.app import PDFToolkitApp, gui_startup_error_message


def main() -> int:
    try:
        app = PDFToolkitApp()
    except tk.TclError:
        print("[ERROR] GUI unavailable")
        print(gui_startup_error_message())
        return 2
    try:
        app.update_idletasks()
        for tool_id in list(app.tools.keys()):
            app.switch_view(tool_id)
            app.update_idletasks()
            app.update()
            print(f"[OK] Rendered {tool_id}")
        print(f"[OK] Rendered {len(app.tools)} tools")
        return 0
    finally:
        app.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
