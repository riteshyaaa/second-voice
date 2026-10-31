"""Local end-to-end smoke: register → session → transcribe → reconstruct →
confirm → synthesize → audio. Exits non-zero on any failure."""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import wave

API = os.environ.get("SMOKE_API", "http://127.0.0.1:8000")
WEB = os.environ.get("SMOKE_WEB", "http://127.0.0.1:3000")


def wait(url: str, timeout: int = 90) -> None:
    for _ in range(timeout * 2):
        try:
            urllib.request.urlopen(url, timeout=3)
            return
        except Exception:
            time.sleep(0.5)
    raise SystemExit(f"TIMEOUT waiting for {url}")


def call(method: str, path: str, body=None, token: str | None = None, raw: bytes | None = None, ctype: str = "application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Content-Type": ctype, **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main() -> None:
    wait(API + "/healthz")
    wait(WEB + "/")

    email = f"smoke{int(time.time())}@test.app"
    st, out = call("POST", "/api/v1/auth/register", {"email": email, "password": "password12345"})
    assert st == 200, out
    token = json.loads(out)["access_token"]

    st, out = call("POST", "/api/v1/audio/sessions", {"title": "smoke", "language": "en"}, token)
    assert st == 200, out
    sid = json.loads(out)["id"]

    wav_path = os.path.join(os.environ.get("TEMP", "/tmp"), "smoke.wav")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 1600)
    with open(wav_path, "rb") as f:
        wav = f.read()
    st, out = call("POST", f"/api/v1/audio/sessions/{sid}/audio", raw=wav, token=token, ctype="audio/wav")
    assert st == 200, out
    audio_id = json.loads(out)["audio_id"]

    st, out = call("POST", f"/api/v1/transcription/manual?audio_id={audio_id}&manual_transcript=I+want+meet+doctor&language=en", token=token)
    assert st == 200, out
    tid = json.loads(out)["transcript_id"]

    st, out = call("POST", "/api/v1/reconstruction", {"transcript_id": tid}, token)
    assert st == 200, out
    sug = json.loads(out)
    assert sug["proposed_text"], sug
    print("SUGGESTION:", sug["proposed_text"], "| provider:", sug["provider"])

    st, out = call("POST", "/api/v1/confirmation",
                   {"suggestion_id": sug["suggestion_id"], "final_text": "I want to meet my doctor.",
                    "language": "en", "source": "edited", "save_as_learning": True}, token)
    assert st == 200, out
    mid = json.loads(out)["approved_message_id"]

    st, out = call("POST", "/api/v1/speech/synthesize", {"approved_message_id": mid}, token)
    assert st == 200, (st, out)
    audio_url = json.loads(out)["audio_url"]
    audio_req = urllib.request.Request(API + audio_url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(audio_req, timeout=30) as r:
        blob = r.read()
    assert blob[:4] == b"RIFF", blob[:16]
    print("TTS WAV bytes:", len(blob))

    st, out = call("GET", "/api/v1/feedback/stats", token=token)
    assert st == 200, (st, out)
    stats = json.loads(out)
    assert stats["corrections_approved"] >= 1, stats
    print("STATS:", {k: stats[k] for k in ("corrections_approved", "words_learned", "suggestions_total")})
    print("SMOKE PASS")


if __name__ == "__main__":
    main()
