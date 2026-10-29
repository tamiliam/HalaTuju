"""The payment schedule an application follows when NO contract template governs it.

Until 2026-10-29 that case paid a flat RM200 from a per-pathway start month with no gap months
and no end (`MONTHLY_RATE` + `PATHWAY_PAYMENT_START_MONTH`); only a template could skip a month.
No template was ever activated, so every live student was paid that way. The owner asked for the
default to mirror BrightPath's contract 10 ("2026 July 28 BPB") instead, so the default is now a
schedule of its own, read through the SAME `PaymentScheduleRow` shape and the same row-choosing
rule (`contracts.pick_schedule_row`) a template uses — so a template and the default can only
differ in their numbers, never in how those numbers are applied.

tenancy: rule-1 exemption — template-superseded fallback. The org-owned tunable is the template's
own schedule; this is only what a gift WITHOUT one pays. It mirrors the seed fixture's schedule
block, and `test_default_schedule.py` fails if the two drift apart.

`paid_offsets` are 0-based months from `start_month`: poly/university skip offset 3 (November),
STPM skips offsets 5 and 11 (December, June).
"""
from decimal import Decimal

from .models import PaymentScheduleRow

_RM200 = Decimal('200.00')
_TEN = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
_DIPLOMA = [0, 1, 2, 4, 5, 6, 7, 8, 9, 10]          # Aug–Jun, no November

# (pathway, variant, start_month, paid_offsets) — every row is RM200 a month.
DEFAULT_SCHEDULE = (
    ('stpm', '', 7, [0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16]),
    ('stpm', 'continuing', 7, [0, 1, 2, 3, 4]),
    ('matric', '', 7, _TEN),
    ('asasi', '', 7, _TEN),
    ('poly', '', 8, _DIPLOMA),
    ('university', '', 8, _DIPLOMA),
    ('pismp', '', 9, _TEN),
    ('default', '', 7, _TEN),
)


def default_rows():
    """Fresh, UNSAVED rows each call — a caller can never mutate a shared one."""
    return [PaymentScheduleRow(pathway=p, variant=v, monthly_amount=_RM200,
                               start_month=start, paid_offsets=list(offsets))
            for p, v, start, offsets in DEFAULT_SCHEDULE]


def row_for(application):
    """The default row for this application (always one: 'default' catches any pathway)."""
    from . import contracts
    return contracts.pick_schedule_row(default_rows(), application)
