# All settings in one place, read from environment variables or backend/.env.

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://homi:homi@localhost:5432/samjho"
    # Comma-separated in the environment: CORS_ORIGINS=https://samjho.vercel.app,http://localhost:3000
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    upload_dir: Path = BACKEND_ROOT / "storage" / "uploads"
    cache_dir: Path = BACKEND_ROOT / "storage" / "cache"

    @field_validator("database_url")
    @classmethod
    def useThePsycopgDriver(cls, value: str) -> str:
        """Render and most hosts give 'postgres://' or 'postgresql://'; SQLAlchemy needs 'postgresql+psycopg://'."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def splitOrigins(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().startswith("["):
            value = json.loads(value)  # '["https://a.app"]' also works
        if isinstance(value, str):
            value = value.split(",")
        if isinstance(value, list):
            return [str(origin).strip().rstrip("/") for origin in value if str(origin).strip()]
        return value

    # Lines the vision model is less sure about than this must be confirmed by the student.
    confidence_threshold: float = 0.80
    # After the red pen, prepare the lesson (board + tutor steps) in the background while the student reads it.
    prepare_ahead: bool = True

    # AI models, tried in this order. Every provider speaks the OpenAI chat API.
    # Each entry is "provider:model"; providers: openai, groq, gemini, openrouter. A provider without a key is skipped.
    # Photo reading tries OpenAI first when OPENAI_API_KEY is set: free tiers throttle under a burst of photos.
    # a third provider: when the free Groq and Gemini quotas run out (429), a student still gets an answer
    text_models: str = "groq:qwen/qwen3.8-27b,openai:gpt-4.1-mini,gemini:gemini-3.5-flash-lite,openrouter:dots-studio/dots-3-note-preview:free"
    vision_models: str = "openai:gpt-4.1-mini,gemini:gemini-3.5-flash-lite,openrouter:dots-studio/dots-3-note-preview:free"
    openai_api_key: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    model_timeout_seconds: float = 30.0

    # Voice: "sarvam" for real STT/TTS, "browser" to let the browser do it (development).
    speech_provider: str = "browser"
    sarvam_api_key: str = ""
    # Teaching voices: Sarvam's "edtech" personas on bulbul:v4-flash (see docs.sarvam.ai -> Text to speech -> Voices).
    sarvam_tts_model: str = "bulbul:v4-flash"
    sarvam_speaker_hinglish: str = "ritu_hi_edtech"
    sarvam_speaker_en: str = "simran_en_edtech"
    sarvam_pace: float = 1.0  # natural speed; the text itself has pauses before key points
    sarvam_temperature: float = 0.75  # more expressive, closer to a real teacher (lower = flatter)


@lru_cache
def getSettings() -> Settings:
    return Settings()
