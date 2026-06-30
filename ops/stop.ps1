# Stop SignalPulse
$ErrorActionPreference = "Continue"

$procs = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*streamlit*" }
if ($procs) {
    $procs | Stop-Process -Force
    Write-Host "[OK] killed streamlit (PID $($procs.Id))" -ForegroundColor Green
} else {
    Write-Host "[WARN] no streamlit process found" -ForegroundColor Yellow
}

$port = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if ($port) {
    Stop-Process -Id $port.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "[OK] freed port 8501" -ForegroundColor Green
} else {
    Write-Host "[OK] port 8501 already free" -ForegroundColor Green
}
