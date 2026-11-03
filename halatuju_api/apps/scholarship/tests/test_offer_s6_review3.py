"""Offer exact-read S6 — the THIRD adversarial review (2026-11-03): the reviewer's own probes, one regression
each. Every letter is invented (`test_no_gitignored_corpus.py`). Accepted residual risk (owner, decisions S6
item 4): a full, well-laid-out institute letter with every part, and deliberate Unicode tricks.
"""
import time

from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_rulings import (_folded_lines, _letter_structure, _private_signs,
                                                         confirmation_kind, ruled_offer, ruling_of, _TITLE)
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, signature_genuineness
from apps.scholarship.tests.test_offer_s6_narrowing import baseline_status


def _g(text):
    return signature_genuineness(text, doc_type='offer_letter')


def _r(p, family='ua_offer'):
    return {'probability': p, 'type': family, 'present': [], 'missing': [], 'scores': {}}


def _letter(head, *, cand='Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\n',
            body='Kursus : Sijil Kemahiran Contoh\nTarikh lapor diri : 3 Ogos 2026\nTempat : IKBN Pekan\n',
            extra='', closing='Sekian, terima kasih.\nYang benar,\nPENGARAH\nIKBN Pekan\n'):
    return (f'{head}\nJalan Contoh, 26600 Pekan\nTel : 09-000 0000\nRujukan : KBS.600-1/2/3\nTarikh : 1 Jun 2026\n'
            f'{cand}Tuan,\nSURAT TAWARAN KEMASUKAN\nDengan sukacitanya dimaklumkan bahawa anda ditawarkan tempat.\n'
            f'{body}{extra}Sila bawa dokumen asal semasa mendaftar.\nTawaran ini tertakluk kepada syarat.\n{closing}')


REAL = _letter('KEMENTERIAN BELIA DAN SUKAN\nINSTITUT KEMAHIRAN BELIA NEGARA (IKBN) PEKAN')


class Positive(SimpleTestCase):
    def test_a_full_letter_reads_genuine(self):
        g = _g(REAL)
        self.assertEqual((g['status'], ruling_of(g)), ('genuine', 'tvet_offer'))


class H1ThinPages(SimpleTestCase):
    def test_the_reviewers_thin_pages_are_not_genuine(self):
        for text in ('IKBN\nRuj: 1 1 Jun 2026\nSURAT TAWARAN\nNama: A\nYang benar',
                     'IKBN SURAT TAWARAN\nRuj 1\n1 Jun 2026\nNama A\nPENGARAH'):
            with self.subTest(text=text[:20]):
                self.assertNotEqual(_g(text)['status'], 'genuine')

    def test_each_new_part_is_needed(self):
        for label, broken in (('no IC', REAL.replace('080808-10-5566', '')),
                              ('no course', REAL.replace('Kursus : Sijil Kemahiran Contoh\n', '')),
                              ('no reporting', REAL.replace('Tarikh lapor diri : 3 Ogos 2026\n', '')
                               .replace('semasa mendaftar', 'semasa datang'))):
            with self.subTest(label):
                self.assertNotEqual(_g(broken)['status'], 'genuine')

    def test_below_the_floor_the_body_names_the_institute_again(self):
        body_less = REAL.replace('Tempat : IKBN Pekan\n', '').replace('PENGARAH\nIKBN Pekan\n', 'PENGARAH\n')
        low = _r(0.1)                       # a photo below the suspect floor
        self.assertEqual(ruled_offer(REAL, low, 'not_offer_letter', 'r', MODEL_VERSION)['status'], 'genuine')
        self.assertEqual(ruled_offer(body_less, low, 'not_offer_letter', 'r', MODEL_VERSION)['status'],
                         'not_offer_letter')     # round 7: not lifted → the baseline


class H2TheLetterheadNamesOnlyTheAllowed(SimpleTestCase):
    def test_another_organisation_on_the_letterhead_never_lifts(self):
        for head in ('PUSAT LATIHAN KEMAHIRAN ABC\nIKBN', 'ABC TRAINING CENTRE\nIKBN', 'ABC SKILLS CENTRE\nIKBN',
                     'ABC LEARNING HUB\nIKBN', 'ABC EDUCATION GROUP\nIKBN', 'ABC TECH PLT\nIKBN',
                     'ABC POLYTECHNIC\nRakan Strategik IKM', 'IKBN\nKOLEJ ABC', 'IKBN KOLEJ ABC',
                     'INSTITUT KEMAHIRAN BELIA NEGARA\nKOLEJ ABC'):
            with self.subTest(head=head):
                self.assertNotEqual(_g(_letter(head))['status'], 'genuine')

    def test_partner_wording_on_the_letterhead_never_lifts(self):
        for word in ('Partner', 'Rakan', 'Bersama', 'Affiliated', 'Francais', 'Strategik'):
            with self.subTest(word=word):
                self.assertNotEqual(_g(_letter(f'IKBN PEKAN\n{word} IKBN'))['status'], 'genuine')


class H3ConfirmationStructure(SimpleTestCase):
    def test_thin_or_foreign_confirmations_are_not_genuine(self):
        for text, p in (('UNIVERSITI MALAYSIA SABAH\nPENGESAHAN PELAJAR\nNama : Ali', 0.30),
                        ('POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI\nPENGESAHAN PELAJAR\nNama : Ali', 0.11)):
            with self.subTest(head=text.splitlines()[0]):
                out = ruled_offer(text, _r(p), 'not_offer_letter', 'r', MODEL_VERSION)
                # S6 round 7 (the narrowing, owner option 1): unproven → the baseline, never a guess
                self.assertEqual(out['status'], 'not_offer_letter')
        for text in ('ABC LEARNING CENTRE\nPENGESAHAN PELAJAR\nNama : Ali\nUniversiti Malaysia Sabah\n',
                     'ABC EDU HUB\nSMK Contoh Tingkatan Enam\nPENGESAHAN PELAJAR\nNama : Ali\n'
                     'Kementerian Pendidikan Malaysia\n'):
            with self.subTest(head=text.splitlines()[0]):
                self.assertEqual(confirmation_kind(text, 0.3), '')


class SafetyRule(SimpleTestCase):
    """A closed-list public body, NO positive private evidence, one rule missed → suspect, never a fail."""

    def test_a_real_shaped_letter_missing_a_rule_is_suspect_not_a_fail(self):
        for label, text in (
                ('a koperasi line', REAL.replace('Sila bawa', 'Bayaran kepada Koperasi IKBN Pekan Berhad.\nSila bawa')),
                ('a Maybank Islamic line', REAL.replace('Sila bawa', 'Akaun Maybank Islamic Berhad.\nSila bawa')),
                ('a takaful line', REAL.replace('Sila bawa', 'Perlindungan takaful oleh Contoh Takaful Berhad.\nSila bawa')),
                ('Saudara, no Nama label', REAL.replace('Nama : Ali bin Abu\n', 'Saudara Ali bin Abu\n')),
                ('reference after the body', REAL.replace('Rujukan : KBS.600-1/2/3\n', '') + 'Rujukan : KBS.1\n'),
                ('title after the closing', REAL.replace('SURAT TAWARAN KEMASUKAN\n', '') + 'SURAT TAWARAN\n'),
                ('JALAN KOLEJ above the letterhead', 'No 1, Jalan Kolej\n' + REAL)):
            with self.subTest(label):
                # suspect, or NOT CHECKED ("unchecked", no signal) in the suspect band — never a fail
                self.assertIn(_g(text)['status'], ('genuine', 'suspect', 'unchecked'))

    def test_a_bank_berhad_is_not_private_evidence(self):
        for line in ('Akaun Maybank Islamic Berhad', 'CIMB Bank Berhad', 'RHB Islamic Berhad'):
            with self.subTest(line=line):
                self.assertFalse(_private_signs(_folded_lines(f'IKBN\nRujukan 1\n{line}\n')))
        # S6 round 8 (almost no excuses): a co-operative or an insurer is no closed-list bank: a private marker.
        for line in ('Koperasi Contoh Berhad', 'Contoh Takaful Malaysia Berhad', 'Insurans Contoh Berhad'):
            with self.subTest(line=line):
                self.assertTrue(_private_signs(_folded_lines(f'IKBN\nRujukan 1\n{line}\n')))


class MediumOtherFirstIsPrivate(SimpleTestCase):
    def test_a_college_with_a_partner_line_reads_private_not_unchecked(self):
        for word in ('Partner', 'Rakan', 'Affiliated', 'Francais'):
            with self.subTest(word=word):
                text = _letter(f'KOLEJ ABC\n{word} IKBN')
                self.assertEqual(_g(text)['status'], 'not_offer_letter')
        # S6 round 7 (the narrowing, owner option 1): "Bersama" alone is no explicit tie-up word: never lifted, the baseline.
        text = _letter('KOLEJ ABC\nBersama IKBN')
        self.assertEqual(_g(text)['status'], baseline_status(text))


_POLY = ('KEMENTERIAN PENDIDIKAN TINGGI\nJABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI\nRujukan : JPPKK/1\n'
         'Tarikh : 01/06/2026\n{cand}SURAT TAWARAN PENGAJIAN\nProgram : Diploma Contoh\nInstitusi : Politeknik Contoh\n'
         'Tarikh dan Masa Daftar : 15 Jun 2026\nTawaran ini adalah muktamad dan terbatal sekiranya anda tidak mendaftar '
         'di institusi.\nTertakluk kepada kesahihan maklumat dalam borang permohonan.\n{pay}Yang benar,\nPENGARAH\n')


class MediumSdnBhdExcuses(SimpleTestCase):
    def test_an_address_below_the_date_but_not_in_the_candidate_block_keeps_the_veto(self):
        text = _POLY.format(cand='ABC EDUCATION SDN BHD\nJALAN AMPANG 50450 KL\n', pay='')
        self.assertEqual(_g(text)['status'], 'not_offer_letter')

    def test_a_fee_to_a_company_keeps_the_veto(self):
        text = _POLY.format(cand='', pay='Bayaran yuran kepada ABC Edu Sdn Bhd.\n')
        self.assertEqual(_g(text)['status'], 'not_offer_letter')

    def test_the_candidates_own_estate_address_is_excused(self):
        text = _POLY.format(cand='ALI BIN ABU (080808105566)\nLADANG CONTOH SDN BHD\nPETI SURAT 1, 90000 SANDAKAN\n',
                            pay='')
        self.assertEqual(_g(text)['status'], 'genuine')


class MediumPublicAcademy(SimpleTestCase):
    def test_a_conditional_offer_from_a_public_academy_is_never_private(self):
        out = ruled_offer('AKADEMI BINAAN MALAYSIA (ABM)\nTawaran Kemasukan Bersyarat\n', _r(0.4), 'suspect', 'r',
                          MODEL_VERSION)
        self.assertEqual(out['status'], 'suspect')


class MediumPerformance(SimpleTestCase):
    def test_forty_thousand_lines_in_under_a_second(self):
        lines = _folded_lines('\n'.join(f'baris {i} kandungan surat' for i in range(40000)))
        t0 = time.perf_counter()
        _letter_structure(lines, _TITLE, min_lines=12, reporting=True)
        _private_signs(lines)
        self.assertLess(time.perf_counter() - t0, 1.0)


class LowUniklMention(SimpleTestCase):
    def test_a_real_ikm_letter_naming_unikl_as_a_pathway_is_not_failed(self):
        text = _letter('MAJLIS AMANAH RAKYAT\nINSTITUT KEMAHIRAN MARA KOTA CONTOH',
                       extra='Laluan ke Universiti Kuala Lumpur selepas tamat pengajian.\n',
                       body='Kursus : Sijil Kemahiran Contoh\nTarikh lapor diri : 3 Ogos 2026\n'
                            'Tempat : Institut Kemahiran MARA Kota Contoh\n')
        # S6 round 7 (the narrowing, owner option 1): a named private body ANYWHERE on the page stops a lift (owner: no private
        # marker on page 1), and a body mention is no letterhead proof: the baseline, never blocked.
        self.assertEqual(_g(text)['status'], baseline_status(text))
        self.assertNotEqual(ruling_of(_g(text)), 'private_offer')

    def test_a_unikl_letterhead_still_fails(self):
        self.assertNotEqual(_g(_letter('UNIVERSITI KUALA LUMPUR\nMAJLIS AMANAH RAKYAT'))['status'], 'genuine')


class OwnerPppl(SimpleTestCase):
    def test_a_ums_pppl_confirmation_or_offer_is_private(self):     # owner 2026-11-03, the subsidy test
        for head in ('UNIVERSITI MALAYSIA SABAH\nPusat Pendidikan Profesional dan Lanjutan (PPPL)',
                     'UNIVERSITI MALAYSIA SABAH\nPusat Pendidikan Lanjutan'):
            with self.subTest(head=head):
                self.assertEqual(_g(f'{head}\nPENGESAHAN PELAJAR\nNama : Ali\nTAWARAN KEMASUKAN\n')['status'],
                                 'not_offer_letter')


class TvetSpeltOutIsNotAnotherInstitution(SimpleTestCase):
    """Found by the final held-out run (round 3): an IKM offer titled "… Technical and Vocational Education and
    Training" read its EDUCATION / TRAINING as another organisation named before the institute."""

    def test_an_offer_title_spelling_out_tvet_still_lifts(self):
        text = REAL.replace('SURAT TAWARAN KEMASUKAN\n',
                            'SURAT TAWARAN KEMASUKAN PROGRAM TECHNICAL AND VOCATIONAL EDUCATION AND TRAINING\n')
        self.assertEqual(_g(text)['status'], 'genuine')

    def test_a_training_centre_is_still_another_organisation(self):
        self.assertNotEqual(_g(_letter('ABC TRAINING CENTRE\nIKBN'))['status'], 'genuine')
