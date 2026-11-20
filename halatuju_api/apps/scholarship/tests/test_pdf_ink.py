"""S-visible 2 — `pdf_ink.ink_missing`, pure: hand-made child answers (one row per page-1 character)."""
from django.test import SimpleTestCase

from apps.scholarship import pdf_ink
from apps.scholarship.pdf_ink import ink_missing


def _line(text, x=30.0, y=700.0, h=7.0, w=5.4, ink=12, area=40, gap=0.0, cover=(0.9, 0.8)):
    """Rows for ``text`` set left to right from (x, y): every character inked unless changed after."""
    rows = []
    for c in text:
        if c == ' ':
            rows.append([32, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0])
        else:
            rows.append([ord(c), 0, round(x, 2), y, round(x + w, 2), y + h, ink, area, 1, *cover])
        x += w + gap
    return rows


def _answer(*lines, modes=True, annots=True, stray=0, optional=False, xfa=False):
    chars = []
    for i, ln in enumerate(lines):
        if i:
            chars.append([13, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0])     # pdfium's generated line break
        chars.extend(ln)
    return {'chars': chars, 'modes_ok': modes, 'annots_ok': annots, 'stray_px': stray, 'optional': optional,
            'xfa': xfa}


PHRASE = [('p1', 'tawaran kemasukan')]
NAME = [('v:name', 'ALI BIN ABU')]


class TheWordRules(SimpleTestCase):
    def test_every_character_inked_passes(self):
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN'), _line('ALI BIN ABU', y=680)),
                                     PHRASE, NAME), [])

    def test_one_character_with_no_ink_refuses_its_target_only(self):
        a = _answer(_line('TAWARAN KEMASUKAN'), _line('ALI BIN ABU', y=680))
        a['chars'][3][6] = 0                                       # the second A of TAWARAN
        self.assertEqual(ink_missing(a, PHRASE, NAME), ['p1'])

    def test_a_character_outside_the_page(self):
        a = _answer(_line('TAWARAN KEMASUKAN'))
        a['chars'][9][8] = 0
        self.assertEqual(ink_missing(a, PHRASE, []), ['p1'])

    def test_short_text(self):
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN', h=2.9, w=2.0)), PHRASE, []), ['p1'])
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN', h=3.0, w=2.0)), PHRASE, []), [])

    def test_squeezed_text(self):
        # Tz 3: seven 7 pt characters in 2.1 pt (ratio 0.04 < 0.06)
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN', w=0.3)), PHRASE, []), ['p1'])

    def test_a_word_under_other_text_borrows_nothing(self):
        cover = _line('XXXXXXXXXXXXXXXXX')                          # visible text over the same boxes
        hidden = _line('TAWARAN KEMASUKAN')
        self.assertEqual(ink_missing(_answer(cover, hidden), PHRASE, []), ['p1'])

    def test_a_small_overlap_of_a_neighbour_is_allowed(self):
        above = _line('XXXXXXXXXXXXXXXXX', y=706.0)                 # 1 pt of a 7 pt box: 14 %
        self.assertEqual(ink_missing(_answer(above, _line('TAWARAN KEMASUKAN')), PHRASE, []), [])

    def test_every_occurrence_must_pass(self):
        good, bad = _line('TAWARAN KEMASUKAN'), _line('TAWARAN KEMASUKAN', y=600)
        bad[0][6] = 0                                               # a hidden second copy
        self.assertEqual(ink_missing(_answer(good, bad), PHRASE, []), ['p1'])

    def test_a_character_carved_to_a_sliver(self):
        """Open risk 2: each character needs ink over a tenth of its box (genuine minimum 0.143)."""
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN', ink=5, area=40)), PHRASE, []), [])
        a = _answer(_line('TAWARAN KEMASUKAN'))
        a['chars'][4][6] = 3                                       # 3 of 40 pixels: 0.075
        self.assertEqual(ink_missing(a, PHRASE, []), ['p1'])

    def test_ink_in_a_thin_strip_of_the_box(self):
        """Review round 1, B2: a word covered all but a 1-2 pt strip keeps a fair share of ink but spans 0.2-0.3
        of each box's height (genuine minimum 0.545); a sliver column the same across the width."""
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN', cover=(0.5, 0.15))), PHRASE, []), [])
        for cover in ((0.3, 0.9), (0.9, 0.1)):
            with self.subTest(cover=cover):
                a = _answer(_line('TAWARAN KEMASUKAN'))
                a['chars'][2][9:11] = list(cover)
                self.assertEqual(ink_missing(a, PHRASE, []), ['p1'])

    def test_large_glyphs_over_a_word_lend_it_no_ink(self):
        """Review round 1, B1: one 60 pt square covers many target characters, yet only a sliver of its OWN box
        lies on the word: the overlap is also measured against each target character's box."""
        square = [[0x25A0, 0, 20.0, 690.0, 80.0, 750.0, 900, 900, 1, 1.0, 1.0]]
        self.assertEqual(ink_missing(_answer(square, _line('TAWARAN KEMASUKAN')), PHRASE, []), ['p1'])

    def test_many_small_glyphs_together_lend_it_no_ink(self):
        """Two tall glyphs per character, one from below and one from above: each lies mostly outside the word's
        box (the word-box rule lets it pass) and covers 25 % of the character, together 50 %."""
        tiles = []
        for k in range(17):
            x = 30.0 + 5.4 * k
            for y0 in (695.0, 705.25):
                tiles.append([0x25A0, 0, x, y0, x + 5.4, y0 + 6.75, 30, 36, 1, 1.0, 1.0])
        self.assertEqual(ink_missing(_answer(tiles, _line('TAWARAN KEMASUKAN')), PHRASE, []), ['p1'])


class FindingTheWords(SimpleTestCase):
    def test_pdfium_glues_two_words_of_a_phrase(self):
        self.assertEqual(ink_missing(_answer(_line('TAWARANKEMASUKAN')), PHRASE, []), [])

    def test_an_ic_printed_with_hyphens_or_split(self):
        nric = [('v:nric', '900101145678')]
        self.assertEqual(ink_missing(_answer(_line('NO. K/P: 900101-14-5678')), [], nric), [])
        self.assertEqual(ink_missing(_answer(_line('900101 14 5678')), [], nric), [])

    def test_word_edges_stay_strict(self):
        nric = [('v:nric', '900101145678')]
        self.assertEqual(ink_missing(_answer(_line('19001011456789')), [], nric), ['v:nric'])
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKANNYA')), PHRASE, []), ['p1'])

    def test_case_accents_and_punctuation_are_normalised(self):
        self.assertEqual(ink_missing(_answer(_line('Tawarán, kemasukan.')), PHRASE, []), [])

    def test_a_phrase_pdfium_cannot_find_refuses(self):
        self.assertEqual(ink_missing(_answer(_line('TAWARAN')), PHRASE, NAME), ['p1', 'v:name'])

    def test_too_many_occurrences_refuse(self):
        lines = [_line('ALI BIN ABU', y=800 - 10 * i) for i in range(pdf_ink.MAX_OCCURRENCES + 1)]
        self.assertEqual(ink_missing(_answer(*lines), [], NAME), ['v:name'])


class ThePageRulesAndAnswers(SimpleTestCase):
    def test_a_render_mode_past_two(self):
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN'), modes=False), PHRASE, []), ['page:modes'])

    def test_stray_ink_optional_content_and_xfa(self):
        line = _line('TAWARAN KEMASUKAN')
        self.assertEqual(ink_missing(_answer(line, stray=pdf_ink.MAX_STRAY_PX), PHRASE, []), [])
        for kw, label in (({'stray': pdf_ink.MAX_STRAY_PX + 1}, 'page:stray'), ({'stray': None}, 'page:stray'),
                          ({'stray': True}, 'page:stray'), ({'optional': True}, 'page:optional'),
                          ({'optional': None}, 'page:optional'), ({'xfa': True}, 'page:xfa'),
                          ({'xfa': None}, 'page:xfa')):
            with self.subTest(kw=kw):
                self.assertEqual(ink_missing(_answer(line, **kw), PHRASE, []), [label])

    def test_an_annotation_other_than_a_link(self):
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN'), annots=False), PHRASE, []),
                         ['page:annots'])

    def test_no_answer_refuses(self):
        for bad in (None, {}, {'error': 'mode'}, {'chars': 'x'}, {'chars': [[65, 0, 1]]},
                    {'chars': [[0x110000, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0]]},
                    {'chars': [[65, 0, 0, 0, 0, 0, 0, 0, 1]]}):         # a row without the cover columns
            with self.subTest(bad=bad):
                self.assertEqual(ink_missing(bad, PHRASE, NAME), ['no_answer'])

    def test_nothing_to_check_refuses(self):
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN')), [], []), ['no_targets'])

    def test_a_blank_target_refuses(self):
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN')), [('p2', ' - ')], []), ['p2'])

    def test_the_op_asks_the_measured_settings(self):
        op = pdf_ink.ink_op(3)
        self.assertEqual((op['op'], op['page'], op['count'], op['delta'], op['scale'][0]), ('ink', 0, 3, 96, 100))
        self.assertEqual(pdf_ink.ink_ops(b'not a pdf'), [])
        self.assertIsNone(pdf_ink.page1_ink(b''))
