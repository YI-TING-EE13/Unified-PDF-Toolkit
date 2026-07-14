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

set "PYTHON_VERSION=3.12"

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

if not exist "scripts\repair_project_venv.py" (
  echo Error: scripts\repair_project_venv.py was not found. Please make sure you downloaded and unzipped the full project folder.
  echo.
  pause
  exit /b 1
)

echo Ensuring Python %PYTHON_VERSION% is available...
uv python install %PYTHON_VERSION%
if errorlevel 1 (
  echo.
  echo Error: Python %PYTHON_VERSION% setup failed. Please check the messages above.
  echo.
  pause
  exit /b 1
)

set "PYTHON_EXE="
for /f "usebackq delims=" %%P in (`uv python find --no-project --managed-python %PYTHON_VERSION% 2^>nul`) do set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE (
  echo.
  echo Error: Python %PYTHON_VERSION% was installed but could not be located.
  echo.
  pause
  exit /b 1
)

echo Checking the project environment for incomplete package metadata...
"%PYTHON_EXE%" scripts\repair_project_venv.py --venv .venv
if errorlevel 1 (
  echo.
  echo Error: The project environment could not be repaired. Please check the messages above.
  echo.
  pause
  exit /b 1
)

echo Checking and syncing dependencies...
uv sync --python "%PYTHON_EXE%"
if errorlevel 1 (
  echo.
  echo Error: Dependency setup failed. Please check the messages above.
  echo.
  pause
  exit /b 1
)

echo.
echo Opening the app...
uv run --no-sync --python "%PYTHON_EXE%" python src/app.py
if errorlevel 1 (
  echo.
  echo Error: The app closed with an error. Please check the messages above.
  echo.
  pause
  exit /b 1
)
