# run.ps1 — SignalPulse UI 一键启动 (前台模式)
# 用法：在项目根目录直接 `.\run.ps1`
$ErrorActionPreference = "Continue"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "[run] SignalPulse UI launcher" -ForegroundColor Cyan
Write-Host "[run] cwd: $ProjectRoot"

# 1) 杀旧 streamlit + 释放 8501
Get-Process streamlit -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
$portProc = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if ($portProc) { Stop-Process -Id $portProc.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

# 2) 清 pycache (避免旧 module 缓存)
Get-ChildItem "$ProjectRoot\src" -Recurse -Filter "__pycache__" -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 3) 环境变量
$env:PYTHONPATH = "src"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"

# 4) 启动 streamlit (前台)
Write-Host "[run] launching streamlit on http://localhost:8501" -ForegroundColor Green
Write-Host "[run] 按 Ctrl+C 停止" -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" -m streamlit run "src\signalpulse\ui\app.py" --server.port 8501 --server.headless true --server.address 0.0.0.0 --browser.gatherUsageStats false