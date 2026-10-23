[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DistDir,

    [Parameter(Mandatory = $true)]
    [string]$ModelPath,

    [Parameter(Mandatory = $true)]
    [string]$ProjectorPath,

    [Parameter(Mandatory = $true)]
    [string]$ImagePath,

    [string]$PythonPath = "python",

    [ValidateRange(5, 120)]
    [int]$LaunchWaitSeconds = 20,

    [ValidateRange(5, 600)]
    [int]$TimeoutSeconds = 180,

    [switch]$RequireGpu,

    [switch]$ForceCpu
)

$ErrorActionPreference = "Stop"
$stage = "initialization"
$packagedResultPath = $null

function Resolve-RequiredFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    $resolved = Resolve-Path -LiteralPath $Path -ErrorAction Stop
    if (-not (Test-Path -LiteralPath $resolved.Path -PathType Leaf)) {
        throw "$Label is not a file: $($resolved.Path)"
    }
    return $resolved.Path
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host "[release-smoke] $Label"
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

try {
    if ($RequireGpu -and $ForceCpu) {
        throw "-RequireGpu cannot be combined with -ForceCpu"
    }
    if (-not [Environment]::UserInteractive -or $env:SESSIONNAME -eq "Services") {
        throw "interactive desktop session is required for the packaged launch gate"
    }

    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
    $dist = (Resolve-Path -LiteralPath $DistDir -ErrorAction Stop).Path
    $executable = Resolve-RequiredFile -Path (Join-Path $dist "CloudHime.exe") -Label "packaged executable"

    $runtimeDir = $null
    foreach ($candidate in @(
        (Join-Path $dist "_internal\runtime"),
        (Join-Path $dist "runtime")
    )) {
        if (
            (Test-Path -LiteralPath (Join-Path $candidate "llama-server.exe") -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $candidate "runtime-manifest.json") -PathType Leaf)
        ) {
            $runtimeDir = (Resolve-Path -LiteralPath $candidate).Path
            break
        }
    }
    if ([string]::IsNullOrWhiteSpace($runtimeDir)) {
        throw "frozen runtime directory with llama-server.exe and runtime-manifest.json was not found"
    }

    $model = Resolve-RequiredFile -Path $ModelPath -Label "model"
    $projector = Resolve-RequiredFile -Path $ProjectorPath -Label "projector"
    $image = Resolve-RequiredFile -Path $ImagePath -Label "image"
    $pythonScript = Resolve-RequiredFile -Path (Join-Path $repoRoot "release_functional_smoke.py") -Label "functional smoke runner"
    $verifier = Resolve-RequiredFile -Path (Join-Path $PSScriptRoot "verify_release_dist.ps1") -Label "release verifier"
    $cleanMachine = Resolve-RequiredFile -Path (Join-Path $PSScriptRoot "test_clean_machine.ps1") -Label "clean-machine smoke"
    $packagedResultPath = Join-Path ([IO.Path]::GetTempPath()) ("cloudhime-packaged-functional-" + [Guid]::NewGuid().ToString("N") + ".json")
    $requireGpuValue = if ($RequireGpu) { "1" } else { "0" }
    $forceCpuValue = if ($ForceCpu) { "1" } else { "0" }
    $packagedEnvironment = @{
        "CLOUDHIME_PACKAGED_FUNCTIONAL_SMOKE" = "1"
        "CLOUDHIME_PACKAGED_SMOKE_RESULT_PATH" = $packagedResultPath
        "CLOUDHIME_PACKAGED_SMOKE_RUNTIME_DIR" = $runtimeDir
        "CLOUDHIME_PACKAGED_SMOKE_MODEL_PATH" = $model
        "CLOUDHIME_PACKAGED_SMOKE_PROJECTOR_PATH" = $projector
        "CLOUDHIME_PACKAGED_SMOKE_IMAGE_PATH" = $image
        "CLOUDHIME_PACKAGED_SMOKE_REQUIRE_GPU" = $requireGpuValue
        "CLOUDHIME_PACKAGED_SMOKE_FORCE_CPU" = $forceCpuValue
        "CLOUDHIME_PACKAGED_SMOKE_TIMEOUT_SECONDS" = $TimeoutSeconds.ToString()
        "CLOUDHIME_PACKAGED_SMOKE_STARTUP_TIMEOUT_SECONDS" = $TimeoutSeconds.ToString()
        "CLOUDHIME_PACKAGED_SMOKE_CONTEXT_SIZE" = "4096"
        "CLOUDHIME_PACKAGED_SMOKE_GPU_LAYERS" = "999"
    }

    $stage = "release dist preflight"
    Invoke-Checked -Label $stage -Action {
        & $verifier -DistDir $dist -PythonPath $PythonPath
    }

    $smokeArgs = @(
        $pythonScript,
        "--runtime-dir", $runtimeDir,
        "--model", $model,
        "--projector", $projector,
        "--image", $image,
        "--timeout", $TimeoutSeconds.ToString(),
        "--startup-timeout", $TimeoutSeconds.ToString()
    )
    if ($RequireGpu) {
        $smokeArgs += "--require-gpu"
    }
    if ($ForceCpu) {
        $smokeArgs += "--force-cpu"
    }

    $stage = "functional smoke input validation"
    Invoke-Checked -Label $stage -Action {
        & $PythonPath @smokeArgs "--validate-only"
    }

    $stage = "environment-isolated packaged launch"
    Invoke-Checked -Label $stage -Action {
        & $cleanMachine -ExecutablePath $executable -LaunchWaitSeconds $LaunchWaitSeconds
    }

    $stage = "functional vision smoke"
    Invoke-Checked -Label $stage -Action {
        & $cleanMachine `
            -ExecutablePath $executable `
            -LaunchWaitSeconds $LaunchWaitSeconds `
            -FunctionalSmoke `
            -FunctionalTimeoutSeconds $TimeoutSeconds `
            -AdditionalEnvironmentVariables $packagedEnvironment
        if ($LASTEXITCODE -ne 0) {
            throw "packaged functional smoke process failed with exit code $LASTEXITCODE"
        }
        if (-not (Test-Path -LiteralPath $packagedResultPath -PathType Leaf)) {
            throw "packaged functional smoke result is missing"
        }
        try {
            $packagedResult = Get-Content -LiteralPath $packagedResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
            throw "packaged functional smoke result is not valid JSON"
        }
        if (
            $packagedResult.schema_version -ne 1 -or
            $packagedResult.status -ne "passed" -or
            $packagedResult.evaluation_mode -ne "technical_coverage" -or
            [int]$packagedResult.image_count -le 0 -or
            [int]$packagedResult.successful_images -ne [int]$packagedResult.image_count -or
            [int]$packagedResult.request_success_images -ne [int]$packagedResult.image_count
        ) {
            throw "packaged functional smoke result failed its bounded summary contract"
        }
        Write-Host "[release-smoke] packaged functional smoke result passed"
    }

    Write-Host "[release-smoke] PASS"
    exit 0
}
catch {
    $exitCode = switch -Regex ($stage) {
        "^release dist" { 20; break }
        "^environment" { 30; break }
        "^functional" { 40; break }
        default { 70 }
    }
    Write-Error ("[release-smoke] FAILED at {0}: {1} (exit={2})" -f $stage, $_.Exception.Message, $exitCode)
    exit $exitCode
} finally {
    if (-not [string]::IsNullOrWhiteSpace($packagedResultPath) -and (Test-Path -LiteralPath $packagedResultPath)) {
        Remove-Item -LiteralPath $packagedResultPath -Force -ErrorAction SilentlyContinue
    }
}
