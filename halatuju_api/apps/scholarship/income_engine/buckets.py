"""The name / NRIC bucket comparison every relationship document is judged by. It is its own
module rather than part of `doc_checks` because `relationships`, `identity_checks` and
`str_route` all read it too, and leaving it beside its callers was the one import cycle
this cut had to break.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

from ..vision import relationship_name_match as name_match


# ── Relationship-proof documents: birth certificate + guardianship letter ────
def _name_bucket(extracted, reference):
    if not (extracted or '').strip() or not (reference or '').strip():
        return 'no_ref'
    return 'mismatch' if name_match(extracted, reference) == 'mismatch' else 'match'


#: TD-404: the longest token a single romanised syllable spells (ZHUANG, CHUANG, KWONG …).
_SYLLABLE_MAX = 6


def _romanised_near_miss(extracted, reference):
    """TD-404 — True when two names differ in exactly ONE token that looks like a romanisation variant
    of the same syllable (Chinese names romanise one sound many ways: TAN AH KOW / TAN AH KAU, LEONG /
    LIONG): the same number of tokens, every other token agreeing under the tolerant matcher, and the
    odd pair short (≤ ``_SYLLABLE_MAX``) and sharing its first letter. NEVER a match — it only means a
    NAME comparison cannot tell, so the STR ownership rule asks for the IC/NRIC instead of calling the
    STR a stranger's (`str_route._str_recipient_household_match`). A different given name (KOW / MENG)
    does not qualify.

    TD-408: a reversed patronymic ("KOW ANAK TAN" / "TAN ANAK KAU" — a father and a son) is not a near
    miss (`_near_miss_reversal`); every other pair keeps the rule above unchanged."""
    from ..vision import _canonical_name_seq
    a, b = _canonical_name_seq(extracted), _canonical_name_seq(reference)
    if len(a) != len(b) or len(a) < 2 or _near_miss_reversal(extracted, reference):
        return False
    return _one_syllable_apart(a, b)


def _one_syllable_apart(a, b):
    """Two token lists of one length that agree under the tolerant matcher but for ONE short pair
    sharing its first letter (the TD-404 core, on any length)."""
    from ..vision import _tokens_close
    if len(a) != len(b):
        return False
    rest, odd = list(b), []
    for x in a:
        hit = next((i for i, y in enumerate(rest) if _tokens_close(x, y)), None)
        if hit is None:
            odd.append(x)
        else:
            rest.pop(hit)
    return (len(odd) == 1 and len(rest) == 1 and odd[0][0] == rest[0][0]
            and max(len(odd[0]), len(rest[0])) <= _SYLLABLE_MAX)


def _near_miss_reversal(extracted, reference):
    """TD-408 — `name_order.patronymic_reversed` with the near miss's own tolerance on each part (the
    tolerant matcher, or one romanised syllable apart), so KOW / KAU across the connector still counts
    as the same word in a reversal."""
    from ..name_order import patronymic_reversed
    from ..vision import _canonical_name_seq

    def close(x, y):
        ok = (name_match(x, y) != 'mismatch'
              or _one_syllable_apart(_canonical_name_seq(x), _canonical_name_seq(y)))
        return 'match' if ok else 'mismatch'
    return patronymic_reversed(extracted, reference, close)


def _nric_bucket(extracted, reference):
    from ..vision import nric_match
    if not (extracted or '').strip() or not (reference or '').strip():
        return 'no_ref'
    return 'match' if nric_match(extracted, reference) else 'mismatch'
