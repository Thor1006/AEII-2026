<#
TrueRehab-RF model: one-time setup on Windows (PowerShell 5.1 or 7).

  model\windows\setup.cmd            (double-click, or run from a terminal)
  model\windows\setup.ps1 -Cpu       (CPU build of PyTorch even with an NVIDIA card)
  model\windows\setup.ps1 -Cuda cu128 (pick the CUDA build yourself)

Makes model\.venv, installs numpy and PyTorch (the CUDA build if nvidia-smi finds an NVIDIA card, else the CPU
build) and runs the model's tests. Downloads: about 2.5 GB with CUDA, about 200 MB without. Nothing is installed
outside model\.venv; delete that folder to undo it.
#>
param([switch]$Cpu, [string]$Cuda = "")

# "Continue", not "Stop": Windows PowerShell 5.1 would turn any program's stderr into a crash; every step checks
# $LASTEXITCODE itself instead.
$ErrorActionPreference = "Continue"
$Model = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Model ".venv"
$Py = Join-Path $Venv "Scripts\python.exe"

function Say($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nSTOPPED: $text" -ForegroundColor Red; exit 1 }

# ------------------------------------------------------------------ 1. Python 3.10 or newer
Say "Looking for Python 3.10 or newer"
$base = $null
foreach ($line in @("py -3", "python", "python3")) {
    $cand = $line.Split(" ")
    $exe = $cand[0]
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $args0 = @()
    if ($cand.Count -gt 1) { $args0 = @($cand[1..($cand.Count - 1)]) }
    try {
        $ver = & $exe @args0 -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    } catch { continue }
    $ver = "$ver".Trim()
    if ($ver -notmatch '^3\.(\d+)$') { continue }   # the Microsoft Store stub prints nothing useful
    if ([int]$Matches[1] -ge 10) { $base = @($exe) + $args0; Write-Host "found Python $ver ($exe)"; break }
    Write-Host "Python $ver ($exe) is too old"
}
if (-not $base) {
    Fail "no Python 3.10+ found. Install Python 3.12 from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH'), open a new terminal and run this again."
}

# ------------------------------------------------------------------ 2. model\.venv
if (Test-Path $Py) {
    Say "model\.venv already exists: reusing it"
} else {
    Say "Making model\.venv"
    $exe = $base[0]; $rest = @(); if ($base.Count -gt 1) { $rest = $base[1..($base.Count - 1)] }
    & $exe @rest -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Fail "python -m venv failed" }
}
& $Py -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { Fail "pip could not upgrade itself (no internet?)" }
& $Py -m pip install numpy
if ($LASTEXITCODE -ne 0) { Fail "numpy did not install" }

# ------------------------------------------------------------------ 3. PyTorch: CUDA build if an NVIDIA card is there
$builds = @()
if (-not $Cpu) {
    if ($Cuda) {
        $builds = @($Cuda)
    } elseif (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        $smi = (& nvidia-smi 2>$null) -join "`n"
        $m = [regex]::Match($smi, "CUDA Version:\s*(\d+)\.(\d+)")
        $gpu = (& nvidia-smi --query-gpu=name --format=csv,noheader 2>$null) -join ", "
        if ($m.Success) {
            $driver = [int]$m.Groups[1].Value * 10 + [int]$m.Groups[2].Value
            Write-Host "NVIDIA card: $gpu; its driver supports CUDA $($m.Groups[1].Value).$($m.Groups[2].Value)"
            # newest first; only builds this driver can run (cu128 = CUDA 12.8)
            foreach ($b in @("cu130", "cu129", "cu128", "cu126", "cu124", "cu121", "cu118")) {
                if ([int]$b.Substring(2) -le $driver) { $builds += $b }
            }
        } else {
            Write-Host "nvidia-smi is there but shows no CUDA version: using the CPU build"
        }
    } else {
        Write-Host "No NVIDIA card found (no nvidia-smi): using the CPU build. Training will be slower (about 1-2 h)."
    }
}

$haveTorch = (& $Py -c "import torch; print(torch.__version__)" 2>$null)
$ok = $false
if ($haveTorch) {
    $cudaNow = (& $Py -c "import torch; print(torch.cuda.is_available())" 2>$null)
    if ($builds.Count -eq 0 -or $cudaNow -eq "True") { Say "PyTorch $haveTorch already installed (CUDA: $cudaNow)"; $ok = $true }
}
if (-not $ok) {
    foreach ($b in $builds) {
        Say "Installing PyTorch, CUDA build $b (about 2.5 GB)"
        & $Py -m pip install torch --index-url "https://download.pytorch.org/whl/$b"
        if ($LASTEXITCODE -eq 0) {
            $cudaNow = (& $Py -c "import torch; print(torch.cuda.is_available())" 2>$null)
            if ($cudaNow -eq "True") { $ok = $true; break }
            Write-Host "installed, but PyTorch can't use the card with build $b; trying the next one"
            & $Py -m pip uninstall -y torch | Out-Null
        } else {
            Write-Host "no $b build for this Python; trying the next one"
        }
    }
    if (-not $ok) {
        if ($builds.Count -gt 0) { Write-Host "No CUDA build worked: falling back to the CPU build" -ForegroundColor Yellow }
        Say "Installing PyTorch, CPU build (about 200 MB)"
        & $Py -m pip install torch --index-url "https://download.pytorch.org/whl/cpu"
        if ($LASTEXITCODE -ne 0) { Fail "PyTorch did not install. Send the lines above to Claude." }
    }
}

# ------------------------------------------------------------------ 4. What training will use, then the tests
Say "Check"
& $Py -c "import sys, numpy, torch; print('python', sys.version.split()[0], '| numpy', numpy.__version__, '| torch', torch.__version__); print('training will run on:', 'NVIDIA GPU (' + torch.cuda.get_device_name(0) + ')' if torch.cuda.is_available() else 'CPU')"
if ($LASTEXITCODE -ne 0) { Fail "PyTorch does not load. Send the lines above to Claude." }

Say "Running the model's tests (about 1 min; real-recording tests are skipped here)"
$env:PYTHONUTF8 = "1"
Push-Location $Model
try {
    & $Py -m unittest discover -s tests
    $code = $LASTEXITCODE
} finally { Pop-Location }
if ($code -ne 0) { Fail "some tests failed. Send the lines above to Claude." }

Write-Host "`nSETUP OK. Next: model\windows\train.cmd E:\truerehab-sessions  (use your SSD's drive letter)" -ForegroundColor Green
