"""Standardised assistance amount — the deterministic award-sizing rule.

Owner decision (2026-06-29): the assistance is no longer a free reviewer choice. It is
fixed by the student's pre-U PATHWAY and only a SUPER admin may override it:

    STPM (Form 6, ``chosen_pathway == 'stpm'``)            → RM3,000
    everything else (Matrikulasi / UA Diploma / Poly Diploma
    / Asasi / PISMP / university / unknown)                → RM2,000

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


def proposed_award_amount(application):
    """The standardised assistance for this application's pathway (always a value —
    RM3,000 for STPM/Form 6, RM2,000 otherwise, incl. a blank/unknown pathway)."""
    pathway = (getattr(application, 'chosen_pathway', '') or '').strip().lower()
    return _STPM_AMOUNT if pathway == 'stpm' else _DEFAULT_AMOUNT


def is_allowed_amount(value):
    """True if ``value`` (Decimal) is one of the permitted slider stops."""
    try:
        return Decimal(str(value)) in ALLOWED_AMOUNTS
    except (ArithmeticError, TypeError, ValueError):
        return False
