[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\build\provenance"),
    [string[]]$PythonCommand = @("py", "-3.10-64")
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$buildRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "build"))
$output = [System.IO.Path]::GetFullPath($OutputDir)
$relativeOutput = [System.IO.Path]::GetRelativePath($buildRoot, $output)
$parentPrefix = ".." + [System.IO.Path]::DirectorySeparatorChar
$alternateParentPrefix = ".." + [System.IO.Path]::AltDirectorySeparatorChar
if (
    $relativeOutput -eq "." -or
    $relativeOutput -eq ".." -or
    [System.IO.Path]::IsPathRooted($relativeOutput) -or
    $relativeOutput.StartsWith($parentPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
    $relativeOutput.StartsWith($alternateParentPrefix, [System.StringComparison]::OrdinalIgnoreCase)
) {
    throw "OutputDir must be a strict child directory of $buildRoot."
}

$pathToCheck = $buildRoot
foreach ($segment in @($relativeOutput -split '[\\/]')) {
    if (Test-Path -LiteralPath $pathToCheck) {
        $item = Get-Item -LiteralPath $pathToCheck -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "OutputDir must not traverse a reparse point: $pathToCheck"
        }
    }
    $pathToCheck = Join-Path $pathToCheck $segment
}
if (Test-Path -LiteralPath $pathToCheck) {
    $item = Get-Item -LiteralPath $pathToCheck -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "OutputDir must not traverse a reparse point: $pathToCheck"
    }
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("cloudhime-release-provenance-" + [Guid]::NewGuid().ToString("N"))
$venv = Join-Path $tempRoot "venv"
$report = Join-Path $tempRoot "production-pip-report.json"
$sbom = Join-Path $tempRoot "production-sbom.cdx.json"
$python = $PythonCommand[0]
$pythonArguments = @()
if ($PythonCommand.Count -gt 1) { $pythonArguments = $PythonCommand[1..($PythonCommand.Count - 1)] }

try {
    & $python @pythonArguments -c "import platform, sys; assert sys.implementation.name == 'cpython'; assert sys.version_info[:2] == (3, 10); assert sys.platform == 'win32'; assert platform.machine().lower() in ('amd64', 'x86_64')"
    if ($LASTEXITCODE -ne 0) { throw "A CPython 3.10 Windows x64 interpreter is required for release provenance." }
    & $python @pythonArguments -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Fresh production provenance venv creation failed." }
    $venvPython = Join-Path $venv "Scripts\python.exe"
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Production provenance pip bootstrap failed." }
    & $venvPython -m pip install --require-hashes --report $report -r (Join-Path $repoRoot "requirements-lock-win-amd64-py310.txt")
    if ($LASTEXITCODE -ne 0) { throw "Production hash-lock installation failed." }
    & $venvPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Production pip check failed." }
    & $venvPython (Join-Path $repoRoot "packaging\dependency_contract.py") validate --report $report --requirements (Join-Path $repoRoot "requirements-lock-win-amd64-py310.txt") --direct-requirements (Join-Path $repoRoot "requirements.txt") --lock (Join-Path $repoRoot "requirements-lock-win-amd64-py310.txt") --sbom-output $sbom
    if ($LASTEXITCODE -ne 0) { throw "Production dependency contract validation failed." }
    if (Test-Path -LiteralPath $output) { Remove-Item -LiteralPath $output -Recurse -Force }
    & $venvPython (Join-Path $repoRoot "packaging\release_provenance.py") stage --report $report --requirements (Join-Path $repoRoot "requirements.txt") --lock (Join-Path $repoRoot "requirements-lock-win-amd64-py310.txt") --sbom $sbom --output $output
    if ($LASTEXITCODE -ne 0) { throw "Release provenance staging failed." }
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}