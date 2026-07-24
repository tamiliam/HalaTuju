"""Requests space — admin endpoint tests (Sprint 15, Phase 2).

Two-org isolation + cross-org 404s, REAL 403s for the wrong roles on list/detail/one write, the
flag-off dark ship (404 on EVERY route), and the exact-key ORG-payload snapshot proving the AI
draft (ai_*) + triage never leak to an org. The AI seam is never called live (no GEMINI_API_KEY
in the test settings → the create auto-run swallows a ContractsError).
"""
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship.models import OrgRequest

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
BASE = '/api/v1/admin/scholarship/requests/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = PartnerOrganisation.objects.create(code='req-a', name='Org A')
        cls.org_b = PartnerOrganisation.objects.create(code='req-b', name='Org B')
        cls.oa_a = PartnerAdmin.objects.create(
            supabase_user_id='oa-a', role='org_admin', is_active=True,
            owning_organisation=cls.org_a, name='OrgAdmin A', email='oaa@x.com')
        cls.oa_b = PartnerAdmin.objects.create(
            supabase_user_id='oa-b', role='org_admin', is_active=True,
            owning_organisation=cls.org_b, name='OrgAdmin B', email='oab@x.com')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='sup', is_super_admin=True, is_active=True,
            name='Super', email='sup@x.com')
        # Every other B40 role, bound to org A — all must be refused (403) on the requests surface.
        for role in ('admin', 'reviewer', 'qc', 'finance'):
            PartnerAdmin.objects.create(
                supabase_user_id=f'{role}-a', role=role, is_active=True,
                owning_organisation=cls.org_a, name=role, email=f'{role}@x.com')
        PartnerAdmin.objects.create(
            supabase_user_id='partner-a', role='partner', is_active=True,
            org=cls.org_a, name='partner', email='partner@x.com')

        cls.req_a = OrgRequest.objects.create(
            organisation=cls.org_a, submitted_by=cls.oa_a, kind='feature',
            title='A feature', description='org A wants a page')
        cls.req_b = OrgRequest.objects.create(
            organisation=cls.org_b, submitted_by=cls.oa_b, kind='bug',
            title='B bug', description='org B hit a crash')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')


class TestOrgIsolation(_Base):
    def test_list_scoped_to_own_org(self):
        self._auth('oa-a')
        ids = {r['id'] for r in self.client.get(BASE).json()['requests']}
        self.assertEqual(ids, {self.req_a.id})

    def test_super_sees_all(self):
        self._auth('sup')
        ids = {r['id'] for r in self.client.get(BASE).json()['requests']}
        self.assertEqual(ids, {self.req_a.id, self.req_b.id})

    def test_cross_org_detail_404(self):
        self._auth('oa-a')
        self.assertEqual(self.client.get(f'{BASE}{self.req_b.id}/').status_code, 404)

    def test_cross_org_write_404(self):
        self._auth('oa-a')
        r = self.client.post(f'{BASE}{self.req_b.id}/defer/', {}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_own_org_detail_200(self):
        self._auth('oa-a')
        self.assertEqual(self.client.get(f'{BASE}{self.req_a.id}/').status_code, 200)


class TestRoleDenials(_Base):
    """admin / reviewer / qc / partner / finance are REAL 403s on list + detail + one write."""
    DENIED = ('admin-a', 'reviewer-a', 'qc-a', 'partner-a', 'finance-a')

    def test_list_403(self):
        for uid in self.DENIED:
            self._auth(uid)
            self.assertEqual(self.client.get(BASE).status_code, 403, uid)

    def test_detail_403(self):
        for uid in self.DENIED:
            self._auth(uid)
            self.assertEqual(self.client.get(f'{BASE}{self.req_a.id}/').status_code, 403, uid)

    def test_write_403(self):
        for uid in self.DENIED:
            self._auth(uid)
            r = self.client.post(f'{BASE}{self.req_a.id}/defer/', {}, format='json')
            self.assertEqual(r.status_code, 403, uid)

    def test_super_side_denied_to_org_admin(self):
        # The owner actions are super-only: an org_admin is 403 on triage/quote/etc.
        self._auth('oa-a')
        for verb in ('triage', 'quote', 'schedule', 'done', 'ai-rerun'):
            r = self.client.post(f'{BASE}{self.req_a.id}/{verb}/', {}, format='json')
            self.assertEqual(r.status_code, 403, verb)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=False)
class TestFlagOff(TestCase):
    """Dark ship: every route 404s while REQUESTS_ENABLED is off — even for a super."""
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='req-off', name='Off')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='oa-off', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OA', email='oa@off.com')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='sup-off', is_super_admin=True, is_active=True,
            name='S', email='s@off.com')
        cls.req = OrgRequest.objects.create(
            organisation=cls.org, submitted_by=cls.oa, kind='feature',
            title='t', description='d')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def test_every_route_404(self):
        pk = self.req.id
        gets = [BASE, f'{BASE}count/', f'{BASE}{pk}/']
        posts = [BASE, f'{BASE}{pk}/answer/', f'{BASE}{pk}/approve/', f'{BASE}{pk}/defer/',
                 f'{BASE}{pk}/modify/', f'{BASE}{pk}/decline/', f'{BASE}{pk}/triage/',
                 f'{BASE}{pk}/quote/', f'{BASE}{pk}/requote/', f'{BASE}{pk}/schedule/',
                 f'{BASE}{pk}/done/', f'{BASE}{pk}/ai-rerun/']
        for uid in ('oa-off', 'sup-off'):
            self._auth(uid)
            for url in gets:
                self.assertEqual(self.client.get(url).status_code, 404, f'{uid} GET {url}')
            for url in posts:
                self.assertEqual(self.client.post(url, {}, format='json').status_code, 404,
                                 f'{uid} POST {url}')


class TestOrgPayloadAllowlist(_Base):
    """The exact ORG-facing key set — the AI draft + triage must NEVER be in it (the single worst
    leak). A snapshot, so a new field becomes a deliberate decision, not a quiet widening."""
    ORG_KEYS = {
        'id', 'kind', 'title', 'description', 'status', 'clarifications',
        'quote_hours', 'quote_margin_pct', 'quote_note', 'quoted_at', 'approved_at',
        'scheduled_for', 'decline_reason', 'created_at', 'updated_at', 'submitted_by_name',
    }

    def test_org_detail_exact_key_set(self):
        # Give the request an AI draft + triage so a leak would actually show up.
        self.req_a.ai_draft_kind = 'feature'
        self.req_a.ai_draft_hours = 9
        self.req_a.ai_draft_note = 'secret estimate'
        self.req_a.triaged_kind = 'bug'
        self.req_a.triage_note = 'owner-only note'
        self.req_a.save()
        self._auth('oa-a')
        body = self.client.get(f'{BASE}{self.req_a.id}/').json()
        self.assertEqual(set(body), self.ORG_KEYS)

    def test_no_ai_or_triage_tokens_in_org_payload(self):
        self.req_a.ai_draft_note = 'secret estimate'
        self.req_a.triage_note = 'owner-only note'
        self.req_a.save()
        self._auth('oa-a')
        blob = str(self.client.get(f'{BASE}{self.req_a.id}/').json())
        for banned in ('secret estimate', 'owner-only note', 'ai_draft', 'triage'):
            self.assertNotIn(banned, blob, banned)

    def test_super_sees_owner_payload(self):
        self._auth('sup')
        body = self.client.get(f'{BASE}{self.req_a.id}/').json()
        self.assertIn('ai_draft_hours', body)
        self.assertIn('organisation_name', body)


class TestHappyPath(_Base):
    def test_create_scoped_to_caller_org(self):
        self._auth('oa-a')
        r = self.client.post(BASE, {'kind': 'bug', 'title': 'New', 'description': 'broken'},
                             format='json')
        self.assertEqual(r.status_code, 201)
        created = OrgRequest.objects.get(id=r.json()['id'])
        self.assertEqual(created.organisation_id, self.org_a.id)
        self.assertEqual(created.submitted_by_id, self.oa_a.id)

    def test_super_create_needs_org_id(self):
        self._auth('sup')
        r = self.client.post(BASE, {'kind': 'bug', 'title': 'x', 'description': 'y'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'org_required')

    def test_owner_flow_triage_quote_accept(self):
        self._auth('sup')
        pk = self.req_a.id
        self.assertEqual(self.client.post(
            f'{BASE}{pk}/triage/', {'triaged_kind': 'feature', 'lane': 'sprint'},
            format='json').status_code, 200)
        self.assertEqual(self.client.post(
            f'{BASE}{pk}/quote/', {'hours': 10, 'note': 'a page'}, format='json').status_code, 200)
        # org_admin accepts
        self._auth('oa-a')
        r = self.client.post(f'{BASE}{pk}/approve/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.req_a.refresh_from_db()
        self.assertEqual(self.req_a.status, 'approved')

    def test_quote_bug_is_free_400(self):
        self._auth('sup')
        pk = self.req_b.id if False else self.req_a.id
        self.client.post(f'{BASE}{pk}/triage/', {'triaged_kind': 'bug', 'lane': 'small_change'},
                         format='json')
        r = self.client.post(f'{BASE}{pk}/quote/', {'hours': 3}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bug_is_free')

    def test_count_super_global_submitted(self):
        self._auth('sup')
        self.assertEqual(self.client.get(f'{BASE}count/').json()['count'], 2)  # both submitted

    def test_count_org_admin_scoped(self):
        # org A has one submitted (no attention item yet) → 0; make it quoted → 1.
        self._auth('oa-a')
        self.assertEqual(self.client.get(f'{BASE}count/').json()['count'], 0)
        self.req_a.status = 'quoted'
        self.req_a.save()
        self.assertEqual(self.client.get(f'{BASE}count/').json()['count'], 1)

    def test_ai_rerun_503_when_unconfigured(self):
        # No GEMINI_API_KEY in test settings → the seam raises → mapped to 503, never a 500.
        self._auth('sup')
        r = self.client.post(f'{BASE}{self.req_a.id}/ai-rerun/', {}, format='json')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()['code'], 'triage_ai_unconfigured')
