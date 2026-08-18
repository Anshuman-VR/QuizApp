from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from backend.routers import auth, quiz, admin, recon
from backend.ws import timer
from backend.questions_loader import load_questions
from backend.config import settings
from contextlib import asynccontextmanager
import os

import sys

def disable_windows_quickedit():
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h_in = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE = -10
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(h_in, ctypes.byref(mode)):
                # Clear 0x0040 (QuickEdit) and 0x0020 (InsertMode), set 0x0080 (ExtendedFlags)
                new_mode = (mode.value & ~0x0040 & ~0x0020) | 0x0080
                kernel32.SetConsoleMode(h_in, new_mode)
        except Exception:
            pass

disable_windows_quickedit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    disable_windows_quickedit()
    load_questions()
    yield

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)  # disable docs in production

# ── Rate Limiting ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
# P0-1/P0-4: Cloudflare Quick Tunnel domain is unknown at startup, so we allow
# credentials from any origin. Security is enforced by HttpOnly cookie + session_token check.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # must be False with allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Admin IP Restriction Middleware ───────────────────────────────────────────
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    response = await call_next(request)

    # Security headers
    response.headers["X-Powered-By"] = "ACE-Quiz/1.0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"

    return response

# ── Routers ───────────────────────────────────────────────────────────────────
# P0-4: raise login rate limit to 60/min (campus NAT means many students = one IP)
app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["Quiz"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(recon.router, prefix="/api", tags=["Recon"])
app.include_router(timer.router, prefix="/ws", tags=["WS"])

# ── Static Frontend ───────────────────────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
