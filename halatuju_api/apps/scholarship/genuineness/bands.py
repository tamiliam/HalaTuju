"""Shared probability → soft-status bands for document genuineness.

Calibrated on the 48-doc labelled results-slip corpus (2026-06-15): 46 genuine 0.56–0.80,
1 typed fake 0.04; crediting the visual QR/crest lifts genuine photos to ~0.80. The three
statuses map onto the vocabulary the verdict cap already reads ('likely_genuine' = no cap,
'low_confidence'/'suspect' = soft cap + caveat). Used by the signature scorer; the IC and
supporting-doc checks map their model verdict words to the same statuses directly.
"""
GENUINE_MIN = 0.70      # >= → genuine (no cap)
SUSPECT_MAX = 0.35      # <  → not_<type> (so few signatures it isn't recognisably that document)
# in between (0.35–0.70) → suspect (cropped / partial / not confidently genuine; reviewer confirms).

# The CANONICAL genuineness outcome — shared by EVERY document type, however it's derived
# (probability bands for the signature docs; a holistic model verdict for the IC / STR / EPF):
#   'genuine'    — a real official document of the expected type (no cap)
#   'suspect'    — the right kind of document but not confidently genuine (incomplete/cropped/fabricated)
#   'not_<type>' — not recognisably that document at all ('not_ic', 'not_birth_certificate', …)
# 'suspect' and 'not_<type>' get the SAME soft treatment (cap + officer flag); only the message differs.
_GENUINE = {'genuine', 'likely_genuine'}            # incl. the legacy 'likely_genuine'
_NOT_LEGACY = {'wrong_type', 'not_an_ic'}           # legacy "wrong document" values


def band_for(probability: float) -> str:
    """Probability → canonical band: 'genuine' / 'suspect' / 'not_type' (the caller substitutes
    the doc type for 'not_type', e.g. 'not_birth_certificate')."""
    if probability >= GENUINE_MIN:
        return 'genuine'
    if probability < SUSPECT_MAX:
        return 'not_type'
    return 'suspect'


def canonical_status(raw, doc_type=None) -> str:
    """Fold any genuineness status — current OR legacy (likely_genuine / low_confidence / wrong_type
    / not_an_ic) — to the canonical enum: 'genuine' / 'suspect' / 'not_<type>' / '' (no signal). So
    existing stored authenticity (from live IC/supporting runs) keeps working without a backfill."""
    s = (raw or '').strip().lower()
    if not s:
        return ''
    if s in _GENUINE:
        return 'genuine'
    if s.startswith('not_') or s in _NOT_LEGACY:
        return f'not_{doc_type}' if doc_type else (s if s.startswith('not_') else 'not_document')
    return 'suspect'   # low_confidence / suspect / review / anything else non-empty


def needs_attention(raw, doc_type=None) -> bool:
    """Does this genuineness status warrant the soft cap + officer flag? — anything non-empty
    that isn't 'genuine'."""
    return canonical_status(raw, doc_type) not in ('', 'genuine')
