"""R3 — My Giving activity feed + community stats.

The feed is synthesised from existing models (no event-log table) and is
allowlist-safe: each event carries only the anonymous ``ref`` + type + time. The
community stats are programme-wide counts. Both are flag + approval gated.
"""
import json
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship import in_programme
from apps.scholarship import sponsor_feed
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Consent, Donation, GraduationMessage, ScholarshipApplication, ScholarshipCohort,
    Sponsor, SponsorProfile,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADULT_NRIC = '000101-10-1233'


def _token(uid, email='x@x.com'):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
         'email': email, 'is_anonymous': False},
        TEST_JWT_SECRET, algorithm='HS256')


def _fundable_app(cohort, *, suffix='1', award=Decimal('3000')):
    profile = StudentProfile.objects.create(
        supabase_user_id=f'stu-{suffix}', name='Zxq Student', nric=ADULT_NRIC,
        preferred_state='Kedah', exam_type='spm', grades={'bm': 'A'},
        contact_email='student@secret.example', contact_phone='012-7776666')
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='recommended', award_amount=award,
        notify_email='student@secret.example')
    SponsorProfile.objects.create(application=app, anon_markdown='Determined.', anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
    return app


def _sponsor(uid='spon-1', status='approved'):
    return Sponsor.objects.create(
        supabase_user_id=uid, name='Jane Sponsor', email='jane@sponsor.example',
        phone='0123', source='friend', consent_at=timezone.now(), status=status)


def _fund_accept(sponsor, app):
    svc.fund_student(sponsor, app)
    return svc.respond_to_award(app, action='accept')


class TestSponsorActivityService(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_activity_collects_lifecycle_events_newest_first(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('10000'))
        app = _fundable_app(self.cohort)
        _fund_accept(s, app)                                            # funded + accepted
        in_programme.record_semester_result(app, semester='1', cgpa=Decimal('3.5'))   # semester
        in_programme.record_semester_result(app, semester='2', cgpa=Decimal('3.9'), graduated=True)  # graduated
        GraduationMessage.objects.create(
            application=app, raw_text='thank you', scrubbed_text='thank you',
            status='approved', reviewed_at=timezone.now())             # thank_you

        events = sponsor_feed.sponsor_activity(s)
        types = {e['type'] for e in events}
        self.assertEqual(types, {'funded', 'accepted', 'semester', 'graduated', 'thank_you'})
        # newest first
        ats = [e['at'] for e in events]
        self.assertEqual(ats, sorted(ats, reverse=True))
        # anonymous ref, no identity
        blob = json.dumps(events, default=str)
        for v in ('Zxq Student', ADULT_NRIC, 'student@secret.example'):
            self.assertNotIn(v, blob, 'student identity leaked to sponsor')
        self.assertTrue(all(e['ref'].startswith('S-') for e in events))

    def test_activity_empty_for_new_sponsor(self):
        self.assertEqual(sponsor_feed.sponsor_activity(_sponsor('spon-empty')), [])


class TestCommunityStats(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_community_counts(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        app = _fundable_app(self.cohort)
        _fund_accept(s, app)                       # one active sponsorship → 1 supported
        _fundable_app(self.cohort, suffix='wait')  # a second student stays in the pool

        stats = sponsor_feed.community_stats()
        self.assertGreaterEqual(stats['sponsors'], 1)
        self.assertEqual(stats['students_supported'], 1)
        self.assertEqual(stats['students_waiting'], 1)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorFeedEndpoints(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        _sponsor('spon-ok')
        _sponsor('spon-pending', status='pending')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_activity_and_community_shape(self):
        self._auth('spon-ok')
        a = self.client.get('/api/v1/sponsor/activity/')
        self.assertEqual(a.status_code, 200, a.content)
        self.assertIn('events', a.json())
        c = self.client.get('/api/v1/sponsor/community/')
        self.assertEqual(c.status_code, 200, c.content)
        for k in ('sponsors', 'students_supported', 'students_waiting'):
            self.assertIn(k, c.json())

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_pending_forbidden(self):
        self._auth('spon-pending')
        self.assertEqual(self.client.get('/api/v1/sponsor/activity/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/sponsor/community/').status_code, 403)

    @override_settings(SPONSOR_POOL_ENABLED=False)
    def test_404_when_flag_off(self):
        self._auth('spon-ok')
        self.assertEqual(self.client.get('/api/v1/sponsor/activity/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/sponsor/community/').status_code, 404)
