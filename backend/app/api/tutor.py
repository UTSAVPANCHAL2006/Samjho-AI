# Tutor: talk through the first mistake of a check. One TutorGraph run per student message.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.grading import findMistake, showNames
from app.agents.solution import getDetailedSteps
from app.agents.tutor import TutorState, buildTeachingSteps, findRootLine, runTutorTurn
from app.ai.models import AiModels
from app.api import getAi
from app.db import Check, TutorChat, getDbSession
from app.schemas import BoardLine, BoardScene, TutorMessageIn, TutorOut, TutorStartIn

router = APIRouter(prefix="/tutor", tags=["tutor"])


def buildContext(check: Check, language: str, ai: AiModels) -> TutorState:
    """What the tutor knows: the question, the student's lines, the facts about the mistake (SymPy)
    and the verified solution steps it may teach from."""
    question = check.question
    lines = [line["latex"] for line in check.lines]
    # No line is proven wrong but marks were lost (answer missing / incomplete): talk about finishing the last line.
    wrongLine = check.wrong_line or max(1, len(lines))
    context = {
        "text": question.text,
        "expressions": question.expressions,
        "answer": question.answer,
        "class_level": question.class_level,
        "traps": question.traps or [],
    }
    return {
        "question": context,
        "lines": lines,
        "wrongLine": wrongLine,
        "rootLine": findRootLine(lines, wrongLine),
        "facts": showNames(findMistake(context, lines, wrongLine)[1])
        if check.wrong_line
        else "No line is wrong, but the working stops before the complete final answer. Help them finish it.",
        "language": language,
        # the detailed notebook steps in the student's language (the same verified write-up as the lesson's
        # Full solution): small steps a teacher walks through one at a time, each with maths to work out
        "steps": buildTeachingSteps(getDetailedSteps(question, language, ai) or []),
    }


def runTurn(session: Session, chat: TutorChat, text: str, ai: AiModels) -> TutorOut:
    state: TutorState = {
        **buildContext(chat.check, chat.language, ai),
        "history": chat.messages,
        "stage": chat.stage,
        "hintsUsed": chat.hints_used or 0,  # a new chat is not flushed yet: column defaults are still None
        "step": chat.step or 0,
        "quickCheck": chat.quick_check,
        "asked": chat.asked,
        "studentText": text,
    }
    result = runTutorTurn(ai, state)
    chat.stage = result["nextStage"]
    chat.hints_used = result["hintsUsed"]
    chat.step = result["nextStep"]
    chat.quick_check = result.get("quickCheck")
    chat.asked = result.get("asked")
    student = [{"role": "student", "text": text}] if text else []
    chat.messages = [*chat.messages, *student, {"role": "tutor", "text": result["reply"]}]
    session.commit()
    return TutorOut(
        chat_id=chat.id,
        reply=result["reply"],
        speech=result["speech"],
        stage=chat.stage,
        fix_correct=result.get("fixCorrect"),
        quick_check_correct=result.get("quickCheckCorrect"),
        step_correct=result["stepCorrect"] if result.get("stepCorrect") is not None else result.get("askedCorrect"),
        focus_line=result.get("rootLine") or result["wrongLine"],
        show_practice=chat.stage == "practice",
        scenes=[BoardScene(**scene) for scene in result.get("scenes") or []],
        board_line=BoardLine(
            line_no=result.get("rootLine") or result["wrongLine"],
            latex=result["lines"][(result.get("rootLine") or result["wrongLine"]) - 1],
        )
        if result.get("lines")
        else None,
    )


@router.post("", response_model=TutorOut, status_code=201)
def startChat(body: TutorStartIn, session: Session = Depends(getDbSession), ai: AiModels = Depends(getAi)) -> TutorOut:
    check = session.get(Check, body.check_id)
    if check is None:
        raise HTTPException(404, "Check not found.")
    if check.wrong_line is None and check.score >= check.question.marks:
        raise HTTPException(409, "Full marks — there is no mistake to talk about in this check.")
    chat = TutorChat(check_id=check.id, check=check, language=body.language, stage="start", messages=[])
    session.add(chat)
    return runTurn(session, chat, "", ai)


@router.post("/{chat_id}", response_model=TutorOut)
def sendMessage(
    chat_id: str,
    body: TutorMessageIn,
    session: Session = Depends(getDbSession),
    ai: AiModels = Depends(getAi),
) -> TutorOut:
    chat = session.get(TutorChat, chat_id)
    if chat is None:
        raise HTTPException(404, "Chat not found.")
    return runTurn(session, chat, body.text, ai)
