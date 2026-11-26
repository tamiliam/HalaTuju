"""OCR-14 phase 1: the owner's words for ten more universities, and the measured answer for UTeM's Asasi line.

Synthetic text only (no letter text). The lanes stay OFF: no layout reader dispatches to them yet, so these tests
check the allow-list data and the Asasi exit, not a lock. UTeM gets NO Asasi excuse: measured, none of its degree
letters prints ASASI, and the UTeM letters that do are diploma letters naming the school in their faculty field.
"""
from django.test import SimpleTestCase

from apps.scholarship.offer_owner_words import (_EXCUSED_LINE, OPTIONAL_ON_TEXT_PDF, OWNER_WORDS, ai_only,
                                                ai_only_on_lane, missing)
from apps.scholarship.offer_parse import _rules_exit

COUNTS = {'ua:UKM': 9, 'ua:UMK': 10, 'ua:UMPSA': 9, 'ua:UniMAP': 8, 'ua:UNIMAS': 6, 'ua:UniSZA': 8, 'ua:UPM': 6,
          'ua:USM': 9, 'ua:UTeM': 7, 'ua:UTHM': 8}
NEW_LANES = tuple(COUNTS)
#: The faculty line UTeM's diploma letters print (the shape measured; the spacing is made up).
UTEM_SCHOOL = 'Fakulti                              : SEKOLAH ASASI TEKNIKAL DAN PENGAJIAN DIPLOMA'
#: UiTM's excused letterhead contact label (made-up number): excused on UiTM only.
UITM_OFFICE = 'Asasi & Diploma : 03-5500 0000 / 0001'


def _letter(lane, skip=None):
    """Every owner phrase of ``lane`` on its own line, except number ``skip`` (1-based)."""
    return '\n'.join(p for k, p in enumerate(OWNER_WORDS[lane], 1) if k != skip)


class TestOcr14LanesData(SimpleTestCase):
    def test_counts_as_the_owner_gave(self):
        self.assertEqual({lane: len(OWNER_WORDS[lane]) for lane in NEW_LANES}, COUNTS)

    def test_earlier_rows_unchanged(self):
        self.assertEqual({lane: len(OWNER_WORDS[lane]) for lane in ('ua:UMS', 'ua:UPSI', 'ua:UUM', 'ua:UiTM', 'ua:UM')},
                         {'ua:UMS': 11, 'ua:UPSI': 11, 'ua:UUM': 7, 'ua:UiTM': 8, 'ua:UM': 8})

    def test_phrases_as_the_owner_typed_them(self):
        self.assertIn('Dengan sukacitanya saya bagi pihak Universiti Kebangsaan Malaysia', OWNER_WORDS['ua:UKM'])
        self.assertIn('(NO. K/P:', OWNER_WORDS['ua:UMPSA'])
        self.assertIn('Tahniah! Saudara/saudari adalah ditawarkan tempat', OWNER_WORDS['ua:UNIMAS'])
        self.assertIn('Rujukan Kami(Our Ref.)', OWNER_WORDS['ua:UTHM'])
        self.assertIn('Program & Kod Program', OWNER_WORDS['ua:UTHM'])
        self.assertEqual(OWNER_WORDS['ua:USM'][0], 'Jabatan Pendaftar')

    def test_letterhead_picture_phrases(self):
        self.assertEqual(OPTIONAL_ON_TEXT_PDF, {'ua:UMS': (1,), 'ua:USM': (1,)})


class TestOcr14LanesMatch(SimpleTestCase):
    def test_all_words_shown(self):
        for lane in NEW_LANES:
            with self.subTest(lane=lane):
                self.assertEqual(missing(lane, _letter(lane)), [])
                self.assertEqual(missing(lane, _letter(lane).upper().replace('\n', '  ')), [])

    def test_each_missing_word_is_reported(self):
        for lane in NEW_LANES:
            for k in range(1, len(OWNER_WORDS[lane]) + 1):
                if (lane, k) == ('ua:USM', 5):
                    continue
                with self.subTest(lane=lane, phrase=k):
                    self.assertEqual(missing(lane, _letter(lane, skip=k)), [k])

    def test_usm_label_inside_its_closing_sentence(self):
        # USM 5 "PROGRAM PENGAJIAN" is printed inside 8 "Program pengajian yang ditawarkan ...": the one-word
        # rule is for one-word phrases only, so 8 shows 5 too. A USM reader (phase 2 on) must read the label itself.
        self.assertEqual(missing('ua:USM', _letter('ua:USM', skip=5)), [])
        self.assertEqual(missing('ua:USM', _letter('ua:USM', skip=8)), [8])

    def test_one_word_inside_a_longer_phrase_does_not_count(self):
        # USM 9 "Pendaftar" printed only inside 1 "Jabatan Pendaftar"; UniSZA's offer sentence ends in "program".
        self.assertEqual(missing('ua:USM', _letter('ua:USM', skip=9)), [9])
        self.assertEqual(missing('ua:USM', _letter('ua:USM', skip=9), text_pdf=True), [9])
        self.assertEqual(missing('ua:UPM', _letter('ua:UPM', skip=6) + '\nTarikhnya'), [6])
        self.assertEqual(missing('ua:UNIMAS', _letter('ua:UNIMAS', skip=6) + '\nPendaftaran'), [6])
        self.assertEqual(missing('ua:UKM', _letter('ua:UKM', skip=2) + '\nRujukan Kami'), [])   # a whole word
        self.assertEqual(missing('ua:UMK', _letter('ua:UMK', skip=5) + '\nPrograms'), [5])

    def test_usm_letterhead_phrase_optional_on_a_text_pdf_only(self):
        text = _letter('ua:USM', skip=1)
        self.assertEqual(missing('ua:USM', text, text_pdf=True), [])
        self.assertEqual(missing('ua:USM', text), [1])             # a scan (OCR of the page) still needs it
        for lane in NEW_LANES:
            if lane != 'ua:USM':
                with self.subTest(lane=lane):
                    self.assertEqual(missing(lane, _letter(lane, skip=1), text_pdf=True), [1])

    def test_glued_or_misread_words_do_not_count(self):
        text = _letter('ua:UTHM').replace('Tawaran ini adalah MUKTAMAD', 'Tawaran ini adalah MUKTARNAD')
        self.assertEqual(missing('ua:UTHM', text), [8])
        text = _letter('ua:UNIMAS').replace('Universiti Malaysia Sarawak', 'Universiti Malaysia Sarawakk')
        self.assertEqual(missing('ua:UNIMAS', text), [2])

    def test_older_layouts_go_to_the_ai(self):
        # UNIMAS and UMPSA: this year's layout only (the owner's words name it).
        old_unimas = _letter('ua:UNIMAS').replace('Pejabat Timbalan Naib Canselor', 'PEJABAT PENDAFTAR')
        self.assertEqual(missing('ua:UNIMAS', old_unimas), [1])
        old_umpsa = _letter('ua:UMPSA').replace('TARIKH PENDAFTARAN KOLEJ KEDIAMAN', 'TARIKH PENDAFTARAN')
        self.assertEqual(missing('ua:UMPSA', old_umpsa), [7])

    def test_english_and_confirmation_letters_go_to_the_ai(self):
        english = ('OFFER OF ADMISSION\nCongratulations, you have been offered a place\nProgramme : X\n'
                   'Duration of Study : 4 years\nRegistration Date : 1 September 2031\nofficial confirmation letter')
        confirm = 'PENGESAHAN PENDAFTARAN\nRujukan\nProgram Pengajian\nTempoh Pengajian\nTarikh\nPendaftar'
        for lane in NEW_LANES:
            with self.subTest(lane=lane):
                self.assertTrue(missing(lane, english))
                self.assertTrue(missing(lane, confirm))

    def test_one_lanes_words_do_not_pass_another(self):
        for lane in NEW_LANES:
            for other in NEW_LANES:
                if other != lane:
                    with self.subTest(lane=lane, other=other):
                        self.assertTrue(missing(other, _letter(lane)))


class TestUtemHasNoAsasiExcuse(SimpleTestCase):
    def test_only_uitm_has_an_excused_line(self):
        self.assertEqual(set(_EXCUSED_LINE), {'ua:UiTM'})

    def test_a_utem_diploma_letter_with_every_owner_phrase_still_refuses(self):
        page = _letter('ua:UTeM') + '\n' + UTEM_SCHOOL + '\nProgram Pengajian : Diploma Teknologi X'
        self.assertEqual(missing('ua:UTeM', page, text_pdf=True), [])
        self.assertEqual(ai_only_on_lane('ua:UTeM', page), 'asasi_ai_read')
        self.assertEqual(ai_only(page), 'asasi_ai_read')

    def test_utem_does_not_borrow_the_uitm_excuse(self):
        self.assertEqual(ai_only_on_lane('ua:UTeM', UITM_OFFICE + '\n' + _letter('ua:UTeM')), 'asasi_ai_read')
        self.assertEqual(ai_only_on_lane('ua:UiTM', UITM_OFFICE + '\nSURAT TAWARAN'), '')

    def test_a_utem_degree_page_passes_the_asasi_exit(self):
        page = _letter('ua:UTeM') + '\nProgram Pengajian : Ijazah Sarjana Muda Kejuruteraan X'
        self.assertEqual(ai_only_on_lane('ua:UTeM', page), '')


class TestRulesExitOcr14Lanes(SimpleTestCase):
    @staticmethod
    def _out(**lock):
        return {'locked': dict(lock), 'guard': None}

    def test_a_clean_degree_lock_passes_on_every_new_lane(self):
        for lane in NEW_LANES:
            with self.subTest(lane=lane):
                out = _rules_exit(self._out(rules_lane=lane, programme='Ijazah Sarjana Muda Sains'), _letter(lane))
                self.assertIsNotNone(out['locked'])

    def test_asasi_refuses_on_every_new_lane(self):
        cases = (('Asasi Sains', 'TAWARAN'), ('Foundation in Science', 'TAWARAN'),
                 ('Ijazah Sarjana Muda Sains', UITM_OFFICE + '\nTAWARAN'),
                 ('Ijazah Sarjana Muda Sains', UTEM_SCHOOL), ('Ijazah Sarjana Muda Sains', 'Program A S A S I'))
        for lane in NEW_LANES:
            for prog, page in cases:
                with self.subTest(lane=lane, prog=prog, page=page[:12]):
                    out = _rules_exit(self._out(rules_lane=lane, programme=prog), page)
                    self.assertEqual((out['locked'], out['guard']), (None, 'asasi_ai_read'))
