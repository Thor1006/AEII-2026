$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv and install backend/requirements.txt first.' }
Push-Location $projectRoot
try {
  & $pythonExe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
} finally {
  Pop-Location
}
