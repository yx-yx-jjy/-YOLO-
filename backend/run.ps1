$ErrorActionPreference = 'Stop'
$backendRoot = $PSScriptRoot
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
  throw 'Backend virtual environment is missing. Run setup.ps1 first.'
}

& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir $backendRoot

