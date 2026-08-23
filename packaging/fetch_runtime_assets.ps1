[CmdletBinding()]
param(
    [string]$ArchiveUrl = "",
    [string]$ArchivePath = "",
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[0-9A-Fa-f]{64}$")]
    [string]$ExpectedSha256,
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[0-9A-Fa-f]{7,64}$")]
    [string]$SourceCommit,
    [ValidateSet("cuda", "cpu")]
    [string]$Backend = "cuda",
    [ValidateSet("x64")]
    [string]$Architecture = "x64",
    [string]$OutputRuntimeDir = (Join-Path $PSScriptRoot "..\runtime"),
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [IO.FileStream]::new(
            $Path,
            [IO.FileMode]::Open,
            [IO.FileAccess]::Read,
            [IO.FileShare]::Read,
            1048576,
            [IO.FileOptions]::SequentialScan
        )
        $buffer = New-Object byte[] 1048576
        while (($read = $stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $algorithm.TransformBlock($buffer, 0, $read, $buffer, 0) | Out-Null
        }
        $algorithm.TransformFinalBlock($buffer, 0, 0) | Out-Null
        return ([BitConverter]::ToString($algorithm.Hash)).Replace("-", "").ToLowerInvariant()
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $algorithm.Dispose()
    }
}

function Assert-SafeZipEntry {
    param([Parameter(Mandatory = $true)][string]$Name)

    $normalized = $Name.Replace("\", "/")
    if ([string]::IsNullOrWhiteSpace($normalized) -or $normalized.EndsWith("/")) {
        return
    }
    if ($normalized.StartsWith("/") -or $normalized.Contains(":")) {
        throw "Runtime archive contains an absolute or drive-qualified path: $Name"
    }
    foreach ($part in $normalized.Split("/")) {
        if ($part -eq ".." -or [string]::IsNullOrWhiteSpace($part)) {
            throw "Runtime archive contains a path traversal entry: $Name"
        }
    }
}

if ([string]::IsNullOrWhiteSpace($ArchiveUrl) -and [string]::IsNullOrWhiteSpace($ArchivePath)) {
    throw "Provide exactly one of -ArchiveUrl or -ArchivePath."
}
if (-not [string]::IsNullOrWhiteSpace($ArchiveUrl) -and -not [string]::IsNullOrWhiteSpace($ArchivePath)) {
    throw "Provide exactly one of -ArchiveUrl or -ArchivePath, not both."
}
if (-not [string]::IsNullOrWhiteSpace($ArchiveUrl)) {
    $uri = $null
    if (-not [Uri]::TryCreate($ArchiveUrl, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne "https") {
        throw "Runtime archive URL must be an absolute HTTPS URL."
    }
}

$archiveFile = $null
$downloadedArchive = $false
$extractRoot = $null
$stagingRoot = $null
$promoted = $false
try {
    if ([string]::IsNullOrWhiteSpace($ArchivePath)) {
        $archiveFile = [IO.Path]::GetTempFileName()
        $downloadedArchive = $true
        Write-Host "Downloading pinned llama-server runtime archive..."
        Invoke-WebRequest -Uri $ArchiveUrl -OutFile $archiveFile -UseBasicParsing
    } else {
        $archiveFile = (Resolve-Path -LiteralPath $ArchivePath -ErrorAction Stop).Path
    }

    if (-not (Test-Path -LiteralPath $archiveFile -PathType Leaf)) {
        throw "Runtime archive file was not created: $archiveFile"
    }
    $actualSha256 = Get-Sha256Hex -Path $archiveFile
    if ($actualSha256 -ine $ExpectedSha256) {
        throw "Runtime archive SHA-256 mismatch. Expected $ExpectedSha256 but received $actualSha256."
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($archiveFile)
    try {
        $entries = @($zip.Entries)
        foreach ($entry in $entries) {
            Assert-SafeZipEntry -Name $entry.FullName
        }
        $serverEntries = @(
            $entries |
                Where-Object {
                    -not $_.FullName.EndsWith("/") -and
                    ([IO.Path]::GetFileName($_.FullName.TrimEnd("/", "\")) -ieq "llama-server.exe")
                }
        )
        if ($serverEntries.Count -ne 1) {
            throw "Runtime archive must contain exactly one llama-server.exe; found $($serverEntries.Count)."
        }
        $serverEntryName = $serverEntries[0].FullName.Replace("/", "\")
    } finally {
        $zip.Dispose()
    }

    $extractRoot = Join-Path ([IO.Path]::GetTempPath()) ("cloudhime-runtime-extract-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
    [IO.Compression.ZipFile]::ExtractToDirectory($archiveFile, $extractRoot)
    $serverPath = Join-Path $extractRoot $serverEntryName
    if (-not (Test-Path -LiteralPath $serverPath -PathType Leaf)) {
        throw "Runtime archive extraction did not produce llama-server.exe."
    }

    $runtimeSourceRoot = [IO.Directory]::GetParent($serverPath).FullName
    $outputRoot = [IO.Path]::GetFullPath($OutputRuntimeDir)
    if (Test-Path -LiteralPath $outputRoot) {
        if (-not $Force) {
            throw "Output runtime directory already exists; pass -Force only for an explicit replacement: $outputRoot"
        }
    } else {
        $outputParent = [IO.Directory]::GetParent($outputRoot).FullName
        New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
    }

    $stagingRoot = "$outputRoot.tmp-$([Guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $runtimeSourceRoot -Force) {
        Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $stagingRoot $item.Name) -Recurse -Force
    }
    if (-not (Test-Path -LiteralPath (Join-Path $stagingRoot "llama-server.exe") -PathType Leaf)) {
        throw "Staged runtime is missing llama-server.exe."
    }

    $encoding = [Text.UTF8Encoding]::new($false)
    [IO.File]::WriteAllText(
        (Join-Path $stagingRoot "llama-runtime-commit.txt"),
        "$($SourceCommit.Trim())`r`n",
        $encoding
    )
    $sourceMetadata = [ordered]@{
        schema_version = 1
        source_commit = $SourceCommit.Trim()
        archive_sha256 = $actualSha256
        backend = $Backend
        architecture = $Architecture
    }
    [IO.File]::WriteAllText(
        (Join-Path $stagingRoot "runtime-source.json"),
        (($sourceMetadata | ConvertTo-Json -Depth 3) + "`r`n"),
        $encoding
    )

    if (Test-Path -LiteralPath $outputRoot) {
        Remove-Item -LiteralPath $outputRoot -Recurse -Force
    }
    Move-Item -LiteralPath $stagingRoot -Destination $outputRoot
    $promoted = $true
    Write-Host "Pinned llama-server runtime staged: $outputRoot"
    Write-Host "Runtime source commit: $($SourceCommit.Trim())"
    Write-Host "Runtime archive SHA-256: $actualSha256"
} finally {
    if ($null -ne $stagingRoot -and -not $promoted -and (Test-Path -LiteralPath $stagingRoot)) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($null -ne $extractRoot -and (Test-Path -LiteralPath $extractRoot)) {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($downloadedArchive -and $null -ne $archiveFile -and (Test-Path -LiteralPath $archiveFile)) {
        Remove-Item -LiteralPath $archiveFile -Force -ErrorAction SilentlyContinue
    }
}