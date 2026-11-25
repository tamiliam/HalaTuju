"""THE CASE-PAGE DISPLAY of the identity links (TD-742 linkage Phase 1, owner ruling 25 Nov 2026).

⛔ DISPLAY ONLY. Nothing here feeds a decision, a gate, an owed line, a verdict, the stranger rule or
an Action Centre hold. Those still read the decision fields of `income_engine` (``name_status``,
``nric_status``, ``proof_*_status``, ``wrong_card``, ``mother_status``), which this module never
changes. It ADDS ``display_*`` fields beside them, which only the student checklists and the
officer's document facts read (falling back to the old fields when absent). It lives outside
`income_engine` on purpose: that package is the verdict engine's source (`model_registry`), and
Phase 1 must leave it byte-identical. Phase 2 (decisions move to the bands) is a later sprint.

The owner's rulings it draws (25 Nov 2026, `docs/decisions.md`):

1. A fault in one document must not infect a correct one (case 177: a ':' read as the STR
   recipient made the correct parent IC show "Wrong card" and a red Name row).
2. A name or number the document itself did not give us (blank, or junk by `name_guard`) shows
   GREY "not read" (``'not_read'``) on that document's row. Never a green tick for a field nobody
   compared; never amber or red on another document because of it. The IC-number chain (#9)
   confirms the link; it no longer paints 'match' on fields it did not compare (L2-1 narrowed for
   DISPLAY only).
3. When the parent IC and an income proof truly disagree, the red shows on the INCOME DOCUMENT
   (the incoming proof), never on the IC card. The card shows "Wrong card" only when its own
   number is far from the chained number, or its own row is RED against its anchor (the birth
   certificate's parent row) on values that read cleanly.
4. Stored bad reads are not changed or re-read; the guard runs here, at comparison time.

The words served are the ones the web already draws ('match', 'mismatch', 'no_ref', the amber
'check_*' words of `match_bands.chip_status`) plus 'not_read'. The BC father row stays outside the
bands (#23) and is not touched; the student's own IC stays strict and is not touched.
"""
from __future__ import annotations

from .income_engine import (_bc_parent_identity, _cluster_proof_identity, _member_ic_doc,
                            _name_bucket, chain_verified_earner)
from .income_engine.buckets import _romanised_near_miss
from .income_engine.match_bands import (AMBER, BLUE, FAR, GREEN, GREY, RED, chip_status, number_level,
                                        score_row)
from .income_engine.relationships import _MEMBER_ORDER
from .name_guard import clean_person_name
from .read_errors import ic_second_opinion_deferred
from .vision import nric_close, nric_match

NOT_READ = 'not_read'


def _card(ic):
    """(clean name, number, deferred) off a parent IC card; ('', '', False) for no card."""
    if ic is None:
        return '', '', False
    return (clean_person_name(getattr(ic, 'vision_name', '')),
            (getattr(ic, 'vision_nric', '') or '').strip(), ic_second_opinion_deferred(ic))


def _with_chain(name, nric, name_st, nric_st, application, member):
    """Rulings 2 and 3 under the IC-number chain (#9): the chain's own anchor, the birth
    certificate's parent identity, is compared with THIS document's own values. A field equal to
    it is a real comparison and shows green; a number one digit off shows amber; a name that is
    far while the number agrees shows amber 'check_name' (an exact number and a far name is BLUE
    in the #78 table, drawn amber). Fields the document did not give stay as they are."""
    if not member or not chain_verified_earner(application, member):
        return name_st, nric_st
    bc_name, bc_nric = _bc_parent_identity(application, member)
    bc_name = clean_person_name(bc_name)
    if nric and nric_st != 'match':
        if nric_match(nric, bc_nric):
            nric_st = 'match'
        elif nric_close(nric, bc_nric):
            nric_st = 'check_near'
    if name and name_st != 'match':
        if bc_name and _name_bucket(name, bc_name) == 'match':
            name_st = 'match'
        elif nric_st == 'match':
            name_st = 'check_name'
    return name_st, nric_st


def _not_read(raw_name, nric, name_st, nric_st):
    """Ruling 2: the document's own blank or junk value is 'not_read', whatever it was compared to."""
    return (NOT_READ if not clean_person_name(raw_name) else name_st,
            NOT_READ if not (nric or '').strip() else nric_st)


def str_display(doc, sc):
    """``display_name_status`` / ``display_nric_status`` for an STR's Recipient and IC No rows:
    the recipient against every household card (as the decision's household match tries them),
    with the junk guard on BOTH sides, not forced by the chain. A card our outage left half-read
    proves no mismatch (TD-390); a name one romanised syllable from a card is not settled by it
    (TD-404). Under the chain, the chain's anchor is compared too (`_with_chain`)."""
    app = doc.application
    name = clean_person_name(sc.get('name'))
    nric = (sc.get('nric') or '').strip()
    tagged = ((getattr(app, 'income_earner', '') or '').strip()
              or (getattr(doc, 'household_member', '') or '').strip())
    name_st = nric_st = 'no_ref'
    for m in dict.fromkeys([x for x in ([tagged] + list(_MEMBER_ORDER)) if x]):
        ic = _member_ic_doc(app, m)
        if ic is None:
            continue
        ic_name, ic_nric, deferred = _card(ic)
        if name and ic_name and name_st != 'match':
            if _name_bucket(name, ic_name) == 'match':
                name_st = 'match'
            elif not deferred and not _romanised_near_miss(name, ic_name):
                name_st = 'mismatch'
        if nric and ic_nric and nric_st != 'match':
            if nric_match(nric, ic_nric):
                nric_st = 'match'
            elif not deferred:
                nric_st = 'mismatch'
    name_st, nric_st = _with_chain(name, nric, name_st, nric_st, app, sc.get('member') or tagged)
    name_st, nric_st = _not_read(sc.get('name'), nric, name_st, nric_st)
    return {'display_name_status': name_st, 'display_nric_status': nric_st}


def income_proof_display(doc, chk):
    """``display_name_status`` / ``display_nric_status`` for a salary slip / EPF: THIS document's
    own values against its member's card (junk guard on both sides), not forced by the chain.
    Every slip in the group is judged on its own values: the chain compared only one of them."""
    app = doc.application
    member = chk.get('member') or ''
    name = clean_person_name(chk.get('name'))
    nric = (chk.get('nric') or '').strip()
    ic_name, ic_nric, deferred = _card(_member_ic_doc(app, member))
    name_st = _name_bucket(name, ic_name)
    nric_st = 'no_ref' if not (nric and ic_nric) else ('match' if nric_match(nric, ic_nric) else 'mismatch')
    if deferred:                                   # TD-390: half a read proves no mismatch
        name_st, nric_st = ('no_ref' if s == 'mismatch' else s for s in (name_st, nric_st))
    name_st, nric_st = _with_chain(name, nric, name_st, nric_st, app, member)
    name_st, nric_st = _not_read(chk.get('name'), nric, name_st, nric_st)
    return {'display_name_status': name_st, 'display_nric_status': nric_st}


def income_ic_display(doc, chk):
    """Ruling 3 on the parent IC card. ``display_proof_name_status`` /
    ``display_proof_nric_status``: green when the card matches the proof, else neutral 'no_ref'
    (a disagreement shows on the PROOF, never here). ``display_wrong_card``: only when the chain
    holds and the card's own number is far from the chained number, or its own row (clean values)
    is RED against the birth certificate's parent row."""
    app = doc.application
    member = chk.get('member') or ''
    card_name = clean_person_name(chk.get('name'))
    card_nric = (chk.get('nric') or '').strip()
    name_st = 'match' if chk.get('proof_name_status') == 'match' else 'no_ref'
    nric_st = 'match' if chk.get('proof_nric_status') == 'match' else 'no_ref'
    if name_st != 'match' and card_name and chk.get('proof_kind'):
        _, p_name, _ = _cluster_proof_identity(app, member)
        p_name = clean_person_name(p_name)
        if p_name and _name_bucket(card_name, p_name) == 'match':
            name_st = 'match'
    wrong = False
    if chk.get('chain_verified') and not chk.get('deferred'):
        bc_name, bc_nric = _bc_parent_identity(app, member)
        row = score_row(card_name, card_nric, (clean_person_name(bc_name),), bc_nric)
        wrong = number_level(card_nric, bc_nric) == FAR or row['band'] == RED
    return {'display_proof_name_status': name_st, 'display_proof_nric_status': nric_st,
            'display_wrong_card': wrong}


_BEST = {GREEN: 0, BLUE: 1, AMBER: 2, GREY: 3, RED: 4}


def bc_display(doc, chk):
    """``display_mother_status`` for a birth certificate's Mother row: the row scored against the
    mother's card with the junk guard on both sides (`match_bands.score_row`), not forced by the
    chain. Under the chain, the row is ALSO scored against the income proof the chain matched
    it with (a real comparison of this row's own values) and the better band shows: a wrong card
    in the mother's slot shows on that card ("Wrong card"), not on this certificate."""
    app = doc.application
    mother_name = clean_person_name(chk.get('mother_name'))
    mother_nric = chk.get('mother_nric') or ''
    ic_name, ic_nric, deferred = _card(_member_ic_doc(app, 'mother'))
    rows = [score_row(mother_name, mother_nric, (ic_name,), ic_nric,
                      waiting=not (ic_name or ic_nric))]
    if chain_verified_earner(app, 'mother'):
        _, p_name, p_nric = _cluster_proof_identity(app, 'mother')
        rows.append(score_row(mother_name, mother_nric, (clean_person_name(p_name),), p_nric))
    status = chip_status(min(rows, key=lambda r: _BEST[r['band']]))
    if deferred and status == 'mismatch':
        status = 'no_ref'                          # TD-390: a half-read card proves no clash
    if not (mother_name or mother_nric.strip()):
        status = NOT_READ                          # ruling 2: the certificate's own row was not read
    return {'display_mother_status': status}
