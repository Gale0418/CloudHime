[CmdletBinding(DefaultParameterSetName = 'AppxPackagePath')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'AppxPackagePath')]
    [string]$AppxPackagePath,
    [Parameter(Mandatory = $true, ParameterSetName = 'PackageFullName')]
    [string]$PackageFullName,
    [Parameter(Mandatory = $true)]
    [string]$ReportOutputPath,
    [string]$AppCertPath = 'C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-DirectoryWritable {
    param([Parameter(Mandatory = $true)][string]$Path)

    $probePath = Join-Path $Path ('.wack-write-probe-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $probe = [System.IO.File]::Open($probePath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        $probe.Dispose()
    } catch {
        throw "Report output parent is not writable: $Path"
    } finally {
        if ([System.IO.File]::Exists($probePath)) {
            [System.IO.File]::Delete($probePath)
        }
    }
}

# Appx cmdlets are hosted by Windows PowerShell on some machines, so bridge from pwsh.
if ($PSVersionTable.PSEdition -eq 'Core') {
    $windowsPowerShell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if (-not (Test-Path -LiteralPath $windowsPowerShell -PathType Leaf)) {
        throw 'Windows PowerShell 5.1 is required for Appx deployment cmdlets.'
    }

    $forwardedArgs = @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
    foreach ($boundParameter in $PSBoundParameters.GetEnumerator()) {
        $forwardedArgs += "-$($boundParameter.Key)"
        $forwardedArgs += [string]$boundParameter.Value
    }
    & $windowsPowerShell @forwardedArgs
    exit $LASTEXITCODE
}

$currentSessionId = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
if ($currentSessionId -eq 0 -or -not [Environment]::UserInteractive) {
    throw 'WACK requires an active interactive user session; Session 0 is not allowed.'
}

$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'WACK requires an elevated Administrator session.'
}

if (-not (Test-Path -LiteralPath $AppCertPath -PathType Leaf)) {
    throw "appcert.exe was not found: $AppCertPath"
}
$AppCertPath = (Resolve-Path -LiteralPath $AppCertPath -ErrorAction Stop).Path

$ReportOutputPath = [System.IO.Path]::GetFullPath($ReportOutputPath)
if ([System.IO.Path]::GetExtension($ReportOutputPath) -ine '.xml') {
    throw "Report output path must use the .xml extension: $ReportOutputPath"
}
$reportParent = Split-Path -LiteralPath $ReportOutputPath -Parent
if (-not (Test-Path -LiteralPath $reportParent -PathType Container)) {
    throw "Report output parent does not exist: $reportParent"
}
Assert-DirectoryWritable -Path $reportParent
if (Test-Path -LiteralPath $ReportOutputPath) {
    throw "Report output path already exists and will not be overwritten: $ReportOutputPath"
}

if ($PSCmdlet.ParameterSetName -eq 'AppxPackagePath') {
    if (-not (Test-Path -LiteralPath $AppxPackagePath -PathType Leaf)) {
        throw "Appx package path must be an existing file: $AppxPackagePath"
    }
    if ($AppxPackagePath -notmatch '(?i)\.(msix|appx|msixbundle|appxbundle)$') {
        throw "Unsupported package extension: $AppxPackagePath"
    }
    $AppxPackagePath = (Resolve-Path -LiteralPath $AppxPackagePath -ErrorAction Stop).Path
} else {
    $installedPackages = @(Get-AppxPackage | Where-Object { $_.PackageFullName -ceq $PackageFullName })
    if ($installedPackages.Count -ne 1) {
        throw "PackageFullName must exactly match one package installed for the current user: $PackageFullName"
    }
}

& $AppCertPath reset
if ($LASTEXITCODE -ne 0) {
    throw "appcert.exe reset failed with exit code $LASTEXITCODE."
}
if ($PSCmdlet.ParameterSetName -eq 'AppxPackagePath') {
    & $AppCertPath test -appxpackagepath $AppxPackagePath -reportoutputpath $ReportOutputPath
} else {
    & $AppCertPath test -packagefullname $PackageFullName -reportoutputpath $ReportOutputPath
}
if ($LASTEXITCODE -ne 0) {
    throw "appcert.exe test failed with exit code $LASTEXITCODE."
}

if (-not (Test-Path -LiteralPath $ReportOutputPath -PathType Leaf)) {
    throw "WACK did not create a report: $ReportOutputPath"
}
$reportFile = Get-Item -LiteralPath $ReportOutputPath -ErrorAction Stop
if ($reportFile.Length -le 0) {
    throw "WACK report is empty: $ReportOutputPath"
}
try {
    $report = [System.Xml.XmlDocument]::new()
    $report.Load($ReportOutputPath)
} catch {
    throw "WACK report is not valid XML: $ReportOutputPath"
}
$overallResults = @($report.SelectNodes("/REPORT/@OVERALL_RESULT"))
if ($overallResults.Count -ne 1) {
    throw "WACK report must contain exactly one OVERALL_RESULT value; found $($overallResults.Count)."
}
$overallResult = [string]$overallResults[0].Value
if ($overallResult -ine 'PASS') {
    throw "WACK OverallResult is not PASS: $overallResult"
}

Write-Output 'Status: Passed'
Write-Output "Mode: $($PSCmdlet.ParameterSetName)"
Write-Output "ReportOutputPath: $ReportOutputPath"
Write-Output "OverallResult: $overallResult"