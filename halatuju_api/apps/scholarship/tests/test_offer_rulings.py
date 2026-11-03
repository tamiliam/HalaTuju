"""Offer exact-read S6 — the owner's offer genuineness rulings (`genuineness/offer_rulings.py`,
MODEL_VERSION 1.24.0). Synthetic twins only: every letter below is invented in the wording the real
letters use (`test_no_gitignored_corpus.py`); the corpus measurement is `eval/offer_genuineness_check.py`.

Rulings (decisions.md 2026-11-01 rule 3, 2026-11-03): `not_offer_letter` = a fail; `suspect` = a person
decides; a public TVET offer named on the letterhead is genuine (Q2), a TVET slip suspect; a confirmation
of studies from a polytechnic / UMS / Form-6 college is genuine, from another university suspect; a
private college's suspect offer is not_offer_letter; a portal page / admission printout is never below
suspect; the private-arm veto's "Sdn Bhd" arm does not fail a ministry family's own letter.
"""
from django.test import SimpleTestCase

from apps.scholarship.genuineness import assess
from apps.scholarship.genuineness.offer_rulings import confirmation_kind, ruled_offer
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, signature_genuineness
from apps.scholarship.tests.test_offer_s6_narrowing import baseline_status
from apps.scholarship.genuineness.offer_rulings import ruling_of

# Below the suspect floor (no family signature) the review's H1 rule asks the BODY to name the candidate and
# the institute again (`offer_rulings._tvet`), so the twin carries a letterhead, filler, then its body.
IKM = ("INSTITUT KEMAHIRAN MARA KOTA CONTOH\nMAJLIS AMANAH RAKYAT\nJalan Contoh, 88000 Kota Contoh\n"
       "Rujukan : KBS.600-1/2/3\nTarikh : 1 Jun 2026\nSURAT TAWARAN\n"
       + 'Dengan sukacitanya dimaklumkan bahawa permohonan anda telah diproses dengan teliti.\n' * 8
       + "Nama : Ali bin Abu\nNo. Kad Pengenalan : 080808-10-5566\nTahniah, anda ditawarkan tempat di Institut Kemahiran MARA Kota Contoh untuk "
         "mengikuti Diploma Kemahiran Contoh.\nSila hadir pada 3 Ogos 2026.\nSekian, terima kasih.\nYang benar,\nPENGARAH\n")
IKBN_SLIP = """INSTITUT KEMAHIRAN BELIA NEGARA CONTOH
SLIP TAWARAN UP_TVET FLEXI
Anda ditawarkan kursus Sijil Contoh.
"""
SPONSORED_PRIVATE = """KOLEJ CONTOH SDN BHD
SURAT TAWARAN
Tajaan: Majlis Amanah Rakyat (MARA)
Anda ditawarkan Diploma Contoh.
"""
KPTM = """KOLEJ POLY-TECH MARA CONTOH
SURAT TAWARAN
Anda ditawarkan Diploma Contoh.
"""


def _confirm(head):
    # S6 review H4: a confirmation names the student / programme and scores above `CONFIRM_MIN` (the
    # "Program" / "Institusi" / "Bidang" labels a real one prints give the family score its floor).
    return f"""{head}
Jalan Contoh, 90000 Bandar Contoh
PENGESAHAN PELAJAR
Rujukan : CONTOH/600-1/2
Tarikh : 1 Jun 2026
Dengan ini disahkan bahawa penama di bawah adalah pelajar yang sedang mengikuti pengajian.
Nama : Ali bin Abu
No. Kad Pengenalan : 080808-10-5566
Program : Diploma Contoh
Institusi : Contoh
Bidang : Sains
Sekian, terima kasih.
Yang benar,
PENGARAH
"""


POLY_CONFIRM = _confirm('POLITEKNIK CONTOH\nKEMENTERIAN PENDIDIKAN TINGGI\nJABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI')
UMS_CONFIRM = _confirm('UNIVERSITI MALAYSIA SABAH\nBahagian Perkhidmatan Akademik')
FORM6_CONFIRM = _confirm('KOLEJ TINGKATAN ENAM CONTOH\nKEMENTERIAN PENDIDIKAN MALAYSIA').replace('PENGESAHAN PELAJAR', 'PENGESAHAN BELAJAR')
UM_CONFIRM = _confirm('UNIVERSITI MALAYA\nJabatan Pendaftar')
PRIVATE_CONFIRM = _confirm('KOLEJ CONTOH\nKampus Utama')
JPPKK_ONLY_CONFIRM = _confirm('JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI\nKementerian Pendidikan Tinggi')

UPU_PORTAL = """Semakan Keputusan Permohonan UPU
Tahniah! Permohonan anda berjaya.
Anda ditawarkan Diploma Contoh di Politeknik Contoh.
Keputusan Permohonan : BERJAYA
"""
MATRIC_PORTAL = """Sistem Matrikulasi
Muat Turun Surat Tawaran
Cetak Surat Tawaran
Tawaran Program Matrikulasi
"""
EDAFTAR = """SLIP E-DAFTAR
No. Pelajar : 00000
Program : Ijazah Sarjana Muda Contoh
"""
APPLICATION_SLIP = """SLIP PERMOHONAN UPU
Semakan Keputusan
Tahniah, permohonan anda berjaya dihantar. Pilihan program yang ditawarkan: ...
Muat Turun
"""

POLY_OFFER_SDN = """KEMENTERIAN PENDIDIKAN TINGGI
JABATAN PENDIDIKAN POLITEKNIK DAN KOLEJ KOMUNITI
SURAT TAWARAN PENGAJIAN
Program : Diploma Contoh
Institusi : Politeknik Contoh
Tarikh dan Masa Daftar : 15 Jun 2026
Tawaran ini adalah muktamad dan terbatal sekiranya anda tidak mendaftar di institusi.
Tertakluk kepada kesahihan maklumat dalam borang permohonan.
Bayaran yuran boleh dibuat di Bank Contoh Sdn Bhd.
"""


def _r(p, family='polytechnic'):
    return {'probability': p, 'type': family, 'present': [], 'missing': [], 'scores': {}}


class TestTvetOffers(SimpleTestCase):
    def test_a_public_tvet_offer_on_the_letterhead_is_genuine_at_any_band(self):
        out = signature_genuineness(IKM, doc_type='offer_letter')
        self.assertLess(out['probability'], 0.35)                  # scored "not an offer" before S6
        self.assertEqual((out['status'], out['type']), ('genuine', 'tvet_mara'))
        self.assertEqual(out['model_version'], '1.24.0')

    def test_a_tvet_offer_slip_is_suspect_not_a_fail(self):
        out = signature_genuineness(IKBN_SLIP, doc_type='offer_letter')
        self.assertEqual((out['status'], out['type']), ('suspect', 'tvet_belia_sukan'))

    def test_a_sponsor_line_or_a_private_mara_college_never_reads_as_a_public_offer(self):
        for text in (SPONSORED_PRIVATE, KPTM):
            with self.subTest(text=text.splitlines()[0]):
                self.assertNotEqual(signature_genuineness(text, doc_type='offer_letter')['status'], 'genuine')

    def test_assess_stores_it_the_same(self):
        self.assertEqual(assess('offer_letter', ocr_text=IKM)['status'], 'genuine')


class TestConfirmationLetters(SimpleTestCase):
    def test_kinds(self):
        self.assertEqual(confirmation_kind(POLY_CONFIRM), 'confirmation_polytechnic')
        self.assertEqual(confirmation_kind(UMS_CONFIRM), 'confirmation_ums')
        self.assertEqual(confirmation_kind(FORM6_CONFIRM), 'confirmation_form6')
        self.assertEqual(confirmation_kind(UM_CONFIRM), '')     # round 7: no "another university" hedge
        self.assertEqual(confirmation_kind(PRIVATE_CONFIRM), '')
        self.assertEqual(confirmation_kind(IKM), '')               # no confirmation title

    def test_a_private_institution_confirmation_is_never_a_no_private_wing_one(self):
        self.assertEqual(confirmation_kind(_confirm('KOLEJ POLY-TECH MARA CONTOH\nPOLITEKNIK CONTOH')), '')
        self.assertEqual(confirmation_kind(_confirm('POLITEKNIK CONTOH SDN BHD')), '')

    def test_the_jppkk_department_alone_is_not_a_polytechnic(self):
        self.assertEqual(confirmation_kind(JPPKK_ONLY_CONFIRM), '')

    def test_no_private_wing_reads_genuine_another_university_suspect_a_private_college_unchanged(self):
        for text, want in ((POLY_CONFIRM, 'genuine'), (UMS_CONFIRM, 'genuine'), (FORM6_CONFIRM, 'genuine'),
                           (UM_CONFIRM, baseline_status(UM_CONFIRM)),      # round 7: the baseline
                           (PRIVATE_CONFIRM, 'not_offer_letter')):
            with self.subTest(want=want, head=text.splitlines()[0]):
                self.assertEqual(signature_genuineness(text, doc_type='offer_letter')['status'], want)


class TestPrintoutsAndPrivate(SimpleTestCase):
    def test_portal_pages_and_an_edaftar_slip_are_never_below_suspect(self):
        for text in (UPU_PORTAL, MATRIC_PORTAL, EDAFTAR):
            with self.subTest(head=text.splitlines()[0]):
                self.assertEqual(signature_genuineness(text, doc_type='offer_letter')['status'], 'suspect')

    def test_an_application_slip_stays_not_an_offer(self):
        self.assertEqual(signature_genuineness(APPLICATION_SLIP, doc_type='offer_letter')['status'],
                         'not_offer_letter')

    def test_a_private_college_offer_in_the_suspect_band_is_not_an_offer(self):
        text = 'KOLEJ CONTOH\nKampus Utama\nTAWARAN KEMASUKAN BERSYARAT\nAnda ditawarkan Diploma Contoh.'
        out = ruled_offer(text, _r(0.45, 'ua_offer'), 'suspect', 'r', MODEL_VERSION)
        # S6 round 7 (the narrowing, owner option 1): a conditional offer is no letterhead proof: the baseline (suspect, IPTS reason)
        self.assertEqual(out['status'], 'suspect')
        self.assertIn('IPTS', out['reason'])
        blocked = ruled_offer(text.replace('KOLEJ CONTOH', 'KOLEJ CONTOH SDN BHD'), _r(0.45, 'ua_offer'), 'suspect',
                              'r', MODEL_VERSION)
        self.assertEqual(blocked['status'], 'not_offer_letter')

    def test_a_public_suspect_band_offer_stays_suspect(self):
        text = 'UNIVERSITI MALAYA\nPemakluman\nTawaran kemasukan bersyarat.'
        self.assertEqual(ruled_offer(text, _r(0.45, 'ua_offer'), 'suspect', 'r', MODEL_VERSION)['status'],
                         'suspect')

    def test_a_printout_in_the_suspect_band_is_not_demoted(self):
        self.assertEqual(ruled_offer(UPU_PORTAL, _r(0.45, 'ua_offer'), 'suspect', 'r', MODEL_VERSION)['status'],
                         'suspect')


class TestPrivateArmVeto(SimpleTestCase):
    def test_a_ministry_family_letter_naming_a_bank_sdn_bhd_is_not_vetoed(self):
        # S6 round 8 (almost no excuses): only a closed-list bank's own "Berhad" excuses a company line; an
        # unlisted "Bank Contoh Sdn Bhd" is a private marker, so the pre-S6 veto stands (the baseline).
        out = signature_genuineness(POLY_OFFER_SDN, doc_type='offer_letter')
        self.assertEqual(out['status'], baseline_status(POLY_OFFER_SDN))
        self.assertEqual(ruling_of(out), '')

    def test_a_private_college_on_a_sdn_bhd_letterhead_is_still_vetoed(self):
        text = ('KOLEJ CONTOH SDN BHD\nSURAT TAWARAN PENGAJIAN\nProgram : Diploma Contoh\nInstitusi : Kolej Contoh\n'
                'Tarikh dan Masa Daftar : 15 Jun 2026\nKementerian Pendidikan Tinggi')
        self.assertEqual(signature_genuineness(text, doc_type='offer_letter')['status'], 'not_offer_letter')

    def test_a_university_letter_with_sdn_bhd_is_still_vetoed(self):
        text = ('UNIVERSITI TEKNOLOGI MALAYSIA\nTAWARAN KEMASUKAN\nPejabat Pendaftar\nAdalah muktamad\n'
                'Program Pengajian\nTarikh Pendaftaran\nDikendalikan oleh Contoh Sdn Bhd')
        self.assertEqual(signature_genuineness(text, doc_type='offer_letter')['status'], 'not_offer_letter')

    def test_space_is_still_vetoed_on_any_letter(self):
        text = POLY_OFFER_SDN.replace('Bank Contoh Sdn Bhd', 'UTM SPACE')
        self.assertEqual(signature_genuineness(text, doc_type='offer_letter')['status'], 'not_offer_letter')


class TestNothingElseMoves(SimpleTestCase):
    def test_a_genuine_band_offer_is_untouched_and_carries_the_new_version(self):
        out = signature_genuineness(POLY_OFFER_SDN.replace('Bayaran yuran boleh dibuat di Bank Contoh Sdn Bhd.', ''),
                                    doc_type='offer_letter')
        self.assertEqual((out['status'], out['type'], out['model_version']), ('genuine', 'polytechnic', '1.24.0'))

    def test_a_junk_page_stays_not_an_offer(self):
        self.assertEqual(signature_genuineness('E-TICKET\nFlight XX123\nPassenger', doc_type='offer_letter')['status'],
                         'not_offer_letter')
