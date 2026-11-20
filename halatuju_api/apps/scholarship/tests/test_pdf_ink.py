"""S-visible 2 — `pdf_ink.ink_missing`, pure: hand-made child answers (one row per page-1 character)."""
from django.test import SimpleTestCase

from apps.scholarship import pdf_ink
from apps.scholarship.pdf_ink import ink_missing


def _line(text, x=30.0, y=700.0, h=7.0, w=5.4, ink=12, area=40, gap=0.0):
    """Rows for ``text`` set left to right from (x, y): every character inked unless changed after."""
    rows = []
    for c in text:
        if c == ' ':
            rows.append([32, 0, 0, 0, 0, 0, 0, 0, 1])
        else:
            rows.append([ord(c), 0, round(x, 2), y, round(x + w, 2), y + h, ink, area, 1])
        x += w + gap
    return rows


def _answer(*lines, modes=True, annots=True):
    chars = []
    for i, ln in enumerate(lines):
        if i:
            chars.append([13, 1, 0, 0, 0, 0, 0, 0, 1])           # pdfium's generated line break
        chars.extend(ln)
    return {'chars': chars, 'modes_ok': modes, 'annots_ok': annots}


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

    def test_partial_ink_is_judged_only_when_a_share_is_set(self):
        a = _answer(_line('TAWARAN KEMASUKAN', ink=1, area=40))
        self.assertEqual(ink_missing(a, PHRASE, []), [])
        from unittest.mock import patch
        with patch.object(pdf_ink, 'MIN_CHAR_SHARE', 0.05):
            self.assertEqual(ink_missing(a, PHRASE, []), ['p1'])


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

    def test_an_annotation_other_than_a_link(self):
        self.assertEqual(ink_missing(_answer(_line('TAWARAN KEMASUKAN'), annots=False), PHRASE, []),
                         ['page:annots'])

    def test_no_answer_refuses(self):
        for bad in (None, {}, {'error': 'mode'}, {'chars': 'x'}, {'chars': [[65, 0, 1]]},
                    {'chars': [[0x110000, 0, 0, 0, 0, 0, 0, 0, 1]]}):
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
