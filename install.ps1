$ErrorActionPreference = "Stop"

Write-Host "=============================================="
Write-Host "       CloudHime Automated Installer"
Write-Host "=============================================="
Write-Host ""

$condaPath = "$env:USERPROFILE\Miniconda3"
$condaExe = "$condaPath\Scripts\conda.exe"

# 1. Install Conda if not found
if (-not (Test-Path $condaExe)) {
    Write-Host "[1/5] Miniconda not found. Downloading..."
    $installerUrl = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
    $installerPath = "$env:TEMP\miniconda_installer.exe"
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
    
    Write-Host "[1/5] Installing Miniconda silently (this may take a few minutes)..."
    Start-Process -FilePath $installerPath -ArgumentList "/InstallationType=JustMe /RegisterPython=0 /S /D=$condaPath" -Wait -NoNewWindow
    Remove-Item $installerPath -Force
    Write-Host "[1/5] Miniconda installation complete."
} else {
    Write-Host "[1/5] Miniconda found at $condaPath."
}

# 2. Setup Conda Environment
$envName = "cloudhime_env"
Write-Host "[2/5] Setting up conda environment '$envName'..."

# Check if env exists
$envList = & $condaExe env list
if ($envList -notmatch $envName) {
    Write-Host "      Creating new environment..."
    & $condaExe create -y -n $envName python=3.13
} else {
    Write-Host "      Environment '$envName' already exists."
}

# 3. Install core dependencies (llama-cpp-python via conda-forge for automatic CUDA support)
Write-Host "[3/5] Installing core dependencies (llama-cpp-python)..."
& $condaExe install -y -n $envName -c conda-forge llama-cpp-python

# 4. Install other dependencies via pip
Write-Host "[4/5] Installing requirements.txt via pip..."
$pipExe = "$condaPath\envs\$envName\Scripts\pip.exe"
if (Test-Path "$PSScriptRoot\requirements.txt") {
    & $pipExe install -r "$PSScriptRoot\requirements.txt"
} else {
    Write-Host "      requirements.txt not found! Skipping pip install."
}

# 5. Download Local Model
Write-Host "[5/5] Checking local Gemma model..."
$modelDir = "$PSScriptRoot\models"
$modelFile = "gemma-3-4b-it.Q4_K_M.gguf"
$modelUrl = "https://huggingface.co/mradermacher/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it.Q4_K_M.gguf"
$modelPath = Join-Path $modelDir $modelFile

if (-not (Test-Path $modelDir)) {
    New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
}

if (-not (Test-Path $modelPath)) {
    Write-Host "      Model not found. Downloading (approx 1.8GB)..."
    Write-Host "      This might take a while depending on your internet connection."
    Invoke-WebRequest -Uri $modelUrl -OutFile $modelPath
    Write-Host "      Model download complete."
} else {
    Write-Host "      Model already exists!"
}

Write-Host ""
Write-Host "=============================================="
Write-Host " Installation Complete! You can now start CloudHime."
Write-Host "=============================================="
Write-Host ""
