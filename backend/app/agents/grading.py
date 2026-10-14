# GradingGraph (LangGraph) — checks one attempt at a question.
#
#   readPhoto ──> guardZero ──> checkSteps ──> explainMistake (SymPy facts)
#      │              │             │
#      └─ stop: bad photo / not maths / unsure reading (student confirms the lines first)
#                     └─ stop: blank / skipped / copied / off-question = 0 marks
#                                   └─ stop: no mistake
#
# Typed working skips readPhoto. Marks and right/wrong come only from SymPy (maths/checker.py);
# the AI only reads the photo.

import re
from pathlib import Path
from typing import Any, TypedDict, cast

import sympy
from langgraph.graph import END, START, StateGraph

from app.ai.models import AiModels
from app.ai.photos import findPhotoProblem
from app.ai.prompts import READ_WORKING_PROMPT
from app.maths import checker
from app.maths.misconceptions import findQuadraticFormulaSlip, findWrongRule
from app.maths.parser import LatexParseError, normalizeLatex, parseLatex


class GradingState(TypedDict, total=False):
    # input
    question: dict[str, Any]  # {text, expressions, answer, marks, class_level}
    imagePath: str | None
    mediaType: str
    lines: list[dict[str, Any]]  # [{latex, confidence}]; given when typed or confirmed
    confidenceThreshold: float
    # output
    status: str
    steps: list[dict[str, Any]]
    score: float
    wrongLine: int | None
    explanation: str | None
    mistake: str | None  # kind of mistake, decided by code (Progress counts recurring ones)


def readPhoto(state: GradingState, ai: AiModels) -> dict[str, Any]:
    imageBytes = Path(state["imagePath"] or "").read_bytes()
    problem = findPhotoProblem(imageBytes)
    if problem:
        return {"status": "needs_retake", "explanation": problem}
    reading = ai.readImage(READ_WORKING_PROMPT, imageBytes, state["mediaType"])
    if reading is None:
        return {"status": "ai_unavailable"}  # the student can type the steps instead
    lines: list[dict[str, Any]] = [
        {"latex": str(line.get("latex", "")).strip(), "confidence": float(line.get("confidence", 0))}
        for line in reading.get("lines", [])
        if isinstance(line, dict)
        and str(line.get("latex", "")).strip()
        and line.get("kind", "working") == "working"  # rough work and the page header are not marked, like in school
        and not isPageHeader(str(line.get("latex", "")))
    ]
    if reading.get("page") == "not_maths":
        return {"lines": [], "status": "not_maths"}
    if not lines:
        return {"lines": [], "status": "blank"}
    unsure = any(line["confidence"] < state["confidenceThreshold"] for line in lines)
    return {"lines": lines, "status": "needs_confirmation" if unsure else "reading_done"}


PAGE_HEADER = re.compile(
    r"^\s*(\\text\{\s*)?(date|page|pg|chapter|ch\b|exercise|ex\b|class|name|roll|rough work|q\.?\s*\d|question\s*\d)",
    re.IGNORECASE,
)


def isPageHeader(latex: str) -> bool:
    """'DATE: 17/10/2026', 'PAGE NO: 26', 'Chapter 12: ...': a header read as maths would be checked as a step."""
    return bool(PAGE_HEADER.match(latex))


# '\\qquad' separates two statements on one line: 'x + y = 10 \\quad (1) \\qquad x - y = 2 \\quad (2)'.
STEP_BREAKS = re.compile(r"\n+|\\Rightarrow|\\implies|\\therefore|⇒|=>|;|\\qquad")
INLINE_TAG = re.compile(r"\\q?quad\s*\(\s*(?:\d+|[ivx]+)\s*\)")  # '\\quad (1)' names an equation; it is not maths


def splitChain(latex: str) -> list[str]:
    """'x = 8/2 = 4' is two steps for a teacher: 'x = 8/2' and 'x = 4'. '= 2 * 22/7 = 44/7' continues the line
    before, so it becomes '= 2 * 22/7' and '= 44/7'."""
    parts = latex.split("=")
    if len(parts) >= 3 and not parts[0].strip():
        return [f"= {part.strip()}" for part in parts[1:] if part.strip()]
    if len(parts) < 3:
        return [latex]
    first = parts[0].strip()
    return [f"{first} = {part.strip()}" for part in parts[1:] if part.strip()]


LIST_BREAKS = re.compile(r",|\\text\{\s*(?:or|and)\s*\}|\s(?:or|and)\s")
# '132/7 (= 18.86)', 'Ans: 44/7 cm^2 (approx 6.28 cm^2)', '(≈ 6.28)', '(~ 6.28)': the rounded value is its own step.
APPROXIMATELY = re.compile(
    r"^(.*?\S)\s*(?:\\text\{\s*)?\(\s*(?:\\text\{\s*)?(?:=|\\approx|≈|~|\\sim|approx\.?|approximately|or)\s*\}?\s*"
    r"([^()]+?)\s*(?:\\text\{\s*)?\)\s*\}?\s*$",
    re.IGNORECASE,
)


def splitCommaSteps(latex: str) -> list[str]:
    """'2x = 8, x = 4' or 'x = 1/2 or x = 3' -> separate lines, but only when EVERY piece is an equation
    ('A(2, 3)' stays whole). '132/7 (= 18.86)' -> '132/7' and '= 18.86'."""
    approximately = APPROXIMATELY.match(latex)
    if approximately:
        return [approximately.group(1).strip(), "= " + approximately.group(2).strip()]
    pieces = [piece.strip() for piece in LIST_BREAKS.split(latex)]
    if len(pieces) > 1 and all("=" in piece for piece in pieces):
        prefix = re.match(r"^(\\text\{[^{}]*:\s*\}\s*)", pieces[0])  # 'Ans: x = 2 or x = 3' -> both are answers
        return [pieces[0], *[(prefix.group(1) if prefix else "") + piece for piece in pieces[1:]]]
    return [latex]


TRAILING_BACKSLASH = re.compile(r"(?:[\\,]\s*)+$")  # 'a = 2, \\' at a line break
GROUP_OPENER = re.compile(r"\\[a-zA-Z]+\s*\{|\{")


def balanceBraces(steps: list[str]) -> list[str]:
    """Splitting '\\text{Rate = 8\\% \\n Time = 3 years}' cuts a group in two: the first piece never closes it and
    the second closes one it never opened, so neither shows as maths. Each piece reopens the group the one before
    left open and closes it at its own end; a stray '}' and a dangling '\\' are dropped."""
    result = []
    carried: list[str] = []
    for step in steps:
        text = "".join(carried) + TRAILING_BACKSLASH.sub("", step).strip()
        stack: list[str] = []
        kept = ""
        index = 0
        while index < len(text):
            opener = GROUP_OPENER.match(text, index) if text[index] in "\\{" else None
            if text[index] == "\\" and index + 1 < len(text) and not opener:
                kept += text[index : index + 2]  # '\\{', '\\}', '\\%': an escaped character, never a group
                index += 2
                continue
            if opener:
                stack.append(opener.group(0))
                kept += opener.group(0)
                index = opener.end()
                continue
            if text[index] == "}":
                if stack:
                    stack.pop()
                    kept += "}"
                index += 1
                continue
            kept += text[index]
            index += 1
        carried = stack
        closed = re.sub(r"\\text\{\s*\}", "", kept + "}" * len(stack))  # 'V = 12\\text{' leaves '\\text{}'
        result.append(TRAILING_BACKSLASH.sub("", closed).strip())
    return result


def splitWorkingLines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Students pack several steps in one line; the checker compares one step at a time."""
    result = []
    for line in lines:
        steps = []
        for chunk in STEP_BREAKS.split(INLINE_TAG.sub(" ", line["latex"])):
            for piece in splitCommaSteps(chunk.strip()):
                for step in splitChain(piece):
                    if step.strip():
                        steps.append(step.strip())
        for step in balanceBraces(steps):
            if step and not re.fullmatch(r"(\\[a-zA-Z]+\s*)?\{\s*\}", step):
                result.append({**line, "latex": step})
    return result or lines


def guardZero(state: GradingState) -> dict[str, Any]:
    with checker.piFromWorking([line["latex"] for line in state["lines"]]):
        return guardZeroWithPi(state)


def guardZeroWithPi(state: GradingState) -> dict[str, Any]:
    lines = splitWorkingLines(state["lines"])
    question = state["question"]
    latexLines = [line["latex"] for line in lines]
    zero = {"lines": lines, "score": 0.0, "steps": [], "wrongLine": None}
    reason = checker.findZeroReason(question["expressions"], latexLines, question.get("text"))
    if reason == "unreadable" and any(re.search(r"\d", line) for line in latexLines):
        # There ARE numbers on the page; we could not read them as maths. Our reading failed, not the student:
        # ask them to check the lines instead of giving 0.
        return {"lines": lines, "status": "needs_confirmation"}
    if reason:
        return {**zero, "status": reason}
    if not checker.isFinalAnswerCorrect(question["answer"], checker.hideCheckLines(question["answer"], latexLines)):
        # Working for a different question (another chapter exercise, a wrong page) scores 0, with the proof.
        other = checker.findOtherQuestion(
            question.get("text") or "", question["expressions"] or [], question["answer"], latexLines
        )
        if other:
            return {**zero, "status": "off_question", "explanation": other}
    return {"lines": lines, "status": "checking"}


def checkSteps(state: GradingState) -> dict[str, Any]:
    with checker.piFromWorking([line["latex"] for line in state["lines"]]):
        return checkStepsWithPi(state)


def checkStepsWithPi(state: GradingState) -> dict[str, Any]:
    question = state["question"]
    latexLines = [line["latex"] for line in state["lines"]]
    steps = checker.checkSteps(question["expressions"], latexLines, checker.getKnownPoint(question["answer"]))
    for index, step in enumerate(steps):
        # Right value, wrong structure (a square lost, the error cancelled out): a teacher marks it, so do we.
        if step.verdict == checker.CORRECT and checker.findStructureSlip(question["expressions"] or [], latexLines[index]):
            steps[index] = checker.Step(step.lineNo, checker.INCORRECT, step.isQuestionCopy, step.isAnswerLine)
    # Compare with the verified answer, like a teacher with the answer key: a line that already has the answer's
    # value is right even when nothing before it can be compared.
    referenceValues = checker.readReferenceValues(question.get("solution") or [], question.get("text") or "")
    steps = checker.markValueLines(steps, question["answer"], latexLines, referenceValues)
    answerLines = checker.hideCheckLines(question["answer"], latexLines)  # a check after the answer is not the answer
    isAnswerCorrect = checker.isFinalAnswerCorrect(question["answer"], answerLines)
    if checker.isWrongFinalAnswer(question["answer"], answerLines):
        # The answer key decides first: the stated answer is provably wrong, so the mistake is the line where that
        # wrong value first appears (every later line only simplifies it) — even when each line follows from the
        # one before it — and the wrong answer line itself.
        first = checker.findFirstWrongLine(steps)
        root = checker.findWrongValueLine(question["answer"], answerLines)
        answerLine = checker.findLastValueLine(answerLines)
        if answerLine and answerLine != checker.findLastMathsLine(answerLines):
            # The real answer line below it could not be read: this line only carries the value, so it keeps its
            # 'carried' mark — one mistake gets one ✗, never a second one on a line in between.
            answerLine = None
        if first is None:
            targets = {line for line in (root, answerLine) if line} or ({len(steps)} if root is None else set())
        else:
            # A mistake was already proven; only a wrong value that started EARLIER moves the ✗ up. The wrong answer
            # after it is that mistake carried forward, not a new one.
            targets = {root} if root and root < first else set()
        for target in targets:
            step = steps[target - 1]
            steps[target - 1] = checker.Step(step.lineNo, checker.INCORRECT, step.isQuestionCopy, step.isAnswerLine)
    score = checker.calculateMarks(question["marks"], steps, isAnswerCorrect)  # before 'carried': marks do not change
    steps = checker.markCarriedLines(steps, question["answer"], latexLines, referenceValues)
    first = checker.findFirstWrongLine(steps)
    if first and checker.findStructureSlip(question["expressions"] or [], latexLines[first - 1]):
        # The value stayed right only because the mistake cancelled out: what follows is built on it, not a ✓.
        steps = [
            checker.Step(step.lineNo, checker.CARRIED, step.isQuestionCopy, step.isAnswerLine)
            if step.lineNo > first and step.verdict == checker.CORRECT
            else step
            for step in steps
        ]
    return {
        "status": "graded",
        "steps": [
            {"line_no": step.lineNo, "verdict": step.verdict, "is_question_copy": step.isQuestionCopy} for step in steps
        ],
        "score": score,
        "wrongLine": checker.findFirstWrongLine(steps),
        "explanation": None,
    }


def explainMistake(state: GradingState) -> dict[str, Any]:
    """The explanation IS a SymPy fact ('the line before gives 3x = 15, this line gives 3x = 29'),
    a substitution check of a wrong final answer, or a known misconception for this question's numbers.
    No AI here: an AI rewording once invented a wrong story about the mistake."""
    mistake, facts = findMistake(state["question"], [line["latex"] for line in state["lines"]], state["wrongLine"] or 1)
    return {"explanation": showNames(facts), "mistake": mistake}


def showNames(text: str) -> str:
    """The parser's name for 'LCM' is Q_{lcm}; the student must see LCM."""
    return re.sub(r"Q_\{(\w+)\}", lambda match: "\\text{" + match.group(1).upper() + "}", text)


def isMathsLine(latex: str) -> bool:
    try:
        parseLatex(latex)
    except LatexParseError:
        return False
    return True


def findMistake(question: dict[str, Any], latexLines: list[str], wrongLine: int) -> tuple[str, str]:
    """(kind of mistake, the facts) for the first wrong line.
    1. a known wrong rule replayed on an earlier line gives exactly their line (misconceptions.py) — the most useful
    2. term-by-term comparison with the last MATHS line before it (word lines like 'Adding the fractions:' are skipped)
    3. a wrong final answer checked by substitution / a known trap for this question's numbers"""
    wrongLatex = latexLines[wrongLine - 1]
    structureSlip = checker.findStructureSlip(question["expressions"] or [], wrongLatex)
    if structureSlip:
        return "missed a power while substituting", structureSlip
    slip = findQuadraticFormulaSlip(question["expressions"] or [], wrongLatex)
    if slip:
        return slip
    isValueRoot = checker.findWrongValueLine(question["answer"], checker.hideCheckLines(question["answer"], latexLines)) == wrongLine
    traps = question.get("traps") or []
    value = checker.readLineValues(latexLines)[wrongLine - 1]
    if isValueRoot:
        trapped = checker.describeWrongValue(question["answer"], value, len(latexLines) - wrongLine, traps)
        if trapped and trapped[0] != "wrong formula or values":
            return trapped
        if trapped and re.match(r"^\s*Q_\{|^\s*[A-Z]\(", wrongLatex):
            return trapped  # 'P(6) = 1/6' names a value: 'this line works out to 1/6' is clearer than a term list
    earlierMaths = [line for line in latexLines[: wrongLine - 1] if isMathsLine(line)]
    starts = [*reversed(earlierMaths), *(question["expressions"] or [])]
    for start in starts:
        found = findWrongRule(start, wrongLatex)
        if found:
            return found
    # Compare like with like: an equation with the equation it came from ('Let angle = x' is only a name).
    wrongIsEquation = "=" in normalizeLatex(wrongLatex)
    sameKind = [start for start in starts if ("=" in normalizeLatex(start)) == wrongIsEquation]
    previous = (sameKind or starts or [""])[0]
    found = checker.describeMistake(previous, wrongLatex) if previous else None
    if found and previous in (question["expressions"] or []) and previous not in earlierMaths and found[1].startswith("Moving the numbers"):
        # Compared with the QUESTION itself: say the setup is wrong without giving away the answer it should lead to.
        stated = checker.readLineValues([wrongLatex])[0]
        value = f" (it leads to ${sympy.latex(stated)}$)" if stated is not None else ""
        found = (
            found[0],
            f"This line does not match the question{value}. Read the question again and check the rule or total you used to write it.",
        )
    if found is None:
        found = checker.describeScaledEquation(question["expressions"] or [], earlierMaths, wrongLatex)
    if found is None and isValueRoot:
        found = checker.describeWrongValue(question["answer"], value, len(latexLines) - wrongLine, traps)
    if found is None:
        found = checker.describeWrongAnswer(question["expressions"], question["answer"], latexLines[:wrongLine], traps)
    return found or (
        "wrong step",
        "This line does not follow from the line before it — something changed that should not have. Do just this "
        "one step again, slowly, and compare it with the line above.",
    )


def routeFromStart(state: GradingState) -> str:
    """A new photo is read first; typed or confirmed lines go straight to checking."""
    return "readPhoto" if state.get("imagePath") and not state.get("lines") else "guardZero"


def buildGradingGraph(ai: AiModels) -> Any:
    graph = StateGraph(GradingState)
    graph.add_node("readPhoto", lambda state: readPhoto(state, ai))
    graph.add_node("guardZero", guardZero)
    graph.add_node("checkSteps", checkSteps)
    graph.add_node("explainMistake", explainMistake)
    graph.add_conditional_edges(START, routeFromStart)
    graph.add_conditional_edges("readPhoto", lambda state: "guardZero" if state["status"] == "reading_done" else END)
    graph.add_conditional_edges("guardZero", lambda state: "checkSteps" if state["status"] == "checking" else END)
    graph.add_conditional_edges("checkSteps", lambda state: "explainMistake" if state["wrongLine"] else END)
    graph.add_edge("explainMistake", END)
    return graph.compile()


def runGrading(ai: AiModels, state: GradingState) -> GradingState:
    return cast(GradingState, buildGradingGraph(ai).invoke(state))
