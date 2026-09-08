"""Vircle Airtable integration (vircle_airtable.py) — we tell Vircle WHO, Vircle tells us the
WALLET.

The load-bearing behaviours, in the order they can hurt someone:

  * the OUTBOUND push can never fail the student's own confirmation (fault-injected);
  * the INBOUND write never overwrites a stored wallet id (the field decides where money goes —
    a mismatch is logged for a human, not auto-resolved);
  * an invalid wallet id (fails `valid_vircle_id`) is refused, exactly as a typed one would be;
  * matching is by NRIC DIGITS (dashes or not), restricted to the relay population, so a webhook
    row can never write onto a rejected/expired file;
  * the endpoint is inert without the shared secret.
"""
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship import vircle_airtable
from apps.scholarship.resolution import VIRCLE_CODE
from apps.scholarship.vircle import raise_setup_task

_TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      _TEST_JWT_SECRET, algorithm='HS256')


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _make(self, uid, status='awarded', nric='080214-08-1234', name='KAVITHA A/P SURESH',
              vircle_id=''):
        profile = StudentProfile.objects.create(
            supabase_user_id=uid, name=name, nric=nric, contact_phone='0123456789',
            preferred_state='Perak', household_income=1500, household_size=4,
            receives_str=False, receives_jkm=False,
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status, vircle_id=vircle_id,
            profile_completed_at=timezone.now(), notify_email='k@example.com',
        )


# ── The outbound payload ─────────────────────────────────────────────────────
class TestRecipientPayload(_Base):
    def test_principal_for_a_student_who_can_hold_their_own_account(self):
        app = self._make('u1', nric='080214081234')   # born 2008 → can register
        p = vircle_airtable.recipient_payload(app)
        self.assertEqual(p, {'Name': 'KAVITHA A/P SURESH',
                             'NRIC': '080214-08-1234',   # digits → the dashed shape the guide shows
                             'Type': 'Principal'})

    def test_supplementary_for_a_child_registration(self):
        # Born after 2008 → registers under a parent = Supplementary (Gokula, 2026-09-08).
        # The SAME birth-year rule the setup email uses — not a second copy of it.
        app = self._make('u2', nric='090101-08-1234')
        self.assertEqual(vircle_airtable.recipient_payload(app)['Type'], 'Supplementary')

    def test_a_non_12_digit_nric_is_passed_through_untouched(self):
        app = self._make('u3', nric='A1234567')
        self.assertEqual(vircle_airtable.recipient_payload(app)['NRIC'], 'A1234567')


# ── The push rides the student's confirmation and can never break it ─────────
@override_settings(SUPABASE_JWT_SECRET=_TEST_JWT_SECRET, VIRCLE_SETUP_ENABLED=True,
                   VIRCLE_AIRTABLE_PUSH_URL='https://hooks.airtable.example/wh')
class TestPushOnConfirm(_Base):
    def setUp(self):
        self.client = APIClient()
        self.app = self._make('u1')
        raise_setup_task(self.app)
        self.item = self.app.resolution_items.get(code=VIRCLE_CODE)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("u1")}')

    def _resolve(self):
        return self.client.post(
            f'/api/v1/scholarship/resolution-items/{self.item.id}/resolve/',
            {'text': '012-345 6789', 'vircle_id': '8000400175123'}, format='json')

    @mock.patch('requests.post')
    def test_confirming_pushes_name_nric_type_to_vircle(self, post):
        post.return_value = mock.Mock(status_code=200)
        r = self._resolve()
        self.assertEqual(r.status_code, 200)
        (url,), kwargs = post.call_args
        self.assertEqual(url, 'https://hooks.airtable.example/wh')
        self.assertEqual(kwargs['json'], {'Name': 'KAVITHA A/P SURESH',
                                         'NRIC': '080214-08-1234', 'Type': 'Principal'})
        self.item.refresh_from_db()
        self.assertEqual(self.item.params.get('airtable_push'), 'sent')

    @mock.patch('requests.post', side_effect=OSError('network down'))
    def test_a_dead_webhook_never_fails_the_confirmation(self, post):
        # Fault injection — the usage-meter contract. The student's confirm succeeds, the
        # wallet id is stored, and the failure is recorded on the item for the cockpit.
        r = self._resolve()
        self.assertEqual(r.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'resolved')
        self.app.refresh_from_db()
        self.assertEqual(self.app.vircle_id, '8000400175123')
        self.assertEqual(self.item.params.get('airtable_push'), 'failed')

    @override_settings(VIRCLE_AIRTABLE_PUSH_URL='')
    @mock.patch('requests.post')
    def test_no_url_configured_means_no_call_at_all(self, post):
        self._resolve()
        post.assert_not_called()


# ── The inbound update ───────────────────────────────────────────────────────
class TestApplyUpdate(_Base):
    def test_sets_wallet_and_activation_matched_on_nric_digits(self):
        app = self._make('u1', nric='080214-08-1234')
        # Vircle sends bare digits; we store dashed — digits-matching bridges them.
        out = vircle_airtable.apply_update({'NRIC': '080214081234',
                                            'Wallet ID': '8000400181509',
                                            'Activated On': '08/09/2026'})
        app.refresh_from_db()
        self.assertEqual(out['wallet'], 'set')
        self.assertEqual(out['activated'], 'set')
        self.assertEqual(app.vircle_id, '8000400181509')
        self.assertIsNotNone(app.vircle_activated_at)

    def test_a_stored_wallet_is_NEVER_overwritten(self):
        # The field decides where money goes. A disagreement between Vircle's row and our
        # stored id is a human's question — auto-resolving it is how a wrong id becomes a
        # wrong payment with no witness.
        app = self._make('u1', vircle_id='8000400175123')
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Wallet ID': '8000400179999'})
        app.refresh_from_db()
        self.assertEqual(out['wallet'], 'mismatch')
        self.assertEqual(app.vircle_id, '8000400175123')

    def test_an_identical_wallet_reads_kept(self):
        self._make('u1', vircle_id='8000400175123')
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Wallet ID': '="8000400175123"'})
        self.assertEqual(out['wallet'], 'kept')

    def test_an_invalid_wallet_is_refused_like_a_typed_one(self):
        # Same gate as the Action Centre: valid_vircle_id. A DuitNow-shaped or out-of-band
        # value from the webhook is held for a human, never stored.
        app = self._make('u1')
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Wallet ID': '8000400101003'})
        app.refresh_from_db()
        self.assertEqual(out['wallet'], 'invalid')
        self.assertEqual(app.vircle_id, '')

    def test_activation_is_set_if_null_only(self):
        app = self._make('u1')
        when = timezone.now()
        app.vircle_activated_at = when
        app.save(update_fields=['vircle_activated_at'])
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Activated On': '01/01/2020'})
        app.refresh_from_db()
        self.assertEqual(out['activated'], 'kept')
        self.assertEqual(app.vircle_activated_at, when)

    def test_unknown_nric_reports_no_match(self):
        self._make('u1', nric='080214-08-1234')
        out = vircle_airtable.apply_update({'NRIC': '990101-14-5678',
                                            'Wallet ID': '8000400175123'})
        self.assertEqual(out, {'ok': False, 'reason': 'no_match'})

    def test_a_rejected_file_is_outside_the_population(self):
        # Restricted to VIRCLE_SETUP_STATES — a webhook row can never write onto a closed-out
        # application, even with a matching NRIC.
        app = self._make('u1', status='rejected')
        out = vircle_airtable.apply_update({'NRIC': '080214-08-1234',
                                            'Wallet ID': '8000400175123'})
        app.refresh_from_db()
        self.assertEqual(out['reason'], 'no_match')
        self.assertEqual(app.vircle_id, '')


# ── The endpoint: inert without the secret ───────────────────────────────────
@override_settings(VIRCLE_AIRTABLE_SECRET='s3cret')
class TestInboundEndpoint(_Base):
    URL = '/api/v1/internal/vircle/airtable/'

    def setUp(self):
        self.client = APIClient()
        self.app = self._make('u1', nric='080214-08-1234')

    def test_no_secret_is_403(self):
        r = self.client.post(self.URL, {'NRIC': '080214-08-1234'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_wrong_secret_is_403(self):
        r = self.client.post(self.URL, {'NRIC': '080214-08-1234'}, format='json',
                             HTTP_X_VIRCLE_SECRET='wrong')
        self.assertEqual(r.status_code, 403)

    @override_settings(VIRCLE_AIRTABLE_SECRET='')
    def test_unset_secret_refuses_everything(self):
        # Dark by default: with no secret configured, even an empty header must not pass —
        # ''=='' would otherwise open the endpoint to the world.
        r = self.client.post(self.URL, {'NRIC': '080214-08-1234'}, format='json',
                             HTTP_X_VIRCLE_SECRET='')
        self.assertEqual(r.status_code, 403)

    def test_good_secret_applies_the_update_through_the_url(self):
        # Through the URL, not the service — the view/service seam lesson (2026-08-18).
        r = self.client.post(self.URL,
                             {'NRIC': '080214081234', 'Wallet ID': '8000400181509'},
                             format='json', HTTP_X_VIRCLE_SECRET='s3cret')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['wallet'], 'set')
        self.app.refresh_from_db()
        self.assertEqual(self.app.vircle_id, '8000400181509')
