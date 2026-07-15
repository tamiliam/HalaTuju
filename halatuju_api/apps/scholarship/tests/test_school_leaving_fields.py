"""School-leaving certificate field extraction (deterministic parser) + the officer chip check
(`student_school_leaving_check`). Synthetic OCR text only — no PII. Owner 2026-07-15: read the cert
OCR-first (deterministic) with Gemini fallback, and surface School / Name / IC / Behaviour chips +
the co-curricular leadership notes."""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.academic_engine import student_school_leaving_check
from apps.scholarship.doc_parse import parse_by_labels
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort

# A standard numbered Sijil Berhenti Sekolah (synthetic, modelled on the real form).
STD_CERT = (
    "SMK SEKSYEN 10 KOTA DAMANSARA\nSIJIL BERHENTI SEKOLAH\n"
    "1. Nama Murid : AARON A/L BALA\n2. Nama Bapa/Penjaga : BALA A/L RAJ\n"
    "3. No. Kad Pengenalan : 080114-10-1495\n"
    "13. Kurikulum/Sukan/Badan Khas:\n"
    "a. Jawatan : NAIB BENDAHARI PERSATUAN BAHASA TAMIL\n"
    "b. Jawatan : AHLI AKTIF KELAB KABADI\n"
    "14. Kelakuan : TERPUJI\n15. Tarikh Berhenti : 19/12/2025\n"
    "16. Sebab Berhenti : TAMAT PERSEKOLAHAN\n17. Catatan : SEORANG MURID YANG BERDISIPLIN\n")


class TestSchoolLeavingParser(SimpleTestCase):
    def _p(self, text):
        return parse_by_labels('school_leaving_cert', text)

    def test_parses_standard_cert(self):
        r = self._p(STD_CERT)
        self.assertIsNotNone(r)
        self.assertEqual(r['name'], 'AARON A/L BALA')
        self.assertEqual(r['nric'], '080114-10-1495')
        self.assertIn('SMK SEKSYEN 10', r['school'])
        self.assertEqual(r['kelakuan'], 'TERPUJI')

    def test_activities_capture_roles_and_catatan(self):
        # Leadership roles (both Jawatan lines) + the Catatan remark, folded into one field —
        # captured DETERMINISTICALLY so notes show on the Exact path too (owner 2026-07-15).
        r = self._p(STD_CERT)
        self.assertIn('NAIB BENDAHARI', r['activities'])
        self.assertIn('KELAB KABADI', r['activities'])
        self.assertIn('BERDISIPLIN', r['activities'])   # catatan folded in

    def test_free_form_testimonial_returns_none(self):
        # Leaver prose but no numbered-form 'Nama Murid' label → None → Gemini reads the prose.
        txt = ("SEKOLAH MENENGAH KEBANGSAAN TAMAN DESA\nSURAT AKUAN\n"
               "Adalah disahkan pelajar ini telah berhenti sekolah pada 2025 dan berkelakuan baik.")
        self.assertIsNone(self._p(txt))

    def test_non_leaver_returns_none(self):
        self.assertIsNone(self._p("random document with no leaver anchor at all"))

    def test_missing_school_header_returns_none(self):
        # Leaver anchor + Nama Murid but no readable school header → bail to Gemini (conservative).
        txt = "SIJIL BERHENTI SEKOLAH\n1. Nama Murid : X Y\n15. Tarikh Berhenti : 2025"
        self.assertIsNone(self._p(txt))

    # ── strict confidence gates (validated on the 18 live certs, 2026-07-15) ──────────────────
    def test_invalid_kelakuan_bails_to_gemini(self):
        # Real multi-column OCR: the Kelakuan value reads as the NEXT field, not a conduct word →
        # the parser must DEFER to Gemini rather than emit "16 Tarikh Berhenti Sekolah" (the #47 bug).
        txt = STD_CERT.replace("14. Kelakuan : TERPUJI", "14. Kelakuan :")
        self.assertIsNone(self._p(txt))

    def test_truncated_school_bails(self):
        # A 1-2-word school fragment ("SMK BUKIT") is a truncated OCR read → defer to Gemini (#80).
        self.assertIsNone(self._p(STD_CERT.replace("SMK SEKSYEN 10 KOTA DAMANSARA", "SMK BUKIT")))

    def test_kelakuan_strips_stray_colon(self):
        # A next-line value keeps a leading ':' (the #66 ": TERPUJI") — cleaned to the conduct word.
        r = self._p(STD_CERT.replace("14. Kelakuan : TERPUJI", "14. Kelakuan\n: TERPUJI"))
        self.assertEqual(r['kelakuan'], 'TERPUJI')

    def test_activities_filters_boilerplate(self):
        # 'Jawatan Khas' headers + 'jika ada' boilerplate are dropped; the real role stays (#80/#110).
        txt = STD_CERT.replace(
            "a. Jawatan : NAIB BENDAHARI PERSATUAN BAHASA TAMIL",
            "Jawatan Khas\na. Jawatan : jika ada\nb. Jawatan : NAIB BENDAHARI PERSATUAN BAHASA TAMIL")
        r = self._p(txt)
        self.assertIn('NAIB BENDAHARI', r['activities'])
        self.assertNotIn('jika ada', r['activities'].lower())


class TestSchoolLeavingCheck(TestCase):
    def setUp(self):
        cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        self.profile = StudentProfile.objects.create(
            supabase_user_id='sl2', nric='080114-10-1495', name='AARON A/L BALA',
            school='SMK SEKSYEN 10 KOTA DAMANSARA')
        self.app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=self.profile, status='profile_complete')

    def _doc(self, fields):
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='school_leaving_cert', storage_path='x',
            vision_fields={'student_verdict': 'ok', 'fields': fields}, uploaded_at=timezone.now())

    def test_match_and_values(self):
        c = student_school_leaving_check(self._doc({
            'name': 'AARON A/L BALA', 'nric': '080114-10-1495',
            'school': 'SMK SEKSYEN 10 KOTA DAMANSARA',
            'kelakuan': 'TERPUJI', 'activities': 'Ketua Pengawas'}))
        self.assertEqual(c['name_status'], 'match')
        self.assertEqual(c['nric_status'], 'match')
        self.assertEqual(c['school_status'], 'match')          # vs the student's declared school
        self.assertEqual(c['kelakuan_status'], 'good')         # TERPUJI → green
        self.assertEqual(c['activities'], 'Ketua Pengawas')

    def test_nric_and_school_mismatch(self):
        c = student_school_leaving_check(self._doc({
            'name': 'SOMEONE ELSE', 'nric': '010101-01-0101',
            'school': 'SEKOLAH MENENGAH TOTALLY DIFFERENT PLACE', 'kelakuan': '', 'activities': ''}))
        self.assertEqual(c['nric_status'], 'mismatch')
        self.assertEqual(c['school_status'], 'mismatch')
        self.assertEqual(c['kelakuan_status'], 'unknown')      # blank conduct → grey

    def test_kelakuan_quality_classification(self):
        def kq(v):
            return student_school_leaving_check(self._doc({'name': 'AARON A/L BALA', 'nric': '',
                'school': '', 'kelakuan': v, 'activities': ''}))['kelakuan_status']
        self.assertEqual(kq('BAIK'), 'good')
        self.assertEqual(kq('CEMERLANG'), 'good')
        self.assertEqual(kq('TERPUJI (EMAS)'), 'good')
        self.assertEqual(kq('SEDERHANA'), 'concern')
        self.assertEqual(kq('KURANG MEMUASKAN'), 'bad')        # NOT 'good' (contains 'MEMUASKAN')
        self.assertEqual(kq('TIDAK BAIK'), 'bad')

    def test_unread_returns_none(self):
        d = ApplicantDocument.objects.create(
            application=self.app, doc_type='school_leaving_cert', storage_path='x',
            vision_fields={}, uploaded_at=timezone.now())
        self.assertIsNone(student_school_leaving_check(d))

    def test_serializer_exposes_check(self):
        from apps.scholarship.serializers import ApplicantDocumentSerializer as S
        d = self._doc({'name': 'AARON A/L BALA', 'nric': '080114-10-1495', 'school': 'SMK X',
                       'kelakuan': 'BAIK', 'activities': ''})
        data = S(d).data
        self.assertEqual(data['school_leaving_check']['kelakuan'], 'BAIK')
        self.assertEqual(data['school_leaving_check']['name_status'], 'match')
