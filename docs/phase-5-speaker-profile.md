# Phase 5 — Personal Speaker Profile (done 2026-11-01)

## What was built and why

Vocabulary and memory rows had no provenance, no approval state, no
versioning, and no edit path — only add/delete. Correction patterns were
counted nowhere a user could review them. Phase 5 turns the existing
tables into a structured, reviewable speaker profile without changing
what gets learned or when.

## Changes

- **Migration `0004_profile_provenance`**: `vocabulary_entries` gains
  `source` / `status` (`approved|provisional`) / `version`;
  `communication_memory` gains `source` / `provenance`; `corrections`
  gains `provenance`. Backfills read `user-approved/approved/v1`, which
  is what those rows were — every one came from an explicit save.
- **Edit support**: `PATCH /vocabulary/{id}` (term/language/category/
  status; term edits renormalize; every edit bumps `version`) and
  `PATCH /memory/{id}` (kind/content/language; bumps `version`).
  Ownership enforced (cross-user → 404), status validated (422).
- **Recognition patterns** (`recognition_patterns()` +
  `GET /learning/patterns`): recurring mishearing→correction pairs
  counted **only from user-approved corrections**. Counts come from
  Correction rows (one per explicit save); pattern events add a source
  label — counting both would double every save, and a case-sensitivity
  trap (`aarav` vs `Aarav`) was fixed by case-insensitive keying that
  keeps the user's casing for display. Terms with competing readings are
  flagged `ambiguous` (clarification candidates for Phase 8).
- **Dashboard profile section** (additive): `vocab_by_language`,
  `provisional_count`, `top_patterns`, `ambiguous_terms`.
- List responses now expose provenance fields for review UI.

## Explicit non-goals (documented, not deferred silently)

- No audio-based speaker analysis: phoneme data doesn't exist in this
  system, so "recurring recognition errors" means counted user edits.
- No medical inference of any kind — the endpoint docstring says so.
- No automatic rules: pattern rows never write back into vocabulary;
  promotion to a vocab entry stays a user action.
- No profile rollback yet (versions recorded; restore endpoint is
  Phase 6 scope).

## Verification (observed)

- 3 new tests in `test_profile.py` (defaults, edit/version/422/404,
  patterns with exact counts + ambiguity, dashboard keys). Suite 62/62.
- Live Docker on migration `0004`: provenance defaults, edit→v2,
  patterns `{arav→Aarav ×2, sources [correction, pattern]}`,
  dashboard keys. PHASE5-DOCKER-PASS.

## Limits

`status=provisional` is review metadata — both states still apply in
suggestions (promotion/demotion semantics belong to Phase 6 reuse
scoring); `0004` downgrade written, not executed live.
