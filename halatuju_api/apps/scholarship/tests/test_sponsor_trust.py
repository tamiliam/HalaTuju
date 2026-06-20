"""R5 — Trust & Transparency hub + the enrolment-verified badge.

The hub content is programme-level (no PII); the ``enrolment_verified`` badge is a
BARE boolean on the allowlist card — never the verifier or the evidence. Both are
flag + approval gated.
"""
import json
from decimal import Decimal

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship import trust as trust_service
from apps.scholarship.serializers import SponsorPoolCardSerializer
from apps.scholarship.models import (
    Consent, ScholarshipApplication, ScholarshipCohort, Sponsor, SponsorProfile,
    TrustContent,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADULT_NRIC = '000101-10-1233'


def _token(uid, email='x@x.com'):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
         'email': email, 'is_anonymous': False},
        TEST_JWT_SECRET, algorithm='HS256')


def _eligible_app(cohort, *, suffix='1', verified=False):
    profile = StudentProfile.objects.create(
        supabase_user_id=f'stu-{suffix}', name='Zxq Student', nric=ADULT_NRIC,
        preferred_state='Kedah', exam_type='spm', grades={'bm': 'A'},
        school='SMK Rahsia', contact_email='student@secret.example',
        contact_phone='012-7776666')
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='accepted', award_amount=Decimal('3000'),
        enrolment_verified=verified, notify_email='student@secret.example')
    SponsorProfile.objects.create(application=app, anon_markdown='Determined.', anon_published=True)
    Consent.objects.create(application=app, consent_type='share_with_sponsors', version='e', is_active=True)
    return app


def _sponsor(uid='spon-1', status='approved'):
    return Sponsor.objects.create(
        supabase_user_id=uid, name='Jane Sponsor', email='jane@sponsor.example',
        phone='0123', source='friend', consent_at=timezone.now(), status=status)


class TestTrustContentService(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_seeded_row_drives_illustrative_content(self):
        # The migration seeds one active illustrative row.
        self.assertTrue(TrustContent.objects.filter(is_active=True).exists())
        c = trust_service.get_trust_content()
        for k in ('legal_entity', 'contact_email', 'trustees', 'sources', 'uses',
                  'assurance', 'figures_are_illustrative', 'community'):
            self.assertIn(k, c)
        self.assertTrue(c['figures_are_illustrative'])
        # placeholder org — not yet formalised
        self.assertEqual(c['legal_entity'], '')
        self.assertEqual(c['trustees'], [])
        # illustrative figures present (shape conveyed) + live community counts
        self.assertTrue(c['sources'] and c['uses'])
        for k in ('sponsors', 'students_supported', 'students_waiting'):
            self.assertIn(k, c['community'])

    def test_active_row_edits_show_without_a_deploy(self):
        # Editing the DB row (no code change) flows straight through.
        TrustContent.objects.update(legal_entity='Yayasan Demo (PPM-000-00)',
                                    figures_are_illustrative=False)
        c = trust_service.get_trust_content()
        self.assertEqual(c['legal_entity'], 'Yayasan Demo (PPM-000-00)')
        self.assertFalse(c['figures_are_illustrative'])

    def test_default_when_no_active_row(self):
        TrustContent.objects.update(is_active=False)
        c = trust_service.get_trust_content()
        self.assertEqual(c['legal_entity'], '')
        self.assertTrue(c['figures_are_illustrative'])
        self.assertIn('community', c)


class TestEnrolmentVerifiedBadge(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_badge_is_a_bare_boolean_and_leaks_nothing(self):
        app = _eligible_app(self.cohort, verified=True)
        data = SponsorPoolCardSerializer(app).data
        self.assertIs(data['enrolment_verified'], True)
        # allowlist-safe: still no identity, even with the new field
        blob = json.dumps(data, default=str)
        for v in ('Zxq Student', ADULT_NRIC, 'student@secret.example',
                  '012-7776666', 'SMK Rahsia'):
            self.assertNotIn(v, blob, 'identity leaked on the trust card')

    def test_badge_defaults_false(self):
        app = _eligible_app(self.cohort, suffix='2', verified=False)
        self.assertIs(SponsorPoolCardSerializer(app).data['enrolment_verified'], False)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestSponsorTrustEndpoint(TestCase):
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
    def test_trust_shape(self):
        self._auth('spon-ok')
        r = self.client.get('/api/v1/sponsor/trust/')
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        for k in ('sources', 'uses', 'assurance', 'trustees',
                  'figures_are_illustrative', 'community'):
            self.assertIn(k, body)

    @override_settings(SPONSOR_POOL_ENABLED=True)
    def test_pending_forbidden(self):
        self._auth('spon-pending')
        self.assertEqual(self.client.get('/api/v1/sponsor/trust/').status_code, 403)

    @override_settings(SPONSOR_POOL_ENABLED=False)
    def test_404_when_flag_off(self):
        self._auth('spon-ok')
        self.assertEqual(self.client.get('/api/v1/sponsor/trust/').status_code, 404)
