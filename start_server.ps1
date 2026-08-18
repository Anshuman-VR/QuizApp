# ACE Cybersecurity Quiz - PRODUCTION Server Startup Script
# -----------------------------------------------------------------
# Run this on event day. Does NOT wipe the database.
# Cloudflare Quick Tunnel (run in a separate terminal AFTER this):
#   .\cloudflared.exe tunnel --url http://localhost:3000 --protocol http2
#   (--protocol http2 forces TCP only — required on campus networks where UDP/QUIC is blocked)
# -----------------------------------------------------------------

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  ACE Cybersecurity Quiz - PRODUCTION " -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Disable QuickEdit mode in Windows registry so console clicks never freeze output
Set-ItemProperty -Path "HKCU:\Console" -Name "QuickEdit" -Value 0 -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKCU:\Console" -Name "InsertMode" -Value 0 -ErrorAction SilentlyContinue

# 1. Check PostgreSQL service is running
$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Running" }
if (-not $pgService) {
    Write-Host "[ERROR] PostgreSQL service is NOT running. Start it with:" -ForegroundColor Red
    Write-Host "        Start-Service postgresql*" -ForegroundColor Red
    Write-Host "   OR open Services (services.msc) and start it manually." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] PostgreSQL service is running." -ForegroundColor Green

# 2. Sync system clock (NTP)
Write-Host "[INFO] Syncing system clock (NTP)..." -ForegroundColor Cyan
w32tm /resync /force 2>$null | Out-Null
Write-Host "[OK] Clock synced." -ForegroundColor Green

# 3. Create backup directory if needed
if (-not (Test-Path ".\backups")) { New-Item -ItemType Directory -Path ".\backups" | Out-Null }

# 4. Scheduled DB backup every 10 minutes
$backupJob = Start-Job -ScriptBlock {
    param($pwd, $pgPass)
    $env:PGPASSWORD = $pgPass
    while ($true) {
        Start-Sleep -Seconds 600
        $ts = Get-Date -Format "yyyyMMdd_HHmmss"
        $outFile = Join-Path $pwd "backups\quizapp_$ts.sql"
        & pg_dump -U postgres -h localhost quizapp | Out-File -FilePath $outFile -Encoding utf8
        Write-Host "[BACKUP] Saved: $outFile" -ForegroundColor Cyan
    }
} -ArgumentList (Get-Location).Path, (python -c "from dotenv import dotenv_values; print(dotenv_values('.env').get('DATABASE_URL','').split(':')[2].split('@')[0])" 2>$null)

Write-Host "[OK] Auto-backup job started (every 10 min -> ./backups/)" -ForegroundColor Green

# 5. Set PYTHONPATH
$env:PYTHONPATH = (Get-Location).Path

Write-Host ""
Write-Host "[START] Launching FastAPI on http://0.0.0.0:3000" -ForegroundColor Cyan
Write-Host "[INFO]  Admin panel: http://localhost:3000/admin.html (localhost only)" -ForegroundColor Yellow
Write-Host "[INFO]  Then run in another terminal: cloudflared tunnel run ace-quiz" -ForegroundColor Yellow
Write-Host ""

# 6. Launch server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 3000

# Cleanup backup job on exit
Stop-Job $backupJob
Remove-Job $backupJob
