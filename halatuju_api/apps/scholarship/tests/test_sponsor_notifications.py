"""F3 — sponsor notifications: real-time alerts + weekly digests.

Load-bearing assertions: the email body leaks NO student identity (it's built from
the allowlist serializer), 'off' sponsors get nothing, real-time is batched (one
email per sponsor for a batch, not one per student) and idempotent, and the
preference endpoint validates the frequency.
"""
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scholarship import pool
from apps.scholarship import sponsor_notifications as notif
from apps.scholarship.models import (
    ScholarshipCohort, Sponsor, SponsorProfile,
)
from .test_sponsor_pool import IDENTIFIERS, TEST_JWT_SECRET, _make_eligible_app, _token


def _sponsor(uid, freq, *, status='approved', last_digest_sent_at=None):
    return Sponsor.objects.create(
        supabase_user_id=uid, name=f'S {uid}', email=f'{uid}@spon.example',
        phone='0123', source='friend', consent_at=timezone.now(), status=status,
        notify_frequency=freq, last_digest_sent_at=last_digest_sent_at)


def _publish_now(app):
    """Stamp the eligible app's anon profile as published just now (the fixture
    sets anon_published but not the timestamp the digest window needs)."""
    SponsorProfile.objects.filter(application=app).update(anon_published_at=timezone.now())


def _identity_free(msg):
    blob = f'{msg.subject}\n{msg.body}'
    return all(v not in blob for v in IDENTIFIERS.values())


class TestSponsorRealtime(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        mail.outbox = []

    def test_batched_one_email_then_idempotent(self):
        a1 = _make_eligible_app(self.cohort, suffix='1'); _publish_now(a1)
        a2 = _make_eligible_app(self.cohort, suffix='2'); _publish_now(a2)
        _sponsor('rt', 'realtime')
        res = notif.send_sponsor_realtime()
        self.assertEqual(res['students'], 2)
        self.assertEqual(res['sent'], 1)              # ONE batched email, not one per student
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn(pool.pool_ref(a1.id), body)     # both anonymised refs in the one email
        self.assertIn(pool.pool_ref(a2.id), body)
        # second run sends nothing — the batch was stamped realtime_notified_at
        mail.outbox = []
        self.assertEqual(notif.send_sponsor_realtime()['students'], 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_leaks_no_identity(self):
        a = _make_eligible_app(self.cohort); _publish_now(a)
        _sponsor('rt', 'realtime')
        notif.send_sponsor_realtime()
        self.assertTrue(_identity_free(mail.outbox[0]))

    def test_off_sponsor_gets_nothing_but_batch_is_stamped(self):
        a = _make_eligible_app(self.cohort); _publish_now(a)
        _sponsor('off', 'off')
        res = notif.send_sponsor_realtime()
        self.assertEqual(res['sent'], 0)
        self.assertEqual(len(mail.outbox), 0)
        a.sponsor_profile.refresh_from_db()
        self.assertIsNotNone(a.sponsor_profile.realtime_notified_at)  # one real-time cycle, regardless of audience

    def test_pending_sponsor_excluded(self):
        a = _make_eligible_app(self.cohort); _publish_now(a)
        _sponsor('rt', 'realtime', status='pending')
        res = notif.send_sponsor_realtime()
        self.assertEqual(res['sponsors'], 0)
        self.assertEqual(len(mail.outbox), 0)


class TestSponsorDigests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        mail.outbox = []

    def test_digest_sends_then_advances_clock(self):
        a = _make_eligible_app(self.cohort); _publish_now(a)
        s = _sponsor('wk', 'weekly')
        res = notif.send_sponsor_digests()
        self.assertEqual(res['sent'], 1)
        self.assertEqual(len(mail.outbox), 1)
        s.refresh_from_db()
        self.assertIsNotNone(s.last_digest_sent_at)
        # nothing new since → second run is silent (no empty digest)
        mail.outbox = []
        self.assertEqual(notif.send_sponsor_digests()['sent'], 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_leaks_no_identity(self):
        a = _make_eligible_app(self.cohort); _publish_now(a)
        _sponsor('wk', 'weekly')
        notif.send_sponsor_digests()
        self.assertTrue(_identity_free(mail.outbox[0]))

    def test_only_weekly_sponsors_counted(self):
        a = _make_eligible_app(self.cohort); _publish_now(a)
        _sponsor('off', 'off'); _sponsor('rt', 'realtime')
        res = notif.send_sponsor_digests()
        self.assertEqual(res['sponsors'], 0)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorNotificationPref(TestCase):
    @classmethod
    def setUpTestData(cls):
        Sponsor.objects.create(supabase_user_id='spon', name='S', email='s@x.com',
                               phone='0123', source='friend', consent_at=timezone.now(),
                               status='approved')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("spon", "x@x.com")}')

    def test_patch_sets_frequency(self):
        r = self.client.patch('/api/v1/sponsor/notifications/', {'notify_frequency': 'realtime'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['notify_frequency'], 'realtime')
        self.assertEqual(Sponsor.objects.get(supabase_user_id='spon').notify_frequency, 'realtime')

    def test_patch_rejects_bad_value(self):
        r = self.client.patch('/api/v1/sponsor/notifications/', {'notify_frequency': 'daily'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'bad_frequency')
