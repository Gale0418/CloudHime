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