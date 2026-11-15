"""H3a rebuild (2026-11-15): the GIFT's own careful start-year reading (`session_year`).

The lead's rule (second fix round): only OUTSIDE changes a result, so OUTSIDE must be SURE; INSIDE
needs a clear first-year signal; any doubt is unknown (a reviewer line). The cases are the
adversarial reviews' probes (h3r3, h3r4) and the lead's lists; the generated table is in
`test_start_year_gift_property.py`. The money never reads this module: `test_start_year_money.py`.
"""
from django.test import SimpleTestCase

from apps.scholarship.session_year import EMPTY, gift_reading, gift_start_years, looks_stpm
from apps.scholarship.start_year import decide

GIFT = [2025, 2026]


def _state(intake, rd='', **kw):
    return decide(gift_reading(intake, rd, **kw), GIFT)


class LaterTermsAreUnknown(SimpleTestCase):
    """Semester 3+ / Year 2+ is the student's place in the course, not the intake, with ANY date."""

    LATER = ('Semester 3 Sesi 2024/2025', 'Semester III 2024/2025', 'Sem3 2024/2025',
             'Semester 10 Sesi 2024/2025', 'Semester XII Sesi 2025/2026', 'Semester Lima Sesi 2025/2026',
             'Semester Dua Belas 2025/2026', 'Semester Kelima 2025/2026', 'Sesi 2024/2025 Semester IV',
             'Sesi : 2026/2027 Semester : 3', 'Third Semester, Session 2024/2025', 'Semester 2/3 2024/2025',
             'Tahun 2 Sesi 2025/2026', 'Year 2, Session 2025/2026', 'Tahun II Sesi 2025/2026',
             'Tahun Kedua Sesi 2025/2026', 'Tahun Akhir Sesi 2025/2026', 'Year 3 Semester 1 Session 2025/2026',
             'Second year, 2025/2026', '2nd Year Sem 1 2025/2026', 'Final Year, Session 2025/2026',
             'Penggal 3 Sesi 2024/2025', 'Tingkatan 6 Atas 2024/2025', 'Semester 3, Julai 2025', 'Tahun 2',
             # the second review's wordings
             'Tahun ke-2 Sesi 2025/2026', 'Tahun Ke-2 2025/2026', 'Semester ke-3 Sesi 2025/2026',
             'Semester Ke-5, Sesi 2025/2026', 'Semester ke 3 2025/2026', 'Tahun Pengajian 2, Sesi 2025/2026',
             'Tahun Pengajian: 3 Sesi 2025/2026', 'Year of Study 2, Session 2025/2026',
             'Year of study: 3, 2025/2026', 'Semester Pengajian 5 Sesi 2025/2026', '2nd-year, Session 2025/2026',
             '3rd-Year 2025/2026', 'Year-3 2025/2026', 'Final-year 2025/2026', 'Senior year 2025/2026',
             'Y2S1 2025/2026', 'Y3 S1 Session 2025/2026', 'Part 4, Sesi 2025/2026', 'Bahagian 3 Sesi 2025/2026',
             'Tahap 2 Sesi 2025/2026', 'Level 2, 2025/2026', 'Sem: V 2025/2026', 'Semester-III 2025/2026',
             'Penggal Ketiga 2025/2026', 'Sixth Semester, 2025/2026', 'Fourth year 2025', 'Tahun Akhir 2025',
             'Semester 1 Tahun 2 Sesi 2025/2026', 'Sem 1, Year 2, 2025/2026', 'Kemasukan Semester 4 Sesi 2025/2026',
             'Lanjutan pengajian Sesi 2025/2026', 'Pelajar Lama Sesi 2025/2026', 'Continuing Sesi 2025/2026',
             'Tahun 2 (Sesi 2025/2026)', 'Tahun dua', 'Year 4 Sem 2 2025', 'Semester Kesebelas 2025',
             'semester sepuluh 2025')

    def test_later_terms_with_a_session_a_date_or_neither(self):
        for intake in self.LATER:
            for rd in ('', '8 September 2025', '3 Mac 2026'):
                with self.subTest(intake=intake, rd=rd):
                    self.assertEqual(gift_start_years(intake, rd), EMPTY)
        for intake, rd in (('Semester 1 Tahun II', '8 September 2025'), ('Semester1 Tahun2', '8/9/2025'),
                           ('SEM 3', '15 September 2025'), ('Semester Empat', '10 Mac 2025')):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake, rd), EMPTY)

    def test_the_programme_and_stream_text_is_scanned_too(self):
        for context in ('Ijazah Sarjana Muda Kejuruteraan (Tahun 2)', 'Diploma Perakaunan Semester 5',
                        'Bachelor of Science, Year of Study 3', 'Part 4'):
            with self.subTest(context=context):
                self.assertEqual(gift_start_years('Semester 1 Sesi 2025/2026', context=context), EMPTY)
        # A qualification's level in the programme name is not a year of study.
        self.assertEqual(gift_start_years('Ambilan Julai 2025', context='Sijil Kemahiran Malaysia Tahap 3'),
                         {2025})

    def test_a_first_year_is_not_a_later_term(self):
        self.assertEqual(_state('Tahun 1 Semester 1 Sesi 2025/2026'), 'inside')
        self.assertEqual(_state('SEMESTER 1 TAHUN 2026'), 'inside')


class SecondTermsAreUnknown(SimpleTestCase):
    """A second term is the student's place: a February starter and a September one share it."""

    def test_second_terms(self):
        for intake, rd in (('Semester 2 Sesi 2024/2025', ''), ('Sem 2 Sesi 2024/2025', ''),
                           ('Semester II Sesi 2024/2025', ''), ('Sem. II 2024/2025', ''),
                           ('Semester Kedua 2024/2025', ''), ('Term 2 2024/2025', ''),
                           ('Second Semester, Session 2024/2025', ''), ('Semester 2 Tahun 1 Sesi 2024/2025', ''),
                           ('Semester 2', '1 Mac 2025'), ('Semester II', '1 Mac 2025'), ('Semester 2 2025', ''),
                           ('Semester II 2024/2025', '17 Februari 2025'), ('Penggal 2 Sesi 2024/2025', ''),
                           ('2024/2025 Semester 2 (Feb 2025 intake)', ''), ('Sesi 2024/2025: Sem 2; Mac 2025', ''),
                           ('Semester 2 Sesi 2022/2023', '')):
            with self.subTest(intake=intake, rd=rd):
                self.assertEqual(gift_start_years(intake, rd), EMPTY)

    def test_sesi_ii_on_a_confirmation_or_stpm_letter_is_unknown(self):
        self.assertEqual(gift_start_years('Sesi II 2024/2025', confirmation=True), EMPTY)
        self.assertEqual(gift_start_years('Sesi II 2024/2025', '6 Januari 2025', stpm=True), EMPTY)

    def test_a_first_term_on_an_stpm_letter_still_reads(self):
        self.assertEqual(_state('Penggal 1 Sesi 2025/2026', stpm=True), 'inside')

    def test_looks_stpm(self):
        for words in ('Kolej Tingkatan Enam Gombak', 'Tingkatan 6', 'STPM', 'Form Six', 'Penggal 1'):
            with self.subTest(words=words):
                self.assertTrue(looks_stpm(words))
        self.assertFalse(looks_stpm('Ijazah Sarjana Muda Universiti Malaya'))


class BareSessionsAndSesiII(SimpleTestCase):
    """No first-year signal: never inside; outside only when every year read is before the gift's
    (a continuing student started earlier still)."""

    def test_a_bare_session_is_both_years(self):
        for intake in ('Sesi 2024/2025', 'Sesi 2024/25', 'Sesi 2024-25', 'SESI 2024 / 2025', '2024/2025',
                       'Sesi Akademik 2024/2025', 'Academic Session 2024/2025', 'Sesi II 2024/2025',
                       'Sesi 2 : 2024/2025', 'Sesi II 2024-2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), {2024, 2025})

    def test_the_rule(self):
        for intake in ('Sesi 2025/2026', '2025/2026', 'Sesi II 2025/2026', 'Sesi 2024/2025', 'Sesi 2027/2028',
                       'SESI I : 2025/2026', 'SESI 1-2025/2026', 'SESI 2-2025/2026'):
            with self.subTest(intake=intake):
                self.assertEqual(_state(intake), 'unknown')
        for intake in ('Sesi 2022/2023', 'Sesi Akademik 2023/2024', 'Semester 1 Sesi 2023/2024'):
            with self.subTest(intake=intake):
                self.assertEqual(_state(intake), 'outside')
        # Fifth review: "II" after "Sesi" is not in OUTSIDE's closed vocabulary.
        self.assertEqual(_state('Sesi II 2022/2023'), 'unknown')

    def test_the_letters_date_picks_the_year_but_is_no_first_year_signal(self):
        self.assertEqual(gift_start_years('Sesi II 2024/2025', '2 Disember 2024'), {2024})
        self.assertEqual(gift_start_years('Sesi II 2024/2025', '6 Januari 2025'), {2025})
        self.assertEqual(gift_start_years('Sesi 2024/2025', '17 Februari 2025'), {2025})
        for intake, rd in (('Sesi Akademik 2025/2026', '8 September 2025'), ('Sesi 2025/2026', '30 Jun 2025'),
                           ('Sesi 2024/2025', '3 Mac 2025')):
            with self.subTest(intake=intake):
                self.assertEqual(_state(intake, rd), 'unknown')
        self.assertEqual(_state('Sesi 2023/2024', '8 September 2023'), 'outside')

    def test_a_sesi_number_with_no_session_is_unknown(self):
        self.assertEqual(gift_start_years('Sesi II 2025'), EMPTY)

    def test_an_intake_word_makes_a_bare_session_a_first_year(self):
        self.assertEqual(_state('Ambilan 2025 (Sesi 2025/2026)'), 'inside')
        self.assertEqual(_state('Ambilan Julai 2024/2025'), 'unknown')        # 2024 or 2025


class OtherYearsOnTheLine(SimpleTestCase):
    def test_a_year_outside_the_session_is_unknown(self):
        for intake in ('Ambilan 2023, Semester 1 Sesi 2025/2026', 'Ambilan 2023 Sesi 2025/2026',
                       'Intake Sept 2023 - Session 2025/2026', 'Ambilan September 2023 Sesi 2025/2026',
                       'Sesi 2024/2025, Sesi 2025/2026'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), EMPTY)

    def test_an_exam_year_is_not_a_start_year(self):
        for intake, rd in (('SPM 2024, Ambilan 2025', '14 Julai 2025'), ('Ambilan Julai 2025 (SPM 2024)', '14 Julai 2025'),
                           ('Keputusan SPM 2024; Ambilan 2025', ''), ('Kemasukan 2025 (2024 lulus SPM)', ''),
                           ('Ambilan September 2025 Sesi 2025/2026 (STPM 2024)', '')):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake, rd), {2025})
                self.assertEqual(_state(intake, rd), 'inside')

    def test_several_years_without_a_session(self):
        self.assertEqual(gift_start_years('Sesi Julai 2025 hingga Jun 2029'), EMPTY)
        self.assertEqual(gift_start_years('2023 2025', '8 Jun 2025'), {2025})
        self.assertEqual(_state('Ambilan 2022 2023', '8 Jun 2023'), 'unknown')   # clashing years: never a fail

    def test_no_session_reads_the_year_or_the_date(self):
        self.assertEqual(_state('2024', '10 Jun 2024'), 'outside')
        self.assertEqual(_state('Mac 2025'), 'inside')
        self.assertEqual(_state('2025'), 'inside')
        self.assertEqual(_state('Ambilan Jun', '8 Jun 2025'), 'inside')
        self.assertEqual(_state('', '8 Jun 2025'), 'unknown')                 # a date alone: no first year
        self.assertEqual(_state('', '8 Jun 2023'), 'outside')
        self.assertEqual(gift_start_years('', ''), EMPTY)
        self.assertEqual(gift_start_years('2024', '10 Jun 2025'), EMPTY)      # year and date disagree


class SlashTailsAndWrittenMonths(SimpleTestCase):
    def test_after_a_slash_the_tail_is_never_a_day(self):
        for intake, rd in (('Session 2024/25 Feb 2025', ''), ('Sesi 2024/25 Februari 2025', ''),
                           ('SESI 2024/25 MAC 2025', '3 Mac 2025')):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake, rd), {2025})
                self.assertEqual(_state(intake, rd), 'inside')

    def test_after_a_dash_a_date_is_not_a_session(self):
        for intake, year in (('Jul 2025 - 26/02/2026', 2025),
                             ('6 / 2025 – 12 / 2026', 2025), ('2024/2026', 2024)):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake, '8 Jun ' + str(year)), {year})
        # Two written month-years, or two months, on one line (a course span): doubt, so unknown,
        # never a session (fifth review: two months are two dates).
        for intake in ('Julai 2025 - 26 Februari 2026', '1 Julai 2025 - 26 Feb 2026', 'Julai 2025 – 26 Februari'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake, '8 Jun 2025'), EMPTY)

    def test_a_written_month_and_year_wins(self):
        for intake, year in (('Intake Jan 2025 (Session 2024/2025)', 2025),
                             ('Intake: February 2025, Session 2024/2025', 2025),
                             ('Ambilan September 2025 Sesi 2025/2026', 2025), ('Sesi 2024/2025 (Oktober 2024)', 2024),
                             ('Ambilan Februari 2025 Sesi 2024/2025', 2025), ('2025/2026 Sem 1 Okt 2025', 2025)):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), {year})
        self.assertEqual(_state('Sesi 2024/2025 (Oktober 2024)'), 'outside')

    def test_month_names(self):
        self.assertEqual(_state('Sesi 2024/2025 Ambilan Februari'), 'inside')
        self.assertEqual(_state('Ambilan Sesi Februari 2025/2026'), 'inside')
        self.assertEqual(_state('Intake 2025/26 September'), 'inside')
        self.assertEqual(gift_start_years('Session 2024/25 Sept'), {2024})


class Disagreements(SimpleTestCase):
    def test_term_and_date_disagree(self):
        for intake, rd in (('Sesi 2024/2025 Semester I', '25 Februari 2025'), ('Semester 1 Sesi 2024/2025', '3 Mac 2025'),
                           ('Semester 1 2024/2025', '8 September 2025'), ('Session 2024/25 Sept', '3 Februari 2025'),
                           ('Sesi 2024/2025', '5 Jan 2023'), ('Intake Jan 2025 (Session 2024/2025)', '8 Sept 2024')):
            with self.subTest(intake=intake, rd=rd):
                self.assertEqual(gift_start_years(intake, rd), EMPTY)

    def test_both_terms(self):
        for intake in ('Semester 1 / 2 Sesi 2025/2026', 'Semester 1/2 2025/2026',
                       'Sesi 2024/2025 Semester 1 dan Semester 2', 'Sesi 2024/2025 Ambilan September / Februari',
                       'Sesi II 2024/2025 (Oktober)', 'Sesi I 2024/2025 Februari'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), EMPTY)


class ConfirmationLetters(SimpleTestCase):
    """A confirmation-of-studies letter names the CURRENT session, not the intake."""

    def test_a_bare_session_a_lone_year_or_only_a_date_is_unknown(self):
        for intake, rd in (('Sesi 2025/2026', ''), ('Sesi 2025/2026', '8 September 2025'), ('', '8 September 2025'),
                           ('2025', ''), ('Sesi 2022/2023', ''), ('Ambilan 2025', ''), ('Semester ke-4', '')):
            with self.subTest(intake=intake, rd=rd):
                self.assertEqual(gift_start_years(intake, rd, confirmation=True), EMPTY)

    def test_a_first_term_or_a_written_month_year_reads(self):
        # Fifth review: a confirmation letter's Semester 1 or intake line may be the session's, shared
        # by every year, so only Year 1 passes; the rest goes to a person.
        self.assertEqual(decide(gift_reading('Semester 1 Sesi 2025/2026', confirmation=True), GIFT), 'unknown')
        self.assertEqual(decide(gift_reading('Ambilan September 2025', confirmation=True), GIFT), 'unknown')
        self.assertEqual(decide(gift_reading('Tahun 1 Semester 1 Sesi 2025/2026', confirmation=True), GIFT),
                         'inside')
        self.assertEqual(decide(gift_reading('Ambilan September 2022, Sesi 2022/2023', confirmation=True), GIFT),
                         'outside')


class DamageNeverReadsInside(SimpleTestCase):
    """Fifth review, found by the mutation fuzz: a damaged line or date must not read INSIDE (a hidden
    true year may be outside). Each case was inside before these guards."""

    def test_a_number_run_with_a_letter_or_symbol_glued_is_unknown(self):
        for intake in ('Intake 2O21 1 Julai 2025', 'Semester Pertama Session 2025/2026 20g21/22',
                       'Ambilan 2025a', 'Ambilan Julai 2025—2026', 'Sesi 2025/2026Semester'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), EMPTY)

    def test_a_messy_date_is_unknown(self):
        for rd in ('8 September 202q4', '8 Jun 2023 hingga 3 Januari 2026', '3 Mac 2027 / Jan 2026', '/ 2019'):
            with self.subTest(rd=rd):
                self.assertEqual(gift_start_years('Ambilan Julai 2025', rd), EMPTY)

    def test_a_second_date_on_the_line_is_unknown(self):
        for intake in ('Semester Pertama Sesi 2024/2025 1 Julai 2025', 'Ambilan 3 Mac 2025 Session 2024/25',
                       '1 Julai 2025 Ambilan Jun', 'Sem I September 2021 1 Julai 2025',
                       'Intake Mac 2024 - 25 2024', 'Ambilan Mac 2024 - 25'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), EMPTY)

    def test_a_written_month_year_in_the_wrong_half_of_the_session_is_unknown(self):
        for intake in ('Intake Session Jan 2026 2026/27', 'Tahun 1 Semester 1 Julai 2025 Session 2024/25'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), EMPTY)

    def test_an_exam_year_needs_the_start_year_named_after_an_intake_word(self):
        for intake in ('September SPM 2022 12/1/2025', 'Tahun 1 Semester 1 SPM 2021 2025/2026',
                       '2025/2026 Ambilan Kohort SPM 2024', 'SPM 2023 3 Mac 2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), EMPTY)
        self.assertEqual(_state('SPM 2024, Ambilan 2025'), 'inside')
