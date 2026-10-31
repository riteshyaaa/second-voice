# Testing

## Backend (pytest, 17 tests)
```bash
cd backend && ..\..\\.venv\\Scripts\\python -m pytest -q   # Windows project venv
# or: source ../.venv/bin/activate && python -m pytest -q
```
- `test_reconstruction.py` — negation/number guards, abstention, no-flip end to end.
- `test_language.py` — en/hi/hinglish/mr detection, code-switch, translation preserves original.
- `test_evaluation.py` — WER/CER values, guard report.
- `test_confirmation_gate.py` — forged TTS id rejected; confirm → speak works; WAV served.
- `test_personalization.py` — Arav→Aarav correction reused next session; user isolation.

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
