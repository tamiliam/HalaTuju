"""S1c owner words, part 1 (2026-11-20): the owner's phrase list (`offer_owner_words`), the split refusal module
(`offer_ums_refusal`) with round 3 blocker 1 and MED 5, MED 3's later-page check, and blocker 2 (the reporting
date). Part 2: the owner-words lock wired into `_diagnose_ums`, with MED 4 (the visible page texts), MED 3's wiring,
the lane-off path unchanged and the confirmation letters' result the same with the lane on and off.

Synthetic twins only — invented names, ICs and places (`test_no_gitignored_corpus.py`)."""
import time
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship.genuineness.results_doc import signature_genuineness
from apps.scholarship.offer_exact import exact_offer_read, exact_read
from apps.scholarship.offer_owner_words import OPTIONAL_ON_TEXT_PDF, OWNER_WORDS, missing, page_of_each
from apps.scholarship.offer_parse import diagnose, parse_govt_offer
from apps.scholarship.offer_parse_university import read_ums
from apps.scholarship.offer_ums_refusal import _cancel_said, later_pages_refusal, letter_refusal
from apps.scholarship.tests.test_offer_parse_university import LAYOUT, NAME, NRIC, PAGE_TEXTS, PROG, READ_UMS, ums
from apps.scholarship.tests.test_offer_rulings import _confirm

LANE = 'ua:UMS'
INTAKE, CODE = 'SESI I-2031/2032', 'UH6481001'
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

    def test_punctuation_and_accents_match_as_the_genuineness_markers_do(self):
        """Owner option 1 (a): `results_doc._norm_fold_upper_alnum` on phrase and text alike."""
        for old, new in (('Tahniah, sukacita', 'Tahniah , sukacita'), ('Saudara/i', 'Saudara / i'),
                         ('saudara/saudari', 'saudara / saudari'), ('No. Kad', 'No Kad'),
                         ('Tahniah, sukacita', 'Tahniah sukacita'), ('dimaklumkan', 'dimaklumkán')):
            with self.subTest(new=new):
                self.assertEqual(missing(LANE, FULL.replace(old, new, 1)), [])

    def test_whole_words_and_spelling_are_not_loosened(self):
        for old, new, n in (('Rujukan :', 'Rujukankami :', 2), ('bahawa', 'bahwa', 5), ('Saudara/i', 'Saudarai', 11),
                            ('Tarikh Lapor Diri', 'Tarikh Lapor-Diri2', 10)):
            with self.subTest(new=new):
                self.assertIn(n, missing(LANE, FULL.replace(old, new, 1)))

    def test_phrase_one_is_optional_on_a_text_pdf_only(self):
        """Owner option 1 (b): the UMS letterhead picture carries phrase 1; a scan still needs all 11."""
        self.assertEqual(OPTIONAL_ON_TEXT_PDF[LANE], (1,))
        no_head = FULL.replace('BAHAGIAN PERKHIDMATAN AKADEMIK', '')
        self.assertEqual(missing(LANE, no_head), [1])
        self.assertEqual(missing(LANE, no_head, text_pdf=True), [])
        for n, phrase in enumerate(OWNER_WORDS[LANE][1:], start=2):
            with self.subTest(n=n):
                cut = no_head.replace(phrase, 'X' * len(phrase), 1)
                if n == 7:
                    cut = no_head.replace('Program :', 'Bidang :', 1)
                self.assertIn(n, missing(LANE, cut, text_pdf=True))

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

    def test_text_that_unpacks_long_is_capped_and_fast(self):
        """Review round 1 LOW 5: the cap counts AFTER unpacking (one U+FDFA unpacks to 18 characters)."""
        for n in (12_000, 200_000):
            with self.subTest(n=n):
                start = time.perf_counter()
                self.assertEqual(missing(LANE, FULL + '\uFDFA' * n), list(range(1, 12)))
                self.assertLess(time.perf_counter() - start, 2.0)
        self.assertEqual(missing(LANE, FULL + '\uFDFA' * 100), [])      # short: still read

    def test_a_letter_of_any_script_is_part_of_the_word(self):
        """Review round 1 LOW 6: Cyrillic, Greek and other letters or digits glued on are not a word edge."""
        for old, new, n in (('Rujukan :', 'Rujukan\u0416 :', 2), ('Program :', 'Program\u0391 :', 7),
                            ('Rujukan :', '\u0663Rujukan :', 2), ('BAHAGIAN', '\u0416BAHAGIAN', 1)):
            with self.subTest(new=new):
                self.assertIn(n, missing(LANE, FULL.replace(old, new, 1)))


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
        """Round 3 MED 5: 200,000 characters of conditional phrases and cancel words finish in under 5 s."""
        hostile = ('akan terbatal sekiranya ' * 9_000)[:200_000]
        start = time.perf_counter()
        _cancel_said(hostile)
        letter_refusal(hostile)
        self.assertLess(time.perf_counter() - start, 5.0)         # owner words review round 1: 5 s, not 2 s


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
        self.assertEqual(later_pages_refusal(['Program yang ditawarkan tertakluk kepada syarat.'], NRIC, '28 Sep 2031'),
                         '')                                      # a bare "ditawarkan": every genuine page 2

    def test_a_second_offer_refuses(self):
        for page2 in ('TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH',
                      'untuk mendapat Diploma Sains Marin dan sebanyak 90 jam kredit',
                      'No. Kad Pengenalan : 020304-15-6789',
                      'Tarikh Lapor Diri :\n5 Oktober 2031'):
            with self.subTest(page2=page2):
                self.assertEqual(later_pages_refusal([page2], NRIC, '28 Sep 2031'), 'second_offer')

    def test_the_templates_conditions_page_passes(self):
        """Every genuine two-page UMS letter's page 2 is headed "SYARAT-SYARAT TAWARAN KEMASUKAN SESI ..."."""
        for head in ('SYARAT-SYARAT TAWARAN KEMASUKAN SESI 2031/2032.', 'SYARAT-SYARAT TAWARAN KEMASUKAN SESI I-2031/2032',
                     'B.P PENDAFTARSYARAT - SYARAT TAWARAN KEMASUKAN\nSESI 2031/2032'):
            with self.subTest(head=head):
                self.assertEqual(later_pages_refusal([head + '\nTawaran ini tertakluk'], NRIC, '28 Sep 2031', INTAKE), '')

    def test_the_heading_is_skipped_only_with_page_1s_session(self):
        """Review round 1 MED 1: another session, another series, no session, or no page-1 intake refuses."""
        for head, intake in (('SYARAT-SYARAT TAWARAN KEMASUKAN SESI 2032/2033', INTAKE),
                             ('SYARAT-SYARAT TAWARAN KEMASUKAN SESI II-2031/2032', INTAKE),
                             ('SYARAT-SYARAT TAWARAN KEMASUKAN', INTAKE),
                             ('B.P PENDAFTARSYARAT - SYARAT TAWARAN KEMASUKAN', INTAKE),
                             ('SYARAT-SYARAT TAWARAN KEMASUKAN SESI 2031/2032', '')):
            with self.subTest(head=head, intake=intake):
                self.assertEqual(later_pages_refusal([head], NRIC, '28 Sep 2031', intake), 'second_offer')

    def test_another_programme_on_a_later_page_refuses(self):
        """Review round 1 MED 1: a programme code or a "Program :" / "Kod Program :" value other than page 1's."""
        args = (NRIC, '28 Sep 2031', INTAKE, CODE, PROG)
        for page2 in ('Kod Program : UH6481002', 'Kod  Program\n:  UH 648 1002', 'Rujuk UH6481002 untuk butiran',
                      'Program : Diploma Sains Marin', 'PROGRAM: Diploma Sains Marin'):
            with self.subTest(page2=page2):
                self.assertEqual(later_pages_refusal([page2], *args), 'second_offer')
        for page2 in ('Kod Program : UH6481001', 'Program : ' + PROG, 'Rujuk UH6481001 untuk butiran'):
            with self.subTest(page2=page2):
                self.assertEqual(later_pages_refusal([page2], *args), '')

    def test_any_spacing_of_the_offer_words_refuses(self):
        """Review round 1 MED 2: glued, spread, split over lines or letter-spaced; and "telah ditawarkan tempat"."""
        for page2 in ('TAWARANKEMASUKAN KE UNIVERSITI MALAYSIA SABAH', 'TAWARAN \t   KEMASUKAN', 'TAWARAN\nKEMASUKAN',
                      'T A W A R A N  K E M A S U K A N', 'T-A-W-A-R-A-N KEMASUKAN', 'untukmendapat Diploma Sains Marin',
                      'untuk    mengikuti Diploma Sains Marin', 'untuk\nmengikuti', 'u n t u k m e n d a p a t',
                      'saudara telah ditawarkan tempat', 'telah\nditawarkan   tempat'):
            with self.subTest(page2=page2):
                self.assertEqual(later_pages_refusal([page2], NRIC, '28 Sep 2031', INTAKE), 'second_offer')

    def test_another_reporting_date_however_printed_refuses(self):
        """Review round 1 MED 2: "5hb Oktober 2031", a label split over lines or spaced; page 1's date passes."""
        for page2 in ('Tarikh Lapor Diri : 5hb Oktober 2031', 'Tarikh Lapor Diri : 5 hb. Oktober 2031',
                      'Tarikh\nLapor\nDiri :\n5 Oktober 2031', 'Tarikh  Lapor   Diri\n\n5 Oktober 2031',
                      'T a r i k h  L a p o r  D i r i : 5 Oktober 2031', 'TarikhLaporDiri: 5 Oktober 2031'):
            with self.subTest(page2=page2):
                self.assertEqual(later_pages_refusal([page2], NRIC, '28 Sep 2031', INTAKE), 'second_offer')
        for page2 in ('Tarikh Lapor Diri : 28hb September 2031', 'Tarikh\nLapor Diri :\n28 September 2031'):
            with self.subTest(page2=page2):
                self.assertEqual(later_pages_refusal([page2], NRIC, '28 Sep 2031', INTAKE), '')

    def test_a_page_of_no_letters_refuses(self):
        self.assertEqual(later_pages_refusal(['- . -'], NRIC, '28 Sep 2031', INTAKE), 'second_offer')

    def test_the_conditions_page_still_refuses_a_second_offer_on_it(self):
        head = 'SYARAT-SYARAT TAWARAN KEMASUKAN SESI 2031/2032.\n'
        for rest in ('TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH', 'No. Kad Pengenalan : 020304-15-6789',
                     'untuk mendapat Diploma Sains Marin dan sebanyak 90 jam kredit'):
            with self.subTest(rest=rest):
                self.assertEqual(later_pages_refusal([head + rest], NRIC, '28 Sep 2031'), 'second_offer')


def _digital(layout, page_texts, text=None):
    """`diagnose` as a digital PDF: the layer is ``text`` (default the layout), page 1's plain layer the layout."""
    return diagnose(text or layout, page1_text=layout, page1_layout=layout, page_texts=page_texts)


class TestOwnerWordsLock(SimpleTestCase):
    """Part 2: a UMS letter locks by rules only when its drawn (render-mode visible) page-1 text shows all 11
    phrases (owner, 20 Nov; page 1 only since review round 1)."""

    def test_the_template_locks_digital_and_scanned(self):
        self.assertEqual(_digital(ums(), [ums()])['locked']['candidate_name'], NAME)
        self.assertEqual(parse_govt_offer(ums())['candidate_name'], NAME)

    def test_a_missing_phrase_refuses_with_its_number_only(self):
        cut = ums().replace('Sekiranya saudara/saudari menerima tawaran ini', 'Jika saudara bersetuju')
        for name, d in (('digital', _digital(cut, [cut])), ('scan', diagnose(cut))):
            with self.subTest(name):
                self.assertEqual((d['guard'], d['owner_words_missing'], d['locked']),
                                 ('owner_words_missing', [9], None))

    def test_spaces_around_punctuation_lock(self):
        """Owner option 1 (a): the digital layout's "Tahniah , sukacita" / "Saudara / i" now match."""
        spaced = ums().replace('Tahniah, sukacita', 'Tahniah , sukacita').replace('Saudara/i', 'Saudara / i')
        self.assertIsNotNone(_digital(spaced, [spaced])['locked'])
        self.assertIsNotNone(parse_govt_offer(spaced))

    def test_phrase_one_missing_locks_a_text_pdf_and_refuses_a_scan(self):
        """Owner option 1 (b), wired: the PDF's letterhead picture; a scan without it refuses."""
        no_head = ums().replace('BAHAGIAN PERKHIDMATAN AKADEMIK\n', '')
        self.assertEqual(_digital(no_head, [no_head])['locked']['candidate_name'], NAME)
        d = diagnose(no_head)
        self.assertEqual((d['guard'], d['owner_words_missing']), ('owner_words_missing', [1]))
        cut = no_head.replace('telah ditawarkan tempat', 'ditawarkan')
        self.assertEqual(_digital(cut, [cut])['owner_words_missing'], [6])

    def test_a_phrase_only_in_the_hidden_layer_does_not_count(self):
        """S-visible: the page-1 layout and the visible pages judge, not the plain layer."""
        cut = ums().replace('Sekiranya saudara/saudari menerima tawaran ini', 'Jika saudara bersetuju')
        self.assertEqual(_digital(cut, [cut], text=ums())['owner_words_missing'], [9])

    def test_a_phrase_only_on_a_later_page_refuses(self):
        """Review round 1 LOW 4: every owner phrase must be on page 1 (all 33 locking genuine letters have them)."""
        line = 'Saudara/i akan mengikuti program pengajian selama empat tahun.\n'
        cut = ums().replace(line, '')
        d = _digital(cut, [cut, line], text=cut + line)
        self.assertEqual((d['guard'], d['owner_words_missing'], d['locked']), ('owner_words_missing', [11], None))

    def test_the_why_names_the_missing_numbers(self):
        why = {}
        cut = ums().replace('Sekiranya saudara/saudari menerima tawaran ini', 'Jika saudara bersetuju')
        self.assertIsNone(exact_read(cut, why=why))
        self.assertEqual(why, {'lane': LANE, 'reason': 'read_owner_words_missing', 'owner_words_missing': [9]})

    def test_no_owner_words_walk_once_read_ums_refused(self):
        """Review round 1 LOW 5: a letter `read_ums` refuses is not walked for the owner's phrases."""
        cut = ums().replace('Tarikh Lapor Diri', 'Tarikh Daftar')
        with mock.patch('apps.scholarship.offer_owner_words.missing', wraps=missing) as walk:
            d = _digital(cut, [cut])
        self.assertEqual((walk.call_count, d['empty_required'], d['locked']), (0, ['reporting_date'], None))
        self.assertNotIn('owner_words_missing', d)


class TestVisiblePages(SimpleTestCase):
    """Round 3 MED 4: a digital PDF needs its drawn page texts, its first 3 pages must all show text, and
    (review round 1) it has at most 3 pages."""

    def test_no_page_texts_refuses(self):
        for pages in (None, []):
            with self.subTest(pages=pages):
                self.assertEqual(_digital(ums(), pages)['guard'], 'no_page_texts')

    def test_an_empty_page_among_the_first_three_refuses(self):
        for pages in ([''], [ums(), ''], [ums(), 'Lampiran', '  ']):
            with self.subTest(n=len(pages)):
                self.assertEqual(_digital(ums(), pages)['guard'], 'hidden_page')

    def test_more_than_three_pages_refuses(self):
        """Review round 1 LOW 3: no page the checks do not read can carry a second offer."""
        for pages in ([ums(), 'Lampiran A', 'Lampiran B', ''], [ums(), 'Lampiran A', 'Lampiran B', 'Lampiran C']):
            with self.subTest(last=pages[-1]):
                self.assertEqual(_digital(ums(), pages)['guard'], 'too_many_pages')
        self.assertIsNotNone(_digital(ums(), [ums(), 'Lampiran A', 'Lampiran B'])['locked'])

    def test_a_second_offer_on_a_later_page_in_any_spacing_refuses(self):
        for page2 in ('TAWARANKEMASUKAN KE UNIVERSITI MALAYSIA SABAH', 'Kod Program :      UH6481002',
                      'SYARAT-SYARAT TAWARAN KEMASUKAN SESI 2032/2033'):
            with self.subTest(page2=page2):
                self.assertEqual(_digital(ums(), [ums(), page2], text=ums() + page2)['guard'], 'second_offer')
        page2 = 'SYARAT-SYARAT TAWARAN KEMASUKAN SESI 2031/2032\nTarikh Lapor Diri : 28 September 2031'
        self.assertIsNotNone(_digital(ums(), [ums(), page2], text=ums() + page2)['locked'])


class TestSecondOfferWired(SimpleTestCase):
    """Round 3 MED 3, wired: a later page showing another IC refuses; the letter's own IC does not."""

    def test_a_second_offer_on_page_two_refuses(self):
        page2 = 'No. Kad Pengenalan :      020304-15-6789'
        self.assertEqual(_digital(ums(), [ums(), page2], text=ums() + page2)['guard'], 'second_offer')

    def test_the_letters_own_ic_on_page_two_still_locks(self):
        page2 = f'Syarat-syarat tawaran\nNo. KP : {NRIC}'
        self.assertIsNotNone(_digital(ums(), [ums(), page2], text=ums() + page2)['locked'])


class TestTheLaneSwitch(SimpleTestCase):
    """Lane off: exactly as before (no layout child, no page texts, no `read_ums`). Lane on: page texts read."""

    def _read(self, text):
        why = {}
        with mock.patch('apps.scholarship.offer_exact.pdf_layers', return_value=(text, text)), \
                mock.patch(LAYOUT, return_value=text) as layout, \
                mock.patch(PAGE_TEXTS, return_value=[text]) as pages, mock.patch(READ_UMS, wraps=read_ums) as rules:
            ex = exact_offer_read(text, image=b'%PDF-1.4 x', content_type='application/pdf', why=why)
        return ex, why, (layout.call_count, pages.call_count, rules.call_count)

    @override_settings(OCR_FIRST_LANES=())
    def test_lane_off_reads_no_page_texts(self):
        self.assertEqual(self._read(ums()), (None, {'lane': LANE, 'reason': 'lane_off'}, (0, 0, 0)))

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_lane_on_reads_the_page_texts_once(self):
        self.assertEqual(self._read(ums())[2], (1, 1, 1))


class TestConfirmationsUnchanged(SimpleTestCase):
    """A UMS confirmation letter: the same Exact read (none) and the same genuineness with the lane on and off."""

    def _both(self, text):
        out = []
        for lanes in ((), (LANE,)):
            with override_settings(OCR_FIRST_LANES=lanes), \
                    mock.patch('apps.scholarship.offer_exact.pdf_layers', return_value=(text, text)), \
                    mock.patch(LAYOUT, return_value=text), mock.patch(PAGE_TEXTS, return_value=[text]):
                ex = exact_offer_read(text, image=b'%PDF-1.4 x', content_type='application/pdf', why={})
                g = signature_genuineness(text, doc_type='offer_letter', has_crest=False) or {}
            out.append((ex, g.get('doc_seen') or g.get('type'), g.get('status')))
        return out

    def test_a_ums_confirmation_reads_the_same_with_the_lane_on_and_off(self):
        head = 'UNIVERSITI MALAYSIA SABAH\nBahagian Perkhidmatan Akademik'
        for text in (_confirm(head), _confirm(head) + 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH\n'):
            with self.subTest(title='TAWARAN' in text):
                off, on = self._both(text)
                self.assertEqual(off, on)
                self.assertIsNone(on[0])
                self.assertTrue(on[1])
