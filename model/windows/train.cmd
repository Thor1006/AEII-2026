@echo off
rem Train and count reps: train.cmd E:\truerehab-sessions [-CopyFirst]
if "%~1"=="" (
  echo Usage: train.cmd E:\truerehab-sessions   ^(use your SSD drive letter^)
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0train.ps1" %*
pause
