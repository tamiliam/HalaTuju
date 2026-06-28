"""R4 — the giving statement's two ledgers (donations-in vs gifts-out).

Allowlist-safe: gifts carry the anonymous ref only. Flag + approval gated.
"""
import json
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    Consent, Donation, ScholarshipApplication, ScholarshipCohort,
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


class TestSponsorStatementService(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_statement_two_ledgers(self):
        s = _sponsor()
        Donation.objects.create(sponsor=s, amount=Decimal('5000'), reference='DN-1')
        Donation.objects.create(sponsor=s, amount=Decimal('3000'), reference='DN-2')
        app = _fundable_app(self.cohort, award=Decimal('2500'))
        svc.fund_student(s, app)
        svc.respond_to_award(app, action='accept')   # → active gift of 2500

        st = svc.sponsor_statement(s)
        self.assertEqual(len(st['donations']), 2)
        self.assertEqual(Decimal(st['total_in']), Decimal('8000'))
        self.assertEqual(len(st['gifts']), 1)
        self.assertEqual(Decimal(st['total_out']), Decimal('2500'))
        self.assertTrue(st['gifts'][0]['ref'].startswith('S-'))
        # no identity in the gifts ledger
        blob = json.dumps(st, default=str)
        for v in ('Zxq Student', ADULT_NRIC, 'student@secret.example'):
            self.assertNotIn(v, blob, 'student identity leaked to sponsor')

    def test_statement_empty(self):
        st = svc.sponsor_statement(_sponsor('spon-empty'))
        self.assertEqual(st['donations'], [])
        self.assertEqual(st['gifts'], [])
        self.assertEqual(Decimal(st['total_in']), Decimal('0'))
        self.assertEqual(Decimal(st['total_out']), Decimal('0'))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorStatementEndpoint(TestCase):
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
    def test_shape(self):
        self._auth('spon-ok')
        r = self.client.get('/api/v1/sponsor/statement/')
        self.assertEqual(r.status_code, 200, r.content)
        for k in ('donations', 'gifts', 'total_in', 'total_out'):
            self.assertIn(k, r.json())

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_pending_forbidden(self):
        self._auth('spon-pending')
        self.assertEqual(self.client.get('/api/v1/sponsor/statement/').status_code, 403)

    @override_settings(SPONSOR_POOL_ENABLED=False)
    def test_404_when_flag_off(self):
        self._auth('spon-ok')
        self.assertEqual(self.client.get('/api/v1/sponsor/statement/').status_code, 404)
