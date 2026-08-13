from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from backend.database import get_db
from backend.models import Session as QuizSession, StudentAnswer, Option, Quiz
from backend.schemas import AnswerRequest, QuizStateResponse, QuestionResponse
from backend.auth import get_current_session
from backend.config import settings
from backend.questions_loader import get_question
import datetime

router = APIRouter()


def _remaining(start_time: datetime.datetime, limit_mins: int) -> int:
    now = datetime.datetime.now(datetime.timezone.utc)
    # start_time may be naive (UTC) from DB — normalise
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=datetime.timezone.utc)
    elapsed = (now - start_time).total_seconds()
    return int(limit_mins * 60 - elapsed)


async def _get_limit(quiz_id: int, db: AsyncSession) -> int:
    result = await db.execute(select(Quiz).where(Quiz.quiz_id == quiz_id))
    quiz = result.scalar_one_or_none()
    return quiz.time_limit if quiz else 60


async def _auto_submit(reg_no: str, quiz_id: int, db: AsyncSession):
    """Idempotent submit: flips hassubmitted and calculates score atomically."""
    res = await db.execute(
        text("""
            UPDATE session
            SET hassubmitted = true, finish_time = now()
            WHERE reg_no = :reg_no AND quiz_id = :quiz_id AND hassubmitted = false
            RETURNING reg_no
        """),
        {"reg_no": reg_no, "quiz_id": quiz_id},
    )
    if res.fetchone():
        # Score = correct answers count
        await db.execute(
            text("""
                UPDATE session SET score = (
                    SELECT COUNT(*) FROM studentanswers sa
                    JOIN options o ON sa.quiz_id = o.quiz_id AND sa.question_no = o.question_no
                    WHERE sa.reg_no = :reg_no AND sa.quiz_id = :quiz_id
                      AND sa.option = o.correctanswer
                ) WHERE reg_no = :reg_no AND quiz_id = :quiz_id
            """),
            {"reg_no": reg_no, "quiz_id": quiz_id},
        )
        await db.commit()


@router.get("/state", response_model=QuizStateResponse)
async def get_state(
    db_session: QuizSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    limit = await _get_limit(db_session.quiz_id, db)
    remaining = _remaining(db_session.start_time, limit)

    result = await db.execute(
        select(StudentAnswer.question_no).where(
            StudentAnswer.reg_no == db_session.reg_no,
            StudentAnswer.quiz_id == db_session.quiz_id,
        )
    )
    answered = [row[0] for row in result.all()]

    if remaining <= 0 and not db_session.hassubmitted:
        await _auto_submit(db_session.reg_no, db_session.quiz_id, db)
        db_session.hassubmitted = True

    return QuizStateResponse(
        total_questions=60,
        remaining_seconds=max(remaining, 0),
        has_submitted=db_session.hassubmitted,
        answered_questions=answered,
    )


@router.get("/question/{n}", response_model=QuestionResponse)
async def get_question_endpoint(
    n: int,
    db_session: QuizSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    if db_session.hassubmitted:
        raise HTTPException(status_code=403, detail="Already submitted")
    if n < 1 or n > 60:
        raise HTTPException(status_code=404, detail="Question not found")

    q_data = get_question(n)
    if not q_data:
        raise HTTPException(status_code=404, detail="Question not found")

    result = await db.execute(
        select(StudentAnswer.option).where(
            StudentAnswer.reg_no == db_session.reg_no,
            StudentAnswer.quiz_id == db_session.quiz_id,
            StudentAnswer.question_no == n,
        )
    )
    ans = result.scalar_one_or_none()

    return QuestionResponse(
        no=q_data["no"],
        text=q_data["text"],
        options=q_data["options"],
        your_answer=ans,
    )


@router.post("/answer")
async def save_answer(
    req: AnswerRequest,
    db_session: QuizSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    if db_session.hassubmitted:
        raise HTTPException(status_code=403, detail="Already submitted")

    limit = await _get_limit(db_session.quiz_id, db)
    remaining = _remaining(db_session.start_time, limit)
    if remaining <= 0:
        await _auto_submit(db_session.reg_no, db_session.quiz_id, db)
        raise HTTPException(status_code=403, detail="Time expired — quiz auto-submitted")

    # P0-5: upsert answer
    await db.execute(
        text("""
            INSERT INTO studentanswers (reg_no, quiz_id, question_no, option)
            VALUES (:reg_no, :quiz_id, :q_no, :opt)
            ON CONFLICT (reg_no, quiz_id, question_no)
            DO UPDATE SET option = EXCLUDED.option
        """),
        {
            "reg_no": db_session.reg_no,
            "quiz_id": db_session.quiz_id,
            "q_no": req.question_no,
            "opt": req.option,
        },
    )
    await db.commit()
    return {"saved": True, "question_no": req.question_no}  # P0-5


@router.post("/submit")
async def manual_submit(
    db_session: QuizSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
):
    if db_session.hassubmitted:
        return {"submitted": True}  # idempotent
    await _auto_submit(db_session.reg_no, db_session.quiz_id, db)
    return {"submitted": True}
