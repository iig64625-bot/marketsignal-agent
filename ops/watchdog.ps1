# SignalPulse Watchdog ? ?????
$port = 8501
$projectRoot = 'D:\marketsignal-agent'
$logFile = "$projectRoot\logs\watchdog.log"

$listen = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
$healthy = $false
if ($listen) {
    try {
        $hc = Invoke-WebRequest "http://localhost:$port/_stcore/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($hc.StatusCode -eq 200) { $healthy = $true }
    } catch { }
}

if ($healthy) {
    Add-Content -Path $logFile -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] OK PIDs $(($listen.OwningProcess | Sort-Object -Unique) -join ',')"
} else {
    Add-Content -Path $logFile -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] FAIL down, restarting"
    & "$projectRoot\ops\start.ps1"
    Start-Sleep -Seconds 10
    $listen2 = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listen2) {
        Add-Content -Path $logFile -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] OK restarted PIDs $(($listen2.OwningProcess | Sort-Object -Unique) -join ',')"
    } else {
        Add-Content -Path $logFile -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] CRITICAL restart failed"
    }
}