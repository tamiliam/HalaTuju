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
        # round 9: a company / tie-up counts only BEFORE the public name, a tie-up only beside an institution noun
        for head in ('ABC TRAINING SDN BHD\nIKBN PEKAN', 'GERMAN MALAYSIAN INSTITUTE', 'UNIVERSITI KUALA LUMPUR',
                     'UNIVERSITI MALAYSIA SABAH\nPUSAT PENDIDIKAN PROFESIONAL DAN LANJUTAN (PPPL)',
                     'KOLEJ ABC\nRakan Strategik : Kolej Contoh\nIKBN', 'KOLEJ ABC\nKerjasama dengan Universiti Contoh'):
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


# ── Review round 8 (2026-11-03): stricter, simpler overlays ─────────────────────────────────
IK = 'INSTITUT KEMAHIRAN BELIA NEGARA PEKAN'


def _r8(head, *, body='Kursus : Sijil Kemahiran Contoh\nTarikh lapor diri : 3 Ogos 2026\nTempat : IKBN Pekan\n',
        foot='', sign='PENGARAH\nIKBN Pekan\n'):
    return (f'{head}\nJalan Contoh, 26600 Pekan\nTel : 09-000 0000\nRujukan : KBS.600-1/2/3\nTarikh : 1 Jun 2026\n'
            'Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\nTuan,\nSURAT TAWARAN KEMASUKAN\n'
            'Dengan sukacitanya dimaklumkan bahawa anda ditawarkan tempat.\n' + body
            + 'Sila bawa dokumen asal semasa mendaftar.\nTawaran ini tertakluk kepada syarat.\n'
            f'Sekian, terima kasih.\nYang benar,\n{sign}{foot}')


_POLY8 = ('KEMENTERIAN PENDIDIKAN TINGGI\nJABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI\n{addr}'
          'Ruj. Kami : JPPKK/600-2/1\n{date}\n{addr2}SURAT TAWARAN PENGAJIAN\nNama : Ali bin Abu\n'
          'No. Kad Pengenalan : 080808-10-5566\nProgram : Diploma Kejuruteraan Contoh\nInstitusi : Politeknik Contoh\n'
          'Tarikh dan Masa Daftar : 3 Jul 2026\nTawaran ini adalah muktamad dan terbatal sekiranya anda tidak mendaftar '
          'di institusi\nTawaran ini tertakluk kepada kesahihan maklumat dalam borang permohonan\nSekian.\nPENGARAH\n')
_UA8 = ('UNIVERSITI PUTRA MALAYSIA\nPEJABAT PENDAFTAR\n{addr}Tarikh : {date} 2026\n'
        'TAWARAN KEMASUKAN KE PROGRAM PENGAJIAN DIPLOMA\nNama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\n'
        'Program Pengajian : Diploma Contoh\nTarikh pendaftaran : 3 Jul 2026\nPertukaran program adalah tidak '
        'dibenarkan\nTawaran ini adalah muktamad\nSekian.\nPENDAFTAR\n')
_ESTATE = 'ALI BIN ABU\nRUMAH PEKERJA, LADANG BUKIT CONTOH\nSIME CONTOH PLANTATION BERHAD\n31000 BATU GAJAH, PERAK\n'
_POLY_HEAD = _POLY8.format(addr='', date='Tarikh : 1 Jun 2026', addr2='')

#: Private pages a LIFT must never touch (H1 / H1b-d, H2 / H2b, M3).
ROUND8_NEVER_LIFTED = {
    'signed by a Sdn Bhd above an address': _r8(IK, sign='PENGARAH\nMERCU JAYA SDN BHD\n'
                                                        'No 5 Jalan Contoh Dua, 50450 Kuala Lumpur\n'),
    'fees to the operator company account': _r8(IK, body='Kursus : Sijil Contoh\nTarikh lapor diri : 3 Ogos 2026\n'
                                                     'Yuran RM3,000 hendaklah dibayar ke akaun MERCU JAYA SDN BHD '
                                                     '(Maybank)\n'),
    'Swasta beside a bank': _r8(IK, body='Kursus : Sijil Contoh\nTarikh lapor diri : 3 Ogos 2026\n'
                                     'Institusi latihan swasta bertauliah, bayaran ke akaun Bank Mercu\n'),
    'company footer with registration and address': _r8(IK, foot='MERCU JAYA SDN BHD (123456-X)\n'
                                                                 'Lot 5, Jalan Dua, 50450 Kuala Lumpur\n'),
    'company footer, Sendirian Berhad': _r8(IK, foot='MERCU JAYA SENDIRIAN BERHAD\n'
                                                     'Lot 5, Jalan Dua, 50450 Kuala Lumpur\n'),
    'company footer, Berhad only': _r8(IK, foot='MERCU JAYA BERHAD\nLot 5, Jalan Dua, 50450 Kuala Lumpur\n'),
    'company footer, no address': _r8(IK, foot='Dikeluarkan oleh MERCU JAYA SDN BHD\n'),
    'footer glued SDNBHD': _r8(IK, foot='Dikeluarkan oleh MERCU JAYA SDNBHD\n'),
    'footer S/B': _r8(IK, foot='Dikeluarkan oleh MERCU JAYA S/B\n'),
    'letterhead S/B under IKBN': _r8(IK + '\nMERCU JAYA S/B'),
    'footer company, postcode 3 lines down': _r8(IK, foot='MERCU JAYA SDN BHD\nTingkat 3, Wisma Contoh\nJalan Dua\n'
                                                         '50450 Kuala Lumpur\n'),
    'footer company, postcode 4 lines down': _r8(IK, foot='MERCU JAYA SDN BHD\nTingkat 3\nWisma Contoh\nJalan Dua\n'
                                                         '50450 Kuala Lumpur\n'),
    'ministry family + company footer with address': (_POLY_HEAD + 'MERCU JAYA SDN BHD\n'
                                                      'Lot 5, Jalan Dua, 50450 Kuala Lumpur\n'),
    'ministry family + company signs': _POLY_HEAD + 'MERCU JAYA SDN BHD\n',
}
#: Public pages the BLOCK must never touch (H3 / H3b-d, M1, M2).
ROUND8_NEVER_BLOCKED = {
    'poly, addressee before Ruj: estate Berhad': _POLY8.format(addr=_ESTATE, date='Tarikh : 1 Jun 2026', addr2=''),
    'poly, addressee before Ruj: Jalan Rakan': _POLY8.format(
        addr='ALI BIN ABU\nNO 3 JALAN RAKAN 2, TAMAN CONTOH\n31000 BATU GAJAH, PERAK\n', date='Tarikh : 1 Jun 2026',
        addr2=''),
    'poly, addressee d/a Koperasi Berhad': _POLY8.format(
        addr='ALI BIN ABU\nD/A FELCRA CONTOH BERHAD\n31000 BATU GAJAH, PERAK\n', date='Tarikh : 1 Jun 2026', addr2=''),
    'IKBN sponsor Berhad on the letterhead': _r8(IK + '\nPenaja : Petroliam Contoh Berhad'),
    'IKBN Program Latihan Kerjasama Industri': _r8(IK + '\nProgram Latihan Kerjasama Industri'),
    'UA addressee estate Berhad, odd date': _UA8.format(
        addr='ALI BIN ABU\nLADANG CONTOH, KUMPULAN CONTOH BERHAD\n31000 BATU GAJAH\n', date='1hb Jun'),
    'UA addressee estate Berhad, normal date': _UA8.format(
        addr='ALI BIN ABU\nLADANG CONTOH, KUMPULAN CONTOH BERHAD\n31000 BATU GAJAH\n', date='1 Jun'),
    'poly Ruj + date first, estate Berhad': _POLY8.format(addr='', date='Tarikh : 1 Jun 2026', addr2=_ESTATE),
    'poly Ruj first, no date, estate Berhad': _POLY8.format(addr='', date='', addr2=_ESTATE).replace('\n\n', '\n'),
    'poly, 5-line address, Berhad 4 above the postcode': _POLY8.format(
        addr='', date='Tarikh : 1 Jun 2026', addr2='ALI BIN ABU\nSIME CONTOH PLANTATION BERHAD\nRUMAH PEKERJA NO 3\n'
                                                   'LADANG BUKIT CONTOH\nBATU GAJAH\n31000 PERAK\n'),
    'poly English date, estate Berhad': _POLY8.format(addr='', date='Date : June 1, 2026', addr2=_ESTATE).replace(
        'Ruj. Kami : JPPKK/600-2/1\n', ''),
}


class Round8(SimpleTestCase):
    def test_the_lift_has_almost_no_excuses(self):
        for name, text in ROUND8_NEVER_LIFTED.items():
            with self.subTest(name):
                out = signature_genuineness(text, doc_type='offer_letter')
                self.assertNotIn(ruling_of(out), LIFTS)
                self.assertNotEqual(out['status'], 'genuine')

    def test_the_block_reads_only_the_true_letterhead(self):
        for name, text in ROUND8_NEVER_BLOCKED.items():
            with self.subTest(name):
                out = signature_genuineness(text, doc_type='offer_letter')
                self.assertEqual(private_proof(_folded_lines(text)), '')
                self.assertEqual((out['status'], ruling_of(out)), (baseline_status(text), ''))

    def test_a_company_on_the_letterhead_in_any_spelling_still_blocks(self):
        for company in ('MERCU JAYA S/B', 'MERCU JAYA SDNBHD', 'MERCU JAYA SDN. BHD.', 'MERCU JAYA SENDIRIAN BERHAD'):
            with self.subTest(company):
                # round 9 (M1): the company BEFORE the public name; after it, it reads as an addressee
                self.assertEqual(private_proof(_folded_lines(_r8(company + '\n' + IK))), 'company')
                self.assertEqual(private_proof(_folded_lines(_r8(IK + '\n' + company))), '')

    def test_a_closed_list_bank_line_is_the_only_finance_excuse(self):
        from apps.scholarship.genuineness.offer_rulings import _bank_line
        for ln in ('Bayaran ke akaun Maybank Berhad', 'CIMB Bank Berhad', 'Bank Islam Malaysia Berhad',
                   'Public Bank Berhad', 'Hong Leong Islamic Bank Berhad'):
            with self.subTest(ln):
                self.assertTrue(_bank_line(_folded_lines(ln)[0]))
        for ln in ('dibayar ke akaun MERCU JAYA SDN BHD (Maybank)', 'Takaful Contoh Berhad', 'Koperasi Contoh Berhad',
                   'Bayaran ke akaun Bank Mercu Berhad'):
            with self.subTest(ln):
                self.assertFalse(_bank_line(_folded_lines(ln)[0]))

    def test_round8_pages_obey_the_property(self):
        for text in list(ROUND8_NEVER_LIFTED.values()) + list(ROUND8_NEVER_BLOCKED.values()):
            with self.subTest(text.splitlines()[0][:40]):
                TheProperty._check(self, text)

    def test_a_long_page_stays_fast(self):
        import time
        text = 'INSTITUT KEMAHIRAN BELIA NEGARA\nSURAT TAWARAN\n' + ''.join(
            f'Baris {i} ABC SDN BHD contoh\n' for i in range(4000))
        t0 = time.perf_counter()
        signature_genuineness(text, doc_type='offer_letter')
        self.assertLess(time.perf_counter() - t0, 5.0)


# ── Review round 9 (2026-11-03): stricter again, no new guesses ──────────────────────────────
def _l9(head, addressee='', body='Kursus : Sijil Kemahiran Contoh\nTarikh lapor diri : 3 Ogos 2026\nTempat : {venue}\n',
        venue='IKBN Pekan', foot='', addr='Jalan Contoh, 26600 Pekan\n'):
    return (f'{head}\n{addr}Tel : 09-000 0000\nRujukan : KBS.600-1/2/3\nTarikh : 1 Jun 2026\n'
            f'{addressee}Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\nTuan,\nSURAT TAWARAN KEMASUKAN\n'
            'Dengan sukacitanya dimaklumkan bahawa anda ditawarkan tempat.\n' + body.format(venue=venue)
            + 'Sila bawa dokumen asal semasa mendaftar.\nTawaran ini tertakluk kepada syarat.\n'
            f'Sekian, terima kasih.\nYang benar,\nPENGARAH\n{venue}\n{foot}')


def _c9(head, title='PENGESAHAN PELAJAR', prog='Program : Diploma Contoh\nSemester : 3\nSesi : 2026/2027\n'):
    return (f'{head}\nJalan Contoh, 88400 Kota Kinabalu\nTel : 088-000000\nRujukan : RJ/600-1/2\nTarikh : 1 Jun 2026\n'
            f'KEPADA SESIAPA YANG BERKENAAN\n{title}\nDengan ini disahkan bahawa:\nNama : Ali bin Abu\n'
            'No. Kad Pengenalan : 080808-10-5566\n' + prog + 'Sekian, terima kasih.\nYang benar,\nPENGARAH\n')


_REST9 = ('Rujukan : KBS.600-1/2/3\nTarikh : 1 Jun 2026\nNama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\n'
          'Tuan,\nSURAT TAWARAN KEMASUKAN\nDengan sukacitanya dimaklumkan bahawa anda ditawarkan tempat.\n'
          'Kursus : Sijil Kemahiran Contoh\nTarikh lapor diri : 3 Ogos 2026\nTempat : IKBN Pekan\n'
          'Sila bawa dokumen asal semasa mendaftar.\nTawaran ini tertakluk kepada syarat.\nSekian, terima kasih.\n'
          'Yang benar,\nPENGARAH\nIKBN Pekan\n')
_MARA_LOAN = ('MAJLIS AMANAH RAKYAT (MARA)\nBahagian Pembiayaan Pelajaran\nJalan Raja Laut, 50609 Kuala Lumpur\n'
              'Tel : 03-0000 0000\nRujukan : MARA/PP/600-1\nTarikh : 1 Jun 2026\nNama : Ali bin Abu\n'
              'No. Kad Pengenalan : 080808-10-5566\nTuan,\nSURAT TAWARAN PEMBIAYAAN PENDIDIKAN\n'
              'Dengan sukacitanya dimaklumkan bahawa anda ditawarkan pembiayaan pendidikan.\n'
              'Program : Diploma Kejuruteraan\nInstitusi : Institut Kemahiran MARA Kuantan\n'
              'Sila hadir ke pejabat MARA negeri untuk menandatangani perjanjian.\n'
              'Pembiayaan ini tertakluk kepada syarat.\nSekian, terima kasih.\nYang benar,\nPENGARAH\n'
              'Bahagian Pembiayaan Pelajaran\n')

#: Pages a LIFT must never touch (H1, H2, M2, M3, the body tie-up).
ROUND9_NEVER_LIFTED = {
    'private name, JPK accredited centre': _l9('MERCU JAYA\nPUSAT BERTAULIAH JABATAN PEMBANGUNAN KEMAHIRAN'),
    'private name under the JPK line': _l9('MERCU JAYA\nJABATAN PEMBANGUNAN KEMAHIRAN'),
    'accredited centre, IKBN only in a later line': _l9(
        'MERCU JAYA\nPUSAT BERTAULIAH JPK', venue='Mercu Jaya',
        body='Kursus : Sijil Kemahiran Malaysia\nTarikh lapor diri : 3 Ogos 2026\nTempat : Mercu Jaya\n'
             'Peperiksaan di IKBN Pekan\n'),
    'ministry letterhead, IKBN only in the body': _l9('KEMENTERIAN BELIA DAN SUKAN MALAYSIA'),
    'MARA financing letter': _MARA_LOAN,
    'MARA loan letter': _MARA_LOAN.replace('SURAT TAWARAN PEMBIAYAAN PENDIDIKAN', 'SURAT TAWARAN PINJAMAN PELAJARAN'),
    'SMK Form 5 confirmation': _c9('SMK CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA',
                                   prog='Tingkatan : 5 Sains\nJurusan : Sains Tulen\nSesi Pengajian : 2025\n'),
    'SMK Form 4, no ministry line': _c9('SEKOLAH MENENGAH KEBANGSAAN CONTOH\nJALAN SEKOLAH',
                                        title='SURAT PENGESAHAN PELAJAR',
                                        prog='Tingkatan : 4 Sains\nJurusan : Sains\nSesi Pengajian : 2026\n'),
    'SMK Form 3, a Bidang line': _c9('SEKOLAH MENENGAH KEBANGSAAN CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA',
                                     prog='Kelas : Tingkatan 3 Cempaka\nBidang : Tiada\nSesi : 2026\n'),
    'UMS PPPL in English, OCR-garbled': _c9('UNIVERSITI MALAYSIA SABAH\nCENTRE FOR PROFESSIONAL AND CONTINUlNG EDUCATION'),
    'UMS PPPL with an ampersand': _c9('UNIVERSITI MALAYSIA SABAH\nPUSAT PENDIDIKAN PROFESIONAL & LANJUTAN'),
    'UMS, PPPL in the body': _c9('UNIVERSITI MALAYSIA SABAH', prog='Program : Diploma Pengurusan (Pusat Pendidikan '
                                                                  'Profesional & Lanjutan)\nSemester : 3\nSesi : 2026/2027\n'),
    'polytechnic, a private college partner in the body': _c9(
        'POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI',
        prog='Program : Diploma Kejuruteraan\nTempat pengajian : Kolej ABC (rakan industri)\nSemester : 3\n'),
    'a private academy on a contact line': _l9('INSTITUT KEMAHIRAN BELIA NEGARA PEKAN\nABC SKILLS ACADEMY  '
                                               'Tel : 09-111 2222  www.abcskills.com'),
    'a private academy first, on a contact line': _l9('ABC SKILLS ACADEMY Tel 09-111 2222\n'
                                                      'INSTITUT KEMAHIRAN BELIA NEGARA PEKAN'),
}
#: Pages the BLOCK must never touch (M1, the narrowed tie-up, S/B in an address).
ROUND9_NEVER_BLOCKED = {
    'no-postcode head, a d/a Yayasan addressee': ('INSTITUT KEMAHIRAN BELIA NEGARA PEKAN\nPeti Surat 12, Pekan, Pahang\n'
                                                  'TAN WEI MING\nd/a YAYASAN CONTOH BERHAD\n'
                                                  'Jalan Dua, 50000 Kuala Lumpur\n' + _REST9),
    'two columns: the addressee read before the head address': (
        'INSTITUT KEMAHIRAN BELIA NEGARA PEKAN\nPengurus\nKOPERASI CONTOH BERHAD\nLot 5, 26600 Pekan\n'
        'Jalan Contoh, 26600 Pekan\n' + _REST9),
    'an industry partner group on the letterhead': ('INSTITUT LATIHAN PERINDUSTRIAN KUANTAN\nRakan Industri : Contoh '
                                                    'Group\nJalan Contoh, 25000 Kuantan\n'
                                                    + _REST9.replace('IKBN', 'ILP')),
    'S.B. in the head address': ('INSTITUT LATIHAN PERINDUSTRIAN KUANTAN\nLot 3, Kawasan Perindustrian S.B. Jaya, '
                                 '25000 Kuantan\n' + _REST9.replace('IKBN', 'ILP')),
    'IKBN, a company in the addressee block': _l9('INSTITUT KEMAHIRAN BELIA NEGARA PEKAN',
                                                  addressee='MERCU JAYA SDN BHD\nLot 5, 26600 Pekan\n'),
}


class Round9(SimpleTestCase):
    def test_the_lift_needs_the_institute_itself_and_an_admission(self):
        for name, text in ROUND9_NEVER_LIFTED.items():
            with self.subTest(name):
                out = signature_genuineness(text, doc_type='offer_letter')
                self.assertNotIn(ruling_of(out), LIFTS)
                self.assertEqual(out['status'], baseline_status(text))

    def test_the_block_proof_comes_before_the_public_name(self):
        for name, text in ROUND9_NEVER_BLOCKED.items():
            with self.subTest(name):
                out = signature_genuineness(text, doc_type='offer_letter')
                self.assertEqual(private_proof(_folded_lines(text)), '')
                self.assertNotEqual(ruling_of(out), 'private_offer')

    def test_what_still_blocks_and_lifts(self):
        self.assertEqual(private_proof(_folded_lines(_l9('MERCU JAYA S/B\nINSTITUT KEMAHIRAN BELIA NEGARA'))),
                         'company')
        self.assertEqual(private_proof(_folded_lines(_l9('KOLEJ ABC\nRakan Strategik : Universiti Contoh'))),
                         'tie-up wording')
        self.assertEqual(private_proof(_folded_lines(_c9('UNIVERSITI MALAYSIA SABAH\nPUSAT PENDIDIKAN PROFESIONAL'
                                                         ' & LANJUTAN'))), 'named private body')
        out = signature_genuineness(_l9('INSTITUT KEMAHIRAN BELIA NEGARA PEKAN'), doc_type='offer_letter')
        self.assertEqual((out['status'], ruling_of(out)), ('genuine', 'tvet_offer'))
        form6 = _c9('KOLEJ TINGKATAN ENAM CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA')
        self.assertEqual(confirmation_kind(form6, 0.2), 'confirmation_form6')
        smk6 = _c9('SMK CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA', prog='Tingkatan : 6 Atas\nTINGKATAN 6\nSesi : 2026\n')
        self.assertEqual(confirmation_kind(smk6, 0.2), 'confirmation_form6')

    def test_round9_pages_obey_the_property(self):
        for text in list(ROUND9_NEVER_LIFTED.values()) + list(ROUND9_NEVER_BLOCKED.values()):
            with self.subTest(text.splitlines()[0][:40]):
                TheProperty._check(self, text)

    def test_a_long_one_line_unit_prefix_stays_fast(self):
        import time
        text = 'INSTITUT KEMAHIRAN BELIA NEGARA\n' + ' '.join(['ACADEMIC STUDENT'] * 3000) + '\nTAWARAN\n'
        t0 = time.perf_counter()
        signature_genuineness(text, doc_type='offer_letter')
        self.assertLess(time.perf_counter() - t0, 2.0)
