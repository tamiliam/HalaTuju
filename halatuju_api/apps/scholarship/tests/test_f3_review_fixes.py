"""F3 review fixes 2 and 3. All data is made up.

Fix 2: a reject before interview stores its four facts in `officer_verdict` (with the AI snapshot
beside them). A CANCELLED one takes them back (`pre_interview.take_back_assessment`), so the next
reviewer meets an empty assessment, not facts she never rated. A reviewer's (or super's) recorded
assessment already on the case (`verdict_decided_at`) is kept: the reject never writes over it.
Other declines' cancels are unchanged.

Fix 3: for one release, the old LL2 Fail-reason codes from a browser tab opened before the deploy
are read as `other`; a truly unknown code is still refused.
"""
from datetime import timedelta

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.scholarship import fail_reasons
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import cancel_pending_decline
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)

FACTS = {'identity': 'pass', 'academic': 'pass', 'pathway': 'pass', 'income': 'fail'}
WHY = {'income': 'proof_missing'}
REVIEWER_OWN = {'identity': 'pass', 'academic': 'pass', 'income': 'pass', 'pathway': 'pass',
                'overall': 'hold', 'fail_reasons': {}}


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class CancelTakesTheFactsBackTest(TestCase):
    def setUp(self):
        self.org = make_org()
        self.cohort = make_cohort(owning_organisation=self.org)
        self.org_admin = make_admin('org_admin', owning_org=self.org)
        self.app = make_application('profile_complete', cohort=self.cohort)
        mail.outbox = []

    def _reject(self):
        body = {'reason': 'not_b40', 'comments': 'Made up: the payslip is above the band.',
                'facts': FACTS, 'fail_reasons': WHY}
        r = authed_client(self.org_admin).post(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/reject-before-interview/', body,
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()

    def _cancel(self):
        return authed_client(self.org_admin).post(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/cancel-decline/', {}, format='json')

    def test_a_cancel_leaves_no_facts_and_no_ai_snapshot(self):
        self._reject()
        self.assertEqual(self.app.officer_verdict, {**FACTS, 'fail_reasons': WHY})   # stored first
        r = self._cancel()
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'profile_complete')
        self.assertEqual(self.app.officer_verdict, {})
        self.assertEqual(self.app.ai_verdict_snapshot, [])
        self.assertEqual(self.app.ai_verdict_engine_version, '')
        self.assertEqual(self.app.ai_verdict_context, {})
        self.assertIsNone(self.app.verdict_decided_at)

    def test_the_next_reviewer_is_served_an_empty_assessment(self):
        # The cockpit's "Complete your assessment" reads an empty officer_verdict (useVerdict).
        self._reject()
        body = self._cancel().data
        self.assertEqual(body['officer_verdict'], {})
        self.assertEqual(body['ai_verdict_snapshot'], [])
        self.assertIsNone(body['verdict_decided_at'])

    def test_a_recorded_assessment_already_on_the_case_is_kept_through_reject_and_cancel(self):
        stamp = timezone.now() - timedelta(days=1)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(
            officer_verdict=REVIEWER_OWN, verdict_decided_at=stamp, ai_verdict_engine_version='v-old')
        self.app.refresh_from_db()
        self._reject()
        self.assertEqual(self.app.officer_verdict, REVIEWER_OWN)   # not written over
        self.assertEqual(self.app.ai_verdict_engine_version, 'v-old')
        self.assertEqual(self._cancel().status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.officer_verdict, REVIEWER_OWN)
        self.assertEqual(self.app.ai_verdict_engine_version, 'v-old')
        self.assertEqual(self.app.verdict_decided_at, stamp)


class OtherCancelsAreUnchangedTest(TestCase):
    def test_a_cancelled_reviewer_decline_keeps_her_assessment(self):
        app = make_application('verdict_recorded', outcome='decline', cohort=make_cohort())
        stamp = timezone.now() - timedelta(hours=2)
        ScholarshipApplication.objects.filter(pk=app.pk).update(
            status='rejected', rejection_category='interview', rejected_at=stamp,
            pending_rejection_category='interview', decline_due_at=timezone.now() + timedelta(hours=20),
            pre_decline_status='interviewed', officer_verdict={**REVIEWER_OWN, 'overall': 'decline'},
            ai_verdict_snapshot=[{'fact': 'income'}], ai_verdict_engine_version='v-1',
            verdict_decided_at=stamp)
        app.refresh_from_db()
        self.assertTrue(cancel_pending_decline(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')
        self.assertEqual(app.officer_verdict, {**REVIEWER_OWN, 'overall': 'decline'})
        self.assertEqual(app.ai_verdict_snapshot, [{'fact': 'income'}])
        self.assertEqual(app.ai_verdict_engine_version, 'v-1')

    def test_the_take_back_answers_only_its_own_bucket(self):
        from apps.scholarship.services.pre_interview import take_back_assessment
        app = ScholarshipApplication(rejection_category='interview', officer_verdict=dict(FACTS))
        self.assertEqual(take_back_assessment(app), [])
        self.assertEqual(app.officer_verdict, FACTS)


class OldFailReasonCodesTest(SimpleTestCase):
    """Fix 3: one release of grace for a tab opened before the F3 deploy."""

    def test_every_old_code_reads_as_other(self):
        self.assertTrue(fail_reasons.OLD_CODES_READ_AS_OTHER)
        for old in fail_reasons.OLD_CODES_READ_AS_OTHER:
            with self.subTest(old=old):
                self.assertNotIn(old, fail_reasons.CODES)
                self.assertEqual(fail_reasons.validate({'income': old}), {'income': 'other'})

    def test_engine_wrong_is_one_of_them(self):
        self.assertIn('engine_wrong', fail_reasons.OLD_CODES_READ_AS_OTHER)

    def test_a_truly_unknown_code_is_still_refused(self):
        with self.assertRaises(fail_reasons.BadFailReasons):
            fail_reasons.validate({'income': 'made_up_code'})
