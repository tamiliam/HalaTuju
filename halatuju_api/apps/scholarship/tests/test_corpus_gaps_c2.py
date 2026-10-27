"""Corpus-gaps C2 (MODEL_VERSION 1.8.1): UiTM in the public-university family, and the C1 review's
follow-up — an officer's own offer request is never closed by a NOT CHECKED upload.

The UiTM letters below are SYNTHETIC, built from the fixed printed wording of seven real UiTM offers
(PII-free, roadmap C0): no name, NRIC, programme or campus of any applicant. The real OCR texts were
checked by hand against the same scorer (all seven genuine; every other cached offer unchanged) —
they are gitignored PII and never collected here.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.genuineness import signature_genuineness
from apps.scholarship.genuineness.bands import NOT_CHECKED
from apps.scholarship.genuineness.results_doc import (MODEL_VERSION, UA_OFFER_SIGNATURES, _UA_NAMES,
                                                      _norm_fold_upper_alnum, _score_list)
from apps.scholarship.models import ApplicantDocument, ResolutionItem
from apps.scholarship.tests import test_corpus_gaps_c1 as c1
from apps.scholarship.tests import test_doc_signatures as fixtures
from apps.scholarship.tests.factories import make_application, make_student

STUDENT, STUDENT_NRIC = 'Nurul Ain Binti Hamzah', '080909-12-5566'

_UITM_BODY = """SURAT TAWARAN
Sukacita dimaklumkan bahawa anda ditawarkan tempat untuk mengikuti program di UiTM seperti berikut:
No. Kad Pengenalan :
Program :
Mod Pengajian : Sepenuh Masa
Sila hadir mendaftar pada tarikh, masa dan tempat yang ditetapkan.
Tarikh :
MAKLUMAT PENTING
1. Program dan kampus yang ditawarkan adalah muktamad. Sebarang permohonan pertukaran tidak dibenarkan.
2. Tawaran ini adalah terbatal sekiranya terdapat maklumat yang salah.
PENGARAH
"""
UITM_OFFER = 'UNIVERSITI TEKNOLOGI MARA\nBAHAGIAN PENGAMBILAN PELAJAR\n' + _UITM_BODY + 'BAHAGIAN PENGAMBILAN PELAJAR\n'
# d3299's shape: OCR split the letterhead and garbled the office line in the signature block; the
# university's name survives in the footer.
UITM_GARBLED_OFFICE = ('UNIVERSITI TEKNOLOGI\nPengambilan\nMARA\n' + _UITM_BODY
                       + 'Bahagian Pengaman Pelajar\nUNIVERSITI TEKNOLOGI MARA www.uitm.edu.my\n')
# A pemakluman (admission NOTIFICATION) that borrows the generic wording — policy 1.1 keeps it off the
# offer line, so the UiTM line must keep its "PROGRAM DI UITM" (the a31 lesson: 0.40 → 0.70 without it).
UM_PEMAKLUMAN = """UNIVERSITI MALAYA
PEMAKLUMAN KEMASUKAN
Sukacita dimaklumkan bahawa anda ditawarkan tempat untuk mengikuti program Asasi.
Surat tawaran rasmi akan menyusul.
"""
# A DIGITAL PDF's text layer (C2 review): no letterhead, no footer — only UiTM's own clauses name it.
UITM_PDF_TEXT_LAYER = (_UITM_BODY + '3. Calon hanya diterima sebagai pelajar UiTM setelah membuat pendaftaran '
                       'secara dalam talian.\n6. UiTM berhak menukarkan calon ke mana-mana kampus.\n'
                       'BAHAGIAN PENGAMBILAN PELAJAR\n')
# Copiers (C2 review probes): a private university borrowing UiTM's offer line, and a private college
# quoting UiTM's office. Neither may gain UiTM's NAME.
PRIVATE_COPIES_UITM_LINE = ('UNIVERSITI SWASTA CEMERLANG\nSukacita dimaklumkan bahawa anda ditawarkan tempat '
                            'untuk mengikuti program di UiTM\nProgram ini adalah muktamad.\n')
PRIVATE_QUOTES_UITM_OFFICE = 'KOLEJ BESTARI\nBAHAGIAN PENGAMBILAN PELAJAR\nSurat tawaran\nNama :\n'
# A letter carrying only the shorter "Pengambilan Pelajar" (as on a12) is not the UiTM office.
SHORT_OFFICE = 'UNIVERSITI TEKNOLOGI MALAYSIA\nUNIT PENGAMBILAN PELAJAR\nTAWARAN KEMASUKAN\n'

# The 1.8.0 university list, frozen here, so "every other letter is unchanged" is a diff against
# the list C2 replaced rather than a number re-typed from a run.
_UA_1_8_0 = [
    ('public university (UA) name', list(_UA_NAMES), 3, 'text'),
    ('offer/admission line', ['TAWARAN KEMASUKAN'], 3, 'text'),
    ('academic office', ['PEJABAT PENGURUSAN AKADEMIK', 'PUSAT PENGURUSAN AKADEMIK',
                         'BAHAGIAN HAL EHWAL AKADEMIK', 'PEJABAT PENDAFTAR',
                         'PUSAT PEMASARAN DAN KEMASUKAN'], 1, 'text'),
    ('finality / no-change clause', ['PERTUKARAN PROGRAM ADALAH TIDAK DIBENARKAN', 'SEBARANG PERTUKARAN',
                                     'TIDAK DIBENARKAN MENUKAR PROGRAM', 'TAWARAN AKAN DITARIK BALIK',
                                     'ADALAH MUKTAMAD'], 1, 'text'),
    ('Program / Kod Program', ['PROGRAM PENGAJIAN', 'PROGRAM KOD'], 1, 'text'),
    ('registration date', ['TARIKH PENDAFTARAN', 'TARIKH MENDAFTAR', 'TARIKH LAPOR DIRI'], 1, 'text'),
]


def _ua(signatures, text):
    return _score_list(signatures, _norm_fold_upper_alnum(text), False, False)['probability']


class UiTMScoresAsAPublicUniversity(TestCase):

    def test_a_uitm_offer_is_genuine(self):
        g = signature_genuineness(UITM_OFFER, doc_type='offer_letter')
        self.assertEqual((g['status'], g['type'], g['probability'], g['model_version']),
                         ('genuine', 'ua_offer', 0.9, MODEL_VERSION))
        self.assertEqual(_ua(_UA_1_8_0, UITM_OFFER), 0.4)               # what 1.8.0 said: suspect

    def test_a_garbled_office_line_still_clears(self):
        g = signature_genuineness(UITM_GARBLED_OFFICE, doc_type='offer_letter')
        self.assertEqual((g['status'], g['probability']), ('genuine', 0.8))

    def test_a_uitm_pdf_text_layer_is_named_by_its_own_clauses(self):
        """1.8.2: a digital PDF is read through its text layer, which has no letterhead."""
        g = signature_genuineness(UITM_PDF_TEXT_LAYER, doc_type='offer_letter')
        self.assertIn('public university (UA) name', g['present'])
        self.assertEqual((g['status'], g['probability']), ('genuine', 0.9))

    def test_a_copier_never_gains_uitms_name(self):
        for text, band in ((PRIVATE_COPIES_UITM_LINE, 'suspect'), (PRIVATE_QUOTES_UITM_OFFICE, 'not_offer_letter')):
            with self.subTest(text[:24]):
                g = signature_genuineness(text, doc_type='offer_letter')
                self.assertNotIn('public university (UA) name', g['present'])
                self.assertEqual(g['status'], band)

    def test_the_uitm_offer_line_is_not_a_pemakluman(self):
        g = signature_genuineness(UM_PEMAKLUMAN, doc_type='offer_letter')
        self.assertNotIn('offer/admission line', g['present'])
        self.assertEqual(_ua(UA_OFFER_SIGNATURES, UM_PEMAKLUMAN), _ua(_UA_1_8_0, UM_PEMAKLUMAN))

    def test_the_short_office_wording_is_not_uitms(self):
        self.assertEqual(_ua(UA_OFFER_SIGNATURES, SHORT_OFFICE), _ua(_UA_1_8_0, SHORT_OFFICE))

    def test_every_other_letter_scores_exactly_as_under_1_8_0(self):
        texts = {n: getattr(fixtures, n) for n in (
            'GENUINE_STPM_OFFER', 'GENUINE_MATRIC_OFFER', 'GENUINE_POLY_OFFER', 'CROPPED_STPM_OFFER',
            'UNIVERSITY_OFFER', 'GENUINE_PISMP_OFFER', 'PISMP_ANNOUNCEMENT', 'GENUINE_UTHM_OFFER',
            'GENUINE_UPNM_OFFER', 'PRIVATE_UNIV_OFFER')}
        texts.update({'ILKBS_OFFER': c1.ILKBS_OFFER, 'FORGED_UNNAMED': c1.FORGED_UNNAMED,
                      'UITM_TEXT_LAYER': c1.UITM_TEXT_LAYER, 'KPTM': c1.KPTM, 'UNIKL': c1.UNIKL,
                      **{f'probe {k}': v for k, v in c1.REVIEW_PROBES.items()}})
        for name, text in texts.items():
            with self.subTest(name):
                self.assertEqual(_ua(UA_OFFER_SIGNATURES, text), _ua(_UA_1_8_0, text))

    def test_the_c1_net_still_answers_request_47(self):
        self.assertEqual(signature_genuineness(c1.ILKBS_OFFER, doc_type='offer_letter')['status'], NOT_CHECKED)

    def test_uitms_bare_tarikh_label_earns_the_reporting_bonus(self):
        from apps.scholarship.pathway_engine import offer_reporting_bonus
        g = signature_genuineness(UITM_OFFER, doc_type='offer_letter')
        doc = ApplicantDocument(doc_type='offer_letter', vision_fields={
            'fields': {'reporting_date': '10 Julai 2026', 'reporting_date_label': 'Tarikh',
                       'institution': 'Universiti Teknologi MARA'},
            'authenticity': {'status': g['status'], 'doc_seen': g['type'], 'present': g['present']}})
        self.assertIs(offer_reporting_bonus(doc), True)

    def test_the_model_version(self):
        self.assertGreaterEqual(tuple(map(int, MODEL_VERSION.split('.'))), (1, 8, 2))      # UiTM shipped at 1.8.1 / 1.8.2 (C3: 1.9.0)


def _offer(app, status, *, doc_seen='ua_offer'):
    return ApplicantDocument.objects.create(
        application=app, doc_type='offer_letter', storage_path=f'{app.id}/of/{status}',
        vision_fields={'fields': {'candidate_name': STUDENT, 'candidate_nric': STUDENT_NRIC,
                                  'programme': 'Sijil Kemahiran', 'institution': 'IKBN'},
                       'student_verdict': 'ok',
                       'authenticity': {'status': status, 'doc_seen': doc_seen}})


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
class TheUploadDoor(TestCase):

    def test_an_uploaded_uitm_offer_is_stored_genuine_and_official(self):
        from apps.scholarship.pathway_engine import offer_official_status
        app = make_application('shortlisted', student=make_student(name=STUDENT, nric=STUDENT_NRIC))
        doc = ApplicantDocument.objects.create(application=app, doc_type='offer_letter',
                                               storage_path=f'{app.id}/of/u')
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': UITM_OFFER, 'error': None}), \
             patch('apps.scholarship.vision.extract_document_fields',
                   return_value={'fields': {}, 'warnings': [], 'error': ''}):
            doc.vision_fields = vision.run_field_extraction_for_document(doc, names=[])
        doc.save(update_fields=['vision_fields'])
        auth = doc.vision_fields['authenticity']
        self.assertEqual((auth['status'], auth['doc_seen'], auth['model_version']), ('genuine', 'ua_offer', MODEL_VERSION))
        self.assertEqual(offer_official_status(doc), 'genuine')


class AnOfficersOfferRequestWaitsForTheOfficer(TestCase):
    """C1 review follow-up: a NOT CHECKED offer reads 'ok' to `doc_match_verdict` (nothing failed),
    so it used to close an OFFICER's own "upload your official offer" request on upload. It now stays
    open, held for the officer (`needs_officer_eye` — the Action Centre's "we've received what you
    sent; our team is checking it" card), until the officer closes it by hand. The upload itself
    answers 'ok' (C2 review: 'pending' told the student "still checking — refresh", though nothing
    automatic will finish it). System requests close as before; the student is never blocked."""

    def setUp(self):
        from apps.scholarship.resolution import add_officer_item
        self.app = make_application('profile_complete', student=make_student(name=STUDENT, nric=STUDENT_NRIC))
        self.ask = add_officer_item(self.app, kind='doc', prompt='Upload your official offer letter',
                                    admin_email='officer@example.test', doc_type='offer_letter',
                                    fact='pathway')

    def _upload(self, status):
        from apps.scholarship.resolution import doc_match_verdict, resolve_doc_items_for_upload
        doc = _offer(self.app, status, doc_seen='tvet_belia_sukan' if status == NOT_CHECKED else 'ua_offer')
        self.assertEqual(doc_match_verdict(doc), 'ok')                 # nothing about the scan failed
        return resolve_doc_items_for_upload(self.app, doc)

    def test_a_not_checked_upload_leaves_the_officers_request_open_and_with_the_officer(self):
        self.assertEqual(self._upload(NOT_CHECKED), 'ok')
        self.ask.refresh_from_db()
        self.assertEqual(self.ask.status, 'open')
        self.assertIs(self.ask.params.get('needs_officer_eye'), True)

    def test_no_failed_attempt_is_stamped_on_the_held_request(self):
        """The re-ask counter and circuit-breaker read requests by system / Check-2 CODE; an officer's
        `officer_N` request is not among them, so the hold never reads as "not the page we asked for"."""
        from apps.scholarship.views import _note_unresolved_attempts, _open_doc_request_items
        self._upload(NOT_CHECKED)
        _note_unresolved_attempts(self.app, self.app.documents.get(doc_type='offer_letter'), [], False)
        self.ask.refresh_from_db()
        self.assertNotIn('attempts', self.ask.params)
        self.assertNotIn(self.ask, list(_open_doc_request_items(self.app, 'offer_letter')))

    def test_the_officer_closes_it_by_hand(self):
        from apps.scholarship.resolution import resolve_item
        self._upload(NOT_CHECKED)
        resolve_item(self.ask, by='officer@example.test')
        self.ask.refresh_from_db()
        self.assertEqual(self.ask.status, 'resolved')

    def test_a_genuine_upload_still_closes_it(self):
        self.assertEqual(self._upload('genuine'), 'ok')
        self.ask.refresh_from_db()
        self.assertEqual(self.ask.status, 'resolved')

    def test_a_system_request_still_closes_on_a_not_checked_upload(self):
        self.ask.delete()
        system = ResolutionItem.objects.create(application=self.app, source='system', code='offer_letter_missing',
                                               fact='pathway', kind='doc', doc_type='offer_letter')
        self.assertEqual(self._upload(NOT_CHECKED), 'ok')
        system.refresh_from_db()
        self.assertEqual(system.status, 'resolved')

    def test_the_student_is_never_blocked_by_it(self):
        from apps.scholarship.services.blockers import _offer_blocks
        _offer(self.app, NOT_CHECKED, doc_seen='tvet_belia_sukan')
        self.assertIs(_offer_blocks(self.app), False)
