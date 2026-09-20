"""The name / NRIC bucket comparison every relationship document is judged by. It is its own
module rather than part of `doc_checks` because `relationships`, `identity_checks` and
`str_route` all read it too, and leaving it beside its callers was the one import cycle
this cut had to break.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from ..vision import relationship_name_match as name_match


# ── Relationship-proof documents: birth certificate + guardianship letter ────
def _name_bucket(extracted, reference):
    if not (extracted or '').strip() or not (reference or '').strip():
        return 'no_ref'
    return 'mismatch' if name_match(extracted, reference) == 'mismatch' else 'match'


def _nric_bucket(extracted, reference):
    from ..vision import nric_match
    if not (extracted or '').strip() or not (reference or '').strip():
        return 'no_ref'
    return 'match' if nric_match(extracted, reference) else 'mismatch'


def _combine_relationship(name_b, nric_b, nric_one_digit=False):
    """Combine a relationship row's NAME + NRIC buckets, treating the NAME as the primary
    proof of the link and the NRIC as corroboration. A birth-certificate / letter NRIC is
    AI-read off a security-printed JPN document, so a single misread digit (8↔9, 0↔6 over
    the green guilloche) is common; when the NAME matches, an NRIC clash is therefore amber
    ("look at the number"), NOT a red 'mismatch'. When the clash is exactly one digit
    (``nric_one_digit``) the amber is the more reassuring 'check_near' ("differs by one
    digit — likely a scan misread"); a larger clash is the plainer 'check'. Red is reserved
    for a real NAME mismatch (a genuinely different person) or an NRIC clash with no name to
    vouch for it. Strictly demotes false reds to amber — never turns a real mismatch green.

    ⚠ **AND THE MIRROR OF THAT RULE (BrightPath #19, 2026-09-08): AN EXACTLY-MATCHING NRIC MAY
    VOUCH FOR A DIFFERING NAME.** The paragraph above forgives a misread NUMBER when the name
    agrees. It did not forgive a differing NAME when the number agrees exactly, and the number is
    the stronger evidence of the two: twelve government-issued digits identifying one person,
    against a Tamil name transliterated into Latin script — which varies so routinely that JPN
    issues a letter attesting that two spellings are the same human being. Application 144's
    certificate and her mother's MyKad both read 760201-14-5030 while the names differ by spacing
    and several letters, and we told her to fetch "a corrected birth certificate" she cannot get.
    Application 84 is the same red for a different reason: OUR OCR read her MyKad as
    "KAVITA N. SURE NIAM" instead of SUBRAMANIAM.

    ⚠ IT DEMOTES TO AMBER, NEVER TO GREEN, and only on an EXACT number match — never on
    ``nric_close``, whose whole meaning is "these digits are not the same". A person still reads
    the row. Measured over all 62 live mother rows before shipping: exactly two move (144 and 84),
    and the two genuinely-different-person reds — a different woman on #5, a father's IC in the
    mother slot on #9 — stay red, because neither number matches either.
    """
    if name_b == 'mismatch':
        return 'check_name' if nric_b == 'match' else 'mismatch'
    if name_b == 'match':
        if nric_b == 'mismatch':
            return 'check_near' if nric_one_digit else 'check'
        # ⚠ ONE CELL ALONE IS NOT GREEN (BrightPath #23, owner 2026-09-08). A matching name with
        # no number to check it against used to read as fully verified — "which is how a father
        # with no Malaysian number passes on his name". We checked half of this row, so the row
        # says half: AMBER, and a person decides. It does not block; only a red does.
        return 'match' if nric_b == 'match' else 'check_one'
    # No NAME to compare (no_ref) — the NRIC alone, and the same rule applies to it.
    if nric_b == 'mismatch':
        return 'mismatch'
    if nric_b == 'match':
        return 'check_one'
    return 'no_ref'
