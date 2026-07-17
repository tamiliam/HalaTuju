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


@override_settings(FRONTEND_URL='https://halatuju.xyz')
class TestSponsorEmailContent(TestCase):
    """Part 2 — the reworked mini-card emails: HTML+text pair, per-student links,
    n-aware subjects with a standout hook, and no '—'/empty-line fallbacks."""

    def setUp(self):
        mail.outbox = []

    def _card(self, **over):
        c = {
            'id': 42, 'ref': 'S-ABC123', 'state': 'Perak', 'field': 'engineering',
            'course': 'Diploma Kejuruteraan Mekanikal', 'academic': 'SPM · 7A 1B',
            'institution': 'Politeknik Ungku Omar', 'blurb': 'A determined leaver.',
            'funding_categories': ['tuition'], 'programme_months': 24, 'award_amount': '3000',
            'progress_state': None, 'support_status': None, 'enrolment_verified': True,
            'field_image_slug': 'kejuruteraan', 'reporting_date': '2099-09-01',
        }
        c.update(over)
        return c

    def _last(self):
        msg = mail.outbox[-1]
        html = msg.alternatives[0][0] if msg.alternatives else ''
        return msg, html

    def test_html_and_text_pair_with_per_student_link(self):
        from apps.scholarship.emails import send_sponsor_digest_email
        send_sponsor_digest_email('s@x.com', [self._card()], lang='en', name='Aisha')
        msg, html = self._last()
        self.assertTrue(html, 'HTML alternative present')
        # per-student link in BOTH parts
        link = 'https://halatuju.xyz/sponsor/students/42'
        self.assertIn(link, msg.body)
        self.assertIn(link, html)
        # programme (never the raw field key), amount (RM2,000 format), artwork thumbnail
        self.assertIn('Diploma Kejuruteraan Mekanikal', msg.body)
        self.assertIn('RM3,000', msg.body)                 # whole ringgit, thousands-grouped
        self.assertNotIn('RM 3000', msg.body)              # not the raw "RM 3000"
        self.assertNotIn('Perak', msg.body)                # state dropped from the card line
        self.assertIn('Politeknik Ungku Omar', msg.body)   # institution still shown
        self.assertIn('field-images/kejuruteraan.png', html)
        # greeting carries the sponsor's name
        self.assertIn('Aisha', msg.body)
        # no '—' placeholder anywhere (the rework dropped the em-dash separator too)
        self.assertNotIn('—', msg.body)

    def test_singular_vs_plural_subject(self):
        from apps.scholarship.emails import send_sponsor_new_student_email
        send_sponsor_new_student_email('s@x.com', [self._card()], lang='en')
        self.assertIn('A new student', mail.outbox[-1].subject)
        self.assertNotIn('student(s)', mail.outbox[-1].subject)
        mail.outbox = []
        send_sponsor_new_student_email('s@x.com', [self._card(), self._card(id=2, ref='S-2')], lang='en')
        self.assertIn('2 new students', mail.outbox[-1].subject)

    def test_standout_hook_picks_best_academic(self):
        from apps.scholarship.emails import send_sponsor_digest_email
        cards = [
            self._card(id=1, ref='S-1', academic='SPM · 3A', state='Johor'),
            self._card(id=2, ref='S-2', academic='SPM · 9A', state='Perak'),  # standout
            self._card(id=3, ref='S-3', academic='SPM · 5A', state='Kedah'),
        ]
        send_sponsor_digest_email('s@x.com', cards, lang='en')
        subj = mail.outbox[-1].subject
        self.assertIn('SPM · 9A', subj)
        self.assertIn('Perak', subj)

    def test_empty_fields_no_dash_no_empty_lines(self):
        from apps.scholarship.emails import send_sponsor_digest_email
        # No course → falls back to the field's taxonomy display name (not the raw key);
        # no institution/state → the location line is omitted, not rendered as '—'.
        from apps.courses.models import FieldTaxonomy
        FieldTaxonomy.objects.create(key='zz_x', name_en='Widgetry', name_ms='Widget',
                                     name_ta='விட்செட்', image_slug='umum-kemanusiaan')
        card = self._card(course='', field='zz_x', institution='', state='',
                          award_amount=None, reporting_date=None, blurb='', field_image_slug='')
        send_sponsor_digest_email('s@x.com', [card], lang='en')
        msg, html = self._last()
        self.assertNotIn('—', msg.body)
        self.assertNotIn('\n\n\n', msg.body)          # no doubled blank lines from omitted facts
        self.assertIn('Widgetry', msg.body)           # taxonomy display name, never 'zz_x'
        self.assertNotIn('zz_x', msg.body)
        self.assertNotIn('<img', html)                # empty slug → no thumbnail

    def test_all_three_languages_render(self):
        from apps.scholarship.emails import send_sponsor_digest_email
        for lang in ('en', 'ms', 'ta'):
            mail.outbox = []
            self.assertTrue(send_sponsor_digest_email('s@x.com', [self._card()], lang=lang))
            msg, html = self._last()
            self.assertTrue(msg.subject and msg.body and html)


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
