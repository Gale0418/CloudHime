function Find-AppxPackageForCleanup {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$IdentityName,

        [ValidateRange(1, 30)]
        [int]$MaxAttempts = 10
    )

    for ($attempt = 0; $attempt -lt $MaxAttempts; $attempt++) {
        if ($attempt -gt 0) {
            Start-Sleep -Seconds 1
        }
        $package = Get-AppxPackage -Name $IdentityName -ErrorAction SilentlyContinue |
            Sort-Object Version -Descending |
            Select-Object -First 1
        if ($null -ne $package) {
            return $package
        }
    }
    return $null
}

function Remove-AppxPackageForCleanup {
    [CmdletBinding()]
    param(
        [AllowNull()]
        [object]$InstalledPackage,

        [Parameter(Mandatory = $true)]
        [string]$IdentityName,

        [ValidateRange(1, 30)]
        [int]$MaxAttempts = 10
    )

    $cleanupPackage = $InstalledPackage
    if ($null -eq $cleanupPackage) {
        $cleanupPackage = Find-AppxPackageForCleanup -IdentityName $IdentityName -MaxAttempts $MaxAttempts
    }
    if ($null -ne $cleanupPackage) {
        Remove-AppxPackage -Package $cleanupPackage.PackageFullName -ErrorAction SilentlyContinue
    }
    return $cleanupPackage
}

function Activate-AppxApplication {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [AllowNull()]
        [object]$InstalledPackage,

        [string]$ApplicationId = "CloudHime"
    )

    if ($null -eq $InstalledPackage) {
        throw "Installed package is required for application activation."
    }

    $packageFamilyName = [string]$InstalledPackage.PackageFamilyName
    if ([string]::IsNullOrWhiteSpace($packageFamilyName)) {
        throw "Installed package is missing PackageFamilyName."
    }
    if ([string]::IsNullOrWhiteSpace($ApplicationId)) {
        throw "ApplicationId is required for application activation."
    }

    if ($null -eq ("AppxSmoke.IApplicationActivationManager" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

namespace AppxSmoke
{
    [Flags]
    public enum ActivateOptions
    {
        None = 0
    }

    [ComImport]
    [Guid("2e941141-7f97-4756-ba1d-9decde894a3d")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IApplicationActivationManager
    {
        void ActivateApplication(
            [MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments,
            ActivateOptions options,
            out uint processId);
    }

    [ComImport]
    [Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
    public class ApplicationActivationManager
    {
    }
}
"@
    }

    $aumid = "$packageFamilyName!$ApplicationId"
    $activationManager = [AppxSmoke.IApplicationActivationManager](New-Object AppxSmoke.ApplicationActivationManager)
    [uint32]$processId = 0
    $activationManager.ActivateApplication($aumid, $null, [AppxSmoke.ActivateOptions]::None, [ref]$processId)
    if ($processId -eq 0) {
        throw "Application activation returned no process ID for '$aumid'."
    }

    $process = Get-Process -Id ([int]$processId) -ErrorAction Stop
    return [pscustomobject]@{
        Aumid = $aumid
        ProcessId = [int]$processId
        Process = $process
    }
}
