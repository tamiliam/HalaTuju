"""Student maintenance Sprint 3 — the student's own "My Bursary" summary.

Pinned: her OWN file only (another student's never; no file is 404, whatever the reason); her money
from the ledger with the funding summary's "remaining"; the coarse `support_paused` and NEVER a
sub-state word, an actor email or an activity row; the results gate served as `can_record_results`.
"""
import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import activity, maintenance, payments
from apps.scholarship.models import Disbursement, SemesterResult
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_student,
)

URL = '/api/v1/scholarship/bursary/summary/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestBursarySummary(TestCase):
    def setUp(self):
        self.cohort = make_cohort()
        self.student = make_student(name='Aisyah')
        self.app = make_application('awarded', cohort=self.cohort, student=self.student,
                                    vircle_activated_at=timezone.now(),
                                    chosen_programme={'course_name': 'Diploma in Accounting',
                                                      'institution': 'Politeknik Ungku Omar'})

    def _get(self, student=None):
        return authed_client((student or self.student).supabase_user_id).get(URL)

    def test_her_own_file(self):
        Disbursement.objects.create(application=self.app, amount=Decimal('200'), status='released',
                                    sequence=1, released_at=timezone.now())
        SemesterResult.objects.create(application=self.app, semester='Sem 1', cgpa=Decimal('3.25'))
        r = self._get()
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual((body['application_id'], body['name'], body['course'], body['status']),
                         (self.app.id, 'AISYAH', 'Diploma in Accounting', 'awarded'))
        self.assertEqual(body['funds']['received'], '200.00')
        self.assertEqual(body['funds']['remaining'], f'{payments._remaining(self.app):.2f}')
        self.assertEqual(body['funds']['last_payment']['amount'], '200.00')
        self.assertEqual((body['latest_result']['semester'], body['latest_result']['cgpa']),
                         ('Sem 1', '3.25'))
        self.assertEqual((body['in_maintenance'], body['can_record_results'], body['support_paused']),
                         (True, False, False))

    def test_never_a_staff_word(self):
        maintenance.set_substate(self.app, 'probation', by_email='officer@example.test')
        activity.add_entry(self.app, 'note', 'Private staff note.', actor_email='officer@example.test',
                           internal=True)
        text = json.dumps(self._get().json())
        for leak in ('probation', 'officer@example.test', 'Private staff note', 'maintenance_substate',
                     'nric'):
            self.assertNotIn(leak, text)

    def test_on_hold_is_only_support_paused(self):
        maintenance.set_substate(self.app, 'on_hold')
        body = self._get().json()
        self.assertTrue(body['support_paused'])
        self.assertNotIn('on_hold', json.dumps(body))

    def test_no_file_is_404(self):
        loner = make_student()
        make_application('awarded', cohort=self.cohort, student=loner)       # no live wallet
        self.assertEqual(self._get(loner).status_code, 404)
        self.assertEqual(self._get(make_student()).status_code, 404)        # never applied

    def test_a_closed_funded_file_still_opens_read_only(self):
        closed = make_student()
        make_application('closed', cohort=self.cohort, student=closed)
        body = self._get(closed).json()
        self.assertEqual((body['status'], body['in_maintenance'], body['can_record_results']),
                         ('closed', False, False))

    def test_only_her_own(self):
        other = make_student()
        mine = self._get().json()['application_id']
        self.assertEqual(mine, self.app.id)
        self.assertEqual(self._get(other).status_code, 404)

    def test_an_active_student_may_record_results(self):
        active = make_student()
        make_application('active', cohort=self.cohort, student=active)
        self.assertTrue(self._get(active).json()['can_record_results'])

    def test_sign_in_required(self):
        from rest_framework.test import APIClient
        self.assertIn(APIClient().get(URL).status_code, (401, 403))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestBursarySummaryReviewGaps(TestCase):
    """S3 adversarial review L8."""

    def setUp(self):
        self.cohort = make_cohort()
        self.student = make_student()

    def _get(self):
        return authed_client(self.student.supabase_user_id).get(URL)

    def test_a_newer_live_file_wins_over_an_older_graduated_one(self):
        make_application('closed', cohort=self.cohort, student=self.student)
        live = make_application('maintenance', cohort=make_cohort(), student=self.student)
        self.assertEqual(self._get().json()['application_id'], live.id)

    def test_a_newer_pre_award_case_does_not_hide_an_older_funded_file(self):
        funded = make_application('maintenance', cohort=self.cohort, student=self.student)
        make_application('submitted', cohort=make_cohort(), student=self.student)
        self.assertEqual(self._get().json()['application_id'], funded.id)

    def test_returned_and_withheld_money_is_not_received(self):
        app = make_application('maintenance', cohort=self.cohort, student=self.student)
        now = timezone.now()
        Disbursement.objects.create(application=app, amount=Decimal('200'), status='released',
                                    sequence=1, released_at=now - timezone.timedelta(days=30))
        Disbursement.objects.create(application=app, amount=Decimal('300'), status='returned',
                                    sequence=2, released_at=now)
        Disbursement.objects.create(application=app, amount=Decimal('400'), status='withheld',
                                    sequence=3)
        funds = self._get().json()['funds']
        self.assertEqual((funds['received'], funds['last_payment']['amount']), ('200.00', '200.00'))

    def test_a_stalled_pre_award_close_with_a_wallet_stamp_has_no_hub(self):
        make_application('closed', cohort=self.cohort, student=self.student, active_at=None,
                         vircle_activated_at=timezone.now(), closure_reason='stalled')
        self.assertEqual(self._get().status_code, 404)

    def test_the_gift_name_falls_back_to_english(self):
        make_application('maintenance', cohort=self.cohort, student=self.student)
        names = self._get().json()['gift_names']
        self.assertEqual(names['ms'], self.cohort.programme.name_ms or self.cohort.programme.name_en)
        self.assertEqual(set(names), {'en', 'ms', 'ta'})
