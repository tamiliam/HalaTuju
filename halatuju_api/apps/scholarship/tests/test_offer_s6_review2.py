"""Offer exact-read S6 — the SECOND adversarial review (2026-11-03): the reviewer's own probes, one
regression each, against the STRUCTURAL rules (owner: "Let us be guided by data … if we allow the model to
hedge now, the issue will never be resolved"). Every letter is invented (`test_no_gitignored_corpus.py`).
"""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship.genuineness.offer_rulings import confirmation_kind, ruled_offer, ruling_of
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, signature_genuineness
from apps.scholarship.tests.test_offer_s6_narrowing import baseline_status

HEAD = 'Rujukan : ABC/600-1/2\nTarikh : 1 Jun 2026\n'
TAIL = 'Sekian, terima kasih.\nYang benar,\nPENGARAH\n'


def _g(text):
    return signature_genuineness(text, doc_type='offer_letter')


def _r(p, family='ua_offer'):
    return {'probability': p, 'type': family, 'present': [], 'missing': [], 'scores': {}}


_FILL = ('Dengan sukacitanya dimaklumkan bahawa anda ditawarkan tempat.\nSila bawa dokumen asal semasa hadir.\n'
         'Tawaran ini tertakluk kepada syarat.\nSila sahkan penerimaan dalam tempoh tujuh hari.\n')


def _offer(head, body='Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\nKursus : Sijil Kemahiran Contoh\nTarikh lapor diri : 3 Ogos 2026\n'):
    return f'{head}\n{HEAD}SURAT TAWARAN KEMASUKAN\n{body}{_FILL}{TAIL}'


REAL_IKBN = _offer('KEMENTERIAN BELIA DAN SUKAN\nINSTITUT KEMAHIRAN BELIA NEGARA (IKBN) PEKAN')


def _fullwidth(s):
    return ''.join(chr(ord(c) + 0xFEE0) if '!' <= c <= '~' else c for c in s)


class Positive(SimpleTestCase):
    def test_a_real_shaped_ikbn_letter_reads_genuine_and_names_its_ruling(self):
        g = _g(REAL_IKBN)
        self.assertEqual((g['status'], g['type']), ('genuine', 'tvet_belia_sukan'))
        self.assertEqual(ruling_of(g), 'tvet_offer')              # learnable: the lift names its rule


class H1PaddingAndShape(SimpleTestCase):
    def test_padding_past_the_letterhead_never_earns_genuine(self):
        for head in ('IKBN', 'ILP KUANTAN'):
            with self.subTest(head=head):
                text = f'{head}\nSURAT TAWARAN\n' + 'x ' * 320 + f'\nNama: A\n{head}\nKursus Sijil\nTarikh 1 Jan\n'
                self.assertNotEqual(_g(text)['status'], 'genuine')

    def test_full_width_letters_are_read_as_letters(self):
        self.assertEqual(_g(_fullwidth(REAL_IKBN))['status'], 'genuine')
        text = _fullwidth('IKBN\nSURAT TAWARAN\n' + 'x ' * 320 + '\nNama: A\nIKBN\nKursus Sijil\nTarikh 1 Jan\n')
        self.assertNotEqual(_g(text)['status'], 'genuine')

    def test_each_part_of_the_structure_is_needed(self):
        for part in ('Rujukan : ABC/600-1/2\n', TAIL, 'Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\n'):
            with self.subTest(missing=part.split()[0]):
                self.assertNotEqual(_g(REAL_IKBN.replace(part, ''))['status'], 'genuine')


class H2TheFirstInstitutionIsTheIssuer(SimpleTestCase):
    def test_a_college_or_academy_named_first_is_not_a_tvet_institute(self):
        for head, mention in (('KOLEJ TEKNIK ABC\nDiiktiraf JABATAN PEMBANGUNAN KEMAHIRAN', 'setara ILP'),
                              ('AKADEMI ABC\nMAJLIS AMANAH RAKYAT', 'dengan kerjasama IKM')):
            with self.subTest(head=head.splitlines()[0]):
                text = _offer(head, f'Nama : Ali\nNo. Kad Pengenalan : 080808-10-5566\nKursus : Sijil Contoh ({mention})\nTarikh lapor diri 3 Ogos 2026\n')
                self.assertNotEqual(_g(text)['status'], 'genuine')


class H3TieUpsAndGmi(SimpleTestCase):
    def test_a_tie_up_under_a_college_letterhead_is_not_genuine(self):
        for line in ('Dengan kerjasama Institut Kemahiran MARA', 'In collaboration with IKM',
                     'Program usahasama IKBN', 'Pinjaman Pendidikan MARA', 'Funded by MARA', 'Scholarship MARA'):
            with self.subTest(line=line):
                text = _offer('KOLEJ ABC\n' + line)
                self.assertNotEqual(_g(text)['status'], 'genuine')

    def test_gmi_is_mara_owned_but_private(self):              # owner 2026-11-03: the programme, not the owner
        text = _offer('GERMAN-MALAYSIAN INSTITUTE\nMAJLIS AMANAH RAKYAT\nKOLEJ MARA')
        self.assertNotEqual(_g(text)['status'], 'genuine')
        self.assertEqual(ruled_offer('GERMAN-MALAYSIAN INSTITUTE\nTawaran Kemasukan\n', _r(0.4), 'suspect', 'r',
                                     MODEL_VERSION)['status'], 'not_offer_letter')


class H4ConfirmationIssuers(SimpleTestCase):
    def test_the_reviewers_confirmation_probes(self):
        for text in (
                'KOLEJ ABC\nPENGESAHAN PELAJAR\nNama : Ali\nlepasan Politeknik Ungku Omar\nKementerian Pendidikan Tinggi\n',
                'PUSAT TUISYEN CEMERLANG\nKelas Tingkatan Enam\nPENGESAHAN PELAJAR\nNama : Ali\nKementerian Pendidikan Malaysia\n',
                'KOLEJ ABC\nPENGESAHAN PELAJAR\nNama : Ali\nProgram usahasama UNIVERSITI MALAYSIA SABAH\n',
                'KOLEJ ABC (TINGKATAN ENAM)\nKEMENTERIAN PENDIDIKAN TINGGI\nPENGESAHAN PELAJAR\nNama : Ali\n'):
            with self.subTest(head=text.splitlines()[0]):
                self.assertEqual(confirmation_kind(text, 0.2), '')

    def test_the_public_issuers_still_qualify(self):
        self.assertEqual(confirmation_kind('POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI\nPENGESAHAN PELAJAR\n'
                                           'Nama : Ali\n', 0.2), 'confirmation_polytechnic')
        self.assertEqual(confirmation_kind('UNIVERSITI MALAYSIA SABAH\nBahagian Akademik\nPENGESAHAN PELAJAR\n'
                                           'Nama : Ali\n', 0.3), 'confirmation_ums')
        self.assertEqual(confirmation_kind('KOLEJ TINGKATAN ENAM CONTOH\nPENGESAHAN BELAJAR\nNama : Ali\n', 0.2),
                         'confirmation_form6')


class H5APrivatePrintoutStaysAFail(SimpleTestCase):
    def test_the_reviewers_printout_probes(self):
        for text in ('KOLEJ UNIVERSITI ABC\nSemakan Keputusan\nKeputusan Permohonan\nTahniah anda ditawarkan\nCetak\n',
                     'ABC UNIVERSITY COLLEGE\nOffer of Admission\nMuat Turun\nCetak\nYuran RM 20000\n',
                     'KOLEJ ABC\nSLIP E-DAFTAR\nTawaran Kemasukan\nYuran RM 9000\n'):
            with self.subTest(head=text.splitlines()[0]):
                self.assertEqual(_g(text)['status'], 'not_offer_letter')


_POLY = ('KEMENTERIAN PENDIDIKAN TINGGI\nJABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI\nRujukan : JPPKK/1\n'
         'Tarikh : 01/06/2026\nALI BIN ABU (000000000000)\n{addr}SURAT TAWARAN PENGAJIAN\nProgram : Diploma Contoh\n'
         'Institusi : Politeknik Contoh\nTarikh dan Masa Daftar : 15 Jun 2026\nTawaran ini adalah muktamad dan '
         'terbatal sekiranya anda tidak mendaftar di institusi.\nTertakluk kepada kesahihan maklumat dalam borang '
         'permohonan.\n{pay}Yang benar,\nPENGARAH\n{foot}')


class H6WhereTheCompanySits(SimpleTestCase):
    def test_a_company_on_a_payment_line_or_the_addressees_estate_is_not_the_issuer(self):
        # S6 round 8 (almost no excuses): an unlisted bank's company is no excuse - the baseline (the veto stands);
        # the addressee's estate, between the reference / date and the title, still is.
        text = _POLY.format(addr='', pay='Bayaran ke akaun Bank Contoh Sdn Bhd.\n', foot='')
        out = _g(text)
        self.assertEqual((out['status'], ruling_of(out)), (baseline_status(text), ''))
        out = _g(_POLY.format(addr='LADANG CONTOH SDN BHD\nPETI SURAT 1, 90000 SANDAKAN\n', pay='', foot=''))
        self.assertEqual((out['status'], ruling_of(out)), ('genuine', 'incidental_company'))

    def test_a_company_anywhere_else_keeps_the_veto(self):
        for addr, foot in (('', 'Hakcipta ABC College Sdn Bhd\n'), ('ABC COLLEGE SDN BHD\n', ''),
                           ('', 'PUSAT TUISYEN ABC SDN BHD\n')):   # round 7: "Sendirian Berhad" in a footer is
                                                                      # the baseline's (no veto, not letterhead)
            with self.subTest(addr=addr, foot=foot):
                self.assertEqual(_g(_POLY.format(addr=addr, pay='', foot=foot))['status'], 'not_offer_letter')

    def test_a_company_above_the_ministry_strip_keeps_the_veto(self):
        text = 'JPPKK | KPT\nABC COLLEGE SDN BHD\n' + _POLY.format(addr='', pay='', foot='')
        self.assertEqual(_g(text)['status'], 'not_offer_letter')
        tuition = 'SEKTOR OPERASI SEKOLAH\nPUSAT TUISYEN ABC SDN BHD\nTAWARAN KE TINGKATAN ENAM\n'
        self.assertEqual(_g(tuition)['status'], 'not_offer_letter')


class H7MediumABankBerhadIsNotPrivate(SimpleTestCase):
    def test_public_bodies_with_bank_lines_are_not_failed(self):
        for text in ('AKADEMI BINAAN MALAYSIA\nLEMBAGA PEMBANGUNAN INDUSTRI PEMBINAAN\nTawaran Kemasukan\n'
                     'Bayaran ke akaun Bank Rakyat Berhad\n',
                     'KOLEJ KEJURURAWATAN CONTOH\nTawaran Kemasukan Bersyarat\n'):
            with self.subTest(head=text.splitlines()[0]):
                self.assertEqual(ruled_offer(text, _r(0.4), 'suspect', 'r', MODEL_VERSION)['status'], 'suspect')

    def test_a_real_tvet_letter_with_a_bank_line_stays_genuine(self):
        text = REAL_IKBN.replace(TAIL, 'Bayaran yuran ke akaun Bank Rakyat Berhad.\n' + TAIL)
        self.assertEqual(_g(text)['status'], 'genuine')


class Learnable(SimpleTestCase):
    def test_every_lift_names_its_ruling(self):
        self.assertEqual(ruling_of(_g(REAL_IKBN)), 'tvet_offer')
        conf = ('POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI\nJalan Contoh, 93050 Kuching\nRujukan : PO/1\n'
                'Tarikh : 1 Jun 2026\nKEPADA SESIAPA YANG BERKENAAN\nPENGESAHAN PELAJAR\nDengan ini disahkan:\n'
                'Nama : Ali\nNo. Kad Pengenalan : 080808-10-5566\nProgram : Diploma\nInstitusi : Contoh\n'
                'Semester : 3\nSekian.\nYang benar,\nPENGARAH\n')   # round 4: a confirmation is 12+ lines
        self.assertEqual(ruling_of(_g(conf)), 'confirmation')
        self.assertEqual(ruling_of(_g('Semakan Keputusan\nKeputusan Permohonan\nAnda ditawarkan\n')), 'printout')
        self.assertEqual(ruling_of(ruled_offer('KOLEJ ABC SDN BHD\nTawaran Kemasukan\n', _r(0.4), 'suspect', 'r',
                                               MODEL_VERSION)), 'private_offer')
        self.assertEqual(ruling_of({'reason': '7/9 polytechnic signatures present'}), '')


class DryRunBuckets(SimpleTestCase):
    def _row(self, **o):
        r = {'app': 7, 'doc': 8, 'stored': 'not_offer_letter', 'open': True, 'band_old': 'Probable',
             'band_new': 'Probable', 'blocked_old': False, 'blocked_new': True, 'chips_old': {}, 'chips_new': {},
             'set_by_offer': False}
        r.update(o)
        return r

    def test_an_app_with_no_rescore_is_its_own_bucket_never_assumed_a_fail(self):
        from apps.scholarship.eval import offer_s6_dry_run as s6
        verdict, _stop, review, _t = s6.judge([self._row()], {})
        self.assertEqual((verdict, review['newly_blocked_no_rescore']), ('GO', [7]))


class LowAStaleConfirmIsLogged(TestCase):
    def test_confirm_pathway_on_a_confirmation_logs_and_writes_nothing(self):
        from apps.scholarship.models import ApplicantDocument
        from apps.scholarship.services.confirmation import confirm_pathway
        from apps.scholarship.tests.factories import make_application
        app = make_application('shortlisted', chosen_programme={})
        ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/c',
            vision_fields={'fields': {'programme': 'DIPLOMA'}, 'student_verdict': 'ok',
                           'authenticity': {'status': 'genuine', 'doc_seen': 'confirmation_ums'}},
            vision_run_at=timezone.now())
        with self.assertLogs('apps.scholarship.services', level='INFO') as logs:
            self.assertFalse(confirm_pathway(app))
        self.assertTrue(any('confirmation-of-studies' in m for m in logs.output))
