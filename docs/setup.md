# Setup & Local Run

## Prerequisites
Docker + Docker Compose. For local dev: Python 3.12+, Node 20+.

## Docker (recommended)
```bash
cp .env.example .env
# optional: set META_API_KEY (https://dev.meta.ai → API Keys) for live models
docker compose up --build
```
- App: http://localhost:3000 · API: http://localhost:8000 (`/healthz`, `/docs`)
- Demo login: `demo@secondvoice.app / demo1234` — seed with:
  `docker compose exec backend python scripts/seed_demo.py`
  (or locally `.venv/Scripts/python infrastructure/scripts/seed_demo.py`).
- Going to production? Read [deployment](deployment.md) next (TLS, env,
  migrations, backups).

Without `META_API_KEY` every AI response is labelled `dev-fallback`; the full
workflow (type → understand → confirm → speak via device voice) still works.

## Local dev
```bash
# backend (from repo root, project venv)
.venv/Scripts/activate  # Windows · or: source .venv/bin/activate
cd backend && uvicorn app.main:app --reload --port 8000
# frontend (new shell)
cd frontend && npm install && npm run dev
```
`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`.

## TTS
`TTS_PROVIDER=webspeech-fallback` (default, device voice) · `azure` needs
`AZURE_SPEECH_KEY/REGION` · `elevenlabs` needs `ELEVENLABS_API_KEY`.
