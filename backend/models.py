from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime
from sqlalchemy.sql import func
from backend.database import Base

class Student(Base):
    __tablename__ = "students"
    reg_no = Column(String(9), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    branch = Column(String(100), nullable=False)
    year = Column(Integer)

class Quiz(Base):
    __tablename__ = "quiz"
    quiz_id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    time_limit = Column(Integer, nullable=False, default=60)
    isactive = Column(Boolean, nullable=False, default=False)

class Option(Base):
    __tablename__ = "options"
    quiz_id = Column(Integer, ForeignKey("quiz.quiz_id"), primary_key=True)
    question_no = Column(Integer, primary_key=True)
    correctanswer = Column(String(1), nullable=False)

class Session(Base):
    __tablename__ = "session"
    reg_no = Column(String(9), ForeignKey("students.reg_no"), primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quiz.quiz_id"), primary_key=True)
    start_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finish_time = Column(DateTime(timezone=True))
    hassubmitted = Column(Boolean, default=False)
    score = Column(Integer)
    session_token = Column(String(64), unique=True)

class StudentAnswer(Base):
    __tablename__ = "studentanswers"
    reg_no = Column(String(9), primary_key=True)
    quiz_id = Column(Integer, primary_key=True)
    question_no = Column(Integer, primary_key=True)
    option = Column(String(1), nullable=False)
