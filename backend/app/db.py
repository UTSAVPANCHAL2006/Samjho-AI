# Database: 4 tables. Lines, step verdicts and chat messages are small lists, so they live in JSON columns.
#   students   -> who is studying (name + class, no login)
#   questions  -> the practice bank + questions students typed or photographed
#   checks     -> one checked attempt: the lines, a verdict per line, marks, the first mistake
#   tutor_chats-> one conversation about a check's first mistake

import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from app.config import getSettings

QUESTION_BANK_FILE = Path(__file__).parent / "data" / "questions.json"


def newId() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=newId)
    name: Mapped[str] = mapped_column(String(80))
    class_level: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(16), default="bank")  # bank | student
    class_level: Mapped[int] = mapped_column(Integer, index=True)
    chapter: Mapped[str] = mapped_column(String(120), index=True)
    text: Mapped[str] = mapped_column(Text)
    expressions: Mapped[list[str]] = mapped_column(JSON)  # the maths of the question, as LaTeX
    answer: Mapped[dict[str, Any]] = mapped_column(JSON)  # computed by SymPy (see maths/checker.py)
    marks: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    family: Mapped[str] = mapped_column(String(20), default="expression")  # which solver (maths/solvers.py)
    trust: Mapped[str] = mapped_column(String(20), default="verified")  # verified | single_reading
    checks: Mapped[list[str]] = mapped_column(JSON, default=list)  # verifications the answer passed
    traps: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)  # known wrong answers + the mistake
    solution: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # {language: verified steps}


class Check(Base):
    __tablename__ = "checks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=newId)
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id"), nullable=True, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    image_path: Mapped[str | None] = mapped_column(String(300), nullable=True)  # None when typed
    # needs_retake | needs_confirmation | graded | blank | skipped | unreadable | only_question_copied
    # | off_question | not_maths | ai_unavailable
    status: Mapped[str] = mapped_column(String(32))
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # [{latex, confidence}]
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)  # [{line_no, verdict, ...}]
    score: Mapped[float] = mapped_column(Float, default=0.0)
    wrong_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    mistake: Mapped[str | None] = mapped_column(String(120), nullable=True)  # kind of mistake, decided by code
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    question: Mapped[Question] = relationship()


class TutorChat(Base):
    __tablename__ = "tutor_chats"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=newId)
    check_id: Mapped[str] = mapped_column(ForeignKey("checks.id"), index=True)
    language: Mapped[str] = mapped_column(String(10))  # en | hinglish
    stage: Mapped[str] = mapped_column(String(20))  # see agents/tutor.py
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    step: Mapped[int] = mapped_column(Integer, default=0)  # walkthrough: which verified step the student is on
    quick_check: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)  # {question, answer}
    asked: Mapped[str | None] = mapped_column(Text, nullable=True)  # calculation the tutor asked last (LaTeX)
    messages: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)  # [{role, text}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    check: Mapped[Check] = relationship()


engine = create_engine(getSettings().database_url, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


def getDbSession() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session


def setUpDatabase(session: Session) -> None:
    """Create missing tables and load the question bank (safe to run on every start)."""
    Base.metadata.create_all(session.get_bind())
    # create_all never changes an existing table: add columns that newer code expects (the only "migration" so far).
    if "mistake" not in {column["name"] for column in inspect(session.get_bind()).get_columns("checks")}:
        session.execute(text("ALTER TABLE checks ADD COLUMN mistake VARCHAR(120)"))
    if "asked" not in {column["name"] for column in inspect(session.get_bind()).get_columns("tutor_chats")}:
        session.execute(text("ALTER TABLE tutor_chats ADD COLUMN asked TEXT"))
    known = {question.id: question for question in session.scalars(select(Question).where(Question.source == "bank"))}
    for item in json.loads(QUESTION_BANK_FILE.read_text(encoding="utf-8")):
        if item["id"] in known:  # the file is the source of truth (e.g. chapters renamed for the 2026-27 books)
            for name, value in item.items():
                setattr(known[item["id"]], name, value)
        else:
            session.add(Question(source="bank", **item))
    session.commit()
