@echo off
setlocal

echo Website Monitor - Starting setup...

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download it from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

:: Install/update dependencies
echo Installing dependencies...
.venv\Scripts\pip install -q -r requirements.txt

:: Run the monitor
echo Starting monitor...
.venv\Scripts\python monitor.py

pause
