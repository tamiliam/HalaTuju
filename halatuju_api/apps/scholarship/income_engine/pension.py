"""Pension members, the pension context line, and the STR earner income-document gap.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .gaps import _member_income_documented
from .informal import _NEGATIONS, _member_occupation_label


# ── The retired / unable parent's pension (#117, owner 2026-07-14) ────────────────────────────
# A 'retired' / 'unable' parent sits in family.NON_EARNING, so member_income_status returns
# 'satisfied': we never ask what they draw and never count it. But a pension IS household income.
# So — mirroring #126 exactly — ASK FIRST ("does he draw a pension / benefit, and roughly how
# much?"), hear the answer, and only on an explicit YES ask for the statement (which reuses the
# salary_slip slot; the extraction prompt already accepts a pension/benefit statement). Never demand
# a document from someone who cannot have one. The error otherwise runs toward UNDERstating income —
# the direction a fiscal steward should mind.
_PENSION_TERMS = ('pension', 'pencen', 'benefit', 'bantuan', 'faedah', 'perkeso', 'socso')


def pension_members(application):
    """Parents whose status is retired / unable (``family.BENEFIT_OCC``) and who have NO income
    evidence on file — the ones whose pension is currently invisible to the means test. Parent-
    scoped (father/mother), matching the father/mother pension-proof codes."""
    from ..family import BENEFIT_OCC
    out = []
    for member in ('father', 'mother'):
        occ = (getattr(application, f'{member}_occupation', '') or '').strip()
        # #117 (owner 2026-07-16): the STR-ignoring documented check — a retired father who is the
        # STR recipient still draws an invisible pension, so being the STR earner must NOT suppress
        # the pension ask (the STR settles the verdict, not the salary picture).
        if occ in BENEFIT_OCC and not _member_income_documented(application, member):
            out.append(member)
    return out


def pension_context(application):
    """Params for the ``pension_amount_unknown`` clarify, or ``None`` when there is no gap — the
    ``ctx is not None`` idiom doubles as the gap detector (as ``high_utility_expense_context`` does).
    Mirrors ``informal_income_context``: ``members`` = the retired/unable parents with no income
    evidence, ``jobs`` = their declared status label(s) for display."""
    members = pension_members(application)
    if not members:
        return None
    jobs = [lbl for lbl in (_member_occupation_label(application, m) for m in members) if lbl]
    return {'members': members, 'jobs': '; '.join(jobs)}


def str_earner_income_document_gap(application):
    """The STR-recipient parent's OWN salary is still worth documenting for the household picture
    even though the STR settles the means test (owner 2026-07-16). This covers the FORMAL working
    STR earner (factory / teacher / clerk / …) whose salary slip we never asked for because the STR
    marked them 'evidenced' — the retired/unable case is ``pension_members`` and the informal case is
    ``informal_income_members``, so this partition excludes both. Returns the parent member code
    ('father'|'mother') or None. STR route only; a soft doc request, never a submission blocker."""
    if (getattr(application, 'income_route', '') or '').strip() != 'str':
        return None
    earner = (getattr(application, 'income_earner', '') or '').strip()
    if earner not in ('father', 'mother'):
        return None
    from ..family import NON_EARNING, INFORMAL_OCC
    occ = (getattr(application, f'{earner}_occupation', '') or '').strip()
    if not occ or occ in NON_EARNING or occ in INFORMAL_OCC:
        return None                                  # non-earning / retired-unable / informal → other paths
    if _member_income_documented(application, earner):
        return None                                  # their income is already SHOWN (income_shown)
    return earner


def pension_claim(text):
    """Does this answer say the retired / unable member DOES draw a pension / recurring benefit?
    → 'yes' | 'no' | 'unclear'. A near-copy of ``payslip_claim`` — negation is checked FIRST ("he
    gets no pension" contains 'pension'), the ordering that stops the #130-style dead-end from
    re-forming (never demand a statement from someone who just told us there is none)."""
    t = ' ' + (text or '').lower().strip() + ' '
    if not any(term in t for term in _PENSION_TERMS):
        return 'unclear'
    if any(neg in t for neg in _NEGATIONS):
        return 'no'
    return 'yes'


def pension_claimed(application, member):
    """True when the student answered the pension clarify saying the retired/unable earner DOES draw
    a pension / benefit — read from the RESOLVED item's stored params (classified once, at resolve
    time; never an LLM inside a sync). Household-level: the answer opens the proof request for each
    such member, so ``member`` is accepted for call-site symmetry but the claim is shared. Tolerant
    of a stand-in application with no items relation (the #126 SimpleNamespace lesson)."""
    items = getattr(application, 'resolution_items', None)
    if items is None:
        return False
    for item in items.filter(code='pension_amount_unknown', status='resolved'):
        if (getattr(item, 'params', None) or {}).get('pension_claim') == 'yes':
            return True
    return False
