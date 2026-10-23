[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$TestFiles,
    [switch]$IsolateUi,
    [ValidateRange(1, 3600)]
    [int]$TimeoutSeconds = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-PrivateBaseTemp {
    $roots = [System.Collections.Generic.List[string]]::new()
    if ($env:RUNNER_TEMP) {
        [void]$roots.Add($env:RUNNER_TEMP)
    }
    [void]$roots.Add([System.IO.Path]::GetTempPath())
    if ($env:LOCALAPPDATA) {
        [void]$roots.Add($env:LOCALAPPDATA)
    }

    foreach ($root in ($roots | Select-Object -Unique)) {
        $run = Join-Path $root ("cloudhime-pytest-" + [Guid]::NewGuid().ToString("N"))
        try {
            New-Item -ItemType Directory -Path $run -Force | Out-Null
            $probe = Join-Path $run ".write-probe"
            [System.IO.File]::WriteAllText($probe, "ok", [System.Text.Encoding]::UTF8)
            [System.IO.File]::Delete($probe)
            return $run
        } catch {
            if (Test-Path -LiteralPath $run) {
                Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }

    throw "Unable to create a private writable pytest basetemp."
}
function Invoke-PytestFiles {
    param([string[]]$Files)

    $baseTemp = New-PrivateBaseTemp
    try {
        $pytestArgs = @("-m", "pytest", "-q", "--basetemp", $baseTemp) + $Files
        if ($IsolateUi) {
            $isolatedPytestArgs = @("-m", "pytest", "-q", "--basetemp", ('"{0}"' -f $baseTemp)) + $Files
            $process = Start-Process -FilePath "python" -ArgumentList $isolatedPytestArgs -PassThru -NoNewWindow
            $completed = $process.WaitForExit($TimeoutSeconds * 1000)
            if (-not $completed) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                throw "UI test file timed out after $TimeoutSeconds seconds: $($Files -join ', ')"
            }
            return $process.ExitCode
        }

        & python @pytestArgs 2>&1 | Out-Host
        $pytestExitCode = $LASTEXITCODE
        return $pytestExitCode
    } finally {
        if (Test-Path -LiteralPath $baseTemp) {
            Remove-Item -LiteralPath $baseTemp -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

if (-not $TestFiles -or $TestFiles.Count -eq 0) {
    throw "At least one pytest file is required."
}

$exitCode = 0
if ($IsolateUi) {
    foreach ($testFile in $TestFiles) {
        Write-Host "Running isolated UI test file: $testFile"
        $exitCode = Invoke-PytestFiles -Files @($testFile)
        if ($exitCode -ne 0) { break }
    }
} else {
    $exitCode = Invoke-PytestFiles -Files $TestFiles
}

exit $exitCode
