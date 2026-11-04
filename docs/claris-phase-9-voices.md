# CLARIS Phase 9 — Voice expansion (Google Cloud TTS)

Date: 2026-11-04. Status: complete. Marker: `CLARIS-P9-DOCKER-PASS`.

## Goal

More real voices for Hindi and English — behind the same
server-side confirmation gate, with the same honest labelling. XTTS-v2
stays excluded (CPML non-commercial).

## What was built

- Google Cloud TTS provider (`tts_service._synthesize_google`): API-key
  REST, `LINEAR16` PCM at 16 kHz wrapped into a WAV container, speaking
  rate clamped to the API range. Curated per-language voice lists
  (Standard/Wavenet/Neural2 that exist in each locale):
  en → `en-IN-*` (+ one `en-US-Neural2`); hi → `hi-IN-*`;
  mr → `mr-IN-*`; Hinglish spans both `hi-IN` and `en-IN` honestly.
- Locale-prefix validation: the voice's `xx-YY` prefix must match the
  requested language (Hinglish allows either Indian locale). Mismatches
  fail before any network call.
- `check_voice()` is now the single gate used by `/synthesize`
  (previously it only rejected for languages in the Azure table;
  unknown languages now validate against the fallback table and fail
  with a clean 409 instead of a provider error).
- `POST /speech/preview`: fixed sample lines per language — the request
  carries no text field, so nothing user-supplied can enter and no
  confirmation is bypassed. Temp file cleaned after serving.
  Unsupported voice → 409 with the supported list.
- Workspace: voice picker gains a Preview button (fixed sample, honest
  toast naming fallback tone vs selected voice; blob URLs revoked).
- Config: `GOOGLE_TTS_API_KEY` (empty = unconfigured), `TTS_PROVIDER`
  gains `google`; documented in `.env.example`. No secrets in code.

## Verification

- Backend **134/134** (5 new: provider voice tables, 16 kHz WAV
  output + request shape with stubbed HTTP, key/HTTP/malformed/voice
  errors, preview fixed-text + 409, keyless voice list). Frontend
  **18/18**, `tsc` clean.
- Live Docker: default provider serves Azure lists; fallback preview
  returns 200 `audio/wav` with `X-TTS-Fallback: True`; bad voice 409s;
  google lists resolve with `TTS_PROVIDER=google`.
- Docker: backend + frontend rebuilt and healthy; Meta live.
- Headless Chrome: learn renders with no page errors.
- **Not verified live**: real Google synthesis — no API key on hand.
  The HTTP path is unit-covered with a stubbed transport; the
  keyless states are all verified live. First live call needs
  `GOOGLE_TTS_API_KEY` + `TTS_PROVIDER=google`.

## Honest limits

- Voice names are curated from the public locale lists; if Google
  retires one, the failure is a clean 502, not a silent substitution.
- Preview speaks fixed samples only — by design it cannot preview an
  arbitrary sentence. That is the confirmation gate working.
- No voice cloning, no training on user audio — correctly absent.
- Rate limiter is per-process memory; TLS via proxy; single-node.

## Next (Phase 10)

Speaker-disjoint atypical-speech evaluation (needs lawful data access),
performance + limitations report.
