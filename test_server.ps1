# ACE Cybersecurity Quiz - TEST Server Startup Script
# -----------------------------------------------------------------
# Use this for dry runs and load testing.
# WIPES THE DATABASE clean on every start.
# -----------------------------------------------------------------

Write-Host ""
Write-Host "======================================" -ForegroundColor Yellow
Write-Host "  ACE Cybersecurity Quiz - TEST MODE  " -ForegroundColor Yellow
Write-Host "======================================" -ForegroundColor Yellow
Write-Host ""

# 1. Check PostgreSQL service is running
$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Running" }
if (-not $pgService) {
    Write-Host "[ERROR] PostgreSQL service is NOT running. Start it with:" -ForegroundColor Red
    Write-Host "        Start-Service postgresql*" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] PostgreSQL service is running." -ForegroundColor Green

# 2. Read DB password from .env
$envVars = @{}
Get-Content ".env" | Where-Object { $_ -match "^[^#]" } | ForEach-Object {
    $parts = $_ -split "=", 2
    if ($parts.Length -eq 2) { $envVars[$parts[0].Trim()] = $parts[1].Trim() }
}
$dbUrl = $envVars["DATABASE_URL"]
# Extract password from postgresql+asyncpg://user:password@host:port/db
if ($dbUrl -match "://([^:]+):([^@]+)@") {
    $env:PGPASSWORD = $matches[2]
    $pgUser = $matches[1]
} else {
    $env:PGPASSWORD = "postgres"
    $pgUser = "postgres"
}

# 3. Clear DB tables for clean test environment
Write-Host "[INFO] Truncating database tables for test run..." -ForegroundColor Cyan
& psql -U $pgUser -h localhost -d quizapp -c "TRUNCATE TABLE studentanswers, session, students RESTART IDENTITY CASCADE;" 2>$null
Write-Host "[OK] Database cleared." -ForegroundColor Green

# 4. Sync system clock (NTP)
Write-Host "[INFO] Syncing system clock (NTP)..." -ForegroundColor Cyan
w32tm /resync /force 2>$null | Out-Null
Write-Host "[OK] Clock synced." -ForegroundColor Green

# 5. Create backup directory if needed
if (-not (Test-Path ".\backups")) { New-Item -ItemType Directory -Path ".\backups" | Out-Null }

# 6. Set PYTHONPATH
$env:PYTHONPATH = (Get-Location).Path

Write-Host ""
Write-Host "[START] Launching FastAPI on http://0.0.0.0:3000 [TEST MODE]" -ForegroundColor Yellow
Write-Host "[INFO]  Admin panel: http://localhost:3000/admin.html (localhost only)" -ForegroundColor Cyan
Write-Host "[INFO]  Load test: python -m locust -f scripts/locust_test.py --host http://localhost:3000 --users 100 --spawn-rate 10" -ForegroundColor Cyan
Write-Host ""

# 7. Launch server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 3000
