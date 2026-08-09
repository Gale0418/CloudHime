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

function Assert-ProcessLaunchLiveness {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [object]$Process
    )

    if (-not $Process.HasExited) {
        return
    }

    $exitCode = [int]$Process.ExitCode
    if ($exitCode -eq 0) {
        throw "Packaged executable exited before launch liveness window."
    }

    throw "Packaged executable exited with code $exitCode before launch liveness window."
}



$helperPath = Join-Path $PSScriptRoot "msix_install_helpers.ps1"
if (-not (Test-Path -LiteralPath $helperPath -PathType Leaf)) {
    throw "MSIX install helper not found: $helperPath"
}
. $helperPath

# Appx cmdlets are hosted by Windows PowerShell on some machines, so bridge from pwsh.
if ($PSVersionTable.PSEdition -eq "Core") {
    $windowsPowerShell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
    if (-not (Test-Path -LiteralPath $windowsPowerShell -PathType Leaf)) {
        throw "Windows PowerShell 5.1 is required for Appx deployment cmdlets."
    }
    $forwardedArgs = @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $PSCommandPath,
        "-PackagePath",
        $PackagePath,
        "-IdentityName",
        $IdentityName,
        "-ExecutableName",
        $ExecutableName,
        "-LaunchWaitSeconds",
        $LaunchWaitSeconds
    )
    & $windowsPowerShell @forwardedArgs
    exit $LASTEXITCODE
}

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

    $process = Start-Process -FilePath $executablePath -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds $LaunchWaitSeconds
    Assert-ProcessLaunchLiveness -Process $process
    Write-Host "Installed and launched $IdentityName from $($installed.InstallLocation)."
}
finally {
    if ($null -ne $process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    Remove-AppxPackageForCleanup -InstalledPackage $installed -IdentityName $IdentityName | Out-Null

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