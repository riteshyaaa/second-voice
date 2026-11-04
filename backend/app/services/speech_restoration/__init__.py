"""CLARIS Phase 4: speech-restoration pipeline (S2U units as evidence).

Stages: normalize (existing) -> enhance (no implementation: skipped,
honestly) -> s2u_units (inference sidecar, weights-gated) -> vocode
(gated off: no vocoder checkpoint was ever published, Phase 3).

Units are evidence, never spoken output: there is no waveform until the
vocoder question resolves, and no stage invents one.
"""
