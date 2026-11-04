# CLARIS Phase 8 — Evidence workspaces (frontend)

Date: 2026-11-04. Status: complete. Marker: `CLARIS-P8-DOCKER-PASS`.

## Goal

Surface the Phase 5–7 evidence where the user works: source-labelled
candidates and recognition evidence in the communication workspace, and
the personalization review on the learn page. Frontend-only phase —
no backend changes.

## What was built

- `lib/candidates.ts`: `Candidate` type, plain-words `sourceLabel()`
  (never an engine id), `groupCandidates()` — usable text first by
  source priority (contextual → alternative-asr → vocab → rules), then
  flagged readings, then acoustic spans. Tolerates missing input.
- `components/CandidatesPanel.tsx`: "Where this came from" section.
  Usable readings get "Use this text (still needs confirming)" — it
  fills the edit box, never speaks, never confirms. Flagged readings
  stay visible with their guard reason. Spans listed as uncertain
  regions.
- Workspace (`communicate/[sessionId]`): suggestion type carries
  candidates; panel renders under the comparison section; new
  recognition-evidence line under "What We Heard" (provider, typed
  fallback when no ASR ran, no-confidence disclaimer, top uncertainty
  notes).
- Learn page: fetches `/api/v1/personalization/review`; ranked
  correction patterns with counts and ambiguity flags, vocabulary with
  status/use-counts pointing at the vocabulary page for edits, and the
  calibration storage note. Existing stats cards untouched.
- `api.review()` client.

## Verification

- `tsc --noEmit` clean, `next build` prerenders all routes, vitest
  **18/18** (3 new: labels, ordering, malformed-input tolerance).
- Docker: frontend rebuilt and serving, backend healthy with Meta live.
- Headless Chrome: `/learn` redirects to a cleanly rendered login page
  with no page JS errors (only unrelated extension-registry noise);
  new bundle confirmed serving.
- Authenticated visuals (candidates panel populated, review sections
  filled) verified at API + unit level, not in a logged-in browser —
  pending a human eyeball in the running app. Nothing about them is
  claimed beyond what the tests and build prove.

## Honest limits

- No Testing Library in the repo (vitest only, lib-level convention) —
  component rendering is covered by build + types, not DOM tests.
  Matches the project's existing gate; not presented as more.
- Restoration job creation/comparison has no UI yet (API-level,
  Phases 4–5). The workspace shows ASR evidence, not restoration
  evidence — the report does not conflate them.
- Unit counts and pattern counts are shown as provenance, never as
  quality scores.

## Next (Phase 9)

Voice expansion (Google Cloud TTS per assessment; XTTS-v2 stays
excluded) + speaking UX on confirmed text only.
