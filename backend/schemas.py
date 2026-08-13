from pydantic import BaseModel, Field, constr
from typing import Dict, List, Optional
from datetime import datetime

class LoginRequest(BaseModel):
    reg_no: constr(pattern=r'^1\d{8}$')
    name: str
    year: int
    branch: str

class AnswerRequest(BaseModel):
    question_no: int = Field(ge=1, le=60)
    option: constr(pattern=r'^[ABCD]$')

class ReconRequest(BaseModel):
    flag: str

class QuizStateResponse(BaseModel):
    total_questions: int = 60
    remaining_seconds: int
    has_submitted: bool
    answered_questions: List[int]

class QuestionResponse(BaseModel):
    no: int
    text: str
    options: Dict[str, str]
    your_answer: Optional[str] = None
