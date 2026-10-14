# The verified worked solution of a question — used by the "full solution" card AND by the tutor,
# so what the tutor teaches always matches what the solution card shows.
#
#   1. steps from a solver (questions typed by students went through maths/solvers.py)
#   2. else, a bank question made of equations -> the equation solver
#   3. else, the AI writes steps and SymPy must accept EVERY maths line and the final answer
# Other languages only reword the explanations; the maths lines are never changed.

import re
from typing import Any

import sympy

from app.ai.models import AiModels
from app.ai.prompts import (
    DETAILED_SOLUTION_PROMPT,
    LANGUAGES,
    SOLUTION_PROMPT,
    SOLUTION_TRANSLATE_PROMPT,
    cleanAddress,
    isWrongLanguage,
    wrapBareLatex,
)
from app.db import Question
from app.maths import checker, solvers
from app.maths.parser import LatexParseError, parseLatex

Steps = list[dict[str, Any]]  # [{"explain": str, "latex": str | None}]


def isSolutionVerified(question: Question, steps: Steps) -> bool:
    """Every maths line must follow from the one before (SymPy), and the last must be the right answer."""
    mathsLines = [str(step["latex"]) for step in steps if step.get("latex")]
    if not mathsLines:
        return False
    knownPoint = checker.getKnownPoint(question.answer)
    if any(
        step.verdict == checker.INCORRECT for step in checker.checkSteps(question.expressions, mathsLines, knownPoint)
    ):
        return False
    answerLines = []
    if question.answer["type"] == "solution_set":
        answerLines = [f"{question.answer['variable']} = {value}" for value in question.answer["values"]]
    elif question.answer["type"] == "point":
        answerLines = [f"{name} = {value}" for name, value in question.answer["values"].items()]
    # A correct chain may stop at '(x-2)(x-3) = 0'; adding the answer lines must then still check out.
    return checker.isFinalAnswerCorrect(question.answer, mathsLines) or checker.isFinalAnswerCorrect(
        question.answer, mathsLines + answerLines
    )


def readSteps(data: dict[str, Any] | None, maxSteps: int = 8) -> Steps:
    steps = []
    for item in (data or {}).get("steps", [])[:maxSteps]:
        if isinstance(item, dict) and (item.get("explain") or item.get("latex")):
            latex = str(item.get("latex") or "").strip().strip("$").strip()
            if latex.lower() in ("null", "none", "-", "n/a"):
                latex = ""  # the model wrote the word instead of JSON null
            explain = cleanAddress(wrapBareLatex(str(item.get("explain") or "").strip()))
            steps.append({"explain": explain, "latex": latex or None})
    return steps


def solveBankQuestion(question: Question) -> Steps | None:
    """Bank questions have no stored solver steps; equation questions can be solved directly."""
    try:
        if question.expressions and all(
            isinstance(parseLatex(item), type(parseLatex("x=1"))) for item in question.expressions
        ):
            solved = solvers.solveEquations(question.expressions)
            if (
                checker.isFinalAnswerCorrect(question.answer, [checker.formatAnswer(solved.answer)])
                or solved.answer == question.answer
            ):
                return [{"explain": step["explain"], "latex": step["latex"] or None} for step in solved.steps]
    except (solvers.SolverError, LatexParseError):
        return None
    return None


def writeWithAi(question: Question, language: str, ai: AiModels) -> Steps | None:
    prompt = SOLUTION_PROMPT.format(
        class_level=question.class_level,
        question=question.text,
        answer=checker.formatAnswer(question.answer),
        language=LANGUAGES.get(language, LANGUAGES["en"]),
    )
    for temperature in (0.0, 0.5):  # one retry with a fresh attempt
        steps = readSteps(ai.askJson(prompt, "Write the solution.", temperature))
        if isSolutionVerified(question, steps):
            return steps
    return None


def translateExplanations(steps: Steps, language: str, ai: AiModels) -> Steps:
    sentences = [step["explain"] for step in steps]
    data = ai.askJson(SOLUTION_TRANSLATE_PROMPT.format(language=LANGUAGES[language]), "\n".join(sentences))
    translated = (data or {}).get("sentences")
    if not isinstance(translated, list) or len(translated) != len(sentences):
        return steps  # keep English rather than risk mismatched steps
    return [{**step, "explain": str(text)} for step, text in zip(steps, translated, strict=True)]


def getVerifiedSteps(question: Question, language: str, ai: AiModels) -> Steps | None:
    """Verified steps in the student's language, cached on the question (the caller commits). None = not available."""
    cache = dict(question.solution or {})
    if cache.get(language):
        return list(cache[language])
    english = cache.get("en") or solveBankQuestion(question)
    if english is None:
        steps = writeWithAi(question, language, ai)
        if steps is None:
            return None
        cache[language] = steps
    else:
        cache["en"] = english
        cache[language] = english if language == "en" else translateExplanations(english, language, ai)
    question.solution = cache
    return list(cache[language])


# ---------- detailed, notebook-style solution (Given -> To find -> Formula -> one calculation per step -> Therefore) ----------

DETAILED_MAX_STEPS = 20
EQUALITY_GROUP_SPLIT = r"\\qquad|\\quad|,|;|\\Rightarrow|\\implies|\\therefore"


def readNumber(text: str) -> sympy.Expr | None:
    """'2 \\times 2' -> 4; anything with a letter (a formula, 'S_{20}') -> None."""
    try:
        parsed = parseLatex(text)
    except LatexParseError:
        return None
    if isinstance(parsed, sympy.Expr) and parsed.is_number:
        return sympy.nsimplify(parsed)
    return None


def isLineArithmeticTrue(latex: str) -> bool:
    """Every '=' between two pure-number parts must hold: '2a = 2 \\times 2 = 4' checks 2x2 = 4.
    Parts with letters (formulas, names like S_{20}) are skipped — they are words, not claims."""
    cleaned = latex.replace("\\checkmark", "")
    for group in re.split(EQUALITY_GROUP_SPLIT, cleaned):
        values = [readNumber(part) for part in group.split("=") if part.strip()]
        numbers = [value for value in values if value is not None]
        for first, second in zip(numbers, numbers[1:], strict=False):
            if not checker.areExpressionsEquivalent(first, second) and not checker.isPiApproximation(first, second):
                return False
    return True


def readLastNumbers(latex: str) -> list[sympy.Expr]:
    """The final number of each '=' chain in a line: 'x = 2, x = 3' -> [2, 3]."""
    found = []
    for group in re.split(EQUALITY_GROUP_SPLIT, latex.replace("\\checkmark", "")):
        parts = [part for part in group.split("=") if part.strip()]
        value = readNumber(parts[-1]) if parts else None
        if value is not None:
            found.append(value)
    return found


def expectedAnswerValues(question: Question) -> list[sympy.Expr] | None:
    answer = question.answer
    try:
        if answer["type"] == "expression":
            value = readNumber(answer["latex"])
            return [value] if value is not None else None
        if answer["type"] == "solution_set":
            return [sympy.nsimplify(checker.readValue(str(item))) for item in answer["values"]]
        if answer["type"] == "point":
            return [sympy.nsimplify(checker.readValue(str(item))) for item in answer["values"].values()]
    except (LatexParseError, ValueError, TypeError, sympy.SympifyError):
        return None
    return None


def isAlgebraWriteUpTrue(question: Question, mathsLines: list[str]) -> bool:
    """A teacher's write-up also has lines that only NAME things ('3x', 'x^2 = x \\times x'), so it is not checked as
    a chain like a student's working. Instead: every '=' must be exactly true (SymPy), and one of the last lines must
    be the verified answer in the asked form (factorised / expanded)."""
    for line in mathsLines:
        for group in re.split(EQUALITY_GROUP_SPLIT, line.replace("\\checkmark", "")):
            parts = [part for part in group.split("=") if part.strip()]
            for first, second in zip(parts, parts[1:], strict=False):
                try:
                    left, right = parseLatex(first), parseLatex(second)
                except LatexParseError:
                    return False  # a claim we cannot read is not trusted
                if not isinstance(left, sympy.Expr) or not isinstance(right, sympy.Expr):
                    return False
                if checker.areExpressionsEquivalent(left, right) is not True:
                    return False
    for line in mathsLines[-5:]:
        for group in re.split(EQUALITY_GROUP_SPLIT, line):
            last = [part for part in group.split("=") if part.strip()]
            if last and checker.isFinalAnswerCorrect(question.answer, [last[-1]]):
                return True
    return False


def isDetailedSolutionTrusted(question: Question, steps: Steps) -> bool:
    """Accept the AI's detailed write-up only if all its arithmetic is true and it ends on the computed answer."""
    mathsLines = [str(step["latex"]) for step in steps if step.get("latex")]
    if len(steps) < 4 or not mathsLines:
        return False
    if not all(isLineArithmeticTrue(line) for line in mathsLines):
        return False
    expected = expectedAnswerValues(question)
    if expected is None:  # not a numeric answer (factorise, expand, simplify, prove)
        return isAlgebraWriteUpTrue(question, mathsLines) or isSolutionVerified(question, steps)
    # The answer may be followed by a check step ('3(7 - 2) = 15', '15 = 15'): look at the last 5 lines and every
    # 'x = 7' line, not only the last one.
    stated = [value for line in mathsLines[-5:] for value in readLastNumbers(line)]
    for line in mathsLines:
        assignment = checker.readAssignment(line)
        if assignment:
            stated.append(assignment[1])
    return all(any(checker.areExpressionsEquivalent(value, given) for given in stated) for value in expected)


def writeDetailedSteps(question: Question, baseSteps: Steps, language: str, ai: AiModels) -> Steps | None:
    prompt = DETAILED_SOLUTION_PROMPT.format(
        class_level=question.class_level,
        question=question.text,
        steps="\n".join(
            f"{index}. {step.get('explain') or ''} {step.get('latex') or ''}".strip()
            for index, step in enumerate(baseSteps, start=1)
        )
        or "(none yet — work it out yourself; the final answer above is correct)",
        answer=checker.formatAnswer(question.answer),
        traps="; ".join(trap["mistake"] for trap in question.traps or []) or "(none known)",
        language=LANGUAGES.get(language, LANGUAGES["en"]),
    )
    for temperature in (0.0, 0.4):
        steps = readSteps(
            ai.askJson(prompt, "Write the detailed solution.", temperature, prefer="gemini"), DETAILED_MAX_STEPS
        )
        if isStepsWrongLanguage(steps, language):
            prompt += "\nWrite EVERY explanation ONLY in simple English: no Hindi or Hinglish words at all."
            continue
        if isDetailedSolutionTrusted(question, steps):
            return steps
    return None


def isStepsWrongLanguage(steps: Steps, language: str) -> bool:
    """An English solution whose explanations read as Hinglish (the model copied the prompt's examples)."""
    return isWrongLanguage(" ".join(str(step.get("explain") or "") for step in steps), language)


def getDetailedSteps(question: Question, language: str, ai: AiModels) -> Steps | None:
    """The detailed notebook solution in the student's language (cached on the question; the caller commits).
    Falls back to the shorter verified steps when the detailed write-up cannot be trusted."""
    cacheKey = f"detailed_v5_{language}"  # v5: teaches like a class teacher (why + common mistakes), maths in $...$
    cache = dict(question.solution or {})
    if cache.get(cacheKey) and not isStepsWrongLanguage(cache[cacheKey], language):
        return list(cache[cacheKey])
    baseSteps = getVerifiedSteps(question, language, ai)
    # Even without verified base steps (e.g. cube roots), a detailed write-up is safe to show: every number line
    # is re-checked and it must end on the computed answer.
    detailed = writeDetailedSteps(question, baseSteps or [], language, ai)
    if detailed is None:
        return baseSteps
    cache = dict(question.solution or {})  # getVerifiedSteps may have added entries
    cache[cacheKey] = detailed
    question.solution = cache
    return list(detailed)
