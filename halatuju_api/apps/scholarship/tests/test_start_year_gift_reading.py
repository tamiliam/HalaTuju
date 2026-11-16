"""The gift's start-year reader (`session_year`), owner ruling 16 Nov 2026.

The owner: "Most offer letters have a reporting date. Otherwise the title says the year like 2026, or
it may say 2024/25 (which means 2024)." In order: the stored reporting date's year; else one year on
the intake line; else a session's first year (its second with Sesi 2 / Semester 2); else unknown.
Later terms, readmission words and session-only confirmation letters are unknown whatever the date.
The shapes below are the ones the 286-letter corpus holds (docs/decisions.md). The review probes are
in `test_start_year_gift_probes.py`; the money never reads this module (`test_start_year_money.py`).
"""
from django.test import SimpleTestCase

from apps.scholarship.session_year import gift_reading
from apps.scholarship.start_year import decide

GIFT = [2025, 2026]


def _year(intake, rd='', **kw):
    return gift_reading(intake, rd, **kw).year


def _state(intake, rd='', **kw):
    return decide(_year(intake, rd, **kw), GIFT)


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
        # Eleventh review: only on a line holding an admission word (Ambilan, Kemasukan, Intake...).
        for intake in ('Sesi 2024/2025 Ambilan Februari', 'Ambilan Mac Sesi 2024/2025', 'Session 2024-25 Feb intake',
                       'Intake: January, Sesi 2024/2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (2025, 'session_second'))
        self.assertEqual(gift_reading('Ambilan Ogos 2024/2025'), (2024, 'session_first'))

    def test_a_month_on_a_line_with_no_admission_word_is_unknown(self):
        # Eleventh review (lead's rules A / C): a month is never ignored. With no admission word on its
        # line (Sesi, Session, Semester and Sem are none) it is unknown, not the session's first year.
        for intake in ('Sesi 2026/2027 (mendaftar sebelum Mac)', 'Session 2026-27 February', 'Sesi 2026/27 Februari',
                       'Sesi Ogos 2024/2025', 'Sesi 2024/2025 Semester Februari', 'SEPTEMBER SESI AKADEMIK 2026/2027'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'unclear_month'))

    def test_a_month_on_a_line_with_an_intake_word_is_the_intake_month(self):
        # Review 8: the month need not sit next to the word, only on its line.
        for intake in ('Ambilan Sesi 2024/25Feb', 'Ambilan Sesi 2024-25 Mac', 'Ambilan Sesi 2024-25 (Mac)',
                       'Ambilan 2024-25 Jan', 'Ambilan Sesi 2024/2025: Februari',
                       'Ambilan Sesi 2024/2025_Feb', 'Ambilan Sesi 2024/2025 Sem I (Feb)'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (2025, 'session_second'))
        self.assertEqual(_state('Ambilan Sesi 2024/2025: Februari'), 'inside')
        self.assertEqual(gift_reading('Kemasukan Sesi 2024/2025 Ogos'), (2024, 'session_first'))
        # Only the admission word's own line: a month on another line is unknown, never passed over.
        self.assertEqual(_year('Sesi 2024/2025\nAmbilan\nTarikh tutup: 30 April'), None)
        self.assertEqual(gift_reading('Sesi 2024/2025\nAmbilan Februari'), (2025, 'session_second'))

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
                self.assertEqual(_year(intake, confirmation=True), year)
        # Its date is never read: it is the current session's date, not the intake's.
        self.assertEqual(_year('Tahun 1 Sesi 2023/2024', '8 Sep 2025', confirmation=True), 2023)


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
                self.assertEqual(_year('Semester 1 Sesi 2025/2026', '8 Sep 2025', context=context), None)

    def test_a_qualification_level_or_a_course_length_is_not_a_later_term(self):
        self.assertEqual(_year('Ambilan Julai 2025', context='Sijil Kemahiran Malaysia Tahap 3'), 2025)
        self.assertEqual(_year('2026', '13 May 2026', context='PROGRAM SATU TAHUN ; 13-KOLEJ MATRIKULASI'),
                         2026)
        self.assertEqual(_year('Ambilan 2024', context='Matrikulasi Program Dua Tahun'), 2024)

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


class ASessionLineWithAnotherDate(SimpleTestCase):
    """Lead's rule, 16 Nov 2026 (owner: "why complicate?"): WHEN IN DOUBT, UNKNOWN. A session line
    with no reporting date reads (1) the session alone; (2) ONE date or month-year straight after an
    admission phrase, in the session's two years; (3) anything else beside the session is unknown."""

    def test_a_date_after_an_admission_phrase_reads_its_year(self):
        # Ninth review (Opus): numeric and month-name dates behave the same.
        for intake in ('Sesi 2024/2025, Tarikh Kemasukan: 10/03/2025', 'Sesi 2024/2025 Tarikh Mendaftar 3/3/2025',
                       'Sesi 2024/2025 Tarikh Lapor Diri: 3 Mac 2025', 'Sesi 2024/2025 Lapor Diri 2025-03-03',
                       'Ambilan Februari 2025 Sesi 2024/2025', 'Sesi 2024/2025 Tarikh Pendaftaran 17.02.2025',
                       'Sesi Akademik 2024/2025 Kemasukan Februari 2025', 'Intake: March 2025 (Session 2024/2025)',
                       'Session 2024/2025, Date of Registration: 3 March 2025',
                       'Session 2024/2025 Date of Admission 3 March 2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (2025, 'intake_date'))
        # The session may stand between the intake word and its month-year.
        self.assertEqual(gift_reading('Ambilan Sesi 2023/2024 Feb 2024'), (2024, 'intake_date'))
        self.assertEqual(_state('Ambilan Sesi 2023/2024 Feb 2024'), 'outside')
        self.assertEqual(gift_reading('Sesi 2024/2025 Ambilan Sept 2024'), (2024, 'intake_date'))

    def test_any_other_date_beside_a_session_is_unknown(self):
        # Ninth review (Opus): a closing, update or letter date, a reference, two dates, no start word.
        for intake in ('Sesi 2024/2025, tutup 30 April 2025', 'Sesi 2024/2025 (dikemaskini Jan 2025)',
                       'Ambilan September Sesi 2024/2025 (Surat bertarikh 5 Feb 2025)',
                       'Sesi 2025/2026 Rujukan UPU/2024/77', 'Sesi 2025/2026 (dikemaskini 1/12/2024)',
                       'Sesi 2025/2026 No. Rujukan 2024', 'Sesi 2024/2025 Semester 1, kemaskini 1 Feb 2025',
                       'Sesi 2024/2025 bermula 2 September 2024 hingga 30 Mac 2025',
                       'Intake: Sept 2024 (Session 2024/2025), updated Feb 2025',
                       # No start word straight before the date. "Session 2024/25 Feb 2025" is the
                       # lead's case, decided by the rule.
                       'Session 2024/25 Feb 2025', 'Sesi 2024/25 Februari 2025', 'Sesi 2024/2025 - Jan 2025',
                       'Sesi 2025/2026 (Tarikh: 26/02/2025)', 'Sesi 2024/2025 Pendaftaran 03-03-2025',
                       # Eleventh review: mulai, bermula, commencing, starting, Semester / Sem start nothing.
                       'Sesi 2024/2025 mulai 17.02.2025', 'Sesi 2024/2025 bermula 2025-03-03',
                       'Sesi 2024/2025, Semester 1 (Jan 2025)', 'Session 2024/2025 starting 3 March 2025',
                       # A year outside the session's two years.
                       'Intake Sept 2023 - Session 2025/2026', 'Sesi 2025/2026 bermula 1 Ogos 2024',
                       # A clash with an intake month or an intake already on the line.
                       'Ambilan Februari Sesi 2024/2025 bermula 2 September 2024',
                       'Sesi II 2024/2025 bermula 2 September 2024', 'Sesi 1 2024/2025 mulai 3 Mac 2025'):
            with self.subTest(intake=intake):
                # The reason may be the date or a loose month beside it (unclear_date / _month).
                self.assertIsNone(_year(intake))
        self.assertEqual(_state('Sesi 2025/2026 Rujukan UPU/2024/77'), 'unknown')

    def test_a_plain_intake_year_beside_a_session_reads(self):
        # A plain year straight after an intake word, when it is one of the session's two years.
        for intake, year in (('Ambilan 2025 (Sesi 2025/2026)', 2025), ('Sesi 2024/2025 Intake 2025', 2025),
                             ('Kemasukan: 2024 Sesi 2024/2025', 2024)):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (year, 'intake_year'))
        # Thirteenth review: outside the session it is unknown (it may name a cohort).
        for intake in ('Ambilan 2023 Sesi 2025/2026', 'Ambilan 2023, Semester 1 Sesi 2025/2026'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'unclear_date'))
        # Not straight after, or after another start word: unknown.
        self.assertEqual(gift_reading('Ambilan Sesi 2025/2026 2024'), (None, 'unclear_date'))
        self.assertEqual(gift_reading('Sesi 2024/2025 mulai 2025'), (None, 'unclear_date'))

    def test_a_session_line_with_no_other_date_is_unchanged(self):
        self.assertEqual(gift_reading('Ambilan Sesi 2024-25 Mac'), (2025, 'session_second'))
        self.assertEqual(gift_reading('Sesi 2025/2026 (S.P.M. 2024)'), (2025, 'session_first'))
        self.assertEqual(gift_reading('Sesi 2025/2026 kod UH2024'), (2025, 'session_first'))
        # A reference year with no session is still the line's one year (several stay unknown).
        self.assertEqual(gift_reading('Rujukan UPU/2024/77'), (2024, 'intake_year'))


class TenthReviewWhenInDoubtUnknown(SimpleTestCase):
    """Tenth review (Opus), WHEN IN DOUBT, UNKNOWN: only 20xx years are read, so a date the reader
    cannot date stops the reading; an exam's session is no session."""

    def test_a_reporting_date_with_no_20xx_year_makes_the_reading_unknown(self):
        # Present but undatable: the session (or intake line) is NOT read in its place.
        for rd in ('16 Februari', '16/02/25', '16 Feb (Ahad)', '16.2.25'):
            for intake in ('Sesi 2024/2025', 'Ambilan 2025', '', 'Sesi II 2024/2025'):
                with self.subTest(intake=intake, rd=rd):
                    self.assertEqual(gift_reading(intake, rd), (None, 'undated_reporting_date'))
        self.assertEqual(_state('Sesi 2024/2025', '16 Februari'), 'unknown')
        # Blank is no date: the line reads as before. A date with its year still decides.
        self.assertEqual(gift_reading('Sesi 2024/2025', '   '), (2024, 'session_first'))
        self.assertEqual(gift_reading('Sesi 2024/2025', 'Februari 2025'), (2025, 'reporting_date'))
        # A confirmation never reads its date, so an undatable one changes nothing there.
        self.assertEqual(gift_reading('Tahun 1 Sesi 2025/2026', '16/02/25', confirmation=True), (2025, 'session_first'))

    def test_a_two_digit_year_date_on_a_session_line_is_an_extra_date(self):
        # Never expanded to 20xx: "16/02/25" is an extra date, so the line is unknown.
        for intake in ('Sesi 2024/2025 Lapor Diri 16/02/25', 'Sesi 2024/2025 mulai 16.02.25',
                       'Sesi 2024/25 Tarikh Kemasukan: 3-3-25', 'Sesi 2025/2026 (dikemaskini 1/12/24)',
                       'Sesi 2024/2025 Ambilan Februari 2025, lapor diri 16/02/25'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'unclear_date'))
        # A session's own two-digit tail and a full 20xx date are not one.
        self.assertEqual(gift_reading('Sesi 2/2024/2025'), (2025, 'session_second'))
        self.assertEqual(gift_reading('Sesi 2024/2025 Tarikh Kemasukan 17.02.2025'), (2025, 'intake_date'))

    def test_a_session_straight_after_an_exam_word_is_an_exam_line(self):
        for intake in ('Lepasan STPM 2024/2025', 'STPM 2024/2025 Ijazah Sarjana Muda', 'SPM 2024/25',
                       'Keputusan S.P.M. 2024-2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'exam_line'))
        self.assertEqual(_state('Lepasan STPM 2024/2025'), 'unknown')
        # Beside a real session, the exam's session leaves a stray year: unknown.
        self.assertEqual(gift_reading('Kemasukan Sesi 2025/2026 (Lepasan STPM 2024/2025)'), (None, 'unclear_date'))
        # An exam word that does not stand straight before the session leaves it a session.
        self.assertEqual(gift_reading('Calon STPM Sesi 2024/2025'), (2024, 'session_first'))

    def test_a_holiday_date_is_unknown(self):
        # Eleventh review: no break-word list; "bermula" / "mulai" start nothing at all.
        for intake in ('Sesi 2024/2025 Semester 1, cuti semester bermula 1 Jan 2025',
                       'Sesi 2024/2025, cuti bermula 1 Jan 2025', 'Sesi 2024/2025 Sem 1, cuti sem mulai 1 Jan 2025',
                       'Session 2024/2025 Semester 1, semester break starting 3 Feb 2025',
                       'Session 2024/2025, holiday commencing 3 Feb 2025', 'Sesi 2024/2025 bermula 1 Jan 2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'unclear_date'))


class EleventhReviewSimplified(SimpleTestCase):
    """Lead's rule, 16 Nov 2026 - SIMPLIFY, no word lists: the start words are ONLY admission phrases;
    a month or date on a session line is never ignored (it is read by an admission phrase, or the
    reading is unknown). One test per case the lead named."""

    def _unknown(self, intake):
        self.assertIsNone(_year(intake))
        self.assertEqual(_state(intake), 'unknown')

    def test_bermula_and_a_month(self):
        self._unknown('Sesi 2024/2025 bermula Februari')

    def test_mulai_and_a_month(self):
        self._unknown('Sesi 2024/2025 mulai Mac')

    def test_kuliah_bermula_and_a_day_and_month(self):
        self._unknown('Sesi 2024/2025, kuliah bermula 3 Februari')

    def test_commencing_and_a_full_date(self):
        self._unknown('Session 2024/2025 commencing 3 March 2025')

    def test_lapor_diri_and_a_two_digit_year(self):
        self._unknown('Sesi 2024/2025 Lapor Diri 16 Feb 25')

    def test_an_apostrophe_two_digit_year(self):
        self._unknown("Ambilan Sesi 2024/2025, Semester 1 (Jan '25)")

    def test_a_month_followed_by_a_two_digit_year(self):
        self._unknown('Ambilan Sesi 2024/2025 Februari 25')

    def test_a_holiday_starting(self):
        self._unknown('Sesi 2024/2025 Semester 1, Cuti Pertengahan Semester: bermula 2 Jan 2025')

    def test_a_test_starting(self):
        self._unknown('Sesi 2024/2025 Semester 1, ujian bermula 6 Jan 2025')

    def test_an_exam_starting(self):
        self._unknown('Sesi 2024/2025 Semester 1, peperiksaan akhir bermula 6 Jan 2025')

    def test_fees_from(self):
        self._unknown('Sesi 2024/2025 Semester 1, yuran mulai Feb 2025')

    def test_a_holiday_month_even_beside_an_admission_word(self):
        self._unknown('Sesi 2024/2025 Semester 1, cuti semester bermula Januari')
        self.assertEqual(gift_reading('Ambilan Sesi 2024/2025 Semester 1, cuti semester bermula Januari'),
                         (None, 'unclear_month'))

    def test_tarikh_kemasukan_and_a_full_date(self):
        self.assertEqual(gift_reading('Sesi 2024/2025, Tarikh Kemasukan: 10/03/2025'), (2025, 'intake_date'))

    def test_ambilan_and_an_early_month(self):
        self.assertEqual(gift_reading('Ambilan Sesi 2024-25 Mac'), (2025, 'session_second'))

    def test_ambilan_and_a_late_month(self):
        self.assertEqual(gift_reading('Ambilan September Sesi 2024/2025'), (2024, 'session_first'))

    def test_sem_is_no_admission_word(self):
        self.assertEqual(gift_reading('Sem 1 2024/2025 Feb'), (None, 'unclear_month'))

    def test_a_closing_date_with_no_year(self):
        self._unknown('Sesi 2026/2027, tutup 30 April')

    def test_a_bare_session(self):
        self.assertEqual(gift_reading('Sesi 2025/2026'), (2025, 'session_first'))

    def test_a_bare_second_session(self):
        self.assertEqual(gift_reading('Sesi II 2025/2026'), (2026, 'session_second'))

    def test_a_second_intake_with_a_late_month_is_a_clash(self):
        self.assertEqual(gift_reading('Sesi II 2024/2025 Ambilan September'), (None, 'both_intakes'))


class TwelfthReview(SimpleTestCase):
    """Twelfth review (Opus), WHEN IN DOUBT, UNKNOWN: each input the reviewer wrote."""

    def test_a_plain_intake_year_on_an_exam_line_is_unknown(self):
        # The year after the intake word may be the exam's ("2024 SPM leavers"). Thirteenth review: any
        # plain year outside the session is unknown, exam word or not (the exam guard is gone).
        for intake in ('Intake: 2024 SPM leavers, Session 2025/2026', 'Kemasukan 2024 lulus SPM, Sesi 2025/2026',
                       'Kemasukan 2024 (Lepasan STPM) Sesi 2025/2026', 'Intake (2024 SPM) Session 2025/2026',
                       'Ambilan 2023 Sesi 2025/2026'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'unclear_date'))
                self.assertEqual(_state(intake), 'unknown')

    def test_a_deadline_word_is_an_event_word(self):
        for intake in ('Kemasukan Sesi 2024/2025, tawaran sah hingga Januari', 'Kemasukan Sesi 2024/2025 (tamat Mac)',
                       'Intake Session 2024/2025, reply by January', 'Kemasukan Sesi 2024/2025 sehingga Mac',
                       'Kemasukan Sesi 2024/2025 until Feb', 'Kemasukan Sesi 2024/2025 berakhir Mac',
                       'Intake by September Sesi 2024/2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'unclear_month'))
        # "by" with no date or month after it is no deadline.
        self.assertEqual(gift_reading('Intake Februari Sesi 2024/2025, offered by the college'),
                         (2025, 'session_second'))

    def test_a_misspelt_malay_month_is_a_month(self):
        for intake in ('Ambilan Febuari Sesi 2024/2025', 'Ambilan Pebruari Sesi 2024/2025',
                       'Ambilan Febrauri Sesi 2024/2025', 'Ambilan Mach Sesi 2024/2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (2025, 'session_second'))
        # On a line with no admission word it is unknown, like any month (rule A).
        self.assertEqual(gift_reading('Sesi 2024/2025 Febuari'), (None, 'unclear_month'))

    def test_a_year_after_an_admission_number_is_no_intake_year(self):
        for intake in ('No. Kemasukan 2024 Sesi 2025/2026', 'No Kemasukan 2024 Sesi 2025/2026',
                       'Nombor Kemasukan 2024 Sesi 2025/2026', 'Admission No 2024 Session 2025/2026',
                       'Admission No.: 2024 Session 2025/2026'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (2025, 'session_first'))
        # Its Kemasukan is no admission phrase either: a month beside it is unknown.
        self.assertEqual(gift_reading('No. Kemasukan 2024 Sesi 2025/2026 Februari'), (None, 'unclear_month'))
        self.assertEqual(gift_reading('No. Kemasukan 2024'), (None, 'no_year'))
        # A plain year after Kemasukan itself reads only inside the session (thirteenth review);
        # "Admission Notice" is no admission number.
        self.assertEqual(gift_reading('Kemasukan 2024 Sesi 2025/2026'), (None, 'unclear_date'))
        self.assertEqual(gift_reading('Kemasukan 2025 Sesi 2025/2026'), (2025, 'intake_year'))
        self.assertEqual(gift_reading('Admission Notice 2024 Sesi 2025/2026'), (None, 'unclear_date'))


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
                       'Sesi 2025/2026 (S.P.M. 2024)', 'Sesi 2025/2026 (SPM tahun 2024)', 'Sesi 2025/2026 SKM 2024'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (2025, 'session_first'))
        # Only the exam's own year is ignored: the intake date beside it still reads, and any other
        # year still makes the line unclear.
        self.assertEqual(gift_reading('Ambilan September 2025 Sesi 2025/2026 (STPM 2024)'), (2025, 'intake_date'))
        self.assertEqual(gift_reading('Sesi 2024/2025 (SPM 2023), tutup 30 April 2025'), (None, 'unclear_date'))
        self.assertEqual(gift_reading('Kemasukan Sesi 2025/2026 (2024 lulus SPM)'), (None, 'unclear_date'))
        self.assertEqual(_state('Sesi 2025/2026 (SPM2024)'), 'inside')
        self.assertEqual(_state('Ambilan SPM 2024'), 'unknown')

    def test_every_exam_form_counts(self):
        # Review 8: dotted forms, SPMV / SVM / STAM, the long names and the bare exam words.
        for exam in ('S.P.M. 2024', 'S.P.M 2024', 'S. P. M. 2024', 'S.T.P.M. 2024', 'SPMV 2024', 'S.P.M.V. 2024',
                     'SVM 2024', 'STAM 2024', 'Sijil Vokasional Malaysia 2024', 'Sijil Tinggi Agama Malaysia 2024',
                     'Unified Examination Certificate 2024', 'Malaysian University English Test 2024',
                     'Keputusan peperiksaan 2024', 'Examination 2024', 'Exam 2024',
                     # Ninth review: spaced letters, and the skills certificates.
                     'S P M 2024', 'S T P M 2024', 'Lepasan S P M 2024', 'SKM 2024', 'S.K.M. 2024', 'DKM 2024',
                     'Sijil Kemahiran Malaysia 2024', 'Diploma Kemahiran Malaysia 2024'):
            with self.subTest(exam=exam):
                self.assertEqual(gift_reading(exam), (None, 'exam_line'))
                self.assertEqual(gift_reading(f'Ambilan 2025 ({exam})'), (None, 'exam_line'))
                self.assertEqual(gift_reading(f'Sesi 2025/2026 ({exam})'), (2025, 'session_first'))
        # Not an exam: a word that only holds the letters.
        self.assertEqual(gift_reading('Ambilan 2025 Sp Mekanikal'), (2025, 'intake_year'))

    def test_the_date_still_wins(self):
        self.assertEqual(gift_reading('Intake 2024 SPM 2022', '3 Mar 2025'), (2025, 'reporting_date'))
        self.assertEqual(gift_reading('SPM 2024, Ambilan 2025', '14 Jul 2025'), (2025, 'reporting_date'))


class OddUnicodeNeverRaises(SimpleTestCase):
    """Review 8: a dotted capital I or a long s folded into a table word and raised a KeyError."""

    def test_odd_letters_read_or_stay_unknown(self):
        self.assertEqual(gift_reading('FİRST YEAR 2025/2026'), (2025, 'session_first'))
        self.assertEqual(gift_reading('ſecond semester 2025'), (2025, 'intake_year'))
        self.assertEqual(gift_reading('Sesi 2024/2025 Ambilan DİS'), (2024, 'session_first'))

    def test_a_long_odd_line_reads_fast(self):
        # No pattern backtracks badly on a long run of words, months or numbers (20,000 characters).
        import time
        n = 20000
        for line in ('Sesi 2024/2025 ' + 'cuti bermula ' * (n // 13) + '1 Jan 2025',
                     'Sesi 2024/2025 1/' + ' ' * n + '1/' + ' ' * n + 'x', 'STPM ' * (n // 5) + '2024/2025',
                     'Ambilan Sesi 2024/2025 ' + 'Feb ' * (n // 4), 'Sesi 2024/2025\n' + 'Ambilan Feb\n' * (n // 12),
                     'Sesi 2024/2025 ' + 'tarikh ' * (n // 7) + 'lapor diri 1 Feb 2025',
                     'Ambilan Sesi 2024/2025 ' + '1 ' * (n // 2) + 'Feb'):
            start = time.perf_counter()
            gift_reading(line, '')
            self.assertLess(time.perf_counter() - start, 1.0)

    def test_the_reader_never_raises(self):
        odd = ('İ', 'ı', 'ſ', 'K', 'ﬁ', 'ß', 'Ⅱ', '２０２５', '\u00a0', '\u200b', 'é', 'ம', '\ufffd')
        words = ('first year', 'second semester', 'final year', 'Semester 2', 'Ambilan Dis', 'Intake Sep',
                 'Sem Mac', 'Sesi II', 'SPM', 'Tahun kedua', 'Ambilan 2025', '2024/2025 Ambilan Feb')
        for o in odd:
            for w in words:
                for i in range(len(w)):        # the odd letter in every place, and glued between two
                    for base in (w[:i] + o + w[i + 1:], w[:i] + o + w[i:]):
                        for line in (base, f'{base} 2024/2025', f'Ambilan {base} 2025'):
                            for kw in ({}, {'confirmation': True}, {'context': line}):
                                with self.subTest(line=line, kw=kw):
                                    gift_reading(line, line, **kw)
