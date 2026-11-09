"""Audit sprint A2.8a (TD-378) — re-verifying an IC at AWAITING QC, without a reopen.

A super's lock release on a ruled intake leaves an AWAITING-QC case that QC accept refuses
(`birth_state_ic_unlocked`). The cockpit's new "Re-verify IC" card (`ReverifyIcCard.tsx`) calls the
EXISTING verify-accept door directly, as a QC holder could already do through the API. These tests pin
what the card relies on: a QC may press it at AWAITING QC; it re-locks the IC and leaves the case at
AWAITING QC with no reopen, no "returned for revision" email and no verdict re-record; the presser is
then the IC's verifier, so the separation rule sends the QC to someone else; and the cockpit is served
what it needs to show the card. Synthetic data only.
"""
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from apps.scholarship import birth_state
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

        r = self._post(self.qc, 'verify-accept')                    # the card's one call
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.app.profile.refresh_from_db()
        self.assertTrue(self.app.profile.nric_verified)
        self.assertEqual(self.app.status, 'interviewed')            # still awaiting QC
        self.assertIsNone(self.app.decision_reopened_at)            # no reopen …
        self.assertFalse(self.app.decision_reopens.exists())        # … so no false correction
        self.assertEqual(self.app.verdict_decided_at, decided_at)   # the verdict is not re-recorded
        self.assertEqual(mail.outbox, [])                           # no "returned for revision"
        self.assertEqual(self.app.verified_by, self.qc.email)

        r = self._post(self.qc, 'qc-decision', {'decision': 'accept'})
        self.assertEqual((r.status_code, r.json()['code']), (403, 'self_review_qc_forbidden'))
        r = self._post(self.other_qc, 'qc-decision', {'decision': 'accept'})
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'recommended')
