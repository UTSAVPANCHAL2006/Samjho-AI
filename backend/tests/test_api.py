# End-to-end through HTTP with a fake AI: question -> check -> tutor -> solution -> practice -> progress.

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.api.students import countStreak
from tests.conftest import FakeAi, makePagePhoto

QUADRATIC = "c10_quad_01"  # x^2 - 5x + 6 = 0, 3 marks


def typedCheck(client: TestClient, lines: list[str], studentId: str | None = None) -> dict[str, Any]:
    response = client.post(
        "/api/checks/typed", json={"question_id": QUADRATIC, "lines": lines, "student_id": studentId}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def testBankQuestionsAreListedWithoutGivingTheMethodAway(client: TestClient) -> None:
    questions = client.get("/api/questions?class_level=10").json()
    assert questions and all(question["class_level"] == 10 for question in questions)
    wordProblem = next(
        question for question in client.get("/api/questions").json() if question["id"] == "c10_circles_01"
    )
    assert wordProblem["expressions"] == []  # the hidden calculation is the method


def testTypedQuestionIsSolvedAndSavedWithItsVerifiedSteps(client: TestClient) -> None:
    result = client.post("/api/questions", json={"text": "Solve:\n2x + 3y = 11\n2x - 4y = -24"}).json()
    assert result["status"] == "solved" and result["question"]["trust"] == "verified"
    question = client.get(f"/api/questions/{result['question']['id']}").json()
    assert question["expressions"] == ["2x + 3y = 11", "2x - 4y = -24"]


def testUnclearQuestionGetsASpecificStatusNotAGenericFailure(client: TestClient) -> None:
    result = client.post("/api/questions", json={"text": "Solve x + y = 10"}).json()
    assert result["status"] == "needs_clarification" and result["understood"] == ["x + y = 10"]


def testNonMathsIsRefused(client: TestClient, ai: FakeAi) -> None:
    ai.json["ONLY to understand it"] = {"scope": "not_maths", "parts": []}
    result = client.post("/api/questions", json={"text": "who won the match?"}).json()
    assert result["status"] == "not_maths" and "maths" in result["message"]


def testWrongFinalAnswerIsMarkedAndExplainedWithTheMisconception(client: TestClient, ai: FakeAi) -> None:
    ai.json["ONLY to understand it"] = {
        "scope": "maths", "question": "AP sum", "class_level": 10, "chapter": "Arithmetic Progressions", "missing": None, "ambiguous": None,
        "parts": [{"text": "Find the sum of the first 20 terms of 2, 7, 12, ...", "family": "progression", "params": {"terms": [2, 7, 12], "ask": "sum", "n": 20}}],
    }  # fmt: skip
    question = client.post(
        "/api/questions", json={"text": "An AP is 2, 7, 12, 17, ... Find the sum of the first 20 terms."}
    ).json()["question"]
    lines = ["S_{20} = \\frac{20}{2}[2 + 19 \\cdot 5]", "S_{20} = 970"]
    check = client.post("/api/checks/typed", json={"question_id": question["id"], "lines": lines}).json()
    # The wrong value 970 first appears in line 1 (a used instead of 2a); line 2 only repeats it.
    assert (check["status"], check["score"], check["wrong_line"]) == ("graded", 0, 1)
    assert "needs 2a, not a" in check["explanation"]


def testPhotoFlowWithConfirmation(client: TestClient, ai: FakeAi) -> None:
    ai.image = {
        "page": "maths",
        "lines": [{"latex": "(x-2)(x-3)=0", "confidence": 0.95}, {"latex": "x=2", "confidence": 0.4}],
    }
    first = client.post(
        "/api/checks", files={"image": ("page.png", makePagePhoto(), "image/png")}, data={"question_id": QUADRATIC}
    ).json()
    assert first["status"] == "needs_confirmation" and first["lines"][1]["needs_check"]
    assert client.get(f"/api/checks/{first['id']}/photo").status_code == 200
    confirmed = client.post(f"/api/checks/{first['id']}/confirm", json={"lines": ["(x-2)(x-3)=0", "x=2", "x=3"]}).json()
    assert (confirmed["status"], confirmed["score"]) == ("graded", 3)


def testTutorConversationEndsInPractice(client: TestClient, ai: FakeAi) -> None:
    check = typedCheck(client, ["(x+2)(x+3)=0", "x=-2", "x=-3"])
    assert check["wrong_line"] == 1
    start = client.post("/api/tutor", json={"check_id": check["id"], "language": "hinglish"}).json()
    assert start["stage"] == "hints" and start["focus_line"] == 1
    fixed = client.post(f"/api/tutor/{start['chat_id']}", json={"text": "(x-2)(x-3)=0"}).json()
    assert fixed["fix_correct"] is True and fixed["show_practice"]  # no quick check offline -> practice
    practice = client.get(f"/api/practice?check_id={check['id']}").json()
    assert practice["question"]["id"] != QUADRATIC


def testEmptyTypedAttemptIsBlankNotACrash(client: TestClient) -> None:
    assert typedCheck(client, ["  "])["status"] == "blank"


def testNoTutorWhenThereIsNoMistake(client: TestClient) -> None:
    check = typedCheck(client, ["(x-2)(x-3)=0", "x=2", "x=3"])
    assert client.post("/api/tutor", json={"check_id": check["id"]}).status_code == 409


def testSolutionUnlocksOnlyAfterAnAttemptAndEquationsAreSolvedByCode(client: TestClient, ai: FakeAi) -> None:
    skipped = typedCheck(client, ["skip"])
    assert client.get(f"/api/checks/{skipped['id']}/solution").status_code == 409
    attempt = typedCheck(client, ["(x+2)(x+3)=0"])
    solution = client.get(f"/api/checks/{attempt['id']}/solution").json()
    assert solution["verified"] is True and solution["answer_latex"] == "x = 2 \\text{ or } x = 3"
    assert "(x - 3) (x - 2) = 0" in [step["latex"] for step in solution["steps"]]
    # The maths comes from the equation solver. The AI is only asked to write the teacher's explanation around it;
    # with no usable reply (the fake AI), the SymPy-verified steps are shown as they are.
    assert ai.calls and all(call.startswith("You are a CBSE maths teacher TEACHING") for call in ai.calls)


def testAiWrittenSolutionIsShownOnlyWhenEveryLineChecksOut(client: TestClient, ai: FakeAi) -> None:
    lines = ["x^2 + 5x + 25"]  # c8_identities_01: expand (x+5)^2 — not an equation, so the AI writes the steps
    attempt = client.post("/api/checks/typed", json={"question_id": "c8_identities_01", "lines": lines}).json()
    ai.json["full worked solution"] = {"steps": [{"explain": "Square each term", "latex": "x^2 + 25"}]}
    wrong = client.get(f"/api/checks/{attempt['id']}/solution").json()
    assert wrong["verified"] is False and wrong["steps"] == []  # a wrong AI solution is never shown
    ai.json["full worked solution"] = {
        "steps": [
            {"explain": "(a+b)^2 = a^2 + 2ab + b^2", "latex": "x^2 + 2 \\cdot 5x + 25"},
            {"explain": "", "latex": "x^2 + 10x + 25"},
        ]
    }
    right = client.get(f"/api/checks/{attempt['id']}/solution").json()
    assert right["verified"] is True and len(right["steps"]) == 2


def testProgressAndStreakPerStudent(client: TestClient) -> None:
    riya = client.post("/api/students", json={"name": "Riya", "class_level": 10}).json()
    aman = client.post("/api/students", json={"name": "Aman", "class_level": 10}).json()
    typedCheck(client, ["(x-2)(x-3)=0", "x=2", "x=3"], riya["id"])
    progress = client.get(f"/api/students/{riya['id']}/progress").json()
    assert (progress["streak_days"], progress["checks_done"], progress["full_marks"]) == (1, 1, 1)
    assert client.get(f"/api/students/{aman['id']}/progress").json()["checks_done"] == 0


def testProgressShowsRecurringMistakesAndWhatToRevise(client: TestClient) -> None:
    riya = client.post("/api/students", json={"name": "Riya", "class_level": 10}).json()
    for _ in range(2):  # the same slip twice: 6 should stay -6 on the left, not become +6 on the right
        typedCheck(client, ["x^2 - 5x = 6", "x = 6"], riya["id"])
    progress = client.get(f"/api/students/{riya['id']}/progress").json()
    assert progress["mistakes"] == [
        {"mistake": "moving terms across the = sign", "times": 2, "chapters": ["Quadratic Equations"]}
    ]
    assert progress["chapters"][0]["needs_revision"] is True
    typedCheck(client, ["(x-2)(x-3)=0", "x=2", "x=3"], riya["id"])  # latest attempt is right: no longer to revise
    assert client.get(f"/api/students/{riya['id']}/progress").json()["chapters"][0]["needs_revision"] is False


def testOldDatabaseGetsTheNewColumn(settings: Any) -> None:
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import sessionmaker

    from app.db import setUpDatabase

    engine = create_engine(settings.database_url.replace(".db", "_old.db"))
    with engine.begin() as connection:  # a 'checks' table from before the mistake column existed
        connection.execute(text("CREATE TABLE checks (id VARCHAR(36) PRIMARY KEY, status VARCHAR(32))"))
    with sessionmaker(bind=engine)() as session:
        setUpDatabase(session)
    assert "mistake" in {column["name"] for column in inspect(engine).get_columns("checks")}


def testStreakCounting() -> None:
    today = date(2026, 10, 11)
    assert countStreak({today, today - timedelta(days=1), today - timedelta(days=4)}, today) == 2
    assert countStreak({today - timedelta(days=1)}, today) == 1  # alive until tonight
    assert countStreak({today - timedelta(days=2)}, today) == 0


def testVoiceIsOffWithoutSarvam(client: TestClient) -> None:
    assert client.get("/api/voice").json() == {"provider": "browser"}
    assert client.post("/api/voice/speak", json={"text": "Namaste"}).status_code == 409


def testAStaleStudentIdNeverBreaksChecking(client: TestClient) -> None:
    check = typedCheck(client, ["(x-2)(x-3)=0", "x=2", "x=3"], studentId="deleted-student")
    assert check["status"] == "graded"


def testUnexpectedErrorsReachTheBrowserReadablyWithCors(session: Any, settings: Any) -> None:
    from app.config import getSettings
    from app.db import getDbSession
    from app.main import createApp

    app = createApp(setUp=False)
    app.dependency_overrides[getDbSession] = lambda: session
    app.dependency_overrides[getSettings] = lambda: settings

    @app.get("/api/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/api/boom", headers={"Origin": "http://localhost:3000"}
    )
    assert response.status_code == 500 and "our side" in response.json()["detail"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def testBankChangesReachAnExistingDatabase(session: Any) -> None:
    from app.db import Question, setUpDatabase

    question = session.get(Question, "c10_quad_01")
    question.chapter = "Quadratic equations"  # as an older bank file named it
    session.commit()
    setUpDatabase(session)
    assert session.get(Question, "c10_quad_01").chapter == "Quadratic Equations"


def testGaltiSamjhoSaysWhenThePictureIsMissingSoTheAppAsksAgain(client: TestClient, monkeypatch: Any) -> None:
    attempt = typedCheck(client, ["(x+2)(x+3)=0"])
    board = client.get(f"/api/checks/{attempt['id']}/visual").json()
    assert board["visual"] and board["complete"] is True
    monkeypatch.setattr("app.api.checks.makeVisual", lambda *args, **kwargs: None)  # the drawing failed (busy AI)
    board = client.get(f"/api/checks/{attempt['id']}/visual").json()
    assert board["visual"]["frames"] and board["complete"] is False  # their own line is still shown


def testTooManyPaidRequestsAreTurnedAwayPolitely(client: Any, monkeypatch: Any) -> None:
    # One person (or a script) cannot drain the AI quota: past the limit, a clear 429 instead of more AI calls.
    import app.main

    monkeypatch.setitem(app.main.RATE_LIMITS, "photo", 3)
    codes = [client.post("/api/checks/typed", json={"question_id": "none", "lines": ["x = 1"]}).status_code for _ in range(4)]
    assert codes[:3] != [429, 429, 429] and codes[3] == 429
    assert "try again" in client.post("/api/checks/typed", json={}).json()["detail"].lower()
    assert client.get("/api/health").status_code == 200  # reading is never limited


def testSpokenHinglishKeepsEveryNumberAndNeverAsksAModel(monkeypatch: Any, settings: Any) -> None:
    # Maths is turned into words by code; only the script changes (Sarvam transliteration, faked here).
    from app.ai import speech
    from app.api.voice import toTeacherSpeech

    seen: list[str] = []
    monkeypatch.setattr(speech, "toDevanagari", lambda text, _settings: seen.append(text) or "देवनागरी")
    assert toTeacherSpeech("Line 3 mein $\\frac{60}{360}$ likha", "hinglish", settings) == "देवनागरी"
    assert seen == ["Line 3 mein 60 by 360 likha"]  # the line number and both numbers reach the voice intact
    monkeypatch.setattr(speech, "toDevanagari", lambda text, _settings: None)
    assert toTeacherSpeech("Line 3 mein $\\frac{60}{360}$ likha", "hinglish", settings) == "Line 3 mein 60 by 360 likha"


def testHostedDatabaseUrlsAndCorsOriginsAreReadFromTheEnvironment(monkeypatch: Any) -> None:
    # Render gives 'postgresql://...'; Vercel's address is set as a comma-separated CORS_ORIGINS.
    from app.config import Settings

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@db.render.com:5432/samjho")
    monkeypatch.setenv("CORS_ORIGINS", "https://samjho.vercel.app/, http://localhost:3000")
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql+psycopg://user:secret@db.render.com")
    assert settings.cors_origins == ["https://samjho.vercel.app", "http://localhost:3000"]


def testCorsOriginsAlsoAcceptAJsonList(monkeypatch: Any) -> None:
    from app.config import Settings

    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"]')  # the docker-compose style
    assert Settings(_env_file=None).cors_origins == ["http://localhost:3000"]


def testSlowEndpointsDoNotBlockTheServer() -> None:
    # A plain `def` runs in a worker thread; an `async def` that calls a slow AI model or SymPy would freeze
    # every other request (even /api/health) until the photo is done.
    import inspect

    from app.api import checks, questions, voice

    for endpoint in (checks.checkPhoto, questions.understandQuestionPhoto, voice.listen):
        assert not inspect.iscoroutinefunction(endpoint), endpoint.__name__


def testBlankQuestionPhotoIsNeverSentToTheAi(client: TestClient, ai: FakeAi) -> None:
    # Given a blank page, a vision model once invented a whole question ("a rectangle with length 3x + 1...").
    import io

    from PIL import Image

    blank = io.BytesIO()
    Image.new("RGB", (900, 700), (250, 250, 248)).save(blank, format="PNG")
    ai.image = {"page": "maths", "question": "The length of a rectangle is 3x + 1. Find x."}
    response = client.post("/api/questions/photo", files={"image": ("q.png", blank.getvalue(), "image/png")})
    assert response.json()["status"] == "parse_failed"
    assert "retake" in response.json()["message"]
    assert "image" not in ai.calls


def testAFakeForwardedAddressDoesNotGetPastTheLimit(client: Any, monkeypatch: Any) -> None:
    # X-Forwarded-For is written by the caller: a new fake address per request once walked past the limit.
    import app.main

    monkeypatch.setitem(app.main.RATE_LIMITS, "photo", 2)
    codes = [
        client.post("/api/checks/typed", json={}, headers={"X-Forwarded-For": f"10.0.0.{number}"}).status_code
        for number in range(3)
    ]
    assert codes[2] == 429
    # Behind Cloudflare each real person has their own address and their own limit.
    assert client.post("/api/checks/typed", json={}, headers={"CF-Connecting-IP": "203.0.113.9"}).status_code != 429


def testEveryoneTogetherHasACeiling(client: Any, monkeypatch: Any) -> None:
    import app.main

    monkeypatch.setitem(app.main.ALL_VISITORS_LIMITS, "photo", 2)
    codes = [
        client.post("/api/checks/typed", json={}, headers={"CF-Connecting-IP": f"203.0.113.{number}"}).status_code
        for number in range(3)
    ]
    assert codes[2] == 429  # three different people, but the shared ceiling was 2
