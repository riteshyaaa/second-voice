# Phase 13 — Frontend experience (2.0)

Board rewired to the cards API, workspace honesty pass, clarification
surfacing. No backend changes.

## Safety fixes (the point of this phase)

Three confirm-before-speak bypasses removed:

1. Workspace quick phrases called device speech directly — unconfirmed text
   spoken with no audit. Now: favorite cards via tap-to-speak (tap IS the
   audited confirmation).
2. `prompt()` Quick Edit set a local "accepted" flag with no backend
   confirmation. Removed; the inline edit box + Confirm-my-edit path only.
3. `speak()` played whenever a local flag was set, including for demo clips.
   Now: `speak()` requires a backend `approved_message_id`. Demo samples are
   explicitly labeled ("not your message") and play only through a separate
   demo button.

Remaining device-speech uses (2): confirmed-text fallback when the server has
no TTS audio, and the labeled demo sample. Both legitimate.

## Board (`/board`)

- Cards loaded from `GET /api/v1/cards` (12 seeds, categories, native
  labels), grouped favorites-first (`lib/cards.ts`, unit-tested).
- Tap → `POST /cards/{id}/speak` → server audio played, last-spoken shown,
  Stop control. Favorite toggle, delete, add-custom (en/hi/mr), category
  filter. Old hardcoded tiles and memory-phrase hack deleted.

## Workspace (`/communicate/[id]`)

- Removed fabricated precision: hardcoded "96% confident", "96.4%",
  "94% latency lock", fake calibrator panel, hardcoded user, fake voice
  presets, pitch/gain sliders that affected nothing.
- Real data instead: account name + saved-word count, provider + risk badge
  per suggestion, real voice list from `/speech/voices` wired to
  `synthesize(voice, speed)`.
- Clarification (Phase 8) surfaced for the first time: questions with option
  buttons / typed answers / explicit skip, original-audio replay, blocker
  count gating confirm, re-check after answering. `acceptBackend` refuses
  while blockers are open (server also 409s — both layers agree).
- Save-to-vocabulary wired to the real endpoint (was a toast-only fake).
- Sidebar fiction replaced with real navigation links + how-it-works note.
- Demo clips reframed: loading fills the type box to run the real pipeline
  (manual-transcript path), never presented as "what we heard".

## Accessibility

- 44–64 px touch targets, labeled controls, `role=status/alert` live
  regions, pre-existing `:focus-visible` + `prefers-reduced-motion` global
  rules kept. No `prompt()`/`alert()` blocking calls remain.

## Validation

- `tsc --noEmit` clean; vitest 12/12 (6 new cards tests: grouping,
  URL building, tap-to-speak server + fallback paths).
- `next build` clean; frontend container rebuilt and serving.
- Live Docker probe PHASE13-DOCKER-PASS: 12 cards → favorite → tap speak →
  audited TTS request → interaction shows 1 confirmed + 1 TTS.
- Component rendering beyond the served bundle is not browser-verified
  (no browser automation in this environment); page shells return 200 and
  the shipped JS bundle was confirmed to contain the new board code.

## Honest limits

- No React Testing Library (dependency disproportionate) — UI logic covered
  at the lib level; pages verified via build + bundle + API probes.
- Illustration endpoint still 409 (unverified Muse Image shapes) — no UI
  button added for it.
