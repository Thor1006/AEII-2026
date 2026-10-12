$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv and install backend/requirements.txt first.' }
Push-Location $projectRoot
try {
  npm run build
  if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
  & $pythonExe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
} finally {
  Pop-Location
}
