"""Salary-slip signature scorer (genuineness/salary_doc.py). Synthetic OCR text only — no PII.
Design: docs/scholarship/salary-signature-model.md."""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.genuineness import assess
from apps.scholarship.genuineness.salary_doc import MODEL_VERSION, salary_genuineness, score_family
from apps.scholarship.income_engine import usable_salary_slip
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.tests.factories import create_document


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

    # ── #85: statutory deductions win over missing wage labels (1.3.0) ──────────
    # Text with statutory words and NO wage label (none of _WAGE_LABELS appears in it).
    _STAT_ONLY = "KWSP 308.00\nPERKESO 12.75\nEIS 5.10\nBulan Mac 2026"

    def test_two_statutory_and_no_wage_label_is_a_private_payslip(self):
        """Regression (#85, case 242): the old cascade rejected this as 'no recognisable payslip fields'."""
        m = score_family(self._STAT_ONLY)
        self.assertEqual((m['statutory'], m['wage'], m['mykad']), (3, 0, False))
        r = self._g(self._STAT_ONLY)
        self.assertEqual((r['status'], r['family']), ('genuine', 'private'))
        self.assertEqual(r['probability'], 0.90)
        self.assertEqual(self._g('KWSP 308.00\nPERKESO 12.75')['probability'], 0.80)   # still >= GENUINE_MIN

    def test_mykad_wins_over_statutory_words(self):
        """The MyKad reject runs first: an identity card is refused even beside statutory words."""
        r = self._g("WARGANEGARA\nKETUA PENGARAH PENDAFTARAN NEGARA\nKWSP\nPERKESO")
        self.assertEqual((r['status'], r['family']), ('not_salary', 'not_salary'))
        self.assertTrue(r['reason'].startswith('MyKad'))

    def test_one_statutory_and_no_wage_label_is_still_not_salary(self):
        r = self._g("KWSP 308.00\nBulan Mac 2026")
        self.assertEqual(r['status'], 'not_salary')
        self.assertTrue(r['reason'].startswith('no recognisable payslip fields'))

    # ── #85 review round 1: on the no-wage path the deductions are WHOLE words (1.3.0) ──
    def test_no_wage_label_needs_whole_word_deductions(self):
        """'EIS' inside LEISURE / REISSUE and a tax form's LHDN beside a KWSP relief line counted as two
        deductions by substring (genuine/private 0.8). With no wage label they no longer do."""
        for text in ("KWSP i-Akaun\nLeisure", "KWSP\nREISSUE", "LHDN\nBorang BE 2025\nKWSP",
                     "LEISURE REISSUE\nEPF"):
            with self.subTest(text=text):
                m = score_family(text)
                self.assertGreaterEqual(m['statutory'], 2)            # the substring count still fires
                self.assertLess(m['statutory_words'], 2)
                r = self._g(text)
                self.assertEqual((r['status'], r['family']), ('not_salary', 'not_salary'))

    def test_whole_word_deductions_with_no_wage_label_are_a_payslip(self):
        r = self._g("KWSP 308.00\nPERKESO (SOCSO) 12.75\nPCB 40.00\nMac 2026")
        self.assertEqual((r['status'], r['family'], r['probability']), ('genuine', 'private', 0.9))
        r = self._g("Kumpulan Wang Simpanan Pekerja 308.00\nSistem Insurans Pekerjaan 5.10")   # phrases
        self.assertEqual((r['status'], r['family']), ('genuine', 'private'))

    def test_a_wage_label_keeps_the_substring_count(self):
        """Slips WITH a wage label are counted exactly as in 1.2.0 (moving them needs a corpus check)."""
        r = self._g("Slip Gaji\nKWSP 308.00\nLHDN")
        self.assertEqual((r['status'], r['family'], r['probability']), ('genuine', 'private', 0.83))

    # ── #85 review round 2: letter edges, glued amounts, payroll suffixes, MTD (1.3.0) ──
    def _words(self, text):
        return score_family(text)['statutory_words']

    def test_a_label_glued_to_its_amount_counts(self):
        """PDF text layers glue column labels to amounts; a digit is not a letter, so the word still counts.
        Round 1's padded match scored this 0 and left the slip not_salary."""
        text = "KWSP308.00\nPERKESO12.75\nEIS5.10"
        self.assertEqual(self._words(text), 3)
        self.assertEqual((self._g(text)['status'], self._g(text)['family']), ('genuine', 'private'))
        for text in ("EPF-EE 308.00", "KWSP: 308.00", "KWSP308", "(SOCSO)12.75"):
            with self.subTest(text=text):
                self.assertEqual(self._words(text), 1)

    def test_payroll_suffixes_glued_on_the_right_count(self):
        """Decision (round 2): a single-word label may carry ONE employee / employer suffix glued on its
        right — PEKERJA, MAJIKAN, EMPLOYEE, EMPLOYER, EE, ER — the payroll column heads."""
        text = "KWSPPEKERJA 308\nSOCSOEE 12"
        self.assertEqual(self._words(text), 2)
        self.assertEqual((self._g(text)['status'], self._g(text)['family']), ('genuine', 'private'))
        for text in ("KWSPMAJIKAN 400", "EPFER 400", "EISEMPLOYEE 5", "PCBEMPLOYER 0", "PERKESOEE 12"):
            with self.subTest(text=text):
                self.assertEqual(self._words(text), 1)

    def test_other_glued_letters_still_do_not_count(self):
        """A letter on the left, or a letter run that is not a known suffix, is still another word."""
        for text in ("LEISURE", "REISSUE", "AKAUNKWSP 308", "KWSPX 308", "EISX 5", "EPFEEX 3",
                     "SOCSOPEKERJAAN 12", "LEISURE REISSUE\nEPF"):
            with self.subTest(text=text):
                self.assertLess(self._words(text), 2)
                self.assertEqual(self._g(text + "\nMac 2026")['status'], 'not_salary')
        self.assertEqual(self._words("LEISURE REISSUE"), 0)

    def test_mtd_is_the_pcb_group_on_the_no_wage_path(self):
        """MTD (monthly tax deduction) is the English label for PCB — counted on the no-wage path only."""
        text = "EPF 308.00\nMTD 40.00\nMac 2026"
        self.assertEqual((score_family(text)['statutory'], self._words(text)), (1, 2))
        r = self._g(text)
        self.assertEqual((r['status'], r['family'], r['probability']), ('genuine', 'private', 0.8))
        self.assertEqual(self._words("PCB 40\nMTD 40"), 1)                  # one group, counted once
        self.assertEqual(self._words("LIMITED\nAMTD"), 0)                   # letter edges hold
        # A slip WITH a wage label is unchanged from 1.2.0: MTD does not join its substring count.
        r = self._g("Slip Gaji\nEPF 308.00\nMTD 40.00")
        self.assertEqual((r['status'], r['family']), ('suspect', 'informal'))

    def test_socso_and_eis_alone_are_two_groups_owner_ruling_25_nov(self):
        """Owner ruling 25 Nov 2026 (#85, decisions.md): PERKESO runs both SOCSO and EIS, but they stay
        separate groups — two of KWSP / SOCSO / EIS / PCB is enough, as the organisation was told."""
        r = self._g("SOCSO 12.75\nEIS 5.10\nMac 2026")
        self.assertEqual((r['status'], r['family']), ('genuine', 'private'))

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


class TestUsableSalarySlipGate(TestCase):
    """The #47 fix: a salary_slip scored 'not_salary' (a MyKad in the slot) no longer satisfies the
    income-proof requirement; unscored/genuine/suspect slips still count (fail-open)."""

    def setUp(self):
        cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        profile = StudentProfile.objects.create(supabase_user_id='s47', nric='030101-14-1234', name='X')
        self.app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='profile_complete',
            income_route='salary', income_working_members=['father'])

    def _slip(self, auth_status, doc_seen=None):
        vf = {'authenticity': {'status': auth_status}} if auth_status is not None else {}
        if doc_seen is not None:
            vf['authenticity']['doc_seen'] = doc_seen
            # An informal slip counts only signed and stamped since ruling 2A (#374) — approved here, as
            # this file is about the family; `test_income_declarations` owns the approver rule.
            from apps.scholarship.tests.factories import APPROVED_INFORMAL_FIELDS
            vf['fields'] = dict(APPROVED_INFORMAL_FIELDS)
        return create_document(
            application=self.app, doc_type='salary_slip', household_member='father',
            storage_path='x', vision_fields=vf, uploaded_at=timezone.now())

    def test_not_salary_slip_is_not_usable(self):
        self._slip('not_salary')
        self.assertFalse(usable_salary_slip(self.app, 'father'))

    def test_genuine_slip_is_usable(self):
        self._slip('genuine')
        self.assertTrue(usable_salary_slip(self.app, 'father'))

    def test_suspect_informal_slip_is_usable(self):
        """TD-410, owner option A: the model's `suspect` IS the informal family — still usable."""
        for seen in ('informal', None):
            with self.subTest(seen):
                ApplicantDocument.objects.filter(application=self.app).delete()
                self._slip('suspect', doc_seen=seen)
                self.assertTrue(usable_salary_slip(self.app, 'father'))

    def test_suspect_slip_of_another_family_is_not_usable(self):
        """TD-410: a suspect slip naming a formal family (no current writer — a legacy / future score)."""
        self._slip('suspect', doc_seen='private')
        self.assertFalse(usable_salary_slip(self.app, 'father'))

    def test_unscored_legacy_slip_fails_open(self):
        self._slip(None)   # no authenticity yet (the existing 100 slips)
        self.assertTrue(usable_salary_slip(self.app, 'father'))

    def test_serializer_surfaces_wrongtype_only(self):
        # The cockpit chip: a not_salary slip surfaces (red 'wrong document'); a genuine or informal
        # (suspect) slip is hidden — no amber noise on a genuine B40 family's informal payslip.
        from apps.scholarship.serializers import ApplicantDocumentSerializer as S
        self.assertTrue(S(self._slip('not_salary')).data['authenticity']['status'].startswith('not_'))
        self.assertIsNone(S(self._slip('genuine')).data['authenticity'])
        self.assertIsNone(S(self._slip('suspect')).data['authenticity'])
