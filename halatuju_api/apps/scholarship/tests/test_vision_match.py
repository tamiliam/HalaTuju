"""Tests for the generic supporting-document soft name/address presence checks."""
from unittest.mock import patch

from django.test import TestCase

from apps.courses.models import StudentProfile
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.vision import (
    address_present, name_present, run_vision_match_for_document,
)


class TestPresenceMatchers(TestCase):
    def test_name_present_student_or_guardian(self):
        text = 'TENAGA NASIONAL BERHAD\nBil untuk: MUTHU A/L RAMAN\nJumlah: RM85.40'
        self.assertTrue(name_present(text, ['Muthu Raman']))          # student (connector-stripped)
        self.assertTrue(name_present(text, ['Someone Else', 'Muthu Raman']))  # any in the list
        self.assertFalse(name_present(text, ['Priya Devi']))          # not on the document
        self.assertFalse(name_present('', ['Muthu Raman']))           # empty text

    def test_name_present_tolerates_order_and_extra_words(self):
        self.assertTrue(name_present('Account holder: RAMAN, MUTHU KUMAR', ['Muthu Raman']))

    def test_address_present_postcode_and_city(self):
        text = 'No 12 Jalan ABC\n62100 PUTRAJAYA\nWILAYAH PERSEKUTUAN'
        self.assertTrue(address_present(text, postcode='62100', city='Putrajaya'))
        self.assertFalse(address_present(text, postcode='50000', city='Putrajaya'))   # wrong postcode
        self.assertFalse(address_present('random text', postcode='62100', city='KL'))


class TestRunVisionMatch(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='vm', nric='030101-14-1234', name='Muthu Raman',
            postal_code='62100', city='Putrajaya')
        cls.app = ScholarshipApplication.objects.create(
            cohort=cls.cohort, profile=cls.profile, status='shortlisted')

    def _doc(self, doc_type='str'):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type=doc_type, storage_path='x')

    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img')
    @patch('apps.scholarship.vision.extract_text')
    def test_name_found(self, mock_text, _fetch):
        mock_text.return_value = {'text': 'Salary slip for MUTHU RAMAN', 'error': None}
        doc = self._doc('salary_slip')
        run_vision_match_for_document(doc, names=['Muthu Raman'])
        doc.refresh_from_db()
        self.assertEqual(doc.vision_name_match, 'found')
        self.assertEqual(doc.vision_address_match, '')   # not a bill

    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img')
    @patch('apps.scholarship.vision.extract_text')
    def test_name_not_found(self, mock_text, _fetch):
        mock_text.return_value = {'text': 'Salary slip for SOMEONE ELSE', 'error': None}
        doc = self._doc('salary_slip')
        run_vision_match_for_document(doc, names=['Muthu Raman'])
        doc.refresh_from_db()
        self.assertEqual(doc.vision_name_match, 'not_found')

    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img')
    @patch('apps.scholarship.vision.extract_text')
    def test_bill_checks_address(self, mock_text, _fetch):
        mock_text.return_value = {
            'text': 'TNB bill\nMUTHU RAMAN\nNo 12 Jalan ABC 62100 PUTRAJAYA', 'error': None}
        doc = self._doc('electricity_bill')
        run_vision_match_for_document(
            doc, names=['Muthu Raman'], postcode='62100', city='Putrajaya', check_address=True)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_name_match, 'found')
        self.assertEqual(doc.vision_address_match, 'found')

    @patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img')
    @patch('apps.scholarship.vision.extract_text')
    def test_unreadable_on_error(self, mock_text, _fetch):
        mock_text.return_value = {'text': '', 'error': 'API quota exceeded'}
        doc = self._doc('water_bill')
        run_vision_match_for_document(doc, names=['Muthu Raman'], check_address=True)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_name_match, 'unreadable')
        self.assertEqual(doc.vision_address_match, 'unreadable')


class TestExtractNameHeaderBlocklist(TestCase):
    """_extract_name must pick the real name, not a MyKad header/label line."""

    def _name(self, text, nric=''):
        from apps.scholarship.vision import _extract_name
        return _extract_name(text, nric)

    def test_skips_header_phrases_picks_name(self):
        # "WARGANEGARA MALAYSIA" (20 chars) is LONGER than "MUTHU RAMAN" (11) —
        # the old heuristic would have grabbed it. The blocklist skips it.
        text = ("KAD PENGENALAN\nMYKAD\n850101-14-5523\nMUTHU RAMAN\n"
                "WARGANEGARA MALAYSIA\nLELAKI\nISLAM\nNO 12 JALAN ABC\n50000 KUALA LUMPUR")
        self.assertEqual(self._name(text, '850101-14-5523'), 'MUTHU RAMAN')

    def test_header_only_text_returns_empty(self):
        text = "KAD PENGENALAN\nMYKAD\nWARGANEGARA MALAYSIA\nLELAKI"
        self.assertEqual(self._name(text), '')

    def test_normal_name_still_extracted(self):
        # Regression: a plain card with a parentage marker still reads the name.
        text = "KAD PENGENALAN\n030101-14-1234\nPRIYA A/L KRISHNAN\nWARGANEGARA MALAYSIA"
        self.assertEqual(self._name(text, '030101-14-1234'), 'PRIYA A/L KRISHNAN')

    def test_name_containing_malaysia_word_kept(self):
        # A name that happens to include a blocklist word is NOT dropped (only
        # lines made up ENTIRELY of header tokens are skipped).
        text = "KAD PENGENALAN\nNUR MALAYSIA BINTI ALI\nWARGANEGARA MALAYSIA"
        self.assertEqual(self._name(text), 'NUR MALAYSIA BINTI ALI')
