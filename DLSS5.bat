@echo off
cd /d "%~dp0"
where pythonw.exe >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw.exe "%~dp0dlss5.py"
) else (
    python "%~dp0dlss5.py"
    if errorlevel 1 pause
)
