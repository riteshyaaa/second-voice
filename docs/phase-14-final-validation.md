# Phase 14 — Final validation (2.0)

Full user flow probed live against Docker on 2026-11-01 (user
`phase14@probe.app`, session 27), both suites green, deliverables audited.
Backend 102/102, frontend 12/12. Earlier real-speech evidence stands in
[validation-report](validation-report.md) (Oct-31 live Meta ASR); this phase
re-verified the complete plumbing with a tone clip plus a manual-transcript
meaning pass, and every safety gate by direct API call.

## Flow probe (observed, Docker)

| Step | Call | Result |
|---|---|---|
| Register + session (hi) | `POST /auth/register`, `POST /audio/sessions` | session 27, audio 25 |
| Upload 1 s tone, live ASR | `POST …/audio`, `POST /transcription` | transcript 23, **empty text**, `provider: meta-asr` (live, not fallback) |
| Abstention evidence | — | `empty_output` risk + `rerecord_suggested: true`, quality `usable/too_noisy`, no invention |
| Meaning pass | manual "I dont want to go to the doctor" → `POST /reconstruction` | proposed unchanged, **abstained: true, risk high, provider meta-spark** — negation preserved, nothing invented |
| Clarification | `GET /questions/23` → 1 question, 0 blockers; `POST …/answer` skip | recorded, "uncertainty preserved by explicit choice" |
| Confirm (edited) | `POST /confirmation` | approved 10, "I don't want to go to the doctor." |
| Speak | `POST /speech/synthesize` + fetch `audio_url` | HTTP 200 audio bytes |
| History | `GET /sessions/27` | full trail: empty ASR + manual-entry (labeled user-typed, never ASR) + 2 pending abstained suggestions + approval |
| Negative: synth unknown id | `POST /speech/synthesize {999999}` | 404 — unconfirmed text never speaks |
| Negative: confirm unknown | `POST /confirmation {999999,…}` | 404 |
| Board contract (Phase 13 re-check) | 12 cards → favorite → tap speak | 1 confirmed + 1 TTS in `/evaluation/interaction` |

## Acceptance criteria (§18) — final disposition

- Register/login, recording/upload, genuine Meta ASR integration, originals
  preserved: PASS (live + suites).
- Hindi/English/Hinglish workflows, language preferences, Marathi: PASS per
  [validation-report](validation-report.md) + Phase 4 tests (live Hindi
  sentence fluent; isolated-word English bias documented as limitation).
- Spark structured suggestions + abstention: PASS (observed abstain above).
- Edit/confirm, TTS supported languages, unconfirmed-never-synthesized
  (server-side): PASS (404s observed; web speech fallback labeled).
- Corrections saved with consent, vocab reuse, review/delete
  personalization: PASS (Phases 5–6, `/learning/patterns`, wipe verified).
- History, retention config, per-user isolation, Docker Compose, env-only
  secrets: PASS.
- Tests + setup docs: PASS (102 + 12, this folder).

## Remaining limitations (not fixed, stated)

1. No dysarthric-speech validation — TORGO/UASpeech need human licensing;
   thresholds uncalibrated on the target population. The demo must not claim
   clinical effectiveness.
2. Second ASR engine: none benchmarked (`second_available()` honest stub);
   single-engine uncertainty is labeled, not hidden.
3. Muse Image shapes unverified → illustrate stays 409 by design.
4. Transliteration (Romanized Hindi output) deferred; unit synonyms
   over-abstain by design.
5. Rate limiter is per-process (single-node); no TLS in Compose (proxy
   terminates); no multi-replica story.
6. Spark abstained on a clean negation sentence (high risk) — safe direction,
   but conservative tuning adds a user review step.

## Next actions for a real deployment

Rotate any secret ever pasted in chat/shell history → set real `JWT_SECRET`
→ TLS proxy → schedule `backup.ps1` → license dysarthric corpora →
benchmark a second ASR engine → calibrate thresholds → re-run this probe.
