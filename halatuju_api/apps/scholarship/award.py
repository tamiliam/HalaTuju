"""Standardised bursary amount — the deterministic award-sizing rule.

Owner decision (2026-06-29): the bursary is not a free reviewer choice. It is FIXED by the
student's pre-U PATHWAY:

    STPM (Form 6, ``chosen_pathway == 'stpm'``)            → RM3,000
      …but a CONTINUING STPM student (already started a year ago — their offer's
      reporting date is in an intake YEAR before the cohort's) has only one year left
      → RM1,000; and one whose start year is UNKNOWN → no amount (None, TD-465).
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

Owner decision (2026-11-07, decision 7 of the degree funding-estimate fix): the bursary is sized by
the FUNDED PERIOD. STPM gets RM3,000 only because Form 6 is an 18-month programme; every other
pathway is funded for 12 months at RM2,000 (and a continuing STPM student's RM1,000 is the remaining
stretch). A DEGREE-BOUND student (``results_route.degree_bound``) is therefore on the 12-month
RM2,000 basis whatever the stored pathway code says: never the STPM amount, never the STPM
start-year stop. Live case #251: a stale ``chosen_pathway='stpm'`` over a degree course.
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
    docs/retrospectives/retrospective-2026-07-23-reporting-date.md.
    """
    from .pathway_engine import started_before_cohort
    return started_before_cohort(application)


def _sized_as_stpm(application):
    """True for a Form 6 student: ``chosen_pathway == 'stpm'`` AND not degree-bound (owner
    2026-11-07, decision 7: a degree is funded for 12 months at RM2,000 whatever the stored code
    says, because STPM's RM3,000 exists only for Form 6's 18 months)."""
    pathway = (getattr(application, 'chosen_pathway', '') or '').strip().lower()
    if pathway != 'stpm':
        return False
    from .results_route import degree_bound
    return not degree_bound(application)


def course_start_unknown(application):
    """True when the course-start year cannot be established at all — neither an intake year on
    the offer nor a stored reporting date. The bursary CANNOT be sized honestly here: the rule
    would silently fall through to the fresh-entrant (larger) amount. QC refuses to accept such a
    case (owner 2026-07-23: an absolute stop, no override — the officer records the date instead).
    Only meaningful for STPM, the one pathway whose amount depends on the start year; a
    degree-bound student under a stale 'stpm' code never trips it (owner 2026-11-07, decision 7:
    a degree is on the 12-month RM2,000 basis, ``_sized_as_stpm``)."""
    from .pathway_engine import course_start_year
    return _sized_as_stpm(application) and course_start_year(application) is None

# Verdict codes that DEFAULT the proposal to "no amount". Confident negatives only —
# a clear, evidence-backed reason this pathway/income is outside the accepted criteria.
# (Genuinely-uncertain "settle at interview" codes are deliberately excluded.)
# TD-617 (owner 2026-11-14): `pathway_funded_or_abroad` (the American Degree Program under MARA is
# fully funded; overseas study is not supported) is one too. The flag only; the amount is unchanged.
CONFIDENT_DISQUALIFIERS = ('offer_not_official', 'income_above_b40_line', 'pathway_funded_or_abroad')


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
    ``verdict`` is accepted for backward compatibility and ignored.

    TD-465 (2026-11-05): an STPM student whose course-start year is UNKNOWN
    (``course_start_unknown``) gets NO proposed amount (None) — the size cannot be established,
    and the old fall-through to RM3,000 committed the fresh-entrant figure by default. None is
    the existing "no automatic amount" outcome: record-verdict leaves ``award_amount`` unset and
    QC's absolute reporting-date stop (owner 2026-07-23) refuses the accept until the officer
    records the date; a re-recorded verdict then sizes it from the known year.

    Owner decision 2026-11-07 (decision 7): the amount follows the FUNDED PERIOD — STPM's RM3,000
    is Form 6's 18 months, everything else is 12 months at RM2,000. A DEGREE-BOUND student
    (``results_route.degree_bound``) gets RM2,000 whatever the stored code says (#251: a stale
    'stpm' over a degree), never RM3,000 / RM1,000 and never None. This only sizes an EMPTY
    ``award_amount``: record-verdict applies it on an APPROVE when the amount is unset, so a stored
    amount (an earlier verdict's, or a super's) is never resized by a re-recorded verdict. The
    payment schedule follows the stored amount (`contracts.pick_schedule_row`'s guard)."""
    if _sized_as_stpm(application):
        if course_start_unknown(application):
            return None
        return _STPM_CONTINUING_AMOUNT if _stpm_continuing(application) else _STPM_AMOUNT
    return _DEFAULT_AMOUNT


def is_allowed_amount(value):
    """True if ``value`` (Decimal) is one of the permitted slider stops."""
    try:
        return Decimal(str(value)) in ALLOWED_AMOUNTS
    except (ArithmeticError, TypeError, ValueError):
        return False
