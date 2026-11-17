@echo off
"%~dp0..\..\work\venv\Scripts\python.exe" "%~dp0app.py"
if errorlevel 1 pause
