from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, text
from backend.database import AsyncSessionLocal
from backend.models import Session as QuizSession, Quiz
from backend.config import settings
from jose import jwt, JWTError
import asyncio
import datetime

router = APIRouter()

RESYNC_INTERVAL = 8   # P0-6: DB resync every 8s, client interpolates in between


@router.websocket("/timer")
async def websocket_timer(websocket: WebSocket):
    await websocket.accept()

    # ── Extract session cookie ────────────────────────────────────────────────
    cookie_header = next(
        (v for k, v in websocket.headers.raw if k.lower() == b"cookie"), b""
    ).decode()
    token = None
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith("session="):
            token = part[len("session="):]
            break

    if not token:
        await websocket.close(code=1008, reason="No session cookie")
        return

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        reg_no: str = payload["sub"]
        quiz_id: int = payload["quiz_id"]
        jti: str = payload["jti"]
    except (JWTError, KeyError):
        await websocket.close(code=1008, reason="Invalid token")
        return

    # ── Validate session in DB ────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(QuizSession).where(
                QuizSession.reg_no == reg_no, QuizSession.quiz_id == quiz_id
            )
        )
        db_session = result.scalar_one_or_none()

        if not db_session or db_session.session_token != jti:
            await websocket.close(code=1008, reason="Session invalid")
            return

        if db_session.hassubmitted:
            await websocket.send_json({"type": "expired", "remaining": 0})
            await websocket.close()
            return

        result = await db.execute(select(Quiz).where(Quiz.quiz_id == quiz_id))
        quiz = result.scalar_one_or_none()
        limit_mins = quiz.time_limit if quiz else 60
        start_time = db_session.start_time
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=datetime.timezone.utc)

    # ── Tick loop — DB resync every RESYNC_INTERVAL seconds ──────────────────
    try:
        tick_count = 0
        cached_remaining = None

        while True:
            if tick_count % RESYNC_INTERVAL == 0:
                # Hard resync from DB
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(QuizSession.start_time, QuizSession.hassubmitted).where(
                            QuizSession.reg_no == reg_no, QuizSession.quiz_id == quiz_id
                        )
                    )
                    row = result.one_or_none()

                if not row:
                    break
                st, submitted = row
                if submitted:
                    await websocket.send_json({"type": "expired", "remaining": 0})
                    await websocket.close()
                    break

                if st.tzinfo is None:
                    st = st.replace(tzinfo=datetime.timezone.utc)
                now = datetime.datetime.now(datetime.timezone.utc)
                cached_remaining = int(limit_mins * 60 - (now - st).total_seconds())
            else:
                # Client-side interpolation: decrement cached value
                cached_remaining = (cached_remaining or 0) - 1

            if cached_remaining <= 0:
                # Auto-submit
                async with AsyncSessionLocal() as db:
                    res = await db.execute(
                        text("""
                            UPDATE session
                            SET hassubmitted = true, finish_time = now()
                            WHERE reg_no = :r AND quiz_id = :q AND hassubmitted = false
                            RETURNING reg_no
                        """),
                        {"r": reg_no, "q": quiz_id},
                    )
                    if res.fetchone():
                        await db.execute(
                            text("""
                                UPDATE session SET score = (
                                    SELECT COUNT(*) FROM studentanswers sa
                                    JOIN options o ON sa.quiz_id = o.quiz_id
                                                  AND sa.question_no = o.question_no
                                    WHERE sa.reg_no = :r AND sa.quiz_id = :q
                                      AND sa.option = o.correctanswer
                                ) WHERE reg_no = :r AND quiz_id = :q
                            """),
                            {"r": reg_no, "q": quiz_id},
                        )
                        await db.commit()

                await websocket.send_json({"type": "expired", "remaining": 0})
                await websocket.close(code=1000)
                break

            await websocket.send_json({"type": "tick", "remaining": cached_remaining})
            await asyncio.sleep(1)
            tick_count += 1

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Error for {reg_no}: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
