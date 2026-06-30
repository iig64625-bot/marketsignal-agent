# run_scheduled.ps1 - SignalPulse 一键启动 (streamlit + scheduler daemon 后台)
$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "[sched] SignalPulse launcher (streamlit + scheduler daemon)" -ForegroundColor Cyan

# 1) 杀旧进程
Get-Process streamlit -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$portProc = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if ($portProc) { Stop-Process -Id $portProc.OwningProcess -Force -ErrorAction SilentlyContinue }
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
    $cmd -and ($cmd -like "*signalpulse.scheduler*" -or $cmd -like "*scheduler_daemon*")
} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 2) 清 pycache
Get-ChildItem "$ProjectRoot\src" -Recurse -Filter "__pycache__" -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 3) 环境
$env:PYTHONPATH = "src"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"

# 4) 启动 scheduler daemon (后台, 从 schedules.yaml 读 jobs)
Write-Host "[sched] launching scheduler daemon..." -ForegroundColor Green
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList @("-u", "scripts\scheduler_daemon.py") -WorkingDirectory $ProjectRoot -WindowStyle Hidden
Start-Sleep -Seconds 2

# 5) 启动 streamlit (后台)
Write-Host "[sched] launching streamlit on :8501..." -ForegroundColor Green
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList @("-m", "streamlit", "run", "src\signalpulse\ui\app.py", "--server.port", "8501", "--server.headless", "true", "--server.address", "0.0.0.0", "--browser.gatherUsageStats", "false") -WorkingDirectory $ProjectRoot -WindowStyle Hidden

# 6) 验证
Start-Sleep -Seconds 8
$port = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if ($port) {
    Write-Host ("[OK] Streamlit UP  PID={0}" -f $port.OwningProcess) -ForegroundColor Green
} else {
    Write-Host "[FAIL] 8501 not listening" -ForegroundColor Red
}
$schedRunning = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
    $cmd -and $cmd -like "*scheduler_daemon*"
}
if ($schedRunning) { Write-Host "[OK] scheduler daemon running" -ForegroundColor Green }
else { Write-Host "[WARN] scheduler daemon not detected (no schedules.yaml?)" -ForegroundColor Yellow }

Write-Host ""
Write-Host "Open http://localhost:8501" -ForegroundColor Cyan
Write-Host "Stop:  .\stop_all.ps1" -ForegroundColor Yellow