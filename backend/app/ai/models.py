# One small client for every AI model. Groq, Gemini and OpenRouter all speak the OpenAI chat API,
# so a call is: try model 1 -> (rate limited? wait, retry once) -> model 2 -> ... -> None.
# None means "AI unavailable"; every caller has a safe fallback, so the app never guesses.

import base64
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "openrouter": "https://openrouter.ai/api/v1",
}
RATE_LIMIT_WAIT_SECONDS = 2.0
MAX_RATE_LIMIT_WAIT_SECONDS = 12.0  # never keep a student waiting longer than this per model
# Live conversation (tutor): answer fast or fall back to a template — never leave a student waiting.
LIVE_TIMEOUT_SECONDS = 10.0
LIVE_RATE_LIMIT_WAIT_SECONDS = 1.5


RATE_LIMIT_COOLDOWN_SECONDS = 30.0
MAX_EXTRA_WAIT_SECONDS = 10.0  # the most one background request waits for a rate limit to clear before its last try
rateLimitedUntil: dict[str, float] = {}  # provider -> time until which it is tried last (it just said 429)


def orderModels(models: list[tuple[str, str, str]], prefer: str | None) -> list[tuple[str, str, str]]:
    """Preferred provider first; a provider that is rate limited right now goes last instead of making us wait."""
    now = time.monotonic()
    return sorted(
        models,
        key=lambda item: (rateLimitedUntil.get(item[0], 0.0) > now, item[0] != prefer if prefer else False),
    )


class AiModels:
    """Calls the configured text or vision models in fallback order."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def listModels(self, kind: str) -> list[tuple[str, str, str]]:
        """[(provider, model, api_key)] for 'text' or 'vision', skipping providers without a key."""
        names = self.settings.text_models if kind == "text" else self.settings.vision_models
        models = []
        for entry in filter(None, (name.strip() for name in names.split(","))):
            provider, _, model = entry.partition(":")
            apiKey = getattr(self.settings, f"{provider}_api_key", "")
            if apiKey and model and provider in BASE_URLS:
                models.append((provider, model, apiKey))
        return models

    def isAvailable(self, kind: str = "text") -> bool:
        return bool(self.listModels(kind))

    def askJson(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
        secondOpinion: bool = False,
        live: bool = False,
        prefer: str | None = None,
    ) -> dict[str, Any] | None:
        """The model's JSON answer, or None. Same prompt at temperature 0 is served from cache.
        secondOpinion=True starts with the NEXT model, so a check is done by a different model.
        live=True: a student is waiting in a conversation — short timeout, almost no retrying.
        prefer: provider to try first (e.g. "gemini" for long JSON like visuals: fast and rarely rate limited)."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        text = self.complete(
            "text",
            messages,
            temperature,
            True,
            useCache=temperature == 0,
            rotate=secondOpinion,
            live=live,
            prefer=prefer,
        )
        return parseJsonObject(text) if text else None

    def askText(self, messages: list[dict[str, Any]], temperature: float = 0.4, live: bool = True) -> str | None:
        return self.complete("text", messages, temperature, wantsJson=False, useCache=False, live=live)

    def readImage(self, prompt: str, imageBytes: bytes, mediaType: str) -> dict[str, Any] | None:
        """Send a photo to the vision models and return their JSON answer, or None."""
        encoded = base64.b64encode(imageBytes).decode("ascii")
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mediaType};base64,{encoded}"}},
        ]
        text = self.complete("vision", [{"role": "user", "content": content}], 0.0, True, useCache=True)
        return parseJsonObject(text) if text else None

    def complete(
        self,
        kind: str,
        messages: list[dict[str, Any]],
        temperature: float,
        wantsJson: bool,
        useCache: bool,
        rotate: bool = False,
        live: bool = False,
        prefer: str | None = None,
    ) -> str | None:
        models = self.listModels(kind)
        if rotate and len(models) > 1:
            models = models[1:] + models[:1]
        else:
            models = orderModels(models, prefer)
        # The cache key does not depend on which model is tried first: when one provider is rate limited the order
        # changes, and an answer already cached must still be found (not asked again into the same rate limit).
        cachePath = self.findCachePath(kind, sorted(m[1] for m in models), messages) if useCache else None
        if cachePath and cachePath.exists():
            return str(json.loads(cachePath.read_text())["text"])
        # Background work (a solution, an insight, a practice question) gets one more round after a short wait when
        # every provider was rate limited; a live conversation never waits.
        for round in range(1 if live else 2):
            if round == 1:
                waits = [until - time.monotonic() for until in rateLimitedUntil.values() if until > time.monotonic()]
                if not waits:
                    break  # they failed for another reason: waiting will not help
                time.sleep(min(min(waits), MAX_EXTRA_WAIT_SECONDS))
            for index, (provider, model, apiKey) in enumerate(models):
                canFallBack = index < len(models) - 1
                text = self.callModel(provider, model, apiKey, messages, temperature, wantsJson, live, canFallBack)
                if text is not None:
                    if cachePath:
                        cachePath.write_text(json.dumps({"text": text}))
                    return text
        return None

    def callModel(
        self,
        provider: str,
        model: str,
        apiKey: str,
        messages: list[dict[str, Any]],
        temperature: float,
        wantsJson: bool,
        live: bool = False,
        canFallBack: bool = False,
    ) -> str | None:
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
        if wantsJson and provider != "openrouter":
            payload["response_format"] = {"type": "json_object"}
        for attempt in range(3):
            started = time.monotonic()
            try:
                response = httpx.post(
                    f"{BASE_URLS[provider]}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {apiKey}"},
                    timeout=LIVE_TIMEOUT_SECONDS if live else self.settings.model_timeout_seconds,
                )
            except httpx.HTTPError as error:
                logger.warning("model=%s failed error=%s", model, type(error).__name__)
                return None
            if response.status_code == 429:
                rateLimitedUntil[provider] = time.monotonic() + RATE_LIMIT_COOLDOWN_SECONDS
            if response.status_code == 429 and canFallBack:
                logger.warning("model=%s rate limited, trying the next model", model)
                return None  # another model is waiting: do not sit out the rate limit
            if response.status_code == 429 and attempt < (1 if live else 2):
                time.sleep(LIVE_RATE_LIMIT_WAIT_SECONDS if live else readRetryAfter(response))
                continue
            if response.status_code == 400 and "json_validate_failed" in response.text:
                payload.pop("response_format", None)  # some models fail strict JSON mode; parse leniently
                continue
            if response.status_code >= 400:
                logger.warning("model=%s failed status=%s", model, response.status_code)
                return None
            text = readMessageText(response.json())
            logger.info("model=%s ok ms=%d", model, (time.monotonic() - started) * 1000)
            return text
        return None

    def findCachePath(self, kind: str, firstModel: list[str], messages: list[dict[str, Any]]) -> Path:
        digest = hashlib.sha256(json.dumps([kind, firstModel, messages], default=str).encode())
        folder = self.settings.cache_dir / "ai"
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{digest.hexdigest()[:40]}.json"


def readRetryAfter(response: httpx.Response) -> float:
    try:
        seconds = float(response.headers.get("retry-after", RATE_LIMIT_WAIT_SECONDS))
    except ValueError:
        seconds = RATE_LIMIT_WAIT_SECONDS
    return min(max(seconds, RATE_LIMIT_WAIT_SECONDS), MAX_RATE_LIMIT_WAIT_SECONDS)


def readMessageText(body: dict[str, Any]) -> str | None:
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(text, str) or not text.strip():
        return None
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()  # reasoning models think aloud


# Models often write LaTeX with ONE backslash inside JSON ("\frac"), which JSON reads as a form feed.
LATEX_CONTROL_CHARACTERS = {"\f": "\\f", "\t": "\\t", "\b": "\\b", "\r": "\\r"}


def parseJsonObject(text: str) -> dict[str, Any] | None:
    """Parse the JSON object in a model reply, repairing LaTeX backslashes. None if it is not JSON."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    raw = text[start : end + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            # Read backslashes in pairs: a correct '\\\\sqrt' stays, a lone '\\sqrt' (invalid JSON) is doubled.
            # Doubling every lone backslash broke replies that mixed both ('\\\\s' became three backslashes).
            data = json.loads(
                re.sub(r'\\\\|\\(?!["\\/bfnrtu])', lambda match: match.group(0) if len(match.group(0)) == 2 else "\\\\", raw)
            )
        except json.JSONDecodeError:
            return None
    return restoreLatex(data) if isinstance(data, dict) else None


def restoreLatex(value: Any) -> Any:
    if isinstance(value, str):
        for character, latex in LATEX_CONTROL_CHARACTERS.items():
            value = value.replace(character, latex)
        return value
    if isinstance(value, list):
        return [restoreLatex(item) for item in value]
    if isinstance(value, dict):
        return {key: restoreLatex(item) for key, item in value.items()}
    return value
