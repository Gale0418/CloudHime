[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DistDir
)

$ErrorActionPreference = "Stop"
$dist = [System.IO.Path]::GetFullPath($DistDir)
if (-not (Test-Path -LiteralPath $dist -PathType Container)) {
    throw "Release dist directory not found: $dist"
}

$runtimeFiles = @(
    "llama-server.exe",
    "llama-server-impl.dll",
    "llama-common.dll",
    "llama.dll",
    "ggml.dll",
    "ggml-base.dll",
    "ggml-cpu-x64.dll",
    "ggml-cuda.dll",
    "mtmd.dll",
    "libomp140.x86_64.dll",
    "cublas64_12.dll",
    "cublasLt64_12.dll",
    "cudart64_12.dll"
)

function Find-NonEmptyFile {
    param([string[]]$RelativeCandidates)

    foreach ($relativePath in $RelativeCandidates) {
        $candidate = Join-Path $dist $relativePath
        if ((Test-Path -LiteralPath $candidate -PathType Leaf) -and ((Get-Item -LiteralPath $candidate).Length -gt 0)) {
            return $relativePath
        }
    }
    return $null
}

$executable = Join-Path $dist "CloudHime.exe"
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Release dist is missing CloudHime.exe"
}
if ((Get-Item -LiteralPath $executable).Length -le 0) {
    throw "Release dist contains an empty CloudHime.exe"
}

$logoRelativePath = Find-NonEmptyFile @(
    "assets\cloudhime_logo.png",
    "_internal\assets\cloudhime_logo.png"
)
if (-not $logoRelativePath) {
    throw "Release dist is missing a non-empty cloudhime_logo.png"
}

foreach ($requiredFile in @("dictionary.json", "LICENSE", "THIRD_PARTY_NOTICES.md")) {
    $relativePath = Find-NonEmptyFile @($requiredFile, "_internal\$requiredFile")
    if (-not $relativePath) {
        throw "Release dist is missing a non-empty $requiredFile"
    }
}

$runtimeCandidates = @("runtime", "_internal\runtime")
$runtimeRoot = $null
$missingByCandidate = @()
foreach ($candidate in $runtimeCandidates) {
    $candidateRoot = Join-Path $dist $candidate
    if (-not (Test-Path -LiteralPath $candidateRoot -PathType Container)) {
        continue
    }
    $missing = @($runtimeFiles | Where-Object {
        $runtimePath = Join-Path $candidateRoot $_
        if (-not (Test-Path -LiteralPath $runtimePath -PathType Leaf)) {
            $true
        } else {
            (Get-Item -LiteralPath $runtimePath).Length -le 0
        }
    })
    if ($missing.Count -eq 0) {
        $runtimeRoot = $candidateRoot
        break
    }
    $missingByCandidate += "${candidate}: $($missing -join ', ')"
}
if (-not $runtimeRoot) {
    $detail = if ($missingByCandidate.Count) { " Candidates checked: $($missingByCandidate -join ' | ')" } else { " No runtime directory was found." }
    throw "Release dist is missing required llama/ggml runtime files.$detail"
}

$files = @(Get-ChildItem -LiteralPath $dist -Recurse -File)
$reservedPackageFiles = @($files | Where-Object { $_.Name -in @("AppxManifest.xml", "AppxBlockMap.xml", "AppxSignature.p7x") })
if ($reservedPackageFiles.Count -gt 0) {
    $names = $reservedPackageFiles | Select-Object -ExpandProperty FullName
    throw "Release dist must not contain generated MSIX files: $($names -join ', ')"
}

$signingMaterial = @($files | Where-Object {
    $relativePath = $_.FullName.Substring($dist.Length).TrimStart("\", "/")
    $isPublicCaBundle = $relativePath -match "(?i)(^|[\\/])certifi[\\/]cacert\.pem$"
    (
        $_.Extension -in @(".pfx", ".p12", ".key", ".pem", ".pvk", ".ppk", ".priv", ".cer", ".crt") -or
        $_.Name -eq ".env" -or
        $_.Name -like ".env.*"
    ) -and -not $isPublicCaBundle
})
if ($signingMaterial.Count -gt 0) {
    $names = $signingMaterial | Select-Object -ExpandProperty FullName
    throw "Release dist must not contain signing material or development secrets: $($names -join ', ')"
}
$unexpectedModels = @($files | Where-Object {
    $_.Name -match "(?i)\.gguf($|\.)" -or $_.Name -like "mmproj*"
})
if ($unexpectedModels.Count -gt 0) {
    $names = $unexpectedModels | Select-Object -ExpandProperty FullName
    throw "Release dist must not bundle model/projector files; move them to managed AppData. Found: $($names -join ', ')"
}

$bytes = ($files | Measure-Object -Property Length -Sum).Sum
[pscustomobject]@{
    Status = "ready"
    DistDir = $dist
    Executable = $executable
    Logo = (Join-Path $dist $logoRelativePath)
    RuntimeRoot = $runtimeRoot
    FileCount = $files.Count
    Bytes = [int64]$bytes
    ModelFiles = 0
}
