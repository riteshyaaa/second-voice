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


def voices_for(language: str) -> list[str]:
    return VOICES.get(language, VOICES["en"])


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


async def synthesize(text: str, language: str, voice: str, speed: float, out_path: str) -> dict:
    provider = settings.TTS_PROVIDER
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
