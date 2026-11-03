"""Corpus-gaps C1 (MODEL_VERSION 1.8.0, owner rulings A + B, 2026-10-26): an offer from a KNOWN
public TVET issuer we have not fingerprinted reads NOT CHECKED — no genuineness penalty, never a
block, never an official-document request, a plain officer line — and a private college gets an
honest reason. Everything else scores EXACTLY as before.

SUPERSEDED IN PART (offer exact-read S6, MODEL_VERSION 1.23.0, owner 2026-11-03 Q2 + rulings 2 / 7):
a closed-list TVET offer named on the letterhead WITH an offer body now reads GENUINE (at any band), not
NOT CHECKED; a private college's suspect-band offer (incl. KPTM / UniKL, ruling C) now reads
not_offer_letter. NOT CHECKED remains for a body-less suspect-band TVET page. The guards (letterhead
only, offer words, sponsor line, private MARA, bare acronyms) are pinned unchanged below.

The "as before" half is pinned against `_pre_c1`, the 1.7.0 scorer's own rule re-stated here (best
family by score, `band_for`, the n/m reason), so a change to any fingerprinted family's outcome
shows as a diff, not as a number someone re-typed.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.genuineness import assess, score_signatures, signature_genuineness
from apps.scholarship.genuineness.bands import NOT_CHECKED, band_for, canonical_status
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, _private_arm_offer
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests import test_doc_signatures as fixtures
from apps.scholarship.tests.factories import make_application, make_student

STUDENT, STUDENT_NRIC = 'Kavitha A/P Raman', '080808-10-5566'

# Request #47's shape: a Belia & Sukan (IKBN, under ILKBS) offer. Against the nearest pattern (the
# university family) it finds only the offer line + a registration date: p=0.40 → 'suspect' at 1.7.0.
ILKBS_BODY = """TAWARAN KEMASUKAN KE INSTITUSI LATIHAN KEMENTERIAN BELIA DAN SUKAN (ILKBS) SESI 2026
NAMA : KAVITHA A/P RAMAN
NO. KAD PENGENALAN : 080808-10-5566
PROGRAM : SIJIL KEMAHIRAN MALAYSIA TAHAP 3 TEKNOLOGI AUTOMOTIF
TARIKH LAPOR DIRI : 5 JULAI 2026
"""
# S6 review round 2: Q2's genuine needs a real letter's structure (reference, date, title, candidate, a
# closing after the title), so request #47's twin carries them, as the real letter does.
ILKBS_OFFER = ("KEMENTERIAN BELIA DAN SUKAN MALAYSIA\nINSTITUT KEMAHIRAN BELIA NEGARA (IKBN) PEKAN\n"
               "Rujukan : KBS.600-1/2/3\nTarikh : 1 Jun 2026\n" + ILKBS_BODY + "Sekian, terima kasih.\nYang benar,\nPENGARAH\n")
# The same body with no issuer in it, and forged under an issuer that is NOT on the closed list.
NEUTRAL_BODY = ILKBS_BODY.replace('INSTITUSI LATIHAN KEMENTERIAN BELIA DAN SUKAN (ILKBS)',
                                  'PUSAT LATIHAN BINTANG')
FORGED_UNNAMED = "PUSAT LATIHAN BINTANG NUSANTARA\nCAWANGAN UTARA\n" + NEUTRAL_BODY
# A cropped public-university letter whose letterhead also names MARA as the sponsor: the UA name
# is on the page, so it stays in the university family's band — never "not checked".
UA_WITH_MARA_SPONSOR = """UNIVERSITI MALAYSIA PAHANG
PENAJA : MAJLIS AMANAH RAKYAT (MARA)
TAWARAN KEMASUKAN
"""
# A private college that names JPK and MARA only in its BODY (accreditation / sponsorship), well
# past the letterhead: the net must not excuse it.
_FILLER = 'Dengan sukacitanya dimaklumkan bahawa permohonan anda telah diproses dengan teliti. ' * 10
PRIVATE_SKILLS_COLLEGE = ("KOLEJ TEKNIKAL CEMERLANG\nTAWARAN KEMASUKAN\n" + _FILLER
                          + "\nProgram diiktiraf oleh Jabatan Pembangunan Kemahiran (JPK).\n"
                          "Pembiayaan Majlis Amanah Rakyat (MARA) boleh dipohon.\n")


def _pre_c1(text):
    """The 1.7.0 offer outcome for `text` (no TVET net, the nearest family's reason)."""
    r = score_signatures(text, doc_type='offer_letter')
    status = band_for(r['probability'])
    status = 'not_offer_letter' if status == 'not_type' else status
    n = len(r['present'])
    reason = (f"{n}/{n + len(r['missing'])} {r['type'].replace('_', ' ')} signatures present "
              f"(p={r['probability']:.2f}); missing: {', '.join(r['missing'][:4]) or 'none'}")
    return status, r['type'], r['probability'], reason


class TheScorer(TestCase):

    def test_request_47_ilkbs_reads_genuine(self):
        self.assertEqual(_pre_c1(ILKBS_OFFER)[:3], ('suspect', 'ua_offer', 0.4))   # what 1.7.0 said
        g = signature_genuineness(ILKBS_OFFER, doc_type='offer_letter')
        self.assertEqual((g['status'], g['type'], g['model_version']),
                         ('genuine', 'tvet_belia_sukan', MODEL_VERSION))          # S6 Q2 (was NOT CHECKED)
        self.assertIn('Kementerian Belia dan Sukan', g['reason'])
        self.assertEqual(assess('offer_letter', ocr_text=ILKBS_OFFER)['status'], 'genuine')

    def test_a_body_less_tvet_page_in_the_suspect_band_keeps_not_checked(self):
        """S6: Q2's genuine needs an offer body; without one the 1.8.0 net still answers."""
        text = 'INSTITUT KEMAHIRAN BELIA NEGARA PEKAN\nTAWARAN KEMASUKAN\nPejabat Pendaftar\nAdalah muktamad\n'
        g = signature_genuineness(text, doc_type='offer_letter')
        self.assertEqual((g['status'], g['type']), (NOT_CHECKED, 'tvet_belia_sukan'))

    def test_the_regression_corpus_entry_holds_on_its_synthetic_twin(self):
        """`eval/labels.json` → `offer_letter__req47__ilkbs`, through the harness's own check."""
        from apps.scholarship.eval import regression_check as rc
        self.assertTrue(rc.signature_status({}, ILKBS_OFFER, 'genuine', doc_type='offer_letter')[0])

    def test_each_ministry_on_the_closed_list_is_recognised(self):
        for head, key in (('TVETMARA\nINSTITUT KEMAHIRAN MARA BESUT', 'tvet_mara'),
                          ('KKTM KEMAMAN', 'tvet_mara'),
                          ('JABATAN TENAGA MANUSIA\nADTEC SHAH ALAM', 'tvet_jtm'),
                          ('ILP KEPALA BATAS', 'tvet_jtm'),
                          ('IKTBN SEPANG', 'tvet_belia_sukan')):
            with self.subTest(head=head):
                g = signature_genuineness(f'{head}\n{NEUTRAL_BODY}', doc_type='offer_letter')
                # S6 round 2: no letter structure (no reference / closing) → the 1.8.0 net, NOT CHECKED
                self.assertEqual((g['status'], g['type']), (NOT_CHECKED, key))

    def test_an_acronym_matches_only_as_a_whole_word(self):
        g = signature_genuineness('PUSAT ILPS SERANTAU\n' + FORGED_UNNAMED, doc_type='offer_letter')
        self.assertNotEqual(g['status'], NOT_CHECKED)

    def test_a_forged_letter_from_an_unnamed_issuer_scores_exactly_as_before(self):
        g = signature_genuineness(FORGED_UNNAMED, doc_type='offer_letter')
        self.assertEqual((g['status'], g['type'], g['probability'], g['reason']), _pre_c1(FORGED_UNNAMED))
        self.assertEqual(g['status'], 'suspect')

    def test_every_fingerprinted_family_scores_exactly_as_before(self):
        for name in ('GENUINE_STPM_OFFER', 'GENUINE_MATRIC_OFFER', 'GENUINE_POLY_OFFER',
                     'CROPPED_STPM_OFFER', 'UNIVERSITY_OFFER', 'GENUINE_PISMP_OFFER',
                     'PISMP_ANNOUNCEMENT', 'GENUINE_UTHM_OFFER', 'GENUINE_UPNM_OFFER'):
            text = getattr(fixtures, name)
            with self.subTest(fixture=name):
                g = signature_genuineness(text, doc_type='offer_letter')
                self.assertEqual((g['status'], g['type'], g['probability'], g['reason']), _pre_c1(text))

    def test_a_family_letter_naming_mara_stays_in_its_family(self):
        g = signature_genuineness(UA_WITH_MARA_SPONSOR, doc_type='offer_letter')
        self.assertEqual((g['status'], g['type']), ('suspect', 'ua_offer'))
        self.assertEqual(g['reason'], _pre_c1(UA_WITH_MARA_SPONSOR)[3])

    def test_a_private_college_says_private_college_and_keeps_its_band(self):
        for text in (fixtures.PRIVATE_UNIV_OFFER, PRIVATE_SKILLS_COLLEGE):
            with self.subTest(text=text[:30]):
                g = signature_genuineness(text, doc_type='offer_letter')
                status, family, p, _old = _pre_c1(text)
                self.assertEqual((g['status'], g['type'], g['probability']), (status, family, p))
                self.assertNotEqual(g['status'], NOT_CHECKED)       # TVET words in the BODY only
                self.assertTrue(g['reason'].startswith('private college / university (IPTS)'))

    def test_a_private_company_on_a_tvet_letterhead_is_still_the_private_veto(self):
        text = 'AKADEMI IKBN SDN BHD\n' + ILKBS_BODY
        self.assertTrue(_private_arm_offer(text))
        self.assertEqual(signature_genuineness(text, doc_type='offer_letter')['status'], 'not_offer_letter')

    def test_not_checked_is_no_signal_never_a_fake(self):
        self.assertEqual(canonical_status(NOT_CHECKED, 'offer_letter'), '')
        self.assertGreaterEqual(tuple(map(int, MODEL_VERSION.split('.'))), (1, 8, 0))     # the net shipped at 1.8.0 (C2: 1.8.1)

    def test_the_tvet_pathways_have_a_family(self):
        from apps.scholarship.offer_pathway import pathway_family
        for p in ('ilkbs', 'iljtm', 'kkom'):
            self.assertEqual(pathway_family(p), 'tertiary')


_REG = 'PROGRAM PENGAJIAN : DIPLOMA PERNIAGAAN\nTARIKH PENDAFTARAN : 1 JULAI 2026\n'
# C1 review probes (2026-10-26): each read NOT CHECKED in the first cut. They must score exactly as
# at 7d0f013a (status, family, probability), whatever names they carry.
REVIEW_PROBES = {
    'a typed fake under an ILKBS heading': 'INSTITUT KEMAHIRAN BELIA NEGARA ILKBS\nSurat tawaran\nNama: Ali\n',
    'a JPK skills certificate in the offer slot': (
        'JABATAN PEMBANGUNAN KEMAHIRAN\nKEMENTERIAN SUMBER MANUSIA\nSIJIL KEMAHIRAN MALAYSIA\n'
        'TAHAP 3\nDengan ini diperakui bahawa calon telah memenuhi syarat\n'),
    'a MARA loan letter': ('MAJLIS AMANAH RAKYAT\nBAHAGIAN PENDIDIKAN\nTAWARAN PINJAMAN PELAJARAN MARA\n'
                           + _REG),
    'a page reading only JTM': 'JTM',
    'a private college MARA sponsors': ('KOLEJ BESTARI\nTajaan MAJLIS AMANAH RAKYAT\nTAWARAN KEMASUKAN\n'
                                        + _REG),
}
# Suspect-band letters, one per guard, so each guard is pinned on a letter only it stops.
NO_OFFER_WORDS = ('INSTITUT KEMAHIRAN BELIA NEGARA\nPEJABAT PENDAFTAR\n' + _REG
                  + 'Program ini adalah muktamad.\n')
SHORT_ACRONYM_HEAD = '{}\n' + _FILLER + '\nTAWARAN KEMASUKAN\nTARIKH LAPOR DIRI : 5 JULAI 2026\n'
SPONSOR_ACRONYM = 'PUSAT LATIHAN BINTANG\nDitaja oleh TVETMARA\nTAWARAN KEMASUKAN\n' + _REG
# A genuine UiTM offer's PDF text layer: no letterhead, no full university name — only "UiTM".
UITM_TEXT_LAYER = ('TAWARAN KEMASUKAN KE PROGRAM DIPLOMA\nUiTM Cawangan Sabah Kampus Kota Kinabalu\n'
                   'Kolej Pengajian Perakaunan\n' + _REG)
# Owner ruling C: MARA-owned but PRIVATE, and saying so does not make them public.
KPTM = 'KOLEJ POLY-TECH MARA\nMilik Majlis Amanah Rakyat\nTAWARAN KEMASUKAN\n' + _REG
STRUCT, CLOSE = 'Rujukan : MARA/1/2\nTarikh : 1 Jun 2026\n', 'Sekian.\nYang benar,\nPENGARAH\n'
UNIKL = 'UNIVERSITI KUALA LUMPUR (UniKL)\nMilik Majlis Amanah Rakyat\nTAWARAN KEMASUKAN\n' + _REG


class TheReviewProbes(TestCase):

    def assertAsBefore(self, text):
        g = signature_genuineness(text, doc_type='offer_letter')
        self.assertEqual((g['status'], g['type'], g['probability']), _pre_c1(text)[:3])
        return g

    def test_each_probe_scores_exactly_as_before(self):
        for name, text in REVIEW_PROBES.items():
            if name == 'a typed fake under an ILKBS heading':
                continue                            # S6 round 3: the safety rule — see the test below
            with self.subTest(name):
                g = self.assertAsBefore(text)       # S6 review H7: no positive private sign, so as before
                self.assertNotIn(g['status'], (NOT_CHECKED, 'genuine'))

    def test_a_fake_below_the_suspect_floor_is_never_not_checked(self):
        """Rule 1: the net is the suspect band only — the typed fake and the bare page stay fakes."""
        self.assertEqual(self.assertAsBefore(REVIEW_PROBES['a page reading only JTM'])['status'], 'not_offer_letter')
        # S6 round 3 (the safety rule): a closed-list body on the page, no private evidence, below the floor
        # → suspect (a person decides), never a fail — the typed fake is no longer a fake.
        self.assertEqual(signature_genuineness(REVIEW_PROBES['a typed fake under an ILKBS heading'],
                                               doc_type='offer_letter')['status'], 'suspect')

    def test_a_sponsor_is_not_the_issuer(self):
        # S6 review H7: a fail needs POSITIVE private evidence; this letterhead has none (only the absence of a
        # public word), so it stays suspect — a person decides. KPTM / UniKL (named private) do fail, below.
        g = signature_genuineness(REVIEW_PROBES['a private college MARA sponsors'], doc_type='offer_letter')
        self.assertEqual(g['status'], 'suspect')
        self.assertTrue(g['reason'].startswith('private college / university (IPTS)'))
        self.assertNotEqual(self.assertAsBefore(SPONSOR_ACRONYM)['status'], NOT_CHECKED)

    def test_a_suspect_letter_with_no_offer_wording_is_not_excused(self):
        g = self.assertAsBefore(NO_OFFER_WORDS)
        self.assertEqual((g['status'], g['reason']), ('suspect', _pre_c1(NO_OFFER_WORDS)[3]))

    def test_a_bare_three_letter_acronym_needs_offer_wording_on_the_letterhead(self):
        self.assertEqual(self.assertAsBefore(SHORT_ACRONYM_HEAD.format('JTM'))['status'], 'suspect')
        g = signature_genuineness(SHORT_ACRONYM_HEAD.format('ADTEC'), doc_type='offer_letter')
        self.assertEqual((g['status'], g['type']), (NOT_CHECKED, 'tvet_jtm'))   # positive control (no course line: S6 keeps 1.8.0)

    def test_request_47_now_reads_genuine(self):
        self.assertEqual(signature_genuineness(ILKBS_OFFER, doc_type='offer_letter')['status'], 'genuine')

    def test_a_uitm_text_layer_is_never_called_a_private_college(self):
        g = self.assertAsBefore(UITM_TEXT_LAYER)
        self.assertEqual(g['reason'], _pre_c1(UITM_TEXT_LAYER)[3])

    def test_the_mara_colleges_are_public(self):
        for head in ('KOLEJ MARA BANTING', 'KOLEJ PROFESIONAL MARA BERANANG'):
            with self.subTest(head):
                g = signature_genuineness(f'{head}\nTAWARAN KEMASUKAN\n{_REG}', doc_type='offer_letter')
                self.assertEqual((g['status'], g['type']), (NOT_CHECKED, 'tvet_mara'))   # S6 r2: no structure
                g = signature_genuineness(f'{head}\n{STRUCT}TAWARAN KEMASUKAN\nNama : Ali\nNo. Kad Pengenalan : 080808-10-5566\n{_REG}'
                                          'Sila hadir dengan dokumen asal.\nTawaran ini tertakluk kepada syarat.\n'
                                          f'Sila sahkan penerimaan.\nTerima kasih.\n{CLOSE}',
                                          doc_type='offer_letter')
                self.assertEqual((g['status'], g['type']), ('genuine', 'tvet_mara'))      # with it: Q2

    def test_kptm_and_unikl_are_mara_owned_but_private(self):
        for name, text in (('KPTM', KPTM), ('UniKL', UNIKL)):
            with self.subTest(name):
                g = signature_genuineness(text, doc_type='offer_letter')
                self.assertEqual(g['status'], 'not_offer_letter')      # S6 rulings 2 / 7 (was suspect)
                self.assertIn('private college / university (IPTS)', g['reason'])
                self.assertTrue(g['reason'].startswith('[S6 ruling: private_offer]'))   # learnable


#: S6: a TVET page with no offer body still reads NOT CHECKED (the 1.8.0 net) — the doors below pin it.
BODYLESS_TVET = 'INSTITUT KEMAHIRAN BELIA NEGARA PEKAN\nTAWARAN KEMASUKAN\nPejabat Pendaftar\nAdalah muktamad\n'


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TheDoors(TestCase):
    """Upload extraction stores NOT CHECKED, and every reader downstream takes it as no signal. (S6: a
    letter WITH an offer body now reads genuine — `test_the_upload_stores_a_tvet_offer_as_genuine`.)"""

    def setUp(self):
        self.app = make_application('shortlisted', student=make_student(name=STUDENT, nric=STUDENT_NRIC),
                                    chosen_pathway='ilkbs')

    def _upload(self, text):
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter', storage_path=f'{self.app.id}/of/x')
        fields = {'candidate_name': STUDENT, 'candidate_nric': STUDENT_NRIC,
                  'programme': 'Sijil Kemahiran Malaysia Tahap 3', 'institution': 'IKBN Pekan'}
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': text, 'error': None}), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': fields, 'warnings': [], 'error': ''}):
            result = vision.run_field_extraction_for_document(doc, names=[])
        doc.vision_fields = dict(result, student_verdict='ok')
        doc.save(update_fields=['vision_fields'])
        return doc

    def test_the_upload_stores_not_checked_unfolded(self):
        auth = self._upload(BODYLESS_TVET).vision_fields['authenticity']
        self.assertEqual((auth['status'], auth['doc_seen'], auth['model_version']),
                         (NOT_CHECKED, 'tvet_belia_sukan', MODEL_VERSION))

    def test_no_block_no_request_no_student_chip(self):
        from apps.scholarship.pathway_engine import offer_band, offer_official_status
        from apps.scholarship.resolution import _ticketable_unresolved
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        from apps.scholarship.services.blockers import _offer_blocks
        doc = self._upload(BODYLESS_TVET)
        self.assertEqual(offer_official_status(doc), 'unknown')
        self.assertEqual(offer_band(doc), '')
        self.assertIs(_offer_blocks(self.app), False)
        self.assertNotIn('offer_not_official', _ticketable_unresolved(self.app))
        self.assertIsNone(ApplicantDocumentSerializer(doc).data['authenticity'])

    def test_the_officer_reads_not_checked_plainly_and_the_card_holds_at_probable(self):
        from apps.scholarship.verdict_engine import build_verdict
        self._upload(BODYLESS_TVET)
        pathway = next(f for f in build_verdict(self.app) if f['fact'] == 'pathway')
        codes = {i['code']: i for i in pathway['unresolved']}
        self.assertIn('offer_issuer_not_checked', codes)
        self.assertEqual(codes['offer_issuer_not_checked']['params']['issuer'],
                         'Kementerian Belia dan Sukan (ILKBS / IKBN / IKTBN)')
        self.assertFalse({'offer_not_official', 'document_not_genuine'} & set(codes))
        self.assertEqual(pathway['status'], 'review')            # TD-114: never Certain unchecked

    def test_the_upload_stores_a_tvet_offer_as_genuine(self):
        """S6 (owner Q2, 2026-11-03): request #47's letter, with its offer body, is a public offer."""
        from apps.scholarship.pathway_engine import offer_band, offer_fails
        from apps.scholarship.services.blockers import _offer_blocks
        doc = self._upload(ILKBS_OFFER)
        auth = doc.vision_fields['authenticity']
        self.assertEqual((auth['status'], auth['doc_seen'], auth['model_version']),
                         ('genuine', 'tvet_belia_sukan', MODEL_VERSION))
        self.assertEqual(offer_band(doc), 'genuine')
        self.assertFalse(offer_fails(doc))
        self.assertIs(_offer_blocks(self.app), False)

    def test_the_same_letter_from_an_unnamed_issuer_reads_suspect_and_never_blocks(self):
        """The positive control: suspect, not official — and since S6 (ruling 8) Probable, never a block."""
        from apps.scholarship.pathway_engine import offer_official_status
        from apps.scholarship.verdict_engine import build_verdict
        doc = self._upload(FORGED_UNNAMED)
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'suspect')
        self.assertEqual(offer_official_status(doc), 'not_genuine')
        pathway = next(f for f in build_verdict(self.app) if f['fact'] == 'pathway')
        self.assertNotIn('offer_issuer_not_checked', [i['code'] for i in pathway['unresolved']])
        self.assertEqual(pathway['status'], 'review')                 # S6: the step alone, Probable
        from apps.scholarship.services.blockers import _offer_blocks
        self.assertIs(_offer_blocks(self.app), False)
