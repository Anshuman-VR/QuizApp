from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from backend.database import get_db
from backend.models import Student, Session as QuizSession
from backend.schemas import LoginRequest
from backend.auth import create_access_token, get_current_session
from backend.config import settings
import uuid
import re

router = APIRouter()

REG_NO_RE = re.compile(r'^1\d{8}$')


# ── P0-2: Resume endpoint ─────────────────────────────────────────────────────
# Called on every page-load by the frontend. Only reads — never mutates session_token.
@router.get("/resume")
async def resume(db_session: QuizSession = Depends(get_current_session)):
    """Validate existing cookie without rotating session_token.
    Returns current quiz status so the frontend can decide where to route."""
    return {
        "status": "resumed" if not db_session.hassubmitted else "submitted",
        "has_submitted": db_session.hassubmitted,
    }


# ── P0-2 / P0-3: Login ───────────────────────────────────────────────────────
@router.post("/login")
async def login(
    req: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # P0-3: server-side format check (frontend may be bypassed)
    if not REG_NO_RE.match(req.reg_no):
        raise HTTPException(status_code=422, detail="Invalid registration number format")

    # P0-3: race-safe upsert — INSERT … ON CONFLICT DO NOTHING, then re-select
    await db.execute(
        text("""
            INSERT INTO students (reg_no, name, year, branch)
            VALUES (:reg_no, :name, :year, :branch)
            ON CONFLICT (reg_no) DO NOTHING
        """),
        {"reg_no": req.reg_no, "name": req.name, "year": req.year, "branch": req.branch},
    )
    await db.commit()

    result = await db.execute(select(Student).where(Student.reg_no == req.reg_no))
    student = result.scalar_one_or_none()

    # Validate name matches (case-insensitive)
    if student.name.strip().lower() != req.name.strip().lower():
        raise HTTPException(
            status_code=401,
            detail="Registration number already used with a different name",
        )

    # Check existing quiz session
    result = await db.execute(
        select(QuizSession).where(
            QuizSession.reg_no == req.reg_no,
            QuizSession.quiz_id == settings.QUIZ_ID,
        )
    )
    db_session = result.scalar_one_or_none()

    if db_session and db_session.hassubmitted:
        raise HTTPException(status_code=403, detail="You have already submitted the quiz")

    # Rotate session_token — kills any existing device session
    new_jti = str(uuid.uuid4())

    if db_session:
        await db.execute(
            text("""
                UPDATE session SET session_token = :jti
                WHERE reg_no = :reg_no AND quiz_id = :quiz_id
            """),
            {"jti": new_jti, "reg_no": req.reg_no, "quiz_id": settings.QUIZ_ID},
        )
        status_msg = "resumed"
    else:
        import datetime
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        await db.execute(
            text("""
                INSERT INTO session (reg_no, quiz_id, session_token, start_time)
                VALUES (:reg_no, :quiz_id, :jti, :start_time)
            """),
            {"reg_no": req.reg_no, "quiz_id": settings.QUIZ_ID, "jti": new_jti, "start_time": now_utc},
        )
        status_msg = "new"

    await db.commit()

    token = create_access_token(req.reg_no, settings.QUIZ_ID, new_jti)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=False,   # set False so it works over plain http (cloudflare handles TLS)
        samesite="lax", # lax works cross-origin with Cloudflare tunnel
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )

    return {"status": status_msg, "message": "Login successful"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session")
    return {"message": "Logged out"}
