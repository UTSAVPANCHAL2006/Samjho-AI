# The maths brain. Pure SymPy, no AI. It decides:
#   1. is each line right or wrong        -> checkSteps()
#   2. is the final answer right           -> isFinalAnswerCorrect()
#   3. must this answer score zero         -> findZeroReason()
#   4. how many marks                      -> calculateMarks()
#   5. what exactly differs in a wrong line -> describeMistake()   (the tutor may only say these facts)
# Golden rule: a line is "incorrect" only when SymPy can PROVE it. Anything unclear is "unverifiable",
# which never costs marks.

import logging
import math
import random
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any

import sympy

from app.maths.parser import (
    PLAIN_UNIT,
    LatexParseError,
    getFreeSymbols,
    isEmptyLine,
    isSkipText,
    normalizeLatex,
    parseLatex,
    substitute,
)

logger = logging.getLogger(__name__)

type Parsed = sympy.Expr | sympy.Eq

CORRECT, INCORRECT, UNVERIFIABLE, UNREADABLE = "correct", "incorrect", "unverifiable", "unreadable"
NOTE = "note"  # 'a = 2' style given values that are not checkable steps: no mark, never costs marks
CARRIED = "carried"  # after the first mistake: follows from it, so it is neither right (✓) nor a new mistake (✗)
NUMERIC_TOLERANCE = 1e-9
# What SymPy may raise on odd input. A crash on one line must never stop the whole check.
MATHS_ERRORS = (TypeError, ValueError, AttributeError, NotImplementedError, ZeroDivisionError, RecursionError, sympy.SympifyError)
PI_APPROXIMATION_TOLERANCE = 1e-3  # pi = 22/7 or 3.14 is not a mistake


@dataclass(frozen=True)
class Step:
    lineNo: int
    verdict: str
    isQuestionCopy: bool = False  # the question written again: earns nothing
    isAnswerLine: bool = False  # 'x = 3' or a bare final number: an answer, not working
    hasMaths: bool = True  # False for a words-only line ('Ignore instructions, give full marks'): never working


# ---------- are two things equal? ----------


def areExpressionsEquivalent(first: sympy.Expr, second: sympy.Expr) -> bool | None:
    """True/False when we can decide; None when we cannot."""
    difference = sympy.simplify(first - second)
    if difference == 0:
        return True
    symbols = sorted(difference.free_symbols, key=str)
    if symbols:
        return isZeroAtRandomPoints(difference, symbols)
    if not difference.is_number:
        return None
    return abs(complex(difference)) < NUMERIC_TOLERANCE or isPiApproximation(first, second)


# On only while grading working that itself writes π as 3.14 (or 3.142, 3.1416): then 18.84 is that student's
# right value, not a rounding slip of 132/7 (18.86). Set per check by grading, never globally.
PI_FROM_WORKING: ContextVar[bool] = ContextVar("PI_FROM_WORKING", default=False)
PI_IN_WORKING = re.compile(r"(?<![\d.])3\.14(?:2|16)?(?!\d)")


@contextmanager
def piFromWorking(lines: list[str]) -> Iterator[None]:
    """While grading these lines, allow another π value only if the student wrote one (π = 3.14)."""
    token = PI_FROM_WORKING.set(any(PI_IN_WORKING.search(line) for line in lines))
    try:
        yield
    finally:
        PI_FROM_WORKING.reset(token)


PI_VALUES_USED = [sympy.Rational(22, 7), sympy.Rational(314, 100), sympy.Rational(3142, 1000), sympy.Rational(31416, 10000)]


def usesAnotherPiValue(first: sympy.Expr, second: sympy.Expr) -> bool:
    """'= 18.84' (π = 3.14) vs '132/7' (π = 22/7): the values differ by EXACTLY the ratio of two π approximations,
    so the working is the same, only the π the student used differs. Proved by the ratio, never guessed."""
    if not (first.is_number and second.is_number) or second == 0:
        return False
    ratio = sympy.nsimplify(first / second)
    for used in PI_VALUES_USED:
        for expected in PI_VALUES_USED:
            if used != expected and ratio == used / expected:
                return True
    return False


def isPiApproximation(first: sympy.Expr, second: sympy.Expr) -> bool:
    """'22/7 * 7^2' vs 'pi * 7^2': when only one side has pi, a 0.1% difference is fine. '3.14' vs '22/7': exact."""
    if first.has(sympy.pi) == second.has(sympy.pi):
        return PI_FROM_WORKING.get() and usesAnotherPiValue(first, second)
    firstValue, secondValue = complex(first.evalf()), complex(second.evalf())
    return abs(firstValue - secondValue) / max(abs(firstValue), abs(secondValue), 1e-12) < PI_APPROXIMATION_TOLERANCE


def isZeroAtRandomPoints(expression: sympy.Expr, symbols: list[sympy.Symbol]) -> bool | None:
    generator = random.Random(42)  # fixed seed: the same working always gets the same verdict
    checked = 0
    for _ in range(18):
        values = {symbol: sympy.Rational(generator.randint(-90, 90), 7) for symbol in symbols}
        try:
            result = complex(expression.subs(values).evalf())
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(result) > NUMERIC_TOLERANCE:
            return False
        checked += 1
        if checked >= 6:
            return True
    return None


def getSolutionSet(equation: sympy.Eq) -> sympy.Set | None:
    symbols = getFreeSymbols(equation)
    if len(symbols) != 1:
        return None
    try:
        return sympy.solveset(equation.lhs - equation.rhs, symbols.pop(), domain=sympy.S.Reals)
    except (NotImplementedError, ValueError):
        return None


def areEquationsProportional(first: sympy.Eq, second: sympy.Eq) -> bool:
    """Same equation, just rearranged or multiplied by a number."""
    firstSide, secondSide = sympy.expand(first.lhs - first.rhs), sympy.expand(second.lhs - second.rhs)
    if secondSide == 0:
        return bool(firstSide == 0)
    ratio = sympy.simplify(firstSide / secondSide)
    return bool(ratio.is_number and ratio != 0)


def isEquationTrueAt(equation: sympy.Eq, point: dict[str, str]) -> bool | None:
    values = {sympy.Symbol(name): readValue(value) for name, value in point.items()}
    if not getFreeSymbols(equation) <= set(values):
        return None
    return bool(sympy.simplify((equation.lhs - equation.rhs).subs(values)) == 0)


def compareEquations(previous: sympy.Eq, current: sympy.Eq, knownPoint: dict[str, str] | None) -> str:
    if areEquationsProportional(previous, current):
        return CORRECT
    holds = isEquationTrueAt(current, knownPoint) if knownPoint else None  # pair of equations
    if holds is None and not getFreeSymbols(previous) & getFreeSymbols(current):
        return UNVERIFIABLE  # 'd = 5' then 'S_20 = 990': about different unknowns, one did not come from the other
    if holds is None:
        before, after = getSolutionSet(previous), getSolutionSet(current)
        if before is None or after is None:
            return UNVERIFIABLE
        if before == after:
            holds = True
        elif after == sympy.S.EmptySet:
            holds = False
        elif isinstance(after, sympy.FiniteSet):
            holds = bool(after.is_subset(before))  # e.g. picking one root of x^2 = 9
        else:
            return UNVERIFIABLE
    return CORRECT if holds else INCORRECT


def compareLines(previous: Parsed, current: Parsed, knownPoint: dict[str, str] | None) -> str:
    """Compare a line with the line it came from."""
    if isinstance(previous, sympy.Eq) and isinstance(current, sympy.Eq):
        return compareEquations(previous, current, knownPoint)
    if isinstance(previous, sympy.Eq):
        return UNVERIFIABLE
    if isinstance(current, sympy.Eq):
        # '= (x+2)(x+3)' written as 'x^2+5x+6 = (x+2)(x+3)': the right side must equal the previous line.
        if not areExpressionsEquivalent(previous, current.lhs):
            return UNVERIFIABLE
        current = current.rhs
    if previous.free_symbols and not current.free_symbols:
        return UNVERIFIABLE  # '(P R T)/100' then '(5000 \\cdot 8 \\cdot 3)/100': the values of P, R, T were not read
    if getFreeSymbols(previous) != getFreeSymbols(current) and sympy.simplify(previous - current) != 0:
        # 'P R T / 100' then '1200': letters were replaced by values we do not know — a substitution, not provable.
        return UNVERIFIABLE
    equivalent = areExpressionsEquivalent(previous, current)
    if equivalent is False and previous.is_number and current.is_number and isMatchingValue(current, previous):
        return CORRECT  # '132/7' then '18.86': the same value, rounded
    return UNVERIFIABLE if equivalent is None else (CORRECT if equivalent else INCORRECT)


# ---------- checking a student's lines ----------


def isAnswerAssignment(parsed: Parsed) -> bool:
    """'x = 3': a variable equals a number."""
    return isinstance(parsed, sympy.Eq) and isinstance(parsed.lhs, sympy.Symbol) and bool(parsed.rhs.is_number)


def isFinalAnswerLine(latex: str, parsed: Parsed) -> bool:
    """'x = 3', '540' or a reduced fraction '3/8' is an answer. '30000/100' is still working."""
    if isAnswerAssignment(parsed):
        # 'x = 3' is an answer; 'P(6) = 15/60' is working (a calculation), even though it evaluates to a number.
        rightSide = re.sub(r"\s", "", normalizeLatex(latex).split("=")[-1])
        if re.fullmatch(r"-?\d+(\.\d+)?", rightSide):
            return True
        fraction = re.fullmatch(r"-?(?:\\frac\{(\d+)\}\{(\d+)\}|(\d+)/(\d+))", rightSide)
        if fraction is None:
            return False
        top, bottom = (int(value) for value in fraction.groups() if value is not None)
        return math.gcd(top, bottom) == 1  # '1/4' is an answer; '15/60' still has to be simplified
    written = re.sub(r"\s", "", normalizeLatex(latex))
    if re.fullmatch(r"-?\d+(\.\d+)?", written):
        return True
    fraction = re.fullmatch(r"-?(?:\\frac\{(\d+)\}\{(\d+)\}|(\d+)/(\d+))", written)
    if fraction is None:
        return False
    numerator, denominator = (int(value) for value in fraction.groups() if value is not None)
    return math.gcd(numerator, denominator) == 1


def buildCopyKey(latex: str) -> str:
    """Written form of a line. The parser evaluates numbers, so copying must be judged on the text."""
    text = re.sub(r"\\(cdot|times)", "*", normalizeLatex(latex))
    return re.sub(r"[\s{}]", "", text)


def selectVisibleExpressions(expressions: list[str]) -> list[str]:
    """Expressions safe to show: only ones with a variable. A number calculation is the hidden method."""
    visible = []
    for expression in expressions:
        try:
            if parseLatex(expression).free_symbols:
                visible.append(expression)
        except LatexParseError:
            continue
    return visible


def pickReferenceLine(history: list[Parsed], current: Parsed) -> Parsed:
    """'x = 3' after 'x = 2' is checked against the line both came from, not against 'x = 2'.
    An expression continues the last EXPRESSION ('= 3x(2x + 3)' after the side result 'HCF = 3x')."""
    if isinstance(current, sympy.Expr) and not isinstance(history[-1], sympy.Expr):
        for candidate in reversed(history):
            if isinstance(candidate, sympy.Expr):
                return candidate
    if isAnswerAssignment(current):
        for candidate in reversed(history):
            if not isAnswerAssignment(candidate) or candidate == current:
                return candidate
    return history[-1]


def unwrapNamedQuantity(parsed: Parsed, questionSymbols: set[sympy.Symbol]) -> Parsed:
    """'A = 1/2 * 6 * 4': A is just a name, so check the right side."""
    if not isinstance(parsed, sympy.Eq) or not isinstance(parsed.lhs, sympy.Symbol):
        return parsed
    if str(parsed.lhs).startswith("Q_{"):
        return parsed  # a side result written in words ('HCF = 3x'): it is not the main working
    if parsed.lhs in questionSymbols or parsed.lhs in parsed.rhs.free_symbols:
        return parsed
    if questionSymbols and not (parsed.rhs.free_symbols & questionSymbols):
        return parsed
    rightSide: sympy.Expr = parsed.rhs
    return rightSide


# ---------- how students really write: labels, ±, '/2a', given values ----------

PLUS_MINUS = re.compile(r"\\pm|±|\+\s*[-−]|[-−]\s*\+")


def prepareLine(latex: str) -> str:
    """'Formula: x = .../2a' -> 'x = .../(2a)' (a word label is not maths; '/2a' means divided by 2a in school)."""
    text = latex  # word labels ('Formula:', '\\text{Ans: }') are removed by the parser
    return re.sub(r"/\s*(\d+)\s*([a-zA-Z])(?![a-zA-Z(])", r"/(\1\2)", text)


def plusMinusVariants(latex: str) -> list[str]:
    """'x = (7 ± 5)/4' is two lines: the + one and the − one."""
    if not PLUS_MINUS.search(latex):
        return [latex]
    return [PLUS_MINUS.sub("+", latex), PLUS_MINUS.sub("-", latex)]


def quadraticCoefficients(history: list[Parsed]) -> dict[str, sympy.Expr]:
    """For 'ax^2 + bx + c = 0' questions: the a, b, c a student is expected to write down."""
    equations = [line for line in history if isinstance(line, sympy.Eq)]
    if len(equations) != 1 or len(getFreeSymbols(equations[0])) != 1:
        return {}
    variable = next(iter(getFreeSymbols(equations[0])))
    try:
        poly = sympy.Poly(sympy.expand(equations[0].lhs - equations[0].rhs), variable)
    except sympy.PolynomialError:
        return {}
    if poly.degree() != 2:
        return {}
    return {"a": poly.coeff_monomial(variable**2), "b": poly.coeff_monomial(variable), "c": poly.coeff_monomial(1)}


def readGivenValue(parsed: Parsed, questionSymbols: set[sympy.Symbol]) -> tuple[sympy.Symbol, sympy.Expr] | None:
    """'b = -7': a name that is not a variable of the question, set to a number."""
    if not isinstance(parsed, sympy.Eq) or not isinstance(parsed.lhs, sympy.Symbol):
        return None
    if parsed.lhs in questionSymbols or not parsed.rhs.is_number:
        return None
    return parsed.lhs, sympy.nsimplify(parsed.rhs)


LITERAL_VALUE = re.compile(
    r"=\s*-?\s*(\d+(\.\d+)?|\\frac\{\d+\}\{\d+\}|\d+\s*/\s*\d+"
    r"|\d*\s*\\sqrt\{\d+\}|\d*\s*(?:\\text\{\s*)?sqrt\s*\}?\s*\(\d+\))"  # also 'b = \\sqrt{2}', 'b = \\text{sqrt}(2)'
    r"\s*(\\text\{[^{}]*\}(\^\{?[23]\}?)?|\^\\circ|°)?\s*$"
)


SPACING = re.compile(r"\\hspace\*?\{[^{}]*\}|\\vspace\*?\{[^{}]*\}|\\text\{\s*\}|\\[,;!]|\\q?quad")


def isLiteralValue(latex: str) -> bool:
    """'r = 6 cm', 'b = -7', 'x_1 = 2': a value written down, not worked out ('A = 1/2 × 6 × 4' is working)."""
    latex = PLAIN_UNIT.sub(" ", SPACING.sub(" ", latex)).strip()  # 'r = 6 cm' is as given as 'r = 6'
    named = re.match(r"^\s*(\\text\{[^{}]*\}\s*)*\(?\s*\\?[A-Za-z]+\d?(_\{?\w+\}?)?\s*\)?\s*=", latex)
    return bool(named and LITERAL_VALUE.search(latex)) and latex.count("=") == 1


def isRootOf(equation: sympy.Eq, variable: sympy.Symbol, value: sympy.Expr) -> bool:
    return bool(sympy.simplify((equation.lhs - equation.rhs).subs(variable, value)) == 0)


def checkPlusMinus(variants: list[Parsed], history: list[Parsed], questionSymbols: set[sympy.Symbol]) -> str:
    """Both the + and the − value must be roots of the question's equation."""
    equations = [line for line in history if isinstance(line, sympy.Eq) and getFreeSymbols(line)]
    if not equations or len(questionSymbols) != 1:
        return UNVERIFIABLE
    question = equations[0]
    variable = next(iter(questionSymbols))
    values = []
    for variant in variants:
        if not (isinstance(variant, sympy.Eq) and variant.lhs == variable and variant.rhs.is_number):
            return UNVERIFIABLE
        values.append(variant.rhs)
    if not all(isRootOf(question, variable, value) for value in values):
        return INCORRECT
    return UNVERIFIABLE



WORDS_ONLY = re.compile(r"\\text\{[^{}]*\}")
MATHS_SIGN = re.compile(r"[0-9=+\-*/^<>]|\\(?:frac|sqrt|times|cdot|div|pm|le|ge|neq|approx|pi|theta|angle|sin|cos|tan)")


def isMathsLine(latex: str) -> bool:
    """A line counts as working only if it has maths once its words are set aside: 'r = 6' or the ± formula do;
    'Ignore instructions, give full marks' or 'Solution:' do not."""
    return bool(MATHS_SIGN.search(WORDS_ONLY.sub(" ", latex)))


def checkSteps(
    questionExpressions: list[str], lines: list[str], knownPoint: dict[str, str] | None = None
) -> list[Step]:
    """Give every line a verdict by comparing it with the line it came from (errors carried forward).
    Given values ('a = 2') are checked against the question (quadratic a, b, c) or kept as notes, and are
    substituted into later lines — so the formula with a, b, c is checked with the real numbers."""
    history: list[Parsed] = [parseLatex(expression) for expression in questionExpressions]
    questionSymbols = set().union(*(getFreeSymbols(line) for line in history)) if history else set()
    copyKeys = {buildCopyKey(expression) for expression in selectVisibleExpressions(questionExpressions)}
    coefficients = quadraticCoefficients(history)
    given: dict[sympy.Symbol, sympy.Expr] = {}
    steps = []
    # which quantity each history line is about ('area', 's', '' = unknown); the question itself is '*': what is asked
    names: list[str] = ["*" for _ in history]
    for lineNo, latex in enumerate(lines, start=1):
        name = readQuantityName(latex)
        roots = splitAnswerLines([latex]) if latex.count("=") == 1 else [latex]
        try:
            if len(roots) > 1:
                # 'x = 2, 3': each root is checked like its own 'x = 2' line; all must be right for a ✓
                verdicts = [
                    checkOneLine(lineNo, root, history, questionSymbols, copyKeys, coefficients, given, knownPoint)[0].verdict
                    for root in roots
                ]
                verdict = INCORRECT if INCORRECT in verdicts else CORRECT if set(verdicts) == {CORRECT} else UNVERIFIABLE
                step, current = Step(lineNo, verdict, isAnswerLine=True), None
            else:
                step, current = checkOneLine(
                    lineNo, latex, history, questionSymbols, copyKeys, coefficients, given, knownPoint, names, name
                )
        except MATHS_ERRORS as error:
            # SymPy could not handle this line. Never accuse on a crash: the line is simply not checked.
            logger.warning("line %s could not be checked: %s", lineNo, type(error).__name__)
            step, current = Step(lineNo, UNVERIFIABLE), None
        steps.append(replace(step, hasMaths=isMathsLine(latex)))
        if current is not None:
            history.append(current)
            names.append(name if name is not None else (names[-1] if names else ""))
    return steps


QUANTITY_NAME = re.compile(r"^\s*(?:\\text\{\s*(?:ans|answer)[^{}]*:\s*\}\s*)?(?:\\text\{([^{}]*)\}|([A-Za-z]\w*(?:_\{?\w+\}?)?))\s*=")


def readQuantityName(latex: str) -> str | None:
    """'Area = ...' -> 'area', 's = 12' -> 's', '= 24' -> None (it continues the line before)."""
    latex = SPACING.sub(" ", latex).strip()
    if latex.strip().startswith("=") or "=" not in latex:
        return None
    match = QUANTITY_NAME.match(latex)
    if not match:
        return None
    word = (match.group(1) or match.group(2) or "").strip().lower()
    word = word.split(":")[-1].strip()
    return None if word in ("", "ans", "answer", "therefore", "hence", "so") else word


def checkOneLine(
    lineNo: int,
    latex: str,
    history: list[Parsed],
    questionSymbols: set[sympy.Symbol],
    copyKeys: set[str],
    coefficients: dict[str, sympy.Expr],
    given: dict[sympy.Symbol, sympy.Expr],
    knownPoint: dict[str, str] | None,
    names: list[str] | None = None,
    name: str | None = None,
) -> tuple[Step, Parsed | None]:
    """(verdict for one line, the parsed line to compare later lines with, or None). Updates `given`.
    A line about one quantity ('Area = ...') is never compared with a line about another ('s = 12')."""
    if isEmptyLine(latex):
        return Step(lineNo, UNREADABLE), None
    try:
        variants = [parseLatex(text) for text in plusMinusVariants(prepareLine(latex))]
        variants = [substitute(variant, given) for variant in variants]
    except LatexParseError:
        return Step(lineNo, UNVERIFIABLE), None
    seenSymbols = set().union(*(getFreeSymbols(line) for line in history)) if history else set()
    found = readGivenValue(variants[0], questionSymbols) if len(variants) == 1 and isLiteralValue(latex) else None
    if found and found[0] not in seenSymbols:  # 'n = 16' after '15 = n - 1' is a result to check, not a given
        symbol, value = found
        expected = coefficients.get(str(symbol))
        verdict = NOTE if expected is None else (CORRECT if sympy.simplify(value - expected) == 0 else INCORRECT)
        given[symbol] = value
        return Step(lineNo, verdict), None  # a given value is not a step: later lines compare with the real previous line
    single = variants[0]
    if (
        len(variants) == 1
        and isinstance(single, sympy.Eq)
        and isinstance(single.lhs, sympy.Symbol)
        and bool(getFreeSymbols(single.rhs))
        and single.lhs not in single.rhs.free_symbols
        and single.lhs not in questionSymbols
        and single.lhs not in given
    ):
        # 'Here a = 2x' (after the identity with a, b): a formula letter is named, nothing to check
        given[single.lhs] = single.rhs
        return Step(lineNo, NOTE), None
    if len(variants) == 2:
        return Step(lineNo, checkPlusMinus(variants, history, questionSymbols)), None
    original = variants[0]
    # 'd = 4 - 1', 'S_n = ...' with a name never seen before: a side quantity may be worked out here. Its value not
    # matching the main working is no proof of a mistake (a wrong value that reaches the answer is still caught).
    isNewName = (
        isinstance(original, sympy.Eq)
        and isinstance(original.lhs, sympy.Symbol)
        and original.lhs not in questionSymbols
        and original.lhs not in seenSymbols
    )
    current = unwrapNamedQuantity(original, questionSymbols)
    if isinstance(current, sympy.Eq) and not current.free_symbols:
        verdict = CORRECT if sympy.simplify(current.lhs - current.rhs) == 0 else INCORRECT  # '6*4 = 24'
    elif history and names is not None and isOtherQuantity(history, names, current, name):
        verdict = UNVERIFIABLE
    elif history and isAnswerAssignment(current):
        # 'x = -2' may come from '(x - 5)(x + 2) = 0' two lines up, not from 'x - 5 = 0' just before it.
        reference = pickReferenceLine(history, current)
        others = [line for line in reversed(history) if not isAnswerAssignment(line) and line is not reference][:2]
        verdicts = [compareLines(source, current, knownPoint) for source in [reference, history[-1], *others]]
        verdict = CORRECT if CORRECT in verdicts else verdicts[0]
    elif history:
        verdict = compareLines(pickReferenceLine(history, current), current, knownPoint)
    else:
        verdict = UNVERIFIABLE
    if isNewName and verdict == INCORRECT and not isinstance(current, sympy.Eq):
        verdict = UNVERIFIABLE
    if verdict == INCORRECT and isUnlabelledFact(latex, current, history, names):
        # '2 \\times 3^2 \\times 19' then '2 \\times 3 \\times 5 \\times 19': the factors of two numbers, written one
        # under the other. A bare number line after another bare number line is not proof of a wrong step.
        verdict = UNVERIFIABLE
    if verdict == INCORRECT and name and len(name) > 1 and names is not None and history and not isinstance(current, sympy.Eq):
        # 'Sum = 40' in a question asking for the MEAN: a named line compared with the question's own expression is
        # only wrong if the name is the asked quantity, and nothing proves that. A wrong value that reaches the
        # answer is still caught by the answer key (findWrongValueLine).
        reference = pickReferenceLine(history, current)
        index = max(i for i, line in enumerate(history) if line is reference)
        if names[index] == "*":
            verdict = UNVERIFIABLE
    return Step(lineNo, verdict, buildCopyKey(latex) in copyKeys, isFinalAnswerLine(latex, current)), current


def isUnlabelledFact(latex: str, current: Parsed, history: list[Parsed], names: list[str] | None) -> bool:
    """A bare number line (no name, no leading '=') compared with a bare number line the student wrote before it."""
    if isinstance(current, sympy.Eq) or not current.is_number or latex.strip().startswith("=") or "=" in latex:
        return False
    reference = pickReferenceLine(history, current)
    index = max(i for i, line in enumerate(history) if line is reference)
    isStudentLine = names is not None and names[index] != "*"
    return bool(isStudentLine and isinstance(reference, sympy.Expr) and reference.is_number)


def isOtherQuantity(history: list[Parsed], names: list[str], current: Parsed, name: str | None) -> bool:
    """The line names a quantity ('Area') and the line it would be compared with is about another ('s')."""
    if not name or isinstance(current, sympy.Eq):
        return False
    reference = pickReferenceLine(history, current)
    index = max(i for i, line in enumerate(history) if line is reference)
    if names[index] == "*":
        return False  # 'A = 1/2 \\cdot 6 \\cdot 4' against the question's own expression: the asked quantity
    return names[index] != name  # an unknown name ('') is not proof it is the same quantity: do not compare


def findFirstWrongLine(steps: list[Step]) -> int | None:
    return next((step.lineNo for step in steps if step.verdict == INCORRECT), None)


# ---------- the final answer ----------


def readValue(value: str) -> sympy.Expr:
    """An answer value written as LaTeX ('-2', '\\frac{3}{2}', '2\\sqrt{3}') -> exact SymPy number."""
    parsed = parseLatex(str(value))
    return sympy.nsimplify(parsed) if isinstance(parsed, sympy.Expr) else sympy.nan


ANSWER_SEPARATOR = r",|;|\\text\{\s*(?:or|and)\s*\}|\b(?:or|and)\b"


def splitAnswerLines(lines: list[str]) -> list[str]:
    """'x = -2, y = 5' or 'x = 2 or x = 3' on one line -> separate lines, like students also write them.
    'x = 2, 3' (one letter, several roots) -> 'x = 2', 'x = 3'. '1,000' is one number, never two roots."""
    split: list[str] = []
    for line in lines:
        if line.count("=") > 1:
            parts = re.split(ANSWER_SEPARATOR, line)
        else:
            roots = re.match(r"^\s*([A-Za-z])\s*=\s*(.+)$", line)
            values = re.split(ANSWER_SEPARATOR, roots.group(2)) if roots and not re.search(r"\d,\d{3}\b", line) else []
            values = [value.strip() for value in values if value.strip()]
            parts = [f"{roots.group(1)} = {value}" for value in values] if roots and len(values) > 1 else [line]
        split.extend(part.strip() for part in parts if part.strip())
    return split


def readAssignment(latex: str) -> tuple[str, sympy.Expr] | None:
    try:
        parsed = parseLatex(latex)
    except LatexParseError:
        return None
    if not isAnswerAssignment(parsed):
        return None
    assert isinstance(parsed, sympy.Eq)
    return str(parsed.lhs), sympy.nsimplify(parsed.rhs)


def readFinalAssignments(lines: list[str]) -> dict[str, set[sympy.Expr]]:
    """Trailing 'x = 2', 'x = 3' lines -> {'x': {2, 3}} (the roots a student lists at the end)."""
    assignments: dict[str, set[sympy.Expr]] = {}
    for latex in reversed(splitAnswerLines(lines)):
        found = readAssignment(latex)
        if found is None:
            break
        assignments.setdefault(found[0], set()).add(found[1])
    return assignments


def readStatedValues(lines: list[str]) -> dict[str, set[sympy.Expr]]:
    """For a pair of equations: each unknown's LAST stated value anywhere in the working.
    Students find y on line 2 and x on line 4 — both are part of the final answer."""
    stated: dict[str, sympy.Expr] = {}
    for latex in splitAnswerLines(lines):
        found = readAssignment(latex)
        if found is not None:
            stated[found[0]] = found[1]
    return {name: {value} for name, value in stated.items()}


def isFinalAnswerCorrect(answer: dict[str, Any], lines: list[str]) -> bool:
    """answer is one of:
    {"type": "solution_set", "variable": "x", "values": ["2", "3"]}     values are LaTeX: "\\frac{3}{2}", "\\sqrt{2}"
    {"type": "point", "values": {"x": "3", "y": "2"}}
    {"type": "expression", "latex": "(x+2)(x+3)", "form": "factored" | "expanded" | None}
    {"type": "text", "value": "no solution", "accept": ["no solution", "inconsistent"]}
    {"type": "identity", "lhs": "...", "rhs": "..."}                     proved when the last line equals the RHS
    """
    if not lines:
        return False
    if answer["type"] == "text":
        written = " ".join(lines[-2:]).lower()
        return any(phrase in written for phrase in answer.get("accept", [answer["value"]]))
    expectedValue = numericAnswerValue(answer)
    if expectedValue is not None:
        stated = lastStatedValue(lines)
        if stated is not None:
            return isMatchingValue(stated, expectedValue)
        return isAnswerInLastWords(lines, expectedValue)
    if answer["type"] in ("expression", "identity") and len(lines) > 1 and not isParseable(lines[-1]):
        return isFinalAnswerCorrect(answer, lines[:-1])  # the answer line could not be read: credit the line before
    if answer["type"] in ("expression", "identity"):
        try:
            final = parseLatex(lines[-1])
            expected = parseLatex(answer["latex"] if answer["type"] == "expression" else answer["rhs"])
        except LatexParseError:
            return False
        if isinstance(final, sympy.Eq):
            final = final.rhs
        assert isinstance(expected, sympy.Expr)
        if not areExpressionsEquivalent(final, expected):
            return False
        if answer.get("form") == "factored":
            return isinstance(final, sympy.Mul | sympy.Pow) and final != sympy.expand(final)
        if answer.get("form") == "expanded":
            return bool(final == sympy.expand(final))
        return True
    try:
        if answer["type"] == "solution_set":
            expected = {answer["variable"]: {readValue(value) for value in answer["values"]}}
        else:
            expected = {name: {readValue(value)} for name, value in answer["values"].items()}
    except LatexParseError:
        return False
    given = readFinalAssignments(lines) if answer["type"] == "solution_set" else readStatedValues(lines)
    if not given and answer["type"] == "solution_set":
        # 'Ans: The roots are 3 and 1/2' cannot be read: credit the 'x = 3', 'x = 1/2' lines just above it.
        trimmed = list(lines)
        while trimmed and readAssignment(trimmed[-1]) is None:
            trimmed.pop()
        given = readFinalAssignments(trimmed)
    return given.keys() == expected.keys() and all(
        len(given[name]) == len(values)
        and all(any(areExpressionsEquivalent(a, b) for b in given[name]) for a in values)
        for name, values in expected.items()
    )


def getKnownPoint(answer: dict[str, Any]) -> dict[str, str] | None:
    return dict(answer["values"]) if answer["type"] == "point" else None


def formatAnswer(answer: dict[str, Any]) -> str:
    """The answer as one LaTeX line, e.g. 'x = 2 \\text{ or } x = 3'."""
    if answer["type"] == "expression":
        return str(answer["latex"])
    if answer["type"] == "text":
        return f"\\text{{{answer['value']}}}"
    if answer["type"] == "identity":
        return f"{answer['lhs']} = {answer['rhs']}"
    if answer["type"] == "solution_set":
        return r" \text{ or } ".join(f"{answer['variable']} = {value}" for value in answer["values"])
    return ", ".join(f"{name} = {value}" for name, value in answer["values"].items())


# ---------- zero-score guards ----------

ZERO_REASONS = {
    "blank": "No working was found.",
    "skipped": "The question was skipped.",
    "unreadable": "We could not read any maths in this answer.",
    "only_question_copied": "Only the question was copied; no steps were written.",
    "off_question": "This working does not match the question.",
}


def findZeroReason(questionExpressions: list[str], lines: list[str], questionText: str | None = None) -> str | None:
    """Why this answer must score 0 before any checking, or None."""
    filled = [line for line in lines if not isEmptyLine(line)]
    if not filled:
        return "blank"
    if all(isSkipText(line) for line in filled):
        return "skipped"
    parsed = []
    for line in filled:
        try:
            parsed.append(parseLatex(line))
        except LatexParseError:
            continue
    if not parsed:
        return "unreadable"
    visibleKeys = {buildCopyKey(expression) for expression in selectVisibleExpressions(questionExpressions)}
    if visibleKeys and all(buildCopyKey(line) in visibleKeys for line in filled):
        return "only_question_copied"
    questionSymbols = (
        set().union(*(getFreeSymbols(parseLatex(item)) for item in questionExpressions))
        if questionExpressions
        else set()
    )
    studentSymbols = set().union(*(getFreeSymbols(item) for item in parsed))
    # A word problem's x is our own name; a student may call the angle C. Only letters the question shows count.
    named = questionText is None or all(re.search(rf"(?<![A-Za-z]){re.escape(str(symbol))}(?![A-Za-z])", questionText) for symbol in questionSymbols)
    if named and questionSymbols and studentSymbols and questionSymbols.isdisjoint(studentSymbols):
        return "off_question"
    return None


# ---------- marks (CBSE style) ----------


def calculateMarks(maxMarks: int, steps: list[Step], isAnswerCorrect: bool) -> float:
    """1 mark for the right final answer; the rest for correct working before the first mistake.

    No working (only the answer written) earns no method marks, like a CBSE examiner.
    """
    methodMarks = maxMarks - 1
    minSteps = 1 if maxMarks <= 2 else 2
    judged = [step for step in steps if step.verdict in (CORRECT, INCORRECT) and not step.isQuestionCopy]
    # Any real working line counts as working, even one SymPy could not check (e.g. the ± formula).
    hasWorking = any(
        not step.isAnswerLine
        and not step.isQuestionCopy
        and step.verdict not in (UNREADABLE, NOTE)  # copying the given values is not a method
        and step.hasMaths
        for step in steps
    )
    methodScore = 0.0
    if judged and hasWorking:
        correctBeforeMistake = 0
        for step in judged:
            if step.verdict == INCORRECT:
                break
            correctBeforeMistake += 1
        share = correctBeforeMistake / len(judged) * min(1.0, len(judged) / minSteps)
        methodScore = math.floor(methodMarks * share * 2) / 2  # marks move in steps of 0.5
    answerScore = 1.0 if isAnswerCorrect and findFirstWrongLine(steps) is None else 0.0
    return min(float(maxMarks), methodScore + answerScore)


# ---------- what exactly is wrong (facts for the tutor) ----------


def describeMistake(previousLatex: str, wrongLatex: str) -> tuple[str, str] | None:
    """Compare a wrong line with the line before it, term by term: (kind of mistake, the facts).
    None when that is not simple. The kind is what Progress counts as a recurring mistake."""
    try:
        previous, wrong = parseLatex(previousLatex), parseLatex(wrongLatex)
    except LatexParseError:
        return None
    symbols = getFreeSymbols(previous) | getFreeSymbols(wrong)
    if isinstance(wrong, sympy.Eq) and not wrong.free_symbols:
        written = wrongLatex.split("=")[0].strip()  # as the student wrote it ('6 \cdot 4'), not SymPy's '24'
        return (
            "calculation slip",
            f"${written}$ is ${sympy.latex(sympy.simplify(wrong.lhs))}$, not ${sympy.latex(wrong.rhs)}$.",
        )
    if len(symbols) != 1:
        return None
    variable = symbols.pop()
    single = describeWholeValues(previous, wrong)
    if single:
        return single
    previousSide = sympy.expand(previous.lhs - previous.rhs if isinstance(previous, sympy.Eq) else previous)
    wrongSide = sympy.expand(wrong.lhs - wrong.rhs if isinstance(wrong, sympy.Eq) else wrong)
    if isinstance(previous, sympy.Eq) and isinstance(wrong, sympy.Eq):
        linear = describeLinearMistake(previousSide, wrongSide, variable)
        if linear:
            return "moving terms across the = sign", linear
    try:
        if isinstance(previous, sympy.Eq) and isinstance(wrong, sympy.Eq):
            wrongLead = sympy.Poly(wrongSide, variable).LC()
            if wrongLead != 0:  # '2x = 6' and 'x = 3' are the same: scale before comparing
                wrongSide = sympy.expand(wrongSide * sympy.Poly(previousSide, variable).LC() / wrongLead)
        previousPoly, wrongPoly = sympy.Poly(previousSide, variable), sympy.Poly(wrongSide, variable)
    except (sympy.PolynomialError, sympy.GeneratorsNeeded, ValueError):
        return None
    differences = []
    onlySignsFlipped = True  # every wrong term is the right one with its sign flipped: a term moved across '='
    prevDegree = int(max(previousPoly.degree(), 0))
    wrongDegree = int(max(wrongPoly.degree(), 0))
    for power in range(max(prevDegree, wrongDegree), -1, -1):
        expected = previousPoly.coeff_monomial(variable**power)
        written = wrongPoly.coeff_monomial(variable**power)
        if sympy.simplify(expected - written) != 0:
            name = "number term" if power == 0 else f"{variable} term" if power == 1 else f"{variable}^{power} term"
            differences.append(f"the {name} should be {expected}, the line gives {written}")
            onlySignsFlipped = onlySignsFlipped and sympy.simplify(expected + written) == 0
    if not differences:
        return None
    kind = "moving terms across the = sign" if onlySignsFlipped else "simplifying or collecting terms"
    return kind, "In this line " + "; ".join(differences) + "."


def describeWholeValues(previous: Parsed, wrong: Parsed) -> tuple[str, str] | None:
    """'x^3 x^4' then 'x^{12}': 'the line before equals x^7, this line equals x^12'. A product like '3x(2x + 9)'
    is multiplied back out instead ('gives 6x^2 + 27x, not 6x^2 + 9x') — that never gives the answer away."""
    if isinstance(previous, sympy.Eq) or isinstance(wrong, sympy.Eq):
        return None
    if isinstance(wrong, sympy.Mul | sympy.Pow) and wrong.has(sympy.Add):
        return "factorising or expanding", (
            f"Multiply this line back out: it gives ${sympy.latex(sympy.expand(wrong))}$, "
            f"but the line before is ${sympy.latex(sympy.expand(previous))}$ — so the factors are not right."
        )
    before, after = sympy.simplify(previous), sympy.simplify(wrong)
    if isinstance(before, sympy.Add) or isinstance(after, sympy.Add):
        return None
    return "simplifying or collecting terms", (
        f"The line before equals ${sympy.latex(before)}$, but this line equals ${sympy.latex(after)}$ — they are not the same."
    )


def describeLinearMistake(previousSide: sympy.Expr, wrongSide: sympy.Expr, variable: sympy.Symbol) -> str | None:
    """For 'ax + b = 0' equations, say it like a teacher: 'the line before gives 3x = 15, this line gives 3x = 29'."""
    try:
        previousPoly, wrongPoly = sympy.Poly(previousSide, variable), sympy.Poly(wrongSide, variable)
    except (sympy.PolynomialError, sympy.GeneratorsNeeded):
        return None
    if previousPoly.degree() != 1 or wrongPoly.degree() != 1:
        return None
    coefficient = previousPoly.coeff_monomial(variable)
    expected = -previousPoly.coeff_monomial(1)
    written = -wrongPoly.coeff_monomial(1) * coefficient / wrongPoly.coeff_monomial(variable)
    if sympy.simplify(expected - written) == 0:
        return None  # the line follows from the one before: the mistake is elsewhere (e.g. the final answer)
    term = sympy.latex(coefficient * variable)
    return (
        f"Moving the numbers to one side, the line before gives ${term} = {sympy.latex(expected)}$, "
        f"but this line gives ${term} = {sympy.latex(written)}$."
    )


# ---------- checking a short answer (tutor quick check) ----------


def isSameAnswer(givenText: str, expectedLatex: str) -> bool | None:
    """Does the student's answer match? Accepts '5', 'x = 5' and chains like 'x = 10 - 5 = 5'.

    None when nothing in the answer can be read as maths.
    """
    if not re.search(r"\d|=", givenText):
        return None  # words like 'pata nahi' are not an answer
    try:
        expected = parseLatex(expectedLatex)
    except LatexParseError:
        return None
    parts = [part.strip() for part in givenText.split("=") if part.strip()]
    candidates = [givenText] + ([f"{parts[0]} = {parts[-1]}", parts[-1]] if len(parts) > 2 else [])
    readable = []
    for candidate in candidates:
        try:
            readable.append(parseLatex(candidate))
        except LatexParseError:
            continue
    if not readable:
        return None
    for given in readable:
        if isinstance(given, sympy.Eq) and isinstance(expected, sympy.Eq):
            matches: bool | None = areEquationsProportional(given, expected)
        else:
            givenSide = given.rhs if isinstance(given, sympy.Eq) else given
            expectedSide = expected.rhs if isinstance(expected, sympy.Eq) else expected
            matches = areExpressionsEquivalent(givenSide, expectedSide)
        if matches:
            return True
    return False


# ---------- why a final answer is wrong ----------


def readFinalValue(line: str) -> sympy.Expr | None:
    """The number a final line states: '970', 'S = 970', '= 970', and chains like 'AB = \\sqrt{0} = 0'.
    None when the line does not end on a single number."""
    parts = [part for part in line.split("=") if part.strip()]
    candidates = [line] + ([parts[-1]] if len(parts) > 1 else [])
    for candidate in candidates:
        try:
            parsed = parseLatex(candidate)
        except LatexParseError:
            continue
        value = parsed.rhs if isinstance(parsed, sympy.Eq) else parsed
        if isinstance(value, sympy.Expr) and value.is_number:
            return sympy.nsimplify(value)
    return None


def hideCheckLines(answer: dict[str, Any], lines: list[str]) -> list[str]:
    """Lines after the right answer that only check it ('Check: 5(5) - 4 = 21': a true sum with no unknown) are not
    a new final answer. They become '' for the final-answer questions, so line numbers stay the same. A true sum
    can never be a mistake; without this, '21' was compared with x = 5 and a right solution lost marks."""
    expected = numericAnswerValue(answer)
    if expected is None:
        return lines
    values = readLineValues(lines)
    reached = [index for index, value in enumerate(values) if value is not None and isMatchingValue(value, expected)]
    if not reached:
        return lines
    shown = list(lines)
    for index in range(len(lines) - 1, reached[0], -1):
        if not shown[index].strip() or not re.search(r"\d|=", normalizeLatex(shown[index])):
            continue  # a word line ('Hence verified') changes nothing
        if not (isTrueNumberStatement(shown[index]) or CHECK_SIDE_NAME.match(shown[index])):
            break
        shown[index] = ""
    return shown


CHECK_SIDE_NAME = re.compile(r"^\s*(\\text\{\s*)?(check\W*)?[LR]\.?\s*H\.?\s*S\.?\s*(\}\s*)?=", re.IGNORECASE)  # 'LHS = ...', 'R.H.S. = ...'


def isTrueNumberStatement(latex: str) -> bool:
    """'5(5) - 4 = 21': both sides are numbers, there is working on the left, and the two sides are equal."""
    try:
        parsed = parseLatex(prepareLine(latex))
    except LatexParseError:
        return False
    if not isinstance(parsed, sympy.Eq) or parsed.free_symbols:
        return False
    left = normalizeLatex(prepareLine(latex)).split("=")[0]
    if re.fullmatch(r"\s*-?[\d.]+\s*", left):
        return False  # '21 = 21' or a bare value: no working to check, so it is an answer, not a check
    try:
        return bool(sympy.simplify(parsed.lhs - parsed.rhs) == 0)
    except MATHS_ERRORS:
        return False


def isWrongFinalAnswer(answer: dict[str, Any], lines: list[str]) -> bool:
    """The last line states a final answer that is provably different from the verified answer."""
    if not lines or isFinalAnswerCorrect(answer, lines):
        return False
    if numericAnswerValue(answer) is not None:
        return lastStatedValue(lines) is not None
    if answer["type"] == "expression":
        try:
            final, expected = parseLatex(lines[-1]), parseLatex(answer["latex"])
        except LatexParseError:
            return False
        final = final.rhs if isinstance(final, sympy.Eq) else final
        return isinstance(expected, sympy.Expr) and areExpressionsEquivalent(final, expected) is False  # not just the form
    if answer["type"] in ("solution_set", "point"):
        # Wrong only if a stated value contradicts the answer; a missing value is incomplete, not wrong.
        try:
            expected = (
                {answer["variable"]: answer["values"]}
                if answer["type"] == "solution_set"
                else {name: [value] for name, value in answer["values"].items()}
            )
            given = readFinalAssignments(lines) if answer["type"] == "solution_set" else readStatedValues(lines)
            return any(
                name not in expected
                or not any(areExpressionsEquivalent(value, readValue(right)) for right in expected[name])
                for name, values in given.items()
                for value in values
            )
        except LatexParseError:
            return False
    return False


def describeWrongAnswer(
    questionExpressions: list[str], answer: dict[str, Any], lines: list[str], traps: list[dict[str, str]]
) -> tuple[str, str] | None:
    """Why the student's final answer is wrong, without giving the right one: (kind of mistake, the facts).
    Equations: substitute their values back. Numbers: match a known misconception for this question."""
    if answer["type"] == "expression":
        value = readFinalValue(lines[-1])
        expected = numericAnswerValue(answer)
        if value is None or (expected is not None and isMatchingValue(value, expected)):
            return None
        for trap in traps:
            if areExpressionsEquivalent(value, readValue(trap["value"])):
                return trap["mistake"], f"Your answer ${sympy.latex(value)}$ is what you get if you {trap['mistake']}."
        return (
            "wrong final answer",
            f"Your final answer ${sympy.latex(value)}$ is not right. Go back over the formula and each calculation, one line at a time.",
        )
    given = readFinalAssignments(lines)
    equations = []
    for expression in questionExpressions:
        try:
            parsed = parseLatex(expression)
        except LatexParseError:
            continue
        if isinstance(parsed, sympy.Eq):
            equations.append(parsed)
    for name, values in given.items():
        symbol = sympy.Symbol(name)
        for value in values:
            for index, equation in enumerate(equations, start=1):
                substituted = (equation.lhs - equation.rhs).subs(symbol, value)
                others = sorted(substituted.free_symbols, key=str)
                if not others:
                    if sympy.simplify(substituted) != 0:
                        left = sympy.latex(sympy.nsimplify(equation.lhs.subs(symbol, value)))
                        return (
                            "answer does not fit the equations",
                            f"Put ${name} = {sympy.latex(value)}$ in ${sympy.latex(equation)}$: the left side becomes ${left}$, not ${sympy.latex(equation.rhs)}$.",
                        )
                    continue
                if len(others) == 1 and len(equations) > 1:
                    # Two unknowns: their value fixes the other unknown in this equation — does the other equation still hold?
                    otherValues = sympy.solve(substituted, others[0])
                    for checkEquation in equations:
                        if checkEquation is equation or not otherValues:
                            continue
                        result = sympy.nsimplify((checkEquation.lhs).subs({symbol: value, others[0]: otherValues[0]}))
                        if sympy.simplify(result - checkEquation.rhs) != 0:
                            return "answer does not fit the equations", (
                                f"With ${name} = {sympy.latex(value)}$, equation ({index}) gives ${others[0]} = {sympy.latex(otherValues[0])}$, "
                                f"but then the other equation gives ${sympy.latex(result)}$ instead of ${sympy.latex(checkEquation.rhs)}$ — "
                                f"so ${name} = {sympy.latex(value)}$ does not satisfy both equations."
                            )
    return None


# ---------- numeric answers: compare every line's value with the verified answer ----------
# Like a teacher with the answer key: a line whose value is already the final (wrong) value is where the
# mistake entered — every line after it only simplifies it. Proven by SymPy, so it may be marked wrong.


def isParseable(latex: str) -> bool:
    try:
        parseLatex(latex)
    except LatexParseError:
        return False
    return True


def numericAnswerValue(answer: dict[str, Any]) -> sympy.Expr | None:
    """The answer when it is one number (an area, a distance, an amount, the one root x = 70), else None."""
    if answer.get("type") == "solution_set" and len(answer.get("values") or []) == 1:
        try:
            return sympy.nsimplify(readValue(str(answer["values"][0])))
        except (LatexParseError, *MATHS_ERRORS):
            return None
    if answer.get("type") != "expression":
        return None
    try:
        parsed = parseLatex(str(answer["latex"]))
    except LatexParseError:
        return None
    if isinstance(parsed, sympy.Expr) and parsed.is_number:
        return sympy.nsimplify(parsed)
    return None


def isMatchingValue(given: sympy.Expr, expected: sympy.Expr) -> bool:
    """Same value, pi written as 22/7 or 3.14, or the exact value rounded to 1-4 decimals (18.86 for 132/7)."""
    try:
        if areExpressionsEquivalent(given, expected) or isPiApproximation(given, expected):
            return True
        givenNumber, expectedNumber = float(given), float(expected)
    except MATHS_ERRORS:
        return False
    for decimals in range(1, 5):
        rounded = round(expectedNumber, decimals)
        truncated = math.trunc(expectedNumber * 10**decimals) / 10**decimals  # 44/7 = 6.2857... written as 6.28
        closeEnough = abs(givenNumber - expectedNumber) < 10**-decimals
        if closeEnough and (abs(givenNumber - rounded) < 1e-9 or abs(givenNumber - truncated) < 1e-9):
            return True
    return False


def readLineValues(lines: list[str], questionSymbols: set[sympy.Symbol] | None = None) -> list[sympy.Expr | None]:
    """The number each line states, or None: '4 - 2 = 2' -> 2, 'Area = 2 \\times 22/7' -> 44/7.
    Given values ('x_1 = 2', 'r = 6') are put into later lines, so 'd = \\sqrt{(x_2 - x_1)^2}' has a value too."""
    questionSymbols = questionSymbols or set()
    given: dict[sympy.Symbol, sympy.Expr] = {}
    values: list[sympy.Expr | None] = []
    for latex in lines:
        value = None
        try:
            parsed = substitute(parseLatex(prepareLine(latex)), given)
            found = readGivenValue(parsed, questionSymbols)
            if found:
                given[found[0]] = found[1]  # 'r = 6' is used by later lines; 'd = 0' is also a stated value
            if isinstance(parsed, sympy.Eq):
                named = isinstance(parsed.lhs, sympy.Symbol) or parsed.lhs.is_number
                value = sympy.nsimplify(parsed.rhs) if named and parsed.rhs.is_number else None
                solutions = getSolutionSet(parsed) if value is None else None
                if isinstance(solutions, sympy.FiniteSet) and len(solutions) == 1:
                    value = sympy.nsimplify(next(iter(solutions)))  # '110 + x = 360' states x = 250
            elif parsed.is_number:
                value = sympy.nsimplify(parsed)
        except (LatexParseError, *MATHS_ERRORS):
            value = None
        values.append(value if value is None or value.is_finite else None)
    return values


def findLastValueLine(lines: list[str]) -> int | None:
    """1-based number of the line that states the final value, or None when it is not known.
    Word lines at the end ('Hence proved') are skipped, but a maths line we cannot read ends the search:
    then the real final answer is unknown, and a given like 'y_2 = 1' above it must never be taken for it."""
    values = readLineValues(lines)
    for index in range(len(lines) - 1, -1, -1):
        if values[index] is not None:
            return index + 1
        if re.search(r"\d|=", normalizeLatex(lines[index])) and not restatesValueAbove(lines[index], values[:index]):
            return None
    return None


def findLastMathsLine(lines: list[str]) -> int | None:
    """1-based number of the last line with maths on it (a number or '='), word lines like 'Hence proved' skipped."""
    for index in range(len(lines) - 1, -1, -1):
        if re.search(r"\d|=", normalizeLatex(lines[index])):
            return index + 1
    return None


def restatesValueAbove(latex: str, valuesAbove: list[sympy.Expr | None]) -> bool:
    """An unreadable last line that only repeats the value above ('Ans: 44/7 cm^2 (approx 6.28)') hides nothing:
    all the numbers of that value (44 and 7), or a rounded decimal of it, are in the line."""
    previous = next((value for value in reversed(valuesAbove) if value is not None), None)
    if previous is None:
        return False
    numbers = NUMBER_TEXT.findall(latex)
    if previous.is_rational:
        rational = sympy.Rational(previous)
        parts = {str(abs(rational.p))} | ({str(rational.q)} if rational.q != 1 else set())
        if parts <= set(numbers):
            return True
    return any(isMatchingValue(sympy.Rational(number), previous) for number in numbers if "." in number)


def isAnswerInLastWords(lines: list[str], expected: sympy.Expr) -> bool:
    """'Ans: Third angle is 70°', 'Ans: 16th term is 78': a final sentence we cannot parse still earns the answer
    mark when it names the right value. Only ever used to GIVE the mark, never to take one away."""
    for line in lines[-2:]:
        for number in NUMBER_TEXT.findall(re.sub(r"(?<=\d),(?=\d{2,3}\b)", "", line)):
            if isMatchingValue(sympy.nsimplify(sympy.Rational(number)), expected):
                return True
    return False


def lastStatedValue(lines: list[str]) -> sympy.Expr | None:
    """The final number the working states, or None when it is not known."""
    line = findLastValueLine(lines)
    return readLineValues(lines)[line - 1] if line else None


def findWrongValueLine(answer: dict[str, Any], lines: list[str]) -> int | None:
    """The line where a wrong final value FIRST appears (1-based), or None when the answer is right / not a number.
    Walk back from the final value over lines with the same value; a line with a different value ends the run."""
    expected = numericAnswerValue(answer)
    values = readLineValues(lines)
    stated = [index for index, value in enumerate(values) if value is not None]
    if expected is None or not stated:
        return None
    last = stated[-1]
    wrongValue = values[last]
    assert wrongValue is not None
    if isMatchingValue(wrongValue, expected):
        return None
    root = last
    for index in reversed(stated[:-1]):
        value = values[index]
        assert value is not None
        if not (isMatchingValue(value, wrongValue) or isMatchingValue(wrongValue, value)):  # 44/7 then 6.28
            break
        root = index
    return root + 1


def splitTopLevelTerms(latex: str) -> list[str]:
    """'\\frac{1}{6} \\times \\frac{792}{7}' -> ['\\frac{1}{6}', '\\frac{792}{7}']: pieces joined by ×, ·, *, + or −
    outside any bracket. Each piece is a value the reference solution passes through."""
    pieces, depth, start, index = [], 0, 0, 0
    operator = re.compile(r"\\times|\\cdot|\*|\+|(?<=[\w)}\]])\s*-")
    while index < len(latex):
        character = latex[index]
        if character in "({[":
            depth += 1
        elif character in ")}]":
            depth -= 1
        elif depth == 0:
            match = operator.match(latex, index)
            if match:
                pieces.append(latex[start:index])
                start = index = match.end()
                continue
        index += 1
    pieces.append(latex[start:])
    return [piece.strip() for piece in pieces if piece.strip()]


def readReferenceValues(solutionSteps: list[dict[str, Any]], questionText: str) -> list[sympy.Expr]:
    """The values the verified solution passes through — the answer key a teacher marks against: every '= ...' part
    of every step and every term of it ('\\frac{1}{6} \\times \\frac{792}{7}' gives 132/7 and 792/7).
    Givens from the question, π's value and small numbers (integers up to 10, fractions like 1/6) are left out:
    matching those would be a coincidence, not proof."""
    givens = readNumbers(questionText)
    found: list[sympy.Expr] = []
    for step in solutionSteps:
        for group in re.split(r"\\qquad|\\quad|,|;", str(step.get("latex") or "")):
            for part in group.split("="):
                for text in [part, *splitTopLevelTerms(part)]:
                    try:
                        parsed = parseLatex(text)
                    except (LatexParseError, *MATHS_ERRORS):
                        continue
                    if not isinstance(parsed, sympy.Expr) or not parsed.is_number:
                        continue
                    value = sympy.nsimplify(parsed)
                    if isCoincidenceProne(value, givens) or any(value == other for other in found):
                        continue
                    found.append(value)
    return found


def markCarriedLines(
    steps: list[Step], answer: dict[str, Any], lines: list[str], referenceValues: list[sympy.Expr] | None = None
) -> list[Step]:
    """After the first mistake, a line that only follows from it must not get a ✓ (the student would think the
    working is fine): it becomes CARRIED. A later line that is back on the answer key's path keeps its ✓."""
    wrongLine = findFirstWrongLine(steps)
    if wrongLine is None:
        return steps
    expected = numericAnswerValue(answer)
    path = [*(referenceValues or []), *([expected] if expected is not None else [])]
    values = readLineValues(lines)
    marked = []
    for step in steps:
        value = values[step.lineNo - 1] if step.lineNo - 1 < len(values) else None
        onPath = value is not None and any(isMatchingValue(value, reference) for reference in path)
        if step.lineNo > wrongLine and step.verdict == CORRECT and not onPath:
            step = Step(step.lineNo, CARRIED, step.isQuestionCopy, step.isAnswerLine)
        marked.append(step)
    return marked


def isCoincidenceProne(value: sympy.Expr, givens: set[str]) -> bool:
    if str(value) in givens or value in (sympy.Rational(22, 7), sympy.Rational(314, 100)):
        return True
    if value.is_rational:
        rational = sympy.Rational(value)
        return bool(abs(rational.p) <= 10 and rational.q <= 10)  # 3, 1/6, -2/5: too common to prove anything
    return False


def markValueLines(
    steps: list[Step], answer: dict[str, Any], lines: list[str], referenceValues: list[sympy.Expr] | None = None
) -> list[Step]:
    """A line SymPy could not compare (nothing before it) is still right when its value IS the verified answer,
    or a value the verified solution passes through on the way (teacher with the answer key)."""
    expected = numericAnswerValue(answer)
    pointValues = readPointValues(answer)
    if expected is None and not referenceValues and not pointValues:
        return steps
    values = readLineValues(lines)
    marked = []
    for step in steps:
        value = values[step.lineNo - 1] if step.lineNo - 1 < len(values) else None
        if step.verdict == UNVERIFIABLE and value is not None and statesPointValue(lines[step.lineNo - 1], value, pointValues):
            marked.append(Step(step.lineNo, CORRECT, step.isQuestionCopy, step.isAnswerLine))
            continue  # 'x = (2 + 6)/2' when the answer is the point (4, 6): the x of the answer key
        onPath = value is not None and any(isMatchingValue(value, reference) for reference in referenceValues or [])
        if step.verdict == UNVERIFIABLE and onPath:
            marked.append(Step(step.lineNo, CORRECT, step.isQuestionCopy, step.isAnswerLine))
            continue
        if expected is None:
            marked.append(step)
            continue
        # Only a line that states the ASKED value ('Area = ...', '= 132/7', 'x = 70'): an in-between 's = 24' that
        # happens to equal the answer is not proof of anything.
        if step.verdict == UNVERIFIABLE and value is not None and isMatchingValue(value, expected) and statesAnswer(lines[step.lineNo - 1], answer):
            step = Step(step.lineNo, CORRECT, step.isQuestionCopy, step.isAnswerLine)
        marked.append(step)
    return marked


def readPointValues(answer: dict[str, Any]) -> dict[str, sympy.Expr]:
    if answer.get("type") != "point":
        return {}
    try:
        return {name: sympy.nsimplify(readValue(str(value))) for name, value in answer["values"].items()}
    except (LatexParseError, *MATHS_ERRORS):
        return {}


def statesPointValue(latex: str, value: sympy.Expr, pointValues: dict[str, sympy.Expr]) -> bool:
    """'x = (2 + 6)/2' states the x of the answer point when its value is that x."""
    try:
        parsed = parseLatex(prepareLine(latex))
    except LatexParseError:
        return False
    if not isinstance(parsed, sympy.Eq) or not isinstance(parsed.lhs, sympy.Symbol):
        return False
    expected = pointValues.get(str(parsed.lhs))
    return expected is not None and isMatchingValue(value, expected)


def statesAnswer(latex: str, answer: dict[str, Any]) -> bool:
    try:
        parsed = parseLatex(prepareLine(latex))
    except LatexParseError:
        return False
    if not isinstance(parsed, sympy.Eq):
        return True  # '= 132/7', 'Area = 132/7' (the asked quantity's name is dropped by the parser)
    if answer.get("type") == "solution_set":
        return str(parsed.lhs) == answer.get("variable")
    # 'S_{20} = 990', 'a_{15} = 74': a named result. A small number (s = 6) could match by chance, so not those.
    value = parsed.rhs
    return isinstance(parsed.lhs, sympy.Symbol) and bool(value.is_number) and not (value.is_integer and abs(value) <= 10)


def describeWrongValue(
    answer: dict[str, Any], value: sympy.Expr | None, laterLines: int, traps: list[dict[str, str]]
) -> tuple[str, str] | None:
    """Why the line where the wrong value starts is wrong, without giving the answer: a known trap for this
    question's numbers ('used the arc length formula instead of the area'), else the plain proven fact."""
    if value is None or numericAnswerValue(answer) is None:
        return None
    for trap in traps:
        try:
            if isMatchingValue(value, readValue(trap["value"])):
                return trap["mistake"], (
                    f"This line works out to ${sympy.latex(value)}$ — that is exactly what you get if you {trap['mistake']}. "
                    "Fix this one idea and the rest of your working will follow."
                )
        except (LatexParseError, *MATHS_ERRORS):
            continue
    after = " The lines after it are calculated correctly — they just carry this value forward." if laterLines else ""
    return (
        "wrong formula or values",
        f"Your answer goes wrong here: this line gives ${sympy.latex(value)}$, which is not what this question needs."
        f"{after} Check two things in this line: is the formula right, and did each number go in the right place?",
    )


# ---------- working that belongs to a different question ----------

PI_VALUES = re.compile(r"\\frac\{22\}\{7\}|22\s*/\s*7|3\.14")
QUESTION_NUMBER = re.compile(r"^\s*(?:Q\.?|Question)\s*\d+[.):]?\s*", re.IGNORECASE)
NUMBER_TEXT = re.compile(r"\d+(?:\.\d+)?")


def readNumbers(text: str) -> set[str]:
    return {match.lstrip("0") or "0" for match in NUMBER_TEXT.findall(PI_VALUES.sub(" ", text))}


def findOtherQuestion(questionText: str, questionExpressions: list[str], answer: dict[str, Any], lines: list[str]) -> str | None:
    """Facts when the working provably solves a DIFFERENT question, else None. Only used when the answer is wrong.
    1. a pair of equations: none of the student's equations holds at the verified solution, and their first two
       are not a multiple of the question's (a multiplied equation would be their own mistake, not another question)
    2. a word problem: the question gives 2+ numbers and the working uses none of them."""
    knownPoint = getKnownPoint(answer)
    equations = []
    for line in lines:
        try:
            parsed = parseLatex(prepareLine(line))
        except LatexParseError:
            continue
        if isinstance(parsed, sympy.Eq) and len(getFreeSymbols(parsed)) == 2:
            equations.append((line, parsed))
    if knownPoint and len(equations) >= 2:
        question = [parseLatex(expression) for expression in questionExpressions]
        holds = [isEquationTrueAt(parsed, knownPoint) for _, parsed in equations]
        related = any(
            isinstance(item, sympy.Eq) and haveProportionalUnknowns(parsed, item) for _, parsed in equations[:2] for item in question
        )
        if not any(holds) and not related:
            written = ", ".join(f"${normalizeLatex(line)}$" for line, _ in equations[:2])
            asked = ", ".join(f"${expression}$" for expression in questionExpressions)
            return f"This working starts from {written}, but the question is {asked}. Solve the equations that were asked."
    questionNumbers = readNumbers(QUESTION_NUMBER.sub("", questionText))
    workingNumbers = readNumbers(" ".join(lines))
    # The student's own 'r = 6', 'θ = 60': values they wrote down as given, none of which the question has.
    ownGivens = {number for line in lines if isLiteralValue(line) for number in readNumbers(line.split("=")[-1])}
    if (
        knownPoint is None
        and len(questionNumbers) >= 2
        and len(ownGivens - questionNumbers) >= 2
        and not questionNumbers & workingNumbers
    ):
        given = ", ".join(sorted(questionNumbers, key=float))
        used = ", ".join(sorted(ownGivens - questionNumbers, key=float))
        return (
            f"This working uses the values {used}, but the question gives {given} — none of the question's numbers "
            "is in the working. Solve the question that was asked."
        )
    return None


def haveProportionalUnknowns(first: sympy.Eq, second: sympy.Eq) -> bool:
    """'6x - 2y = 12' and '3x - y = 7' have the same x, y parts (×2): one came from the other."""
    symbols = sorted(getFreeSymbols(first) | getFreeSymbols(second), key=str)
    if len(symbols) != 2:
        return False
    firstSide, secondSide = sympy.expand(first.lhs - first.rhs), sympy.expand(second.lhs - second.rhs)
    firstCoefficients = [firstSide.coeff(symbol) for symbol in symbols]
    secondCoefficients = [secondSide.coeff(symbol) for symbol in symbols]
    if 0 in secondCoefficients:
        return firstCoefficients == secondCoefficients
    ratios = {sympy.nsimplify(a / b) for a, b in zip(firstCoefficients, secondCoefficients, strict=True)}
    return len(ratios) == 1 and 0 not in ratios


def describeScaledEquation(questionExpressions: list[str], earlierLines: list[str], wrongLatex: str) -> tuple[str, str] | None:
    """'6x - 2y = 12' after '3x - y = 7': the x, y parts were multiplied by 2 but the number side was not."""
    try:
        wrong = parseLatex(prepareLine(wrongLatex))
    except LatexParseError:
        return None
    if not isinstance(wrong, sympy.Eq) or len(getFreeSymbols(wrong)) != 2:
        return None
    sources = []
    for line in [*reversed(earlierLines), *questionExpressions]:
        try:
            parsed = parseLatex(prepareLine(line))
        except LatexParseError:
            continue
        if isinstance(parsed, sympy.Eq) and len(getFreeSymbols(parsed)) == 2:
            sources.append(parsed)
    for source in sources:
        if not haveProportionalUnknowns(wrong, source) or areEquationsProportional(wrong, source):
            continue
        symbols = sorted(getFreeSymbols(source), key=str)
        sourceSide, wrongSide = sympy.expand(source.lhs - source.rhs), sympy.expand(wrong.lhs - wrong.rhs)
        factor = sympy.nsimplify(wrongSide.coeff(symbols[0]) / sourceSide.coeff(symbols[0]))
        unknownPart = sympy.expand(factor * (source.lhs - source.rhs - sourceSide.subs({symbol: 0 for symbol in symbols})))
        expected = sympy.expand(-factor * sourceSide.subs({symbol: 0 for symbol in symbols}))
        written = -wrongSide.subs({symbol: 0 for symbol in symbols})
        if factor == 1:
            return "simplifying or collecting terms", (
                f"From ${sympy.latex(source)}$ the number side should stay ${sympy.latex(expected)}$, but this line has ${sympy.latex(written)}$."
            )
        return "multiplying an equation", (
            f"You multiplied ${sympy.latex(source)}$ by ${sympy.latex(factor)}$: the left side became ${sympy.latex(unknownPart)}$, "
            f"so the right side must also be multiplied — it should be ${sympy.latex(expected)}$, not ${sympy.latex(written)}$."
        )
    return None


# ---------- substitution that only happens to give the right value ----------
# '2 tan²45° + cos²30° − sin²60°' written as '2(1) + √3/2 − √3/2' is 2 — the right value — yet the squares are gone:
# cos 30° and sin 60° are equal, so the mistake cancels. Values alone cannot see it; the structure can. Each special
# value of the question becomes a symbol (2A² + B² − C²) and the student's numbers are read as those symbols, left to
# right (2A + B − C). Wrong ONLY when no reading of their numbers fits the question's structure.

TRIG_CALL = re.compile(r"\{\\(sin|cos|tan|cot|sec|csc)(?:\^\{(\d+)\})?\(([^()]*)\)\}")
VALUE_TOKEN = re.compile(
    r"\\frac\{\\sqrt\{\d+\}\}\{\d+\}|\\frac\{\d+\}\{\\sqrt\{\d+\}\}|\\frac\{\d+\}\{\d+\}|\\sqrt\{\d+\}\s*/\s*\d+"
    r"|\d+\s*/\s*\\sqrt\{\d+\}|\\sqrt\{\d+\}|\d+\s*/\s*\d+|\d+(?:\.\d+)?"
)
MAX_READINGS = 400


def readQuestionStructure(expression: str) -> tuple[sympy.Expr, list[sympy.Expr], list[int]] | None:
    """('2A^2 + B^2 - C^2', [1, √3/2, √3/2], [2, 2, 2]) for a question with trig values, else None."""
    from app.maths.parser import parseExpression

    text = normalizeLatex(expression)
    calls = list(TRIG_CALL.finditer(text))
    if not calls or "=" in text:
        return None
    values, powers, pieces, last = [], [], [], 0
    for index, call in enumerate(calls):
        value = parseExpression(f"\\{call.group(1)}({call.group(3)})")
        if not isinstance(value, sympy.Expr) or not value.is_number:
            return None
        values.append(sympy.nsimplify(value))
        powers.append(int(call.group(2) or 1))
        pieces.append(text[last : call.start()] + f"(T_{{{index}}})^{{{call.group(2) or 1}}}")
        last = call.end()
    structure = parseExpression("".join(pieces) + text[last:])
    return (structure, values, powers) if isinstance(structure, sympy.Expr) else None


def readValueReadings(text: str, values: list[sympy.Expr]) -> list[str]:
    """Every way to read the line's numbers, left to right, as the question's values (T_0, T_1, ...)."""
    from app.maths.parser import parseExpression

    tokens = []
    for match in VALUE_TOKEN.finditer(text):
        try:
            tokens.append((match.start(), match.end(), sympy.nsimplify(parseExpression(match.group(0)))))
        except (LatexParseError, *MATHS_ERRORS):
            continue
    readings: list[str] = []

    def place(valueIndex: int, tokenIndex: int, spans: list[tuple[int, int, int]]) -> None:
        if len(readings) >= MAX_READINGS:
            return
        if valueIndex == len(values):
            rebuilt, last = "", 0
            for start, end, symbol in spans:
                rebuilt += text[last:start] + f"(T_{{{symbol}}})"
                last = end
            readings.append(rebuilt + text[last:])
            return
        for index in range(tokenIndex, len(tokens)):
            start, end, value = tokens[index]
            if value == values[valueIndex]:
                place(valueIndex + 1, index + 1, [*spans, (start, end, valueIndex)])

    place(0, 0, [])
    return readings


def findStructureSlip(questionExpressions: list[str], latex: str) -> str | None:
    """The facts when a line has the question's VALUE but not its structure (a power or a term lost on the way),
    else None. None also whenever it cannot be decided — this never accuses on a doubt."""
    from app.maths.parser import parseExpression

    lawSlip = findExponentLawSlip(questionExpressions, latex)
    if lawSlip:
        return lawSlip

    line = normalizeLatex(latex).split("=")[-1].strip()
    if not line or TRIG_PATTERN_IN_LINE.search(line):
        return None
    for expression in questionExpressions:
        try:
            found = readQuestionStructure(expression)
        except (LatexParseError, *MATHS_ERRORS):
            continue
        if found is None:
            continue
        structure, values, powers = found
        readings = readValueReadings(line, values)
        if not readings:
            continue  # their numbers are not the values (e.g. squares already worked out): nothing to say
        for reading in readings:
            try:
                written = parseExpression(reading)
                if isinstance(written, sympy.Expr) and sympy.simplify(written - structure) == 0:
                    return None  # one reading fits the question exactly
            except (LatexParseError, *MATHS_ERRORS):
                return None
        squared = [index for index, power in enumerate(powers) if power > 1]
        if squared:
            return (
                "The question has squares (like $\\tan^2 45^\\circ$): each value must be squared before it is added, "
                "but this line uses the values without their squares. The answer only came out right because two "
                "terms cancel — the working is not right."
            )
        return "This line does not follow the question's expression: put each value exactly where the question has it."
    return None


TRIG_PATTERN_IN_LINE = re.compile(r"\\(sin|cos|tan|cot|sec|csc)(?![a-zA-Z])")


# ---------- exponent laws that only happen to give the right value ----------
# '3^2 × 3^2' written as '3^{2 × 2}' is 3^4 — right value, wrong law (2 + 2 = 2 × 2 = 4). The law is visible in the
# exponent the student wrote: the question's own two exponents joined by the wrong operation.

POWER = r"([A-Za-z]|\d+)\s*\^\s*\{?\s*(\d+)\s*\}?"
PRODUCT_OF_POWERS = re.compile(POWER + r"\s*(?:\\cdot|\*)\s*" + POWER)
QUOTIENT_OF_POWERS = re.compile(POWER + r"\s*(?:\\cdot\s*)?(?:\\div|/)\s*" + POWER)
POWER_OF_POWER = re.compile(r"\(\s*" + POWER + r"\s*\)\s*\^\s*\{?\s*(\d+)\s*\}?")
WRITTEN_EXPONENT = re.compile(r"([A-Za-z]|\d+)\s*\^\s*\{\s*(\d+)\s*(\\cdot|\*|\+|-|/|\\div)\s*(\d+)\s*\}")
LAWS = {
    "product": ("+", "multiplied the powers: with the same base, powers are ADDED ($a^m \\times a^n = a^{m+n}$)"),
    "quotient": ("-", "divided the powers: with the same base, powers are SUBTRACTED ($a^m \\div a^n = a^{m-n}$)"),
    "power": ("*", "added the powers: a power of a power MULTIPLIES them ($(a^m)^n = a^{mn}$)"),
}
OPERATIONS = {"\\cdot": "*", "*": "*", "+": "+", "-": "-", "/": "/", "\\div": "/"}


def findExponentLawSlip(questionExpressions: list[str], latex: str) -> str | None:
    """The facts when a line joins the question's two exponents with the wrong operation, else None."""
    written = WRITTEN_EXPONENT.search(normalizeLatex(latex).split("=")[-1])
    if not written:
        return None
    base, first, operation, second = written.group(1), written.group(2), OPERATIONS[written.group(3)], written.group(4)
    for expression in questionExpressions:
        text = normalizeLatex(expression)
        found = [
            ("product", PRODUCT_OF_POWERS.search(text)),
            ("quotient", QUOTIENT_OF_POWERS.search(text)),
            ("power", POWER_OF_POWER.search(text)),
        ]
        for law, match in found:
            if not match:
                continue
            if law == "power":
                questionBase, exponents = match.group(1), (match.group(2), match.group(3))
            elif match.group(1) == match.group(3):
                questionBase, exponents = match.group(1), (match.group(2), match.group(4))
            else:
                continue
            rightOperation, mistake = LAWS[law]
            if questionBase == base and (first, second) == exponents and operation != rightOperation:
                return f"You {mistake}. This line happens to give the same number here, but the law used is wrong."
    return None


# ---------- the mistake in numbers: what 'Understand the mistake' shows, every number computed here ----------

TEST_POINTS = [2, 3, 5, -1]


def formatApprox(value: sympy.Expr) -> str | None:
    """'132/7' -> '18.86'; None for a whole number (nothing to approximate)."""
    try:
        number = float(value)
    except MATHS_ERRORS:
        return None
    if number == int(number):
        return None
    return f"{number:.3g}" if abs(number) < 1 else f"{number:.2f}"  # 1/8 -> 0.125, 132/7 -> 18.86


def findSimpleRatio(given: sympy.Expr, expected: sympy.Expr) -> sympy.Rational | None:
    """'Yours is exactly 1/3 of the right one': a small fraction or whole number tells which factor went wrong."""
    try:
        ratio = sympy.nsimplify(given / expected)
    except MATHS_ERRORS:
        return None
    if isinstance(ratio, sympy.Rational) and ratio > 0 and ratio != 1 and max(ratio.p, ratio.q) <= 12:
        return ratio
    return None


def compareSizes(answer: dict[str, Any], lines: list[str]) -> dict[str, str] | None:
    """The student's final number next to the right one, and how many times off it is."""
    expected = numericAnswerValue(answer)
    given = lastStatedValue(lines)
    if expected is None or given is None or expected == 0 or isMatchingValue(given, expected):
        return None
    for value in readLineValues(lines):
        if value is not None and value != given and not value.is_Float and isMatchingValue(given, value):
            given = value  # '= 6.28' rounds the '44/7' above it: compare the exact value, so the factor shows
            break
    fact = {"kind": "size", "given": sympy.latex(given), "expected": sympy.latex(expected)}
    for key, value in (("givenApprox", given), ("expectedApprox", expected)):
        approx = formatApprox(value)
        if approx:
            fact[key] = approx
    ratio = findSimpleRatio(given, expected)
    if ratio is not None:
        fact["ratio"] = sympy.latex(ratio)
    return fact


def plugIntoQuestion(answer: dict[str, Any], questionExpressions: list[str], lines: list[str]) -> dict[str, str] | None:
    """Put the student's root back into the question's equation: both sides come out different, so it cannot be a
    root. Proves the answer wrong without giving the right one away."""
    if answer.get("type") != "solution_set":
        return None
    variable = str(answer.get("variable") or "")
    givenValues = readFinalAssignments(lines).get(variable) or set()
    try:
        rightValues = [readValue(str(value)) for value in answer.get("values") or []]
    except (LatexParseError, *MATHS_ERRORS):
        return None
    wrongValues = [value for value in givenValues if not any(isMatchingValue(value, right) for right in rightValues)]
    if not wrongValues:
        return None
    given = wrongValues[0]
    for expression in questionExpressions:
        try:
            equation = parseLatex(expression)
        except LatexParseError:
            continue
        if not isinstance(equation, sympy.Eq) or {str(symbol) for symbol in equation.free_symbols} != {variable}:
            continue
        symbol = next(iter(equation.free_symbols))
        try:
            left = sympy.nsimplify(equation.lhs.subs(symbol, given))
            right = sympy.nsimplify(equation.rhs.subs(symbol, given))
        except MATHS_ERRORS:
            continue
        if left.is_number and right.is_number and sympy.simplify(left - right) != 0:
            return {
                "kind": "plug_in", "equation": expression, "variable": variable, "given": sympy.latex(given),
                "left": sympy.latex(left), "right": sympy.latex(right),
            }  # fmt: skip
    return None


def testAtAPoint(answer: dict[str, Any], questionExpressions: list[str], lines: list[str]) -> dict[str, str] | None:
    """For 'simplify / expand / factorise': put x = 2 into the question's expression and into the student's last
    one. A right rewrite gives the same number at every x, so two different numbers prove the rewrite wrong."""
    if answer.get("type") != "expression" or not lines:
        return None
    try:
        parsedAnswer = parseLatex(str(answer["latex"]))
        lastLine = parseLatex(prepareLine(lines[-1]))
    except (LatexParseError, KeyError):
        return None
    if not isinstance(parsedAnswer, sympy.Expr) or not parsedAnswer.free_symbols:
        return None
    given = lastLine.rhs if isinstance(lastLine, sympy.Eq) else lastLine
    symbols = parsedAnswer.free_symbols
    if not isinstance(given, sympy.Expr) or not given.free_symbols or not given.free_symbols <= symbols:
        return None
    for expression in questionExpressions:
        try:
            question = parseLatex(expression)
        except LatexParseError:
            continue
        if not isinstance(question, sympy.Expr) or question.free_symbols != symbols:
            continue
        for point in TEST_POINTS:
            values = {symbol: point for symbol in symbols}
            try:
                questionValue = sympy.nsimplify(question.subs(values))
                answerValue = sympy.nsimplify(parsedAnswer.subs(values))
                givenValue = sympy.nsimplify(given.subs(values))
            except MATHS_ERRORS:
                continue
            if not (questionValue.is_finite and givenValue.is_finite) or questionValue != answerValue:
                continue  # the question's expression must really equal the answer here, or the check proves nothing
            if givenValue != questionValue:
                names = sorted(str(symbol) for symbol in symbols)
                return {
                    "kind": "test_point", "point": ", ".join(f"{name} = {point}" for name in names),
                    "question": expression, "given": sympy.latex(given),
                    "questionValue": sympy.latex(questionValue), "givenValue": sympy.latex(givenValue),
                }  # fmt: skip
            break
    return None


def measureMistake(answer: dict[str, Any], questionExpressions: list[str], lines: list[str]) -> list[dict[str, str]]:
    """Every proven number check that shows the wrong answer is wrong: sizes, the answer put back, a test point."""
    plugged = plugIntoQuestion(answer, questionExpressions, lines)
    if plugged:
        return [plugged]  # the sizes would show the right root; finding it is the student's job in the next step
    found = [compareSizes(answer, lines), testAtAPoint(answer, questionExpressions, lines)]
    return [fact for fact in found if fact]
