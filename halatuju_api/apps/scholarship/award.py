"""Standardised assistance amount — the deterministic award-sizing rule.

Owner decision (2026-06-29): the assistance is no longer a free reviewer choice. It is
fixed by the student's pre-U PATHWAY and only a SUPER admin may override it:

    STPM (Form 6, ``chosen_pathway == 'stpm'``)            → RM3,000
    everything else (Matrikulasi / UA Diploma / Poly Diploma
    / Asasi / PISMP / university / unknown)                → RM2,000

Owner decision (2026-06-29b): when the verification verdict carries a CONFIDENT
DISQUALIFIER — the pathway is *not a genuine official public-university offer*
(``offer_not_official``), or per-capita income is *at/above the B40 line*
(``income_above_b40_line``) — the system proposes NO amount (``None``): the slider has
no value and the cockpit shows the reason. This is a default, not a stop — a SUPER may
override to a real amount via the set-award endpoint if the system has erred, and the
rule self-corrects (the amount returns the moment the disqualifier clears). The merely
*uncertain* codes (a missing offer, ``income_unverified_needs_interview``) are NOT
disqualifiers: those keep the normal pathway amount and are settled at interview.

The amount is applied automatically when a reviewer records an APPROVE verdict (see
``views_admin.AdminRecordVerdictView``); a super can adjust it via the (super-only)
set-award endpoint, constrained to ``ALLOWED_AMOUNTS``. This module is the single source
of truth for the rule + the allowed override values, so the cockpit slider and the backend
can't drift.
"""
from decimal import Decimal

# The slider's discrete stops (RM): min RM1,000 → max RM3,000 in RM500 steps. A super
# override must land on one of these.
ALLOWED_AMOUNTS = (
    Decimal('1000'), Decimal('1500'), Decimal('2000'), Decimal('2500'), Decimal('3000'),
)

_STPM_AMOUNT = Decimal('3000')
_DEFAULT_AMOUNT = Decimal('2000')

# Verdict codes that DEFAULT the proposal to "no amount". Confident negatives only —
# a clear, evidence-backed reason this pathway/income is outside the accepted criteria.
# (Genuinely-uncertain "settle at interview" codes are deliberately excluded.)
CONFIDENT_DISQUALIFIERS = ('offer_not_official', 'income_above_b40_line')


def verdict_disqualifier(verdict):
    """The first confident-disqualifier code present in a ``build_verdict`` result
    (a list of fact dicts), or '' if none. Reads only the ``unresolved`` items."""
    for fact in (verdict or []):
        for item in (fact.get('unresolved') or []):
            if item.get('code') in CONFIDENT_DISQUALIFIERS:
                return item['code']
    return ''


def proposed_award_amount(application, verdict=None):
    """The standardised assistance for this application — RM3,000 for STPM/Form 6,
    RM2,000 otherwise (incl. a blank/unknown pathway) — UNLESS the verdict carries a
    confident disqualifier, in which case it returns ``None`` (no amount). Pass the
    already-computed ``verdict`` (a ``build_verdict`` list) to avoid recomputing it;
    omit it and the rule computes the verdict itself."""
    if verdict is None:
        from .verdict_engine import build_verdict
        verdict = build_verdict(application)
    if verdict_disqualifier(verdict):
        return None
    pathway = (getattr(application, 'chosen_pathway', '') or '').strip().lower()
    return _STPM_AMOUNT if pathway == 'stpm' else _DEFAULT_AMOUNT


def is_allowed_amount(value):
    """True if ``value`` (Decimal) is one of the permitted slider stops."""
    try:
        return Decimal(str(value)) in ALLOWED_AMOUNTS
    except (ArithmeticError, TypeError, ValueError):
        return False
