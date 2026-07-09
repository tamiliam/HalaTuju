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

    def test_bill_holder_not_name_checked(self):
        # Owner 2026-07-09 (#130): a utility bill is an ADDRESS anchor in a PARENT's name — a holder
        # who isn't in the reference names is NOT a name_mismatch (that looped the student forever).
        for dt in ('water_bill', 'electricity_bill'):
            self.assertEqual(vision.doc_student_verdict(
                dt, {'name': 'SIVAKUMAR A/L KALIAPPAN', 'address': '12 Jln Mawar', 'amount': 'RM90'},
                names=['A Different Student']), 'ok')

    def test_str_recipient_not_name_checked(self):
        # Owner 2026-07-09 (#126): an STR recipient is a PARENT/earner — the proper household match is
        # done by student_str_check, not this display verdict. A parent-name recipient not in the
        # narrow reference names must NOT read 'name_mismatch' (it panicked the student into junk).
        self.assertEqual(vision.doc_student_verdict(
            'str', {'recipient_name': 'VIMALA A/P MUNIANDY', 'status': 'Lulus',
                    'source_type': 'semakan_status'},
            names=['A Different Student']), 'ok')


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

    @patch('apps.scholarship.vision._call_gemini_json')
    def test_extract_str_classifies_source_type(self, mock_call):
        # #5: the STR extractor returns source_type (closed set) alongside the currency facts.
        mock_call.return_value = {'recipient_name': 'Susila A/P Kanniah', 'recipient_nric': '601006055058',
                                  'status': 'Lulus', 'year': '', 'amount': 'RM 1,200',
                                  'source_type': 'semakan_status', 'warnings': []}
        r = vision.extract_document_fields('Semakan Status ... Status Permohonan Semasa Lulus', 'str')
        self.assertEqual(r['error'], '')
        self.assertEqual(r['fields']['source_type'], 'semakan_status')
        self.assertEqual(r['fields']['status'], 'Lulus')

    def test_str_schema_has_closed_source_type_enum(self):
        props = vision._FIELD_SCHEMAS['str']['properties']
        self.assertIn('source_type', props)
        self.assertEqual(set(props['source_type']['enum']),
                         {'letter', 'semakan_status', 'dashboard', 'unknown'})

    def test_str_hint_describes_the_three_layouts_and_tarikh_kredit(self):
        h = vision._DOC_HINTS['str'].lower()
        for token in ('semakan_status', 'dashboard', 'letter', 'tarikh', 'semasa'):
            self.assertIn(token, h)

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

    @patch('apps.scholarship.vision.extract_document_fields')
    @patch('apps.scholarship.vision._fetch_image_bytes')
    @patch('apps.scholarship.doc_parse.parse_by_labels')
    def test_birth_certificate_reads_image_when_deterministic_defers(self, mock_parse, mock_img, mock_gemini):
        # When the conservative deterministic BC parser can't lock on, the Gemini fallback must read
        # the IMAGE (not the OCR-flattened text, which cross-wires the child's far-off "Nama" with the
        # father's fuller name — #10: child read as 'MUGINDRAN A/L ATHIAH' instead of 'TAANUSIYA').
        mock_parse.return_value = None
        mock_img.return_value = b'fake-bc-image'
        mock_gemini.return_value = {'fields': {'bc_child_name': 'TAANUSIYA',
                                               'bc_father_name': 'MUGINDRAN A/L ATHIAH',
                                               'bc_mother_name': 'THAVAMALAR A/P VIJAYAN'},
                                    'warnings': [], 'error': ''}
        doc = self._doc('birth_certificate')
        vision.run_field_extraction_for_document(
            doc, names=['Muthu Raman'],
            ocr={'text': 'SIJIL KELAHIRAN KANAK-KANAK Nama TAANUSIYA No. Kad Pengenalan', 'error': None})
        self.assertEqual(mock_gemini.call_count, 1)
        # the IMAGE was passed (image=...), NOT the scrambled OCR text
        self.assertEqual(mock_gemini.call_args.kwargs.get('image'), b'fake-bc-image')
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['fields']['bc_child_name'], 'TAANUSIYA')

    @patch('apps.scholarship.vision.extract_document_fields')
    @patch('apps.scholarship.vision._fetch_image_bytes')
    @patch('apps.scholarship.doc_parse.parse_by_labels')
    def test_birth_certificate_image_fallback_uses_text_if_no_image(self, mock_parse, mock_img, mock_gemini):
        # If the image can't be fetched, the BC fallback still degrades to the OCR-text read.
        mock_parse.return_value = None
        mock_img.return_value = None
        mock_gemini.return_value = {'fields': {'bc_child_name': 'X'}, 'warnings': [], 'error': ''}
        doc = self._doc('birth_certificate')
        vision.run_field_extraction_for_document(
            doc, names=['Muthu Raman'], ocr={'text': 'SIJIL KELAHIRAN ...', 'error': None})
        self.assertIsNone(mock_gemini.call_args.kwargs.get('image'))   # text path, no image


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
    def test_interactive_upload_forces_read_past_throttle(self):
        # Race fix (2026-06-12): the doc the student JUST uploaded is always read, even
        # when the hourly doc-assist cap is already hit. A deferred 'review_manually' read
        # is exactly what let an unscanned upload greenlight its task (it read as 'pending'
        # → 'ok' before the scan finished). The interactive upload now forces the read.
        # (Different doc types so the single-instance salary_slip upload doesn't sweep them;
        # the rate cap counts every extracted doc regardless of type.)
        ApplicantDocument.objects.bulk_create([
            ApplicantDocument(application=self.app, doc_type=dt,
                              storage_path=f'r-{dt}', vision_fields_run_at=timezone.now())
            for dt in ('water_bill', 'electricity_bill')])
        with patch('apps.scholarship.vision.run_field_extraction_for_document') as mock_run:
            r = self._post(doc_type='salary_slip')
            self.assertEqual(r.status_code, 201)          # upload still succeeds
            mock_run.assert_called_once()                 # forced read past the cap


class TestExtractionSanitizer(TestCase):
    """Item B — deterministic guards so a header/label or a wrong-section name can't pass
    through as a person's name (the BC child / slip name misreads)."""

    def test_looks_like_non_name(self):
        self.assertTrue(vision._looks_like_non_name('KERAJAAN MALAYSIA'))
        self.assertTrue(vision._looks_like_non_name('KANAK-KANAK'))
        self.assertFalse(vision._looks_like_non_name('TAANUSIYA A/P MUGINDRAN'))

    def test_slip_candidate_name_label_stripped(self):
        out = vision._sanitize_extracted_fields(
            'results_slip', {'candidate_name': 'NAMA : SANJANA A / P KALIANA KUMAR'})
        self.assertEqual(out['candidate_name'], 'SANJANA A / P KALIANA KUMAR')

    def test_bc_child_equal_to_father_is_blanked(self):
        # #10: the BAPA 'Nama' was pulled into the child slot → blank it (soft 'unread'),
        # never a wrong-person child mismatch.
        out = vision._sanitize_extracted_fields('birth_certificate', {
            'bc_child_name': 'MUGINDRAN A/L ATHIAH', 'bc_father_name': 'MUGINDRAN A/L ATHIAH',
            'bc_mother_name': 'THAVAMALAR A/P VIJAYAN'})
        self.assertEqual(out['bc_child_name'], '')

    def test_bc_child_header_is_blanked(self):
        out = vision._sanitize_extracted_fields('birth_certificate', {
            'bc_child_name': 'KERAJAAN MALAYSIA', 'bc_father_name': 'X A/L Y', 'bc_mother_name': 'Z A/P W'})
        self.assertEqual(out['bc_child_name'], '')

    def test_bc_genuine_child_kept(self):
        out = vision._sanitize_extracted_fields('birth_certificate', {
            'bc_child_name': 'TAANUSIYA A/P MUGINDRAN', 'bc_father_name': 'MUGINDRAN A/L ATHIAH',
            'bc_mother_name': 'THAVAMALAR A/P VIJAYAN'})
        self.assertEqual(out['bc_child_name'], 'TAANUSIYA A/P MUGINDRAN')


class TestReportingDateNormalisation(TestCase):
    """Offer reporting_date → clean 'D Mon YYYY' (strip weekday/time/parenthetical; range→start)."""
    def test_variants(self):
        from apps.scholarship.vision import _normalise_reporting_date as N
        cases = {
            '22/06/2026': '22 Jun 2026',
            '13 JUN 2026 (SABTU)': '13 Jun 2026',
            '20 Julai 2026 Isnin': '20 Jul 2026',
            '08 Jun 2026 (Isnin)': '8 Jun 2026',
            '20 JUN 2026 (2.30 PETANG - 4.00 PETANG)': '20 Jun 2026',
            '8 HINGGA 9 JUN 2026': '8 Jun 2026',                 # range → start
            '13 MEI HINGGA 06 JUN 2026': '13 May 2026',          # range, year only at end
            '2 September 2025': '2 Sep 2025',
            '26 OGOS 2024': '26 Aug 2024',
            '28 JULAI 2024 2:30 PETANG - 4:30 PETANG': '28 Jul 2024',
        }
        for raw, want in cases.items():
            self.assertEqual(N(raw), want, raw)

    def test_unparseable_is_kept(self):
        from apps.scholarship.vision import _normalise_reporting_date as N
        self.assertEqual(N('TBA'), 'TBA')
        self.assertEqual(N(''), '')

    def test_wired_into_sanitizer(self):
        from apps.scholarship.vision import _sanitize_extracted_fields
        out = _sanitize_extracted_fields('offer_letter', {'reporting_date': '20 JUN 2026 (SABTU)'})
        self.assertEqual(out['reporting_date'], '20 Jun 2026')
