# Phase 10 — Safety and User Authority Audit (done 2026-11-01)

## What was done and why

Phases 1–9 added speak paths (card tap), data tables (revisions, cards),
and history fields. Phase 10 re-proves the safety invariant against the
whole surface: **no AI-generated or unconfirmed text is speakable through
any API path**, every artifact in the required chain is retrievable, and
every user's data is unreachable from any other account — all tested with
direct forged requests, not frontend flows.

## Gaps closed

- Account wipe missed `ProfileRevision` (user data). Added + tested.
- Session history items now carry the full per-transcript `evidence`
  package (providers, comparison verdict incl. `secondary_text`,
  uncertainty) — the audit trail is one GET, not scattered calls.

## Battery (`test_safety.py`, 5 tests)

Forged approved id → 404; unconfirmed synth → 409 (existing, re-pinned);
cross-user synthesis/confirmation/questions/audio/cards → 404;
card tap provably mints confirmation (direct synth on its approval
works); per-item audit completeness (original, quality, uncertainty,
evidence, suggestion evidence, replayable recording); wipe clears the
revision journal.

## Verified live

Forged + cross-user synthesis refused; audit item complete.
PHASE10-DOCKER-PASS. Suite 90/90.

## Standing statements (re-confirmed, not new)

- Stop playback and method-switching are client-side (files served over
  HTTP; no streaming to interrupt server-side) — Phase 13 frontend work.
- Confirmations are append-only (no edit endpoint for approvals).
- Wonder analysis never speaks. TTS files are wipe-deleted; time-based
  retention sweeping stays a Phase 12 item.
