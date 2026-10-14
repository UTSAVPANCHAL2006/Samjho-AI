# Concept visual. First choice: a template drawn and calculated by code (visual_templates.py).
# Fallback: the AI writes a small "recipe" (JSON) built from ~11 drawing blocks; the frontend draws it
# in one consistent style. The AI never draws pixels, and every number it writes is checked by SymPy first.

import re
from typing import Any

from app.agents import visual_templates
from app.agents.solution import isLineArithmeticTrue
from app.agents.visual_templates import Board
from app.ai.models import AiModels
from app.ai.prompts import (
    INSIGHT_PROMPT,
    LANGUAGES,
    NARRATE_PROMPT,
    VISUAL_PROMPT,
    VISUAL_TEMPLATE_PROMPT,
    cleanAddress,
    isWrongLanguage,
)
from app.db import Question
from app.maths import checker

CANVAS_WIDTH = 640
CANVAS_HEIGHT = 360
MAX_ELEMENTS = 40
MAX_FRAMES = 8
COLORS = {"blue", "purple", "gold", "green", "red", "gray", "white"}
ELEMENT_TYPES = {
    "bar",
    "grid",
    "numberline",
    "axes",
    "balance",
    "rect",
    "circle",
    "polygon",
    "arrow",
    "text",
    "mark",
}
MATHS_SPAN = re.compile(r"\$([^$]+)\$")


def collectTexts(value: Any) -> list[str]:
    """Every string inside an element (labels, captions, balance items...)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in collectTexts(item)]
    if isinstance(value, list):
        return [text for item in value for text in collectTexts(item)]
    return []


def mathsKey(latex: str) -> str:
    return re.sub(r"\s|\$", "", latex)


def isTextTrue(text: str, wrongLatex: str | None = None) -> bool:
    """All maths written in $...$ (or a bare label like '2x/6') must have true arithmetic — except the student's
    own wrong line, which a picture of their mistake has to show."""
    spans = MATHS_SPAN.findall(text) or ([text] if "=" in text else [])
    allowed = mathsKey(wrongLatex) if wrongLatex else None
    return all(isLineArithmeticTrue(span) or (allowed is not None and mathsKey(span) == allowed) for span in spans)


def cleanElement(element: Any, frameCount: int) -> dict[str, Any] | None:
    if not isinstance(element, dict) or element.get("type") not in ELEMENT_TYPES:
        return None
    cleaned = dict(element)
    try:
        cleaned["frame"] = max(0, min(frameCount - 1, int(element.get("frame", 0))))
    except (TypeError, ValueError):
        cleaned["frame"] = 0
    if cleaned.get("color") not in COLORS:
        cleaned["color"] = "blue"
    return cleaned


def cleanVisual(data: dict[str, Any] | None, wrongLatex: str | None = None) -> dict[str, Any] | None:
    """Keep only what the renderer understands; reject the visual if any written maths is false."""
    if not data or not isinstance(data.get("frames"), list) or not isinstance(data.get("elements"), list):
        return None
    frames = [
        {"caption": str(frame.get("caption") or "").strip()}
        for frame in data["frames"][:MAX_FRAMES]
        if isinstance(frame, dict)
    ]
    if len(frames) < 2:
        return None
    elements = [
        element
        for element in (cleanElement(item, len(frames)) for item in data["elements"][:MAX_ELEMENTS])
        if element is not None
    ]
    if not elements:
        return None
    texts = [frame["caption"] for frame in frames] + [text for element in elements for text in collectTexts(element)]
    if not all(isTextTrue(text, wrongLatex) for text in texts):
        return None
    return {"title": str(data.get("title") or "").strip()[:80], "frames": frames, "elements": elements}


def describeSteps(question: Question) -> str:
    cache = question.solution or {}
    steps = cache.get("detailed_v5_en") or cache.get("en") or []
    return " | ".join(f"{step.get('explain', '')} {step.get('latex') or ''}".strip() for step in steps[:10]) or "(none)"


def chooseByAi(question: Question, ai: AiModels, wrongLatex: str | None, mistakeFacts: str | None) -> tuple[str, dict[str, Any]] | None:
    """The AI only names a template and copies numbers from the question; the numbers are checked to be there."""
    mistake = f"The student's mistake: they wrote ${wrongLatex}$ ({mistakeFacts})" if wrongLatex else ""
    prompt = VISUAL_TEMPLATE_PROMPT.format(
        class_level=question.class_level,
        question=question.text,
        expressions=" ; ".join(question.expressions or []) or "(none)",
        answer=checker.formatAnswer(question.answer),
        mistake=mistake,
    )
    choice = ai.askJson(prompt, "Choose the template.", 0.0, prefer="gemini")
    if not choice or not isinstance(choice.get("template"), str) or not isinstance(choice.get("params"), dict):
        return None
    source = " ".join([question.text, *(question.expressions or []), wrongLatex or ""])
    return (choice["template"], choice["params"]) if visual_templates.isGrounded(choice["params"], source) else None


def makeVisual(
    question: Question,
    language: str,
    ai: AiModels,
    wrongLatex: str | None = None,
    mistakeFacts: str | None = None,
    mistakeKind: str | None = None,
) -> dict[str, Any] | None:
    """A concept visual, or None. Order: a code template chosen by rule (instant, certain) -> a code template
    chosen by the AI (all maths still computed by code) -> the AI's own drawing (every number SymPy-checked)."""
    expressions = [str(item) for item in question.expressions or []]
    visual = None
    chosen = visual_templates.chooseByRule(expressions, mistakeKind, wrongLatex)
    if chosen:
        visual = visual_templates.buildTemplate(*chosen, language)
    if visual is None:
        chosen = chooseByAi(question, ai, wrongLatex, mistakeFacts)
        visual = visual_templates.buildTemplate(*chosen, language) if chosen else None
        if visual is not None and not visual_templates.showsAnswer(visual, question.answer):
            visual = None  # e.g. a circle's AREA drawn for a hemisphere's VOLUME question: right maths, wrong picture
    if visual is not None:
        name, params = chosen if chosen else (None, None)
        mistakeVisual = visual_templates.mistakePicture(mistakeKind, language, name, params)
        return visual_templates.joinVisuals(mistakeVisual, visual) if mistakeVisual else visual
    return drawWithAi(question, language, ai, wrongLatex, mistakeFacts)


def drawWithAi(
    question: Question, language: str, ai: AiModels, wrongLatex: str | None, mistakeFacts: str | None
) -> dict[str, Any] | None:
    """Fallback for questions no template fits. Same inputs at temperature 0 come from the AI cache."""
    mistake = (
        f"The student's mistake: they wrote ${wrongLatex}$. What is wrong (computed): {mistakeFacts}"
        if wrongLatex
        else "There is no student mistake: explain the main idea of the question."
    )
    prompt = VISUAL_PROMPT.format(
        class_level=question.class_level,
        question=question.text,
        answer=checker.formatAnswer(question.answer),
        steps=describeSteps(question),
        mistake=mistake,
        language=LANGUAGES.get(language, LANGUAGES["en"]),
    )
    for temperature in (0.0, 0.5):
        visual = cleanVisual(ai.askJson(prompt, "Design the visual.", temperature, prefer="gemini"), wrongLatex)
        if visual is not None:
            return useStudentsOwnLine(visual, wrongLatex, language)
    return None


HAS_VARIABLE = re.compile(r"(?<![\\a-zA-Z])[a-zA-Z](?![a-zA-Z])")


def useStudentsOwnLine(visual: dict[str, Any], wrongLatex: str | None, language: str = "hinglish") -> dict[str, Any]:
    """A "wrong" note about the student's algebra must show EXACTLY what they wrote — the AI once showed
    x/3 + x/2 = x/5 when the student had written (x+x)/(3+2). Number examples (1/2 + 1/3 = 2/5) are kept."""
    if not wrongLatex:
        return visual
    for element in visual["elements"]:
        text = str(element.get("text") or "")
        maths = " ".join(MATHS_SPAN.findall(text))
        if element.get("type") == "text" and element.get("tone") == "wrong" and HAS_VARIABLE.search(maths):
            element["text"] = f"You wrote: ${wrongLatex}$" if language == "en" else f"Tumne likha: ${wrongLatex}$"
    return visual


# ---------- Understand the mistake: the student's own line first, then a teacher's narration ----------


def findRuleLine(question: Question) -> str | None:
    """The formula line of the verified solution ('\\frac{\\theta}{360} \\pi r^2, ...'), if it has one."""
    cache = question.solution or {}
    for step in cache.get("en") or []:
        latex = str(step.get("latex") or "")
        formula = re.split(r",?\s*\\q?quad", latex)[0].strip()  # '\\frac{\\theta}{360} \\pi r^2, \\quad r = 6' -> the formula
        if formula and HAS_VARIABLE.search(formula):
            return formula
    return None


def buildMistakeIntro(
    question: Question,
    language: str,
    ai: AiModels,
    lineNo: int,
    wrongLatex: str,
    facts: str,
    mistakeKind: str | None,
    insight: str | None = None,
    numbers: list[dict[str, str]] | None = None,
    rightSoFar: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Frames built by code from SymPy facts: what you wrote -> why it is wrong -> the mistake in numbers ->
    (for a formula mistake) the right rule.
    The teacher's note (an AI insight that passed the number checks) is shown with the proven fact when there is one."""
    board = Board("Your mistake, on the board", language)
    if rightSoFar:
        addRightSoFarFrame(board, rightSoFar, lineNo)
    frame = board.say(
        f"Line {lineNo} dekho. Tumne yahan ${wrongLatex}$ likha — galti yahin se shuru hoti hai.",
        f"Look at line {lineNo}. You wrote ${wrongLatex}$ — this is where the mistake starts.",
    )
    board.write(frame, f"Line {lineNo}: ${wrongLatex}$", "wrong")
    frame = board.say(f"Kyun galat hai? {facts}", f"Why is it wrong? {facts}")
    board.write(frame, facts)
    for fact in numbers or []:
        addNumbersFrame(board, fact)
    if insight:
        frame = board.say(insight, insight)
        board.write(frame, insight)  # an explanation, not a right line: no tick
    traps = {trap["mistake"] for trap in question.traps or []}
    rule = findRuleLine(question)
    if rule and mistakeKind and (mistakeKind in traps or "formula" in mistakeKind):
        frame = board.say(
            f"Is sawaal ka sahi rule yeh hai: ${rule}$. Har letter ki jagah sawaal ka number aata hai.",
            f"The right rule for this question is ${rule}$. Each letter gets a number from the question.",
        )
        board.write(frame, f"${rule}$", "right")
    return board.build()


def findRightSoFar(
    lines: list[str], steps: list[dict[str, Any]], rootLine: int, mistakeKind: str | None, traps: set[str]
) -> dict[str, Any]:
    """What the student got right before the mistake, all of it proven: ✓ lines, given values written correctly, and
    (for a known trap) that only one idea broke. A teacher starts here, so the student knows what to keep."""
    right, givens = [], []
    for step in steps:
        lineNo = int(step.get("line_no") or 0)
        if not 0 < lineNo < rootLine:
            continue
        latex = lines[lineNo - 1]
        if step.get("verdict") == "correct":
            right.append({"line": lineNo, "latex": latex})
        elif step.get("verdict") == "note" and checker.readAssignment(latex):
            givens.append(latex)  # 'r = 6': a value read from the question
    return {"lines": right, "givens": givens, "oneIdea": bool(mistakeKind and mistakeKind in traps)}


def addRightSoFarFrame(board: Board, rightSoFar: dict[str, Any], rootLine: int) -> None:
    lines, givens, oneIdea = rightSoFar["lines"], rightSoFar["givens"], rightSoFar["oneIdea"]
    if not lines and not givens and not oneIdea:
        return
    hinglish, english = ["Pehle dekho kya sahi hai."], ["First, look at what you got right."]
    if givens:
        values = ", ".join(f"${given}$" for given in givens)
        hinglish.append(f"Tumne sawaal ki values sahi likhi: {values}.")
        english.append(f"You wrote the question's values correctly: {values}.")
    if lines:
        upto = lines[-1]["line"]
        hinglish.append(f"Line {upto} tak har step sahi hai — yeh sab rakhna hai.")
        english.append(f"Every step up to line {upto} is correct — keep all of it.")
    if oneIdea:
        hinglish.append(f"Aur line {rootLine} mein bhi tumhara tareeka sahi raaste par hai — sirf ek idea galat hua.")
        english.append(f"And in line {rootLine} your method is on the right track — only one idea went wrong.")
    frame = board.say(" ".join(hinglish), " ".join(english))
    for given in givens:
        board.write(frame, f"${given}$", "right")
    for line in lines[-3:]:  # the last few right steps, right before the mistake
        board.write(frame, f"Line {line['line']}: ${line['latex']}$", "right")
    if oneIdea and not lines and not givens:
        board.write(frame, board.pick("Tareeka sahi, ek idea galat", "Right method, one wrong idea"), "right")


def withApprox(latex: str, approx: str | None) -> str:
    return f"{latex} \\approx {approx}" if approx else latex


def addNumbersFrame(board: Board, fact: dict[str, str]) -> None:
    """One proven number check (checker.measureMistake) as a board frame: the mistake measured, not just named."""
    if fact["kind"] == "size":
        given, expected = withApprox(fact["given"], fact.get("givenApprox")), withApprox(fact["expected"], fact.get("expectedApprox"))
        ratio = fact.get("ratio")
        frame = board.say(
            f"Ab numbers se dekho: tumhara answer ${given}$ aaya, par sahi answer ${expected}$ hai."
            + (f" Tumhara answer theek ${ratio}$ guna hai — itna saaf fark ek hi galat factor se aata hai." if ratio else ""),
            f"Now look at the numbers: your answer is ${given}$, but the right answer is ${expected}$."
            + (f" Yours is exactly ${ratio}$ times the right one — a clean factor like that comes from one wrong factor." if ratio else ""),
        )
        board.write(frame, board.pick(f"Tumhara: ${given}$", f"Yours: ${given}$"), "wrong")
        board.write(frame, board.pick(f"Sahi: ${expected}$", f"Right: ${expected}$"), "right")
        if ratio:
            board.write(frame, board.pick(f"Tumhara $= {ratio} \\times$ sahi", f"Yours $= {ratio} \\times$ right"))
    elif fact["kind"] == "plug_in":
        variable, given, left, right = fact["variable"], fact["given"], fact["left"], fact["right"]
        frame = board.say(
            f"Ek pakka check: ${variable} = {given}$ ko sawaal ki equation ${fact['equation']}$ mein wapas daalo. "
            f"Left side ${left}$ aata hai aur right side ${right}$ — dono barabar nahi, isliye ${variable} = {given}$ answer nahi ho sakta.",
            f"A sure check: put ${variable} = {given}$ back into the question's equation ${fact['equation']}$. "
            f"The left side gives ${left}$ and the right side gives ${right}$ — they are not equal, so ${variable} = {given}$ cannot be the answer.",
        )
        board.write(frame, f"${variable} = {given}$: LHS $= {left}$, RHS $= {right}$", "wrong")
        board.write(frame, f"${left} \\neq {right}$", "wrong")
    elif fact["kind"] == "test_point":
        point, question, given = fact["point"], fact["question"], fact["given"]
        questionValue, givenValue = fact["questionValue"], fact["givenValue"]
        frame = board.say(
            f"Ek pakka check: ${point}$ rakh ke dekho. Sawaal wala ${question}$ deta hai ${questionValue}$, par tumhara ${given}$ "
            f"deta hai ${givenValue}$. Sahi tarike se badla hua expression har value par same number deta hai.",
            f"A sure check: try ${point}$. The question's ${question}$ gives ${questionValue}$, but your ${given}$ gives "
            f"${givenValue}$. A correct rewrite gives the same number for every value.",
        )
        board.write(frame, board.pick(f"Sawaal, ${point}$: ${questionValue}$", f"Question at ${point}$: ${questionValue}$"), "right")
        board.write(frame, board.pick(f"Tumhara, ${point}$: ${givenValue}$", f"Yours at ${point}$: ${givenValue}$"), "wrong")


NUMBER_IN_TEXT = re.compile(r"\d+(?:\.\d+)?")
COUNTING_NUMBERS = {str(number) for number in range(13)}  # '4 sides', '2 baar': words a teacher says, not results
# Facts every class knows: angle sums (90, 180, 360), per cent (100), units (60, 1000). A rule may name them.
STANDARD_NUMBERS = {"90", "180", "360", "100", "1000", "60", "24", "365"}
MAX_CAPTION_CHARACTERS = 420


def narrateVisual(
    visual: dict[str, Any], question: Question, language: str, ai: AiModels, wrongLatex: str, facts: str
) -> dict[str, Any]:
    """The AI rewrites each short caption as 2-3 sentences a teacher says. A new caption is used only if it adds no
    number and all its maths is true; otherwise that frame keeps its code-written caption."""
    captions = [str(frame.get("caption") or "") for frame in visual["frames"]]
    prompt = NARRATE_PROMPT.format(
        class_level=question.class_level,
        language=LANGUAGES.get(language, LANGUAGES["en"]),
        question=question.text,
        wrong_latex=wrongLatex,
        facts=facts,
        frames="\n".join(f"{index}. {caption}" for index, caption in enumerate(captions, start=1)),
        count=len(captions),
    )
    data = ai.askJson(prompt, "Narrate the frames.", 0.0, prefer="gemini")
    written = (data or {}).get("captions")
    if isinstance(written, list) and any(isWrongLanguage(str(text or ""), language) for text in written):
        prompt += "\nWrite EVERY caption ONLY in simple English: no Hindi or Hinglish words at all."
        data = ai.askJson(prompt, "Narrate the frames.", 0.0, prefer="gemini")
        written = (data or {}).get("captions")
    if not isinstance(written, list) or len(written) != len(captions):
        return visual
    source = " ".join([*captions, question.text, facts, wrongLatex, *collectTexts(visual["elements"])])
    allowed = set(NUMBER_IN_TEXT.findall(source)) | COUNTING_NUMBERS
    frames = []
    for frame, original, new in zip(visual["frames"], captions, written, strict=True):
        text = cleanAddress(str(new or "").strip())
        isSafe = (
            0 < len(text) <= MAX_CAPTION_CHARACTERS
            and set(NUMBER_IN_TEXT.findall(text)) <= allowed
            and text.count("$") % 2 == 0
            and isTextTrue(text)
            and not isWrongLanguage(text, language)
        )
        frames.append({**frame, "caption": text if isSafe else original})
    return {**visual, "frames": frames}


def findInsight(
    question: Question, lines: list[str], wrongLine: int, facts: str, language: str, ai: AiModels
) -> str | None:
    """The teacher's 'why' for a PROVEN wrong line: which concept went wrong (AI). Shown only when it adds no number
    that is not already in the question, the working or the verified solution, and never states the final answer."""
    steps = (question.solution or {}).get("en") or []
    stepsText = "\n".join(f"{index}. {step.get('explain', '')} {step.get('latex') or ''}" for index, step in enumerate(steps, 1))
    prompt = INSIGHT_PROMPT.format(
        class_level=question.class_level,
        question=question.text,
        lines="\n".join(f"{number}. {line}" for number, line in enumerate(lines, start=1)),
        wrong_line=wrongLine,
        wrong_latex=lines[wrongLine - 1],
        facts=facts,
        steps=stepsText or "(not available)",
        language=LANGUAGES.get(language, LANGUAGES["en"]),
    )
    detailed = " ".join(str(step.get("latex") or "") for step in (question.solution or {}).get("detailed_v4_en") or [])
    traps = " ".join(trap.get("mistake", "") for trap in question.traps or [])
    allowed = set(NUMBER_IN_TEXT.findall(" ".join([question.text, *lines, stepsText, facts, detailed, traps])))
    allowed |= COUNTING_NUMBERS | STANDARD_NUMBERS
    working = set(NUMBER_IN_TEXT.findall(" ".join([question.text, *lines])))
    # Parts of the answer the student has not written. A small number ('1' in 1/a^m) is not a give-away.
    hidden = set(NUMBER_IN_TEXT.findall(checker.formatAnswer(question.answer))) - working - COUNTING_NUMBERS
    for attempt in range(2):
        data = ai.askJson(prompt, "Write the teacher's note.", 0.3 * attempt, prefer="gemini")
        insight = cleanAddress(str((data or {}).get("insight") or "").strip())
        if not insight or len(insight) > MAX_CAPTION_CHARACTERS or insight.count("$") % 2 or not isTextTrue(insight):
            return None
        if isWrongLanguage(insight, language):
            prompt += "\nWrite ONLY in simple English: no Hindi or Hinglish words at all."
            continue
        numbers = set(NUMBER_IN_TEXT.findall(insight))
        leaked = numbers & hidden
        if numbers <= allowed and not leaked:
            return insight
        # It named a number it must not (often a piece of the answer, like the middle term -12x): ask once more.
        prompt += f"\nDo NOT write these numbers (they give away the answer or are not in the work): {', '.join(sorted(leaked or numbers - allowed))}."
    return None


def cleanBoardText(text: str) -> str:
    """'First fraction: \\frac{-6}{10}' -> 'First fraction: $\\frac{-6}{10}$' so the board draws maths, not raw LaTeX."""
    if "$" in text or "\\" not in text:
        return text
    label, separator, maths = text.partition(": ")
    if separator and "\\" in maths and "\\" not in label:
        return f"{label}: ${maths.strip()}$"
    return f"${text.strip()}$"


FIRST_SENTENCE = re.compile(r"^(.+?[.!?।])(?:\s|$)")


RULE_WORDS = re.compile(r"\b(hota hai|hote hain|hoti hai|use karte|use karo|karte hain|is|are|means|always|hamesha|matlab)\b", re.IGNORECASE)
SENTENCES = re.compile(r"[^.!?।]+[.!?।]?")


def pickRuleSentence(insight: str) -> str:
    """The sentence of the insight that states the RULE ('Triangle ke angles ka sum 180° hota hai'), not its first
    sentence, which usually only repeats the mistake ('Line 4 mein tumne ... laga diya')."""
    sentences = [sentence.strip() for sentence in SENTENCES.findall(insight) if sentence.strip()]
    for sentence in sentences:
        if RULE_WORDS.search(sentence) and not re.search(r"\btumne\b|\byou wrote\b|\bline \d", sentence, re.IGNORECASE):
            return str(sentence)
    match = FIRST_SENTENCE.match(insight.strip())
    return str(match.group(1) if match else insight).strip()


def addRememberCard(visual: dict[str, Any], insight: str, language: str) -> dict[str, Any]:
    """The last frame is one rule to remember, so the board ends on the idea and not on a calculation.
    A board that already has a 'Yaad rakho' line (the code-built mistake pictures add one) gets no second card."""
    texts = [str(element.get("text") or "") for element in visual["elements"]] + [str(frame.get("caption") or "") for frame in visual["frames"]]
    if any(re.match(r"\s*(Yaad rakho|Remember)\s*:", text, re.IGNORECASE) for text in texts):
        return visual
    # 'Dekho, sector ka area...' is how a teacher starts talking, not how a rule to remember starts
    rule = re.sub(r"^\s*(?:dekho|suno|look|see|so|toh|achha|ok)\b\s*[,!:—-]?\s*", "", pickRuleSentence(insight), flags=re.IGNORECASE)
    rule = rule[:1].upper() + rule[1:]
    if not rule or rule.count("$") % 2:
        return visual
    label = "Remember" if language == "en" else "Yaad rakho"
    frame = len(visual["frames"])
    return {
        **visual,
        "frames": [*visual["frames"], {"caption": f"{label}: {rule}"}],
        "elements": [*visual["elements"], {"type": "text", "text": f"{label}: {rule}", "tone": "right", "frame": frame, "color": "white"}],
    }


GENERIC_MISTAKES = {"wrong step", "wrong final answer", "wrong formula or values", "simplifying or collecting terms"}


def fallbackInsight(question: Question, mistakeKind: str | None, language: str) -> str | None:
    """When the AI gives no usable note, the known mistake for THIS question still says why — never an empty 'why'.
    Only a specific mistake (a trap or a named misconception) is said; a generic 'wrong step' says nothing new."""
    if not mistakeKind or mistakeKind in GENERIC_MISTAKES:
        return None
    if language == "en":
        return f"The idea that went wrong: you {mistakeKind}. Fix that one idea and redo the line."
    return f"Galti ka asli kaaran: tumne {mistakeKind}. Bas yeh ek baat theek karo aur line dobara likho."
