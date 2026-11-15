<#
TrueRehab-RF model: train and count reps on Windows (after setup.ps1).

  model\windows\train.cmd E:\truerehab-sessions
  model\windows\train.ps1 -Sessions E:\truerehab-sessions -CopyFirst
  model\windows\train.ps1 -Sessions E:\truerehab-sessions -Device cpu -Epochs 40

-CopyFirst copies the sessions to model\data\sessions first (robocopy; only new or changed files) and trains from
that copy, so a drive that drops out mid-run can't break it. The run folders are copied next to the sessions
folder, into truerehab-runs\ (on the SSD), unless -NoCopyBack.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Sessions,
    [switch]$CopyFirst,
    [switch]$NoCopyBack,
    [string]$Device = "auto",
    [int]$Epochs = 0
)

$ErrorActionPreference = "Continue"   # see setup.ps1: each step checks $LASTEXITCODE
$Model = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Model ".venv\Scripts\python.exe"
$env:PYTHONUTF8 = "1"

function Say($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nSTOPPED: $text" -ForegroundColor Red; exit 1 }

if (-not (Test-Path $Py)) { Fail "model\.venv is missing: run model\windows\setup.cmd first" }
if (-not (Test-Path $Sessions)) { Fail "no folder $Sessions (is the SSD plugged in? check its drive letter in File Explorer)" }
$Sessions = (Resolve-Path $Sessions).Path
$found = @(Get-ChildItem -Path $Sessions -Directory | Where-Object { Test-Path (Join-Path $_.FullName "meta.json") })
if ($found.Count -eq 0) { Fail "no session folders (with a meta.json) in $Sessions" }
Write-Host "$($found.Count) session folders in $Sessions"
$SourceSessions = $Sessions

if ($CopyFirst) {
    $local = Join-Path $Model "data\sessions"
    Say "Copying the sessions to $local (only new or changed files)"
    robocopy $Sessions $local /E /XD '$RECYCLE.BIN' 'System Volume Information' /XF '._*' '.DS_Store' /NFL /NDL /NJH /NP /R:2 /W:2 | Out-Host
    if ($LASTEXITCODE -ge 8) { Fail "robocopy could not copy every file (code $LASTEXITCODE)" }
    $Sessions = $local
}

$started = Get-Date
$runs = Join-Path $Model "runs"
Push-Location $Model
try {
    Say "Training (5 people take about 7 min on a GPU, 1-2 h on the CPU)"
    $trainArgs = @("train.py", "--sessions", $Sessions, "--device", $Device)
    if ($Epochs -gt 0) { $trainArgs += @("--epochs", "$Epochs") }
    & $Py @trainArgs
    if ($LASTEXITCODE -ne 0) { Fail "train.py stopped (code $LASTEXITCODE). Send the lines above to Claude." }

    Say "Radar rep counter"
    & $Py armtrack.py --sessions $Sessions
    if ($LASTEXITCODE -ne 0) { Fail "armtrack.py stopped (code $LASTEXITCODE). Send the lines above to Claude." }
} finally { Pop-Location }

$new = @(Get-ChildItem -Path $runs -Directory | Where-Object { $_.LastWriteTime -ge $started -and $_.Name -ne "checks" })
Say "New run folders"
$new | ForEach-Object { Write-Host "  $($_.FullName)" }

if (-not $NoCopyBack -and $new.Count -gt 0) {
    $back = Join-Path (Split-Path -Parent $SourceSessions) "truerehab-runs"
    Say "Copying them to $back"
    foreach ($r in $new) {
        robocopy $r.FullName (Join-Path $back $r.Name) /E /NFL /NDL /NJH /NJS /NP /R:2 /W:2 | Out-Null
        if ($LASTEXITCODE -ge 8) { Write-Host "  could not copy $($r.Name) (code $LASTEXITCODE)" -ForegroundColor Yellow }
        else { Write-Host "  $($r.Name)" }
    }
}
Write-Host "`nDONE. Each run's report.md is in its folder." -ForegroundColor Green
