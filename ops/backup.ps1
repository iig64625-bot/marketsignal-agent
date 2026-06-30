# SignalPulse ????
# ?? data/ + configs/ + .env ? D:\backups\signalpulse\
# ???? 28 ?

$ErrorActionPreference = 'Stop'
$projectRoot = 'D:\marketsignal-agent'
$backupRoot  = 'D:\backups\signalpulse'
$ts   = Get-Date -Format 'yyyyMMdd-HHmmss'
$dest = Join-Path $backupRoot "backup-$ts"

if (-not (Test-Path $backupRoot)) {
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
}
New-Item -ItemType Directory -Path $dest -Force | Out-Null

if (Test-Path "$projectRoot\data") {
    Copy-Item "$projectRoot\data" "$dest\data" -Recurse -Force
    Write-Host "[OK] data/"
}
if (Test-Path "$projectRoot\configs") {
    Copy-Item "$projectRoot\configs" "$dest\configs" -Recurse -Force
    Write-Host "[OK] configs/"
}
if (Test-Path "$projectRoot\.env") {
    Copy-Item "$projectRoot\.env" "$dest\.env"
    Write-Host "[OK] .env"
}

$size = (Get-ChildItem $dest -Recurse | Measure-Object -Property Length -Sum).Sum
Write-Host "[DONE] $dest ($([math]::Round($size/1MB, 2)) MB)"

$cutoff = (Get-Date).AddDays(-28)
Get-ChildItem -Path $backupRoot -Directory -Filter 'backup-*' |
    Where-Object { $_.CreationTime -lt $cutoff } |
    ForEach-Object {
        Write-Host "[DEL] $($_.Name)"
        Remove-Item $_.FullName -Recurse -Force
    }
Write-Host "[CLEAN] removed backups older than 28 days"