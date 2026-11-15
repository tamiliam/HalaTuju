"""H3a rebuild (2026-11-15): the GIFT's own conservative start-year reading (`session_year`).

The cases are the adversarial reviewer's probe (h3r3/probe.py) plus the lead's list. The reader
names a year only when the letter makes it sure; else EMPTY (a person checks) or both years of a
session (then `start_year.reading`'s straddle rule). The money never reads this module: see
`test_start_year_money.py`.
"""
from django.test import SimpleTestCase

from apps.scholarship.session_year import EMPTY, gift_start_years, looks_stpm

GIFT = {2025, 2026}


def _state(years):
    """`start_year.reading`'s straddle rule over the Degree gift's years."""
    inside = [y in GIFT for y in years]
    if years and all(inside):
        return 'inside'
    if years and not any(inside):
        return 'outside'
    return 'unknown'


class LaterTermsAreUnknown(SimpleTestCase):
    """Semester 3+ / Year 2+ is the student's place in the course, not the intake, with ANY date."""

    def test_later_semesters_and_years(self):
        for intake, rd in (
                ('Semester 3 Sesi 2024/2025', ''), ('Semester 3 Sesi 2024/2025', '3 Mac 2025'),
                ('Semester III 2024/2025', ''), ('Sem3 2024/2025', ''), ('Sem 3 Sesi 2024/2025', ''),
                ('Semester 10 Sesi 2024/2025', ''), ('Semester VII Sesi 2025/2026', ''),
                ('Semester XII Sesi 2025/2026', ''), ('Semester Lima Sesi 2025/2026', ''),
                ('Semester Tiga 2025/2026', ''), ('Semester Dua Belas 2025/2026', ''),
                ('Semester Kelima 2025/2026', ''), ('Semester Ketiga 2025/2026', ''),
                ('Sesi 2024/2025 Semester IV', '9 Sept 2025'), ('Sesi : 2026/2027 Semester : 3', ''),
                ('Third Semester, Session 2024/2025', ''), ('Semester 2/3 2024/2025', ''),
                ('Tahun 2 Sesi 2025/2026', ''), ('Tahun 2 Sesi 2025/2026', '7 September 2025'),
                ('Year 2, Session 2025/2026', ''), ('Tahun II Sesi 2025/2026', ''),
                ('Tahun Kedua Sesi 2025/2026', ''), ('Tahun Akhir Sesi 2025/2026', ''),
                ('Year 3 Semester 1 Session 2025/2026', ''), ('Second year, 2025/2026', ''),
                ('2nd Year Sem 1 2025/2026', ''), ('Final Year, Session 2025/2026', ''),
                ('Penggal 3 Sesi 2024/2025', ''), ('Tingkatan 6 Atas 2024/2025', ''),
                ('Semester 3, Julai 2025', ''), ('Tahun 2', '1 Mac 2026')):
            with self.subTest(intake=intake, rd=rd):
                self.assertEqual(gift_start_years(intake, rd), EMPTY)

    def test_no_stored_date_rescues_a_later_term(self):
        self.assertEqual(gift_start_years('Semester 3 Sesi 2024/2025', '', stored_year=2025), EMPTY)
        self.assertEqual(gift_start_years('Tahun 2', '', stored_year=2026), EMPTY)

    def test_a_first_year_is_not_a_later_term(self):
        self.assertEqual(gift_start_years('Tahun 1 Semester 1 Sesi 2025/2026'), {2025})
        self.assertEqual(gift_start_years('SEMESTER 1 TAHUN 2026'), {2026})


class SecondTerms(SimpleTestCase):
    def test_semester_2_on_an_ordinary_offer_reads_the_second_year(self):
        for intake in ('Semester 2 Sesi 2024/2025', 'Sem 2 Sesi 2024/2025', 'Semester II Sesi 2024/2025',
                       'Sem. II 2024/2025', 'Semester Kedua 2024/2025', 'Term 2 2024/2025',
                       'Second Semester, Session 2024/2025', 'Semester 2 Tahun 1 Sesi 2024/2025',
                       'Sesi 2024/2025 Ambilan Februari', 'Session 2024/25 February intake',
                       'Session 2024/2025 January intake', 'Sesi 2024/2025 - 26 Feb'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), {2025})

    def test_semester_2_on_a_confirmation_or_stpm_letter_is_unknown(self):
        for intake in ('Semester 2 Sesi 2024/2025', 'Semester II Sesi 2024/2025', 'Sesi II 2024/2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake, confirmation=True), EMPTY)
                self.assertEqual(gift_start_years(intake, stpm=True), EMPTY)
                self.assertEqual(gift_start_years(intake, '2 Mac 2025', stpm=True), EMPTY)
        self.assertEqual(gift_start_years('Penggal 2 Sesi 2024/2025'), EMPTY)   # a Form 6 term
        self.assertEqual(gift_start_years('Semester 2, Mac 2025', stpm=True), EMPTY)

    def test_a_first_term_on_an_stpm_letter_still_reads(self):
        self.assertEqual(gift_start_years('Penggal 1 Sesi 2025/2026', stpm=True), {2025})

    def test_looks_stpm(self):
        for words in ('Kolej Tingkatan Enam Gombak', 'Tingkatan 6', 'STPM', 'Form Six', 'Penggal 1'):
            with self.subTest(words=words):
                self.assertTrue(looks_stpm(words))
        self.assertFalse(looks_stpm('Ijazah Sarjana Muda Universiti Malaya'))


class PolySesiII(SimpleTestCase):
    """TD-631: a polytechnic "Sesi II S/S+1" starts in December of S or January of S+1."""

    def test_no_date_is_both_years(self):
        for intake in ('Sesi II 2024/2025', 'Sesi 2 : 2024/2025', 'Sesi II 2024-2025'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), {2024, 2025})
                self.assertEqual(_state(gift_start_years(intake)), 'unknown')
        self.assertEqual(_state(gift_start_years('Sesi II 2025/2026')), 'inside')
        self.assertEqual(_state(gift_start_years('Sesi II 2022/2023')), 'outside')

    def test_the_letters_date_picks_the_year(self):
        self.assertEqual(gift_start_years('Sesi II 2024/2025', '2 Disember 2024'), {2024})
        self.assertEqual(gift_start_years('Sesi II 2024/2025', '6 Januari 2025'), {2025})

    def test_sesi_i_reads_the_first_year(self):
        self.assertEqual(gift_start_years('Sesi I 2025/2026'), {2025})


class BareSessions(SimpleTestCase):
    def test_a_bare_session_is_both_years(self):
        for intake in ('Sesi 2024/2025', 'Sesi 2024/25', 'Sesi 2024-25', 'SESI 2024 / 2025', '2024/2025',
                       'Sesi Akademik 2024/2025', 'Academic Session 2024/2025',
                       'Ambilan Julai 2024/2025', 'Ambilan Disember 2024/2025',
                       'Sesi 2024/2025 Ambilan Disember'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), {2024, 2025})

    def test_the_straddle_rule(self):
        self.assertEqual(_state(gift_start_years('Sesi 2025/2026')), 'inside')
        self.assertEqual(_state(gift_start_years('Sesi Akademik 2025/2026')), 'inside')
        self.assertEqual(_state(gift_start_years('Sesi 2024/2025')), 'unknown')
        self.assertEqual(_state(gift_start_years('Sesi 2022/2023')), 'outside')

    def test_a_date_inside_the_session_picks_the_year(self):
        self.assertEqual(gift_start_years('Sesi 2025/2026', '14 Julai 2025'), {2025})
        self.assertEqual(gift_start_years('Sesi 2024/2025', '17 Februari 2025'), {2025})

    def test_a_stored_date_does_not_pick_a_session_year(self):
        self.assertEqual(gift_start_years('Sesi 2024/2025', '', stored_year=2025), {2024, 2025})


class DisagreementsAreUnknown(SimpleTestCase):
    def test_term_and_date_disagree(self):
        for intake, rd in (('Sesi 2024/2025 Semester I', '25 Februari 2025'),
                           ('Sesi 2024/2025 Semester 1', '3 Mac 2025'),
                           ('Semester 1 2024/2025', '8 September 2025'),
                           ('Semester 2 Sesi 2024/2025', '9 September 2024'),
                           ('Session 2024/25 Sept', '3 Februari 2025'),
                           ('Sesi 2024/2025', '5 Jan 2023'),               # a date outside the session
                           ('Intake Jan 2025 (Session 2024/2025)', '8 Sept 2024'),
                           ('2024', '10 Jun 2025')):                        # no session: year vs date
            with self.subTest(intake=intake, rd=rd):
                self.assertEqual(gift_start_years(intake, rd), EMPTY)

    def test_both_terms_or_two_sessions(self):
        for intake in ('Semester 1 / 2 Sesi 2025/2026', 'Semester 1/2 2025/2026',
                       'Sesi 2024/2025 Semester 1 dan Semester 2',
                       'Sesi 2024/2025 Ambilan September / Februari', 'Sesi 2024/2025, Sesi 2025/2026'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), EMPTY)

    def test_agreeing_term_and_date(self):
        self.assertEqual(gift_start_years('Semester 2 Sesi 2025/2026', '2 Mac 2026'), {2026})
        self.assertEqual(gift_start_years('Semester 2 2024/2025', '2 Mac 2025'), {2025})
        self.assertEqual(gift_start_years('Semester 1 Sesi 2024/2025', '8 Sept 2024'), {2024})


class WrittenMonthAndYear(SimpleTestCase):
    def test_a_written_month_and_year_on_the_intake_line_wins(self):
        for intake, year in (('Intake Jan 2025 (Session 2024/2025)', 2025),
                             ('Intake: February 2025, Session 2024/2025', 2025),
                             ('Ambilan September 2025 Sesi 2025/2026', 2025),
                             ('Sesi 2024/2025 (Oktober 2024)', 2024)):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), {year})

    def test_a_written_year_outside_the_session_is_unknown(self):
        self.assertEqual(gift_start_years('Ambilan September 2023 Sesi 2025/2026'), EMPTY)


class SessionParsing(SimpleTestCase):
    """The good parts kept from the branch: date ranges are not sessions; two-digit sessions,
    slashes and dashes, "Sesi Akademik" are."""

    def test_a_date_range_is_not_a_session(self):
        for intake, year in (('Julai 2025 - 26 Februari 2026', 2025), ('1 Julai 2025 - 26 Feb 2026', 2025),
                             ('Julai 2025 – 26 Februari', 2025), ('Jul 2025 - 26/02/2026', 2025),
                             ('Jun 2024 - 25 Mei 2025', 2024), ('6 / 2025 – 12 / 2026', 2025),
                             ('2024/2026', 2024)):
            with self.subTest(intake=intake):
                self.assertEqual(gift_start_years(intake), {year})

    def test_month_terms(self):
        self.assertEqual(gift_start_years('Sesi 2024/2025 Ambilan September'), {2024})
        self.assertEqual(gift_start_years('Session 2024/25 Sept'), {2024})
        self.assertEqual(gift_start_years('Session 2025/26 October intake'), {2025})
        self.assertEqual(gift_start_years('Sesi 2025/2026 Kemasukan Semester 1'), {2025})

    def test_no_session_reads_the_first_year_then_the_date_then_the_stored_year(self):
        self.assertEqual(gift_start_years('Mac 2025'), {2025})
        self.assertEqual(gift_start_years('Ambilan Jun 2025', '8 Jun 2025'), {2025})
        self.assertEqual(gift_start_years('', '10 JUN 2024'), {2024})
        self.assertEqual(gift_start_years('', '', stored_year=2026), {2026})
        self.assertEqual(gift_start_years('', ''), EMPTY)
