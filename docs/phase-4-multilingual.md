# Phase 4 — Multilingual Intelligence (done 2026-11-01)

## What was built and why

Detection was script-led: any Devanagari read as Hindi, so Marathi was
systematically mislabelled (validation report §3), spans only knew hi/en,
translation had no safety checks, and vocabulary review had no language
view. Phase 4 fixes the detection layer honestly — lexicons, not script —
and puts guards on the translation path.

## Changes (`backend/app/services/language_service.py`)

- **Devanagari lexicons** for Hindi and Marathi. Script alone never
  decides hi-vs-mr anymore; पानी (hi, dental न) vs पाणी (mr, retroflex
  ण) are distinct entries, and **ळ (U+0933)** is a Marathi signature
  signal. Devanagari with no lexicon hit on either side keeps the old
  Hindi default but now says so (`devanagari-script default`).
- **Segment spans tag hi/mr/en per token**; Devanagari tokens without a
  lexicon hit take the sentence decision. Response adds
  `languages_present[]`, `ambiguous` (close hi/mr calls surface for
  clarification instead of guessing), and `script`.
- **Script preference** (`script_of` + `check_script`): detection and
  mismatch reporting only. Full transliteration needs a benchmarked
  engine with native-speaker review — evaluated as a next step, never
  hand-rolled into an AAC product.
- **`translation_guards()`**: cross-script digit check (Devanagari
  digits normalized), multilingual negation-presence check, emptiness,
  lenient length sanity. Advisory warnings on the translate response —
  the user still confirms which version is spoken. Cross-script name
  preservation stays a documented limitation.
- **Vocabulary `?language=` filter** on `GET /vocabulary` for per-language
  review (the learning dashboard's Phase 6 needs it). Swap application
  stays match-based, which is self-limiting by construction: a term can
  only fire when its text is actually present.

## Verification (observed)

- 10 new tests in `test_multilingual.py` (mr Devanagari ±ळ, hi
  stability, ambiguity flag, mr span runs, script checks, guard matrix,
  endpoint guards + vocab filter). Suite 59/59 green, including all
  pre-existing language tests unchanged.
- Live Docker: mr Devanagari → `mr`, hi → `hi`, mr→en span runs correct,
  and real Spark translated "मुझे २ गोलियां चाहिए" → "I need 2 pills"
  with zero guard warnings (२→2 digit handling proven live).
  PHASE4-DOCKER-PASS.

## Limits

Devanagari Marathi without ळ or lexicon hits still defaults to Hindi
(surfaced honestly in `confidence_note`); `ambiguous` exists but no
clarification flow consumes it yet (Phase 8); transliteration unevaluated;
name preservation across scripts unchecked; user language/script
preferences are stored but not yet enforced as ASR hints end-to-end.
