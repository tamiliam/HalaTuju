"""Water-bill signature scorer (genuineness/water_doc.py). Synthetic OCR text only — no PII. Design
+ calibration: docs/scholarship/water-bill-catalogue.md (validated on 28 live OCR'd bills, 0
false-rejects). GRAMMAR-first, operator-as-bonus — water is state-run with no single national
operator, so the shared bill grammar decides genuineness and the operator only names the family."""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.genuineness import assess
from apps.scholarship.genuineness.water_doc import (
    MODEL_VERSION, water_genuineness, score_markers)
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort


class TestWaterSignatures(SimpleTestCase):
    def _g(self, text):
        return water_genuineness(text)

    # ── genuine (recognised operator) ────────────────────────────────────────────
    def test_full_air_selangor_bill_is_genuine(self):
        text = ("AIR SELANGOR\nBil Air\nNo. Akaun 210262399810\nTempoh Bil 17.02.2026 - 16.03.2026\n"
                "Caj Air Semasa RM31.00\nTunggakan 0.00\nTarif Domestik\nPenggunaan 15 meter padu\n"
                "Jumlah Perlu Dibayar RM31.00\nSila bayar sebelum 05.04.2026")
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('genuine', 'air_selangor'))
        self.assertGreaterEqual(r['probability'], 0.70)

    def test_ranhill_saj_johor_is_genuine(self):
        text = ("RANHILL SAJ\nBekalan Air Johor\nNo. Akaun 55\nTunggakan 0.00\nTarif\n"
                "Jumlah Perlu Dibayar RM22.10\nTempoh Bil ...")
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('genuine', 'saj_johor'))

    # ── genuine (unlisted operator — grammar carries it) ─────────────────────────
    def test_unlisted_operator_with_water_grammar_is_genuine(self):
        # An operator we haven't catalogued (or a cropped letterhead) but full water grammar → the
        # grammar-first design must still pass it as genuine 'unrecognised' (the a69 corpus case).
        text = ("Bil Air\nMeter Air\nNo. Akaun 123\nTunggakan 0.00\nTarif\nPenggunaan 12 m3\n"
                "Jumlah Perlu Dibayar RM18.00")
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('genuine', 'unrecognised'))

    # ── suspect (thin/cropped — never rejected) ──────────────────────────────────
    def test_thin_operator_screenshot_is_suspect(self):
        # An operator app screenshot: header + amount but no field-label grammar → suspect, confirm.
        r = self._g("AIR SELANGOR\nJumlah RM 40.00")
        self.assertEqual((r['status'], r['family']), ('suspect', 'air_selangor'))
        self.assertNotEqual(r['status'], 'not_water_bill')

    # ── reject (wrong type / not a bill) ─────────────────────────────────────────
    def test_mykad_in_slot_is_rejected(self):
        r = self._g("KAD PENGENALAN\nWARGANEGARA\nKETUA PENGARAH PENDAFTARAN NEGARA\nLELAKI")
        self.assertEqual(r['status'], 'not_water_bill')

    def test_electricity_bill_in_slot_is_rejected(self):
        # The reverse of the #83 swap — a TNB electricity bill misfiled into the water slot (the a75
        # corpus case). No water signal at all → reject, family 'electricity_bill'.
        text = ("TENAGA NASIONAL BERHAD\nBil Elektrik Anda\nNo. Akaun 123\nKegunaan 250 kWh\n"
                "Caj Semasa RM112.95\nTarif Domestik Am")
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('not_water_bill', 'electricity_bill'))

    def test_empty_or_junk_rejected(self):
        for text in ('', '   ', 'blurry photo lorem ipsum dolor sit amet'):
            self.assertEqual(self._g(text)['status'], 'not_water_bill')

    # ── guards ───────────────────────────────────────────────────────────────────
    def test_genuine_water_bill_mentioning_elektrik_not_rejected(self):
        # Real PBAPP/SAMB bills in the corpus (a62/a9) mention 'elektrik' incidentally — the water
        # term must anchor them so the electricity-swap reject never fires on a genuine water bill.
        text = ("PBAPP\nBil Air\nPerbandingan penggunaan elektrik dan air\nNo. Akaun 9\n"
                "Tunggakan 0.00\nTarif\nJumlah Perlu Dibayar RM15.00\nPenggunaan 10 meter padu")
        self.assertEqual(self._g(text)['status'], 'genuine')

    def test_m3_alone_anchors_as_water(self):
        # Even without a 'Bil Air' term, an m³ usage unit + grammar keeps it out of the reject floor.
        text = ("No. Akaun 1\nPenggunaan 20 m3\nTunggakan 0\nTarif\nJumlah Perlu Dibayar RM25")
        self.assertEqual(self._g(text)['status'], 'genuine')

    def test_operator_never_collides_with_common_malay_word(self):
        # 'satu' (= "one") must NOT be read as the Terengganu operator; a bare word is not a marker.
        m = score_markers("Bayar satu kali sahaja")
        self.assertEqual(m['operator'], '')

    def test_score_markers_tallies(self):
        m = score_markers("AIR SELANGOR No. Akaun Tunggakan Tarif Jumlah Perlu Dibayar meter padu")
        self.assertEqual(m['operator'], 'air_selangor')
        self.assertTrue(m['m3'])
        self.assertGreaterEqual(m['labels'], 3)

    def test_model_version_stamped(self):
        self.assertEqual(self._g('AIR SELANGOR No. Akaun Tunggakan Tarif')['model_version'],
                         MODEL_VERSION)

    def test_assess_dispatch_routes_water_bill(self):
        r = assess('water_bill', ocr_text='AIR SELANGOR Bil Air No. Akaun Tunggakan Tarif Jumlah Perlu Dibayar')
        self.assertEqual((r['status'], r['family']), ('genuine', 'air_selangor'))


class TestWaterChipSurface(TestCase):
    """The cockpit chip: a not_water_bill (wrong type in the slot) surfaces the red 'wrong document'
    chip; a genuine/suspect bill is hidden (a thin/cropped bill is common → no amber noise)."""

    def setUp(self):
        cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        profile = StudentProfile.objects.create(supabase_user_id='sw', nric='030101-14-1234', name='X')
        self.app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='profile_complete')

    def _bill(self, auth_status):
        vf = {'authenticity': {'status': auth_status}} if auth_status is not None else {}
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='water_bill', storage_path='x',
            vision_fields=vf, uploaded_at=timezone.now())

    def test_serializer_surfaces_wrongtype_only(self):
        from apps.scholarship.serializers import ApplicantDocumentSerializer as S
        self.assertTrue(
            S(self._bill('not_water_bill')).data['authenticity']['status'].startswith('not_'))
        self.assertIsNone(S(self._bill('genuine')).data['authenticity'])
        self.assertIsNone(S(self._bill('suspect')).data['authenticity'])

    def test_unscored_legacy_bill_has_no_chip(self):
        from apps.scholarship.serializers import ApplicantDocumentSerializer as S
        self.assertIsNone(S(self._bill(None)).data['authenticity'])
