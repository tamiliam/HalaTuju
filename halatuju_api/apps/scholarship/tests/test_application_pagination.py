"""
Server-side pagination for the B40 admin applications list.

The endpoint used to serialise every matching application in one response. It
now paginates via ?page / ?page_size (FlexiblePageNumberPagination). Filters are
applied to the queryset before paging, so paging reflects the filtered set.
`total_count` is retained as a backward-compatible alias for the total filtered
count (existing tests assert on it).
"""
import jwt
from django.test import TestCase, override_settings

from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ADMIN = 'admin-uid'


def _token(uid):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        TEST_JWT_SECRET, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ApplicationListPaginationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id=ADMIN, is_super_admin=True, is_active=True,
            name='Admin', email='admin@example.com',
        )
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        # 30 applications: 18 bucket A, 12 bucket B.
        for i in range(30):
            prof = StudentProfile.objects.create(
                supabase_user_id=f'stud-{i:03d}',
                nric=f'{i:06d}-14-1234',
                name=f'Applicant {i:03d}',
            )
            ScholarshipApplication.objects.create(
                cohort=cls.cohort, profile=prof, status='shortlisted',
                bucket='A' if i % 5 else 'B',
            )

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(ADMIN)}')

    def test_default_page(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/').json()
        self.assertEqual(body['count'], 30)
        self.assertEqual(body['total_count'], 30)  # backward-compat alias
        self.assertEqual(body['page'], 1)
        self.assertEqual(body['page_size'], 25)
        self.assertEqual(body['total_pages'], 2)
        self.assertEqual(len(body['applications']), 25)
        self.assertIsNone(body['previous'])
        self.assertIsNotNone(body['next'])

    def test_second_page_remainder(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/?page=2').json()
        self.assertEqual(body['page'], 2)
        self.assertEqual(len(body['applications']), 5)
        self.assertIsNone(body['next'])

    def test_filter_then_paginate_compose(self):
        # 24 bucket-A apps (i % 5 != 0 over 0..29) → still one+ pages, count is
        # the filtered total, not the unfiltered 30.
        body = self.client.get('/api/v1/admin/scholarship/applications/?bucket=A&page_size=10').json()
        self.assertEqual(body['count'], 24)
        self.assertEqual(body['total_count'], 24)
        self.assertEqual(body['page_size'], 10)
        self.assertEqual(body['total_pages'], 3)
        self.assertEqual(len(body['applications']), 10)

    def test_empty_filter_result(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/?status=accepted').json()
        self.assertEqual(body['count'], 0)
        self.assertEqual(body['total_count'], 0)
        self.assertEqual(body['applications'], [])

    def test_page_size_capped(self):
        body = self.client.get('/api/v1/admin/scholarship/applications/?page_size=500').json()
        self.assertEqual(body['page_size'], 100)
        self.assertEqual(len(body['applications']), 30)
