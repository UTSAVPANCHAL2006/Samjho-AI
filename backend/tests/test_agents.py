# The two LangGraph agents with a fake AI: GradingGraph (red pen) and TutorGraph (the conversation).

from pathlib import Path
from typing import Any

from app.agents.grading import runGrading
from app.agents.tutor import buildTeachingSteps, decideTurn, runTutorTurn
from tests.conftest import FakeAi, makePagePhoto

QUESTION = {
    "text": "Solve x^2 - 5x + 6 = 0",
    "expressions": ["x^2-5x+6=0"],
    "answer": {"type": "solution_set", "variable": "x", "values": ["2", "3"]},
    "marks": 3,
    "class_level": 10,
}


def grade(ai: FakeAi, lines: list[str] | None = None, photo: bytes | None = None, tmp: Path | None = None) -> Any:
    state: dict[str, Any] = {"question": QUESTION, "confidenceThreshold": 0.8, "mediaType": "image/png"}
    if lines is not None:
        state["lines"] = [{"latex": line, "confidence": 1.0} for line in lines]
    if photo is not None and tmp is not None:
        path = tmp / "page.png"
        path.write_bytes(photo)
        state["imagePath"] = str(path)
    return runGrading(ai, state)  # type: ignore[arg-type]


def testCorrectWorkingGetsFullMarksWithoutAnyAiCall(ai: FakeAi) -> None:
    result = grade(ai, ["(x-2)(x-3)=0", "x=2", "x=3"])
    assert (result["status"], result["score"], result["wrongLine"]) == ("graded", 3, None)
    assert ai.calls == []


def testWrongStepIsExplainedWithSympyFactsNotAi(ai: FakeAi) -> None:
    result = grade(ai, ["(x+2)(x+3)=0", "x=-2", "x=-3"])
    assert (result["score"], result["wrongLine"]) == (0, 1)
    assert result["explanation"] == "In this line the x term should be -5, the line gives 5."
    assert ai.calls == []  # grading typed work never calls an AI


def testSkippedWorkScoresZeroBeforeChecking(ai: FakeAi) -> None:
    result = grade(ai, ["pata nahi"])
    assert (result["status"], result["score"]) == ("skipped", 0)


def testUnsureReadingWaitsForTheStudentToConfirm(ai: FakeAi, tmp_path: Path) -> None:
    ai.image = {
        "page": "maths",
        "lines": [{"latex": "(x-2)(x-3)=0", "confidence": 0.95}, {"latex": "x=2", "confidence": 0.5}],
    }
    result = grade(ai, photo=makePagePhoto(), tmp=tmp_path)
    assert result["status"] == "needs_confirmation"
    assert "steps" not in result  # nothing is marked until the student confirms


def testPhotoProblemsNeverReachTheAi(ai: FakeAi, tmp_path: Path) -> None:
    result = grade(ai, photo=makePagePhoto(brightness=10), tmp=tmp_path)
    assert (result["status"], result["explanation"]) == ("needs_retake", "too_dark")
    assert "image" not in ai.calls


def testNonMathsPhotoAndAiOutage(ai: FakeAi, tmp_path: Path) -> None:
    ai.image = {"page": "not_maths", "lines": []}
    assert grade(ai, photo=makePagePhoto(), tmp=tmp_path)["status"] == "not_maths"
    ai.image = None
    assert grade(ai, photo=makePagePhoto(), tmp=tmp_path)["status"] == "ai_unavailable"


def testTeachingRules() -> None:
    # (stage, hints, step, step count, intent, fixCorrect, stepCorrect) -> (task, next stage, hints, step)
    assert decideTurn("start", 0, 0, 7, "chat", None, None) == ("probe", "hints", 0, 0)
    assert decideTurn("hints", 0, 0, 7, "maths", False, None) == ("diagnose", "hints", 1, 0)
    assert decideTurn("hints", 1, 0, 7, "maths", False, None) == ("strong_hint", "hints", 2, 0)
    assert decideTurn("hints", 2, 0, 7, "chat", None, None) == ("walk_start", "walkthrough", 0, 1)  # no 3rd hint
    assert decideTurn("hints", 0, 0, 7, "explain", None, None) == ("walk_start", "walkthrough", 0, 1)
    assert decideTurn("hints", 0, 0, 7, "full_solution", None, None) == ("ask_one_try", "hints", 1, 0)  # one try first
    assert decideTurn("hints", 1, 0, 7, "full_solution", None, None) == ("full_solution", "quick_check", 1, 0)  # asked again
    assert decideTurn("hints", 1, 0, 7, "maths", True, None) == ("praise", "quick_check", 1, 0)
    assert decideTurn("walkthrough", 0, 2, 7, "maths", None, True) == ("walk_next", "walkthrough", 0, 3)
    assert decideTurn("walkthrough", 0, 2, 7, "maths", None, False) == ("walk_show", "walkthrough", 0, 3)
    assert decideTurn("walkthrough", 0, 2, 7, "explain", None, None) == ("walk_simpler", "walkthrough", 1, 2)
    assert decideTurn("walkthrough", 1, 2, 7, "explain", None, None) == ("walk_show", "walkthrough", 0, 3)  # no loop
    assert decideTurn("walkthrough", 0, 6, 7, "maths", None, True) == ("walk_done", "quick_check", 0, 6)
    assert decideTurn("quick_check", 1, 0, 7, "maths", None, None) == ("quick_check_result", "practice", 1, 0)


def tutorState(stage: str, text: str, **extra: Any) -> Any:
    return {
        "question": QUESTION,
        "lines": ["(x+2)(x+3)=0", "x=-2", "x=-3"],
        "wrongLine": 1,
        "facts": "the x term should be -5, the line gives 5",
        "language": "hinglish",
        "history": [],
        "steps": [],
        "stage": stage,
        "hintsUsed": 0,
        "step": 0,
        "studentText": text,
        **extra,
    }


def testCorrectFixIsProvenThenAQuickCheckIsAsked(ai: FakeAi) -> None:
    ai.text = "Shabash! Sign sahi kar diya."
    ai.json["Make ONE tiny question"] = {"question": "Factorise $x^2-7x+12$", "answer": "(x-3)(x-4)"}
    result = runTutorTurn(ai, tutorState("hints", "(x-2)(x-3)=0"))
    assert result["fixCorrect"] is True
    assert result["nextStage"] == "quick_check"
    assert result["reply"].endswith("Ek chhota sawaal: Factorise $x^2-7x+12$")


def testWrongFixIsDiagnosedNotAnswered(ai: FakeAi) -> None:
    result = runTutorTurn(ai, tutorState("hints", "(x+1)(x+6)=0"))
    assert (result["fixCorrect"], result["task"]) == (False, "diagnose")
    assert "x = 2" not in result["reply"]  # offline template, no answer given away


def testQuickCheckAnswerIsCheckedBySympy(ai: FakeAi) -> None:
    result = runTutorTurn(
        ai, tutorState("quick_check", "(x-4)(x-3)", quickCheck={"question": "q", "answer": "(x-3)(x-4)"})
    )
    assert (result["quickCheckCorrect"], result["nextStage"]) == (True, "practice")


def testNoCheckableQuickCheckGoesStraightToPractice(ai: FakeAi) -> None:
    ai.json["Make ONE tiny question"] = {"question": "Why?", "answer": "because signs"}
    result = runTutorTurn(ai, tutorState("hints", "(x-2)(x-3)=0"))
    assert result["nextStage"] == "practice"


# ---------- Tests K and L: the reported conversation ----------

PAIR = {
    "text": "Solve 2x + 3y = 11 and 2x - 4y = -24",
    "expressions": ["2x + 3y = 11", "2x - 4y = -24"],
    "answer": {"type": "point", "values": {"x": "-2", "y": "5"}},
    "class_level": 10,
    "traps": [],
}


def pairState(stage: str, text: str, **extra: Any) -> Any:
    from app.maths import solvers

    steps = [
        {"explain": step["explain"], "latex": step["latex"] or None}
        for step in solvers.solveEquations(PAIR["expressions"]).steps
    ]  # type: ignore[arg-type]
    return {
        **tutorState(stage, text),
        "question": PAIR,
        "lines": ["x = 8"],
        "facts": "x = 8 is wrong",
        "steps": steps,
        **extra,
    }


def testStudentsWrongValueIsDiagnosedBySubstitution(ai: FakeAi) -> None:
    """'Maine x = 8 likha' — the maths inside the sentence is found and checked, with a concrete reason."""
    result = runTutorTurn(ai, pairState("hints", "Maine x = 8 likha"))
    assert result["claim"] == "x = 8" and result["fixCorrect"] is False
    assert "y = - \\frac{5}{3}" in (result["claimFacts"] or "")  # x = 8 in (1) gives y = -5/3, which breaks (2)
    assert result["task"] == "diagnose"


def testTheAiIsToldExactlyWhatWasWrong(ai: FakeAi) -> None:
    captured: list[str] = []
    ai.askText = lambda messages, temperature=0.4: captured.append(messages[0]["content"]) or "ok"  # type: ignore[method-assign]
    runTutorTurn(ai, pairState("hints", "Maine x = 8 likha"))
    assert "Their maths $x = 8$ is WRONG. Why (computed): With $x = 8$" in captured[0]
    assert "7 y = 35" in captured[0]  # the verified steps are in front of the tutor, not a generic method


def testConfusionStartsAGuidedWalkthroughAndKeepsTheProblem(ai: FakeAi) -> None:
    """'Samjhao, mujhe samajh nahi aaya' -> teach the verified steps one at a time, then check their step."""
    first = runTutorTurn(ai, pairState("hints", "Samjhao, mujhe samajh nahi aaya", hintsUsed=1))
    assert (first["intent"], first["task"], first["nextStage"], first["nextStep"]) == (
        "explain",
        "walk_start",
        "walkthrough",
        1,
    )
    assert "2 x + 3 y = 11" in first["reply"]  # step 1 of THIS problem, not a generic lecture
    # Their answer to the guided step is checked against the verified step, and the walkthrough moves on.
    second = runTutorTurn(ai, pairState("walkthrough", "Subtract karne se y bachega", step=2))
    assert second["task"] == "walk_chat" and second["nextStep"] == 2  # no maths: re-ask the same step, keep context
    partial = runTutorTurn(ai, pairState("walkthrough", "7y banega", step=2))  # one side of '7y = 35' is right too
    assert partial["stepCorrect"] is True
    third = runTutorTurn(ai, pairState("walkthrough", "7y = 35", step=2))
    assert (third["stepCorrect"], third["task"], third["nextStep"]) == (True, "walk_next", 3)
    wrong = runTutorTurn(ai, pairState("walkthrough", "y = 7", step=3))
    assert (wrong["stepCorrect"], wrong["task"], wrong["nextStep"]) == (False, "walk_show", 4)


def testRepeatedConfusionDoesNotLoop(ai: FakeAi) -> None:
    once = runTutorTurn(ai, pairState("walkthrough", "samajh nahi aaya", step=2))
    assert (once["task"], once["hintsUsed"], once["nextStep"]) == ("walk_simpler", 1, 2)
    twice = runTutorTurn(ai, pairState("walkthrough", "abhi bhi samajh nahi aaya", step=2, hintsUsed=1))
    assert (twice["task"], twice["nextStep"]) == ("walk_show", 3)


def testFullSolutionIsBuiltFromVerifiedStepsOnly(ai: FakeAi) -> None:
    ai.text = "This must not be used"
    first = runTutorTurn(ai, pairState("hints", "pura solution batao"))
    assert first["task"] == "ask_one_try" and "$x = -2, y = 5$" not in first["reply"]  # never the first thing given
    result = runTutorTurn(ai, pairState("hints", "pura solution batao", hintsUsed=1))
    assert result["task"] == "full_solution"
    assert (
        "$7 y = 35$" in result["reply"] and "$x = -2, y = 5$" in result["reply"] and "must not" not in result["reply"]
    )


def testEveryTeachingStepHasMathsToWorkOut() -> None:
    from app.maths import solvers

    steps = buildTeachingSteps(solvers.solveEquations(PAIR["expressions"]).steps)  # type: ignore[arg-type]
    assert all(step["latex"] for step in steps)
    assert steps[1]["latex"] == "7 y = 35" and "subtract (2) from (1)" in steps[1]["explain"]


def testStepAnswersAcceptAnyCorrectPartOfTheStep() -> None:
    from app.agents.tutor import checkStepAnswer

    assert checkStepAnswer("11", "11 = 11 \\checkmark \\qquad -24 = -24 \\checkmark") is True  # the check step
    assert checkStepAnswer("7y", "7 y = 35") is True  # answered the sub-question "3y − (−4y)?"
    assert checkStepAnswer("y = 6", "y = 5") is False


# ---------- real notebook pages (read by vision, then checked by SymPy) ----------

SECTOR = {
    "text": "Find the area of a sector of a circle with radius $6\\text{ cm}$ if the angle of the sector is $60^\\circ$ (use $\\pi = 22/7$).",
    "expressions": [],
    "answer": {"type": "expression", "latex": "\\frac{132}{7}"},
    "marks": 3,
    "class_level": 10,
    "traps": [{"value": "\\frac{44}{7}", "mistake": "used the arc length formula instead of the area formula"}],
}
DISTANCE = {
    "text": "Find the distance between the two points: $A(2, 3)$ and $B(4, 1)$",
    "expressions": [],
    "answer": {"type": "expression", "latex": "2 \\sqrt{2}"},
    "marks": 2,
    "class_level": 10,
    "traps": [{"value": "0", "mistake": "forgot to square (x₂ − x₁) and (y₂ − y₁) inside the square root"}],
}
PAIR_37 = {
    "text": "Solve: 3x - y = 7 and x + 2y = 7",
    "expressions": ["3x-y=7", "x+2y=7"],
    "answer": {"type": "point", "values": {"x": "3", "y": "2"}},
    "marks": 4,
    "class_level": 10,
}


def gradeLines(ai: FakeAi, question: dict[str, Any], lines: list[str]) -> Any:
    state = {"question": question, "lines": [{"latex": line, "confidence": 1.0} for line in lines], "confidenceThreshold": 0.8}
    return runGrading(ai, state)  # type: ignore[arg-type]


def testWrongSectorFormulaIsFoundWhereItStartsAndNamed(ai: FakeAi) -> None:
    lines = [
        "\\text{Given: } r = 6 \\text{ cm}",
        "\\theta = 60 ^\\circ",
        "\\text{Area} = (60 / 360) * 2 * (22 / 7) * 6",
        "\\text{Area} = (1 / 6) * 2 * (22 / 7) * 6",
        "\\text{Area} = 44 / 7 \\text{ cm}^2",
        "\\text{Ans: } 44 / 7 \\text{ cm}^2",
    ]
    result = gradeLines(ai, SECTOR, lines)
    assert (result["status"], result["score"], result["wrongLine"]) == ("graded", 0, 3)
    assert "arc length formula instead of the area formula" in result["explanation"]


def testRightSectorWorkingWithARoundedAnswerGetsFullMarks(ai: FakeAi) -> None:
    lines = [
        "\\text{Given: Radius } (r) = 6 \\text{ cm}",
        "\\text{Area} = (60^\\circ / 360^\\circ) * (22 / 7) * (6)^2",
        "\\text{Area} = (1 / 6) * (22 / 7) * 36",
        "\\text{Area} = 132 / 7 \\text{ cm}^2",
        "\\text{Ans: Area} = 18.86 \\text{ cm}^2",
    ]
    result = gradeLines(ai, SECTOR, lines)
    assert (result["status"], result["score"], result["wrongLine"]) == ("graded", 3, None)


def testDistanceWithoutSquaresIsCaughtAndXOneIsASubscriptNotXTimesOne(ai: FakeAi) -> None:
    lines = ["x1 = 2", "y1 = 3", "x2 = 4", "y2 = 1", "d = \\sqrt{(x2 - x1) + (y2 - y1)}", "d = \\sqrt{2 + (-2)}", "d = 0"]
    result = gradeLines(ai, DISTANCE, lines)  # 'x1 = 2' once crashed the checker (x * 1 = 2, then 2 * 2 = 4 -> True)
    assert (result["status"], result["wrongLine"]) == ("graded", 5)
    assert "forgot to square" in result["explanation"]
    right = ["d = \\sqrt{(4 - 2)^2 + (1 - 3)^2}", "d = \\sqrt{4 + 4} = \\sqrt{8}", "\\text{Ans: Distance } = 2\\sqrt{2} \\text{ units}"]
    assert gradeLines(ai, DISTANCE, right)["score"] == 2


def testWorkingForADifferentPairOfEquationsScoresZeroWithTheProof(ai: FakeAi) -> None:
    lines = ["x + y = 14 -- (1)", "x - y = 4 -- (2)", "Add (1) + (2):", "2x = 18", "x = 9", "9 - y = 4", "y = 5"]
    result = gradeLines(ai, PAIR_37, lines)
    assert (result["status"], result["score"]) == ("off_question", 0)
    assert "$x + y = 14$" in result["explanation"] and "$3x-y=7$" in result["explanation"]


def testAMultipliedEquationIsTheStudentsMistakeNotAnotherQuestion(ai: FakeAi) -> None:
    result = gradeLines(ai, PAIR_37, ["6x - 2y = 12", "x + 2y = 7", "7x = 19"])
    assert (result["status"], result["wrongLine"]) == ("graded", 1)
    assert "it should be $14$, not $12$" in result["explanation"]


def testWorkingWithOtherGivenValuesIsOffQuestion(ai: FakeAi) -> None:
    question = {**SECTOR, "text": "Find the area of a sector of radius 14 cm and angle 90° (π = 22/7).", "answer": {"type": "expression", "latex": "154"}}
    lines = ["r = 6 \\text{ cm}", "\\theta = 60^\\circ", "\\text{Area} = (60 / 360) * (22 / 7) * 6^2", "\\text{Area} = 132 / 7"]
    result = gradeLines(ai, question, lines)
    assert (result["status"], result["score"]) == ("off_question", 0)
    assert "14, 90" in result["explanation"]


def testPageHeaderAndRoughWorkAreNotMarked(ai: FakeAi, tmp_path: Path) -> None:
    ai.image = {
        "page": "maths",
        "lines": [
            {"latex": "\\text{DATE: } 17 / 10 / 2026", "kind": "header", "confidence": 0.95},
            {"latex": "\\text{PAGE NO: } 26", "confidence": 0.95},  # no kind given: the header rule still drops it
            {"latex": "\\text{Area} = (1 / 6) * (22 / 7) * 36", "kind": "working", "confidence": 0.95},
            {"latex": "\\text{Area} = 132 / 7", "kind": "working", "confidence": 0.95},
            {"latex": "22 \\times 6 = 133", "kind": "rough", "confidence": 0.95},
        ],
    }
    path = tmp_path / "page.png"
    path.write_bytes(makePagePhoto())
    state = {"question": SECTOR, "imagePath": str(path), "mediaType": "image/png", "confidenceThreshold": 0.8}
    result = runGrading(ai, state)  # type: ignore[arg-type]
    assert [line["latex"] for line in result["lines"]] == ["\\text{Area} = (1 / 6) * (22 / 7) * 36", "\\text{Area} = 132 / 7"]
    assert (result["status"], result["score"]) == ("graded", 3)


def testTutorStartsWhenTheNewChatHasNoStepYet(ai: FakeAi) -> None:
    state = {
        "question": QUESTION,
        "lines": ["(x+2)(x+3)=0", "x=-2"],
        "wrongLine": 1,
        "rootLine": 1,
        "facts": "In this line the x term should be -5, the line gives 5.",
        "language": "en",
        "steps": [],
        "history": [],
        "stage": "start",
        "hintsUsed": None,
        "step": None,  # a TutorChat that is not flushed yet: column defaults are still None (this crashed before)
        "studentText": "",
    }
    result = runTutorTurn(ai, state)  # type: ignore[arg-type]
    assert result["reply"] and result["nextStage"] == "hints"


def testGaltiSamjhoStartsWithTheirLineAndNarrationNeverAddsNumbers(ai: FakeAi) -> None:
    from types import SimpleNamespace

    from app.agents.visual import buildMistakeIntro, narrateVisual

    question = SimpleNamespace(
        text=SECTOR["text"],
        class_level=10,
        traps=SECTOR["traps"],
        solution={"en": [{"explain": "Formula.", "latex": "\\frac{\\theta}{360} \\pi r^2"}]},
    )
    facts = "This line works out to $\\frac{44}{7}$ — that is exactly what you get if you used the arc length formula instead of the area formula."
    wrong = "\\text{Area} = (60 / 360) * 2 * (22 / 7) * 6"
    intro = buildMistakeIntro(question, "hinglish", ai, 3, wrong, facts, SECTOR["traps"][0]["mistake"])  # type: ignore[arg-type]
    assert len(intro["frames"]) == 3 and intro["elements"][0]["tone"] == "wrong"
    assert intro["elements"][-1]["text"] == "$\\frac{\\theta}{360} \\pi r^2$"  # a formula mistake shows the right rule
    ai.json["frame by frame"] = {
        "captions": [
            "Dekho, line 3 mein tumne yeh likha. Yahin se galti shuru hui.",
            "Tumhara answer 99 hai.",  # a new number: rejected, the code-written caption stays
            "Sahi rule yaad karo: $\\frac{\\theta}{360} \\pi r^2$. Isme r ka square hota hai.",
        ]
    }
    narrated = narrateVisual(intro, question, "hinglish", ai, wrong, facts)  # type: ignore[arg-type]
    captions = [frame["caption"] for frame in narrated["frames"]]
    assert captions[0].startswith("Dekho, line 3") and captions[1] == intro["frames"][1]["caption"]
    ai.json["frame by frame"] = None  # AI down: every caption stays as code wrote it
    assert narrateVisual(intro, question, "hinglish", ai, wrong, facts) == intro  # type: ignore[arg-type]


def testAnUnreadableAnswerLineIsNeverReplacedByAGivenValueAbove(ai: FakeAi) -> None:
    # The right working, but the last lines could not be read: 'y_2 = 1' must not be taken as the final answer.
    lines = ["x_1 = 2", "y_1 = 3", "x_2 = 4", "y_2 = 1", "d = \\sqrt{(4 - 2)^2 + (1 - 3)^2", "\\text{Ans: } d = 2 \\sqrt{"]
    result = gradeLines(ai, DISTANCE, lines)
    assert result["wrongLine"] is None and all(step["verdict"] != "incorrect" for step in result["steps"])


def testAnotherLetterForTheUnknownIsNotAnotherQuestion(ai: FakeAi) -> None:
    question = {**PAIR_37, "text": "Two angles of a triangle are 50° and 60°. Find the third angle.", "expressions": ["x + 50 + 60 = 180"],
                "answer": {"type": "solution_set", "variable": "x", "values": ["70"]}, "marks": 3}  # fmt: skip
    lines = ["50^\\circ + 60^\\circ + C = 180^\\circ", "110^\\circ + C = 180^\\circ", "C = 180^\\circ - 110^\\circ", "C = 70^\\circ", "\\text{Ans: Third angle is } 70^\\circ"]
    result = gradeLines(ai, question, lines)  # 'C' instead of 'x' once scored 0 as "off question"
    assert (result["status"], result["score"]) == ("graded", 3)


def testAFormulaWithLettersIsNotComparedWithANumber(ai: FakeAi) -> None:
    question = {**SECTOR, "text": "Find the simple interest on Rs 5000 at 8% per annum for 3 years.", "answer": {"type": "expression", "latex": "1200"}, "traps": []}
    lines = ["\\text{Formula: S.I.} = (P * R * T) / 100", "= (5000 * 8 * 3) / 100", "= 50 * 24", "= \\text{Rs } 1200"]
    result = gradeLines(ai, question, lines)  # '(5000 × 8 × 3)/100' was once marked wrong against 'P R T / 100'
    assert (result["score"], result["wrongLine"]) == (3, None)


def testDetailedSolutionEndingWithACheckStepIsTrusted() -> None:
    from types import SimpleNamespace

    from app.agents.solution import isDetailedSolutionTrusted

    question = SimpleNamespace(answer={"type": "solution_set", "variable": "x", "values": ["7"]}, expressions=["3(x-2)=15"])
    lines = ["3(x - 2) = 15", "3x - 6 = 15", "3x = 21", "x = 7", "3(7 - 2) = 15", "3(5) = 15", "15 = 15"]
    steps = [{"explain": "...", "latex": line} for line in lines]
    assert isDetailedSolutionTrusted(question, steps)  # type: ignore[arg-type]
    wrong = [{"explain": "...", "latex": line} for line in ["3x - 6 = 15", "3x = 24", "x = 8", "3(8 - 2) = 18"]]
    assert not isDetailedSolutionTrusted(question, wrong)  # type: ignore[arg-type]


def testAnEnglishSolutionIsNeverWrittenInHinglish(ai: FakeAi) -> None:
    from types import SimpleNamespace

    from app.agents.solution import writeDetailedSteps

    question = SimpleNamespace(class_level=7, text="Solve 3(x-2)=15", answer={"type": "solution_set", "variable": "x", "values": ["7"]},
                               expressions=["3(x-2)=15"], traps=[])  # fmt: skip
    lines = ["3(x - 2) = 15", "3x - 6 = 15", "3x = 21", "x = 7"]
    hinglish = {"steps": [{"explain": "Dekho, pehle bracket ko kholo, yeh hamesha karna hota hai.", "latex": line} for line in lines]}
    english = {"steps": [{"explain": "First open the bracket.", "latex": line} for line in lines]}
    ai.json["TEACHING this question"] = hinglish
    ai.thirdJson["TEACHING this question"] = english  # the retry (temperature > 0) is asked for English only
    steps = writeDetailedSteps(question, [], "en", ai)  # type: ignore[arg-type]
    assert steps and steps[0]["explain"] == "First open the bracket."
    ai.thirdJson["TEACHING this question"] = hinglish
    assert writeDetailedSteps(question, [], "en", ai) is None  # type: ignore[arg-type]  # the verified short steps are shown instead
    assert writeDetailedSteps(question, [], "hinglish", ai)  # type: ignore[arg-type]


def testSplittingApproximationsAndEqualsChains() -> None:
    from app.agents.grading import splitWorkingLines

    lines = [{"latex": "= 2 * 22/7 = 44/7 cm²", "confidence": 1.0}, {"latex": "Ans: 44/7 cm^2 (approx 6.28 cm^2)", "confidence": 1.0}]
    assert [line["latex"] for line in splitWorkingLines(lines)] == ["= 2 * 22/7", "= 44/7 cm²", "Ans: 44/7 cm^2", "= 6.28 cm^2"]


def testSplitLinesKeepTheirBracesBalanced() -> None:
    from app.agents.grading import splitWorkingLines

    lines = [
        {"latex": "\\text{Rate (R) = 8\\% p.a.\nTime (T) = 3 years}", "confidence": 1.0},
        {"latex": "a = 2, \\\nb = -7, \\", "confidence": 1.0},
        {"latex": "\\text{Given: } V = 12\\text{\nE} = 30", "confidence": 1.0},
    ]
    assert [line["latex"] for line in splitWorkingLines(lines)] == [
        "\\text{Rate (R) = 8\\% p.a.}",
        "\\text{Time (T) = 3 years}",
        "a = 2",
        "b = -7",
        "\\text{Given: } V = 12",
        "\\text{E} = 30",
    ]


def testAnUncheckableLineOnTheVerifiedPathIsRight(ai: FakeAi) -> None:
    question = {**SECTOR, "solution": [{"latex": "\\frac{60}{360} \\times \\frac{22}{7} \\times 6^2 = \\frac{1}{6} \\times \\frac{792}{7}"}]}
    lines = ["\\text{Whole circle} = \\frac{792}{7}", "\\text{Area} = \\frac{1}{6} \\times \\frac{792}{7}", "= \\frac{132}{7}"]
    result = gradeLines(ai, question, lines)
    assert result["steps"][0]["verdict"] == "correct" and result["score"] == 3


def testAlgebraWriteUpIsTrustedWhenEveryEqualsIsTrue() -> None:
    from types import SimpleNamespace

    from app.agents.solution import isDetailedSolutionTrusted

    question = SimpleNamespace(answer={"type": "expression", "latex": "3x(2x+3)", "form": "factored"}, expressions=["6x^2+9x"])
    good = ["6x^2 + 9x", "6 = 3 \\times 2", "3x", "\\frac{6x^2}{3x} = 2x", "6x^2 + 9x = 3x(2x + 3)", "3x(2x) + 3x(3) = 6x^2 + 9x"]
    bad = ["6x^2 + 9x", "6x^2 + 9x = 3x(2x + 9)", "3x", "\\frac{9x}{3x} = 3", "6x^2 + 9x = 3x(2x + 3)"]
    assert isDetailedSolutionTrusted(question, [{"explain": "", "latex": line} for line in good])  # type: ignore[arg-type]
    assert not isDetailedSolutionTrusted(question, [{"explain": "", "latex": line} for line in bad])  # type: ignore[arg-type]


def testApproxWrittenInsideTextIsItsOwnStepAndARestatedAnswerHidesNothing(ai: FakeAi) -> None:
    lines = ["r = 6 \\text{ cm}", "= (60/360) * 2 * (22/7) * 6", "= (1/6) * 12 * (22/7)", "= 44/7 \\text{ cm}^2",
             "\\text{Ans: } 44/7 \\text{ cm}^2 (\\text{approx } 6.28 \\text{ cm}^2)"]  # fmt: skip
    result = gradeLines(ai, SECTOR, lines)
    assert (result["wrongLine"], result["score"]) == (2, 0)
    assert "arc length formula instead of the area formula" in result["explanation"]


def testASideQuantityIsNotComparedWithTheMainSumButAWrongSumIsStillCaught(ai: FakeAi) -> None:
    question = {"text": "Find the sum of the first 20 terms of the AP: 1, 4, 7, 10, ...", "expressions": ["\\frac{20}{2} \\times (2 \\times 1 + 19 \\times 3)"],
                "answer": {"type": "expression", "latex": "590"}, "marks": 2, "class_level": 10, "traps": []}  # fmt: skip
    right = ["a = 1", "\\text{Common difference } d = 4 - 1", "n = 20", "S_{20} = 10 [2 + 19 \\times 3]", "= 590"]
    assert gradeLines(ai, question, right)["score"] == 2  # 'd = 4 - 1' (= 3) is not a wrong step of the sum 590
    wrong = ["a = 1", "d = 3", "S_{20} = (20 / 2) [1 + 19 \\times 3]", "= 580"]
    assert gradeLines(ai, question, wrong)["wrongLine"] == 3


def testAPictureOfTheMistakeMayShowTheStudentsWrongLineButNothingElseFalse() -> None:
    from app.agents.visual import cleanVisual

    wrong = "\\frac{-6}{10} - \\frac{7}{10} = \\frac{-6 + 7}{10}"
    data = {"frames": [{"caption": "Tumne likha"}, {"caption": "Sahi"}], "elements": [
        {"type": "text", "text": f"${wrong}$", "tone": "wrong", "frame": 0},
        {"type": "text", "text": "$\\frac{-6}{10} - \\frac{7}{10} = \\frac{-13}{10}$", "tone": "right", "frame": 1},
    ]}  # fmt: skip
    assert cleanVisual(data, wrong) is not None  # their own wrong line is the point of the picture
    assert cleanVisual(data) is None  # without it, false maths still rejects the picture
    data["elements"].append({"type": "text", "text": "$2 + 2 = 5$", "frame": 1})
    assert cleanVisual(data, wrong) is None  # any OTHER false line still rejects it


def testCommonMistakesGetAPictureOfTheirWayNextToTheRightWay() -> None:
    from app.agents.visual_templates import mistakePicture

    sector = mistakePicture("used the arc length formula instead of the area formula", "hinglish", "sector", {"radius": 6, "angle": 60})
    distance = mistakePicture("forgot to square (x₂ − x₁) and (y₂ − y₁) inside the square root", "hinglish", "coordinates", {"points": [[2, 3], [4, 1]]})
    perimeter = mistakePicture("wrong formula or values", "hinglish", "shape", {"shape": "rectangle", "length": 8, "breadth": 5, "quantity": "perimeter"})
    for picture in (sector, distance, perimeter):
        assert picture is not None
        tones = [element.get("tone") for element in picture["elements"] if element["type"] == "text"]
        assert "wrong" in tones and "right" in tones  # their way, then the right way
    assert any(element.get("arc") for element in sector["elements"])  # the edge drawn as a line, the area as a region
    assert mistakePicture("calculation slip", "hinglish", "sector", {"radius": 6, "angle": 60}) is None  # no picture that does not fit


def testTheTeacherNeverStartsWithAccha() -> None:
    from app.ai.prompts import cleanAddress

    assert cleanAddress("Accha, dekho line 4.") == "Dekho line 4."
    assert cleanAddress("Ab socho. Achha accha, phir yeh karo.") == "Ab socho. Phir yeh karo."
    assert cleanAddress("अच्छा, तो देखो।") == "तो देखो।"
    assert cleanAddress("Yeh accha sawaal hai.") == "Yeh accha sawaal hai."  # the word itself, not a filler


def testRememberCardStatesTheRuleOnceOnly() -> None:
    from app.agents.visual import addRememberCard, pickRuleSentence

    insight = "Line 2 mein tumne 360 le liya. Triangle ke teeno angles ka sum $180^\\circ$ hota hai. Agli baar yaad rakhna."
    assert pickRuleSentence(insight) == "Triangle ke teeno angles ka sum $180^\\circ$ hota hai."
    board = {"title": "", "frames": [{"caption": "a"}], "elements": [{"type": "text", "text": "Yaad rakho: kinaara → 2πr", "frame": 0}]}
    assert addRememberCard(board, insight, "hinglish") == board  # the board already ends on a rule
    plain = {"title": "", "frames": [{"caption": "a"}], "elements": []}
    assert addRememberCard(plain, insight, "hinglish")["frames"][-1]["caption"].endswith("hota hai.")


def testInsightGuardsAllowRulesButNeverTheAnswer(ai: FakeAi) -> None:
    from types import SimpleNamespace

    from app.agents.visual import fallbackInsight, findInsight

    question = SimpleNamespace(text="Three angles of a quadrilateral are 75°, 90° and 105°. Find the fourth.", class_level=8,
                               answer={"type": "solution_set", "variable": "x", "values": ["90"]}, solution={}, traps=[])  # fmt: skip
    lines = ["75 + 90 + 105 + x = 180"]
    ai.json["checking a Class"] = {"insight": "Quadrilateral ke chaaron angles ka sum $360^\\circ$ hota hai, $180^\\circ$ nahi."}
    assert "360" in (findInsight(question, lines, 1, "fact", "hinglish", ai) or "")  # a standard fact, not a new number
    ai.json["checking a Class"] = {"insight": "Answer $x = 90$ hai, kyunki sum 360 hota hai."}
    question.answer = {"type": "solution_set", "variable": "x", "values": ["\\frac{45}{2}"]}
    ai.json["checking a Class"] = {"insight": "Answer $\\frac{45}{2}$ aayega."}
    assert findInsight(question, lines, 1, "fact", "hinglish", ai) is None  # the answer is never given away
    assert "arc length" in (fallbackInsight(question, "used the arc length formula instead of the area formula", "hinglish") or "")
    assert fallbackInsight(question, "wrong step", "hinglish") is None
    # An English lesson never shows a Hinglish note: the model copied the prompt's examples.
    ai.json["checking a Class"] = {"insight": "Quadrilateral ke chaaron angles ka sum $360^\\circ$ hota hai, $180^\\circ$ nahi."}
    assert findInsight(question, lines, 1, "fact", "en", ai) is None
    ai.json["checking a Class"] = {"insight": "The four angles of a quadrilateral add up to $360^\\circ$, not $180^\\circ$."}
    assert "add up" in (findInsight(question, lines, 1, "fact", "en", ai) or "")


def testAReplyMixingEscapedAndLoneBackslashesIsStillRead() -> None:
    from app.ai.models import parseJsonObject

    # '\\sqrt' (valid JSON) and '\sqrt' (a lone backslash) in ONE reply: the whole detailed solution was once lost.
    reply = '{"steps": [{"explain": "Dekho \\\\sqrt{2} aur \\sqrt{3}", "latex": "3^2 - (\\sqrt{2})^2"}]}'
    data = parseJsonObject(reply)
    assert data is not None and data["steps"][0]["explain"] == "Dekho \\sqrt{2} aur \\sqrt{3}"
    assert data["steps"][0]["latex"] == "3^2 - (\\sqrt{2})^2"


def testAnEqualsInsideTheWordsIsReadAndUnreadableNumbersAreNeverZero(ai: FakeAi) -> None:
    question = {"text": "Find the area of a parallelogram with base 9 cm and height 6 cm.", "expressions": [],
                "answer": {"type": "expression", "latex": "54"}, "marks": 2, "class_level": 7, "traps": []}  # fmt: skip
    right = ["\\text{Area = } 9 \\text{ cm} \\times 6 \\text{ cm}", "\\text{Area = } 54 \\text{ cm}^2"]
    assert gradeLines(ai, question, right)["score"] == 2  # '\text{Area = }' once made every line unreadable -> 0
    unreadable = ["\\text{Area is } 9 \\text{ times } 6"]
    assert gradeLines(ai, question, unreadable)["status"] == "needs_confirmation"  # our reading failed, not the student


def testAProbabilityNamedPOfSixAndAnAnswerInsideWordsAreRead(ai: FakeAi) -> None:
    question = {"text": "A die is thrown 60 times and 6 turns up 15 times. Find the experimental probability of a 6.", "expressions": ["15 / 60"],
                "answer": {"type": "expression", "latex": "\\frac{1}{4}"}, "marks": 2, "class_level": 9, "traps": []}  # fmt: skip
    wrong = gradeLines(ai, question, ["\\text{Probability of getting 6:}", "P(6) = 1 / 6", "\\text{Ans: 1/6}"])
    assert wrong["wrongLine"] == 2 and "1}{6}" in wrong["explanation"]  # theoretical 1/6 instead of 15/60
    assert gradeLines(ai, question, ["P(6) = 15 / 60", "P(6) = 1 / 4", "\\text{Ans: 1/4}"])["score"] == 2


def testALostSquareThatCancelsOutIsStillAMistake(ai: FakeAi) -> None:
    question = {"text": "Evaluate: 2 tan²45° + cos²30° − sin²60°", "expressions": ["2 \\tan^2 45^\\circ + \\cos^2 30^\\circ - \\sin^2 60^\\circ"],
                "answer": {"type": "expression", "latex": "2"}, "marks": 2, "class_level": 10, "traps": []}  # fmt: skip
    wrong = ["\\tan 45^\\circ = 1", "\\cos 30^\\circ = \\sqrt{3}/2", "\\sin 60^\\circ = \\sqrt{3}/2",
             "= 2(1) + \\sqrt{3}/2 - \\sqrt{3}/2", "= 2 + 0", "= 2"]  # fmt: skip
    result = gradeLines(ai, question, wrong)
    # 0.5: the three trig values were written right (CBSE gives that step); the answer mark is lost.
    assert result["wrongLine"] == 4 and result["score"] == 0.5 and "squares" in result["explanation"]
    assert [step["verdict"] for step in result["steps"]][4:] == ["carried", "carried"]  # built on the mistake: no ✓
    right = ["\\tan 45^\\circ = 1", "= 2(1)^2 + (\\sqrt{3}/2)^2 - (\\sqrt{3}/2)^2", "= 2(1) + 3/4 - 3/4", "= 2"]
    right_result = gradeLines(ai, question, right)
    assert right_result["score"] == 2 and right_result["wrongLine"] is None  # the same numbers, squared: right


def testALessonStartsWithWhatTheStudentGotRight() -> None:
    from app.agents.visual import buildMistakeIntro, findRightSoFar

    lines = ["r = 6", "x + 2 = 5", "x = 3", "y = 2x", "y = 5"]
    steps = [
        {"line_no": 1, "verdict": "note"},
        {"line_no": 2, "verdict": "correct"},
        {"line_no": 3, "verdict": "correct"},
        {"line_no": 4, "verdict": "incorrect"},
        {"line_no": 5, "verdict": "carried"},
    ]
    right = findRightSoFar(lines, steps, 4, "used the arc length formula", {"used the arc length formula"})
    assert right == {"lines": [{"line": 2, "latex": "x + 2 = 5"}, {"line": 3, "latex": "x = 3"}], "givens": ["r = 6"], "oneIdea": True}
    assert findRightSoFar(lines, steps, 4, "wrong step", set())["oneIdea"] is False  # a generic slip proves nothing about the method

    from types import SimpleNamespace

    question = SimpleNamespace(traps=[], solution={})
    board = buildMistakeIntro(question, "en", None, 4, "y = 2x", "fact", None, rightSoFar=right)  # type: ignore[arg-type]
    assert board["frames"][0]["caption"].startswith("First, look at what you got right.")
    assert "up to line 3" in board["frames"][0]["caption"]
    nothing = {"lines": [], "givens": [], "oneIdea": False}
    assert buildMistakeIntro(question, "en", None, 4, "y = 2x", "fact", None, rightSoFar=nothing)["frames"][0]["caption"].startswith("Look at line 4")  # type: ignore[arg-type]


def testAFixMadeDuringTheWalkthroughEndsTheWalkthrough() -> None:
    # The student fixed the whole mistake while the tutor was walking them through small steps: praise and move on.
    from app.agents.tutor import decideTurn

    assert decideTurn("walkthrough", 0, 1, 7, "maths", True, None) == ("praise", "quick_check", 0, 1)
    assert decideTurn("walkthrough", 0, 1, 7, "maths", None, True) == ("walk_next", "walkthrough", 0, 2)  # one step only


def testAFixWrittenLooselyIsJudgedByTheValueItEndsOn() -> None:
    from app.agents.tutor import checkClaim

    state = {"question": SECTOR, "lines": ["r = 6", "= (60/360) * 2 * (22/7) * 6"], "wrongLine": 2}
    assert checkClaim(state, "60/360 x 22/7 x 6^2 = 132/7")["fixCorrect"] is True  # 'x' as times, ends on the answer
    assert checkClaim(state, "60/360 x 22/7 x 6 = 44/7")["fixCorrect"] is not True


def testReachingTheAnswerMidWalkthroughEndsIt(ai: FakeAi) -> None:
    # A correct STEP keeps the walkthrough going; the right FINAL answer ends it with praise.
    step = runTutorTurn(ai, pairState("walkthrough", "7y = 35", step=2))
    assert step["task"] == "walk_next"
    sector = {
        **tutorState("walkthrough", "Mujhe pi r square use karna tha. Area = 60/360 x 22/7 x 6^2 = 132/7"),
        "question": SECTOR, "lines": ["r = 6", "= (60/360) * 2 * (22/7) * 6"], "wrongLine": 2, "facts": "arc length used",
        "steps": [{"explain": "Simplify the angle part", "latex": "\\frac{60}{360} = \\frac{1}{6}"},
                  {"explain": "Multiply", "latex": "\\frac{1}{6} \\times \\frac{22}{7} \\times 36 = \\frac{132}{7}"}],
        "step": 0,
    }  # fmt: skip
    done = runTutorTurn(ai, sector)
    assert done["task"] == "praise" and done["nextStage"] in ("quick_check", "practice")  # the live bug: it kept asking 60/360


def testMathsThatLostItsBackslashesIsRepairedForDisplay() -> None:
    from app.ai.prompts import restoreLostBackslashes

    assert restoreLostBackslashes("angle $90^circ$ (use $pi = 22/7$)") == "angle $90^\\circ$ (use $\\pi = 22/7$)"
    assert restoreLostBackslashes("Say pi times two") == "Say pi times two"  # words outside maths are untouched
    assert restoreLostBackslashes("$\\frac{1}{2}$") == "$\\frac{1}{2}$"  # correct LaTeX is unchanged
