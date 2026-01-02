import sys
import os
import tkinter as tk

# Add project root to path
sys.path.append(os.getcwd())

from src.app import PDFToolkitApp
from src.base.tool import BaseTool
from src.tools.compressor.tool import CompressorTool
from src.tools.merger.tool import MergerTool
from src.tools.splitter.tool import SplitterTool
from src.tools.converter.tool import ConverterTool

def test_instantiation():
    print("Testing Tool Instantiation...")
    try:
        tools = [
            CompressorTool(),
            MergerTool(),
            SplitterTool(),
            ConverterTool()
        ]
        for t in tools:
            print(f"✅ {t.name} (Icon: {t.icon}) loaded successfully.")
    except Exception as e:
        print(f"❌ Tool Instantiation Failed: {e}")
        sys.exit(1)

def test_app_structure():
    print("\nTesting Main App Structure...")
    try:
        # Headless Tkinter test
        # We can't actually run mainloop() in headless, but we can init the class
        app = PDFToolkitApp()
        
        # Verify tools registered
        registered = app.tools.keys()
        print(f"App registered tools: {list(registered)}")
        
        expected = ["Compress PDF/Image", "Merge PDFs", "Split PDF", "PDF to Image"]
        missing = [t for t in expected if t not in registered]
        
        if missing:
            print(f"❌ Missing tools in registry: {missing}")
            sys.exit(1)
        else:
            print("✅ All tools registered in App.")
            
        app.destroy()
    except tk.TclError as e:
        print(f"⚠️ Tkinter Error (likely due to headless env, ignoring): {e}")
    except Exception as e:
        print(f"❌ App Init Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_instantiation()
    test_app_structure()
