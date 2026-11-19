"""S1c owner words, part 1 (2026-11-20): the owner's phrase list (`offer_owner_words`), the split refusal module
(`offer_ums_refusal`) with round 3 blocker 1 and MED 5, MED 3's later-page check, and blocker 2 (the reporting
date). The owner-words lock itself is wired into `_diagnose_ums` in part 2.

Synthetic twins only — invented names, ICs and places (`test_no_gitignored_corpus.py`)."""
import time

from django.test import SimpleTestCase

from apps.scholarship.offer_owner_words import OWNER_WORDS, missing, page_of_each
from apps.scholarship.offer_parse_university import read_ums
from apps.scholarship.offer_ums_refusal import _cancel_said, later_pages_refusal, letter_refusal
from apps.scholarship.tests.test_offer_parse_university import NRIC, ums

LANE = 'ua:UMS'
#: A synthetic UMS letter's visible text carrying all 11 owner phrases.
FULL = """BAHAGIAN PERKHIDMATAN AKADEMIK
Rujukan :      UMS/PPA/100-1/2/3
No. Kad Pengenalan :      010203-14-5678
TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH SESI I-2031/2032
Tahniah, sukacita dimaklumkan bahawa ZORBEX A/L QUENTARO telah ditawarkan tempat
Program :      Ijazah Sarjana Muda Sains Komputer Dengan Kepujian
Kod Program :      UH6481001
Sekiranya saudara/saudari menerima tawaran ini, sila lapor diri.
Tarikh Lapor Diri :      28 September 2031
Saudara/i akan mengikuti program pengajian selama empat tahun.
"""


class TestOwnerWords(SimpleTestCase):
    def test_all_eleven_shown(self):
        self.assertEqual(len(OWNER_WORDS[LANE]), 11)
        self.assertEqual(missing(LANE, FULL), [])

    def test_each_missing_phrase_is_reported_by_number(self):
        for n, phrase in enumerate(OWNER_WORDS[LANE], start=1):
            with self.subTest(n=n):
                cut = FULL.replace(phrase, 'X' * len(phrase), 1)
                if n == 7:                                  # "Program" alone: remove its label only
                    cut = FULL.replace('Program :', 'Bidang :', 1)
                self.assertIn(n, missing(LANE, cut))

    def test_case_spacing_and_line_breaks_are_tolerated(self):
        loose = FULL.replace('Tahniah, sukacita dimaklumkan', 'TAHNIAH,\n   sukacita    dimaklumkan')
        loose = loose.replace('No. Kad Pengenalan', 'no.  kad\npengenalan')
        self.assertEqual(missing(LANE, loose), [])

    def test_nothing_else_is_loosened(self):
        for old, new, n in (('Tahniah, sukacita', 'Tahniah , sukacita', 5), ('Saudara/i', 'Saudara / i', 11),
                            ('No. Kad', 'No Kad', 3), ('Rujukan :', 'Rujukankami :', 2)):
            with self.subTest(new=new):
                self.assertIn(n, missing(LANE, FULL.replace(old, new, 1)))

    def test_program_inside_another_word_or_phrase_does_not_count(self):
        no_label = FULL.replace('Program :', 'Programme :', 1)
        self.assertEqual(missing(LANE, no_label), [7])     # "Kod Program", "program pengajian" do not count

    def test_page_of_each(self):
        pages = page_of_each(LANE, [FULL, ''])
        self.assertEqual(set(pages.values()), {1})
        self.assertEqual(page_of_each(LANE, ['', 'Tarikh Lapor Diri'])[10], 2)

    def test_hostile_text_is_fast(self):
        hostile = ('Program ' + ' ' * 150 + 'Kod ') * 12_000
        start = time.perf_counter()
        missing(LANE, hostile[:200_000])
        self.assertLess(time.perf_counter() - start, 2.0)


class TestConditionalTerbatal(SimpleTestCase):
    """Round 3 blocker 1: the conditional phrases are excused only with a condition word in the same sentence."""

    def test_genuine_conditional_wordings_are_excused(self):
        for said in ('Tawaran ini akan terbatal sekiranya saudara tidak mendaftar.',
                     'Sekiranya saudara gagal mendaftar, tawaran ini akan terbatal.',
                     'Jika saudara tidak hadir, tawaran ini terbatal dengan sendirinya.',
                     'Tawaran ini terbatal dengan\nsendirinya apabila saudara gagal mendaftar.'):
            with self.subTest(said=said):
                self.assertFalse(_cancel_said(said))

    def test_said_of_the_letter_refuses(self):
        for said in ('Tawaran ini akan terbatal.', 'Tawaran ini terbatal dengan sendirinya.',
                     'Tawaran ini telah terbatal dengan sendirinya sekiranya saudara bertanya.',
                     'Status : akan terbatal sekiranya perlu.', 'Status :\nakan terbatal sekiranya perlu.',
                     'Sekiranya perlu, Status akan terbatal.', 'Sekiranya perlu: akan terbatal.',
                     'Tawaran ini akan terbatal. Sekiranya saudara bertanya, hubungi kami.'):
            with self.subTest(said=said):
                self.assertTrue(_cancel_said(said))

    def test_a_genuine_letter_with_the_condition_still_reads(self):
        text = ums() + 'Tawaran ini akan terbatal sekiranya saudara tidak mendaftar.\n'
        self.assertEqual(read_ums(text)[1], '')
        self.assertEqual(letter_refusal(ums() + 'Tawaran ini telah terbatal dengan sendirinya.\n'), 'not_an_offer')

    def test_hostile_text_is_fast(self):
        """Round 3 MED 5: 200,000 characters of conditional phrases and cancel words finish in under 2 s."""
        hostile = ('akan terbatal sekiranya ' * 9_000)[:200_000]
        start = time.perf_counter()
        _cancel_said(hostile)
        letter_refusal(hostile)
        self.assertLess(time.perf_counter() - start, 2.0)


class TestReportingDateLabelValue(SimpleTestCase):
    """Round 3 blocker 2: a non-date value on the label's own line gives no date; TBD / ditentukan too."""

    def test_a_non_date_value_on_the_label_line_gives_no_date(self):
        for report in ('TBD\n28 September 2031', 'Akan ditentukan', 'Rujuk lampiran\n28 September 2031'):
            with self.subTest(report=report):
                f, reason = read_ums(ums(report=report))
                self.assertEqual(f['reporting_date'], '')
                self.assertIn('reporting_date', reason)

    def test_a_date_on_the_label_line_or_below_still_reads(self):
        for report in ('28 September 2031', ':\n28 September 2031'):
            with self.subTest(report=report):
                self.assertEqual(read_ums(ums(report=report))[0]['reporting_date'], '28 Sep 2031')


class TestLaterPages(SimpleTestCase):
    """Round 3 MED 3 (`later_pages_refusal`; wired in part 2): a later page that shows a second offer refuses."""

    def test_a_clean_later_page_passes(self):
        page2 = 'Syarat-syarat tawaran\nTarikh Lapor Diri : 28 September 2031\nNo. KP : ' + NRIC
        self.assertEqual(later_pages_refusal([page2, ''], NRIC, '28 Sep 2031'), '')

    def test_a_second_offer_refuses(self):
        for page2 in ('TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH',
                      'untuk mendapat Diploma Sains Marin dan sebanyak 90 jam kredit',
                      'No. Kad Pengenalan : 020304-15-6789',
                      'Tarikh Lapor Diri :\n5 Oktober 2031'):
            with self.subTest(page2=page2):
                self.assertEqual(later_pages_refusal([page2], NRIC, '28 Sep 2031'), 'second_offer')
