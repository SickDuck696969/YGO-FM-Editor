@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m fm_editor
) else (
  py -3 -m fm_editor
)
if errorlevel 1 pause
