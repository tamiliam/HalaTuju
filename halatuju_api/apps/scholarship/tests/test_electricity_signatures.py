"""Electricity-bill signature scorer (genuineness/electricity_doc.py). Synthetic OCR text only — no
PII. Design + calibration: docs/scholarship/electricity-bill-catalogue.md (validated on 27 live OCR'd
bills, 0 false-rejects)."""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.genuineness import assess
from apps.scholarship.genuineness.electricity_doc import (
    MODEL_VERSION, electricity_genuineness, score_markers)
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort


class TestElectricitySignatures(SimpleTestCase):
    def _g(self, text):
        return electricity_genuineness(text)

    # ── genuine ──────────────────────────────────────────────────────────────────
    def test_full_tnb_bill_is_genuine(self):
        text = ("TENAGA NASIONAL BERHAD\nBil Elektrik Anda\nNo. Akaun 210262399810\n"
                "Tarikh Bil 18.03.2026\nTempoh Bil 17.02.2026 - 16.03.2026\n"
                "Caj Semasa RM112.95\nBaki Terdahulu 0.00\nTarif Domestik Am\nKegunaan 250 kWj\n"
                "Sila bayar sebelum 05.04.2026")
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('genuine', 'tnb'))
        self.assertGreaterEqual(r['probability'], 0.70)

    def test_cropped_photo_without_issuer_header_is_genuine(self):
        # A cropped bill photo that lost the TNB letterhead but keeps electricity grammar + labels.
        text = ("Kegunaan 300 kWj\nCaj Semasa RM90.00\nTarikh Bil 01.05.2026\n"
                "Tempoh Bil ...\nBacaan Meter\nTarif")
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('genuine', 'unrecognised'))

    # ── suspect (thin/cropped — never rejected) ──────────────────────────────────
    def test_thin_tnb_screenshot_is_suspect(self):
        # A myTNB app screenshot: issuer + amount but no field-label grammar → suspect, officer confirms.
        r = self._g("TNB\nJumlah Perlu Dibayar RM 88.20")
        self.assertEqual((r['status'], r['family']), ('suspect', 'tnb'))
        self.assertNotEqual(r['status'], 'not_electricity_bill')

    # ── reject (wrong type / not a bill) ─────────────────────────────────────────
    def test_mykad_in_slot_is_rejected(self):
        r = self._g("KAD PENGENALAN\nWARGANEGARA\nKETUA PENGARAH PENDAFTARAN NEGARA\nLELAKI")
        self.assertEqual(r['status'], 'not_electricity_bill')

    def test_water_bill_in_slot_is_rejected(self):
        r = self._g("BIL AIR SELANGOR\nBekalan Air\nJumlah Perlu Dibayar RM40.00\nTunggakan 0.00")
        self.assertEqual((r['status'], r['family']), ('not_electricity_bill', 'water_bill'))

    def test_empty_or_junk_rejected(self):
        for text in ('', '   ', 'blurry photo lorem ipsum dolor sit amet'):
            self.assertEqual(self._g(text)['status'], 'not_electricity_bill')

    # ── guards ───────────────────────────────────────────────────────────────────
    def test_genuine_tnb_with_incidental_air_token_not_rejected(self):
        # A real TNB bill whose address contains 'AIR' (e.g. a street name) must NOT be water-rejected —
        # the issuer marker anchors it.
        text = ("TENAGA NASIONAL\nNo. Akaun 123\nJalan Air Panas\nCaj Semasa RM70\n"
                "Tarikh Bil 01.06.2026\nTarif Domestik\nKegunaan 200 kWj")
        self.assertEqual(self._g(text)['status'], 'genuine')

    def test_score_markers_tallies(self):
        m = score_markers("TNB No. Akaun Caj Semasa Tarikh Bil Tarif Kegunaan kWj")
        self.assertEqual(m['issuer'], 'tnb')
        self.assertGreaterEqual(m['labels'], 4)

    def test_model_version_stamped(self):
        self.assertEqual(self._g('TNB No. Akaun Caj Semasa Tarif')['model_version'], MODEL_VERSION)

    def test_assess_dispatch_routes_electricity_bill(self):
        r = assess('electricity_bill', ocr_text='TENAGA NASIONAL No. Akaun Caj Semasa Tarikh Bil Tarif')
        self.assertEqual((r['status'], r['family']), ('genuine', 'tnb'))


class TestElectricityChipSurface(TestCase):
    """The cockpit chip: a not_electricity_bill (wrong type in the slot) surfaces the red 'wrong
    document' chip; a genuine/suspect bill is hidden (a thin/cropped bill is common → no amber noise)."""

    def setUp(self):
        cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        profile = StudentProfile.objects.create(supabase_user_id='seb', nric='030101-14-1234', name='X')
        self.app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='profile_complete')

    def _bill(self, auth_status):
        vf = {'authenticity': {'status': auth_status}} if auth_status is not None else {}
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='electricity_bill', storage_path='x',
            vision_fields=vf, uploaded_at=timezone.now())

    def test_serializer_surfaces_wrongtype_only(self):
        from apps.scholarship.serializers import ApplicantDocumentSerializer as S
        self.assertTrue(
            S(self._bill('not_electricity_bill')).data['authenticity']['status'].startswith('not_'))
        self.assertIsNone(S(self._bill('genuine')).data['authenticity'])
        self.assertIsNone(S(self._bill('suspect')).data['authenticity'])

    def test_unscored_legacy_bill_has_no_chip(self):
        self.assertIsNone(S_data(self._bill(None)))


def S_data(doc):
    from apps.scholarship.serializers import ApplicantDocumentSerializer as S
    return S(doc).data['authenticity']
