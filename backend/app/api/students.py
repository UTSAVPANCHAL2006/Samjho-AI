# Students: a profile per child (no login), their progress and streak, and the next practice question.

import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.understand import understandQuestion
from app.ai.models import AiModels
from app.ai.prompts import PRACTICE_QUESTION_PROMPT
from app.api import getAi
from app.api.questions import saveQuestion
from app.db import Check, Question, Student, TutorChat, getDbSession
from app.maths import checker
from app.schemas import (
    ChapterProgress,
    MistakeCount,
    PracticeOut,
    ProgressOut,
    RecentCheck,
    StudentIn,
    StudentOut,
    toQuestionOut,
)

router = APIRouter(tags=["students"])

INDIA = ZoneInfo("Asia/Kolkata")
ATTEMPT_STATUSES = {"graded", "blank", "skipped", "only_question_copied", "off_question", "unreadable"}


@router.post("/students", response_model=StudentOut, status_code=201)
def createStudent(body: StudentIn, session: Session = Depends(getDbSession)) -> StudentOut:
    student = Student(name=body.name.strip(), class_level=body.class_level)
    session.add(student)
    session.commit()
    return StudentOut(id=student.id, name=student.name, class_level=student.class_level)


def toIndiaDate(moment: datetime) -> date:
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(INDIA).date()


def countStreak(activeDays: set[date], today: date) -> int:
    """Days in a row with a checked sum, ending today — or yesterday, so the streak lives until tonight."""
    day = today if today in activeDays else today - timedelta(days=1)
    streak = 0
    while day in activeDays:
        streak += 1
        day -= timedelta(days=1)
    return streak


def isFullMarks(check: Check) -> bool:
    return check.status == "graded" and check.score >= check.question.marks


@router.get("/students/{student_id}/progress", response_model=ProgressOut)
def getProgress(student_id: str, session: Session = Depends(getDbSession)) -> ProgressOut:
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(404, "Student not found.")
    checks = [
        check
        for check in session.scalars(
            select(Check).where(Check.student_id == student_id).order_by(Check.created_at.desc())
        )
        if check.status in ATTEMPT_STATUSES
    ]
    chats = session.scalars(select(TutorChat).join(Check).where(Check.student_id == student_id))
    byChapter: dict[str, list[Check]] = defaultdict(list)
    for check in checks:
        byChapter[check.question.chapter].append(check)
    chapters = [
        ChapterProgress(
            chapter=name,
            attempts=len(items),
            full_marks=sum(isFullMarks(item) for item in items),
            needs_revision=not isFullMarks(items[0]),  # checks are newest first
        )
        for name, items in byChapter.items()
    ]
    byMistake: dict[str, list[Check]] = defaultdict(list)
    for check in checks:
        if check.mistake and not isFullMarks(check):
            byMistake[check.mistake].append(check)
    mistakes = [
        MistakeCount(mistake=name, times=len(items), chapters=sorted({item.question.chapter for item in items}))
        for name, items in byMistake.items()
    ]
    mistakes.sort(key=lambda item: -item.times)
    chapters.sort(key=lambda item: item.full_marks / item.attempts)
    today = datetime.now(INDIA).date()
    activeDays = {toIndiaDate(check.created_at) for check in checks}
    return ProgressOut(
        name=student.name,
        class_level=student.class_level,
        streak_days=countStreak(activeDays, today),
        checked_today=today in activeDays,
        checks_done=len(checks),
        full_marks=sum(isFullMarks(check) for check in checks),
        mistakes_fixed=sum(chat.stage == "practice" for chat in chats),
        chapters=chapters,
        mistakes=mistakes,
        recent=[
            RecentCheck(
                check_id=check.id,
                question_text=check.question.text,
                chapter=check.question.chapter,
                score=check.score,
                max_score=check.question.marks,
                created_at=check.created_at,
            )
            for check in checks[:20]
        ],
    )


def chapterKey(chapter: str) -> str:
    """'Arithmetic Progressions' and 'arithmetic progressions ' are the same chapter."""
    return re.sub(r"[^a-z0-9]", "", chapter.lower())


def isSameTopic(question: Question, source: Question) -> bool:
    if source.chapter == "Mixed practice":  # the chapter (and so the class) is unsure: match the kind of maths
        return bool(source.family) and question.family == source.family and abs(question.class_level - source.class_level) <= 2
    if question.class_level != source.class_level:
        return False
    return chapterKey(question.chapter) == chapterKey(source.chapter)


def isSameSum(question: Question, source: Question) -> bool:
    """The same sum under another id ('Add 2/3 + 1/4' in the bank and the student's photo of it): the same
    answer AND the same numbers. Practice must be a NEW sum — but 'a red king from 52 cards' is new even though
    every card question has 52, and 'a queen' vs 'a king' (same numbers, same answer) is not."""
    # 'from the origin (0, 0)' and 'from the origin' are the same sum: a 0 or a 1 never makes a sum new
    numbers = checker.readNumbers(question.text) - {"0", "1"}
    sameNumbers = bool(numbers) and numbers == checker.readNumbers(source.text) - {"0", "1"}
    return question.answer == source.answer and (sameNumbers or question.text.strip() == source.text.strip())


def makeSimilarQuestion(source: Question, harder: bool, session: Session, ai: AiModels) -> Question | None:
    """A NEW question on the same chapter, written by the AI and then solved by the same pipeline as a typed
    question (SymPy computes the answer). It was written FOR this chapter, so it keeps the chapter even when the
    re-reading files it elsewhere (a hemisphere's volume is in more than one class). Two attempts."""
    if not ai.isAvailable():
        return None
    rejected: list[str] = []
    for _ in range(3):
        avoid = " ".join(f"Not this one (rejected): {text}" for text in rejected[-2:])
        data = ai.askJson(
            PRACTICE_QUESTION_PROMPT.format(
                class_level=source.class_level,
                chapter=source.chapter,
                question=source.text,
                level="slightly harder" if harder else "slightly easier",
            ),
            f"Write the practice question. Its answer must differ from the original's. {avoid}".strip(),
            temperature=0.7,
        )
        text = str((data or {}).get("question") or "").strip()
        if not text:
            continue
        result = understandQuestion(text, ai)
        if result.status != "solved" or not result.parts:
            rejected.append(text)
            continue
        question = saveQuestion(session, {**result.parts[0], "class_level": source.class_level, "chapter": source.chapter})
        if not isSameSum(question, source):
            return question
        rejected.append(text)
    return None


@router.get("/practice", response_model=PracticeOut)
def getNextPractice(
    check_id: str,
    student_id: str | None = None,
    session: Session = Depends(getDbSession),
    ai: AiModels = Depends(getAi),
) -> PracticeOut:
    """Practice is ALWAYS from the same chapter as the checked sum — never another topic.
    Order: a bank question not tried yet -> a new AI-written question (answer solved by SymPy) -> a tried bank
    question. Harder after full marks, easier after a mistake."""
    check = session.get(Check, check_id)
    if check is None:
        raise HTTPException(404, "Check not found.")
    source = check.question
    harder = isFullMarks(check)
    targetDifficulty = max(1, min(3, source.difficulty + (1 if harder else -1)))
    tried = (
        set(session.scalars(select(Check.question_id).where(Check.student_id == student_id))) if student_id else set()
    )
    tried.add(source.id)
    sameTopic = [
        question
        for question in session.scalars(select(Question).where(Question.source == "bank", Question.id != source.id))
        if isSameTopic(question, source) and not isSameSum(question, source)
    ]
    sameTopic.sort(key=lambda question: abs(question.difficulty - targetDifficulty))
    reason = f"Same chapter: {source.chapter}"
    fresh = [question for question in sameTopic if question.id not in tried]
    if fresh:
        return PracticeOut(question=toQuestionOut(fresh[0]), reason=reason)
    made = makeSimilarQuestion(source, harder, session, ai)
    if made is not None and made.id not in tried:
        return PracticeOut(question=toQuestionOut(made), reason=f"{reason} (a new question for you)")
    if sameTopic:
        return PracticeOut(question=toQuestionOut(sameTopic[0]), reason=f"{reason} (try it once more)")
    if source.chapter == "Mixed practice" and source.family:
        # The chapter could not be named: the same kind of maths from the nearest class is still the right practice.
        sameKind = [
            question
            for question in session.scalars(select(Question).where(Question.source == "bank", Question.family == source.family))
            if question.id not in tried and not isSameSum(question, source)
        ]
        sameKind.sort(key=lambda question: abs(question.class_level - source.class_level))
        if sameKind:
            return PracticeOut(question=toQuestionOut(sameKind[0]), reason=f"Same kind of sum ({source.family})")
    return PracticeOut(question=None, reason=f"No practice question for {source.chapter} right now.")
