"""TD-465 part 2 (A1.13): `course_start.recorded_date` is the ONE read point for the student's course
start, at both money sites — QC accept and the payment run — and the refactor changes NO behaviour.

Two kinds of pin:
  * WIRING — each site's answer follows the helper (patched), not the stored column, so a later rule
    about which dates count lands in one place for both;
  * GOLDEN — today's answers, case by case, so the move is provably neutral. QC stays strict (no
    recorded date is an absolute stop); the payments rule is unchanged (strict `<`, a missing date
    leaves the pathway floor as the only gate). The proposed payments tightening is TD-592, NOT here.
All on dummy data.
"""
import datetime
import inspect
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.scholarship import course_start, payments
from apps.scholarship.tests.factories import make_application, make_cohort
from apps.scholarship.views_admin import qc_checks

D = datetime.date
#: A July payment floor (the diploma pathways'), in the default cohort year 2026.
JULY_ROW = SimpleNamespace(start_month=7)


class TestTheHelper(TestCase):
    def test_it_is_the_stored_reporting_date(self):
        app = make_application('awarded', reporting_date=D(2026, 7, 14))
        self.assertEqual(course_start.recorded_date(app), D(2026, 7, 14))
        app.reporting_date = None
        self.assertIsNone(course_start.recorded_date(app))

    def test_neither_site_reads_the_column_directly(self):
        self.assertNotIn('app.reporting_date', inspect.getsource(qc_checks._accept_absolute_stop))
        self.assertNotIn('application.reporting_date', inspect.getsource(payments._has_started))


class TestQcSite(TestCase):
    """QC accept's absolute stop (`reporting_date_required`) — strict, as before."""
    def setUp(self):
        self.app = make_application('awaiting_qc', outcome='recommend', cohort=make_cohort())

    def _code(self):
        stop = qc_checks._accept_absolute_stop(self.app)
        return None if stop is None else stop.data['code']

    # ── golden ──
    def test_a_recorded_date_passes(self):
        self.assertIsNotNone(self.app.reporting_date)
        self.assertIsNone(self._code())

    def test_no_recorded_date_is_an_absolute_stop(self):
        self.app.reporting_date = None
        self.assertEqual(self._code(), 'reporting_date_required')

    def test_any_recorded_date_counts_past_or_future(self):
        for when in (D(2024, 9, 1), D(2026, 1, 2), D(2027, 7, 1)):
            with self.subTest(when=str(when)):   # str: xdist cannot serialise a date
                self.app.reporting_date = when
                self.assertIsNone(self._code())

    # ── wiring ──
    def test_the_answer_follows_the_helper(self):
        with patch.object(course_start, 'recorded_date', return_value=None) as helper:
            self.assertEqual(self._code(), 'reporting_date_required')   # column is set; helper wins
        helper.assert_called_once_with(self.app)
        self.app.reporting_date = None
        with patch.object(course_start, 'recorded_date', return_value=D(2026, 6, 8)):
            self.assertIsNone(self._code())


class TestPaymentsSite(TestCase):
    """`payments._has_started(application, period_month, row)` — unchanged."""
    def setUp(self):
        self.app = make_application('awarded', cohort=make_cohort())

    def _started(self, reporting, period):
        self.app.reporting_date = reporting
        return payments._has_started(self.app, period, JULY_ROW)

    # ── golden: (reporting date, month paid for) -> payable? ──
    GOLDEN = (
        (None, D(2026, 6, 1), False),            # before the pathway floor
        (None, D(2026, 7, 1), True),             # no date: the floor is the only gate (lenient)
        (None, D(2026, 12, 1), True),
        (D(2026, 7, 1), D(2026, 7, 1), False),   # reports 1 July: not payable for July (strict <)
        (D(2026, 7, 1), D(2026, 8, 1), True),
        (D(2026, 8, 5), D(2026, 8, 1), False),   # reports 5 August: first payable for September
        (D(2026, 8, 5), D(2026, 9, 1), True),
        (D(2025, 9, 1), D(2026, 7, 1), True),    # continuing student, from the floor
        (D(2025, 9, 1), D(2026, 6, 1), False),   # the floor applies even to a continuing student
        (D(2027, 7, 1), D(2026, 12, 1), False),  # a later start is not yet payable
    )

    def test_golden_cases(self):
        for reporting, period, expected in self.GOLDEN:
            with self.subTest(reporting=str(reporting), period=str(period)):
                self.assertIs(self._started(reporting, period), expected)

    # ── wiring ──
    def test_the_answer_follows_the_helper(self):
        with patch.object(course_start, 'recorded_date', return_value=D(2026, 9, 15)) as helper:
            self.assertFalse(self._started(None, D(2026, 8, 1)))   # column None; helper wins
        helper.assert_called_once_with(self.app)
        with patch.object(course_start, 'recorded_date', return_value=None):
            self.assertTrue(self._started(D(2026, 9, 15), D(2026, 8, 1)))
