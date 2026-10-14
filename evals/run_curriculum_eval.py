# Curriculum eval: runs the REAL question pipeline (agents/understand.py, real AI models, disk-cached) on the
# hand-written Class 6–10 set and reports, with denominators:
#   pass                 the outcome is one of the accepted ones
#   false success        claimed "solved" with a WRONG answer (must be 0 — the worst failure)
#   unnecessary refusal  a valid question was refused / needed clarification it did not need
#   wrong status         any other mismatch
# It also writes the coverage matrix (coverage.md) from these results — chapters are only marked as
# supported when tests actually pass. Run from backend/:  uv run python ../evals/run_curriculum_eval.py

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

EVALS = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS.parent / "backend"))

from app.agents.understand import understandQuestion  # noqa: E402
from app.ai.models import AiModels  # noqa: E402
from app.ai.prompts import CHAPTERS  # noqa: E402
from app.config import getSettings  # noqa: E402
from app.maths import checker  # noqa: E402
from app.maths.parser import LatexParseError, parseLatex  # noqa: E402


class CountingModels(AiModels):
    """The real models, counting calls so the report can show cost per question."""

    calls = 0

    def complete(self, *args: Any, **kwargs: Any) -> str | None:
        CountingModels.calls += 1
        return super().complete(*args, **kwargs)


def answerMatches(answer: dict[str, Any], expected: str) -> bool:
    if expected == "identity":
        return answer["type"] == "identity"
    if expected.startswith("text:"):
        return answer["type"] == "text" and expected[5:] in answer["value"].lower()
    if "=" not in expected and answer["type"] in ("solution_set", "point"):
        values = answer["values"] if answer["type"] == "solution_set" else list(answer["values"].values())
        try:
            return len(values) == 1 and checker.areExpressionsEquivalent(checker.readValue(values[0]), parseLatex(expected)) is True
        except LatexParseError:
            return False
    lines = [part.strip() for chunk in expected.split(" or ") for part in chunk.split(", ")] if "=" in expected else [expected]
    try:
        return checker.isFinalAnswerCorrect(answer, lines)
    except (LatexParseError, KeyError, TypeError):
        return False


def judge(result: Any, expects: list[str]) -> str:
    for expected in expects:
        if expected.startswith("status:") and result.status == expected[7:]:
            return "pass"
        if result.status == "solved" and expected.startswith("parts:"):
            wanted = expected[6:].split("|")
            if len(result.parts) == len(wanted) and all(answerMatches(part["answer"], value) for part, value in zip(result.parts, wanted, strict=True)):
                return "pass"
        if result.status == "solved" and not expected.startswith(("status:", "parts:")) and answerMatches(result.parts[0]["answer"], expected):
            return "pass"
    if result.status == "ai_unavailable":
        return "provider limit"
    wantedAnswer = any(not expected.startswith("status:") for expected in expects)
    if result.status == "solved":
        return "false success"
    return "unnecessary refusal" if wantedAnswer else "wrong status"


def rate(counts: dict[str, int]) -> str:
    total = sum(counts.values())
    return f"{counts.get('pass', 0)}/{total}"


def chapterStatus(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Not tested"
    passed = [row for row in rows if row["outcome"] == "pass"]
    computed = [row for row in passed if row["status"] == "solved" and row["trust"] == "verified"]
    honestlyUnsupported = [row for row in passed if row["status"] == "unsupported"]
    if len(passed) == len(rows) and len(computed) >= 2:
        return "Implemented and tested"
    if len(passed) == len(rows) and computed:
        return "Implemented, insufficiently tested"
    if passed and len(honestlyUnsupported) == len(passed) and not computed:
        return "Not yet supported (refused honestly)"
    if passed:
        return "Partially supported"
    return "Not yet supported"


def main() -> int:
    cases = json.loads((EVALS / "data" / "curriculum_v1.json").read_text(encoding="utf-8"))["cases"]
    ai = CountingModels(getSettings())
    rows = []
    for index, case in enumerate(cases, start=1):
        callsBefore, started = CountingModels.calls, time.monotonic()
        result = understandQuestion(case["text"], ai)
        if result.status == "ai_unavailable":  # free-tier rate limit: wait and retry once, report if it persists
            time.sleep(45)
            result = understandQuestion(case["text"], ai)
        outcome = judge(result, case["expect"])
        got = ", ".join(checker.formatAnswer(part["answer"]) for part in result.parts) if result.status == "solved" else f"[{result.status}] {result.message or ''}"
        trust = result.parts[0]["trust"] if result.parts else "-"
        rows.append({**case, "outcome": outcome, "status": result.status, "got": got, "trust": trust, "seconds": round(time.monotonic() - started, 1), "calls": CountingModels.calls - callsBefore})
        time.sleep(2)  # stay under the free-tier token limits
        print(f"{index:3}/{len(cases)} {outcome:20} {case['text'][:60]!r} -> {got[:70]}", flush=True)

    byOutcome: dict[str, int] = defaultdict(int)
    byClass: dict[Any, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    byFamily: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    byChapter: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        byOutcome[row["outcome"]] += 1
        byClass[row["class"]][row["outcome"]] += 1
        byFamily[row["family"]][row["outcome"]] += 1
        byChapter[(row["class"], row["chapter"])].append(row)
    solved = [row for row in rows if row["status"] == "solved"]
    report = [
        f"# Curriculum eval ({len(rows)} cases, real models, {time.strftime('%Y-%m-%d')})",
        "",
        "| Outcome | Cases |",
        "|---|---|",
        *[f"| {name} | {byOutcome.get(name, 0)}/{len(rows)} |" for name in ("pass", "false success", "unnecessary refusal", "wrong status", "provider limit")],
        "",
        f"Trust of solved answers: verified {sum(row['trust'] == 'verified' for row in solved)}, AI agreement only {sum(row['trust'] == 'ai_agreement' for row in solved)}, single reading {sum(row['trust'] == 'single_reading' for row in solved)} (of {len(solved)}).",
        f"Latency per question: median {sorted(row['seconds'] for row in rows)[len(rows) // 2]} s; AI calls per question: {sum(row['calls'] for row in rows) / len(rows):.1f} on average (cached calls included).",
        "",
        "## By class",
        "",
        "| Class | Pass |",
        "|---|---|",
        *[f"| {'input handling' if key == 0 else key} | {rate(value)} |" for key, value in sorted(byClass.items())],
        "",
        "## By problem family",
        "",
        "| Family | Pass |",
        "|---|---|",
        *[f"| {key} | {rate(value)} |" for key, value in sorted(byFamily.items())],
        "",
        "## Every failure",
        "",
        "| Class | Chapter | Question | Expected | Got | Outcome |",
        "|---|---|---|---|---|---|",
        *[f"| {row['class']} | {row['chapter']} | {row['text'][:80].replace(chr(10), ' ')} | {' / '.join(row['expect'])} | {row['got'][:90]} | {row['outcome']} |" for row in rows if row["outcome"] != "pass"],
    ]
    (EVALS / "curriculum_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    matrix = [
        "# Coverage matrix — Class 6–10 (generated from the curriculum eval, not hand-written)",
        "",
        "Status rules: *Implemented and tested* = every case passes with ≥2 answers computed and verified by code. "
        "*Insufficiently tested* = passes, but fewer computed cases. *Partially supported* = some cases fail. "
        "*Not yet supported* = fails, or is refused honestly. *Not tested* = no case in the eval yet.",
        "",
        "| Class | Chapter (NCERT 2026-27) | Cases | Pass | Status |",
        "|---|---|---|---|---|",
    ]
    for level, titles in CHAPTERS.items():
        for title in titles:
            chapterRows = byChapter.get((int(level), title), []) + [row for (rowClass, chapter), rowsHere in byChapter.items() if rowClass == int(level) and chapter != title and title.startswith(chapter) for row in rowsHere]
            matrix.append(f"| {level} | {title} | {len(chapterRows)} | {sum(row['outcome'] == 'pass' for row in chapterRows)} | {chapterStatus(chapterRows)} |")
    (EVALS / "coverage.md").write_text("\n".join(matrix) + "\n", encoding="utf-8")
    (EVALS / "curriculum_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(report[:12]))
    return 0 if byOutcome.get("false success", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
