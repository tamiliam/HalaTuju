"""Offer exact-read S6 — the FOURTH adversarial review (2026-11-03): the reviewer's own probes, one regression
each (N1-N8). Every letter is invented (`test_no_gitignored_corpus.py`)."""
from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_rulings import (_first_institution, _folded_lines, _letter_structure,
                                                         _TITLE, confirmation_kind, ruled_offer, ruling_of)
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, signature_genuineness
from apps.scholarship.tests.test_offer_s6_narrowing import baseline_status
from apps.scholarship.tests.test_offer_s6_review3 import REAL, _letter


def _g(text):
    return signature_genuineness(text, doc_type='offer_letter')


def _r(p, family='ua_offer'):
    return {'probability': p, 'type': family, 'present': [], 'missing': [], 'scores': {}}


def _conf(text, p):
    return ruled_offer(text, _r(p, 'polytechnic'), 'not_offer_letter', 'r', MODEL_VERSION)['status']


class N1ShortConfirmations(SimpleTestCase):
    def test_five_and_six_line_confirmations_are_not_genuine(self):
        for text, p in (
                ('POLITEKNIK X\nKEMENTERIAN PENDIDIKAN TINGGI\nRUJ 1 1 JUN 2026\n'
                 'PENGESAHAN PELAJAR NAMA ALI 080808105566 PROGRAM DIPLOMA X\nYANG BENAR', 0.17),
                ('POLITEKNIK X\nKEMENTERIAN PENDIDIKAN TINGGI\nRujukan : 1\nTarikh : 1 Jun 2026\n'
                 'PENGESAHAN PELAJAR\nNama : Ali 080808105566 Program Diploma X\nYang benar', 0.17),
                ('KOLEJ TINGKATAN ENAM X\nKEMENTERIAN PENDIDIKAN MALAYSIA\nRujukan : 1\nTarikh : 1 Jun 2026\n'
                 'PENGESAHAN BELAJAR\nNama : Ali\nNo KP : 080808105566\nBidang : Sains\nYang benar', 0.2),
                ('UNIVERSITI MALAYSIA SABAH\nRujukan : 1\nTarikh : 1 Jun 2026\nPENGESAHAN PELAJAR\nNama : Ali\n'
                 'No KP : 080808105566\nProgram : Ijazah\nYang benar', 0.3)):
            with self.subTest(head=text.splitlines()[0]):
                self.assertNotEqual(_conf(text, p), 'genuine')

    def test_the_title_line_may_not_carry_the_name_and_ic(self):
        lines = _folded_lines('PENGESAHAN PELAJAR NAMA ALI 080808105566\n' * 1)
        from apps.scholarship.genuineness.offer_rulings import _own_identity_lines, _CONFIRM_TITLES
        self.assertFalse(_own_identity_lines(lines, _CONFIRM_TITLES))


class N2TieUpWordsOnTheLetterhead(SimpleTestCase):
    def test_tie_up_wording_on_the_letterhead_never_lifts(self):
        for line in ('ABC ENTERPRISES\nDengan kerjasama IKBN Pekan', 'Usahasama IKBN', 'Accredited by IKBN',
                     'Diiktiraf oleh IKBN', 'In association with IKBN', 'Member of IKBN network'):
            with self.subTest(line=line):
                self.assertNotEqual(_g(_letter(f'IKBN PEKAN\n{line}'))['status'], 'genuine')


class N3CompanyLinesOnARealTvetLetter(SimpleTestCase):
    def test_a_supplier_insurer_estate_or_sponsor_line_does_not_fail_a_real_letter(self):
        for label, text in (
                ('supplier', REAL.replace('Sila bawa', 'Pembekal pakaian seragam : ABC Uniform Sdn Bhd\nSila bawa')),
                ('insurer', REAL.replace('Sila bawa', 'Perlindungan oleh ABC Insurance Sdn Bhd\nSila bawa')),
                ('estate address', REAL.replace('No. Kad Pengenalan : 080808-10-5566\n',
                                                'No. Kad Pengenalan : 080808-10-5566\nd/a Ladang Contoh Sdn Bhd\n'
                                                '31000 Batu Gajah\n')),
                ('sponsor', REAL.replace('Sila bawa', 'Penaja : ABC Sdn Bhd\nSila bawa'))):
            with self.subTest(label):
                # S6 round 8 (almost no excuses): a supplier / insurer / sponsor line is a private marker (no lift),
                # never a new block: the baseline; the addressee's estate above the title is still excused.
                out = _g(text)
                if label == 'estate address':
                    self.assertNotEqual(out['status'], 'not_offer_letter')
                else:
                    self.assertEqual((out['status'], ruling_of(out)), (baseline_status(text), ''))

    def test_a_sdn_bhd_on_the_letterhead_still_vetoes(self):
        self.assertEqual(_g(_letter('ABC TRAINING SDN BHD\nIKBN PEKAN'))['status'], 'not_offer_letter')


class N4TheLetterheadPastAReferenceOrDate(SimpleTestCase):
    def test_a_date_or_reference_first_does_not_hide_the_letterhead(self):
        for head in ('Tarikh : 1 Jun 2026\nINSTITUT KEMAHIRAN MARA\nGERMAN MALAYSIAN INSTITUTE',
                     'Ruj : 1\nINSTITUT KEMAHIRAN MARA\nKPTM',
                     'INSTITUT KEMAHIRAN MARA\nTarikh : 1 Jun 2026\nKOLEJ ABC\nRakan Strategik IKBN'):
            with self.subTest(head=head.replace('\n', ' / ')):
                self.assertNotEqual(_g(_letter(head))['status'], 'genuine')


class N5OrganisationStems(SimpleTestCase):
    def test_plural_and_new_organisation_words_are_organisations(self):
        for head in ('ABC ENTERPRISES', 'ABC CENTRES', 'ABC EDUCATIONAL', 'ABC TRAINERS', 'MAKTAB ABC',
                     'ABC INSTITUTION', 'PUSAT PENDIDIKAN ABC', 'PUSAT BAHASA ABC', 'ABC EDU', 'ABC SERVICES',
                     'ABC SOLUTIONS', 'ABC HOLDINGS', 'ABC CORPORATION', 'ABC LTD', 'ABC LIMITED', 'ABC INC',
                     'ABC KONSULTANSI', 'PERSATUAN ABC', 'PERTUBUHAN ABC', 'ABC ACADEMIC', 'ABC VENTURES',
                     'ABC TECH', 'KAMPUS ABC', 'YAYASAN ABC'):
            with self.subTest(head=head):
                self.assertNotEqual(_g(_letter(f'{head}\nIKBN PEKAN'))['status'], 'genuine')


class N6TvetSpeltOutIsNeutralOnlyOnTheTitle(SimpleTestCase):
    def test_on_the_letterhead_it_is_an_organisations_name(self):
        for head in ('ABC TECHNICAL AND VOCATIONAL EDUCATION AND TRAINING\nIKBN',
                     'ABC TECHNICAL AND VOCATIONAL EDUCATION AND TRAINING HQ\nIKBN',
                     'PUSAT PENDIDIKAN DAN LATIHAN TEKNIKAL DAN VOKASIONAL ABC\nIKBN'):
            with self.subTest(head=head.splitlines()[0]):
                self.assertNotEqual(_g(_letter(head))['status'], 'genuine')

    def test_on_the_title_line_it_names_no_institution(self):
        text = REAL.replace('SURAT TAWARAN KEMASUKAN\n',
                            'SURAT TAWARAN KEMASUKAN PROGRAM TECHNICAL AND VOCATIONAL EDUCATION AND TRAINING\n')
        self.assertEqual(_g(text)['status'], 'genuine')


class N7GluedReference(SimpleTestCase):
    def test_rujuk_inside_a_word_is_not_a_reference(self):
        glued = ' '.join(['ISI'] * 20) + ' SILA DIRUJUK KEPADA PEJABAT ' + ' '.join(['LAGI'] * 20)
        lines = _folded_lines(glued)
        from apps.scholarship.genuineness.offer_rulings import _GLUED_RUJ
        self.assertIsNone(_GLUED_RUJ.search(lines[0]))
        self.assertIsNotNone(_GLUED_RUJ.search(' TEL 0000RUJUKAN UMS '))


class N8StreetsAndCertifications(SimpleTestCase):
    def test_taman_bandar_seksyen_presint_and_iso_lines_name_no_organisation(self):
        for line in ('No 1, Taman Kolej Indah', 'Bandar Universiti Pagoh', 'Seksyen Akademi 3', 'Presint 1 Kolej',
                     'ISO 9001:2015 International Certification'):
            with self.subTest(line=line):
                lines = _folded_lines(f'{line}\nIKBN PEKAN\n')
                self.assertEqual(_first_institution(lines, (' IKBN ',)), 'allowed')

    def test_the_structure_still_reads_the_real_letter(self):
        self.assertTrue(_letter_structure(_folded_lines(REAL), _TITLE, min_lines=12, reporting=True))


class ConfirmationsStillQualify(SimpleTestCase):
    def test_a_full_polytechnic_confirmation_is_genuine(self):
        text = ('POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI\nJalan Contoh, 93050 Kuching\nTel : 082-000000\n'
                'Rujukan : PO/600-1/2\nTarikh : 1 Jun 2026\nKEPADA SESIAPA YANG BERKENAAN\nPENGESAHAN PELAJAR\n'
                'Dengan ini disahkan bahawa penama berikut adalah pelajar kami:\nNama : Ali bin Abu\n'
                'No. Kad Pengenalan : 080808-10-5566\nProgram : Diploma Kejuruteraan Contoh\nSemester : 3\n'
                'Sesi : 2026/2027\nSekian, terima kasih.\nYang benar,\nPENGARAH\nPoliteknik Contoh\n')
        self.assertEqual(confirmation_kind(text, 0.17), 'confirmation_polytechnic')
        self.assertEqual(_conf(text, 0.17), 'genuine')
