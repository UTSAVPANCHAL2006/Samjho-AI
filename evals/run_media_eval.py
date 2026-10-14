# Image and voice eval with the REAL providers (Gemini/OpenRouter vision, Sarvam speech).
# Honest scope: images are font-rendered pages (not real student handwriting); voice is Sarvam's own TTS voice
# read back by Sarvam STT (not real students' recordings). Run from backend/:  uv run python ../evals/run_media_eval.py

import base64
import io
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

EVALS = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS.parent / "backend"))

from app.agents.grading import runGrading  # noqa: E402
from app.agents.tutor import findMaths  # noqa: E402
from app.agents.understand import understandQuestion  # noqa: E402
from app.ai import speech  # noqa: E402
from app.ai.models import AiModels  # noqa: E402
from app.ai.prompts import READ_QUESTION_PROMPT  # noqa: E402
from app.config import getSettings  # noqa: E402
from app.maths import checker  # noqa: E402

FONTS = ["/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf", "/System/Library/Fonts/Supplemental/Chalkboard.ttc", "/System/Library/Fonts/Helvetica.ttc"]

QUESTION_PHOTOS = [
    (["Solve the following pair of linear equations:", "2x + 3y = 11", "2x − 4y = −24"], "x = -2, y = 5"),
    (["An AP is 2, 7, 12, 17, ...", "Find the sum of the first 20 terms."], "990"),
    (["Solve: x² − 5x + 6 = 0"], "x = 2 or x = 3"),
    (["Q3. Solve  x/2 + 3 = 7"], "x = 8"),
    (["Find the mean of 2, 4, 6, 8, 10."], "6"),
    (["Find the HCF of 96 and 404."], "4"),
    (["Find the volume of a cylinder of radius 7 cm", "and height 10 cm. (Take π = 22/7)"], "1540"),
    (["Evaluate: sin 60° cos 30° + sin 30° cos 60°"], "1"),
]
WORKING_PHOTO = (["2x + 3y = 11", "2x − 4y = −24", "7y = −13", "y = −13/7"], 3)  # sign error on line 3 (line 1-2 copy the question)
SPOKEN_ANSWERS = [  # (what the student says, the maths the tutor must find)
    ("Maine x barabar aath likha", "x = 8"),
    ("teen x barabar pandrah", "3x = 15"),
    ("y ki value paanch hai", "5"),
    ("saat y barabar paintees", "7y = 35"),
    ("x equals minus two", "x = -2"),
    ("answer nau sau nabbe aaya", "990"),
]


def renderPage(lines: list[str]) -> bytes:
    font = next((ImageFont.truetype(path, 48) for path in FONTS if Path(path).exists()), ImageFont.load_default())
    image = Image.new("RGB", (1100, 120 + 90 * len(lines)), (250, 248, 240))
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((60, 50 + index * 90), line, fill=(20, 30, 90), font=font)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def answerText(result: Any) -> str:
    return checker.formatAnswer(result.parts[0]["answer"]) if result.status == "solved" else f"[{result.status}]"


def matches(result: Any, expected: str) -> bool:
    if result.status != "solved":
        return False
    lines = [part.strip() for chunk in expected.split(" or ") for part in chunk.split(", ")] if "=" in expected else [expected]
    return checker.isFinalAnswerCorrect(result.parts[0]["answer"], lines)


def main() -> None:
    settings = getSettings()
    ai = AiModels(settings)
    report = ["# Image and voice eval (real providers)", "", "Images: font-rendered pages, NOT real handwriting. Voice: Sarvam TTS voice read by Sarvam STT, NOT real students.", ""]

    report += ["## Question photos → read → understood → solved", "", "| Photo text | Read as | Answer | Expected | Pass |", "|---|---|---|---|---|"]
    passed = 0
    for lines, expected in QUESTION_PHOTOS:
        reading = ai.readImage(READ_QUESTION_PROMPT, renderPage(lines), "image/png") or {}
        readText = str(reading.get("question", ""))
        result = understandQuestion(readText, ai) if readText else None
        ok = bool(result and matches(result, expected))
        passed += ok
        report.append(f"| {' / '.join(lines)} | {readText.replace(chr(10), ' / ')[:90]} | {answerText(result) if result else '[not read]'} | {expected} | {'✓' if ok else '✗'} |")
        time.sleep(2)
    report += ["", f"Question photos: **{passed}/{len(QUESTION_PHOTOS)}** solved correctly.", ""]

    page = EVALS / "tmp_working.png"
    page.write_bytes(renderPage(WORKING_PHOTO[0]))
    question = {"text": "Solve 2x + 3y = 11 and 2x - 4y = -24", "expressions": ["2x + 3y = 11", "2x - 4y = -24"], "answer": {"type": "point", "values": {"x": "-2", "y": "5"}}, "marks": 3, "class_level": 10, "traps": []}
    graded = runGrading(ai, {"question": question, "imagePath": str(page), "mediaType": "image/png", "confidenceThreshold": 0.8})
    page.unlink()
    readLines = [line["latex"] for line in graded.get("lines", [])]
    report += [
        "## Photo of working with a sign error",
        "",
        f"Read lines: {readLines} · status: {graded.get('status')} · wrong line: {graded.get('wrongLine')} (expected {WORKING_PHOTO[1]}) · "
        f"{'✓' if graded.get('wrongLine') == WORKING_PHOTO[1] else '✗'}",
        f"Explanation shown: {graded.get('explanation')}",
        "",
    ]

    report += ["## Voice: spoken answer → Sarvam STT → maths found by the tutor", "", "| Said | Transcript | Maths found | Expected | Pass |", "|---|---|---|---|---|"]
    voicePassed = 0
    for said, expected in SPOKEN_ANSWERS:
        audio = speech.speak(said, "hinglish", settings)
        transcript = speech.transcribe(base64.b64decode(audio), "hinglish", settings) if audio else None
        found = findMaths(transcript or "")
        ok = found is not None and checker.isSameAnswer(found, expected) is True
        voicePassed += ok
        report.append(f"| {said} | {transcript} | {found} | {expected} | {'✓' if ok else '✗'} |")
    report += ["", f"Spoken answers: **{voicePassed}/{len(SPOKEN_ANSWERS)}** turned into the right maths.", ""]
    (EVALS / "media_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
