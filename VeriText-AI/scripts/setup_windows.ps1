<#
.SYNOPSIS
    VeriText AI — one-shot environment setup for Windows (Conda + CUDA PyTorch + deps + frontend).

.DESCRIPTION
    Creates (or reuses) a dedicated Conda environment, verifies the CUDA-enabled PyTorch
    installation instead of blindly reinstalling it, installs the backend requirements,
    installs the frontend packages, builds the UI and runs the environment check.

    Nothing here installs a CPU-only PyTorch wheel, and an existing working CUDA
    environment is left untouched.

.PARAMETER EnvName
    Conda environment name. Default: veritext

.PARAMETER PythonVersion
    Python version used when creating the environment. Default: 3.11

.PARAMETER ReuseExisting
    Skip environment creation and install into the currently activated environment
    (use this when you already have a working CUDA PyTorch setup).

.PARAMETER CudaIndex
    PyTorch index URL suffix, e.g. cu124 / cu121 / cu118. Default: cu124

.PARAMETER SkipFrontend
    Do not install Node packages or build the frontend.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 -ReuseExisting
#>

[CmdletBinding()]
param(
    [string]$EnvName = "veritext",
    [string]$PythonVersion = "3.11",
    [switch]$ReuseExisting,
    [string]$CudaIndex = "cu124",
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

function Write-Step($message) { Write-Host "`n=== $message ===" -ForegroundColor Cyan }
function Write-Ok($message)   { Write-Host "[ ok ] $message" -ForegroundColor Green }
function Write-Warn2($message){ Write-Host "[warn] $message" -ForegroundColor Yellow }

Write-Step "VeriText AI setup (Windows)"
Write-Host "Project root: $Root"

# ---------------------------------------------------------------- prerequisites
foreach ($tool in @("conda", "python", "node", "npm")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "'$tool' was not found in PATH. Install it first (Miniconda / Node.js 18+) and reopen PowerShell."
    }
}
Write-Ok "conda, python, node and npm are available"

if (-not $ReuseExisting) {
    Write-Step "Conda environment: $EnvName (Python $PythonVersion)"
    $existing = conda env list | Select-String -Pattern "^$EnvName\s"
    if ($existing) {
        Write-Ok "Environment '$EnvName' already exists — reusing it"
    } else {
        conda create -n $EnvName "python=$PythonVersion" -y
        if ($LASTEXITCODE -ne 0) { throw "conda create failed" }
        Write-Ok "Environment '$EnvName' created"
    }

    # 'conda activate' only works inside an initialised shell; call the environment's
    # python directly so the script behaves the same in any terminal.
    $envPython = (conda run -n $EnvName python -c "import sys; print(sys.executable)").Trim()
    Write-Ok "Using interpreter: $envPython"
} else {
    $envPython = (Get-Command python).Source
    Write-Ok "Reusing the current environment: $envPython"
}

function Invoke-EnvPython([string[]]$Arguments) {
    if ($ReuseExisting) { & python @Arguments } else { & conda run -n $EnvName python @Arguments }
    return $LASTEXITCODE
}

# --------------------------------------------------------------------- PyTorch
Write-Step "PyTorch (CUDA) check"
$torchProbe = @'
import sys
try:
    import torch
    print(f"{torch.__version__}|{torch.version.cuda}|{torch.cuda.is_available()}")
except Exception as exc:
    print(f"MISSING|{type(exc).__name__}|False")
'@
$probeFile = Join-Path $env:TEMP "veritext_torch_probe.py"
Set-Content -Path $probeFile -Value $torchProbe -Encoding UTF8
$torchInfo = (& (Get-Command python).Source $probeFile) 2>$null
if (-not $torchInfo -and -not $ReuseExisting) {
    $torchInfo = (conda run -n $EnvName python $probeFile).Trim()
}
$parts = "$torchInfo".Trim().Split("|")
$torchVersion = $parts[0]; $cudaBuild = $parts[1]; $cudaAvailable = $parts[2]

if ($torchVersion -eq "MISSING") {
    Write-Warn2 "PyTorch is not installed — installing the CUDA $CudaIndex wheel"
    Invoke-EnvPython @("-m", "pip", "install", "torch", "--index-url", "https://download.pytorch.org/whl/$CudaIndex") | Out-Null
} elseif ($cudaBuild -eq "None") {
    Write-Warn2 "PyTorch $torchVersion is a CPU-only build — installing the CUDA $CudaIndex wheel"
    Write-Warn2 "If you already have a working GPU environment, stop here and re-run with -ReuseExisting"
    Invoke-EnvPython @("-m", "pip", "install", "--upgrade", "torch", "--index-url", "https://download.pytorch.org/whl/$CudaIndex") | Out-Null
} elseif ($cudaAvailable -ne "True") {
    Write-Warn2 "PyTorch $torchVersion (+$cudaBuild) is installed but CUDA is not available."
    Write-Warn2 "The backend will run on CPU. Update the NVIDIA driver, then re-run this script."
} else {
    Write-Ok "PyTorch $torchVersion with CUDA $cudaBuild — GPU detected, leaving it untouched"
}

# ---------------------------------------------------------------- backend deps
Write-Step "Backend requirements (torch is not touched)"
Push-Location $Backend
try {
    Invoke-EnvPython @("-m", "pip", "install", "-r", "requirements-dev.txt") | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    Write-Ok "Backend dependencies installed"

    Write-Step "Environment verification"
    Invoke-EnvPython @("check_environment.py") | Out-Null
} finally {
    Pop-Location
}

# -------------------------------------------------------------------- frontend
if (-not $SkipFrontend) {
    Write-Step "Frontend (npm install + build)"
    Push-Location $Frontend
    try {
        npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
        Write-Ok "Frontend built into frontend\dist"
    } finally {
        Pop-Location
    }
}

Write-Step "Done"
if ($ReuseExisting) {
    Write-Host "Start the app:  cd backend; python app.py      ->  http://localhost:5000"
} else {
    Write-Host "Start the app:  conda activate $EnvName; cd backend; python app.py  ->  http://localhost:5000"
}
Write-Host "Dev UI:         cd frontend; npm run dev       ->  http://localhost:5173"
