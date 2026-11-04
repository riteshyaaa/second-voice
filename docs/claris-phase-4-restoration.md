# CLARIS Phase 4 — Restoration service (S2U units as evidence)

Date: 2026-11-04. Status: complete. Marker: `CLARIS-P4-DOCKER-PASS`.

## Scope (vocoder-blocked, per Phase 3)

Phase 3 proved the Code HiFi-GAN checkpoint was never published. Phase 4
therefore builds the restoration pipeline with the S2U evidence stage
live and waveform synthesis explicitly gated off — no substitute vocoder,
no invented audio. True A/B listening comparison stays in Phase 5,
pending the vocoder decision.

## What was built

- `inference/` sidecar: torch CPU + upstream CLARIS-Inference cloned at
  build (research-only, never vendored), FastAPI service exposing
  `GET /healthz` and `POST /units` (raw 16 kHz WAV in, units + timing
  out). Compose mounts `./models/claris` read-only; checkpoint chosen by
  `CLARIS_CHECKPOINT` (default `wtimit_44spkrs_trained.pt`, beam 5).
- `backend/app/services/speech_restoration/`: `pipeline.plan_stages()`
  (pure, offline-testable: normalize ready / enhance skipped-no-impl /
  s2u gated by `RESTORATION_ENABLED` / vocode skipped-no-checkpoint),
  `pipeline.run_job()` (normalize → sidecar units → `restored`
  AudioDerivative, operation `s2u-units`, JSON — never audio),
  `s2u_client.fetch_units()` (bounded timeout, every failure explains
  itself via `S2UUnavailable`).
- `RestorationJob` model + migration `0013` (create/drop roundtripped:
  `MIGRATION-ROUNDTRIP-PASS`, 13 downgrades, schema identical).
- API `POST/GET .../audio/{id}/restoration/jobs`: ownership-checked,
  rate-limited, disabled-by-default with an honest `unavailable` + stages
  response. Job states: `running` → `units_ready` | `failed` (reason kept).
- Config: `RESTORATION_ENABLED=false`, `RESTORATION_S2U_URL`,
  `RESTORATION_CHECKPOINT/BEAM/TIMEOUT_S` (documented in `.env.example`;
  no secrets).

## Live verification (real audio, Docker)

- Sidecar `/healthz`: units available, `vocoder_available: false`.
- `POST /units` (en_us_3.wav): 200, 185 units, 2.4 s at beam 5. Unit
  prefix matches the Phase 3 host repro (beam 20) on the first 9 units.
- Full job via API (`RESTORATION_ENABLED=true`): `units_ready`,
  165 units, derivative `restored/s2u-units` stored; stages
  `normalize ready / enhance skipped / s2u_units ready / vocode skipped`.
  (Unit count differs from the raw call because the pipeline transcribes
  the normalized derivative — expected, not a discrepancy.)
- Disabled default verified: `unavailable` + stages, no job created.
- Suites: backend **117/117** (6 new restoration tests: stage planning,
  client contract incl. unreachable/malformed sidecar, job
  success/failure/isolation), frontend **15/15**.
- Docker: `db` + `backend` healthy at 0013 head, `frontend` serving,
  `inference` healthy (3.21 GB image — torch CPU cost, documented).

## Bugs found and fixed

- `pipeline.py` used `from .. import models` (resolves to
  `app.services`); correct is `from ... import models`. Caught by the
  live API run (500), fixed, covered end-to-end. Host unit tests missed
  it because they stub `run_job` — noted, live run is the backstop.
- Backend image must be rebuilt after adding the migration file: the
  image COPYs `alembic/`, so a container-generated revision does not
  exist at startup until rebuild. Caught by `alembic current` showing
  0012 as head; fixed by rebuild.

## Honest limits

- Units are evidence, not speech: no waveform, no restored-audio
  playback, no transcript comparison yet (Phase 5, needs vocoder).
- `torgo_trainall.pt` stays impractical on CPU (~8 h per Phase 3);
  default checkpoint is wtimit. Torgo path needs GPU/ONNX (not built).
- Sidecar image is 3.21 GB (torch CPU). Acceptable for a research
  sidecar; revisit if it ever joins the critical path.
- Rate limiter is per-process memory; TLS via proxy; single-node.

## Next (Phase 5)

Evidence comparison across original / normalized / units: surface
per-stage artifacts side-by-side in the workspace with availability
flags, still without claiming restoration quality that needs the
vocoder.
