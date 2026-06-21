"""Phone-verification views (roadmap S4 / TD-136) — Twilio Verify over WhatsApp, opt-in.

The Verify transport (`apps.scholarship.whatsapp.start/check_phone_verification`) is mocked;
these tests cover the view contract: rate limiting, status mapping, and that a confirmed code
flips `contact_phone_verified` (and persists a newly-verified number)."""
import unittest.mock
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.courses.models import StudentProfile
from apps.courses.views import PhoneVerifyStartView, PhoneVerifyCheckView

_W = 'apps.scholarship.whatsapp'


class TestPhoneVerifyStart(TestCase):
    def setUp(self):
        cache.clear()                       # rate-limit counter lives in the cache
        self.factory = APIRequestFactory()
        self.profile = StudentProfile.objects.create(
            supabase_user_id='pv-s-1', nric='040815-10-2022', contact_phone='012-345 6789')

    def _post(self, data=None):
        request = self.factory.post('/api/v1/profile/verify-phone/send/', data or {}, format='json')
        request.user_id = 'pv-s-1'
        request.supabase_user = {'id': 'pv-s-1'}
        return PhoneVerifyStartView.as_view()(request)

    @unittest.mock.patch(f'{_W}.start_phone_verification', return_value=(True, 'pending', ''))
    def test_send_uses_saved_phone(self, m):
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'sent')
        self.assertEqual(m.call_args[0][0], '012-345 6789')
        self.assertEqual(m.call_args[1]['channel'], 'whatsapp')

    def test_send_missing_phone_400(self):
        self.profile.contact_phone = ''
        self.profile.save(update_fields=['contact_phone'])
        resp = self._post()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['error'], 'phone_required')

    @unittest.mock.patch(f'{_W}.start_phone_verification', return_value=(False, 'unconfigured', ''))
    def test_send_unconfigured_503(self, _m):
        resp = self._post()
        self.assertEqual(resp.status_code, 503)

    @unittest.mock.patch(f'{_W}.start_phone_verification', return_value=(False, 'invalid_number', ''))
    def test_send_invalid_number_400(self, _m):
        resp = self._post({'phone': 'abc'})
        self.assertEqual(resp.status_code, 400)

    @unittest.mock.patch(f'{_W}.start_phone_verification', return_value=(True, 'pending', ''))
    def test_send_rate_limited_after_5(self, _m):
        for _ in range(5):
            self.assertEqual(self._post().status_code, 200)
        self.assertEqual(self._post().status_code, 429)


class TestPhoneVerifyCheck(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.profile = StudentProfile.objects.create(
            supabase_user_id='pv-c-1', nric='040815-11-2022', contact_phone='012-345 6789')

    def _post(self, data):
        request = self.factory.post('/api/v1/profile/verify-phone/check/', data, format='json')
        request.user_id = 'pv-c-1'
        request.supabase_user = {'id': 'pv-c-1'}
        return PhoneVerifyCheckView.as_view()(request)

    @unittest.mock.patch(f'{_W}.check_phone_verification', return_value=(True, ''))
    def test_correct_code_marks_verified(self, _m):
        resp = self._post({'code': '123456'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['verified'])
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.contact_phone_verified)

    @unittest.mock.patch(f'{_W}.check_phone_verification', return_value=(True, ''))
    def test_correct_code_persists_new_phone(self, _m):
        resp = self._post({'code': '123456', 'phone': '011-1234 5678'})
        self.assertEqual(resp.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.contact_phone, '011-1234 5678')
        self.assertTrue(self.profile.contact_phone_verified)

    @unittest.mock.patch(f'{_W}.check_phone_verification', return_value=(False, 'incorrect'))
    def test_wrong_code_400_not_verified(self, _m):
        resp = self._post({'code': '000000'})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data['verified'])
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.contact_phone_verified)

    def test_missing_code_400(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['error'], 'code_required')

    @unittest.mock.patch(f'{_W}.check_phone_verification', return_value=(False, 'unconfigured'))
    def test_unconfigured_503(self, _m):
        resp = self._post({'code': '123456'})
        self.assertEqual(resp.status_code, 503)
