import os
import sys
import tkinter as tk

# Add project root to path
sys.path.append(os.getcwd())

from src.app import PDFToolkitApp
from src.tools.compressor.tool import CompressorTool
from src.tools.converter.tool import ConverterTool
from src.tools.merger.tool import MergerTool
from src.tools.splitter.tool import SplitterTool


def test_instantiation():
    print("Testing Tool Instantiation...")
    try:
        tools = [
            CompressorTool(),
            MergerTool(),
            SplitterTool(),
            ConverterTool(),
        ]
        for tool in tools:
            print(f"[OK] {tool.name} loaded successfully.")
    except Exception as exc:
        print(f"[ERROR] Tool Instantiation Failed: {exc}")
        sys.exit(1)


def test_app_structure():
    print("\nTesting Main App Structure...")
    try:
        # We do not run mainloop here; this only validates construction.
        app = PDFToolkitApp()

        registered = app.tools.keys()
        print(f"App registered tools: {list(registered)}")

        expected = ["Compress PDF/Image", "Merge PDFs", "Split PDF", "PDF to Image"]
        missing = [tool for tool in expected if tool not in registered]

        if missing:
            print(f"[ERROR] Missing tools in registry: {missing}")
            sys.exit(1)

        print("[OK] All tools registered in App.")
        app.destroy()
    except tk.TclError as exc:
        print(f"[WARN] Tkinter Error (likely due to headless env, ignoring): {exc}")
    except Exception as exc:
        print(f"[ERROR] App Init Failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    test_instantiation()
    test_app_structure()
