# Phase 11 — Evaluation and research harness (2.0)

Speaker-separated, reproducible measurement of what the earlier phases built.
No new pipelines; this phase scores them.

## What was built

- `backend/app/services/reconstruction_service.py`: `_guard_checks()` is now the
  single source of truth — `violates_guards()` messages are byte-identical to
  before (regression-tested), and `guard_scores()` exposes the 8 per-category
  results (`GUARD_CATEGORIES`: negation, number, name, datetime, modal,
  conditional, unit, medical).
- `backend/app/services/evaluation_service.py`:
  - `preservation_report(reference, proposed)` — intent preservation per
    category. Reported ALONGSIDE `guard_report(original, proposed)` (corruption
    of the transcript): the two answer different questions.
  - `empty_rate(texts)` — share of empty transcripts (abstention signal, not an
    error; empty input must abstain, never invent).
  - `span_retention(reference_runs, detected_runs)` — code-switch evaluation:
    token recall per language plus the share of language-switch boundaries
    still present (merged spans keep recall but lose the boundary).
- `backend/app/services/evaluation_harness.py`: `run_study()` — offline
  speaker-separated personalization study. Train pairs populate each speaker's
  vocab with the SAME rule as the runtime user-save path (same-length token
  alignment, stopwords skipped); test cases run rules-only vs rules+vocab with
  intent WER, corruption counts, abstentions, and a cross-speaker leakage check
  (every other speaker's vocab run over my tests must equal plain: leaks = 0).
- `backend/app/api/evaluation.py`:
  - `POST /evaluation/study` — runs the harness on caller-supplied bundles.
  - `GET /evaluation/interaction` — UX metrics from the user's own audit
    trail: confirmed messages, edits/sentence, clarification rate, median
    confirm seconds (session start is the earliest available anchor; card taps
    have no session and are excluded — stated in the response), TTS success
    rate. All queries scoped to the caller (isolation-tested).
- `backend/tests/test_evaluation.py` — 9 tests (95/95 suite green).

## 7-way pipeline comparison (honest mapping)

The harness covers the offline-deterministic arms; the rest already existed:

| Arm | Where it is measured |
|---|---|
| Baseline ASR (raw transcript) | pipeline-demo `baseline_asr`; study `baseline` |
| ASR + keyword/vocab hints | study `personalized` (approved vocab swaps) |
| Context-heavy reconstruction | pipeline-demo `context_heavy` |
| Evidence-first reconstruction | pipeline-demo `evidence_first`; study `baseline` (rules) |
| Evidence-first + personal vocab | pipeline-demo `personalized`; study `personalized` |
| Alternative/second ASR engine | `/transcription/compare` agreement endpoint (Phase 2) |
| Full clarification loop | `/reconstruction/questions` + answers (Phase 8); clarification_rate in `/interaction` |

Live Spark arms are NOT inside the offline harness (network + non-determinism
would break reproducibility) — the study response states this scope boundary.

## Corpora status (unchanged, still blocked)

TORGO/UASpeech require human-approved licensing — no dysarthric speech has
been ingested. The harness is ready for licensed data: a corpus becomes
{original ASR text, user-approved reference} pairs per speaker. Synthetic /
consented-typical-speech pairs validate the machinery only, never clinical
effectiveness. No claim beyond "personalization machinery works on this sample"
is made.

## Validation (Docker)

- Suite: 95/95 passed (host venv; containers carry app code, not tests).
- Live probes: PHASE11-DOCKER-PASS (study endpoint + interaction endpoint +
  compare regression) after `docker compose up --build backend`.
