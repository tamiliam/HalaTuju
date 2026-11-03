"""Offer exact-read S6 round 7 — THE NARROWING (owner option 1, 2026-11-03): S6 changes a genuineness call ONLY on
clear proof; every other page keeps the BASELINE, the pre-S6 call (`results_doc.baseline_genuineness`).

The property is asserted over every probe page of review rounds 1-7 (each string literal of the round test files
that reads as a page, harvested from their source) and the round-7 probes below: either the S6 call EQUALS the
baseline, or it carries an S6 ruling tag that is consistent with what changed. Every letter is invented
(`test_no_gitignored_corpus.py`)."""
import ast
import os

from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_issuers import unfingerprinted_offer
from apps.scholarship.genuineness.offer_rulings import (_folded_lines, confirmation_kind, private_proof, ruled_offer,
                                                         ruling_of)
from apps.scholarship.genuineness.results_doc import (MODEL_VERSION, baseline_genuineness, score_signatures,
                                                      signature_genuineness)

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND_FILES = ('test_offer_rulings.py', 'test_offer_s6_doors.py', 'test_offer_s6_review.py',
               'test_offer_s6_review2.py', 'test_offer_s6_review3.py', 'test_offer_s6_review4.py',
               'test_offer_s6_review5.py', 'test_offer_s6_review6.py', 'test_corpus_gaps_c1.py')
#: What each tag may do to the baseline.
LIFTS = {'tvet_offer', 'confirmation', 'incidental_company'}
SOFTENINGS = {'printout', 'tvet_slip'}


def _r(p, family='ua_offer'):
    return {'probability': p, 'type': family, 'present': [], 'missing': [], 'scores': {}}


def baseline_status(text, p=None, status=None, family='polytechnic'):
    """The pre-S6 call: of the whole scorer (no `p`), or of the 1.8.0 net for a test's own band (`p`, `status`)."""
    if p is None:
        return baseline_genuineness(text, score_signatures(text, doc_type='offer_letter'), 'offer_letter')['status']
    return unfingerprinted_offer(text, _r(p, family), status, 'r', MODEL_VERSION)['status']


def harvested_pages():
    """Every string literal of the round test files that reads as a page (2+ lines, no format placeholder)."""
    pages = set()
    for name in ROUND_FILES:
        with open(os.path.join(HERE, name), encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.count('\n') >= 1
                    and len(node.value) >= 20 and '{' not in node.value):
                pages.add(node.value)
    return sorted(pages)


def _letter(head, *, body='Kursus : Sijil Kemahiran Contoh\nTarikh lapor diri : 3 Ogos 2026\nTempat : {venue}\n',
            venue='IKBN Pekan', addressee='', foot=''):
    return (f'{head}\nJalan Contoh, 26600 Pekan\nTel : 09-000 0000\nRujukan : KBS.600-1/2/3\nTarikh : 1 Jun 2026\n'
            f'{addressee}Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\nTuan,\nSURAT TAWARAN KEMASUKAN\n'
            'Dengan sukacitanya dimaklumkan bahawa anda ditawarkan tempat.\n' + body.format(venue=venue)
            + 'Sila bawa dokumen asal semasa mendaftar.\nTawaran ini tertakluk kepada syarat.\n'
            f'Sekian, terima kasih.\nYang benar,\nPENGARAH\n{venue}\n{foot}')


def _confirm(head, *, title='PENGESAHAN PELAJAR', addressee=''):
    return (f'{head}\nJalan Contoh, 88400 Kota Kinabalu\nTel : 088-000000\nRujukan : RJ/600-1/2\nTarikh : 1 Jun 2026\n'
            f'{addressee}KEPADA SESIAPA YANG BERKENAAN\n{title}\nDengan ini disahkan bahawa:\nNama : Ali bin Abu\n'
            'No. Kad Pengenalan : 080808-10-5566\nProgram : Diploma Contoh\nSemester : 3\nSesi : 2026/2027\n'
            'Sekian, terima kasih.\nYang benar,\nPENGARAH\n')


#: Round 7's probes, as invented pages: each must NOT be newly blocked against its baseline.
ROUND7_NEVER_NEWLY_BLOCKED = {
    'JMTI above JTM': _letter('JAPAN-MALAYSIA TECHNICAL INSTITUTE (JMTI)\nJABATAN TENAGA MANUSIA', venue='JMTI'),
    'KEMAHlRAN OCR slip': _letter('INSTITUT KEMAHlRAN BELIA NEGARA PEKAN'),
    'NATIONAL YOUTH SKILL INSTITUTE': _letter('NATIONAL YOUTH SKILL INSTITUTE PEKAN'),
    'SKILLS MALAYSIA logo': _letter('SKILLS MALAYSIA\nJABATAN PEMBANGUNAN KEMAHIRAN\nIKBN PEKAN'),
    'English-only polytechnic': _confirm('POLYTECHNIC CONTOH\nMINISTRY OF HIGHER EDUCATION'),
    'UMS + ACADEMIC': _confirm('UNIVERSITI MALAYSIA SABAH\nACADEMIC SERVICES DIVISION'),
    'Tingkatan 6': _confirm('KOLEJ TINGKATAN 6 CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA'),
    'Yayasan addressee': _letter('INSTITUT KEMAHIRAN BELIA NEGARA PEKAN',
                                 addressee='YAYASAN CONTOH BERHAD\nJalan Dua, 50000 Kuala Lumpur\n'),
    'Persatuan addressee': _confirm('UNIVERSITI MALAYSIA SABAH',
                                    addressee='PERSATUAN CONTOH SDN BHD\nJalan Tiga, 88000 Kota Kinabalu\n'),
    'UMS Labuan': _confirm('UNIVERSITI MALAYSIA SABAH KAMPUS ANTARABANGSA LABUAN'),
    'Victoria Institution': _confirm('VICTORIA INSTITUTION\nKEMENTERIAN PENDIDIKAN MALAYSIA'),
    'Penang Free School': _confirm('PENANG FREE SCHOOL\nKEMENTERIAN PENDIDIKAN MALAYSIA'),
    'low title': ('POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI\n' + 'Maklumat am pelajar.\n' * 14
                  + 'PENGESAHAN PELAJAR\nNama : Ali bin Abu\n'),
    'Rujukan Tuan: Permohonan Tawaran Biasiswa': _letter(
        'INSTITUT KEMAHIRAN BELIA NEGARA PEKAN\nRujukan Tuan : Permohonan Tawaran Biasiswa'),
    'PENGESAHAN MURID': _confirm('SMK CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA', title='PENGESAHAN MURID'),
    'PENGESAHAN BERSEKOLAH': _confirm('SMK CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA', title='PENGESAHAN BERSEKOLAH'),
    'CONFIRMATION OF STUDENT STATUS': _confirm('UNIVERSITI MALAYSIA SABAH', title='CONFIRMATION OF STUDENT STATUS'),
    'SMJK': _confirm('SMJK CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA'),
    'SIRIM QAS footer': _letter('INSTITUT KEMAHIRAN BELIA NEGARA PEKAN', foot='SIRIM QAS International Sdn Bhd\n'),
    'SIRIM QAS beside the crest': _letter('INSTITUT KEMAHIRAN BELIA NEGARA PEKAN\nMS ISO 9001 SIRIM QAS Sdn Bhd'),
}
#: Round 7's probes that must NOT be lifted.
ROUND7_NEVER_LIFTED = {
    'a private name after a public word': _confirm('KEMENTERIAN PENDIDIKAN TINGGI\nKOLEJ ABC'),
    'a private name after the polytechnic': _confirm('POLITEKNIK CONTOH\nKOLEJ ABC'),
    'a private name after a TVET agency': _letter('JABATAN PEMBANGUNAN KEMAHIRAN\nABC SKILLS ACADEMY'),
    'a private letterhead, the institute in the body': _letter('ABC COLLEGE\nJalan Empat', venue='IKBN Pekan'),
    'a private confirmation, UMS in the body': _confirm('KOLEJ ABC').replace('Program :', 'Universiti Malaysia Sabah\n'
                                                                             'Program :'),
}


class TheProperty(SimpleTestCase):
    """For every probe page: the S6 call == the baseline, or a consistent tag."""

    def _check(self, text):
        b = baseline_status(text)
        out = signature_genuineness(text, doc_type='offer_letter')
        tag = ruling_of(out)
        if out['status'] == b:
            return
        self.assertTrue(tag, f'an untagged change {b} -> {out["status"]}')
        if tag == 'private_offer':
            self.assertEqual(out['status'], 'not_offer_letter')
            self.assertTrue(private_proof(_folded_lines(text)), 'a block without letterhead proof')
        elif tag in LIFTS:
            self.assertEqual(out['status'], 'genuine')
        else:
            self.assertIn(tag, SOFTENINGS)
            self.assertEqual((b, out['status']), ('not_offer_letter', 'suspect'))

    def test_every_round_1_to_7_probe_page(self):
        pages = harvested_pages() + list(ROUND7_NEVER_NEWLY_BLOCKED.values()) + list(ROUND7_NEVER_LIFTED.values())
        self.assertGreater(len(pages), 100)
        for text in pages:
            with self.subTest(page=text.splitlines()[0][:40]):
                self._check(text)

    def test_the_test_path_too(self):
        """`ruled_offer` (a band handed in) obeys the same property at every band."""
        for text in harvested_pages():
            for p, status in ((0.05, 'not_offer_letter'), (0.2, 'not_offer_letter'), (0.45, 'suspect')):
                out = ruled_offer(text, _r(p), status, 'r', MODEL_VERSION)
                b = unfingerprinted_offer(text, _r(p), status, 'r', MODEL_VERSION)['status']
                with self.subTest(page=text.splitlines()[0][:40], p=p):
                    self.assertTrue(out['status'] == b or ruling_of(out))
                    if out['status'] == 'not_offer_letter' and b != 'not_offer_letter':
                        self.assertTrue(private_proof(_folded_lines(text)))


class Round7Probes(SimpleTestCase):
    def test_none_is_newly_blocked(self):
        for name, text in ROUND7_NEVER_NEWLY_BLOCKED.items():
            with self.subTest(name):
                out = signature_genuineness(text, doc_type='offer_letter')
                if out['status'] == 'not_offer_letter':
                    self.assertEqual(baseline_status(text), 'not_offer_letter')
                self.assertNotEqual(ruling_of(out), 'private_offer')

    def test_none_is_lifted(self):
        for name, text in ROUND7_NEVER_LIFTED.items():
            with self.subTest(name):
                out = signature_genuineness(text, doc_type='offer_letter')
                self.assertNotIn(ruling_of(out), LIFTS)
                self.assertEqual(out['status'], baseline_status(text))

    def test_the_unclear_pages_keep_the_baseline_exactly(self):
        for name in ('KEMAHlRAN OCR slip', 'NATIONAL YOUTH SKILL INSTITUTE', 'Tingkatan 6', 'Victoria Institution',
                     'Penang Free School', 'low title', 'PENGESAHAN MURID', 'PENGESAHAN BERSEKOLAH',
                     'CONFIRMATION OF STUDENT STATUS', 'SMJK', 'SKILLS MALAYSIA logo'):
            text = ROUND7_NEVER_NEWLY_BLOCKED[name]
            with self.subTest(name):
                out = signature_genuineness(text, doc_type='offer_letter')
                self.assertEqual((out['status'], ruling_of(out)), (baseline_status(text), ''))

    def test_an_addressee_or_a_certification_is_never_letterhead_proof(self):
        for name in ('Yayasan addressee', 'Persatuan addressee', 'SIRIM QAS footer', 'SIRIM QAS beside the crest'):
            with self.subTest(name):
                self.assertEqual(private_proof(_folded_lines(ROUND7_NEVER_NEWLY_BLOCKED[name])), '')


class TheLifts(SimpleTestCase):
    def test_a_public_tvet_institute_offer(self):
        out = signature_genuineness(_letter('KEMENTERIAN BELIA DAN SUKAN\nINSTITUT KEMAHIRAN BELIA NEGARA PEKAN'),
                                    doc_type='offer_letter')
        self.assertEqual((out['status'], out['type'], ruling_of(out)), ('genuine', 'tvet_belia_sukan', 'tvet_offer'))

    def test_jmti_and_ciast_are_government_jtm_institutes(self):
        """Owner 2026-11-03 (decisions.md S6 item 8): each name, under the JTM parent line, lifts by the rules."""
        for head, venue in (('JABATAN TENAGA MANUSIA\nJAPAN-MALAYSIA TECHNICAL INSTITUTE', 'Japan-Malaysia Technical '
                                                                                            'Institute'),
                            ('JTM\nJMTI BUKIT CONTOH', 'JMTI Bukit Contoh'),
                            ('JABATAN TENAGA MANUSIA\nPUSAT LATIHAN PENGAJAR DAN KEMAHIRAN LANJUTAN', 'CIAST'),
                            ('JTM\nCIAST SHAH ALAM', 'CIAST Shah Alam')):
            with self.subTest(head=head):
                out = signature_genuineness(_letter(head, venue=venue), doc_type='offer_letter')
                self.assertEqual((out['status'], out['type'], ruling_of(out)), ('genuine', 'tvet_jtm', 'tvet_offer'))

    def test_jmti_and_ciast_need_the_same_proof(self):
        for head in ('JMTI\nABC TRAINING SDN BHD', 'CIAST\nRakan Strategik ABC'):
            with self.subTest(head=head):
                self.assertNotEqual(signature_genuineness(_letter(head, venue='JMTI'),
                                                          doc_type='offer_letter')['status'], 'genuine')
        thin = 'JABATAN TENAGA MANUSIA\nJMTI\nSURAT TAWARAN\nAnda ditawarkan kursus.\n'
        self.assertEqual(signature_genuineness(thin, doc_type='offer_letter')['status'], baseline_status(thin))

    def test_the_confirmations(self):
        for head, seen in (('POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI', 'confirmation_polytechnic'),
                           ('UNIVERSITI MALAYSIA SABAH', 'confirmation_ums'),
                           ('KOLEJ TINGKATAN ENAM CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA', 'confirmation_form6')):
            with self.subTest(head=head):
                self.assertEqual(confirmation_kind(_confirm(head), 0.2), seen)
                out = ruled_offer(_confirm(head), _r(0.2), 'not_offer_letter', 'r', MODEL_VERSION)
                self.assertEqual((out['status'], ruling_of(out)), ('genuine', 'confirmation'))

    def test_another_universitys_confirmation_keeps_its_baseline(self):
        text = _confirm('UNIVERSITI MALAYA')
        out = signature_genuineness(text, doc_type='offer_letter')
        self.assertEqual((out['status'], ruling_of(out)), (baseline_status(text), ''))


class TheBlock(SimpleTestCase):
    def test_letterhead_proof_blocks(self):
        for head in ('IKBN PEKAN\nABC TRAINING SDN BHD', 'GERMAN MALAYSIAN INSTITUTE', 'UNIVERSITI KUALA LUMPUR',
                     'UNIVERSITI MALAYSIA SABAH\nPUSAT PENDIDIKAN PROFESIONAL DAN LANJUTAN (PPPL)',
                     'KOLEJ ABC\nRakan Strategik IKBN', 'KOLEJ ABC\nIn collaboration with IKM'):
            with self.subTest(head=head):
                out = signature_genuineness(_letter(head), doc_type='offer_letter')
                self.assertEqual(out['status'], 'not_offer_letter')
                # the block's own tag, or the baseline already failed it (the pre-S6 "Sdn Bhd" veto)
                self.assertTrue(ruling_of(out) == 'private_offer' or baseline_status(_letter(head)) == 'not_offer_letter')
                self.assertTrue(private_proof(_folded_lines(_letter(head))))

    def test_a_body_company_is_no_block(self):
        text = _letter('INSTITUT KEMAHIRAN BELIA NEGARA PEKAN',
                       body='Kursus : Sijil Contoh\nTarikh lapor diri : 3 Ogos 2026\nPenaja : ABC Holdings Berhad\n')
        self.assertEqual(private_proof(_folded_lines(text)), '')
        self.assertNotEqual(ruling_of(signature_genuineness(text, doc_type='offer_letter')), 'private_offer')
