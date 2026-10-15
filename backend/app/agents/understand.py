# Understanding any typed or photographed question — and only claiming an answer we have verified.
#
#   1. normalize      Unicode minus signs, superscripts, line breaks -> plain text (meaning preserved)
#   2. fast path      "Solve: 2x + 3y = 11, 2x - 4y = -24" -> read the equations straight from the text (no AI)
#   3. plan (AI)      which problem family, which numbers — the AI never calculates
#   4. solve (code)   maths/solvers.py computes the answer, the steps, and checks it (substitution, 2nd formula...)
#   5. trust check    every number the AI used must be in the question; if not, or if the AI had to turn words
#                     into maths, a SECOND model reads the question independently and must reach the same answer
#
# Outcome (status): solved | needs_clarification | unsupported | parse_failed | verification_failed | not_maths
#                   | ai_unavailable (the models did not answer; nothing is wrong with the question)

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

import sympy

from app.ai.models import AiModels
from app.ai.prompts import CHAPTERS, PLAN_QUESTION_PROMPT
from app.maths import checker, solvers
from app.maths.parser import DIGIT_GROUPS, LatexParseError, getFreeSymbols, hasPlainWords, normalizeSymbols, parseLatex

# Words that may surround equations in a pure "solve these equations" question.
SOLVE_WORDS = set(
    "solve the following pair of linear equation equations for and find value values using by elimination "
    "substitution method in two one variable variables simultaneous get obtain if given system solution "
    "solutions question both their its then x y z a b p q m n t u v k quadratic roots root".split()
)
REFUSALS = {
    "not_maths": "I only check Class 6–10 maths questions. Try a maths question!",
    "above_class_10": "This looks like maths beyond Class 10. For now I check Class 6–10 questions.",
}
PROOF_WORDS = re.compile(r"\bprove\b|\bshow that\b|\birrational\b", re.IGNORECASE)
UNSUPPORTED_MESSAGE = (
    "I understood the question, but I can't check {reason} yet. Calculation, equation and formula questions work best."
)
TWO_READINGS_MESSAGE = "I read this question in two ways and got two different answers, so I won't guess. Could you write it a bit more clearly?"
# Numbers the AI may use without them being in the question (e.g. "twice" -> 2, "percent" -> 100).
EVERYDAY_NUMBERS = {Fraction(value) for value in (0, 1, 2, 3, 4, 10, 12, 60, 100, 180, 360, 1000)} | {
    Fraction(22, 7),
    Fraction(314, 100),
}


@dataclass
class Understanding:
    status: str
    message: str | None = None
    understood: list[str] = field(default_factory=list)  # the maths we read, shown when we ask something
    parts: list[dict[str, Any]] = field(default_factory=list)  # one entry per (sub)question, ready to save


# ---------- 1-2: normalize and the fast path ----------


def normalizeQuestion(text: str) -> str:
    text = normalizeSymbols(text.replace("\r", "\n"))
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.split("\n") if line.strip())


def isSimpleSymbolName(symbol: sympy.Symbol) -> bool:
    return len(str(symbol)) == 1


def readEquation(segment: str) -> tuple[str, list[str]] | None:
    """The longest run of words in a segment that is an equation, plus the leftover words."""
    words = segment.split()
    for start in range(len(words)):
        for end in range(len(words), start, -1):
            candidate = " ".join(words[start:end]).strip(" .:;")
            if "=" not in candidate or hasPlainWords(candidate):
                continue
            try:
                parsed = parseLatex(candidate)
            except LatexParseError:
                continue
            symbols = getFreeSymbols(parsed) if isinstance(parsed, sympy.Eq) else set()
            if symbols and all(isSimpleSymbolName(symbol) for symbol in symbols):
                return candidate, words[:start] + words[end:]
    return None


def readExplicitEquations(text: str) -> list[str] | None:
    """Equations written in the question, when the question is ONLY 'solve these'. Else None (use the AI)."""
    segments = [part for part in re.split(r"\n|;|,(?![^(]*\))|\band\b|\.\s", text) if part.strip()]
    equations: list[str] = []
    for segment in segments:
        found = readEquation(segment) if "=" in segment else None
        leftover = segment.split() if found is None else found[1]
        if found:
            equations.append(found[0])
        for word in leftover:
            cleaned = word.lower().strip(".,:;?!()")
            if cleaned and cleaned not in SOLVE_WORDS and not re.fullmatch(r"q?\d{1,2}|[ivx]{1,4}|[a-d]", cleaned):
                return None  # the question asks something more than solving these equations
    return equations or None


def chapterOfEquations(equations: list[str]) -> dict[str, Any]:
    """Class and chapter follow from the maths itself: two linear equations, a quadratic, or one linear equation."""
    parsed = [parseLatex(item) for item in equations]
    degree = max(
        sympy.Poly(item.lhs - item.rhs, *getFreeSymbols(item)).total_degree()
        for item in parsed
        if isinstance(item, sympy.Eq)
    )
    if len(parsed) >= 2:
        return {"class_level": 10, "chapter": "Pair of Linear Equations in Two Variables"}
    if degree == 2:
        return {"class_level": 10, "chapter": "Quadratic Equations"}
    return {"class_level": 8, "chapter": "Algebra Play (linear equations)"}


YES_NO_CHECKS = {"prime", "divisible", "perfect_square", "perfect_cube", "rational", "terminating_decimal"}


def isYesNoQuestion(text: str) -> bool:
    """'Is 91 prime?', 'Check whether 2744 is a perfect cube', 'Kya 91 prime hai?' — not 'Find the smallest number...'."""
    lowered = text.lower().strip()
    return bool(
        re.search(
            r"^\s*(q?\d+[.)]\s*)?(is|are|does|do|can|will|kya)\b|\bwhether\b|\b(true or false|yes or no)\b", lowered
        )
    )


# ---------- 4: running a solver ----------


# A length, an age, a price, a speed cannot be negative: PT^2 = 144 means PT = 12, not -12 as well.
MEASURE = re.compile(
    r"\b(?:cm|mm|km|metres?|meters?|m|kg|g|litres?|length|distance|height|width|breadth|radius|diameter|side|"
    r"perimeter|area|volume|tangent|age|years?|speed|price|cost|rs|₹|minutes?|hours?|days?)\b",
    re.IGNORECASE,
)


# A number with a unit or a degree sign ('60°', '6 cm', '8%') is a measurement the question gives on purpose.
MEASUREMENT = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\$\s*)?(?:\\text\{\s*|\\,|\\ )*"
    r"(?:°|\^\s*\{?\s*\\circ|degrees?\b|cm\b|mm\b|km\b|m\b|metres?\b|meters?\b|kg\b|g\b|litres?\b|ml\b|%|\\%|percent\b)",
    re.IGNORECASE,
)


def findIgnoredMeasurements(params: dict[str, Any], questionText: str) -> set[Fraction]:
    """Measurements the question gives that the reading never uses. 'Area of a sector, radius 6 cm, angle 60°' was
    once read as a whole circle of radius 6: both readings dropped the 60° and agreed on the wrong area, 792/7."""
    given = {Fraction(number) for number in MEASUREMENT.findall(questionText)}
    used = readNumbers({key: value for key, value in params.items() if key != "pi"} if isinstance(params, dict) else params)
    # 'diameter 12 cm' may be read as radius 6, and a percentage as a fraction: the same measurement, not ignored
    nearby = used | {value * 2 for value in used} | {value / 2 for value in used} | {value * 100 for value in used}
    return given - nearby


ASKS_FOR_ZEROES = re.compile(r"\bzero(?:e)?s\b|\broots?\s+of\b", re.IGNORECASE)
ASKS_FOR_POLYNOMIAL = re.compile(r"\bpolynomial whose\b|\bwhose zero|\bfind (?:a|the) (?:quadratic |cubic )?polynomial\b", re.IGNORECASE)
ASKS_FOR_NATURE = re.compile(r"\bnature of (?:the )?roots\b", re.IGNORECASE)


def runSolver(family: str, params: dict[str, Any], questionText: str = "") -> solvers.Solved:
    """Solve one reading, then make sure it answers what the question ASKS (zeroes are values, not factors)."""
    ignored = findIgnoredMeasurements(params, questionText) if questionText else set()
    if ignored:
        numbers = ", ".join(sorted(str(value) for value in ignored))
        raise solvers.SolverError(f"it did not use {numbers}, which the question gives")
    solved = solveFamily(family, params, questionText)
    answer = solved.answer
    if ASKS_FOR_NATURE.search(questionText):
        # The equation is written in the question: SymPy works out b² − 4ac from it. A reading once set up the
        # discriminant with a wrong coefficient and called 2x² − 4x + 3 = 0 "two equal real roots" (D is −8).
        discriminant = discriminantInQuestion(questionText)
        if discriminant is None:
            discriminant = checker.numericAnswerValue(answer)
        if discriminant is None or not discriminant.is_real:
            raise solvers.SolverError("the question asks for the nature of the roots: work out the discriminant b² − 4ac")
        nature = "no real roots" if discriminant < 0 else "two equal real roots" if discriminant == 0 else "two distinct real roots"
        accept = {"no real roots": ["no real roots", "not real", "imaginary", "no real"],
                  "two equal real roots": ["equal", "coincident"],
                  "two distinct real roots": ["distinct", "unequal", "different"]}[nature]  # fmt: skip
        sign = "less than 0" if discriminant < 0 else "0" if discriminant == 0 else "greater than 0"
        solved.step(f"The discriminant is {sign}, so the equation has {nature}.", f"D = {sympy.latex(discriminant)}")
        solved.answer = {"type": "text", "value": nature, "accept": accept}
    elif ASKS_FOR_ZEROES.search(questionText) and not ASKS_FOR_POLYNOMIAL.search(questionText) and answer.get("type") == "expression":
        try:
            expressionHasUnknown = bool(getFreeSymbols(parseLatex(str(answer.get("latex")))))
        except LatexParseError:
            expressionHasUnknown = False
        if expressionHasUnknown:  # '(x - 4)(x + 2)' answers "factorise", not "find the zeroes"
            raise solvers.SolverError("the question asks for the zeroes (the values of the unknown), not a factorised form")
    return solved


def discriminantInQuestion(questionText: str) -> sympy.Expr | None:
    """b² − 4ac of the quadratic equation written in the question (the longest run of words that is an equation in
    one unknown: 'of' in 'roots of x² − 5x + 6 = 0' is not maths), or None when there is none."""
    words = normalizeQuestion(questionText).replace("$", " ").split()
    best: sympy.Poly | None = None
    bestLength = 0
    for start in range(len(words)):
        for end in range(len(words), start, -1):
            candidate = " ".join(words[start:end]).strip(" .,:;?")
            if end - start <= bestLength or "=" not in candidate:
                continue
            try:
                equation = parseLatex(candidate)
                symbols = getFreeSymbols(equation)
                if isinstance(equation, sympy.Eq) and len(symbols) == 1:
                    best, bestLength = sympy.Poly(equation.lhs - equation.rhs, *symbols), end - start
            except (LatexParseError, sympy.PolynomialError):
                continue
    if best is None or best.degree() != 2:
        return None
    a, b, c = best.all_coeffs()
    return sympy.nsimplify(b**2 - 4 * a * c)


def solveFamily(family: str, params: dict[str, Any], questionText: str = "") -> solvers.Solved:
    get = params.get
    if family == "equations":
        positive = [str(name) for name in get("positive") or []]
        if MEASURE.search(questionText):
            for equation in get("equations") or []:
                try:
                    positive += [str(symbol) for symbol in getFreeSymbols(parseLatex(str(equation)))]
                except LatexParseError:
                    continue
        ask = str(get("ask")) if get("ask") else None
        return solvers.solveEquations([str(item) for item in get("equations") or []], positive, ask)
    if family == "progression":
        terms = get("terms")
        if not terms and get("first") is not None and get("difference") is not None:
            first, difference = solvers.number(get("first")), solvers.number(get("difference"))
            terms = [first, first + difference]
        return solvers.solveProgression(terms or [], str(get("ask")), get("n"), get("value"))
    if family == "statistics":
        return solvers.solveStatistics(str(get("ask")), get("values") or [], get("frequencies"))
    if family == "hcf_lcm":
        return solvers.solveHcfLcm(str(get("ask")), get("numbers") or [])
    if family == "mensuration":
        return solvers.solveMensuration(
            str(get("shape")), str(get("quantity")), get("dimensions") or {}, str(get("pi") or "pi")
        )
    if family == "interest":
        return solvers.solveInterest(
            str(get("kind")), str(get("ask")), get("principal"), get("rate"), get("time"), get("periods_per_year") or 1
        )
    if family == "coordinates":
        return solvers.solveCoordinates(str(get("ask")), get("points") or [], get("ratio"))
    if family == "identity":
        if not get("lhs") or not get("rhs"):
            raise solvers.SolverError("both sides of the identity are needed")
        return solvers.solveIdentity(str(get("lhs")), str(get("rhs")))
    if family == "property":
        return solvers.solveProperty(str(get("check")), get("value"), get("other"), get("point"))
    if family == "expression":
        form = get("form") if get("form") in ("factored", "expanded") else None
        if not get("expression"):  # str(None) would be read as the letters N·o·n·e
            raise solvers.SolverError("no expression was given")
        return solvers.solveExpression(str(get("expression")), form)
    raise solvers.SolverError(f"unknown problem type '{family}'")


def gradingExpressions(family: str, params: dict[str, Any]) -> list[str]:
    """The maths a student's first line is compared with when their working is checked."""
    if family == "equations":
        return [str(item) for item in params.get("equations") or []]
    if family == "identity":
        return [str(params.get("lhs"))]
    if family == "expression":
        return [str(params.get("expression"))]
    return []


# ---------- 5: the trust check ----------


VULGAR_FRACTIONS = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅕": "1/5", "⅖": "2/5", "⅗": "3/5",
                    "⅘": "4/5", "⅙": "1/6", "⅚": "5/6", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8", "⅐": "1/7", "⅑": "1/9"}


def readNumbers(value: Any) -> set[Fraction]:
    text = " ".join(str(item) for item in flatten(value))
    for symbol, fraction in VULGAR_FRACTIONS.items():
        text = text.replace(symbol, f" {fraction} ")  # 'Subtract ⅙ from 5/8' gives 6 too
    text = DIGIT_GROUPS.sub(lambda match: match.group(0).replace(",", ""), text)  # 'Rs 5,000' gives 5000, not 5 and 0
    text = re.sub(r"(\d)(?:\{,\}|,\\[!,]?\s?)(\d{3})\b", r"\1\2", text)  # LaTeX '5{,}000' / '5,\\!000'
    found = set()
    for match in re.findall(r"\d+(?:\.\d+)?", text):
        found.add(Fraction(match))
    return found


def flatten(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return [item for inner in value.values() for item in flatten(inner)]
    if isinstance(value, (list, tuple)):
        return [item for inner in value for item in flatten(inner)]
    return [value]


NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100,
    "half": 2, "twice": 2, "double": 2, "thrice": 3, "triple": 3, "dozen": 12, "quarter": 4, "third": 3,
}  # fmt: skip


WORLD_NUMBERS = (
    (r"\bdi(?:e|ce)\b", (6, 36)),
    # A deck is a closed world: 52 cards, 26 red / black, 13 per suit, 12 face cards (6 red), 4 of each rank, and
    # the counts a question builds from them (20 red non-face, 40 non-face, 48 not a king, 36 numbered, ...).
    (r"\bcards?\b|\bdeck\b|\bpack\b", (52, 26, 13, 12, 6, 4, 2, 3, 8, 16, 20, 22, 24, 36, 39, 40, 44, 48, 50)),
    (r"\bcoins?\b", (2, 4, 8)),
    (r"\bweeks?\b", (7,)),
    (r"\byears?\b|\bmonths?\b|\bannum\b", (12, 365, 366)),
    (r"\bdays?\b|\bhours?\b", (24, 60)),
    (r"\bminutes?\b|\bseconds?\b", (60,)),
    (r"\bkm\b|\bkilomet", (1000,)),
    (r"\bcm\b|\bmet(?:re|er)s?\b", (100,)),
    (r"\bkg\b|\bkilogram", (1000,)),
    (r"\blit(?:re|er)s?\b", (1000,)),
    # Words that ARE numbers to a student: angle facts, polygon names, the smallest / largest n-digit numbers.
    (r"\bcomplementary\b|\bright[- ]angle", (90,)),
    (r"\bsupplementary\b|\blinear pair\b|\bstraight (?:line|angle)\b", (180,)),
    (r"\bpentagon", (5,)), (r"\bhexagon", (6,)), (r"\bheptagon", (7,)), (r"\boctagon", (8,)),
    (r"\bnonagon", (9,)), (r"\bdecagon", (10,)),
    (r"\btwo[- ]digit", (10, 99, 90)), (r"\bthree[- ]digit", (100, 999, 900)), (r"\bfour[- ]digit", (1000, 9999, 9000)),
    # A recurring decimal is turned into p/q with 9, 99, 999 ...
    (r"\.\.\.|…|\\overline|\\dot|recurring|repeating", (9, 99, 999, 9999)),
)


def findInventedNumbers(params: dict[str, Any], questionText: str) -> set[Fraction]:
    """Numbers the reading uses that the question never gives (as digits, a number word or an everyday constant).
    A question photo that lost a line ('Find the third angle.') once came back as 50 + 60 + x = 180: two models
    'remembered' the famous NCERT sum. Such a reading is a guess, never an answer."""
    words = {Fraction(value) for word, value in NUMBER_WORDS.items() if re.search(rf"\b{word}", questionText, re.IGNORECASE)}
    # World knowledge every student has: a die has 6 faces, a deck 52 cards, a week 7 days. Not a guess.
    for pattern, values in WORLD_NUMBERS:
        if re.search(pattern, questionText, re.IGNORECASE):
            words |= {Fraction(value) for value in values}
    # The value of π ('22/7') is a choice of approximation, not a number of the question (a cuboid has none).
    used = {key: value for key, value in params.items() if key != "pi"} if isinstance(params, dict) else params
    given = readNumbers(questionText)
    # Worked out from two given numbers is not invented: d = 9 - 4 = 5 for the AP 4, 9, 14, ...
    derived = set()
    for first in given:
        derived |= {first + 1, abs(first - 1)}  # the 31st term is a + 30d
        if re.search(r"standard form|scientific notation|\d\.\d", questionText, re.IGNORECASE):
            derived |= {first * Fraction(10) ** power for power in range(-12, 13)}  # 0.00045 = 4.5 × 10⁻⁴
        for second in given:
            derived |= {first + second, abs(first - second), first * second}
            derived |= {(first + second) / 2, abs(first - second) / 2}  # 105 × 95 = (100 + 5)(100 − 5)
            hypotenuse = sympy.sqrt(sympy.Rational(first) ** 2 + sympy.Rational(second) ** 2)
            if hypotenuse.is_Rational:  # tan A = 4/3 needs the third side, 5
                derived.add(Fraction(int(hypotenuse.p), int(hypotenuse.q)))
            if second:
                derived.add(first / second)
    # The digits of a repeating block ('0.363636...' repeats 36) are given too
    if re.search(r"\.\.\.|…|recurring|repeating", questionText):
        for digits in re.findall(r"\d+\.(\d+)", questionText):
            words |= {Fraction(digits[start:end]) for start in range(len(digits)) for end in range(start + 1, min(len(digits), start + 4) + 1)}
    return readNumbers(used) - given - derived - EVERYDAY_NUMBERS - words


def usesOnlyQuestionNumbers(params: dict[str, Any], questionText: str) -> bool:
    return readNumbers(params) <= readNumbers(questionText) | EVERYDAY_NUMBERS


def singleValue(answer: dict[str, Any]) -> str | None:
    """'70', 'x = 70' and '(x: 70)' are the same single answer, however the reading set the maths up."""
    if answer["type"] == "expression":
        return str(answer["latex"])
    values = answer.get("values")
    values = list(values.values()) if isinstance(values, dict) else values
    return str(values[0]) if answer["type"] in ("solution_set", "point") and values and len(values) == 1 else None


def isSameAnswer(first: dict[str, Any], second: dict[str, Any]) -> bool:
    if first["type"] != second["type"]:
        firstValue, secondValue = singleValue(first), singleValue(second)
        if firstValue is None or secondValue is None:
            return False
        try:
            same = checker.areExpressionsEquivalent(checker.readValue(firstValue), checker.readValue(secondValue))
        except LatexParseError:
            return False
        return same is True
    if first["type"] == "text":
        return bool(first["value"] == second["value"])
    lines = (
        [checker.formatAnswer(second)]
        if second["type"] in ("expression", "identity")
        else [f"{name} = {value}" for name, value in second["values"].items()]
        if second["type"] == "point"
        else [f"{second['variable']} = {value}" for value in second["values"]]
    )
    try:
        return checker.isFinalAnswerCorrect(first, lines)
    except (LatexParseError, KeyError, TypeError):
        return False


# ---------- the pipeline ----------


def planQuestion(
    ai: AiModels, text: str, secondOpinion: bool = False, temperature: float = 0.0
) -> dict[str, Any] | None:
    plan = ai.askJson(PLAN_QUESTION_PROMPT, text, temperature=temperature, secondOpinion=secondOpinion)
    if not plan or not isinstance(plan.get("parts"), list):
        return None
    return plan


READ_ERRORS = (solvers.SolverError, LatexParseError, TypeError, ValueError, KeyError, ZeroDivisionError, AttributeError)


def solveReading(plan: dict[str, Any] | None, partIndex: int) -> tuple[str, dict[str, Any], solvers.Solved] | None:
    """Solve part `partIndex` of one reading of the question. None when that reading cannot be solved."""
    parts = (plan or {}).get("parts") or []
    if len(parts) <= partIndex:
        return None
    family, params = str(parts[partIndex].get("family")), parts[partIndex].get("params") or {}
    try:
        return family, params, runSolver(family, params, str((plan or {}).get("question") or ""))
    except READ_ERRORS:
        return None


def buildPart(
    text: str, family: str, params: dict[str, Any], solved: solvers.Solved, plan: dict[str, Any], trust: str
) -> dict[str, Any]:
    classLevel = int(plan["class_level"]) if plan.get("class_level") in range(6, 11) else 8
    chapter = str(plan.get("chapter") or "")
    if chapter not in CHAPTERS.get(str(classLevel), []):
        # The AI named a real chapter of another class (a circle's circumference read as Class 7): trust the chapter.
        owners = [int(level) for level, titles in CHAPTERS.items() if chapter in titles]
        if owners:
            classLevel = min(owners, key=lambda level: abs(level - classLevel))
        else:
            chapter = "Mixed practice"
    return {
        "text": text,
        "expressions": gradingExpressions(family, params),
        "answer": solved.answer,
        "marks": 2 if len(solved.steps) <= 2 else 3 if len(solved.steps) <= 5 else 4,
        "class_level": classLevel,
        "chapter": chapter,
        "family": family,
        "trust": trust,
        "checks": solved.checks,
        "traps": solved.traps,
        "solution": {"en": solved.steps},
    }


def solvePart(
    part: dict[str, Any], questionText: str, plan: dict[str, Any], ai: AiModels, partIndex: int
) -> dict[str, Any] | Understanding:
    family, params = str(part.get("family")), part.get("params") or {}
    if family == "unsupported":
        return Understanding(
            "unsupported", UNSUPPORTED_MESSAGE.format(reason=params.get("reason") or "this kind of question")
        )
    readingText = questionText  # what each confirming reading sees
    try:
        if family == "property" and str(params.get("check")) in YES_NO_CHECKS and not isYesNoQuestion(questionText):
            raise solvers.SolverError("the question asks for a value, not a yes/no answer")
        solved = runSolver(family, params, questionText)
    except READ_ERRORS as error:
        # Bounded correction: the AI may have picked the wrong method (e.g. called 1, 4, 9, 16 an AP).
        # Re-read ONCE, telling it why the first reading failed; if that also fails, ask the student.
        reason = str(error) if isinstance(error, solvers.SolverError) else "the maths could not be read"
        readingText = f"{questionText}\n\n(Note: a first reading as '{family}' was wrong because {reason}. Do NOT use the family '{family}' for this part.)"
        retryPlan = planQuestion(ai, readingText, secondOpinion=True)  # a different model re-reads
        retryParts = (retryPlan or {}).get("parts") or []
        if len(retryParts) > partIndex and retryParts[partIndex].get("family") == "unsupported":
            why = (retryParts[partIndex].get("params") or {}).get("reason")
            return Understanding("unsupported", UNSUPPORTED_MESSAGE.format(reason=why or "this kind of question"))
        retry = solveReading(retryPlan, partIndex)
        if retry is None:
            # One more fresh reading before asking the student: on live, a Class 10 AP sum and a Thales question
            # each got two bad readings in a row, and a third one read them right. Agreement checks still follow.
            retry = solveReading(planQuestion(ai, readingText, temperature=0.4), partIndex)
        if retry is None:
            if isinstance(error, solvers.SolverError):
                reason = str(error).replace("'None' is not a number", "a value was missing")
                return Understanding(
                    "needs_clarification",
                    f"I read the question, but {reason}. Could you check the question?",
                    [str(item) for item in flatten(params)][:6],
                )
            return Understanding(
                "parse_failed",
                "I could not read the maths in this question reliably. Could you type it again, one equation per line?",
            )
        family, params, solved = retry
        solved.checks.append("re-read after the first reading did not fit")
    trust = "verified"
    setsUpMaths = family in ("expression", "equations")  # the AI turned words into maths: a second reading must agree
    if setsUpMaths or not usesOnlyQuestionNumbers(params, questionText):
        secondPlan = planQuestion(ai, readingText, secondOpinion=True)
        second = solveReading(secondPlan, partIndex)
        if second is not None and isSameAnswer(solved.answer, second[2].answer):
            solved.checks.append("a second, independent reading of the question gave the same answer")
        else:
            # Tie-break: a third reading; only an answer that 2 of 3 readings reach is accepted.
            thirdPlan = planQuestion(ai, readingText, temperature=0.6)
            third = solveReading(thirdPlan, partIndex)
            if third is not None and isSameAnswer(solved.answer, third[2].answer):
                solved.checks.append("2 of 3 independent readings gave this answer")
            elif third is not None and second is not None and isSameAnswer(second[2].answer, third[2].answer):
                family, params, solved = second
                solved.checks.append("2 of 3 independent readings gave this answer")
            elif secondPlan is None and thirdPlan is None:
                # The models did not answer (rate limits) — not a disagreement. Keep the answer, say it was read once.
                trust = "single_reading"
            else:
                return Understanding("verification_failed", TWO_READINGS_MESSAGE, gradingExpressions(family, params))
    # after the vote: the reading we keep must not use numbers the question never gave
    invented = findInventedNumbers(params, questionText)
    if invented:
        shown = ", ".join(str(number) for number in sorted(invented))
        return Understanding(
            "needs_clarification",
            f"The question does not seem to give all the numbers needed (I would have to guess {shown}). "
            "Please take a photo of the whole question.",
            [str(item) for item in flatten(params)][:6],
        )
    if family == "expression" and isPlainNumber(str(params.get("expression"))):
        trust = "ai_agreement" if trust == "verified" else trust  # the AI stated the answer; nothing was computed
    # One part: keep the WHOLE question. The part text is often only the last sentence ('Find the third angle.'),
    # which drops the given values the student needs to see.
    isOnlyPart = len(plan.get("parts") or []) <= 1
    text = (plan.get("question") or questionText) if isOnlyPart else (part.get("text") or plan.get("question") or questionText)
    return buildPart(str(text), family, params, solved, plan, trust)


def isPlainNumber(expression: str) -> bool:
    return re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", expression) is not None


def understandQuestion(rawText: str, ai: AiModels) -> Understanding:
    text = normalizeQuestion(rawText)
    equations = readExplicitEquations(text)
    if equations:
        try:
            solved = solvers.solveEquations(equations)
        except solvers.SolverError as error:
            return Understanding(
                "needs_clarification", f"I read {', '.join(equations)} — but {error}. Is anything missing?", equations
            )
        context = chapterOfEquations(equations)  # no AI call: the fast path stays fast and works offline
        return Understanding(
            "solved", parts=[buildPart(text, "equations", {"equations": equations}, solved, context, "verified")]
        )
    if not ai.isAvailable():
        return Understanding(
            "parse_failed", "AI is offline right now. Type just the equation(s), one per line, e.g. 3x + 7 = 22."
        )
    plan = planQuestion(ai, text)
    if plan is None:
        # The models did not answer (rate limited / down) — that is not a problem with the question.
        return Understanding(
            "ai_unavailable",
            "The AI is busy right now. Please try again in a minute — or type just the equation(s), which I can solve without AI.",
        )
    if plan.get("scope") == "above_class_10" and PROOF_WORDS.search(text):
        # 'Prove that √2 is irrational' is Class 10: a proof we cannot check yet, not maths beyond the syllabus
        return Understanding("unsupported", UNSUPPORTED_MESSAGE.format(reason="written proofs"))
    if plan.get("scope") in REFUSALS:
        return Understanding("not_maths", REFUSALS[str(plan["scope"])])
    if plan.get("missing"):
        return Understanding("needs_clarification", f"Something is missing: {plan['missing']}")
    if plan.get("ambiguous"):
        return Understanding("needs_clarification", str(plan["ambiguous"]))
    parts: list[dict[str, Any]] = []
    for index, part in enumerate(plan["parts"][:6]):
        result = solvePart(part, text, plan, ai, index)
        if isinstance(result, Understanding):
            if not parts:
                return result
            break  # keep the parts we could solve
        parts.append(result)
    return (
        Understanding("solved", parts=parts)
        if parts
        else Understanding("parse_failed", "I could not find a question to solve.")
    )
