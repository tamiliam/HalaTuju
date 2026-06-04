"""Document-assist: Gemini field extraction (mocked) + deterministic verdict + upload guardrails."""
from unittest.mock import patch

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import StudentProfile
from apps.scholarship import vision
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
USER = 'extract-user'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


class TestDocStudentVerdict(TestCase):
    def test_ok_when_name_matches_student(self):
        self.assertEqual(vision.doc_student_verdict(
            'salary_slip', {'name': 'Muthu Raman', 'gross_income': '3000'}, names=['Muthu Raman']), 'ok')

    def test_ok_when_name_matches_a_parent(self):
        # Income docs are usually in a parent's name — matching either is fine.
        self.assertEqual(vision.doc_student_verdict(
            'salary_slip', {'name': 'Ahmad Bin Ali', 'gross_income': '3000'},
            names=['Siti Ahmad', 'Ahmad Bin Ali']), 'ok')

    def test_name_mismatch(self):
        self.assertEqual(vision.doc_student_verdict(
            'salary_slip', {'name': 'Totally Different', 'gross_income': '3000'},
            names=['Muthu Raman']), 'name_mismatch')

    def test_wrong_doc_when_nothing_extracted(self):
        self.assertEqual(vision.doc_student_verdict(
            'salary_slip', {'name': '', 'gross_income': '', 'period': ''}, names=['Muthu Raman']), 'wrong_doc')

    def test_bill_address_mismatch(self):
        self.assertEqual(vision.doc_student_verdict(
            'electricity_bill', {'name': 'Muthu Raman', 'address': 'No 9 Jalan Z 99999 Ipoh'},
            names=['Muthu Raman'], postcode='62100', city='Putrajaya', check_address=True), 'address_mismatch')


class TestExtractDocumentFields(TestCase):
    @patch('apps.scholarship.vision._call_gemini_json')
    def test_extract_salary_slip(self, mock_call):
        mock_call.return_value = {'name': 'Muthu Raman', 'employer': 'ACME', 'gross_income': '3000',
                                  'net_income': '2700', 'period': 'Jan 2026', 'warnings': ['blurry']}
        r = vision.extract_document_fields('Salary slip OCR text', 'salary_slip')
        self.assertEqual(r['error'], '')
        self.assertEqual(r['fields']['gross_income'], '3000')
        self.assertNotIn('warnings', r['fields'])   # warnings split out
        self.assertEqual(r['warnings'], ['blurry'])

    def test_unknown_doc_type(self):
        self.assertIn('no extractor', vision.extract_document_fields('text', 'photo')['error'])

    def test_blank_text_makes_no_call(self):
        with patch('apps.scholarship.vision._call_gemini_json') as m:
            r = vision.extract_document_fields('', 'salary_slip')
            self.assertEqual(r['error'], 'no text')
            m.assert_not_called()

    @patch('apps.scholarship.vision._call_gemini_json')
    def test_gemini_error_propagates_soft(self, mock_call):
        mock_call.return_value = {'_error': 'All AI models failed: boom'}
        self.assertIn('boom', vision.extract_document_fields('text', 'salary_slip')['error'])

    @override_settings(GEMINI_API_KEY='')
    def test_no_api_key_no_call(self):
        # The key guard short-circuits before importing/calling the SDK.
        self.assertIn('_error', vision._call_gemini_json('p', {}))


class TestRunFieldExtraction(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='fe', nric='030101-14-1234', name='Muthu Raman',
            postal_code='62100', city='Putrajaya')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted')

    def _doc(self, dt='salary_slip'):
        return ApplicantDocument.objects.create(application=self.app, doc_type=dt, storage_path='x')

    @patch('apps.scholarship.vision.extract_document_fields')
    def test_stores_and_stamps(self, mock_ex):
        mock_ex.return_value = {'fields': {'name': 'Muthu Raman'}, 'warnings': [], 'error': ''}
        doc = self._doc()
        vision.run_field_extraction_for_document(
            doc, names=['Muthu Raman'], ocr={'text': 'some text', 'error': None})
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['student_verdict'], 'ok')
        self.assertIsNotNone(doc.vision_fields_run_at)

    @patch('apps.scholarship.vision.extract_document_fields')
    def test_unreadable_skips_gemini(self, mock_ex):
        doc = self._doc()
        vision.run_field_extraction_for_document(
            doc, names=['Muthu Raman'], ocr={'text': '', 'error': 'could not fetch image'})
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['student_verdict'], 'unreadable')
        mock_ex.assert_not_called()

    @staticmethod
    def _spm_words():
        rows = [('BAHASA MELAYU', 'A-', 'CEMERLANG'), ('SEJARAH', 'B', 'KEPUJIAN TINGGI'),
                ('PERTANIAN', 'A', 'CEMERLANG TINGGI'), ('PERNIAGAAN', 'B', 'KEPUJIAN TINGGI')]
        words = [{'text': t, 'cx': 100 + i * 40, 'cy': 100, 'h': 20}
                 for i, t in enumerate('SIJIL PELAJARAN MALAYSIA'.split())]
        y = 300
        for subj, letter, band in rows:
            words += [{'text': t, 'cx': 100 + i * 60, 'cy': y, 'h': 20}
                      for i, t in enumerate(subj.split())]
            words.append({'text': letter, 'cx': 500, 'cy': y, 'h': 20})
            words += [{'text': t, 'cx': 560 + j * 80, 'cy': y, 'h': 20}
                      for j, t in enumerate(band.split())]
            y += 40
        return words

    @patch('apps.scholarship.vision.extract_document_fields')
    @patch('apps.scholarship.vision._vision_words')
    @patch('apps.scholarship.vision._fetch_image_bytes')
    def test_results_slip_uses_deterministic_ocr_not_gemini(self, mock_img, mock_words, mock_gemini):
        # SPM slip → positional OCR parse wins; Gemini (extract_document_fields) untouched.
        mock_img.return_value = b'fake-image-bytes'
        mock_words.return_value = {'words': self._spm_words(), 'error': None}
        doc = self._doc('results_slip')
        vision.run_field_extraction_for_document(doc, names=['Sharmila'])
        doc.refresh_from_db()
        got = {r['subject']: r['grade'] for r in doc.vision_fields['fields']['results']}
        self.assertEqual(got['Pertanian'], 'A')      # paired by geometry, not transposed
        self.assertEqual(got['Perniagaan'], 'B')
        mock_gemini.assert_not_called()

    @patch('apps.scholarship.vision.extract_document_fields')
    @patch('apps.scholarship.vision._vision_words')
    @patch('apps.scholarship.vision._fetch_image_bytes')
    def test_results_slip_falls_back_to_gemini_when_ocr_blank(self, mock_img, mock_words, mock_gemini):
        # OCR found nothing parseable → fall back to the Gemini image read.
        mock_img.return_value = b'fake-image-bytes'
        mock_words.return_value = {'words': [], 'error': None}
        mock_gemini.return_value = {'fields': {'results': [{'subject': 'X', 'grade': 'A'}]},
                                    'warnings': [], 'error': ''}
        doc = self._doc('results_slip')
        vision.run_field_extraction_for_document(doc, names=['Sharmila'])
        mock_gemini.assert_called_once()


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestUploadGuardrails(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(supabase_user_id=USER, nric='030101-14-1234', name='Muthu')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(USER)}')

    def _post(self, doc_type='salary_slip', size=1000):
        return self.client.post('/api/v1/scholarship/documents/', {
            'doc_type': doc_type, 'storage_path': f'{self.app.id}/{doc_type}/x',
            'original_filename': 'f.pdf', 'size': size}, format='json')

    @override_settings(MAX_DOC_SIZE_BYTES=8 * 1024 * 1024)
    def test_oversize_rejected(self):
        r = self._post(size=9 * 1024 * 1024)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'file_too_large')

    @override_settings(MAX_DOCS_PER_APPLICATION=3)
    def test_doc_limit_reached(self):
        # Fill to the cap with multi-instance docs (which don't replace).
        ApplicantDocument.objects.bulk_create([
            ApplicantDocument(application=self.app, doc_type='salary_slip', storage_path=f'x{i}') for i in range(3)])
        r = self._post(doc_type='water_bill')   # a new type → would exceed
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'doc_limit_reached')

    @override_settings(MAX_DOCS_PER_APPLICATION=3)
    def test_replacement_allowed_at_cap(self):
        # results_slip is single-instance → re-upload replaces, not blocked by cap.
        ApplicantDocument.objects.bulk_create([
            ApplicantDocument(application=self.app, doc_type='salary_slip', storage_path=f'x{i}') for i in range(2)])
        ApplicantDocument.objects.create(application=self.app, doc_type='results_slip', storage_path='r')
        r = self._post(doc_type='results_slip')   # replaces existing → allowed
        self.assertEqual(r.status_code, 201)

    @override_settings(DOC_ASSIST_RATE_LIMIT_PER_HOUR=2)
    def test_ai_throttle_skips_gemini_but_uploads(self):
        # Two recent extractions already this hour → the 3rd skips Gemini. (Different
        # doc types so the new salary_slip upload — now single-instance — doesn't sweep
        # them; the rate cap counts every extracted doc regardless of type.)
        ApplicantDocument.objects.bulk_create([
            ApplicantDocument(application=self.app, doc_type=dt,
                              storage_path=f'r-{dt}', vision_fields_run_at=timezone.now())
            for dt in ('water_bill', 'electricity_bill')])
        with patch('apps.scholarship.vision.run_field_extraction_for_document') as mock_run:
            r = self._post(doc_type='salary_slip')
            self.assertEqual(r.status_code, 201)          # upload still succeeds
            mock_run.assert_not_called()                  # Gemini skipped
        self.assertEqual(r.json()['vision_fields']['student_verdict'], 'review_manually')
