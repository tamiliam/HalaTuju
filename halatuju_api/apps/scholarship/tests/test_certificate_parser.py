"""Deterministic SPM CERTIFICATE parser (academic_engine.parse_spm_cert + ensure_exam_year).
Synthetic OCR text only — no real PII. Structure mirrors the live certs: a SUBJECT block then a
separate GRADE block (paired by index), 'layak dianugerahi', year at the foot ('Peperiksaan Tahun')."""
from django.test import SimpleTestCase

from apps.scholarship.academic_engine import ensure_exam_year, parse_spm_cert

# A clean cert: 5 subjects, 5 grades, year at the foot, name with a parentage marker.
CERT = """KEMENTERIAN PENDIDIKAN MALAYSIA
LEMBAGA PEPERIKSAAN
Calon yang namanya tercatat di bawah telah menduduki peperiksaan Sijil Pelajaran Malaysia (SPM) dan
layak dianugerahi
SIJIL PELAJARAN MALAYSIA
AISYAH BINTI RAHMAN
010101-01-0101
JH001A043
SMK CONTOH
Mata Pelajaran
Subject
BAHASA MELAYU
BAHASA INGGERIS
MATEMATIK
SEJARAH
SAINS
UJIAN LISAN BAHASA MELAYU: KEPUJIAN
Gred
Grade
A- (CEMERLANG)
B+ (KEPUJIAN TERTINGGI)
A (CEMERLANG TINGGI)
A+ (CEMERLANG TERTINGGI)
B (KEPUJIAN TINGGI)
JUMLAH MATA PELAJARAN LIMA
PEPERIKSAAN TAHUN 2022
Pengarah Peperiksaan
"""

# A cert with a SPLIT grade (letter and band on separate OCR lines) + a CEFR line in the grade block.
CERT_SPLIT = """Calon telah menduduki peperiksaan Sijil Pelajaran Malaysia (SPM) dan
layak dianugerahi
SIJIL PELAJARAN MALAYSIA
KUMAR A/L RAJAN
020202-02-0202
Mata Pelajaran
BAHASA MELAYU
MATEMATIK
SAINS
Gred
A- (CEMERLANG)
B
(KEPUJIAN TINGGI)
TAHAP KESELURUHAN CEFR BAHASA INGGERIS: B2
A (CEMERLANG TINGGI)
PEPERIKSAAN TAHUN 2024
"""

# A results SLIP (NOT a cert) — no 'layak dianugerahi'.
SLIP = """SIJIL PELAJARAN MALAYSIA TAHUN 2025
NAMA KUMAR A/L RAJAN
1103 BAHASA MELAYU A CEMERLANG TINGGI
Slip keputusan ini bukan sijil / pernyataan.
"""


class TestCertificateParser(SimpleTestCase):
    def test_clean_cert_parses(self):
        r = parse_spm_cert(CERT)
        self.assertIsNotNone(r)
        self.assertEqual(r['candidate_name'], 'AISYAH BINTI RAHMAN')
        self.assertEqual(r['nric'], '010101-01-0101')
        self.assertEqual(r['exam'], 'SIJIL PELAJARAN MALAYSIA TAHUN 2022')

    def test_subject_grade_pairing_by_index(self):
        results = parse_spm_cert(CERT)['results']
        got = {x['subject']: x['grade'] for x in results}
        self.assertEqual(got, {
            'Bahasa Melayu': 'A-', 'Bahasa Inggeris': 'B+', 'Matematik': 'A',
            'Sejarah': 'A+', 'Sains': 'B'})

    def test_year_from_foot_of_cert(self):
        # The cert's year lives at the foot ('Peperiksaan Tahun 2022'), not in the title.
        self.assertIn('2022', parse_spm_cert(CERT)['exam'])

    def test_split_grade_and_cefr_line(self):
        # A split grade ('B' + '(Kepujian Tinggi)') still counts as one; the CEFR line is skipped.
        r = parse_spm_cert(CERT_SPLIT)
        self.assertIsNotNone(r)
        self.assertEqual([x['grade'] for x in r['results']], ['A-', 'B', 'A'])
        self.assertIn('2024', r['exam'])

    def test_slip_is_not_a_cert(self):
        # No 'layak dianugerahi' → not a certificate → defer (None → the slip parser / Gemini).
        self.assertIsNone(parse_spm_cert(SLIP))

    def test_count_mismatch_defers(self):
        # Conservative: a grade dropped by OCR (4 subjects, 3 grades) → None, never a mis-paired read.
        bad = CERT.replace('SAINS\n', '').replace('BAHASA INGGERIS\n', '')  # drop 2 subjects → 3 subj / 5 grades
        self.assertIsNone(parse_spm_cert(bad))

    def test_self_identifying_no_profile_dependency(self):
        # Pure function of the text — no exam_type / profile input, so it runs for STPM students too.
        self.assertIsNotNone(parse_spm_cert(CERT))

    def test_ensure_exam_year_backfills_from_text(self):
        self.assertEqual(
            ensure_exam_year('SIJIL PELAJARAN MALAYSIA', 'foo PEPERIKSAAN TAHUN 2022 bar'),
            'SIJIL PELAJARAN MALAYSIA TAHUN 2022')

    def test_ensure_exam_year_idempotent(self):
        already = 'SIJIL PELAJARAN MALAYSIA TAHUN 2025'
        self.assertEqual(ensure_exam_year(already, 'PEPERIKSAAN TAHUN 2022'), already)

    def test_ensure_exam_year_no_year_in_text(self):
        self.assertEqual(ensure_exam_year('SIJIL PELAJARAN MALAYSIA', 'no year here'),
                         'SIJIL PELAJARAN MALAYSIA')
