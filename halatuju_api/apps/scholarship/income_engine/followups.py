"""The last follow-up gaps: a roster undercount, other scholarships, and a high utility bill.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .evidence import has_valid_str
from .household import _described_household_count
from .utilities import utility_monthly_total, utility_reasonable


_ROSTER_UNDERCOUNT_MARGIN = 1   # owner (2026-07-14): a gap of ≥1 — the household count is the
                                # per-capita denominator, so one unaccounted person changes the means test


def household_roster_undercount(application):
    """The MISSING direction of 2C: the stated household size is LARGER than the people explicitly
    described → ask who else is in the household (the officers' '6 members, 5 listed' query).
    Opposite of ``household_size_shortfall`` (the over-count). A gap of ≥1: the earlier "an
    under-count of one is common/benign" justification was explicitly overruled by the owner
    (2026-07-14) — the household count is the per-capita denominator, so one unaccounted person
    changes the means test (#117 described 5 against a stated 6, gap 1, and nothing was asked).
    Returns ``{'described','size'}`` or None. Advisory only."""
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not size:
        return None
    described = _described_household_count(application)
    return ({'described': described, 'size': int(size)}
            if int(size) - described >= _ROSTER_UNDERCOUNT_MARGIN else None)


def other_scholarships_followup_gap(application):
    """The student listed other scholarships at apply → follow up on their status (the
    not-double-funded picture). Fires when ``other_scholarships`` is non-empty."""
    raw = getattr(application, 'other_scholarships', None)
    if isinstance(raw, (list, tuple)):
        return len(raw) > 0
    if isinstance(raw, str):
        return bool(raw.strip())
    return bool(raw)


def high_utility_expense_gap(application):
    """Owner decision 2 (V4): promote ``utility_reasonable``'s 'high' officer signal to a student
    clarify — a high per-capita utility spend, ask them to explain it (a possible undeclared income,
    or a legitimate reason). Fires only when BOTH bills are on file AND per-capita is above the high
    floor (so it can't fire on a partial/unknown read)."""
    return utility_reasonable(application).get('status') == 'high'


def high_utility_expense_context(application):
    """Params for the high-usage clarify (owner 2026-07-08 — state the amount, ask point-blank):
    the combined monthly bill total (RM), the declared household income (RM), and whether the
    household holds a VALID STR (so the query references STR status rather than an income figure).
    Returns None when there is no high signal (the caller then raises nothing)."""
    if utility_reasonable(application).get('status') != 'high':
        return None
    amount = utility_monthly_total(application)
    income = getattr(getattr(application, 'profile', None), 'household_income', None)
    return {
        'amount': int(round(amount)) if amount is not None else None,
        'income': int(round(income)) if income else None,
        'on_str': has_valid_str(application),
    }
