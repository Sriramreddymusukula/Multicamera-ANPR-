@echo off
cd /d "%~dp0"
set "PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" -m uvicorn app.main:app --app-dir "%~dp0web\backend" --host 127.0.0.1 --port 8000
