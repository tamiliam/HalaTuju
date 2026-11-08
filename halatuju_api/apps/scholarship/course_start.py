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
