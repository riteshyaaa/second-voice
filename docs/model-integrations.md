# Model Integration Plan (verified, Oct 2026)

Sources checked: Meta Model API docs via dev.meta.ai / api.meta.ai
(OpenAI-compatible surface), MarkTechPost + Dataconomy + BizzBuzz (Sept 2026
launch coverage), orcarouter.ai Muse API survey, promptfoo Meta provider docs,
anarlog `meta` STT PR (#7498), spora-ai Muse plugin, vtcode Meta provider docs.

## 1. Platform

- **Base URL:** `https://api.meta.ai/v1` (configurable via `META_BASE_URL`).
- **Auth:** `Authorization: Bearer $META_API_KEY` (`MODEL_API_KEY` in Meta
  docs; key created at <https://dev.meta.ai> → API Keys).
- **Retired:** the separate Llama API at `api.llama.com` (retired 2026-07-06)
  — this project uses only `api.meta.ai`.
- All model IDs below are used verbatim; nothing is invented. If Meta
  renames a model, change only the `META_*_MODEL` env var.

## 2. Muse Voice Transcribe — speech recognition

- **Model:** `muse-voice-transcribe-1.0` (Meta Superintelligence Labs' first
  real-time audio perception model, released 2026-09-01).
- **REST:** `POST https://api.meta.ai/v1/asr/transcribe` with two
  multipart parts (verified live 2026-10-31 — the API rejects anything else):
  `request` = JSON `{"model": "muse-voice-transcribe-1.0",
  "audioEncoding": "WAV", "language"?: ..., "keywords"?: [...]}` and `audio`
  = the file bytes. `language`/`keywords` field names accepted without error;
  language-hint effect on 1 s clips measured as negligible (see validation
  report).
- **Realtime:** `wss://api.meta.ai/v1/asr/realtime` (in-handshake auth).
- **Native capabilities:** streaming ASR, speaker diarization (20+ speakers),
  endpointing (`<|speech_onset|>`, `<|speech_endpoint|>`), native
  code-switching, multilingual incl. five Indian languages per launch
  coverage. Pricing ~$3 / 1,000 audio-minutes.
- **What we send:** every upload normalized server-side to mono s16le WAV
  at 16 kHz (the endpoint rejects 44.1 kHz: "expected mono s16le at 16000 or
  24000 Hz") + `language` = user preference, overrideable + `keywords[]` =
  approved vocabulary terms. Original file stays stored untouched for replay.
- **What we store:** transcript text, detected language, provider
  `meta-asr`, model version, confidence/timestamps **only if the response
  contains them** — we never fabricate word-level confidence.
- **Honesty note:** general language support ≠ dysarthric-speech accuracy.
  `docs/evaluation.md` benchmarks WER/CER per speaker; no clinical claims.

## 3. Muse Spark — contextual reconstruction

- **Models:** `muse-spark-1.3` (current recommendation), fallbacks `1.2`,
  `1.1`. Env: `META_SPARK_MODEL`.
- **Endpoint:** `POST https://api.meta.ai/v1/responses` (Meta's
  recommended surface; verified live 2026-10-31). The chat-completions
  endpoint also answers, but is not used: `muse-spark-1.3` is a reasoning
  model and can spend the whole `max_tokens` budget thinking, returning
  `content: null`.
- **Reasoning control:** `reasoning: {"effort": "low"}`, `max_output_tokens`
  2500 (reconstruction) / 1500 (translation). Verified: low effort completes
  in ~850–1200 tokens with valid JSON; medium effort over-thinks past the
  budget on this constrained task, so it is reserved for Wonder.
- **Request:** system prompt (evidence-first rules, versioned in
  `services/prompts.py`) + user payload with **separated** fields:
  `asr_transcript`, `acoustic_evidence`, `vocabulary[]`,
  `history[]`, `language_preference`, `user_request`.
- **Response contract:** strict JSON validated by Pydantic
  (`SuggestionSchema`): `proposed_text`, `explanation`, `changed_words[]`,
  `alternatives[]`, `needs_clarification`, `clarification_question`,
  `meaning_risk`. Malformed → retry once → rules-only fallback (labelled).
- **Cost control:** one call per transcript, `max_output_tokens` cap,
  timeout 90 s (120 s Wonder), never in a loop. Typical reconstruction costs
  ~1–2k tokens total. Self-reported confidence is surfaced as
  `model_uncertainty_note`, never as a calibrated probability.

## 4. Muse Wonder — routed reasoning only

- **Model:** `muse-wonder-1.0` via `POST https://api.meta.ai/v1/responses`
  with `reasoning: {"effort": "medium"}`, `max_output_tokens` 4000
  (verified live 2026-10-31: returns a targeted clarification question).
- **Used for:** competing interpretations, contradiction checks,
  clarification questions — only when the router flags complex ambiguity
  (negation/number at stake, or ≥2 close interpretations) or the user taps
  "Ask for clarification". Ordinary reconstructions never call it.
- **Output:** ranked interpretations + contradiction flags + one short
  clarification question; still requires user confirmation.

## 5. Muse Image — optional visual board

- **Model:** `muse-image-1.0` (same platform image endpoint).
- **Used for:** visual communication cards from *user-approved* concepts
  only. Never input to reconstruction; never evidence of what was said.
- Optional; primary workflow works without it.

## 6. Open weights (Spark Open / Glimmer)

- `Muse Spark Open` (open-weight, ~Oct 2026; OpenAI-compatible
  `chat/completions`, e.g. `meta/muse-spark-open`) and Glimmer were
  evaluated: suitable only for self-hosted deployments with GPU + licensing
  review. The `ModelProvider` abstraction (`core/providers.py`) lets them be
  plugged in without rewriting services. Default remains the hosted API.

## 7. TTS (NOT Muse Voice Transcribe)

Muse Voice Transcribe is STT-only. TTS is a separate provider:

- `TTS_PROVIDER=azure` → Azure Speech (voice per language, speed control).
- `TTS_PROVIDER=elevenlabs` → ElevenLabs equivalent.
- default `webspeech-fallback` → backend returns a labelled placeholder WAV
  (`fallback:true`) and the frontend speaks via `speechSynthesis`.
- Unsupported language/voice → transparent 409 + supported list.

## 8. Provider abstraction

`core/providers.py`: `ProviderStatus {live, missing_key, error}`,
`MetaProvider` (real HTTP via `httpx`, retries + timeouts + cost logging),
`DevFallbackProvider` (deterministic rules, always labelled). Every service
returns `(result, ProviderStatus)` and every DB row / API response carries
`provider` + `model_version` so UI can badge "Meta live" vs "Dev fallback".
No mock is ever presented as a Meta response.

## 9. Verification checklist

- [ ] `META_API_KEY` set → `/api/v1/transcription` returns
  `provider:"meta-asr"`.
- [ ] ASR 401 → 502 `ASR_UNAUTHORIZED`, fallback offered, nothing faked.
- [ ] Spark malformed JSON → 1 retry → rules-only suggestion labelled.
- [ ] No key → all AI responses carry `provider:"dev-fallback"`.
- [ ] No `Authorization` header ever leaves the backend; keys only in env.
