[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DistDir,
    [switch]$UnpackedMsix,
    [string]$ExpectedIdentityName = "CloudHime",
    [string]$ExpectedPublisher = "",
    [ValidateSet("x64")]
    [string]$ExpectedArchitecture = "x64"
)

$ErrorActionPreference = "Stop"
$dist = [System.IO.Path]::GetFullPath($DistDir)
if (-not (Test-Path -LiteralPath $dist -PathType Container)) {
    throw "Release dist directory not found: $dist"
}

$provenanceRoot = Join-Path $dist "_internal\provenance"
& python (Join-Path $PSScriptRoot "release_provenance.py") verify --provenance-dir $provenanceRoot
if ($LASTEXITCODE -ne 0) {
    throw "Release dist dependency provenance verification failed."
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

function Get-PngCrc32 {
    param(
        [byte[]]$Bytes,
        [int]$Start,
        [int]$Count
    )

    [uint32]$crc = [uint32]::MaxValue
    for ($index = $Start; $index -lt ($Start + $Count); $index++) {
        $crc = $crc -bxor [uint32]$Bytes[$index]
        for ($bit = 0; $bit -lt 8; $bit++) {
            if (($crc -band [uint32]1) -ne 0) {
                $crc = ($crc -shr 1) -bxor [uint32]3988292384
            } else {
                $crc = $crc -shr 1
            }
        }
    }
    return $crc -bxor [uint32]::MaxValue
}

function Read-PngUInt32 {
    param(
        [byte[]]$Bytes,
        [int]$Start
    )

    return ([uint64]$Bytes[$Start] -shl 24) -bor
        ([uint64]$Bytes[$Start + 1] -shl 16) -bor
        ([uint64]$Bytes[$Start + 2] -shl 8) -bor
        [uint64]$Bytes[$Start + 3]
}

function Find-PngWithDimensions {
    param(
        [string[]]$RelativeCandidates,
        [int]$ExpectedWidth,
        [int]$ExpectedHeight
    )

    foreach ($relativePath in $RelativeCandidates) {
        $candidate = Join-Path $dist $relativePath
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        $fileInfo = Get-Item -LiteralPath $candidate
        if ($fileInfo.Length -le 0 -or $fileInfo.Length -ge 204800) {
            continue
        }
        $bytes = [IO.File]::ReadAllBytes($candidate)
        if ($bytes.Length -lt 33) {
            continue
        }

        $signature = [byte[]](137, 80, 78, 71, 13, 10, 26, 10)
        $signatureMatches = $true
        for ($index = 0; $index -lt $signature.Length; $index++) {
            if ($bytes[$index] -ne $signature[$index]) {
                $signatureMatches = $false
                break
            }
        }
        if (-not $signatureMatches) {
            continue
        }

        $offset = 8
        $hasHeader = $false
        $hasImageData = $false
        $hasEnd = $false
        $width = 0
        $height = 0
        $valid = $true
        while ($offset -lt $bytes.Length) {
            if ($offset + 12 -gt $bytes.Length) {
                $valid = $false
                break
            }
            $chunkLength = Read-PngUInt32 $bytes $offset
            if ($chunkLength -gt [int]::MaxValue -or ([int64]$offset + 12 + $chunkLength) -gt $bytes.Length) {
                $valid = $false
                break
            }
            $chunkLengthInt = [int]$chunkLength
            $chunkTypeOffset = $offset + 4
            $chunkDataOffset = $offset + 8
            $chunkCrcOffset = $chunkDataOffset + $chunkLengthInt
            $chunkType = [Text.Encoding]::ASCII.GetString($bytes, $chunkTypeOffset, 4)
            $actualCrc = Get-PngCrc32 $bytes $chunkTypeOffset (4 + $chunkLengthInt)
            $expectedCrc = Read-PngUInt32 $bytes $chunkCrcOffset
            if ($actualCrc -ne $expectedCrc) {
                $valid = $false
                break
            }

            switch ($chunkType) {
                "IHDR" {
                    if ($hasHeader -or $chunkLengthInt -ne 13) {
                        $valid = $false
                        break
                    }
                    $width = [int](Read-PngUInt32 $bytes $chunkDataOffset)
                    $height = [int](Read-PngUInt32 $bytes ($chunkDataOffset + 4))
                    $hasHeader = $true
                }
                "IDAT" {
                    $hasImageData = $true
                }
                "IEND" {
                    if ($chunkLengthInt -ne 0 -or $hasEnd) {
                        $valid = $false
                        break
                    }
                    $hasEnd = $true
                }
            }
            if (-not $valid) {
                break
            }
            $offset += 12 + $chunkLengthInt
            if ($hasEnd) {
                if ($offset -ne $bytes.Length) {
                    $valid = $false
                }
                break
            }
        }

        if ($valid -and $hasHeader -and $hasImageData -and $hasEnd -and
            $width -eq $ExpectedWidth -and $height -eq $ExpectedHeight) {
            return $relativePath
        }
    }
    return $null
}$executable = Join-Path $dist "CloudHime.exe"
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

$logoRelativePaths = @{}
foreach ($logoSize in @(44, 50, 150)) {
    $logoPath = Find-PngWithDimensions @(
        "assets\cloudhime_logo_$($logoSize).png",
        "_internal\assets\cloudhime_logo_$($logoSize).png"
    ) $logoSize $logoSize
    if (-not $logoPath) {
        throw "Release dist is missing a valid $($logoSize)x$($logoSize) cloudhime logo."
    }
    $logoRelativePaths[$logoSize] = $logoPath
}

foreach ($requiredFile in @("dictionary.json", "LICENSE", "THIRD_PARTY_NOTICES.md")) {
    $relativePath = Find-NonEmptyFile @($requiredFile, "_internal\$requiredFile")
    if (-not $relativePath) {
        throw "Release dist is missing a non-empty $requiredFile"
    }
}

$noticeRelativePath = Find-NonEmptyFile @("THIRD_PARTY_NOTICES.md", "_internal\THIRD_PARTY_NOTICES.md")
if (-not $noticeRelativePath) {
    throw "Release dist is missing a non-empty THIRD_PARTY_NOTICES.md"
}
$noticeText = [IO.File]::ReadAllText((Join-Path $dist $noticeRelativePath))
$requiredNoticeMarkers = @(
    "## Knowledge research providers",
    "DDGS",
    "click",
    "primp",
    "lxml",
    "httpx",
    "fake-useragent",
    "certifi",
    "Jina Reader",
    "## meikiocr",
    "Apache License 2.0",
    "## Meiki OCR model weights",
    "GNU Lesser General Public License v3.0"
)
foreach ($marker in $requiredNoticeMarkers) {
    if ($noticeText.IndexOf($marker, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Release dist THIRD_PARTY_NOTICES.md is missing required third-party notices marker: $marker"
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


$manifestPath = Join-Path $runtimeRoot "runtime-manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Release dist is missing runtime-manifest.json"
}
if ((Get-Item -LiteralPath $manifestPath).Length -le 0) {
    throw "Release dist contains an empty runtime-manifest.json"
}
try {
    $runtimeManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
} catch {
    throw "Release dist runtime manifest is not valid JSON: $($_.Exception.Message)"
}
if ($runtimeManifest.schema_version -ne 1 -or $runtimeManifest.runtime -ne "llama-server") {
    throw "Release dist runtime manifest has an unsupported schema or runtime"
}
foreach ($metadataName in @("source_commit", "backend", "architecture")) {
    $metadataValue = [string]$runtimeManifest.build.$metadataName
    if ([string]::IsNullOrWhiteSpace($metadataValue)) {
        throw "Release dist runtime manifest is missing build metadata: $metadataName"
    }
}
$runtimeArchitecture = [string]$runtimeManifest.build.architecture
if ($runtimeArchitecture -ine "x64") {
    throw "Release dist runtime manifest has unsupported architecture '$runtimeArchitecture'. Expected 'x64'."
}

if ([string]::IsNullOrWhiteSpace([string]$runtimeManifest.server.version)) {
    throw "Release dist runtime manifest is missing llama-server version"
}

$manifestEntries = @($runtimeManifest.files)
if ($manifestEntries.Count -eq 0) {
    throw "Release dist runtime manifest contains no files"
}
$manifestFiles = @{}
foreach ($entry in $manifestEntries) {
    $relative = [string]$entry.path
    if ([string]::IsNullOrWhiteSpace($relative) -or
        [IO.Path]::IsPathRooted($relative) -or
        $relative.Replace("/", "\").Split("\") -contains "..") {
        throw "Release dist runtime manifest contains an invalid file path: $relative"
    }
    $normalized = $relative.Replace("/", "\")
    if ($manifestFiles.ContainsKey($normalized)) {
        throw "Release dist runtime manifest contains duplicate file: $relative"
    }
    $manifestFiles[$normalized] = $entry
    $candidate = Join-Path $runtimeRoot $normalized
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "Release dist runtime manifest file is missing: $relative"
    }
    $expectedSize = [int64]$entry.size
    if ($expectedSize -lt 0) {
        throw "Release dist runtime manifest has an invalid size: $relative"
    }
    $actualFile = Get-Item -LiteralPath $candidate
    if ($actualFile.Length -ne $expectedSize) {
        throw "Release dist runtime manifest hash or size mismatch: $relative"
    }
    $expectedHash = [string]$entry.sha256
    if ($expectedHash -notmatch "^[0-9a-fA-F]{64}$") {
        throw "Release dist runtime manifest has an invalid SHA-256: $relative"
    }
    $actualHash = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash
    if ($actualHash -ine $expectedHash) {
        throw "Release dist runtime manifest hash or size mismatch: $relative"
    }
}
$actualRuntimeFiles = @(Get-ChildItem -LiteralPath $runtimeRoot -Recurse -File |
    Where-Object { $_.FullName -ine $manifestPath } |
    ForEach-Object { $_.FullName.Substring($runtimeRoot.Length).TrimStart("\", "/") })
foreach ($actualRelative in $actualRuntimeFiles) {
    if (-not $manifestFiles.ContainsKey($actualRelative)) {
        throw "Release dist runtime manifest file set mismatch; unexpected file: $actualRelative"
    }
}
if ($actualRuntimeFiles.Count -ne $manifestFiles.Count) {
    throw "Release dist runtime manifest file set mismatch"
}
$serverManifestPath = ([string]$runtimeManifest.server.path).Replace("/", "\")
if ($serverManifestPath -ne "llama-server.exe" -or -not $manifestFiles.ContainsKey($serverManifestPath)) {
    throw "Release dist runtime manifest does not identify llama-server.exe"
}

$files = @(Get-ChildItem -LiteralPath $dist -Recurse -File)
$inProcessLlamaBindings = @($files | Where-Object {
    $relativePath = $_.FullName.Substring($dist.Length).TrimStart("\", "/")
    $pathParts = @($relativePath -split "[\\/]")
    $_.Name -like "_llama_cpp*.pyd" -or
        ($pathParts | Where-Object { $_ -ieq "llama_cpp" }).Count -gt 0
})
if ($inProcessLlamaBindings.Count -gt 0) {
    $names = $inProcessLlamaBindings | Select-Object -ExpandProperty FullName
    throw "Release dist must not contain an in-process llama binding: $($names -join ', ')"
}

$runtimePrefix = ([System.IO.Path]::GetFullPath($runtimeRoot).TrimEnd("\", "/")) + [System.IO.Path]::DirectorySeparatorChar
$managedRuntimeFileNames = @($runtimeFiles)
$duplicateRuntimeFiles = @($files | Where-Object {
    $isManagedRuntimeFile = ($managedRuntimeFileNames -contains $_.Name) -or
        $_.Name -ieq "llama-server.exe" -or
        $_.Name -ieq "llama.dll" -or
        $_.Name -like "ggml*.dll" -or
        $_.Name -like "cublas*.dll" -or
        $_.Name -like "cudart*.dll" -or
        $_.Name -like "nvrtc*.dll" -or
        $_.Name -like "nvJitLink*.dll" -or
        $_.Name -like "cufft*.dll" -or
        $_.Name -like "curand*.dll" -or
        $_.Name -like "cusolver*.dll" -or
        $_.Name -like "cusparse*.dll"
    $isOutsideRuntime = -not $_.FullName.StartsWith($runtimePrefix, [System.StringComparison]::OrdinalIgnoreCase)
    $isManagedRuntimeFile -and $isOutsideRuntime
})
if ($duplicateRuntimeFiles.Count -gt 0) {
    $names = $duplicateRuntimeFiles | Select-Object -ExpandProperty FullName
    throw "Release dist contains managed runtime files outside the runtime directory: $($names -join ', ')"
}
if ($UnpackedMsix) {
    $expectedUnpackedMetadata = @("AppxManifest.xml", "AppxBlockMap.xml")
    foreach ($metadataName in $expectedUnpackedMetadata) {
        $metadataPath = Join-Path $dist $metadataName
        if (-not (Test-Path -LiteralPath $metadataPath -PathType Leaf) -or (Get-Item -LiteralPath $metadataPath).Length -le 0) {
            throw "Unpacked MSIX is missing required root metadata: $metadataName"
        }
    }
    try {
        [xml]$unpackedManifest = Get-Content -LiteralPath (Join-Path $dist "AppxManifest.xml") -Raw
        $namespaceManager = New-Object System.Xml.XmlNamespaceManager($unpackedManifest.NameTable)
        $namespaceManager.AddNamespace("foundation", "http://schemas.microsoft.com/appx/manifest/foundation/windows10")
        $identity = $unpackedManifest.SelectSingleNode("/foundation:Package/foundation:Identity", $namespaceManager)
    } catch {
        throw "Unpacked MSIX AppxManifest.xml is not valid XML: $($_.Exception.Message)"
    }
    if ($null -eq $identity -or $identity.Name -ne $ExpectedIdentityName) {
        throw "Unpacked MSIX AppxManifest.xml has an unexpected identity name. Expected '$ExpectedIdentityName'."
    }
    if ([string]::IsNullOrWhiteSpace([string]$identity.Publisher)) {
        throw "Unpacked MSIX AppxManifest.xml is missing a publisher."
    }
    if ([string]::IsNullOrWhiteSpace($ExpectedPublisher)) {
        if ($identity.Publisher -notmatch "^CN=") {
            throw "Unpacked MSIX AppxManifest.xml publisher must begin with 'CN=' when ExpectedPublisher is not provided."
        }
    } elseif ($identity.Publisher -cne $ExpectedPublisher) {
        throw "Unpacked MSIX AppxManifest.xml has an unexpected publisher. Expected '$ExpectedPublisher'."
    }
    if ($identity.ProcessorArchitecture -ne $ExpectedArchitecture) {
        throw "Unpacked MSIX AppxManifest.xml has an unexpected processor architecture. Expected '$ExpectedArchitecture'."
    }
}

$generatedMsixFiles = @($files | Where-Object {
    $relativePath = $_.FullName.Substring($dist.Length).TrimStart("\", "/")
    $isExpectedUnpackedRootMetadata = $UnpackedMsix -and
        ($relativePath -notmatch "[\\/]") -and
        ($_.Name -in @("AppxManifest.xml", "AppxBlockMap.xml"))
    $isGeneratedMsixFile = $_.Name -in @("AppxManifest.xml", "AppxBlockMap.xml", "AppxSignature.p7x") -or
        $_.Extension -in @(".msix", ".appx", ".msixbundle", ".appxbundle")
    $isGeneratedMsixFile -and -not $isExpectedUnpackedRootMetadata
})
if ($generatedMsixFiles.Count -gt 0) {
    $names = $generatedMsixFiles | Select-Object -ExpandProperty FullName
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
