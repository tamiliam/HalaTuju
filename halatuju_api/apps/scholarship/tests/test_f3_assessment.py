"""F3 (I-12) - the reporting date is required before Recommend.

`course_start.box_shows` answers the shared case table (`reporting_date_box_cases.json`), which the
web's `showsReportingDateBox` runs too (`reportingDateBoxDrift.test.ts`), so the cockpit's box and the
server's refusal are one condition. `record-verdict` refuses an `accept` in that state with
`reporting_date_required_before_recommend`; a Decline never asks. All data is made up.
"""
import datetime
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.scholarship import audit, course_start
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

CASES = json.loads((Path(__file__).parent / 'reporting_date_box_cases.json').read_text('utf-8'))['cases']
BUILD = 'apps.scholarship.views_admin.verdict.build_verdict'
GATE = 'apps.scholarship.views_admin.verdict.decision_refusal'
LETTER = 'apps.scholarship.course_start.letter_has_date'


class TheBoxRuleTest(SimpleTestCase):
    def test_the_shared_case_table(self):
        self.assertGreaterEqual(len(CASES), 8)
        for case in CASES:
            with self.subTest(case=case):
                self.assertIs(course_start.box_shows(case['status'], case['reopened'],
                                                     case['letter_has_date']), case['shows'])

    def test_a_reopen_stamp_counts_as_reopened(self):
        self.assertTrue(course_start.box_shows('interviewed', timezone.now(), False))
        self.assertFalse(course_start.box_shows('interviewed', None, False))

    def test_a_live_dated_letter_hides_the_box(self):
        app = mock.Mock()
        with mock.patch('apps.scholarship.document_snapshot.live_docs', return_value=['a', 'b']), \
                mock.patch('apps.scholarship.pathway_engine.student_offer_check',
                           side_effect=[{'reporting_date': None}, {'reporting_date': '2026-09-01'}]):
            self.assertTrue(course_start.letter_has_date(app))
        with mock.patch('apps.scholarship.document_snapshot.live_docs', return_value=[]):
            self.assertFalse(course_start.letter_has_date(app))

    def test_a_recorded_date_never_needs_one(self):
        app = mock.Mock(reporting_date=datetime.date(2026, 9, 1), status='interviewing')
        self.assertFalse(course_start.recommend_needs_date(app))
        app = mock.Mock(reporting_date=None, status='interviewing', decision_reopened_at=None)
        with mock.patch(LETTER, return_value=False):
            self.assertTrue(course_start.recommend_needs_date(app))
        with mock.patch(LETTER, return_value=True):
            self.assertFalse(course_start.recommend_needs_date(app))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class RecordVerdictRefusesRecommendTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.reviewer = make_admin('reviewer', owning_org=cls.cohort.owning_organisation)

    def setUp(self):
        # The factory records a reporting date; this case has none.
        self.app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(reporting_date=None)

    def _post(self, overall, letter_has_date=False):
        body = {'officer_verdict': {**dict.fromkeys(audit.FACTS, 'pass'), 'overall': overall},
                'reason': 'Made up.'}
        snap = [{'fact': f, 'status': 'verified', 'evidence': [], 'unresolved': []} for f in audit.FACTS]
        with mock.patch(BUILD, return_value=snap), mock.patch(GATE, return_value=None), \
                mock.patch(LETTER, return_value=letter_has_date):
            return authed_client(self.reviewer).post(
                f'/api/v1/admin/scholarship/applications/{self.app.pk}/record-verdict/', body,
                format='json')

    def test_recommend_without_a_date_is_refused_and_nothing_is_saved(self):
        r = self._post('accept')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()['code'], 'reporting_date_required_before_recommend')
        self.assertIsNone(ScholarshipApplication.objects.get(pk=self.app.pk).verdict_decided_at)

    def test_decline_never_needs_the_date(self):
        self.assertEqual(self._post('decline').status_code, 200)

    def test_recommend_goes_through_once_a_date_is_recorded(self):
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(
            reporting_date=datetime.date(2026, 9, 1))
        r = self._post('accept')
        self.assertNotEqual(r.json().get('code'), 'reporting_date_required_before_recommend')
        self.assertEqual(r.status_code, 200, r.content)

    def test_recommend_goes_through_when_the_letter_carries_the_date(self):
        self.assertEqual(self._post('accept', letter_has_date=True).status_code, 200)
