# Checks: a student's attempt (photo or typed steps) -> GradingGraph -> red-pen result.
# Also the full solution, which unlocks only after a real attempt.


import logging
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.agents.grading import GradingState, findMistake, runGrading, showNames
from app.agents.solution import getDetailedSteps, getVerifiedSteps
from app.agents.tutor import findRootLine
from app.agents.visual import (
    addRememberCard,
    buildMistakeIntro,
    cleanBoardText,
    fallbackInsight,
    findInsight,
    findRightSoFar,
    makeVisual,
    narrateVisual,
)
from app.agents.visual_templates import joinVisuals
from app.ai.models import AiModels
from app.ai.photos import PHOTO_PROBLEMS, NotAnImageError, readMediaType
from app.ai.prompts import LANGUAGES
from app.ai.speech import speakMaths, toSpokenText
from app.api import getAi
from app.config import Settings, getSettings
from app.db import Check, Question, Student, getDbSession, newId
from app.maths import checker
from app.schemas import CheckOut, ConfirmIn, SolutionOut, SolutionStep, TypedCheckIn, toCheckOut

router = APIRouter(prefix="/checks", tags=["checks"])
logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 10 * 1024 * 1024

# The lesson after the red pen (the "Understand the mistake" board and the tutor's step-by-step solution) takes several
# AI calls: ~15 s on the live server. It is started the moment the red pen is ready, while the student reads it; the
# lesson request then waits for that work instead of starting it again.
LESSON_LANGUAGE = "hinglish"  # the lesson's default language; another language is made when asked
PREPARE_WAIT_SECONDS = 90
preparer = ThreadPoolExecutor(max_workers=2, thread_name_prefix="prepare")
preparing: dict[str, Future[dict[str, Any] | None]] = {}


def loadCheck(session: Session, checkId: str) -> Check:
    check = session.get(Check, checkId)
    if check is None:
        raise HTTPException(404, "Check not found.")
    return check


def buildAnswerKey(question: Question, ai: AiModels) -> list[dict[str, Any]]:
    """The verified worked solution, BEFORE the student's lines are graded: the red pen compares every line with it.
    Solver steps or a bank equation need no AI; otherwise an AI solution SymPy checks line by line (cached on the
    question). The detailed write-up is added when it was already made (its numbers are checked too)."""
    steps = list(getVerifiedSteps(question, "en", ai) or [])
    return steps + list((question.solution or {}).get("detailed_v4_en") or [])


def gradeAndSave(session: Session, check: Check, ai: AiModels, settings: Settings, mediaType: str = "") -> CheckOut:
    question = check.question
    answerKey = buildAnswerKey(question, ai)
    state: GradingState = {
        "question": {
            "text": question.text,
            "expressions": question.expressions,
            "answer": question.answer,
            "marks": question.marks,
            "class_level": question.class_level,
            "traps": question.traps or [],
            "solution": answerKey,
        },
        "imagePath": check.image_path,
        "mediaType": mediaType,
        "lines": check.lines,
        "confidenceThreshold": settings.confidence_threshold,
    }
    result = runGrading(ai, state)
    check.status = result["status"]
    check.lines = result.get("lines", check.lines)
    check.steps = result.get("steps", [])
    check.score = result.get("score", 0.0)
    check.wrong_line = result.get("wrongLine")
    check.explanation = PHOTO_PROBLEMS.get(result.get("explanation") or "", result.get("explanation"))
    check.mistake = result.get("mistake")
    session.commit()
    if settings.prepare_ahead and check.status == "graded" and check.wrong_line:
        startPreparing(session, check.id, ai)
    return toCheckOut(check, settings.confidence_threshold)


def startPreparing(session: Session, checkId: str, ai: AiModels) -> None:
    for key in [key for key, future in preparing.items() if future.done()]:
        preparing.pop(key, None)  # finished work nobody asked for: it is in the AI cache and the database anyway
    engine = session.get_bind()
    preparing[checkId] = preparer.submit(prepareLesson, engine, checkId, ai)


def prepareLesson(engine: Any, checkId: str, ai: AiModels) -> dict[str, Any] | None:
    """Runs in the background with its own database session. Never raises: the lesson is simply made on request."""
    try:
        with Session(bind=engine) as session:
            check = loadCheck(session, checkId)
            getDetailedSteps(check.question, LESSON_LANGUAGE, ai)  # the tutor's walkthrough, saved on the question
            session.commit()
            return buildCheckVisual(session, check, LESSON_LANGUAGE, ai)
    except Exception:
        logger.warning("preparing the lesson failed; it will be made when asked", exc_info=True)
        return None


def waitForPreparation(checkId: str) -> dict[str, Any] | None:
    """The board prepared in the background (waiting for it if it is still being made), or None."""
    future = preparing.get(checkId)
    if future is None:
        return None
    try:
        return future.result(timeout=PREPARE_WAIT_SECONDS)
    except Exception:
        return None


def newCheck(session: Session, questionId: str, studentId: str | None, lines: list[str]) -> Check:
    question = session.get(Question, questionId)
    if question is None:
        raise HTTPException(404, "Question not found.")
    if studentId and session.get(Student, studentId) is None:
        logger.warning("unknown student id on a check; saving it without a student")
        studentId = None  # a stale id in the browser must never break checking
    check = Check(
        id=newId(),
        question_id=question.id,
        question=question,
        student_id=studentId,
        status="new",
        lines=[{"latex": line, "confidence": 1.0} for line in lines],  # typed or confirmed = certain
    )
    session.add(check)
    return check


@router.post("", response_model=CheckOut, status_code=201)
def checkPhoto(
    image: UploadFile = File(...),
    question_id: str = Form(...),
    student_id: str | None = Form(None),
    session: Session = Depends(getDbSession),
    ai: AiModels = Depends(getAi),
    settings: Settings = Depends(getSettings),
) -> CheckOut:
    """Photo of handwritten working -> red-pen result (or the lines to confirm first)."""
    imageBytes = image.file.read(MAX_PHOTO_BYTES + 1)
    if len(imageBytes) > MAX_PHOTO_BYTES:
        raise HTTPException(400, "The photo must be under 10 MB.")
    try:
        mediaType = readMediaType(imageBytes)
    except NotAnImageError as error:
        raise HTTPException(400, "Please upload a JPEG, PNG or WEBP photo.") from error
    check = newCheck(session, question_id, student_id, [])
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    imagePath = settings.upload_dir / f"{check.id}.{mediaType.split('/')[1]}"
    imagePath.write_bytes(imageBytes)
    check.image_path = str(imagePath)
    return gradeAndSave(session, check, ai, settings, mediaType)


@router.post("/typed", response_model=CheckOut, status_code=201)
def checkTypedSteps(
    body: TypedCheckIn,
    session: Session = Depends(getDbSession),
    ai: AiModels = Depends(getAi),
    settings: Settings = Depends(getSettings),
) -> CheckOut:
    check = newCheck(session, body.question_id, body.student_id, [line for line in body.lines if line.strip()])
    return gradeAndSave(session, check, ai, settings)


@router.post("/{check_id}/confirm", response_model=CheckOut)
def confirmLines(
    check_id: str,
    body: ConfirmIn,
    session: Session = Depends(getDbSession),
    ai: AiModels = Depends(getAi),
    settings: Settings = Depends(getSettings),
) -> CheckOut:
    """The student fixed what we misread. Their lines are final: our reading mistakes never cost marks."""
    check = loadCheck(session, check_id)
    check.lines = [{"latex": line, "confidence": 1.0} for line in body.lines if line.strip()]
    return gradeAndSave(session, check, ai, settings)


@router.get("/{check_id}", response_model=CheckOut)
def getCheck(
    check_id: str, session: Session = Depends(getDbSession), settings: Settings = Depends(getSettings)
) -> CheckOut:
    return toCheckOut(loadCheck(session, check_id), settings.confidence_threshold)


@router.get("/{check_id}/photo")
def getCheckPhoto(check_id: str, session: Session = Depends(getDbSession)) -> FileResponse:
    check = loadCheck(session, check_id)
    if check.image_path is None:
        raise HTTPException(404, "This check has no photo.")
    return FileResponse(check.image_path)


@router.get("/{check_id}/solution", response_model=SolutionOut)
def getSolution(
    check_id: str,
    language: str = "en",
    session: Session = Depends(getDbSession),
    ai: AiModels = Depends(getAi),
) -> SolutionOut:
    """Try first, then learn: only a graded attempt unlocks the worked solution."""
    check = loadCheck(session, check_id)
    if check.status != "graded":
        raise HTTPException(409, "Try the question first — the full solution unlocks after your attempt.")
    question = check.question
    # The detailed, teacher-style write-up (every number re-checked, must end on the computed answer);
    # it falls back to the shorter SymPy-verified steps when the detailed one cannot be trusted.
    steps = getDetailedSteps(question, language if language in LANGUAGES else "en", ai)
    session.commit()
    return SolutionOut(
        steps=[
            SolutionStep(
                explain=step["explain"],
                latex=step.get("latex"),
                speech=" ".join(
                    part
                    for part in (toSpokenText(step["explain"]), speakMaths(step["latex"]) if step.get("latex") else "")
                    if part
                ),
            )
            for step in steps or []
        ],
        answer_latex=checker.formatAnswer(question.answer),
        verified=steps is not None,  # never show unchecked steps
    )


@router.get("/{check_id}/visual")
def getCheckVisual(
    check_id: str, language: str = "hinglish", session: Session = Depends(getDbSession), ai: AiModels = Depends(getAi)
) -> dict[str, Any]:
    """The concept visual for this attempt: it shows the student's own mistake when there is one."""
    check = loadCheck(session, check_id)
    if language == LESSON_LANGUAGE:
        prepared = waitForPreparation(check_id)
        if prepared and prepared.get("complete"):
            return prepared
    return buildCheckVisual(session, check, language, ai)


def buildCheckVisual(session: Session, check: Check, language: str, ai: AiModels) -> dict[str, Any]:
    question = check.question
    if check.status != "graded":
        return {"visual": None}
    lines = [line["latex"] for line in check.lines]
    wrongLatex, facts, kind, rootLine = None, None, None, 0
    if check.wrong_line:
        context = {
            "text": question.text,
            "expressions": question.expressions,
            "answer": question.answer,
            "traps": question.traps or [],
        }
        rootLine = findRootLine(lines, check.wrong_line)
        wrongLatex = lines[rootLine - 1]
        kind, facts = findMistake(context, lines, check.wrong_line)
        facts = showNames(facts)
    visual = makeVisual(question, language, ai, wrongLatex, facts, kind)
    hasPicture = visual is not None  # False when the drawing could not be made (e.g. the AI was rate limited)
    insight = None
    numbers: list[dict[str, str]] = []
    rightSoFar: dict[str, Any] | None = None
    if wrongLatex and facts:
        # SymPy proved WHERE; the teacher's note says WHY (which concept), then THEIR line, the fact, the concept
        # picture — narrated by a teacher voice.
        getVerifiedSteps(question, "en", ai)  # the insight is checked against the verified solution
        session.commit()
        insight = findInsight(question, lines, rootLine, facts, language, ai) or fallbackInsight(question, kind, language)
        numbers = checker.measureMistake(question.answer, question.expressions or [], lines)
        traps = {trap["mistake"] for trap in question.traps or []}
        rightSoFar = findRightSoFar(lines, check.steps or [], rootLine, kind, traps)
        intro = buildMistakeIntro(question, language, ai, rootLine, wrongLatex, facts, kind, insight, numbers, rightSoFar)
        if visual:
            # The intro already shows their wrong line; a ✗ in the concept picture would repeat it, or mark the question.
            visual["elements"] = [
                element
                for element in visual["elements"]
                if element.get("tone") != "wrong" or element.get("mistakePicture")
            ]
        visual = joinVisuals(intro, visual) if visual else intro
        visual = narrateVisual(visual, question, language, ai, wrongLatex, facts)
        if insight:
            visual = addRememberCard(visual, insight, language)
    for element in (visual or {}).get("elements", []):
        if element.get("type") == "text":
            element["text"] = cleanBoardText(str(element.get("text") or ""))
    # 'complete' tells the app to ask again later: the picture is often ready a few seconds after a busy moment.
    return {"visual": visual, "insight": insight, "numbers": numbers, "rightSoFar": rightSoFar, "complete": hasPicture}
