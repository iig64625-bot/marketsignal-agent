# Tail logs
$ErrorActionPreference = "Continue"
$root = $PSScriptRoot | Split-Path -Parent
$logDir = "$root\logs"

if (!(Test-Path $logDir)) { Write-Host "[FAIL] log dir not found" -ForegroundColor Red; exit 1 }

$latest = Get-ChildItem $logDir -Filter "*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3
if (!$latest) { Write-Host "[FAIL] no log files" -ForegroundColor Red; exit 1 }

foreach ($f in $latest) {
    Write-Host ""
    Write-Host "=== $($f.Name) (last 20) ===" -ForegroundColor Cyan
    Get-Content $f.FullName -Tail 20 -ErrorAction SilentlyContinue
}
