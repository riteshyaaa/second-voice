# Privacy, Security & Responsible AI

- **Isolation:** every query filters by `user_id` at the API layer; cross-user
  access returns 404 (tested in `test_personalization.py::test_user_isolation`).
- **Auth:** bcrypt passwords, JWT bearer tokens, no keys in code or logs.
- **Audio:** stored only as private files under `STORAGE_DIR`; served only to
  the owner; retention enforced (`audio_retention_days`, 410 when expired).
- **Learning consent:** `learning_enabled` master switch; rejections stored
  only if `save_rejections` is on; no silent fine-tuning — retrieval-based
  personalization from user-approved rows only.
- **Transparency:** every AI output carries `provider` + `model_version`;
  dev-fallback is always labelled, never presented as Meta output.
- **Confirmation:** TTS rejects unconfirmed text server-side (409
  `UNCONFIRMED`); full audit (`transcripts` → `suggestions` → `approved` →
  `confirmation_events` → `tts_requests`).
- **Control:** export (`POST /account/data`), full wipe (`DELETE
  /account/data`), per-entry vocabulary/memory deletion.
- **Transport/storage:** run behind TLS in production; secrets only via env;
  rate limits + input validation + 15 MB audio cap.
- **Scope:** assistive communication prototype. No diagnosis, no treatment,
  no clinical-effectiveness claims. Generated suggestions are never presented
  as the user's confirmed words.
