# Questions: the practice bank, and understanding ANY question a student types or photographs
# (the pipeline itself is agents/understand.py).

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.understand import understandQuestion
from app.agents.visual import makeVisual
from app.ai.models import AiModels
from app.ai.photos import PHOTO_PROBLEMS, NotAnImageError, findPhotoProblem, readMediaType
from app.ai.prompts import READ_QUESTION_PROMPT
from app.api import getAi
from app.api.checks import MAX_PHOTO_BYTES
from app.db import Question, getDbSession
from app.schemas import QuestionOut, UnderstandIn, UnderstandOut, toQuestionOut

router = APIRouter(prefix="/questions", tags=["questions"])


def saveQuestion(session: Session, fields: dict[str, Any]) -> Question:
    """Same question text -> same id, so a repeated question is not stored twice."""
    questionId = "student_" + hashlib.sha256(fields["text"].lower().encode()).hexdigest()[:12]
    question = session.get(Question, questionId)
    if question is None:
        question = Question(id=questionId, source="student", **fields)
        session.add(question)
        session.commit()
    elif question.answer == fields["answer"] and question.traps != fields.get("traps", question.traps):
        question.traps = fields["traps"]  # newer solvers know more common mistakes; they only diagnose, never mark
        session.commit()
    elif question.answer != fields["answer"] and fields.get("trust") == "verified":
        # A newer solver computed a different, verified answer (e.g. a length is 12, not ±12): the old key is wrong.
        for key in ("answer", "expressions", "traps", "checks", "family", "marks"):
            if key in fields:
                setattr(question, key, fields[key])
        question.solution = fields.get("solution")  # the cached worked solution belonged to the old answer
        session.commit()
    return question


def answerQuestion(text: str, ai: AiModels, session: Session) -> UnderstandOut:
    result = understandQuestion(text, ai)
    saved = [toQuestionOut(saveQuestion(session, part)) for part in result.parts]
    return UnderstandOut(
        status=result.status,
        question=saved[0] if saved else None,
        other_parts=saved[1:],
        message=result.message,
        understood=result.understood,
    )


@router.get("", response_model=list[QuestionOut])
def listBankQuestions(class_level: int | None = None, session: Session = Depends(getDbSession)) -> list[QuestionOut]:
    query = select(Question).where(Question.source == "bank").order_by(Question.chapter, Question.difficulty)
    if class_level:
        query = query.where(Question.class_level == class_level)
    return [toQuestionOut(question) for question in session.scalars(query)]


@router.get("/{question_id}", response_model=QuestionOut)
def getQuestion(question_id: str, session: Session = Depends(getDbSession)) -> QuestionOut:
    question = session.get(Question, question_id)
    if question is None:
        raise HTTPException(404, "Question not found.")
    return toQuestionOut(question)


@router.get("/{question_id}/visual")
def getQuestionVisual(
    question_id: str,
    language: str = "hinglish",
    session: Session = Depends(getDbSession),
    ai: AiModels = Depends(getAi),
) -> dict[str, Any]:
    """The concept visual for a question (no student mistake). visual is null when none could be checked."""
    question = session.get(Question, question_id)
    if question is None:
        raise HTTPException(404, "Question not found.")
    return {"visual": makeVisual(question, language, ai)}


@router.post("", response_model=UnderstandOut)
def understandTypedQuestion(
    body: UnderstandIn, session: Session = Depends(getDbSession), ai: AiModels = Depends(getAi)
) -> UnderstandOut:
    return answerQuestion(body.text, ai, session)


@router.post("/photo", response_model=UnderstandOut)
def understandQuestionPhoto(
    image: UploadFile = File(...), session: Session = Depends(getDbSession), ai: AiModels = Depends(getAi)
) -> UnderstandOut:
    imageBytes = image.file.read(MAX_PHOTO_BYTES + 1)
    if len(imageBytes) > MAX_PHOTO_BYTES:
        raise HTTPException(400, "The photo must be under 10 MB.")
    try:
        mediaType = readMediaType(imageBytes)
    except NotAnImageError as error:
        raise HTTPException(400, "Please upload a JPEG, PNG or WEBP photo.") from error
    problem = findPhotoProblem(imageBytes)
    if problem:
        # Checked before any AI sees it: given a blank page, a vision model once invented a whole question.
        return UnderstandOut(status="parse_failed", message=PHOTO_PROBLEMS[problem])
    reading = ai.readImage(READ_QUESTION_PROMPT, imageBytes, mediaType)
    if reading is None:
        return UnderstandOut(
            status="parse_failed", message="We could not read the photo right now. Please try again in a moment, or retake it in good light."
        )
    if reading.get("page") != "maths" or not str(reading.get("question", "")).strip():
        return UnderstandOut(status="not_maths", message="This photo does not look like a maths question.")
    readText = str(reading["question"]).strip()
    result = answerQuestion(readText, ai, session)
    result.read_text = readText
    return result
