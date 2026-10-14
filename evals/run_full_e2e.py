# Full student journey on every class-wise set in docs/test-sets-all (real models, live API on :8000):
# question photo -> understand -> wrong + right working photos -> red pen -> Galti samjho (insight + board)
# -> tutor first message -> Poora solution -> practice question. Writes evals/full_e2e_report.md.

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).parents[1]
SETS = ROOT / "docs" / "test-sets-all"
API = "http://localhost:8000/api"
client = httpx.Client(base_url=API, timeout=300)


def postPhoto(path: str, url: str, data: dict[str, str] | None = None) -> dict:
    with open(SETS / path, "rb") as photo:
        response = client.post(url, files={"image": (Path(path).name, photo, "image/png")}, data=data or {})
    return response.json() if response.headers.get("content-type", "").startswith("application/json") else {"error": response.text[:200]}


def runSet(item: dict) -> dict:
    result: dict = {"id": item["id"], "class": item["class"], "misconception": item["misconception"], "problems": []}
    problems = result["problems"]
    understood = postPhoto(item["paths"]["question"], "/questions/photo")
    question = understood.get("question")
    result["understood"] = {"status": understood.get("status"), "text": (question or {}).get("text"), "answer": (question or {}).get("answer_latex"), "message": understood.get("message")}
    if not question:
        problems.append(f"question not understood: {understood.get('status')} {understood.get('message')}")
        return result
    for kind in ("wrong", "right"):
        check = postPhoto(item["paths"][kind], "/checks", {"question_id": question["id"]})
        lines = check.get("lines") or []
        steps = check.get("steps") or []
        summary = {
            "status": check.get("status"),
            "score": check.get("score"),
            "max": check.get("max_score"),
            "wrongLine": check.get("wrong_line"),
            "mistake": check.get("mistake"),
            "explanation": check.get("explanation") or check.get("message"),
            "wrongLatex": lines[check["wrong_line"] - 1]["latex"] if check.get("wrong_line") and lines else None,
            "afterMistakeTicks": sum(
                1 for step in steps if check.get("wrong_line") and step["line_no"] > check["wrong_line"] and step["verdict"] == "correct"
            ),
            "lines": [f"{(steps[index]['verdict'] if index < len(steps) else '-')[:5]:5} {line['latex']}" for index, line in enumerate(lines)],
        }
        result[kind] = summary
        if check.get("status") == "needs_confirmation":
            problems.append(f"{kind}: reading needs confirmation")
            continue
        if kind == "wrong" and not (check.get("score", 0) < check.get("max_score", 0) and check.get("wrong_line")):
            problems.append(f"wrong working not caught: {check.get('status')} {check.get('score')}/{check.get('max_score')}")
        if kind == "right" and check.get("score") != check.get("max_score"):
            problems.append(f"right working lost marks: {check.get('score')}/{check.get('max_score')} line {check.get('wrong_line')}")
        if kind == "right" and any(step["verdict"] == "incorrect" for step in steps):
            problems.append("FALSE ACCUSATION on the right working")
        if check.get("status") != "graded":
            continue
        checkId = check["id"]
        if kind == "wrong" and check.get("wrong_line"):
            visual = client.get(f"/checks/{checkId}/visual", params={"language": "hinglish"}).json()
            frames = (visual.get("visual") or {}).get("frames") or []
            result["insight"] = visual.get("insight")
            result["board"] = [frame["caption"] for frame in frames]
            elements = (visual.get("visual") or {}).get("elements") or []
            result["drawing"] = sorted({element["type"] for element in elements if element.get("type") not in ("text", "mark")})
            result["boardTitle"] = (visual.get("visual") or {}).get("title")
            if not result["drawing"]:
                problems.append("Galti samjho board has no picture (text only)")
            if not visual.get("insight"):
                problems.append("no teacher insight (why) for the mistake")
            if len(frames) < 3:
                problems.append(f"Galti samjho board has only {len(frames)} frames")
            tutor = client.post("/tutor", json={"check_id": checkId, "language": "hinglish"})
            result["tutor"] = tutor.json().get("reply") if tutor.status_code < 300 else f"HTTP {tutor.status_code}"
            if tutor.status_code >= 300:
                problems.append(f"tutor failed: HTTP {tutor.status_code}")
        solution = client.get(f"/checks/{checkId}/solution", params={"language": "hinglish"}).json()
        result[f"{kind}_solution"] = {"verified": solution.get("verified"), "steps": len(solution.get("steps") or []), "answer": solution.get("answer_latex"), "first": [f"{step.get('explain')} | {step.get('latex')}" for step in (solution.get("steps") or [])[:3]]}
        if len(solution.get("steps") or []) < 4:
            problems.append(f"{kind}: solution too short ({len(solution.get('steps') or [])} steps, verified={solution.get('verified')})")
        practice = client.get("/practice", params={"check_id": checkId}).json()
        practiceQuestion = practice.get("question") or {}
        result[f"{kind}_practice"] = {"text": practiceQuestion.get("text"), "chapter": practiceQuestion.get("chapter"), "reason": practice.get("reason")}
        if not practiceQuestion:
            problems.append(f"{kind}: no practice question ({practice.get('reason')})")
    return result


def main() -> int:
    # usage: run_full_e2e.py [id filter, comma separated] [seconds to wait between sets: free-tier AI rate limits]
    only = [part for part in (sys.argv[1] if len(sys.argv) > 1 else "").split(",") if part]
    pause = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    items = [item for item in json.loads((SETS / "manifest.json").read_text()) if not only or any(part in item["id"] for part in only)]
    results = []
    for item in items:
        started = time.monotonic()
        try:
            outcome = runSet(item)
        except Exception as error:  # a crash is a finding, not the end of the run
            outcome = {"id": item["id"], "class": item["class"], "problems": [f"CRASH {type(error).__name__}: {error}"]}
        outcome["seconds"] = round(time.monotonic() - started)
        results.append(outcome)
        time.sleep(pause)
        print(f"{'OK ' if not outcome['problems'] else 'BAD'} {item['id']:34} {outcome['seconds']:4}s  {'; '.join(outcome['problems'])}", flush=True)
    # A partial rerun (some ids) replaces only those sets in the saved results, so the report always covers all sets.
    resultsPath = ROOT / "evals" / "full_e2e_results.json"
    if only and resultsPath.exists():
        rerun = {outcome["id"] for outcome in results}
        kept = [outcome for outcome in json.loads(resultsPath.read_text()) if outcome["id"] not in rerun]
        order = [item["id"] for item in json.loads((SETS / "manifest.json").read_text())]
        results = sorted(kept + results, key=lambda outcome: order.index(outcome["id"]))
    resultsPath.write_text(json.dumps(results, indent=1, ensure_ascii=False))
    return writeReport(results)


def writeReport(results: list[dict]) -> int:
    passed = sum(1 for outcome in results if not outcome["problems"])
    report = [f"# Full student journey — {passed}/{len(results)} sets with no problem", ""]
    report += ["| Class | Sets | Wrong attempt caught (✗ on a line, marks lost) | Right attempt full marks | False accusations |", "|---|---|---|---|---|"]
    for level in sorted({outcome["class"] for outcome in results}):
        inClass = [outcome for outcome in results if outcome["class"] == level]
        caught = sum(1 for outcome in inClass if (outcome.get("wrong") or {}).get("wrongLine") and (outcome["wrong"]["score"] or 0) < (outcome["wrong"]["max"] or 0))
        full = sum(1 for outcome in inClass if (outcome.get("right") or {}).get("score") is not None and outcome["right"]["score"] == outcome["right"]["max"])
        accused = sum(1 for outcome in inClass if "FALSE ACCUSATION on the right working" in outcome["problems"])
        report.append(f"| {level} | {len(inClass)} | {caught}/{len(inClass)} | {full}/{len(inClass)} | {accused} |")
    report.append("")
    for outcome in results:
        report.append(f"## {outcome['id']} — {'OK' if not outcome['problems'] else 'problems'}")
        report += [f"- {problem}" for problem in outcome["problems"]]
        for kind in ("wrong", "right"):
            if kind in outcome:
                summary = outcome[kind]
                report.append(f"- {kind}: {summary['status']} {summary['score']}/{summary['max']}, ✗ line {summary['wrongLine']} `{summary.get('wrongLatex')}` — {summary['explanation']}")
        if outcome.get("misconception"):
            report.append(f"- planted mistake: {outcome['misconception']}")
        if outcome.get("insight"):
            report.append(f"- insight: {outcome['insight']}")
        report.append("")
    (ROOT / "evals" / "full_e2e_report.md").write_text("\n".join(report))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
