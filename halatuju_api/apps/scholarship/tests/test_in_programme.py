"""B40 Phase E/F (F9a) — in-programme student lifecycle.

Covers the three new surfaces and their load-bearing guarantees:
  - semester results gate on in-programme status + validate CGPA;
  - promotional_use consent enforces 18+ server-side (NO guardian path);
  - the graduation relay BLOCKS the student's own identifiers (structural scan),
    needs staff approval, and the SPONSOR-facing relay leaks nothing identifying.

All synthetic data; no external calls.
"""
import json

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import in_programme, pool
from apps.scholarship.models import (
    ApplicantDocument, GraduationMessage, ScholarshipApplication,
    ScholarshipCohort, SemesterResult, Sponsor, Sponsorship,
)
from apps.scholarship.serializers import GraduationRelaySerializer

TEST_JWT_SECRET = 'test-supabase-jwt-secret'

# Distinctive identifiers — if any reaches a sponsor-facing payload, it leaked.
IDENT = {
    'name': 'Zxqvbn Identifiable',
    'school': 'SMK Secret Place',
    'city': 'Siretown',
    'nric': '050505-10-9991',          # born 2005 → adult in 2026
    'contact_phone': '012-9998888',
    'contact_email': 'leak@secret.example',
}
MINOR_NRIC = '101010-10-1234'          # born 2010 → 16 in 2026


def _token(uid, email=''):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated',
         'email': email, 'is_anonymous': False},
        TEST_JWT_SECRET, algorithm='HS256')


def _profile(suffix, *, nric=IDENT['nric']):
    return StudentProfile.objects.create(
        supabase_user_id=f'inprog-{suffix}',
        grades={'bm': 'A'}, exam_type='spm', preferred_state='Kedah',
        name=IDENT['name'], nric=nric, school=IDENT['school'], city=IDENT['city'],
        contact_phone=IDENT['contact_phone'], contact_email=IDENT['contact_email'],
    )


def _app(cohort, suffix, *, status='active', nric=IDENT['nric']):
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=_profile(suffix, nric=nric), status=status,
        field_of_study='engineering',
    )


class TestSemesterResults(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_record_requires_in_programme(self):
        app = _app(self.cohort, 'r1', status='recommended')  # not yet sponsored
        with self.assertRaises(in_programme.InProgrammeError) as ctx:
            in_programme.record_semester_result(app, semester='2026 S1', cgpa='3.4')
        self.assertEqual(ctx.exception.code, 'not_in_programme')

    def test_record_happy_path(self):
        app = _app(self.cohort, 'r2')
        row = in_programme.record_semester_result(app, semester='2026 S1', cgpa='3.40')
        self.assertEqual(row.application_id, app.id)
        self.assertEqual(str(row.cgpa), '3.40')

    def test_bad_cgpa_rejected(self):
        app = _app(self.cohort, 'r3')
        for bad in ('5.0', '-1', 'abc'):
            with self.assertRaises(in_programme.InProgrammeError) as ctx:
                in_programme.record_semester_result(app, cgpa=bad)
            self.assertEqual(ctx.exception.code, 'bad_cgpa')

    def test_cgpa_optional(self):
        app = _app(self.cohort, 'r4')
        row = in_programme.record_semester_result(app, semester='Pending', cgpa=None)
        self.assertIsNone(row.cgpa)


class TestPromotionalConsent(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_adult_can_grant(self):
        app = _app(self.cohort, 'p1')  # adult NRIC
        consent = in_programme.grant_promotional_consent(app)
        self.assertEqual(consent.consent_type, 'promotional_use')
        self.assertEqual(consent.granted_by, 'self')
        self.assertTrue(in_programme.has_promotional_consent(app))

    def test_minor_blocked_no_guardian_path(self):
        app = _app(self.cohort, 'p2', nric=MINOR_NRIC)
        with self.assertRaises(in_programme.InProgrammeError) as ctx:
            in_programme.grant_promotional_consent(app)
        self.assertEqual(ctx.exception.code, 'minor_not_allowed')
        self.assertFalse(in_programme.has_promotional_consent(app))

    def test_withdraw(self):
        app = _app(self.cohort, 'p3')
        in_programme.grant_promotional_consent(app)
        in_programme.withdraw_promotional_consent(app)
        self.assertFalse(in_programme.has_promotional_consent(app))

    def test_uses_bumped_version(self):
        from apps.scholarship.services import CONSENT_VERSION
        app = _app(self.cohort, 'p4')
        consent = in_programme.grant_promotional_consent(app)
        self.assertEqual(consent.version, CONSENT_VERSION)


class TestGraduationRelay(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def test_clean_message_is_pending(self):
        app = _app(self.cohort, 'g1')
        msg = in_programme.submit_graduation_message(
            app, raw_text='Thank you so much for believing in me. I graduated!')
        self.assertEqual(msg.status, 'pending')
        self.assertEqual(msg.scan_result, [])

    def test_message_with_own_name_is_blocked(self):
        app = _app(self.cohort, 'g2')
        msg = in_programme.submit_graduation_message(
            app, raw_text=f'Hi, I am {IDENT["name"]} and I just graduated, thank you!')
        self.assertEqual(msg.status, 'blocked')
        self.assertIn('name', msg.scan_result)

    def test_message_with_own_city_is_blocked(self):
        app = _app(self.cohort, 'g3')
        msg = in_programme.submit_graduation_message(
            app, raw_text=f'Greetings from {IDENT["city"]} — thank you for the support!')
        self.assertEqual(msg.status, 'blocked')
        self.assertIn('city', msg.scan_result)

    def test_empty_message_rejected(self):
        app = _app(self.cohort, 'g4')
        with self.assertRaises(in_programme.InProgrammeError) as ctx:
            in_programme.submit_graduation_message(app, raw_text='   ')
        self.assertEqual(ctx.exception.code, 'empty_message')

    def test_approve_only_pending(self):
        app = _app(self.cohort, 'g5')
        msg = in_programme.submit_graduation_message(
            app, raw_text=f'I am {IDENT["name"]}!')  # blocked
        with self.assertRaises(in_programme.InProgrammeError) as ctx:
            in_programme.approve_graduation_message(msg, by_email='staff@x.org')
        self.assertEqual(ctx.exception.code, 'not_reviewable')

    def test_approve_rescans_scrubbed_text(self):
        app = _app(self.cohort, 'g6')
        msg = in_programme.submit_graduation_message(app, raw_text='Thank you, kind stranger.')
        # A staff edit that REINTRODUCES an identifier must be refused.
        with self.assertRaises(in_programme.InProgrammeError) as ctx:
            in_programme.approve_graduation_message(
                msg, by_email='staff@x.org', scrubbed_text=f'From {IDENT["name"]}')
        self.assertEqual(ctx.exception.code, 'scrubbed_leak')

    def test_approve_happy_path(self):
        app = _app(self.cohort, 'g7')
        msg = in_programme.submit_graduation_message(app, raw_text='Thank you for everything.')
        in_programme.approve_graduation_message(msg, by_email='staff@x.org')
        msg.refresh_from_db()
        self.assertEqual(msg.status, 'approved')
        self.assertEqual(msg.scrubbed_text, 'Thank you for everything.')
        self.assertEqual(msg.approved_by, 'staff@x.org')

    def test_reject(self):
        app = _app(self.cohort, 'g8')
        msg = in_programme.submit_graduation_message(app, raw_text='Thanks.')
        in_programme.reject_graduation_message(msg, by_email='staff@x.org', review_note='spam')
        msg.refresh_from_db()
        self.assertEqual(msg.status, 'rejected')

    def test_relay_for_sponsor_only_approved_and_anonymous(self):
        app = _app(self.cohort, 'g9')
        sponsor = Sponsor.objects.create(name='S', email='s@x.org', status='approved')
        Sponsorship.objects.create(sponsor=sponsor, application=app, amount=1000, status='active')
        # one approved, one still pending → relay returns only the approved one
        approved = in_programme.submit_graduation_message(app, raw_text='Thank you deeply.')
        in_programme.approve_graduation_message(approved, by_email='staff@x.org')
        in_programme.submit_graduation_message(app, raw_text='A second note, pending.')

        relay = in_programme.approved_messages_for_sponsor(sponsor)
        self.assertEqual(len(relay), 1)
        self.assertEqual(relay[0]['ref'], pool.pool_ref(app.id))
        # The relay serializer output must carry NO identifier.
        blob = json.dumps(GraduationRelaySerializer(relay, many=True).data)
        for label, value in IDENT.items():
            self.assertNotIn(value, blob, f'{label} leaked into the graduation relay')

    def test_relay_empty_without_active_sponsorship(self):
        app = _app(self.cohort, 'g10')
        sponsor = Sponsor.objects.create(name='S', email='s2@x.org', status='approved')
        # offered (not active) → not yet a funded student
        Sponsorship.objects.create(sponsor=sponsor, application=app, amount=1000, status='offered')
        msg = in_programme.submit_graduation_message(app, raw_text='Thanks!')
        in_programme.approve_graduation_message(msg, by_email='staff@x.org')
        self.assertEqual(in_programme.approved_messages_for_sponsor(sponsor), [])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestInProgrammeEndpoints(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()

    def _auth(self, app):
        self.client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + _token(app.profile.supabase_user_id))

    def test_semester_results_post_and_list(self):
        app = _app(self.cohort, 'e1')
        self._auth(app)
        r = self.client.post(
            f'/api/v1/scholarship/applications/{app.id}/semester-results/',
            {'semester': '2026 S1', 'cgpa': '3.50'}, format='json')
        self.assertEqual(r.status_code, 201)
        r2 = self.client.get(f'/api/v1/scholarship/applications/{app.id}/semester-results/')
        self.assertEqual(len(r2.json()['results']), 1)

    def test_promo_consent_minor_400(self):
        app = _app(self.cohort, 'e2', nric=MINOR_NRIC)
        self._auth(app)
        r = self.client.post(
            f'/api/v1/scholarship/applications/{app.id}/promotional-consent/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'minor_not_allowed')

    def test_graduation_message_blocked_returns_scan(self):
        app = _app(self.cohort, 'e3')
        self._auth(app)
        r = self.client.post(
            f'/api/v1/scholarship/applications/{app.id}/graduation-message/',
            {'text': f'I am {IDENT["name"]}'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['status'], 'blocked')
        self.assertIn('name', r.json()['scan_result'])

    def test_cannot_touch_another_students_application(self):
        app = _app(self.cohort, 'e4')
        other = _app(self.cohort, 'e5')
        self._auth(other)  # authenticate as a different student
        r = self.client.post(
            f'/api/v1/scholarship/applications/{app.id}/semester-results/',
            {'cgpa': '3.0'}, format='json')
        self.assertEqual(r.status_code, 404)
