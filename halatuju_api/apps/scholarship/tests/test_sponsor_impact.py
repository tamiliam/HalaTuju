"""R2 — My Giving dashboard: the impact aggregate + the journey signals.

`sponsor_impact` is counts + money only (allowlist-safe — no student identity), and
the sponsorship serializer carries the non-identifying `onboarded`/`semesters` signals
the FE derives the journey tracker from. The endpoint is flag + approval gated.
"""
import json
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship import in_programme
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Consent, Donation, ScholarshipApplication, ScholarshipCohort,
    Sponsor, SponsorProfile,
)
from apps.scholarship.serializers import SponsorSponsorshipSerializer

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


class TestSponsorImpactService(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_impact_aggregates_committed_completed_and_semesters(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('10000'))
        # Student A — ongoing, two semesters recorded.
        a = _fundable_app(self.cohort, suffix='a', award=Decimal('2500'))
        _fund_accept(s, a)
        in_programme.record_semester_result(a, semester='1', cgpa=Decimal('3.5'))
        in_programme.record_semester_result(a, semester='2', cgpa=Decimal('3.6'))
        # Student B — graduated (latest result marks graduation).
        b = _fundable_app(self.cohort, suffix='b', award=Decimal('2000'))
        _fund_accept(s, b)
        in_programme.record_semester_result(b, semester='final', cgpa=Decimal('3.8'), graduated=True)

        impact = svc.sponsor_impact(s)
        self.assertEqual(impact['students_supported'], 2)
        self.assertEqual(impact['students_active'], 1)
        self.assertEqual(impact['students_graduated'], 1)
        self.assertEqual(impact['semesters_completed'], 3)
        self.assertEqual(Decimal(impact['total_given']), Decimal('4500'))
        self.assertEqual(Decimal(impact['balance']['committed']), Decimal('2500'))
        self.assertEqual(Decimal(impact['balance']['completed']), Decimal('2000'))
        # 10000 donated − 4500 held = 5500 available
        self.assertEqual(Decimal(impact['balance']['available']), Decimal('5500'))

    def test_impact_empty_for_new_sponsor(self):
        s = _sponsor('spon-empty')
        impact = svc.sponsor_impact(s)
        self.assertEqual(impact['students_supported'], 0)
        self.assertEqual(impact['students_graduated'], 0)
        self.assertEqual(impact['semesters_completed'], 0)
        self.assertEqual(Decimal(impact['total_given']), Decimal('0'))


class TestSponsorshipSerializerJourney(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_serializer_carries_onboarded_and_semesters_no_leak(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('3000'))
        app = _fundable_app(self.cohort)
        sp = _fund_accept(s, app)
        in_programme.record_semester_result(app, semester='1', cgpa=Decimal('3.0'))
        data = SponsorSponsorshipSerializer(sp).data
        self.assertEqual(data['semesters'], 1)
        self.assertFalse(data['onboarded'])   # onboarding not completed yet
        blob = json.dumps(data)
        for v in ('Zxq Student', ADULT_NRIC, 'student@secret.example', '012-7776666'):
            self.assertNotIn(v, blob, 'student identity leaked to sponsor')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorImpactEndpoint(TestCase):
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
    def test_impact_endpoint_shape(self):
        self._auth('spon-ok')
        r = self.client.get('/api/v1/sponsor/impact/')
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        for k in ('total_given', 'students_supported', 'students_active',
                  'students_graduated', 'semesters_completed', 'balance'):
            self.assertIn(k, body)
        for k in ('committed', 'completed', 'available'):
            self.assertIn(k, body['balance'])

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_pending_sponsor_forbidden(self):
        self._auth('spon-pending')
        self.assertEqual(self.client.get('/api/v1/sponsor/impact/').status_code, 403)

    @override_settings(SPONSOR_POOL_ENABLED=False)
    def test_404_when_flag_off(self):
        self._auth('spon-ok')
        self.assertEqual(self.client.get('/api/v1/sponsor/impact/').status_code, 404)
