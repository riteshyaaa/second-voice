# Phase 7 — Evidence-First Reconstruction 2.0 (done 2026-11-01)

## What was built and why

Reconstruction received a flat transcript plus prose reliability note and
returned prose explanations. Guards covered negation/numbers only.
Phase 7 threads the structured evidence built in Phases 1–6 into and out
of the reconstruction layer, and adds a deterministic semantic layer for
the meaning-carriers the old guards missed.

## Deterministic semantic checks (all run on every suggestion, incl. model output)

Added to `violates_guards()`: proper-noun preservation (Latin-script
capitals past sentence start — Devanagari has no case, documented gap),
date/time patterns (fixed a `findall`-subgroup trap with `finditer`
group(0) so 10:30 vs 11:30 can't compare equal), modal verbs
(can vs must), conditionals (if/unless + Hindi/Marathi markers),
quantity units, and medical/emergency terms (never droppable).
`risk_floor()`: medical content is at least medium risk.
`escalate()`: risk-severity observables lift under-confident lows,
meaning divergence forces clarification, abstentions pass through
untouched — it never lowers anything.

Known strictness: unit synonyms (tablets→pills) trip the unit guard and
abstain rather than paraphrase. Safe direction; synonym mapping is a
next step.

## Structured Spark I/O (prompt v1.5)

New inputs: `secondary_transcript`, `uncertainty_indicators`,
`language_spans`, `correction_patterns` (Phase 6). New outputs:
`evidence_for` (what supports each change), `evidence_missing` (what
could not be verified), `uncertainty_reasons` (echoed observables, never
invented confidence). Prompt rules extended for names/dates/modals/
medical (medical ⇒ risk ≥ medium) and second-engine handling (one more
imperfect interpretation, never ground truth).

## Persistence (migration `0006_suggestion_evidence`)

Suggestions store `evidence_for`/`evidence_missing`; transcripts already
carry `secondary_text` via `pack_evidence()` (unified helper for the
live and manual paths); session history exposes suggestion evidence for
audit.

## Verification (observed)

- 7 new tests in `test_reconstruction_v2.py` (guard matrix, escalation,
  pack helper, output keys + medical floor). Two hierarchy fakes
  extended for new kwargs/fields (assertions unchanged). Suite 73/73.
- Live Docker on `0006`: real Spark preserved "Aarav", "10:30", and the
  conditional, held risk at medium, and returned honest evidence
  ("no second opinion", "no word-level confidence scores").
  PHASE7-DOCKER-PASS.

## Limits

Proper nouns uncovered in Devanagari; unit synonyms over-abstain;
`0006` downgrade written, not executed live; v1.5 battery was one live
probe plus the guard suite — re-run the full 14-case meaning battery
before demoing v1.5 claims.
