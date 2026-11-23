"""The ONE read point for "when does this student's course start?" — TD-465 part 2 (A1.13).

Two money decisions read the student's course start, and until A1.13 each read
``application.reporting_date`` directly:

  * QC accept (`views_admin/qc_checks._accept_absolute_stop`): no recorded date is an ABSOLUTE stop
    (``reporting_date_required``) — the date sizes the bursary;
  * the payment run (`payments._has_started`): a month is payable only if the student reported
    BEFORE it began (``reporting_date < period_month``); a missing date leaves the pathway floor
    as the only gate.

Both now ask ``recorded_date`` here, so any later rule about WHICH dates count (e.g. "a
not_offer_letter document never dates the course", deferred in ``docs/decisions.md`` 2026-11-02)
can be applied once, for both. ⚠ A1.13 CHANGES NO BEHAVIOUR (lead ruling, owner's rule "fix only,
do not change the design"): ``recorded_date`` is exactly the stored ``reporting_date``, QC stays
strict, and the payments rule is untouched. A proposed tightening of the payments rule (a start
year after the paid month's year is not payable) is TD-592, for the owner. Pinned by
``tests/test_course_start.py`` (both sites go through this helper; golden cases of today's answers).
"""


def recorded_date(application):
    """The student's recorded course start (her reporting date), or None when none is recorded.

    Exactly ``application.reporting_date`` today — the single place a future rule about which
    dates count would go."""
    return getattr(application, 'reporting_date', None)


# ── F3 (I-12): the reporting date is required before Recommend ─────────────────────────────────────

def box_shows(status, decision_reopened, letter_has_date) -> bool:
    """Does the cockpit show the "record the reporting date" box? The case table both sides run is
    ``tests/reporting_date_box_cases.json``.

    ``letter_has_date`` here means "the letter's date is the case's date": a live offer letter's
    date that parses AND a recorded date (`letter_dates_the_case`). The cockpit itself reads the
    served answer (`shows_box`, field ``shows_reporting_date_box``), so the box and this rule cannot
    disagree.

    drift-test: halatuju-web/src/lib/__tests__/reportingDateBoxDrift.test.ts — the web's
    ``showsReportingDateBox`` (its fallback for a payload without the field) answers the same table."""
    if letter_has_date:
        return False
    return (status or '') == 'interviewing' or bool(decision_reopened)


def letter_has_date(application) -> bool:
    """Does the latest LIVE offer letter give a reporting date that PARSES? Exactly the reading the
    copy into ``reporting_date`` makes (`services/offer_sync.sync_reporting_date_from_offer`: the
    latest live offer, ``parse_reporting_date``), via ``pathway_engine.offer_reporting_date``. A date
    text the parser cannot read ("JULAI 2026") is NO date: nothing is copied, so the box must show
    (F3 review fix 1)."""
    from .pathway_engine import offer_reporting_date
    return offer_reporting_date(application) is not None


def letter_dates_the_case(application) -> bool:
    """The letter's date is the case's date: the letter's date parses AND a date is recorded. Only
    then is the box hidden. A readable letter whose copy has not landed yet (no recorded date)
    still shows the box, so a case can never be left with no date and no way to type one."""
    return recorded_date(application) is not None and letter_has_date(application)


def shows_box(application) -> bool:
    """THE server answer to "does the reporting-date box show?", served to the cockpit as
    ``shows_reporting_date_box`` (`serializers_admin/detail_blocks`)."""
    return box_shows(application.status, getattr(application, 'decision_reopened_at', None),
                     letter_dates_the_case(application))


def recommend_needs_date(application) -> bool:
    """Recording a Recommend (``overall == 'accept'``) is refused while the box shows and no date is
    recorded (``reporting_date_required_before_recommend``). Decline never asks. The web's "Still to
    do" line is the same condition.

    With no recorded date the letter never hides the box (`letter_dates_the_case`), so inside the
    box's window (interviewing, or a reopened case) this refuses exactly when QC accept's absolute
    stop (`views_admin/qc_checks._accept_absolute_stop`, ``reporting_date_required``) would: both
    read ``recorded_date``. Pinned by ``test_f3_assessment.RecommendAndQcAgreeTest``."""
    if recorded_date(application) is not None:
        return False
    return shows_box(application)
