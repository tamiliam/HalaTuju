"""Billing & usage v1 — the super/org_admin usage endpoint (Sprint 13a).

Drives the REAL endpoint. Proves: flag-gated 404-first dark ship; super sees every org
plus the platform (NULL-org) row; org_admin sees ONLY its own org and NEVER the platform
row or any other org (the leak test); role refusals; exact-key payload snapshots for both
role shapes; the live document-storage snapshot; month scoping.
"""
import jwt
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort, UsageEvent,
)
from rest_framework.test import APIClient

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
URL = '/api/v1/admin/scholarship/billing/usage/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BILLING_USAGE_ENABLED=True)
class TestBillingUsageEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.month = timezone.now().strftime('%Y-%m')
        cls.a = PartnerOrganisation.objects.create(code='aa', name='Alpha Org')
        cls.b = PartnerOrganisation.objects.create(code='bb', name='Beta Org')

        cohort = ScholarshipCohort.objects.create(code='ca', name='A', year=2026,
                                                  owning_organisation=cls.a)
        prof = StudentProfile.objects.create(supabase_user_id='stud-a', nric='010101-14-0001',
                                             name='Stud A')
        cls.app_a = ScholarshipApplication.objects.create(cohort=cohort, profile=prof,
                                                          status='submitted')
        ApplicantDocument.objects.create(application=cls.app_a, doc_type='ic',
                                         storage_path=f'{cls.app_a.id}/ic/x', size=2048)

        UsageEvent.objects.create(organisation=cls.a, application=cls.app_a, service='gemini',
                                  source='doc_extract', input_tokens=100, output_tokens=40)
        UsageEvent.objects.create(organisation=cls.a, service='email', source='send_ack')
        UsageEvent.objects.create(organisation=cls.b, service='whatsapp', source='reminder')
        UsageEvent.objects.create(organisation=None, service='gemini', source='report',
                                  input_tokens=200, output_tokens=80)

        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@x.com')
        cls.org_admin_a = PartnerAdmin.objects.create(
            supabase_user_id='oa-a', role='org_admin', is_active=True,
            owning_organisation=cls.a, name='OA A', email='oa-a@x.com')
        cls.reviewer_a = PartnerAdmin.objects.create(
            supabase_user_id='rev-a', role='reviewer', is_active=True,
            owning_organisation=cls.a, name='Rev A', email='rev-a@x.com')

    def _get(self, uid, **params):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')
        return c.get(URL, params)

    # ── flag-first dark ship ────────────────────────────────────────────────
    @override_settings(BILLING_USAGE_ENABLED=False)
    def test_flag_off_is_404_even_for_super(self):
        self.assertEqual(self._get('super-uid').status_code, 404)
        self.assertEqual(self._get('oa-a').status_code, 404)

    # ── super view ──────────────────────────────────────────────────────────
    def test_super_sees_all_orgs_plus_platform(self):
        resp = self._get('super-uid')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['can_see_platform'])
        by_id = {o['organisation_id']: o for o in data['organisations']}
        self.assertIn(None, by_id)                 # platform row
        self.assertTrue(by_id[None]['is_platform'])
        self.assertIn(self.a.id, by_id)
        self.assertIn(self.b.id, by_id)

    # ── org_admin view — THE fence + leak test ────────────────────────────────
    def test_org_admin_sees_only_own_org(self):
        resp = self._get('oa-a')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['can_see_platform'])
        self.assertEqual(len(data['organisations']), 1)
        block = data['organisations'][0]
        self.assertEqual(block['organisation_id'], self.a.id)
        self.assertFalse(block['is_platform'])

    def test_org_admin_payload_leaks_no_platform_or_other_org(self):
        data = self._get('oa-a').json()
        # No platform (NULL) block, no Beta org, anywhere in the payload.
        ids = {o['organisation_id'] for o in data['organisations']}
        self.assertNotIn(None, ids)
        self.assertNotIn(self.b.id, ids)
        blob = str(data)
        self.assertNotIn('Beta Org', blob)
        self.assertNotIn('Platform', blob)

    def test_org_admin_storage_snapshot(self):
        block = self._get('oa-a').json()['organisations'][0]
        self.assertEqual(block['storage_bytes'], 2048)

    # ── role refusals ─────────────────────────────────────────────────────────
    def test_reviewer_is_forbidden(self):
        self.assertEqual(self._get('rev-a').status_code, 403)

    def test_unknown_caller_is_forbidden(self):
        self.assertEqual(self._get('nobody').status_code, 403)

    # ── input validation ──────────────────────────────────────────────────────
    def test_bad_month_is_400(self):
        self.assertEqual(self._get('super-uid', month='2026/07').status_code, 400)
        self.assertEqual(self._get('super-uid', month='July').status_code, 400)

    def test_month_param_scopes_the_data(self):
        # An event in a different month must not appear in this month's totals.
        other = '2020-01'
        ev = UsageEvent.objects.create(organisation=self.a, service='email', source='old')
        UsageEvent.objects.filter(pk=ev.pk).update(created_at='2020-01-15T00:00:00Z')
        this_month = self._get('super-uid').json()
        a_block = next(o for o in this_month['organisations'] if o['organisation_id'] == self.a.id)
        self.assertNotIn('old', [s['service'] for s in a_block['services']])
        # And the old month is listed in the available months.
        self.assertIn(other, this_month['months'])

    # ── exact-key snapshots (the allowlist contract, per role) ────────────────
    def test_super_payload_exact_keys(self):
        data = self._get('super-uid').json()
        self.assertEqual(set(data), {'month', 'months', 'can_see_platform', 'organisations'})
        block = data['organisations'][0]
        self.assertEqual(set(block), {'organisation_id', 'organisation', 'is_platform',
                                      'services', 'totals', 'storage_bytes'})
        self.assertEqual(set(block['totals']),
                         {'events', 'quantity', 'input_tokens', 'output_tokens'})
        svc = next(s for o in data['organisations'] for s in o['services'])
        self.assertEqual(set(svc), {'service', 'events', 'quantity', 'input_tokens', 'output_tokens'})

    def test_org_admin_payload_exact_keys(self):
        data = self._get('oa-a').json()
        self.assertEqual(set(data), {'month', 'months', 'can_see_platform', 'organisations'})
        block = data['organisations'][0]
        self.assertEqual(set(block), {'organisation_id', 'organisation', 'is_platform',
                                      'services', 'totals', 'storage_bytes'})
