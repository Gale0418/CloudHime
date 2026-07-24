$ErrorActionPreference = "Stop"

Write-Host "=============================================="
Write-Host "       CloudHime Source Development Setup"
Write-Host "=============================================="
Write-Host ""
Write-Host "這是原始碼開發環境腳本，不是 Microsoft Store 安裝器。"
Write-Host "CloudHime 不需要 Ollama、外部模型服務或使用者手動啟動 server。"
Write-Host ""

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $projectRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    throw "找不到 Python。請先安裝 Python 3.10 或更新版本，再重新執行此腳本。"
}

$pythonVersionOutput = & $pythonCommand.Source --version 2>&1
if ($pythonVersionOutput -notmatch "Python\s+(\d+)\.(\d+)") {
    throw "無法判斷 Python 版本，請安裝 Python 3.10 或更新版本。"
}
$pythonMajor = [int]$Matches[1]
$pythonMinor = [int]$Matches[2]
if (($pythonMajor -lt 3) -or (($pythonMajor -eq 3) -and ($pythonMinor -lt 10))) {
    throw "Python 3.10 或更新版本是必要條件。"
}

if (-not (Test-Path $pythonExe)) {
    Write-Host "[1/2] 建立本機開發用 Python 虛擬環境..."
    & $pythonCommand.Source -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        throw "建立 .venv 失敗。"
    }
} else {
    Write-Host "[1/2] 已找到 .venv。"
}

Write-Host "[2/2] 安裝 requirements.txt..."
& $pythonExe -m pip install -r (Join-Path $projectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "requirements.txt 安裝失敗。"
}

Write-Host ""
Write-Host "開發環境完成。執行 run.bat 或使用 .venv\Scripts\python.exe CloudHime.py。"
Write-Host "本地 Gemma 的 runtime 由程式隨附；模型與 projector 會由 CloudHime 管理到使用者 AppData。"
Write-Host "正式發行請使用 build_exe.bat / MSIX 流程，不要把 .venv 或 models/ 帶進發行包。"
