"""Per-member and per-parent income status, and the gaps each one raises.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

from .identity_checks import chain_verified_earner
from .occupation import _member_occupation


# ── Full-household-income completeness (reviewer-query automation S1) ─────────
# The sponsor counts the FULL household income, but apply only collects the ONE declared
# earner's documents — so reviewers repeatedly ask, by hand, for the OTHER parent's payslip
# (when they work) or their status (when their slot is blank). This is deterministic: every
# parent must be EITHER marked non-earning (status known) OR have income evidence on file.

def _member_income_documented(application, member):
    """True when this member's income has been SHOWN — the per-earner answer (``income_shown``:
    a usable payslip, a readable EPF, or a declared amount backed by a letter that read) — or the
    IC-number chain confirms them.

    ⚠ IT READS, IT NO LONGER COUNTS (TD-262 chunks 2+3, findings F1 / F4 / F5). It used to ask
    ``_cluster_docs(...).exists()`` — document PRESENCE — while the submission gate asked whether
    the document could be READ, so the two answered differently about the same household and the
    chase list went quiet on exactly the families the gate was holding shut: a BLANK EPF and a
    ``not_salary`` photo each read 'satisfied' (F4 / F5), and income proved the owner's third way
    (a declared amount + a letter that read) read 'need_proof' and was chased for a payslip the
    family cannot produce (F1, application 144 / Janani). Both directions are now the gate's own
    answer.

    ⚠ IT STILL DOES NOT COUNT AN STR, AND THAT IS THE OWNER'S RULING, NOT AN OVERSIGHT. An STR
    (Sumbangan Tunai Rahmah) proves the HOUSEHOLD's B40 / welfare status; it neither quantifies
    nor even mentions this member's own pay or pension. So for building the household's SALARY
    PICTURE (owner 2026-07-16 — "the STR route shouldn't prevent the system from getting a
    complete salary picture of the household") an STR-recipient parent is still 'undocumented'
    and IS inquired about. It falls out for free here: ``income_shown`` has no STR arm. This
    governs only the soft completeness ASKS (pension / informal / formal-slip); it never touches
    the income verdict or the submission gate, where the STR stays dispositive."""
    from ..income_shown import income_shown
    if income_shown(application, member).shown:
        return True
    if member in ('mother', 'father') and chain_verified_earner(application, member):
        return True
    return False


def _parent_has_income_evidence(application, member):
    """True when income evidence covers this parent for the MEANS TEST: their income is SHOWN
    (``_member_income_documented``) OR — on the STR route — they are the single STR earner with an
    STR doc on file. Used by ``parent_income_status`` / ``member_income_status`` (whether a member's
    economic status is 'known', which the household-size tick keys off) and the STR-route reads.

    For the SALARY-PICTURE completeness asks (pension / informal / formal-slip) use
    ``_member_income_documented`` instead — an STR must not silence those (owner 2026-07-16)."""
    if _member_income_documented(application, member):
        return True
    route = (getattr(application, 'income_route', '') or '').strip()
    if (route == 'str'
            and (getattr(application, 'income_earner', '') or '').strip() == member
            and application.documents.filter(doc_type='str', superseded_at__isnull=True).exists()):
        return True
    return False


def parent_income_status(application, member):
    """One parent's income-completeness verdict (member = 'father' | 'mother'):
      'satisfied'  — non-earning status is recorded (homemaker/deceased/…), OR income
                     evidence is on file;
      'need_proof' — an EARNING occupation is recorded but NO income document covers them
                     (ask for that parent's salary slip / EPF);
      'need_status'— the parent's slot is blank (no occupation), so we don't know whether
                     they earn (ask their work/status — the "why one earner" question).
    Tolerant of a test double missing the roster columns."""
    from ..family import NON_EARNING
    occ = (getattr(application, f'{member}_occupation', '') or '').strip()
    if occ in NON_EARNING:
        return 'satisfied'                       # status known, non-earning → answered
    if _parent_has_income_evidence(application, member):
        return 'satisfied'                       # documented income on file
    if occ:
        return 'need_proof'                      # earning occupation, no income doc
    return 'need_status'                         # blank slot → ask their work/status


def parent_income_gaps(application):
    """The household-income completeness gaps across BOTH parents, as
    ``[{'member': 'father'|'mother', 'need': 'proof'|'status'}, …]`` (empty when both are
    satisfied). Drives the auto-raised reviewer queries that today are typed by hand.
    (Superseded by ``household_status_gaps``; kept for any parent-only callers.)"""
    gaps = []
    for member in ('father', 'mother'):
        status = parent_income_status(application, member)
        if status == 'need_proof':
            gaps.append({'member': member, 'need': 'proof'})
        elif status == 'need_status':
            gaps.append({'member': member, 'need': 'status'})
    return gaps


def member_income_status(application, member):
    """Income-completeness verdict for ANY roster member (father/mother/guardian/brother/sister),
    from the roster occupation + income evidence. Same states as ``parent_income_status``:
    'satisfied' | 'need_proof' | 'need_status'. Reads the occupation via ``_member_occupation``
    (father/mother columns; guardian/brother/sister from ``other_family_members``). Only a parent
    slot can be blank → 'need_status'; an other_family_members entry always carries a chosen
    occupation, so it can only be 'satisfied' or 'need_proof'."""
    from ..family import NON_EARNING
    occ = _member_occupation(application, member)
    if occ in NON_EARNING:
        return 'satisfied'
    if _parent_has_income_evidence(application, member):
        return 'satisfied'
    if occ:
        return 'need_proof'
    return 'need_status'


def household_status_gaps(application):
    """P2 — income-completeness gaps across the WHOLE household, not just the parents: father,
    mother, AND each ``other_family_members`` earner (guardian/brother/sister). Generalises
    ``parent_income_gaps`` so a working guardian/sibling with no income document is chased for
    proof too (the sponsor counts the full household income). ``[{'member','need'}]``, empty when
    all satisfied. Other-members always carry an occupation → they only ever surface 'proof'."""
    gaps = []
    for member in ('father', 'mother'):
        st = member_income_status(application, member)
        if st == 'need_proof':
            gaps.append({'member': member, 'need': 'proof'})
        elif st == 'need_status':
            gaps.append({'member': member, 'need': 'status'})
    seen = set()
    for m in (getattr(application, 'other_family_members', None) or []):
        if not isinstance(m, dict):
            continue
        role = m.get('role', '')
        if role in ('guardian', 'brother', 'sister') and role not in seen:
            seen.add(role)
            if member_income_status(application, role) == 'need_proof':
                gaps.append({'member': role, 'need': 'proof'})
    return gaps
