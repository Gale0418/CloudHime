[CmdletBinding()]
param(
    [string]$DistDir = (Join-Path $PSScriptRoot "..\dist\CloudHime"),
    [string]$OutputDir = (Join-Path $PSScriptRoot "..\dist"),
    [string]$IdentityName = "CloudHime",
    [string]$Publisher = "CN=CloudHime Development",
    [string]$PublisherDisplayName = "CloudHime",
    [string]$DisplayName = "CloudHime",
    [string]$Description = "Windows screen translation assistant",
    [string]$Version = "0.1.0.0",
    [ValidateSet("x64")]
    [string]$Architecture = "x64",
    [string]$MakeAppxPath = "",
    [switch]$CreateUpload,
    [switch]$PreflightOnly
)

$ErrorActionPreference = "Stop"

$versionParts = $Version.Split(".")
$validVersion = $versionParts.Count -eq 4
foreach ($part in $versionParts) {
    if (($part -notmatch "^\d+$") -or ([int]$part -gt 65535)) {
        $validVersion = $false
    }
}
if (-not $validVersion) {
    throw "Version must contain four numeric components in the range 0-65535, for example 0.1.0.0."
}

function Resolve-MakeAppx {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        if (-not (Test-Path -LiteralPath $RequestedPath)) {
            throw "makeappx.exe not found at $RequestedPath"
        }
        return (Resolve-Path -LiteralPath $RequestedPath).Path
    }

    $kitsRoot = Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Windows Kits\10\bin"
    if (Test-Path -LiteralPath $kitsRoot) {
        $candidates = @(Get-ChildItem -LiteralPath $kitsRoot -Filter "makeappx.exe" -Recurse -File |
            Sort-Object FullName -Descending)
        $candidate = $candidates |
            Where-Object { $_.FullName -match 'x64[\\/]makeappx\.exe$' } |
            Select-Object -First 1
        if (-not $candidate) {
            $candidate = $candidates | Select-Object -First 1
        }
        if ($candidate) {
            return $candidate.FullName
        }
    }

    throw "makeappx.exe not found. Install the Windows 10/11 SDK or pass -MakeAppxPath."
}

function Escape-XmlValue {
    param([string]$Value)
    return [System.Security.SecurityElement]::Escape($Value)
}

$dist = [System.IO.Path]::GetFullPath($DistDir)
$output = [System.IO.Path]::GetFullPath($OutputDir)
$template = Join-Path $PSScriptRoot "Package.appxmanifest.in"
$stage = Join-Path (Split-Path -Parent $output) "CloudHime-msix-stage"
$package = Join-Path $output "CloudHime-$Version-$Architecture.msix"
$upload = Join-Path $output "CloudHime-$Version-$Architecture.msixupload"
$uploadZip = "$upload.zip"
$validator = Join-Path $PSScriptRoot "verify_release_dist.ps1"
if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) {
    throw "Release dist validator not found: $validator"
}
& $validator -DistDir $dist
if ($PreflightOnly) {
    Write-Host "Release dist preflight passed. Use the same DistDir with Windows SDK tools to build MSIX."
    return
}
$makeappx = Resolve-MakeAppx $MakeAppxPath
$packagingSucceeded = $false

foreach ($required in @(
    $dist,
    $template,
    (Join-Path $dist "CloudHime.exe")
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required release asset not found: $required"
    }
}

$logoCandidates = @{
    "44" = @(
        "assets\cloudhime_logo_44.png",
        "_internal\assets\cloudhime_logo_44.png"
    )
    "50" = @(
        "assets\cloudhime_logo_50.png",
        "_internal\assets\cloudhime_logo_50.png"
    )
    "150" = @(
        "assets\cloudhime_logo_150.png",
        "_internal\assets\cloudhime_logo_150.png"
    )
}
$logoRelativePaths = @{}
foreach ($size in @("44", "50", "150")) {
    $logoRelativePath = $logoCandidates[$size] |
        Where-Object { Test-Path -LiteralPath (Join-Path $dist $_) } |
        Select-Object -First 1
    if (-not $logoRelativePath) {
        throw "Required release asset not found for $($size)x$($size) logo."
    }
    $logoRelativePaths[$size] = $logoRelativePath
}

New-Item -ItemType Directory -Force -Path $output | Out-Null
if (Test-Path -LiteralPath $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
if (Test-Path -LiteralPath $package) {
    Remove-Item -LiteralPath $package -Force
}
if (Test-Path -LiteralPath $upload) {
    Remove-Item -LiteralPath $upload -Force
}
if (Test-Path -LiteralPath $uploadZip) {
    Remove-Item -LiteralPath $uploadZip -Force
}

try {
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    Copy-Item -Path (Join-Path $dist "*") -Destination $stage -Recurse -Force

    $manifest = Get-Content -LiteralPath $template -Raw
    $replacements = @{
        "__IDENTITY_NAME__" = Escape-XmlValue $IdentityName
        "__PUBLISHER__" = Escape-XmlValue $Publisher
        "__VERSION__" = Escape-XmlValue $Version
        "__ARCHITECTURE__" = Escape-XmlValue $Architecture
        "__PUBLISHER_DISPLAY_NAME__" = Escape-XmlValue $PublisherDisplayName
        "__DISPLAY_NAME__" = Escape-XmlValue $DisplayName
        "__DESCRIPTION__" = Escape-XmlValue $Description
        "__LOGO_44_PATH__" = Escape-XmlValue ($logoRelativePaths["44"] -replace "/", "\")
        "__LOGO_50_PATH__" = Escape-XmlValue ($logoRelativePaths["50"] -replace "/", "\")
        "__LOGO_150_PATH__" = Escape-XmlValue ($logoRelativePaths["150"] -replace "/", "\")
    }
    foreach ($token in $replacements.Keys) {
        $manifest = $manifest.Replace($token, $replacements[$token])
    }
    Set-Content -LiteralPath (Join-Path $stage "AppxManifest.xml") -Value $manifest -Encoding UTF8

    & $makeappx pack /d $stage /p $package /o
    if ($LASTEXITCODE -ne 0) {
        throw "makeappx failed with exit code $LASTEXITCODE"
    }

    if ($CreateUpload) {
        Compress-Archive -LiteralPath $package -DestinationPath $uploadZip -Force
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create MSIX upload archive"
        }
        Move-Item -LiteralPath $uploadZip -Destination $upload -Force
        Write-Host "Created $upload"
    }

    $packagingSucceeded = $true
    Write-Host "Created $package"
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
    if (-not $packagingSucceeded) {
        foreach ($artifact in @($package, $upload, $uploadZip)) {
            if (Test-Path -LiteralPath $artifact) {
                Remove-Item -LiteralPath $artifact -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
