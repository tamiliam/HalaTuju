"""Platform Sprint 3a — the organisation fence on the B40 admin gates.

Unit + endpoint tests for each amended gate: the org-scoped queryset, the row-level
allow check, and their wiring into the list / detail / QC / write paths. With one
real org this is invisible (same-org everywhere); these tests stand up a SECOND org
to prove the wall. Super is global; partner has no B40 access; a NULL owning_org is a
safe degenerate bucket.
"""
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.views_admin import _AdminBase

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


class OrgFenceMixin:
    """Two tenants (A, B), each with a cohort + an application + org-bound staff;
    plus a global super and a platform-level partner. Concrete subclasses carry the
    @override_settings (a mixin can't be decorated)."""
    @classmethod
    def setUpTestData(cls):
        cls.org_a = PartnerOrganisation.objects.create(code='fence-a', name='Tenant A')
        cls.org_b = PartnerOrganisation.objects.create(code='fence-b', name='Tenant B')
        cls.cohort_a = ScholarshipCohort.objects.create(
            code='ca', name='A', year=2026, owning_organisation=cls.org_a)
        cls.cohort_b = ScholarshipCohort.objects.create(
            code='cb', name='B', year=2026, owning_organisation=cls.org_b)
        cls.prof_a = StudentProfile.objects.create(supabase_user_id='sa', nric='010101-14-0001', name='Anwar')
        cls.prof_b = StudentProfile.objects.create(supabase_user_id='sb', nric='020202-14-0002', name='Bala')
        cls.app_a = ScholarshipApplication.objects.create(cohort=cls.cohort_a, profile=cls.prof_a)
        cls.app_b = ScholarshipApplication.objects.create(cohort=cls.cohort_b, profile=cls.prof_b)
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@x.com')
        cls.admin_a = PartnerAdmin.objects.create(
            supabase_user_id='admin-a', role='admin', is_active=True, owning_organisation=cls.org_a,
            name='Admin A', email='admina@x.com')
        cls.admin_b = PartnerAdmin.objects.create(
            supabase_user_id='admin-b', role='admin', is_active=True, owning_organisation=cls.org_b,
            name='Admin B', email='adminb@x.com')
        cls.qc_a = PartnerAdmin.objects.create(
            supabase_user_id='qc-a', role='qc', is_active=True, owning_organisation=cls.org_a,
            name='QC A', email='qca@x.com')
        cls.reviewer_a = PartnerAdmin.objects.create(
            supabase_user_id='rev-a', role='reviewer', is_active=True, owning_organisation=cls.org_a,
            name='Reviewer A', email='reva@x.com')
        cls.partner = PartnerAdmin.objects.create(
            supabase_user_id='partner-uid', role='partner', is_active=True,
            name='Partner', email='partner@x.com')
        cls.org_admin_a = PartnerAdmin.objects.create(
            supabase_user_id='oa-a', role='org_admin', is_active=True, owning_organisation=cls.org_a,
            name='OrgAdmin A', email='oaa@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestGateHelpers(OrgFenceMixin, TestCase):
    """Direct unit tests of the amended gate helpers on _AdminBase."""
    def setUp(self):
        super().setUp()
        self.view = _AdminBase()

    def test_org_scoped_filters_to_caller_org(self):
        qs = ScholarshipApplication.objects.all()
        ids = set(self.view._org_scoped(qs, self.admin_a).values_list('id', flat=True))
        self.assertEqual(ids, {self.app_a.id})

    def test_org_scoped_super_sees_all(self):
        qs = ScholarshipApplication.objects.all()
        ids = set(self.view._org_scoped(qs, self.super).values_list('id', flat=True))
        self.assertEqual(ids, {self.app_a.id, self.app_b.id})

    def test_org_scoped_none_admin_is_null_bucket(self):
        """A NULL owning_org (partner) filters to the IS NULL partition — never another org."""
        qs = ScholarshipApplication.objects.all()
        ids = set(self.view._org_scoped(qs, self.partner).values_list('id', flat=True))
        self.assertEqual(ids, set())   # no app has a NULL owning_org here

    def test_org_allows_same_org(self):
        self.assertTrue(self.view._org_allows(self.admin_a, self.app_a))

    def test_org_allows_cross_org_false(self):
        self.assertFalse(self.view._org_allows(self.admin_a, self.app_b))

    def test_org_allows_super_global(self):
        self.assertTrue(self.view._org_allows(self.super, self.app_b))

    def test_org_admin_scope_is_all_but_org_fenced(self):
        # org_admin gets 'all' scope, then _org_scoped fences it to its own org.
        self.assertEqual(self.view._b40_scope(self.org_admin_a), 'all')
        qs = ScholarshipApplication.objects.all()
        ids = set(self.view._org_scoped(qs, self.org_admin_a).values_list('id', flat=True))
        self.assertEqual(ids, {self.app_a.id})

    def test_org_admin_cross_org_not_allowed(self):
        self.assertTrue(self.view._org_allows(self.org_admin_a, self.app_a))
        self.assertFalse(self.view._org_allows(self.org_admin_a, self.app_b))

    def test_can_review_app_cross_org_false(self):
        # super assigns appA to adminA out-of-band; even so, adminB may not write it.
        self.app_a.assigned_to = self.admin_a
        self.app_a.save(update_fields=['assigned_to'])
        self.assertFalse(self.view._can_review_app(self.admin_b, self.app_a))
        self.assertTrue(self.view._can_review_app(self.super, self.app_a))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestListEndpoint(OrgFenceMixin, TestCase):
    URL = '/api/v1/admin/scholarship/applications/'

    def _ids(self, resp):
        return {a['id'] for a in resp.json()['applications']}

    def test_admin_sees_only_own_org(self):
        self._auth('admin-a')
        r = self.client.get(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._ids(r), {self.app_a.id})

    def test_other_admin_sees_only_their_org(self):
        self._auth('admin-b')
        self.assertEqual(self._ids(self.client.get(self.URL)), {self.app_b.id})

    def test_super_sees_both(self):
        self._auth('super-uid')
        self.assertEqual(self._ids(self.client.get(self.URL)), {self.app_a.id, self.app_b.id})

    def test_partner_denied(self):
        self._auth('partner-uid')
        self.assertEqual(self.client.get(self.URL).status_code, 403)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDetailEndpoint(OrgFenceMixin, TestCase):
    def _url(self, app):
        return f'/api/v1/admin/scholarship/applications/{app.id}/'

    def test_same_org_detail_ok(self):
        self._auth('admin-a')
        self.assertEqual(self.client.get(self._url(self.app_a)).status_code, 200)

    def test_cross_org_detail_404_not_403(self):
        """Cross-org must be 404 — never 403 — so existence isn't leaked."""
        self._auth('admin-a')
        self.assertEqual(self.client.get(self._url(self.app_b)).status_code, 404)

    def test_super_detail_any_org(self):
        self._auth('super-uid')
        self.assertEqual(self.client.get(self._url(self.app_b)).status_code, 200)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestQcGateOrg(OrgFenceMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Put both apps into AWAITING-QC; mock the verdict so the gap floor never blocks.
        for app, rev in ((self.app_a, self.reviewer_a), (self.app_b, None)):
            app.status = 'interviewed'
            app.verdict_decided_at = timezone.now()
            app.assigned_to = rev
            app.save(update_fields=['status', 'verdict_decided_at', 'assigned_to'])
        patcher = mock.patch('apps.scholarship.views_admin.build_verdict', return_value=[])
        patcher.start(); self.addCleanup(patcher.stop)

    def _qc(self, app, payload):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/qc-decision/', payload, format='json')

    def test_qc_cross_org_404(self):
        self._auth('qc-a')
        self.assertEqual(self._qc(self.app_b, {'decision': 'accept'}).status_code, 404)

    def test_qc_same_org_accepts(self):
        self._auth('qc-a')
        r = self._qc(self.app_a, {'decision': 'accept'})
        self.assertEqual(r.status_code, 200)
        self.app_a.refresh_from_db()
        self.assertEqual(self.app_a.status, 'recommended')
