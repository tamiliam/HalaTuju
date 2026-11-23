"""Asasi goes to the AI (owner, 20 Nov: "For now, let AI handle Asasi. When there a larger sample, we can consider
switching."): a letter whose page-1 text (as its rules lane reads it), or parsed programme, says ASASI (whole,
spaced, glued or OCR-misread) never locks in ANY rules lane (university or government family; guard
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
        """ASAS alone (basic), a spaced I with more letters after it ("ASAS INI"), a spaced 1 ("ASAS 1") and
        letters split differently ("KASA SI", "AS ASIA") do not say ASASI: unchanged by the fix round."""
        for text in ('', 'Program Ijazah Sarjana Muda', 'ASAS', 'Pendidikan Asas', 'ASAS INI', 'ASAS 1',
                     'KASA SI', 'AS ASIA'):
            with self.subTest(text):
                self.assertEqual(ai_only(text), '')

    def test_asas_then_a_lone_i_refuses_as_before(self):
        """The spaced form (any letter may be followed by one space) already took "ASAS I" (the I standing
        alone) and "ASA SI": kept."""
        for text in ('ASAS I', 'Program Asas\nI', 'A.S.A.S.I', 'ASA SI'):
            with self.subTest(text):
                self.assertEqual(ai_only(text), 'asasi_ai_read')


class TestGluedAndMisread(SimpleTestCase):
    """Asasi fix round (review MEDIUM): the unspaced ASASI anywhere, no word edges; OCR's 1 / L / | for the last I;
    Cyrillic / Greek look-alike capitals folded first. Refusing more costs one AI call; a wrong lock is serious."""

    def test_glued_to_other_letters_or_digits(self):
        for text in ('PROGRAMASASI', 'ASASISAINS', '178Asasi', 'ASASIpin', 'Kod:178Asasi Sains', 'xASASIx'):
            with self.subTest(text):
                self.assertEqual(ai_only(text), 'asasi_ai_read')

    def test_ocr_misreads_of_the_last_i(self):
        for text in ('ASAS1', 'ASASl', 'ASAS|', 'Program ASAS1 Sains', 'asasl', 'ASASL', 'Program: ASAS| SAINS'):
            with self.subTest(text):
                self.assertEqual(ai_only(text), 'asasi_ai_read')

    def test_cyrillic_and_greek_look_alikes(self):
        for text in ('АSASI', 'AЅAЅI', 'ASASІ', 'ΑSASI', 'ASASΙ',
                     'Program аsasi Sains', 'А S А S I'):
            with self.subTest(text.encode('unicode_escape')):
                self.assertEqual(ai_only(text), 'asasi_ai_read')

    def test_longer_words_holding_asasi_now_refuse(self):
        """The safe direction, accepted: before the fix round these were not ASASI (whole words only)."""
        for text in ('ASASIAH', 'ASASINYA', 'BASASI', 'ASASI2'):
            with self.subTest(text):
                self.assertEqual(ai_only(text), 'asasi_ai_read')

    def test_a_glued_programme_field_refuses_a_government_lock(self):
        letter = _poly(':ATK-PROGRAMASASI TEKNOLOGI KEJURUTERAAN')
        with mock.patch(AI_ONLY, return_value=''):              # control: otherwise a lock
            self.assertIsNotNone(diagnose(letter)['locked'])
        self.assertEqual(diagnose(letter)['guard'], 'asasi_ai_read')

    def test_glued_or_misread_on_a_ums_page_refuses(self):
        for word in ('178Asasi', 'ASASIpin', 'ASAS1', 'АSASI'):
            letter = ums().replace('Saudara/i akan', f'Kod {word} tidak berkaitan.\nSaudara/i akan')
            with self.subTest(word.encode('unicode_escape')):
                self.assertEqual(diagnose(letter)['guard'], 'asasi_ai_read')

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

    def test_a_letter_with_no_rules_lane_is_not_checked(self):
        with mock.patch(AI_ONLY, wraps=ai_only) as check:
            d = diagnose('SURAT BIASA\nProgram Asasi\n')
        self.assertEqual((check.call_count, d['family'], d['guard']), (0, '', None))


#: A made-up polytechnic letter (the government polytechnic family; fake name and IC).
POLY = """JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI
Tarikh: 25/05/2031
ZORVATH A/L QUENMIR (130212080355)
SURAT TAWARAN PENGAJIAN SESI : 2031/2032
Program
Mod Pengajian
Institusi
Tempoh Pengajian
:DKM-DIPLOMA KEJURUTERAAN MEKANIKAL
SEPENUH MASA
:POLITEKNIK ZELVORA
:6 SEMESTER
Tarikh dan Masa Daftar: 20 JUN 2031 (8.30 PAGI)
"""
POLY_PROG = ':DKM-DIPLOMA KEJURUTERAAN MEKANIKAL'


def _poly(prog=POLY_PROG):
    return POLY.replace(POLY_PROG, prog)


class TestEveryRulesLane(SimpleTestCase):
    """Not only the university lanes: a government family (polytechnic, STPM, matriculation) lock is refused the
    same way (`offer_parse._rules_exit`), on its visible page-1 text OR its parsed programme / stream."""

    def test_a_normal_polytechnic_letter_still_locks(self):
        d = diagnose(_poly())
        self.assertEqual((d['family'], d['guard'], d['locked']['programme']),
                         ('polytechnic', None, 'DIPLOMA KEJURUTERAAN MEKANIKAL'))

    def test_a_polytechnic_asasi_programme_is_refused(self):
        letter = _poly(':ATK-ASASI TEKNOLOGI KEJURUTERAAN')
        with mock.patch(AI_ONLY, return_value=''):              # control: the word alone is what refuses
            self.assertIn('ASASI', diagnose(letter)['locked']['programme'])
        for name, d in (('scan', diagnose(letter)), ('digital', diagnose(letter, page1_text=letter))):
            with self.subTest(name):
                self.assertEqual((d['family'], d['guard'], d['locked']), ('polytechnic', 'asasi_ai_read', None))
        self.assertIsNone(exact_read(letter))

    def test_the_programme_field_judges_too(self):
        """Page 1's plain layer (the visible text a government read uses) shows no Asasi, but the programme
        parsed from the whole layer does: refused all the same."""
        letter = _poly(':ATK-ASASI TEKNOLOGI KEJURUTERAAN')
        d = diagnose(letter, page1_text=_poly())
        self.assertEqual((d['guard'], d['locked']), ('asasi_ai_read', None))

    def test_asasi_on_the_visible_page_refuses_a_government_letter(self):
        from apps.scholarship.tests.test_offer_parser import MATRIC, STPM
        for name, letter in (('poly', _poly() + 'Calon program asasi tidak layak.\n'),
                             ('stpm', STPM + 'Program A S A S I tidak berkaitan.\n'),
                             ('matric', MATRIC + 'Bukan tawaran Asasi.\n')):
            with self.subTest(name):
                self.assertEqual(diagnose(letter)['guard'], 'asasi_ai_read')

    def test_government_letters_without_the_word_still_lock(self):
        from apps.scholarship.tests.test_offer_parser import MATRIC, STPM
        for letter in (STPM, MATRIC, _poly()):
            with self.subTest(letter[:20]):
                self.assertIsNotNone(diagnose(letter)['locked'])

    def test_asas_alone_does_not_refuse(self):
        d = diagnose(_poly(':DAK-DIPLOMA ASAS KEJURUTERAAN'))
        self.assertEqual((d['guard'], d['locked'] is not None), (None, True))
        self.assertIsNotNone(diagnose(_poly() + 'ASAS ASAS INI\n')['locked'])

    def test_asasiah_now_refuses(self):
        """Fix round: ASASI is matched anywhere, so "ASASIAH" (which holds ASASI) refuses. Accepted: the safe
        direction (one AI call); before the round it locked."""
        for letter in (_poly(':DAS-DIPLOMA ASASIAH KEJURUTERAAN'), _poly() + 'ASASIAH ASAS BASASI\n'):
            with self.subTest(letter[-30:]):
                d = diagnose(letter)
                self.assertEqual((d['guard'], d['locked']), ('asasi_ai_read', None))

    def test_normal_letters_of_every_lane_still_lock(self):
        """STPM, matriculation, polytechnic and UMS letters with no Asasi in them lock after the fix round."""
        from apps.scholarship.tests.test_offer_parser import MATRIC, STPM
        for name, d in (('stpm', diagnose(STPM)), ('matric', diagnose(MATRIC)), ('poly', diagnose(_poly())),
                        ('ums digital', _digital(ums())), ('ums scan', diagnose(ums()))):
            with self.subTest(name):
                self.assertIsNotNone(d['locked'])
