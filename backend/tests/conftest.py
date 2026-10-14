# Test setup: no network, a fresh SQLite database per test, and a fake AI whose answers each test chooses.

import io
import socket
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api import getAi
from app.config import Settings, getSettings
from app.db import getDbSession, setUpDatabase
from app.main import createApp

Answer = dict[str, Any] | None | Callable[[str], dict[str, Any] | None]


class FakeAi:
    """Stands in for AiModels. json maps a piece of the system prompt to the answer for that prompt."""

    def __init__(self) -> None:
        self.json: dict[str, Answer] = {}
        self.secondJson: dict[str, dict[str, Any] | None] = {}  # what the second (independent) model says
        self.thirdJson: dict[str, dict[str, Any] | None] = {}  # the tie-break reading (temperature > 0)
        self.text: str | None = None
        self.image: dict[str, Any] | None = None
        self.calls: list[str] = []

    def isAvailable(self, kind: str = "text") -> bool:
        return True

    def askJson(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
        secondOpinion: bool = False,
        live: bool = False,
        prefer: str | None = None,
    ) -> dict[str, Any] | None:
        self.calls.append(("second: " if secondOpinion else "") + system[:40])
        for key, answer in self.json.items():
            if key in system:
                if secondOpinion and key in self.secondJson:
                    return self.secondJson[key]
                if temperature > 0 and key in self.thirdJson:
                    return self.thirdJson[key]
                return answer(user) if callable(answer) else answer
        return None

    def askText(self, messages: list[dict[str, Any]], temperature: float = 0.4, live: bool = True) -> str | None:
        self.calls.append("text")
        return self.text

    def readImage(self, prompt: str, imageBytes: bytes, mediaType: str) -> dict[str, Any] | None:
        self.calls.append("image")
        return self.image


@pytest.fixture(autouse=True)
def blockNetwork(monkeypatch: pytest.MonkeyPatch) -> None:
    """No real AI or voice calls in tests, ever."""

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("Network access is blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        upload_dir=tmp_path / "uploads",
        cache_dir=tmp_path / "cache",
        groq_api_key="",
        gemini_api_key="",
        openrouter_api_key="",
        speech_provider="browser",
        sarvam_api_key="",
        prepare_ahead=False,  # background work would race the assertions; one test turns it on
    )


@pytest.fixture
def ai() -> FakeAi:
    return FakeAi()


@pytest.fixture
def session(settings: Settings) -> Iterator[Session]:
    engine = create_engine(settings.database_url)
    with sessionmaker(bind=engine, expire_on_commit=False)() as dbSession:
        setUpDatabase(dbSession)
        yield dbSession


@pytest.fixture
def client(session: Session, settings: Settings, ai: FakeAi) -> Iterator[TestClient]:
    app = createApp(setUp=False)
    app.dependency_overrides[getDbSession] = lambda: session
    app.dependency_overrides[getSettings] = lambda: settings
    app.dependency_overrides[getAi] = lambda: ai
    with TestClient(app) as testClient:
        yield testClient


def makePagePhoto(brightness: int = 245) -> bytes:
    """A white page with pen-like strokes: passes the photo quality check."""
    image = Image.new("RGB", (800, 600), (brightness,) * 3)
    draw = ImageDraw.Draw(image)
    for row in range(3):
        draw.text((60, 80 + row * 120), "x^2 - 5x + 6 = 0", fill=(20, 20, 20))
        draw.line((60, 110 + row * 120, 700, 120 + row * 120), fill=(10, 10, 10), width=4)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
