"""The course-start year and the owner's ruling that a non-offer never dates the course.

Owner, 2026-11-02 (`docs/decisions.md`): a document scored `not_offer_letter` never sets the course-start
year, so it never feeds `award.proposed_award_amount`, `award.course_start_unknown` or `epf_evidence`.

Moved out of `pathway_engine.py` (which sits at its file-size limit); `pathway_engine.course_start_year`
calls `course_start_year` here, so every caller and patch target is unchanged.

THE LEAK THE S4 RE-REVIEW FOUND (H1). Skipping the letter's intake year is not enough: the reporting-date
sync (`offer_sync.sync_reporting_date_from_offer`, run by the autofill on every upload and re-read, and
`backfill_reporting_dates`) copied the same letter's reporting date into `application.reporting_date`,
and the course-start year falls back to that field. So:

  * `dates_the_course(offer)` — the one test: a letter scored `not_offer_letter` does not. The sync and
    the backfill (through `pathway_engine.offer_reporting_date`) refuse to copy a date from such a letter.
  * A date ALREADY synced from it before it was scored (the sync can run first) is caught at READ time:
    when the latest offer is `not_offer_letter` and the stored `reporting_date` equals that letter's own
    reporting date, the stored date is not used. An officer-typed date that differs still answers.
"""


def dates_the_course(offer) -> bool:
    """False for a letter scored `not_offer_letter` (owner, 2026-11-02); True otherwise (genuine, suspect,
    unscored, no letter at all)."""
    from .pathway_engine import offer_band
    return offer is None or offer_band(offer) != 'not_offer_letter'


def _offer_reporting_date(offer):
    from .pathway_engine import parse_reporting_date, student_offer_check
    return parse_reporting_date(student_offer_check(offer).get('reporting_date'))


def course_start_year(application, offer):
    """The calendar year the course started, or None — see `pathway_engine.course_start_year` for the two
    sources. ``offer`` is the application's latest offer letter (or None)."""
    from .pathway_engine import student_offer_check
    if offer is not None and dates_the_course(offer):
        iy = (student_offer_check(offer).get('intake_year') or '').strip()
        if iy.isdigit():
            return int(iy)
    rd = getattr(application, 'reporting_date', None)
    if rd and offer is not None and not dates_the_course(offer) and _offer_reporting_date(offer) == rd:
        return None              # synced from the non-offer itself: it does not date the course either
    return rd.year if rd else None
