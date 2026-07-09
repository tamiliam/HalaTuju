"""Salary-slip signature scorer (genuineness/salary_doc.py). Synthetic OCR text only — no PII.
Design: docs/scholarship/salary-signature-model.md."""
from django.test import SimpleTestCase

from apps.scholarship.genuineness import assess
from apps.scholarship.genuineness.salary_doc import MODEL_VERSION, salary_genuineness, score_family


class TestSalarySignatures(SimpleTestCase):
    def _g(self, text):
        return salary_genuineness(text)

    # ── genuine families ────────────────────────────────────────────────────────
    def test_private_statutory_scaffold(self):
        # ≥2 statutory markers + wage labels → genuine private payslip.
        text = ("SLIP GAJI\nGaji Pokok 2,500.00\nElaun 300.00\nJumlah Pendapatan 2,800.00\n"
                "Potongan: KWSP 308.00  PERKESO 12.75  Gaji Bersih 2,479.25")
        r = self._g(text)
        self.assertEqual(r['status'], 'genuine')
        self.assertEqual(r['family'], 'private')
        self.assertGreaterEqual(r['probability'], 0.70)

    def test_govt_janm(self):
        text = ("PENYATA GAJI\nJABATAN PERKHIDMATAN AWAM\nGRED N19  No. Gaji 12345\n"
                "Pendapatan  Gaji Pokok 2,100.00  Bulan JAN 2026")
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('genuine', 'govt'))

    def test_singapore_cpf(self):
        text = ("Payslip\nABC PTE LTD\nBasic Pay 2000\nCPF 400\nNet Pay 1600\nMonth Jan")
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('genuine', 'singapore'))

    def test_gig_platform(self):
        text = "GRAB\nPendapatan minggu ini\nJumlah 1,200.00\nTrips 210"
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('genuine', 'gig'))

    # ── informal (low ceiling, never rejected) ───────────────────────────────────
    def test_informal_no_statutory(self):
        # Wage labels but NO statutory scaffold / issuer → suspect/informal, not rejected.
        text = "Slip Gaji\nNama: (redacted)\nPendapatan 1,500\nGaji Bersih 1,500\nBulan Mei"
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('suspect', 'informal'))
        self.assertNotEqual(r['status'], 'not_salary')

    # ── reject ───────────────────────────────────────────────────────────────────
    def test_mykad_in_slot_is_rejected(self):
        # The #47 class: a MyKad uploaded as a salary slip → not_salary.
        text = "KAD PENGENALAN\nWARGANEGARA\nKETUA PENGARAH PENDAFTARAN NEGARA\nLELAKI ISLAM"
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('not_salary', 'not_salary'))

    def test_empty_or_no_wage_fields_rejected(self):
        for text in ('', '   ', 'blurry photo lorem ipsum dolor sit amet'):
            self.assertEqual(self._g(text)['status'], 'not_salary')

    # ── guards ───────────────────────────────────────────────────────────────────
    def test_nric_label_is_not_a_reject_marker(self):
        # 'Kad Pengenalan' is a legitimate NRIC label on real payslips — must NOT reject a
        # genuine private slip that happens to print it.
        text = ("SLIP GAJI\nNo. Kad Pengenalan: xxxxxx-xx-xxxx\nGaji Pokok 3000\n"
                "KWSP 330  PERKESO 15  Gaji Bersih 2655")
        r = self._g(text)
        self.assertEqual(r['status'], 'genuine')

    def test_score_family_tallies(self):
        m = score_family("KWSP PERKESO Gaji Pokok Potongan Slip Gaji")
        self.assertEqual(m['statutory'], 2)
        self.assertGreaterEqual(m['wage'], 3)

    def test_model_version_stamped(self):
        self.assertEqual(self._g('KWSP PERKESO Slip Gaji Gaji Pokok')['model_version'], MODEL_VERSION)

    def test_assess_dispatch_routes_salary_slip(self):
        r = assess('salary_slip', ocr_text='KWSP PERKESO Slip Gaji Gaji Pokok Potongan')
        self.assertEqual(r['status'], 'genuine')
        self.assertEqual(r['family'], 'private')
