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

Plus the fixed probe tables of the reviews (h3r4, h3r5): continuing students never pass, clear
2025 / 2026 starters and messy or OCR-damaged lines are never failed. And a FUZZ (fifth review): every
clean OUTSIDE line, damaged at random (letters glued to its digits, OCR digit swaps, extra words, a
second date, a messy letter date), reads unknown or exactly as the clean line, never another OUTSIDE.
"""
import itertools
import random

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
        # A first term or Sesi I no longer pins S (fifth review): her own Semester 1 may be a
        # February intake's, in S+1. Only a September-November month does.
        t = {s} if suffix == 'month' else {s, s + 1}
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
    """The adversarial reviews' probe tables (h3r4, h3r5), every case."""

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

    # The fifth review's probes (h3r5), every case: (intake line, the letter's date, the programme
    # words, the letter kind: C = confirmation, S = Form 6). Messy first-year lines and doubtful
    # starters are never failed; continuing students are never passed; OCR-damaged lines are never
    # failed.
    H3R5_RED = (
        ('Sesi 2024/2025Semester II', '', '', ''),
        ('Sesi Akademik 2024/2025Ambilan Februari', '', '', ''),
        ('Ambilan Februari', '20 Disember 2024', '', ''),
        ('', '30 Disember 2024 hingga 3 Januari 2025', '', ''),
        ('', '28/12/2024 - 05/01/2025', '', ''),
        ('', '2024/2025', '', ''),
        ('Ambilan Mac', 'Sesi 2024/2025', '', ''),
        ('Sesi 2024/2025', '30 Disember 2024 - 3 Januari 2025', '', ''),
        ('Ambilan Sesi 2024/2025', '28 Dis 2024 / 2 Jan 2025', '', ''),
        ('Ambilan Julai 2025', '', '', ''),
        ('Intake: March 2025 (Session 2024/2025)', '', '', ''),
        ('Academic Session 2024/2025, Semester 2 (February 2025 intake)', '', '', ''),
        ('Sem II 2024/2025', '', '', ''),
        ('Session 2024/2025 Sem. 2', '', '', ''),
        ('Semester Two, 2024/2025', '', '', ''),
        ('Semester Kedua Sesi 2024/2025', '', '', ''),
        ('2nd Semester 2024/2025', '', '', ''),
        ('Semester (2) 2024/2025', '', '', ''),
        ('Semester:2 Sesi 2024/2025', '', '', ''),
        ('Semester 2 / Sesi 2024/2025', '', '', ''),
        ('SEMESTER 2 SESI 2024 / 2025', '', '', ''),
        ('Semester-2 2024/2025', '', '', ''),
        ('Sem2 2024/2025', '', '', ''),
        ('Semester II/2024/2025', '', '', ''),
        ('Ambilan 2/2024/2025', '', '', ''),
        ('Ambilan Kedua 2024/2025', '', '', ''),
        ('Pengambilan Jan 2025 Sesi 2024/2025', '', '', ''),
        ('Kemasukan: 2025', '', '', ''),
        ('Kemasukan Ambilan Februari 2025, Surat bertarikh 12.12.2024', '', '', ''),
        ('Ambilan Feb 2025 (tawaran dikeluarkan Dis 2024)', '', '', ''),
        ('Tarikh lapor diri: 2/3/2025, Tarikh surat: 3/12/2024', '', '', ''),
        ('Lapor diri 03-03-2025; surat 2024-12-03', '', '', ''),
        ('Ambilan 2025/26', '', '', ''),
        ('Ambilan 2025 / 26 Februari', '', '', ''),
        ('2024-25 Session, Semester 2', '', '', ''),
        ('Session 2024–25 Semester II', '', '', ''),
        ('Session 2024-25 Feb intake', '', '', ''),
        ('Semester 2 2024/25', '', '', ''),
        ('Sesi 2 2024/2025', '', '', ''),
        ('Sesi II 2024/2025', 'Februari 2025', '', ''),
        ('Sesi II 2024/2025', '', '', ''),
        ('Sesi Disember 2024', '', '', ''),
        ('Ambilan Disember 2024', '', '', ''),
        ('Sesi 1 2024/2025', '', '', ''),
        ('Semester 1 2024/2025', 'Mac 2025', '', ''),
        ('Semester 1 2024/2025', '', '', ''),
        ('Semester I Sesi 2024/2025 (Ambilan Februari)', '', '', ''),
        ('Semester 1, Session 2024/2025 (March intake)', '', '', ''),
        ('Sem 1 2024/2025 Feb', '', '', ''),
        ('Intake 2024/2025 (II)', '', '', ''),
        ('Sesi 2024/2025 (Ambilan II)', '', '', ''),
        ('Ambilan 2024 (tangguh ke 2025)', '', '', ''),
        ('UPU 2024 Ambilan 2025', '', '', ''),
        ('Ambilan Sesi 2024/2025 Semester 2 bermula 3 Mac 2025', '', '', ''),
        ('Ambilan Julai 2024 / Januari 2025', '', '', ''),
        ('Jan 2025 Intake', '', '', ''),
        ("Intake Jan '25", '', '', ''),
        ('Intake 01/2025', '', '', ''),
        ('Intake 2025-01', '', '', ''),
        ('Intake: 2025-01-06', '', '', ''),
        ('2025-01-06', '', '', ''),
        ('06.01.2025', '', '', ''),
        ('Ambilan Sesi 2024/2025: Februari', '', '', ''),
        ('Semester Pendek 2024/2025', '', '', ''),
        ('Sesi 2024/2025 Fasa 2', '', '', ''),
        ('Sesi 2024/2025 Kumpulan 2', '', '', ''),
        ('Ambilan 2024/2025 (Gelombang 2)', '', '', ''),
        ('Ambilan Kedua Sesi 2024/2025', '', '', ''),
        ('Ambilan Mac Sesi 2024/2025', '', '', ''),
        ('Ambilan Mei 2024/2025', '', '', ''),
        ('Ambilan 2024/2025 Mei', '', '', ''),
        ('Pengambilan Sesi Jun 2025 / Sesi 2024/2025', '', '', ''),
        ('Ambilan Sesi Julai 2024/2025', '14 Julai 2025', '', ''),
        ('Sesi Ogos 2024/2025', '', '', ''),
        ('Semester 1 Sesi 2024/2025', '1 Julai 2025', '', ''),
        ('Program Asasi 2024/2025 Semester 2', '', '', ''),
        ('2024/2025Sem2', '', '', ''),
        ('Ambilan:2024/2025-II', '', '', ''),
        ('2024/2025 Semester 2', '', '', ''),
    )
    H3R5_CONT = (
        ('Sem 1 Yr 2 2025/2026', '', '', 'C'),
        ('Yr 2 Sem 1 Sesi 2025/2026', '', '', ''),
        ('Semester 1, Second Yr, 2025/2026', '', '', 'C'),
        ('Semester 1 (Sophomore) 2025/2026', '', '', 'C'),
        ('Semester 1 Level 200 Session 2025/2026', '', '', 'C'),
        ('Semester 1 Level 2 2025/2026', '', '', 'C'),
        ('Semester 1 Sesi 2025/2026', '', '', 'C'),
        ('Semester 1 Sesi 2025/2026', '', 'Ijazah Sarjana Muda Tahun 3', 'C'),
        ('Semester 1 Sesi 2025/2026', '', 'Bachelor (Year 3)', 'C'),
        ('Semester 1 Sesi 2025/2026', '', 'Tahun Kedua', 'C'),
        ('Semester 1 Sesi 2025/2026', '8 September 2025', 'Tingkatan Enam Atas', 'S'),
        ('Semester 1 Sesi 2025/2026', '', '', 'C'),
        ('Semester 1 Tahun Kedua 2025/2026', '', '', 'C'),
        ('Semester 1 Thn 2 Sesi 2025/2026', '', '', 'C'),
        ('Sem 1 Thn 3 2025/2026', '', '', 'C'),
        ('Semester 1, Year Three, 2025/2026', '', '', 'C'),
        ('Semester Satu Tahun Tiga 2025/2026', '', '', 'C'),
        ('Semester 1 (2nd Year) 2025/2026', '', '', 'C'),
        ('Semester 1 (Year 2/4) 2025/2026', '', '', 'C'),
        ('Year:2 Semester:1 2025/2026', '', '', 'C'),
        ('Year-2 Sem-1 2025/2026', '', '', 'C'),
        ('YEAR2 SEM1 2025/2026', '', '', 'C'),
        ('Tahun2 Semester1 2025/2026', '', '', 'C'),
        ('Semester 1 Tahun Pengajian Kedua 2025/2026', '', '', 'C'),
        ('Semester 1 / Tahun 2 / 2025/2026', '', '', 'C'),
        ('Semester 1 Sesi 2025/2026 (Ambilan 2023)', '', '', 'C'),
        ('Semester 1 Sesi 2025/2026 Kohort 2023', '', '', 'C'),
        ('Semester 1 Sesi 2025/2026 Batch 23', '', '', 'C'),
        ('Semester 1 Sesi 2025/2026 No Matrik A23CS0001', '', '', 'C'),
        ('Ambilan September 2025', '', '', 'C'),
        ('Ambilan Oktober 2025 Semester 5', '', '', 'C'),
        ('Semester 01 Sesi 2025/2026', '', '', 'C'),
        ('Semester 1 Tahun Akhir 2025/2026', '', '', 'C'),
        ('Final Year Semester 1 2025/2026', '', '', 'C'),
        ('Semester 1 Final Year 2025/2026', '', '', 'C'),
        ('Semester 1 Tahun Akhir', '8 Sep 2025', '', 'C'),
        ('Semester 1', '8 September 2025', '', 'C'),
        ('Semester 1', '8 September 2025', '', ''),
        ('Kemasukan 2025', '', '', 'C'),
        ('U6 2025', '', '', 'S'),
        ('Form Six Upper 2025', '', '', 'S'),
        ('Upper Form 6 2025', '', '', 'S'),
        ('Tingkatan 6 Atas Penggal 1 2025', '', '', 'S'),
        ('Penggal 1 2025', '', '', 'S'),
        ('Penggal Satu 2025', '', '', 'S'),
        ('Penggal 3 2025', '', '', 'S'),
        ('Semester 1 2025', '', '', 'S'),
        ('STPM Semester 1 2025', '', '', 'S'),
        ('Semester 1 Tahun 2 2025', '', '', ''),
        ('Senior 2025/2026 Semester 1', '', '', 'C'),
        ('Semester 1 Sarjana Muda Tahun 2 2025/2026', '', '', 'C'),
        ('1st Semester, 3rd year 2025/2026', '', '', 'C'),
        ('first semester third year 2025/2026', '', '', 'C'),
        ('Semester 1, Tahun Ketiga', '9 Mac 2026', '', 'C'),
        ('Semester Pertama Tahun Ketiga', '9 Mac 2026', '', 'C'),
        ('Semester 1', '9 Mac 2026', 'Tahun Ketiga', 'C'),
    )
    H3R5_OCR = (
        ('Ambilan Februari Sesi 2024/2O25', '', '', ''),
        ('Ambilan Sesi 2024/2O25', '', '', ''),
        ('Ambilan Sesi 2024/202S', '', '', ''),
        ('Ambilan Sesi 2024/25Feb', '', '', ''),
        ('Ambilan Sesi 2024/2025.Semester 2', '', '', ''),
        ('Ambilan Sesi 2024/2025_Feb', '', '', ''),
        ('Sesi 2024—2025 Ambilan Februari', '', '', ''),
        ('Sesi 2024‑2025 Ambilan Februari', '', '', ''),
        ('Sesi 2024−2025 Ambilan Februari', '', '', ''),
        ('Sesi 2024／2025 Ambilan Februari', '', '', ''),
        ('Sesi 2024 ⁄ 2025 Ambilan Februari', '', '', ''),
        ('Sesi 2024~2025 Ambilan II', '', '', ''),
        ('Sesi 2024 hingga 2025 Ambilan II', '', '', ''),
        ('Ambilan Sesi 2024-25 Mac', '', '', ''),
        ('Ambilan Sesi 2024-25 (Mac)', '', '', ''),
        ('Session 2024-25, Feb intake', '', '', ''),
        ('Session 2024-25 February', '', '', ''),
        ('Sesi 2024-25 Semester 2', '', '', ''),
        ('Sesi 2024 - 25 Februari', '', '', ''),
        ('Ambilan 2024-25 Jan', '', '', ''),
        ('2024/2025 ஆம் கல்வியாண்டு, இரண்டாம் பருவம்', '', '', ''),
        ('2024/2025ஆம் கல்வியாண்டு', '', '', ''),
        ('Ambilan Sesi 2024/2025 (Semester II)', '', '', ''),
        ('Ambilan Sesi 2024/2025 (Semester Dua)', '', '', ''),
        ('Ambilan Sesi 2024/2025 - Sem.II', '', '', ''),
        ('Ambilan Sesi 2024/2025 Sem.ll', '', '', ''),
        ('Ambilan Sesi 2024/2025 Semester ll', '', '', ''),
        ('Ambilan Sesi 2024/2025 Semester 11', '', '', ''),
        ('Ambilan Sesi 2024/2025 Semester I1', '', '', ''),
        ('Ambilan Sesi 2024/2025 SEMESTER Il', '', '', ''),
        ('Sesi 2024/2025 Semester Il', 'Februari 2025', '', ''),
        ('Ambilan Sesi 2024/2025 Semester ', '', '', ''),
        ('Ambilan Sesi 2024/2025 Semester 1', 'Februari 2025', '', ''),
        ('Sesi 2024/2025 Semester I', '', '', ''),
        ('Ambilan 2024/2025 Semester I', '', '', ''),
        ('Ambilan Sesi 2O24/2025', '', '', ''),
        ('Ambilan Sesi 2024/2025 Sem I (Feb)', '', '', ''),
        ('Sesi 2024/2025, Semester 1 (Jan 2025)', '', '', ''),
        ("Ambilan Sesi 2024/2025, Semester 1 (Jan '25)", '', '', ''),
    )

    @staticmethod
    def _read(intake, rd, context, flags):
        return gift_reading(intake, rd, context=context, confirmation='C' in flags, stpm='S' in flags)

    def test_the_fifth_reviews_messy_lines_are_never_failed(self):
        for intake, rd, context, flags in self.H3R5_RED + self.H3R5_OCR:
            with self.subTest(intake=intake, rd=rd, context=context, flags=flags):
                self.assertNotEqual(decide(self._read(intake, rd, context, flags), GIFT), 'outside')

    def test_the_fifth_reviews_continuing_students_are_never_passed(self):
        for intake, rd, context, flags in self.H3R5_CONT:
            with self.subTest(intake=intake, rd=rd, context=context, flags=flags):
                self.assertNotEqual(decide(self._read(intake, rd, context, flags), GIFT), 'inside')

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


def _clean_outsides():
    """Every OUTSIDE of the generated table, plus a hand list using the rest of the vocabulary."""
    out = []
    for (pk, prefixes), (ck, cores), (sk, suf), (dk, dat), s, kind in itertools.product(
            PREFIXES.items(), CORES.items(), SUFFIXES.items(), DATES.items(), STARTS, KINDS):
        for prefix, core in itertools.product(prefixes, cores):
            text, rd = prefix + core(s) + suf(s), dat(s)
            kw = {'confirmation': kind == 'confirmation', 'stpm': kind == 'stpm'}
            if decide(gift_reading(text, rd, **kw), GIFT) == 'outside':
                out.append((text, rd, kw))
    for text, rd in MutatedOutsideLines.HAND:
        out.append((text, rd, {}))
    return out


class MutatedOutsideLines(SimpleTestCase):
    HAND = (
        ('Ambilan Julai 2024', ''), ('Intake: September 2023 (Session 2023/2024)', ''),
        ('Sesi Akademik 2022/2023', ''), ('Kemasukan 2024', ''), ('First Semester, Session 2022/2023', ''),
        ('Tahun 1 Semester 1 Sesi 2023/2024', ''), ('2024', '10 Jun 2024'), ('Ambilan Jun', '8 Jun 2022'),
        ('', '8 Jun 2023'), ('Ambilan Sesi 2023/24', '11 September 2023'), ('Sesi 2024/2025 (Oktober 2024)', ''),
        ('Ambilan bagi Sesi 2022-2023', ''), ('Intake for the Academic Session 2023-24', ''),
        ('Semester Satu Sesi 2022/2023', '2022-09-20'), ('Ambilan Julai 2024', 'Isnin, 15 Julai 2024'),
    )
    JUNK = ('hingga', 'tangguh', 'Kohort', 'Batch', 'No.', 'SPM', 'UPU', 'dan', 'atau', '&', '+', '~',
            'ஆம்', 'lulus', '*', '#', 'Fasa', 'Gelombang', 'II', 'Il', 'ke-2', '1st', "'25",
            'Semester 2', 'Tahun 2', 'Yr 3', 'U6', 'continuing', '.', '_', '—', '／')
    DATES = ('3 Mac 2025', '2026', '12/1/2025', '2025/2026', 'Jan 2026', '1 Julai 2025', '2019',
             '30 Disember 2024 hingga 3 Januari 2025', '2025-26', '2024 - 25', '20 Disember 2024')
    OCR = {'0': 'O', '1': 'l', '2': 'Z', '5': 'S', '8': 'B', '6': 'G', '4': 'A'}
    LETTERS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZகé'

    @classmethod
    def _glue(cls, rng, t):
        spots = [i for i, ch in enumerate(t) if ch.isdigit()]
        if not spots:
            return t + rng.choice(cls.LETTERS)
        i = rng.choice(spots) + rng.choice((0, 1))
        return t[:i] + rng.choice(cls.LETTERS) + t[i:]

    @classmethod
    def _ocr(cls, rng, t):
        spots = [i for i, ch in enumerate(t) if ch in cls.OCR]
        if not spots:
            return t
        i = rng.choice(spots)
        return t[:i] + cls.OCR[t[i]] + t[i + 1:]

    @staticmethod
    def _insert(rng, t, word):
        cuts = [0, len(t)] + [i for i, ch in enumerate(t) if ch == ' ']
        i = rng.choice(cuts)
        return (t[:i] + ' ' + word + ' ' + t[i:]).strip()

    EXAM_WORDS = ('SPM', 'lulus')

    def _mutate(self, rng, text, rd):
        exam = dated = False
        for _ in range(rng.choice((1, 1, 2, 3))):
            kind = rng.choice(('glue', 'ocr', 'junk', 'date', 'rd'))
            # An exam word AND a second date write a different, sound letter ("Intake 2026 SPM 2022":
            # the clean year becomes the exam year), which no reader can tell from a real one; so
            # the fuzz never combines the two. Each alone is damage and must read unknown or unchanged.
            if kind == 'date' and exam:
                kind = 'glue'
            if kind == 'glue':
                text = self._glue(rng, text)
            elif kind == 'ocr':
                text = self._ocr(rng, text)
            elif kind == 'junk':
                word = rng.choice([w for w in self.JUNK if not (dated and w in self.EXAM_WORDS)])
                exam = exam or word in self.EXAM_WORDS
                text = self._insert(rng, text, word)
            elif kind == 'date':
                dated = True
                text = self._insert(rng, text, rng.choice(self.DATES))
            else:
                how = rng.choice(('glue', 'ocr', 'range', 'second'))
                rd = (self._glue(rng, rd) if how == 'glue' else self._ocr(rng, rd) if how == 'ocr'
                      else (rd + ' hingga 3 Januari 2026').strip() if how == 'range'
                      else (rd + ' / ' + rng.choice(self.DATES)).strip())
        return text, rd

    def test_a_damaged_outside_line_is_unknown_or_unchanged(self):
        clean = _clean_outsides()
        self.assertGreater(len(clean), 200)
        rng = random.Random(20261115)
        bad, changed = [], 0
        for text, rd, kw in clean:
            base = gift_reading(text, rd, **kw)
            for _ in range(12):
                mt, mrd = self._mutate(rng, text, rd)
                r = gift_reading(mt, mrd, **kw)
                state = decide(r, GIFT)
                if state == 'unknown':
                    changed += 1
                elif state != 'outside' or r.years != base.years:
                    bad.append((text, rd, kw, mt, mrd, state, sorted(r.years)))
        self.assertEqual(bad[:20], [], f'{len(bad)} damaged lines read differently')
        self.assertGreater(changed, len(clean))          # the fuzz bites: damage mostly reads unknown

    def test_the_hand_list_is_outside_when_clean(self):
        for text, rd in self.HAND:
            with self.subTest(text=text, rd=rd):
                self.assertEqual(decide(gift_reading(text, rd), GIFT), 'outside')
