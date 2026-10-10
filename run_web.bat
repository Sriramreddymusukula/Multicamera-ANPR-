@echo off
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir "%~dp0web\backend" --host 127.0.0.1 --port 8000
