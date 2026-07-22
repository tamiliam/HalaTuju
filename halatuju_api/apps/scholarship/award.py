"""Standardised bursary amount — the deterministic award-sizing rule.

Owner decision (2026-06-29): the bursary is not a free reviewer choice. It is FIXED by the
student's pre-U PATHWAY:

    STPM (Form 6, ``chosen_pathway == 'stpm'``)            → RM3,000
      …but a CONTINUING STPM student (already started a year ago — their offer's
      reporting date is in an intake YEAR before the cohort's) has only one year left
      → RM1,000.
    everything else (Matrikulasi / UA Diploma / Poly Diploma
    / Asasi / PISMP / university / unknown)                → RM2,000

Owner decision (2026-07-04, supersedes 2026-06-29b): the bursary is now PURELY a function of
pathway TYPE — the same figure ("Standard bursary") is shown and committed for every student,
including one the verdict flags for likely decline. A confident disqualifier
(``offer_not_official`` / ``income_above_b40_line``) NO LONGER zeroes the amount (the old
"no amount" state is gone, along with the super override slider). The disqualifier still
surfaces as a red verdict fact so the officer weighs it in the Recommend/Decline decision.

The amount is applied automatically when a reviewer records an APPROVE verdict (see
``views_admin.AdminRecordVerdictView``). ``verdict_disqualifier`` / ``CONFIDENT_DISQUALIFIERS``
remain for the ``award_disqualifier`` cockpit flag; ``ALLOWED_AMOUNTS`` / ``is_allowed_amount``
remain for the still-present (now UI-less) super set-award endpoint. This module is the single
source of truth for the rule so the cockpit and the backend can't drift.
"""
from decimal import Decimal

# The slider's discrete stops (RM): min RM1,000 → max RM3,000 in RM500 steps. A super
# override must land on one of these.
ALLOWED_AMOUNTS = (
    Decimal('1000'), Decimal('1500'), Decimal('2000'), Decimal('2500'), Decimal('3000'),
)

_STPM_AMOUNT = Decimal('3000')
_STPM_CONTINUING_AMOUNT = Decimal('1000')   # started a year ago → one year of funding left
_DEFAULT_AMOUNT = Decimal('2000')


def _stpm_continuing(application):
    """True iff an STPM student's course started in a YEAR before this cohort's — they have
    already completed a year, so one year of support remains.

    Delegates to ``pathway_engine.started_before_cohort``, the single source of truth shared with
    the semester-result request. It reads the offer's INTAKE year first and the stored
    ``reporting_date`` second (owner 2026-07-23).

    Previously this read ``application.reporting_date`` alone, which was silently wrong twice
    over: the column was NULL for ~45% of applications whose pathway needed confirming (the sync
    bailed out on an unrelated guard), and a Form 6 letter often carries an intake RANGE
    ("6 / 2025 – 12 / 2026") with no reporting date at all — so a continuing student read as a
    fresh entrant and was committed RM3,000 instead of RM1,000. See
    docs/retrospective-2026-07-23-reporting-date.md.
    """
    from .pathway_engine import started_before_cohort
    return started_before_cohort(application)


def course_start_unknown(application):
    """True when the course-start year cannot be established at all — neither an intake year on
    the offer nor a stored reporting date. The bursary CANNOT be sized honestly here: the rule
    would silently fall through to the fresh-entrant (larger) amount. QC refuses to accept such a
    case (owner 2026-07-23: an absolute stop, no override — the officer records the date instead).
    Only meaningful for STPM, the one pathway whose amount depends on the start year."""
    from .pathway_engine import course_start_year
    pathway = (getattr(application, 'chosen_pathway', '') or '').strip().lower()
    return pathway == 'stpm' and course_start_year(application) is None

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
    """The standardised bursary for this application, fixed by the pre-U PATHWAY:
    RM3,000 for STPM/Form 6 (RM1,000 for a CONTINUING STPM student with one year left),
    RM2,000 otherwise (incl. a blank/unknown pathway).

    Owner decision 2026-07-04 (supersedes 2026-06-29b): the bursary is now PURELY a
    function of pathway type — the same figure is shown and committed for every student,
    including one the verdict flags for likely decline. A confident disqualifier
    (``offer_not_official`` / ``income_above_b40_line``) NO LONGER zeroes the amount; it
    still surfaces as a red verdict fact for the officer to weigh in Recommend/Decline.
    ``verdict`` is accepted for backward compatibility and ignored."""
    pathway = (getattr(application, 'chosen_pathway', '') or '').strip().lower()
    if pathway == 'stpm':
        return _STPM_CONTINUING_AMOUNT if _stpm_continuing(application) else _STPM_AMOUNT
    return _DEFAULT_AMOUNT


def is_allowed_amount(value):
    """True if ``value`` (Decimal) is one of the permitted slider stops."""
    try:
        return Decimal(str(value)) in ALLOWED_AMOUNTS
    except (ArithmeticError, TypeError, ValueError):
        return False
