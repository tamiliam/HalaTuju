"""The STR route's half of the income verdict (``verdict_engine._verdict_income``).

⚠ WHY THIS IS A MODULE (audit sprint A3.4, 2026-11-10). ``_verdict_income`` was a 210-line
straight run on the long-function ledger, in a file on the oversize ledger. Its head — the bills,
STR PRECEDENCE, the salary route, the undeclared wizard and the absent-STR fall-through — stays in
``verdict_engine``; everything after it, the declared STR route, lives here as four named steps:
the earner's IC, the relationship, the STR document's reading, and placing the verdict.

⚠ THE SPLIT WAS A PURE MOVE. Every line below is the line that was in ``_verdict_income``, in the
same order, with the shared ``evidence`` / ``gap`` / ``review`` lists passed explicitly instead of
closed over. No rule, threshold, code or order changed; the A3.4 golden cases
(`tests/test_a34_golden_verdicts.py`) and the characterisation suites passed unedited across it.
The ONE consolidation is the STR currency tuples, which now name the shared income_engine
constants instead of re-typing their members (TD-262; the members are pinned by
``test_income_str_consistency.test_a34_str_state_tuples``).

Every collaborator that a test patches at its source (``income_engine.*``,
``verdict_income_salary.*``) is still imported INSIDE the function that calls it, exactly as it
was, so each patch reaches the moved code. ``verdict_engine`` imports this module lazily, so the
edge is one-way at import time (the ``verdict_income_salary`` pattern).
"""
from __future__ import annotations

from . import verdict_engine as _ve
from .read_errors import ic_second_opinion_deferred
from .verdict_engine import _fact, _income_open_item, _item, _usable_relationship_fields


def str_route_income_fact(application, earner, str_doc, student_name, present, evidence, utility):
    """A declared STR-route household that STR PRECEDENCE did not settle: check the earner's IC,
    prove the earner is the student's family, read the STR document, and place the verdict.
    ``evidence`` is the caller's list (the bills' soft context), appended to in place."""
    gap, review = [], []
    earner_ic_name, ic_deferred = _earner_ic(application, earner, evidence, gap, review)
    rel = _earner_relationship(application, earner, student_name, earner_ic_name, ic_deferred,
                               present, evidence, gap, review)
    reading = _str_reading(str_doc, earner, evidence, gap, review)
    return _place_income_verdict(application, earner, str_doc, student_name, present, utility,
                                 rel, reading, evidence, gap, review)


def _earner_ic(application, earner, evidence, gap, review):
    """── Earner IC (the income docs are issued in their name) ──"""
    # `members=[earner]` keeps the IC/relationship reason-code copy uniform with the
    # salary route (which lists several) — both render "… for {members}".
    # Code-health S4 #17: select the EARNER'S IC (member-tagged, with the earner-only
    # legacy-blank fallback) — the member-agnostic latest parent_ic could pick another
    # member's card after a route switch with several ICs on file, making this verdict
    # contradict the student checklist (which uses _member_ic_doc) on identical data.
    from .income_engine import _member_ic_doc
    ic_doc = _member_ic_doc(application, earner)
    earner_ic_name = (getattr(ic_doc, 'vision_name', '') or '').strip() if ic_doc else ''
    ic_deferred = ic_doc is not None and ic_second_opinion_deferred(ic_doc)   # TD-390
    if ic_doc is None:
        gap.append(_item('earner_ic_missing', members=[earner]))
    elif not earner_ic_name and ic_deferred:
        review.append(_item('ic_service_down', members=[earner]))
    elif not earner_ic_name:
        review.append(_item('earner_ic_unreadable', members=[earner]))
    else:
        evidence.append(_item('earner_ic_present', name=earner_ic_name))
    return earner_ic_name, ic_deferred


def _earner_relationship(application, earner, student_name, earner_ic_name, ic_deferred, present,
                         evidence, gap, review):
    """── Relationship: prove the earner is the student's family ── Returns ``rel``."""
    from .income_engine import (father_link, mother_relationship,
                                guardian_link, chain_verified_earner)
    # A WRONG-TYPE relationship doc (#27: a non-BC in the birth-certificate slot) is UNUSABLE —
    # its fields prove nothing, and the student gets a specific re-upload ticket (gap, like a
    # missing doc) instead of the officer-only generic genuineness caveat.
    rel = None
    if earner == 'father':
        # Patronymic, with a BC fallback for a mononym student (#55) when a BC is uploaded.
        _, bcf, _ = _usable_relationship_fields(application, 'birth_certificate')
        rel = father_link(student_name, earner_ic_name,
                          bcf.get('bc_child_name', ''), bcf.get('bc_father_name', ''))
    elif earner == 'mother':
        if 'birth_certificate' not in present:
            gap.append(_item('birth_cert_missing'))
        else:
            _, bcf, bc_unusable = _usable_relationship_fields(application, 'birth_certificate')
            if bc_unusable == 'unreadable':
                gap.append(_item('birth_cert_unreadable'))
            elif bc_unusable:
                gap.append(_item('birth_cert_not_genuine'))
            else:
                rel = mother_relationship(bcf.get('bc_child_name', ''), bcf.get('bc_mother_name', ''),
                                          student_name, earner_ic_name)
    elif earner == 'guardian':
        if 'guardianship_letter' not in present:
            gap.append(_item('guardianship_letter_missing'))
        else:
            g, _, g_unusable = _usable_relationship_fields(application, 'guardianship_letter')
            if g_unusable == 'unreadable':
                gap.append(_item('guardianship_letter_unreadable'))
            elif g_unusable:
                gap.append(_item('guardianship_letter_not_genuine'))
            else:
                rel = guardian_link(g, earner_ic_name, student_name)   # TD-089 + review F1
    # IC-number chain: the BC's parent number matching the income proof's number confirms a
    # mother/father earner even when the IC uploaded in their slot is the wrong card (#9).
    if rel != 'match' and earner in ('mother', 'father') and chain_verified_earner(application, earner):
        rel = 'match'
    rel = 'pending' if (rel == 'mismatch' and ic_deferred) else rel   # TD-390: half a read, no clash
    if rel == 'match':
        evidence.append(_item('relationship_confirmed'))
    elif rel == 'mismatch':
        if earner == 'father':
            review.append(_item('father_patronymic_mismatch', members=[earner]))
        else:
            review.append(_item('birth_cert_mismatch'))
    # 'unknown' (no patronymic — e.g. a Chinese name) / 'pending' → no claim; officer eyeballs.
    return rel


def _str_reading(str_doc, earner, evidence, gap, review):
    """── Income evidence — the STR document (recipient = the earner, and CURRENT) ──
    Returns ``(str_verified, str_failed, str_unsure, str_mismatch)``."""
    # The STR currency state (docs/scholarship/str-proof-spec.md) carries its own decisive copy via
    # the `status` param: wrong_type (not an STR at all) / rejected (Ditolak) / stale (prior-year) /
    # unreadable (cropped) / unconfirmed (approved, no date → confirm currency). Anything that isn't
    # a CURRENT approved STR keeps the income fact off green — a human looks (and, post Sprint-2, the
    # salary route is assessed when the STR is wrong_type/rejected).
    from .income_engine import STR_COACH_STATES, STR_NOT_THIS_YEAR_STATES, student_str_check
    sc = student_str_check(str_doc) if str_doc is not None else None
    str_verified = False
    # A wrong_type (not an STR at all) or rejected (Ditolak) STR is definitively NOT a current STR;
    # the family may still be B40 on their salary/benefit docs, so we fall through to the salary
    # route below rather than freezing on the failed STR (str-proof-spec.md §6).
    str_failed = bool(sc and sc['current_status'] in ('wrong_type', 'rejected'))
    # STR-proof band matrix (str-proof-spec.md): approval Status × cycle Current →
    #   Lulus + dated-current → Certain (verified) ; Lulus + no date → Probable (review, needs a green)
    #   Lulus + prior-year (stale) OR approval-unread (unreadable) → Unsure (recommend → amber)
    #   Ditolak / not-an-STR → Fail, with the salary route as the net beneath it (str_failed).
    # 'stale'/'unreadable' → Unsure (NOT the blue 'review'): a review tile would read BLUE off the
    # verified earner-IC/relationship greens, overstating a doc whose cycle is old or whose approval
    # never read. Same reasoning as the salary unsure/over bands below.
    # 'unknown' (not read yet / deferred by our outage) bands with them, unticketed (2026-10-24).
    # TD-262 (A3.4): the year states are TD-403's shared tuple — ('stale', 'future') — not a copy.
    str_unsure = bool(sc and sc['current_status'] in STR_NOT_THIS_YEAR_STATES + ('unreadable', 'unknown'))
    # V5 (#10): a POSITIVE recipient mismatch (the STR is in someone else's name) bands Unsure
    # (amber) per str-proof-spec.md §8 — never a blue 'review' read off the earner-IC/relationship
    # greens, which would overstate an STR that provably belongs to a different person.
    str_mismatch = False
    if str_doc is None:
        gap.append(_item('income_proof_missing'))
    # TD-262 (A3.4): every non-green state the student coach names (`STR_COACH_STATES`) — the same
    # six members this line used to re-type: stale, future, rejected, unconfirmed, wrong_type,
    # unreadable.
    elif sc and sc['current_status'] in STR_COACH_STATES:
        review.append(_item('str_not_current', status=sc['current_status']))
    elif sc and 'mismatch' in (sc['name_status'], sc['nric_status']):
        str_mismatch = True
        review.append(_item('str_recipient_mismatch', members=[earner]))
    elif sc and (sc['name_status'] == 'match' or sc['nric_status'] == 'match'):
        str_verified = True
        evidence.append(_item('str_verified'))
    else:
        # Present but the recipient couldn't be confirmed (earner IC missing/unreadable,
        # or the STR didn't read) — a human looks.
        review.append(_item('str_present_unverified'))
    return str_verified, str_failed, str_unsure, str_mismatch


def _place_income_verdict(application, earner, str_doc, student_name, present, utility, rel,
                          reading, evidence, gap, review):
    """── Place the verdict ──"""
    str_verified, str_failed, str_unsure, str_mismatch = reading
    # ⚠ TD-262 item 1b (R4, owner 2026-09-19): an INCOMPLETE STR cluster — a missing earner IC or
    # birth certificate — used to RETURN here, ahead of BOTH fall-throughs below, so the payslips
    # on file were never looked at. It now offers the salary reading too and keeps whichever is
    # stronger; see `_stronger_income_fact`, which can only RAISE and carries these asks onward.
    # ⚠ AND ONLY WHERE AN STR ACTUALLY EXISTS. With NO STR letter at all, §6 rule 2 above has
    # ALREADY decided this household — on `salary_income_satisfied`, a deliberately STRICTER gate
    # that holds §8's red row for a household with nothing to fall through to. Offering a second,
    # looser reading here would quietly overrule a gate somebody chose on purpose (an unlinked
    # adult's payslip would lift the card off the floor `test_unrelated_earner_ic_...` pins).
    if gap:
        red = _fact('income', 'gap', evidence, gap + review)
        return (_ve._stronger_income_fact(red, application, student_name, present, utility)
                if str_doc is not None else red)
    if str_failed:
        # §6 evidence-driven fall-through, in the salary module for the usual reason (this file is
        # on the oversize ledger): a rejected / wrong-type STR is no STR, so band the household on
        # the salary/benefit documents it did supply. Same one-way edge as the two calls above.
        from .verdict_income_salary import _failed_str_headroom_fact
        return _failed_str_headroom_fact(application, earner, evidence, review)
    # Two states, one answer (they are mutually exclusive — a mismatch is only read off a CURRENT
    # STR). `str_unsure`: Lulus-but-stale or approval-unread → Unsure (amber), not a blue review
    # off incidental greens. `str_mismatch`: an approved STR provably in someone ELSE'S name
    # proves nothing about this household (spec §8), so a human owns the call.
    # ⚠ TD-262 item 1 (R4): each of these used to RETURN here, so the payslips on file were never
    # looked at. They now offer the salary reading too and keep whichever is stronger — see
    # `_stronger_income_fact`, which can only ever RAISE a household.
    if str_unsure or str_mismatch:
        return _ve._stronger_income_fact(_fact('income', 'recommend', evidence, review),
                                         application, student_name, present, utility)
    if review:
        return _fact('income', 'review', evidence, review)
    # Income GREEN only when the whole cluster adds up: a CURRENT STR whose recipient is
    # the earner + the earner IC present + the relationship CONFIRMED (mother→BC,
    # father→patronymic, guardian→letter). An unconfirmed relationship → a human places it.
    if str_verified and rel == 'match':
        return _fact('income', 'verified', evidence, [])
    return _fact('income', 'recommend', evidence, [_income_open_item(application)])
