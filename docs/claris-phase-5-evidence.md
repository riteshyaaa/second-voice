# CLARIS Phase 5 — Evidence comparison

Date: 2026-11-04. Status: complete. Marker: `CLARIS-P5-DOCKER-PASS`.

## Goal

Surface everything the restoration pipeline produced — and everything it
did not — side by side, so a reviewer sees evidence with availability
flags instead of a single synthesized claim. No restoration-quality
claim: there is still no waveform (Phase 3).

## What was built

- `speech_restoration/comparison.py` (pure, offline-testable):
  `compare_texts()` (agree / disagree / either_empty / both_empty with
  word diffs + meaning-guard divergence, reusing the reconstruction
  guards), `build_report()` (per-artifact ready / failed / unavailable
  with reasons; pairwise text comparison only where both sides are
  ready; units attached as codes-with-statistics, never as words).
- API `GET .../restoration/jobs/{id}/comparison`: ownership-checked;
  404 unknown job, 409 unless `units_ready`; runs primary ASR over the
  original and the (idempotent) normalized derivative — two live ASR
  calls, explicit user action — attaches stored S2U units; per-artifact
  ASR failures recorded, never hidden; expired audio 410s.
- Report shape: `artifacts[original, normalized, s2u_units,
  enhanced_audio, restored_waveform]` + `comparisons[]` + a note stating
  audio primacy and the no-waveform limit.

## Live verification (real services, Docker)

Job + comparison on `en_us_3.wav` (Meta ASR live, S2U sidecar live):

- `original` ready (Meta transcript), `normalized` ready (Meta
  transcript of the normalized derivative).
- Pairwise verdict **agree**, `meaning_divergence: []` — normalization
  did not change the ASR reading on this clip. The comparison
  discriminates rather than rubber-stamps (Phase 2 showed it emitting
  `disagree` + diffs where engines differ).
- `s2u_units` ready (165 units, checkpoint, beam, latency).
- `enhanced_audio` / `restored_waveform` unavailable with the exact
  Phase 3/4 reasons.

## Tests

- Backend **121/121** (4 new: pure text-compare cases incl. negation
  flip, report availability matrix, live-shape report with stubbed ASR,
  ASR-failure recording, 404/409 gating).
- Frontend **15/15**. Migration head unchanged (0013; no schema change
  this phase). Docker: `db` + `backend` healthy, `frontend` serving,
  `inference` healthy.

## Honest limits

- Comparison costs two primary ASR calls per view; documented on the
  endpoint, not hidden.
- Units statistics (count, prefix) are shown for provenance, not as a
  quality signal — unit counts are not intelligibility scores.
- No enhanced-audio or waveform sides exist yet; the report shape is
  ready for them (Phase 5 slots, later phases fill).
- Rate limiter is per-process memory; TLS via proxy; single-node.

## Next (Phase 6)

Source-labelled suggestion categories in the reconstruction flow:
acoustic / alternative-ASR / contextual / vocab candidates, reusing this
report's artifact slots as labelled inputs.
