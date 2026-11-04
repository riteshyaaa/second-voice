"""TTS: Azure / ElevenLabs when configured, else labelled fallback WAV.

Server-side confirmation gate lives in api/speech.py; this module only
renders audio. Unsupported language/voice → transparent error, never fake.
"""
import math
import os
import struct
import time
import wave

import httpx

from ..core.config import settings
from . import audio_service

VOICES = {
    "en": ["en-US-AriaNeural", "en-IN-NeerjaNeural"],
    "hi": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"],
    "hinglish": ["hi-IN-SwaraNeural", "en-IN-NeerjaNeural"],
    "mr": ["mr-IN-AarohiNeural"],
}

# Google Cloud TTS (API-key REST). Names are curated Standard/Wavenet/
# Neural2 voices that exist in each locale; the locale prefix is always
# validated against the requested language before any call.
GOOGLE_VOICES = {
    "en": ["en-IN-Wavenet-A", "en-IN-Wavenet-B", "en-IN-Standard-A", "en-US-Neural2-A"],
    "hi": ["hi-IN-Wavenet-A", "hi-IN-Wavenet-D", "hi-IN-Standard-A", "hi-IN-Standard-B"],
    "hinglish": ["hi-IN-Wavenet-A", "en-IN-Wavenet-A"],
    "mr": ["mr-IN-Wavenet-A", "mr-IN-Wavenet-B", "mr-IN-Standard-A"],
}

GOOGLE_LANG = {"en": "en-IN", "hi": "hi-IN", "hinglish": "hi-IN", "mr": "mr-IN"}

# Fixed preview lines (no user text ever enters preview).
PREVIEW_LINES = {
    "en": "Hello. This is how I will sound.",
    "hi": "नमस्ते। मैं ऐसे सुनाई दूंगा।",
    "hinglish": "Namaste. This is how I will sound.",
    "mr": "नमस्कार. मी असा ऐकू येईन.",
}


def voices_for(language: str) -> list[str]:
    table = GOOGLE_VOICES if settings.TTS_PROVIDER == "google" else VOICES
    return table.get(language, table["en"])


def check_voice(language: str, voice: str) -> tuple[bool, list[str]]:
    """Is this voice speakable for this language under the active provider?"""
    supported = voices_for(language)
    if not voice:
        return True, supported
    return voice in supported, supported


def _fallback_wav(path: str, text: str) -> None:
    """Valid 1.2 s soft tone placeholder so playback/stop UX is testable."""
    rate, secs = 16000, 1.2
    frames = int(rate * secs)
    buf = bytearray()
    for i in range(frames):
        env = min(i / (rate * 0.05), (frames - i) / (rate * 0.2), 1.0)
        sample = int(0.25 * 32767 * env * math.sin(2 * math.pi * 440 * i / rate))
        buf += struct.pack("<h", sample)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(buf))


async def _synthesize_google(text: str, language: str, voice: str, speed: float, out_path: str) -> dict:
    """Google Cloud TTS via API-key REST. LINEAR16 PCM -> WAV container."""
    key = settings.GOOGLE_TTS_API_KEY
    if not key:
        raise RuntimeError("GOOGLE_TTS_API_KEY is not configured")
    ok, supported = check_voice(language, voice)
    if not ok:
        raise ValueError(f"Voice {voice} not available for {language}.")
    lang_code = GOOGLE_LANG.get(language, "en-IN")
    voice_name = voice or supported[0]
    # The locale prefix must match the requested language — never let a
    # mismatched voice through, even if it is in the list.
    prefix = "-".join(voice_name.split("-")[:2])
    allowed = {lang_code, "en-IN"} if language == "hinglish" else {lang_code}
    if prefix not in allowed:
        raise ValueError(f"Voice {voice_name} ({prefix}) does not match {language}.")
    import base64

    url = "https://texttospeech.googleapis.com/v1/text:synthesize"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, params={"key": key}, json={
            "input": {"text": text},
            "voice": {"languageCode": lang_code, "name": voice_name},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 16000,
                            "speakingRate": min(4.0, max(0.25, speed))}})
    if resp.status_code >= 400:
        raise RuntimeError(f"Google TTS error {resp.status_code}")
    try:
        pcm = base64.b64decode(resp.json()["audioContent"])
    except (ValueError, KeyError) as exc:
        raise RuntimeError(f"Google TTS malformed response: {exc}") from exc
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm)
    return {"provider": "google", "voice": voice_name, "fallback": False}


async def synthesize(text: str, language: str, voice: str, speed: float, out_path: str) -> dict:
    provider = settings.TTS_PROVIDER
    if provider == "google":
        return await _synthesize_google(text, language, voice, speed, out_path)
    if provider == "azure" and settings.AZURE_SPEECH_KEY:
        vs = voice or (voices_for(language)[0] if voices_for(language) else "")
        headers = {"Ocp-Apim-Subscription-Key": settings.AZURE_SPEECH_KEY, "Content-Type": "application/ssml+xml", "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm"}
        ssml = f"<speak version='1.0' xml:lang='{language}'><voice name='{vs}'><prosody rate='{speed}'>{text}</prosody></voice></speak>"
        url = f"https://{settings.AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, content=ssml.encode())
        if resp.status_code >= 400:
            raise RuntimeError(f"Azure TTS error {resp.status_code}")
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return {"provider": "azure", "voice": vs, "fallback": False}
    if provider == "elevenlabs" and settings.ELEVENLABS_API_KEY:
        voice_id = voice or "21m00Tcm4TlvDq8ikWAM"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": settings.ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                json={"text": text, "model_id": "eleven_multilingual_v2"},
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"ElevenLabs error {resp.status_code}")
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return {"provider": "elevenlabs", "voice": voice_id, "fallback": False}
    # Transparent fallback: real WAV file, honestly labelled.
    _fallback_wav(out_path, text)
    return {"provider": "webspeech-fallback", "voice": voice or "browser-speechSynthesis", "fallback": True,
            "note": "No TTS key configured — placeholder tone served; browser speaks the confirmed text via speechSynthesis."}


def tts_path(user_id: int, msg_id: int) -> str:
    d = audio_service.storage_dir()
    return os.path.join(d, f"tts_u{user_id}_m{msg_id}_{int(time.time()*1000)}.wav")
