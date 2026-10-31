# Deployment Guide (production)

Takes the Docker Compose stack from [setup](setup.md) to a production host.
Local run stays unchanged; nothing below modifies the app images.

## 1. Services (as declared in `docker-compose.yml`)

| Service | Image / build | Port | Depends on | Health check |
|---|---|---|---|---|
| `db` | `postgres:16-alpine`, data in `pgdata` volume | internal 5432 | — | `pg_isready -U secondvoice` |
| `backend` | `backend/Dockerfile` (FastAPI, creates tables on start) | 8000 | `db` healthy | `GET /healthz` |
| `frontend` | `frontend/Dockerfile` (Next.js standalone) | 3000 | `backend` healthy | via `backend` gate |

Persistent volumes: `pgdata` (database), `audiodata` (mounted at
`STORAGE_DIR=/data/audio`). Back up both (see §6).

## 2. Required environment (`.env` from `.env.example`)

Must change from defaults before exposing the stack:

- `JWT_SECRET` — long random string (≥32 chars). Rotating it logs everyone out.
- `POSTGRES_PASSWORD` — set via compose `db.environment` (default
  `secondvoice`; change it and `DATABASE_URL` together).
- `CORS_ORIGINS` — your public frontend origin(s), e.g.
  `https://secondvoice.example.org`. Never `*` with credentials.
- `NEXT_PUBLIC_API_URL` — public backend URL. Baked into the frontend **at
  build time**: set it before `docker compose build`, and rebuild the
  frontend image whenever it changes.

Optional but recommended for live AI:

- `META_API_KEY` (+ `META_BASE_URL`, `META_*_MODEL` to pin versions).
  Empty = labelled dev fallback (see [model-integrations](model-integrations.md)).
- `TTS_PROVIDER=azure|elevenlabs` + provider keys; default
  `webspeech-fallback` speaks via the device voice.

Tuning: `JWT_EXPIRE_MINUTES`, `AUDIO_RETENTION_DAYS` (default 30),
`LOG_LEVEL`, `STORAGE_DIR`.

## 3. TLS termination

Compose exposes plain HTTP. Put a reverse proxy in front (Caddy or nginx on
the host or as an extra service) that terminates TLS and forwards `/` to
`frontend:3000` and `/api/*` + `/docs` to `backend:8000`. Example Caddyfile:

```
secondvoice.example.org {
    handle /api/* { reverse_proxy backend:8000 }
    handle { reverse_proxy frontend:3000 }
}
```

Keep `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` consistent with the public
origin, otherwise browsers block API calls.

## 4. PostgreSQL & migrations

- The backend runs `python -m app.core.init_db` on start, which creates
  missing tables **and stamps the alembic version** — a fresh
  `docker compose up` needs no manual step, and `upgrade head` stays a
  no-op afterwards (both verified against the running stack).
- Versioned schema changes live in `backend/alembic/versions/` (shipped
  inside the image). After pulling an update, apply them explicitly before
  (re)starting the backend. Use `python -m` (the bare `alembic` script
  cannot see the app package inside the image):

```bash
docker compose run --rm backend python -m alembic -c alembic.ini upgrade head
```

(`backend/alembic.ini` points at the compose `db` host by default.)

## 5. Storage & retention

- Audio and synthesised speech live under `STORAGE_DIR` (`audiodata`
  volume). Expired items return HTTP 410 once older than
  `AUDIO_RETENTION_DAYS`; users can also delete data per-item or wipe the
  account (`DELETE /api/v1/account/data`, which removes their audio files).
- Size guard: uploads over 15 MB are rejected (413); non-audio types 415.

## 6. Backup & restore

```bash
docker compose exec db pg_dump -U secondvoice secondvoice > backup.sql
docker run --rm -v secondvoice_audiodata:/data -v "$PWD":/out alpine \
  tar czf /out/audiodata.tar.gz /data/audio
```

Restore: fresh `up`, `psql < backup.sql`, extract the tarball back into the
`audiodata` volume. Test restores; an untested backup is not a backup.

## 7. Health checks & monitoring

- `GET /backend-host:8000/healthz` → `{ok, asr_provider, asr_live,
  tts_provider}`; compose marks the backend unhealthy after 10 failed
  10 s-interval checks and holds the frontend on its gate.
- Structured logs on stdout (`LOG_LEVEL`); every response carries
  `X-Trace-Id` for correlating a user report with backend logs.
- Alert on: backend unhealthy, `db` restarts, disk use of `pgdata` /
  `audiodata`, and 5xx spikes on `/api/v1/transcription` and
  `/api/v1/reconstruction` (Meta outage/readiness signal).

## 8. Updates

```bash
git pull
docker compose build backend frontend   # rebuilds frontend with current NEXT_PUBLIC_API_URL
docker compose run --rm backend python -m alembic -c alembic.ini upgrade head
docker compose up -d
docker compose exec backend python scripts/seed_demo.py  # demo account only, optional
```

## 9. Production security checklist

- [ ] `JWT_SECRET`, `POSTGRES_PASSWORD` changed; `.env` never committed.
- [ ] TLS on, `CORS_ORIGINS` exact, security headers at the proxy.
- [ ] `META_API_KEY` server-side only (never into the frontend image).
- [ ] Backups scheduled and restore-tested; retention policy communicated.
- [ ] No clinical-effectiveness claims on any public page (see
  [privacy](privacy.md)).
