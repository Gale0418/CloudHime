$ErrorActionPreference = 'Stop'
if ($env:USERNAME -ne 'WDAGUtilityAccount') { throw 'Run only inside Windows Sandbox.' }
$result = [ordered]@{ schemaVersion=1; status='running'; stage='inventory'; startedUtc=[DateTime]::UtcNow.ToString('o'); executableSha256=''; checks=@{} }
function Save-Result {
    $result.updatedUtc = [DateTime]::UtcNow.ToString('o')
    $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath 'C:\TestOutput\result.json' -Encoding UTF8
}
try {
    $os = Get-CimInstance Win32_OperatingSystem
    $result.os = [ordered]@{ caption=$os.Caption; version=$os.Version; build=$os.BuildNumber; architecture=$os.OSArchitecture }
    $result.checks.tools = @('python','python3','py','pip','conda','ollama') | ForEach-Object {
        $name = $_
        $commands = @(Get-Command $name -ErrorAction SilentlyContinue)
        [ordered]@{ name=$name; paths=@($commands | ForEach-Object {$_.Source}) }
    }
    $result.checks.initialCloudHimeProfile = Test-Path (Join-Path $env:LOCALAPPDATA 'CloudHime')
    Save-Result
    $result.stage = 'copy-release'
    Save-Result
    Copy-Item -LiteralPath 'C:\Release' -Destination 'C:\CloudHime' -Recurse
    $exe = 'C:\CloudHime\CloudHime.exe'
    $result.executableSha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($result.executableSha256 -ne '3f32e40a332db9542d3278dadceb815051d6d0321565b11552d85e98a0c32d9c') { throw 'Unexpected executable hash.' }
    $result.stage = 'frozen-import'
    Save-Result
    $result.checks.importOutput = @(& 'C:\TestInput\test_clean_machine.ps1' -ExecutablePath $exe -FunctionalSmoke -AdditionalEnvironmentVariables @{CLOUDHIME_PACKAGED_IMPORT_SMOKE='1'})
    $result.checks.importPassed = $true
    $result.stage = 'launch-liveness'
    Save-Result
    $result.checks.launchOutput = @(& 'C:\TestInput\test_clean_machine.ps1' -ExecutablePath $exe -LaunchWaitSeconds 20)
    $result.checks.launchPassed = $true
    $result.status = 'passed'
    $result.stage = 'complete'
} catch {
    $result.status = 'failed'
    $result.error = $_.Exception.Message
} finally {
    Save-Result
}
