function Test-NeoExactPidInstance {
    param(
        [Parameter(Mandatory = $true)][string]$InstanceName,
        [Parameter(Mandatory = $true)][int]$TargetPid
    )

    $marker = "pid_${TargetPid}_"
    return $InstanceName.StartsWith($marker, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-NeoTraceTelemetrySnapshot {
    param(
        [Parameter(Mandatory = $true)][int]$LaunchedPid,
        [Parameter(Mandatory = $true)][int]$ListenerPid,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$InstanceNames,
        [Parameter(Mandatory = $true)][bool]$HadValidAttribution,
        [bool]$GraceExpired = $false
    )

    if ($LaunchedPid -ne $ListenerPid) {
        throw "candidate listener PID $ListenerPid differs from launched PID $LaunchedPid"
    }

    $invalid = @($InstanceNames | Where-Object { -not (Test-NeoExactPidInstance -InstanceName $_ -TargetPid $LaunchedPid) })
    if ($invalid.Count -gt 0) {
        throw "non-candidate WDDM instance accepted: $($invalid -join ', ')"
    }

    if ($InstanceNames.Count -eq 0 -and $HadValidAttribution) {
        throw "candidate WDDM telemetry disappeared after valid attribution"
    }
    if ($InstanceNames.Count -eq 0 -and $GraceExpired) {
        throw "no exact candidate-PID WDDM instance appeared within the grace period"
    }

    return [pscustomobject]@{
        Valid = ($InstanceNames.Count -gt 0)
        ExactMarker = "pid_${LaunchedPid}_"
        InstanceNames = @($InstanceNames)
    }
}
