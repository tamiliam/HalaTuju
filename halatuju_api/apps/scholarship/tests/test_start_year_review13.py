"""Thirteenth review (Opus) of the gift's start-year reader (`session_year`), lead's decision 16 Nov 2026:
fix by simplifying, WHEN IN DOUBT, UNKNOWN.

- The "plain intake year beats the session" exception is gone: a plain year straight after an intake
  word on a session line reads only when it is one of the session's two years; any other is unknown
  ("Ambilan 2023 Sesi 2025/2026", "Intake: 2024 school leavers, Session 2025/2026").
- Exam words take a plural s ("SPMs"), and a capital SPM / SPMV / STPM / STAM counts glued to letters
  ("SPMleavers", "lepasanSPM").
- A misspelt month is a month (edit distance to a full month name; `session_year._misspelt_month`).

Every input the reviewer wrote is in `INPUTS`, with the answer it now reads.
"""
from django.test import SimpleTestCase

from apps.scholarship.session_year import _misspelt_month, gift_reading
from apps.scholarship.start_year import decide

GIFT = [2025, 2026]

# (intake line, reporting date, confirmation, year, why)
INPUTS = [
    # cohort words beside a session (plain intake year)
    ('Intake: 2024 Matriculation leavers, Session 2025/2026', '', False, None, 'unclear_date'),
    ('Kemasukan 2024 (Lepasan Matrikulasi) Sesi 2025/2026', '', False, None, 'unclear_date'),
    ('Kemasukan 2024 lepasan Asasi, Sesi 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 Foundation graduates, Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake: 2024 school leavers, Session 2025/2026', '', False, None, 'unclear_date'),
    ('Kemasukan 2024 lulusan Diploma Sesi 2025/2026', '', False, None, 'unclear_date'),
    ('Intake: 2024 IELTS, Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake: 2024 graduates Session 2025/2026', '', False, None, 'unclear_date'),
    ('Ambilan 2023 Sesi 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 SPM Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 S.P.M Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 SAM Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 UPSR Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 PT3 Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 SPMs Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 Spm-leavers Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 (S.T.P.M.) Session 2025/2026', '', False, None, 'unclear_date'),
    ("Intake 2024 STPM's Session 2025/2026", '', False, None, 'unclear_date'),
    ('Intake 2024 STPMleavers Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 SPMleavers Session 2025/2026', '', False, None, 'unclear_date'),
    ('Intake 2024 lepasanSPM Session 2025/2026', '', False, None, 'unclear_date'),
    ('Sesi 2025/2026 Kemasukan 2024 lepasan Matrikulasi', '', False, None, 'unclear_date'),
    ('Sesi 2025/2026 Intake 2024 school leavers', '', False, None, 'unclear_date'),
    ('Sesi 2025/2026 Intake 2024', '', False, None, 'unclear_date'),
    ('Intake 2024, Session 2025/2026', '', False, None, 'unclear_date'),
    # admission number
    ('No. Kemasukan 2024 Sesi 2025/2026', '', False, 2025, 'session_first'),
    ('No.Kemasukan 2024 Sesi 2025/2026', '', False, 2025, 'session_first'),
    ('No.Kemasukan:2024 Sesi 2025/2026', '', False, 2025, 'session_first'),
    ('NO KEMASUKAN 2024 Sesi 2025/2026', '', False, 2025, 'session_first'),
    ('No Kemasukan: 2023 Ambilan 2024', '', False, 2024, 'intake_year'),
    ('No Kemasukan 2023 Sesi 2025/2026 Ambilan Februari', '', False, 2026, 'session_second'),
    ('No. Kemasukan Sesi 2025/2026 Ambilan Februari', '', False, 2026, 'session_second'),
    ('Admission No 2024 Session 2025/2026', '', False, 2025, 'session_first'),
    ('Admission No. : 2024 Session 2025/2026', '', False, 2025, 'session_first'),
    ('Admission Number 2024 Intake 2023', '', False, 2023, 'intake_year'),
    ('Admission No 2024 Intake 2023', '', False, 2023, 'intake_year'),
    ('Admission No 2024 Date of Admission 3 March 2026 Session 2025/2026', '', False, 2026, 'intake_date'),
    ('No. Kemasukan 2024-001 Sesi 2025/2026', '', False, None, 'unclear_date'),
    ('No. Kemasukan 2024/001 Sesi 2025/2026', '', False, None, 'unclear_date'),
    ('No. Kemasukan: 2024 2026', '', False, 2026, 'intake_year'),
    ('Nombor Kemasukan 2024 Sesi 2025/2026', '', False, 2025, 'session_first'),
    ('Nombor Kemasukan 2024', '', False, None, 'no_year'),
    ('Admission No 2024', '', False, None, 'no_year'),
    ('Tarikh Kemasukan No. Kemasukan 2024 Sesi 2025/2026', '', False, 2025, 'session_first'),
    ('Kemasukan No. 2024 Sesi 2025/2026', '', False, None, 'unclear_date'),
    ('No Kemasukan 2025 Sesi 2025/2026 Februari', '', False, None, 'unclear_month'),
    ('Admission no.2024 Session 2025/2026', '', False, 2025, 'session_first'),
    ('Admission Nos 2024 Session 2025/2026', '', False, None, 'unclear_date'),
    ('No. Kemasukan 2024 Ambilan Sesi 2025/2026 Mac', '', False, 2026, 'session_second'),
    ('Admission No 2026 Session 2024/2025', '', False, 2024, 'session_first'),
    ('No. Kemasukan 2026 Sesi 2024/2025 Ambilan Feb', '', False, 2025, 'session_second'),
    # deadline
    ('Kemasukan Sesi 2024/2025 (tamat Mac)', '', False, None, 'unclear_month'),
    ('Ambilan Mac Sesi 2024/2025 sah hingga', '', False, None, 'unclear_month'),
    ('Ambilan Februari Sesi 2024/2025 reply by Mac', '', False, None, 'unclear_month'),
    ('Ambilan Februari Sesi 2024/2025 bypass', '', False, 2025, 'session_second'),
    ('Ambilan Februari Sesi 2024/2025 by 2', '', False, None, 'unclear_month'),
    ('Ambilan Sesi 2024/2025 Februari by', '', False, 2025, 'session_second'),
    ('Ambilan Sesi 2024/2025 Februari (sah)', '', False, None, 'unclear_month'),
    ('Ambilan Sesi 2024/2025 Februari standby', '', False, 2025, 'session_second'),
    # misspelt months
    ('Ambilan Febuari Sesi 2024/2025', '', False, 2025, 'session_second'),
    ('Ambilan Pebruari Sesi 2024/2025', '', False, 2025, 'session_second'),
    ('Ambilan Mach Sesi 2024/2025', '', False, 2025, 'session_second'),
    ('Ambilan Sesi 2024/2025', '16 Febuari 2025', False, 2025, 'reporting_date'),
    ('Ambilan Sesi 2024/2025', '16 Mach 2025', False, 2025, 'reporting_date'),
    ('Sesi 2024/2025', '16 Pebruari', False, None, 'undated_reporting_date'),
    ('Sesi 2024/2025 Mach 3', '', False, None, 'unclear_date'),
    ('Ambilan 2024/2025 Mach 2', '', False, None, 'unclear_date'),
    ('Sesi 2024/2025 Tarikh Kemasukan 3 Febuari 2025', '', False, 2025, 'intake_date'),
    ('Sesi 2024/2025 Tarikh Kemasukan 3 Febuari 2024', '', False, 2024, 'intake_date'),
    ('Ambilan Febuary Sesi 2024/2025', '', False, 2025, 'session_second'),
    ('Ambilan Februray Sesi 2024/2025', '', False, 2025, 'session_second'),
    ('Ambilan Sept. Sesi 2025/2026', '', False, 2025, 'session_first'),
    ('Ambilan Ogo Sesi 2025/2026', '', False, 2025, 'session_first'),
    ('Ambilan Febuari 2025 Semester 1 Sesi 2024/2025', '', True, 2025, 'intake_date'),
    ('Ambilan Febuari 2025', '', True, 2025, 'intake_year'),
    ('Ambilan Mach 2024', '', True, 2024, 'intake_year'),
    ('Ambilan Feburary Sesi 2024/2025', '', False, 2025, 'session_second'),
    ('Ambilan Febraury Sesi 2024/2025', '', False, 2025, 'session_second'),
    ('Ambilan Januay Sesi 2024/2025', '', False, 2025, 'session_second'),
    ('Intake Agust Session 2024/2025', '', False, 2024, 'session_first'),
    ('Intake Septembar Session 2025/2026', '', False, 2025, 'session_first'),
    # exam words, plural and glued, with no session
    ('Lepasan SPMs 2024', '', False, None, 'exam_line'),
    ('SPMleavers 2024', '', False, None, 'exam_line'),
    ('lepasanSPM 2024', '', False, None, 'exam_line'),
]


class ThirteenthReview(SimpleTestCase):
    """Each review-13 input reads the answer in `INPUTS`; none is a year outside the session it names
    unless the letter writes that year as its intake date or its only year."""

    def test_each_input(self):
        for intake, rd, conf, year, why in INPUTS:
            with self.subTest(intake=intake, rd=rd, confirmation=conf):
                self.assertEqual(gift_reading(intake, rd, confirmation=conf), (year, why))

    def test_a_plain_intake_year_reads_only_inside_the_session(self):
        self.assertEqual(gift_reading('Ambilan 2025 Sesi 2025/2026'), (2025, 'intake_year'))
        self.assertEqual(gift_reading('Ambilan 2026 Sesi 2025/2026'), (2026, 'intake_year'))
        self.assertEqual(gift_reading('Intake 2025 (SPM 2024 leavers) Session 2025/2026'), (2025, 'intake_year'))
        # It agrees with the terms like a date: a first intake's year is the session's first.
        self.assertEqual(gift_reading('Ambilan 2026 Sesi 1 2025/2026'), (None, 'unclear_date'))
        self.assertEqual(_state('Ambilan 2023 Sesi 2025/2026'), 'unknown')
        # With no session a plain intake year is unchanged.
        self.assertEqual(gift_reading('Ambilan 2023'), (2023, 'intake_year'))
        self.assertEqual(gift_reading('Intake 2024 school leavers'), (2024, 'intake_year'))

    def test_a_glued_exam_word_is_capitals_only(self):
        for intake in ('Ambilan 2025 Stamford College', 'Ambilan 2025 Kampus Hospmed', 'Ambilan 2025 Sp Mekanikal'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (2025, 'intake_year'))
        for intake in ('Ambilan 2025 SPMleavers', 'Ambilan 2025 lepasanSTPM', 'Ambilan 2025 STAMholders',
                       'Ambilan 2025 SPMVcalon', 'Ambilan 2025 MUETs'):
            with self.subTest(intake=intake):
                self.assertEqual(gift_reading(intake), (None, 'exam_line'))

    def test_a_misspelt_month_is_a_month(self):
        for word, name in (('Febuary', 'february'), ('Feburary', 'february'), ('Febraury', 'february'),
                           ('Februray', 'february'), ('Febuari', 'februari'), ('Febrauri', 'februari'),
                           ('Januay', 'january'), ('Agust', 'august'), ('Septmber', 'september'),
                           ('Septembar', 'september'), ('Novembar', 'november'), ('Disembr', 'disember')):
            with self.subTest(word=word):
                self.assertEqual(_misspelt_month(word), name)
        # On a line with no admission word, or beside a deadline, it is unknown like any month.
        self.assertEqual(gift_reading('Sesi 2024/2025 Febuary'), (None, 'unclear_month'))
        self.assertEqual(gift_reading('Kemasukan Sesi 2024/2025 tamat Feburary'), (None, 'unclear_month'))
        self.assertEqual(gift_reading('Ambilan Sesi 2024/2025 3 Febuary'), (None, 'unclear_date'))

    def test_an_ordinary_word_is_no_month(self):
        # Words near the short names (March, April, Julai) and looser matches stay words.
        for word in ('match', 'march', 'batch', 'mulai', 'nilai', 'jalan', 'jumlah', 'ambil', 'markah', 'adjust',
                     'remember', 'member', 'semester', 'number', 'janani', 'session', 'ambilan', 'kemasukan'):
            with self.subTest(word=word):
                self.assertIsNone(_misspelt_month(word))
        self.assertEqual(gift_reading('Ambilan Sesi 2024/2025 Jalan Ampang, nilai semester'), (2024, 'session_first'))


def _state(intake, rd='', **kw):
    return decide(gift_reading(intake, rd, **kw).year, GIFT)
