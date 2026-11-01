# Phase 3 — Phonetic & Acoustic Evidence as Transparent Uncertainty (done 2026-11-01)

## Position

The spec asks for phoneme hypotheses, forced alignment, and acoustic
likelihoods. No provider in this system exposes any of them, and the
spec forbids claiming them. So Phase 3 implements the honest half of the
phase: a **transparent uncertainty layer built only from observable
evidence** — provider outputs, their (dis)agreement, recording-quality
metrics, transcript length. Phoneme-level evidence stays an open
research item, explicitly not claimed.

An LLM must never manufacture acoustic evidence. The indicators below
are the only uncertainty language the reconstruction layer may use.

## What was built

- `services/uncertainty_service.py` — pure `summarize(primary,
  comparison, quality)` → typed indicators `{kind, severity
  (info|watch|risk), message}` from a **closed kind set**: `no_confidence`
  (always — no provider exposes it), `manual_entry`, `single_engine`,
  `empty_output` (risk, early-return), `very_short`, `disagreement`,
  `meaning_divergence` (risk, from guard violations between engines),
  `language_mismatch`, `poor_audio` (risk) / `audio_quality` (watch).
  Plus `reliability_text()` — the evidence-derived prompt note.
- `Transcript.evidence` JSON + migration `0003_transcript_evidence`:
  `{providers, comparison_verdict, uncertainty[], secondary_trigger,
  model_confidence: None, reliability_note}`.
- `_do_transcribe` now runs `transcribe_multi` (same single ASR call with
  no secondary configured) and persists evidence; manual entries store a
  `manual_entry` package. Compare endpoint and session history expose
  `uncertainty`.
- Reconstruction's reliability note is built from stored evidence
  (pre-Phase-3 rows derive single-engine indicators on the fly); provider
  confidence, when ever present, is still surfaced.

## Verification (observed)

- 8 new tests in `test_uncertainty.py` (closed kind set, matrix incl.
  negation-flip divergence, persistence + history round-trip,
  reconstruction consumes evidence). Suite 49/49 green.
- Live Docker: real Meta ASR returned empty on non-speech tones →
  `empty_output` risk stored → Spark path **abstained with no invention**
  and asked a clarification question. PHASE3-DOCKER-PASS.

## Limits

Text-level only (no timings available); evidence returned and stored but
not yet used for retrieval (Phase 5–6) or span-targeted clarification
(Phase 8); `0003` downgrade written, not executed live; phoneme-level
evidence still unavailable from providers.
