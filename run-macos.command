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

echo "Checking and syncing dependencies..."
if ! uv sync; then
  fail "Dependency setup failed. Please check the messages above."
fi

echo
echo "Opening the app..."
if ! uv run python src/app.py; then
  fail "The app closed with an error. Please check the messages above."
fi
