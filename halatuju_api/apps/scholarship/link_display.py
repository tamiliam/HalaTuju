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
from .vision import nric_match

NOT_READ = 'not_read'


def _card(ic):
    """(clean name, number, deferred) off a parent IC card; ('', '', False) for no card."""
    if ic is None:
        return '', '', False
    return (clean_person_name(getattr(ic, 'vision_name', '')),
            (getattr(ic, 'vision_nric', '') or '').strip(), ic_second_opinion_deferred(ic))


def _anchor(application, member):
    """The chain's own anchor, the birth certificate's (clean name, number) for this parent, when
    the IC-number chain (#9) holds for ``member``; None otherwise."""
    if not member or not chain_verified_earner(application, member):
        return None
    bc_name, bc_nric = _bc_parent_identity(application, member)
    return clean_person_name(bc_name), (bc_nric or '').strip()


def _off_chain(card_nric, anchor) -> bool:
    """Ruling 3: under the chain, a card whose own number is FAR from the chained number is a wrong
    card. The fault shows on that card ("Wrong card"); it gives no say on another document."""
    return bool(anchor and anchor[1] and card_nric and number_level(card_nric, anchor[1]) == FAR)


def _with_chain(name, nric, name_st, nric_st, anchor):
    """Ruling 2 under the chain: THIS document's own value equal to the anchor is a real comparison
    and shows green. Nothing else is added: a field the anchor cannot speak to (blank or junk on
    either side) keeps what the card comparison gave, and the chain never paints amber."""
    if not anchor:
        return name_st, nric_st
    bc_name, bc_nric = anchor
    if nric and bc_nric and nric_match(nric, bc_nric):
        nric_st = 'match'
    if name and bc_name and _name_bucket(name, bc_name) == 'match':
        name_st = 'match'
    return name_st, nric_st


def _not_read(raw_name, nric, name_st, nric_st, unread=(False, False)):
    """Ruling 2: the document's own blank or junk value is 'not_read', whatever it was compared to.
    ``unread`` = (name, number) of the card(s) it would have been compared with were not read (blank,
    junk or half-read): a value left uncompared for that reason is 'not_read' too, never "add their IC"."""
    name_st = NOT_READ if not clean_person_name(raw_name) or (name_st == 'no_ref' and unread[0]) else name_st
    nric_st = NOT_READ if not (nric or '').strip() or (nric_st == 'no_ref' and unread[1]) else nric_st
    return name_st, nric_st


def str_display(doc, sc):
    """``display_name_status`` / ``display_nric_status`` for an STR's Recipient and IC No rows:
    the recipient against every household card (as the decision's household match tries them),
    with the junk guard on BOTH sides, not forced by the chain. A card our outage left half-read
    proves no mismatch (TD-390); a name one romanised syllable from a card is not settled by it
    (TD-404); a wrong card under the chain gives no say (`_off_chain`). Under the chain, the
    chain's anchor is compared too (`_with_chain`)."""
    app = doc.application
    name = clean_person_name(sc.get('name'))
    nric = (sc.get('nric') or '').strip()
    tagged = ((getattr(app, 'income_earner', '') or '').strip()
              or (getattr(doc, 'household_member', '') or '').strip())
    anchor = _anchor(app, sc.get('member') or tagged)
    name_st = nric_st = 'no_ref'
    unread_name = unread_nric = False
    for m in dict.fromkeys([x for x in ([tagged] + list(_MEMBER_ORDER)) if x]):
        ic = _member_ic_doc(app, m)
        if ic is None:
            continue
        ic_name, ic_nric, deferred = _card(ic)
        if _off_chain(ic_nric, anchor):
            continue
        unread_name = unread_name or deferred or not ic_name
        unread_nric = unread_nric or deferred or not ic_nric
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
    name_st, nric_st = _with_chain(name, nric, name_st, nric_st, anchor)
    name_st, nric_st = _not_read(sc.get('name'), nric, name_st, nric_st, (unread_name, unread_nric))
    return {'display_name_status': name_st, 'display_nric_status': nric_st}


def income_proof_display(doc, chk):
    """``display_name_status`` / ``display_nric_status`` for a salary slip / EPF: THIS document's
    own values against its member's card (junk guard on both sides), not forced by the chain.
    Every slip in the group is judged on its own values: the chain compared only one of them, so a
    second slip that is someone else's shows red here (ruling 3), whatever the decision says."""
    app = doc.application
    member = chk.get('member') or ''
    name = clean_person_name(chk.get('name'))
    nric = (chk.get('nric') or '').strip()
    anchor = _anchor(app, member)
    ic = _member_ic_doc(app, member)
    ic_name, ic_nric, deferred = _card(ic)
    if _off_chain(ic_nric, anchor):
        ic, ic_name, ic_nric, deferred = None, '', '', False
    name_st = _name_bucket(name, ic_name)
    nric_st = 'no_ref' if not (nric and ic_nric) else ('match' if nric_match(nric, ic_nric) else 'mismatch')
    if deferred:                                   # TD-390: half a read proves no mismatch
        name_st, nric_st = ('no_ref' if s == 'mismatch' else s for s in (name_st, nric_st))
    name_st, nric_st = _with_chain(name, nric, name_st, nric_st, anchor)
    unread = (ic is not None and (deferred or not ic_name), ic is not None and (deferred or not ic_nric))
    name_st, nric_st = _not_read(chk.get('name'), nric, name_st, nric_st, unread)
    # Case 1048: the SHOWN word only. A near miss on a handwritten declaration that is still a
    # 'mismatch' after every rule above shows 'close' (amber: a person must look). The decision
    # field `chk['name_status']` stays 'mismatch', so every gate still treats it as one. Review round 2:
    # a no-op until NRIC chip Sprint 3 turns on `declaration_name.SHOW_CLOSE`.
    from .income_engine.declaration_name import soften
    name_st = soften(doc, name_st, name, ic_name)
    return {'display_name_status': name_st, 'display_nric_status': nric_st}


def income_ic_display(doc, chk):
    """Ruling 3 on the parent IC card. ``display_wrong_card``: only when the chain holds and the
    card's own number is far from the chained number, or its own row (clean values) is RED against
    the birth certificate's parent row. ``display_proof_name_status`` /
    ``display_proof_nric_status``: green when the card matches the proof; red ONLY on the field
    that makes it a wrong card (so the student still sees it); else neutral 'no_ref' (a
    disagreement with the proof shows on the PROOF, never here)."""
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
        far_number = number_level(card_nric, bc_nric) == FAR
        wrong = far_number or row['band'] == RED
        if wrong:
            if far_number or row['number'] == FAR:
                nric_st = 'mismatch'
            if row['name'] == FAR:
                name_st = 'mismatch'
    return {'display_proof_name_status': name_st, 'display_proof_nric_status': nric_st,
            'display_wrong_card': wrong}


_BEST = {GREEN: 0, BLUE: 1, AMBER: 2, RED: 3, GREY: 4}


def bc_display(doc, chk):
    """``display_mother_status`` for a birth certificate's Mother row, scored (`match_bands.score_row`)
    against each reference that can speak to it, with the junk guard on both sides, not forced by
    the chain: the mother's card, and under the chain the income proof the chain matched it with.
    A reference whose name is blank or junk, a wrong card under the chain (`_off_chain`), and a
    half-read card that does not agree (TD-390) give no say: never amber, never red. The best row
    shows. The certificate's OWN name blank or junk reads 'not_read' (red only when its number is
    far from every reference)."""
    app = doc.application
    mother_name = clean_person_name(chk.get('mother_name'))
    mother_nric = (chk.get('mother_nric') or '').strip()
    if not (mother_name or mother_nric):
        return {'display_mother_status': NOT_READ}     # ruling 2: the certificate's own row was not read
    anchor = (mother_name, mother_nric) if chain_verified_earner(app, 'mother') else None
    ic_name, ic_nric, deferred = _card(_member_ic_doc(app, 'mother'))
    refs = []
    if ic_name and not _off_chain(ic_nric, anchor):
        refs.append((ic_name, ic_nric, deferred))
    if anchor:
        _, p_name, p_nric = _cluster_proof_identity(app, 'mother')
        if clean_person_name(p_name):
            refs.append((clean_person_name(p_name), p_nric, False))
    rows = [r for r, half in ((score_row(mother_name, mother_nric, (n,), k), h) for n, k, h in refs)
            if not (half and r['band'] != GREEN)]
    if not rows:
        return {'display_mother_status': 'no_ref'}
    best = min(rows, key=lambda r: _BEST[r['band']])
    if not mother_name:
        return {'display_mother_status': 'mismatch' if best['band'] == RED else NOT_READ}
    return {'display_mother_status': chip_status(best)}
