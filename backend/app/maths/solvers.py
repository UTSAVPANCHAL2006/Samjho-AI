# Solvers for the problem families of Class 6–10 maths. Pure code, no AI.
# Each solver gets numbers/equations (read from the question) and returns:
#   answer -> the checked answer (format used by checker.isFinalAnswerCorrect)
#   steps  -> a school-level derivation; every maths line is computed here, never written by AI
#   checks -> the independent verifications that passed (substitution, second formula, ...)
# A solver raises SolverError when the input does not make sense (e.g. 2, 5, 9 is not an AP),
# and never returns an answer that failed its own check.

import math
import re
from dataclasses import dataclass, field
from typing import Any

import sympy

from app.maths.parser import LatexParseError, getFreeSymbols, parseLatex


class SolverError(Exception):
    """The question is understood, but these values cannot be solved as asked (the message says why)."""


@dataclass
class Solved:
    answer: dict[str, Any]
    steps: list[dict[str, str]] = field(default_factory=list)  # [{"explain", "latex"}]
    checks: list[str] = field(default_factory=list)
    # Common wrong answers for THIS question's numbers, e.g. the AP sum with "a" instead of "2a".
    # [{"value": LaTeX, "mistake": what the student most likely did}] — used to diagnose, never to mark.
    traps: list[dict[str, str]] = field(default_factory=list)

    def trap(self, value: Any, mistake: str, correct: Any) -> None:
        if sympy.nsimplify(value) != sympy.nsimplify(correct):
            self.traps.append({"value": valueText(value), "mistake": mistake})

    def step(self, explain: str, latex: str = "") -> None:
        self.steps.append({"explain": explain, "latex": latex})


def tex(value: Any) -> str:
    latex = str(sympy.latex(sympy.nsimplify(value) if isinstance(value, float) else value))
    return latex.replace("\\left(", "(").replace("\\right)", ")")


def number(value: Any) -> sympy.Expr:
    """'3/4', '2.5', '\\sqrt{2}', 7 -> exact SymPy number. Raises SolverError for anything else."""
    try:
        parsed = sympy.nsimplify(value) if isinstance(value, (int, float)) else parseLatex(str(value))
    except (LatexParseError, TypeError, ValueError, sympy.SympifyError) as error:
        raise SolverError(f"'{value}' is not a number") from error
    if not isinstance(parsed, sympy.Expr) or not parsed.is_number:
        raise SolverError(f"'{value}' is not a number")
    return sympy.nsimplify(parsed)


def valueText(value: sympy.Expr) -> str:
    """Exact answer value as LaTeX: '-2', '\\frac{3}{2}', '2 \\sqrt{3}'."""
    return str(sympy.latex(sympy.nsimplify(value)))


# ---------- equations ----------


def parseEquations(equations: list[str]) -> list[sympy.Eq]:
    parsed = []
    for text in equations:
        try:
            item = parseLatex(text)
        except LatexParseError as error:
            raise SolverError(f"could not read the equation '{text}'") from error
        if not isinstance(item, sympy.Eq):
            raise SolverError(f"'{text}' is not an equation")
        parsed.append(item)
    return parsed


def solveEquations(equations: list[str], positive: list[str] | None = None, ask: str | None = None) -> Solved:
    """positive: unknowns that cannot be negative or zero (lengths, ages, counts) — other roots are rejected.
    ask: what the question wants, in terms of the unknowns (e.g. '4x' for "the largest angle")."""
    solved = applyPositive(solveEquationsAnyValue(equations), positive)
    return reportAskedValue(solved, ask) if ask and ask.strip() else solved


def reportAskedValue(solved: Solved, ask: str) -> Solved:
    """The question asks for a quantity built from the unknowns: compute it from the verified solution."""
    if solved.answer.get("type") not in ("solution_set", "point"):
        return solved
    try:
        asked = parseLatex(ask)
    except LatexParseError as error:
        raise SolverError(f"could not read what the question asks for ('{ask}')") from error
    if isinstance(asked, sympy.Eq):
        return solved
    if solved.answer["type"] == "point":
        values = {sympy.Symbol(name): number(value) for name, value in solved.answer["values"].items()}
    elif len(solved.answer["values"]) == 1:
        values = {sympy.Symbol(solved.answer["variable"]): number(solved.answer["values"][0])}
    else:
        return solved  # several roots: report them all
    if not asked.free_symbols <= set(values):
        raise SolverError(f"'{ask}' uses unknowns that are not in the equations")
    if asked in values:
        if solved.answer["type"] == "point":  # helper unknowns were used, but the question asks for one of them
            solved.answer = {"type": "solution_set", "variable": str(asked), "values": [valueText(values[asked])]}
            solved.step(f"The question asks for ${tex(asked)}$.", f"{tex(asked)} = {valueText(values[asked])}")
        return solved
    result = sympy.nsimplify(asked.subs(values))
    solved.step(f"The question asks for ${tex(asked)}$.", f"{tex(asked)} = {tex(result)}")
    solved.answer = {"type": "expression", "latex": tex(result)}
    return solved


def applyPositive(solved: Solved, positive: list[str] | None) -> Solved:
    if not positive or solved.answer.get("type") != "solution_set" or solved.answer["variable"] not in positive:
        return solved
    kept = [value for value in solved.answer["values"] if number(value) > 0]
    dropped = [value for value in solved.answer["values"] if value not in kept]
    if not kept:
        raise SolverError(f"no positive value of {solved.answer['variable']} works")
    if dropped:
        solved.steps = [
            step
            for step in solved.steps
            if step["latex"] not in {f"{solved.answer['variable']} = {value}" for value in dropped}
        ]
        solved.step(f"Reject {', '.join(dropped)}: {solved.answer['variable']} must be positive here.")
        solved.answer = {**solved.answer, "values": kept}
        solved.checks.append("negative/zero values rejected (they make no sense for this quantity)")
    return solved


def solveEquationsAnyValue(equations: list[str]) -> Solved:
    parsed = parseEquations(equations)
    unknowns = sorted(set().union(*(getFreeSymbols(item) for item in parsed)), key=str)
    if len(parsed) == 1 and len(unknowns) == 1:
        return solveOneEquation(parsed[0], unknowns[0])
    if len(parsed) == 2 and len(unknowns) == 2:
        return solvePair(parsed[0], parsed[1], unknowns[0], unknowns[1])
    if len(parsed) == len(unknowns):
        return solveGeneralSystem(parsed, unknowns)
    raise SolverError(f"{len(parsed)} equation(s) with {len(unknowns)} unknown(s) cannot give a single answer")


def joinTerms(terms: list[sympy.Expr]) -> str:
    """[3x, -2x] -> '3 x - 2 x' (each term as written, not added up)."""
    text = ""
    for term in terms:
        if not text:
            text = tex(term)
        elif sympy.Mul(-1, term).could_extract_minus_sign() is False and term.could_extract_minus_sign():
            text += f" - {tex(-term)}"
        else:
            text += f" + {tex(term)}"
    return text or "0"


def transposeSteps(equation: sympy.Eq, variable: sympy.Symbol) -> list[tuple[str, str]]:
    """The school steps of a linear equation, each one move: '3x - 6 = 2x + 5' -> '3x - 2x = 5 + 6' -> 'x = 11'.
    Empty for fractional equations (their own steps stay)."""
    left, right = sympy.expand(equation.lhs), sympy.expand(equation.rhs)
    if not (left.is_polynomial(variable) and right.is_polynomial(variable)):
        return []
    def ordered(side: sympy.Expr) -> list[sympy.Expr]:  # '3x - 6', the way it is written: the x-term first
        terms = list(sympy.Add.make_args(side))
        return [term for term in terms if term.has(variable)] + [term for term in terms if not term.has(variable)]

    leftTerms, rightTerms = ordered(left), ordered(right)
    moved = [term for term in leftTerms if term.has(variable)] + [-term for term in rightTerms if term.has(variable)]
    numbers = [term for term in rightTerms if not term.has(variable) and term != 0]
    numbers += [-term for term in leftTerms if not term.has(variable) and term != 0]
    steps = [("Open the brackets and write each side out.", f"{joinTerms(leftTerms)} = {joinTerms(rightTerms)}")]
    if any(term.has(variable) for term in rightTerms) or any(not term.has(variable) for term in leftTerms if term != 0):
        steps.append((
            f"Move the {variable}-terms to the left and the numbers to the right — a term changes its sign when it crosses '='.",
            f"{joinTerms(moved)} = {joinTerms(numbers)}",
        ))
    return steps


def isAllowed(equation: sympy.Eq, variable: sympy.Symbol, root: sympy.Expr) -> bool:
    """A root must not make any denominator zero (extraneous roots of fractional equations)."""
    for side in (equation.lhs, equation.rhs):
        for denominator in [sympy.denom(term) for term in sympy.Add.make_args(sympy.together(side))]:
            if denominator.has(variable) and sympy.simplify(denominator.subs(variable, root)) == 0:
                return False
    return True


def solveOneEquation(equation: sympy.Eq, variable: sympy.Symbol) -> Solved:
    difference = sympy.together(equation.lhs - equation.rhs)
    numerator = sympy.expand(sympy.numer(difference))
    solved = Solved(answer={})
    try:
        degree = sympy.Poly(numerator, variable).degree()
    except sympy.PolynomialError:
        degree = -1
    roots = sympy.solveset(numerator, variable, domain=sympy.S.Reals)
    if roots == sympy.S.Reals:
        return Solved({"type": "text", "value": "every number is a solution", "accept": ["every", "infinite", "all"]})
    if roots == sympy.S.EmptySet and degree != 2:
        return Solved({"type": "text", "value": "no solution", "accept": ["no solution", "no real"]})
    if roots != sympy.S.EmptySet and not isinstance(roots, sympy.FiniteSet):
        raise SolverError("this equation has no simple exact solution")
    rootList = list(roots) if isinstance(roots, sympy.FiniteSet) else []  # empty: D < 0, explained below
    real = [root for root in rootList if isAllowed(equation, variable, root)]
    rejected = [root for root in rootList if root not in real]
    if degree == 1:
        coefficient = sympy.Poly(numerator, variable).coeff_monomial(variable)
        constant = -sympy.Poly(numerator, variable).coeff_monomial(1)
        for explain, latex in transposeSteps(equation, variable):
            solved.step(explain, latex)
        if not solved.steps or solved.steps[-1]["latex"] != f"{tex(coefficient * variable)} = {tex(constant)}":
            solved.step("Simplify both sides.", f"{tex(coefficient * variable)} = {tex(constant)}")
        if coefficient != 1:
            solved.step(f"Divide both sides by {tex(coefficient)}.", f"{variable} = {tex(constant / coefficient)}")
    elif degree == 2:
        a, b, c = (sympy.Poly(numerator, variable).coeff_monomial(variable**power) for power in (2, 1, 0))
        solved.step("Write it in the form ax² + bx + c = 0.", f"{tex(numerator)} = 0")
        split = findMiddleTermSplit(a, b, c)
        if split:
            p, q = split
            solved.step(
                f"Split the middle term: find two numbers whose sum is {tex(b)} and product is {tex(a * c)} — they are {tex(p)} and {tex(q)}.",
                f"{tex(a * variable**2)} {sign(p)} {tex(abs(p) * variable)} {sign(q)} {tex(abs(q) * variable)} {sign(c)} {tex(abs(c))} = 0",
            )
            solved.step("Take out the common factors.", f"{tex(sympy.factor(numerator))} = 0")
        else:
            discriminant = b**2 - 4 * a * c
            solved.step(
                "Find the discriminant D = b² − 4ac.", f"D = ({tex(b)})^2 - 4({tex(a)})({tex(c)}) = {tex(discriminant)}"
            )
            if discriminant < 0:
                solved.answer = {
                    "type": "text",
                    "value": "no real roots",
                    "accept": ["no real", "not real", "no solution"],
                }
                solved.step("D is negative, so the equation has no real roots.")
                return solved
            solved.step(
                "Use the quadratic formula x = (−b ± √D) / 2a.",
                f"{variable} = \\frac{{{tex(-b)} \\pm \\sqrt{{{tex(discriminant)}}}}}{{{tex(2 * a)}}}",
            )
    if rejected:
        solved.step(f"Reject {', '.join(valueText(root) for root in rejected)}: it makes a denominator zero.")
        solved.checks.append("extraneous roots removed")
    if not real:
        return Solved(
            {"type": "text", "value": "no solution", "accept": ["no solution", "no real"]}, solved.steps, solved.checks
        )
    for root in real:
        if sympy.simplify((equation.lhs - equation.rhs).subs(variable, root)) != 0:
            raise SolverError("a root failed the substitution check")
    solved.checks.append("each root substituted back into the equation")
    for root in real:
        solved.step("", f"{variable} = {valueText(root)}")
    solved.answer = {"type": "solution_set", "variable": str(variable), "values": [valueText(root) for root in real]}
    return solved


def sign(value: sympy.Expr) -> str:
    return "-" if value < 0 else "+"


def findMiddleTermSplit(a: sympy.Expr, b: sympy.Expr, c: sympy.Expr) -> tuple[sympy.Expr, sympy.Expr] | None:
    """Two integers p, q with p + q = b and p·q = ac (the NCERT 'splitting the middle term' method)."""
    if not all(value.is_integer for value in (a, b, c)) or a * c == 0:
        return None
    product = int(a * c)
    for p in sorted({divisor * sign for divisor in sympy.divisors(abs(product)) for sign in (1, -1)}):
        if p + product // p == b and p * (product // p) == product:
            return sympy.Integer(p), sympy.Integer(product // p)
    return None


def linearCoefficients(
    equation: sympy.Eq, x: sympy.Symbol, y: sympy.Symbol
) -> tuple[sympy.Expr, sympy.Expr, sympy.Expr]:
    side = sympy.expand(equation.lhs - equation.rhs)
    poly = sympy.Poly(side, x, y)
    if poly.total_degree() > 1:
        raise SolverError("these are not linear equations")
    return poly.coeff_monomial(x), poly.coeff_monomial(y), -poly.coeff_monomial(1)


def solvePair(first: sympy.Eq, second: sympy.Eq, x: sympy.Symbol, y: sympy.Symbol) -> Solved:
    """Two linear equations: elimination, like the NCERT method, then substitution and a check."""
    try:
        a1, b1, c1 = linearCoefficients(first, x, y)
        a2, b2, c2 = linearCoefficients(second, x, y)
    except sympy.PolynomialError:
        return solveGeneralSystem([first, second], [x, y])
    solved = Solved(answer={})

    def show(a: sympy.Expr, b: sympy.Expr, c: sympy.Expr) -> str:
        return f"{tex(a * x + b * y)} = {tex(c)}"

    solved.step(
        "Write both equations as ax + by = c.", f"{show(a1, b1, c1)} \\quad (1) \\qquad {show(a2, b2, c2)} \\quad (2)"
    )
    determinant = a1 * b2 - a2 * b1
    if determinant == 0:
        consistent = a1 * c2 == a2 * c1 and b1 * c2 == b2 * c1
        solved.step(f"a₁/a₂ = b₁/b₂ here, so the lines are {'the same line' if consistent else 'parallel'}.")
        if consistent:
            solved.answer = {
                "type": "text",
                "value": "infinitely many solutions",
                "accept": ["infinite", "many solutions", "coincident"],
            }
        else:
            solved.answer = {
                "type": "text",
                "value": "no solution",
                "accept": ["no solution", "inconsistent", "parallel"],
            }
        return solved
    # Eliminate x: make its coefficients equal, then subtract.
    if a1 == a2:
        solved.step(f"The {x}-terms are the same, so subtract (2) from (1) to remove {x}.")
        multiplier1, multiplier2 = 1, 1
    elif a1 == -a2:
        solved.step(f"The {x}-terms are opposites, so add (1) and (2) to remove {x}.")
        multiplier1, multiplier2 = 1, -1
    else:
        multiplier1, multiplier2 = a2, a1
        solved.step(
            f"Multiply (1) by {tex(a2)} and (2) by {tex(a1)} so the {x}-terms match.",
            f"{show(a1 * a2, b1 * a2, c1 * a2)} \\qquad {show(a1 * a2, b2 * a1, c2 * a1)}",
        )
        solved.step(f"Subtract to remove {x}.")
    yCoefficient = b1 * multiplier1 - b2 * multiplier2
    yConstant = c1 * multiplier1 - c2 * multiplier2
    solved.step("", f"{tex(yCoefficient * y)} = {tex(yConstant)}")
    yValue = yConstant / yCoefficient
    solved.step(f"Divide by {tex(yCoefficient)}.", f"{y} = {valueText(yValue)}")
    substituted = sympy.expand(a1 * x + b1 * yValue)
    solved.step(f"Put {y} = {valueText(yValue)} in equation (1).", f"{tex(substituted)} = {tex(c1)}")
    xValue = sympy.solve(sympy.Eq(substituted, c1), x)[0]
    solved.step("", f"{x} = {valueText(xValue)}")
    for equation in (first, second):
        if sympy.simplify((equation.lhs - equation.rhs).subs({x: xValue, y: yValue})) != 0:
            raise SolverError("the solution failed the substitution check")
    solved.step(
        "Check in both equations.",
        f"{tex(a1 * xValue + b1 * yValue)} = {tex(c1)} \\checkmark \\qquad {tex(a2 * xValue + b2 * yValue)} = {tex(c2)} \\checkmark",
    )
    solved.checks.append("solution substituted into both original equations")
    solved.answer = {"type": "point", "values": {str(x): valueText(xValue), str(y): valueText(yValue)}}
    return solved


def solveGeneralSystem(equations: list[sympy.Eq], unknowns: list[sympy.Symbol]) -> Solved:
    found = sympy.solve([item.lhs - item.rhs for item in equations], unknowns, dict=True)
    real = [item for item in found if all(value.is_real for value in item.values()) and len(item) == len(unknowns)]
    if len(real) != 1:
        raise SolverError("this system does not have exactly one real solution")
    point = real[0]
    for equation in equations:
        if sympy.simplify((equation.lhs - equation.rhs).subs(point)) != 0:
            raise SolverError("the solution failed the substitution check")
    solved = Solved({"type": "point", "values": {str(name): valueText(value) for name, value in point.items()}})
    solved.step(
        "Solve the equations together.", ", ".join(f"{name} = {valueText(value)}" for name, value in point.items())
    )
    solved.checks.append("solution substituted into every original equation")
    return solved


# ---------- arithmetic progressions ----------


def solveProgression(terms: list[Any], ask: str, n: Any = None, value: Any = None) -> Solved:
    """ask: 'nth_term' | 'sum' | 'term_number' (which term is `value`?) | 'sum_up_to' (sum till the term `value`)."""
    numbers = [number(term) for term in terms]
    if len(numbers) < 2:
        raise SolverError("an AP needs at least two terms")
    first, difference = numbers[0], numbers[1] - numbers[0]
    if any(numbers[index + 1] - numbers[index] != difference for index in range(len(numbers) - 1)):
        raise SolverError(f"{', '.join(tex(item) for item in numbers)} is not an AP: the differences are not equal")
    solved = Solved(answer={})
    solved.step(
        "First term and common difference.",
        f"a = {tex(first)}, \\quad d = {tex(numbers[1])} - {tex(first)} = {tex(difference)}",
    )
    if ask in ("term_number", "sum_up_to"):
        target = number(value)
        position = (target - first) / difference + 1
        solved.step(
            "Use aₙ = a + (n − 1)d and solve for n.",
            f"{tex(target)} = {tex(first)} + (n - 1)({tex(difference)}) \\Rightarrow n = {tex(position)}",
        )
        if not (position.is_integer and position > 0):
            raise SolverError(f"{tex(target)} is not a term of this AP")
        if ask == "term_number":
            solved.answer = {"type": "expression", "latex": tex(position)}
            solved.checks.append("the term at that position recomputed")
            return solved
        n = position
    count = number(n)
    if not (count.is_integer and count > 0):
        raise SolverError("n must be a positive whole number")
    last = first + (count - 1) * difference
    if ask == "nth_term":
        solved.step(
            "Use aₙ = a + (n − 1)d.",
            f"a_{{{tex(count)}}} = {tex(first)} + ({tex(count)} - 1)({tex(difference)}) = {tex(last)}",
        )
        if numbers[0] + (count - 1) * difference != sympy.nsimplify(sum([first] + [difference] * int(count - 1))):
            raise SolverError("term check failed")
        solved.checks.append("term rebuilt by adding d repeatedly")
        solved.trap(first + count * difference, "used aₙ = a + n·d instead of a + (n − 1)d", last)
        solved.answer = {"type": "expression", "latex": tex(last)}
        return solved
    total = count / 2 * (2 * first + (count - 1) * difference)
    solved.step(
        "Use Sₙ = n/2 [2a + (n − 1)d].",
        f"S_{{{tex(count)}}} = \\frac{{{tex(count)}}}{{2}}[2({tex(first)}) + ({tex(count)} - 1)({tex(difference)})] = {tex(count / 2)} \\times {tex(2 * first + (count - 1) * difference)} = {tex(total)}",
    )
    second = count / 2 * (first + last)
    if total != second:
        raise SolverError("the two sum formulas disagree")
    solved.step(
        "Check with Sₙ = n/2 (a + l), where l is the last term.",
        f"l = {tex(last)}, \\quad \\frac{{{tex(count)}}}{{2}}({tex(first)} + {tex(last)}) = {tex(second)} \\checkmark",
    )
    solved.checks.append("sum checked with both Sₙ = n/2[2a + (n−1)d] and Sₙ = n/2(a + l)")
    solved.trap(
        count / 2 * (first + (count - 1) * difference),
        "used Sₙ = n/2[a + (n − 1)d] — the formula needs 2a, not a",
        total,
    )
    solved.trap(count / 2 * (2 * first + count * difference), "used n·d instead of (n − 1)d in the sum formula", total)
    solved.trap(count * (2 * first + (count - 1) * difference), "forgot to divide by 2 (Sₙ = n/2 [...])", total)
    solved.answer = {"type": "expression", "latex": tex(total)}
    return solved


# ---------- statistics ----------


def solveStatistics(ask: str, values: list[Any], frequencies: list[Any] | None = None) -> Solved:
    """mean / median / mode / range of a list (optionally with frequencies).
    For grouped data, `values` are class intervals like '10-20' and the NCERT formulas are used."""
    if frequencies and all("-" in str(item).strip("-") for item in values):
        return solveGroupedStatistics(ask, values, frequencies)
    numbers = [number(item) for item in values]
    counts = [number(item) for item in frequencies] if frequencies else [sympy.Integer(1)] * len(numbers)
    if len(counts) != len(numbers) or not numbers:
        raise SolverError("each value needs a frequency")
    total = sum(counts)
    solved = Solved(answer={})
    if ask == "mean":
        weighted = sum(value * count for value, count in zip(numbers, counts, strict=True))
        solved.step(
            "Mean = sum of all observations ÷ number of observations.",
            f"\\bar{{x}} = \\frac{{{tex(weighted)}}}{{{tex(total)}}} = {tex(weighted / total)}",
        )
        result = weighted / total
        if abs(float(result) * float(total) - float(weighted)) > 1e-9:
            raise SolverError("mean check failed")
        solved.checks.append("mean × count equals the total")
        if frequencies:
            solved.trap(
                weighted / len(numbers),
                "divided by the number of different values instead of the total frequency",
                weighted / total,
            )
    elif ask == "median":
        ordered = sorted(value for value, count in zip(numbers, counts, strict=True) for _ in range(int(count)))
        size = len(ordered)
        middle = size // 2
        result = ordered[middle] if size % 2 else (ordered[middle - 1] + ordered[middle]) / 2
        solved.step("Arrange in order.", ", ".join(tex(item) for item in ordered))
        solved.step(
            f"There are {size} values, so take the {'middle value' if size % 2 else 'average of the two middle values'}.",
            f"\\text{{median}} = {tex(result)}",
        )
        solved.checks.append("values below and above the median counted")
    elif ask == "mode":
        best = max(counts)
        modes = (
            [value for value, count in zip(numbers, counts, strict=True) if count == best]
            if frequencies
            else [
                value for value in set(numbers) if numbers.count(value) == max(numbers.count(item) for item in numbers)
            ]
        )
        if len(modes) != 1:
            raise SolverError("there is more than one mode")
        result = modes[0]
        solved.step("The mode is the value that occurs most often.", f"\\text{{mode}} = {tex(result)}")
    elif ask == "range":
        result = max(numbers) - min(numbers)
        solved.step(
            "Range = highest value − lowest value.", f"{tex(max(numbers))} - {tex(min(numbers))} = {tex(result)}"
        )
    else:
        raise SolverError(f"unknown statistic '{ask}'")
    solved.answer = {"type": "expression", "latex": tex(result)}
    return solved


def solveGroupedStatistics(ask: str, intervals: list[Any], frequencies: list[Any]) -> Solved:
    bounds = []
    for item in intervals:
        low, _, high = str(item).replace("–", "-").partition("-")
        bounds.append((number(low.strip()), number(high.strip())))
    counts = [number(item) for item in frequencies]
    width = bounds[0][1] - bounds[0][0]
    total = sum(counts)
    solved = Solved(answer={})
    if ask == "mean":
        marks = [(low + high) / 2 for low, high in bounds]
        weighted = sum(mark * count for mark, count in zip(marks, counts, strict=True))
        solved.step("Class marks xᵢ = (lower + upper) / 2.", ", ".join(tex(mark) for mark in marks))
        solved.step("Mean = Σfᵢxᵢ / Σfᵢ.", f"\\frac{{{tex(weighted)}}}{{{tex(total)}}} = {tex(weighted / total)}")
        result = weighted / total
    elif ask == "median":
        cumulative, index = sympy.Integer(0), 0
        while cumulative + counts[index] < total / 2:  # find the median class
            cumulative += counts[index]
            index += 1
        low = bounds[index][0]
        result = low + (total / 2 - cumulative) / counts[index] * width
        solved.step(
            "Median class: the first class whose cumulative frequency reaches n/2.",
            f"n/2 = {tex(total / 2)}, \\quad l = {tex(low)}, \\ cf = {tex(cumulative)}, \\ f = {tex(counts[index])}, \\ h = {tex(width)}",
        )
        solved.step(
            "Median = l + ((n/2 − cf) / f) × h.",
            f"{tex(low)} + \\frac{{{tex(total / 2)} - {tex(cumulative)}}}{{{tex(counts[index])}}} \\times {tex(width)} = {tex(result)}",
        )
    elif ask == "mode":
        index = counts.index(max(counts))
        f1, f0 = counts[index], counts[index - 1] if index > 0 else 0
        f2 = counts[index + 1] if index + 1 < len(counts) else 0
        low = bounds[index][0]
        result = low + (f1 - f0) / (2 * f1 - f0 - f2) * width
        solved.step(
            "Modal class: the class with the highest frequency.",
            f"l = {tex(low)}, f_1 = {tex(f1)}, f_0 = {tex(f0)}, f_2 = {tex(f2)}, h = {tex(width)}",
        )
        solved.step("Mode = l + ((f₁ − f₀) / (2f₁ − f₀ − f₂)) × h.", f"{tex(result)}")
    else:
        raise SolverError(f"'{ask}' is not supported for grouped data")
    solved.checks.append("computed with the NCERT grouped-data formula")
    solved.answer = {"type": "expression", "latex": tex(result)}
    return solved


# ---------- HCF and LCM ----------


def solveHcfLcm(ask: str, numbers: list[Any]) -> Solved:
    values = [int(number(item)) for item in numbers]
    if len(values) < 2 or any(value <= 0 for value in values):
        raise SolverError("HCF/LCM needs two or more positive whole numbers")
    solved = Solved(answer={})
    for value in values:
        factors = sympy.factorint(value)
        solved.step(
            f"Prime factors of {value}.",
            " \\times ".join(f"{prime}^{{{power}}}" if power > 1 else str(prime) for prime, power in factors.items()),
        )
    hcf, lcm = math.gcd(*values), math.lcm(*values)
    if len(values) == 2 and hcf * lcm != values[0] * values[1]:
        raise SolverError("HCF × LCM check failed")
    if ask == "hcf":
        solved.step("HCF = product of the smallest power of each common prime.", f"\\text{{HCF}} = {hcf}")
        result = hcf
    else:
        solved.step("LCM = product of the greatest power of each prime.", f"\\text{{LCM}} = {lcm}")
        result = lcm
    if len(values) == 2:
        solved.checks.append("HCF × LCM equals the product of the two numbers")
    solved.answer = {"type": "expression", "latex": str(result)}
    return solved


# ---------- mensuration ----------

# shape -> quantity -> (formula as LaTeX, formula as a function of the dimensions)
FORMULAS: dict[str, dict[str, tuple[str, Any]]] = {
    "square": {"area": ("s^2", lambda d: d["side"] ** 2), "perimeter": ("4s", lambda d: 4 * d["side"])},
    "rectangle": {
        "area": ("l \\times b", lambda d: d["length"] * d["breadth"]),
        "perimeter": ("2(l + b)", lambda d: 2 * (d["length"] + d["breadth"])),
    },
    "triangle": {"area": ("\\frac{1}{2} \\times b \\times h", lambda d: d["base"] * d["height"] / 2)},
    "triangle_sides": {
        "area": ("\\sqrt{s(s-a)(s-b)(s-c)}", lambda d: heron(d["a"], d["b"], d["c"])),
        "perimeter": ("a + b + c", lambda d: d["a"] + d["b"] + d["c"]),
    },
    "parallelogram": {"area": ("b \\times h", lambda d: d["base"] * d["height"])},
    "trapezium": {"area": ("\\frac{1}{2}(a + b) \\times h", lambda d: (d["a"] + d["b"]) * d["height"] / 2)},
    "rhombus": {"area": ("\\frac{1}{2} d_1 d_2", lambda d: d["d1"] * d["d2"] / 2)},
    "circle": {
        "area": ("\\pi r^2", lambda d: d["pi"] * d["radius"] ** 2),
        "circumference": ("2 \\pi r", lambda d: 2 * d["pi"] * d["radius"]),
    },
    "sector": {
        "area": ("\\frac{\\theta}{360} \\pi r^2", lambda d: d["angle"] / 360 * d["pi"] * d["radius"] ** 2),
        "arc_length": ("\\frac{\\theta}{360} 2 \\pi r", lambda d: d["angle"] / 360 * 2 * d["pi"] * d["radius"]),
    },
    "cube": {
        "volume": ("a^3", lambda d: d["side"] ** 3),
        "total_surface_area": ("6a^2", lambda d: 6 * d["side"] ** 2),
        "lateral_surface_area": ("4a^2", lambda d: 4 * d["side"] ** 2),
    },
    "cuboid": {
        "volume": ("l b h", lambda d: d["length"] * d["breadth"] * d["height"]),
        "total_surface_area": (
            "2(lb + bh + hl)",
            lambda d: 2 * (d["length"] * d["breadth"] + d["breadth"] * d["height"] + d["height"] * d["length"]),
        ),
        "lateral_surface_area": ("2h(l + b)", lambda d: 2 * d["height"] * (d["length"] + d["breadth"])),
    },
    "cylinder": {
        "volume": ("\\pi r^2 h", lambda d: d["pi"] * d["radius"] ** 2 * d["height"]),
        "curved_surface_area": ("2 \\pi r h", lambda d: 2 * d["pi"] * d["radius"] * d["height"]),
        "total_surface_area": ("2 \\pi r (r + h)", lambda d: 2 * d["pi"] * d["radius"] * (d["radius"] + d["height"])),
    },
    "cone": {
        "volume": ("\\frac{1}{3} \\pi r^2 h", lambda d: d["pi"] * d["radius"] ** 2 * d["height"] / 3),
        "curved_surface_area": ("\\pi r l", lambda d: d["pi"] * d["radius"] * slant(d)),
        "total_surface_area": ("\\pi r (l + r)", lambda d: d["pi"] * d["radius"] * (slant(d) + d["radius"])),
    },
    "sphere": {
        "volume": ("\\frac{4}{3} \\pi r^3", lambda d: 4 * d["pi"] * d["radius"] ** 3 / 3),
        "surface_area": ("4 \\pi r^2", lambda d: 4 * d["pi"] * d["radius"] ** 2),
    },
    "hemisphere": {
        "volume": ("\\frac{2}{3} \\pi r^3", lambda d: 2 * d["pi"] * d["radius"] ** 3 / 3),
        "curved_surface_area": ("2 \\pi r^2", lambda d: 2 * d["pi"] * d["radius"] ** 2),
        "total_surface_area": ("3 \\pi r^2", lambda d: 3 * d["pi"] * d["radius"] ** 2),
    },
}


def heron(a: sympy.Expr, b: sympy.Expr, c: sympy.Expr) -> sympy.Expr:
    if not (a + b > c and b + c > a and a + c > b):
        raise SolverError("these three sides cannot make a triangle")
    s = (a + b + c) / 2
    return sympy.sqrt(s * (s - a) * (s - b) * (s - c))


def slant(dimensions: dict[str, sympy.Expr]) -> sympy.Expr:
    return dimensions.get("slant") or sympy.sqrt(dimensions["radius"] ** 2 + dimensions["height"] ** 2)


def solveMensuration(shape: str, quantity: str, dimensions: dict[str, Any], pi: str = "pi") -> Solved:
    formulas = FORMULAS.get(shape, {})
    if quantity not in formulas:
        raise SolverError(f"no formula for the {quantity.replace('_', ' ')} of a {shape.replace('_', ' ')}")
    values = {name: number(value) for name, value in dimensions.items() if value is not None}
    if any(value <= 0 for value in values.values()):
        raise SolverError("lengths must be positive")
    values["pi"] = {"22/7": sympy.Rational(22, 7), "3.14": sympy.Rational(314, 100)}.get(str(pi), sympy.pi)
    latexFormula, compute = formulas[quantity]
    try:
        result = sympy.nsimplify(compute(values))
    except KeyError as error:
        raise SolverError(f"the {error.args[0]} is missing") from error
    solved = Solved(answer={"type": "expression", "latex": tex(result)})
    if shape == "circle" and "radius" in values:
        radius, piValue = values["radius"], values["pi"]
        wrong = 2 * piValue * radius if quantity == "area" else piValue * radius**2
        solved.trap(wrong, "mixed up area (πr²) and circumference (2πr)", result)
        solved.trap(
            piValue * (2 * radius) ** 2 if quantity == "area" else 2 * piValue * 2 * radius,
            "used the diameter where the radius was needed",
            result,
        )
    addMensurationTraps(solved, shape, quantity, values, result)
    known = ", ".join(f"{name} = {tex(value)}" for name, value in values.items() if name != "pi")
    solved.step(
        f"Formula for the {quantity.replace('_', ' ')} of a {shape.replace('_', ' ')}.",
        f"{latexFormula}, \\quad {known}",
    )
    if shape == "triangle_sides":
        a, b, c = values["a"], values["b"], values["c"]
        half = (a + b + c) / 2
        solved.step("Semi-perimeter s = (a + b + c) / 2.", f"s = \\frac{{{tex(a)} + {tex(b)} + {tex(c)}}}{{2}} = {tex(half)}")
        solved.step(
            "Find s − a, s − b and s − c.",
            f"s - a = {tex(half - a)}, \\quad s - b = {tex(half - b)}, \\quad s - c = {tex(half - c)}",
        )
        solved.step(
            "Put them in Heron's formula.",
            f"\\sqrt{{{tex(half)} \\times {tex(half - a)} \\times {tex(half - b)} \\times {tex(half - c)}}} = "
            f"\\sqrt{{{tex(half * (half - a) * (half - b) * (half - c))}}}",
        )
    approximate = f" \\approx {float(result):.2f}" if result.has(sympy.pi) or not result.is_rational else ""
    solved.step("Put in the values.", f"{tex(result)}{approximate}")
    solved.checks.append("computed from the standard NCERT formula")
    return solved


def addMensurationTraps(
    solved: Solved, shape: str, quantity: str, values: dict[str, sympy.Expr], result: sympy.Expr
) -> None:
    """Common wrong answers for THIS question's numbers: another formula of the same shape (area vs perimeter,
    sector area vs arc length, volume vs surface area), the diameter used as the radius, a forgotten θ/360."""
    for other, (_, otherCompute) in FORMULAS.get(shape, {}).items():
        if other == quantity:
            continue
        try:
            solved.trap(otherCompute(values), f"used the {other.replace('_', ' ')} formula instead of the {quantity.replace('_', ' ')} formula", result)
        except (KeyError, SolverError, TypeError, ValueError):
            continue
    compute = FORMULAS[shape][quantity][1]
    if "radius" in values:
        try:
            solved.trap(compute({**values, "radius": 2 * values["radius"]}), "used the diameter where the radius was needed", result)
        except (KeyError, SolverError, TypeError, ValueError):
            pass
    if shape == "triangle_sides" and quantity == "area" and {"a", "b", "c"} <= set(values):
        a, b, c = values["a"], values["b"], values["c"]
        perimeter = a + b + c
        solved.trap(sympy.sqrt(perimeter * (perimeter - a) * (perimeter - b) * (perimeter - c)), "used the perimeter a + b + c as s — Heron's s is the SEMI-perimeter (a + b + c)/2", result)
    if shape == "sector" and "angle" in values:
        solved.trap(compute({**values, "angle": sympy.Integer(360)}), "forgot to multiply by θ/360 (that is the whole circle)", result)
        if quantity == "area":
            solved.trap(values["angle"] / 360 * values["pi"] * values["radius"], "forgot to square the radius (r² = r × r)", result)
    if shape == "circle" and quantity == "area" and "radius" in values:
        solved.trap(values["pi"] * values["radius"], "forgot to square the radius (r² = r × r)", result)


# ---------- interest ----------


def solveInterest(kind: str, ask: str, principal: Any, rate: Any, time: Any, periodsPerYear: Any = 1) -> Solved:
    p, r, t, k = number(principal), number(rate), number(time), number(periodsPerYear)
    solved = Solved(answer={})
    if kind == "simple":
        interest = p * r * t / 100
        solved.step(
            "Simple interest = P × R × T / 100.",
            f"\\frac{{{tex(p)} \\times {tex(r)} \\times {tex(t)}}}{{100}} = {tex(interest)}",
        )
        amount = p + interest
    else:
        amount = p * (1 + r / (100 * k)) ** (t * k)
        solved.step(
            "Amount = P(1 + R/100)ⁿ.",
            f"{tex(p)}\\left(1 + \\frac{{{tex(r / k)}}}{{100}}\\right)^{{{tex(t * k)}}} = {tex(amount)}",
        )
        interest = amount - p
        yearly = p
        for _ in range(int(t * k)):
            yearly = yearly * (1 + r / (100 * k))
        if yearly != amount:
            raise SolverError("compound interest check failed")
        solved.checks.append("amount rebuilt period by period")
    if kind == "simple":
        solved.trap(
            p * r * t if ask == "interest" else p + p * r * t,
            "forgot to divide by 100 in P × R × T / 100",
            interest if ask == "interest" else amount,
        )
    else:
        simple = p * r * t / 100
        solved.trap(
            simple if ask == "interest" else p + simple,
            "used simple interest instead of compound interest",
            interest if ask == "interest" else amount,
        )
    if ask == "amount":
        if kind == "simple":
            solved.step("Amount = P + SI.", f"{tex(p)} + {tex(interest)} = {tex(amount)}")
        result = amount
    else:
        if kind != "simple":
            solved.step("Interest = Amount − P.", f"{tex(amount)} - {tex(p)} = {tex(interest)}")
        result = interest
    solved.answer = {"type": "expression", "latex": tex(result)}
    return solved


# ---------- coordinate geometry ----------


def solveCoordinates(ask: str, points: list[list[Any]], ratio: list[Any] | None = None) -> Solved:
    coordinates = [(number(point[0]), number(point[1])) for point in points]
    solved = Solved(answer={})
    if ask == "distance" and len(coordinates) == 2:
        (x1, y1), (x2, y2) = coordinates
        result = sympy.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        solved.step(
            "Distance = √[(x₂ − x₁)² + (y₂ − y₁)²].",
            f"\\sqrt{{({tex(x2)} - {tex(x1)})^2 + ({tex(y2)} - {tex(y1)})^2}} = {tex(result)}",
        )
        solved.answer = {"type": "expression", "latex": tex(result)}
        dx, dy = x2 - x1, y2 - y1
        if dx + dy >= 0:
            solved.trap(sympy.sqrt(dx + dy), "forgot to square (x₂ − x₁) and (y₂ − y₁) inside the square root", result)
        solved.trap(dx**2 + dy**2, "forgot to take the square root at the end", result)
        solved.trap(sympy.sqrt((x2 + x1) ** 2 + (y2 + y1) ** 2), "added the coordinates instead of subtracting them", result)
    elif ask in ("midpoint", "section") and len(coordinates) == 2:
        (x1, y1), (x2, y2) = coordinates
        m, n = (
            (number(ratio[0]), number(ratio[1])) if ask == "section" and ratio else (sympy.Integer(1), sympy.Integer(1))
        )
        x, y = (m * x2 + n * x1) / (m + n), (m * y2 + n * y1) / (m + n)
        solved.step(
            "Section formula ((m x₂ + n x₁)/(m + n), (m y₂ + n y₁)/(m + n)).", f"\\left({tex(x)}, {tex(y)}\\right)"
        )
        solved.answer = {"type": "point", "values": {"x": valueText(x), "y": valueText(y)}}
    elif ask == "area" and len(coordinates) == 3:
        (x1, y1), (x2, y2), (x3, y3) = coordinates
        result = abs(x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2
        solved.step("Area = ½ |x₁(y₂ − y₃) + x₂(y₃ − y₁) + x₃(y₁ − y₂)|.", tex(result))
        solved.answer = {"type": "expression", "latex": tex(result)}
    else:
        raise SolverError(f"cannot find the {ask} from {len(coordinates)} point(s)")
    solved.checks.append("computed from the NCERT coordinate formula")
    return solved


# ---------- identities (prove that LHS = RHS) ----------


def solveIdentity(left: str, right: str) -> Solved:
    """Algebraic or trigonometric identities: SymPy checks LHS − RHS is zero for all values."""
    try:
        lhs, rhs = parseLatex(left), parseLatex(right)
    except LatexParseError as error:
        raise SolverError("could not read the identity") from error
    if not isinstance(lhs, sympy.Expr) or not isinstance(rhs, sympy.Expr):
        raise SolverError("could not read the identity")
    from app.maths.checker import areExpressionsEquivalent  # local import: checker imports nothing from here

    if areExpressionsEquivalent(lhs, rhs) is not True:
        raise SolverError("this is not an identity: the two sides are not always equal")
    solved = Solved({"type": "identity", "lhs": left, "rhs": right})
    solved.step("Start from the left side and simplify until you reach the right side.", f"{left} = {right}")
    solved.checks.append("LHS − RHS simplifies to 0 (checked at many values too)")
    return solved


def decimalText(value: sympy.Expr) -> str | None:
    """'12.27' for a rational with a terminating decimal; None otherwise (e.g. 1/3 stays a fraction)."""
    if not value.is_rational:
        return None
    rational = sympy.Rational(value)
    if not set(sympy.factorint(int(rational.q))) <= {2, 5}:
        return None
    from decimal import Decimal

    text = format(Decimal(int(rational.p)) / Decimal(int(rational.q)), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def schoolForm(value: sympy.Expr) -> sympy.Expr:
    """Exact value in the form a student writes: rational denominators for surds, e.g. (√3 + √5)/2."""
    if value.has(sympy.Float):
        value = sympy.nsimplify(value, rational=True)  # 2.5 × 0.4 -> 1, not 1.0
    if value.is_rational:
        return sympy.nsimplify(value)
    return sympy.radsimp(sympy.sqrtdenest(value))


def solveExpression(expression: str, form: str | None = None) -> Solved:
    """A number to calculate, or an expression to simplify / factorise / expand."""
    try:
        parsed = parseLatex(expression)
    except LatexParseError as error:
        raise SolverError(f"could not read '{expression}'") from error
    if isinstance(parsed, sympy.Eq):
        raise SolverError("this is an equation, not an expression")
    if parsed.free_symbols:
        result = (
            sympy.factor(parsed)
            if form == "factored"
            else sympy.expand(parsed)
            if form == "expanded"
            else sympy.simplify(parsed)
        )
        solved = Solved({"type": "expression", "latex": tex(result), "form": form})
        solved.step(
            {"factored": "Factorise.", "expanded": "Expand and collect like terms."}.get(form or "", "Simplify."),
            f"{expression} = {tex(result)}",
        )
    else:
        result = schoolForm(parsed)
        shown = decimalText(result) if re.search(r"\d\.\d", expression) else None  # decimals in, decimals out
        solved = Solved({"type": "expression", "latex": shown or tex(result)})
        solved.step("Calculate.", f"{expression} = {shown or tex(result)}")
    solved.checks.append("computed by SymPy")
    return solved


# ---------- yes/no and "which one" questions about numbers ----------


def solveProperty(check: str, value: Any = None, other: Any = None, point: list[Any] | None = None) -> Solved:
    """Is 91 prime? Is 123456 divisible by 8? Is √2 rational? Which is greater, 3/7 or 4/9? Which quadrant is (−3, 5) in?"""

    def yesNo(isTrue: bool, reason: str, explain: str) -> Solved:
        word = "yes" if isTrue else "no"
        solved = Solved({"type": "text", "value": word, "accept": [word]})
        solved.step(explain, reason)
        solved.checks.append("decided by exact computation")
        return solved

    if check == "quadrant":
        x, y = number((point or [])[0]), number((point or [])[1])
        if x == 0 or y == 0:
            name = "on an axis"
        else:
            name = {(True, True): "first", (False, True): "second", (False, False): "third", (True, False): "fourth"}[
                (x > 0, y > 0)
            ]
        solved = Solved(
            {
                "type": "text",
                "value": f"{name} quadrant" if name != "on an axis" else name,
                "accept": [name, {"first": "i ", "second": "ii", "third": "iii", "fourth": "iv"}.get(name, name)],
            }
        )
        solved.step("Look at the signs of x and y.", f"x = {tex(x)}, \\ y = {tex(y)}")
        solved.checks.append("decided from the signs of the coordinates")
        return solved
    first = number(value)
    if check == "prime":
        n = int(first)
        factors = sympy.factorint(n)
        return yesNo(
            bool(sympy.isprime(n)),
            " \\times ".join(f"{p}^{{{k}}}" if k > 1 else str(p) for p, k in factors.items()) if n > 1 else str(n),
            f"Factorise {n}.",
        )
    if check == "divisible":
        divisor = number(other)
        return yesNo(
            first % divisor == 0,
            f"{tex(first)} \\div {tex(divisor)} = {tex(first / divisor)}",
            f"Divide by {tex(divisor)}.",
        )
    if check in ("perfect_square", "perfect_cube"):
        power = 2 if check == "perfect_square" else 3
        root = sympy.integer_nthroot(int(first), power)
        return yesNo(
            root[1],
            f"\\sqrt[{power}]{{{tex(first)}}} {'=' if root[1] else '\\approx'} {tex(root[0]) if root[1] else f'{float(first) ** (1 / power):.3f}'}",
            "Find the root.",
        )
    if check in ("multiply_to_square", "multiply_to_cube", "divide_to_square", "divide_to_cube"):
        return solveSmallestFactor(int(first), 2 if check.endswith("square") else 3, check.startswith("multiply"))
    if check == "rational":
        return yesNo(bool(first.is_rational), tex(first), "A rational number can be written as p/q.")
    if check == "terminating_decimal":
        denominator = sympy.fraction(sympy.nsimplify(first))[1]
        primes = set(sympy.factorint(int(denominator)))
        return yesNo(
            primes <= {2, 5},
            f"q = {tex(denominator)}",
            "A fraction in lowest terms terminates only when q has no prime factors other than 2 and 5.",
        )
    if check == "compare":
        second = number(other)
        if first == second:
            solved = Solved({"type": "text", "value": "they are equal", "accept": ["equal", "same"]})
        else:
            bigger = first if first > second else second
            solved = Solved({"type": "expression", "latex": tex(bigger)})
        solved.step(
            "Compare the two values.",
            f"{tex(first)} \\approx {float(first):.4g}, \\quad {tex(second)} \\approx {float(second):.4g}",
        )
        solved.checks.append("compared exactly")
        return solved
    raise SolverError(f"unknown check '{check}'")


def solveSmallestFactor(value: int, power: int, multiply: bool) -> Solved:
    """Smallest number to multiply (or divide) by so that the result is a perfect square/cube (Class 8)."""
    factors = sympy.factorint(value)
    leftover = {prime: exponent % power for prime, exponent in factors.items() if exponent % power}
    if multiply:
        factor = math.prod(prime ** (power - remainder) for prime, remainder in leftover.items())
    else:
        factor = math.prod(prime**remainder for prime, remainder in leftover.items())
    result = value * factor if multiply else value // factor
    root, exact = sympy.integer_nthroot(result, power)
    if not exact:
        raise SolverError("smallest factor check failed")
    word = "square" if power == 2 else "cube"
    solved = Solved({"type": "expression", "latex": str(factor)})
    solved.step(
        f"Prime factorise {value} and group the primes in {'pairs' if power == 2 else 'triples'}.",
        " \\times ".join(f"{p}^{{{k}}}" if k > 1 else str(p) for p, k in factors.items()),
    )
    solved.step(
        f"{'Multiply' if multiply else 'Divide'} by the primes that do not complete a group.",
        f"{value} {'\\times' if multiply else '\\div'} {factor} = {result} = {root}^{power}",
    )
    solved.checks.append(f"the result {result} is a perfect {word} ({root}^{power})")
    return solved
