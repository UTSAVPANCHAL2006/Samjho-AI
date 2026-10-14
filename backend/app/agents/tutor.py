# TutorGraph (LangGraph) — one turn of a conversation about the student's mistake.
#
#   understandMessage ──> decideNext ──> makeQuickCheck ──> writeReply
#   (code: what did they say?   (teaching rules,   (only after the    (AI words it, using ONLY the
#    maths checked by SymPy)     pure function)     mistake is fixed)  verified steps' numbers)
#
# Teaching path (like a class teacher):
#   start -> explain the question, praise what was right, point at the ROOT line (where the wrong value first appears,
#            e.g. a wrong formula), ask them to recall the rule
#   each small question the tutor asks carries "ASKED: <calculation>"; SymPy computes it, so the student's
#   answer to THAT question is marked right/wrong — never confused with fixing the whole line
#   -> probe the wrong line -> hint -> stronger hint -> walk through the verified steps together
#   "samjhao / I don't understand"  -> walk through the steps: explain one, the student computes the next
#   "full solution / answer batao"  -> all verified steps, then a quick check
#   a correct fix (proven by SymPy)  -> praise -> quick check on the same rule -> practice
#   a wrong value ("x = 8")          -> show by substitution exactly why it fails

import re
from typing import Any, TypedDict, cast

import sympy
from langgraph.graph import END, START, StateGraph

from app.agents.solution import isLineArithmeticTrue
from app.ai.models import AiModels
from app.ai.prompts import (
    LANGUAGES,
    QUICK_CHECK_PROMPT,
    TUTOR_PROMPT,
    TUTOR_TASKS,
    cleanAddress,
    restoreLostBackslashes,
)
from app.ai.speech import toSpokenText
from app.maths import checker
from app.maths.parser import LatexParseError, getFreeSymbols, hasPlainWords, parseLatex

FULL_SOLUTION_WORDS = (
    "full solution",
    "pura solution",
    "poora solution",
    "complete solution",
    "sab steps",
    "answer batao",
    "answer bata",
    "jawab batao",
    "tell me the answer",
    "solution batao",
    "solve karke dikhao",
    "solve kar ke dikhao",
    "show me the solution",
    "give me the answer",
)
EXPLAIN_WORDS = (
    "samajh nahi",
    "samjh nahi",
    "samjha nahi",
    "nahi samjha",
    "samajh nahin",
    "samjhao",
    "samjha do",
    "samjhaiye",
    "explain",
    "don't understand",
    "dont understand",
    "do not understand",
    "not understand",
    "confused",
    "kaise",
    "how to",
    "how do",
    "why",
    "kyun",
    "kyu ",
    "help",
    "pata nahi",
    "don't know",
    "dont know",
    "idk",
    "stuck",
    "nahi aata",
)
MAX_HINTS = 2
MAX_CONFUSION_PER_STEP = 1  # after one simpler re-explanation, show the step instead of looping


class TutorState(TypedDict, total=False):
    # context
    question: dict[str, Any]  # {text, expressions, answer, class_level, traps}
    lines: list[str]
    wrongLine: int
    rootLine: int  # where the mistake first appears (e.g. the wrong formula); <= wrongLine
    facts: str
    language: str
    history: list[dict[str, str]]
    steps: list[dict[str, Any]]  # verified solution steps [{explain, latex}] ([] if none are available)
    # this turn
    stage: str  # start | hints | walkthrough | quick_check | practice
    hintsUsed: int  # hints given; in the walkthrough, how often the student was confused on this step
    step: int  # walkthrough: index of the step the student is working out now
    quickCheck: dict[str, str] | None
    asked: str | None  # the calculation the tutor asked for last turn (LaTeX, numbers only)
    studentText: str
    # results of understanding the message
    intent: str  # full_solution | explain | maths | chat
    claim: str | None  # the maths found in their message
    fixCorrect: bool | None
    stepCorrect: bool | None
    quickCheckCorrect: bool | None
    askedCorrect: bool | None  # their answer to the tutor's last small question (checked by SymPy)
    askedValue: str | None
    claimFacts: str | None  # why their value is wrong (substitution / known misconception)
    # decisions and output
    task: str
    nextStage: str
    nextStep: int
    reply: str
    speech: str
    scenes: list[dict[str, Any]]  # the reply as sentences + board maths (smart board)


# ---------- understanding the student's message (code, no AI) ----------


def findMaths(text: str) -> str | None:
    """'Maine x = 8 likha' -> 'x = 8'; 'mujhe 35 aaya' -> '35'. The longest piece of the message that is maths."""
    words = text.replace("=", " = ").split()
    best: str | None = None
    for start in range(len(words)):
        for end in range(len(words), start, -1):
            candidate = " ".join(words[start:end]).strip(" .,:;?!")
            if not re.search(r"\d", candidate) or hasPlainWords(candidate) or (best and len(candidate) <= len(best)):
                continue
            try:
                parsed = parseLatex(candidate)
            except LatexParseError:
                continue
            if all(len(str(symbol)) == 1 for symbol in getFreeSymbols(parsed)):
                best = candidate
    return best


def mentions(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = f" {text.lower()} "
    return any(phrase in lowered for phrase in phrases)


def givesFinalAnswer(state: TutorState, claim: str) -> bool:
    """'... = 132/7' or 'x = 5': their maths ends on the question's right answer (proved by SymPy)."""
    answer = state["question"]["answer"]
    finalValue = claim.split("=")[-1].strip()
    return any(checker.isFinalAnswerCorrect(answer, [candidate]) for candidate in (claim, finalValue) if candidate)


def checkClaim(state: TutorState, claim: str) -> dict[str, Any]:
    """Their maths as a corrected line, or as a final answer."""
    question = state["question"]
    linesBefore = state["lines"][: state["wrongLine"] - 1]
    steps = checker.checkSteps(
        question["expressions"], [*linesBefore, claim], checker.getKnownPoint(question["answer"])
    )
    last = steps[-1]
    if last.verdict == checker.CORRECT and not last.isQuestionCopy:
        return {"fixCorrect": True}
    try:
        parsed = parseLatex(claim)
    except LatexParseError:
        return {"fixCorrect": None}
    isAnswer = checker.isAnswerAssignment(parsed) or (isinstance(parsed, sympy.Expr) and parsed.is_number)
    if isAnswer and checker.isFinalAnswerCorrect(question["answer"], [claim]):
        return {"fixCorrect": True}
    if "=" in claim and givesFinalAnswer(state, claim):  # '... x 6^2 = 132/7': the value they ended on
        return {"fixCorrect": True}
    if isAnswer and checker.isWrongFinalAnswer(question["answer"], [claim]):
        found = checker.describeWrongAnswer(
            question["expressions"], question["answer"], [claim], question.get("traps") or []
        )
        return {"fixCorrect": False, "claimFacts": found[1] if found else None}
    return {"fixCorrect": False if last.verdict == checker.INCORRECT else None}


FORMULA_LETTERS = re.compile(r"(?<![\\a-zA-Z])[a-zA-Z](?![a-zA-Z])")


def readLineValue(latex: str) -> sympy.Expr | None:
    """The number a working line ends on: 'S_{20} = 10 \\cdot 97' -> 970; a formula line -> None."""
    parts = [part for part in latex.split("=") if part.strip()]
    for candidate in (latex, parts[-1] if parts else ""):
        value = checker.readFinalValue(candidate) if candidate else None
        if value is not None:
            return value
    return None


def isFormulaLine(latex: str) -> bool:
    """'Formula: S_n = (n/2)[a + (n - 1)d]' — a rule written with letters, not yet with numbers."""
    return "=" in latex and (len(FORMULA_LETTERS.findall(latex)) >= 3 or "formula" in latex.lower())


def findRootLine(lines: list[str], wrongLine: int) -> int:
    """The line where the wrong value FIRST appears. If a formula line sits right before it, the formula
    was the real mistake, so the teacher starts there (not at the arithmetic that came after it)."""
    wrongValue = readLineValue(lines[wrongLine - 1]) if 0 < wrongLine <= len(lines) else None
    if wrongValue is None:
        return wrongLine
    for index in range(wrongLine):
        value = readLineValue(lines[index])
        if value is not None and checker.areExpressionsEquivalent(value, wrongValue):
            if index >= 1 and isFormulaLine(lines[index - 1]):
                return index  # 1-based number of the formula line
            return index + 1
    return wrongLine


def checkAskedAnswer(asked: str | None, claim: str | None) -> tuple[bool | None, str | None]:
    """Is their number the answer to the calculation the tutor asked? The value is computed here, not by the AI."""
    if not asked or not claim:
        return None, None
    try:
        parsed = parseLatex(asked)
    except LatexParseError:
        return None, None
    if not isinstance(parsed, sympy.Expr) or not parsed.is_number:
        return None, None
    expected = sympy.latex(sympy.nsimplify(parsed))
    return checker.isSameAnswer(claim, expected), expected


def understandMessage(state: TutorState) -> dict[str, Any]:
    text = (state.get("studentText") or "").strip()
    claim = findMaths(text) if text else None
    result: dict[str, Any] = {
        "claim": claim,
        "fixCorrect": None,
        "stepCorrect": None,
        "quickCheckCorrect": None,
        "askedCorrect": None,
        "askedValue": None,
        "claimFacts": None,
    }
    if mentions(text, FULL_SOLUTION_WORDS):
        result["intent"] = "full_solution"
    elif mentions(text, EXPLAIN_WORDS) and not claim:
        result["intent"] = "explain"
    else:
        result["intent"] = "maths" if claim else "chat"
    stage = state["stage"]
    if stage == "quick_check" and state.get("quickCheck") and claim:
        result["quickCheckCorrect"] = checker.isSameAnswer(claim, state["quickCheck"]["answer"])  # type: ignore[index]
    elif stage == "walkthrough" and claim and state.get("steps"):
        expected = state["steps"][state.get("step") or 0].get("latex")
        result["stepCorrect"] = checkStepAnswer(claim, expected) if expected else None
        if givesFinalAnswer(state, claim):
            result["fixCorrect"] = True  # they reached the right answer mid-walkthrough: no more small steps
    elif claim and stage in ("start", "hints"):
        askedCorrect, askedValue = checkAskedAnswer(state.get("asked"), claim)
        result.update({"askedCorrect": askedCorrect, "askedValue": askedValue})
        claimCheck = checkClaim(state, claim)
        if askedCorrect is None or claimCheck.get("fixCorrect") is True:
            result.update(claimCheck)  # an answer to a small question is not a failed attempt at the whole line
    ending = findLastMaths(text) if text else None
    if ending and ending != claim and stage in ("hints", "walkthrough") and givesFinalAnswer(state, ending):
        # '21 + 4 = 25, so x = 5': the longest maths is the working, but they ENDED on the right answer. A tutor
        # that then asks "what is 21 + 4?" is not listening.
        result["fixCorrect"] = True
    return result


def findLastMaths(text: str) -> str | None:
    """The part the message ends on, after its last 'so' / 'toh' / 'then': '21 + 4 = 25, so x = 5' -> 'x = 5'.
    It is given to the answer checker whole, so 'x = 2, 3' stays one answer with two roots."""
    pieces = re.split(r"\.\s|\b(?:so|toh|to|then|therefore|hence|isliye|matlab)\b", text, flags=re.IGNORECASE)
    for piece in reversed(pieces):
        piece = piece.strip(" .,:;?!")
        if re.search(r"\d", piece):
            return piece
    return None


def buildTeachingSteps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every walkthrough step must have maths the student can work out: an explanation-only step
    ("the x-terms are the same, so subtract") is joined to the maths step that follows it."""
    merged: list[dict[str, Any]] = []
    pendingExplain = ""
    for step in steps:
        explain = " ".join(part for part in (pendingExplain, step.get("explain") or "") if part)
        if step.get("latex"):
            merged.append({"explain": explain, "latex": step["latex"]})
            pendingExplain = ""
        else:
            pendingExplain = explain
    if pendingExplain and merged:
        merged[-1] = {**merged[-1], "explain": f"{merged[-1]['explain']} {pendingExplain}".strip()}
    return merged


def checkStepAnswer(claim: str, expected: str) -> bool | None:
    """The step is '7y = 35'; asked "3y − (−4y) kya banega?", '7y' is right too — accept either side or the whole line."""
    parts = [
        part.strip() for part in re.split(r"\\qquad|\\quad|,", expected.replace("\\checkmark", "")) if part.strip()
    ]
    candidates = [expected, *parts]
    for part in parts:  # '11 = 11 ✓  −24 = −24 ✓' -> each equation, and each side of it
        if part.count("=") == 1:
            candidates += [side.strip() for side in part.split("=")]
        elif part.count("=") > 1:  # '2a = 2 \\times 2 = 4' -> the result 4
            candidates.append(part.split("=")[-1].strip())
    results = [checker.isSameAnswer(claim, candidate) for candidate in candidates]
    if any(result is True for result in results):
        return True
    return False if any(result is False for result in results) else None


# ---------- teaching rules (pure function) ----------


def decideTurn(
    stage: str,
    hintsUsed: int,
    step: int,
    stepCount: int,
    intent: str,
    fixCorrect: bool | None,
    stepCorrect: bool | None,
    askedCorrect: bool | None = None,
) -> tuple[str, str, int, int]:
    """(task for this reply, next stage, hints/confusion counter, walkthrough step)."""
    if stage == "start":
        return "probe", "hints", 0, 0
    if stage == "quick_check":
        return "quick_check_result", "practice", hintsUsed, step
    if stage == "practice":
        return "chat", "practice", hintsUsed, step
    if intent == "full_solution" and stage == "hints" and hintsUsed == 0:
        # Asked for the answer before trying even once: one strong hint and one try first. Asking again shows it,
        # so nobody is ever stuck - but the answer is never the first thing the tutor gives.
        return "ask_one_try", "hints", 1, step
    if intent == "full_solution":
        return (
            ("full_solution", "quick_check", hintsUsed, step)
            if stepCount
            else ("reveal", "quick_check", hintsUsed, step)
        )
    if stage == "walkthrough":
        if fixCorrect:
            return "praise", "quick_check", 0, step
        isLast = step + 1 >= stepCount
        if stepCorrect is True:
            return ("walk_done", "quick_check", 0, step) if isLast else ("walk_next", "walkthrough", 0, step + 1)
        if stepCorrect is False or (intent == "explain" and hintsUsed >= MAX_CONFUSION_PER_STEP):
            return ("walk_show_done", "quick_check", 0, step) if isLast else ("walk_show", "walkthrough", 0, step + 1)
        if intent == "explain":
            return "walk_simpler", "walkthrough", hintsUsed + 1, step
        return "walk_chat", "walkthrough", hintsUsed, step
    # hints stage
    if fixCorrect:
        return "praise", "quick_check", hintsUsed, step
    if askedCorrect is True:
        return "guide_next", "hints", hintsUsed, step  # progress: not a used hint
    if intent == "explain" or hintsUsed >= MAX_HINTS:
        return ("walk_start", "walkthrough", 0, 1) if stepCount >= 2 else ("reveal", "quick_check", hintsUsed, step)
    if askedCorrect is False:
        return "guide_retry", "hints", hintsUsed + 1, step
    if fixCorrect is False:
        return ("diagnose" if hintsUsed == 0 else "strong_hint"), "hints", hintsUsed + 1, step
    return "chat_hint", "hints", hintsUsed + 1, step


def decideNext(state: TutorState) -> dict[str, Any]:
    task, nextStage, hintsUsed, step = decideTurn(
        state["stage"],
        state.get("hintsUsed") or 0,
        state.get("step") or 0,
        len(state.get("steps") or []),
        state.get("intent", "chat"),
        state.get("fixCorrect"),
        state.get("stepCorrect"),
        state.get("askedCorrect"),
    )
    return {"task": task, "nextStage": nextStage, "hintsUsed": hintsUsed, "nextStep": step}


# ---------- quick check (after the mistake is understood) ----------


def makeQuickCheck(state: TutorState, ai: AiModels) -> dict[str, Any]:
    if state["nextStage"] != "quick_check":
        return {}
    data = ai.askJson(
        QUICK_CHECK_PROMPT.format(
            class_level=state["question"]["class_level"],
            facts=state["facts"],
            wrong_latex=state["lines"][state["wrongLine"] - 1],
            question=state["question"]["text"],
            language=LANGUAGES[state["language"]],
        ),
        "Make the quick check.",
        temperature=0.3,
        live=True,
    )
    answer = str((data or {}).get("answer") or "")
    if data and str(data.get("question", "")).strip() and checker.isSameAnswer(answer, answer):
        return {"quickCheck": {"question": restoreLostBackslashes(str(data["question"]).strip()), "answer": answer.strip()}}
    return {"quickCheck": None, "nextStage": "practice"}


# ---------- the reply ----------


def describeStep(step: dict[str, Any]) -> str:
    latex = f" ${step['latex']}$" if step.get("latex") else ""
    return f"{step.get('explain') or ''}{latex}".strip()


def describeTurnCheck(state: TutorState) -> str:
    """Exactly what the computer verified this turn, so the AI never praises an unchecked answer."""
    claim = state.get("claim")
    checks = (
        ("quickCheckCorrect", "Their quick-check answer"),
        ("stepCorrect", "Their answer for this step"),
        ("askedCorrect", "Their answer to your last small question"),
        ("fixCorrect", f"Their maths ${claim}$"),
    )
    for key, label in checks:
        value = state.get(key)
        if value is True:
            return f"{label} is CORRECT."
        if value is False:
            facts = state.get("claimFacts")
            return f"{label} is WRONG." + (f" Why (computed): {facts}" if facts else "")
    if claim:
        return f"They wrote ${claim}$, which could not be checked. Do not call it right or wrong."
    return "No maths in their message, nothing was checked. Respond to what they actually said."


def buildFullSolution(state: TutorState) -> str:
    lines = [f"{index}. {describeStep(step)}" for index, step in enumerate(state.get("steps") or [], start=1)]
    answer = checker.formatAnswer(state["question"]["answer"])
    intro = (
        "Chalo, poora solution step by step:"
        if state["language"] == "hinglish"
        else "Here is the full solution, step by step:"
    )
    return "\n".join([intro, *lines, f"Answer: ${answer}$"])


FALLBACK_REPLIES = {
    "probe": "Line {root_line} dekho: ${root_latex}$. Is line mein jo rule use kiya, woh ek baar phir se bolo?",
    "guide_next": "Sahi! Ab line {root_line} ko dobara dekho: ${root_latex}$. Ismein kya badalna chahiye?",
    "guide_retry": "Thoda dhyan se: yeh ${asked_value}$ aata hai. Ab line {root_line} par wapas chalte hain.",
    "diagnose": "{claim_facts} Ab dobara dekho — kahan galti hui?",
    "chat_hint": "Line {wrong_line} par dhyan do: {facts}",
    "strong_hint": "Hint: {facts} Ab line {wrong_line} dobara likho.",
    "ask_one_try": "Ek baar khud try karo, phir bhi atke toh main poora solution dikha dunga. Hint: {facts} Ab line {wrong_line} dobara likho.",
    "reveal": "Sahi answer hai ${answer}$. Line {wrong_line} mein galti yeh thi: {facts}",
    "praise": "Shabash, tumne galti khud pakdi!",
    "walk_start": "Chalo saath mein karte hain. {done_step} Ab tum batao: {next_explain}",
    "walk_next": "Bilkul sahi! {done_step} Ab agla: {next_explain}",
    "walk_show": "Yahan {done_step} aata hai. Ab agla: {next_explain}",
    "walk_simpler": "Koi baat nahi, chhote step mein dekhte hain: {current_explain} Isme kya aayega?",
    "walk_chat": "Chalo is step par wapas aate hain: {current_explain}",
    "walk_done": "Bilkul sahi! {done_step} Answer: ${answer}$.",
    "walk_show_done": "Yahan {done_step} aata hai. Toh answer: ${answer}$.",
    "quick_check_result": "Sahi jawab hai ${quick_answer}$. Neeche ek practice question hai.",
    "chat": "Chalo, practice question try karo — main yahin hoon.",
}


FALLBACK_REPLIES_EN = {
    "probe": "Look at line {root_line}: ${root_latex}$. Say the rule you used in this line once more.",
    "guide_next": "Right! Now look at line {root_line} again: ${root_latex}$. What should change in it?",
    "guide_retry": "Careful: this gives ${asked_value}$. Now let's go back to line {root_line}.",
    "diagnose": "{claim_facts} Now look again: where did it go wrong?",
    "chat_hint": "Look at line {wrong_line}: {facts}",
    "strong_hint": "Hint: {facts} Now write line {wrong_line} again.",
    "ask_one_try": "Try once yourself; if you are still stuck, I will show the full solution. Hint: {facts} Now write line {wrong_line} again.",
    "reveal": "The right answer is ${answer}$. The mistake in line {wrong_line} was: {facts}",
    "praise": "Well done, you found the mistake yourself!",
    "walk_start": "Let's do it together. {done_step} Now you tell me: {next_explain}",
    "walk_next": "Exactly right! {done_step} Next: {next_explain}",
    "walk_show": "Here we get {done_step} Next: {next_explain}",
    "walk_simpler": "No problem, let's take a smaller step: {current_explain} What do you get?",
    "walk_chat": "Let's come back to this step: {current_explain}",
    "walk_done": "Exactly right! {done_step} Answer: ${answer}$.",
    "walk_show_done": "Here we get {done_step} So the answer is ${answer}$.",
    "quick_check_result": "The right answer is ${quick_answer}$. There is a practice question below.",
    "chat": "Try the practice question — I am right here.",
}


def stepText(steps: list[dict[str, Any]], index: int | None, key: str | None = None) -> str:
    if index is None or not 0 <= index < len(steps):
        return ""
    return str(steps[index].get(key) or "") if key else describeStep(steps[index])


def buildValues(state: TutorState) -> dict[str, Any]:
    steps = state.get("steps") or []
    current = state.get("step") or 0
    quickCheck = state.get("quickCheck") or {}
    rootLine = state.get("rootLine") or state["wrongLine"]
    return {
        "wrong_line": state["wrongLine"],
        "wrong_latex": state["lines"][state["wrongLine"] - 1],
        "root_line": rootLine,
        "root_latex": state["lines"][rootLine - 1],
        "asked_value": state.get("askedValue") or "",
        "facts": state["facts"],
        "claim_facts": state.get("claimFacts") or state["facts"],
        "answer": checker.formatAnswer(state["question"]["answer"]),
        # walk_start explains step 1; walk_next/walk_show confirm the step just worked out, then ask the next one.
        "done_step": stepText(steps, 0 if state["task"] == "walk_start" else current),
        "next_explain": stepText(steps, state.get("nextStep") or 0, "explain")
        or ("what is the next step?" if state["language"] == "en" else "agla step kya hoga?"),
        "next_result": stepText(steps, state.get("nextStep") or 0, "latex"),
        "current_explain": stepText(steps, current, "explain") or state["facts"],
        "current_result": stepText(steps, current, "latex"),
        "quick_answer": quickCheck.get("answer", "") if state["stage"] == "quick_check" else "",
    }


def writeReply(state: TutorState, ai: AiModels) -> dict[str, Any]:
    task = state["task"]
    values = buildValues(state)
    asked: str | None = None
    if task == "full_solution":
        reply = buildFullSolution(state)  # built from the verified steps only: nothing for the AI to get wrong
    else:
        steps = state.get("steps") or []
        system = TUTOR_PROMPT.format(
            class_level=state["question"]["class_level"],
            language=LANGUAGES[state["language"]],
            question=state["question"]["text"],
            lines="\n".join(f"{number}. {line}" for number, line in enumerate(state["lines"], start=1)),
            wrong_line=state["wrongLine"],
            wrong_latex=values["wrong_latex"],
            root_line=values["root_line"],
            root_latex=values["root_latex"],
            facts=state["facts"],
            steps="\n".join(f"{number}. {describeStep(step)}" for number, step in enumerate(steps, start=1))
            or "(not available)",
            student_text=state.get("studentText") or "(nothing yet — this is your first message)",
            turn_check=describeTurnCheck(state),
            task=TUTOR_TASKS[task].format(**values),
        )
        messages = [{"role": "system", "content": system}]
        for turn in (state.get("history") or [])[-8:]:
            messages.append({"role": "user" if turn["role"] == "student" else "assistant", "content": turn["text"]})
        messages.append({"role": "user", "content": state.get("studentText") or "(start)"})
        fallbacks = FALLBACK_REPLIES_EN if state["language"] == "en" else FALLBACK_REPLIES
        reply, asked = splitAsked(ai.askText(messages) or fallbacks[task].format(**values))
        reply = restoreLostBackslashes(cleanAddress(" ".join(re.split(r"(?<=[.!?])\s+", reply.strip())[:6])[:800]))
    if state["nextStage"] != "hints":
        asked = None  # small questions are only tracked while guiding towards the fix
    if state["nextStage"] == "quick_check" and state.get("quickCheck"):
        label = "Quick check:" if state["language"] == "en" else "Ek chhota sawaal:"
        reply = f"{reply}\n{label} {state['quickCheck']['question']}"  # type: ignore[index]
    return {"reply": reply, "speech": toSpokenText(reply), "asked": asked, "scenes": buildScenes(reply)}


SENTENCE_END = re.compile(r"(?<=[.!?।])\s+|\n+")
BOARD_WORTHY = re.compile(r"[=+\-−×÷^/]|\\(times|cdot|frac|sqrt|div)")


def buildScenes(reply: str) -> list[dict[str, Any]]:
    """Split the reply into sentences. Each sentence is spoken while its maths is written on the board.
    Only real working goes on the board (not a lone '5'), and only lines whose arithmetic is true."""
    scenes: list[dict[str, Any]] = []
    shown: set[str] = set()
    for sentence in SENTENCE_END.split(reply):
        sentence = sentence.strip()
        if not sentence:
            continue
        maths = []
        for latex in re.findall(r"\$([^$]+)\$", sentence):
            key = re.sub(r"\s+", "", latex)
            if key in shown or not BOARD_WORTHY.search(latex) or not isLineArithmeticTrue(latex):
                continue
            shown.add(key)
            maths.append(latex.strip())
        scenes.append({"text": sentence, "speech": toSpokenText(sentence), "maths": maths})
    return scenes


ASKED_LINE = re.compile(r"^\s*ASKED:\s*(.*?)\s*$", re.MULTILINE | re.IGNORECASE)


def splitAsked(text: str) -> tuple[str, str | None]:
    """Remove the 'ASKED: ...' line the tutor adds and return (reply, calculation or None)."""
    match = ASKED_LINE.search(text)
    if not match:
        return text, None
    asked = match.group(1).strip().strip("$").strip()
    reply = ASKED_LINE.sub("", text).strip()
    return reply, (None if not asked or asked.lower() in ("none", "null", "-") else asked)


def buildTutorGraph(ai: AiModels) -> Any:
    graph = StateGraph(TutorState)
    graph.add_node("understandMessage", understandMessage)
    graph.add_node("decideNext", decideNext)
    graph.add_node("makeQuickCheck", lambda state: makeQuickCheck(state, ai))
    graph.add_node("writeReply", lambda state: writeReply(state, ai))
    graph.add_edge(START, "understandMessage")
    graph.add_edge("understandMessage", "decideNext")
    graph.add_edge("decideNext", "makeQuickCheck")
    graph.add_edge("makeQuickCheck", "writeReply")
    graph.add_edge("writeReply", END)
    return graph.compile()


def runTutorTurn(ai: AiModels, state: TutorState) -> TutorState:
    return cast(TutorState, buildTutorGraph(ai).invoke(state))
