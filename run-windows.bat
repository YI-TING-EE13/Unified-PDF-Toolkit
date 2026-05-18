@echo off
setlocal

if /I not "%OS%"=="Windows_NT" (
  echo Error: This launcher is for Windows only. On macOS, use run-macos.command.
  echo.
  pause
  exit /b 1
)

cd /d "%~dp0" || (
  echo Error: Could not open the project folder.
  echo.
  pause
  exit /b 1
)

echo Starting Unified PDF Toolkit...
echo Project folder: %CD%
echo.

where uv >nul 2>nul
if errorlevel 1 (
  echo uv was not found on this Windows computer.
  echo.
  echo Please install uv first, then double-click this file again:
  echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 ^| iex"
  echo.
  echo After installing uv, close and reopen this window, or restart Windows if the command is still not found.
  echo.
  pause
  exit /b 1
)

if not exist "src\app.py" (
  echo Error: src\app.py was not found. Please make sure you downloaded and unzipped the full project folder.
  echo.
  pause
  exit /b 1
)

echo Checking and syncing dependencies...
uv sync
if errorlevel 1 (
  echo.
  echo Error: Dependency setup failed. Please check the messages above.
  echo.
  pause
  exit /b 1
)

echo.
echo Opening the app...
uv run python src/app.py
if errorlevel 1 (
  echo.
  echo Error: The app closed with an error. Please check the messages above.
  echo.
  pause
  exit /b 1
)
