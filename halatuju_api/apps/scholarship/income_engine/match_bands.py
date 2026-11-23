"""THE ONE ROW SCORE for a relationship document (request #78, owner rulings 23 Nov 2026).

A row is one person on a birth certificate or guardianship letter compared with that person's
reference: the certificate's child against the student, its mother against the mother's own IC,
a letter's guardian against the guardian's IC, a letter's ward against the student. Each row is
scored on its NAME and its IC NUMBER, by slips counted (never percentages), into one band:

    GREEN  both exact; or one exact and the other close; or NO NUMBER and a name today's
           name-only link accepts (`relationship_name_match`)
    BLUE   both close; or exact number + far name (a name change, a bad read)
    AMBER  close + far; exact name + far number; NO NAME and an exact or close number
    RED    both far, or one far and the other missing
    GREY   nothing read

⚠ OWNER RULING, 23 Nov 2026 (later the same evening): NO NUMBER ON THE DOCUMENT = THE NAME ALONE,
AS TODAY. When the document or the reference IC gives no IC number for a row, the NAME decides it
by today's matcher (passes → GREEN, fails → RED), exactly as the name-only decision did before #78;
the wider slip-count close name counts only where a number stands beside it. "One value
missing = AMBER" applies only when the NAME is missing and the number is present. The ward row on a
guardianship letter is always judged on the name alone (letters never print the ward's number).

Two rows make the relationship link (``link_band``): only RED asks the student to act, GREEN
confirms the link, and everything between goes to the reviewer. The case-page chips
(`doc_checks`) and the decision (`relationships.mother_relationship` / `guardian_relationship`,
and the certificate's CHILD row on the mononym father fallback, `relationships._bc_link`) all
read this module, so they can no longer disagree.

A close number is one digit changed, dropped or added (`vision.nric_close`). A close name is the
owner's slip count OR anything today's tolerant matcher accepts, so no row that passes today
turns red.

⚠ OUTSIDE THE BANDS, ON PURPOSE: the FATHER row on a birth certificate and the father / brother /
sister patronymic links (BrightPath #23: the father row never blocks). Pure: no I/O, no queries.
"""
from __future__ import annotations

import re
from itertools import permutations

from ..name_order import patronymic_reversed
from ..vision import _canonical_name_seq, _fold_name_token, _levenshtein, nric_close
from ..vision import name_match as exact_name_match
from ..vision import relationship_name_match

GREEN, BLUE, AMBER, RED, GREY = 'green', 'blue', 'amber', 'red', 'grey'
EXACT, CLOSE, FAR, MISSING = 'exact', 'close', 'far', 'missing'

#: A word this long may carry two slips; a shorter one, one (owner: slips are counted).
_LONG_WORD = 8
#: Above this many words the pairing search stops trying every order (names are short).
_PAIRING_CAP = 7


def _digits(s) -> str:
    return re.sub(r'\D', '', str(s or ''))


def number_level(read, ref) -> str:
    """EXACT (every digit equal) · CLOSE (exactly ONE digit changed, dropped or added:
    `vision.nric_close`, owner ruling 23 Nov 2026) · FAR · MISSING (either side blank)."""
    a, b = _digits(read), _digits(ref)
    if not a or not b:
        return MISSING
    if a == b:
        return EXACT
    return CLOSE if nric_close(a, b) else FAR


def _word_close(x: str, y: str) -> bool:
    fx, fy = _fold_name_token(x), _fold_name_token(y)
    allowed = 2 if max(len(x), len(y)) >= _LONG_WORD else 1
    return _levenshtein(fx, fy) <= allowed


def _slips_close(read: str, ref: str) -> bool:
    """The owner's close name: every word within one letter (two in a word of 8+ letters), with
    at most one word missing or extra. Word order does not matter. A father's and a son's
    reversed patronymic (TD-408) is never close."""
    a, b = _canonical_name_seq(read), _canonical_name_seq(ref)
    if not a or not b or abs(len(a) - len(b)) > 1:
        return False
    if patronymic_reversed(read, ref, relationship_name_match):
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if len(long_) > _PAIRING_CAP:
        return False
    for order in permutations(long_, len(short)):
        if all(_word_close(x, y) for x, y in zip(short, order)):
            return True
    return False


def name_level(read, ref) -> str:
    """EXACT (the same words, ignoring spacing, word order and the connectors) · CLOSE · FAR ·
    MISSING. CLOSE is the owner's slip count OR anything today's tolerant matcher already accepts
    (`relationship_name_match`): no name that passes today may score FAR (never newly red)."""
    if not (read or '').strip() or not (ref or '').strip():
        return MISSING
    if exact_name_match(read, ref) == 'match':
        return EXACT
    if relationship_name_match(read, ref) != 'mismatch' or _slips_close(read, ref):
        return CLOSE
    return FAR


_RANK = {EXACT: 0, CLOSE: 1, FAR: 2, MISSING: 3}


def best_name_level(read, refs) -> str:
    """The best `name_level` of ``read`` against any of ``refs`` (the student's typed name and
    the name off their own verified IC are two spellings of ONE identity)."""
    levels = [name_level(read, r) for r in refs if (r or '').strip()] or [MISSING]
    return min(levels, key=_RANK.get)


_BAND = {
    (EXACT, EXACT): GREEN, (EXACT, CLOSE): GREEN, (CLOSE, EXACT): GREEN,
    (CLOSE, CLOSE): BLUE, (FAR, EXACT): BLUE,
    (CLOSE, FAR): AMBER, (FAR, CLOSE): AMBER, (EXACT, FAR): AMBER,
    (EXACT, MISSING): GREEN, (CLOSE, MISSING): GREEN,      # no number: the name decides (ruling)
    (MISSING, EXACT): AMBER, (MISSING, CLOSE): AMBER,      # no name: a number alone is not green
    (FAR, FAR): RED, (FAR, MISSING): RED, (MISSING, FAR): RED,
    (MISSING, MISSING): GREY,
}


def row_band(name_lvl: str, number_lvl: str) -> str:
    """The owner's table, (name level, number level) → band. All sixteen pairs are listed."""
    return _BAND[(name_lvl, number_lvl)]


def name_alone_level(read, refs) -> str:
    """The name level when NO NUMBER corroborates it: EXACT / CLOSE only where today's name-only
    link passes (`relationship_name_match` not 'mismatch' against one of ``refs``), else FAR.

    ⚠ OWNER RULING 23 Nov 2026: "no number on the document = name alone, AS TODAY". The owner's
    wider slip count (`_slips_close`, no 5-letter floor) needs a number beside it: alone it would
    merge short words the floor keeps apart on purpose (`vision.names._tokens_close`: Siva≠Sira,
    Vani≠Vasu; TD-404) and turn today's reds green (review round 1: K RAJAN vs M RAJAN)."""
    level = best_name_level(read, refs)
    if level not in (EXACT, CLOSE):
        return level                    # FAR / MISSING stand as they are
    today = any(relationship_name_match(read, r) != 'mismatch' for r in refs if (r or '').strip())
    return level if today else FAR


def score_row(name, nric, ref_names, ref_nric, *, waiting=False) -> dict:
    """One row: ``{name, number, band, waiting}``. ``waiting`` marks a GREY row whose REFERENCE
    is not in yet (the parent's IC not uploaded or not read) — as opposed to a row the document
    itself could not give us. With no number on either side the name is judged as today
    (`name_alone_level`); the slip-count close name counts only beside a number."""
    if isinstance(ref_names, str):
        ref_names = (ref_names,)
    k = number_level(nric, ref_nric)
    n = name_alone_level(name, ref_names) if k == MISSING else best_name_level(name, ref_names)
    band = row_band(n, k)
    return {'name': n, 'number': k, 'band': band, 'waiting': bool(waiting and band == GREY)}


def score_name_only_row(name, ref_names) -> dict:
    """A row whose document never carries a number (a guardianship letter's WARD: letters never
    print the ward's number). Owner ruling 23 Nov 2026: judged on the name alone, always, by
    today's matcher (`name_alone_level`): passes → GREEN, fails → RED, blank → GREY."""
    if isinstance(ref_names, str):
        ref_names = (ref_names,)
    n = name_alone_level(name, ref_names)
    return {'name': n, 'number': MISSING, 'band': row_band(n, MISSING), 'waiting': False}


def link_band(child: dict, parent: dict) -> str:
    """Part B: the link "this parent is the student's parent" from its two rows. Chips have no
    blue (BLUE shows as AMBER). RED + anything = RED; G+G = G; any other mix of green / blue /
    amber = AMBER — B+B too, even with both numbers exact (owner ruling 23 Nov 2026: the officer
    checks; the link is never confirmed while both names are far); GREY + GREEN = GREY while
    the other document is still coming, AMBER once everything is in; both GREY = GREY."""
    bands = (child['band'], parent['band'])
    if RED in bands:
        return RED
    if bands == (GREY, GREY):
        return GREY
    if GREY in bands:
        grey_row = child if child['band'] == GREY else parent
        other = parent['band'] if grey_row is child else child['band']
        return GREY if (other == GREEN and grey_row['waiting']) else AMBER
    if bands == (GREEN, GREEN):
        return GREEN
    return AMBER                       # B+B included: both names far, both numbers exact (ruling)


def link_status(band: str) -> str:
    """The decision's word for a link band: GREEN → 'match' (the relationship is confirmed),
    RED → 'mismatch' (the only state that asks the student to act), anything else → 'pending'
    (no claim; the officer looks)."""
    return {GREEN: 'match', RED: 'mismatch'}.get(band, 'pending')


def chip_status(row: dict) -> str:
    """The served row status the web already draws (`checklists.relPill`, `cockpitDocFacts`):
    GREEN 'match', RED 'mismatch', GREY 'no_ref'; BLUE and AMBER as one of the amber
    'check_*' words, chosen by which cell held."""
    band, n, k = row['band'], row['name'], row['number']
    if band in (GREEN, RED):
        return 'match' if band == GREEN else 'mismatch'
    if band == GREY:
        return 'no_ref'
    if n == FAR and k == EXACT:
        return 'check_name'            # #19: spelt differently, the same IC number
    if n in (EXACT, CLOSE) and k == FAR:
        return 'check'                 # the name holds; check the number
    if n == CLOSE and k == CLOSE:
        return 'check_near'            # one slip in each: likely a scan misread
    if n == FAR and k == CLOSE:
        return 'check_both'            # spelt differently AND one digit off: both were read
    return 'check_one'                 # the number held with no name to read beside it


def mother_link(child_name, child_nric, mother_name, mother_nric,
                student_names, student_nric, ic_name, ic_nric) -> dict:
    """A birth certificate's child + mother rows and the link they make."""
    child = score_row(child_name, child_nric, student_names, student_nric)
    waiting = not ((ic_name or '').strip() or (ic_nric or '').strip())
    parent = score_row(mother_name, mother_nric, (ic_name,), ic_nric, waiting=waiting)
    return {'child': child, 'parent': parent, 'link': link_band(child, parent)}


def guardian_link_rows(guardian_name, guardian_nric, ward_name,
                       student_names, ic_name, ic_nric) -> dict:
    """A guardianship letter's ward + guardian rows and the link they make. The ward row is the
    name alone, as today (owner ruling 23 Nov 2026), so an UNREAD ward has no say, as before
    (review F1): the link is then the guardian row's own band (BLUE shown as AMBER)."""
    ward = score_name_only_row(ward_name, student_names)
    waiting = not ((ic_name or '').strip() or (ic_nric or '').strip())
    parent = score_row(guardian_name, guardian_nric, (ic_name,), ic_nric, waiting=waiting)
    if ward['band'] == GREY:
        link = AMBER if parent['band'] == BLUE else parent['band']
    else:
        link = link_band(ward, parent)
    return {'child': ward, 'parent': parent, 'link': link}
