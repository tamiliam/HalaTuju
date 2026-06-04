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

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_single_instance_doctype_replaces_on_reupload(self, mock_storage_delete, _mock_vision):
        """Post-S14: uploading a new IC sweeps the old one (DB + Storage)."""
        # Existing IC + an unrelated income-proof doc (multi-instance, must NOT be touched).
        old_ic = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='ic',
            storage_path=f'{self.app_a.id}/ic/old-1',
        )
        old_ic_2 = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='ic',
            storage_path=f'{self.app_a.id}/ic/old-2',
        )
        income = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='salary_slip',
            storage_path=f'{self.app_a.id}/salary_slip/keep-1',
        )

        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'ic',
            'storage_path': f'{self.app_a.id}/ic/new',
            'original_filename': 'NRICF.jpeg', 'size': 200_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)

        # Only the new IC remains; the income-proof doc is untouched.
        ic_rows = ApplicantDocument.objects.filter(application=self.app_a, doc_type='ic')
        self.assertEqual(ic_rows.count(), 1)
        self.assertEqual(ic_rows.first().storage_path, f'{self.app_a.id}/ic/new')
        self.assertFalse(ApplicantDocument.objects.filter(id=old_ic.id).exists())
        self.assertFalse(ApplicantDocument.objects.filter(id=old_ic_2.id).exists())
        self.assertTrue(ApplicantDocument.objects.filter(id=income.id).exists())

        # Storage was asked to sweep BOTH stale IC blobs in one call.
        mock_storage_delete.assert_called_once()
        swept = mock_storage_delete.call_args.args[0]
        self.assertEqual(set(swept), {
            f'{self.app_a.id}/ic/old-1', f'{self.app_a.id}/ic/old-2',
        })

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_multi_instance_doctype_keeps_existing_on_reupload(self, mock_storage_delete, _mock_vision):
        """Income-proof types (str / salary_slip / epf) MUST keep prior copies —
        a student may submit several monthly salary slips."""
        first = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='salary_slip',
            storage_path=f'{self.app_a.id}/salary_slip/jan',
        )
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'salary_slip',
            'storage_path': f'{self.app_a.id}/salary_slip/feb',
            'original_filename': 'feb.pdf', 'size': 50_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        rows = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='salary_slip',
        ).order_by('uploaded_at')
        self.assertEqual(rows.count(), 2)
        self.assertEqual([r.storage_path for r in rows], [
            f'{self.app_a.id}/salary_slip/jan',
            f'{self.app_a.id}/salary_slip/feb',
        ])
        self.assertTrue(ApplicantDocument.objects.filter(id=first.id).exists())
        # Storage sweep is NOT called for multi-instance types.
        mock_storage_delete.assert_not_called()

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_member_tagged_income_doc_is_single_instance_per_member(self, mock_del, _mv):
        """Salary route: a member-tagged salary slip replaces THAT member's prior copy
        (single-instance per (doc_type, member)) — never another member's."""
        fathers = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='salary_slip', household_member='father',
            storage_path=f'{self.app_a.id}/salary_slip/father-old')
        mothers = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='salary_slip', household_member='mother',
            storage_path=f'{self.app_a.id}/salary_slip/mother-keep')
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'salary_slip', 'household_member': 'father',
            'storage_path': f'{self.app_a.id}/salary_slip/father-new',
            'original_filename': 'f.pdf', 'size': 50_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        father_rows = ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='salary_slip', household_member='father')
        self.assertEqual(father_rows.count(), 1)
        self.assertEqual(father_rows.first().storage_path, f'{self.app_a.id}/salary_slip/father-new')
        self.assertFalse(ApplicantDocument.objects.filter(id=fathers.id).exists())
        self.assertTrue(ApplicantDocument.objects.filter(id=mothers.id).exists())  # untouched

    @patch('apps.scholarship.vision.run_vision_for_document', return_value=None)
    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_blank_member_parent_ic_does_not_sweep_member_tagged(self, mock_del, _mv):
        """An untagged parent_ic (STR route / minor consent) must NOT sweep the
        salary-route member-tagged parent_ics — the sweep is (doc_type, member)-scoped."""
        father_ic = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='parent_ic', household_member='father',
            storage_path=f'{self.app_a.id}/parent_ic/father')
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'parent_ic',  # no household_member → blank
            'storage_path': f'{self.app_a.id}/parent_ic/str-earner',
            'original_filename': 'ic.jpg', 'size': 50_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(ApplicantDocument.objects.filter(id=father_ic.id).exists())
        self.assertEqual(ApplicantDocument.objects.filter(
            application=self.app_a, doc_type='parent_ic').count(), 2)

    @patch('apps.scholarship.storage.delete_objects', return_value=True)
    def test_delete_sweeps_storage(self, mock_storage_delete):
        """Explicit DELETE on a doc also sweeps its Storage blob."""
        doc = ApplicantDocument.objects.create(
            application=self.app_a, doc_type='water_bill',
            storage_path=f'{self.app_a.id}/water_bill/abc',
        )
        self._auth(USER_A)
        resp = self.client.delete(f'/api/v1/scholarship/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ApplicantDocument.objects.filter(id=doc.id).exists())
        mock_storage_delete.assert_called_once_with([f'{self.app_a.id}/water_bill/abc'])

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

    # ── S4: new doc types ────────────────────────────────────────────────
    @patch('apps.scholarship.storage.create_signed_upload_url', return_value='https://signed.example/upload')
    def test_sign_upload_accepts_salary_slip(self, _mock):
        """salary_slip (new in S4) is a valid doc_type for sign-upload."""
        self._auth(USER_A)
        resp = self.client.post(
            '/api/v1/scholarship/documents/sign-upload/',
            {'doc_type': 'salary_slip'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['doc_type'], 'salary_slip')

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    def test_record_document_accepts_new_types(self, _mock):
        """All four S4 doc types can be recorded via the document API."""
        self._auth(USER_A)
        for doc_type in ('salary_slip', 'water_bill', 'electricity_bill', 'offer_letter'):
            resp = self.client.post('/api/v1/scholarship/documents/', {
                'doc_type': doc_type,
                'storage_path': f'{self.app_a.id}/{doc_type}/abc',
                'original_filename': f'{doc_type}.pdf',
                'size': 512,
            }, format='json')
            self.assertEqual(resp.status_code, 201, f'Expected 201 for doc_type={doc_type}, got {resp.status_code}')

    # ── S13: Vision OCR auto-trigger on IC upload ───────────────────────────
    @staticmethod
    def _mock_vision_call(doc):
        """Mimic vision.run_vision_for_document side effect (writes to the row)."""
        from django.utils import timezone as _tz
        doc.vision_nric = '030101-14-1234'
        doc.vision_name = 'PRIYA A/P KRISHNAN'
        doc.vision_run_at = _tz.now()
        doc.vision_error = ''
        doc.save(update_fields=['vision_nric', 'vision_name', 'vision_run_at', 'vision_error'])
        return {'nric': '030101-14-1234', 'name': 'PRIYA A/P KRISHNAN', 'error': None}

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_ic_upload_auto_runs_vision(self, mock_vision, _dl):
        """Recording an IC document triggers run_vision_for_document; response carries the fields."""
        mock_vision.side_effect = self._mock_vision_call
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'ic',
            'storage_path': f'{self.app_a.id}/ic/abc',
            'original_filename': 'mykad.jpg', 'size': 50_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(mock_vision.called)
        body = resp.json()
        self.assertEqual(body['vision_nric'], '030101-14-1234')
        self.assertEqual(body['vision_name'], 'PRIYA A/P KRISHNAN')
        self.assertEqual(body['vision_error'], '')
        self.assertIsNotNone(body['vision_run_at'])

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_non_ic_upload_does_not_run_vision(self, mock_vision, _dl):
        """Vision is gated on doc_type='ic' — other types must not trigger a call."""
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'results_slip',
            'storage_path': f'{self.app_a.id}/results_slip/abc',
            'original_filename': 'results.pdf', 'size': 1000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(mock_vision.called)
        self.assertEqual(resp.json()['vision_nric'], '')

    @patch('apps.scholarship.storage.create_signed_download_url', return_value='https://signed.example/dl')
    @patch('apps.scholarship.vision.run_vision_for_document')
    def test_ic_upload_survives_vision_failure(self, mock_vision, _dl):
        """If Vision errors, the upload still succeeds; the error is recorded on the row."""
        from django.utils import timezone as _tz

        def boom(doc):
            doc.vision_error = 'AI module not installed'
            doc.vision_run_at = _tz.now()
            doc.save(update_fields=['vision_error', 'vision_run_at'])
            return {'nric': '', 'name': '', 'error': 'AI module not installed'}
        mock_vision.side_effect = boom
        self._auth(USER_A)
        resp = self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': 'ic',
            'storage_path': f'{self.app_a.id}/ic/zzz',
            'original_filename': 'mykad.jpg', 'size': 50_000,
        }, format='json')
        self.assertEqual(resp.status_code, 201)   # upload not blocked
        body = resp.json()
        self.assertEqual(body['vision_nric'], '')
        self.assertEqual(body['vision_error'], 'AI module not installed')


class TestIcGeminiFallbackIntegration(TestCase):
    """#5 — run_vision_for_document escalates a low-confidence MyKad read to the Gemini
    second opinion (cost-gated) and merges it in. Vision + Gemini seams both mocked."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='gx', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id='gemini-ic-user',
                                                    nric='030101-14-1234', name='Priya Krishnan')
        cls.app = ScholarshipApplication.objects.create(cohort=cls.cohort, profile=cls.profile,
                                                        status='shortlisted')

    def _ic_doc(self):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='ic',
            storage_path=f'{self.app.id}/ic/x', original_filename='mykad.jpg',
            content_type='image/jpeg', size=50_000)

    # A misread last digit (…1239) — OCR disagrees with the typed profile (…1234).
    _MISREAD_OCR = {'text': 'MYKAD\nMALAYSIA\n030101-14-1239\nPRIYA A/P KRISHNAN\nNO 1 JALAN\n50000 KL',
                    'error': None}
    _CLEAN_OCR = {'text': 'MYKAD\nMALAYSIA\n030101-14-1234\nPRIYA A/P KRISHNAN\nNO 1 JALAN\n50000 KL',
                  'error': None}

    @patch('apps.scholarship.vision._call_gemini_json')
    @patch('apps.scholarship.vision._vision_document_text')
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'imgbytes')
    def test_low_confidence_escalates_and_merges(self, _img, mock_ocr, mock_gemini):
        from apps.scholarship.vision import run_vision_for_document
        mock_ocr.return_value = self._MISREAD_OCR
        mock_gemini.return_value = {'nric': '030101-14-1234', 'name': 'PRIYA A/P KRISHNAN',
                                    'address': 'NO 1, JALAN BERSIH, 50000 KL'}
        doc = self._ic_doc()
        result = run_vision_for_document(doc)
        self.assertTrue(mock_gemini.called)                 # escalated
        self.assertEqual(result['nric'], '030101-14-1234')  # gemini recovered the digit
        doc.refresh_from_db()
        self.assertEqual(doc.vision_nric, '030101-14-1234')
        self.assertEqual(doc.vision_address, 'NO 1, JALAN BERSIH, 50000 KL')

    @patch('apps.scholarship.vision._call_gemini_json')
    @patch('apps.scholarship.vision._vision_document_text')
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'imgbytes')
    def test_clean_read_does_not_call_gemini(self, _img, mock_ocr, mock_gemini):
        from apps.scholarship.vision import run_vision_for_document
        mock_ocr.return_value = self._CLEAN_OCR
        run_vision_for_document(self._ic_doc())
        mock_gemini.assert_not_called()                     # stayed free

    @override_settings(IC_GEMINI_FALLBACK_ENABLED=False)
    @patch('apps.scholarship.vision._call_gemini_json')
    @patch('apps.scholarship.vision._vision_document_text')
    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'imgbytes')
    def test_knob_off_never_calls_gemini(self, _img, mock_ocr, mock_gemini):
        from apps.scholarship.vision import run_vision_for_document
        mock_ocr.return_value = self._MISREAD_OCR
        run_vision_for_document(self._ic_doc())
        mock_gemini.assert_not_called()
