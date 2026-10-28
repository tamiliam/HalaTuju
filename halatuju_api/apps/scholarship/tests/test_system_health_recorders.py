"""The System health light's recorders (2026-10-28): the mail backend and the cron runner write what
they saw, and NEITHER can ever break the send or the run it is watching. No address, ever."""
import smtplib
from unittest.mock import patch

from django.core.mail import EmailMessage
from django.test import TestCase, override_settings

from apps.scholarship import cron_health
from apps.scholarship import system_health_store as store
from apps.scholarship.mail_backend import RecordingSMTPBackend
from apps.scholarship.models import SystemHealthStatus


def _data(key):
    row = SystemHealthStatus.objects.filter(key=key).first()
    return row.data if row else None


class _Base(TestCase):
    def setUp(self):
        store._since_seen = False


class StoreWrites(_Base):
    def test_waits_for_the_callers_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            store.record_email(True)
        self.assertIsNone(_data(store.EMAIL_KEY))          # nothing written inside the transaction
        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        self.assertIn('last_ok_at', _data(store.EMAIL_KEY))

    def test_failures_count_up_and_a_success_resets(self):
        with self.captureOnCommitCallbacks(execute=True):
            store.record_email(False, 'SMTPServerDisconnected')
            store.record_email(False, 'SMTPServerDisconnected')
        self.assertEqual(_data(store.EMAIL_KEY)['consecutive_failures'], 2)
        self.assertEqual(_data(store.EMAIL_KEY)['last_error'], 'SMTPServerDisconnected')
        with self.captureOnCommitCallbacks(execute=True):
            store.record_email(True)
        self.assertEqual(_data(store.EMAIL_KEY)['consecutive_failures'], 0)

    def test_the_first_write_stamps_since(self):
        with self.captureOnCommitCallbacks(execute=True):
            store.record_cron('query-emails', True)
        self.assertIn('at', _data(store.SINCE_KEY))
        first = _data(store.SINCE_KEY)['at']
        store._since_seen = False
        with self.captureOnCommitCallbacks(execute=True):
            store.record_cron('query-emails', True)
        self.assertEqual(_data(store.SINCE_KEY)['at'], first)   # never moved forward

    def test_a_broken_store_never_raises(self):
        with patch.object(store, '_apply', side_effect=RuntimeError('no such table')):
            with self.captureOnCommitCallbacks(execute=True):
                store.record_email(False, 'X')
                store.record_cron('query-emails', False, 'X')
        with patch('django.db.transaction.on_commit', side_effect=RuntimeError('boom')):
            store.record_email(True)                       # scheduling failure is swallowed too

    def test_a_broken_read_degrades_to_nothing(self):
        with patch.object(SystemHealthStatus.objects, 'all', side_effect=RuntimeError('no table')):
            self.assertEqual(store.load_all(), {})


class _FakeConnection:
    def __init__(self, error=None):
        self.error = error

    def sendmail(self, *a, **kw):
        if self.error:
            raise self.error
        return {}


class MailBackend(_Base):
    def backend(self, error=None, fail_silently=False):
        b = RecordingSMTPBackend(fail_silently=fail_silently)
        b.open = lambda: False                          # no network: use the fake below
        b.close = lambda: None
        b.connection = _FakeConnection(error)
        return b

    def message(self):
        return EmailMessage('Private subject', 'Private body', 'noreply@halatuju.xyz',
                            ['student.private@example.test'])

    def test_a_delivered_send_is_recorded_ok(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.backend().send_messages([self.message()]), 1)
        self.assertIn('last_ok_at', _data(store.EMAIL_KEY))

    def test_a_failed_send_still_raises_and_is_recorded_without_pii(self):
        err = smtplib.SMTPRecipientsRefused({'student.private@example.test': (550, b'no')})
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(smtplib.SMTPRecipientsRefused):
                self.backend(err).send_messages([self.message()])
        data = _data(store.EMAIL_KEY)
        self.assertEqual(data['last_error'], 'SMTPRecipientsRefused')
        self.assertEqual(data['consecutive_failures'], 1)
        text = str(data)
        for secret in ('student.private', 'example.test', 'Private subject', 'Private body'):
            self.assertNotIn(secret, text)

    def test_a_silenced_failure_returns_as_before_and_counts_as_failed(self):
        with self.captureOnCommitCallbacks(execute=True):
            sent = self.backend(smtplib.SMTPServerDisconnected('x'), fail_silently=True).send_messages(
                [self.message()])
        self.assertEqual(sent, 0)
        self.assertEqual(_data(store.EMAIL_KEY)['consecutive_failures'], 1)

    def test_a_message_with_no_recipients_is_neither_success_nor_failure(self):
        nobody = EmailMessage('s', 'b', 'noreply@halatuju.xyz', [])
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.backend().send_messages([nobody]), 0)
        self.assertIsNone(_data(store.EMAIL_KEY))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.backend().send_messages([nobody, self.message()]), 1)
        self.assertEqual(_data(store.EMAIL_KEY)['consecutive_failures'], 0)   # 1 of 1 addressed went

    def test_failure_times_are_kept_newest_first_and_capped(self):
        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(12):
                store.record_email(False, 'X')
        recent = _data(store.EMAIL_KEY)['recent_failures']
        self.assertEqual(len(recent), 10)
        self.assertEqual(recent, sorted(recent, reverse=True))

    def test_nothing_to_send_records_nothing(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.backend().send_messages([])
        self.assertIsNone(_data(store.EMAIL_KEY))

    def test_a_broken_store_never_breaks_a_send(self):
        with patch.object(store, '_apply', side_effect=RuntimeError('no such table')):
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.backend().send_messages([self.message()]), 1)

    def test_production_uses_it(self):
        from pathlib import Path
        from django.conf import settings
        text = (Path(settings.BASE_DIR) / 'halatuju' / 'settings' / 'production.py').read_text(encoding='utf-8')
        self.assertIn("EMAIL_BACKEND = 'apps.scholarship.mail_backend.RecordingSMTPBackend'", text)


@override_settings(ROOT_URLCONF='halatuju.urls', CRON_SECRET='test-cron-secret')
class CronRecorder(_Base):
    def test_a_good_run_is_recorded(self):
        with patch.object(cron_health, 'call_command'):
            with self.captureOnCommitCallbacks(execute=True):
                body = cron_health.run_job('query-emails', 'send_due_query_emails', [])
        self.assertEqual(body['job'], 'query-emails')
        data = _data('cron:query-emails')
        self.assertEqual(data['consecutive_errors'], 0)
        self.assertIn('last_ok_at', data)

    def test_a_failed_run_is_recorded_by_class_name_and_still_answers(self):
        with patch.object(cron_health, 'call_command', side_effect=ValueError('row 12 for x@y.z')):
            with self.captureOnCommitCallbacks(execute=True):
                body = cron_health.run_job('query-emails', 'send_due_query_emails', [])
                cron_health.run_job('query-emails', 'send_due_query_emails', [])
        self.assertIn('error', body)
        data = _data('cron:query-emails')
        self.assertEqual((data['consecutive_errors'], data['last_error']), (2, 'ValueError'))
        self.assertNotIn('x@y.z', str(data))

    def test_the_endpoint_records_and_answers_200(self):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post('/api/v1/internal/cron/vision-outage/',
                                 HTTP_X_CRON_SECRET='test-cron-secret')
        self.assertEqual(r.status_code, 200)
        self.assertIn('output', r.json())
        self.assertIn('last_ok_at', _data('cron:vision-outage'))

    def test_a_broken_store_never_breaks_a_run(self):
        with patch.object(store, '_apply', side_effect=RuntimeError('no such table')):
            with self.captureOnCommitCallbacks(execute=True):
                r = self.client.post('/api/v1/internal/cron/vision-outage/',
                                     HTTP_X_CRON_SECRET='test-cron-secret')
        self.assertEqual(r.status_code, 200)
        self.assertIn('output', r.json())
