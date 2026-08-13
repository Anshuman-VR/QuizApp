from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Request, HTTPException, Depends
from backend.config import settings
from backend.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models import Session
import uuid

ALGORITHM = "HS256"

def create_access_token(reg_no: str, quiz_id: int, jti: str):
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    to_encode = {
        "sub": reg_no,
        "quiz_id": quiz_id,
        "jti": jti,
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_session(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        reg_no: str = payload.get("sub")
        quiz_id: int = payload.get("quiz_id")
        jti: str = payload.get("jti")
        if reg_no is None or quiz_id is None or jti is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # DB Check
    result = await db.execute(
        select(Session).where(Session.reg_no == reg_no, Session.quiz_id == quiz_id)
    )
    db_session = result.scalar_one_or_none()
    if not db_session:
        raise HTTPException(status_code=401, detail="Session not found")
    if db_session.session_token != jti:
        raise HTTPException(status_code=401, detail="Session logged in on another device")

    return db_session
