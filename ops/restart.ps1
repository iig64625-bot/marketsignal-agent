# Restart SignalPulse
$ErrorActionPreference = "Continue"
& "$PSScriptRoot\stop.ps1"
Start-Sleep -Seconds 3
& "$PSScriptRoot\start.ps1"
