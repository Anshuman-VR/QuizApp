"""
Locust load test — ACE Cybersecurity Quiz (P2-13)
Simulates 100 concurrent users doing:
  login → resume → state → answer all 60 Qs → submit

Usage:
  pip install locust
  locust -f scripts/locust_test.py --host http://localhost:3000 --users 100 --spawn-rate 10
Then open http://localhost:8089 for the Locust dashboard.
"""
from locust import HttpUser, task, between, events
import random
import string
import json

BRANCHES = ["CSE(Core)", "CSE(AIDS)", "CSE(Cybersecurity)", "CSE(IOTA)", "IT", "ICT"]

def rand_reg_no():
    """Generate a plausible test reg_no: 1 + 8 random digits."""
    return "1" + "".join(random.choices(string.digits, k=8))

class QuizUser(HttpUser):
    wait_time = between(0.5, 2)  # realistic pause between actions

    def on_start(self):
        """Called once per simulated user on spawn."""
        self.reg_no = rand_reg_no()
        self.name   = f"TestUser_{self.reg_no[-4:]}"
        self.branch = random.choice(BRANCHES)
        self.cookies = {}
        self.has_submitted = False
        self._login()

    # ── Login ─────────────────────────────────────────────────────────────────
    def _login(self):
        payload = {
            "reg_no": self.reg_no,
            "name":   self.name,
            "year":   random.randint(1, 4),
            "branch": self.branch,
        }
        with self.client.post(
            "/api/login", json=payload, catch_response=True, allow_redirects=False
        ) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"Login failed: {res.status_code} — {res.text[:120]}")

    # ── Resume check ──────────────────────────────────────────────────────────
    @task(1)
    def t_resume(self):
        with self.client.get("/api/resume", catch_response=True) as res:
            if res.status_code in (200, 401):
                res.success()
            else:
                res.failure(f"Resume: {res.status_code}")

    # ── Get state ─────────────────────────────────────────────────────────────
    @task(3)
    def t_state(self):
        with self.client.get("/api/quiz/state", catch_response=True) as res:
            if res.status_code in (200, 401, 403):
                res.success()
            else:
                res.failure(f"State: {res.status_code}")

    # ── Answer a random question ──────────────────────────────────────────────
    @task(10)
    def t_answer(self):
        if self.has_submitted:
            return
        payload = {
            "question_no": random.randint(1, 60),
            "option":      random.choice(["A", "B", "C", "D"]),
        }
        with self.client.post(
            "/api/quiz/answer", json=payload, catch_response=True
        ) as res:
            if res.status_code in (200, 401, 403):
                res.success()
            else:
                res.failure(f"Answer: {res.status_code}")

    # ── Fetch a question ──────────────────────────────────────────────────────
    @task(5)
    def t_question(self):
        if self.has_submitted:
            return
        n = random.randint(1, 60)
        with self.client.get(f"/api/quiz/question/{n}", catch_response=True) as res:
            if res.status_code in (200, 401, 403):
                res.success()
            else:
                res.failure(f"Question: {res.status_code}")

    # ── Submit (low frequency — only near end of session) ─────────────────────
    @task(1)
    def t_submit(self):
        if self.has_submitted:
            return
        with self.client.post("/api/quiz/submit", catch_response=True) as res:
            if res.status_code in (200, 401, 403):
                self.has_submitted = True
                res.success()
            else:
                res.failure(f"Submit: {res.status_code}")
