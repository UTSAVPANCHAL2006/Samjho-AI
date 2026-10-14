# Samjho backend. Run: uv run uvicorn app.main:app --reload
#
# Four folders, four jobs:
#   api/     HTTP endpoints, saving to the database
#   agents/  two LangGraph workflows: grading (red pen) and tutor (the conversation)
#   maths/   SymPy: is a line right, what are the marks — no AI, so marks are never guessed
#   ai/      AI models (Groq / Gemini / OpenRouter with fallback), prompts, photos, Sarvam voice

import logging
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api import checks, questions, students, tutor, voice
from app.config import getSettings
from app.db import SessionFactory, setUpDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def startUp(app: FastAPI) -> AsyncIterator[None]:
    with SessionFactory() as session:
        setUpDatabase(session)
    yield


# Requests that spend money (AI photo reading, tutor replies, Sarvam voice): at most this many per person per
# 10 minutes, so one person - or one script - cannot drain the AI quota and take the app down for everyone.
RATE_LIMITS = {"photo": 30, "tutor": 120, "voice": 120}
RATE_WINDOW_SECONDS = 600


def findLimitGroup(method: str, path: str) -> str | None:
    if method != "POST":
        return None
    if path.startswith("/api/checks") or path.startswith("/api/questions"):
        return "photo"
    if path.startswith("/api/tutor"):
        return "tutor"
    if path.startswith("/api/voice"):
        return "voice"
    return None


def readClientId(request: Request) -> str:
    """The person's address; behind a proxy, the first address in X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def createApp(setUp: bool = True) -> FastAPI:
    app = FastAPI(title="Samjho API", lifespan=startUp if setUp else None)
    recentRequests: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    @app.middleware("http")
    async def limitRequests(request: Request, callNext: Any) -> Response:
        group = findLimitGroup(request.method, request.url.path)
        if group:
            now = time.monotonic()
            times = recentRequests[(readClientId(request), group)]
            while times and now - times[0] > RATE_WINDOW_SECONDS:
                times.popleft()
            if len(times) >= RATE_LIMITS[group]:
                return JSONResponse(
                    {"detail": "Too many requests in a few minutes. Please wait a little and try again."}, status_code=429
                )
            times.append(now)
        response: Response = await callNext(request)
        return response

    @app.middleware("http")
    async def catchUnexpectedErrors(request: Request, callNext: Any) -> Response:
        """Registered BEFORE CORS so it runs inside it: the browser gets a readable message
        instead of a bare 500 without CORS headers, which it would report as 'server unreachable'."""
        try:
            response: Response = await callNext(request)
            return response
        except Exception:
            logging.getLogger("app").exception("unhandled error on %s", request.url.path)
            return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)

    app.add_middleware(
        CORSMiddleware, allow_origins=getSettings().cors_origins, allow_methods=["*"], allow_headers=["*"]
    )
    for router in (questions.router, checks.router, tutor.router, students.router, voice.router):
        app.include_router(router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = createApp()
