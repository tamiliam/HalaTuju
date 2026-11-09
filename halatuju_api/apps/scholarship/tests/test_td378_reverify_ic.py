"""Audit sprint A2.8a (TD-378) — re-verifying an IC at AWAITING QC, without a reopen.

A super's lock release on a ruled intake leaves an AWAITING-QC case that QC accept refuses
(`birth_state_ic_unlocked`). The cockpit's new "Re-verify IC" card (`ReverifyIcCard.tsx`) calls the
EXISTING verify-accept door directly, as a QC holder could already do through the API. These tests pin
what the card relies on: a QC may press it at AWAITING QC; it re-locks the IC and leaves the case at
AWAITING QC with no reopen, no "returned for revision" email and no verdict re-record; the reviewer's
verify stamp and checklist are KEPT only while the identity she verified is unchanged (A2.8a review and
re-check), with the presser's re-lock recorded beside it and as their own activity row; a changed IC (or a
stamp with no recorded identity) makes the press a fresh verify; either way the separation rule sends the
QC to someone else; and the cockpit is served what it needs to show the card. Synthetic data only.
"""
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import birth_state
from apps.scholarship.models import StaffActivity
from apps.scholarship.staff_activity import VERIFY_ACCEPT
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_student,
)

ONLY_BIRTH = dict(min_spm_a_count=None, min_spm_bplus_count=None, min_spm_credit_count=None,
                  min_stpm_pngk=None, min_merit_score=None, income_ceiling=None,
                  per_capita_ceiling=None)
SABAH_IC = '080505-12-1234'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TheReverifyAtAwaitingQc(TestCase):

    def setUp(self):
        p = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch('apps.scholarship.views_admin.applications.application_completeness',
                       return_value={'complete': True})
        p.start()
        self.addCleanup(p.stop)
        cohort = make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah'])
        self.app = make_application('awaiting_qc', outcome='recommend', cohort=cohort,
                                    student=make_student(nric=SABAH_IC))
        self.app.profile.nric_verified = False            # a super released the lock
        self.app.profile.save(update_fields=['nric_verified'])
        self.reviewer = make_admin('reviewer', owning_org=cohort.owning_organisation)
        self.stamped_at = timezone.now() - timedelta(days=2)
        self.ticks = {'nric': True, 'name': True, 'results': True, 'document': True}
        self.checklist = {**self.ticks, birth_state.VERIFIED_IC_KEY: birth_state.identity_print(self.app.profile)}
        type(self.app).objects.filter(pk=self.app.pk).update(   # the reviewer's verify-accept
            verified_by=self.reviewer.email, verified_at=self.stamped_at, verify_checklist=self.checklist)
        self.app.refresh_from_db()
        self.qc = make_admin('qc', owning_org=cohort.owning_organisation)
        self.other_qc = make_admin('qc', owning_org=cohort.owning_organisation)

    def _post(self, who, action, body=None):
        return authed_client(who).post(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/{action}/', body or {},
            format='json')

    def test_the_cockpit_is_served_what_the_card_needs(self):
        body = authed_client(self.qc).get(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/').json()
        self.assertEqual(body['status'], 'interviewed')
        self.assertFalse(body['nric_verified'])
        self.assertIsNotNone(body['birth_state']['meets_rule'])   # a ruled intake

    def test_accept_is_refused_then_a_qc_reverifies_and_another_qc_accepts(self):
        r = self._post(self.other_qc, 'qc-decision', {'decision': 'accept'})
        self.assertEqual((r.status_code, r.json()['code']), (400, birth_state.IC_UNLOCKED))
        self.assertIn('Re-verify IC', r.json()['error'])          # the message names the button
        decided_at = self.app.verdict_decided_at
        mail.outbox.clear()

        r = self._post(self.qc, 'verify-accept', {'checklist': {'nric': True}})   # the card's one call
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.app.profile.refresh_from_db()
        self.assertTrue(self.app.profile.nric_verified)
        self.assertEqual(self.app.status, 'interviewed')            # still awaiting QC
        self.assertIsNone(self.app.decision_reopened_at)            # no reopen …
        self.assertFalse(self.app.decision_reopens.exists())        # … so no false correction
        self.assertEqual(self.app.verdict_decided_at, decided_at)   # the verdict is not re-recorded
        self.assertEqual(mail.outbox, [])                           # no "returned for revision"
        # The IC is unchanged, so the reviewer's stamp is kept; the re-lock is recorded beside it (with the
        # presser's own checklist) and as the presser's activity row.
        self.assertEqual((self.app.verified_by, self.app.verified_at), (self.reviewer.email, self.stamped_at))
        relock = self.app.verify_checklist.pop(birth_state.RELOCK_KEY)
        self.assertEqual(self.app.verify_checklist, self.checklist)
        self.assertEqual((relock['by'], relock['checklist']), (self.qc.email, {'nric': True}))
        self.assertTrue(relock['at'])
        self.assertTrue(StaffActivity.objects.filter(actor=self.qc, subject_type='application',
                                                     subject_id=self.app.pk, verb=VERIFY_ACCEPT).exists())

        r = self._post(self.qc, 'qc-decision', {'decision': 'accept'})
        self.assertEqual((r.status_code, r.json()['code']), (403, 'self_review_qc_forbidden'))
        r = self._post(self.other_qc, 'qc-decision', {'decision': 'accept'})
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')

    def test_a_first_verify_accept_before_awaiting_qc_still_stamps_the_case(self):
        type(self.app).objects.filter(pk=self.app.pk).update(status='interviewing', verified_by='',
                                                             verified_at=None, verify_checklist={})
        r = self._post(self.qc, 'verify-accept', {'checklist': self.ticks})
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual((self.app.status, self.app.verified_by, self.app.verify_checklist),
                         ('interviewed', self.qc.email, self.checklist))   # the ticks + the identity digest
        self.assertIsNotNone(self.app.verified_at)

    def _assert_a_fresh_verify_by_the_qc(self):
        r = self._post(self.qc, 'verify-accept', {'checklist': {'nric': True}})
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.verified_by, self.qc.email)                 # the presser is the maker
        self.assertGreater(self.app.verified_at, self.stamped_at)
        self.assertEqual(self.app.verify_checklist, {'nric': True, birth_state.VERIFIED_IC_KEY:
                                                     birth_state.identity_print(self.app.profile)})
        r = self._post(self.qc, 'qc-decision', {'decision': 'accept'})
        self.assertEqual((r.status_code, r.json()['code']), (403, 'self_review_qc_forbidden'))
        r = self._post(self.other_qc, 'qc-decision', {'decision': 'accept'})
        self.assertEqual(r.status_code, 200, r.content)

    def test_a_changed_ic_after_the_release_makes_the_re_lock_a_fresh_verify(self):
        """The student changed the IC while the lock was released: the reviewer never verified this one."""
        self.app.profile.nric = '080505-12-5678'
        self.app.profile.save(update_fields=['nric'])
        self._assert_a_fresh_verify_by_the_qc()

    def test_a_changed_name_also_counts_as_a_changed_identity(self):
        self.app.profile.name = 'ANOTHER NAME'
        self.app.profile.save(update_fields=['name'])
        self._assert_a_fresh_verify_by_the_qc()

    def test_a_stamp_with_no_recorded_identity_is_treated_as_changed(self):
        type(self.app).objects.filter(pk=self.app.pk).update(verify_checklist=self.ticks)
        self.app.refresh_from_db()
        self._assert_a_fresh_verify_by_the_qc()
