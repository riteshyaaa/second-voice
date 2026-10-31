# Evaluation Report (prototype, dev-fallback mode)

Measured with the repo's own gates on 2026-10-30 (backend 17/17 green).
Live-Meta numbers require `META_API_KEY` + consented dysarthric samples and
are NOT claimed here.

> Update 2026-10-31: live validation with real recordings + a Meta key is in
> [validation-report.md](validation-report.md) (backend suite now 25/25).
> Headline: exact-ref WER mean 1.10 on single words (0.78 excluding one
> reference artifact), 0 guard violations in 14 adversarial cases, 22/22
> learning/gate checks, sentence Hindi fluent. Dysarthric corpora remain open
> (no lawful access in-session).
> Update 2026-10-31 (pm): Docker verified — `compose up --build`, smoke with
> live meta-spark on Postgres, live Hindi ASR, seed, and `upgrade head`
> all pass; three deployment fallouts fixed (see validation report §13).

## Method
- Unit: `test_reconstruction` (5), `test_language` (5), `test_evaluation` (4).
- Integration: `test_confirmation_gate`, `test_personalization` (Arav→Aarav).
- Metrics: `GET /api/v1/evaluation/compare` (WER/CER + guard report);
  in-app 4-pipeline demo (`POST /api/v1/evaluation/pipeline-demo`).

## Results (rules engine, deterministic)
| Check | Result |
|---|---|
| Negation flip "I don't want to go." → "I want to go." | Rejected (guard fires) |
| Number change "2 tablets" → "5 tablets" | Rejected |
| Empty input | Abstains with clarification question |
| Arav → corrected to Aarav once → next "Arav" | Suggests "Aarav" (rejectable) |
| Cross-user session/vocab access | 404 isolated |
| Unconfirmed TTS | 409 UNCONFIRMED; confirmed → WAV 200 |
| hi / hinglish+code-switch / mr detection | Correct on fixture sentences |
| WER identical strings / one deletion | 0.0 / 0.25 as expected |

## Honest limits
- No dysarthric-speech benchmark run (no consented samples in repo).
- Dev-fallback grammar coverage is intentionally narrow — it abstains rather
  than guess. Live Spark recall must be measured per speaker before any claim.
- No clinical-effectiveness claim is made or implied.
