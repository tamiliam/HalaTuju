"""Offer exact-read S6 — the adversarial review's findings (2026-11-03), one synthetic regression each.
Every letter is invented (`test_no_gitignored_corpus.py`). H = High, M = Medium, L = Low.
"""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship.genuineness.offer_rulings import confirmation_kind, ruled_offer
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, signature_genuineness


def _status(text):
    return signature_genuineness(text, doc_type='offer_letter')['status']


def _r(p, family='ua_offer'):
    return {'probability': p, 'type': family, 'present': [], 'missing': [], 'scores': {}}


_FILLER = 'Dengan sukacitanya dimaklumkan bahawa permohonan anda telah diproses dengan teliti.\n' * 9
#: A real-shaped IKM letter that scores below the suspect floor (a photo): the letterhead names MARA's TVET
#: arm, the body names the candidate and the institute again.
LOW_SCORE_IKM = ('TVETMARA\nMAJLIS AMANAH RAKYAT\nRujukan : KBS.600-1/2/3\nTarikh : 1 Jun 2026\nSURAT TAWARAN\n' + _FILLER
                 + 'NAMA : ALI BIN ABU\nNo. Kad Pengenalan : 080808-10-5566\nPusat : INSTITUT KEMAHIRAN MARA CONTOH\nProgram : Diploma Kemahiran Contoh\n'
                 'Tarikh lapor diri : 3 Ogos 2026\nSekian, terima kasih.\nYang benar,\nPENGARAH\n')


class H1TheTypedFake(SimpleTestCase):
    def test_a_short_typed_page_under_an_institute_is_not_genuine(self):
        fake = 'INSTITUT KEMAHIRAN MARA\nSURAT TAWARAN\nProgram Diploma\nTarikh daftar 1 Jan\n'
        self.assertNotEqual(_status(fake), 'genuine')

    def test_below_the_floor_the_body_must_name_the_candidate_and_the_institute(self):
        self.assertEqual(_status(LOW_SCORE_IKM), 'genuine')
        self.assertNotEqual(_status(LOW_SCORE_IKM.replace('No. Kad Pengenalan : 080808-10-5566', '').replace('NAMA : ALI BIN ABU\n', '')), 'genuine')


class H1TheOfficersRequest(TestCase):
    def test_a_ruling_made_genuine_offer_never_closes_an_officers_own_request(self):
        from types import SimpleNamespace
        from apps.scholarship.genuineness.offer_issuers import officer_must_close
        item = SimpleNamespace(source='officer', doc_type='offer_letter')
        for seen in ('tvet_mara', 'confirmation_polytechnic'):
            doc = SimpleNamespace(doc_type='offer_letter',
                                  vision_fields={'authenticity': {'status': 'genuine', 'doc_seen': seen}})
            self.assertTrue(officer_must_close(doc, item), seen)
        family = SimpleNamespace(doc_type='offer_letter',
                                 vision_fields={'authenticity': {'status': 'genuine', 'doc_seen': 'polytechnic'}})
        self.assertFalse(officer_must_close(family, item))


class H2AnAgencyIsNotAnInstitute(SimpleTestCase):
    def test_a_private_academy_accredited_by_jpk_is_not_genuine(self):
        text = ('AKADEMI KEMAHIRAN CEMERLANG\nKod Pusat JPK : A0000\nDiiktiraf Jabatan Pembangunan Kemahiran\n'
                'SURAT TAWARAN\nProgram Sijil Kemahiran\nTarikh pendaftaran : 1 Julai 2026\n')
        self.assertNotEqual(_status(text), 'genuine')

    def test_an_agency_alone_is_not_genuine(self):
        for head in ('MAJLIS AMANAH RAKYAT', 'JABATAN TENAGA MANUSIA', 'KEMENTERIAN BELIA DAN SUKAN'):
            with self.subTest(head=head):
                self.assertNotEqual(_status(f'{head}\nSURAT TAWARAN\nProgram Sijil Contoh\nTarikh pendaftaran 1 Julai\n'),
                                    'genuine')


class H3SponsorsAndMaraOwnedPrivate(SimpleTestCase):
    def test_a_sponsor_line_in_any_wording_never_names_the_issuer(self):
        for line in ('Program Penajaan Majlis Amanah Rakyat', 'Dibiayai oleh Majlis Amanah Rakyat',
                     'Pembiayaan Majlis Amanah Rakyat', 'Biasiswa Majlis Amanah Rakyat'):
            with self.subTest(line=line):
                text = f'KOLEJ CONTOH\n{line}\nSURAT TAWARAN\nProgram Diploma Contoh\nTarikh pendaftaran 1 Julai\n'
                self.assertNotEqual(_status(text), 'genuine')

    def test_kuptm_and_uptm_are_mara_owned_but_private(self):
        for head in ('KOLEJ UNIVERSITI POLY-TECH MARA', 'KOLEJ UNIVERSITI POLY TECH MARA',
                     'UNIVERSITI POLY-TECH MALAYSIA', 'KUPTM', 'UPTM'):
            with self.subTest(head=head):
                text = (f'{head}\nMAJLIS AMANAH RAKYAT\nKOLEJ MARA\nSURAT TAWARAN\nProgram Diploma Contoh\n'
                        'Tarikh pendaftaran 1 Julai\n')
                self.assertNotEqual(_status(text), 'genuine')


class H4ConfirmationsNeedTheirPublicMarks(SimpleTestCase):
    def test_bare_or_private_confirmations_are_not_no_private_wing(self):
        for text in ('POLITEKNIK\nPENGESAHAN PELAJAR\n',
                     'KOLEJ POLITEKNIK SWASTA ABC\nPENGESAHAN PELAJAR\nNama : Ali\nProgram : Diploma\n',
                     'SEKOLAH MENENGAH SWASTA ABC (TINGKATAN ENAM)\nPENGESAHAN PELAJAR\nNama : Ali\nYuran RM 300\n'):
            with self.subTest(head=text.splitlines()[0]):
                self.assertEqual(confirmation_kind(text, 0.2), '')
                self.assertNotEqual(_status(text), 'genuine')

    def test_a_polytechnic_needs_its_ministry_line_and_a_body(self):
        text = 'POLITEKNIK CONTOH\nPENGESAHAN PELAJAR\nNama : Ali\nProgram : Diploma Contoh\n'
        self.assertEqual(confirmation_kind(text, 0.2), '')
        self.assertEqual(confirmation_kind('POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI\n' + text.split('\n', 1)[1],
                                           0.2), 'confirmation_polytechnic')

    def test_a_score_floor(self):
        text = 'POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI\nPENGESAHAN PELAJAR\nNama : Ali\n'
        self.assertEqual(confirmation_kind(text, 0.0), '')
        self.assertEqual(confirmation_kind(text, 0.2), 'confirmation_polytechnic')


class H5APrivateOfferIsNotAPortalPage(SimpleTestCase):
    def test_tahniah_and_berjaya_do_not_lift_a_private_offer(self):
        text = ('KOLEJ UNIVERSITI ABC\nTAHNIAH! Anda telah BERJAYA ditawarkan tempat.\nTawaran Kemasukan\n'
                'Yuran RM 15,000 setahun\n')
        self.assertEqual(_status(text), 'not_offer_letter')

    def test_a_private_sign_never_lifts_a_portal_page(self):
        text = 'Semakan Keputusan\nKeputusan Permohonan\nAnda ditawarkan\nKOLEJ ABC SDN BHD\n'
        self.assertEqual(_status(text), 'not_offer_letter')


class H6TheCompanyComesFirst(SimpleTestCase):
    def test_a_company_letterhead_with_the_ministrys_cooperation_is_vetoed(self):
        text = ('ABC COLLEGE SDN BHD\nSURAT TAWARAN PENGAJIAN\nDengan kerjasama Jabatan Pendidikan Politeknik dan '
                'Kolej Komuniti\nProgram : Diploma\nInstitusi : ABC College\nTarikh dan Masa Daftar : 1 Julai\n')
        self.assertEqual(_status(text), 'not_offer_letter')


class H7PublicCollegesAreNotFailedOnAbsence(SimpleTestCase):
    def test_a_public_college_photographed_without_its_ministry_line_stays_suspect(self):
        for head in ('KOLEJ KOMUNITI SELAYANG', 'AKADEMI SENI BUDAYA DAN WARISAN KEBANGSAAN ASWARA',
                     'KOLEJ MATRIKULASI PERAK', 'KOLEJ VOKASIONAL SHAH ALAM', 'KOLEJ CONTOH'):
            with self.subTest(head=head):
                text = f'{head}\nTawaran Kemasukan\nAnda ditawarkan Diploma Contoh.\n'
                self.assertEqual(ruled_offer(text, _r(0.40), 'suspect', 'r', MODEL_VERSION)['status'], 'suspect')

    def test_positive_private_evidence_or_a_private_conditional_still_fails(self):
        self.assertEqual(ruled_offer('KOLEJ CONTOH SDN BHD\nTawaran Kemasukan\n', _r(0.40), 'suspect', 'r',
                                     MODEL_VERSION)['status'], 'not_offer_letter')
        # S6 round 7 (the narrowing, owner option 1): a private conditional is no letterhead proof: the baseline stays.
        self.assertEqual(ruled_offer('KOLEJ CONTOH\nTawaran Kemasukan Bersyarat\n', _r(0.40), 'suspect', 'r',
                                     MODEL_VERSION)['status'], 'suspect')


class LowTheSlipWordInTheBody(SimpleTestCase):
    def test_a_slip_bayaran_below_the_letterhead_is_not_a_tvet_slip(self):
        text = LOW_SCORE_IKM + 'Sila simpan slip bayaran anda.\n'
        self.assertEqual(_status(text), 'genuine')


class M9NoHearingOnAConfirmation(TestCase):
    def test_no_pathway_hearing_and_confirm_pathway_refuses(self):
        from apps.scholarship.models import ApplicantDocument
        from apps.scholarship.pathway_engine import offer_hearing_ok
        from apps.scholarship.services.confirmation import confirm_pathway
        from apps.scholarship.tests.factories import make_application
        app = make_application('shortlisted', chosen_programme={})
        doc = ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/c',
            vision_fields={'fields': {'programme': 'DIPLOMA CONTOH', 'institution': 'POLITEKNIK CONTOH'},
                           'student_verdict': 'ok',
                           'authenticity': {'status': 'genuine', 'doc_seen': 'confirmation_polytechnic'}},
            vision_run_at=timezone.now())
        self.assertFalse(offer_hearing_ok(doc))
        self.assertFalse(confirm_pathway(app))
        app.refresh_from_db()
        self.assertIsNone(app.pathway_confirmed_at)


class M8TheDryRunStopsOnAStaleBlock(SimpleTestCase):
    def _row(self, **o):
        r = {'app': 7, 'doc': 8, 'stored': 'not_offer_letter', 'open': True, 'band_old': 'Probable',
             'band_new': 'Probable', 'blocked_old': False, 'blocked_new': True, 'chips_old': {}, 'chips_new': {},
             'set_by_offer': False}
        r.update(o)
        return r

    def test_a_new_block_the_rescore_would_lift_is_a_stop(self):
        from apps.scholarship.eval import offer_s6_dry_run as s6
        self.assertEqual(s6.judge([self._row()], {8: 'genuine'})[0], 'STOP')          # keyed by DOCUMENT
        self.assertEqual(s6.judge([self._row()], {8: 'not_offer_letter'})[0], 'GO')

    def test_an_old_block_the_rescore_would_lift_is_listed_for_s7(self):
        from apps.scholarship.eval import offer_s6_dry_run as s6
        verdict, _stop, review, _t = s6.judge([self._row(blocked_old=True)], {8: 'genuine'})
        self.assertEqual((verdict, review['blocked_on_a_stale_call']), ('GO', [7]))
