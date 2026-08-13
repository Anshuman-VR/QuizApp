# =============================================================================
# ACE Cybersecurity Quiz — One-Shot Server Setup Script
# Run this ONCE on a fresh Windows machine to provision everything.
# =============================================================================
# Prerequisites (install these manually first):
#   1. Python 3.11+  — https://www.python.org/downloads/
#   2. PostgreSQL 16 — https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
#      During install: remember the postgres user password you set!
#   3. Git           — https://git-scm.com/download/win
#   4. cloudflared   — https://github.com/cloudflare/cloudflared/releases (download .msi)
# =============================================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ACE Quiz — Server Setup (Run Once)       " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── STEP 1: Verify prerequisites ──────────────────────────────────────────────
Write-Host "[CHECK] Verifying prerequisites..." -ForegroundColor Cyan

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { Write-Host "[WARN] Python not found via Get-Command. Hoping it works anyway!" -ForegroundColor Yellow }
else { Write-Host "[OK] Python: $($python.Source)" -ForegroundColor Green }

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) { Write-Host "[WARN] Git not found via Get-Command. Hoping it works anyway!" -ForegroundColor Yellow }
else { Write-Host "[OK] Git: $($git.Source)" -ForegroundColor Green }

$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    Write-Host "[WARN] psql not found via Get-Command. Hoping it works anyway!" -ForegroundColor Yellow
} else {
    Write-Host "[OK] psql: $($psql.Source)" -ForegroundColor Green
}

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    Write-Host "[WARN] cloudflared not found. You can install it later." -ForegroundColor Yellow
    Write-Host "       Download from: https://github.com/cloudflare/cloudflared/releases" -ForegroundColor Yellow
} else {
    Write-Host "[OK] cloudflared: $($cloudflared.Source)" -ForegroundColor Green
}

# ── STEP 2: Collect configuration ─────────────────────────────────────────────
Write-Host ""
Write-Host "[INPUT] Enter configuration values:" -ForegroundColor Cyan

$pgPassword = Read-Host "  PostgreSQL 'postgres' user password (set during install)"
$adminSecret = Read-Host "  Admin dashboard password (you choose)"
$tunnelDomain = Read-Host "  Cloudflare tunnel URL (press Enter to skip for now)"
if (-not $tunnelDomain) { $tunnelDomain = "https://CHANGE_ME.cfargotunnel.com" }

# Generate JWT secret
$jwtSecret = python -c "import secrets; print(secrets.token_hex(32))"
Write-Host "[OK] JWT secret generated." -ForegroundColor Green

# ── STEP 3: Create .env ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[INFO] Creating .env file..." -ForegroundColor Cyan

$envContent = @"
# Secrets - DO NOT COMMIT
DATABASE_URL=postgresql+asyncpg://postgres:$pgPassword@localhost:5432/quizapp
JWT_SECRET=$jwtSecret
JWT_EXPIRE_MINUTES=100
ADMIN_SECRET=$adminSecret
PORT=3000
QUIZ_ID=1
TUNNEL_DOMAIN=$tunnelDomain
EASTER_EGG_SECRET=ACE{y0u_f0und_1t}
EASTER_EGG_FLAG=ACE{c4mpu5_3y35_4r3_4lw4y5_w4tch1ng}
"@

$envContent | Out-File -FilePath ".env" -Encoding utf8 -NoNewline
Write-Host "[OK] .env created." -ForegroundColor Green

# ── STEP 4: Install Python dependencies ───────────────────────────────────────
Write-Host ""
Write-Host "[INFO] Installing Python dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] pip install failed." -ForegroundColor Red; exit 1 }
Write-Host "[OK] Python dependencies installed." -ForegroundColor Green

# ── STEP 5: Create PostgreSQL database and schema ─────────────────────────────
Write-Host ""
Write-Host "[INFO] Setting up PostgreSQL database..." -ForegroundColor Cyan
$env:PGPASSWORD = $pgPassword

# Create the database (ignore error if already exists)
& psql -U postgres -h localhost -c "CREATE DATABASE quizapp;" 2>$null
Write-Host "[OK] Database 'quizapp' ready." -ForegroundColor Green

# Create schema
$schema = @"
CREATE TABLE IF NOT EXISTS students (
    reg_no  VARCHAR(9) PRIMARY KEY,
    name    VARCHAR(100) NOT NULL,
    year    INTEGER,
    branch  VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS quiz (
    quiz_id    INTEGER PRIMARY KEY,
    name       VARCHAR(50) NOT NULL,
    time_limit INTEGER NOT NULL DEFAULT 60,
    isactive   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS options (
    quiz_id       INTEGER REFERENCES quiz(quiz_id),
    question_no   INTEGER,
    correctanswer VARCHAR(1) NOT NULL,
    PRIMARY KEY (quiz_id, question_no)
);

CREATE TABLE IF NOT EXISTS session (
    reg_no        VARCHAR(9) REFERENCES students(reg_no),
    quiz_id       INTEGER REFERENCES quiz(quiz_id),
    session_token VARCHAR(64) UNIQUE,
    start_time    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finish_time   TIMESTAMPTZ,
    hassubmitted  BOOLEAN DEFAULT FALSE,
    score         INTEGER,
    PRIMARY KEY (reg_no, quiz_id)
);

CREATE TABLE IF NOT EXISTS studentanswers (
    reg_no      VARCHAR(9),
    quiz_id     INTEGER,
    question_no INTEGER,
    option      VARCHAR(1) NOT NULL,
    PRIMARY KEY (reg_no, quiz_id, question_no)
);
"@

$schema | & psql -U postgres -h localhost -d quizapp
Write-Host "[OK] Schema created." -ForegroundColor Green

# ── STEP 6: Seed quiz and answer key ──────────────────────────────────────────
Write-Host ""
Write-Host "[INFO] Seeding quiz metadata and answer key..." -ForegroundColor Cyan
$env:PYTHONPATH = (Get-Location).Path
python scripts/seed_db.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] seed_db.py failed or not found. Run manually if needed." -ForegroundColor Yellow
} else {
    Write-Host "[OK] Quiz seeded." -ForegroundColor Green
}

# ── STEP 7: Create backups directory ──────────────────────────────────────────
if (-not (Test-Path ".\backups")) { New-Item -ItemType Directory -Path ".\backups" | Out-Null }
Write-Host "[OK] Backups directory ready." -ForegroundColor Green

# ── STEP 8: Cloudflare Named Tunnel setup ─────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Cloudflare Tunnel Setup (Optional)       " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

if ($cloudflared) {
    Write-Host ""
    Write-Host "Run these commands in order to create a permanent tunnel:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  1. cloudflared tunnel login" -ForegroundColor White
    Write-Host "  2. cloudflared tunnel create ace-quiz" -ForegroundColor White
    Write-Host "  3. cloudflared tunnel route dns ace-quiz ace-quiz" -ForegroundColor White
    Write-Host "  4. Update TUNNEL_DOMAIN in your .env to: https://ace-quiz.cfargotunnel.com" -ForegroundColor White
    Write-Host ""
    Write-Host "Then to run the tunnel:" -ForegroundColor Yellow
    Write-Host "  cloudflared tunnel run ace-quiz" -ForegroundColor White
} else {
    Write-Host "[WARN] Install cloudflared and follow the tunnel setup steps in docs/docs.md." -ForegroundColor Yellow
}

# ── DONE ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Setup Complete!                          " -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start the server:" -ForegroundColor White
Write-Host "  .\start_server.ps1     (production - keeps DB)" -ForegroundColor Cyan
Write-Host "  .\test_server.ps1      (testing - wipes DB)" -ForegroundColor Yellow
Write-Host ""
