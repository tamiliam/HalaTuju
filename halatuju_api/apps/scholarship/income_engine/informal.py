"""Deceased parents, informal work, and the payslip claim a student makes in prose.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

from .evidence import declared_amount
from .gaps import _member_income_documented
from .occupation import _member_occupation
from .relationships import _MEMBER_ORDER


def deceased_parent_members(application):
    """Roster members marked 'deceased' — the officer's recurring 'when / what happened' texture
    query. One clarify covers all such members."""
    return [m for m in _MEMBER_ORDER if _member_occupation(application, m) == 'deceased']


def deceased_parent_detail_gap(application):
    return bool(deceased_parent_members(application))


def informal_work_detail_gap(application):
    """A member has a DECLARED informal wage (``income_declared``) → ask the own-account-vs-employer
    + average-monthly-wage texture officers ask by hand. One clarify covers all such members.
    (Distinct from ``unemployment_detail_gap`` — that's for the UNEMPLOYED.)"""
    raw = getattr(application, 'income_declared', None)
    if not isinstance(raw, dict):
        return False
    return any(declared_amount(application, m) is not None for m in _MEMBER_ORDER)


# ── Informal / self-employed earners (owner 2026-07-08, the #130 fisherman dead-end) ─────────
# A fisherman / hawker / e-hailing rider etc. rarely has a payslip and does NOT contribute to EPF,
# so demanding a salary slip / EPF from them is a dead-end: the request sits open against the SLA
# clock and the student uploads an irrelevant doc to clear it. Instead we ASK FIRST — a one-line
# clarify ("does he get a payslip or contribute to EPF? if not, roughly what does he earn a month?")
# — and route real proof through the flexible income-support-doc path (declared_income_gaps).
def member_is_informal(application, member):
    """True when *member*'s roster occupation is in the self-employed / informal block
    (``family.INFORMAL_OCC``) — the earners we must NOT chase for a payslip / EPF."""
    from ..family import INFORMAL_OCC
    return _member_occupation(application, member) in INFORMAL_OCC


def informal_income_members(application):
    """Informal earners (father/mother/guardian/brother/sister) with NO income document on file —
    the ones a formal salary-slip / EPF demand would dead-end on. Household-wide (mirrors how
    ``household_status_gaps`` walks parents + other_family_members)."""
    out = []
    for member in _MEMBER_ORDER:
        # Salary picture over the means test (owner 2026-07-16): use the STR-ignoring documented
        # check, so an informal STR-recipient parent (e.g. a 'driver' father the STR is under) still
        # gets the ask-first clarify instead of being masked 'evidenced' by the STR.
        if member_is_informal(application, member) and not _member_income_documented(application, member):
            out.append(member)
    return out


# ── The student says the informal earner DOES have a payslip (#126, owner 2026-07-13) ─────────
# The ask-first rule (2026-07-08) suppresses the payslip/EPF demand for an informal earner — a
# fisherman has no payslip, and demanding one dead-ends him (#130). But the suppression is keyed on
# the OCCUPATION CODE, so it never lifts. #126's father is a 'driver' (informal); the student
# answered the clarify with "he has a payslip, I should upload it?" — and nothing in the code could
# hear him. He asked us a question and got silence, and an unevidenced income figure stood.
#
# So we read the answer ONCE, at the moment it is given (see views.ResolutionItemResolveView), and
# store the claim on the item. The gap engine then reads a stored value — never re-classifying, and
# never calling an LLM inside a sync loop.
#
# Deliberately conservative: only an explicit YES re-opens the document request. "No payslip", or
# anything we can't read, leaves the suppression exactly as it is — so the fisherman is never
# dragged back into the dead end this rule exists to prevent.
_PAYSLIP_TERMS = ('payslip', 'pay slip', 'slip gaji', 'penyata gaji', 'salary slip', 'epf', 'kwsp')
_NEGATIONS = ('no ', 'not ', 'none', "n't", 'never', 'tiada', 'tak ', 'tidak', 'bukan', 'without')


def payslip_claim(text):
    """Does this answer say the earner HAS a payslip / EPF? → 'yes' | 'no' | 'unclear'.

    Pure + deterministic (no LLM): the question we asked names the terms, so an answer that
    engages with it almost always echoes them. Negation is checked FIRST — "he has no payslip"
    contains 'payslip', and reading that as a yes is precisely the failure that would re-trap the
    #130 fisherman.
    """
    t = ' ' + (text or '').lower().strip() + ' '
    if not any(term in t for term in _PAYSLIP_TERMS):
        return 'unclear'
    # Negation ANYWHERE in a short answer is enough to hold back — we would rather ask a human
    # than demand a document from someone who just told us they don't have one.
    if any(neg in t for neg in _NEGATIONS):
        return 'no'
    return 'yes'


def informal_payslip_claimed(application):
    """True when the student has told us, in answer to the ask-first clarify, that an informal
    earner does have a payslip / EPF. Read from the RESOLVED item's stored params — the claim was
    classified once, when it was given.

    Tolerates an application object with no items relation (the engine's pure helpers are exercised
    with lightweight stand-ins, same as ``_docs_or_none``): no items → no claim → the ask-first
    suppression stands, which is the safe default.
    """
    items = getattr(application, 'resolution_items', None)
    if items is None:
        return False
    for item in items.filter(code='informal_income_detail', status='resolved'):
        if (item.params or {}).get('payslip_claim') == 'yes':
            return True
    return False


def informal_income_detail_gap(application):
    """True when an informal earner has no income document AND no declared amount yet → the ASK-FIRST
    clarify. Carved so it does NOT overlap ``informal_work_detail_gap`` (which fires once an amount is
    DECLARED): here we still need the rough monthly figure + whether any payslip/EPF exists at all.
    One clarify covers every such member."""
    return any(declared_amount(application, m) is None for m in informal_income_members(application))


def _member_occupation_label(application, member):
    """The human occupation LABEL for a roster member (the declared job, e.g. 'Driver (taxi / bus /
    lorry)'), honouring the free-text 'other' when the code is 'other'. '' when unknown."""
    from ..family import occupation_label
    if member == 'father':
        return occupation_label(_member_occupation(application, member),
                                getattr(application, 'father_occupation_other', '') or '')
    if member == 'mother':
        return occupation_label(_member_occupation(application, member),
                                getattr(application, 'mother_occupation_other', '') or '')
    for m in (getattr(application, 'other_family_members', None) or []):
        if isinstance(m, dict) and m.get('role') == member:
            return occupation_label((m.get('occupation', '') or '').strip(),
                                    (m.get('occupation_other', '') or '').strip())
    return ''


def informal_income_context(application):
    """Params for the ``informal_income_detail`` clarify so its copy NAMES the members the student
    ALREADY declared (owner 2026-07-08 — 'the information is already in My Family'): ``members`` is
    the list of informal-earner member codes (the FE localises them to relation labels), ``jobs`` is
    their declared occupation label(s) joined for display. Only the members whose amount is still
    unknown (the ones the gap is actually about). Empty ``members`` when the gap isn't live."""
    members = [m for m in informal_income_members(application) if declared_amount(application, m) is None]
    jobs = [lbl for lbl in (_member_occupation_label(application, m) for m in members) if lbl]
    return {'members': members, 'jobs': '; '.join(jobs)}
