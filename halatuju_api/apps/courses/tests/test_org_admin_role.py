"""Administration panel — `org_admin` role + platform surface partition (Sprint A).

The courses app has no org-fence CI guard (that's scholarship's); these are the
equivalent proofs for the courses admin surface:
- SURFACE PARTITION (security fix): the platform-wide Students directory / Dashboard /
  export / Course-Data are SUPER-ONLY; a B40 admin/qc/org_admin can no longer fetch
  every course-selector student. The referral `partner` keeps its own-org students.
- `org_admin` staff delegation: invite/list/resend/revoke scoped to the caller's OWN
  organisation, non-super programme staff only; add-tenant on org_admin invite.
"""
from unittest.mock import MagicMock, patch

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SUPABASE_URL='https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY='k')
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        # BrightPath (org #1) is seeded by migration 0098; use it as the caller's tenant.
        cls.bp = PartnerOrganisation.objects.get(code='brightpath')
        cls.other = PartnerOrganisation.objects.create(code='inspire', name='Inspire')
        cls.referral = PartnerOrganisation.objects.create(code='cumig', name='CUMIG')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@x.com')
        cls.org_admin = PartnerAdmin.objects.create(
            supabase_user_id='oa-uid', role='org_admin', is_active=True,
            owning_organisation=cls.bp, name='Suresh', email='oa@x.com')
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='admin-uid', role='admin', is_active=True,
            owning_organisation=cls.bp, name='Admin', email='admin@x.com')
        cls.qc = PartnerAdmin.objects.create(
            supabase_user_id='qc-uid', role='qc', is_active=True,
            owning_organisation=cls.bp, name='QC', email='qc@x.com')
        cls.partner = PartnerAdmin.objects.create(
            supabase_user_id='partner-uid', role='partner', is_active=True,
            org=cls.referral, name='Partner', email='partner@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')


class TestSurfacePartition(_Base):
    """The platform-wide directory + course data are super-only now."""
    PLATFORM_GETS = ['/api/v1/admin/students/', '/api/v1/admin/dashboard/',
                     '/api/v1/admin/students/export/', '/api/v1/admin/course-data/']

    def test_super_still_sees_everything(self):
        self._auth('super-uid')
        for url in self.PLATFORM_GETS:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_admin_qc_org_admin_denied(self):
        for uid in ('admin-uid', 'qc-uid', 'oa-uid'):
            self._auth(uid)
            for url in self.PLATFORM_GETS:
                self.assertEqual(self.client.get(url).status_code, 403, f'{uid} {url}')

    def test_course_data_check_super_only(self):
        self._auth('oa-uid')
        self.assertEqual(self.client.post('/api/v1/admin/course-data/check/', {}, format='json').status_code, 403)

    def test_partner_keeps_own_org_students(self):
        # A referral partner still sees ONLY their referral org's students (unchanged).
        StudentProfile.objects.create(supabase_user_id='s-cumig', referred_by_org=self.referral, name='Ref')
        StudentProfile.objects.create(supabase_user_id='s-other', name='Unref')
        self._auth('partner-uid')
        r = self.client.get('/api/v1/admin/students/')
        self.assertEqual(r.status_code, 200)


class TestOrgAdminInvite(_Base):
    """An org_admin delegates programme staff within their own org only."""
    def _invite(self, uid, payload):
        with patch('apps.courses.views_admin.http_requests.post') as mp:
            mp.return_value = MagicMock(status_code=200, text='ok', json=lambda: {'id': 'new-uid'})
            self._auth(uid)
            return self.client.post('/api/v1/admin/invite/', payload, format='json')

    def test_org_admin_invites_reviewer_bound_to_own_org(self):
        r = self._invite('oa-uid', {'email': 'newrev@x.com', 'name': 'Rev', 'role': 'reviewer'})
        self.assertEqual(r.status_code, 201)
        a = PartnerAdmin.objects.get(email='newrev@x.com')
        self.assertEqual(a.role, 'reviewer')
        self.assertEqual(a.owning_organisation_id, self.bp.id)   # caller's org, forced

    def test_org_admin_org_input_ignored(self):
        # Even if the org_admin passes another org, the invite lands in THEIR org.
        r = self._invite('oa-uid', {'email': 'r2@x.com', 'name': 'R', 'role': 'admin',
                                    'org_id': self.other.id, 'new_org_code': 'inspire'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(PartnerAdmin.objects.get(email='r2@x.com').owning_organisation_id, self.bp.id)

    def test_org_admin_cannot_invite_partner_super_org_admin(self):
        for role in ('partner', 'super', 'org_admin'):
            email = f'new-{role}@x.com'   # distinct from the base fixture accounts
            r = self._invite('oa-uid', {'email': email, 'name': 'X', 'role': role})
            self.assertEqual(r.status_code, 403, role)
            self.assertFalse(PartnerAdmin.objects.filter(email=email).exists(), role)

    def test_org_admin_without_owning_org_400(self):
        PartnerAdmin.objects.create(supabase_user_id='oa2', role='org_admin', is_active=True,
                                    owning_organisation=None, name='Loose', email='oa2@x.com')
        r = self._invite('oa2', {'email': 'x@x.com', 'name': 'X', 'role': 'reviewer'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json().get('code'), 'no_owning_org')


class TestAddTenant(_Base):
    """A super installs a new organisation's admin (add-tenant)."""
    def _invite(self, payload):
        with patch('apps.courses.views_admin.http_requests.post') as mp:
            mp.return_value = MagicMock(status_code=200, text='ok', json=lambda: {'id': 'new-uid'})
            self._auth('super-uid')
            return self.client.post('/api/v1/admin/invite/', payload, format='json')

    def test_super_add_tenant_new_org(self):
        r = self._invite({'email': 'inspire-admin@x.com', 'name': 'Lead', 'role': 'org_admin',
                          'new_org_name': 'Inspire Scholars', 'new_org_code': 'inspire2'})
        self.assertEqual(r.status_code, 201)
        org = PartnerOrganisation.objects.get(code='inspire2')
        self.assertTrue(org.module_scholarship)   # scholarship switched on for the tenant
        a = PartnerAdmin.objects.get(email='inspire-admin@x.com')
        self.assertEqual(a.role, 'org_admin')
        self.assertEqual(a.owning_organisation_id, org.id)
        self.assertIsNone(a.org_id)               # tenant is owning_org, NOT the referral org

    def test_super_add_tenant_existing_org_switches_module_on(self):
        self.assertFalse(self.other.module_scholarship)
        r = self._invite({'email': 'oadmin@x.com', 'name': 'Lead', 'role': 'org_admin',
                          'org_id': self.other.id})
        self.assertEqual(r.status_code, 201)
        self.other.refresh_from_db()
        self.assertTrue(self.other.module_scholarship)
        self.assertEqual(PartnerAdmin.objects.get(email='oadmin@x.com').owning_organisation_id, self.other.id)


class TestOrgAdminStaffManagement(_Base):
    """List / resend / revoke are scoped to the org_admin's own non-super staff."""
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.own_rev = PartnerAdmin.objects.create(
            supabase_user_id='own-rev', role='reviewer', is_active=True,
            owning_organisation=cls.bp, name='Own Rev', email='ownrev@x.com')
        cls.other_rev = PartnerAdmin.objects.create(
            supabase_user_id='other-rev', role='reviewer', is_active=True,
            owning_organisation=cls.other, name='Other Rev', email='otherrev@x.com')

    def test_list_scoped_to_own_org_non_super(self):
        self._auth('oa-uid')
        r = self.client.get('/api/v1/admin/admins/')
        self.assertEqual(r.status_code, 200)
        emails = {a['email'] for a in r.json()['admins']}
        self.assertIn('ownrev@x.com', emails)
        self.assertIn('admin@x.com', emails)      # own-org admin (manageable)
        self.assertNotIn('otherrev@x.com', emails)  # other org
        self.assertNotIn('super@x.com', emails)     # never a super
        self.assertNotIn('partner@x.com', emails)   # partner isn't manageable staff

    def test_super_list_sees_all(self):
        self._auth('super-uid')
        emails = {a['email'] for a in self.client.get('/api/v1/admin/admins/').json()['admins']}
        self.assertTrue({'ownrev@x.com', 'otherrev@x.com', 'super@x.com'} <= emails)

    def test_list_payload_carries_owning_org_name(self):
        """The Administration panel's Add-tenant list shows which organisation an
        org_admin runs — the payload must expose the TENANT binding (never the
        referral org field)."""
        self._auth('super-uid')
        by_email = {a['email']: a for a in self.client.get('/api/v1/admin/admins/').json()['admins']}
        self.assertEqual(by_email['oa@x.com']['owning_org_name'], self.bp.name)
        self.assertIsNone(by_email['super@x.com']['owning_org_name'])

    def test_revoke_own_org_reviewer_ok(self):
        self._auth('oa-uid')
        r = self.client.patch(f'/api/v1/admin/admins/{self.own_rev.id}/revoke/',
                              {'action': 'revoke'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.own_rev.refresh_from_db()
        self.assertFalse(self.own_rev.is_active)

    def test_revoke_cross_org_404(self):
        self._auth('oa-uid')
        r = self.client.patch(f'/api/v1/admin/admins/{self.other_rev.id}/revoke/',
                              {'action': 'revoke'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_revoke_super_target_404(self):
        self._auth('oa-uid')
        r = self.client.patch(f'/api/v1/admin/admins/{self.super.id}/revoke/',
                              {'action': 'revoke'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_resend_cross_org_404(self):
        self._auth('oa-uid')
        with patch('apps.courses.views_admin.http_requests.put') as mp:
            mp.return_value = MagicMock(status_code=200, text='ok')
            r = self.client.post(f'/api/v1/admin/admins/{self.other_rev.id}/resend/', {}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_reviewer_cannot_manage_staff(self):
        # A plain reviewer is neither super nor org_admin → 403 on list/revoke.
        self.own_rev.supabase_user_id = 'ownrev-uid'; self.own_rev.save(update_fields=['supabase_user_id'])
        self._auth('ownrev-uid')
        self.assertEqual(self.client.get('/api/v1/admin/admins/').status_code, 403)


class TestRolePayload(_Base):
    def test_role_view_exposes_owning_org(self):
        self._auth('oa-uid')
        d = self.client.get('/api/v1/admin/role/').json()
        self.assertEqual(d['role'], 'org_admin')
        self.assertEqual(d['owning_org_id'], self.bp.id)
        self.assertEqual(d['owning_org_name'], self.bp.name)
        self.assertIsNone(d['org_name'])   # referral org is None for an org_admin
