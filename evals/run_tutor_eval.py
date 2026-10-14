# Multi-turn tutor eval with the REAL models, through the real HTTP API (temporary SQLite database).
# Automatic checks per tutor turn, plus full transcripts for a human to read:
#   no leak        the final answer is not given away while the tutor should still be hinting
#   uses their value  when the student states a value, the reply refers to it
#   language       Hinglish in -> Hinglish (Roman script) out; English in -> English out
#   one question   at most one question per reply
#   no repeat      never sends the same reply twice in a row
#   context        the stage/step move as the teaching rules say (problem never restarts)
# Run from backend/:  uv run python ../evals/run_tutor_eval.py

import re
import sys
import tempfile
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

EVALS = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS.parent / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.config import Settings, getSettings  # noqa: E402
from app.db import getDbSession, setUpDatabase  # noqa: E402
from app.main import createApp  # noqa: E402

HINT_TASK_STAGES = {"hints"}
HINGLISH_WORDS = re.compile(r"\b(hai|hain|karo|kar|ko|mein|dekho|toh|kya|nahi|yahan|isliye|chalo|batao|aata|hoga|jaata|wala|bhi)\b", re.IGNORECASE)

SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "Reported conversation (pair of equations, student wrote x = 8)",
        "question": "Solve the following pair of linear equations for x and y:\n2x + 3y = 11\n2x - 4y = -24",
        "working": ["x = 8"],
        "language": "hinglish",
        "answers": ["x = -2", "y = 5", "-2"],
        "turns": [
            ("Maine x = 8 likha", "hints"),
            ("y se nikala", "hints"),
            ("Samjhao, mujhe samajh nahi aaya", "walkthrough"),
            ("7y = 35", "walkthrough"),
            ("y = 5", "walkthrough"),
        ],
    },
    {
        "name": "Sign error when moving a term (3x + 7 = 22)",
        "question": "Solve 3x + 7 = 22",
        "working": ["3x = 22 + 7", "x = 29/3"],
        "language": "hinglish",
        "answers": ["x = 5"],
        "turns": [
            ("kyunki 7 dusri side jaata hai", "hints"),
            ("3x = 22 - 7", "quick_check"),
        ],
    },
    {
        "name": "AP sum with the formula missing 2a (English)",
        "question": "An AP is 2, 7, 12, 17, ... Find the sum of the first 20 terms.",
        "working": ["S_{20} = \\frac{20}{2}[2 + 19 \\cdot 5]", "S_{20} = 970"],
        "language": "en",
        "answers": ["990"],
        "turns": [
            ("I used S = n/2[a + (n-1)d]", "hints"),
            ("I don't understand", "walkthrough"),
        ],
    },
    {
        "name": "Student asks for the full solution (quadratic)",
        "question": "Solve x^2 - 5x + 6 = 0",
        "working": ["(x + 2)(x + 3) = 0", "x = -2", "x = -3"],
        "language": "hinglish",
        "answers": [],
        "turns": [("pura solution batao", "quick_check")],
    },
]


def replyChecks(reply: str, previous: str | None, studentText: str, scenario: dict[str, Any], stageBefore: str) -> dict[str, bool]:
    numbersSaid = re.findall(r"-?\d+", studentText)
    leaked = stageBefore in HINT_TASK_STAGES and any(answer.replace(" ", "") in reply.replace(" ", "") for answer in scenario["answers"])
    hinglish = bool(HINGLISH_WORDS.search(reply)) and not re.search(r"[\u0900-\u097F]", reply)
    return {
        "no leak": not leaked,
        "uses their value": not numbersSaid or any(number in reply for number in numbersSaid),
        "language": hinglish if scenario["language"] == "hinglish" else not HINGLISH_WORDS.search(reply) or len(HINGLISH_WORDS.findall(reply)) < 2,
        "one question": reply.count("?") <= 1,
        "no repeat": previous is None or SequenceMatcher(None, previous, reply).ratio() < 0.8,
    }


def main() -> None:
    folder = Path(tempfile.mkdtemp())
    settings = Settings(database_url=f"sqlite:///{folder / 'tutor.db'}", upload_dir=folder / "uploads", cache_dir=getSettings().cache_dir, speech_provider="browser")
    engine = create_engine(settings.database_url)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    setUpDatabase(session)
    app = createApp(setUp=False)
    app.dependency_overrides[getDbSession] = lambda: session
    app.dependency_overrides[getSettings] = lambda: settings
    client = TestClient(app)
    totals: dict[str, list[bool]] = {}
    stageResults: list[bool] = []
    report = ["# Tutor eval — real models, real API", ""]
    for scenario in SCENARIOS:
        question = client.post("/api/questions", json={"text": scenario["question"]}).json()["question"]
        check = client.post("/api/checks/typed", json={"question_id": question["id"], "lines": scenario["working"]}).json()
        report += [f"## {scenario['name']}", "", f"Working: `{' | '.join(scenario['working'])}` → wrong line {check['wrong_line']}: {check['explanation']}", ""]
        reply = client.post("/api/tutor", json={"check_id": check["id"], "language": scenario["language"]}).json()
        report.append(f"**Tutor:** {reply['reply']}")
        previous, stage = reply["reply"], reply["stage"]
        for studentText, expectedStage in scenario["turns"]:
            time.sleep(3)
            reply = client.post(f"/api/tutor/{reply['chat_id']}", json={"text": studentText}).json()
            checks = replyChecks(reply["reply"], previous, studentText, scenario, stage)
            stageOk = reply["stage"] == expectedStage
            stageResults.append(stageOk)
            for name, value in checks.items():
                totals.setdefault(name, []).append(value)
            failed = [name for name, value in checks.items() if not value] + ([] if stageOk else [f"stage {reply['stage']} ≠ {expectedStage}"])
            report += [f"**Student:** {studentText}", f"**Tutor** _(stage {reply['stage']}{'; ✗ ' + ', '.join(failed) if failed else ''})_: {reply['reply']}"]
            previous, stage = reply["reply"], reply["stage"]
        report.append("")
    summary = ["## Summary", "", "| Check | Passed |", "|---|---|"] + [f"| {name} | {sum(values)}/{len(values)} |" for name, values in totals.items()] + [f"| context (stage moved as expected) | {sum(stageResults)}/{len(stageResults)} |"]
    (EVALS / "tutor_report.md").write_text("\n".join(report[:2] + summary + [""] + report[2:]) + "\n", encoding="utf-8")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
