"""Tests for the outbound WhatsApp comms helper (Sprint 1)."""
from unittest import mock

import pytest
from django.test import override_settings

from apps.scholarship import whatsapp
from apps.scholarship.models import WhatsAppMessage

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
