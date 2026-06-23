"""Tests for the outbound WhatsApp comms helper (Sprint 1) + inbound opt-out webhook (S5/TD-135)."""
import base64
import hashlib
import hmac
from unittest import mock

import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship import whatsapp
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort, WhatsAppMessage

_CREDS = dict(
    WHATSAPP_ENABLED=True,
    TWILIO_ACCOUNT_SID='AC_test',
    TWILIO_AUTH_TOKEN='tok_test',
    TWILIO_WHATSAPP_FROM='whatsapp:+14155238886',
)


@pytest.mark.parametrize('raw,expected', [
    ('012-345 6789', '+60123456789'),     # apply-form shape (98/99 prod applicants)
    ('0123456789', '+60123456789'),
    ('+60123456789', '+60123456789'),     # already E.164 (the 1 prod applicant)
    ('60123456789', '+60123456789'),
    ('011-1234 5678', '+601112345678'),   # 11-digit mobile
    ('0060123456789', '+60123456789'),    # 00 international access
    ('', ''),
    (None, ''),
    ('   ', ''),
    ('abc', ''),
    ('123', ''),                          # too short → rejected
])
def test_normalise_msisdn(raw, expected):
    assert whatsapp.normalise_msisdn(raw) == expected


@pytest.mark.django_db
def test_send_is_noop_when_disabled():
    with override_settings(WHATSAPP_ENABLED=False):
        assert whatsapp.send_whatsapp('0123456789', 'hi', kind='t') is None
    assert WhatsAppMessage.objects.count() == 0


@pytest.mark.django_db
def test_send_is_noop_when_unconfigured():
    # Enabled but no creds → still a no-op, no row written.
    with override_settings(WHATSAPP_ENABLED=True, TWILIO_ACCOUNT_SID='',
                           TWILIO_AUTH_TOKEN='', TWILIO_WHATSAPP_FROM=''):
        assert whatsapp.send_whatsapp('0123456789', 'hi', kind='t') is None
    assert WhatsAppMessage.objects.count() == 0


@pytest.mark.django_db
@override_settings(**_CREDS)
def test_send_logs_and_posts_normalised_number():
    with mock.patch.object(whatsapp, '_post_to_twilio',
                           return_value=('SM123', 'queued', '')) as m:
        row = whatsapp.send_whatsapp('012-345 6789', 'hello', kind='interview_reminder_1day')
    assert row is not None
    assert row.to_number == '+60123456789'         # normalised before send + log
    assert row.provider_sid == 'SM123'
    assert row.status == 'queued'
    assert row.kind == 'interview_reminder_1day'
    m.assert_called_once()
    assert m.call_args[0][3] == '+60123456789'      # (sid, token, sender, to_e164, body)


@pytest.mark.django_db
@override_settings(**_CREDS)
def test_send_bad_number_logs_failed():
    row = whatsapp.send_whatsapp('not-a-number', 'hi', kind='t')
    assert row is not None
    assert row.status == 'failed'
    assert row.error == 'invalid_number'


@pytest.mark.django_db
@override_settings(**_CREDS)
def test_send_swallows_exception_and_marks_failed():
    with mock.patch.object(whatsapp, '_post_to_twilio', side_effect=RuntimeError('boom')):
        row = whatsapp.send_whatsapp('0123456789', 'hi', kind='t')   # must NOT raise
    assert row.status == 'failed'
    assert 'boom' in row.error


@pytest.mark.django_db
@override_settings(**_CREDS)
def test_send_uses_content_template_when_sid_given():
    sid, variables = 'HXabc123', {'1': 'Priya', '2': 'Mon 23 Jun, 3:00pm (MYT)', '3': 'https://x'}
    with mock.patch.object(whatsapp, '_post_to_twilio', return_value=('SM9', 'queued', '')) as m:
        row = whatsapp.send_whatsapp('012-345 6789', kind='interview_reminder_1day',
                                     content_sid=sid, content_variables=variables)
    assert row.status == 'queued' and row.provider_sid == 'SM9'
    # _post_to_twilio args = (sid, token, sender, to_e164, body, content_sid, content_variables)
    args = m.call_args[0]
    assert args[5] == sid and args[6] == variables
    assert 'template' in row.body  # audit row records a template marker, not free text


# --- Twilio Verify (S4 / TD-136) -------------------------------------------------------
_VERIFY = dict(TWILIO_ACCOUNT_SID='AC_test', TWILIO_AUTH_TOKEN='tok_test',
               TWILIO_VERIFY_SERVICE_SID='VA_test')


def test_verify_configured_flag():
    with override_settings(**_VERIFY):
        assert whatsapp.verify_configured() is True
    with override_settings(TWILIO_VERIFY_SERVICE_SID=''):
        assert whatsapp.verify_configured() is False


def test_verify_start_unconfigured():
    with override_settings(TWILIO_ACCOUNT_SID='AC', TWILIO_AUTH_TOKEN='t',
                           TWILIO_VERIFY_SERVICE_SID=''):
        ok, st, _ = whatsapp.start_phone_verification('0123456789')
    assert ok is False and st == 'unconfigured'


@override_settings(**_VERIFY)
def test_verify_start_bad_number():
    ok, st, _ = whatsapp.start_phone_verification('abc')
    assert ok is False and st == 'invalid_number'


@override_settings(**_VERIFY)
def test_verify_start_sends_normalised_whatsapp():
    with mock.patch.object(whatsapp, '_post_to_verify', return_value={'status': 'pending'}) as m:
        ok, st, _ = whatsapp.start_phone_verification('012-345 6789')
    assert ok is True and st == 'pending'
    fields = m.call_args[0][3]                       # (url, sid, token, fields)
    assert fields['To'] == '+60123456789' and fields['Channel'] == 'whatsapp'


@override_settings(**_VERIFY)
def test_verify_check_approved():
    with mock.patch.object(whatsapp, '_post_to_verify', return_value={'status': 'approved'}) as m:
        approved, err = whatsapp.check_phone_verification('012-345 6789', ' 123456 ')
    assert approved is True and err == ''
    assert m.call_args[0][3]['Code'] == '123456'      # trimmed


@override_settings(**_VERIFY)
def test_verify_check_wrong_code():
    with mock.patch.object(whatsapp, '_post_to_verify', return_value={'status': 'pending'}):
        approved, err = whatsapp.check_phone_verification('0123456789', '000000')
    assert approved is False and err == ''


@override_settings(**_VERIFY)
def test_verify_check_expired_404_is_incorrect():
    import io
    import urllib.error
    err404 = urllib.error.HTTPError('u', 404, 'NF', {}, io.BytesIO(b'{}'))
    with mock.patch.object(whatsapp, '_post_to_verify', side_effect=err404):
        approved, err = whatsapp.check_phone_verification('0123456789', '123456')
    assert approved is False and err == 'incorrect'


@override_settings(**_VERIFY)
def test_verify_check_swallows_error():
    with mock.patch.object(whatsapp, '_post_to_verify', side_effect=RuntimeError('boom')):
        approved, err = whatsapp.check_phone_verification('0123456789', '123456')  # must NOT raise
    assert approved is False and err == 'failed'


def _twilio_sig(url, params, token):
    """Re-create Twilio's X-Twilio-Signature for a test POST (url + sorted key+value, HMAC-SHA1, b64)."""
    payload = url + ''.join(f'{k}{params[k]}' for k in sorted(params.keys()))
    return base64.b64encode(hmac.new(token.encode(), payload.encode('utf-8'), hashlib.sha1).digest()).decode()


@override_settings(ROOT_URLCONF='halatuju.urls', TWILIO_AUTH_TOKEN='tok_test')
class WhatsAppInboundWebhookTests(TestCase):
    """Twilio inbound webhook honours STOP/START → whatsapp_opt_in (TD-135)."""
    URL = '/api/v1/scholarship/whatsapp/inbound/'
    TOKEN = 'tok_test'
    NUMBER = '+60123456789'

    def setUp(self):
        self.client = APIClient()
        self.cohort = ScholarshipCohort.objects.create(code='wi', name='B40', year=2026)
        self.profile = StudentProfile.objects.create(
            supabase_user_id='wi-stud', nric='030101-14-7777', name='Devi')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='interviewing')
        # A prior outbound message maps the number back to this profile (to_number is normalised).
        WhatsAppMessage.objects.create(
            application=self.app, to_number=self.NUMBER, kind='interview_reminder_1day', status='sent')

    def _post(self, body, from_number=None, sig=None):
        params = {'Body': body, 'From': from_number or f'whatsapp:{self.NUMBER}'}
        url = 'http://testserver' + self.URL
        signature = sig if sig is not None else _twilio_sig(url, params, self.TOKEN)
        return self.client.post(self.URL, params, HTTP_X_TWILIO_SIGNATURE=signature)

    def test_stop_opts_out(self):
        self.assertTrue(self.profile.whatsapp_opt_in)            # default on
        resp = self._post('STOP')
        self.assertEqual(resp.status_code, 200)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.whatsapp_opt_in)

    def test_start_opts_back_in(self):
        self.profile.whatsapp_opt_in = False
        self.profile.save(update_fields=['whatsapp_opt_in'])
        self._post('START')
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.whatsapp_opt_in)

    def test_bad_signature_rejected_and_no_change(self):
        resp = self._post('STOP', sig='not-a-valid-signature')
        self.assertEqual(resp.status_code, 403)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.whatsapp_opt_in)            # untouched

    def test_unknown_number_is_a_noop_200(self):
        resp = self._post('STOP', from_number='whatsapp:+60999999999')
        self.assertEqual(resp.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.whatsapp_opt_in)

    def test_non_keyword_ignored(self):
        resp = self._post('hello, is anyone there?')
        self.assertEqual(resp.status_code, 200)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.whatsapp_opt_in)
