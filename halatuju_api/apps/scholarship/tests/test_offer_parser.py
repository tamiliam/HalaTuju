"""Deterministic government-offer parser (offer_parse.parse_govt_offer). Synthetic OCR text only
(fake names/NRICs) — mirrors the real STPM / Matrikulasi / Polytechnic layouts: identity on same/
adjacent lines, pathway+intake in the title, institution + reporting date in the info block."""
from django.test import SimpleTestCase

from apps.scholarship.offer_parse import parse_govt_offer

STPM = """PEJABAT TIMBALAN KETUA PENGARAH PENDIDIKAN MALAYSIA
SEKTOR OPERASI SEKOLAH
Tarikh : 24 April 2026
Nama: AISYAH BINTI RAHMAN
No. Kad Pengenalan: 080514140354
TAWARAN KEMASUKAN KE TINGKATAN ENAM SEMESTER 1 TAHUN 2026
2.1. Bidang
2.2. Pusat Tingkatan Enam
2.3. Tarikh Lapor Diri
SAINS
SEKOLAH MENENGAH KEBANGSAAN MAXWELL
08 Jun 2026
"""

# #117 (KIRIIYARASAN): the OCR text layer joined each label to its value on ONE line (glued), which
# broke the line-anchored reads — name ran into the NRIC label, the institution sat after its label,
# and the real 'Tarikh Lapor Diri' line was skipped by the TARIKH guard.
STPM_GLUED = """PEJABAT TIMBALAN KETUA PENGARAH PENDIDIKAN MALAYSIA
SEKTOR OPERASI SEKOLAH
Tarikh CETAK : 14 April 2026
Nama: KIRIIYARASAN A/L MUNIANDY No. Kad Pengenalan: 080111140499
TAWARAN KEMASUKAN KE TINGKATAN ENAM SEMESTER 1 TAHUN 2026
2.1 Bidang SAINS
2.2 Pusat Tingkatan Enam KOLEJ TINGKATAN ENAM GOMBAK
2.3 Tarikh Lapor Diri 08 Jun 2026
"""

MATRIC = """KEMENTERIAN PENDIDIKAN
Bahagian Matrikulasi
Tarikh: 27 APRIL 2026
KUMAR A/L RAJAN
K/P: 080923060355
TAWARAN KEMASUKAN PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN SESI 2026/2027
Jurusan:
Tempoh Pengajian:
Kolej:
Pendaftaran dalam talian:
Tarikh Kemasukan ke kolej:
Yuran Pendaftaran:
SAINS
DUA SEMESTER (10 BULAN)
KOLEJ MATRIKULASI PAHANG
13 MEI HINGGA 06 JUN 2026
8 JUN 2026
RM499.00
"""

POLY = """JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI
Tarikh: 25/05/2026
JANANI A/P SURESH (081014080994)
SURAT TAWARAN PENGAJIAN SESI : 2026/2027
Program
Mod Pengajian
Institusi
Tempoh Pengajian
:DPM-DIPLOMA PENGAJIAN PERNIAGAAN
SEPENUH MASA
:POLITEKNIK UNGKU OMAR
:6 SEMESTER
Tarikh dan Masa Daftar: 20 JUN 2026 (8.30 PAGI)
"""


# #125 (RUBESHAN): an Asasi-TVET-at-Politeknik letter whose info block is INTERLEAVED
# (label, value, label, value) rather than block-grouped. The _info_block_pairs zip mis-paired
# it — the institution landed in the programme slot and the 'Tarikh dan Masa Daftar' line in the
# institution slot (the stored fault). The parser now reads it correctly (per-label recovery +
# slot guard). Reconstructed layout — the deterministic path doesn't persist raw OCR, so this
# faithfully reproduces the stored mis-slot signature rather than the exact bytes.
POLY_ASASI_INTERLEAVED = """JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI
Tarikh: 15 JUN 2026
RUBESHAN A/L SANTHASWARAN (080130080735)
SURAT TAWARAN PENGAJIAN SESI : 2026/2027
Program
:ASASI TEKNOLOGI KEJURUTERAAN (ASASI TVET)
Institusi
POLITEKNIK SULTAN IDRIS SHAH
Tarikh dan Masa Daftar: 15 JUN 2026 (8.00 PAGI - 11.00 PAGI)
"""


class TestGovtOfferParser(SimpleTestCase):
    def test_polytechnic_asasi_interleaved_125(self):
        # The reproduced #125 fault must now read cleanly — never institution-as-programme
        # or a 'Tarikh…' line as the institution.
        r = parse_govt_offer(POLY_ASASI_INTERLEAVED)
        self.assertIsNotNone(r)
        self.assertEqual(r['_family'], 'polytechnic')
        self.assertEqual(r['candidate_name'], 'RUBESHAN A/L SANTHASWARAN')
        self.assertIn('ASASI TEKNOLOGI KEJURUTERAAN', r['programme'])
        self.assertEqual(r['institution'], 'POLITEKNIK SULTAN IDRIS SHAH')
        self.assertNotIn('Tarikh', r['institution'])
        self.assertIn('15 JUN 2026', r['reporting_date'])

    def test_stpm(self):
        r = parse_govt_offer(STPM)
        self.assertEqual(r['_family'], 'stpm')
        self.assertEqual(r['candidate_name'], 'AISYAH BINTI RAHMAN')
        self.assertEqual(r['candidate_nric'], '080514-14-0354')
        self.assertEqual(r['programme'], 'Tingkatan Enam Semester 1')
        self.assertEqual(r['intake'], '2026')
        self.assertIn('SEKOLAH', r['institution'])
        self.assertIn('2026', r['reporting_date'])
        self.assertEqual(r['stream'], 'SAINS')           # #117 (a) — Bidang now captured (block layout)

    def test_stpm_glued_lines(self):
        # #117: every label glued to its value on one line. All four reads must still land.
        r = parse_govt_offer(STPM_GLUED)
        self.assertEqual(r['_family'], 'stpm')
        self.assertEqual(r['candidate_name'], 'KIRIIYARASAN A/L MUNIANDY')   # truncated at the NRIC label
        self.assertEqual(r['candidate_nric'], '080111-14-0499')
        self.assertEqual(r['institution'], 'KOLEJ TINGKATAN ENAM GOMBAK')    # value after the label
        self.assertEqual(r['stream'], 'SAINS')                               # Bidang
        self.assertIn('08 Jun 2026', r['reporting_date'])                    # Tarikh Lapor Diri, not skipped
        self.assertNotIn('Bidang', r['institution'])                        # not swallowed by the institution

    def test_matriculation(self):
        r = parse_govt_offer(MATRIC)
        self.assertEqual(r['_family'], 'matriculation')
        self.assertEqual(r['candidate_name'], 'KUMAR A/L RAJAN')
        self.assertEqual(r['candidate_nric'], '080923-06-0355')
        self.assertIn('Matrikulasi', r['programme'])
        self.assertEqual(r['intake'], '2026/2027')
        self.assertEqual(r['institution'], 'KOLEJ MATRIKULASI PAHANG')
        self.assertIn('JUN 2026', r['reporting_date'])

    def test_polytechnic(self):
        r = parse_govt_offer(POLY)
        self.assertEqual(r['_family'], 'polytechnic')
        self.assertEqual(r['candidate_name'], 'JANANI A/P SURESH')
        self.assertEqual(r['candidate_nric'], '081014-08-0994')
        self.assertIn('DIPLOMA', r['programme'])
        self.assertEqual(r['intake'], '2026/2027')
        self.assertIn('POLITEKNIK', r['institution'])
        self.assertIn('JUN 2026', r['reporting_date'])

    def test_university_offer_defers(self):
        # A university offer (no govt-issuer marker) is NOT recognised → None → Gemini.
        uni = ("UNIVERSITI MALAYA\nSurat Tawaran Kemasukan\n"
               "Dear NURUL A/P AHMAD (081010101010)\nBachelor of Science\nSession 2026/2027\n")
        self.assertIsNone(parse_govt_offer(uni))

    def test_conservative_on_missing_identity(self):
        # A recognised issuer but no readable NRIC → None (never a partial/mis-paired offer).
        self.assertIsNone(parse_govt_offer(STPM.replace('080514140354', '')))

    def test_empty(self):
        self.assertIsNone(parse_govt_offer(''))
