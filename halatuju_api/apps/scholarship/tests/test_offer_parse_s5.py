"""The Exact offer read 2.0.0 (offer exact-read S5, 2026-11-03): one synthetic twin per failure class the
real corpus showed (A-E), the two wrong values (poly offer date, matric range), the reporting date as a
DATE ONLY (owner ruling 2026-11-03), the output conventions and the offer-title requirement.

Synthetic text only — invented names, ICs and schools (rule: tests never read the gitignored corpus,
`test_no_gitignored_corpus.py`). Each twin copies the SHAPE of a real layout, never its content."""
from django.test import SimpleTestCase

from apps.scholarship.offer_parse import PARSER_VERSION, diagnose, first_date, parse_govt_offer

# ── A. STPM photo: six numbered labels, the numbers split from their words, a school code line, an
# address under the school, the school's name wrapped onto a second line, "Melapor".
STPM_SIX = """SURAT TAWARAN CETAKAN KOMPUTER
SEKTOR OPERASI SEKOLAH
KEMENTERIAN PENDIDIKAN MALAYSIA
TARIKH CETAKAN: 02 MEI 2031
Rujukan Kami : KPM.600-4/1/22 (34) 990101019999
Tarikh: 28 April 2031
Nama: QORIN A/L VESTRAN
No. Kad Pengenalan: 130405100211
TAWARAN KEMASUKAN KE TINGKATAN ENAM SEMESTER 1 TAHUN 2031
2. Sukacita dimaklumkan bahawa saudara/saudari telah ditawarkan ke Tingkatan Enam Semester 1
Tahun 2031 seperti ketetapan berikut:
2.1. Bidang
2.2. Pusat Tingkatan Enam
2.3. Tarikh Melapor Diri
2.4.
2.5.
Masa Melapor Diri
Dokumen diperlukan
(Asal dan salinan)
2.6. Pakaian
SAINS SOSIAL
ABC1234
SEKOLAH MENENGAH KEBANGSAAN TINGGI ZELVORA
UTARA
JALAN QUERIN
12345 ZELVORA
PERAK
No. Telefon: 051234567
E-mel: abc1234@moe.edu.my
14 Jun 2031 (Isnin)
Minggu hala tuju bermula selepas sesi pendaftaran.
7:30 Pagi
i. Surat Tawaran
Kemas dan sopan
"""

# ── B. Matriculation text layer glued onto one line (the K of "K/P" stuck to the name), with the
# engineering letter's "Aliran" label and the issue date glued after the reference.
MATRIC_GLUED = ("ZENTARO A/L MIRVEXK/P : 130212080355NO MATRIK : MA1234567890NO 5, JALAN QORA 2, TAMAN "
                "ZELVA, 31400 IPOH,PERAK Saudara/ Saudari, TAWARAN KEMASUKAN PROGRAM MATRIKULASI KEMENTERIAN "
                "PENDIDIKAN SESI 2031/2032 Dengan hormatnya perkara di atas adalah dirujuk.\n"
                "Jurusan: KEJURUTERAANAliran: KEJURUTERAAN AWAMTempoh Pengajian: DUA SEMESTER (10 BULAN)"
                "Kolej: KOLEJ MATRIKULASI KEJURUTERAAN ZELVAPendaftaran dalam talian: 13 MEI HINGGA 06 JUN "
                "2031Tarikh Kemasukan ke kolej: 8 JUN 2031Yuran Pendaftaran: RM499.00\n"
                "Rujukan Kami :KPM.BM.S.600-4/1/2 JLD3 (123456)Tarikh : 27 APRIL 2031\n"
                "KEMENTERIAN PENDIDIKANBahagian MatrikulasiAras 3-6, Blok E15\n")

# ── C + E. Matriculation photo: a one-word name with no parentage marker above "K/P:", the label block
# split into two runs by the OCR, and a reporting RANGE (its first day is the date).
MATRIC_SPLIT = """KEMENTERIAN PENDIDIKAN
Bahagian Matrikulasi
Rujukan Kami: KPM.BM.S.600-4/1/2 JLD3(123456)
Tarikh:
9 Mei 2031
VELKORAN
K/P: 130923060355
NO. MATRIK: MS1234567890
KAMPUNG QORVA, 89000 ZELVA,
SABAH
KEPUTUSAN PERTUKARAN PROGRAM/ JURUSAN PENEMPATAN PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN SESI
2031/2032
Jurusan:
Tempoh Pengajian:
Kolej:
SAINS
DUA SEMESTER (10 BULAN)
KOLEJ MATRIKULASI LABUAN
Pendaftaran dalam talian:
Tarikh Kemasukan ke kolej:
Yuran Pendaftaran:
13 MEI HINGGA 06 JUN 2031
8 HINGGA 9 JUN 2031
RM499.00
"""

# ── C + D + E. Polytechnic photo: phone status-bar noise pushes the name below line 20, the name has no
# parentage marker, the session numeral is OCR'd "1", the block is interleaved, the label is
# "Tarikh Daftar", the reporting time window has no bracket and a "TENGAHARI" typo.
POLY_NOISY = "\n".join(['10:42 4G'] * 12) + """
JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI
KEMENTERIAN PENDIDIKAN TINGGI
No. Rujukan: JPPKK/10/01/400/130101101234
Tarikh: 22/05/2031
QIAN ZHOU MEI (130101101234)
LOT 5, KAMPUNG ZELVA
SURAT TAWARAN PENGAJIAN SESI 1:2031/2032
Program
DKA - DIPLOMA KEJURUTERAAN AWAM
Mod Pengajian
: SEPENUH MASA
Institusi
Tempoh Pengajian
: POLITEKNIK ZELVORA (POLITEKNIK PREMIER)
: 6 SEMESTER
Tarikh Daftar: 14 JUN 2031 8.00 PAGI - 12.30 TENGAHARI
1. Tawaran ini adalah MUKTAMAD.
"""

# ── E. Polytechnic: "Sesi" and "Tarikh dan Masa" / "Daftar" (split label) in the block, a long
# programme wrapped onto a second line.
POLY_SESI_LABEL = """JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI
Tarikh 01/06/2031
ZARA BINTI QUENTIN (130707121234)
SURAT TAWARAN PENGAJIAN SESI II: 2031/2032
Program
DE123 - DIPLOMA PENGURUSAN LOGISTIK DAN RANTAIAN
BEKALAN
Mod Pengajian
Institusi
Tempoh Pengajian
Sesi
Tarikh dan Masa
Daftar
: SEPENUH MASA
: POLITEKNIK ZELVORA
: 6 SEMESTER
:II: 2031/2032
: 14 JULAI 2031 (2.00 PETANG - 5.00 PETANG)
"""


class TestClassA_StpmSixLabels(SimpleTestCase):
    def test_every_value_lands_by_shape(self):
        r = parse_govt_offer(STPM_SIX)
        self.assertIsNotNone(r)
        self.assertEqual(r['stream'], 'SAINS SOSIAL')
        self.assertEqual(r['institution'], 'SEKOLAH MENENGAH KEBANGSAAN TINGGI ZELVORA UTARA')   # wrapped name
        self.assertEqual(r['reporting_date'], '14 Jun 2031')                                    # no weekday
        self.assertEqual(r['offer_date'], '28 April 2031')                                      # not the print date
        self.assertEqual(r['intake'], 'SEMESTER 1 TAHUN 2031')

    def test_an_address_line_is_never_a_wrapped_name(self):
        text = STPM_SIX.replace('UTARA\n', '')
        self.assertEqual(parse_govt_offer(text)['institution'], 'SEKOLAH MENENGAH KEBANGSAAN TINGGI ZELVORA')


class TestClassB_GluedMatric(SimpleTestCase):
    def test_the_glued_layer_reads_label_by_label(self):
        r = parse_govt_offer(MATRIC_GLUED)
        self.assertIsNotNone(r)
        self.assertEqual(r['candidate_name'], 'ZENTARO A/L MIRVEX')      # the glued K belongs to "K/P"
        self.assertEqual((r['candidate_nric'], r['candidate_nric_source']), ('130212-08-0355', 'label'))
        self.assertEqual(r['stream'], 'KEJURUTERAAN')                    # not the Aliran
        self.assertEqual(r['institution'], 'KOLEJ MATRIKULASI KEJURUTERAAN ZELVA')
        self.assertEqual(r['reporting_date'], '8 Jun 2031')            # the house shape (review M4)
        self.assertEqual(r['intake'], 'SESI 2031/2032')
        self.assertEqual(r['offer_date'], '27 APRIL 2031')


class TestClassC_Names(SimpleTestCase):
    def test_matric_one_word_name_above_the_ic_label(self):
        r = parse_govt_offer(MATRIC_SPLIT)
        self.assertEqual(r['candidate_name'], 'VELKORAN')

    def test_a_long_single_word_is_two_words_glued_and_never_locks(self):
        self.assertIsNone(parse_govt_offer(MATRIC_SPLIT.replace('VELKORAN', 'VELKORANZENTRO')))

    def test_a_template_line_above_the_ic_is_not_a_name(self):
        self.assertIsNone(parse_govt_offer(MATRIC_SPLIT.replace('VELKORAN\n', 'MALAYSIA\n')))

    def test_poly_name_without_a_marker_below_line_twenty(self):
        r = parse_govt_offer(POLY_NOISY)
        self.assertEqual((r['candidate_name'], r['candidate_nric']), ('QIAN ZHOU MEI', '130101-10-1234'))
        self.assertEqual(r['candidate_nric_source'], 'label')


class TestClassD_SessionNumeral(SimpleTestCase):
    def test_an_ocr_digit_reads_as_the_printed_roman_numeral(self):
        self.assertEqual(parse_govt_offer(POLY_NOISY)['intake'], 'SESI I : 2031/2032')
        self.assertEqual(parse_govt_offer(POLY_NOISY.replace('SESI 1:', 'SESIl:'))['intake'],
                         'SESI I : 2031/2032')
        self.assertEqual(parse_govt_offer(POLY_SESI_LABEL)['intake'], 'SESI II : 2031/2032')


class TestClassE_BlockVariants(SimpleTestCase):
    def test_a_label_block_split_in_two_runs(self):
        r = parse_govt_offer(MATRIC_SPLIT)
        self.assertEqual((r['stream'], r['institution']), ('SAINS', 'KOLEJ MATRIKULASI LABUAN'))

    def test_poly_tarikh_daftar_and_an_interleaved_block(self):
        r = parse_govt_offer(POLY_NOISY)
        self.assertEqual(r['institution'], 'POLITEKNIK ZELVORA (POLITEKNIK PREMIER)')
        self.assertEqual(r['reporting_date'], '14 Jun 2031')

    def test_poly_sesi_label_and_a_split_registration_label(self):
        r = parse_govt_offer(POLY_SESI_LABEL)
        self.assertEqual(r['institution'], 'POLITEKNIK ZELVORA')
        self.assertEqual(r['reporting_date'], '14 Jul 2031')
        self.assertEqual(r['programme'], 'DIPLOMA PENGURUSAN LOGISTIK DAN RANTAIAN BEKALAN')   # wrapped
        self.assertEqual(r['programme_code'], 'DE123')


class TestValueBugs(SimpleTestCase):
    def test_poly_offer_date_is_the_issue_date_never_the_registration_date(self):
        self.assertEqual(parse_govt_offer(POLY_NOISY)['offer_date'], '22/05/2031')
        self.assertEqual(parse_govt_offer(POLY_SESI_LABEL)['offer_date'], '01/06/2031')

    def test_a_reporting_range_takes_its_first_day(self):
        self.assertEqual(parse_govt_offer(MATRIC_SPLIT)['reporting_date'], '8 Jun 2031')
        self.assertEqual(first_date('13 MEI HINGGA 06 JUN 2031'), '13 MEI 2031')


class TestReportingDateIsTheDateOnly(SimpleTestCase):
    """Owner ruling 2026-11-03: the reporting date is the DATE; the time window is not part of it."""

    def test_every_time_window_is_dropped(self):
        for raw in ('15 JUN 2031 (8.30 PAGI - 11.30 PAGI)', '15 JUN 2031 (8.00 PAGI - 12.30 TENGAHARI)',
                    '15 JUN 2031 (8.00 PAGI - 12.30 TENGAH HARI)', '15 JUN 2031 2.00 PETANG - 5.00 PETANG',
                    '15 JUN 2031 8.00 PAGI'):
            self.assertEqual(first_date(raw), '15 JUN 2031', raw)
        self.assertEqual(first_date('28/07/2031 (10.00 PAGI - 12.00 TENGAH HARI)'), '28/07/2031')

    def test_no_family_ever_stores_a_time(self):
        for text in (STPM_SIX, MATRIC_GLUED, MATRIC_SPLIT, POLY_NOISY, POLY_SESI_LABEL):
            rd = parse_govt_offer(text)['reporting_date']
            for word in ('PAGI', 'PETANG', 'TENGAH', '(', ':'):
                self.assertNotIn(word, rd.upper())


class TestConventionsAndShape(SimpleTestCase):
    def test_version_and_output_shape(self):
        r = parse_govt_offer(POLY_NOISY)
        self.assertEqual(PARSER_VERSION, '2.0.0')
        self.assertEqual(r['_offer_parser_version'], '2.0.0')
        self.assertEqual(r['campus'], '')
        self.assertEqual((r['programme'], r['programme_code']), ('DIPLOMA KEJURUTERAAN AWAM', 'DKA'))

    def test_a_code_whose_dash_the_ocr_dropped_still_leaves_the_programme(self):
        r = parse_govt_offer(POLY_NOISY.replace('DKA - DIPLOMA', 'DKA DIPLOMA'))
        self.assertEqual((r['programme'], r['programme_code']), ('DIPLOMA KEJURUTERAAN AWAM', 'DKA'))

    def test_matric_bracket_is_kept_for_its_five_call_sites(self):
        self.assertEqual(parse_govt_offer(MATRIC_SPLIT)['programme'], 'Program Matrikulasi (SAINS)')

    def test_an_unlabelled_ic_is_marked_other(self):
        text = (STPM_SIX.replace('(34) 990101019999', '(34)')
                .replace('No. Kad Pengenalan: 130405100211', 'Rujukan 130405100211'))
        r = parse_govt_offer(text)
        self.assertEqual((r['candidate_nric'], r['candidate_nric_source']), ('130405-10-0211', 'other'))

    def test_identity_comes_from_page_one_when_given(self):
        self.assertEqual(parse_govt_offer(STPM_SIX, page1_text=STPM_SIX)['candidate_name'], 'QORIN A/L VESTRAN')

    def test_h1_a_page_one_identity_that_disagrees_with_the_whole_text_never_locks(self):
        page1 = STPM_SIX.replace('QORIN A/L VESTRAN', 'PAGEONE A/L ONLY')
        d = diagnose(STPM_SIX, page1_text=page1)
        self.assertEqual((d['guard'], d['locked']), ('identity_disagree', None))
        d = diagnose(STPM_SIX, page1_text=STPM_SIX.replace('130405100211', '130405100299'))
        self.assertEqual(d['guard'], 'identity_disagree')


class TestNeverLocks(SimpleTestCase):
    def test_a_page_naming_the_family_without_the_offer_title(self):
        portal = MATRIC_SPLIT.replace('KEPUTUSAN PERTUKARAN PROGRAM/', 'Status permohonan')
        d = diagnose(portal)
        self.assertEqual((d['family'], d['titled'], d['locked']), ('matriculation', False, None))

    def test_an_unknown_stream_defers(self):
        self.assertIsNone(parse_govt_offer(STPM_SIX.replace('SAINS SOSIAL\n', 'SASTERA ZEN\n')))

    def test_a_missing_institution_defers(self):
        self.assertIsNone(parse_govt_offer(POLY_NOISY.replace(': POLITEKNIK ZELVORA (POLITEKNIK PREMIER)\n', '')))


class TestReviewFixes(SimpleTestCase):
    """The adversarial review of 9298e2c9 (2026-11-03): M1-M4, L1."""

    def test_m1_a_long_space_run_never_hangs_any_family(self):
        import time
        run = ' ' * 3000
        for text in (STPM_SIX, MATRIC_GLUED, MATRIC_SPLIT, POLY_NOISY, POLY_SESI_LABEL):
            for bait in ('SESI', 'Tarikh', 'K/P', 'No. Kad Pengenalan', '2.1. Bidang', '8 HINGGA', '12'):
                start = time.perf_counter()
                diagnose(text + '\n' + bait + run + 'x\n' + bait + run)
                self.assertLess(time.perf_counter() - start, 1.0, bait)

    def test_m2_a_portal_page_quoting_the_title_never_locks(self):
        portal = MATRIC_SPLIT.replace(
            'KEPUTUSAN PERTUKARAN PROGRAM/ JURUSAN PENEMPATAN PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN SESI',
            'Tahniah! Anda layak menerima Tawaran Kemasukan Program Matrikulasi Kementerian Pendidikan SESI')
        self.assertIsNone(parse_govt_offer(portal))
        # the title in capitals at a line start, but on a page with a portal's own words
        self.assertIsNone(parse_govt_offer('SEMAKAN KEPUTUSAN\n' + MATRIC_SPLIT))
        self.assertIsNone(parse_govt_offer(MATRIC_SPLIT + 'Surat Tawaran (Sila Cetak)\n'))
        # mid-line, lower case: not the title
        self.assertIsNone(parse_govt_offer(MATRIC_SPLIT.replace('KEPUTUSAN PERTUKARAN PROGRAM/',
                                                                'Status: keputusan pertukaran program/')))
        # a real polytechnic letter says "Tahniah dan sukacita" — that is no portal tell
        self.assertIsNotNone(parse_govt_offer(POLY_NOISY + 'Tahniah dan sukacita dimaklumkan bahawa anda\n'))

    def test_m3_a_state_or_stamp_above_the_ic_is_no_name(self):
        for word in ('PERAK', 'SEGERA', 'SULIT', 'KPM'):
            self.assertIsNone(parse_govt_offer(MATRIC_SPLIT.replace('VELKORAN\n', word + '\n')), word)

    def test_m3_a_name_wrapped_after_its_marker_is_joined_and_a_cut_one_is_refused(self):
        wrapped = MATRIC_SPLIT.replace('VELKORAN\n', 'AHMAD HAKIM BIN\nZENTARO\n')
        self.assertEqual(parse_govt_offer(wrapped)['candidate_name'], 'AHMAD HAKIM BIN ZENTARO')
        self.assertIsNone(parse_govt_offer(MATRIC_SPLIT.replace('VELKORAN\n', 'AHMAD HAKIM BIN\n')))

    def test_m4_a_numeric_reporting_date_is_stored_in_the_house_shape(self):
        from apps.scholarship.pathway_engine import parse_reporting_date
        r = parse_govt_offer(POLY_NOISY.replace('14 JUN 2031 8.00 PAGI', '14/06/2031 8.00 PAGI'))
        self.assertEqual(r['reporting_date'], '14 Jun 2031')
        self.assertIsNotNone(parse_reporting_date(r['reporting_date']))
        self.assertEqual(r['offer_date'], '22/05/2031')                  # not core, kept as printed

    def test_l1_a_thirteen_digit_labelled_number_is_no_ic(self):
        d = diagnose(MATRIC_SPLIT.replace('K/P: 130923060355', 'K/P: 1309230603551'))
        self.assertEqual(d['fields']['candidate_nric'], '')               # never cut to 12 digits
        stpm = diagnose(STPM_SIX.replace('130405100211', '1304051002111'))
        self.assertNotEqual(stpm['fields']['candidate_nric'], '130405-10-0211')

