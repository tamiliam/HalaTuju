"""School-leaving-certificate signature scorer (genuineness/school_leaving_doc.py). Synthetic OCR
text only — no PII. Leaver-anchor-first + standard numbered-form field labels: a *Sijil Berhenti
Sekolah* is school-issued (no single national issuer), so the leaver anchor marks the type and the
field labels grade confidence; a free-form testimonial defers (never 'fake'); a MyKad / another known
document in the slot is the wrong-type reject. See docs (retro 2026-07-15)."""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.genuineness import assess
from apps.scholarship.genuineness.school_leaving_doc import (
    MODEL_VERSION, school_leaving_genuineness, score_markers)
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort

# A full standard numbered Sijil Berhenti Sekolah (synthetic, modelled on the real form structure —
# the owner-specified signature set: title + Kad Pengenalan · Tarikh/Tempat Lahir · Tarikh Masuk
# Sekolah · Kelakuan · Tarikh/Sebab Berhenti).
FULL_CERT = (
    "SMK SEKSYEN 99 SHAH ALAM\nSIJIL BERHENTI SEKOLAH\n"
    "1. Nama Murid : AAAA A/L BBBB\n3. No. Kad Pengenalan : 080101-10-1234\n"
    "4. Tarikh Lahir : 14/01/2008\n5. Tempat Lahir : SELANGOR\n"
    "6. Tarikh Masuk Sekolah : 04/04/2022\n14. Kelakuan : TERPUJI\n"
    "15. Tarikh Berhenti : 19/12/2025\n16. Sebab Berhenti : TAMAT PERSEKOLAHAN TINGKATAN LIMA\n"
    "Tandatangan Pengetua")


class TestSchoolLeavingSignatures(SimpleTestCase):
    def _g(self, text):
        return school_leaving_genuineness(text)

    # ── genuine ──────────────────────────────────────────────────────────────────
    def test_full_standard_cert_is_genuine(self):
        r = self._g(FULL_CERT)
        self.assertEqual((r['status'], r['family']), ('genuine', 'sijil_berhenti'))
        self.assertGreaterEqual(r['probability'], 0.70)

    def test_leaver_anchor_without_title_but_labels_is_genuine(self):
        # No explicit title, but a leaver field label + several structural labels (a school's own
        # layout). 'Sebab/Tarikh Berhenti' both anchor as leaver signals.
        text = ("No. Kad Pengenalan : 1\nTarikh Lahir : 2008\nTempat Lahir : PERAK\n"
                "Kelakuan : BAIK\nSebab Berhenti : TAMAT\nTarikh Berhenti : 2025")
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('genuine', 'sijil_berhenti'))

    # ── suspect (thin/cropped — never rejected) ──────────────────────────────────
    def test_thin_leaver_read_is_suspect(self):
        r = self._g("SIJIL BERHENTI SEKOLAH\nNama Murid : X")
        self.assertEqual(r['status'], 'suspect')
        self.assertNotEqual(r['status'], 'not_school_leaving_cert')

    # ── unrecognised (testimonial — DEFER, never fake) ───────────────────────────
    def test_free_form_testimonial_defers(self):
        # A school letter with no numbered-form grammar and no leaver phrase → defer, not fake.
        text = ("SEKOLAH MENENGAH KEBANGSAAN TAMAN DESA\nSURAT PENGESAHAN\n"
                "Adalah disahkan bahawa pelajar berkelakuan baik.\nGuru Besar")
        r = self._g(text)
        self.assertEqual((r['status'], r['family']), ('unrecognised', 'testimonial'))

    def test_leaver_phrase_no_labels_defers(self):
        r = self._g("Surat ini mengesahkan pelajar telah berhenti sekolah pada 2025.")
        self.assertEqual(r['status'], 'unrecognised')
        self.assertNotEqual(r['status'], 'not_school_leaving_cert')

    # ── reject (wrong type / not the doc) ────────────────────────────────────────
    def test_mykad_in_slot_is_rejected(self):
        r = self._g("KAD PENGENALAN\nWARGANEGARA\nKETUA PENGARAH PENDAFTARAN NEGARA\nLELAKI")
        self.assertEqual(r['status'], 'not_school_leaving_cert')

    def test_results_slip_in_slot_is_rejected(self):
        # An SPM results slip misfiled as the leaving cert — no leaver anchor, matches the results
        # family → wrong-type reject (doc_seen names what it actually is).
        text = ("LEMBAGA PEPERIKSAAN\nKEMENTERIAN PENDIDIKAN\nSIJIL PELAJARAN MALAYSIA\n"
                "ANGKA GILIRAN\nNAMA MATA PELAJARAN\nGRED\nJUMLAH MATA PELAJARAN\n"
                "PENGARAH PEPERIKSAAN\nSLIP KEPUTUSAN INI BUKAN SIJIL")
        r = self._g(text)
        self.assertEqual(r['status'], 'not_school_leaving_cert')

    def test_empty_or_junk_rejected(self):
        for text in ('', '   ', 'blurry photo lorem ipsum dolor sit amet'):
            self.assertEqual(self._g(text)['status'], 'not_school_leaving_cert')

    # ── guards ───────────────────────────────────────────────────────────────────
    def test_genuine_cert_mentioning_spm_not_taken_for_a_results_slip(self):
        # The real form has a 'Tahun Peperiksaan SPM' line — its leaver anchor must protect it from
        # the results-slip misfile path (which only runs when NO leaver signal is present).
        self.assertEqual(self._g(FULL_CERT)['status'], 'genuine')

    def test_score_markers_expose_label_names(self):
        m = score_markers(FULL_CERT)
        self.assertTrue(m['title'])
        self.assertTrue(m['leaver'])
        self.assertGreaterEqual(m['labels'], 5)
        self.assertIn('KELAKUAN', m['label_names'])

    def test_model_version_stamped(self):
        self.assertEqual(self._g(FULL_CERT)['model_version'], MODEL_VERSION)

    def test_assess_dispatch_routes_school_leaving_cert(self):
        r = assess('school_leaving_cert', ocr_text=FULL_CERT)
        self.assertEqual((r['status'], r['family']), ('genuine', 'sijil_berhenti'))


class TestSchoolLeavingChipSurface(TestCase):
    """The cockpit chip: a not_school_leaving_cert (wrong type in the slot) surfaces the red 'wrong
    document' chip; a genuine / suspect / unrecognised cert is hidden (a thin cert or a testimonial is
    common for real B40 families → no amber noise, never a false reject)."""

    def setUp(self):
        cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        profile = StudentProfile.objects.create(supabase_user_id='sl', nric='030101-14-1234', name='X')
        self.app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='profile_complete')

    def _cert(self, auth_status):
        vf = {'authenticity': {'status': auth_status}} if auth_status is not None else {}
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='school_leaving_cert', storage_path='x',
            vision_fields=vf, uploaded_at=timezone.now())

    def test_serializer_surfaces_wrongtype_only(self):
        from apps.scholarship.serializers import ApplicantDocumentSerializer as S
        self.assertTrue(
            S(self._cert('not_school_leaving_cert')).data['authenticity']['status'].startswith('not_'))
        self.assertIsNone(S(self._cert('genuine')).data['authenticity'])
        self.assertIsNone(S(self._cert('suspect')).data['authenticity'])
        self.assertIsNone(S(self._cert('unrecognised')).data['authenticity'])

    def test_unscored_legacy_cert_has_no_chip(self):
        from apps.scholarship.serializers import ApplicantDocumentSerializer as S
        self.assertIsNone(S(self._cert(None)).data['authenticity'])


class TestAcademicDuplicateCollapse(TestCase):
    """The same cert requested twice by an officer lands in two request_code slots, both live (app
    #66). _collapse_duplicate_docs keeps the best by doc_quality and supersedes the rest."""

    def setUp(self):
        cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        profile = StudentProfile.objects.create(supabase_user_id='ad', nric='030101-14-1234', name='X')
        self.app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='profile_complete')

    def _cert(self, request_code, genuine=True):
        st = 'genuine' if genuine else 'suspect'
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='school_leaving_cert', storage_path='x',
            request_code=request_code, vision_fields={'authenticity': {'status': st}},
            uploaded_at=timezone.now())

    def test_collapse_keeps_one_live_copy(self):
        from apps.scholarship.views import _collapse_duplicate_docs
        older = self._cert('officer_1', genuine=False)   # suspect
        newer = self._cert('officer_9', genuine=True)    # genuine — should win
        _collapse_duplicate_docs(self.app, 'school_leaving_cert', '')
        live = ApplicantDocument.objects.filter(
            application=self.app, doc_type='school_leaving_cert', superseded_at__isnull=True)
        self.assertEqual(list(live.values_list('id', flat=True)), [newer.id])
        older.refresh_from_db()
        self.assertEqual(older.superseded_by_id, newer.id)

    def test_collapse_noop_on_single_copy(self):
        from apps.scholarship.views import _collapse_duplicate_docs
        only = self._cert('officer_1')
        _collapse_duplicate_docs(self.app, 'school_leaving_cert', '')
        only.refresh_from_db()
        self.assertIsNone(only.superseded_at)
