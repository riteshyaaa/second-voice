# Second Voice 2.0 — Phase 0 Baseline Report (2026-11-01)

Audit of the existing repo before any 2.0 change. README claims were checked
against code, tests, and live runs — not taken on trust.

## 1. Baseline test results (observed this session)

| Suite | Result | Note |
|---|---|---|
| Backend pytest (`backend/`, `pytest tests`) | **25/25 pass** | After 1 dependency fix (below) |
| Frontend vitest (`npm run test`) | **6/6 pass** | align (3) + auth (3) |
| Docker Compose | 3/3 up | backend + db healthy, frontend up |

Run backend tests from `backend/` — tests import `app.*`, so running from
the repo root fails collection (pre-existing quirk, documented here).

## 2. Bug found and fixed during audit

**Unpinned `starlette` broke the whole API on fresh installs.**
`requirements.txt` pinned `fastapi==0.115.6` but not `starlette`; a fresh
`pip install` now resolves `starlette==1.10.0`, whose `Router` dropped the
`on_startup` kwarg that FastAPI 0.115.6 passes. Result: `import app.main`
raised `TypeError`, so **2 of 7 test files failed collection and the API
could not start** outside the stale Docker image.
Fix (minimal, no behavior change): pinned `starlette==0.41.3` in
`backend/requirements.txt` (top of FastAPI 0.115.6's supported range).
Existing tests `test_confirmation_gate.py` + `test_personalization.py` are
the regression collateral — they failed at import before, pass now.
`@app.on_event("startup")` in `main.py` is deprecated but functional on the
pinned versions; migrate to lifespan in Phase 12, not now.

## 3. What exists — verification ladder

Implemented / unit-tested / live-verified / real-speech / dysarthric-speech:

- **ASR integration** — all five levels except the last. Live Meta
  `POST /asr/transcribe` with `request`+`audio` parts, mono-s16le
  normalization (`audio_service.normalize_to_wav16k`), labelled
  `dev-fallback` without key. Real Wikimedia speech tested (hi/en/mr).
  Dysarthric speech: NOT tested (no dataset access).
- **Evidence hierarchy** — implemented + unit-tested (`test_hierarchy.py`)
  + live-verified. Audio primary, transcript "imperfect interpretation",
  prompt v1.3 pins it. Genuinely good.
- **Reconstruction guards** — implemented + unit-tested + live battery
  (14/14, 0 inventions, 3/3 abstentions). Negation/number guards are
  deterministic and run on Spark output too. Name protection is only via
  vocab-map swap — **no generic proper-noun guard** (weakness §4.3).
- **Confirmation gate** — implemented + API-tested (409 UNCONFIRMED,
  404/401 paths). Server-side, in `api/speech.py`. Solid.
- **Learning loop** — implemented + API-tested 22/22: vocab CRUD, correction
  patterns, consent switches, isolation, wipe, dashboard stats. Reuse proven
  ("Bonnie." → पानी next session).
- **Language core** — heuristic detector + code-switch spans + script prefs
  + explicit-only translation (phrasebook, Spark upgrade path exists).
  Tested on latin-script output; `asr_language` proven unusable (12/12 "en").
- **TTS** — gate solid; **rendering is placeholder tone** unless Azure/
  ElevenLabs keys are configured (neither is). Browser speechSynthesis does
  the real speaking. No real-provider verification exists.
- **Eval endpoints** — `/compare` (WER/CER/guards) + `/pipeline-demo`
  (4-pipeline side-by-side). Metrics are string-level only.
- **Migrations** — single `0001_init.py` mirroring `models.py`. No drift
  detected, but no migration test.

## 4. Architectural weaknesses (prioritized: ASR + evidence first)

1. **Single-ASR dependence.** One provider, no fallback, no comparison.
   Known live failures with no mitigation: deterministic empty transcript on
   loud valid speech (HTTP 200, 3/3 runs); ≤1.3 s embedded-language spans
   silently dropped; short-utterance English-default bias; one script
   collapse (Hindi number → Korean). Retry policy is one blind retry for
   malformed JSON only — no backoff, no ASR retry at all.
2. **No audio intelligence.** No SNR/clipping/silence/energy metrics, no VAD,
   no segmentation. The empty-transcript and dropped-span failures are
   undetectable in-app today (validation caught them offline).
3. **Uncertainty is heuristic-only.** No provider confidence (none exposed),
   no disagreement signal (one provider), no per-segment uncertainty. The
   reliability note passed to Spark is a static string.
4. **Language gaps.** No Marathi-vs-Hindi disambiguation (script-only → mr
   labelled hi); spans are token-tagged hi/en with no `mr` tag path;
   translation is a 9-phrase phrasebook (transparent, but tiny).
5. **No observability/cost layer.** No latency logging per provider call, no
   cost tracking, no health monitoring beyond `status()`, no rate-limit
   tuning evidence (`core/ratelimit.py` exists, limits unverified).
6. **Structural drift from the suggested architecture.** No
   `memory_service.py` (logic inline in `api/memory.py`), single-file
   `models.py`/`schemas.py`, no repositories/middleware/workers packages.
   Cosmetic — do not refactor for its own sake; extract only when a phase
   needs it.
7. **Frontend shows none of the evidence.** No quality status, no
   alternatives view, no uncertainty spans, no reliability note (validation
   report §7 explicitly lists this as next action).
8. **Stray files in repo root:** `Microsoft/`, `pip/` dirs,
   `backend/dbg_probe.py`, `frontend/tsconfig.tsbuildinfo`. Untracked;
   remove after confirming nothing references them.

## 5. Implementation plan (incremental, flagged, stable path kept)

- **Phase 1 — Audio intelligence** (first): new `audio_intelligence.py`
  beside `audio_service.py` (don't touch normalization): SNR estimate,
  clipping/silence/energy metrics on the normalized PCM we already hold;
  store per-audio quality JSON; surface "re-record" nudge. Tests on the
  committed validation corpus (empty-transcript clip must flag).
- **Phase 2 — ASR orchestration**: `ASRProvider` interface; Meta provider
  = current code moved, unchanged behavior default. Secondary provider only
  behind `SECOND_ASR_ENABLED` flag + uncertainty trigger; comparison +
  disagreement record. Benchmark before adopting any second engine.
- **Phase 3 — Evidence package**: per-transcript uncertainty from
  observables (quality metrics + disagreement + instability + emptiness);
  explicit `model_confidence: null` vs heuristic separation. No fake
  phonemes, ever.
- **Phase 4 — Language**: mr/hi lexicon disambiguation, `mr` span tags,
  Spark translation wired behind explicit-request path (phrasebook stays
  offline fallback).
- **Phases 5–6 — Profile**: provenance/version/rollback on vocab+memory
  (migration 0002); reuse-relevance scoring; dashboard shows
  before/after + false-personalization counters.
- **Phase 7 — Reconstruction 2.0**: proper-noun guard, date/time + modal/
  conditional checks, meaning-risk from evidence package, Wonder routing
  unchanged.
- **Phase 8 — Clarification**: span-targeted questions using uncertainty
  spans from Phase 3 (blocked until then — do not build on token spans).
- **Phases 9–10**: typed/phrase input already exists via board + manual
  transcription; add uncertainty display + stop/switch controls; gate
  untouched, regression-test it every phase.
- **Phase 11 — Eval**: speaker-separated harness stubs now (documented
  blocked on dataset licensing); per-speaker WER tables ready.
- **Phase 12 — Hardening**: lifespan, bounded backoff retries, latency/cost
  logging, migration test, backup/restore doc verification.
- **Phase 13 — Frontend**: quality status, alternatives, uncertainty spans,
  reliability note — after Figma/Stitch refinement path is live.

Rule for every phase: inspect → propose → implement modularly → focused
test → full suite → document limits → commit. Feature flags for anything
experimental (`SECOND_*` env). Never break the stable audio→ASR→suggest→
confirm→speak path.

## 6. Phase 1 completion note (2026-11-01)

Delivered: `audio_intelligence.py` (stdlib-only quality verdicts on the
normalized PCM), `AudioAsset.quality` + migration `0002_audio_quality`,
quality + `rerecord_suggested` on upload/transcribe/session-detail
responses, 9 new tests (34/34 suite green), Docker Postgres migrated,
live probe PHASE1-DOCKER-PASS (healthy→good, silence→poor+advice, stable
confirm→speak path intact, gate still 409s unconfirmed).

Two traps found, both documented for later phases:
- **Test suite shared the committed dev sqlite file.** Engine binds at
  import; per-module DATABASE_URL had never taken effect. Fixed with
  `backend/tests/conftest.py` pinning a fresh `.suite.db` before any app
  import. No existing test was modified.
- **init_db stamps alembic head on startup**, so `upgrade head` after a
  rebuild is a no-op and the new column never lands. Had to
  `stamp 0001_init` + `upgrade head` manually. Phase 12 should replace
  stamp-on-startup with migrate-on-startup (or a documented manual step).
- `0002` downgrade written but not executed live. Heuristic LIMITS are in
  the module docstring: SNR is a floor estimate, thresholds uncalibrated
  on real dysarthric speech, verdicts advise and never block.
