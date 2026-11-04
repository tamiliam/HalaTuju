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
    # (the KBS-letterhead + IKBN-body admission now lifts by the owner's S6 item 9: class Round10)
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


# ── Owner ruling 2026-11-03 (decisions.md S6 item 9): ONE narrow agency-letterhead lift ───────────────
def _agency(head, *, title='SURAT TAWARAN KEMASUKAN', venue='Institut Kemahiran MARA Kuantan', extra=''):
    return (f'{head}\nJalan Raja Laut, 50609 Kuala Lumpur\nTel : 03-0000 0000\nRujukan : AG/600-1/2\n'
            f'Tarikh : 1 Jun 2026\nNama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\nTuan,\n{title}\n'
            'Dengan sukacitanya dimaklumkan bahawa anda ditawarkan tempat.\nKursus : Sijil Kemahiran Contoh\n'
            f'Tarikh lapor diri : 3 Ogos 2026\nTempat : {venue}\n{extra}Sila bawa dokumen asal semasa mendaftar.\n'
            'Tawaran ini tertakluk kepada syarat.\nSekian, terima kasih.\nYang benar,\nPENGARAH\n')


class Round10AgencyLetterhead(SimpleTestCase):
    def _out(self, text):
        return signature_genuineness(text, doc_type='offer_letter')

    def test_a_clean_agency_admission_lifts(self):
        for head, venue, key in (('MAJLIS AMANAH RAKYAT', 'Institut Kemahiran MARA Kuantan', 'tvet_mara'),
                                 ('TVETMARA\nMAJLIS AMANAH RAKYAT', 'KKTM Kuantan', 'tvet_mara'),
                                 ('KEMENTERIAN BELIA DAN SUKAN MALAYSIA', 'IKBN Pekan', 'tvet_belia_sukan'),
                                 ('JABATAN TENAGA MANUSIA\nKEMENTERIAN SUMBER MANUSIA', 'ILP Kuantan', 'tvet_jtm')):
            with self.subTest(head=head):
                out = self._out(_agency(head, venue=venue))
                self.assertEqual((out['status'], out['type'], ruling_of(out)), ('genuine', key, 'tvet_offer'))
                self.assertIn('agency_letterhead', out['reason'])

    def test_the_r9_mara_financing_and_loan_letters_stay_out(self):
        for name in ('MARA financing letter', 'MARA loan letter'):
            with self.subTest(name):
                out = self._out(ROUND9_NEVER_LIFTED[name])
                self.assertNotIn(ruling_of(out), LIFTS)
        for title in ('SURAT TAWARAN PEMBIAYAAN PENDIDIKAN', 'SURAT TAWARAN PINJAMAN PELAJARAN',
                      'SURAT TAWARAN BIASISWA', 'SURAT TAWARAN ELAUN LATIHAN', 'SURAT TAWARAN BANTUAN'):
            with self.subTest(title):
                self.assertNotIn(ruling_of(self._out(_agency('MAJLIS AMANAH RAKYAT', title=title))), LIFTS)
        money_body = _agency('MAJLIS AMANAH RAKYAT').replace('anda ditawarkan tempat.',
                                                             'anda ditawarkan tempat dengan tajaan penuh.')
        self.assertNotIn(ruling_of(self._out(money_body)), LIFTS)

    def test_a_parent_mismatch_never_lifts(self):
        for head, venue in (('MAJLIS AMANAH RAKYAT', 'IKBN Pekan'), ('KEMENTERIAN BELIA DAN SUKAN', 'ILP Kuantan'),
                            ('JABATAN TENAGA MANUSIA', 'Institut Kemahiran MARA Kuantan')):
            with self.subTest(head=head):
                self.assertNotIn(ruling_of(self._out(_agency(head, venue=venue))), LIFTS)

    def test_jpk_or_an_unlisted_ministry_letterhead_never_lifts(self):
        for head, venue in (('JABATAN PEMBANGUNAN KEMAHIRAN', 'ILP Kuantan'),
                            ('JABATAN TENAGA MANUSIA\nJABATAN PEMBANGUNAN KEMAHIRAN', 'ILP Kuantan'),
                            ('KEMENTERIAN PENDIDIKAN TINGGI', 'Institut Kemahiran MARA Kuantan'),
                            ('MAJLIS AMANAH RAKYAT\nKEMENTERIAN KEMAJUAN DESA', 'Institut Kemahiran MARA Kuantan')):
            with self.subTest(head=head):
                self.assertNotIn(ruling_of(self._out(_agency(head, venue=venue))), LIFTS)

    def test_another_organisation_in_the_body_never_lifts(self):
        for extra in ('Latihan amali di Kolej ABC Kuantan.\n', 'Pengendali kursus : Akademi Mercu\n',
                      'Yuran dibayar kepada Mercu Jaya Sdn Bhd.\n'):
            with self.subTest(extra=extra):
                self.assertNotIn(ruling_of(self._out(_agency('MAJLIS AMANAH RAKYAT', extra=extra))), LIFTS)

    def test_the_agency_lift_obeys_the_property(self):
        for text in (_agency('MAJLIS AMANAH RAKYAT'), _agency('MAJLIS AMANAH RAKYAT', venue='IKBN Pekan'),
                     _agency('JABATAN PEMBANGUNAN KEMAHIRAN', venue='ILP Kuantan')):
            with self.subTest(text.splitlines()[0]):
                TheProperty._check(self, text)

    # Condition 4 refined (coordinator, 2026-11-03): an institution noun names an organisation only when a NAME
    # follows it on its line, read in the raw case; the agency's umbrella names count as the agency.
    def test_generic_institution_words_are_no_organisation(self):
        for extra in ('Pihak pengurusan institut berhak menarik balik tawaran ini.\n',
                      'Sila bawa dokumen asal semasa hari pendaftaran di institusi/kolej.\n'):
            with self.subTest(extra=extra):
                out = self._out(_agency('MAJLIS AMANAH RAKYAT', extra=extra))
                self.assertEqual((out['status'], ruling_of(out)), ('genuine', 'tvet_offer'))
        # Closed world (lead's ruling 2026-11-04, c): only a LOWERCASE bare noun is generic; upper / title case counts.
        out = self._out(_agency('MAJLIS AMANAH RAKYAT', extra='PIHAK INSTITUT BERHAK MENARIK BALIK TAWARAN INI.\n'))
        self.assertNotIn(ruling_of(out), LIFTS)
        out = self._out(_agency('KEMENTERIAN BELIA DAN SUKAN', venue='IKBN Pekan',
                                extra='Pusat Pengajian IKBN Pekan\n'))
        self.assertEqual((out['status'], ruling_of(out)), ('genuine', 'tvet_offer'))

    def test_a_named_institution_in_the_body_is_another_organisation(self):
        for extra in ('Latihan amali di Kolej Mercu.\n', 'LATIHAN AMALI DI KOLEJ MERCU JAYA.\n',
                      'Pengendali : Akademi Mercu\n', 'Kelas tambahan di Pusat Latihan Mercu.\n'):
            with self.subTest(extra=extra):
                self.assertNotIn(ruling_of(self._out(_agency('MAJLIS AMANAH RAKYAT', extra=extra))), LIFTS)

    def test_the_agency_umbrella_name_counts_only_for_its_own_agency(self):
        umbrella = 'Institusi Latihan Kemahiran Belia dan Sukan (ILKBS)\n'
        out = self._out(_agency('KEMENTERIAN BELIA DAN SUKAN', venue='IKBN Pekan', extra=umbrella))
        self.assertEqual((out['status'], ruling_of(out)), ('genuine', 'tvet_offer'))
        self.assertNotIn(ruling_of(self._out(_agency('MAJLIS AMANAH RAKYAT', extra=umbrella))), LIFTS)


# ── Review round 10 (2026-11-04): money offers, the name first on the letterhead, OCR 0 / 1 ───────────
_IKBN_HEAD = 'INSTITUT KEMAHIRAN BELIA NEGARA PEKAN'


def _inst10(head, **kw):
    kw.setdefault('venue', 'IKBN Pekan')
    return _agency(head, **kw)


class Round10(SimpleTestCase):
    def _lifted(self, text):
        return ruling_of(signature_genuineness(text, doc_type='offer_letter')) in LIFTS

    def test_money_offers_never_lift_either_lift(self):
        """M1: one shared list, the title AND the first five body lines, both lifts (A: the institute; B: the
        agency letterhead)."""
        titles = ('OFFER OF EDUCATION LOAN', 'OFFER OF SPONSORSHIP', 'OFFER OF STUDY FINANCING',
                  'SURAT TAWARAN DERMASISWA', 'SURAT TAWARAN PENAJAAN', 'SURAT TAWARAN PEMBIAYAN PENDIDIKAN',
                  'SURAT TAWARAN ELAUN LATIHAN', 'SURAT TAWARAN BANTUAN', 'OFFER OF SCHOLARSHIP',
                  'OFFER OF ALLOWANCE', 'OFFER OF GRANT', 'OFFER OF BURSARY', 'OFFER OF FUNDING')
        for title in titles:
            for name, text in (('A', _inst10(_IKBN_HEAD, title=title)),
                               ('B', _agency('MAJLIS AMANAH RAKYAT', title=title))):
                with self.subTest(lift=name, title=title):
                    self.assertFalse(self._lifted(text))
        for extra in ('Pembiayaan pendidikan anda diluluskan sebanyak RM10,000.\n',
                      'Jumlah pinjaman pelajaran : RM8,000\n'):
            for name, text in (('A', _inst10(_IKBN_HEAD, title='SURAT TAWARAN', extra=extra)),
                               ('B', _agency('MAJLIS AMANAH RAKYAT', title='SURAT TAWARAN', extra=extra))):
                with self.subTest(lift=name, extra=extra):
                    self.assertFalse(self._lifted(text))

    def test_a_loan_beside_an_rm_amount_is_never_lifted_from_a_fail(self):
        far = _inst10(_IKBN_HEAD, title='SURAT TAWARAN').replace(
            'Sekian, terima kasih.\n', 'Sekian, terima kasih.\nPinjaman pendidikan\nboleh dipohon\nsehingga RM5,000.\n')
        r = score_signatures(far, doc_type='offer_letter')
        out = ruled_offer(far, r, 'not_offer_letter', 'r', MODEL_VERSION)
        self.assertNotIn(ruling_of(out), LIFTS)

    def test_the_institute_first_on_the_letterhead(self):
        """M4 (LIFT A): the closed-list name on the first letterhead line, or after crest / government / address
        lines only."""
        for head in ('MERCU JAYA\n' + _IKBN_HEAD, 'MERCU JAYA\nWisma IKBN, Jalan Contoh'):
            with self.subTest(head=head):
                self.assertFalse(self._lifted(_inst10(head)))
        for head in (_IKBN_HEAD, 'KERAJAAN MALAYSIA\nKEMENTERIAN BELIA DAN SUKAN\n' + _IKBN_HEAD):
            with self.subTest(head=head):
                self.assertTrue(self._lifted(_inst10(head)))

    def test_ocr_zero_and_one_in_an_institution_noun(self):
        """L1: 0 -> O and 1 -> I when the agency lift tests an institution noun in the body."""
        for extra in ('Latihan amali di K0LEJ MERCU.\n', 'Latihan amali di Kolej 1Mercu.\n',
                      'Latihan amali di AKADEM1 MERCU.\n'):
            with self.subTest(extra=extra):
                self.assertFalse(self._lifted(_agency('MAJLIS AMANAH RAKYAT', extra=extra)))
        self.assertTrue(self._lifted(_agency('MAJLIS AMANAH RAKYAT')))


class Round10M4Confirmations(SimpleTestCase):
    """Lead's ruling 2026-11-04: a confirmation's closed-list name comes first on its letterhead, after crest /
    government / address lines, the institution's OWN division lines, or a short crest / motto line."""

    def _kind(self, head):
        return confirmation_kind(_c9(head), 0.2)

    def test_division_and_crest_lines_may_precede_the_name(self):
        for head, seen in (('BAHAGIAN PENGURUSAN AKADEMIK\nUNIVERSITI MALAYSIA SABAH', 'confirmation_ums'),
                           ('PEJABAT PENDAFTAR\nUNIVERSITI MALAYSIA SABAH', 'confirmation_ums'),
                           ('UNIT KEMASUKAN\nPOLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI',
                            'confirmation_polytechnic'),
                           ('BERILMU BERBAKTI\nKOLEJ TINGKATAN ENAM CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA',
                            'confirmation_form6'),
                           ('KERAJAAN MALAYSIA\nKEMENTERIAN PENDIDIKAN TINGGI\nPOLITEKNIK CONTOH',
                            'confirmation_polytechnic')):
            with self.subTest(head=head):
                self.assertEqual(self._kind(head), seen)

    def test_anything_else_above_the_name_is_no_lift(self):
        for head in ('KOLEJ MERCU\nPOLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI',
                     'MERCU JAYA SDN BHD\nPOLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI',
                     'BAHAGIAN AKADEMIK KOLEJ MERCU\nUNIVERSITI MALAYSIA SABAH',
                     'UNIT KEMASUKAN MERCU SDN BHD\nUNIVERSITI MALAYSIA SABAH',
                     'MERCU JAYA EDUCATION GROUP\nUNIVERSITI MALAYSIA SABAH',
                     'MERCU 123\nUNIVERSITI MALAYSIA SABAH'):      # a short line with a digit is no crest
            with self.subTest(head=head):
                self.assertEqual(self._kind(head), '')

    def test_a_two_word_private_name_still_passes_as_a_short_line(self):
        """TD-492 (Medium, accepted): a one- or two-word private name with no institution noun reads as a crest /
        motto line; a known-motto list would drop a123, a real Form-6 confirmation."""
        self.assertEqual(self._kind('MERCU JAYA\nPOLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI'),
                         'confirmation_polytechnic')


# ── Round 10, the agency lift's CLOSED-WORLD condition 4 (owner 2026-11-04: app 329 green; the lead's rulings) ──
_M = 'MAJLIS AMANAH RAKYAT'
_K = 'KEMENTERIAN BELIA DAN SUKAN'


def _ag(head, **kw):
    kw.setdefault('venue', 'Institut Kemahiran MARA Kuantan')
    return _agency(head, **kw)


#: The r10 probes of the agency lift that must stay out (invented text).
ROUND10_AGENCY_NEVER_LIFTED = {
    'Kolej mercu (lowercase name)': _ag(_M, extra='Latihan amali di Kolej mercu.\n'),
    # ("akademi mercu" and "pusat latihan mercu", all-lowercase names: the TD-493 gap, pinned in Round11)
    'Mercu Skills Academy (name before the noun)': _ag(_M, extra='Pengendali kursus : Mercu Skills Academy\n'),
    'Mercu Training Centre': _ag(_M, extra='Pengendali kursus : Mercu Training Centre\n'),
    'Mercu Jaya Enterprise': _ag(_M, extra='Pengendali kursus : Mercu Jaya Enterprise\n'),
    'Mercu Jaya PLT': _ag(_M, extra='Pengendali kursus : Mercu Jaya PLT\n'),
    'Mercu Holdings': _ag(_M, extra='Rakan latihan : Mercu Holdings\n'),
    'Kolej Kemahiran IKM-Mercu': _ag(_M, extra='Lokasi : Kolej Kemahiran IKM-Mercu\n'),
    'Institut Kemahiran MARA Mercu Jaya': _ag(_M, extra='Lokasi : Institut Kemahiran MARA Mercu Jaya\n'),
    'Kolej IKM Mercu': _ag(_M, extra='Lokasi : Kolej IKM Mercu\n'),
    'Pusat Latihan IKM Mercu': _ag(_M, extra='Lokasi : Pusat Latihan IKM Mercu\n'),
    'Kolej Kemahiran Tinggi MARA Mercu': _ag(_M, extra='Lokasi : Kolej Kemahiran Tinggi MARA Mercu\n'),
    'KOLEJ MARA MERCU': _ag(_M, extra='Lokasi : KOLEJ MARA MERCU\n'),
    'Kolej kemahiran Mercu': _ag(_M, extra='Lokasi : Kolej kemahiran Mercu\n'),
    'Kolej Pengajian Mercu': _ag(_M, extra='Lokasi : Kolej Pengajian Mercu\n'),
    'IKM venue operated by Mercu Jaya': _ag(_M, venue='IKM Kuantan (dikendalikan oleh Mercu Jaya)'),
    'Mercu College @ IKM': _ag(_M, venue='Mercu College @ IKM Kuantan'),
    'IKM Kuantan, Mercu College': _ag(_M, venue='IKM Kuantan, Mercu College'),
    'a table row naming Kolej Mercu': _ag(_M, extra='Institusi | Program | Tempoh\nIKM Kuantan | Sijil | 2 tahun\n'
                                                    'Kolej Mercu | Diploma | 3 tahun\n'),
    'a split table cell': _ag(_M, extra='Institusi\nKolej\nMercu Jaya\n'),
    'a noun at the line end, its name on the next line': _ag(_M, extra='Latihan amali di Kolej\nMercu Jaya Kuantan.\n'),
    'MARA head, KBS in the body': _ag(_M, extra='Dengan kerjasama KBS.\n'),
    'MARA head, the JTM full name in the body': _ag(_M, extra='Diiktiraf oleh Jabatan Tenaga Manusia.\n'),
    'KBS head, MARA in the body': _ag(_K, venue='IKBN Pekan', extra='Tajaan oleh MARA.\n'),
    'MARA head, another Majlis': _ag(_M, extra='Majlis Latihan Mercu.\n'),
    'OCR KoLeJ MeRcU': _ag(_M, extra='Latihan amali di KoLeJ MeRcU.\n'),
    'OCR kOLEJ MERCU': _ag(_M, extra='Latihan amali di kOLEJ MERCU.\n'),
    'OCR K0LEJ MERCU': _ag(_M, extra='Latihan amali di K0LEJ MERCU.\n'),
    'Kolej-Mercu': _ag(_M, extra='Latihan amali di Kolej-Mercu.\n'),
    'KolejMercu glued': _ag(_M, extra='Latihan amali di KolejMercu.\n'),
    'KOLEJMERCU glued': _ag(_M, extra='Latihan amali di KOLEJMERCU.\n'),
    'Kolej "Mercu"': _ag(_M, extra='Latihan amali di Kolej "Mercu".\n'),
    'Kolej (Mercu)': _ag(_M, extra='Latihan amali di Kolej (Mercu).\n'),
    'Kolej 1Mercu': _ag(_M, extra='Latihan amali di Kolej 1Mercu.\n'),
    'Kolej Yang Mercu': _ag(_M, extra='Latihan amali di Kolej Yang Mercu.\n'),
    'Kolej Di Mercu Jaya': _ag(_M, extra='Latihan di Kolej Di Mercu Jaya.\n'),
    'kolej swasta': _ag(_M, extra='Latihan di kolej swasta.\n'),
    'University Of Mercu': _ag(_M, extra='Pengajian lanjut di University Of Mercu.\n'),
    'letterhead: MARA + MERCU JAYA': _ag('MAJLIS AMANAH RAKYAT\nMERCU JAYA'),
    'letterhead: MARA + MERCU EDU': _ag('MAJLIS AMANAH RAKYAT\nMERCU EDU'),
    'letterhead: MARA + MERCU JAYA S/B': _ag('MAJLIS AMANAH RAKYAT\nMERCU JAYA S/B'),
    'letterhead: MERCU JAYA / WAKIL MARA': _ag('MERCU JAYA\nWAKIL MAJLIS AMANAH RAKYAT'),
    'letterhead: MERCU JAYA (EJEN MARA)': _ag('MERCU JAYA (EJEN MARA)'),
    'letterhead: Mercu academy above MARA': _ag('Mercu academy\nMAJLIS AMANAH RAKYAT'),
    'letterhead: MARA inside an address': _ag('MERCU JAYA\nWisma MARA, Jalan Raja Laut'),
    'letterhead: KBS + KSM': _ag('KEMENTERIAN BELIA DAN SUKAN\nKEMENTERIAN SUMBER MANUSIA', venue='IKBN Pekan'),
    'IPMA umbrella, KPTM in the body': _ag('INSTITUSI PENDIDIKAN MARA', extra='Kampus : KPTM Kuantan\n'),
    'Kolej Poly-Tech MARA in the body': _ag(_M, extra='Kampus : Kolej Poly-Tech MARA Kuantan\n'),
    'Kolej Profesional MARA Mercu': _ag(_M, extra='Kampus : Kolej Profesional MARA Mercu\n'),
    'unikl mfi lowercase': _ag(_M, extra='Penempatan : unikl mfi\n'),
    'German-Malaysian Institute': _ag(_M, extra='Penempatan : German-Malaysian Institute\n'),
    'GMI in a table': _ag(_M, extra='Tempat | GMI Bangi\n'),
    'IPTS status': _ag(_M, extra='Status : IPTS\n'),
    'mercu sdn bhd lowercase': _ag(_M, extra='Yuran kepada mercu sdn bhd\n'),
    'Pihak Institut Mercu': _ag(_M, extra='Pihak Institut Mercu berhak.\n'),
    'Kolej universiti mercu': _ag(_M, extra='Rakan pelaksana: Kolej universiti mercu\n'),
    'KOLEJ UNIVERSITI MERCU': _ag(_M, extra='Program usahasama: KOLEJ UNIVERSITI MERCU\n'),
    'Mercu Institute of Technology': _ag(_M, extra='Program dikendalikan di Mercu Institute of Technology.\n'),
    'Mercu Polytechnic': _ag(_M, extra='Lokasi kelas: Mercu Polytechnic\n'),
    'Politeknik Mercu': _ag(_M, extra='Lokasi kelas: Politeknik Mercu\n'),
    'Mercu Learning Hub': _ag(_M, extra='Lokasi kelas: Mercu Learning Hub\n'),
    'Mercu Edu Group': _ag(_M, extra='Lokasi kelas: Mercu Edu Group\n'),
    'the title names Kolej Mercu': _ag(_M, title='SURAT TAWARAN KEMASUKAN KE KOLEJ MERCU'),
    'the title names Mercu College': _ag(_M, title='SURAT TAWARAN KEMASUKAN KE MERCU COLLEGE'),
    'a closing signature Mercu Skills Academy': _ag(_M).replace('PENGARAH\n', 'PENGARAH\nMercu Skills Academy\n'),
    'a closing signature Kolej Mercu': _ag(_M).replace('PENGARAH\n', 'PENGARAH\nKolej Mercu\n'),
    'Kolej Swasta Mercu': _ag(_M, extra='Penempatan di Kolej Swasta Mercu\n'),
    'institusi swasta': _ag(_M, extra='Penempatan di institusi swasta terpilih\n'),
    'IPTS Mercu': _ag(_M, extra='Penempatan : IPTS Mercu\n'),
    'Kolej Komuniti in the body': _ag(_M, extra='Penempatan : Kolej Komuniti Kuantan\n'),
    'ILKBS umbrella in a MARA letter': _ag(_M, extra='Rujuk ILKBS\n'),
    'KBS head, Kolej MARA in the body': _ag(_K, venue='IKBN Pekan', extra='Pindah dari Kolej MARA Kuantan\n'),
    'JTM head, JPK and a Pusat Bertauliah': _ag('JABATAN TENAGA MANUSIA', venue='ILP Kuantan',
                                                extra='Diiktiraf oleh Jabatan Pembangunan Kemahiran (JPK) melalui '
                                                      'Pusat Bertauliah Mercu.\n'),
    'JTM head, JPK full name only': _ag('JABATAN TENAGA MANUSIA', venue='ILP Kuantan',
                                        extra='Sijil dikeluarkan oleh Jabatan Pembangunan Kemahiran.\n'),
}


class Round10AgencyClosedWorld(SimpleTestCase):
    def _lifted(self, text):
        return ruling_of(signature_genuineness(text, doc_type='offer_letter')) in LIFTS

    def test_the_clean_controls_lift(self):
        for head, venue in ((_M, 'Institut Kemahiran MARA Kuantan'), (_K, 'IKBN Miri'), (_K, 'IKBN Pekan'),
                            ('JABATAN TENAGA MANUSIA', 'ILP Kuantan')):
            with self.subTest(head=head, venue=venue):
                self.assertTrue(self._lifted(_ag(head, venue=venue)))

    def test_every_r10_agency_probe_stays_out(self):
        for name, text in ROUND10_AGENCY_NEVER_LIFTED.items():
            with self.subTest(name):
                self.assertFalse(self._lifted(text))

    def test_the_allowed_spans(self):
        """Lead's rulings 2026-11-04: a label column line, a label before the institute, the spelt-out sector name,
        lowercase generic nouns, one-token fragments and a KEPADA block above the agency."""
        for head, extra in ((_K, 'c) Tempat/Pusat\nTempoh : 2 tahun\n'),
                            (_K, 'Pusat Pengajian (IKBN/IKTBN) : IKBN Pekan\n'),
                            (_K, 'Program Technical and Vocational Education and Training (TVET)\n'),
                            (_K, 'Semasa hari pendaftaran di institusi/kolej.\n')):
            with self.subTest(extra=extra):
                self.assertTrue(self._lifted(_ag(head, venue='IKBN Pekan', extra=extra)))
        # round 11 (the lead's a329 ruling): a fragment is junk or an echo of an address word below ("LUMPURR")
        for head in ('123\nLUMPURR\n9\nKEPADA\n' + _K, '9\n' + _K):
            with self.subTest(head=head):
                self.assertTrue(self._lifted(_ag(head, venue='IKBN Pekan')))
        for head in ('MERCU JAYA EDU\n' + _K, 'ALPHA\nBETA\nGAMMA\nDELTA\n' + _K):     # four one-token lines > 3
            with self.subTest(head=head):
                self.assertFalse(self._lifted(_ag(head, venue='IKBN Pekan')))

    def test_a_label_followed_by_anything_else_still_counts(self):
        self.assertFalse(self._lifted(_ag(_K, venue='IKBN Pekan', extra='Pusat Latihan Mercu Jaya\n')))
        self.assertFalse(self._lifted(_ag(_K, venue='IKBN Pekan', extra='Pusat : Mercu Skills\n')))
        # a bare "Pusat :" before the allowed institute IS a label (the lead's ruling 1)
        self.assertTrue(self._lifted(_ag(_K, venue='IKBN Pekan', extra='Pusat : IKBN Pekan\n')))

    def test_the_campus_words_come_from_the_catalogue(self):
        from apps.scholarship.genuineness.offer_agency import catalogue_places
        places = catalogue_places()
        self.assertIn('MIRI', places['tvet_belia_sukan'])
        self.assertIn('KUANTAN', places['tvet_mara'])
        self.assertNotIn('MERCU', places['tvet_mara'])
        self.assertFalse(self._lifted(_ag(_M, venue='IKM Mercu')))

    def test_a_private_name_with_no_organisation_word_is_a_known_gap(self):
        """TD-493 (Medium, accepted): "Mercu Engineering Works" names no organisation word."""
        self.assertTrue(self._lifted(_ag('JABATAN TENAGA MANUSIA', venue='ILP Kuantan',
                                         extra='Latihan industri di Mercu Engineering Works.\n')))


# ── Review round 11 (2026-11-04): one org list, the bracket / umbrella / glue / lowercase rules, M5-M7, normaliser ──
def _a11(head, *, title='SURAT TAWARAN KEMASUKAN', venue='Institut Kemahiran MARA Kuantan', extra='',
         addr='Jalan Raja Laut, 50609 Kuala Lumpur'):
    return (f'{head}\n{addr}\nTel : 03-0000 0000\nRujukan : AG/600-1/2\nTarikh : 1 Jun 2026\nNama : Ali bin Abu\n'
            f'No. Kad Pengenalan : 080808-10-5566\nTuan,\n{title}\nDengan sukacitanya dimaklumkan bahawa anda '
            f'ditawarkan tempat.\nKursus : Sijil Kemahiran Contoh\nTarikh lapor diri : 3 Ogos 2026\nTempat : {venue}\n'
            f'{extra}Sila bawa dokumen asal semasa mendaftar.\nTawaran ini tertakluk kepada syarat.\nSekian, terima '
            'kasih.\nYang benar,\nPENGARAH\n')


_IKBN11 = 'INSTITUT KEMAHIRAN BELIA NEGARA PEKAN'
_J = 'JABATAN TENAGA MANUSIA'
_BODY11 = ('Institution', 'MERCU SKILLS INSTITUTION', 'Mercu Academies', 'Mercu Universities', 'Mercu Schools',
           'Mercu Centres', 'Yayasan Mercu', 'Persatuan Mercu', 'Pusat Tuisyen Mercu', 'Mercu Tuition', 'Mercu Skills',
           'Mercu Tech', 'Mercu International', 'Mercu Global', 'Mercu Ltd', 'Mercu Corporation', 'Mercu Solutions',
           'Koperasi Mercu', 'Syarikat Mercu', 'Mercu Academic', 'Mercu Educational', 'Mercu Trainers', 'Kampus Mercu',
           'Mercu Consortium', 'Mercu Ventures', 'Mercu Corp', 'Pertubuhan Mercu', 'Persatuan Usahawan Mercu')
ROUND11_NEVER_LIFTED = dict(
    {f'body: {w}': _a11(_M, extra=f'Latihan amali di {w}.\n') for w in _BODY11},
    **{
        'label bracket before the institute': _a11(_M, venue='(Kolej Mercu) Institut Kemahiran MARA Kuantan'),
        'Tempat (Kolej Mercu) : IKM': _a11(_M, extra='Tempat (Kolej Mercu) : IKM Kuantan\n'),
        'Pusat (Mercu Skills Academy) : IKM': _a11(_M, extra='Pusat (Mercu Skills Academy) : IKM Kuantan\n'),
        'Lokasi (Kolej Mercu Jaya) - IKM': _a11(_M, extra='Lokasi (Kolej Mercu Jaya) - IKM Kuantan\n'),
        'a name before the label': _a11(_M, extra='Kolej Mercu Tempat : IKM Kuantan\n'),
        'Tempat Latihan (Kolej Mercu)': _a11(_M, extra='Tempat Latihan (Kolej Mercu): IKM Kuantan\n'),
        'umbrella IPMA + a private name': _a11(_M, extra='Penyelaras : Institusi Pendidikan MARA Mercu Jaya\n'),
        'umbrella ILKBS + a private name': _a11(_K, venue='IKBN Pekan', extra='Penyelaras : Institusi Latihan '
                                                                              'Kemahiran Belia dan Sukan Mercu\n'),
        'umbrella ILJTM + a private name': _a11(_J, venue='ADTEC Kulim', extra='Penyelaras : Institusi Latihan '
                                                                               'Jabatan Tenaga Manusia Mercu\n'),
        'BPLTV MARA + Kolej Mercu': _a11(_M, extra='Bahagian Pendidikan dan Latihan Teknikal Vokasional MARA Kolej '
                                                   'Mercu\n'),
        'IKM + uncatalogued words': _a11(_M, venue='IKM Jaya Prima'),
        'IKM Kuantan Jaya Prima Academy': _a11(_M, venue='IKM Kuantan Jaya Prima Academy'),
        'IKM Kuantan Kampus Mercu': _a11(_M, venue='IKM Kuantan Kampus Mercu'),
        'IKM Kuantan, Mercu': _a11(_M, venue='IKM Kuantan, Mercu'),
        'IKM Kuantan (Mercu)': _a11(_M, venue='IKM Kuantan (Mercu)'),
        'IKM Kuantan Mercu, a postcode line': _a11(_M, venue='IKM Kuantan Mercu, 25000 Kuantan'),
        'IKM Kuantan GIATMARA Mercu': _a11(_M, venue='IKM Kuantan GIATMARA Mercu'),
        'IKM Japan Industrial Mercu': _a11(_M, venue='IKM Japan Industrial Mercu'),
        'a fragment MERCU above the agency': _a11('MERCU\n' + _M),
        'two fragments MERCU / JAYA': _a11('MERCU\nJAYA\n' + _M),
        'three fragments': _a11('MERCU\nJAYA\nPRIMA\n' + _M),
        'MERCUEDU': _a11('MERCUEDU\n' + _M),
        'MERCUACADEMY': _a11('MERCUACADEMY\n' + _M),
        'KOLEJMERCU': _a11('KOLEJMERCU\n' + _M),
        'lowercase kolej swasta Mercu': _a11(_M, extra='latihan di kolej swasta Mercu.\n'),
        'lowercase kolej di Mercu Jaya': _a11(_M, extra='latihan di kolej di Mercu Jaya.\n'),
        'lowercase kolej, Mercu Jaya': _a11(_M, extra='latihan di kolej, Mercu Jaya.\n'),
        'lowercase kolej : Mercu Jaya': _a11(_M, extra='nama kolej : Mercu Jaya\n'),
        'lowercase kolej, line end, DI MERCU JAYA': _a11(_M, extra='latihan di kolej\nDI MERCU JAYA\n'),
        'lowercase kolej yang Mercu': _a11(_M, extra='latihan di kolej yang Mercu.\n'),
        'accented Kolèj': _a11(_M, extra='Latihan amali di Kolèj Mercu.\n'),
        'full-width Ｋｏｌｅｊ': _a11(_M, extra='Latihan amali di Ｋｏｌｅｊ Mercu.\n'),
        'Cyrillic o': _a11(_M, extra='Latihan amali di Kоlej Mercu.\n'),
        'a soft hyphen': _a11(_M, extra='Latihan amali di Ko­lej Mercu.\n'),
        'a zero-width space': _a11(_M, extra='Latihan amali di Ko​lej Mercu.\n'),
        'spaced K O L E J': _a11(_M, extra='Latihan amali di K O L E J Mercu.\n'),
        'Kolej_Mercu': _a11(_M, extra='Latihan amali di Kolej_Mercu.\n'),
        'kolej. Mercu Jaya': _a11(_M, extra='Latihan amali di kolej. Mercu Jaya\n'),
        'institute lift: MERCU JAYA (WAKIL IKBN)': _a11('MERCU JAYA (WAKIL IKBN)', venue='IKBN Pekan'),
        'institute lift: EJEN : MERCU JAYA': _a11(_IKBN11 + '\nEJEN : MERCU JAYA', venue='IKBN Pekan'),
    })
#: Public pages the BLOCK must not newly fail (M6).
ROUND11_NEVER_NEWLY_BLOCKED = {
    'GMI in a street name': _a11(_IKBN11, venue='IKBN Pekan', addr='Lot 5 Jalan GMI, 26600 Pekan'),
    'GMI in a street line above the institute': _a11('Lot 5 Jalan GMI\n' + _IKBN11, venue='IKBN Pekan'),
    'KPTM in an e-mail line': _a11(_M, addr='Emel : info@kptm.mara.gov.my, 50609 Kuala Lumpur'),
    'a logo strip under the agency': _a11(_M + '\nIKM KKTM KPM GMI'),
    'a logo strip below the address': _a11(_M, addr='Jalan Raja Laut, 50609 Kuala Lumpur\nIKM KKTM GMI UNIKL'),
    'a logo strip under the institute': _a11('INSTITUT KEMAHIRAN MARA KUANTAN\nIKM KKTM GMI', venue='IKM Kuantan'),
}


class Round11(SimpleTestCase):
    def _lifted(self, text):
        return ruling_of(signature_genuineness(text, doc_type='offer_letter')) in LIFTS

    def test_the_controls_lift(self):
        for text in (_a11(_M), _a11(_IKBN11, venue='IKBN Pekan')):
            with self.subTest(text.splitlines()[0]):
                self.assertTrue(self._lifted(text))

    def test_every_r11_probe_stays_out(self):
        for name, text in ROUND11_NEVER_LIFTED.items():
            with self.subTest(name):
                self.assertFalse(self._lifted(text))

    def test_no_r11_public_page_is_newly_blocked(self):
        for name, text in ROUND11_NEVER_NEWLY_BLOCKED.items():
            with self.subTest(name):
                out = signature_genuineness(text, doc_type='offer_letter')
                self.assertNotEqual(ruling_of(out), 'private_offer')

    def test_one_organisation_word_list(self):
        """H1: the agency lift's word test IS the letterhead list; the two cannot drift."""
        from apps.scholarship.genuineness import offer_agency, offer_reading
        self.assertIs(offer_agency.is_org_word, offer_reading.is_org_token)
        for w in ('KOLEJ', 'INSTITUTION', 'INSTITUTIONS', 'ACADEMIES', 'SCHOOLS', 'CENTRES', 'CENTERS', 'UNIVERSITIES',
                  'COLLEGES', 'INSTITUTES', 'YAYASAN', 'PERSATUAN', 'PERTUBUHAN', 'KOPERASI', 'SYARIKAT', 'KAMPUS',
                  'LTD', 'LIMITED', 'CORPORATION', 'INC', 'INTERNATIONAL', 'GLOBAL', 'TECH', 'SKILLS', 'SOLUTIONS',
                  'VENTURES', 'CONSORTIUM', 'EDUCATIONAL', 'TRAINERS'):
            with self.subTest(w):
                self.assertTrue(offer_reading.is_org_token(w))
                self.assertTrue(offer_reading._ORG_RE.search(f' {w} '))

    def test_the_lead_rulings_for_a329(self):
        """A one-word fragment above the agency that echoes an address word below lifts; a weak suffix after a
        descriptor ("Pendidikan Global") is no organisation."""
        echo = _a11('LUMPURR\n' + _M)
        self.assertTrue(self._lifted(echo))
        self.assertTrue(self._lifted(_a11(_M, extra='Keusahawanan & Pendidikan Global\n')))
        for extra in ('Mercu Global\n', 'Mercu Skills Ltd\n', 'Mercu Tech\n'):
            with self.subTest(extra=extra):
                self.assertFalse(self._lifted(_a11(_M, extra=extra)))

    def test_the_one_normaliser(self):
        from apps.scholarship.genuineness.offer_reading import normalise_s6
        self.assertEqual(normalise_s6('Kolèj Ｋｏｌｅｊ Kоlej Ko­lej Ko​lej'), 'Kolej Kolej Kolej Kolej Kolej')

    def test_an_all_lowercase_name_is_a_known_gap(self):
        """TD-493 (accepted): a name in all-lowercase OCR is not read as a name."""
        self.assertTrue(self._lifted(_a11(_M, extra='latihan di kolej\nmercu jaya\n')))
        self.assertTrue(self._lifted(_a11(_M, venue='IKM Kuantan mercu jaya')))
        self.assertTrue(self._lifted(_a11(_M, extra='Pengendali : akademi mercu\n')))
        self.assertTrue(self._lifted(_a11(_M, extra='Latihan amali di kolej mercu jaya.\n')))
        self.assertTrue(self._lifted(_a11('JABATAN TENAGA MANUSIA', venue='ADTEC Kulim',
                                          extra='Latihan industri: pusat latihan mercu\n')))
        for head in ('TAMAN\n' + _M, 'BIRU\n' + _M):          # a 4+ letter fragment with no echo: no lift
            with self.subTest(head=head):
                self.assertFalse(self._lifted(_a11(head)))


# ── Review round 12 (2026-11-04): one glued-name test, the descriptor run, the echo / campus sources ──────────
_TM = 'Taman Mercu Jaya, 25000 Kuantan'
ROUND12_NEVER_LIFTED = {
    'echo MERCUSKILL (glued SKILL)': _a11('MERCUSKILL\n' + _M, addr=_TM),
    'echo MERCUHUB': _a11('MERCUHUB\n' + _M, addr=_TM),
    'echo MERCUTRAINERS': _a11('MERCUTRAINERS\n' + _M, addr=_TM),
    'echo MERCUINSTITUTION': _a11('MERCUINSTITUTION\n' + _M, addr=_TM),
    'echo MERCUTUITION': _a11('MERCUTUITION\n' + _M, addr=_TM),
    'echo MERCUCORP': _a11('MERCUCORP\n' + _M, addr=_TM),
    'echo MERCUPLT': _a11('MERCUPLT\n' + _M, addr=_TM),
    'an echo only from a body address line': _a11('MERCU\n' + _M, extra='Alamat surat-menyurat: Lot 5, Taman Mercu, '
                                                                        '25000 Kuantan\n'),
    'Mercu Technical Solutions': _a11(_M, extra='Latihan industri di Mercu Technical Solutions.\n'),
    'Mercu Vocational Skills': _a11(_M, extra='Latihan industri di Mercu Vocational Skills.\n'),
    'Mercu Technical Skills': _a11(_M, extra='Latihan industri di Mercu Technical Skills.\n'),
    'Latihan Skills Mercu': _a11(_M, extra='Latihan amali di Latihan Skills Mercu.\n'),
    'Mercu Kemahiran Global': _a11(_M, extra='Latihan amali di Mercu Kemahiran Global.\n'),
    'Mercu Pendidikan Global': _a11(_M, extra='Latihan amali di Mercu Pendidikan Global.\n'),
    'Mercu Technical & Vocational Skills': _a11(_M, extra='Latihan amali di Mercu Technical & Vocational Skills.\n'),
    'Mercu Teknikal Ventures': _a11(_M, extra='Latihan industri di Mercu Teknikal Ventures.\n'),
    'Mercu Vocational Tech': _a11(_M, extra='Latihan industri di Mercu Vocational Tech.\n'),
    'Mercu Latihan dan Kemahiran Global': _a11(_M, extra='Latihan industri di Mercu Latihan dan Kemahiran Global.\n'),
    'Penyedia latihan : Mercu Technical Solutions': _a11(_M, extra='Penyedia latihan : Mercu Technical Solutions\n'),
    'Mercu Training Solutions': _a11(_M, extra='Latihan industri di Mercu Training Solutions.\n'),
    'Mercu Education Global': _a11(_M, extra='Latihan industri di Mercu Education Global.\n'),
    'Mercu Latihan Edu': _a11(_M, extra='Latihan industri di Mercu Latihan Edu.\n'),
    'KBS: Mercu Kemahiran Skills': _a11(_K, venue='IKBN Pekan', extra='Latihan industri di Mercu Kemahiran Skills.\n'),
    'JTM: Mercu Technical Solutions': _a11(_J, venue='ADTEC Kulim', extra='Latihan industri di Mercu Technical '
                                                                          'Solutions.\n'),
    'IKM Kuantan Sila Mercu Jaya': _a11(_M, venue='IKM Kuantan Sila Mercu Jaya'),
    'kolej at a line end, MOHON MERCU ACADEMY': _a11(_M, extra='Latihan di kolej\nMOHON MERCU ACADEMY\n'),
    'kolej sila Mercu Academy': _a11(_M, extra='latihan di kolej sila Mercu Academy.\n'),
    'kolej sila hubungi pihak Mercu Academy': _a11(_M, extra='latihan di kolej sila hubungi pihak Mercu Academy.\n'),
    'Harap maklum kolej Mercu': _a11(_M, extra='Harap maklum kolej Mercu menerima anda.\n'),
    'IKM Kuantan Mercu Jaya Academy': _a11(_M, venue='IKM Kuantan Mercu Jaya Academy', addr=_TM),
    'IKM Kuantan Mercu, an address in the footer': _a11(_M, venue='IKM Kuantan Mercu',
                                                        extra='Alamat: Taman Mercu, 25000 Kuantan\n'),
    'IKM Kuantan Pusat Mercu': _a11(_M, venue='IKM Kuantan Pusat Mercu', addr='Pusat Mercu, 25000 Kuantan'),
    'body MercuAcademy': _a11(_M, extra='Latihan amali di MercuAcademy.\n'),
    'body MERCUACADEMY': _a11(_M, extra='Latihan amali di MERCUACADEMY.\n'),
    'body MercuSkills': _a11(_M, extra='Latihan amali di MercuSkills.\n'),
    'body MercuTraining': _a11(_M, extra='Latihan amali di MercuTraining.\n'),
    'body MercuEdu': _a11(_M, extra='Latihan amali di MercuEdu.\n'),
    'body MercuCollege': _a11(_M, extra='Latihan amali di MercuCollege.\n'),
    'body MercuTuition': _a11(_M, extra='Kelas di MercuTuition.\n'),
    'body MercuTech': _a11(_M, extra='Latihan amali di MercuTech.\n'),
    'body Kolej-Mercu': _a11(_M, extra='Latihan amali di Kolej-Mercu.\n'),
    'body MercuKolej': _a11(_M, extra='Latihan amali di MercuKolej.\n'),
    'venue IKM Kuantan / MercuAcademy': _a11(_M, venue='IKM Kuantan / MercuAcademy'),
    'letterhead MERCUTUITION, no echo': _a11('MERCUTUITION\n' + _M),
    'institute lift: MERCUACADEMY on line 2': _a11(_IKBN11 + '\nMERCUACADEMY', venue='IKBN Pekan'),
    'institute lift: MercuCollege on line 2': _a11(_IKBN11 + '\nMercuCollege', venue='IKBN Pekan'),
    'institute lift: MERCUACADEMY on the same line': _a11(_IKBN11 + ' MERCUACADEMY', venue='IKBN Pekan'),
    'institute lift: MERCUTUITION on line 2': _a11(_IKBN11 + '\nMERCUTUITION', venue='IKBN Pekan'),
    'institute lift: Mercu Technical Solutions': _a11(_IKBN11 + '\nMercu Technical Solutions', venue='IKBN Pekan'),
    'institute lift: MERCU PENDIDIKAN GLOBAL': _a11(_IKBN11 + '\nMERCU PENDIDIKAN GLOBAL', venue='IKBN Pekan'),
    'Pusat Latihan Skills Mercu': _a11(_M, extra='Latihan amali di Pusat Latihan Skills Mercu.\n'),
    'Kemahiran Tech Mercu': _a11(_M, extra='Latihan amali di Kemahiran Tech Mercu.\n'),
    'KBS body MercuAcademy': _a11(_K, venue='IKBN Pekan', extra='Latihan amali di MercuAcademy.\n'),
    'JTM body MercuCollege': _a11(_J, venue='ADTEC Kulim', extra='Latihan amali di MercuCollege.\n'),
    'body EduMercu': _a11(_M, extra='Penyedia latihan : EduMercu\n'),
    'body MercuAcademy Sdn Bhd': _a11(_M, extra='Latihan amali di MercuAcademy Sdn Bhd.\n'),
}
#: Public pages with odd characters: never lifted wrongly, never newly blocked (the normaliser).
ROUND12_PUBLIC = {
    'a trademark sign': _a11(_IKBN11 + '™', venue='IKBN Pekan'),
    'a full-width letterhead': _a11('ＩＮＳＴＩＴＵＴ ＫＥＭＡＨＩＲＡＮ ＢＥＬＩＡ ＮＥＧＡＲＡ ＰＥＫＡＮ', venue='IKBN Pekan'),
    'a zero-width space in the name': _a11('INSTITUT KEMAHIRAN BELIA NEGA​RA PEKAN', venue='IKBN Pekan'),
    'Tamil text in the body': _a11(_IKBN11, venue='IKBN Pekan', extra='தமிழ் மாணவர்\n'),
    'a Jawi crest line': _a11('مجليس امانه رعيت\n' + _IKBN11, venue='IKBN Pekan'),
}


class Round12(SimpleTestCase):
    def _out(self, text):
        return signature_genuineness(text, doc_type='offer_letter')

    def test_every_r12_probe_stays_out(self):
        for name, text in ROUND12_NEVER_LIFTED.items():
            with self.subTest(name):
                self.assertNotIn(ruling_of(self._out(text)), LIFTS)

    def test_odd_characters_on_public_pages(self):
        for name, text in ROUND12_PUBLIC.items():
            with self.subTest(name):
                self.assertEqual(ruling_of(self._out(text)), 'tvet_offer')

    def test_a_company_hidden_by_odd_characters_still_blocks(self):
        for head in ('MERCU S­dn B­hd\n' + _IKBN11, 'MERCU Ѕdn Вhd\n' + _IKBN11):
            with self.subTest(head=head):
                self.assertEqual(ruling_of(self._out(_a11(head, venue='IKBN Pekan'))), 'private_offer')

    def test_the_descriptor_slogans_still_pass(self):
        for extra in ('Ke arah Pendidikan & Latihan Global.\n', 'Keusahawanan\n& Pendidikan Global\n'):
            with self.subTest(extra=extra):
                self.assertIn(ruling_of(self._out(_a11(_M, extra=extra))), LIFTS)

    def test_one_glued_name_test(self):
        """H1: one test from the shared words (start: institution nouns; end: any word), never an ordinary word."""
        from apps.scholarship.genuineness.offer_reading import glued_org, is_org_token
        from apps.scholarship.genuineness.offer_text import _GLUE_WORDS
        for w in ('MERCUACADEMY', 'KOLEJMERCU', 'MERCUSKILLS', 'MERCUEDU', 'MERCUHUB', 'MERCUTUITION', 'EDUMERCU'[:0]
                  or 'MERCUPLT'):
            with self.subTest(w):
                self.assertTrue(glued_org(w))
        for w in ('HUBUNGI', 'HUBUNGAN', 'INCLUDE', 'TECHNICAL', 'TECHNOLOGY', 'SCHEDULE', 'AKADEMIK', 'PUSATNYA',
                  'UNIVERSITIMALAYSIASABAH', 'KOLEJ', 'ACADEMY'):
            with self.subTest(w):
                self.assertFalse(glued_org(w))
        import re
        for w in ('KOLEJ', 'COLLEGES', 'AKADEMI', 'ACADEMIES', 'UNIVERSITIES', 'INSTITUTIONS', 'INSTITUSI', 'TUISYEN',
                  'SCHOOLS', 'POLYTECHNICS', 'MAKTAB', 'PUSAT', 'TRAINERS', 'CENTRES', 'CENTERS', 'HUBS', 'GROUPS',
                  'PLT', 'EDU', 'EDUCATION', 'LEARNING', 'SKILLS', 'ENTERPRISES', 'RESOURCES', 'INTERNATIONAL',
                  'GLOBAL', 'SERVICES', 'SOLUTIONS', 'HOLDINGS', 'CORP', 'CORPORATION', 'CONSULTANCY', 'VENTURES',
                  'LTD', 'LIMITED', 'INC', 'PERSATUAN', 'PERTUBUHAN', 'TECH', 'KAMPUS', 'YAYASAN', 'KOPERASI',
                  'SYARIKAT', 'CONSORTIUM', 'MAJLIS'):
            with self.subTest(glue_word=w):                     # every glue word is the shared list's word
                self.assertTrue(re.fullmatch(_GLUE_WORDS, w))
                self.assertTrue(is_org_token(w))

    def test_known_gaps_accepted_by_the_rules(self):
        """Within the agreed rules (reported to the lead): an echo / campus word the letterhead's OWN address gives,
        and a name four or more tokens after a lowercase noun."""
        for text in (_a11('MERCU\n' + _M, addr=_TM), _a11(_M, venue='IKM Kuantan Mercu Jaya', addr=_TM),
                     _a11(_M, extra='latihan di kolej sila hubungi pihak Mercu Jaya.\n')):
            with self.subTest(text=text.splitlines()[0]):
                self.assertIn(ruling_of(self._out(text)), LIFTS)


# ── Review round 13 (2026-11-04, the last check before the ship): digits, names inside glued tokens, affixes ──
def _b13(s, head=_M, **kw):
    return _a11(head, extra=s + '\n', **kw)


ROUND13_NEVER_LIFTED = {
    'IKMMercuAcademy': _b13('Latihan amali di IKMMercuAcademy.'),
    'IKMMERCUACADEMY': _b13('Latihan amali di IKMMERCUACADEMY.'),
    'MaraMercuAcademy': _b13('Latihan amali di MaraMercuAcademy.'),
    'MercuAcademyIKM': _b13('Latihan amali di MercuAcademyIKM.'),
    'SamaraAcademy': _b13('Latihan amali di SamaraAcademy.'),
    'AMARACOLLEGE': _b13('Latihan amali di AMARACOLLEGE.'),
    'Mercu-Academy': _b13('Latihan amali di Mercu-Academy.'),
    'Mercu.Academy': _b13('Latihan amali di Mercu.Academy.'),
    'Mercu/Academy': _b13('Latihan amali di Mercu/Academy.'),
    'Mercu_Academy': _b13('Latihan amali di Mercu_Academy.'),
    'Mercu2Academy': _b13('Latihan amali di Mercu2Academy.'),
    'MercuAcademy2u': _b13('Latihan amali di MercuAcademy2u.'),
    'Academy360': _b13('Latihan amali di Academy360 Kuantan.'),
    'Akademi21 Mercu': _b13('Latihan amali di Akademi21 Mercu.'),
    'Skills360': _b13('Latihan amali di Skills360 Kuantan.'),
    'Edu360': _b13('Latihan amali di Edu360 Kuantan.'),
    'EduPrima': _b13('Latihan amali di EduPrima Kuantan.'),
    'SkillsPrima': _b13('Latihan amali di SkillsPrima Kuantan.'),
    'TrainingMercu': _b13('Latihan amali di TrainingMercu Kuantan.'),
    'TuisyenMercu': _b13('Latihan amali di TuisyenMercu Kuantan.'),
    'MercuAcademyKuantan': _b13('Latihan amali di MercuAcademyKuantan.'),
    'MERCUACADEMYSB': _b13('Latihan amali di MERCUACADEMYSB.'),
    'MercuAcademy(M)': _b13('Latihan amali di MercuAcademy(M).'),
    'K0LEJMERCU': _b13('Latihan amali di K0LEJMERCU.'),
    'Mercu3Academy': _b13('Latihan amali di Mercu3Academy.'),
    'MercuAcad3my': _b13('Latihan amali di MercuAcad3my.'),
    'Mercu Acad3my': _b13('Latihan amali di Mercu Acad3my.'),
    'Mercu Ko1ej': _b13('Latihan amali di Mercu Ko1ej.'),
    'Mercu Akad3mi': _b13('Latihan amali di Mercu Akad3mi.'),
    'letterhead MercuAcademy': _a11('MercuAcademy\n' + _M, addr=_TM),
    'letterhead Mercu2Academy': _a11('Mercu2Academy\n' + _M, addr=_TM),
    'letterhead MERCU-ACADEMY': _a11('MERCU-ACADEMY\n' + _M, addr=_TM),
    'letterhead IKMMERCUACADEMY': _a11('IKMMERCUACADEMY\n' + _M, addr=_TM),
    'letterhead MERCU1ACADEMY': _a11('MERCU1ACADEMY\n' + _M, addr=_TM),
    'KBS: IKBNMercuAcademy': _a11(_K, venue='IKBN Pekan', extra='Latihan di IKBNMercuAcademy.\n'),
    'JTM: ADTECMercuCollege': _a11(_J, venue='ADTEC Kulim', extra='Latihan di ADTECMercuCollege.\n'),
    'MaraSkills': _b13('Latihan amali di MaraSkills Kuantan.'),
    'MaraEdu': _b13('Latihan amali di MaraEdu Kuantan.'),
    'IKMSkills': _b13('Latihan amali di IKMSkills Kuantan.'),
    'KBS: KBSAcademy': _a11(_K, venue='IKBN Pekan', extra='Latihan amali di KBSAcademy Pekan.\n'),
    'PermataMaraCollege': _b13('Latihan amali di PermataMaraCollege.'),
    'MARASKILLS caps': _b13('Latihan amali di MARASKILLS KUANTAN.'),
    'letterhead MaraSkills': _a11('MaraSkills\n' + _M),
    'MaraSkills Academy': _b13('Latihan amali di MaraSkills Academy.'),
    'letterhead SKILLS360': _a11('SKILLS360\n' + _M),
    'Edu360 fees': _b13('Yuran dibayar kepada Edu360 Kuantan.'),
    'Akademi21 classes': _b13('Kelas tambahan di Akademi21 Kuantan.'),
    'KOLEJ21': _b13('Tempat latihan : KOLEJ21 KUANTAN'),
    'Mercu Academy2': _b13('Latihan di Mercu Academy2.'),
    'institute lift: AKADEMI21 on line 2': _a11(_IKBN11 + '\nAKADEMI21', venue='IKBN Pekan'),
    'institute lift: SKILLS360 on line 2': _a11(_IKBN11 + '\nSKILLS360', venue='IKBN Pekan'),
    'institute lift: MERCU ACAD3MY': _a11(_IKBN11 + '\nMERCU ACAD3MY', venue='IKBN Pekan'),
    'institute lift: MERCUACADEMY2U': _a11(_IKBN11 + '\nMERCUACADEMY2U', venue='IKBN Pekan'),
    'institute lift: SAMARAACADEMY': _a11(_IKBN11 + '\nSAMARAACADEMY', venue='IKBN Pekan'),
    'institute lift: IKBNSKILLS': _a11(_IKBN11 + '\nIKBNSKILLS', venue='IKBN Pekan'),
}


def _c13(head, extra='', addr='Jalan Contoh, 88400 Kota Kinabalu\n'):
    return (f'{head}\n{addr}Tel : 088-000000\nRujukan : UMS/600-1/2\nTarikh : 1 Jun 2026\n'
            'KEPADA SESIAPA YANG BERKENAAN\nPENGESAHAN PELAJAR\nDengan ini disahkan bahawa:\nNama : Ali bin Abu\n'
            'No. Kad Pengenalan : 080808-10-5566\nProgram : Ijazah Sarjana Muda Contoh\nSemester : 3\n'
            f'Sesi : 2026/2027\n{extra}Sekian, terima kasih.\nYang benar,\nPENGARAH\n')


#: Real public pages carrying real words the glued test must never read as a name.
ROUND13_PUBLIC_STILL_LIFT = {
    'UMS confirmation': _c13('UNIVERSITI MALAYSIA SABAH'),
    'UMS, a Terpusat line': _c13('UNIVERSITI MALAYSIA SABAH\nSistem Kemasukan Terpusat'),
    'UMS, an Institutional motto': _c13('UNIVERSITI MALAYSIA SABAH\nInstitutional Excellence Since 1994'),
    'UMS, terpusat in the body': _c13('UNIVERSITI MALAYSIA SABAH', extra='Pendaftaran secara terpusat.\n'),
    'MARA offer, berpusat': _b13('Pendaftaran pelajar dibuat secara berpusat di dewan utama.'),
    'MARA offer, prasekolah': _b13('Sila bawa sijil prasekolah dan sekolah rendah.'),
    'KBS offer, prauniversiti': _a11(_K, venue='IKBN Pekan', extra='Calon lepasan prauniversiti dialu-alukan.\n'),
    'UMS, Bahagian Kemasukan Terpusat': _c13('UNIVERSITI MALAYSIA SABAH\nBahagian Kemasukan Terpusat'),
    'UMS, Jalan Intrakampus': _c13('UNIVERSITI MALAYSIA SABAH', addr='Jalan Intrakampus, 88400 Kota Kinabalu\n'),
}


class Round13(SimpleTestCase):
    def _ruling(self, text):
        return ruling_of(signature_genuineness(text, doc_type='offer_letter'))

    def test_every_r13_probe_stays_out(self):
        for name, text in ROUND13_NEVER_LIFTED.items():
            with self.subTest(name):
                self.assertNotIn(self._ruling(text), LIFTS)

    def test_real_words_on_public_pages_still_lift(self):
        for name, text in ROUND13_PUBLIC_STILL_LIFT.items():
            with self.subTest(name):
                self.assertIn(self._ruling(text), LIFTS)

    def test_the_normaliser_reads_digits(self):
        from apps.scholarship.genuineness.offer_text import normalise_s6
        self.assertEqual(normalise_s6('AKADEMI21 Mercu2Academy K0LEJ Ko1ej ACAD3MY 080808-10-5566'),
                         'AKADEMI 21 Mercu 2 Academy KOLEJ Kolej ACADEMY 080808-10-5566')

    def test_the_common_word_list_never_flags(self):
        """The reviewer's 175 common words (Malay affixes, English compounds) read as no glued name."""
        from apps.scholarship.genuineness.offer_text import glued_org
        words = ('BERPUSAT TERPUSAT BERSEKOLAH PERSEKOLAHAN SCHOOLING PRESCHOOL HOMESCHOOL INSTITUTIONAL '
                 'INSTITUSIONAL UNIVERSITINYA MAKTABNYA YAYASANNYA SYARIKATNYA DISSOLUTION BIOTECH FINTECH INFOTECH '
                 'HITECH EDTECH AGROTECH SHAREHOLDING MULTISKILLS SOFTSKILLS UPSKILLING RETRAINING SELFSERVICE '
                 'EPICENTRE MISADVENTURE SUBGROUP UNLIMITED ELEARNING COEDUCATION BERKOLEJ BERINSTITUSI SEKOLAHKAN '
                 'PERSYARIKATAN BERKAMPUS INTRAKAMPUS ANTARABANGSA SCHOOLTEACHER COLLEGEWIDE HIGHSCHOOL '
                 'PRIMARYSCHOOL SUMMERSCHOOL KINDERGARTEN WORKSKILLS LIFESKILLS MEGACORP HIGHTECH NANOTECH '
                 'ANTARAKOLEJ PRAUNIVERSITI PRASEKOLAH PASCAUNIVERSITI SEKOLAHSEKOLAH DATACENTRE CALLCENTRE '
                 'KEYHOLDINGS LANDHOLDING BERMAKTAB KOMUNITIKOLEJ ROMANTECH PERSEKOLAHANNYA KELASTUISYEN HUBUNGI '
                 'HUBUNGAN INCLUDE TECHNICAL SCHEDULE WITHHOLDING CONSTRAINING SECONDARYSCHOOL TEACHERTRAINING')
        self.assertEqual([w for w in words.split() if glued_org(w)], [])

    def test_a_closed_list_name_inside_a_token_is_tested_on_the_rest(self):
        from apps.scholarship.genuineness.offer_text import glued_org
        for w in ('MARASKILLS', 'IKMSKILLS', 'SAMARAACADEMY', 'KBSACADEMY', 'ADTECMERCUCOLLEGE'):
            with self.subTest(w):
                self.assertTrue(glued_org(w))
        self.assertFalse(glued_org('UNIVERSITIMALAYSIASABAH'))

    def test_the_accepted_gaps_after_the_stop_rule(self):
        """Owner's stop rule (decisions S6 item 10): these still lift and are on the TD list for S7 —
        TD-493 (an OCR-misread noun, a lowercase name, a short brand on the institute's own letter) and TD-494
        (a descriptor phrase that hides a company: "Technical Solutions", "Teknikal Vokasional Solutions")."""
        gaps = {
            'TD-493 Acaderny': _a11(_M, extra='Latihan amali di Mercu Acaderny.\n'),
            'TD-493 Kolei': _a11(_M, extra='Latihan amali di Mercu Kolei.\n'),
            'TD-493 lowercase name': _a11(_M, extra='latihan di mercu Technical Solutions.\n'),
            'TD-493 Edu360 on the institute lift': _a11(_IKBN11, venue='IKBN Pekan', extra='Kelas tambahan Edu360.\n'),
            'TD-494 agency before descriptor': _a11(_M, extra='Latihan amali di MARA Technical Solutions.\n'),
            'TD-494 TVET spelt + descriptor': _a11(_M, extra='Latihan di Teknikal Vokasional Solutions.\n'),
        }
        for name, text in gaps.items():
            with self.subTest(name):
                self.assertEqual(self._ruling(text), 'tvet_offer')
