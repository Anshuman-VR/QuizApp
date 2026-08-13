# ACE Cybersecurity Recruitment Quiz — Operator's Manual

This document outlines how to test, run, and administer the quiz application.

## 1. Operating the Server

You have two startup scripts depending on your environment:

### Testing Mode (`.\test_server.ps1`)
Use this when you are doing dry runs or load testing.
- Checks if the Docker database is running.
- **Wipes the database** (`TRUNCATE TABLE`) completely clean.
- Syncs the system clock (NTP).
- Starts the auto-backup job.
- Launches the FastAPI backend.

### Production / Event Day (`.\start_server.ps1`)
Use this on the actual day of the recruitment drive.
- Checks if the Docker database is running.
- **Does NOT wipe the database**. All student sessions and answers are preserved.
- Syncs the system clock (NTP).
- Starts the auto-backup job (saves to `./backups/` every 10 minutes).
- Launches the FastAPI backend.

## 2. Exposing to the Internet (Cloudflare Quick Tunnel)
Since the server runs on a single local laptop on a campus network, we use Cloudflare to punch a hole through the NAT/firewall without needing a paid domain or router access.

1. Ensure your server is running.
2. In a separate terminal, run:
   ```powershell
   cloudflared tunnel --url http://localhost:3000
   ```
3. Cloudflare will output a temporary HTTPS URL (e.g., `https://example.trycloudflare.com`).
4. Give this URL to the candidates.

*WARNING: Do not restart the Cloudflare tunnel once the event starts, as the URL will change!*

## 3. Load Testing (Locust)
To verify the system can handle 100 concurrent candidates, a Locust script is provided.

1. Install Locust: `pip install locust`
2. Run the load test against the tunnel:
   ```powershell
   python -m locust -f scripts/locust_test.py --host https://<YOUR-CLOUDFLARE-URL>.trycloudflare.com --users 100 --spawn-rate 10
   ```
3. Open `http://localhost:8089` to view the Locust dashboard and start the simulation.
4. *Note: The load test script is smart enough to stop trying to answer questions once a simulated user submits their quiz, accurately reflecting real user flows.*

## 4. Admin Dashboard
The Admin dashboard provides live statistics and remediation tools.

**Access**: `http://localhost:3000/admin.html`
*Security Constraint: The admin endpoints will throw a 404 Not Found if accessed from any IP other than `127.0.0.1`. You must open it on the host laptop itself.*

**Features**:
- **Live Stats**: View total registered, total submitted, and average score.
- **Results Export**: Download a CSV of all student scores and details.
- **Remediation (+10M)**: If a student's laptop crashes, you can add 10 minutes to their timer. This alters their `start_time` in the database without destroying any of their previously saved answers.
- **Total Reset (Trash)**: This is a destructive action that wipes the student's session and answers entirely, forcing them to start from question 1.

## 5. Security & Fallbacks
- **Single-Device Enforcement**: If a student logs in on a second device, their `session_token` rotates in the database. Their first device's WebSocket connection is immediately killed, and they are logged out.
- **WiFi Drop Fallback**: If the campus WiFi drops, the WebSocket closes. The frontend immediately falls back to HTTP polling (`GET /api/quiz/state`) every 8 seconds, ensuring the UI and timer never freeze.
- **Docker Clock Drift Immunity**: Windows laptops often suffer from severe clock drift inside Docker VMs after sleeping. The application bypasses this entirely by injecting the exact native Windows UTC time into the database when a student logs in.
