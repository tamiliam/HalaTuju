"""Offer exact-read S6 — the SIXTH adversarial review (2026-11-03): private letters that escaped through the safety
rule (a generic ministry word "named first", a public / unit word excusing a private college's own line, an unclean
letterhead not counted as private evidence, a body "pengesahan pelajar"). Every letter is invented
(`test_no_gitignored_corpus.py`)."""
from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_issuers import _letterhead
from apps.scholarship.genuineness.offer_rulings import (_clean_letterhead, _company_lines_incidental,
                                                         _first_institution, _folded_lines, _incidental,
                                                         _TVET_NAMES, confirmation_kind, ruled_offer)
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, signature_genuineness
from apps.scholarship.tests.test_offer_s6_review3 import _letter
from apps.scholarship.tests.test_offer_s6_review5 import _conf


def _g(text):
    return signature_genuineness(text, doc_type='offer_letter')


def _r(p, family='ua_offer'):
    return {'probability': p, 'type': family, 'present': [], 'missing': [], 'scores': {}}


def _blocks(test, text, ps=(0.05, 0.2)):
    for p in ps:
        with test.subTest(text=text.splitlines()[0], p=p):
            out = ruled_offer(text, _r(p), 'not_offer_letter', 'r', MODEL_VERSION)
            test.assertEqual(out['status'], 'not_offer_letter')


class HAPrivateConfirmationsBlock(SimpleTestCase):
    HEADS = ('ABC UNIVERSITY COLLEGE DEPARTMENT OF ACADEMIC AFFAIRS',
             'JABATAN PENDAFTAR\nKOLEJ UNIVERSITI ABC',
             'KOLEJ ABC (BERDAFTAR DENGAN KEMENTERIAN PENDIDIKAN TINGGI)',
             'KEMENTERIAN PENDIDIKAN TINGGI\nKOLEJ ABC',
             'KEMENTERIAN PENDIDIKAN MALAYSIA\nPUSAT TUISYEN ABC',
             'APPROVED BY THE MINISTRY OF HIGHER EDUCATION\nABC INTERNATIONAL COLLEGE',
             'FAKULTI PERNIAGAAN, KOLEJ UNIVERSITI ABC',
             'ABC COLLEGE, A GOVERNMENT-APPROVED INSTITUTION',
             'UNIVERSITI MALAYSIA SABAH\nKOLEJ ABC',
             'POLITEKNIK\nKOLEJ ABC\nKPT')

    def test_each_private_confirmation_blocks(self):
        for head in self.HEADS:
            text, _out = _conf(head)
            self.assertEqual(confirmation_kind(text, 0.2), '', head)
            _blocks(self, text)

    def test_a_private_offer_with_a_body_confirmation_phrase_blocks(self):
        text = ('KOLEJ ABC\nKPT\nJalan Contoh, 50000 Kuala Lumpur\nRujukan : ABC/1\nTarikh : 1 Jun 2026\n'
                'Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\nSURAT TAWARAN KEMASUKAN\n'
                'Anda ditawarkan Diploma Contoh.\nSurat ini juga sebagai pengesahan pelajar.\nYang benar,\nPENGARAH\n')
        _blocks(self, text)

    def test_the_three_line_cheap_fake_blocks(self):
        _blocks(self, 'KEMENTERIAN PENDIDIKAN MALAYSIA\nPENGESAHAN PELAJAR\nNama: ALI\n', ps=(0.06,))


class HBOwnUnitWordsNeverExcuseAPrivateCollege(SimpleTestCase):
    def test_a_private_college_unit_line_never_reads_genuine(self):
        venue = 'Kursus : Sijil Contoh\nTarikh lapor diri : 3 Ogos 2026\nTempat : ILP Kuala Lumpur\n'
        for head in ('ABC COLLEGE DEPARTMENT OF ADMISSIONS', 'KOLEJ ABC UNIT KEMASUKAN'):
            with self.subTest(head=head):
                self.assertNotEqual(_g(_letter(head, body=venue))['status'], 'genuine')

    def test_a_private_division_over_jpk_blocks(self):
        _blocks(self, _letter('KOLEJ ABC BAHAGIAN KEMASUKAN\nJABATAN PEMBANGUNAN KEMAHIRAN'))


class HCPublicWordsNeverExcuseAPrivateCollege(SimpleTestCase):
    def test_a_private_college_beside_a_ministry_never_reads_genuine(self):
        for head in ('KOLEJ ABC (KEMENTERIAN PENDIDIKAN TINGGI)', 'KOLEJ ABC JABATAN AKADEMIK'):
            for venue in ('IKM Kuala Lumpur', 'IKBN Pekan'):
                body = f'Kursus : Sijil Contoh\nTarikh lapor diri : 3 Ogos 2026\nTempat : {venue}\n'
                with self.subTest(head=head, venue=venue):
                    self.assertNotEqual(_g(_letter(head, body=body))['status'], 'genuine')

    def test_a_private_academy_under_a_closed_list_body_blocks(self):
        for head in ('JABATAN PEMBANGUNAN KEMAHIRAN\nABC SKILLS ACADEMY',
                     'INSTITUT KEMAHIRAN BELIA NEGARA\nABC TECHNICAL ACADEMY',
                     'JTM\nPUSAT LATIHAN ABC', 'JPK\nABC SKILLS CENTRE'):
            _blocks(self, _letter(head))


class RealPublicLinesStayClean(SimpleTestCase):
    def test_campus_words_after_a_closed_list_name(self):
        for head in ('IKTBN KAMPUS SEPANG', 'KKTM TECH CAMPUS', 'INSTITUT LATIHAN PERINDUSTRIAN KAMPUS CONTOH'):
            with self.subTest(head=head):
                self.assertTrue(_clean_letterhead(_folded_lines(head), _TVET_NAMES))

    def test_a_unit_line_with_no_other_organisation(self):
        lines = _folded_lines('UNIVERSITI MALAYSIA SABAH\nACADEMIC SERVICES DIVISION\nFACULTY OF EDUCATION')
        self.assertTrue(_clean_letterhead(lines, (' UNIVERSITI MALAYSIA SABAH ',)))
        self.assertEqual(_first_institution(lines, (' UNIVERSITI MALAYSIA SABAH ',)), 'allowed')

    def test_a_name_followed_by_another_college_is_not_its_campus(self):
        self.assertFalse(_clean_letterhead(_folded_lines('IKBN KOLEJ ABC'), _TVET_NAMES))


class Lows(SimpleTestCase):
    def test_polytechnic_in_english_is_a_no_private_wing_name(self):
        text, _out = _conf('POLYTECHNIC CONTOH\nMINISTRY OF HIGHER EDUCATION')
        self.assertEqual(confirmation_kind(text, 0.2), 'confirmation_polytechnic')

    def test_a_one_word_company_name_on_the_letterhead_keeps_the_veto(self):
        lines = _folded_lines('MERCU\nKEMENTERIAN PENDIDIKAN MALAYSIA\nSURAT TAWARAN\nNama : Ali\n'
                              'Penaja : Mercu Sdn Bhd\n')
        self.assertFalse(_company_lines_incidental(lines))

    def test_islamic_excuses_only_a_bank_or_a_bare_berhad(self):
        self.assertTrue(_incidental(_folded_lines('Bank Islam Malaysia Berhad'), 0))
        self.assertTrue(_incidental(_folded_lines('ABC Islamic Berhad'), 0))
        self.assertFalse(_incidental(_folded_lines('ABC Islamic College Berhad'), 0))

    def test_an_islamic_college_berhad_stays_on_the_letterhead(self):
        self.assertIn(' COLLEGE ', _letterhead('ABC Islamic College Berhad\nSURAT TAWARAN\n'))
        self.assertNotIn(' ISLAMIC ', _letterhead('Bayaran kepada ABC Islamic Berhad\nSURAT TAWARAN\n'))
