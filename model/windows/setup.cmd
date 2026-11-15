@echo off
rem One-time setup of the model on Windows. Runs setup.ps1 for this run only, without changing Windows settings.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
pause
