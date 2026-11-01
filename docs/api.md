# API Reference (`/api/v1/*`)

Auth: `Authorization: Bearer <JWT>`. All errors are JSON (`detail` string or
`{code, message, ...}`). Every response carries `X-Trace-Id`.

## Auth
- `POST /api/v1/auth/register {email, password, display_name}` → `{access_token}`
- `POST /api/v1/auth/login` → `{access_token}`
- `GET /api/v1/auth/me`

## Sessions & audio
- `POST /api/v1/audio/sessions {title, language}` → session
- `POST /api/v1/audio/sessions/{id}/audio` (raw audio bytes, `Content-Type: audio/*`, ≤15 MB) → `{audio_id, duration_s, mime, audio_quality, rerecord_suggested}`
- `GET /api/v1/audio/sessions/{sid}/audio/{aid}` (Phase 8: replay the original recording; ownership + retention checked)

## Communication cards (Phase 9)
- `GET /api/v1/cards?category=&favorites=` (12 seeded defaults, emoji + verified native labels) · `POST /api/v1/cards` · `PATCH /api/v1/cards/{id}` · `DELETE /api/v1/cards/{id}`
- `POST /api/v1/cards/{id}/speak` (tap IS the confirmation → standard synthesis path, gate intact)
- `POST /api/v1/cards/{id}/illustrate` → 409 `IMAGE_UNAVAILABLE` until a verified provider is wired
- `GET /api/v1/sessions` · `GET /api/v1/sessions/{id}` (full audit trail; items carry `audio_quality`)

## Audio quality (Phase 1, see `phase-1-audio-intelligence.md`)
Every upload is assessed on the normalized PCM sent to ASR. `audio_quality`
is `{analyzed, quality: good|usable|poor|unknown, issues[], advice[],
rerecord_suggested, duration_s, peak, rms, snr_db, silence_fraction,
clipping_fraction, longest_silence_s, longest_speech_s}`. Advisory only —
transcription always proceeds.

## Transcription (Muse Voice Transcribe)
- `POST /api/v1/transcription {audio_id, language_hint, keywords[]}` → `{transcript_id, text_original, language, provider, detection, audio_quality, rerecord_suggested, uncertainty[]}` (evidence package persisted on the transcript row)
  - 409 `ASR_FALLBACK_NO_KEY` when no `META_API_KEY` — use manual entry.
- `POST /api/v1/transcription/manual?audio_id=&manual_transcript=&language=` (labelled `manual-entry`; stores a `manual_entry` evidence package)
- `POST /api/v1/transcription/file?session_id=&language_hint=` (multipart upload + transcribe, also returns `audio_quality`)
- `POST /api/v1/transcription/compare {audio_id, language_hint, keywords[], force_secondary?}` (Phase 2) → `{primary, secondary|null, comparison{verdict: single|agree|disagree|both_empty, word_diffs[], meaning_divergence[], language_match}, evidence_package, uncertainty[]}` (Phase 3; analysis-only, not stored)

## Reconstruction (Muse Spark, evidence-first)
- `POST /api/v1/reconstruction {transcript_id, user_request}` → suggestion with `original_text, proposed_text, explanation, changed_words[], alternatives[], needs_clarification, clarification_question, abstained, meaning_risk, provider` + `context_used[]` (Phase 6) + `evidence_for[], evidence_missing[], uncertainty_reasons[]` (Phase 7; persisted on the suggestion row and shown in session history)
- `POST /api/v1/reconstruction/alternatives {transcript_id, count}`
- `POST /api/v1/reconstruction/clarify/{suggestion_id}` (Muse Wonder when routed, labelled fallback otherwise)

## Confirmation & feedback (user authority)
- `POST /api/v1/confirmation {suggestion_id?, transcript_id?, final_text, language, source, save_as_learning?, force?}` → `{approved_message_id}` (Phase 8: 409 `CLARIFICATION_PENDING` while blockers stand; `force: true` overrides with audited `forced_over`)
- `GET /api/v1/reconstruction/questions/{suggestion_id}` → `{questions[{id, target, question, options[{id, label, source}], allows, severity, reason}], answers, unresolved_blockers[], audio_url}` · `POST .../answer {question_id, kind: select|type|saved_phrase|skip, value?}`
- `POST /api/v1/feedback {suggestion_id?, final_text, kind: edit|reject|accept, save?}`
- `GET /api/v1/feedback/stats` (personalization dashboard incl. Phase 5 profile + Phase 6 reuse/false-personalization metrics)
- `GET /api/v1/learning` · `DELETE /api/v1/learning/{id}` · `GET /api/v1/learning/patterns` (Phase 5: recurring user-approved correction pairs with counts, sources, `ambiguous` flag)

## Speech (confirmed text ONLY)
- `GET /api/v1/speech/voices?language=`
- `POST /api/v1/speech/synthesize {approved_message_id, voice?, speed?}` → `{audio_url, provider, fallback}`
  - 409 `UNCONFIRMED` if no confirmation row — the server-side gate.
  - 409 `VOICE_UNSUPPORTED` with `supported_voices` list.
- `GET /api/v1/speech/audio/{tts_id}` (WAV)

## Language
- `GET /api/v1/languages` · `POST /api/v1/languages/detect?text=` → `{language, confidence_note, code_switch, spans[{lang: hi|mr|en, tokens[]}], languages_present[], ambiguous, script}` (Phase 4: Devanagari lexicons + ळ decide hi-vs-mr, never script alone)
- `POST /api/v1/languages/translate {text, target}` (explicit only; original preserved) → `{original, translated, provider, guard_warnings[]}` (Phase 4: cross-script number/negation checks, advisory)

## Vocabulary & memory
- `GET /api/v1/vocabulary?language=` (Phase 4 filter) · `POST /api/v1/vocabulary` · `PATCH /api/v1/vocabulary/{id}` (Phase 5: term/language/category/status; bumps version) · `GET /api/v1/vocabulary/{id}/revisions` + `POST /api/v1/vocabulary/{id}/rollback/{rev_id}` (Phase 6) · `DELETE /api/v1/vocabulary/{id}` (entries carry `source, status, version`)
- `GET/POST /api/v1/memory` · `PATCH /api/v1/memory/{id}` (Phase 5; bumps version) · `GET /api/v1/memory/{id}/revisions` + `POST /api/v1/memory/{id}/rollback/{rev_id}` (Phase 6) · `DELETE /api/v1/memory/{id}` · `POST /api/v1/memory/export` (entries carry `source, provenance, version`)

## Preferences & account
- `GET/PATCH /api/v1/preferences`
- `POST /api/v1/account/data` (export) · `DELETE /api/v1/account/data` (full wipe)

## Evaluation
- `GET /api/v1/evaluation/compare?reference=&hypothesis=` (WER/CER + guard report)
- `POST /api/v1/evaluation/pipeline-demo {transcript}` (4-pipeline comparison)
- `POST /api/v1/evaluation/study {speakers: {name: {train[], test[]}}}` (Phase 11 offline speaker-separated personalization study; per-speaker + overall intent WER, corruption counts, cross-speaker leakage check)
- `GET /api/v1/evaluation/interaction` (Phase 11 UX metrics from own audit trail: edits/sentence, clarification rate, median confirm seconds, TTS success rate)
