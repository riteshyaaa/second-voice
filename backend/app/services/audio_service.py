"""Audio validation + private storage with retention metadata."""
import os
import time
import wave

from fastapi import HTTPException

from ..core.config import settings

ALLOWED_MIME = {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3", "audio/webm", "audio/ogg", "audio/mp4", "audio/aac"}
MAX_BYTES = 15 * 1024 * 1024


def storage_dir() -> str:
    d = settings.STORAGE_DIR
    os.makedirs(d, exist_ok=True)
    return d


def validate_audio(filename: str, mime: str, size: int) -> None:
    if size > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"Audio too large ({size} bytes). Max 15 MB.")
    mt = (mime or "").split(";")[0].strip().lower()
    if mt and mt not in ALLOWED_MIME and not mt.startswith("audio/"):
        raise HTTPException(status_code=415, detail=f"Unsupported audio type: {mime}")


def save_audio(user_id: int, session_id: int, data: bytes, mime: str) -> tuple[str, float]:
    validate_audio("", mime, len(data))
    ext = {"audio/wav": ".wav", "audio/x-wav": ".wav", "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/webm": ".webm", "audio/ogg": ".ogg"}.get(
        mime.split(";")[0].strip().lower(), ".bin"
    )
    path = os.path.join(storage_dir(), f"u{user_id}_s{session_id}_{int(time.time()*1000)}{ext}")
    with open(path, "wb") as f:
        f.write(data)
    duration = _probe_duration(path, mime)
    return path, duration


def _probe_duration(path: str, mime: str) -> float:
    try:
        if path.endswith(".wav"):
            with wave.open(path, "rb") as w:
                return w.getnframes() / max(w.getframerate(), 1)
    except Exception:
        pass
    return 0.0


def load_audio(path: str, retention_days: int) -> bytes:
    if not os.path.exists(path):
        raise HTTPException(status_code=410, detail="Audio expired or deleted per retention policy.")
    age_days = (time.time() - os.path.getmtime(path)) / 86400
    if age_days > retention_days:
        raise HTTPException(status_code=410, detail="Audio expired per retention policy.")
    with open(path, "rb") as f:
        return f.read()


def delete_audio(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _mono16(pcm: bytes, channels: int) -> bytes:
    if channels == 1:
        return pcm
    import array

    a = array.array("h", pcm)
    mono = array.array("h", (int((a[i] + a[i + 1]) / 2) for i in range(0, len(a) - 1, 2)))
    return mono.tobytes()


def resample_linear(pcm: bytes, src_rate: int, dst_rate: int = 16000) -> bytes:
    """Dependency-free linear-interpolation resampler (int16 mono)."""
    import array

    if src_rate == dst_rate:
        return pcm
    a = array.array("h", pcm)
    n_in = len(a)
    n_out = int(round(n_in * dst_rate / src_rate))
    out = array.array("h", [0]) * n_out
    for i in range(n_out):
        pos = i * (n_in - 1) / max(n_out - 1, 1)
        j = int(pos)
        frac = pos - j
        s0, s1 = a[j], a[min(j + 1, n_in - 1)]
        out[i] = int(s0 + (s1 - s0) * frac)
    return out.tobytes()


def normalize_to_wav16k(data: bytes, mime: str) -> bytes:
    """Decode any supported container → mono s16le WAV at 16 kHz.

    Meta's ASR endpoint (verified live) requires mono s16le at 16/24 kHz
    with audioEncoding WAV, so every upload is normalized to that shape
    before sending. Original file stays stored untouched for replay.
    """
    import io
    import wave

    mt = (mime or "").split(";")[0].strip().lower()
    if mt in ("audio/wav", "audio/x-wav", "audio/vnd.wave"):
        with wave.open(io.BytesIO(data), "rb") as w:
            n, rate, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
            if ch == 1 and sw == 2 and rate in (16000, 24000):
                return data  # already compliant; don't touch a sample
            pcm = w.readframes(n)
            if sw != 2:
                raise ValueError(f"unsupported WAV sample width: {sw * 8}-bit")
            pcm = _mono16(pcm, ch)
    else:
        import miniaudio

        dec = miniaudio.decode(data, output_format=miniaudio.SampleFormat.SIGNED16)
        rate = dec.sample_rate
        pcm = _mono16(bytes(dec.samples), dec.nchannels)
    pcm = resample_linear(pcm, rate, 16000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm)
    return buf.getvalue()
