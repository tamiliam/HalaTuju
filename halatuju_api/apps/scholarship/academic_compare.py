"""The typed grades against the results slip (``academic_engine.compare_academics``).

⚠ WHY THIS IS A MODULE (request #62, 2026-11-06). ``academic_engine.py`` is on the oversize ledger
(`code-standards.json`) with ten lines of room, and request #62 has to grow this comparison. The
function below was MOVED here verbatim, in its own commit, with no behaviour change;
``academic_engine.compare_academics`` stays as a seam so every caller and test keeps its import.
The subject-name normalisers it reads stay in ``academic_engine`` (their one home).
"""
from __future__ import annotations

from .academic_engine import (_CELL_NOISE, _GRADE_TO_BAND, _SUBJECT_BM, _base_letter, _is_char_loss,
                              _match_known_subject, _norm_grade, _norm_lower_alnum, _slip_key)
from .slip_subject_aliases import ENGLISH_NAMES

_KNOWN_KEYS = frozenset(_norm_lower_alnum(n) for n in _SUBJECT_BM.values())
#: (Malay key, English words), LONGEST first so "Additional Mathematics" wins over "Mathematics".
_ENGLISH = sorted(((_norm_lower_alnum(bm), frozenset(_norm_lower_alnum(en).split()))
                   for en, bm in ENGLISH_NAMES.items()), key=lambda t: -len(t[1]))


def _compare_key(name: str) -> str:
    """``_slip_key`` plus the six English slip names (request #62). COMPARISON ONLY: the readers
    (``_parse_grade_row``, ``spm_cert_parse``) never see these names, so no read changes (a slip row
    "ENGLISH FOR SCIENCE AND TECHNOLOGY" is never Sains). A cell folds to the Malay subject when it
    holds the English name (and maybe the Malay one, "1449 MATEMATIK MATHEMATICS") plus only a
    subject code / grade / band."""
    key = _slip_key(name)
    if key in _KNOWN_KEYS:
        return key
    words = set(key.split())
    for bm, en in _ENGLISH:
        if en <= words and all(t.isdigit() or len(t) <= 2 or t in _CELL_NOISE
                               for t in words - en - set(bm.split())):
            return bm
    return key


def _printed_keys(line: str) -> set:
    """The subject keys one RAW printed slip line shows: its ``_compare_key`` (an English name, with
    only a code / grade / band beside it), plus the longest Malay subject it CONTAINS — the readers'
    own containment rule (``_match_known_subject``, Malay and old names only), because a raw line
    carries the noise the reader could not get past ("1511 SAINS <watermark> ACEMERLANG TINGGI").
    Longest-first, so "SAINS KOMPUTER" is never Sains; English stays strict, so "ENGLISH FOR SCIENCE
    AND TECHNOLOGY" is never Sains either."""
    found = _match_known_subject(line)
    return {_compare_key(line)} | ({_norm_lower_alnum(found)} if found else set())


def compare_academics(profile_grades, slip) -> dict:
    """Compare the slip's subjects/grades against what the student typed.

    Returns ``{slip_count, missing, extra, mismatched: [{subject, typed, slip}],
    uncertain: [{subject, typed, slip, band}], have_grades, complete, accurate}``. ``missing`` =
    on the slip, not typed; ``extra`` = typed, not on the slip (request #62, complete reads only).

    The slip prints each grade twice — a letter AND a Malay band. When the two
    DISAGREE for a row, the read is unreliable for that subject, so a would-be
    grade mismatch is downgraded to **uncertain** ("please check") rather than
    asserted as a confident mismatch (guards against an OCR row-transposition
    confidently telling the student a wrong grade)."""
    prof_by_name, typed_name = {}, {}   # normname → typed grade / the subject's readable BM name
    for key, grade in (profile_grades or {}).items():
        nm = _SUBJECT_BM.get(key)
        if nm and grade:
            prof_by_name[_norm_lower_alnum(nm)] = grade
            typed_name[_norm_lower_alnum(nm)] = nm

    slip_norm = {}  # normname → first readable form
    for n in slip['names']:
        slip_norm.setdefault(_compare_key(n), n)
    # read_slip keys these by `_slip_key`; re-key them the same way as the names (an English row).
    grades, bands, letters = ({_compare_key(k): v for k, v in (slip.get(f) or {}).items()}
                              for f in ('grades', 'bands', 'letters'))

    missing = sorted(orig for nn, orig in slip_norm.items() if nn not in prof_by_name)
    # Request #62 (owner 2026-11-06): a subject the student TYPED that is not on the slip is
    # flagged too, as "please check" (the slip is the authoritative record, decisions 2026-06-02).
    # Only on a COMPLETE read — names AND grades, the same `have_grades` test that decides whether
    # accuracy can be judged. A legacy names-only read (or a grades-less one) may simply have
    # missed a row, so it never asserts that a typed subject is absent.
    # A subject PRINTED on the slip is never extra, even when the stored read dropped its row (the
    # local reader skipped rows it did not know, e.g. an English name; those reads are never re-read):
    # any of its raw printed lines (`_debug_rows`, local reads only) that shows it counts. A Gemini
    # read keeps no raw lines, so its extra stands.
    printed = set(slip_norm).union(*(_printed_keys(line) for line in slip.get('raw_lines') or ()))
    extra = sorted(typed_name[nn] for nn in prof_by_name if nn not in printed) if slip['grades'] else []
    mismatched, uncertain = [], []
    for nn, slip_g in grades.items():
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
        'extra': extra,
        'complete': len(slip_norm) > 0 and not missing and not extra,
        'accurate': not mismatched and not uncertain,
    }
