"""The gift's start-year reader (`session_year`), owner ruling 16 Nov 2026.

The owner: "Most offer letters have a reporting date. Otherwise the title says the year like 2026, or
it may say 2024/25 (which means 2024)." In order: the stored reporting date's year; else one year on
the intake line; else a session's first year (its second with Sesi 2 / Semester 2); else unknown.
Later terms, readmission words and session-only confirmation letters are unknown whatever the date.
The shapes below are the ones the 286-letter corpus holds (docs/decisions.md). The review probes are
in `test_start_year_gift_probes.py`; the money never reads this module (`test_start_year_money.py`).
"""
from django.test import SimpleTestCase

from apps.scholarship.session_year import gift_reading, gift_start_year
from apps.scholarship.start_year import decide

GIFT = [2025, 2026]


def _state(intake, rd='', **kw):
    return decide(gift_start_year(intake, rd, **kw), GIFT)


class TheCorpusShapes(SimpleTestCase):
    """One test per shape the real letters hold."""

    def test_a_reporting_date_gives_its_year(self):
        # 82% of the letters: the stored date decides, whatever the session says.
        for intake, rd, year in (('SESI 1-2024/2025', '28 Sep 2024', 2024), ('Sesi 2022/2023', '25 Jul 2022', 2022),
                                 ('TAHUN 2026', '13 May 2026', 2026), ('2025/2026', '6 Oct 2025', 2025),
                                 ('SESI 2 2023/2024', '13 Apr 2024', 2024), ('October 2024', '26 Sep 2024', 2024),
                                 ('', '8 Sep 2025', 2025), ('Sesi 2024/2025', '3 Mar 2025', 2025)):
            with self.subTest(intake=intake, rd=rd):
                self.assertEqual(gift_reading(intake, rd), (year, 'reporting_date'))
        self.assertEqual(_state('SESI 1-2024/2025', '28 Sep 2024'), 'outside')
        self.assertEqual(_state('Sesi 2024/2025', '3 Mar 2025'), 'inside')

    def test_a_date_that_is_not_one_dated_year_is_passed_over(self):
        # The normaliser keeps a line it cannot parse; two years in it, or no date shape, is no date.
        self.assertEqual(gift_reading('Sesi 2025/2026', 'Oktober 2024 / Mac 2025'), (2025, 'session_first'))
        self.assertEqual(gift_reading('Ambilan 2026', '2024'), (2026, 'intake_year'))
        self.assertEqual(gift_reading('Ambilan 2026', 'Sesi 2024/2025'), (2026, 'intake_year'))

    def test_a_single_year_on_the_intake_line(self):
        for intake, year in (('2026', 2026), ('TAHUN 2024', 2024), ('Ambilan Julai 2025', 2025),
                             ('Intake 01/2025', 2025), ('SEMESTER 1 TAHUN 2025', 2025), ('Ambilan 2027', 2027)):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (year, 'intake_year'))

    def test_a_session_gives_its_first_year(self):
        for intake, year in (('2024/2025', 2024), ('Sesi 2025/2026', 2025), ('SESI AKADEMIK 2024/2025', 2024),
                             ('Semester 1 Sesi 2023/2024', 2023), ('Sesi 2024/25', 2024), ('Sesi 2024-2025', 2024),
                             ('Sesi 2024-25', 2024), ('SESI 2024 / 2025', 2024), ('20262027', 2026),
                             ('SESI 1-2025/2026', 2025), ('Intake 2025/26 September', 2025)):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (year, 'session_first'))
        self.assertEqual(_state('Sesi 2024/2025'), 'outside')
        self.assertEqual(_state('Sesi 2025/2026'), 'inside')

    def test_sesi_2_gives_the_second_year(self):
        # 9 of 182 dated letters report in the session's second year; all 9 say Sesi 2 / Semester 2.
        for intake in ('SESI 2 2024/2025', 'Sesi II 2024/2025', 'Semester 2 Sesi 2024/2025', 'Semester II 2024/2025',
                       'SESI 2-2024/2025', 'Sesi 2/2024/2025', 'Sem 2 2024/25', 'Semester Kedua Sesi 2024/2025',
                       'Ambilan Kedua 2024/2025', 'Sesi 2024/2025 (Ambilan II)', '2nd Semester 2024/2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (2025, 'session_second'))
        self.assertEqual(_state('Sesi II 2024/2025'), 'inside')

    def test_an_early_intake_month_gives_the_second_year(self):
        # A January-to-April intake month written without its year is the session's second half.
        for intake in ('Sesi 2024/2025 Ambilan Februari', 'Ambilan Mac Sesi 2024/2025', 'Session 2024-25 Feb intake',
                       'Intake: January, Sesi 2024/2025', 'Sesi 2024/2025 Semester Februari'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (2025, 'session_second'))
        self.assertEqual(gift_reading('Sesi Ogos 2024/2025'), (2024, 'session_first'))

    def test_a_month_away_from_an_intake_word_is_no_intake_month(self):
        # Review fix: only a month next to an intake / semester word is the intake month.
        for intake, year in (('Sesi 2026/2027, tutup 30 April', 2026), ('Ambilan Sesi 2024/25Feb', 2024),
                             ('Sesi 2024/2025 (mendaftar sebelum Mac)', 2024)):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (year, 'session_first'))

    def test_a_sesi_ii_beside_a_first_semester_or_year_is_the_second_year(self):
        # Review fix: Sesi II names the intake; Semester 1 / Year 1 is that intake's first term.
        for intake, year in (('Semester 1 Sesi II 2025/2026', 2026), ('Tahun 1 Sesi 2 2025/2026', 2026),
                             ('Sesi II 2026/2027 Semester I', 2027), ('Ambilan 2 Sesi 2024/2025 Semester 1', 2025)):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (year, 'session_second'))

    def test_a_year_inside_a_code_is_not_a_year(self):
        self.assertEqual(gift_reading('Ambilan 2025 kod UH2024'), (2025, 'intake_year'))
        self.assertEqual(gift_reading('Sesi 2025/2026 kod UH2024'), (2025, 'session_first'))
        self.assertEqual(gift_reading('Kod Program UH2024'), (None, 'no_year'))

    def test_penggal_2_is_not_a_second_intake(self):
        # Form Six's second term follows a mid-year start: it reads as the session's first year.
        self.assertEqual(gift_reading('Penggal 2 Sesi 2024/2025'), (2024, 'session_first'))
        self.assertEqual(gift_reading('Penggal 1 2025'), (2025, 'intake_year'))

    def test_a_confirmation_naming_only_its_session_is_unknown(self):
        # All 5 confirmation letters in the corpus show only the current session.
        for intake, rd in (('2024/2025', ''), ('2026/2027', ''), ('1-2024/2025', ''), ('Sesi 2025/2026', '8 Sep 2025'),
                           ('', '8 Sep 2025'), ('2025', ''), ('Kemasukan 2025', ''), ('6 / 2025 - 12 / 2026', ''),
                           # Review fix: Semester 1 is the CURRENT semester, and a bare month-year the
                           # current term's: neither writes the intake.
                           ('Semester 1 Sesi 2025/2026', ''), ('Sem 1 2025/2026', '8 Sep 2025'),
                           ('September 2025', ''), ('Semester 1, September 2025', '')):
            with self.subTest(intake=intake, rd=rd):
                self.assertEqual(gift_reading(intake, rd, confirmation=True), (None, 'confirmation'))

    def test_a_confirmation_that_writes_the_intake_reads_it(self):
        # Year 1 / Tahun 1 / Lower Six, or an intake / admission word with a month and its year.
        for intake, year in (('Ambilan September 2025', 2025), ('Tahun 1 Semester 1 Sesi 2025/2026', 2025),
                             ('Year 1, Session 2025/2026', 2025), ('Tingkatan 6 Bawah 2025/2026', 2025),
                             ('Lower Six 2025/2026', 2025), ('Intake: January 2026', 2026),
                             ('Tarikh Mendaftar: 3 Mac 2025', 2025), ('Kemasukan Julai 2025', 2025),
                             ('Ambilan September 2022, Sesi 2022/2023', 2022)):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_year(intake, confirmation=True), year)
        # Its date is never read: it is the current session's date, not the intake's.
        self.assertEqual(gift_start_year('Tahun 1 Sesi 2023/2024', '8 Sep 2025', confirmation=True), 2023)


class LaterTermsAreUnknown(SimpleTestCase):
    """Year 2+, Semester 3+, final year, Upper Six, Part 3+: her place in the course, with ANY date."""

    LATER = ('Semester 3 Sesi 2024/2025', 'Semester III 2024/2025', 'Sem3 2024/2025', 'Semester 10 Sesi 2024/2025',
             'Semester XII Sesi 2025/2026', 'Semester Lima Sesi 2025/2026', 'Semester Dua Belas 2025/2026',
             'Semester Kelima 2025/2026', 'Sesi 2024/2025 Semester IV', 'Sesi : 2026/2027 Semester : 3',
             'Third Semester, Session 2024/2025', 'Semester 2/3 2024/2025', 'Tahun 2 Sesi 2025/2026',
             'Year 2, Session 2025/2026', 'Tahun II Sesi 2025/2026', 'Tahun Kedua Sesi 2025/2026',
             'Tahun Akhir Sesi 2025/2026', 'Year 3 Semester 1 Session 2025/2026', 'Second year, 2025/2026',
             '2nd Year Sem 1 2025/2026', 'Final Year, Session 2025/2026', 'Penggal 3 Sesi 2024/2025',
             'Tingkatan 6 Atas 2024/2025', 'Upper Six 2025', 'U6 2025', 'Semester 3, Julai 2025', 'Tahun 2',
             'Tahun ke-2 Sesi 2025/2026', 'Semester ke-3 Sesi 2025/2026', 'Tahun Pengajian 2, Sesi 2025/2026',
             'Year of Study 2, Session 2025/2026', 'Y2S1 2025/2026', 'Y3 S1 Session 2025/2026',
             'Part 4, Sesi 2025/2026', 'Bahagian 3 Sesi 2025/2026', 'Sem: V 2025/2026', 'Sixth Semester, 2025/2026',
             'Yr 2 Sem 1 Sesi 2025/2026', 'Thn 3 2025/2026', 'Semester 1 Level 200 Session 2025/2026',
             'Lanjutan pengajian Sesi 2025/2026', 'Pelajar Lama Sesi 2025/2026', 'Continuing Sesi 2025/2026')

    def test_later_terms_with_a_session_a_date_or_neither(self):
        for intake in self.LATER:
            for rd in ('', '8 Sep 2025', '3 Mar 2026'):
                for conf in (False, True):
                    with self.subTest(intake=intake, rd=rd, confirmation=conf):
                        self.assertEqual(gift_reading(intake, rd, confirmation=conf), (None, 'later_term'))

    def test_the_programme_and_stream_words_are_scanned_too(self):
        for context in ('Ijazah Sarjana Muda Kejuruteraan (Tahun 2)', 'Diploma Perakaunan Semester 5',
                        'Bachelor of Science, Year of Study 3', 'Tingkatan Enam Atas'):
            with self.subTest(context=context):
                self.assertEqual(gift_start_year('Semester 1 Sesi 2025/2026', '8 Sep 2025', context=context), None)

    def test_a_qualification_level_or_a_course_length_is_not_a_later_term(self):
        self.assertEqual(gift_start_year('Ambilan Julai 2025', context='Sijil Kemahiran Malaysia Tahap 3'), 2025)
        self.assertEqual(gift_start_year('2026', '13 May 2026', context='PROGRAM SATU TAHUN ; 13-KOLEJ MATRIKULASI'),
                         2026)
        self.assertEqual(gift_start_year('Ambilan 2024', context='Matrikulasi Program Dua Tahun'), 2024)

    def test_a_first_year_is_not_a_later_term(self):
        self.assertEqual(_state('Tahun 1 Semester 1 Sesi 2025/2026'), 'inside')
        self.assertEqual(_state('SEMESTER 1 TAHUN 2026'), 'inside')


class ReadmissionIsUnknown(SimpleTestCase):
    def test_readmission_and_credit_transfer_words(self):
        for intake in ('Kemasukan Semula 2025', 'Re-admission Intake 2025', 'Readmission 2025', 'Re-enrolment 2025',
                       'Pendaftaran Semula Sesi 2025/2026', 'Ambilan 2025 (Pindah Kredit)', 'Advanced Standing Intake 2025',
                       'Credit Transfer 2025', 'Sambung pengajian 2025', 'Lateral Entry 2025', 'Direct entry 2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake, '7 Oct 2025'), (None, 'readmission'))
        self.assertEqual(gift_reading('Ambilan 2025', context='Pindahan Kredit'), (None, 'readmission'))


class OtherUnknowns(SimpleTestCase):
    def test_no_letter_line_and_no_date(self):
        self.assertEqual(gift_reading('', ''), (None, 'no_year'))
        self.assertEqual(gift_reading('Ambilan Mac', ''), (None, 'no_year'))

    def test_several_years_with_no_date(self):
        for intake in ('JAN 2025 - DISEMBER 2027', 'Sesi Julai 2025 hingga Jun 2029', 'Ambilan 2024 (tangguh ke 2025)',
                       'Intake: September 2024 / Start: January 2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'several_years'))
        # The date settles it.
        self.assertEqual(gift_reading('JAN 2025 - DISEMBER 2027', '6 Jan 2025'), (2025, 'reporting_date'))

    def test_a_year_beside_a_session_is_the_single_year(self):
        self.assertEqual(gift_reading('Ambilan 2023 Sesi 2025/2026'), (2023, 'intake_year'))
        self.assertEqual(gift_reading('Ambilan Februari 2025 Sesi 2024/2025'), (2025, 'intake_year'))

    def test_two_sessions_or_both_intakes(self):
        self.assertEqual(gift_reading('Sesi 2024/2025, Sesi 2025/2026'), (None, 'several_sessions'))
        for intake in ('Semester 1 / 2 Sesi 2025/2026', 'Sesi 2024/2025 Semester 1 dan Semester 2',
                       'Sesi 2024/2025 Ambilan September / Februari', 'Sesi I 2024/2025 Ambilan Februari',
                       'Sesi 1 Semester 2 2024/2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'both_intakes'))

    def test_a_course_span_is_no_session(self):
        self.assertEqual(gift_reading('2026/2031'), (None, 'several_years'))
        self.assertEqual(gift_reading('6 / 2025 - 12 / 2026'), (None, 'several_years'))

    def test_a_damaged_year_is_unknown(self):
        for intake in ('Ambilan Sesi 2024/2O25', 'Ambilan Sesi 2O24/2025', 'Ambilan Sesi 2024/202S'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'damaged_year'))


class ExamYearsAreNotStartYears(SimpleTestCase):
    """Owner 16 Nov 2026 ("why complicate?"): exam years are NEVER a start year. A line with an exam
    word in any form gives no single year; only the reporting date or the session reads it."""

    EXAM_LINES = ('SPM 2024, Ambilan 2025', 'Ambilan Julai 2025 (SPM 2024)', 'Keputusan SPM 2024; Ambilan 2025',
                  'Kemasukan 2025 (2024 lulus SPM)', 'Kemasukan 2024 lulus SPM 2023', 'Intake 2026 SPM 2022',
                  'Ambilan SPM 2024', 'SPM2024', 'Ambilan 2025 SPM (2024)', 'STPM/2024 Ambilan 2025',
                  'Sijil Pelajaran Malaysia 2024, Ambilan 2025', 'Sijil Tinggi Persekolahan Malaysia 2024',
                  'MUET 2024 Intake 2025', 'UEC 2024 Intake 2025', 'O-Level 2023 Intake 2025', 'A Level 2024')

    def test_an_exam_line_with_no_session_and_no_date_is_unknown(self):
        for intake in self.EXAM_LINES:
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'exam_line'))

    def test_an_exam_line_reads_its_session(self):
        for intake in ('Sesi 2025/2026 (SPM2024)', 'SPM (2024) Sesi 2025/2026', 'STPM/2024 Sesi 2025/2026',
                       'Ambilan September 2025 Sesi 2025/2026 (STPM 2024)'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (2025, 'session_first'))
        self.assertEqual(_state('Sesi 2025/2026 (SPM2024)'), 'inside')
        self.assertEqual(_state('Ambilan SPM 2024'), 'unknown')

    def test_the_date_still_wins(self):
        self.assertEqual(gift_reading('Intake 2024 SPM 2022', '3 Mar 2025'), (2025, 'reporting_date'))
        self.assertEqual(gift_reading('SPM 2024, Ambilan 2025', '14 Jul 2025'), (2025, 'reporting_date'))
