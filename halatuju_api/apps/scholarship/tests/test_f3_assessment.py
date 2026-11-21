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
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)

_TABLE = json.loads((Path(__file__).parent / 'reporting_date_box_cases.json').read_text('utf-8'))
CASES = _TABLE['cases']
LETTER_CASES = _TABLE['letter_cases']
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

    def test_a_letter_counts_only_when_its_date_parses(self):
        # F3 review fix 1: the same reading the copy into reporting_date makes.
        app = mock.Mock()
        with mock.patch('apps.scholarship.pathway_engine.offer_reporting_date',
                        return_value=datetime.date(2026, 9, 1)):
            self.assertTrue(course_start.letter_has_date(app))
        with mock.patch('apps.scholarship.pathway_engine.offer_reporting_date', return_value=None):
            self.assertFalse(course_start.letter_has_date(app))

    def test_a_recorded_date_never_needs_one(self):
        app = mock.Mock(reporting_date=datetime.date(2026, 9, 1), status='interviewing')
        self.assertFalse(course_start.recommend_needs_date(app))
        app = mock.Mock(reporting_date=None, status='interviewing', decision_reopened_at=None)
        with mock.patch(LETTER, return_value=False):
            self.assertTrue(course_start.recommend_needs_date(app))
        # A readable letter whose copy has not landed never hides the box: still refused.
        with mock.patch(LETTER, return_value=True):
            self.assertTrue(course_start.recommend_needs_date(app))


def _case_with_letter(cohort, reviewer, case):
    """A made-up case from one `letter_cases` row: its stage, reopen stamp, offer letter text and
    recorded date."""
    app = make_application('interviewing', cohort=cohort, reviewer=reviewer)
    if case['letter_date'] is not None:
        ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path='x/offer',
            vision_fields={'student_verdict': 'ok',
                           'fields': {'reporting_date': case['letter_date'], 'programme': 'Diploma'}})
    ScholarshipApplication.objects.filter(pk=app.pk).update(
        status=case['status'],
        decision_reopened_at=timezone.now() if case['reopened'] else None,
        reporting_date=datetime.date(2026, 6, 22) if case['recorded'] else None)
    return ScholarshipApplication.objects.get(pk=app.pk)


class TheLetterCasesTest(TestCase):
    """F3 review fix 1: whole cases from the shared table (`letter_cases`), answered by the server
    function the cockpit is served (`shows_reporting_date_box`). A letter saying "JULAI 2026" has
    no readable date: the copy writes nothing, so the box must show and Recommend must wait."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.reviewer = make_admin('reviewer', owning_org=cls.cohort.owning_organisation)

    def test_the_shared_letter_cases(self):
        self.assertTrue(any(c['letter_date'] == 'JULAI 2026' for c in LETTER_CASES))
        for case in LETTER_CASES:
            with self.subTest(case=case):
                app = _case_with_letter(self.cohort, self.reviewer, case)
                self.assertIs(course_start.letter_has_date(app), case['letter_has_date'])
                self.assertIs(course_start.shows_box(app), case['shows'])

    def test_the_letter_reading_is_the_copys_reading(self):
        # The copy (sync_reporting_date_from_offer) writes a date exactly when the letter counts.
        from apps.scholarship.services import sync_reporting_date_from_offer
        for case in LETTER_CASES:
            if case['recorded']:
                continue
            with self.subTest(case=case):
                app = _case_with_letter(self.cohort, self.reviewer, case)
                self.assertIs(sync_reporting_date_from_offer(app), case['letter_has_date'])

    def test_the_detail_payload_serves_the_answer(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        case = LETTER_CASES[0]
        app = _case_with_letter(self.cohort, self.reviewer, case)
        self.assertIs(AdminApplicationDetailSerializer().get_shows_reporting_date_box(app), case['shows'])


class RecommendAndQcAgreeTest(TestCase):
    """Fix 1: inside the box's window (interviewing, or a reopened case) the Recommend refusal and QC
    accept's absolute reporting-date stop give the same answer for every case in the table: the
    reviewer is never let through to a QC that must refuse. Outside the window (an un-reopened
    case past interviewing) the reviewer is not asked, by design, and QC stays the backstop."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        cls.reviewer = make_admin('reviewer', owning_org=cls.cohort.owning_organisation)

    def test_same_inputs_same_answer(self):
        from apps.scholarship.views_admin.qc_checks import _accept_absolute_stop
        in_window = [c for c in LETTER_CASES if c['status'] == 'interviewing' or c['reopened']]
        self.assertGreaterEqual(len(in_window), 6)
        for case in in_window:
            with self.subTest(case=case):
                app = _case_with_letter(self.cohort, self.reviewer, case)
                stop = _accept_absolute_stop(app)
                qc_refuses = stop is not None and stop.data.get('code') == 'reporting_date_required'
                self.assertIs(course_start.recommend_needs_date(app), qc_refuses)


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

    def test_a_readable_letter_with_no_recorded_date_still_refuses(self):
        # F3 review fix 1: the gap this test used to lock in. With no recorded date QC accept would
        # refuse (reporting_date_required), so the Recommend must too, and the box shows to fill it.
        r = self._post('accept', letter_has_date=True)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()['code'], 'reporting_date_required_before_recommend')

    def test_an_unreadable_letter_date_refuses_too(self):
        ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter', storage_path='x/offer',
            vision_fields={'student_verdict': 'ok', 'fields': {'reporting_date': 'JULAI 2026'}})
        body = {'officer_verdict': {**dict.fromkeys(audit.FACTS, 'pass'), 'overall': 'accept'},
                'reason': 'Made up.'}
        snap = [{'fact': f, 'status': 'verified', 'evidence': [], 'unresolved': []} for f in audit.FACTS]
        with mock.patch(BUILD, return_value=snap), mock.patch(GATE, return_value=None):
            r = authed_client(self.reviewer).post(
                f'/api/v1/admin/scholarship/applications/{self.app.pk}/record-verdict/', body,
                format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()['code'], 'reporting_date_required_before_recommend')
