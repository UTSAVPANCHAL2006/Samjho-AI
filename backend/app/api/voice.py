# Voice: the browser records the student, Sarvam turns speech into text and the tutor's reply into speech.


from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.ai import speech
from app.config import Settings, getSettings
from app.schemas import SpeakIn

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_AUDIO_BYTES = 5 * 1024 * 1024


def requireSarvam(settings: Settings) -> None:
    if settings.speech_provider != "sarvam" or not settings.sarvam_api_key:
        raise HTTPException(409, "Server voice is off; the browser's speech is used instead.")


@router.get("")
def getVoiceMode(settings: Settings = Depends(getSettings)) -> dict[str, str]:
    """'sarvam' = use /voice/listen and /voice/speak; 'browser' = use the browser's own speech."""
    isSarvam = settings.speech_provider == "sarvam" and bool(settings.sarvam_api_key)
    return {"provider": "sarvam" if isSarvam else "browser"}


@router.post("/listen")
def listen(
    audio: UploadFile = File(...), language: str = Form("hinglish"), settings: Settings = Depends(getSettings)
) -> dict[str, str]:
    requireSarvam(settings)
    audioBytes = audio.file.read(MAX_AUDIO_BYTES + 1)
    if not audioBytes or len(audioBytes) > MAX_AUDIO_BYTES:
        raise HTTPException(400, "Audio must be under 5 MB.")
    text = speech.transcribe(audioBytes, language, settings)
    if text is None:
        raise HTTPException(503, "Voice is not available right now. Please type instead.")
    return {"text": text}


def toTeacherSpeech(text: str, language: str, settings: Settings) -> str:
    """What the voice should read. Maths becomes words by code ('60 by 360', 'pi r squared'); for Hinglish the
    sentence is then written in Devanagari, because a Hindi voice reads Roman Hinglish like a robot. No AI model
    rewrites it, so a number can never be misread (it once said 'three sexy' for 360) and it takes ~1.5 s, not ~12 s."""
    spoken = speech.toSpokenText(text)
    if language != "hinglish":
        return spoken
    return speech.toDevanagari(spoken, settings) or spoken  # Roman Hinglish if transliteration fails: robotic but right


@router.post("/speak")
def speak(
    body: SpeakIn, settings: Settings = Depends(getSettings)
) -> dict[str, str]:
    requireSarvam(settings)
    audio = speech.speak(toTeacherSpeech(body.text, body.language, settings), body.language, settings)
    if audio is None:
        raise HTTPException(503, "Voice is not available right now.")
    return {"audio_base64": audio}
