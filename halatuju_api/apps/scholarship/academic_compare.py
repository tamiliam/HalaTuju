"""The typed grades against the results slip (``academic_engine.compare_academics``).

⚠ WHY THIS IS A MODULE (request #62, 2026-11-06). ``academic_engine.py`` is on the oversize ledger
(`code-standards.json`) with ten lines of room, and request #62 has to grow this comparison. The
function below was MOVED here verbatim, in its own commit, with no behaviour change;
``academic_engine.compare_academics`` stays as a seam so every caller and test keeps its import.
The subject-name normalisers it reads stay in ``academic_engine`` (their one home).
"""
from __future__ import annotations

from .academic_engine import (_GRADE_TO_BAND, _SUBJECT_BM, _base_letter, _is_char_loss,
                              _norm_grade, _norm_lower_alnum, _slip_key)


def compare_academics(profile_grades, slip) -> dict:
    """Compare the slip's subjects/grades against what the student typed.

    Returns ``{slip_count, missing, mismatched: [{subject, typed, slip}],
    uncertain: [{subject, typed, slip, band}], have_grades, complete, accurate}``.

    The slip prints each grade twice — a letter AND a Malay band. When the two
    DISAGREE for a row, the read is unreliable for that subject, so a would-be
    grade mismatch is downgraded to **uncertain** ("please check") rather than
    asserted as a confident mismatch (guards against an OCR row-transposition
    confidently telling the student a wrong grade)."""
    prof_by_name = {}
    for key, grade in (profile_grades or {}).items():
        nm = _SUBJECT_BM.get(key)
        if nm and grade:
            prof_by_name[_norm_lower_alnum(nm)] = grade

    slip_norm = {}  # normname → first readable form
    for n in slip['names']:
        slip_norm.setdefault(_slip_key(n), n)
    bands = slip.get('bands', {})
    letters = slip.get('letters', {})

    missing = sorted(orig for nn, orig in slip_norm.items() if nn not in prof_by_name)
    mismatched, uncertain = [], []
    for nn, slip_g in slip['grades'].items():
        typed = prof_by_name.get(nn)
        if not typed or _norm_grade(typed) == _norm_grade(slip_g):
            continue  # not entered, or the typed grade matches the slip letter
        band_g = bands.get(nn)
        row = {'subject': slip_norm.get(nn, nn), 'typed': typed, 'slip': slip_g}
        band_conflict = bool(band_g) and _norm_grade(band_g) != _norm_grade(slip_g)
        # A difference that is ONLY the +/- modifier (A+ vs A) sits in the OCR's blind
        # spot — the letter's ± is a tiny, easily-dropped mark. BUT when the printed
        # letter AND the Malay band agree with each other (a DOUBLE-CONFIRMED read) *and*
        # the typed grade's own band phrase could NOT degrade into the read band by losing
        # characters, the read is trusted → a CONFIDENT mismatch: the student typed the
        # wrong grade (#71: typed A−/'cemerlang', slip A/'cemerlang tinggi' — OCR doesn't
        # INVENT the word 'tinggi'). The char-loss guard keeps the live Fizik A+ case
        # uncertain: 'cemerlang tinggi' IS a degraded 'cemerlang tertinggi' (the faint
        # 'ter' drops), so letter+band agreeing on A can still mean a real A+. Letter-only
        # reads and letter↔band conflicts likewise stay 'uncertain' (check by eye).
        pm_only = _base_letter(typed) == _base_letter(slip_g)
        letter = letters.get(nn, '')
        double_confirmed = bool(band_g) and bool(letter) and \
            _norm_grade(letter) == _norm_grade(band_g)
        typed_phrase = _GRADE_TO_BAND.get(_norm_grade(typed), '')
        read_phrase = _GRADE_TO_BAND.get(_norm_grade(band_g or ''), '')
        plausible_degradation = bool(typed_phrase) and bool(read_phrase) and \
            _is_char_loss(read_phrase, typed_phrase)
        if pm_only and double_confirmed and not band_conflict and not plausible_degradation:
            mismatched.append({**row, 'band_confirmed': True})
        elif band_conflict or pm_only:
            uncertain.append({**row, 'band': band_g or ''})
        else:
            mismatched.append(row)
    return {
        'slip_count': len(slip_norm),
        'missing': missing,
        'mismatched': mismatched,
        'uncertain': uncertain,
        'have_grades': bool(slip['grades']),
        'complete': len(slip_norm) > 0 and not missing,
        'accurate': not mismatched and not uncertain,
    }
