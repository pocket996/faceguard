@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_app.py %*
) else (
    py -3 run_app.py %*
)
if errorlevel 1 pause
