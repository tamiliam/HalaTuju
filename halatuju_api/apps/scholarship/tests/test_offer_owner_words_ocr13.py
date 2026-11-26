"""OCR-13 phase 1: the owner's words for UPSI, UUM, UiTM and UM, and UiTM's one excused Asasi letterhead line.

Synthetic text only (no letter text). The lanes stay OFF: no layout reader dispatches to them yet, so these tests
check the allow-list data and the Asasi exit, not a lock.
"""
from django.test import SimpleTestCase

from apps.scholarship.offer_owner_words import (OWNER_WORDS, ai_only, ai_only_on_lane, missing,
                                                programme_ai_only)
from apps.scholarship.offer_parse import _rules_exit

NEW_LANES = ('ua:UPSI', 'ua:UUM', 'ua:UiTM', 'ua:UM')
#: UiTM's letterhead contact label (the telephone number is made up).
OFFICE = 'Asasi & Diploma : 03-5500 0000 / 0001'
HEAD = 'Pejabat X : 03-5500 0002\n'


def _letter(lane, skip=None):
    """Every owner phrase of ``lane`` on its own line, except number ``skip`` (1-based)."""
    return '\n'.join(p for k, p in enumerate(OWNER_WORDS[lane], 1) if k != skip)


class TestNewLanesData(SimpleTestCase):
    def test_counts_as_the_owner_gave(self):
        self.assertEqual({lane: len(OWNER_WORDS[lane]) for lane in NEW_LANES},
                         {'ua:UPSI': 11, 'ua:UUM': 7, 'ua:UiTM': 8, 'ua:UM': 8})

    def test_corrected_typos(self):
        self.assertIn('TAWARAN KEMASUKAN KE UNIVERSITI PENDIDIKAN SULTAN IDRIS (UPSI)', OWNER_WORDS['ua:UPSI'])
        self.assertIn('Program dan kampus yang ditawarkan adalah MUKTAMAD', OWNER_WORDS['ua:UiTM'])
        self.assertIn('Tahniah saudara/i telah berjaya ditawarkan tempat', OWNER_WORDS['ua:UM'])

    def test_ums_row_unchanged(self):
        self.assertEqual(len(OWNER_WORDS['ua:UMS']), 11)


class TestNewLanesMatch(SimpleTestCase):
    def test_all_words_shown(self):
        for lane in NEW_LANES:
            with self.subTest(lane=lane):
                self.assertEqual(missing(lane, _letter(lane)), [])
                self.assertEqual(missing(lane, _letter(lane).upper().replace('\n', '  ')), [])

    def test_each_missing_word_is_reported(self):
        for lane in NEW_LANES:
            for k in range(1, len(OWNER_WORDS[lane]) + 1):
                with self.subTest(lane=lane, phrase=k):
                    self.assertEqual(missing(lane, _letter(lane, skip=k)), [k])

    def test_one_word_inside_a_longer_phrase_does_not_count(self):
        # UiTM 3 "Program" is printed inside 7 "Program dan kampus ..." only; UPSI 5 inside 4's "program pengajian".
        self.assertEqual(missing('ua:UiTM', _letter('ua:UiTM', skip=3)), [3])
        self.assertEqual(missing('ua:UPSI', _letter('ua:UPSI', skip=5)), [5])
        self.assertEqual(missing('ua:UiTM', _letter('ua:UiTM', skip=6) + '\nTarikhnya'), [6])
        self.assertEqual(missing('ua:UUM', _letter('ua:UUM', skip=2) + '\nRujukan Kami'), [])   # whole word
        self.assertEqual(missing('ua:UUM', _letter('ua:UUM', skip=2) + '\nRujukannya'), [2])

    def test_glued_or_misread_words_do_not_count(self):
        text = _letter('ua:UM').replace('TAWARAN KEMASUKAN KE UNIVERSITI MALAYA', 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYAN')
        self.assertEqual(missing('ua:UM', text), [3])
        text = _letter('ua:UPSI').replace('Tawaran ini adalah muktamad', 'Tawaran ini adalah muktarnad')
        self.assertEqual(missing('ua:UPSI', text), [9])

    def test_english_and_confirmation_letters_go_to_the_ai(self):
        english = ('OFFER OF ADMISSION\nCongratulations, you have been offered a place\nProgramme : X\n'
                   'Duration of Study : 4 years\nRegistration Date : 1 September 2031\nofficial confirmation letter')
        for lane in NEW_LANES:
            with self.subTest(lane=lane):
                self.assertTrue(missing(lane, english))
        senate = 'JABATAN HAL EHWAL AKADEMIK\nRujukan\nPENGESAHAN TAMAT PENGAJIAN\nProgram Pengajian\nTempoh Pengajian'
        self.assertTrue(missing('ua:UUM', senate))
        self.assertTrue(missing('ua:UM', 'TAWARAN KEMASUKAN KE UNIVERSITI MALAYA\nTahniah saudara/i telah ditawarkan tempat'))


class TestUitmAsasiExcuse(SimpleTestCase):
    def test_the_office_label_alone_is_excused_on_uitm_only(self):
        tail = '\nSURAT TAWARAN\nProgram : Ijazah Sarjana Muda Sains (Kepujian)'
        for head in (HEAD + OFFICE, HEAD + 'Bahagian X' + ' ' * 20 + OFFICE, HEAD + '  ' + OFFICE.upper(),
                     HEAD + 'asasi  &  diploma: 03 - 5500 0000', HEAD + 'Asasi & Diploma : (03) 5500 0000 / 0001',
                     HEAD + 'X Y' + ' ' * 5 + 'Asasi & Diploma : (600) 0000 0000 / 0001 / 0002',
                     'SURAT TAWARAN\n' + OFFICE + '      Bahagian Y : (03) 5500 0003'):
            with self.subTest(head=head):
                self.assertEqual(ai_only_on_lane('ua:UiTM', head + tail), '')
        page = HEAD + OFFICE + tail
        for lane in ('ua:UMS', 'ua:UPSI', 'ua:UUM', 'ua:UM', ''):
            with self.subTest(lane=lane):
                self.assertEqual(ai_only_on_lane(lane, page), 'asasi_ai_read')
        self.assertEqual(ai_only(page), 'asasi_ai_read')

    def test_asasi_anywhere_else_still_refuses(self):
        title = '\nSURAT TAWARAN\n'
        cases = {
            'programme': f'{OFFICE}{title}Program : Asasi Sains',
            'sentence': f'{OFFICE}{title}anda ditawarkan tempat dalam program Asasi',
            'spaced': f'{OFFICE}{title}Program : A S A S I Sains',
            'glued': f'{OFFICE}{title}Program : PROGRAMASASI',
            'misread': f'{OFFICE}{title}Program : ASAS1 Sains',
            'lookalike': f'{OFFICE}{title}Program : АSASI Sains',
            'second_copy': f'{OFFICE}\n{OFFICE}{title}',
            'copy_below_title': f'{OFFICE}{title}{OFFICE}',
            'words_after_number': f'Asasi & Diploma : (03) 5500 0000 Sains{title}',
            'number_then_word_column': f'Asasi & Diploma : (03) 5500 0000 / Asasi{title}',
            'no_number': f'Asasi & Diploma :{title}',
            'parenthesised': f'Tel : (03) 5500 0000 (Asasi & Diploma){title}',
            'no_colon': f'Asasi & Diploma 03-5500 0000{title}',
            'word_before': f'Unit {OFFICE}{title}',
            'glued_before': f'X{OFFICE}{title}',
            'glued_after': f'Asasi & Diplomas : 03-5500 0000{title}',
            'split_lines': f'Asasi &\nDiploma : 03-5500 0000{title}',
            'split_lines_2': f'Asasi\n& Diploma : 03-5500 0000{title}',
            'and_word': f'Asasi dan Diploma : 03-5500 0000{title}',
            'cyrillic_in_label': f'Аsasi & Diploma : 03-5500 0000{title}',
            'long_s_in_label': f'Aſasi & Diploma : 03-5500 0000{title}',
            'asasi_beside': f'{OFFICE}      Program Asasi{title}',
        }
        for label, page in cases.items():
            with self.subTest(case=label):
                self.assertEqual(ai_only_on_lane('ua:UiTM', page), 'asasi_ai_read')

    def test_programme_field_foundation_in(self):
        for prog in ('Foundation in Science', 'FOUNDATION  IN ENGINEERING', 'Asasi Sains', 'foundation in\nlaw'):
            with self.subTest(prog=prog):
                self.assertEqual(programme_ai_only(prog), 'asasi_ai_read')
        for prog in ('Ijazah Sarjana Muda Sains (Kepujian)', 'Bachelor of Science (Hons)', ''):
            with self.subTest(prog=prog):
                self.assertEqual(programme_ai_only(prog), '')


class TestRulesExitPerLane(SimpleTestCase):
    @staticmethod
    def _out(**lock):
        return {'locked': dict(lock), 'guard': None}

    def test_uitm_lock_keeps_its_office_line(self):
        out = _rules_exit(self._out(rules_lane='ua:UiTM', programme='Ijazah Sarjana Muda Sains'), f'{OFFICE}\nSURAT TAWARAN')
        self.assertIsNotNone(out['locked'])

    def test_uitm_lock_refuses_asasi_elsewhere_or_foundation(self):
        out = _rules_exit(self._out(rules_lane='ua:UiTM', programme='Asasi Sains'), f'{OFFICE}\nSURAT TAWARAN')
        self.assertEqual((out['locked'], out['guard']), (None, 'asasi_ai_read'))
        out = _rules_exit(self._out(rules_lane='ua:UiTM', programme='Foundation in Science'), 'SURAT TAWARAN')
        self.assertEqual((out['locked'], out['guard']), (None, 'asasi_ai_read'))
        # A programme value shaped like the excused label is still the programme field: refused.
        out = _rules_exit(self._out(rules_lane='ua:UiTM', programme=OFFICE), f'SURAT TAWARAN\nProgram :    {OFFICE}')
        self.assertEqual((out['locked'], out['guard']), (None, 'asasi_ai_read'))

    def test_other_locks_are_judged_as_before(self):
        for lock in ({'rules_lane': 'ua:UMS', 'programme': 'Sarjana Muda Sains'}, {'programme': 'Sarjana Muda Sains'}):
            with self.subTest(lock=lock):
                out = _rules_exit(self._out(**lock), f'{OFFICE}\nSURAT TAWARAN')
                self.assertEqual((out['locked'], out['guard']), (None, 'asasi_ai_read'))
        # A government lock's programme is not checked for "Foundation in" (university lanes only).
        out = _rules_exit(self._out(programme='Foundation in Science'), 'TAWARAN')
        self.assertIsNotNone(out['locked'])
