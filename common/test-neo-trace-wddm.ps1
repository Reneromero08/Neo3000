$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "neo-trace-wddm.ps1")

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

Assert-True (Test-NeoExactPidInstance "pid_123_luid_0x0_phys_0" 123) "exact PID did not match"
Assert-True (-not (Test-NeoExactPidInstance "pid_1234_luid_0x0_phys_0" 123)) "PID prefix collision matched"
Assert-True (-not (Test-NeoExactPidInstance "pid_12_luid_0x0_phys_0" 123)) "short PID matched"

$valid = Assert-NeoTraceTelemetrySnapshot -LaunchedPid 123 -ListenerPid 123 `
    -InstanceNames @("pid_123_luid_0x0_phys_0") -HadValidAttribution $false
Assert-True $valid.Valid "valid exact-PID snapshot rejected"

$lossRejected = $false
try {
    Assert-NeoTraceTelemetrySnapshot -LaunchedPid 123 -ListenerPid 123 `
        -InstanceNames @() -HadValidAttribution $true | Out-Null
} catch { $lossRejected = $true }
Assert-True $lossRejected "telemetry loss after attribution did not reject"

$listenerRejected = $false
try {
    Assert-NeoTraceTelemetrySnapshot -LaunchedPid 123 -ListenerPid 124 `
        -InstanceNames @("pid_123_luid_0x0_phys_0") -HadValidAttribution $false | Out-Null
} catch { $listenerRejected = $true }
Assert-True $listenerRejected "listener PID mismatch did not reject"

$graceRejected = $false
try {
    Assert-NeoTraceTelemetrySnapshot -LaunchedPid 123 -ListenerPid 123 `
        -InstanceNames @() -HadValidAttribution $false -GraceExpired $true | Out-Null
} catch { $graceRejected = $true }
Assert-True $graceRejected "missing telemetry after grace did not reject"

Write-Output "neo trace WDDM tests passed"
