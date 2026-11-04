# Second Voice — Your Voice. Your Meaning. Your Choice.

An assistive communication platform for people with dysarthria and speech
intelligibility difficulties. Speak naturally → keep the original transcript →
review evidence-first AI suggestions → confirm → speak only confirmed text.

> **AI may help someone express their thoughts, but it must never take
> ownership of those thoughts.**

## What it does

- **Records speech** (mic or file upload) and transcribes it with
  **Muse Voice Transcribe** (`muse-voice-transcribe-1.0`).
- **Preserves the original transcript forever** — reconstruction never
  overwrites it.
- **Reconstructs with evidence-first rules + Muse Spark** (`muse-spark-1.3`):
  acoustic evidence ≠ contextual guess ≠ personal vocabulary ≠ user authority.
- **Routes only complex ambiguity to Muse Wonder** (`muse-wonder-1.0`).
- **Optional visual cards** via Muse Image (`muse-image-1.0`).
- **Multilingual core**: English, Hindi, Hinglish (+ extensible).
  Language is preserved by default; translation is explicit and confirmed.
- **Learns transparently**: user-approved vocabulary, corrections, language
  preferences. Retrieval-based personalization, no silent fine-tuning.
- **Confirmation gate**: `Audio → ASR → Reconstruction → Review →
  Confirm → TTS`. The TTS endpoint rejects unconfirmed text server-side.
- **Speaks only confirmed text** via pluggable TTS (Azure / ElevenLabs /
  Web Speech fallback), with stop control.

## Architecture

```
Browser (Next.js) ──REST /api/v1/*──▶ FastAPI ──▶ PostgreSQL
   │ MediaRecorder/WAV upload            │──▶ Meta Model API (api.meta.ai/v1)
   │ speechSynthesis preview             │──▶ Object storage (local volume)
   └────────────────── audit trail ──────┘
Layers: Audio → ASR → Language → Personal Context → Evidence-first
Reconstruction → Memory → Learning → Confirmation → TTS.
```

See [docs/architecture.md](docs/architecture.md) for the full document,
[docs/model-integrations.md](docs/model-integrations.md) for verified Meta
endpoints, and [docs/api.md](docs/api.md) for the API.

## Quickstart (Docker — recommended)

```bash
cp .env.example .env
# add META_API_KEY (from https://dev.meta.ai → API Keys) for real models,
# or leave empty to run with the labelled development fallback.
docker compose up --build
```

- App: <http://localhost:3000>
- API: <http://localhost:8000> · health: `/healthz` · docs: `/docs`
- Demo account: register in the UI, or `demo@secondvoice.app / demo1234`
  (seed via `docker compose exec backend python scripts/seed_demo.py`,
  or locally `.venv/Scripts/python infrastructure/scripts/seed_demo.py`).

## Local dev (without Docker)

Backend:

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev  # http://localhost:3000, NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Meta API credentials

1. Go to <https://dev.meta.ai> → API Keys → create `MODEL_API_KEY`.
2. Set `META_API_KEY=...` in `.env` (never commit it).
3. Verified model IDs / endpoints (Oct 2026):

| Responsibility | Model | Endpoint |
|---|---|---|
| Speech recognition | `muse-voice-transcribe-1.0` | `POST https://api.meta.ai/v1/asr/transcribe`, realtime `wss://api.meta.ai/v1/asr/realtime` |
| Reconstruction | `muse-spark-1.3` | `POST https://api.meta.ai/v1/responses` (low reasoning effort, structured JSON) |
| Complex ambiguity | `muse-wonder-1.0` | `POST https://api.meta.ai/v1/chat/completions` (same platform) |
| Visual cards | `muse-image-1.0` | Meta Model API image endpoint |

Without a key the backend uses the **labelled dev fallback**
(`provider="dev-fallback"`, `model_version` records it) — see
[docs/model-integrations.md](docs/model-integrations.md). Fallback responses
are rule-based, never presented as Meta output.

## TTS configuration

`TTS_PROVIDER=azure|elevenlabs|webspeech-fallback` + provider key.
Without a key the API returns a valid WAV placeholder explicitly labelled
`fallback:true` and the frontend speaks via `speechSynthesis`. Unsupported
voice/language returns a transparent 409, never a fake voice.

## Tests

```bash
cd backend && pytest -q
cd frontend && npm test  # vitest
```

Evaluation: `GET /api/v1/evaluation/compare?reference=...&hypothesis=...`
(WER/CER), `backend/tests/test_evaluation.py`, personalization dashboard in
UI. See [docs/evaluation.md](docs/evaluation.md).

## Project layout

```
backend/        FastAPI app (api/, models/, schemas/, services/, tests/)
frontend/       Next.js App Router (app/, components/, lib/)
docs/           architecture, api, setup, deployment, privacy, model-integrations, testing, evaluation, demo-script
infrastructure/ docker/, scripts/seed_demo.py
```

## Safety & privacy

- Original transcript, suggestion, edits, final text, confirmation timestamp
  audited per message. TTS rejects unconfirmed text (server-side).
- Per-user isolation enforced at API + query layer. Audio stored only with
  consent; retention configurable; `DELETE /api/v1/account/data` wipes all.
- Prototype assistive tool — not diagnostic, not treatment. No clinical
  claims. See [docs/privacy.md](docs/privacy.md).
