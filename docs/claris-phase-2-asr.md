# CLARIS Phase 2 — ASR Benchmark & Second-Engine Decision

Date: 2026-11-03. Status: complete. Marker: `CLARIS-P2-DOCKER-PASS`.

## Goal

Decide whether `local-whisper` (faster-whisper, CPU) is adopted as the
secondary ASR engine behind Meta primary, and which local model it uses.
Adoption bar: runs live in Docker, honest `second_available()` gating,
measured Hindi/English WER/CER/latency on fixed clips — no mock substitutes.

## Method

- Harness: `infrastructure/scripts/bench_asr.py` (pre-normalizes each clip
  to 16 kHz mono first, matching the production ASR path).
- Clips: 16 fixed Fleurs clips, `infrastructure/bench-clips/`
  (`hi/`: 8 Hindi, `en/`: 8 US English) with `refs.jsonl`.
- Same clips, same harness, same day for all three engines (matched runs).
- Raw per-clip rows + summaries: `docs/bench_meta.json`,
  `docs/bench_small.json`, `docs/bench_hindi.json`.

## Engines

- **meta-asr** — `muse-voice-transcribe-1.0` (primary, live API).
- **small** — `Systran/faster-whisper-small` via `LocalWhisperProvider`.
- **hindi** — `bohraanuj23/whisper-small-hindi` (Apache-2.0) converted to
  CTranslate2 (`models/whisper-small-hindi-ct2/`, gitignored, mounted
  read-only at `/models` in compose). Tokenizer is the standard Whisper
  set (snapshot vocab is 50258 + 1607 timestamp tokens = 51865, so the
  stock `tokenizer.json` applies; verified byte-identical need, copied
  from the faster-whisper-small hub cache).

## Results (n = 8 per language, 0 fails everywhere)

| engine | hi WER | hi CER | en WER | mean s |
|---|---|---|---|---|
| meta-asr | 0.151 | 0.099 | 0.100 | 4.2 |
| small | 0.600 | 0.216 | 0.073 | 15.2 |
| hindi | 0.332 | 0.121 | 0.073 | 23.3 |

Detail that leaves the table:

- **meta-asr** — best Hindi (0.151), fluent Devanagari, keeps English
  terms (`pH`, `MS`) and numerals as words. Fastest (4.2 s). Stays primary.
- **small** — best English (0.073) but Hindi unusable (0.600, phonetic
  misspellings, schwa errors). Rejected as the Hindi path.
- **hindi** — Hindi WER 0.332 (CER 0.121: errors are mostly matra-level,
  e.g. विजन→विशुन, रिपोर्टों→विपोटों). English identical to small
  (0.073, same outputs clip-by-clip), so it dominates small on both
  languages. Slower (23 s, 1 GB model loads per call — no cache yet).

## Decision: ADOPT (as secondary)

`local-whisper` is adopted as the **secondary/verification engine** with
the Hindi-adapted model as its configured local model. Routing stays
cost-aware (`asr_orchestration.should_run_secondary`): secondary runs on
explicit request, empty primary, or poor recording quality — never every
call. Meta remains primary for Hindi; local is the offline second
opinion and the English verifier.

## Live verification (real audio, both engines)

`orchestrate(hi_in_6.wav, force_secondary=True)` with secondary enabled:

- Primary `meta-asr/muse-voice-transcribe-1.0`, secondary
  `local-whisper//models/whisper-small-hindi-ct2`.
- Comparison verdict `disagree` with `word_diffs` preserved;
  `meaning_divergence: []` (surface transliteration/matra diffs only).
- `model_confidence: null` — never invented.
- No code changes needed: `/transcription/compare` already wires the
  conditional secondary; this run proved it with two live engines.

## Files changed

- `docker-compose.yml` — `./models:/models:ro` on backend.
- `.gitignore` — `/models/` (2 × ~925 MB weights never committed).
- `backend/tests/test_asr_local.py` — new `test_local_model_path_passes_through`.
- `docs/bench_{meta,small,hindi}.json` — raw evidence.
- Conversion tooling lived in project `.venv` + `/tmp` only (not committed).

## Test evidence

- Backend: **111 passed** (`cd backend; pytest tests/`), incl. 5
  local-Whisper adapter tests (stubbed engine) + orchestration tests.
- Frontend: **15 passed** (`npm run test`).
- Docker: `db` + `backend` healthy, frontend serving, `asr_live:true`.

## Honest limits

- Fleurs clips are typical speech, not dysarthric — no clinical claims;
  speaker-separated dysarthric evaluation still needs lawful data (Phase 10).
- Hindi WER 0.332 trails Meta 0.151; local is a second opinion, not a
  replacement. WER punishes matra variants harshly (CER 0.121 is the
  fairer read for Hindi script).
- No per-call model cache yet: 1 GB reload per transcribe (~20 s of the
  23 s latency). Fine for verification-rate use; must fix before any
  high-frequency use.
- Rate limiter is per-process memory; TLS via proxy; single-node Compose.
- SraVaani/IndicConformer not benched (license check pending).

## Next (Phase 3)

CLARIS inference reproduction against this evidence base: reconstruction
must consume the primary/secondary pair + audio-quality metadata, keep
audio primary, and abstain on `both_empty`.
