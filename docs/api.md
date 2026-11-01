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
- `GET /api/v1/sessions` · `GET /api/v1/sessions/{id}` (full audit trail; items carry `audio_quality`)

## Audio quality (Phase 1, see `phase-1-audio-intelligence.md`)
Every upload is assessed on the normalized PCM sent to ASR. `audio_quality`
is `{analyzed, quality: good|usable|poor|unknown, issues[], advice[],
rerecord_suggested, duration_s, peak, rms, snr_db, silence_fraction,
clipping_fraction, longest_silence_s, longest_speech_s}`. Advisory only —
transcription always proceeds.

## Transcription (Muse Voice Transcribe)
- `POST /api/v1/transcription {audio_id, language_hint, keywords[]}` → `{transcript_id, text_original, language, provider, detection, audio_quality, rerecord_suggested}`
  - 409 `ASR_FALLBACK_NO_KEY` when no `META_API_KEY` — use manual entry.
- `POST /api/v1/transcription/manual?audio_id=&manual_transcript=&language=` (labelled `manual-entry`)
- `POST /api/v1/transcription/file?session_id=&language_hint=` (multipart upload + transcribe, also returns `audio_quality`)
- `POST /api/v1/transcription/compare {audio_id, language_hint, keywords[], force_secondary?}` (Phase 2) → `{primary, secondary|null, comparison{verdict: single|agree|disagree|both_empty, word_diffs[], meaning_divergence[], language_match}, evidence_package}`

## Reconstruction (Muse Spark, evidence-first)
- `POST /api/v1/reconstruction {transcript_id, user_request}` → suggestion with `original_text, proposed_text, explanation, changed_words[], alternatives[], needs_clarification, clarification_question, abstained, meaning_risk, provider`
- `POST /api/v1/reconstruction/alternatives {transcript_id, count}`
- `POST /api/v1/reconstruction/clarify/{suggestion_id}` (Muse Wonder when routed, labelled fallback otherwise)

## Confirmation & feedback (user authority)
- `POST /api/v1/confirmation {suggestion_id?, transcript_id?, final_text, language, source, save_as_learning?}` → `{approved_message_id}`
- `POST /api/v1/feedback {suggestion_id?, final_text, kind: edit|reject|accept, save?}`
- `GET /api/v1/feedback/stats` (personalization dashboard)
- `GET /api/v1/learning` · `DELETE /api/v1/learning/{id}`

## Speech (confirmed text ONLY)
- `GET /api/v1/speech/voices?language=`
- `POST /api/v1/speech/synthesize {approved_message_id, voice?, speed?}` → `{audio_url, provider, fallback}`
  - 409 `UNCONFIRMED` if no confirmation row — the server-side gate.
  - 409 `VOICE_UNSUPPORTED` with `supported_voices` list.
- `GET /api/v1/speech/audio/{tts_id}` (WAV)

## Language
- `GET /api/v1/languages` · `POST /api/v1/languages/detect?text=` · `POST /api/v1/languages/translate {text, target}` (explicit only; original preserved)

## Vocabulary & memory
- `GET/POST /api/v1/vocabulary` · `DELETE /api/v1/vocabulary/{id}`
- `GET/POST /api/v1/memory` · `DELETE /api/v1/memory/{id}` · `POST /api/v1/memory/export`

## Preferences & account
- `GET/PATCH /api/v1/preferences`
- `POST /api/v1/account/data` (export) · `DELETE /api/v1/account/data` (full wipe)

## Evaluation
- `GET /api/v1/evaluation/compare?reference=&hypothesis=` (WER/CER + guard report)
- `POST /api/v1/evaluation/pipeline-demo {transcript}` (4-pipeline comparison)
