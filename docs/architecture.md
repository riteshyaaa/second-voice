# System Architecture — Second Voice

## 1. Product principle

"AI may help someone express their thoughts, but it must never take ownership
of those thoughts." Every design decision below serves that sentence.

## 2. Layered architecture (independently testable services)

```
┌ Layer 1 · Audio Acquisition (frontend + POST /audio/sessions, PUT audio) ┐
│ MediaRecorder, upload, playback, pause/resume, format validation          │
└───────────────────────────────┬───────────────────────────────────────────┘
                                ▼
┌ Layer 2 · Speech Recognition (meta_asr_service) ─────────────────────────┐
│ Muse Voice Transcribe → original transcript, preserved permanently        │
└───────────────────────────────┬───────────────────────────────────────────┘
                                ▼
┌ Layer 3 · Language Intelligence (language_service) ──────────────────────┐
│ detect(en/hi/hinglish/mr) · code-switch spans · script pref · translate   │
└───────────────────────────────┬───────────────────────────────────────────┘
                                ▼
┌ Layer 4 · Personal Context (memory_service, vocabulary) ─────────────────┐
│ user-approved vocab + saved phrases + recent approved sentences (opt-in)   │
└───────────────────────────────┬───────────────────────────────────────────┘
                                ▼
┌ Layer 5 · Evidence-First Reconstruction (reconstruction_service) ─────────┐
│ Muse Spark, structured JSON, rules below. Wonder only on route.           │
└───────────────────────────────┬───────────────────────────────────────────┘
                                ▼
┌ Layer 6 · Conversation Memory (memory + learning_events tables) ─────────┐
│ consent-based, editable, deletable, versioned, exportable                 │
└───────────────────────────────┬───────────────────────────────────────────┘
                                ▼
┌ Layer 7 · Confirmation & Speech (confirmation gate + tts_service) ───────┐
│ user Accept/Edit/Reject → confirmation_events → TTS (confirmed only)      │
└───────────────────────────────────────────────────────────────────────────┘
```

Cross-cutting: JWT auth + per-user isolation, Pydantic validation, rate
limits, structured logging with request IDs, audit trail per message.

## 3. Component / service breakdown

Backend (`backend/app/`):

- `api/auth.py` — register, login, me.
- `api/sessions.py` — communication sessions CRUD + history.
- `api/transcription.py` — audio upload → ASR → transcript row.
- `api/reconstruction.py` — suggest + alternatives + clarification.
- `api/languages.py` — detect, translate (explicit), preferences.
- `api/memory.py` — vocabulary + saved context CRUD, export (there is no
  separate `api/vocabulary.py`).
- `api/feedback.py` — corrections, accept/reject, learning events,
  personalization dashboard stats.
- `api/speech.py` — voices, synthesize (**requires confirmation**), stop is
  client-side + server marks stopped.
- `api/settings.py` — preferences (language, script, TTS, learning, audio).
- `services/asr_providers.py` (Phase 2) — `ASRProvider` interface +
  `MetaASRProvider` + registry; `services/asr_orchestration.py` —
  conditional secondary routing, transcript comparison, evidence package.
- `services/meta_asr_service.py` — thin facade (primary shape unchanged).
- `services/uncertainty_service.py` (Phase 3) — observable-only
  uncertainty indicators (closed kind set; no phoneme/confidence claims)
  + evidence-derived reliability notes.
- `services/clarification_service.py` (Phase 8) — deterministic targeted
  questions from stored evidence (max 3, blockers first); answers/skips
  recorded on the suggestion row (`clarification_answers`, migration 0007).
- `api/cards.py` + `CommCard` (Phase 9, migration 0008) — visual
  communication cards speaking through the confirmed path (tap IS the
  confirmation; migration 0009 allows session-less approvals);
  `muse_image_service.py` documents image generation as unverified.
- `services/muse_spark_service.py` — structured reconstruction via Spark.
- `services/muse_wonder_service.py` — routed deep-reasoning only.
- `services/muse_image_service.py` — optional visual cards.
- `services/reconstruction_service.py` — evidence-first rules engine that
  *constrains* model output (negation/names/numbers guard, abstention).
- `services/language_service.py` — heuristic detect (Devanagari ratio,
  code-switch lexicons) + provider hook; never auto-translates output.
- `services/personalization_service.py` (vocab map, correction patterns,
  dashboard; also serves the memory endpoints — there is no separate
  `memory_service.py`), `tts_service.py`, `audio_service.py`
  (validation, storage, mono-16kHz normalization),
  `services/audio_intelligence.py` (Phase 1: recording-quality verdicts on
  the normalized PCM — peak/RMS/SNR/clipping/silence; advisory only),
  `evaluation_service.py` (WER/CER).
- `core/` — config, security (JWT/bcrypt), db session, rate limit,
  logging, provider abstraction (`providers.py`).

Frontend (`frontend/`): App Router pages for landing, auth, onboarding,
dashboard, workspace (`/communicate/[sessionId]`), history, vocabulary,
personalization dashboard, board, language/accessibility/privacy settings.
`lib/api.ts` typed client, `lib/audio.ts` recorder. Large touch targets,
high contrast, reduced-motion, screen-reader labels, keyboard map.

## 4. Database ER diagram

```
users 1──1 user_preferences
users 1──* communication_sessions 1──* audio_assets 1──* transcripts 1──* reconstruction_suggestions
users 1──* approved_messages ──1 confirmation_events
users 1──* corrections   users 1──* vocabulary_entries
users 1──* communication_memory   users 1──* learning_events
approved_messages 1──* tts_requests
confirmation_events → approved_messages (authorizes TTS)

users(id, email, password_hash, created_at)
user_preferences(user_id PK/FK, preferred_language, output_language, script,
  tts_voice, tts_speed, learning_enabled, save_rejections, use_history,
  audio_retention_days, theme, font_scale, reduced_motion, high_contrast)
communication_sessions(id, user_id FK, title, language, status, created_at)
audio_assets(id, session_id FK, file_path, mime, duration_s, quality JSON NULL
  [Phase 1, migration 0002], consent_stored, created_at)
transcripts(id, audio_id FK, text_original, language, provider, model_version, evidence JSON NULL
  [Phase 3, migration 0003: providers, comparison verdict, uncertainty],
  confidence, timestamps JSON, created_at)        ← NEVER updated by AI
reconstruction_suggestions(id, transcript_id FK, proposed_text, explanation,
  changed_words JSON, alternatives JSON, needs_clarification, clarification_question,
  abstained, provider, model_version, status, created_at)
approved_messages(id, user_id FK, session_id FK, suggestion_id FK NULL,
  transcript_id FK, final_text, language, source[accepted|edited|original|translated],
  created_at)
corrections(id, user_id FK, suggestion_id FK, original_text, suggested_text,
  corrected_text, kind, created_at)
vocabulary_entries(id, user_id FK, term, normalized, language, category, times_used,
  times_corrected, created_at)  UNIQUE(user_id, normalized)
communication_memory(id, user_id FK, kind, content, language, version, created_at)
learning_events(id, user_id FK, kind[vocab|language|correction|pattern|rejection],
  detail JSON, provenance, created_at)
confirmation_events(id, approved_message_id FK UNIQUE, confirmed_at, language,
  tts_status, created_at)        ← TTS requires this row
tts_requests(id, approved_message_id FK, provider, voice, language, status,
  audio_path, fallback BOOL, created_at)
```

All child queries filter by `user_id` (API + repository layer). Alembic
migration `0001_init.py` creates this schema with FKs, indexes, constraints.

## 5. Key request flows

Record → Transcribe → Suggest:

```
POST /api/v1/audio/sessions → {session} → PUT audio bytes
→ POST /api/v1/transcription {audio_id} → meta_asr_service
→ transcripts row (original preserved) + language detect
→ POST /api/v1/reconstruction {transcript_id}
  → retrieve vocab + approved context → muse_spark_service
  → reconstruction_service.apply_guards() → suggestion rows
```

Confirm → Speak (server-enforced):

```
POST /api/v1/confirmation {suggestion_id?, final_text}
→ approved_messages + confirmation_events rows
POST /api/v1/speech/synthesize {approved_message_id}
→ 409 UNCONFIRMED if no confirmation row → else TTS audio
```

Learn (consent-gated):

```
POST /api/v1/feedback {suggestion_id, final_text, save:true}
→ corrections + learning_events + vocabulary upsert (normalized, per-user)
→ GET /api/v1/feedback/stats personalization dashboard
```

## 6. Routing policy (latency/cost)

- Every utterance: ASR (+ local language detect, free).
- Every transcript: rules engine + Spark (one call, capped tokens).
- Wonder: only if `needs_clarification` AND (negation/number ambiguity OR ≥2
  competing interpretations with low separation) AND user taps "Ask for
  clarification" or auto-route flags it. Never on the hot path otherwise.
- Image: only when user opens Visual Board and taps Generate.

## 7. Failure & fallback behaviour

Provider errors → 502 with `provider`, `retryable`, `fallback_available`;
nothing is faked. Dev fallback is labelled (`provider="dev-fallback"`) in
every row and API response. TTS without confirmation → 409. Unsupported
voice/language → 409 with `supported_voices`. Audio over 15 MB / non-audio
MIME → 413/415.
