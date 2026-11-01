# Phase 6 — Adaptive Personalization Engine (done 2026-11-01)

## What was built and why

The loop learned but never *retrieved*: every suggestion got the full
vocab dump (capped at 50) plus the last 5 approvals, with no relevance,
no language matching, no limits rationale — and there was no way to tell
whether personalization was helping or harming, nor any way back from a
bad edit. Phase 6 closes the loop: scored retrieval, harm tracking, and
rollback.

## Retrieval (`retrieve_context()`)

- **Deterministic approved swaps are never subsetted.** The full
  `vocab_map` still drives rules — the "correct it 10 times" guarantee
  is untouched. Scoring and caps apply only to *LLM context*.
- **Pattern triggers first** (score 100 + count bonus): a transcript
  containing a previously-corrected mishearing pulls its fix with a
  reason ("you corrected 'arav' → 'Aarav' 4×").
- Then token overlap, language match (Hinglish bridges), recency;
  provisional entries stay usable but marked. Caps: 20 vocab / 5 history
  / 5 hints. Every inclusion carries provenance (`context_used`,
  returned on the suggestion for user review).
- `use_history=false` is honored (history empties; approved swaps stay —
  they are explicit saves, not history mining).
- Prompt v1.4 adds the `correction_patterns` rule: prefer a pattern's fix
  only when its `from` text is present; patterns never override negation,
  names, or numbers (guards still run on all output).

## Harm tracking (definitions)

- `applied_swaps()` (token-based — substring matching is blind exactly
  when canonicals contain their variant, e.g. "arav" in "Aarav") +
  `reverted_swap()`: a user undoing our fired swap records a
  `false_personalization` event (provenance `user-correction`).
- Dashboard: `correction_saves`, `reused_corrections` (saves into
  patterns seen ≥2×), `reuse_rate`, `false_personalizations`,
  `unwanted_rate` (false / suggestions). No silent training anywhere —
  these are counts of explicit user actions.

## Rollback (migration `0005_profile_revisions`)

Pre-edit snapshots journaled on every vocab/memory PATCH; per-entry
revision lists plus restore endpoints (restore journals the pre-restore
state too, bumps version). Cross-user access 404s.

## Verification (observed)

- 4 new tests in `test_adaptation.py` (pattern priority + caps,
  language-ordered history + opt-out, false-event on revert but not on
  keep-with-edits, rollback round-trip + journal growth + 404).
  Two hierarchy fakes updated for the new optional `pattern_hints`
  kwarg (assertions unchanged). Suite 66/66.
- Live Docker on `0005`: Spark suggestion cited `('pattern',
  'Aarav')` in `context_used`; revert recorded
  `false_personalizations: 1`; rollback restored v3.
  PHASE6-DOCKER-PASS.

## Traps & limits

- `create_all` on startup now auto-creates migration tables while the
  alembic pointer lags → `upgrade head` fails DuplicateTable. Worked
  around by aligning the pointer; Phase 12 must pick ONE mechanism
  (migrate-on-startup, drop the stamp + autosync).
- No time-expiry on entries (user deletion is the expiry mechanism);
  provisional status is review metadata (both states apply); prompt v1.4
  validated by the existing guard battery, not a fresh live battery —
  re-run the meaning battery before demoing v1.4 claims.
