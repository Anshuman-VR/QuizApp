# ACE Cybersecurity Recruitment Quiz Platform - Architecture & File Structure

This document outlines the purpose of each file and folder in this project to help you navigate the codebase.

## Directory Structure

```text
AceCyberRecruitments/
├── backend/                  # The FastAPI backend application
│   ├── routers/              # API Endpoints mapped by domain
│   │   ├── admin.py          # /api/admin/* endpoints (stats, results, resets)
│   │   ├── auth.py           # /api/login and /api/logout logic
│   │   ├── quiz.py           # /api/quiz/* (state, questions, answer saving, submitting)
│   │   └── recon.py          # /api/recon (The Easter Egg honey-pot)
│   ├── ws/                   
│   │   └── timer.py          # WebSocket server pushing time ticks to clients
│   ├── auth.py               # JWT generation and single-session validation logic
│   ├── config.py             # Loads environment variables via Pydantic Settings
│   ├── database.py           # SQLAlchemy async database connection setup
│   ├── main.py               # The FastAPI entry point (Middleware, Rate Limits, Router inclusion)
│   ├── models.py             # SQLAlchemy ORM classes mirroring the database schema
│   ├── schemas.py            # Pydantic models for strict Request/Response validation
│   └── questions_loader.py   # Loads questions.json into RAM on server startup
│
├── frontend/                 # Static vanilla frontend files (served by FastAPI)
│   ├── css/
│   │   └── style.css         # Glassmorphism, animations, and responsive styling
│   ├── js/
│   │   ├── admin.js          # Logic for admin dashboard polling and interactions
│   │   ├── login.js          # Branch dropdown logic and login API communication
│   │   └── quiz.js           # Client-side quiz state, WebSockets, and navigation
│   ├── admin.html            # The admin dashboard view (IP Restricted)
│   ├── index.html            # The login entry point (Contains easter egg hints)
│   └── quiz.html             # The main quiz-taking interface
│
├── scripts/                  # Utility scripts for database management
│   ├── generate_questions.py # Parses questions.txt, seeds DB, outputs JSON
│   └── reset_quiz.py         # Wipes the DB (students, sessions, answers) for fresh starts
│
├── .env                      # Secret keys and database URLs (Not committed to Git)
├── .env.example              # Template for environment variables
├── requirements.txt          # Python package dependencies
├── start_server.ps1          # PowerShell script to cleanly boot the server
└── questions.txt             # Original text file containing all raw questions
```

## How It Works Together
1. **Frontend**: When a user navigates to the root URL, FastAPI's `StaticFiles` serves `frontend/index.html`. 
2. **Authentication**: Upon submitting their registration, `backend/routers/auth.py` creates their session in PostgreSQL and returns an HTTP-only JWT cookie.
3. **Taking the Quiz**: The `quiz.js` script initiates a WebSocket connection to `timer.py` to get authoritative time sync. It fetches single questions on-demand from `quiz.py`.
4. **Resiliency**: Every selected option triggers a background `POST` request. If a user refreshes or disconnects, the single-session logic logs them back in exactly where they were, with their answers intact.
