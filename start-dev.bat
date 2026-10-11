@echo off
rem ============================================================
rem  Non-motor Vehicle Violation Platform - one-click dev launcher
rem
rem  Starts the backend (FastAPI, port 8000) and the frontend
rem  (Vite dev server, port 5173) in two separate windows.
rem  Closing those two windows stops the services.
rem
rem  The SQLite database is created and migrated automatically by
rem  the backend on startup - no manual step needed. If the database
rem  is missing it is built from scratch; if it is present it is reused.
rem
rem  This file is 100 percent ASCII on purpose: the project folder name
rem  is non-ASCII and any hard-coded non-ASCII path would be garbled by
rem  cmd. Every path is derived from %~dp0 at run time.
rem ============================================================
setlocal
cd /d "%~dp0"

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "VENV_PY=%BACKEND%\.venv\Scripts\python.exe"
set "DB_FILE=%BACKEND%\storage\traffic.db"

title Non-motor Vehicle Violation Platform - Launcher

echo ============================================================
echo   Non-motor Vehicle Violation Platform
echo ------------------------------------------------------------
echo   Project root : %ROOT%
echo   Backend      : http://127.0.0.1:8000   (FastAPI + uvicorn)
echo   Frontend     : http://127.0.0.1:5173   (Vite dev server)
echo   Database     : backend\storage\traffic.db  (SQLite, auto-managed)
echo ============================================================
echo.

rem ------------------------------------------------------------
rem  Pre-flight checks: fail loudly with a readable reason instead
rem  of popping up a window that closes instantly.
rem ------------------------------------------------------------
set "MISSING="
if not exist "%VENV_PY%" set "MISSING=%MISSING% backend\.venv"
if not exist "%FRONTEND%\node_modules" set "MISSING=%MISSING% frontend\node_modules"

if not "%MISSING%"=="" (
  echo [ERROR] Missing required components: %MISSING%
  echo.
  echo   How to fix:
  echo     - backend\.venv       : run  backend\setup.ps1  ^(creates the venv + deps^)
  echo     - frontend\node_modules : run  npm install      inside the frontend folder
  echo.
  pause
  exit /b 1
)

echo [check] backend interpreter ...... OK
echo [check] frontend node_modules .... OK
if exist "%DB_FILE%" (
  echo [check] database file .......... found, will be reused
) else (
  echo [check] database file .......... not found, will be auto-created on backend start
)
echo.

rem ------------------------------------------------------------
rem  Launch backend, then frontend, in their own windows.
rem ------------------------------------------------------------
echo [1/2] starting backend  -^>  http://127.0.0.1:8000
start "traffic-backend" cmd /k "cd /d %ROOT%backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

rem small head-start delay; ping is used instead of timeout because some
rem shells on PATH shadow timeout.exe with a non-Windows implementation.
ping -n 4 127.0.0.1 >nul 2>&1

echo [2/2] starting frontend -^>  http://127.0.0.1:5173
start "traffic-frontend" cmd /k "cd /d %ROOT%frontend && npm run dev"

echo.
echo ------------------------------------------------------------
echo  Backend  API docs : http://127.0.0.1:8000/docs
echo  Backend  health   : http://127.0.0.1:8000/api/health
echo  Frontend          : http://127.0.0.1:5173
echo ------------------------------------------------------------
echo  To STOP: close the two windows titled
echo           "traffic-backend" and "traffic-frontend".
echo ------------------------------------------------------------
echo.
pause
endlocal
