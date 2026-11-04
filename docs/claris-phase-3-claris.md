# CLARIS Phase 3 — Inference reproduction report

Date: 2026-11-04. Status: S2U reproduced locally; waveform step blocked
on unpublished vocoder. No repo changes (nothing to commit).

## Sources and license

- Code: `Yash-Kumar-tech/CLARIS-Inference` (cloned, shallow, to /tmp —
  not vendored into the repo).
- Checkpoints (GDrive folder `1EAWnM...`, public, downloaded to
  gitignored `models/claris/`).
- Demo-site Drive folder holds only a VITS-style G/D pair (see below).
- **No LICENSE file in the repo.** All artifacts treated as
  research-only: no redistribution, no product integration in this phase.

## Checkpoints (verified downloads)

| file | bytes | sha256 |
|---|---|---|
| torgo_trainall.pt | 424304402 | 8b2e0944…3396 |
| wtimit_44spkrs_trained.pt | 419568862 | 87cf4200…5e1e |

(Full hashes in bench-style records below; both are fairseq-style
`{args, cfg, model, ...}` training checkpoints.)

## Reproduction method

Faithful `demo_inference.ipynb` flow in `/tmp/claris_repro.py`: build
`SpeechToUnitTransformer` (params.py defaults), load checkpoint,
`SequenceGenerator` beam 20, 80-dim kaldi fbank input, `postProcessPrediction`
to units. Two shims were required (documented in the script, repo
untouched):

1. `torchaudio.sox_effects` no longer exists (repo pins torch 2.7).
   Our clips are 16 kHz mono so the sox path short-circuits; the shim
   raises loudly if ever really called.
2. `sequence_generator.py` has a stale `from generate import Dictionary`
   (fairseq, not shipped). Aliased to the repo's own `utils.Dictionary`
   (`search.py` already uses it; interface matches).

Input: `bench-clips/en/en_us_3.wav` (4.3 s, 16 kHz → 430 fbank frames).

## Results

| checkpoint | load | beam-20 CPU | frames | units |
|---|---|---|---|---|
| torgo_trainall | 0.4 s | 28277 s (~7.8 h) | 430 | 106 |
| wtimit_44spkrs | 1.8 s | 5.8 s | 430 | 155 |

- Both checkpoints load and generate valid 0–999 unit sequences.
- torgo CPU latency is impractical (~7.8 h for 4.3 s of audio); wtimit
  runs in seconds under identical conditions. Any product path needs
  GPU/ONNX/OpenVINO export (repo provides `export.py`/`exportToOV.py`,
  not exercised here) — CPU beam-20 on the torgo checkpoint is a
  non-starter.
- Sample rate 16 kHz; fbank 10 ms shift; `maxSourcePositions` 6000 ≈
  60 s input cap; notebook `maxLen` 50000.

## Coverage correction (vs Phase 0)

`val_sets/` names utterance IDs for TORGO (dysarthric), wTIMIT-44 and
wTIMIT-unseen-4 (whispered), **and Indian-English clean/noisy**
(nonnative effort). Audio is IDs only, not shipped. Hindi remains
unverified — assume English-only for CLARIS behavior until proven
otherwise.

## Vocoder: blocked (honest stop)

- The notebook needs `code_hifigan.pt`; it is in neither Drive folder.
- The demo-site folder's `G_1200000.pth`/`D_1200000.pth` (481/561 MB)
  are a **VITS-style posterior-encoder + decoder** (`enc_p`/`dec`
  tensors, no unit embedding) — mel/latent conditioned, not
  unit-conditioned. It cannot vocode S2U units. Verified by tensor
  inspection, not assumed.
- The repo loader expects a `['generator']`-keyed Code HiFi-GAN
  checkpoint (1000-unit embedding, upsample ×[5,4,4,2,2]).
- Per the Phase 0 stop rule, no substitute vocoder was wired in: a
  mismatched vocoder would change voice identity and fake the
  restoration claim. Waveform synthesis stays open for Phase 4
  (canonical `code_hifigan.pt` from authors, or train own — separate
  decision with data/licensing).

## Limits

- Units were not listening-tested (no vocoder) and not scored against
  references (val audio not shipped). Reproduction proves the S2U path
  runs and its cost — not restoration quality.
- Research-only artifacts; nothing from this phase enters the product
  container or test suite (weights-gated, 400 MB+ downloads — no
  committed tests; P4 adds service tests with the real wiring).

## Next (Phase 4)

`services/speech_restoration/` + `inference/` container design stays
draft until the vocoder question resolves: request `code_hifigan.pt`
from the authors, or scope P4 to S2U-units-as-evidence (restoration as
evidence, never as spoken output without confirmation).
