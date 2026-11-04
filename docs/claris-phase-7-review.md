# CLARIS Phase 7 — Personalization review

Date: 2026-11-04. Status: complete. Marker: `CLARIS-P7-DOCKER-PASS`.

## Goal

Show the user everything the system learned about them — with the real
actions each item supports — so personalization stays checkable and
reversible. Rank correction memory by reuse; add only the tables a
future calibration flow needs.

## What was built

- `GET /api/v1/personalization/review`
  (`personalization_service.review()`): one per-user view —
  - vocabulary entries with status/provenance/use-counts and
    `edit/delete/rollback` actions (the endpoints already exist);
  - memory entries with the same actions;
  - correction patterns ranked by reuse count with explicit rank,
    ambiguity flags, and sources. Read-only and labelled as derived:
    no pattern is stored or trained separately, so there is nothing
    extra to delete — removing a saved correction removes its pattern;
  - suggestion acceptance/rejection/false-personalization stats, so
    any "improvement" claim stays checkable;
  - calibration clips (empty until a collection flow exists) plus an
    honest storage-only note.
- Ranking: `recognition_patterns()` was already count-ordered and feeds
  retrieval first (correction triggers outrank vocab/history in
  `retrieve_context`); Phase 7 exposes the rank instead of changing the
  order. No silent reordering, no new scoring.
- `CalibrationClip` table + migration `0015` (roundtrip-verified):
  `user_id`, nullable `audio_id`, `prompt_text`, `consent_granted`
  (defaults False), `status`. Tables only — no collection, recording,
  or adaptation flow; nothing records here.

## Live verification (Docker)

Review on a real user with a saved name + phrase: vocabulary and memory
items returned with correct actions and provenance; empty patterns,
zeroed stats, empty calibration list with the storage-only note.
Backend/fronted/inference healthy at migration head `f140e919def2`.

## Tests

- Backend **129/129** (4 new: empty review, ranked patterns with
  actions + isolation, rejection stats, calibration consent default).
- Frontend **15/15**. Migration roundtrip:
  `MIGRATION-ROUNDTRIP-PASS` (15 downgrades, schema identical).

## Honest limits

- Patterns are derived, not manageable objects: there is no per-pattern
  delete because there is no per-pattern row. The review says so; the
  alternative (a fake delete button) would be worse.
- No per-pattern precision/recall: counts are "times the user made this
  correction", not accuracy scores. Not presented as learning curves.
- Calibration is schema, not a feature: any future collection flow
  needs its own consent UX, review, and evaluation before it adapts
  anything.

## Next (Phase 8)

Frontend workspaces: evidence comparison + candidate review + this
personalization review as user-facing screens.
