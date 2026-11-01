"""Phase 11: speaker-separated personalization study harness.

Fully offline and reproducible: no network, no DB writes, no model calls.
The caller supplies per-speaker bundles of {original ASR text, user-approved
reference} pairs split into train/test. The harness:

1. builds each speaker's vocab from THEIR train pairs ONLY, using the same
   rule as the runtime learning path (same-length token alignment, stopwords
   skipped — see personalization.learn_correction_pattern);
2. runs each test case through rules-only reconstruction with no vocab
   (baseline) and with that speaker's vocab (personalized);
3. reports per-speaker and overall intent WER, corruption (guard violations
   of the original), abstentions, and a cross-speaker leakage check.

Random-clip splits are forbidden: splits are caller-supplied per speaker,
and speakers never share vocab entries.
"""
from . import evaluation_service, reconstruction_service
from .personalization_service import STOP


def vocab_from_train(pairs: list[dict]) -> dict[str, str]:
    """Mirror of the runtime user-save rule: a train pair is an (ASR
    mishearing, user-approved reference). Same-length pairs contribute
    variant->canonical swaps; different-length pairs contribute nothing
    (the runtime records those only as phrasing patterns)."""
    vocab: dict[str, str] = {}
    for p in pairs:
        o = (p.get("original") or "").split()
        r = (p.get("reference") or "").split()
        if len(o) != len(r) or not o:
            continue
        for a, b in zip(o, r):
            if a.lower() != b.lower() and a.lower() not in STOP and b.lower() not in STOP:
                vocab[a.lower()] = b
    return vocab


def _run_case(original: str, reference: str, vocab: dict) -> dict:
    out = reconstruction_service.rules_only_suggestion(original, vocab)
    proposed = out["proposed_text"]
    return {
        "original": original, "reference": reference, "proposed": proposed,
        "abstained": out["abstained"],
        "intent_wer": (evaluation_service.wer(reference, proposed)["wer"]
                       if reference.strip() else None),
        "corruption": evaluation_service.guard_report(original, proposed)["violations"],
    }


def run_study(study: dict) -> dict:
    """study = {"speakers": {name: {"train": [...], "test": [...]}}}."""
    speakers = (study or {}).get("speakers", {})
    vocabs = {name: vocab_from_train(b.get("train", [])) for name, b in speakers.items()}
    per_speaker: dict[str, dict] = {}
    leaks = 0
    leak_checks = 0
    for name, bundle in speakers.items():
        tests = bundle.get("test", [])
        mine = vocabs[name]
        base_wers, pers_wers, base_corr, pers_corr = [], [], 0, 0
        cases = []
        for t in tests:
            o, r = t.get("original", ""), t.get("reference", "")
            base = _run_case(o, r, {})
            pers = _run_case(o, r, mine)
            base_corr += len(base["corruption"])
            pers_corr += len(pers["corruption"])
            if base["intent_wer"] is not None:
                base_wers.append(base["intent_wer"])
                pers_wers.append(pers["intent_wer"])
            cases.append({"original": o, "reference": r,
                          "baseline": base["proposed"], "personalized": pers["proposed"],
                          "baseline_wer": base["intent_wer"], "personalized_wer": pers["intent_wer"],
                          "abstained": pers["abstained"]})
            # leakage: every OTHER speaker's vocab must not change my output
            for other, ov in vocabs.items():
                if other == name:
                    continue
                leak_checks += 1
                if _run_case(o, r, ov)["proposed"] != base["proposed"]:
                    leaks += 1
        per_speaker[name] = {
            "train_pairs": len(bundle.get("train", [])), "test_cases": len(tests),
            "vocab_entries": len(mine), "vocab": mine,
            "mean_baseline_wer": round(sum(base_wers) / len(base_wers), 3) if base_wers else None,
            "mean_personalized_wer": round(sum(pers_wers) / len(pers_wers), 3) if pers_wers else None,
            "corruption_baseline": base_corr, "corruption_personalized": pers_corr,
            "cases": cases,
        }
    all_base = [c["baseline_wer"] for s in per_speaker.values() for c in s["cases"] if c["baseline_wer"] is not None]
    all_pers = [c["personalized_wer"] for s in per_speaker.values() for c in s["cases"] if c["personalized_wer"] is not None]
    return {
        "speakers": per_speaker,
        "leakage": {"checks": leak_checks, "leaks": leaks},
        "overall": {
            "speakers": len(per_speaker),
            "mean_baseline_wer": round(sum(all_base) / len(all_base), 3) if all_base else None,
            "mean_personalized_wer": round(sum(all_pers) / len(all_pers), 3) if all_pers else None,
        },
        "scope": ("offline deterministic pipelines only (rules, rules+vocab). "
                  "Live Spark, second-ASR agreement and clarification loops are "
                  "covered separately by /evaluation/pipeline-demo, "
                  "/transcription/compare and the Phase 11 validation probes — "
                  "not by this harness."),
    }
