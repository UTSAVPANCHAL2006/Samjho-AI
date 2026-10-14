# One right and one typical wrong working for each important Class 6-10 topic, graded with no AI.
# A right working must get full marks with no ✗; a wrong one must lose marks with a ✗ — including the wrong
# methods that happen to give the right number (a lost square that cancels, 2 × 2 = 2 + 2 in an exponent).

from typing import Any

import pytest

from app.agents.grading import runGrading
from tests.conftest import FakeAi


def E(latex: str) -> dict[str, Any]:
    return {"type": "expression", "latex": latex}


def S(variable: str, *values: str) -> dict[str, Any]:
    return {"type": "solution_set", "variable": variable, "values": list(values)}


def P(**values: str) -> dict[str, Any]:
    return {"type": "point", "values": values}


# (topic, question text, expressions, answer, marks, right lines, wrong lines)
CASES = [
    ("fraction add", "Add 2/3 + 1/4", ["\\frac{2}{3} + \\frac{1}{4}"], E("\\frac{11}{12}"), 2,
     ["= \\frac{8}{12} + \\frac{3}{12}", "= \\frac{11}{12}"], ["= \\frac{2 + 1}{3 + 4}", "= \\frac{3}{7}"]),
    ("integers", "Evaluate (-7) + 12 - (-5)", ["(-7) + 12 - (-5)"], E("10"), 2,
     ["= 5 - (-5)", "= 5 + 5", "= 10"], ["= 5 - (-5)", "= 5 - 5", "= 0"]),
    ("linear", "Solve 3x + 5 = 20", ["3x + 5 = 20"], S("x", "5"), 2,
     ["3x = 20 - 5", "3x = 15", "x = 5"], ["3x = 20 + 5", "3x = 25", "x = 25/3"]),
    ("distributive", "Solve 3(x - 2) = 15", ["3(x - 2) = 15"], S("x", "7"), 2,
     ["3x - 6 = 15", "3x = 21", "x = 7"], ["3x - 2 = 15", "3x = 17", "x = 17/3"]),
    ("exponent product", "Simplify 2^3 \\times 2^4", ["2^3 \\times 2^4"], E("128"), 2,
     ["= 2^{3 + 4}", "= 2^7", "= 128"], ["= 2^{3 \\times 4}", "= 2^{12}", "= 4096"]),
    ("exponent product coincidence", "Simplify 3^2 \\times 3^2", ["3^2 \\times 3^2"], E("81"), 2,
     ["= 3^{2 + 2}", "= 3^4", "= 81"], ["= 3^{2 \\times 2}", "= 3^4", "= 81"]),
    ("negative exponent", "Evaluate 2^{-3}", ["2^{-3}"], E("\\frac{1}{8}"), 2,
     ["= \\frac{1}{2^3}", "= \\frac{1}{8}"], ["= -2^3", "= -8"]),
    ("square root", "Find \\sqrt{144}", ["\\sqrt{144}"], E("12"), 1, ["= \\sqrt{12 \\times 12}", "= 12"], ["= 144 / 2", "= 72"]),
    ("percentage", "Find 15% of 240", ["\\frac{15}{100} \\times 240"], E("36"), 2,
     ["= \\frac{15 \\times 240}{100}", "= \\frac{3600}{100}", "= 36"], ["= 15 \\times 240", "= 3600"]),
    ("simple interest", "Find the SI on Rs 5000 at 8% for 3 years", ["\\frac{5000 \\times 8 \\times 3}{100}"], E("1200"), 2,
     ["SI = \\frac{5000 \\times 8 \\times 3}{100}", "= 1200"], ["SI = 5000 \\times 8 \\times 3", "= 120000"]),
    ("compound interest", "Find the amount on Rs 1000 at 10% for 2 years compounded annually", ["1000(1 + \\frac{10}{100})^2"], E("1210"), 3,
     ["A = 1000(1 + 10/100)^2", "= 1000 \\times 1.21", "= 1210"], ["A = 1000 + 1000 \\times 10 \\times 2/100", "= 1000 + 200", "= 1200"]),
    ("unitary", "If 5 pens cost Rs 60, find the cost of 8 pens", ["\\frac{60}{5} \\times 8"], E("96"), 2,
     ["\\text{Cost of 1 pen} = 60/5 = 12", "\\text{Cost of 8 pens} = 12 \\times 8 = 96"], ["= 60 \\times 8", "= 480"]),
    ("rectangle perimeter", "Find the perimeter of a rectangle 8 cm by 5 cm", ["2(8 + 5)"], E("26"), 2,
     ["P = 2(l + b)", "= 2(8 + 5)", "= 26"], ["P = l + b", "= 8 + 5", "= 13"]),
    ("circle area", "Find the area of a circle of radius 7 cm (pi = 22/7)", ["\\frac{22}{7} \\times 7^2"], E("154"), 2,
     ["A = \\pi r^2", "= \\frac{22}{7} \\times 7 \\times 7", "= 154"], ["A = 2 \\pi r", "= 2 \\times \\frac{22}{7} \\times 7", "= 44"]),
    ("cylinder volume", "Volume of a cylinder r = 7 cm, h = 10 cm (pi = 22/7)", ["\\frac{22}{7} \\times 7^2 \\times 10"], E("1540"), 3,
     ["V = \\pi r^2 h", "= \\frac{22}{7} \\times 49 \\times 10", "= 1540"], ["V = 2 \\pi r h", "= 2 \\times \\frac{22}{7} \\times 7 \\times 10", "= 440"]),
    ("pythagoras", "Find the hypotenuse of a right triangle with legs 6 cm and 8 cm", ["\\sqrt{6^2 + 8^2}"], E("10"), 2,
     ["h^2 = 6^2 + 8^2", "h^2 = 36 + 64", "h^2 = 100", "h = 10"], ["h = 6 + 8", "h = 14"]),
    ("ap nth", "Find the 10th term of the AP 3, 7, 11, ...", ["3 + (10 - 1) \\times 4"], E("39"), 2,
     ["a_{10} = 3 + (10 - 1) \\times 4", "= 3 + 36", "= 39"], ["a_{10} = 3 + 10 \\times 4", "= 43"]),
    ("ap sum", "Sum of first 10 terms of 2, 5, 8, ...", ["\\frac{10}{2}(2 \\times 2 + 9 \\times 3)"], E("155"), 3,
     ["S_{10} = \\frac{10}{2}[2(2) + 9 \\times 3]", "= 5 \\times 31", "= 155"], ["S_{10} = \\frac{10}{2}[2 + 9 \\times 3]", "= 5 \\times 29", "= 145"]),
    ("quadratic factor", "Solve x^2 - 5x + 6 = 0", ["x^2-5x+6=0"], S("x", "2", "3"), 3,
     ["(x - 2)(x - 3) = 0", "x = 2", "x = 3"], ["(x + 2)(x + 3) = 0", "x = -2", "x = -3"]),
    ("pair linear", "Solve x + y = 10 and x - y = 2", ["x + y = 10", "x - y = 2"], P(x="6", y="4"), 3,
     ["2x = 12", "x = 6", "6 + y = 10", "y = 4"], ["2x = 12", "x = 6", "6 + y = 10", "y = 16"]),
    ("distance", "Distance between (1, 2) and (4, 6)", ["\\sqrt{(4-1)^2 + (6-2)^2}"], E("5"), 2,
     ["d = \\sqrt{(4 - 1)^2 + (6 - 2)^2}", "= \\sqrt{9 + 16}", "= \\sqrt{25}", "= 5"], ["d = (4 - 1) + (6 - 2)", "= 7"]),
    ("midpoint", "Midpoint of (2, 4) and (6, 8)", [], P(x="4", y="6"), 2,
     ["x = \\frac{2 + 6}{2} = 4", "y = \\frac{4 + 8}{2} = 6"], ["x = \\frac{6 - 2}{2} = 2", "y = \\frac{8 - 4}{2} = 2"]),
    ("trig values", "Evaluate sin^2 30° + cos^2 60°", ["\\sin^2 30^\\circ + \\cos^2 60^\\circ"], E("\\frac{1}{2}"), 2,
     ["= (1/2)^2 + (1/2)^2", "= 1/4 + 1/4", "= 1/2"], ["= 1/2 + 1/2", "= 1"]),
    ("trig coincidence", "Evaluate 2tan^2 45° + cos^2 30° - sin^2 60°", ["2 \\tan^2 45^\\circ + \\cos^2 30^\\circ - \\sin^2 60^\\circ"], E("2"), 2,
     ["= 2(1)^2 + (\\sqrt{3}/2)^2 - (\\sqrt{3}/2)^2", "= 2 + 3/4 - 3/4", "= 2"], ["= 2(1) + \\sqrt{3}/2 - \\sqrt{3}/2", "= 2"]),
    ("trig coincidence 2", "Evaluate sin^2 45° + cos^2 45°", ["\\sin^2 45^\\circ + \\cos^2 45^\\circ"], E("1"), 2,
     ["= (1/\\sqrt{2})^2 + (1/\\sqrt{2})^2", "= 1/2 + 1/2", "= 1"], ["= 1/\\sqrt{2} + 1/\\sqrt{2}", "= 2/\\sqrt{2}", "= \\sqrt{2}"]),
    ("probability", "A die is thrown once. Find P(even number)", ["\\frac{3}{6}"], E("\\frac{1}{2}"), 1,
     ["P = 3/6", "= 1/2"], ["P = 2/6", "= 1/3"]),
    ("mean", "Find the mean of 4, 6, 8, 10, 12", ["\\frac{4 + 6 + 8 + 10 + 12}{5}"], E("8"), 2,
     ["\\text{Sum} = 40", "\\text{Mean} = 40/5 = 8"], ["\\text{Sum} = 40", "\\text{Mean} = 40/2 = 20"]),
    ("hcf lcm", "HCF(12, 18) = 6. Find LCM(12, 18)", ["\\frac{12 \\times 18}{6}"], E("36"), 2,
     ["LCM = \\frac{12 \\times 18}{6}", "= \\frac{216}{6}", "= 36"], ["LCM = 12 + 18 - 6", "= 24"]),
    ("identity expand", "Expand (x + 3)^2", ["(x+3)^2"], E("x^2 + 6x + 9", ), 2,
     ["= x^2 + 2 \\times x \\times 3 + 3^2", "= x^2 + 6x + 9"], ["= x^2 + 3^2", "= x^2 + 9"]),
    ("factorise", "Factorise x^2 - 16", ["x^2 - 16"], {"type": "expression", "latex": "(x-4)(x+4)", "form": "factored"}, 2,
     ["= x^2 - 4^2", "= (x - 4)(x + 4)"], ["= (x - 4)^2"]),
    ("surds", "Simplify (5 + \\sqrt{3})(5 - \\sqrt{3})", ["(5 + \\sqrt{3})(5 - \\sqrt{3})"], E("22"), 2,
     ["= 5^2 - (\\sqrt{3})^2", "= 25 - 3", "= 22"], ["= 5^2 - (\\sqrt{3})^2", "= 25 - 9", "= 16"]),
    ("cube root", "Find \\sqrt[3]{216}", ["\\sqrt[3]{216}"], E("6"), 2,
     ["216 = 2^3 \\times 3^3", "\\sqrt[3]{216} = 2 \\times 3 = 6"], ["216 = 2^3 \\times 3^3", "\\sqrt[3]{216} = 2^3 \\times 3", "= 24"]),
    ("triangle angle", "Two angles of a triangle are 40° and 70°. Find the third angle.", ["x + 40 + 70 = 180"], S("x", "70"), 2,
     ["x + 40 + 70 = 180", "x = 180 - 110", "x = 70"], ["x + 40 + 70 = 360", "x = 360 - 110", "x = 250"]),
]



def grade(question: dict[str, Any], lines: list[str]) -> Any:
    state = {"question": question, "lines": [{"latex": line, "confidence": 1.0} for line in lines], "confidenceThreshold": 0.8}
    return runGrading(FakeAi(), state)  # type: ignore[arg-type]


@pytest.mark.parametrize(("topic", "text", "expressions", "answer", "marks", "right", "wrong"), CASES, ids=[case[0] for case in CASES])
def testRightIsRightAndWrongIsWrong(
    topic: str, text: str, expressions: list[str], answer: dict[str, Any], marks: int, right: list[str], wrong: list[str]
) -> None:
    question = {"text": text, "expressions": expressions, "answer": answer, "marks": marks, "class_level": 8, "traps": []}
    rightResult = grade(question, right)
    assert rightResult["score"] == marks, f"{topic}: a right working lost marks"
    assert all(step["verdict"] != "incorrect" for step in rightResult["steps"]), f"{topic}: a right line got a ✗"
    wrongResult = grade(question, wrong)
    assert wrongResult["wrongLine"] is not None and wrongResult["score"] < marks, f"{topic}: the mistake was not caught"
