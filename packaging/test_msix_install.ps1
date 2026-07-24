[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,

    [string]$IdentityName = "CloudHime",

    [string]$ExecutableName = "CloudHime.exe",

    [ValidateRange(1, 30)]
    [int]$LaunchWaitSeconds = 3
)

$ErrorActionPreference = "Stop"
$package = (Resolve-Path -LiteralPath $PackagePath).Path
$existing = @(Get-AppxPackage -Name $IdentityName -ErrorAction SilentlyContinue)
if ($existing.Count -gt 0) {
    throw "Refusing to modify an existing package named '$IdentityName'. Use a clean test account or remove it explicitly."
}

$installed = $null
$process = $null
try {
    Add-AppxPackage -Path $package
    $installed = Get-AppxPackage -Name $IdentityName |
        Sort-Object Version -Descending |
        Select-Object -First 1
    if ($null -eq $installed) {
        throw "Installed package '$IdentityName' was not discoverable."
    }

    $executablePath = Join-Path $installed.InstallLocation $ExecutableName
    if (-not (Test-Path -LiteralPath $executablePath)) {
        throw "Installed package is missing $ExecutableName."
    }

    $process = Start-Process -FilePath $executablePath -PassThru
    Start-Sleep -Seconds $LaunchWaitSeconds
    if ($process.HasExited -and $process.ExitCode -ne 0) {
        throw "Packaged executable exited with code $($process.ExitCode)."
    }
    Write-Host "Installed and launched $IdentityName from $($installed.InstallLocation)."
}
finally {
    if ($null -ne $process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    if ($null -ne $installed) {
        Remove-AppxPackage -Package $installed.PackageFullName -ErrorAction SilentlyContinue
    }

    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        if (-not (Get-AppxPackage -Name $IdentityName -ErrorAction SilentlyContinue)) {
            break
        }
        Start-Sleep -Seconds 1
    }
    if (Get-AppxPackage -Name $IdentityName -ErrorAction SilentlyContinue) {
        throw "Failed to remove test package '$IdentityName'."
    }
}