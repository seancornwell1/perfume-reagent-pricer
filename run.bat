@echo off
REM Double-click to run. First run sets up a private Python environment (.venv).
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

if not exist ".venv\Scripts\python.exe" (
    echo Setting up for first run...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo.
        echo Python was not found. Install Python 3.9+ from https://www.python.org/downloads/
        echo and tick "Add python.exe to PATH" during install, then run this again.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
)

".venv\Scripts\python.exe" -m pricer %*
echo.
pause
