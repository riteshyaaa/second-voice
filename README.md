# Second Voice — Your Voice. Your Meaning. Your Choice.

Second Voice is an assistive communication platform for people with
dysarthria and other speech-intelligibility difficulties. A user speaks
naturally; the system transcribes, proposes a clearer sentence, and speaks
**only user-confirmed text** — in Hindi, English, or Hinglish code-switch.

> **AI may help someone express their thoughts, but it must never take
> ownership of those thoughts.**

This is an assistive-communication prototype, not a diagnostic or treatment
product. No clinical claims are made. Original audio is the primary evidence;
the transcript is an imperfect interpretation of it.

## Features

- **Speech-first workspace** — record (mic or file upload) or type; the
  workshop at `/communicate` is the home screen after login.
- **Real transcription** — Meta Muse Voice Transcribe, with a local Whisper
  second engine for comparison (secondary only, opt-in).
- **Original transcript preserved forever** — reconstruction never overwrites
  it; both stay visible side by side with highlighted differences.
- **Evidence-first reconstruction** — Muse Spark returns structured,
  source-labelled candidates (`usable`/`flagged`, never hidden). Guards hold:
  no invented words, no flipped negation, names/numbers/intent preserved,
  abstains when uncertain.
- **Complex-ambiguity routing** — Muse Wonder is invoked only for genuinely
  ambiguous cases, not every sentence.
- **Multilingual core** — English, Hindi, Hinglish code-switch (extensible
  design; Marathi was removed — see `docs/build-log.md` §6.2). Language is
  preserved by default; translation is explicit and user-confirmed.
- **Transparent learning** — user-approved vocabulary, corrections, and
  language preferences improve future suggestions. Retrieval-based only, no
  silent fine-tuning. Everything learned is reviewable, editable, deletable
  in `/learn`.
- **Server-side confirmation gate** — `Audio → ASR → Reconstruction → Review
  → Confirm → TTS`. The TTS endpoint rejects unconfirmed text; only the
  confirmed sentence can be spoken, with replay and stop controls.
- **Quick communication board** (`/board`), personal vocabulary vault
  (`/vocabulary`), session history (`/history`), accessibility settings.
- **Honest fallbacks** — no key, no voice, no model: the app says so and
  labels the fallback. Nothing is ever presented as real output when it isn't.

## How the Meta Muse models are used

Each model has one job; none is called perfunctorily. Verified endpoints live
in `docs/model-integrations.md` (base URL `https://api.meta.ai/v1`,
overridable via `META_BASE_URL`).

| Model | Responsibility | Where | Notes |
|---|---|---|---|
| `muse-voice-transcribe-1.0` | Speech recognition → original transcript + metadata | `backend/app/services/meta_asr_service.py`, `meta_http.py` via `POST /v1/asr/transcribe` (realtime `wss://…/v1/asr/realtime` where supported) | User language passed as hint; keyword hints for personal vocabulary. Without `META_API_KEY`: labelled `dev-fallback`, never shown as Meta output. |
| `muse-spark-1.3` | Contextual reconstruction → structured candidates with explanations, changed words, clarification flags | `backend/app/services/muse_spark_service.py` via `POST /v1/responses` (low reasoning effort, strict Pydantic-validated JSON) | Receives ASR text, acoustic/personal evidence, and the user's request as *separate* inputs. Malformed output is rejected, not rendered. |
| `muse-wonder-1.0` | Advanced reasoning for complex ambiguity only: competing interpretations, contradiction checks, clarification questions | `backend/app/services/muse_wonder_service.py` via `POST /v1/responses` | Routing policy keeps cost/latency down; ordinary sentences never touch it. |
| `muse-image-1.0` | Optional visual communication cards/boards from *confirmed* concepts | `backend/app/services/muse_image_service.py` | Never used as evidence of what was said; never mandatory. |
| (open-weight) | Spark Open / Glimmer evaluated only if documented capability + licensing + deployment fit | provider abstraction in `services/` | No rewrite needed to swap providers. |
| Muse Code | Development assistant | — | Not a runtime dependency. |

**Second engine (non-Meta):** local Whisper via `faster-whisper==1.2.1`
(`SECOND_ASR_ENABLED`/`SECOND_ASR_PROVIDER`), lazy import, CPU `int8` by
default. Benched on Fleurs `hi_in`/`en_us` (`docs/bench_*.json`): kept as
*secondary* because its Hindi lags Meta (WER 0.33–0.6 vs ~0.15). Honest
`second_available()` reason when disabled.

**TTS is not a Muse model.** Speech output is pluggable: Google Cloud TTS
(WaveNet/Standard, needs billing-enabled `GOOGLE_TTS_API_KEY`) → Azure →
ElevenLabs → `webspeech-fallback`. Without a key the API returns a valid,
explicitly-labelled placeholder tone and the browser speaks the confirmed
text with a language-tagged, ranked voice (`speechLang` + `pickBrowserVoice`
in `frontend/lib/api.ts`). Unsupported voice/language → transparent error,
never a fake voice.

## End-to-end workflow

```
Record (mic/file) → Transcribe (Meta, hinted) → Language detect (override wins)
 → Retrieve approved vocab/context → Reconstruct (Spark, guarded candidates)
 → [Wonder only if truly ambiguous] → User reviews: Accept / Edit / Reject /
   Clarify / Translate / Save phrase → Confirm (learning saved iff consented)
 → TTS gate (rejects unconfirmed) → Speak confirmed text → Session saved
```

Every step must work including error and cancellation paths, and every
suggestion carries: original text, proposed text, explanation, changed words,
and whether clarification is needed.

## Quickstart (Docker — recommended)

```bash
cp .env.example .env
# Add META_API_KEY (https://dev.meta.ai → API Keys) for real models,
# or leave empty to run with the labelled development fallback.
# Optional: GOOGLE_TTS_API_KEY for neural server voices (needs billing enabled).
docker compose up --build -d
docker compose ps   # db + backend healthy, inference healthy, frontend serving
```

- App: <http://localhost:3000> — register, and you land in the workshop.
- API: <http://localhost:8000> · health `/healthz` · interactive docs `/docs`.
- Demo account: `demo@secondvoice.app / demo1234`, seeded with vocabulary and
  board phrases:

```bash
docker compose exec backend python scripts/seed_demo.py
```

Without `META_API_KEY`, everything runs end-to-end on the labelled fallback
(rule-based, marked `provider="dev-fallback"` in `model_version`) — the
confirmation gate, learning loop, and TTS path behave identically.

## Configuration

All settings via `.env` (never commit it; `.env.example` is the template).
The essentials:

| Key | Purpose | Default |
|---|---|---|
| `META_API_KEY` | Real Meta models; empty = labelled fallback | empty |
| `META_ASR_MODEL` / `META_SPARK_MODEL` / `META_WONDER_MODEL` / `META_IMAGE_MODEL` | Model IDs (verified Oct 2026) | `muse-voice-transcribe-1.0`, `muse-spark-1.3`, `muse-wonder-1.0`, `muse-image-1.0` |
| `SECOND_ASR_ENABLED` / `SECOND_ASR_PROVIDER` | Local Whisper second engine | `false` |
| `TTS_PROVIDER` | `google` / `azure` / `elevenlabs` / `webspeech-fallback` | `webspeech-fallback` |
| `GOOGLE_TTS_API_KEY` | Neural server voices (Google free tier: 4M Standard+WaveNet / 1M Neural2 chars monthly, billing must still be enabled) | empty |
| `JWT_SECRET` | Auth signing — set a long random string | `change-me-…` |
| `AUDIO_RETENTION_DAYS` | Auto-expiry for stored audio | `30` |
| `RATE_LIMIT_PER_MINUTE` | Auth rate limit per IP (single-process scope) | `120` |
| `NEXT_PUBLIC_API_URL` | Backend URL for the frontend container | `http://localhost:8000` |

## Local dev (without Docker)

Backend (project `.venv` at repo root):

```bash
.venv/Scripts/activate        # or source .venv/bin/activate
cd backend
pip install -r requirements.txt
alembic upgrade head           # migrations (head: 0015 calibration clips)
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000, NEXT_PUBLIC_API_URL=http://localhost:8000
```

Seed the demo account locally (from repo root):

```bash
PYTHONPATH=backend .venv/Scripts/python infrastructure/scripts/seed_demo.py
```

## Tests & evaluation

```bash
cd backend && pytest -q            # 24 files, ~133 passed: pipeline, gates,
                                   # confirmation, guards, TTS, restoration, safety
cd frontend && npm test            # vitest, 6 files / 26 tests
cd frontend && npx tsc --noEmit && npm run build
```

- WER/CER harness: `GET /api/v1/evaluation/compare?reference=…&hypothesis=…`,
  `backend/tests/test_evaluation.py`, personalization dashboard in the UI.
- Live audio evidence (real clips, real endpoints — nothing mocked):
  `docs/validation-report.md`, raw results in `infrastructure/scripts/`.
- ASR benchmark: `infrastructure/scripts/bench_asr.py` + `docs/bench_*.json`.
- Research track (audio derivatives, S2U restoration evidence, candidates,
  review): `docs/claris-phase-0-assessment.md` → `…-10-evaluation.md`.

## Project layout

```
backend/         FastAPI (app/api, app/models, app/schemas, app/services,
                 app/core) · pytest suite (backend/tests/, 24 files)
                 · alembic/ (0001→0015) · Dockerfile · requirements.txt
frontend/        Next.js App Router (app/, components/, lib/) · vitest tests/
inference/       CLARIS S2U sidecar (app.py, Dockerfile) — evidence only
infrastructure/ scripts/ (seed, bench, validation, backup/restore/verify)
                 docker/ · bench-clips/
models/          local weights (git-ignored; mounted read-only in Docker)
docs/            build-log (start here for history), architecture, api, setup,
                 deployment, privacy, model-integrations, testing, evaluation,
                 phase-0…14, claris-phase-0…10, validation-report, demo-script
docker-compose.yml  db (postgres:16) · backend (:8000) · inference (:8001,
                    internal) · frontend (:3000)
```

## Docs map

- New here? `docs/build-log.md` — what was built, how it works, every issue
  faced and fixed, honest limitations.
- Run it: `docs/setup.md`, `docs/deployment.md`. Integrate: `docs/api.md`.
- Trust it: `docs/privacy.md`, `docs/testing.md`, `docs/evaluation.md`,
  `docs/validation-report.md`.
- Extend it: `docs/architecture.md`, `docs/model-integrations.md`,
  `docs/demo-script.md`.

## Safety, privacy & limits

- Per-message audit: original transcript, suggestion, user edits, final text,
  confirmation timestamp, language, TTS status. Unconfirmed text can never
  reach speech — enforced server-side, tested directly against the API.
- Per-user isolation at API and query layers; audio stored only with consent;
  retention configurable; `DELETE /api/v1/account/data` wipes everything.
- **Honest limits:** Google TTS needs a billing-enabled key (browser voices
  carry the load otherwise); no dysarthric datasets were lawfully available,
  so evaluation uses typical speech and makes no clinical claims; the local
  Whisper second engine's Hindi is weak and stays secondary; the rate limiter
  is per-process memory and TLS terminates at a proxy — see
  `docs/build-log.md` §9 for the full list.
