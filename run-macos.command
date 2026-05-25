#!/bin/bash

set -u

pause_before_exit() {
  echo
  read -r -p "Press Enter to close this window..."
}

fail() {
  echo "Error: $1"
  pause_before_exit
  exit 1
}

if [ "$(uname -s)" != "Darwin" ]; then
  fail "This launcher is for macOS only. On Windows, run: uv run python src/app.py"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || fail "Could not open the project folder."

echo "Starting Unified PDF Toolkit..."
echo "Project folder: $SCRIPT_DIR"
echo

find_macos_python() {
  if [ -n "${PDF_TOOLKIT_PYTHON:-}" ] && [ -x "$PDF_TOOLKIT_PYTHON" ]; then
    echo "$PDF_TOOLKIT_PYTHON"
    return 0
  fi

  for candidate in \
    "/opt/homebrew/bin/python3.12" \
    "/usr/local/bin/python3.12" \
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"; do
    if [ -x "$candidate" ]; then
      echo "$candidate"
      return 0
    fi
  done

  return 1
}

if ! command -v uv >/dev/null 2>&1; then
  echo "uv was not found on this Mac."
  echo
  echo "Please install uv first, then double-click this file again:"
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo
  echo "After installing uv, close and reopen Terminal, or restart your Mac if the command is still not found."
  pause_before_exit
  exit 1
fi

if [ ! -f "src/app.py" ]; then
  fail "src/app.py was not found. Please make sure you downloaded and unzipped the full project folder."
fi

PYTHON_BIN="$(find_macos_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "A macOS Framework Python with a modern Tkinter is required for this desktop app."
  echo
  echo "The system /usr/bin/python3 uses an old Tcl/Tk runtime that can open a blank black window on recent macOS versions."
  echo "Install the Homebrew Tk-enabled Python runtime, then double-click this file again:"
  echo "  brew install python-tk@3.12"
  echo
  echo "Advanced: set PDF_TOOLKIT_PYTHON to another Python 3.12 executable with working tkinter."
  pause_before_exit
  exit 1
fi

TK_CHECK="$("$PYTHON_BIN" -c "import sys, tkinter; print(f'{sys.version_info.major}.{sys.version_info.minor} {tkinter.TkVersion}')" 2>/dev/null || true)"
if [ -z "$TK_CHECK" ]; then
  fail "The selected Python could not import tkinter: $PYTHON_BIN"
fi
if ! "$PYTHON_BIN" -c "import sys, tkinter; raise SystemExit(0 if sys.version_info >= (3, 10) and tkinter.TkVersion >= 8.6 else 1)" 2>/dev/null; then
  fail "The selected Python must be Python 3.10+ with Tcl/Tk 8.6+; got: $TK_CHECK ($PYTHON_BIN)"
fi
if ! "$PYTHON_BIN" -c "import sys; raise SystemExit(0 if getattr(sys, '_framework', '') else 1)" 2>/dev/null; then
  fail "The selected Python must be a macOS Framework build so Tkinter can display windows correctly: $PYTHON_BIN"
fi

echo "Using Python: $PYTHON_BIN"
echo "Python/Tk: $TK_CHECK"
echo

PYTHON_BASE="$("$PYTHON_BIN" -c "import os, sys; print(os.path.realpath(sys.base_prefix))")"
if [ -x ".venv/bin/python" ]; then
  VENV_TK="$(".venv/bin/python" -c "import sys, tkinter; print(f'{sys.version_info.major}.{sys.version_info.minor} {tkinter.TkVersion}')" 2>/dev/null || true)"
  VENV_BASE="$(".venv/bin/python" -c "import os, sys; print(os.path.realpath(sys.base_prefix))" 2>/dev/null || true)"
  if [ -z "$VENV_TK" ] || [ "$VENV_BASE" != "$PYTHON_BASE" ] || ! ".venv/bin/python" -c "import sys, tkinter; raise SystemExit(0 if sys.version_info >= (3, 10) and tkinter.TkVersion >= 8.6 else 1)" 2>/dev/null; then
    echo "Rebuilding the virtual environment because the existing Python/Tk runtime is not suitable for macOS GUI display."
    rm -rf .venv
    echo
  fi
fi

echo "Checking and syncing dependencies..."
if ! uv sync --python "$PYTHON_BIN"; then
  fail "Dependency setup failed. Please check the messages above."
fi

echo
echo "Opening the app..."
if ! uv run --python "$PYTHON_BIN" python src/app.py; then
  fail "The app closed with an error. Please check the messages above."
fi
