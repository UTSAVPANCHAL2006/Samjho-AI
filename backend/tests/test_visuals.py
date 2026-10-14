# Chapter visuals built by code (visual_templates.py): each draws, keeps its figure across frames, and ends on the
# right answer computed by SymPy — never a number the AI wrote. Mistake pictures show their way, then the right way.

from typing import Any

import pytest

from app.agents.visual_templates import buildTemplate, chooseByRule, mistakePicture, showsAnswer


def rightLines(visual: dict[str, Any]) -> list[str]:
    return [element["text"] for element in visual["elements"] if element["type"] == "text" and element.get("tone") == "right"]


@pytest.mark.parametrize(
    ("name", "params", "answer"),
    [
        ("power_blocks", {"base": "x", "m": 3, "n": 4, "op": "multiply"}, "x^{7}"),
        ("power_blocks", {"base": "a", "m": 7, "n": 3, "op": "divide"}, "a^{4}"),
        ("power_blocks", {"base": "x", "m": 2, "n": 3, "op": "power"}, "x^{6}"),
        ("solid", {"shape": "cuboid", "quantity": "total_surface_area", "dimensions": {"length": 10, "breadth": 8, "height": 5}}, "340"),
        ("solid", {"shape": "cylinder", "quantity": "volume", "dimensions": {"radius": 7, "height": 10}, "pi": "22/7"}, "1540"),
        ("solid", {"shape": "hemisphere", "quantity": "volume", "dimensions": {"radius": 21}, "pi": "22/7"}, "19404"),
        ("cuboid_net", {"dimensions": {"length": 10, "breadth": 8, "height": 5}}, "340"),
        ("proportionality", {"ad": 4, "db": 6, "ae": 8, "ec": None}, "12"),
        ("histogram", {"intervals": ["0-10", "10-20", "20-30"], "frequencies": [5, 8, 7]}, "16"),
        ("heron", {"a": 6, "b": 8, "c": 10}, "24"),
    ],
)
def testChapterVisualsEndOnTheComputedAnswer(name: str, params: dict[str, Any], answer: str) -> None:
    visual = buildTemplate(name, params, "hinglish")
    assert visual is not None and len(visual["frames"]) >= 2
    assert any(line.rstrip("$").replace(" ", "").endswith(answer.replace(" ", "")) or f"= {answer}$" in line for line in rightLines(visual))


def testNumericChapterVisualsPassTheAnswerCheck() -> None:
    solid = buildTemplate("solid", {"shape": "cylinder", "quantity": "volume", "dimensions": {"radius": 7, "height": 10}, "pi": "22/7"}, "en")
    assert solid is not None and showsAnswer(solid, {"type": "expression", "latex": "1540"})
    assert not showsAnswer(solid, {"type": "expression", "latex": "1541"})


def testTheFigureStaysWhileLaterFramesLabelIt() -> None:
    visual = buildTemplate("proportionality", {"ad": 4, "db": 6, "ae": 8, "ec": None}, "en")
    assert visual is not None
    assert all(element.get("keep") for element in visual["elements"] if element["type"] != "text")


@pytest.mark.parametrize(
    ("params", "reason"),
    [
        ({"base": "x", "m": 30, "n": 4, "op": "multiply"}, "too many blocks to draw"),
        ({"base": "x", "m": 3, "n": 5, "op": "divide"}, "a negative power is not drawn as blocks"),
    ],
)
def testVisualsRefuseWhatTheyCannotDrawHonestly(params: dict[str, Any], reason: str) -> None:
    assert buildTemplate("power_blocks", params, "en") is None, reason
    assert buildTemplate("heron", {"a": 1, "b": 2, "c": 10}, "en") is None  # not a triangle
    assert buildTemplate("proportionality", {"ad": 4, "db": None, "ae": 8, "ec": None}, "en") is None  # two unknowns


def testExponentLawsAreRecognisedWithoutAnyAi() -> None:
    assert chooseByRule(["x^3 \\cdot x^4"], None, None) == ("power_blocks", {"base": "x", "m": 3, "n": 4, "op": "multiply"})
    assert chooseByRule(["\\frac{a^7}{a^3}"], None, None) == ("power_blocks", {"base": "a", "m": 7, "n": 3, "op": "divide"})
    assert chooseByRule(["(x^2)^3"], None, None) == ("power_blocks", {"base": "x", "m": 2, "n": 3, "op": "power"})
    assert chooseByRule(["x^3 \\cdot y^4"], None, None) is None  # different bases: no law of exponents to draw


@pytest.mark.parametrize(
    ("kind", "template", "params"),
    [
        ("simplifying or collecting terms", "power_blocks", {"base": "x", "m": 3, "n": 4, "op": "multiply"}),
        ("used the volume formula instead of the total surface area formula", "solid", {"shape": "cuboid", "quantity": "total_surface_area", "dimensions": {"length": 10, "breadth": 8, "height": 5}}),
        ("used the perimeter a + b + c as s — Heron's s is the SEMI-perimeter (a + b + c)/2", "heron", {"a": 6, "b": 8, "c": 10}),
        ("used aₙ = a + n·d instead of a + (n − 1)d", "ap_stairs", {"first": 4, "difference": 5, "n": 15}),
    ],
)
def testMistakePicturesShowTheirWayThenTheRightWay(kind: str, template: str, params: dict[str, Any]) -> None:
    picture = mistakePicture(kind, "hinglish", template, params)
    assert picture is not None
    tones = [element.get("tone") for element in picture["elements"] if element["type"] == "text"]
    assert "wrong" in tones and "right" in tones
    assert any(str(element.get("text", "")).startswith("Yaad rakho") for element in picture["elements"])


def testANegativePowerIsAStaircaseOfDivisionsNotANegativeNumber() -> None:
    assert chooseByRule(["2^{-3}"], None, None) == ("negative_power", {"base": 2, "n": 3})
    assert chooseByRule(["2^{(-3)}"], None, None) == ("negative_power", {"base": 2, "n": 3})
    assert chooseByRule(["x^{-3}"], None, None) is None  # a letter base has no staircase of values
    visual = buildTemplate("negative_power", {"base": 2, "n": 3}, "hinglish")
    assert visual is not None and rightLines(visual)[-1].endswith("= \\frac{1}{8}$")
    picture = mistakePicture("wrong formula or values", "hinglish", "negative_power", {"base": 2, "n": 3})
    assert picture is not None
    texts = [element["text"] for element in picture["elements"] if element["type"] == "text"]
    assert any("-8" in text for text in texts) and any(text.startswith("Yaad rakho") for text in texts)


def testTheRuleToRememberDoesNotStartLikeAConversation() -> None:
    # The finale card once read "Dekho, sector ka area ..." — a teacher's opener, not a rule.
    from app.agents.visual import addRememberCard

    board = addRememberCard({"frames": [], "elements": []}, "Dekho, sector ka area $\\pi r^2$ se nikalta hai.", "hinglish")
    assert board["elements"][-1]["text"].startswith("Yaad rakho: Sector ka area")


def testLettersOfAnotherScriptNeverReachTheBoardOrTheVoice() -> None:
    from app.ai.speech import removeStrayScripts

    assert removeStrayScripts("Hમેe sirf $60^\\circ$ wala tukda") == "He sirf $60^\\circ$ wala tukda"
    assert removeStrayScripts("हमें $\\frac{1}{6}$ hissa chahiye") == "हमें $\\frac{1}{6}$ hissa chahiye"  # Hindi stays
