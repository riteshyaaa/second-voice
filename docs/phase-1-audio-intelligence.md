# Phase 1 — Audio Intelligence Engine (done 2026-11-01)

## What was built and why

The recognizer could fail (empty transcript on loud speech, dropped
code-switch spans) and the app had no way to tell bad audio from a
provider failure. Phase 1 adds recording-quality assessment so the system
can suggest a re-record when the audio is at fault — and, just as
important, stay silent about quality when the audio is fine but ASR failed.

## Design decisions

- **Assess the normalized PCM, not the upload.** Metrics run on the exact
  mono 16 kHz waveform sent to ASR (`normalize_to_wav16k` output), so the
  verdict describes what the recognizer received.
- **Original untouched.** No filtering, no denoising, no blocking. A poor
  verdict only adds advice + `rerecord_suggested: true`; transcription
  always proceeds.
- **Stdlib only.** No new dependencies (`wave`, `array`, `math`).
- **Loud ≠ bad.** A loud continuous fixture (the profile of the live
  empty-transcript clip: 9.25 s, peak ~25371) must score `good` — that
  failure is provider-side and is pinned by a regression test.

## Module: `backend/app/services/audio_intelligence.py`

`analyze_wav16k(wav) -> dict` — raises `ValueError` on undecodable input.
Metrics: duration, peak, RMS, SNR estimate (loud-half mean vs quiet-decile
floor), silence fraction (20 ms frames, RMS < 400), clipping fraction
(|x| ≥ 32000), longest silence/speech runs (short pauses must not read as
"done").

Issues → verdict mapping (heuristic v1):

| Issue | Trigger | Verdict effect |
|---|---|---|
| `too_short` | < 0.3 s | poor |
| `mostly_silence` | silence > 85% | poor |
| `too_quiet` | RMS < 900 (and not mostly silence) | usable |
| `clipping` | > 1% samples clipped | usable |
| `too_noisy` | SNR < 10 dB **and** loud half < 12000 | usable |

The `loud < 12000` guard is deliberate: sound that is loud everywhere is
signal saturating the chain, not competing noise (a pure loud tone has
~0 dB SNR and must not be called noisy). Any issue sets
`rerecord_suggested: true` with one plain-language advice string each.

`analyze_upload(data, mime)` — normalizes then analyzes; **never raises**.
Corrupt input returns `{analyzed: False, quality: "unknown"}` so uploads
can't break.

## Storage: `AudioAsset.quality` + migration `0002_audio_quality`

Nullable JSON column; pre-Phase-1 rows backfill on next transcribe call.
Docker Postgres migrated live (`stamp 0001_init` + `upgrade head` — see
trap below).

## API surface (see `api.md`)

- `POST /audio/sessions/{id}/audio` and `POST /transcription/file` now
  return `audio_quality` + `rerecord_suggested`.
- `POST /transcription` returns the stored (or backfilled) quality.
- `GET /sessions/{id}` items carry `audio_quality` for history display.

## Verification (observed, not claimed)

- 9 new tests in `backend/tests/test_audio_intelligence.py`: silence,
  quiet, clipped, noisy, too-short, healthy, loud-continuous regression,
  never-raises, and an API test (upload verdicts + history persistence).
- Full suite 34/34 green; Docker probe `PHASE1-DOCKER-PASS` (healthy→good,
  silence→poor+advice, confirm→speak path and 409 gate re-verified).

## Traps found (for later phases)

- Suite shared one stale sqlite file (import-time engine binding). Fixed
  with `backend/tests/conftest.py`. No existing test modified.
- `init_db` stamps alembic head on startup, swallowing new migrations.
  Phase 12 should replace stamp-on-startup with migrate-on-startup.

## Limits

Thresholds calibrated on synthesized fixtures only — uncalibrated on real
dysarthric speech; whisper-quiet speech may read `too_quiet`,
breathy-but-intelligible speech `too_noisy`. SNR is a floor estimate, not
a true noise measurement. `0002` downgrade written, not executed live.
No VAD/segmentation yet — that is still Phase 1.D / Phase 3 work; this
phase deliberately stops at whole-clip verdicts.
