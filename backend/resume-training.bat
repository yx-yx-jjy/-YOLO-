@echo off
rem ============================================================
rem  Start / resume the yolo11s-wuhan-manual-v3 training run.
rem
rem  This launches train-watchdog.py, which keeps restarting the
rem  trainer from last.pt whenever it dies. That is needed on this
rem  machine because host commit memory is nearly exhausted and the
rem  trainer gets killed by allocation failures every few epochs.
rem
rem  A lock file prevents two watchdogs from running at once, so an
rem  accidental double launch is harmless.
rem
rem  All paths derive from %~dp0 - the project folder name is
rem  non-ASCII and hardcoding it in a .bat garbles the text.
rem ============================================================
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"
set "WATCHDOG=%~dp0train-watchdog.py"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

if not exist "%PY%" (
  echo [ERROR] venv python not found:
  echo   %PY%
  pause
  exit /b 1
)
if not exist "%WATCHDOG%" (
  echo [ERROR] watchdog script not found:
  echo   %WATCHDOG%
  pause
  exit /b 1
)

echo ============================================================
echo  YOLO training watchdog - yolo11s-wuhan-manual-v3
echo ------------------------------------------------------------
echo  Target : 100 epochs
echo  batch=1  imgsz=960  device=0
echo  It resumes from last.pt automatically after a crash.
echo ============================================================
echo.
echo  Press Ctrl+C to cancel, otherwise it starts in 10s.
echo.
timeout /t 10

echo.
echo [starting] %DATE% %TIME%
echo.

"%PY%" "%WATCHDOG%"

echo.
echo [watchdog exited] code = %ERRORLEVEL%   %DATE% %TIME%
echo.
echo Progress : runs\violation\yolo11s-wuhan-manual-v3\results.csv
echo Live log : runs\violation\wuhan-manual-v3-resume.out.log
echo.
pause
