# Second Voice — Build log: what was built, how it works, issues faced and fixed

Living record of the whole implementation: foundation, 2.0 phases 0–14,
CLARIS phases 0–10, and the post-CLARIS fix batch (Hindi/English-only,
workshop-as-home, voice fixes). Per-phase detail lives in the sibling files
(`phase-*.md`, `claris-phase-*.md`, `validation-report.md`); this file is the
map over all of them, plus everything fixed after those docs were written.

Status date: 2026-11-04. Tree: `1526370` + uncommitted fix batch (see §7).

Path shorthand used below: `app/…` = `backend/app/…`, `api/…` =
`backend/app/api/…`, `lib/…` and `components/…` = `frontend/lib/…` and
`frontend/components/…`. Bare filenames resolve to their home dir: `*.md`
and `bench_*.json` → `docs/`; backend `*.py` → its module dir under
`backend/`; `*.ps1` and `bench_asr.py` → `infrastructure/scripts/`;
`speech.test.ts` → `frontend/tests/`. All other paths are repo-root-relative.

## 1. What this project is

Second Voice is an assistive communication platform for people with
dysarthria and other speech-intelligibility difficulties. A user speaks,
the system transcribes, proposes a clearer sentence, and speaks **only**
user-confirmed text. Core rule, enforced server-side:

> AI may help someone express their thoughts, but it must never take
> ownership of those thoughts.

Languages: **Hindi + English, including Hinglish code-switch** (Marathi was
removed — see §6.2). This is an assistive prototype, not a diagnostic or
treatment product. No clinical claims are made.

## 2. What was built — foundation

Backend (`backend/`, FastAPI + Pydantic + SQLAlchemy + Alembic, PostgreSQL):

- `app/main.py`, `app/core/` (config, database, security), `app/models.py`,
  `app/schemas.py`, `app/middleware/`.
- `app/api/`: `auth`, `sessions`, `transcription`, `reconstruction`,
  `languages`, `memory`, `feedback`, `speech`, `cards`, `evaluation`,
  `restoration`, `settings` — versioned `/api/v1/...` REST, auth on every
  route, per-user isolation at API and DB layers.
- `app/services/`: `audio_service` (incl. `normalize_to_wav16k`),
  `meta_asr_service` + `meta_http`, `asr_providers` (Meta + local Whisper),
  `asr_orchestration`, `language_service`, `audio_intelligence`,
  `uncertainty_service`, `muse_spark_service`, `muse_wonder_service`,
  `reconstruction_service`, `clarification_service`, `memory` (via
  `personalization_service`), `prompts` (versioned prompts), `tts_service`,
  `evaluation_service` + `evaluation_harness`, `muse_image_service`,
  `speech_restoration/` (S2U pipeline, comparison).
- Migrations `0001_init` → `0015_calibration_clips` (head
  `f140e919def2`) in `backend/alembic/versions/`.

Frontend (`frontend/`, Next.js App Router + React + TypeScript + Tailwind):

- Routes: `/` landing with interactive demo, `/login`, `/register`,
  `/onboarding`, `/communicate` (workshop home: latest-or-new session),
  `/communicate/[sessionId]` (communication workspace), `/history`,
  `/board`, `/vocabulary`, `/learn` (personalization review), `/settings`.
- `lib/api.ts` (typed API client, `speechLang`, `speakBrowser`,
  `pickBrowserVoice`), `lib/audio.ts` (recording), `lib/candidates.ts`,
  `lib/cards.ts`, `lib/align.ts`, `lib/design-system.ts` (Stitch tokens,
  `LANG_DATA`, `CLIP_DATA`).
- `components/`: `Header`, `Footer`, `RequireAuth`, `CandidatesPanel`,
  `DiffView`.

Infrastructure: `docker-compose.yml` → `db` (postgres:16-alpine), `backend`
(:8000), `inference` (:8001, CLARIS S2U), `frontend` (:3000).
`inference/` has its own Dockerfile + requirements. `.env.example`
documents every key; secrets stay in `.env`, never in code.

## 3. What was built — 2.0 phases 0–14 (commits `e04b1af`–`9b37e25`)

| Phase | Content | Anchor doc |
|---|---|---|
| 0–1 | Audit baseline + audio intelligence (quality/clip checks) | `phase-1-audio-intelligence.md`, `baseline-2.0.md` |
| 2 | Multi-engine ASR orchestration (Meta primary, default unchanged) | `phase-2-asr-orchestration.md` |
| 3 | Uncertainty packaging + transcript evidence | `phase-3-uncertainty-evidence.md` |
| 4 | Multilingual spans + translation guards | `phase-4-multilingual.md` |
| 5 | Speaker profile with provenance + versioning | `phase-5-speaker-profile.md` |
| 6 | Adaptive personalization with rollback | `phase-6-adaptation.md` |
| 7 | Reconstruction 2.0 with evidence audit | `phase-7-reconstruction-2.md` |
| 8 | Clarification questions + answers | `phase-8-clarification.md` |
| 9 | Communication cards + multimodal | `phase-9-multimodal.md` |
| 10 | Safety audit + evidence in history | `phase-10-safety-audit.md` |
| 11 | Evaluation + research harness (WER/CER, meaning, latency) | `phase-11-evaluation.md` |
| 12 | Production hardening: retries, backup scripts, schema conformance | `phase-12-production.md` |
| 13 | Cards board + honest workspace (consent-gated speech) | `phase-13-frontend.md` |
| 14 | Final validation + acceptance sign-off | `phase-14-final-validation.md` |

Rule kept throughout: each phase ran the app + tests and fixed failures
before moving on. Markers: `PHASE11-DOCKER-PASS`, `RATELIMIT-DOCKER-PASS`,
`MIGRATION-ROUNDTRIP-PASS`, `PHASE12-SMOKE-PASS`, `PHASE13-DOCKER-PASS`.

## 4. What was built — CLARIS phases 0–10 (commits `a34261b`–`1526370`)

CLARIS = evidence-driven Hindi/English atypical-to-speech research track on
top of the 2.0 app: audio derivatives, a second local ASR engine, S2U
speech-restoration evidence, source-labelled candidates, reviewable
personalization, voice expansion.

| Phase | Content | Anchor doc |
|---|---|---|
| 0 | Assessment: TORGO/UASpeech blocked (consent/access), Fleurs `hi_in`/`en_us` as lawful stand-in; CLARIS checkpoints behind unverified Drive, English-only assumption | `claris-phase-0-assessment.md` |
| 1 | Audio derivatives (`AudioAsset`, `AudioDerivative`, `DERIVATIVE_KINDS`) + retention endpoints | `claris-phase-1-assets.md` |
| 2 | Local Whisper second engine (`SECOND_ASR_ENABLED/PROVIDER`, honest `second_available()`) + Fleurs benchmark; ADOPTED as secondary (Meta en WER ~0.09–0.1, hi ~0.14–0.17; local small en 0.073, hi 0.6) | `claris-phase-2-asr.md`, `bench_{meta,small,hindi}.json` |
| 3 | Inference reproduction: S2U units run (wtimit 1.2–2.4 s, torgo ~7.8 h CPU); vocoder blocked, no waveform claims | `claris-phase-3-claris.md` |
| 4 | Restoration service: S2U units as evidence only, vocode stage gated off | `claris-phase-4-restoration.md` |
| 5 | Evidence comparison across restoration stages | `claris-phase-5-evidence.md` |
| 6 | Source-labelled reconstruction candidates (usable/flagged, never hidden); approved-vocab exact-pair exemption to the name guard | `claris-phase-6-candidates.md` |
| 7 | Personalization review (approve/modify/remove learned entries) + calibration tables (`0015`) | `claris-phase-7-review.md` |
| 8 | Evidence workspaces (candidates, evidence strip, review UI) | `claris-phase-8-workspaces.md` |
| 9 | Google Cloud TTS voices + fixed-text preview (REAL synthesis needs `GOOGLE_TTS_API_KEY`; without it the server returns an honestly-labelled tone and the browser speaks) | `claris-phase-9-voices.md` |
| 10 | Evaluation access log, performance, limitations | `claris-phase-10-evaluation.md` |

Markers: `CLARIS-P1…P10-DOCKER-PASS` (P3 without the `-DOCKER` suffix),
`CLIPS: 16`, `fw-ok 1.2.1`. Live end-to-end (record → confirm → speak)
measured ~15 s.

## 5. How it works (end to end)

1. **Record.** `/communicate/[sessionId]` records via `lib/audio.ts`
   (MediaRecorder, converted to WAV in-browser) or uploads a file.
   Audio is stored only under user consent + retention settings.
2. **Transcribe.** `POST /api/v1/transcription` → Meta Voice Transcribe
   (primary) with user language as hint; local Whisper (`asr_providers.py`,
   lazy `faster-whisper` import, `SECOND_ASR_ENABLED`) as secondary via
   `asr_orchestration.py`. Original transcript + provider/model metadata are
   preserved permanently in the session record and never overwritten.
3. **Language.** `language_service.py` detects Hindi / English / Hinglish
   code-switch; manual override always wins. Hindi stays Hindi; Hinglish is
   preserved unless the user explicitly requests translation.
4. **Reconstruct (evidence-first).** `reconstruction_service.py` (Muse Spark)
   receives ASR text + acoustic/personal evidence separately and returns
   structured, source-labelled candidates (`usable`/`flagged`, never hidden).
   Guards: never invent words, never flip negation, preserve names/numbers/
   intent; approved-vocabulary exact pairs are exempt from the name guard;
   the engine abstains when uncertain. Muse Wonder is routed only for complex
   ambiguity.
5. **Learn (consent-based).** Accept/edit → `POST /api/v1/confirmation`
   records the learning event; retrieval in later sessions uses approved
   vocabulary/corrections/preferences only. Everything learned is reviewable,
   editable, deletable in `/learn`; rejected suggestions never become silent
   permanent rules; no silent self-training, no weight fine-tuning.
6. **Confirm gate.** TTS requests (`POST /api/v1/speech/synthesize`, server
   gate in `api/speech.py`) reject unconfirmed text — tested directly against
   the API in `test_confirmation_gate.py`, not just via disabled buttons.
   Audit trail: original → suggestion → user edit → final text + timestamp.
7. **Speak.** With `TTS_PROVIDER=google` + `GOOGLE_TTS_API_KEY`, server
   WaveNet/Standard synthesis (`tts_service._synthesize_google`, locale
   prefix validated against the request language). Without a key
   (current state): the server returns an honestly-labelled placeholder tone
   and the **browser speaks** the confirmed text via `speakBrowser`
   (`speechLang` tag + explicit ranked voice from `pickBrowserVoice` —
   prefers Natural/Google/en-IN voices, avoids eSpeak/legacy SAPI).

Quick communication board (`/board`), vocabulary vault (`/vocabulary`),
session history (`/history`), settings (language, TTS voice/speed, privacy,
retention) complete the loop. Full API reference: `api.md`. Architecture
diagrams: `architecture.md`.

## 6. Post-CLARIS fix batch (uncommitted at status date — see §7)

6.1 **Hindi/Marathi confirmed-speech silence → fixed.** Browser speech used a
raw utterance with no language, so Devanagari text went silent on default
voices. Fix: `speechLang()` maps `hi/hinglish→hi-IN`, `en→en-IN`, and the
voice is picked explicitly (`frontend/lib/api.ts`). Covered by
`frontend/tests/speech.test.ts`.
6.2 **Marathi removed (Hindi + English only).** Backend detection, TTS voice
tables/config, and all frontend pickers/clips/voices/tests now cover `en`,
`hi`, `hinglish` only; unrecognized languages fall back honestly instead of
mislabeling. Hinglish retained as Hindi/English code-switch.
6.3 **Workshop is now the home screen; old dashboard removed.** Login,
register→onboarding→app all land on `/communicate` (latest-or-new session,
`frontend/app/communicate/page.tsx`); `frontend/app/dashboard/` deleted
(serves 404); header logo/nav, workspace sidebar, history and footer links
updated. The dashboard's recorder was the reported broken path; the workshop
recorder (backend upload + §5 flow) is the supported one.
6.4 **Landing demo speaks again (incl. Hindi).** Hero + demo buttons use the
same language-tagged, explicit-voice path as the workspace.
6.5 **English sounds less robotic (no key needed).** `pickBrowserVoice()`
ranks installed voices: exact `en-IN` locale, Google/Natural/Neural/Online
voices first; eSpeak and legacy "Desktop" SAPI voices last; ties keep list
order. Best free result comes from Edge's online Natural voices (e.g. Neerja);
6 new tests pin the ranking. The ceiling is device voices — real neural
quality still needs the Google key (§5.7).

## 7. Verification status (last full pass, 2026-11-04)

- Backend: 24 test files (`backend/tests/`), **133–134 passed**
  (`pytest tests/ -q -p no:warnings`); suites cover pipeline, gates,
  confirmation, reconstruction, guards, TTS-Google path, personalization,
  restoration, safety, production.
- Frontend: 6 test files, **26/26 passed** (incl. new `speech.test.ts`
  voice-ranking tests); `npx tsc --noEmit` clean; `next build` clean.
- Docker: `db` + `backend` healthy (`asr_live:true`), `inference` healthy,
  `frontend` serving — landing 200, `/communicate` 200, `/dashboard` 404.
  Migration head `f140e919def2` (0015) verified via
  `verify_migrations.ps1`; `backup.ps1`/`restore.ps1` round-trip passed.
- Live (not mocked): Hindi/English detection, voice lists, fallback preview
  200, record→confirm→speak ~15 s end-to-end. Meta ASR benchmark vs Fleurs
  refs in `bench_*.json`. No Google-TTS live call yet (no key — §9).
- Uncommitted at status date: Marathi-removal + TTS fix + workshop routing +
  landing/voice fixes + this doc (`git status` list kept short here; run it
  for the exact set). Nothing in the tree is a mock of a finished workflow;
  where an API is unavailable the integration is labelled unavailable with a
  documented fallback (Google TTS → webspeech-fallback tone + browser speech).

## 8. Issues faced and fixed

Each row: symptom → root cause → fix → where to look / regression cover.

**Audio / ASR**
- Meta rejected our first transcriptions (`request`+`audio` parts required;
  then 44.1 kHz rejected — mono s16le 16/24 kHz only) → added
  `normalize_to_wav16k()` in `audio_service.py`; verified contract in
  `meta_asr_service.py`. Live evidence in `validation-report.md` §1.
- Fleurs clips are float32 (fmt tag 3) → added `_float_to_s16`; local
  faster-whisper call failed on `metadata_errors` kwarg → pass float32
  `ndarray` instead of BytesIO. Pinned `faster-whisper==1.2.1`, `numpy==2.5.4`.
- CT2 converter choked on `suppress_tokens {}` + `dtype` kwarg (transformers
  4.x) → local snapshot patch + CompatConverter mapping to `torch_dtype`;
  stock Whisper tokenizer (50258+1607) copied from hub cache.
- Hindi CT2 WER 0.332 vs Meta 0.151 on the same clips → local Whisper kept as
  SECONDARY only (`SECOND_ASR_ENABLED/PROVIDER`), Meta stays default.
- English feed: recording upload decoded wrong in-browser → convert to WAV
  in-browser (`de1900b`) and surface real transcribe errors in the UI.
- Isolated Hindi words skew English in Meta ASR (WER up to 2.0 on 1-word
  clips); one run returned Korean hangul; long high-energy English clip
  returned empty transcript 3/3 → documented as provider limits, not app
  bugs; app passes user language as hint; UI nudge to confirm language on
  short utterances is the recorded next action (`validation-report.md` §2–4).
- `hf` CLI missing → used `huggingface_hub`; Common Voice 404/gated →
  Fleurs parquet via `fsspec` HTTP range reads (torchcodec/FFmpeg absent,
  `pyarrow.ParquetFile` FS issues); clip path mismatch in container → added
  `--base` remap to `bench_asr.py`.
- PowerShell `&&`/`cp1252` Hindi garbling → `;` separators, forward-slash
  paths, file-based comparison of Hindi output.

**Reconstruction / learning / guards**
- Phase 6 `UnboundLocalError: secondary_text` → hoisted extraction before use.
- Name guard blocked an *approved* correction ("Arav"→"Aarav") → added
  `approved_swaps` exact-pair exemption + focused test; guards still block
  unapproved invented words, negation flips, number/name changes.
- Restoration endpoint 500'd → reproduced with
  `raise_server_exceptions=True`, fixed `Phase4` relative import
  (`from ... import models`).
- TypeScript `SpeakResult` narrowing failure → uniform return type.
- XTTS-v2 evaluated for voices → **excluded** (CPML non-commercial licence);
  Google Cloud TTS adopted instead (Phase 9).

**Migrations / Docker / build**
- Autogenerate produced an empty migration → container image was stale;
  rebuilt image + `up -d` before `alembic revision`; backend rebuild needed
  after adding a migration (COPY alembic step).
- `compare_server_default=True` kept for autogenerate honesty.
- Torch wheel install ~11 min + one transient inference build failure →
  retried, pinned versions; inference image is 3.21 GB (documented, §9).
- Host had no `faster-whisper` for tests → stubbed `sys.modules`
  (`test_asr_local.py`).

**Speech output (this batch)**
- Hindi/Marathi confirmed text silent; English robotic; landing demo silent
  on Hindi → §6.1/6.4/6.5. Root cause in all three: no language tag and no
  explicit voice (first-match voice guessing). Fix: `speechLang()` +
  explicit pick + `pickBrowserVoice()` ranking; regression tests in
  `speech.test.ts`.
- Dashboard recorder broken for the user's test → dashboard removed, workshop
  (`/communicate`) is the single supported path (§6.3).

## 9. Known limitations (honest, not hidden)

- No Google TTS key configured (user has no billing card) → server voices
  are the labelled fallback; browser voices carry the load with a device
  ceiling. Wiring is 2 lines (`TTS_PROVIDER=google`, `GOOGLE_TTS_API_KEY`).
- No dysarthric speech datasets: TORGO not downloadable (non-academic
  ambiguity/consent), UASpeech needs request + ethics approval, mirrors
  rejected → Fleurs typical speech only; **no clinical claims**.
- Second-engine Hindi is weak (WER 0.6 small / 0.332 CT2) → stays secondary;
  SraVaani/IndicConformer never benched.
- Guards use Latin-script proper-noun heuristics; Devanagari has no case
  signal. Rate limiter is per-process memory; TLS via proxy; single-node
  Compose; inference image 3.21 GB.
- Google TTS real synthesis never called live; Meta hints (`language`,
  `keywords`) accepted by the API but measured hint effect ≈ nil.

## 10. Run it / verify it (pointers, not a rewrite)

- Setup: `docs/setup.md`; production: `docs/deployment.md`; API: `docs/api.md`;
  privacy: `docs/privacy.md`; tests: `docs/testing.md`; live audio evidence:
  `docs/validation-report.md`; demo flow: `docs/demo-script.md`.
- `docker compose up --build -d`; `docker compose ps` (all healthy).
- Backend: `pytest tests/ -q -p no:warnings` (expect 133–134 passed).
- Frontend: `npm run test` (26), `npx tsc --noEmit`, `npm run build`.
- Smoke: landing 200, `/communicate` 200, login → workshop, record Hindi →
  confirm → speak; landing demo toggle Hindi → play.
- DB: migration head `f140e919def2`; `verify_migrations.ps1`,
  `backup.ps1`/`restore.ps1` in `infrastructure/scripts/`.


