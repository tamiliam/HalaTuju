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

    drift-test: halatuju-web/src/lib/__tests__/reportingDateBoxDrift.test.ts — the web's
    ``showsReportingDateBox`` answers the same table, so the box and this rule cannot disagree."""
    if letter_has_date:
        return False
    return (status or '') == 'interviewing' or bool(decision_reopened)


def letter_has_date(application) -> bool:
    """Does a LIVE offer letter carry a reporting date? The same reading the cockpit makes of each
    document's ``pathway_check.reporting_date`` (`serializers/documents.get_pathway_check`)."""
    from .document_snapshot import live_docs
    from .pathway_engine import student_offer_check
    return any(student_offer_check(d).get('reporting_date') for d in live_docs(application, 'offer_letter'))


def recommend_needs_date(application) -> bool:
    """Recording a Recommend (``overall == 'accept'``) is refused while the box shows and no date is
    recorded (``reporting_date_required_before_recommend``). Decline never asks. The web's "Still to
    do" line is the same condition."""
    if recorded_date(application) is not None:
        return False
    return box_shows(application.status, getattr(application, 'decision_reopened_at', None),
                     letter_has_date(application))
