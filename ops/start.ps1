# Start SignalPulse
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot | Split-Path -Parent
$bat = "$root\run_streamlit.bat"
$logDir = "$root\logs"

if (!(Test-Path $bat)) { Write-Host "[FAIL] bat not found: $bat" -ForegroundColor Red; exit 1 }
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# kill any existing
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*streamlit*" } | Stop-Process -Force -ErrorAction SilentlyContinue
$port = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if ($port) { Stop-Process -Id $port.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

# start
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
Start-Process -FilePath $bat -RedirectStandardOutput "$logDir\manual-$ts.log" -RedirectStandardError "$logDir\manual-err-$ts.log" -NoNewWindow
Start-Sleep -Seconds 8

# verify
$hc = try { (Invoke-WebRequest "http://localhost:8501/_stcore/health" -UseBasicParsing -ErrorAction Stop).StatusCode } catch { "FAIL" }
if ($hc -eq 200) {
    Write-Host "[OK] started, health 200" -ForegroundColor Green
} else {
    Write-Host "[FAIL] started but health $hc" -ForegroundColor Red
    Write-Host "  log: $logDir\manual-err-$ts.log" -ForegroundColor Yellow
    exit 1
}
