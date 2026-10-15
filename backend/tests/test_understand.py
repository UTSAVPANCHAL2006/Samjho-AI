# Understanding a question -> a verified answer, or an honest, specific reason why not (fake AI, no network).

from typing import Any

import pytest

from app.agents.understand import readExplicitEquations, understandQuestion
from app.maths import checker
from tests.conftest import FakeAi

PLAN = "ONLY to understand it"  # a piece of the planning prompt, so FakeAi knows which call this is


def plan(family: str, params: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "scope": "maths",
        "question": "q",
        "class_level": 10,
        "chapter": "Arithmetic Progressions",
        "missing": None,
        "ambiguous": None,
        "parts": [{"text": "q", "family": family, "params": params}],
        **extra,
    }


def answerOf(result: Any) -> str:
    assert result.status == "solved", result.message
    return checker.formatAnswer(result.parts[0]["answer"])


# Test A — the reported failure: must be solved, even with no AI at all
PAIR_FORMS = [
    "Solve the following pair of linear equations for x and y:\n2x + 3y = 11\n2x - 4y = -24",
    "Solve: 2x + 3y = 11, 2x − 4y = −24",  # Unicode minus signs
    "2x+3y=11\n\n   2x -4y = -24  ",  # messy whitespace
    "Solve 2x + 3y = 11 and 2x - 4y = -24",
    "Q1. Solve for x and y: 2x + 3y = 11; 2x – 4y = –24",  # en dashes, question number
]


@pytest.mark.parametrize("text", PAIR_FORMS)
def testPairIsSolvedFromTheTextWithoutAi(text: str, ai: FakeAi) -> None:
    result = understandQuestion(text, ai)
    assert answerOf(result) == "x = -2, y = 5"
    assert "solution substituted into both original equations" in result.parts[0]["checks"]
    assert not any(call.startswith("second") for call in ai.calls)  # nothing to double-check: no AI reading used


def testWrongAiArithmeticCanNoLongerRejectAValidQuestion(ai: FakeAi) -> None:
    """Root cause of failure A: the AI's own (wrong) mental arithmetic used to veto SymPy's correct answer."""
    ai.json[PLAN] = plan("equations", {"equations": ["2x + 3y = 11", "2x - 4y = -24"]}, answer="x = -1, y = 5")
    assert (
        answerOf(
            understandQuestion(
                "Solve the following pair of linear equations: 2x + 3y = 11 and 2x - 4y = -24 graphically", ai
            )
        )
        == "x = -2, y = 5"
    )


# Test B — the AP from the report: numbers come from the question, solver uses both formulas
def testApSum(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("progression", {"terms": [2, 7, 12, 17], "ask": "sum", "n": 20})
    result = understandQuestion("An AP is 2, 7, 12, 17, ... Find the sum of the first 20 terms.", ai)
    assert answerOf(result) == "990"
    assert any("n/2(a + l)" in check for check in result.parts[0]["checks"])
    assert not any(call.startswith("second") for call in ai.calls)  # every number is in the question


@pytest.mark.parametrize(
    ("text", "expected"),
    [("x + 4 = 9", "x = 5"), ("Solve x/2 + 3 = 7.", "x = 8"), ("Solve x² - 5x + 6 = 0.", "x = 2 \\text{ or } x = 3")],
)
def testSingleEquationsCDE(text: str, expected: str, ai: FakeAi) -> None:
    assert answerOf(understandQuestion(text, ai)) == expected


# Test F — a word problem: the AI turns words into equations, so a second model must agree
def testWordProblemNeedsTwoAgreeingReadings(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("equations", {"equations": ["x + y = 20", "x - y = 4"]})
    result = understandQuestion("The sum of two numbers is 20 and their difference is 4. Find the numbers.", ai)
    assert answerOf(result) == "x = 12, y = 8"
    assert "a second, independent reading of the question gave the same answer" in result.parts[0]["checks"]


def testThreeDisagreeingReadingsAreNotGuessed(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("equations", {"equations": ["x + y = 20", "x - y = 4"]})
    ai.secondJson[PLAN] = plan("equations", {"equations": ["x + y = 20", "x = 4y"]})
    ai.thirdJson[PLAN] = plan("equations", {"equations": ["x + y = 20", "x - y = 6"]})
    result = understandQuestion("The sum of two numbers is 20 and their difference is 4. Find the numbers.", ai)
    assert result.status == "verification_failed" and result.parts == []


def testTwoOfThreeReadingsDecide(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("equations", {"equations": ["180 - x = 4x"]})  # a misreading
    ai.secondJson[PLAN] = plan("equations", {"equations": ["x = 4(180 - x)"]})
    ai.thirdJson[PLAN] = plan("equations", {"equations": ["x = 4(180 - x)"]})
    result = understandQuestion("An angle is 4 times its supplement. Find the angle.", ai)
    assert answerOf(result) == "x = 144" and "2 of 3 independent readings gave this answer" in result.parts[0]["checks"]


def testWrongMethodIsReReadOnce(ai: FakeAi) -> None:
    """The AI called 1, 4, 9, 16 an AP; the solver refuses, the question is re-read with that reason."""

    def reading(user: str) -> dict[str, Any]:
        if "wrong because 1, 4, 9, 16 is not an AP" in user:
            return plan("expression", {"expression": "10^2"})
        return plan("progression", {"terms": [1, 4, 9, 16], "ask": "nth_term", "n": 10})

    ai.json[PLAN] = reading
    result = understandQuestion("What is the 10th number in the pattern 1, 4, 9, 16, ...?", ai)
    assert answerOf(result) == "100"


def testReReadThatSaysUnsupportedIsReportedHonestly(ai: FakeAi) -> None:
    """Regression: the first reading was nonsense, the re-read said "unsupported", but the student was asked to clarify."""

    def reading(user: str) -> dict[str, Any]:
        if "wrong because" in user:
            return plan("unsupported", {"reason": "naming a congruence rule is not a calculation"})
        return plan("property", {"check": "prime", "value": None})

    ai.json[PLAN] = reading
    result = understandQuestion(
        "In triangles ABC and PQR, AB = PQ, BC = QR and CA = RP. Which congruence rule applies?", ai
    )
    assert result.status == "unsupported"
    assert "congruence rule" in (result.message or "")


def testAngleAnswerIsInDegrees(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("expression", {"expression": "180^\\circ - 50^\\circ - 60^\\circ"})
    assert answerOf(understandQuestion("Two angles of a triangle are 50° and 60°. Find the third angle.", ai)) == "70"


def testAnEquationReadingConfirmsANumberReading(ai: FakeAi) -> None:
    """Regression: an empty second reading was read as the letters N·o·n·e, and 'x = 70' did not count as agreeing with 70."""
    ai.json[PLAN] = plan("expression", {"expression": "180 - (50 + 60)"})
    ai.secondJson[PLAN] = plan("expression", {})
    ai.thirdJson[PLAN] = plan("equations", {"equations": ["50 + 60 + x = 180"], "ask": "x"})
    result = understandQuestion("Two angles of a triangle are 50° and 60°. Find the third angle.", ai)
    assert answerOf(result) == "70"
    assert "2 of 3 independent readings gave this answer" in result.parts[0]["checks"]


# Test G
def testMean(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("statistics", {"ask": "mean", "values": [2, 4, 6, 8, 10]})
    assert answerOf(understandQuestion("Find the mean of 2, 4, 6, 8, 10.", ai)) == "6"


def testNumbersNotInTheQuestionTriggerASecondReading(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("statistics", {"ask": "mean", "values": [2, 4, 6, 8, 11]})  # 11 is not in the question
    ai.secondJson[PLAN] = plan("statistics", {"ask": "mean", "values": [2, 4, 6, 8, 10]})
    ai.thirdJson[PLAN] = plan("statistics", {"ask": "mean", "values": [2, 4, 6, 8, 10]})
    result = understandQuestion("Find the mean of 2, 4, 6, 8, 10.", ai)
    assert answerOf(result) == "6"  # the misread 11 lost 2-to-1


# Test H — genuinely ambiguous input: a specific question, not a fabricated solution
def testAmbiguousInputAsksOneSpecificQuestion(ai: FakeAi) -> None:
    ai.json[PLAN] = plan(
        "expression", {"expression": "x"}, ambiguous="Is it 3/4x (three by 4x) or (3/4)x (three-fourths of x)?"
    )
    result = understandQuestion("Solve 3/4x = 6", ai)
    assert result.status == "needs_clarification" and "3/4x" in (result.message or "") and result.parts == []


# Test I — incomplete input: say what is missing
def testIncompleteQuestionSaysWhatIsMissing(ai: FakeAi) -> None:
    ai.json[PLAN] = plan(
        "mensuration",
        {"shape": "circle", "quantity": "area", "dimensions": {}},
        missing="the radius or diameter of the circle",
    )
    result = understandQuestion("Find the area of the circle.", ai)
    assert result.status == "needs_clarification" and "radius" in (result.message or "")


def testIncompleteEquationsAreNotSolved(ai: FakeAi) -> None:
    result = understandQuestion("Solve x + y = 10", ai)  # one equation, two unknowns
    assert result.status == "needs_clarification" and result.understood == ["x + y = 10"]


def testImpossibleNumbersAreQuestionedNotSolved(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("progression", {"terms": [2, 5, 9], "ask": "sum", "n": 10})
    result = understandQuestion("Find the sum of 10 terms of the AP 2, 5, 9, ...", ai)
    assert result.status == "needs_clarification" and "not an AP" in (result.message or "")


# Test J — formatting variations mean the same thing
@pytest.mark.parametrize("text", ["x² − 9 = 0", "x^2 - 9 = 0", "x^{2}-9=0", "x ^ 2 - 9 = 0", " x²-9 = 0\n"])
def testFormattingVariationsGiveTheSameAnswer(text: str, ai: FakeAi) -> None:
    assert answerOf(understandQuestion(text, ai)) == "x = -3 \\text{ or } x = 3"


def testQuestionsThatAskMoreThanSolvingGoToTheAi() -> None:
    assert readExplicitEquations("If 2x + 3 = 11, find the value of 4x + 1") is None  # asks for 4x + 1, not x
    assert readExplicitEquations("Solve: 2x + 3 = 11") == ["2x + 3 = 11"]


def testOutOfScopeAndUnsupported(ai: FakeAi) -> None:
    ai.json[PLAN] = {"scope": "not_maths", "parts": []}
    assert understandQuestion("Who won the 2011 world cup?", ai).status == "not_maths"
    ai.json[PLAN] = plan("unsupported", {"reason": "a geometric proof"})
    result = understandQuestion("Prove that the angles opposite equal sides are equal.", ai)
    assert result.status == "unsupported" and "geometric proof" in (result.message or "")


def testMultiPartQuestionsKeepEveryPart(ai: FakeAi) -> None:
    ai.json[PLAN] = {
        **plan("progression", {"terms": [3, 7], "ask": "nth_term", "n": 10}),
        "parts": [
            {"text": "(a) 10th term", "family": "progression", "params": {"terms": [3, 7], "ask": "nth_term", "n": 10}},
            {
                "text": "(b) sum of 10 terms",
                "family": "progression",
                "params": {"terms": [3, 7], "ask": "sum", "n": 10},
            },
        ],
    }
    result = understandQuestion(
        "For the AP 3, 7, ...: (a) find the 10th term (b) find the sum of the first 10 terms.", ai
    )
    assert [checker.formatAnswer(part["answer"]) for part in result.parts] == ["39", "210"]


def testOfflineStillSolvesTypedEquations(ai: FakeAi) -> None:
    ai.isAvailable = lambda kind="text": False  # type: ignore[method-assign]
    assert answerOf(understandQuestion("3x + 7 = 22", ai)) == "x = 5"
    assert understandQuestion("Find the mean of 2, 4, 6", ai).status == "parse_failed"


def testYesNoQuestionsAreAnsweredByComputationNotByAGuessedNumber(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("property", {"check": "prime", "value": 91})
    result = understandQuestion("Is 91 a prime number?", ai)
    assert answerOf(result) == "\\text{no}" and result.parts[0]["solution"]["en"][0]["latex"] == "7 \\times 13"


def testAYesNoAnswerIsNeverGivenToAFindTheNumberQuestion(ai: FakeAi) -> None:
    """Regression: 'smallest number to multiply 1080 by for a perfect cube' was answered 'no'."""

    def reading(user: str) -> dict[str, Any]:
        if "not a yes/no answer" in user:
            return plan("property", {"check": "multiply_to_cube", "value": 1080})
        return plan("property", {"check": "perfect_cube", "value": 1080})

    ai.json[PLAN] = reading
    result = understandQuestion(
        "Find the smallest number by which 1080 must be multiplied to make it a perfect cube.", ai
    )
    assert answerOf(result) == "25"


def testUnansweredConfirmationIsNotTreatedAsDisagreement(ai: FakeAi) -> None:
    """If the confirming model is rate-limited, keep the answer but label it 'single_reading' — never 'verified'."""
    ai.json[PLAN] = plan("expression", {"expression": "5 \\times 18 - 4 \\times 16"})
    ai.secondJson[PLAN] = None
    ai.thirdJson[PLAN] = None
    result = understandQuestion(
        "The average of 5 numbers is 18. If one is removed, the average of the rest is 16. Find it.", ai
    )
    assert answerOf(result) == "26" and result.parts[0]["trust"] == "single_reading"


def testAQuestionMissingItsNumbersIsNeverAnsweredFromMemory(ai: FakeAi) -> None:
    # The photo lost its first line. Models 'remember' the NCERT sum (50 + 60 + x = 180) — that is a guess.
    remembered = plan("equations", {"equations": ["50 + 60 + x = 180"], "positive": ["x"]})
    ai.json[PLAN] = ai.secondJson[PLAN] = ai.thirdJson[PLAN] = remembered
    result = understandQuestion("Find the measure of the third angle.", ai)
    assert result.status == "needs_clarification" and "50" in (result.message or "") and result.parts == []


def testGroupedDigitsAreOneNumber() -> None:
    from app.agents.understand import findInventedNumbers

    assert findInventedNumbers({"principal": 5000, "rate": 8, "time": 3}, "Rs $5,000$ at $8\\%$ for $3$ years") == set()


def testANumberWorkedOutFromTheQuestionIsNotInvented(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("progression", {"terms": [4, 9, 14, 19], "difference": 5, "ask": "nth_term", "n": 15})
    result = understandQuestion("Find the 15th term of the AP: 4, 9, 14, 19, ...", ai)
    assert result.status == "solved" and answerOf(result) == "74"


def testALengthIsNeverNegative(ai: FakeAi) -> None:
    from app.agents.understand import runSolver

    measured = runSolver("equations", {"equations": ["PT^2 + 5^2 = 13^2"]}, "Find the length of the tangent PT (in cm).")
    assert measured.answer["values"] == ["12"]
    assert runSolver("equations", {"equations": ["x^2 = 144"]}, "Solve x^2 = 144").answer["values"] == ["-12", "12"]


def testWorldKnowledgeNumbersAreNotInvented(ai: FakeAi) -> None:
    # A die has 6 faces: 'probability of an even number on a die' gives no number, and that is not a guess.
    ai.json[PLAN] = plan("expression", {"expression": "\\frac{3}{6}"})
    result = understandQuestion("A die is rolled once. Find the probability of getting an even number.", ai)
    assert result.status == "solved" and answerOf(result) == "\\frac{1}{2}"


def testCardCountsAreWorldKnowledge(ai: FakeAi) -> None:
    # 'a red card that is not a face card': 20 of 52 — counts of a deck are known, not guessed.
    ai.json[PLAN] = plan("expression", {"expression": "\\frac{20}{52}"})
    result = understandQuestion("A card is drawn from a well-shuffled deck of 52 cards. Find the probability that it is a red card which is not a face card.", ai)
    assert result.status == "solved" and answerOf(result) == "\\frac{5}{13}"


def testAReadingThatIgnoresAGivenMeasurementIsNeverTheAnswerKey() -> None:
    # Both readings of "sector, radius 6 cm, angle 60°" once dropped the 60° and agreed on the whole circle (792/7).
    from app.agents.understand import findIgnoredMeasurements

    question = "Find the area of a sector of a circle with radius $6 \\text{ cm}$ if angle of the sector is $60^\\circ$."
    assert findIgnoredMeasurements({"shape": "circle", "quantity": "area", "dimensions": {"radius": 6}}, question) == {60}
    assert not findIgnoredMeasurements({"shape": "sector", "quantity": "area", "dimensions": {"radius": 6, "angle": 60}}, question)
    assert not findIgnoredMeasurements({"dimensions": {"radius": 6}}, "A circle has diameter 12 cm. Find its area.")


# ---------- curriculum eval fixes: what a student knows is not "invented", and the answer matches the ask ----------


@pytest.mark.parametrize(
    ("params", "question"),
    [
        ({"equations": ["x + 35 = 90"]}, "Two angles are complementary. One of them is 35°. Find the other angle."),
        ({"expression": "\\frac{5}{8} - \\frac{1}{6}"}, "Subtract ⅙ from 5/8."),
        ({"expression": "4.5 \\times 10^{-4}"}, "Write 0.00045 in standard form."),
        ({"expression": "\\frac{6(6-3)}{2}"}, "How many diagonals does a hexagon have?"),
        ({"expression": "\\frac{36}{99}"}, "Express 0.363636... in the form p/q."),
        ({"expression": "(100+5)(100-5)"}, "Evaluate 105 × 95 using an identity."),
        ({"first": 12, "last": 99, "difference": 3}, "How many two-digit numbers are divisible by 3?"),
        ({"expression": "\\frac{4}{5}"}, "If tan A = 4/3 and A is acute, find sin A."),
    ],
)
def testNumbersAStudentKnowsOrWorksOutAreNotGuesses(params: dict[str, Any], question: str) -> None:
    from app.agents.understand import findInventedNumbers

    assert not findInventedNumbers(params, question)


def testNumbersNobodyGaveAreStillCaught() -> None:
    from app.agents.understand import findInventedNumbers

    assert findInventedNumbers({"equations": ["50 + 60 + x = 180"]}, "Find the third angle.") == {50}  # a 'remembered' sum
    assert findInventedNumbers({"expression": "304500000"}, "Write 3 crore 45 lakh in figures.")  # a wrong AI figure


def testTheAnswerIsWhatTheQuestionAsksFor() -> None:
    from app.agents.understand import runSolver
    from app.maths import solvers

    nature = runSolver("expression", {"expression": "(-4)^2 - 4 \\cdot 2 \\cdot 3"}, "Find the nature of the roots of 2x² − 4x + 3 = 0.")
    assert nature.answer["value"] == "no real roots"  # not the discriminant -8
    # a reading with a wrong coefficient (D = 16 - 16 = 0) is overruled by the equation the question itself gives
    misread = runSolver("expression", {"expression": "(-4)^2 - 4 \\cdot 2 \\cdot 2"}, "Find the nature of the roots of $2x^{2} - 4x + 3 = 0$.")
    assert misread.answer["value"] == "no real roots"
    with pytest.raises(solvers.SolverError):  # zeroes are values of x, not '(x - 4)(x + 2)'
        runSolver("expression", {"expression": "x^2 - 2x - 8", "form": "factored"}, "Find the zeroes of the polynomial x² − 2x − 8.")
    # ...but a polynomial built FROM its zeroes is an expression answer
    built = runSolver("expression", {"expression": "x^2 + 3x + 2"}, "Find a quadratic polynomial whose zeroes have sum −3 and product 2.")
    assert built.answer["type"] == "expression"


def testATrigTermNextToABracketMultipliesIt() -> None:
    import sympy

    from app.maths.parser import parseLatex

    identity = parseLatex("(1 - \\cos^2 A) \\sec^2 A = \\tan^2 A")
    assert sympy.simplify(identity.lhs - identity.rhs) == 0


def testAThirdFreshReadingIsTriedBeforeAskingTheStudent(ai: FakeAi) -> None:
    # Live, an AP sum got two unusable readings in a row ("'None' is not a number"); a third read it right.
    ai.json[PLAN] = plan("progression", {"terms": [1, 4, 7, 10], "ask": "sum", "n": None})
    ai.secondJson[PLAN] = plan("progression", {"terms": [1, 4, 7, 10], "ask": "sum", "n": None})
    ai.thirdJson[PLAN] = plan("progression", {"terms": [1, 4, 7, 10], "ask": "sum", "n": 20})
    result = understandQuestion("Find the sum of the first 20 terms of the AP: 1, 4, 7, 10, ...", ai)
    assert answerOf(result) == "590"


def testAMissingValueIsExplainedInPlainWords(ai: FakeAi) -> None:
    ai.json[PLAN] = plan("progression", {"terms": [1, 4, 7, 10], "ask": "sum", "n": None})
    ai.secondJson[PLAN] = ai.json[PLAN]
    ai.thirdJson[PLAN] = ai.json[PLAN]
    result = understandQuestion("Find the sum of the first 20 terms of the AP: 1, 4, 7, 10, ...", ai)
    assert result.status == "needs_clarification" and "None" not in (result.message or "")
