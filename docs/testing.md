# Testing

## Backend (pytest, 41 tests)
Run from `backend/` — tests import `app.*`, so running from the repo root
fails collection:
```bash
cd backend && ..\..\\.venv\\Scripts\\python -m pytest -q   # Windows project venv
# or: source ../.venv/bin/activate && python -m pytest -q
```
`tests/conftest.py` pins a fresh `.suite.db` before any app import (the
suite previously shared one stale sqlite file, hiding schema drift).
- `test_reconstruction.py` — negation/number guards, abstention, no-flip end to end.
- `test_language.py` — en/hi/hinglish/mr detection, code-switch, translation preserves original.
- `test_evaluation.py` — WER/CER values, guard report.
- `test_confirmation_gate.py` — forged TTS id rejected; confirm → speak works; WAV served.
- `test_personalization.py` — Arav→Aarav correction reused next session; user isolation.
- `test_hierarchy.py` — audio-primary evidence ordering, transcript labelled imperfect.
- `test_audio_norm.py` — upload normalization to mono s16le 16 kHz.
- `test_audio_intelligence.py` (Phase 1) — quality verdicts on synthesized
  fixtures (silence/quiet/clipped/noisy/short/healthy), loud-continuous
  regression (loud ≠ bad), upload + history API assertions.
- `test_asr_orchestration.py` (Phase 2) — interface conformance, fallback
  shape, single-engine orchestration, pure comparison, routing matrix,
  stub-secondary path, compare endpoint. Live key monkeypatched empty —
  the suite never touches the network.

## Frontend (vitest)
```bash
cd frontend && npm test
```
- `tests/align.test.ts` — diff alignment incl. negation visibility.
- Note: on machines where application-control policy blocks Vite's native
  `rollup` binary, `npm test` cannot start; the same assertions were verified
  via `node --test` against the compiled `lib/align.ts` (3/3 pass).

## E2E (manual script, see demo-script.md)
Register → onboard → record/type → review diff → accept → speak → stop →
correct once → verify reuse → reject path → export → delete.

## Evaluation datasets
UASpeech / TORGO may be used only after verifying licence + consent terms;
split by speaker, never by clip; report per-speaker WER, never aggregate-only.
