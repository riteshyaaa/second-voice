# Phase 2 — Multi-Engine ASR Orchestration (done 2026-11-01)

## What was built and why

The system depended on one recognizer with no seam for a second opinion.
Phase 2 adds the seam — provider interface, conditional routing,
comparison, evidence package — while changing **nothing** about default
behavior. No second engine is adopted here: the spec requires benchmarking
before adoption, and that research is the explicit next step.

## Design

- `services/asr_providers.py` — `ASRProvider` ABC (`transcribe`,
  `supported_languages`, `supported_formats`, `health_check`,
  `provider_metadata`) + `MetaASRProvider` (the old logic, moved
  **verbatim**: 17/17 AST statements identical, 0 diffs vs the committed
  version) + registry (`get_provider`, `primary_provider`,
  `second_available`).
- `services/asr_orchestration.py` — `orchestrate()` (primary, then
  conditional secondary), `should_run_secondary()` (pure, testable),
  `compare_transcripts()` (pure: agree/disagree/both_empty/single +
  word diffs + guard-based meaning divergence + language match),
  `evidence_package()` (quality, provider versions, trigger,
  `model_confidence: None`, reliability note).
- `services/meta_asr_service.py` — now a thin facade: `transcribe()`
  returns `orchestrate()["primary"]` (identical shape to pre-Phase-2);
  `transcribe_multi()` returns the full result; `status()` unchanged.
- `POST /api/v1/transcription/compare` (`CompareIn`: `TranscribeIn` +
  `force_secondary`) — full multi-engine result for one audio.
- Config: `SECOND_ASR_ENABLED` (default false), `SECOND_ASR_PROVIDER`
  (default empty).

## Routing rules (cost/latency)

Secondary runs only when an engine is configured AND justified: explicit
request, empty primary, or usable/poor quality. `mostly_silence` /
`too_short` never trigger it (nothing to re-recognize). `force` cannot
conjure an unconfigured engine. Agreement is recorded, never proof —
both engines can share bias (verified live: short-Hindi English-default).
Both transcripts are always preserved; nothing is silently replaced.

## Verification (observed)

- 7 new tests in `test_asr_orchestration.py` (interface conformance,
  fallback shape identical to pre-Phase-2, single-engine orchestration,
  pure comparison incl. negation-flip divergence, routing matrix, stub
  secondary end-to-end, compare endpoint). Suite 41/41 green.
- Verbatim move proven by AST statement diff, not eyeballing.
- Live Docker check passed: rebuilt image, real Meta primary
  (`meta-asr`, live), `single` verdict, force-without-engine stays
  single. Test key is monkeypatched empty so the suite never touches
  the network.

## Second-engine adoption criteria (next step, not this phase)

Benchmark candidates on Hindi / English / Marathi accuracy, Hinglish and
code-switch spans, dysarthric speech where lawful data exists, latency,
cost, privacy, licensing, reliability — on the committed validation
corpus first, never on generic benchmark rankings alone. Only then
register behind `SECOND_ASR_ENABLED`.

## Limits

Comparison is text-level (no timings — no provider exposes them); the
evidence package is returned, not yet persisted (Phase 3 decides);
`health_check` for Meta reports key presence, not a live probe (no audio
sent, by design).
