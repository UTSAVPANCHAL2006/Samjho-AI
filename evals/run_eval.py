# Grading eval: runs the real GradingGraph on labelled typed-line cases and checks the numbers that matter.
# Run from backend/:  uv run python ../evals/run_eval.py      (no AI calls: grading is pure SymPy)
#
#   false accusations  a correct line marked wrong           must be 0
#   zero-mark leaks    marks given to blank/skipped/copied   must be 0
#   verdict agreement  line verdicts match the label         >= 0.85
#   score match        marks match the label exactly         >= 0.80

import json
import sys
from pathlib import Path
from typing import Any

EVALS = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS.parent / "backend"))

from app.agents.grading import runGrading  # noqa: E402
from app.ai.models import AiModels  # noqa: E402
from app.config import Settings  # noqa: E402

THRESHOLDS = {"false_accusations": 0, "zero_mark_leaks": 0, "verdict_agreement": 0.85, "score_match": 0.80}


def grade(ai: AiModels, question: dict[str, Any], lines: list[str]) -> Any:
    return runGrading(
        ai,
        {
            "question": {"traps": [], **question},
            "lines": [{"latex": line, "confidence": 1.0} for line in lines],
            "confidenceThreshold": 0.8,
        },
    )


def main() -> int:
    data = json.loads((EVALS / "data" / "cases.json").read_text(encoding="utf-8"))
    ai = AiModels(Settings(groq_api_key="", gemini_api_key="", openrouter_api_key=""))  # no AI: explanations fall back
    counts = {"lines": 0, "matching": 0, "cases": 0, "score_match": 0, "false_accusations": 0, "zero_mark_leaks": 0}
    failures = []
    for case in data["cases"]:
        result = grade(ai, data["questions"][case["question"]], case["lines"])
        counts["cases"] += 1
        if result.get("score", 0) == case["expected_score"]:
            counts["score_match"] += 1
        else:
            failures.append(f"{case['id']}: marks {result.get('score', 0)}, expected {case['expected_score']}")
        if case["expected_score"] == 0 and result.get("score", 0) > 0:
            counts["zero_mark_leaks"] += 1
        verdicts = [step["verdict"] for step in result.get("steps", [])]
        for expected, actual in zip(case.get("expected_verdicts", []), verdicts, strict=False):
            counts["lines"] += 1
            counts["matching"] += expected == actual
            if expected == "correct" and actual == "incorrect":
                counts["false_accusations"] += 1
                failures.append(f"{case['id']}: FALSE ACCUSATION")
    metrics = {
        "false_accusations": counts["false_accusations"],
        "zero_mark_leaks": counts["zero_mark_leaks"],
        "verdict_agreement": round(counts["matching"] / max(counts["lines"], 1), 3),
        "score_match": round(counts["score_match"] / max(counts["cases"], 1), 3),
    }
    passed = {
        name: value <= THRESHOLDS[name] if name in ("false_accusations", "zero_mark_leaks") else value >= THRESHOLDS[name]
        for name, value in metrics.items()
    }
    report = [f"# Grading eval — {counts['cases']} cases, {counts['lines']} labelled lines", "", "| Metric | Value | Target | |", "|---|---|---|---|"]
    report += [f"| {name} | {value} | {THRESHOLDS[name]} | {'PASS' if passed[name] else 'FAIL'} |" for name, value in metrics.items()]
    report += ["", "## Differences", ""] + ([f"- {failure}" for failure in failures] or ["- none"])
    (EVALS / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return 0 if all(passed.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
