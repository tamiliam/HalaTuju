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
        self.assertEqual(r['reporting_date'], '15 Jun 2026')        # S5: the house shape, no time

    def test_stpm(self):
        r = parse_govt_offer(STPM)
        self.assertEqual(r['_family'], 'stpm')
        self.assertEqual(r['candidate_name'], 'AISYAH BINTI RAHMAN')
        self.assertEqual(r['candidate_nric'], '080514-14-0354')
        self.assertEqual(r['programme'], 'Tingkatan Enam Semester 1')
        self.assertEqual(r['intake'], 'SEMESTER 1 TAHUN 2026')       # S5: with its semester words
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
        self.assertEqual(r['reporting_date'], '8 Jun 2026')                  # Tarikh Lapor Diri, not skipped
        self.assertNotIn('Bidang', r['institution'])                        # not swallowed by the institution

    def test_matriculation(self):
        r = parse_govt_offer(MATRIC)
        self.assertEqual(r['_family'], 'matriculation')
        self.assertEqual(r['candidate_name'], 'KUMAR A/L RAJAN')
        self.assertEqual(r['candidate_nric'], '080923-06-0355')
        self.assertIn('Matrikulasi', r['programme'])
        self.assertEqual(r['intake'], 'SESI 2026/2027')              # S5: with its label
        self.assertEqual(r['institution'], 'KOLEJ MATRIKULASI PAHANG')
        self.assertEqual(r['reporting_date'], '8 Jun 2026')
        # ⚠ THE JURUSAN IS THE STREAM. Its absence here is what starved the pathway check's track
        # axis for every matriculation letter this parser read (0/4 on production 2026-09-10,
        # against 26/26 for the same letters read by Gemini, whose schema says so explicitly).
        self.assertEqual(r['stream'], 'SAINS')
        # ⚠ AND IT IS STILL INSIDE `programme` TOO — not a leftover. Five call sites derive the
        # matric track from this string (offer_pathway.parse_matric_track via services.py:1549 and
        # :1846, offer_pathway.py:562, backfill_pre_u_track). Retiring the bracket is a separate,
        # measurable change; dropping it here would silently blank those tracks.
        self.assertEqual(r['programme'], 'Program Matrikulasi (SAINS)')

    def test_polytechnic(self):
        r = parse_govt_offer(POLY)
        self.assertEqual(r['_family'], 'polytechnic')
        self.assertEqual(r['candidate_name'], 'JANANI A/P SURESH')
        self.assertEqual(r['candidate_nric'], '081014-08-0994')
        self.assertEqual(r['programme'], 'DIPLOMA PENGAJIAN PERNIAGAAN')   # S5: the code leaves it
        self.assertEqual(r['programme_code'], 'DPM')
        self.assertEqual(r['intake'], 'SESI 2026/2027')              # no session numeral printed
        self.assertIn('POLITEKNIK', r['institution'])
        self.assertEqual(r['reporting_date'], '20 Jun 2026')          # the date only, the house shape
        self.assertEqual(r['offer_date'], '25/05/2026')

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


# ⚠ THE SAME KPM LETTER, WITH ITS VALUE LINES INTERLEAVED AMONG THE LABELS instead of forming one
# block beneath them — which is how application #142's PDF text layer emitted it (the value "SAINS"
# renders on its own line beside "Jurusan:", not below "Yuran Pendaftaran:"). `_info_block_pairs`
# collects values only from AFTER THE LAST label, so here it sees ['8 JUN 2026', 'RM499.00'] and
# zips them onto ('stream', 'duration') BY INDEX. Nothing checks that a date could never be a
# jurusan.
MATRIC_INTERLEAVED = """KEMENTERIAN PENDIDIKAN
Bahagian Matrikulasi
Tarikh: 27 APRIL 2026
AHBINAAYAH A/P CHANDRA
K/P: 080602141410
TAWARAN KEMASUKAN PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN SESI 2026/2027
SAINS
Jurusan:
Tempoh Pengajian:
DUA SEMESTER (10 BULAN)
Kolej:
KOLEJ MATRIKULASI SELANGOR
Pendaftaran dalam talian:
13 MEI HINGGA 06 JUN 2026
Tarikh Kemasukan ke kolej:
Yuran Pendaftaran:
8 JUN 2026
RM499.00
"""

# The fee value alone in the stream slot — the same shift one step further along.
MATRIC_FEE_IN_STREAM = MATRIC_INTERLEAVED.replace('8 JUN 2026\nRM499.00', 'RM499.00')


class TestMatricBlockShift(SimpleTestCase):
    """⚠ A POSITIONAL PAIRING CAN SHIP BY ONE AND NOTHING OBJECTS — application #142, 2026-09-10.

    The offer read its programme as "Program Matrikulasi (8 JUN 2026)" and its reporting date as
    EMPTY: one shift, two wrong fields, no error raised. On screen the officer saw a RED Pathway
    chip on a perfectly good offer, no Institution tick behind it, and no reporting-date tick.
    The letter was fine. The pairing was not.
    """

    def test_the_142_shape_no_longer_puts_a_date_in_the_jurusan(self):
        # 1.3.0 stored #142's document as programme "Program Matrikulasi (8 JUN 2026)", stream
        # "8 JUN 2026", reporting date '' — a positional zip. Since S5 (2.0.0) each value is taken by
        # its SHAPE (`_read_block`): no line after "Jurusan:" has a jurusan's shape, so the stream
        # stays EMPTY (and a required field missing defers), never a date.
        from apps.scholarship.offer_parse import diagnose
        d = diagnose(MATRIC_INTERLEAVED)
        self.assertEqual(d['fields']['stream'], '')
        self.assertIn('stream', d['empty_required'])
        self.assertEqual(d['fields']['institution'], 'KOLEJ MATRIKULASI SELANGOR')

    def test_a_date_in_the_jurusan_slot_defers_to_gemini(self):
        # ⚠ THE ABSENCE IS THE POINT. A partly-wrong deterministic read is worth LESS than no
        # deterministic read: returning None hands the letter to Gemini, which reads this template
        # correctly (26/26 on production 2026-09-10, against 0/4 for the parser).
        self.assertIsNone(parse_govt_offer(MATRIC_INTERLEAVED))

    def test_a_ringgit_amount_in_the_jurusan_slot_defers_too(self):
        self.assertIsNone(parse_govt_offer(MATRIC_FEE_IN_STREAM))

    def test_a_healthy_block_still_parses(self):
        # The guard must not make the parser useless: the well-formed letter is unaffected.
        r = parse_govt_offer(MATRIC)
        self.assertIsNotNone(r)
        self.assertEqual(r['stream'], 'SAINS')
        self.assertEqual(r['_offer_parser_version'], '2.0.1')

    def test_no_text_slot_may_ever_hold_a_date(self):
        # The general rule, stated once: whatever the layout, a date never belongs in any of these.
        from apps.scholarship.card_display import looks_like_date
        r = parse_govt_offer(MATRIC)
        for key in ('stream', 'institution', 'programme'):
            self.assertFalse(looks_like_date(r.get(key, '')),
                             f'{key} holds a date: {r.get(key)!r}')
