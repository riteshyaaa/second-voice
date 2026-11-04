# CLARIS Phase 6 — Source-labelled reconstruction candidates

Date: 2026-11-04. Status: complete. Marker: `CLARIS-P6-DOCKER-PASS`.

## Goal

Every suggestion now shows its work: each candidate reading is labelled
with where it came from and whether the meaning guards let it through.
Unusable candidates are kept and flagged, never silently dropped.

## Sources

| source | kind | what it is |
|---|---|---|
| rules | text | Deterministic layer output |
| vocab | text | Approved-spelling swaps only |
| alternative-asr | text | Second engine reading, verbatim |
| contextual | text | Spark proposal, verbatim |
| acoustic | uncertain-span | Engine-disagreement regions (flags, not proposals) |

Each text candidate carries its guard verdict and `usable` (no guard
fires, and the rules candidate additionally requires no abstention).
Identical-to-transcript sides produce no vacuous candidates.

## Changes

- `reconstruction_service.label_candidates()` (pure) + wiring into all
  four `suggest()` paths (dev-fallback, transport-failure fallback,
  abstention, success). Abstention keeps the rejected contextual text
  as a flagged candidate — the rejection stays auditable.
- Rejected second readings stay visible with `usable: false`
  (e.g. a negation flip from the other engine).
- `Suggestion.candidates` JSON column + migration `0014`
  (roundtrip-verified: 14 downgrades, schema identical). Stored on every
  suggestion row; returned in the `/reconstruction` response.
- Guard exemption (root fix found by the new tests): user-approved
  vocabulary swaps no longer trip the "name dropped" guard. The
  exemption is exact-pair only (`{variant-lower: canonical}` present and
  the canonical in the proposal); default calls without the map keep
  historical strictness. This also fixes the flagship case in the rules
  layer — an approved "Arav → Aarav" no longer abstains.

## Live verification (real services, Docker)

Upload → Meta ASR → reconstruct on a real clip: transcript ended with a
period, so no vacuous rules candidate; single `contextual` candidate,
`usable: true`, no guards. Spark's stutter cleanup ("TheThe" → "The")
surfaced as the labelled proposal, not a silent rewrite.

## Tests

- Backend **125/125** (5 new: exemption exactness + rules-layer fix,
  candidate sources/gating, offline suggest carries candidates, API
  returns + persists candidates with 404/409 gating).
- Frontend **15/15**. Migration head `06be52d7ad6f` (0014), live in
  Docker; `db` + `backend` healthy, `frontend` serving, `inference`
  healthy.

## Honest limits

- Candidates explain the suggestion; they do not rank it. No scores,
  no confidences — nothing the engines expose supports scoring.
- Acoustic spans come from engine word-diffs only; single-engine
  transcripts have no acoustic flags (documented in the span reason,
  not silently omitted — the source is absent).
- Guards cover Latin-script proper nouns; Devanagari has no case
  signal (pre-existing, documented in code).

## Next (Phase 7)

Personalization review: correction-memory ranking already feeds the
flow; surface what was learned per user for approve/modify/remove.
