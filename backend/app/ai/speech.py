# Voice through Sarvam (Indian-accent STT and TTS), plus turning LaTeX into words a teacher would say.

import hashlib
import logging
import re

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

SARVAM_URL = "https://api.sarvam.ai"
LANGUAGE_CODES = {"en": "en-IN", "hinglish": "hi-IN"}
MAX_SPOKEN_CHARS = 500


def transcribe(audio: bytes, language: str, settings: Settings) -> str | None:
    """Student's speech (a WAV recording) -> text. Hinglish comes back in Roman script."""
    try:
        response = httpx.post(
            f"{SARVAM_URL}/speech-to-text",
            headers={"api-subscription-key": settings.sarvam_api_key},
            data={
                "model": "saaras:v3",
                "language_code": LANGUAGE_CODES.get(language, "unknown"),
                "mode": "translit" if language == "hinglish" else "transcribe",
            },
            files={"file": ("speech.wav", audio, "audio/wav")},
            timeout=15,
        )
    except httpx.HTTPError as error:
        logger.warning("sarvam stt failed error=%s", type(error).__name__)
        return None
    if response.status_code >= 400:
        logger.warning("sarvam stt failed status=%s", response.status_code)
        return None
    return str(response.json().get("transcript", "")).strip()


def chooseSpeaker(language: str, settings: Settings) -> str:
    return settings.sarvam_speaker_en if language == "en" else settings.sarvam_speaker_hinglish


def speak(text: str, language: str, settings: Settings) -> str | None:
    """Text -> base64 WAV in a teacher's voice. The same sentence in the same voice is cached, so it costs nothing."""
    text = text[:MAX_SPOKEN_CHARS]
    speaker = chooseSpeaker(language, settings)
    voiceKey = f"{settings.sarvam_tts_model}|{speaker}|{settings.sarvam_pace}|{settings.sarvam_temperature}"
    folder = settings.cache_dir / "speech"
    folder.mkdir(parents=True, exist_ok=True)
    cached = folder / (hashlib.sha256(f"{voiceKey}|{language}|{text}".encode()).hexdigest()[:40] + ".txt")
    if cached.exists():
        return cached.read_text()
    try:
        response = httpx.post(
            f"{SARVAM_URL}/text-to-speech",
            headers={"api-subscription-key": settings.sarvam_api_key},
            json={
                "text": text,
                "language_code": LANGUAGE_CODES.get(language, "hi-IN"),
                "model": settings.sarvam_tts_model,
                "speaker": speaker,
                "pace": settings.sarvam_pace,
                "temperature": settings.sarvam_temperature,
            },
            timeout=15,
        )
    except httpx.HTTPError as error:
        logger.warning("sarvam tts failed error=%s", type(error).__name__)
        return None
    audios = response.json().get("audios") if response.status_code < 400 else None
    if not audios:
        logger.warning("sarvam tts failed status=%s body=%s", response.status_code, response.text[:200])
        return None
    cached.write_text(audios[0])
    return str(audios[0])


# ---------- LaTeX -> spoken words ----------

SPOKEN_SYMBOLS = [
    (r"\\left|\\right", ""),
    (r"\^\{?\\circ\}?|°", " degrees"),
    (r"\\pi", " pi "),
    (r"\\cdot|\\times|×", " into "),
    (r"\\div|÷", " divided by "),
    (r"\\text\{([^{}]*)\}", r" \1 "),
    (r"\\(sin|cos|tan|cot|sec|cosec)", r" \1 "),
]


def speakMaths(latex: str) -> str:
    """'\\frac{x^2}{3} = 12' -> 'x squared by 3 equals 12'."""
    text = latex
    for pattern, words in SPOKEN_SYMBOLS:
        text = re.sub(pattern, words, text)
    for pattern, words in (
        (r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}", r" \1 by \2 "),
        (r"\\sqrt\{([^{}]*)\}", r" root of \1 "),
    ):
        while re.search(pattern, text):
            text = re.sub(pattern, words, text)
    text = re.sub(r"\^\{?2\}?", " squared ", text)
    text = re.sub(r"\^\{?3\}?", " cubed ", text)
    text = re.sub(r"\^\{([^{}]*)\}|\^(\w)", lambda match: f" to the power {match.group(1) or match.group(2)} ", text)
    text = text.replace("=", " equals ").replace("+", " plus ")
    text = re.sub(r"(?<=[\w)])\s*-\s*|(^|\s)-", lambda match: f"{match.group(1) or ''} minus ", text)
    return re.sub(r"\s+", " ", re.sub(r"[{}\\]", " ", text)).strip()


def toSpokenText(reply: str) -> str:
    """Every $...$ maths span in a tutor reply becomes words; the rest stays as it is."""
    return re.sub(r"\$([^$]+)\$", lambda match: speakMaths(match.group(1)), reply).strip()


# ---------- Hinglish for a Hindi voice: Roman script -> Devanagari, without letting an AI touch the maths ----------

# Words Sarvam's transliteration gets wrong in a tutor's sentences ('aata hai' is "comes", not flour).
SPOKEN_FIXES = {"आटा": "आता", "बाई": "बाय", "सब्ज़ाब": "शाबाश", "शबाश": "शाबाश"}


def toDevanagari(text: str, settings: Settings) -> str | None:
    """'Line 3 mein 60 by 360' -> 'लाइन तीन में साठ बाय तीन सौ साठ'. Sarvam's transliteration copies every word
    and says numbers in Hindi; it cannot invent or garble maths the way a language model can. None on failure."""
    folder = settings.cache_dir / "translit"
    folder.mkdir(parents=True, exist_ok=True)
    cached = folder / (hashlib.sha256(text.encode()).hexdigest()[:40] + ".txt")
    if cached.exists():
        return cached.read_text()
    try:
        response = httpx.post(
            f"{SARVAM_URL}/transliterate",
            headers={"api-subscription-key": settings.sarvam_api_key},
            json={"input": text[:1000], "source_language_code": "en-IN", "target_language_code": "hi-IN",
                  "spoken_form": True, "numerals_format": "international"},  # fmt: skip
            timeout=8,
        )
    except httpx.HTTPError as error:
        logger.warning("sarvam transliterate failed error=%s", type(error).__name__)
        return None
    if response.status_code >= 400:
        logger.warning("sarvam transliterate failed status=%s", response.status_code)
        return None
    spoken = str(response.json().get("transliterated_text", "")).strip()
    for wrong, right in SPOKEN_FIXES.items():
        spoken = re.sub(rf"(?<![\u0900-\u097F]){wrong}(?![\u0900-\u097F])", right, spoken)
    if spoken:
        cached.write_text(spoken)
    return spoken or None
