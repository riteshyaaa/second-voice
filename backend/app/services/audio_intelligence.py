"""Audio intelligence, Phase 1: quality assessment on the normalized waveform.

Analyzes the SAME normalized mono-16 kHz PCM that is sent to ASR (via
audio_service.normalize_to_wav16k), so the verdict describes what the
recognizer actually received. The original recording is never touched,
filtered, or blocked — a poor verdict only suggests re-recording.

Metrics are dependency-free heuristics (stdlib only), calibrated on
synthesized fixtures in tests/test_audio_intelligence.py, NOT on provider
behavior. In particular: loud, high-energy, continuous audio scores GOOD —
the live empty-transcript failure on loud valid speech (validation report
§4) is a provider-side issue and must never be mislabelled as bad audio.

Thresholds are v1 heuristics; see LIMITS below. Every value is observable
from the waveform — no model confidence is claimed anywhere here.
"""
import array
import io
import math
import wave

FRAME_MS = 20          # analysis frame length
SILENCE_RMS = 400      # int16 RMS below this counts as silence (~-38 dBFS)
CLIP_LEVEL = 32000     # |sample| at/above this counts as clipped
MIN_DURATION_S = 0.3   # shorter than this is "too_short"
MOSTLY_SILENCE = 0.85  # silence fraction above this is "mostly_silence"
QUIET_RMS = 900        # overall RMS below this is "too_quiet" (~-29 dBFS)
CLIP_FRACTION = 0.01   # clipped-sample fraction above this is "clipping"
NOISY_SNR_DB = 10.0    # SNR estimate below this is "too_noisy"

LIMITS = (
    "Heuristic v1, calibrated on synthesized fixtures only. SNR is a "
    "quiet-frame-floor estimate, not a true noise measurement; thresholds "
    "may misjudge whisper-quiet dysarthric speech as 'too_quiet' and "
    "breathy/noisy-but-intelligible speech as 'too_noisy'. Verdicts advise, "
    "never block: transcription always proceeds."
)


def _read_mono16(wav: bytes) -> tuple[array.array, int]:
    with wave.open(io.BytesIO(wav), "rb") as w:
        n, rate, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        if sw != 2:
            raise ValueError(f"expected 16-bit PCM, got {sw * 8}-bit")
        if n == 0:
            raise ValueError("empty audio (no frames)")
        pcm = array.array("h", w.readframes(n))
    if ch > 1:  # downmix; analysis input is already mono in practice
        mono = array.array("h", (int((pcm[i] + pcm[i + 1]) / 2) for i in range(0, len(pcm) - 1, 2)))
        return mono, rate
    return pcm, rate


def _frame_rms(frames: list[array.array]) -> list[float]:
    out = []
    for fr in frames:
        if not fr:
            out.append(0.0)
            continue
        out.append(math.sqrt(sum(s * s for s in fr) / len(fr)))
    return out


def analyze_wav16k(wav: bytes) -> dict:
    """Assess one normalized WAV. Raises ValueError on undecodable input."""
    samples, rate = _read_mono16(wav)
    total = len(samples)
    duration_s = total / max(rate, 1)
    peak = max((abs(s) for s in samples), default=0)
    mean = sum(samples) / total
    rms = math.sqrt(sum(s * s for s in samples) / total)

    frame_len = max(int(rate * FRAME_MS / 1000), 1)
    frames = [samples[i:i + frame_len] for i in range(0, total, frame_len)]
    fr = _frame_rms(frames)
    silent = [v < SILENCE_RMS for v in fr]
    silence_fraction = sum(silent) / max(len(silent), 1)

    # Longest silence / speech runs (a short pause must NOT read as done).
    longest_sil, longest_sp, cur_sil, cur_sp = 0.0, 0.0, 0.0, 0.0
    step = frame_len / max(rate, 1)
    for s in silent:
        if s:
            cur_sil += step
            cur_sp = 0.0
        else:
            cur_sp += step
            cur_sil = 0.0
        longest_sil = max(longest_sil, cur_sil)
        longest_sp = max(longest_sp, cur_sp)

    clipped = sum(1 for s in samples if abs(s) >= CLIP_LEVEL)
    clipping_fraction = clipped / total

    # SNR estimate: loud-half mean vs quiet-decile mean (observable only).
    ordered = sorted(fr)
    floor = sum(ordered[:max(len(ordered) // 10, 1)]) / max(len(ordered) // 10, 1)
    loud = sum(ordered[len(ordered) // 2:]) / max(len(ordered) - len(ordered) // 2, 1)
    snr_db = round(20 * math.log10(loud / floor), 1) if floor > 0 and loud > 0 else None

    issues: list[str] = []
    if duration_s < MIN_DURATION_S:
        issues.append("too_short")
    if silence_fraction > MOSTLY_SILENCE:
        issues.append("mostly_silence")
    elif rms < QUIET_RMS:
        issues.append("too_quiet")
    if clipping_fraction > CLIP_FRACTION:
        issues.append("clipping")
    # "Loud everywhere" is signal saturating the chain, not competing noise:
    # only flag noise when the loud half itself is modest.
    if (snr_db is not None and snr_db < NOISY_SNR_DB and loud < 12000
            and "mostly_silence" not in issues):
        issues.append("too_noisy")

    if "mostly_silence" in issues or "too_short" in issues:
        quality = "poor"
    elif issues:
        quality = "usable"
    else:
        quality = "good"

    advice = {
        "mostly_silence": "Mostly silence — check the microphone and try again.",
        "too_quiet": "Volume is very low — move closer to the microphone.",
        "clipping": "Recording is distorted (too loud) — move back a little.",
        "too_short": "Recording is very short — hold to finish your sentence.",
        "too_noisy": "Lots of background noise — a quieter spot may help.",
    }
    return {
        "analyzed": True,
        "quality": quality,
        "issues": issues,
        "advice": [advice[i] for i in issues],
        "rerecord_suggested": bool(issues),
        "duration_s": round(duration_s, 2),
        "sample_rate": rate,
        "peak": peak,
        "rms": int(rms),
        "snr_db": snr_db,
        "silence_fraction": round(silence_fraction, 3),
        "clipping_fraction": round(clipping_fraction, 4),
        "longest_silence_s": round(longest_sil, 2),
        "longest_speech_s": round(longest_sp, 2),
    }


def analyze_upload(data: bytes, mime: str) -> dict:
    """Assess raw upload bytes. NEVER raises — analysis must not block upload."""
    try:
        from .audio_service import normalize_to_wav16k

        return analyze_wav16k(normalize_to_wav16k(data, mime))
    except Exception as exc:  # corrupt/unsupported input: record, don't fail
        return {"analyzed": False, "quality": "unknown", "issues": [],
                "advice": [], "rerecord_suggested": False,
                "note": f"quality analysis skipped: {exc}"}
