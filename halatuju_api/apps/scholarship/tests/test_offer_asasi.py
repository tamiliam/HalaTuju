"""Asasi goes to the AI (owner, 20 Nov: "For now, let AI handle Asasi. When there a larger sample, we can consider
switching."): a letter whose VISIBLE page-1 text says ASASI never locks in a university rules lane (guard
``asasi_ai_read``). Made-up text only."""
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship.offer_exact import exact_read
from apps.scholarship.offer_owner_words import MAX_NORM_CHARS, ai_only
from apps.scholarship.offer_parse import diagnose
from apps.scholarship.tests.test_offer_parse_university import NAME, ums

AI_ONLY = 'apps.scholarship.offer_owner_words.ai_only'
#: `read_ums` reads only a degree or diploma programme, so the made-up letter's programme starts "Diploma".
ASASI_PROG = 'Diploma Asasi Sains Komputer'


def _digital(layout, text=None):
    """`diagnose` as a digital PDF: the layer is ``text`` (default the layout), page 1's plain layer the layout."""
    return diagnose(text or layout, page1_text=layout, page1_layout=layout, page_texts=[layout])


def _asasi_letter():
    return ums(prog_line=ASASI_PROG, said=ASASI_PROG)


class TestTheWord(SimpleTestCase):
    def test_asasi_as_a_whole_word_in_any_case_or_spacing(self):
        for text in ('Program : Asasi Sains', 'PROGRAM ASASI', 'program\nasasi\nsains', 'Pra-Asasi', '(ASASI)',
                     'A S A S I', 'a  s a\ns i', 'Program:ASASI.', 'ÁSASI'):
            with self.subTest(text):
                self.assertEqual(ai_only(text), 'asasi_ai_read')

    def test_other_words_do_not_count(self):
        for text in ('', 'Program Ijazah Sarjana Muda', 'ASAS', 'ASASINYA', 'BASASI', 'ASASI2', 'KASA SI',
                     'AS ASIA'):
            with self.subTest(text):
                self.assertEqual(ai_only(text), '')

    def test_text_too_long_to_fold_fails_closed(self):
        self.assertEqual(ai_only('B' * (MAX_NORM_CHARS + 1)), 'asasi_ai_read')


class TestNoUniversityLock(SimpleTestCase):
    def test_the_same_letter_locks_without_the_word(self):
        """Control: the made-up Asasi letter is otherwise a lock, so the word alone is what refuses."""
        with mock.patch(AI_ONLY, return_value=''):
            self.assertEqual(_digital(_asasi_letter())['locked']['candidate_name'], NAME)
            self.assertIsNotNone(diagnose(_asasi_letter())['locked'])
        self.assertIsNotNone(_digital(ums())['locked'])

    def test_an_asasi_letter_refuses_digital_and_scanned(self):
        for name, d in (('digital', _digital(_asasi_letter())), ('scan', diagnose(_asasi_letter()))):
            with self.subTest(name):
                self.assertEqual((d['guard'], d['locked']), ('asasi_ai_read', None))

    def test_asasi_anywhere_on_the_visible_page_refuses(self):
        """Not only in the programme: a line of boilerplate saying Asasi refuses too."""
        letter = ums().replace('Saudara/i akan', 'Calon program asasi tidak layak.\nSaudara/i akan')
        self.assertEqual(_digital(letter)['guard'], 'asasi_ai_read')

    def test_the_visible_page_judges(self):
        """The word only in the plain layer (not drawn on page 1's layout) does not refuse; drawn, it does."""
        self.assertIsNotNone(_digital(ums(), text=ums() + 'ASASI\n')['locked'])
        self.assertEqual(_digital(_asasi_letter(), text=ums())['guard'], 'asasi_ai_read')

    def test_a_letter_already_refused_keeps_its_guard(self):
        cut = _asasi_letter().replace('Sekiranya saudara/saudari menerima tawaran ini', 'Jika saudara bersetuju')
        d = _digital(cut)
        self.assertEqual((d['guard'], d['owner_words_missing'], d['locked']), ('owner_words_missing', [9], None))

    def test_the_why_names_the_reason(self):
        why = {}
        self.assertIsNone(exact_read(_asasi_letter(), why=why))
        self.assertEqual(why, {'lane': 'ua:UMS', 'reason': 'read_asasi_ai_read'})

    def test_a_letter_with_no_university_lane_is_not_checked(self):
        with mock.patch(AI_ONLY, wraps=ai_only) as check:
            d = diagnose('SURAT BIASA\nProgram Asasi\n')
        self.assertEqual((check.call_count, d['family'], d['guard']), (0, '', None))
