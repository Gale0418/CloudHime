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
    [ValidateSet("x86", "x64", "arm64", "neutral")]
    [string]$Architecture = "x64",
    [string]$MakeAppxPath = ""
)

$ErrorActionPreference = "Stop"

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
        $candidate = Get-ChildItem -LiteralPath $kitsRoot -Filter "makeappx.exe" -Recurse -File |
            Sort-Object FullName -Descending |
            Select-Object -First 1
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
$makeappx = Resolve-MakeAppx $MakeAppxPath

foreach ($required in @(
    $dist,
    $template,
    (Join-Path $dist "CloudHime.exe"),
    (Join-Path $dist "assets\cloudhime_logo.png")
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required release asset not found: $required"
    }
}

New-Item -ItemType Directory -Force -Path $output | Out-Null
if (Test-Path -LiteralPath $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
if (Test-Path -LiteralPath $package) {
    Remove-Item -LiteralPath $package -Force
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
    }
    foreach ($token in $replacements.Keys) {
        $manifest = $manifest.Replace($token, $replacements[$token])
    }
    Set-Content -LiteralPath (Join-Path $stage "AppxManifest.xml") -Value $manifest -Encoding UTF8

    & $makeappx pack /d $stage /p $package /o
    if ($LASTEXITCODE -ne 0) {
        throw "makeappx failed with exit code $LASTEXITCODE"
    }

    Write-Host "Created $package"
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
