"""Payments module — Sprint P2 admin endpoints (org-fence + role gate + happy path).

Mirrors test_org_admin_powers.py's access-control style: reviewer/qc/partner are refused
(403), a cross-org run is 404 (no existence leak), admin/org_admin/super pass. Plus the run
lifecycle over the wire (create/detail/item/sign/cancel/csv).
"""
from datetime import date
from decimal import Decimal
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import payments
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
_PREFIX = '8000400175'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=False)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = PartnerOrganisation.objects.create(code='pe-a', name='Org A')
        cls.org_b = PartnerOrganisation.objects.create(code='pe-b', name='Org B')
        cls.cohort_a = ScholarshipCohort.objects.create(
            code='pe-ca', name='CA', year=2026, owning_organisation=cls.org_a)
        cls.cohort_b = ScholarshipCohort.objects.create(
            code='pe-cb', name='CB', year=2026, owning_organisation=cls.org_b)

        def app(cohort, org, i, suffix='001'):
            prof = StudentProfile.objects.create(
                supabase_user_id=f'pe-stud-{i}', nric=f'{i:06d}-14-{i:04d}', name=f'Stud {i}')
            return ScholarshipApplication.objects.create(
                cohort=cohort, profile=prof, owning_organisation=org, status='awarded',
                chosen_pathway='matric', award_amount=Decimal('2000'),
                reporting_date=date(2026, 6, 1), vircle_id=_PREFIX + suffix)
        cls.app_a = app(cls.cohort_a, cls.org_a, 1, '001')
        cls.app_b = app(cls.cohort_b, cls.org_b, 2, '002')

        cls.maker = PartnerAdmin.objects.create(
            supabase_user_id='pe-mk', role='admin', is_active=True, owning_organisation=cls.org_a,
            name='Maker One', email='maker@x.com')
        cls.approver = PartnerAdmin.objects.create(
            supabase_user_id='pe-ap', role='org_admin', is_active=True, owning_organisation=cls.org_a,
            name='Approver One', email='approver@x.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='pe-rv', role='reviewer', is_active=True, owning_organisation=cls.org_a,
            name='Rev', email='rev@x.com')
        cls.qc = PartnerAdmin.objects.create(
            supabase_user_id='pe-qc', role='qc', is_active=True, owning_organisation=cls.org_a,
            name='QC', email='qc@x.com')
        cls.partner = PartnerAdmin.objects.create(
            supabase_user_id='pe-pt', role='partner', is_active=True, org=cls.org_a,
            name='Partner', email='pt@x.com')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='pe-su', is_super_admin=True, is_active=True, name='Super', email='su@x.com')
        cls.admin_b = PartnerAdmin.objects.create(
            supabase_user_id='pe-ab', role='admin', is_active=True, owning_organisation=cls.org_b,
            name='Admin B', email='ab@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _create_run(self, uid='pe-mk', pay_date='2026-08-01'):
        self._auth(uid)
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 7, 20)):
            return self.client.post('/api/v1/admin/scholarship/payment-runs/',
                                    {'payment_date': pay_date}, format='json')


class TestAccessControl(_Base):
    def test_list_role_gate(self):
        for uid in ('pe-mk', 'pe-ap', 'pe-su'):
            self._auth(uid)
            self.assertEqual(self.client.get('/api/v1/admin/scholarship/payment-runs/').status_code, 200, uid)
        for uid in ('pe-rv', 'pe-qc', 'pe-pt'):
            self._auth(uid)
            self.assertEqual(self.client.get('/api/v1/admin/scholarship/payment-runs/').status_code, 403, uid)

    def test_create_role_gate(self):
        self.assertEqual(self._create_run('pe-rv').status_code, 403)
        self.assertEqual(self._create_run('pe-qc').status_code, 403)
        self.assertEqual(self._create_run('pe-pt').status_code, 403)

    def test_cross_org_detail_404(self):
        r = self._create_run('pe-mk')
        run_id = r.json()['id']
        self._auth('pe-ab')   # org B admin
        self.assertEqual(self.client.get(f'/api/v1/admin/scholarship/payment-runs/{run_id}/').status_code, 404)

    def test_list_is_org_fenced(self):
        self._create_run('pe-mk')            # a run in org A
        self._auth('pe-ab')                  # org B admin sees none of org A's runs
        self.assertEqual(self.client.get('/api/v1/admin/scholarship/payment-runs/').json()['runs'], [])


class TestRunLifecycle(_Base):
    def test_past_date_rejected(self):
        self._auth('pe-mk')
        with mock.patch('apps.scholarship.payments.timezone.localdate', return_value=date(2026, 8, 5)):
            r = self.client.post('/api/v1/admin/scholarship/payment-runs/',
                                 {'payment_date': '2026-08-01'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'past_date')

    def test_create_lists_eligible_item(self):
        r = self._create_run('pe-mk')
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body['status'], 'draft')
        self.assertEqual(len(body['items']), 1)
        self.assertEqual(body['items'][0]['application_id'], self.app_a.id)
        self.assertEqual(body['items'][0]['amount'], '200.00')
        self.assertEqual(body['total'], '200.00')

    def test_item_exclude_requires_reason_then_ok(self):
        run = self._create_run('pe-mk').json()
        item_id = run['items'][0]['id']
        url = f"/api/v1/admin/scholarship/payment-runs/{run['id']}/items/{item_id}/"
        self._auth('pe-mk')
        self.assertEqual(self.client.patch(url, {'included': False, 'exclude_reason': ''}, format='json').status_code, 400)
        r = self.client.patch(url, {'included': False, 'exclude_reason': 'Semester break'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['items'][0]['included'])

    def test_sign_maker_then_approver_completes(self):
        run = self._create_run('pe-mk').json()
        sign = f"/api/v1/admin/scholarship/payment-runs/{run['id']}/sign/"
        self._auth('pe-mk')
        r1 = self.client.post(sign, {'typed_name': 'Maker One'}, format='json')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()['status'], 'admin_signed')
        self._auth('pe-ap')
        r2 = self.client.post(sign, {'typed_name': 'Approver One'}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'completed')
        # completion wrote a released disbursement
        self.assertEqual(self.app_a.disbursements.filter(status='released').count(), 1)

    def test_sign_name_mismatch(self):
        run = self._create_run('pe-mk').json()
        self._auth('pe-mk')
        r = self.client.post(f"/api/v1/admin/scholarship/payment-runs/{run['id']}/sign/",
                             {'typed_name': 'Wrong Name'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'name_mismatch')

    def test_cancel_draft(self):
        run = self._create_run('pe-mk').json()
        self._auth('pe-mk')
        r = self.client.post(f"/api/v1/admin/scholarship/payment-runs/{run['id']}/cancel/", {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'cancelled')

    def test_csv_download_after_admin_signed(self):
        run = self._create_run('pe-mk').json()
        csv_url = f"/api/v1/admin/scholarship/payment-runs/{run['id']}/csv/"
        self._auth('pe-mk')
        self.assertEqual(self.client.get(csv_url).status_code, 400)   # draft → not_ready
        self.client.post(f"/api/v1/admin/scholarship/payment-runs/{run['id']}/sign/",
                         {'typed_name': 'Maker One'}, format='json')
        r = self.client.get(csv_url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv')
        self.assertIn('Vircle ID', r.content.decode())
        self.assertIn(self.app_a.vircle_id, r.content.decode())
