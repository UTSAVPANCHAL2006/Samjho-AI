# Every solver path: correct answers, its own verification, school-level steps, and refusing bad input.

import pytest
import sympy

from app.maths import checker, solvers
from app.maths.solvers import SolverError


def answerOf(solved: solvers.Solved) -> str:
    return checker.formatAnswer(solved.answer)


# ---------- Test A: simultaneous equations ----------


def testPairOfEquationsByEliminationWithSubstitutionCheck() -> None:
    solved = solvers.solveEquations(["2x + 3y = 11", "2x - 4y = -24"])
    assert solved.answer == {"type": "point", "values": {"x": "-2", "y": "5"}}
    maths = [step["latex"] for step in solved.steps]
    assert "7 y = 35" in maths and "y = 5" in maths and "2 x + 15 = 11" in maths and "x = -2" in maths
    assert "solution substituted into both original equations" in solved.checks
    x, y = sympy.symbols("x y")
    for equation in ("2x + 3y = 11", "2x - 4y = -24"):  # the test checks the substitution itself too
        parsed = checker.parseLatex(equation)
        assert sympy.simplify((parsed.lhs - parsed.rhs).subs({x: -2, y: 5})) == 0


@pytest.mark.parametrize(
    ("equations", "expected"),
    [
        (["x + y = 20", "x - y = 4"], "x = 12, y = 8"),  # Test F (the equations of the word problem)
        (["3x + 2y = 11", "2x + 3y = 4"], "x = 5, y = -2"),  # needs multiplying both equations
        (["x + y = 2", "2x + 2y = 5"], "\\text{no solution}"),
        (["x + y = 2", "2x + 2y = 4"], "\\text{infinitely many solutions}"),
        (["\\frac{x}{2} + y = 4", "x - y = 2"], "x = 4, y = 2"),
    ],
)
def testPairs(equations: list[str], expected: str) -> None:
    assert answerOf(solvers.solveEquations(equations)) == expected


# ---------- Tests C, D, E: one equation ----------


@pytest.mark.parametrize(
    ("equation", "expected"),
    [
        ("x + 4 = 9", "x = 5"),  # Test C
        ("\\frac{x}{2} + 3 = 7", "x = 8"),  # Test D
        ("x^2 - 5x + 6 = 0", "x = 2 \\text{ or } x = 3"),  # Test E
        ("2(x - 3) = -4", "x = 1"),
        ("0.5x - 1.5 = 2", "x = 7"),
        ("x^2 - 2x - 2 = 0", "x = 1 + \\sqrt{3} \\text{ or } x = 1 - \\sqrt{3}"),
        ("x^2 + x + 1 = 0", "\\text{no real roots}"),
        ("\\frac{x^2}{x-1} = \\frac{1}{x-1}", "x = -1"),  # x = 1 makes the denominator zero
    ],
)
def testOneEquation(equation: str, expected: str) -> None:
    assert answerOf(solvers.solveEquations([equation])) == expected


def testQuadraticStepsUseFactorisation() -> None:
    maths = [step["latex"] for step in solvers.solveEquations(["x^2 - 5x + 6 = 0"]).steps]
    assert "x^{2} - 3 x - 2 x + 6 = 0" in maths and "(x - 3) (x - 2) = 0" in maths


# ---------- Test B: arithmetic progression ----------


def testApSumUsesBothFormulasAndCatchesTheMissingA() -> None:
    solved = solvers.solveProgression([2, 7, 12, 17], "sum", n=20)
    assert solved.answer["latex"] == "990"
    formulaStep = solved.steps[1]["latex"]
    assert "2(2)" in formulaStep and "= 990" in formulaStep  # 2a, not a
    assert any("n/2(a + l)" in check for check in solved.checks)
    wrongFormula = sympy.Rational(20, 2) * (2 + 19 * 5)  # S = n/2 [a + (n-1)d]: the bug that was reported
    assert wrongFormula == 970 and solved.answer["latex"] != "970"
    assert {"value": "970", "mistake": "used Sₙ = n/2[a + (n − 1)d] — the formula needs 2a, not a"} in solved.traps


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (([3, 8], "nth_term", 10, None), "48"),
        (([3, 8, 13], "term_number", None, 78), "16"),
        (([-5, -2], "sum", 10, None), "85"),
        ((["1/2", "1"], "nth_term", 5, None), "\\frac{5}{2}"),
        (([2, 7], "sum_up_to", None, 97), "990"),
    ],
)
def testProgressions(args: tuple, expected: str) -> None:  # type: ignore[type-arg]
    assert answerOf(solvers.solveProgression(*args)) == expected


def testNotAnApIsRefusedNotSolved() -> None:
    with pytest.raises(SolverError, match="not an AP"):
        solvers.solveProgression([2, 5, 9], "sum", n=5)


# ---------- Test G and other statistics ----------


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("mean", [2, 4, 6, 8, 10]), "6"),  # Test G
        (("median", [7, 3, 9, 1]), "5"),
        (("median", [7, 3, 9]), "7"),
        (("mode", [2, 3, 3, 5]), "3"),
        (("range", [12, 3, 25]), "22"),
        (("mean", [10, 20, 30], [1, 2, 1]), "20"),
        (("mean", ["0-10", "10-20", "20-30"], [5, 10, 5]), "15"),
        (("median", ["0-10", "10-20", "20-30", "30-40"], [5, 10, 15, 10]), "\\frac{70}{3}"),
    ],
)
def testStatistics(args: tuple, expected: str) -> None:  # type: ignore[type-arg]
    assert answerOf(solvers.solveStatistics(*args)) == expected


# ---------- other families ----------


@pytest.mark.parametrize(
    ("solve", "expected"),
    [
        (lambda: solvers.solveHcfLcm("hcf", [12, 18]), "6"),
        (lambda: solvers.solveHcfLcm("lcm", [12, 18]), "36"),
        (lambda: solvers.solveMensuration("circle", "area", {"radius": 7}, "22/7"), "154"),
        (lambda: solvers.solveMensuration("cylinder", "volume", {"radius": 7, "height": 10}, "22/7"), "1540"),
        (lambda: solvers.solveMensuration("triangle_sides", "area", {"a": 13, "b": 14, "c": 15}), "84"),
        (
            lambda: solvers.solveMensuration("cuboid", "total_surface_area", {"length": 5, "breadth": 4, "height": 3}),
            "94",
        ),
        (lambda: solvers.solveMensuration("cone", "curved_surface_area", {"radius": 3, "height": 4}, "pi"), "15 \\pi"),
        (lambda: solvers.solveInterest("simple", "interest", 5000, 8, 3), "1200"),
        (lambda: solvers.solveInterest("compound", "amount", 20000, 10, 2), "24200"),
        (lambda: solvers.solveCoordinates("distance", [[1, 2], [4, 6]]), "5"),
        (lambda: solvers.solveCoordinates("section", [[1, 2], [7, 8]], [1, 2]), "x = 3, y = 4"),
        (lambda: solvers.solveCoordinates("area", [[0, 0], [4, 0], [0, 3]]), "6"),
        (lambda: solvers.solveExpression("(x+5)^2", "expanded"), "x^{2} + 10 x + 25"),
        (lambda: solvers.solveExpression("2^{5} \\cdot 2^{-3}"), "4"),
        (
            lambda: solvers.solveIdentity("\\sin^2 \\theta + \\cos^2 \\theta", "1"),
            "\\sin^2 \\theta + \\cos^2 \\theta = 1",
        ),
    ],
)
def testOtherFamilies(solve, expected: str) -> None:  # type: ignore[no-untyped-def]
    assert answerOf(solve()) == expected


@pytest.mark.parametrize(
    "solve",
    [
        lambda: solvers.solveMensuration("triangle_sides", "area", {"a": 1, "b": 2, "c": 5}),  # not a triangle
        lambda: solvers.solveIdentity("(a+b)^2", "a^2 + b^2"),  # not an identity
        lambda: solvers.solveEquations(["x + y = 3"]),  # one equation, two unknowns
        lambda: solvers.solveMensuration("circle", "area", {}),  # radius missing
    ],
)
def testImpossibleOrIncompleteInputIsRefused(solve) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SolverError):
        solve()


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (("prime", 91), "\\text{no}"),
        (("prime", 97), "\\text{yes}"),
        (("divisible", 123456, 8), "\\text{yes}"),
        (("perfect_cube", 2744), "\\text{yes}"),
        (("perfect_square", 50), "\\text{no}"),
        (("rational", "\\sqrt{2}"), "\\text{no}"),
        (("terminating_decimal", "3/8"), "\\text{yes}"),
        (("terminating_decimal", "1/3"), "\\text{no}"),
        (("compare", "3/7", "4/9"), "\\frac{4}{9}"),
    ],
)
def testYesNoAndComparisonQuestions(args: tuple, expected: str) -> None:  # type: ignore[type-arg]
    assert answerOf(solvers.solveProperty(*args)) == expected


def testQuadrant() -> None:
    assert answerOf(solvers.solveProperty("quadrant", point=[-3, 5])) == "\\text{second quadrant}"


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("\\frac{1}{\\sqrt{5} - \\sqrt{3}}", "\\frac{\\sqrt{3} + \\sqrt{5}}{2}"),  # used to come out as √(√15/2 + 2)
        ("\\frac{3}{2+\\sqrt{3}}", "6 - 3 \\sqrt{3}"),
        ("\\sqrt{12}", "2 \\sqrt{3}"),
        ("30 \\tan 30^\\circ", "10 \\sqrt{3}"),
    ],
)
def testSurdsAreInSchoolForm(expression: str, expected: str) -> None:
    assert answerOf(solvers.solveExpression(expression)) == expected


def testPositiveQuantitiesRejectNegativeRoots() -> None:
    solved = solvers.solveEquations(["s^2 = 81"], positive=["s"])
    assert answerOf(solved) == "s = 9" and any("must be positive" in step["explain"] for step in solved.steps)


def testTheAskedQuantityIsReportedNotJustTheUnknown() -> None:
    """'Angles in the ratio 2:3:4 — find the LARGEST angle' must answer 80, not x = 20."""
    solved = solvers.solveEquations(["2x + 3x + 4x = 180"], ask="4x")
    assert answerOf(solved) == "80" and solved.steps[-1]["latex"] == "4 x = 80"
    assert answerOf(solvers.solveEquations(["x + y = 9", "x - y = 3"], ask="10x + y")) == "63"


def testHelperUnknownsAreNotPartOfTheAnswer() -> None:
    """'An angle is 4 times its supplement': x = 4y, x + y = 180 — the answer is the angle x only."""
    assert answerOf(solvers.solveEquations(["x = 4y", "x + y = 180"], ask="x")) == "x = 144"


@pytest.mark.parametrize(
    ("check", "value", "expected"),
    [
        ("multiply_to_cube", 1080, "25"),
        ("multiply_to_square", 1008, "7"),
        ("divide_to_square", 252, "7"),
        ("divide_to_cube", 8640, "5"),
    ],
)
def testSmallestFactorForPerfectPowers(check: str, value: int, expected: str) -> None:
    assert answerOf(solvers.solveProperty(check, value)) == expected


def testMensurationAndDistanceKnowTheCommonWrongFormulas() -> None:
    sector = solvers.solveMensuration("sector", "area", {"radius": 6, "angle": 60}, "22/7")
    assert {"value": "\\frac{44}{7}", "mistake": "used the arc length formula instead of the area formula"} in sector.traps
    distance = solvers.solveCoordinates("distance", [[2, 3], [4, 1]])
    assert any(trap["value"] == "0" and "square" in trap["mistake"] for trap in distance.traps)
