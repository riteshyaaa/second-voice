# CLARIS Phase 10 — Evaluation access log, performance, limitations

Date: 2026-11-04. Status: complete. Marker: `CLARIS-P10-DOCKER-PASS`.

Phase 10 is the honesty checkpoint: what was actually measured on
atypical speech, what the pipeline costs, and what remains unverified.

## 1. Atypical-speech data access log

### TORGO (U Toronto) — terms verified, not downloaded

- Official source: `cs.toronto.edu/~complingweb/data/TORGO/torgo.html`.
- Terms: free for **academic (non-profit)** purposes; any publication
  must cite the TORGO papers; 4 sets, ~18 GB uncompressed, 16 kHz
  audio from speakers with CP/ALS plus matched controls.
- Multiple peer-reviewed data-availability statements call it publicly
  available from the original source.
- **Decision: not downloaded.** This prototype is a personal,
  commercial-adjacent build, not an academic study — the "academic"
  fit is ambiguous, and this is identified patient speech (CP/ALS)
  whose consent scope I cannot verify from the project page. Pulling
  18 GB of patient recordings into a personal repo without an ethics
  framework is exactly what the consent-restriction rule guards
  against. Unblock path: institutional academic use with citation,
  then speaker-disjoint WER/CER via the existing harness.

### UASpeech (UIUC) — blocked

- Published data-availability statements: "accessible upon request,
  subject to ethical considerations by the original authors."
- Requires an author request + ethics clearance that cannot be
  completed in-session. No request filed (filing one in the user's
  name without instruction would be wrong). Status: blocked, path
  documented.

### Mirrors (HuggingFace `abnerh/TORGO-database`, Kaggle copies) — rejected

- The HF mirror carries no license tag and no provenance statement.
  Re-uploads of a licensed patient dataset without clear provenance
  are not a lawful route around the original terms. Rejected in writing;
  never downloaded, never queried.

### Net result

**No atypical-speech evaluation is claimed.** No WER/CER on dysarthric
speech appears anywhere in this track — including by implication. The
Phase 2/3 numbers are typical speech (Fleurs) or engineering timings,
labelled as such where they appear.

## 2. Speaker-disjoint protocol status

- The protocol is implemented and tested: `evaluation_harness.run_study`
  (per-speaker train/test, same-rule vocab mirroring the runtime,
  baseline-vs-personalized intent WER, corruption counts, cross-speaker
  leakage checks), covered by `test_evaluation.py` including the
  2-speaker leakage case (0 leaks) — green in the suite below.
- It has **not** been run on atypical speech: lawfully accessible
  atypical data does not exist in this session (see §1). Running it on
  typical speech and presenting the result as dysarthria evidence would
  be fabrication-adjacent; it was not done.

## 3. Performance (live Docker, real clip, seconds)

| stage | time |
|---|---|
| upload + audio-quality | 0.8 |
| transcribe (Meta primary) | 4.8 |
| reconstruct (Spark + candidates) | 8.9 |
| TTS preview (fallback tone) | ~0.0 |
| S2U units, wtimit, beam 5 (sidecar) | 1.2–2.4 |
| local small, per clip (CPU) | ~6.6 |
| local Hindi, per clip (CPU) | ~23 |
| torgo S2U, beam 20 (CPU) | ~28,000 — impractical, needs GPU/ONNX |

End-to-end voice-to-suggestion on typical infrastructure: roughly
15 s, dominated by the two Meta calls. PII-free, single node.

## 4. Consolidated limitations (whole track)

- ASR: Meta primary is best on Hindi (0.151 WER, typical speech);
  local Hindi (0.332) trails it; local small Hindi unusable (0.600).
  English: local matches Meta (0.073 vs 0.100). All typical speech.
- Restoration: S2U units proven live; waveform impossible without the
  unpublished vocoder. Units are evidence, never speech.
- Reconstruction: guards are Latin-script proper-noun heuristics;
  Devanagari has no case signal. Approved-vocab exemption is exact-pair
  only. Candidates carry no ranking scores.
- Learning: counts are reuse frequencies, not accuracy; no clinical
  claims; calibration is schema only.
- Voices: Google synthesis never called live (no key); names curated
  from public locale lists and may retire.
- Ops: per-process rate limiter, no TLS termination in Compose,
  single node, 3.2 GB inference image.

## 5. Tests and Docker

- Backend suite green (includes `test_evaluation.py` speaker-leakage
  case), frontend suite green, all four containers healthy at
  migration head `f140e919def2` (0015). No code changes this phase.

## Next

The track is complete through Phase 10. Remaining work is gated on
external inputs, in order: (1) Google TTS key for a live synthesis
check; (2) institutional TORGO access for the speaker-disjoint
atypical evaluation; (3) the unpublished Code HiFi-GAN checkpoint for
any waveform claim.
