"""Shared probability → soft-status bands for document genuineness.

Calibrated on the 48-doc labelled results-slip corpus (2026-06-15): 46 genuine 0.56–0.80,
1 typed fake 0.04; crediting the visual QR/crest lifts genuine photos to ~0.80. The three
statuses map onto the vocabulary the verdict cap already reads ('likely_genuine' = no cap,
'low_confidence'/'suspect' = soft cap + caveat). Used by the signature scorer; the IC and
supporting-doc checks map their model verdict words to the same statuses directly.
"""
GENUINE_MIN = 0.70      # >= → likely_genuine (no cap)
SUSPECT_MAX = 0.35      # <  → suspect (typed/fabricated; cap + flag)
# in between → low_confidence (review): a cropped/partial genuine doc, reviewer confirms.


def band_for(probability: float) -> str:
    """Probability → soft status: 'likely_genuine' / 'low_confidence' / 'suspect'."""
    if probability >= GENUINE_MIN:
        return 'likely_genuine'
    if probability < SUSPECT_MAX:
        return 'suspect'
    return 'low_confidence'
