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
