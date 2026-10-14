# Request and response shapes of the API. The frontend mirrors these in frontend/lib/api.ts.

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.db import Check, Question
from app.maths.checker import ZERO_REASONS, selectVisibleExpressions

Language = Literal["en", "hinglish"]


class QuestionOut(BaseModel):
    id: str
    trust: str  # verified | single_reading (only one AI reading was available)
    class_level: int
    chapter: str
    text: str
    expressions: list[str]  # only the ones safe to show (a word problem's calculation stays hidden)
    marks: int
    difficulty: int


def toQuestionOut(question: Question) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        trust=question.trust,
        class_level=question.class_level,
        chapter=question.chapter,
        text=question.text,
        expressions=selectVisibleExpressions(question.expressions),
        marks=question.marks,
        difficulty=question.difficulty,
    )


class UnderstandIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class UnderstandOut(BaseModel):
    # solved | needs_clarification | unsupported | parse_failed | verification_failed | not_maths
    status: str
    question: QuestionOut | None = None
    other_parts: list[QuestionOut] = []  # (b), (c)... of a multi-part question
    message: str | None = None  # what is missing / ambiguous / not supported, in one sentence
    understood: list[str] = []  # the maths we read, shown next to a clarification question
    read_text: str | None = None  # what we read from a photo, so the student can confirm it


class LineOut(BaseModel):
    latex: str
    needs_check: bool  # we were not sure we read it right


class StepOut(BaseModel):
    line_no: int
    verdict: str  # correct | incorrect | carried (follows from the first mistake) | unverifiable | unreadable | note
    is_question_copy: bool


STATUS_MESSAGES = {
    **ZERO_REASONS,
    "not_maths": "This photo does not look like maths working.",
    "ai_unavailable": "We could not read the photo right now. Please type your steps instead.",
}


class CheckOut(BaseModel):
    id: str
    question_id: str
    status: str
    message: str | None
    lines: list[LineOut]
    steps: list[StepOut]
    score: float
    max_score: int
    wrong_line: int | None
    explanation: str | None
    mistake: str | None = None  # kind of mistake, e.g. "adding fractions (tops and bottoms added separately)"
    has_photo: bool


def toCheckOut(check: Check, confidenceThreshold: float) -> CheckOut:
    return CheckOut(
        id=check.id,
        question_id=check.question_id,
        status=check.status,
        message=STATUS_MESSAGES.get(check.status),
        lines=[
            LineOut(latex=line["latex"], needs_check=line["confidence"] < confidenceThreshold) for line in check.lines
        ],
        steps=[StepOut(**step) for step in check.steps],
        score=check.score,
        max_score=check.question.marks,
        wrong_line=check.wrong_line,
        explanation=check.explanation,
        mistake=check.mistake,
        has_photo=check.image_path is not None,
    )


class TypedCheckIn(BaseModel):
    question_id: str
    student_id: str | None = None
    lines: list[Annotated[str, Field(max_length=500)]] = Field(min_length=1, max_length=30)  # a line is never an essay


class ConfirmIn(BaseModel):
    lines: list[Annotated[str, Field(max_length=500)]] = Field(min_length=1, max_length=30)  # a line is never an essay


class SolutionStep(BaseModel):
    explain: str
    latex: str | None
    speech: str = ""  # what the voice says for this step (maths in words), for the "play as lesson" board


class BoardScene(BaseModel):
    """One sentence of the tutor, played with its maths on the smart board."""

    text: str  # display text, maths inside $...$
    speech: str  # what the voice says
    maths: list[str]  # LaTeX lines this sentence writes on the board (arithmetic checked)


class BoardLine(BaseModel):
    line_no: int
    latex: str


class SolutionOut(BaseModel):
    steps: list[SolutionStep]
    answer_latex: str
    verified: bool  # True when SymPy checked every maths line and the final answer


class TutorStartIn(BaseModel):
    check_id: str
    language: Language = "hinglish"


class TutorMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class TutorOut(BaseModel):
    chat_id: str
    reply: str
    speech: str  # the reply with maths turned into words, for text-to-speech
    stage: str  # hints | walkthrough | quick_check | practice
    fix_correct: bool | None
    quick_check_correct: bool | None
    step_correct: bool | None  # walkthrough: their answer for the current step
    focus_line: int
    show_practice: bool
    scenes: list[BoardScene] = []  # the reply split into sentences, for the synced smart board
    board_line: BoardLine | None = None  # the student's line the tutor is talking about


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    class_level: int = Field(ge=6, le=10)


class StudentOut(BaseModel):
    id: str
    name: str
    class_level: int


class ChapterProgress(BaseModel):
    chapter: str
    attempts: int
    full_marks: int
    needs_revision: bool  # the latest sum in this chapter did not get full marks


class MistakeCount(BaseModel):
    mistake: str  # e.g. "moving terms across the = sign" (decided by the checker, not an AI)
    times: int
    chapters: list[str]


class RecentCheck(BaseModel):
    check_id: str
    question_text: str
    chapter: str
    score: float
    max_score: int
    created_at: datetime


class ProgressOut(BaseModel):
    name: str
    class_level: int
    streak_days: int
    checked_today: bool
    checks_done: int
    full_marks: int
    mistakes_fixed: int
    chapters: list[ChapterProgress]  # weakest first
    mistakes: list[MistakeCount]  # most frequent first
    recent: list[RecentCheck]


class PracticeOut(BaseModel):
    question: QuestionOut | None
    reason: str


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    language: Language = "hinglish"
