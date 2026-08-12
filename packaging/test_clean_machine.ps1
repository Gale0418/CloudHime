[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,

    [ValidateRange(5, 120)]
    [int]$LaunchWaitSeconds = 20
)

$ErrorActionPreference = "Stop"
$executable = (Resolve-Path -LiteralPath $ExecutablePath -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Packaged executable not found: $executable"
}
if ([IO.Path]::GetExtension($executable) -ine ".exe") {
    throw "Clean-machine smoke requires a packaged .exe: $executable"
}

$systemRoot = [Environment]::GetEnvironmentVariable("SystemRoot", "Machine")
if ([string]::IsNullOrWhiteSpace($systemRoot)) {
    $systemRoot = $env:SystemRoot
}
if ([string]::IsNullOrWhiteSpace($systemRoot)) {
    throw "SystemRoot is not available."
}

$userEnvironment = @{
    TEMP = [IO.Path]::GetTempPath().TrimEnd("\", "/")
    TMP = [IO.Path]::GetTempPath().TrimEnd("\", "/")
    LOCALAPPDATA = [Environment]::GetEnvironmentVariable("LOCALAPPDATA", "User")
    APPDATA = [Environment]::GetEnvironmentVariable("APPDATA", "User")
    USERPROFILE = [Environment]::GetEnvironmentVariable("USERPROFILE", "User")
    HOMEDRIVE = [Environment]::GetEnvironmentVariable("HOMEDRIVE", "User")
    HOMEPATH = [Environment]::GetEnvironmentVariable("HOMEPATH", "User")
}

$startInfo = [Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = $executable
$startInfo.WorkingDirectory = [IO.Path]::GetDirectoryName($executable)
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$processEnvironment = $startInfo.EnvironmentVariables
$processEnvironment.Clear()
$processEnvironment["SystemRoot"] = $systemRoot
$processEnvironment["WINDIR"] = $systemRoot
$processEnvironment["PATH"] = "$systemRoot\System32;$systemRoot"
$processEnvironment["ComSpec"] = Join-Path $systemRoot "System32\cmd.exe"
$processEnvironment["PATHEXT"] = ".COM;.EXE;.BAT;.CMD"
$processEnvironment["ProgramData"] = [Environment]::GetEnvironmentVariable("ProgramData", "Machine")
foreach ($name in $userEnvironment.Keys) {
    $value = [string]$userEnvironment[$name]
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        $processEnvironment[$name] = $value
    }
}

$process = [Diagnostics.Process]::new()
$process.StartInfo = $startInfo
$processId = 0
try {
    if (-not $process.Start()) {
        throw "Packaged executable failed to start: $executable"
    }
    $processId = $process.Id
    $deadline = [DateTime]::UtcNow.AddSeconds($LaunchWaitSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($process.HasExited) {
            throw "Packaged executable exited before launch liveness window with code $($process.ExitCode)."
        }
        Start-Sleep -Milliseconds 250
    }
    Write-Output "Clean-machine packaged launch passed: PID=$processId, seconds=$LaunchWaitSeconds"
}
finally {
    if ($processId -gt 0) {
        if (-not $process.HasExited) {
            try {
                $process.Kill()
            } catch [InvalidOperationException] {
                if (-not $process.HasExited) {
                    throw
                }
            }
        }
        $process.WaitForExit(5000) | Out-Null
        if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
            throw "Failed to clean up packaged process PID $processId."
        }
    }
    $process.Dispose()
}
