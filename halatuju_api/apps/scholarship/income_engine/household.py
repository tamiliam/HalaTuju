"""The household as a whole: the described count, the size shortfall, the income
reconciliation and whether the size is accounted for.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

from .amounts import earner_monthly_income
from .gaps import household_status_gaps
from .identity_checks import _cluster_docs
from .occupation import _member_occupation
from .relationships import effective_working_members


# ── Household-size consistency (P4 — soft reviewer signal) ───────────────────
# Members a 'deceased' / 'not in contact' occupation marks as NOT part of the living household
# (they're family history, not a per-capita head).
_NOT_IN_HOUSEHOLD = frozenset({'deceased', 'no_contact'})


def _described_household_count(application):
    """A FLOOR on household size from what the applicant explicitly described: the student (+1),
    each parent with an in-household occupation, each ``other_family_members`` entry (excluding
    deceased / not-in-contact), plus the two sibling steppers. Not everyone is itemised, so this
    is a floor, never an exact size."""
    n = 1  # the student themselves
    for member in ('father', 'mother'):
        occ = _member_occupation(application, member)
        if occ and occ not in _NOT_IN_HOUSEHOLD:
            n += 1
    for m in (getattr(application, 'other_family_members', None) or []):
        if isinstance(m, dict) and m.get('role') \
                and (m.get('occupation', '') or '').strip() not in _NOT_IN_HOUSEHOLD:
            n += 1
    n += (getattr(application, 'siblings_in_school', None) or 0)
    n += (getattr(application, 'siblings_in_tertiary', None) or 0)
    return n


def household_size_shortfall(application):
    """P4 soft check: when the people EXPLICITLY described OUTNUMBER the stated household size, the
    per-capita denominator is too small → income is overstated and the student looks LESS needy
    than they are. Returns ``{'described', 'size'}`` for the reviewer to confirm, else None.

    Only the HARMFUL (over-count) direction flags — a household LARGER than the itemised roster is
    common and benign (grandparents, relatives not listed one-by-one), so under-count never fires.
    Advisory only; never a gate."""
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not size:
        return None
    described = _described_household_count(application)
    return {'described': described, 'size': int(size)} if described > size else None


# ── Cockpit "verified value" reconciliation (2026-07-15) ──────────────────────
# For the small field-level verified ticks on the officer cockpit. NON-MUTATING: we never
# overwrite the student's declared figure — we compute what the DOCUMENTS say and report whether
# it corroborates the stated value, leaving the reviewer to reconcile a discrepancy. A stated
# income "matches" the documents only when every working member's income was read AND the
# document-derived total is within tolerance (payslips wander month-to-month with OT/allowances,
# so a small band, not an exact equality).
#
# tenancy: rule-1 exemption — advisory display tolerance, not a programme rule.
# Conventions rule 1 sends new tunables to `ScholarshipCohort`. These two stay module-level
# deliberately: they are NEVER a gate. They decide only whether the cockpit paints a small
# verified tick beside the stated income, and the reconciliation that reads them is
# non-mutating — no band, no verdict, no blocker and no amount depends on either number, so a
# second programme wanting a different band changes nothing but a tick. Promote them to
# `ScholarshipCohort` fields (today's values as defaults) the moment one actually asks.
_INCOME_MATCH_TOL_FRAC = 0.10     # ±10% of the stated figure …
_INCOME_MATCH_TOL_MIN = 300.0     # … but at least ±RM300 grace for small incomes.


def _income_earning_members(application):
    """Every household member whose income should be summed for the documented total — the
    salary-route working members PLUS anyone (either route) with a salary slip / EPF tagged to
    them. This is what lets an STR-route household with a working sibling/parent still get a
    document-verified income picture (owner 2026-07-16): the STR is the means-test, but a real
    payslip on file quantifies that member's pay regardless of route."""
    members = list(effective_working_members(application))
    try:
        doc_members = (application.documents
                       .filter(doc_type__in=('salary_slip', 'epf'), superseded_at__isnull=True)
                       .exclude(household_member='')
                       .values_list('household_member', flat=True))
    except (AttributeError, TypeError):
        doc_members = []
    for m in sorted(set(doc_members)):
        if m not in members:
            members.append(m)
    return members


def _member_income_genuine(application, member):
    """False when any of a member's summed income documents (salary slip / EPF) is genuineness
    SUSPECT or a WRONG type — such a read can't CONFIRM a figure, so it must not earn a verified
    tick. Unscored/genuine → True (fail-open, as elsewhere)."""
    from ..genuineness.bands import canonical_status
    for dt in ('salary_slip', 'epf'):
        for d in _cluster_docs(application, member, dt):
            vf = d.vision_fields if isinstance(d.vision_fields, dict) else {}
            st = canonical_status((vf.get('authenticity') or {}).get('status', ''), dt)
            if st == 'suspect' or st.startswith('not_'):
                return False
    return True


def household_income_reconciliation(application):
    """Document-derived household monthly income vs the student's stated ``household_income``.

    Returns ``{documented_total, all_known, genuine, stated, matches}``:
      - ``documented_total`` — Σ ``earner_monthly_income`` over EVERY documented household earner
        (salary route + STR-route/other members with a payslip/EPF — ``_income_earning_members``),
        rounded; None unless we're CONFIDENT (earners exist, all read, all genuine).
      - ``all_known`` — False when any earner's income couldn't be read.
      - ``genuine`` — False when any contributing income doc is genuineness-suspect / wrong-type.
      - ``stated`` — the profile's declared household income.
      - ``matches`` — True ONLY when confident AND ``documented_total`` is within tolerance of
        ``stated``. A cockpit "verified" tick keys off this; a mismatch is flagged to the reviewer
        (the documented figure shown beside the stated one), never auto-applied.
    """
    members = _income_earning_members(application)
    total, all_known, genuine = 0.0, True, True
    for m in members:
        amt, _src = earner_monthly_income(application, m)
        if amt is None:
            all_known = False
        else:
            total += amt
        if not _member_income_genuine(application, m):
            genuine = False
    stated = getattr(getattr(application, 'profile', None), 'household_income', None)
    confident = bool(members) and all_known and genuine
    documented = round(total, 2) if confident else None
    matches = False
    if documented is not None and stated:
        tol = max(_INCOME_MATCH_TOL_MIN, _INCOME_MATCH_TOL_FRAC * float(stated))
        matches = abs(documented - float(stated)) <= tol
    return {'documented_total': documented, 'all_known': all_known, 'genuine': genuine,
            'stated': stated, 'matches': matches}


def household_size_accounted(application):
    """Whether the household is FULLY accounted for — every stated head is itemised AND every
    member's economic status is known. Returns ``{described, stated, accounted, overcount}``:
      - ``described`` — the itemised-roster headcount floor (``_described_household_count``).
      - ``stated`` — the profile's declared household size.
      - ``accounted`` — True only when the itemised roster EXACTLY equals the stated size (nobody
        unexplained) AND there are no income-status gaps (no member of unknown economic status).
        A cockpit "verified" tick keys off this.
      - ``overcount`` — True when the itemised roster OUTNUMBERS the stated size (the harmful
        direction: per-capita denominator too small); flagged, never auto-applied.
    An under-count (household larger than the itemised roster — grandparents, unlisted relatives)
    is benign and simply doesn't tick.
    """
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    described = _described_household_count(application)
    gaps = household_status_gaps(application)
    return {
        'described': described,
        'stated': int(size) if size else None,
        'accounted': bool(size) and described == int(size) and not gaps,
        'overcount': bool(size) and described > int(size),
    }
