"""H3a second fix round (2026-11-15): a PROPERTY test of the gift's start-year reading.

The lead's rule: only OUTSIDE changes a result, so OUTSIDE must be SURE. A large generated table of
letter lines (a term prefix x a year core x a suffix x the letter's date x the start year x the
letter kind) is read through `session_year.gift_reading` and `start_year.decide`, and:

  * OUTSIDE fires only for a short WHITELIST of sure patterns: a first-term / intake / plain /
    polytechnic-Sesi prefix (never a second or later term), a suffix that adds no clashing year (none,
    a month, an exam year), a date that agrees with the line or none, and on a confirmation letter
    only a first term or a written month-year;
  * an OUTSIDE is RIGHT against the line's true start years: with a first-year signal none of them is
    in the gift; without one (she may be continuing) every year on the line is before the gift's;
  * an INSIDE has a first-year signal and every true start year in the gift.

Plus the two fixed probe tables of the second review (h3r4): continuing students never pass, clear
2025 / 2026 starters are never failed.
"""
import itertools

from django.test import SimpleTestCase

from apps.scholarship.session_year import gift_reading
from apps.scholarship.start_year import decide

GIFT = [2025, 2026]

PREFIXES = {
    'first': ('Semester 1 ', 'Sem I ', 'Tahun 1 Semester 1 ', 'Semester Pertama '),
    'intake': ('Ambilan ', 'Intake '),
    'plain': ('',),
    'poly': ('Sesi I ', 'Sesi II '),
    'second': ('Semester 2 ', 'Sem II ', 'Penggal 2 ', 'Second Semester '),
    'later': ('Semester 3 ', 'Tahun 2 ', 'Tahun ke-2 ', 'Year of Study 2, ', 'Y2S1 ', 'Part 4 ',
              'Final-year ', 'Semester Ke-5 ', 'Pelajar Lama ', '3rd-Year '),
}
CORES = {
    'session': (lambda s: f'Sesi {s}/{s + 1}', lambda s: f'Session {s}/{(s + 1) % 100:02d}'),
    'year': (lambda s: f'{s}',),
    'monthyear': (lambda s: f'September {s}', lambda s: f'Mac {s}'),
}
SUFFIXES = {
    'none': lambda s: '',
    'month': lambda s: ' (Oktober)',
    'exam': lambda s: f' (SPM {s - 1})',
    'extra': lambda s: f' (Ambilan {s - 2})',
    'twosess': lambda s: f' Sesi {s + 1}/{s + 2}',
}
DATES = {
    'none': lambda s: '',
    'in': lambda s: f'8 September {s}',
    'next': lambda s: f'3 Mac {s + 1}',
    'off': lambda s: f'8 Jun {s - 3}',
}
STARTS = range(2021, 2028)
KINDS = ('plain', 'confirmation', 'stpm')


def _first_year(prefix, core, kind):
    """The line names a first-year intake (the table's own model, not the reader's)."""
    if kind == 'confirmation':
        return prefix == 'first' or core == 'monthyear'
    return prefix in ('first', 'intake') or core == 'monthyear' or (prefix == 'plain' and core == 'year')


def _true_starts(prefix, text, core, suffix, date, s):
    """The years a truthful letter's student may have started in, given a first-year intake (and,
    for a continuing student, the years the line places her in)."""
    if core == 'session':
        t = {s} if prefix == 'first' or (prefix == 'poly' and 'Sesi I ' in text) or suffix == 'month' else {s, s + 1}
    else:
        t = {s}
    if date == 'in':
        t &= {s}
    elif date == 'next':
        t &= {s + 1}
    elif date == 'off':
        t &= {s - 3}
    return t


class GeneratedTable(SimpleTestCase):
    def test_outside_only_for_the_whitelist_and_never_wrong(self):
        bad, outs, ins = [], 0, 0
        for (pk, prefixes), (ck, cores), (sk, suf), (dk, dat), s, kind in itertools.product(
                PREFIXES.items(), CORES.items(), SUFFIXES.items(), DATES.items(), STARTS, KINDS):
            for prefix, core in itertools.product(prefixes, cores):
                text = prefix + core(s) + suf(s)
                rd = dat(s)
                r = gift_reading(text, rd, confirmation=kind == 'confirmation', stpm=kind == 'stpm')
                state = decide(r, GIFT)
                labelled = _first_year(pk, ck, kind)
                truth = _true_starts(pk, text, ck, sk, dk, s)
                # A continuing student started no later than the years the line places her in (its
                # session narrowed by a Sesi I, a month or the date).
                line_max = max(truth) if truth else 9999
                case = (text, rd, kind, state, sorted(r.years))
                if state == 'outside':
                    outs += 1
                    white = (pk in ('first', 'intake', 'plain', 'poly') and sk in ('none', 'month', 'exam')
                             and dk in ('none', 'in', 'next')
                             and (kind != 'confirmation' or pk == 'first' or ck == 'monthyear'))
                    sound = (labelled and truth and not truth & set(GIFT)) or line_max < min(GIFT)
                    if not (white and sound):
                        bad.append(('OUTSIDE', case))
                elif state == 'inside':
                    ins += 1
                    if not (labelled and truth and truth <= set(GIFT) and sk not in ('twosess',)
                            and (sk != 'extra' or dk == 'in')):
                        bad.append(('INSIDE', case))
        self.assertEqual(bad[:25], [], f'{len(bad)} bad of the table')
        # The table is not vacuous: both sure states occur.
        self.assertGreater(outs, 200)
        self.assertGreater(ins, 200)


class TheReviewProbes(SimpleTestCase):
    """h3r4's probe tables, every case."""

    CONTINUING = (
        ('Tahun Pengajian 2, Sesi 2025/2026', ''), ('Tahun Pengajian: 3 Sesi 2025/2026', ''),
        ('Year of Study 2, Session 2025/2026', ''), ('Year of study: 3, 2025/2026', ''),
        ('Semester ke-3 Sesi 2025/2026', ''), ('Semester Ke-5, Sesi 2025/2026', ''),
        ('Tahun ke-2 Sesi 2025/2026', ''), ('Tahun Ke-2 2025/2026', '8 September 2025'),
        ('Semester ke 3 2025/2026', ''), ('2nd-year, Session 2025/2026', ''), ('3rd-Year 2025/2026', ''),
        ('Year-3 2025/2026', ''), ('Y2S1 2025/2026', ''), ('Y3 S1 Session 2025/2026', ''),
        ('Part 4, Sesi 2025/2026', ''), ('Bahagian 3 Sesi 2025/2026', ''), ('Tahap 2 Sesi 2025/2026', ''),
        ('Level 2, 2025/2026', ''), ('Semester Pengajian 5 Sesi 2025/2026', ''), ('Sem: V 2025/2026', ''),
        ('Semester-III 2025/2026', ''), ('Penggal Ketiga 2025/2026', ''), ('Third Semester 2025/2026', ''),
        ('Sixth Semester, 2025/2026', ''), ('Semester Enam 2025/2026', ''), ('Semester Tujuh 2025/2026', ''),
        ('Fourth year 2025', ''), ('Tahun Akhir 2025', ''), ('Final-year 2025/2026', ''),
        ('Senior year 2025/2026', ''), ('Sem 1, Year 2, 2025/2026', ''),
        ('Semester 1 Tahun 2 Sesi 2025/2026', ''), ('Semester 1 Tahun II', '8 September 2025'),
        ('Semester1 Tahun2', '8/9/2025'), ('SEM 3', '15 September 2025'), ('Semester 3', ''),
        ('Sesi 2025/2026', ''), ('Sesi Akademik 2025/2026', '8 September 2025'), ('2025/2026', ''),
        ('Semester 2', '1 Mac 2025'), ('Semester II', '1 Mac 2025'), ('Semester 2 2025', ''),
        ('Kemasukan Semester 4 Sesi 2025/2026', ''), ('Semester Empat', '10 Mac 2025'),
        ('Sesi 2024/2025 Semester 2', ''), ('Semester 2 Sesi 2025/2026', ''),
        ('Lanjutan pengajian Sesi 2025/2026', ''), ('Pelajar Lama Sesi 2025/2026', ''),
        ('Continuing Sesi 2025/2026', ''), ('Tahun 2 (Sesi 2025/2026)', ''), ('Tahun II', ''),
        ('Tahun dua', ''), ('Year 4 Sem 2 2025', ''), ('Semester 10', ''), ('Semester 11 2025', ''),
        ('Semester 12 2025', ''), ('Semester Kesebelas 2025', ''), ('semester sepuluh 2025', ''),
        ('Ambilan 2023, Semester 1 Sesi 2025/2026', ''), ('Intake Sept 2023 - Session 2025/2026', ''),
    )
    FRESH = (
        ('Ambilan Julai 2025 (SPM 2024)', '14 Julai 2025'), ('Keputusan SPM 2024; Ambilan 2025', ''),
        ('Sesi 2025/2026 Semester I', ''), ('SESI I : 2025/2026', ''), ('SESI 1-2025/2026', ''),
        ('SESI 2-2025/2026', ''), ('Semester 1 Sesi 2024/2025', '3 Mac 2025'),
        ('Ambilan Februari 2025 Sesi 2024/2025', ''), ('Sesi 2024/2025', '3 Mac 2025'),
        ('Intake March 2025 (Session 2024/2025)', ''), ('Session 2024/25 Feb 2025', ''),
        ('Sesi 2024/25 Februari 2025', ''), ('SESI 2024/25 MAC 2025', '3 Mac 2025'),
        ('SPM 2024, Ambilan 2025', '14 Julai 2025'), ('Semester II Sesi 2024/2025', ''),
        ('Semester II 2024/2025', '17 Februari 2025'), ('Sesi II 2024/2025', '6 Januari 2025'),
        ('Ambilan Disember 2024/2025', '2 Januari 2025'), ('Sesi 2024/2025 Ambilan Januari 2025', ''),
        ('Semester 1 2025/2026', '28 Ogos 2025'), ('Semester 1 Sesi 2025/2026', '28 September 2025'),
        ('Sesi 2025/2026', '30 Jun 2025'), ('SEMESTER 1 TAHUN 2025', ''),
        ('Kemasukan 2025 (2024 lulus SPM)', ''), ('Sesi Julai 2025 hingga Jun 2029', ''),
        ('2024/2025 Semester 2 (Feb 2025 intake)', ''), ('Sesi 2025/2026 (Tarikh: 26/02/2025)', ''),
        ('Ambilan Sesi Februari 2025/2026', ''), ('Intake 2025/26 September', ''),
        ('2025/2026 Sem 1 Okt 2025', ''), ('Sesi 2024/2025: Sem 2; Mac 2025', ''),
    )

    def test_a_continuing_student_is_never_passed(self):
        for intake, rd in self.CONTINUING:
            for kind in ({}, {'confirmation': True}, {'stpm': True}):
                with self.subTest(intake=intake, rd=rd, kind=kind):
                    self.assertNotEqual(decide(gift_reading(intake, rd, **kind), GIFT), 'inside')

    def test_a_2025_or_2026_starter_is_never_failed(self):
        for intake, rd in self.FRESH:
            for kind in ({}, {'confirmation': True}, {'stpm': True}):
                with self.subTest(intake=intake, rd=rd, kind=kind):
                    self.assertNotEqual(decide(gift_reading(intake, rd, **kind), GIFT), 'outside')
