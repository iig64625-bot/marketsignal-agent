# SignalPulse status
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot | Split-Path -Parent

function Write-OK($msg) { Write-Host "  [OK]   $msg" -ForegroundColor Green }
function Write-WARN($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-FAIL($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red }

Write-Host "=== SignalPulse Status ===" -ForegroundColor Cyan

# 1. process (by port 8501, most reliable)
$listen = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if ($listen) {
    $procs = Get-Process -Id $listen.OwningProcess -ErrorAction SilentlyContinue
    if ($procs) {
        $uptime = (Get-Date) - $procs.StartTime
        Write-OK "streamlit process: $($procs.ProcessName) PID $($procs.Id), started $($procs.StartTime.ToString('HH:mm:ss')), uptime $([int]$uptime.TotalMinutes)m, mem $([math]::Round($procs.WorkingSet/1MB,1)) MB"
    } else {
        Write-WARN "port 8501 listening but owner PID $($listen.OwningProcess) not accessible"
    }
} else {
    Write-FAIL "streamlit: not running (no process on port 8501)"
}

# 2. port
$listen = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if ($listen) {
    $pids = ($listen | ForEach-Object { $_.OwningProcess } | Sort-Object -Unique) -join ', '; Write-OK "port 8501: listening, PID $pids"
} else {
    Write-FAIL "port 8501: not listening"
}

# 3. health
$hc = try { (Invoke-WebRequest "http://localhost:8501/_stcore/health" -UseBasicParsing -ErrorAction Stop).StatusCode } catch { "FAIL" }
if ($hc -eq 200) {
    Write-OK "health: 200"
} else {
    Write-FAIL "health: $hc"
}

# 4. startup shortcut
$lnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\SignalPulse.lnk"
if (Test-Path $lnk) {
    Write-OK "auto-start: enabled (Startup shortcut)"
} else {
    Write-WARN "auto-start: NOT configured"
}

# 5. logs
$logDir = "$root\logs"
if (Test-Path "$logDir\manual.log") {
    $last = (Get-Item "$logDir\manual.log").LastWriteTime
    Write-OK "log: $last ($([math]::Round(((Get-Date) - $last).TotalMinutes, 1))m ago)"
} else {
    Write-WARN "log: not found"
}
