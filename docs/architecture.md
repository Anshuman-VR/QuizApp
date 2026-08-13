# System Architecture — ACE Cybersecurity Recruitment Quiz (v4)

**Role**: Single Source of Truth (SSOT)
**Stack**: FastAPI, PostgreSQL (asyncpg), WebSockets, Vanilla JS + CSS
**Deployment Target**: Single local laptop running via Ngrok / Cloudflare Quick Tunnel for 100 concurrent candidates over campus WiFi / hotspots.

---

## 1. Directory Structure
```text
/
├── backend/               # FastAPI Application
│   ├── main.py            # Entrypoint, CORS, Middleware, Rate Limits
│   ├── database.py        # Asyncpg Engine & Session Maker
│   ├── models.py          # SQLAlchemy ORM Models
│   ├── schemas.py         # Pydantic validation schemas
│   ├── auth.py            # JWT logic & Dependency Injection
│   ├── config.py          # Environment Variables (pydantic-settings)
│   ├── questions_loader.py# In-memory JSON cache for MCQ questions
│   ├── routers/           # API Endpoints (auth, quiz, admin, recon)
│   └── ws/                # WebSocket handlers (timer)
├── frontend/              # Static Frontend Assets
│   ├── css/style.css      # Brutalist Design System (Blue/Black theme)
│   ├── js/                # Client logic (login.js, quiz.js, admin.js)
│   ├── aceCyberLogo.png   # Transparent logo
│   └── *.html             # Views (index, quiz, admin)
├── scripts/               # Utility scripts (seed, load tests)
│   └── locust_test.py     # 100-user load testing script
├── docs/
│   └── architecture.md    # SSOT
├── questions.txt          # Source material for questions
├── requirements.txt       # Python dependencies
├── .env                   # Secrets & config
└── start_server.ps1       # Bootstraps Docker DB, NTP sync, auto-backups, and 4 Uvicorn workers
```

---

## 2. Database Schema (PostgreSQL)

All state lives in the database to allow multi-worker horizontal scaling.

### `students`
- `reg_no` (VARCHAR, PK) — E.g., `128158003`.
- `name` (VARCHAR)
- `year` (INT)
- `branch` (VARCHAR)

### `session`
Tracks quiz lifecycle per student per quiz.
- `reg_no` (VARCHAR, PK, FK -> students)
- `quiz_id` (INT, PK) — Default `1`.
- `session_token` (VARCHAR) — **Critical for Single-Device Enforcement**.
- `start_time` (TIMESTAMPTZ) — Server-authoritative start time. Inserted natively from Python in UTC to completely bypass "Windows Docker Clock Drift".
- `finish_time` (TIMESTAMPTZ, Nullable)
- `score` (INT) — Calculated on submission.
- `hassubmitted` (BOOLEAN) — Default `false`.

### `options`
Read-only seed data mapping questions to correct answers.
- `quiz_id` (INT, PK)
- `question_no` (INT, PK)
- `correctanswer` (VARCHAR(1)) — 'A', 'B', 'C', or 'D'.

### `studentanswers`
- `reg_no` (VARCHAR, PK, FK -> students)
- `quiz_id` (INT, PK)
- `question_no` (INT, PK)
- `option` (VARCHAR(1)) — The student's chosen answer.

---

## 3. Core Logic & API Routing

### Auth & Connection Lifecycle
- **`GET /api/resume`**: Called on every page load. Reads the JWT cookie, verifies it against the DB `session_token`. Returns status without mutating the DB. Enables seamless reconnects if wifi drops.
- **`POST /api/login`**: Open registration. Uses a race-safe `INSERT ... ON CONFLICT DO NOTHING`. Generates a new `session_token` UUID, writes it to the DB, and issues a JWT in an `HttpOnly` cookie. **This instantly invalidates the session on any other device using the same reg_no.**
- **Rate Limiting**: Set to 60 req/minute per IP for `/api/login` to prevent blocking legitimate students sharing a campus NAT.

### Timer & WebSockets
The timer is **Server-Authoritative**. The laptop's system clock (synced via NTP on boot) is the only source of truth.
- **`ws://.../ws/timer`**: Authenticates via JWT cookie. Reads `start_time` from DB. Every **8 seconds**, it queries the DB to calculate remaining time and pushes a tick to the client.
- **Client Interpolation**: Between the 8-second ticks, the frontend JS interpolates the countdown locally.
- **HTTP Fallback**: If the WebSocket drops (e.g., mobile hotspot switching), the frontend transparently falls back to polling `GET /api/quiz/state` every 8 seconds.

### Quiz Execution
- **`GET /api/quiz/question/{n}`**: Returns question text and options, plus the user's previously saved answer (if any).
- **`POST /api/quiz/answer`**: Uses `INSERT ... ON CONFLICT DO UPDATE` (upsert) to guarantee atomicity. Returns `{"saved": true}`. The frontend will retry up to 3 times with exponential backoff if this fails.
- **`POST /api/quiz/submit`**: Auto-computes the score via a SQL `JOIN` against the `options` table. Sets `hassubmitted = true` atomically.

---

## 4. Security & Admin

### Anti-Cheating & Exploitation
1. **No LocalStorage**: All session identity relies on `HttpOnly`, `Secure`, `SameSite=Lax` cookies. Token theft via XSS is impossible.
2. **First-Write Wins**: If two people try to register `128158003` at the exact same millisecond, the DB constraint drops the second insert. The backend then verifies that the provided `name` matches the one in the DB.
3. **Session Highjacking**: If an attacker gets someone's reg_no and logs in, the DB `session_token` rotates. The victim's socket closes. When the victim logs back in, the attacker is kicked.
4. **Recon Honeypot**: `/api/recon` logs anyone running automated enumeration tools (like `dirb` or `nmap` scripts) to `easter_egg.log`.

### Admin Tools (Localhost Only)
The `/api/admin/*` endpoints are protected by a strict middleware check: if `request.client.host` is not `127.0.0.1`, it returns a 404.
- **Dashboard**: Live stats (avg score, submitted count).
- **Remediation (`PATCH /extend`)**: In case of a laptop crash, the admin can add 10 minutes to a student's `start_time` without wiping their saved answers.
- **Destructive Reset (`DELETE /session`)**: Completely wipes a student's answers and session if they need a total restart.
- **Auto-Backups**: The `start_server.ps1` script runs `pg_dump` every 10 minutes and saves the SQL snapshot locally.
