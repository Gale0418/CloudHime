[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath,

    [ValidateRange(5, 120)]
    [int]$LaunchWaitSeconds = 20,

    [hashtable]$AdditionalEnvironmentVariables = @{},

    [switch]$FunctionalSmoke,

    [ValidateRange(5, 600)]
    [int]$FunctionalTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

if (-not ("CloudHimeProcessTree" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class CloudHimeProcessTree
{
    private const uint SnapshotAllProcesses = 0x00000002;
    private const int InvalidHandleValue = -1;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct ProcessEntry32
    {
        public uint Size;
        public uint Usage;
        public uint ProcessId;
        public IntPtr DefaultHeapId;
        public uint ModuleId;
        public uint Threads;
        public uint ParentProcessId;
        public int Priority;
        public uint Flags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
        public string ExecutableFile;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint processId);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool Process32FirstW(IntPtr snapshot, ref ProcessEntry32 entry);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool Process32NextW(IntPtr snapshot, ref ProcessEntry32 entry);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    public static Dictionary<int, int> GetParentMap()
    {
        IntPtr snapshot = CreateToolhelp32Snapshot(SnapshotAllProcesses, 0);
        if (snapshot == IntPtr.Zero || snapshot.ToInt64() == InvalidHandleValue)
        {
            throw new Win32Exception(Marshal.GetLastWin32Error(), "Unable to enumerate Windows processes.");
        }

        var parents = new Dictionary<int, int>();
        try
        {
            var entry = new ProcessEntry32 { Size = (uint)Marshal.SizeOf(typeof(ProcessEntry32)) };
            if (!Process32FirstW(snapshot, ref entry))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Unable to read Windows process snapshot.");
            }
            do
            {
                parents[(int)entry.ProcessId] = (int)entry.ParentProcessId;
            }
            while (Process32NextW(snapshot, ref entry));
            return parents;
        }
        finally
        {
            CloseHandle(snapshot);
        }
    }
}
"@
}
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

function Get-DescendantProcessIds {
    param(
        [Parameter(Mandatory = $true)]
        [int]$RootProcessId
    )

    try {
        $snapshot = @{}
        foreach ($candidate in @(Get-CimInstance Win32_Process -ErrorAction Stop | Select-Object ProcessId, ParentProcessId)) {
            $snapshot[[int]$candidate.ProcessId] = [int]$candidate.ParentProcessId
        }
    } catch {
        $snapshot = [CloudHimeProcessTree]::GetParentMap()
    }
    $frontier = [System.Collections.Generic.List[int]]::new()
    $frontier.Add($RootProcessId)
    $seen = [System.Collections.Generic.HashSet[int]]::new()
    $result = [System.Collections.Generic.List[int]]::new()

    while ($frontier.Count -gt 0) {
        $parentId = $frontier[0]
        $frontier.RemoveAt(0)
        foreach ($candidateId in @($snapshot.Keys)) {
            if ([int]$snapshot[$candidateId] -ne $parentId -or [int]$candidateId -eq $RootProcessId) {
                continue
            }
            if ($seen.Add([int]$candidateId)) {
                $result.Add([int]$candidateId)
                $frontier.Add([int]$candidateId)
            }
        }
    }

    return @($result)
}

function Stop-OwnedDescendants {
    param(
        [Parameter(Mandatory = $true)]
        [int]$RootProcessId
    )

    $descendantIds = @(Get-DescendantProcessIds -RootProcessId $RootProcessId)
    foreach ($descendantId in ($descendantIds | Sort-Object -Descending)) {
        if ($descendantId -gt 0) {
            Stop-Process -Id $descendantId -Force -ErrorAction SilentlyContinue
        }
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(5)
    while ([DateTime]::UtcNow -lt $deadline) {
        $remaining = @(Get-DescendantProcessIds -RootProcessId $RootProcessId | Where-Object {
            Get-Process -Id $_ -ErrorAction SilentlyContinue
        })
        if ($remaining.Count -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 100
    }

    $remaining = @(Get-DescendantProcessIds -RootProcessId $RootProcessId | Where-Object {
        Get-Process -Id $_ -ErrorAction SilentlyContinue
    })
    if ($remaining.Count -gt 0) {
        throw "Failed to clean up owned descendant process IDs: $($remaining -join ', ')."
    }
}

$sandboxRoot = Join-Path ([IO.Path]::GetTempPath()) ("cloudhime-clean-machine-" + [Guid]::NewGuid().ToString("N"))
$localAppData = Join-Path $sandboxRoot "LocalAppData"
$appData = Join-Path $sandboxRoot "AppData"
$tempRoot = Join-Path $sandboxRoot "Temp"
New-Item -ItemType Directory -Force -Path $localAppData, $appData, $tempRoot | Out-Null

$userEnvironment = @{
    TEMP = $tempRoot
    TMP = $tempRoot
    LOCALAPPDATA = $localAppData
    APPDATA = $appData
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

foreach ($entry in $AdditionalEnvironmentVariables.GetEnumerator()) {
    $key = [string]$entry.Key
    if ([string]::IsNullOrWhiteSpace($key)) {
        throw "Additional environment variable name must not be empty."
    }
    $processEnvironment[$key] = [string]$entry.Value
}
$process = [Diagnostics.Process]::new()
$process.StartInfo = $startInfo
$processId = 0
try {
    if (-not $process.Start()) {
        throw "Packaged executable failed to start: $executable"
    }
    $processId = $process.Id
    if ($FunctionalSmoke) {
        $functionalDeadline = [DateTime]::UtcNow.AddSeconds($FunctionalTimeoutSeconds)
        while (-not $process.HasExited -and [DateTime]::UtcNow -lt $functionalDeadline) {
            Start-Sleep -Milliseconds 250
        }
        if (-not $process.HasExited) {
            throw "Packaged functional smoke timed out after $FunctionalTimeoutSeconds seconds."
        }
        if ($process.ExitCode -ne 0) {
            throw "Packaged functional smoke failed with exit code $($process.ExitCode)."
        }
        Write-Output "Clean-machine packaged functional smoke passed: PID=$processId"
    }
    else {
    $deadline = [DateTime]::UtcNow.AddSeconds($LaunchWaitSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($process.HasExited) {
            throw "Packaged executable exited before launch liveness window with code $($process.ExitCode)."
        }
        Start-Sleep -Milliseconds 250
    }
    Write-Output "Clean-machine packaged launch passed: PID=$processId, seconds=$LaunchWaitSeconds"
    }
}
finally {
    try {
        if ($processId -gt 0) {
            Stop-OwnedDescendants -RootProcessId $processId
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
    }
    finally {
        $process.Dispose()
        if (Test-Path -LiteralPath $sandboxRoot) {
            Remove-Item -LiteralPath $sandboxRoot -Recurse -Force -ErrorAction Stop
        }
        if (Test-Path -LiteralPath $sandboxRoot) {
            throw "Failed to remove clean-machine sandbox: $sandboxRoot"
        }
    }
}
