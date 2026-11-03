"""Offer exact-read S6 — the FIFTH adversarial review (2026-11-03): the safety rule at ONE exit, and the reviewer's
probes for the wrong blocks of real public letters. Every letter is invented (`test_no_gitignored_corpus.py`)."""
from django.test import SimpleTestCase

from apps.scholarship.genuineness.offer_rulings import (_first_institution, _folded_lines, _unglued,
                                                         confirmation_kind, ruled_offer, ruling_of)
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, signature_genuineness
from apps.scholarship.tests.test_offer_s6_review3 import REAL, _letter


def _g(text):
    return signature_genuineness(text, doc_type='offer_letter')


def _r(p, family='polytechnic'):
    return {'probability': p, 'type': family, 'present': [], 'missing': [], 'scores': {}}


def _conf(head, *, extra='', p=0.2):
    text = (f'{head}\nJalan Contoh, 88400 Kota Kinabalu\nTel : 088-000000\nRujukan : UMS/600-1/2\n'
            'Tarikh : 1 Jun 2026\nKEPADA SESIAPA YANG BERKENAAN\nPENGESAHAN PELAJAR\nDengan ini disahkan bahawa:\n'
            'Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\nProgram : Ijazah Sarjana Muda Contoh\n'
            f'Semester : 3\nSesi : 2026/2027\n{extra}Sekian, terima kasih.\nYang benar,\nPENGARAH\n')
    return text, ruled_offer(text, _r(p, 'ua_offer'), 'not_offer_letter', 'r', MODEL_VERSION)


class TheSafetyRuleAtOneExit(SimpleTestCase):
    """For EVERY ruled kind: a public body named first + no positive private evidence → never a fail."""

    BROKEN = {   # each misses a rule its kind needs, and carries no private evidence
        # (round 6: an unclean letterhead IS positive private evidence — moved to the test below)
        'tvet offer, no structure': 'INSTITUT KEMAHIRAN BELIA NEGARA PEKAN\nSURAT TAWARAN\nAnda ditawarkan kursus.\n',
        'polytechnic confirmation, thin': 'POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI\nPENGESAHAN PELAJAR\nNama : Ali\n',
        'UMS confirmation, thin': 'UNIVERSITI MALAYSIA SABAH\nPENGESAHAN PELAJAR\nNama : Ali\n',
        'Form-6 confirmation, thin': 'KOLEJ TINGKATAN ENAM CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA\nPENGESAHAN BELAJAR\n'
                                     'Nama : Ali\n',
        'ministry-first confirmation': 'KEMENTERIAN PENDIDIKAN TINGGI\nPOLITEKNIK CONTOH\nPENGESAHAN PELAJAR\nNama : Ali\n',
    }

    def test_no_ruled_kind_ever_fails_without_private_evidence(self):
        for label, text in self.BROKEN.items():
            # Round 6 (item 4): a confirmation engages the rule only from CONFIRM_MIN (0.10) up; a TVET body at 0.0.
            for p in ((0.0, 0.1, 0.4) if label.startswith('tvet') else (0.1, 0.4)):
                with self.subTest(label, p=p):
                    out = ruled_offer(text, _r(p), 'not_offer_letter' if p < 0.35 else 'suspect', 'r', MODEL_VERSION)
                    self.assertNotEqual(out['status'], 'not_offer_letter')

    def test_positive_private_evidence_still_fails(self):
        for text in ('ABC TRAINING SDN BHD\nIKBN PEKAN\nSURAT TAWARAN\n',
                     'POLITEKNIK SWASTA ABC\nPENGESAHAN PELAJAR\nNama : Ali\n',
                     'KOLEJ ABC\nRakan Strategik IKBN\nSURAT TAWARAN\n',
                     _letter('IKBN PEKAN\nPusat Latihan Kemahiran')):     # round 6 (item 1)
            with self.subTest(text=text.splitlines()[0]):
                self.assertEqual(ruled_offer(text, _r(0.05), 'not_offer_letter', 'r', MODEL_VERSION)['status'],
                                 'not_offer_letter')

    def test_the_lift_is_learnable(self):
        out = ruled_offer(self.BROKEN['polytechnic confirmation, thin'], _r(0.1), 'not_offer_letter', 'r', MODEL_VERSION)
        self.assertEqual(ruling_of(out), 'confirmation_unverified')


class H1OwnUnitsAreNotOtherOrganisations(SimpleTestCase):
    def test_a_ums_division_line_keeps_a_full_confirmation_genuine(self):
        _t, out = _conf('UNIVERSITI MALAYSIA SABAH\nACADEMIC SERVICES DIVISION', p=0.3)
        self.assertEqual(out['status'], 'genuine')

    def test_an_ikbn_student_services_unit_line_keeps_the_letter(self):
        self.assertEqual(_g(_letter('INSTITUT KEMAHIRAN BELIA NEGARA (IKBN) PEKAN\nSTUDENT SERVICES UNIT'))['status'],
                         'genuine')


class H2EnglishPublicLines(SimpleTestCase):
    def test_english_ministry_lines_are_public(self):
        for head in ('POLITEKNIK CONTOH\nMINISTRY OF HIGHER EDUCATION',
                     'POLITEKNIK CONTOH\nDEPARTMENT OF POLYTECHNIC AND COMMUNITY COLLEGE EDUCATION\n'
                     'KEMENTERIAN PENDIDIKAN TINGGI'):
            with self.subTest(head=head.splitlines()[1]):
                self.assertEqual(confirmation_kind(_conf(head)[0], 0.2), 'confirmation_polytechnic')
        self.assertEqual(confirmation_kind(_conf('UNIVERSITI MALAYSIA SABAH\nCENTRE FOR FOUNDATION STUDIES')[0], 0.3),
                         'confirmation_ums')
        self.assertEqual(confirmation_kind(_conf('UNIVERSITI MALAYSIA SABAH\nFACULTY OF PSYCHOLOGY AND EDUCATION')[0],
                                           0.3), 'confirmation_ums')

    def test_english_first_tvet_letterheads_are_institutes(self):
        for head in ('ADVANCED TECHNOLOGY TRAINING CENTRE (ADTEC) SHAH ALAM\nJABATAN TENAGA MANUSIA',
                     'INDUSTRIAL TRAINING INSTITUTE (ILP) KEPALA BATAS\nJABATAN TENAGA MANUSIA',
                     'NATIONAL YOUTH SKILLS INSTITUTE (IKBN) PEKAN\nKEMENTERIAN BELIA DAN SUKAN',
                     'MARA SKILLS INSTITUTE (IKM) BESUT\nMAJLIS AMANAH RAKYAT',
                     'MARA HIGHER SKILLS COLLEGE (KKTM) KEMAMAN\nMAJLIS AMANAH RAKYAT'):
            with self.subTest(head=head.splitlines()[0]):
                self.assertNotEqual(_g(_letter(head))['status'], 'not_offer_letter')


class H3TheUnlabelledAddresseeBlock(SimpleTestCase):
    def test_an_estate_address_before_nama_does_not_fail_a_real_letter(self):
        text = REAL.replace('Nama : Ali bin Abu\n', 'ALI A/L MUTHU\nLadang Sungai Contoh Sdn Bhd\n31000 Batu Gajah\n'
                                                    'Perak\nNama : Ali bin Abu\n')
        self.assertNotEqual(_g(text)['status'], 'not_offer_letter')

    def test_an_institution_in_that_block_still_fails(self):
        text = REAL.replace('Nama : Ali bin Abu\n', 'ABC COLLEGE SDN BHD\nJalan Contoh\n31000 Batu Gajah\n'
                                                    'Nama : Ali bin Abu\n')
        self.assertEqual(_g(text)['status'], 'not_offer_letter')


class Low4CampusAfterTheName(SimpleTestCase):
    def test_a_campus_or_services_word_after_an_allowed_name_is_its_unit(self):
        for line in ('IKTBN KAMPUS SEPANG', 'KKTM TECH CAMPUS'):
            with self.subTest(line=line):
                self.assertEqual(_first_institution(_folded_lines(line), (' IKTBN ', ' KKTM ')), 'allowed')


class Medium5PrivateNamesBesideRujOrTarikh(SimpleTestCase):
    def test_a_private_name_sharing_the_reference_or_date_line_is_read(self):
        for head in ('INSTITUT KEMAHIRAN MARA\nUNIKL Ruj : 1', 'INSTITUT KEMAHIRAN MARA\nGERMAN MALAYSIAN INSTITUTE '
                     'Tarikh : 1 Jun 2026', 'IKBN PEKAN\nABC ENTERPRISE Ruj : 1',
                     'IKBN PEKAN\nRakan Strategik ABC Tarikh 1 Jun 2026'):
            with self.subTest(head=head.replace('\n', ' / ')):
                self.assertNotEqual(_g(_letter(head))['status'], 'genuine')


class Low6GluedSplittingNeedsARealLayer(SimpleTestCase):
    def test_a_long_filler_line_is_not_split(self):
        filler = ' '.join(['A'] * 30 + ['NAMA', 'ALI', 'PROGRAM', 'X', 'SESI', 'Y', 'TARIKH', 'Z'] + ['B'] * 10)
        self.assertEqual(len(_unglued(_folded_lines(filler))), 1)

    def test_a_real_glued_layer_is_split(self):
        glued = ' '.join(['UNIVERSITI MALAYSIA SABAH', 'RUJUKAN UMS 1', 'TARIKH 1 JUN 2026', 'PENGESAHAN PELAJAR',
                          'NAMA ALI BIN ABU', 'KAD PENGENALAN 080808105566', 'PROGRAM IJAZAH CONTOH',
                          'SEMESTER TIGA', 'SESI 2026 2027', 'STATUS AKTIF', 'TEMPOH EMPAT TAHUN',
                          'YANG BENAR PENGARAH'] + ['KANDUNGAN'] * 8)
        self.assertGreater(len(_unglued(_folded_lines(glued))), 8)


class Low7CompanyNamesAndIslamic(SimpleTestCase):
    def test_a_sponsor_with_the_letterheads_own_name_keeps_the_veto(self):
        text = _letter('MERCU JAYA\nIKBN PEKAN', extra='Penaja : Mercu Jaya Sdn Bhd\n')
        self.assertEqual(_g(text)['status'], 'not_offer_letter')

    def test_a_campus_or_technology_word_beside_the_company_keeps_the_veto(self):
        for line in ('Penaja : ABC Campus Sdn Bhd', 'Penaja : ABC Teknologi Sdn Bhd', 'Pembekal : ABC Sdn Bhd\nTechnology Campus'):
            with self.subTest(line=line):
                self.assertEqual(_g(_letter('IKBN PEKAN', extra=line + '\n'))['status'], 'not_offer_letter')

    def test_islamic_is_finance_only_beside_a_bank_or_berhad(self):
        from apps.scholarship.genuineness.offer_rulings import _incidental
        self.assertTrue(_incidental(_folded_lines('Akaun Maybank Islamic Berhad'), 0))
        self.assertFalse(_incidental(_folded_lines('ABC Islamic College Sdn Bhd'), 0))
