# Names the student's mistake by REPLAYING common wrong rules on the line they started from.
# If applying a wrong rule (e.g. "add the tops and add the bottoms") to their previous line gives exactly the
# line they wrote, that rule is proven to be their mistake — no guessing. The explanation then includes a tiny
# number example a child can check in their head, which the tutor and the visual both teach from.

import re
from collections.abc import Callable
from dataclasses import dataclass

import sympy

from app.maths import checker
from app.maths.parser import LatexParseError, parseLatex

TERM = r"[^{}()+\-=]+"  # a simple term: no brackets, no + / - / =
BRACED = r"\{([^{}]+)\}"


@dataclass(frozen=True)
class WrongRule:
    kind: str  # what Progress counts as a recurring mistake
    pattern: re.Pattern[str]
    rewrite: Callable[[re.Match[str]], str]
    explain: Callable[[re.Match[str], str], str]  # (match, the student's wrong latex) -> facts


def explainFractions(match: re.Match[str], wrong: str) -> str:
    return (
        f"You added the tops and also added the bottoms: ${match.group(0)}$ became ${wrong}$. "
        "Fractions can be added only when the bottoms (denominators) are the same — first make them equal with "
        "the LCM, then add only the tops. Check with numbers: $\\frac{1}{2} + \\frac{1}{3} = \\frac{5}{6}$, "
        "but adding tops and bottoms gives $\\frac{2}{5}$, which is even smaller than $\\frac{1}{2}$ alone."
    )


def explainSquare(match: re.Match[str], wrong: str) -> str:
    return (
        f"You squared each term separately: ${match.group(0)}$ is not ${wrong}$. "
        "$(a + b)^2 = a^2 + 2ab + b^2$ — the middle term $2ab$ is missing. "
        "Check with numbers: $(2 + 3)^2 = 25$, but $2^2 + 3^2 = 13$."
    )


def explainRoot(match: re.Match[str], wrong: str) -> str:
    return (
        f"You took the root of each term separately: ${match.group(0)}$ is not ${wrong}$. "
        "A square root cannot be split over a plus sign. Check with numbers: $\\sqrt{9 + 16} = \\sqrt{25} = 5$, "
        "but $\\sqrt{9} + \\sqrt{16} = 7$."
    )


def explainMinusBracket(match: re.Match[str], wrong: str) -> str:
    return (
        f"When you opened ${match.group(0)}$, only the first sign changed. A minus before a bracket changes the sign "
        "of EVERY term inside: $-(a + b) = -a - b$. Check with numbers: $-(2 + 3) = -5$, but $-2 + 3 = 1$."
    )


def explainPartialMultiply(match: re.Match[str], wrong: str) -> str:
    return (
        f"When you opened ${match.group(0)}$, you multiplied only the first term. The number outside multiplies "
        "EVERY term inside: $k(a + b) = ka + kb$. Check with numbers: $2(3 + 4) = 14$, but $2 \\times 3 + 4 = 10$."
    )


WRONG_RULES = [
    WrongRule(
        "adding fractions (tops and bottoms added separately)",
        re.compile(rf"\\frac{BRACED}{BRACED}\s*\+\s*\\frac{BRACED}{BRACED}"),
        lambda m: f"\\frac{{({m.group(1)}) + ({m.group(3)})}}{{({m.group(2)}) + ({m.group(4)})}}",
        explainFractions,
    ),
    WrongRule(
        "adding fractions (tops and bottoms added separately)",
        re.compile(rf"\(?\s*({TERM})\s*/\s*({TERM})\s*\)?\s*\+\s*\(?\s*({TERM})\s*/\s*({TERM})\s*\)?"),
        lambda m: f"\\frac{{({m.group(1)}) + ({m.group(3)})}}{{({m.group(2)}) + ({m.group(4)})}}",
        explainFractions,
    ),
    WrongRule(
        "squaring a bracket term by term",
        re.compile(rf"\(\s*({TERM})\s*([+-])\s*({TERM})\s*\)\s*\^\s*\{{?2\}}?"),
        lambda m: f"({m.group(1)})^2 {m.group(2)} ({m.group(3)})^2",
        explainSquare,
    ),
    WrongRule(
        "splitting a square root over a plus",
        re.compile(rf"\\sqrt\{{\s*({TERM})\s*\+\s*({TERM})\s*\}}"),
        lambda m: f"\\sqrt{{{m.group(1)}}} + \\sqrt{{{m.group(2)}}}",
        explainRoot,
    ),
    WrongRule(
        "minus sign before a bracket",
        re.compile(rf"-\s*\(\s*({TERM})\s*([+-])\s*({TERM})\s*\)"),
        lambda m: f"-({m.group(1)}) {m.group(2)} ({m.group(3)})",
        explainMinusBracket,
    ),
    WrongRule(
        "multiplying into a bracket (only the first term)",
        re.compile(rf"(\d+)\s*\(\s*({TERM})\s*([+-])\s*({TERM})\s*\)"),
        lambda m: f"{m.group(1)} \\cdot ({m.group(2)}) {m.group(3)} ({m.group(4)})",
        explainPartialMultiply,
    ),
]


def followsFrom(candidateLatex: str, wrongLatex: str) -> bool:
    """True when the student's line is exactly what the wrong rule produces (up to simple rearranging)."""
    try:
        candidate, wrong = parseLatex(candidateLatex), parseLatex(wrongLatex)
    except LatexParseError:
        return False
    return checker.compareLines(candidate, wrong, None) == checker.CORRECT


def findWrongRule(previousLatex: str, wrongLatex: str) -> tuple[str, str] | None:
    """(kind, facts) when replaying a known wrong rule on the previous line gives exactly the wrong line."""
    for rule in WRONG_RULES:
        for match in rule.pattern.finditer(previousLatex):
            replayed = previousLatex[: match.start()] + rule.rewrite(match) + previousLatex[match.end() :]
            if followsFrom(replayed, wrongLatex):
                written = next((part.strip() for part in wrongLatex.split("=") if part.strip()), wrongLatex)
                return rule.kind, rule.explain(match, written)  # '= (2+1)/(3+4)' -> '(2+1)/(3+4)', never empty
    return None


# ---------- quadratic formula: replay the three classic slips with the question's own a, b, c ----------


def findQuadraticFormulaSlip(questionExpressions: list[str], wrongLatex: str) -> tuple[str, str] | None:
    """The ± line gives two values; if they are exactly what a known slip produces, name that slip."""
    try:
        history = [parseLatex(expression) for expression in questionExpressions]
        variants = [parseLatex(text) for text in checker.plusMinusVariants(checker.prepareLine(wrongLatex))]
    except LatexParseError:
        return None
    coefficients = checker.quadraticCoefficients(history)
    if not coefficients or len(variants) != 2:
        return None
    written = set()
    for variant in variants:
        value = variant.rhs if isinstance(variant, sympy.Eq) else variant
        if not (isinstance(value, sympy.Expr) and value.is_number):
            return None
        written.add(sympy.nsimplify(value))
    a, b, c = coefficients["a"], coefficients["b"], coefficients["c"]
    root = sympy.sqrt(b**2 - 4 * a * c)
    slips = [
        (
            "quadratic formula: sign of -b",
            {(b + root) / (2 * a), (b - root) / (2 * a)},
            f"The formula starts with $-b$. Here $b = {sympy.latex(b)}$, so $-b = {sympy.latex(-b)}$ — "
            f"you wrote ${sympy.latex(b)}$ instead. A minus in front of a negative number makes it positive.",
        ),
        (
            "quadratic formula: dividing by 2 instead of 2a",
            {(-b + root) / 2, (-b - root) / 2},
            f"The whole top is divided by $2a = 2 \\times {sympy.latex(a)} = {sympy.latex(2 * a)}$, not just by 2.",
        ),
        (
            "quadratic formula: forgot the square root",
            {(-b + (b**2 - 4 * a * c)) / (2 * a), (-b - (b**2 - 4 * a * c)) / (2 * a)},
            f"Take the square root of $b^2 - 4ac = {sympy.latex(b**2 - 4 * a * c)}$ first: "
            f"$\\sqrt{{{sympy.latex(b**2 - 4 * a * c)}}} = {sympy.latex(root)}$.",
        ),
    ]
    for kind, values, facts in slips:
        if {sympy.nsimplify(value) for value in values} == written:
            return kind, facts
    return None
