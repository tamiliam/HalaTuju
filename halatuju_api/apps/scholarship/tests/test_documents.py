"""Tests for the document vault + referee endpoints (Sprint 5a)."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
USER_A = 'doc-user-a'
USER_B = 'doc-user-b'
USER_C = 'doc-user-c'  # has only a rejected application


def _token(uid, secret=TEST_JWT_SECRET):
    return jwt.encode(
        {'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
        secret, algorithm='HS256',
    )


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDocumentApi(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.cohort2 = ScholarshipCohort.objects.create(code='c2', name='B40-2', year=2025)
        cls.profile_a = StudentProfile.objects.create(supabase_user_id=USER_A, nric='030101-14-1234')
        cls.profile_b = StudentProfile.objects.create(supabase_user_id=USER_B, nric='040101-14-5678')
        cls.profile_c = StudentProfile.objects.create(supabase_user_id=USER_C, nric='050101-14-9999')
        cls.app_a = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile_a, status='shortlisted')
        cls.app_b = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile_b, status='shortlisted')
        cls.rejected_c = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile_c, status='rejected')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    @patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://signed.example/upload')
    def test_sign_upload(self, _mock):
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/sign-upload/', {'doc_type': 'ic'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['upload_url'], 'https://signed.example/upload')
        self.assertTrue(resp.json()['storage_path'].startswith(f'{self.app_a.id}/ic/'))

    @patch('apps.scholarship.storage.create_signed_upload_url', return_value=None)
    def test_sign_upload_unavailable_503(self, _mock):
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/sign-upload/', {'doc_type': 'ic'}, format='json')
        self.assertEqual(resp.status_code, 503)

    def test_sign_upload_no_shortlisted_403(self):
        self._auth(USER_C)
        resp = self.client.post('/api/v1/scholarship/documents/sign-upload/', {'doc_type': 'ic'}, format='json')
        self.assertEqual(resp.status_code, 403)

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    def test_create_and_list_document(self, _mock):
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'results_slip',
            'storage_path': f'{self.app_a.id}/results_slip/abc',
            'original_filename': 'results.pdf', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        resp2 = self.client.get('/api/v1/scholarship/documents/')
        self.assertEqual(resp2.status_code, 200)
        docs = resp2.json()['documents']
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['doc_type'], 'results_slip')
        self.assertEqual(docs[0]['download_url'], 'https://signed.example/dl')

    def test_delete_own_document(self):
        doc = ApplicantDocument.objects.create(application=self.app_a, doc_type='ic', storage_path='x')
        self._auth(USER_A)
        resp = self.client.delete(f'/api/v1/scholarship/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ApplicantDocument.objects.filter(id=doc.id).exists())

    def test_delete_cross_user_404(self):
        doc = ApplicantDocument.objects.create(application=self.app_b, doc_type='ic', storage_path='x')
        self._auth(USER_A)
        resp = self.client.delete(f'/api/v1/scholarship/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_referee_create_and_list(self):
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/referees/', {
            'name': 'Mr Teacher', 'role': 'teacher', 'phone': '012-3456789',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        resp2 = self.client.get('/api/v1/scholarship/referees/')
        self.assertEqual(len(resp2.json()['referees']), 1)
        self.assertEqual(resp2.json()['referees'][0]['name'], 'Mr Teacher')

    @override_settings(SUPABASE_URL='', SUPABASE_SERVICE_ROLE_KEY='')
    def test_storage_returns_none_when_unconfigured(self):
        from apps.scholarship.storage import create_signed_download_url, create_signed_upload_url
        self.assertIsNone(create_signed_upload_url('x/y/z'))
        self.assertIsNone(create_signed_download_url('x/y/z'))

    def test_documents_require_auth(self):
        resp = self.client.get('/api/v1/scholarship/documents/')
        self.assertEqual(resp.status_code, 401)
