# Validation Report — real-world audio-to-speech (2026-10-31)

Live validation with **actual recordings** (freely licensed Wikimedia Commons
speech, see `infrastructure/scripts/validation_corpus.py`) against the real
Meta endpoints, plus the full learning loop and confirmation gate through the
backend API. Nothing here is mocked. Raw evidence:
`infrastructure/scripts/validation_asr_results.json`,
`validation_meaning_results.json`, `validation_learning_results.json`.
Per-item headings below carry the seven required dimensions
(Feature · Test · Result · Evidence · Failures · Limitations · Next action).

## Corpus

11 real clips + 1 constructed code-switch. Exact references come from the
Lingua Libre transcription in each filename; sentence references are
approximate (spoken-Wikipedia openings).

- Hindi exact: paani, ladka, phal, 46, 99. Marathi exact: panchsheel, pune, shaniwarwada.
- English exact: water caltrop, water dripping. Hindi sentence: dengue lead (25 s).
- Constructed: paani + water caltrop concatenated (labelled as constructed).

## 1. ASR request integration

- Test: sent real WAV bytes to `POST /v1/asr/transcribe` in three shapes.
- Result: PASS after two rejections taught us the true contract.
- Evidence: `Both a 'request' and an 'audio' part are required`; then
  `expected mono s16le at 16000 or 24000 Hz` for 44.1 kHz input.
- Failures: initial shape (form fields) and 44.1 kHz audio rejected.
- Limitations: `language`/`keywords` field names accepted but hint effect ~nil.
- Next action: DONE in code — `normalize_to_wav16k()` in `audio_service.py`,
  verified shape in `meta_asr_service.py`, regression tests added.

## 2. Hindi ASR (5 exact single words)

- Test: live transcribe, auto mode + explicit `hi` hint, WER/CER vs exact refs.
- Result: MIXED. Sentence-level Hindi is fluent; isolated words skew English.
- Evidence: 99 → exact Devanagari (CER 0.11); paani → "Bani."; phal →
  "Fala."/"Fall"/"Follow." across runs; 46 → "Che alikes" and once Korean
  hangul. Hinted WER identical-or-worse (1.0→2.0 on 46).
- Failures: English-default bias on ≤1.2 s clips; one script-collapsed output.
- Limitations: single words lack context; ASR is nondeterministic run to run.
- Next action: app already passes user language as hint; add UI nudge to
  confirm language on short utterances; re-test with phrase-length Hindi.

## 3. Marathi ASR (3 exact words/names)

- Test: same protocol, `mr` hints.
- Result: MIXED. Script correct (Devanagari), our detector labels it "hi".
- Evidence: panchsheel → exact match (WER 0.0); shaniwarwada → Devanagari
  phonetics (script right, WER vs latin ref 1–2); pune clip repeats the word
  (7.7 s audio vs 1-word ref → WER 4.0, a reference-granularity artifact).
- Failures: detector has no Marathi-vs-Hindi distinction (script-only).
- Limitations: latin-script refs punish correct Devanagari output.
- Next action: add lexicon-based mr/hi disambiguation; score script-aware WER.

## 4. English ASR (2 clips)

- Test: same protocol.
- Result: PARTIAL. "water caltrop." exact (WER 0.0, 2.3 s); "Water dripping"
  (9.25 s, high energy, peak 25371) → **empty transcript, HTTP 200, 3/3 runs**.
- Evidence: energy audit in report; retry probe; results JSON row.
- Failures: deterministic empty output on loud, valid speech.
- Limitations: content unauditioned (no playback here); root cause undetermined.
- Next action: escalate clip + session IDs to provider; add empty-transcript
  alerting (treat as abstention, prompt re-record).

## 5. Hindi sentence + Hinglish code-switch

- Test: 25 s dengue lead; intra-utterance mixes (Hindi dengue + English
  "water caltrop" inserted mid-stream, 1.3 s and 2.7 s spans). No natural
  Hinglish recordings exist on Wikimedia Commons (0 hits, 2026-10-31), so
  both mixes are constructed from real clips and labelled as such.
- Result: PARTIAL with a threshold finding. Dengue lead fluent Devanagari.
  The 1.3 s English insertion was DROPPED entirely (transcript reads as
  continuous Hindi, switch flag false). The 2.7 s insertion survived
  ("...water caltrop water caltrop..."). Earlier word-level mix transcribed
  both spans ("Bani. Water caltrop.").
- Evidence: `validation_hinglish_results.json` (committed run) + variant probe
  transcript; suggest latency 8.5 s on the 18 s clip.
- Failures: brief embedded-language spans get smoothed away; switch flag and
  detector miss the mix either way.
- Limitations: constructed splices (audible boundary stutter in variant);
  natural Hinglish still untested; detector tested on latin-script output only.
- Next action: warn users that quick English insertions may be lost and to
  replay original audio (already supported); span-level switch detection;
  source natural Hinglish recordings.

## 6. Auto language identification

- Test: `asr_language` field across 12 clips.
- Result: FAIL as a signal — always "en", even for perfect Devanagari output.
- Evidence: 12/12 rows `asr_language: en`, including exact Hindi/Marathi hits.
- Failures: provider auto-ID unusable for routing on this content.
- Limitations: only short clips tested; may behave better on long audio.
- Next action: DONE in design — app uses explicit user preference as hint and
  its own detector; never trust `asr_language` alone (documented).

## 7. Evidence hierarchy (code fix, validated)

- Test: reframed audio as primary evidence, transcript as imperfect
  interpretation, in prompt v1.3 + API reliability note + service plumbing.
- Result: PASS. Prompt pins "IMPERFECT"; API passes provider/version/
  confidence provenance per transcript; service forwards it to the model.
- Evidence: `test_hierarchy.py` (4 tests), live suggest() still meta-spark.
- Failures: none found.
- Limitations: model may still overweight fluent-but-wrong transcripts.
- Next action: surface reliability note in the workspace UI next to the
  original transcript.

## 8. Meaning preservation, live Spark (14 cases)

- Test: negation (en/hi), numbers, names, intent, disfluency, garbage, empty,
  vocab repair, stability — pass = guards clean + no invention + abstain.
- Result: 14/14 PASS, 0 guard violations, 0 invented words, 3/3 abstentions
  echoed input without adding content. Median latency 3.65 s (2.7–11.8 s).
- Evidence: `validation_meaning_results.json`; suite `test_reconstruction.py`.
- Failures: none. (Methodology note: one Hindi case rendered English because
  the battery passed preference "en"; re-ran with "hi" → preserved.)
- Limitations: 14 hand-picked cases, not a population sample.
- Next action: grow battery from real user corrections (consented).

## 9. Language preservation

- Test: Hindi inputs with preference "hi" through live suggest().
- Result: PASS. Output stayed Hindi, numbers/negation intact.
- Evidence: probe output (Devanagari preserved, "3" preserved).
- Failures: none under correct preference. Hinglish preference test: the
  mixed transcript came back unchanged (guards clean) — but since ASR had
  already deleted the English span, this verifies stability, not mix
  preservation. True mix preservation is untestable until ASR keeps the mix.
- Limitations: Hinglish/Marathi preservation not yet live-tested on real mixes.
- Next action: same battery in hi/hinglish/mr with matching preferences.

## 10. Learning loop, consent, CRUD (22/22 via API)

- Test: real audio → live ASR "Bonnie." → correct to पानी with consent →
  next session reuses; disable switch; rejection opt-in; vocab/memory CRUD;
  verbatim confirmation; gate 409/404/401; isolation; full wipe.
- Result: 22/22 PASS. Reuse worked ("Bonnie." → पानी next session).
- Evidence: `validation_learning_results.json` + TestClient logs.
- Failures: none.
- Limitations: single correction pair; long-term retention untested.
- Next action: longitudinal check — same user, 10 corrections, reuse rate.

## 11. Latency (measured, not claimed)

- ASR: ~2–3.3 s for 1–8 s clips; 7.3–7.8 s for 25 s. Suggest: 2.7–11.8 s,
  median ~3.6 s. Fallback TTS WAV: instant local. Azure/ElevenLabs: unmeasured.
- Next action: set user-visible budgets (e.g. 30 s reconstruct timeout is
  already generous); measure hosted TTS when keys exist.

## 12. Dysarthric datasets

- Test: checked TORGO/UASpeech access terms; asked the user for access or
  consented samples (2026-10-31).
- Result: BLOCKED. Both need human-completed license/request processes; the
  user declined all offered paths ("none of the above", no alternative given).
- Evidence: TORGO free for academic non-profit via request; UASpeech licensed.
- Limitations: all speech above is typical speech; dysarthric accuracy unknown.
- Next action (concrete unblock): (a) complete the TORGO request or UASpeech
  license and place audio where the harness can read it; or (b) provide
  consented dysarthric recordings with references. Then run:
  `evaluation/compare` per speaker (never pooled across speakers), report
  per-speaker WER/CER + guard stats. Harness and protocol are ready in
  `docs/evaluation.md`.

## 13. Docker deployment — VERIFIED 2026-10-31

- Test: full `docker compose up --build -d` on this machine (Docker 29.9.2,
  Compose v5.6.1) + `smoke_e2e.py` + live Hindi ASR + seed + migrations.
- Result: PASS. db/backend healthy, frontend serving; smoke passes with
  **live meta-spark** on Postgres; real Hindi clip → `meta-asr`; demo seed
  works; `upgrade head` exits 0 with `current` = head.
- Evidence: container health output, smoke transcript, seed output (this
  session); per-user Docker path needed one addition (`resources/bin` on
  PATH for `docker-credential-desktop` — environment setup, not repo).
- Failures found and fixed: (1) `@rollup/rollup-win32-x64-msvc` in
  devDependencies broke the Linux build (EBADPLATFORM) → moved to
  `optionalDependencies`; (2) bare `alembic` can't see the app package in
  the image → docs now use `python -m alembic`; (3) `upgrade head` failed
  on init_db-created schemas → startup now stamps head (sqlite skipped).
- Limitations: single-node Docker Desktop; TLS/backup/restore untested.
- Next action: exercise backup/restore (§6) before production data lands.

## Bugs fixed this phase (all with regression tests)

1. Wrong ASR multipart shape → verified `request`+`audio` contract.
2. 44.1 kHz rejected → server-side `normalize_to_wav16k()` (+`miniaudio` dep).
3. Chat-completions null content → Responses API + low reasoning effort.
4. Prompt v1.2 treated transcript as ground truth → v1.3 + reliability note.
5. Suite: 25/25 green (`test_hierarchy.py`, `test_audio_norm.py` added).

## Aggregate metrics

- Exact-ref WER (auto): mean 1.10 (0.78 excluding the pune reference
  artifact); CER mean 1.47. Script-aware reading: 4/10 phonetically correct
  (2 exact Devanagari).
- Code-switch: 1.3 s embedded English span dropped by ASR; 2.7 s span kept.
  No natural Hinglish audio found on Commons (0 hits).
- False correction rate: 0/14. Meaning preservation: 14/14. Abstention: 3/3.
- Personalization: correction→reuse demonstrated end to end (22/22 battery).
- Docker: VERIFIED same day (§13). Still blocked (user declined
  alternatives 2026-10-31): dysarthric corpora.
- No API keys appear anywhere in this report or the evidence files.
