from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from backend.database import get_db
from backend.config import settings
from pydantic import BaseModel
import csv
from io import StringIO
from fastapi.responses import StreamingResponse

router = APIRouter()


class AdminLoginRequest(BaseModel):
    secret: str


class ExtendRequest(BaseModel):
    minutes: int = 10


def verify_admin(request: Request):
    token = request.cookies.get("admin_token")
    if token != settings.ADMIN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/login")
async def admin_login(req: AdminLoginRequest, response: Response):
    if req.secret == settings.ADMIN_SECRET:
        response.set_cookie(
            key="admin_token", value=req.secret, httponly=True, samesite="lax"
        )
        return {"success": True}
    raise HTTPException(status_code=401, detail="Wrong secret")


@router.get("/stats", dependencies=[Depends(verify_admin)])
async def get_stats(db: AsyncSession = Depends(get_db)):
    total = (
        await db.execute(
            text("SELECT COUNT(*) FROM session WHERE quiz_id = :q"),
            {"q": settings.QUIZ_ID},
        )
    ).scalar() or 0

    submitted = (
        await db.execute(
            text("SELECT COUNT(*) FROM session WHERE quiz_id = :q AND hassubmitted = true"),
            {"q": settings.QUIZ_ID},
        )
    ).scalar() or 0

    avg_raw = (
        await db.execute(
            text("SELECT AVG(score) FROM session WHERE quiz_id = :q AND hassubmitted = true"),
            {"q": settings.QUIZ_ID},
        )
    ).scalar()
    avg_score = round(float(avg_raw), 2) if avg_raw else 0.0

    return {
        "total_registered": total,
        "total_submitted": submitted,
        "not_started": total - submitted,
        "avg_score": avg_score,
    }


@router.get("/results", dependencies=[Depends(verify_admin)])
async def get_results(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            text("""
                SELECT s.reg_no, s.name, s.branch, s.year,
                       se.score, se.hassubmitted, se.start_time, se.finish_time
                FROM session se
                JOIN students s ON se.reg_no = s.reg_no
                WHERE se.quiz_id = :q
                ORDER BY se.score DESC NULLS LAST
            """),
            {"q": settings.QUIZ_ID},
        )
    ).fetchall()
    return [
        {
            "reg_no": r[0], "name": r[1], "branch": r[2], "year": r[3],
            "score": r[4], "has_submitted": r[5],
            "start_time": str(r[6]), "finish_time": str(r[7]),
        }
        for r in rows
    ]


@router.get("/export", dependencies=[Depends(verify_admin)])
async def export_csv(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            text("""
                SELECT s.reg_no, s.name, s.branch, s.year,
                       se.score, se.hassubmitted, se.start_time, se.finish_time
                FROM session se
                JOIN students s ON se.reg_no = s.reg_no
                WHERE se.quiz_id = :q
                ORDER BY se.score DESC NULLS LAST
            """),
            {"q": settings.QUIZ_ID},
        )
    ).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Reg No", "Name", "Branch", "Year", "Score", "Submitted", "Start Time", "Finish Time"])
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )


# P1-7: Non-destructive remediation — extend start_time (grants more time)
@router.patch("/session/{reg_no}/extend", dependencies=[Depends(verify_admin)])
async def extend_session(reg_no: str, req: ExtendRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        text("""
            UPDATE session
            SET start_time = start_time + make_interval(mins => :minutes)
            WHERE reg_no = :reg_no AND quiz_id = :quiz_id AND hassubmitted = false
            RETURNING reg_no
        """),
        {"reg_no": reg_no, "quiz_id": settings.QUIZ_ID, "minutes": req.minutes},
    )
    if not res.fetchone():
        raise HTTPException(status_code=404, detail="Session not found or already submitted")
    await db.commit()
    return {"extended": True, "minutes_added": req.minutes, "reg_no": reg_no}


# Destructive reset — kept for catastrophic failures
@router.delete("/session/{reg_no}", dependencies=[Depends(verify_admin)])
async def reset_session(reg_no: str, db: AsyncSession = Depends(get_db)):
    await db.execute(
        text("DELETE FROM studentanswers WHERE reg_no = :r AND quiz_id = :q"),
        {"r": reg_no, "q": settings.QUIZ_ID},
    )
    await db.execute(
        text("DELETE FROM session WHERE reg_no = :r AND quiz_id = :q"),
        {"r": reg_no, "q": settings.QUIZ_ID},
    )
    await db.commit()
    return {"reset": True}
