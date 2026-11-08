"""The Exact offer read's one entry point (`offer_exact`, offer exact-read S5, 2026-11-03): the IC guard on
the Exact path (a blanked IC means NO lock), the merge over the prior read (the parser's own keys whole,
the dates merge-preserve), page 1 of a digital PDF, and the `vision` offer branch calling it.

Synthetic twins only — invented names, ICs and colleges (`test_no_gitignored_corpus.py`)."""
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.scholarship import vision
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.offer_exact import exact_offer_read, exact_read, merge_over, page1_text_layer
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_reader import png, text_pdf

NAME, NRIC = 'ZORBEX A/L QUENTARO', '010203-14-5678'
COLLEGE = 'KOLEJ MATRIKULASI ZANTHARION'


def matric(nric=NRIC, ic_label='K/P: ', reporting='17 OGOS 2031'):
    return f"""KEMENTERIAN PENDIDIKAN
Bahagian Matrikulasi
Tarikh: 3 MAC 2031
{NAME}
{ic_label}{nric}
TAWARAN KEMASUKAN PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN SESI 2031/2032
Jurusan:
Tempoh Pengajian:
Kolej:
Pendaftaran dalam talian:
Tarikh Kemasukan ke kolej:
Yuran Pendaftaran:
SAINS
DUA SEMESTER (10 BULAN)
{COLLEGE}
1 OGOS HINGGA 9 OGOS 2031
{reporting}
RM499.00
"""


STPM = f"""SEKTOR OPERASI SEKOLAH
Tarikh : 24 April 2031
Nama: {NAME}
No. Kad Pengenalan: {NRIC}
TAWARAN KEMASUKAN KE TINGKATAN ENAM SEMESTER 1 TAHUN 2031
2.1. Bidang SAINS
2.2. Pusat Tingkatan Enam KOLEJ TINGKATAN ENAM ZANTHARION
2.3. Tarikh Lapor Diri 08 Jun 2031
"""


class TestTheIcGuardOnTheExactPath(SimpleTestCase):
    def test_a_labelled_well_formed_ic_locks(self):
        ex = exact_offer_read(matric())
        self.assertEqual(ex['capture'], 'deterministic')
        self.assertEqual(ex['offer_reader_inputs'], {'reader': 'deterministic', 'nric_check': 'kept_well_formed'})
        self.assertEqual(ex['fields']['candidate_nric_source'], 'label')

    def test_the_profile_ic_reads_kept_profile(self):
        ex = exact_offer_read(matric(), profile_nric=NRIC.replace('-', ''))
        self.assertEqual(ex['offer_reader_inputs']['nric_check'], 'kept_profile')

    def test_another_persons_well_formed_labelled_ic_still_locks_that_is_a_wrong_person_letter(self):
        ex = exact_offer_read(matric(), profile_nric='020304-14-1111')
        self.assertEqual(ex['fields']['candidate_nric'], NRIC)

    def test_a_malformed_labelled_ic_is_blanked_and_never_locks(self):
        self.assertIsNone(exact_offer_read(matric(nric='019999-14-5678'), profile_nric='020304-14-1111'))

    def test_an_unlabelled_ic_locks_only_when_it_is_the_profile_ic(self):
        text = STPM.replace('No. Kad Pengenalan: ', 'Rujukan ')    # the first IC anywhere, source other
        self.assertIsNone(exact_offer_read(text, profile_nric='020304-14-1111'))
        self.assertIsNone(exact_offer_read(text))
        ex = exact_offer_read(text, profile_nric=NRIC)
        self.assertEqual(ex['offer_reader_inputs']['nric_check'], 'kept_corroborated')


class TestTheMerge(SimpleTestCase):
    STALE = {'candidate_name': 'OLD AI NAME', 'candidate_nric': '999999-99-9999', 'candidate_nric_source': 'other',
             'campus': 'STALE CAMPUS', 'programme_code': 'X1', 'institution': 'OLD', 'reporting_date': '1 Jan 2031',
             'reporting_date_label': 'Tarikh Pendaftaran', 'offer_date': '2 Jan 2031', 'reporting_venue': 'DEWAN'}

    def test_the_parser_owns_its_keys_whole_and_the_dates_merge_preserve(self):
        ex = exact_offer_read(matric(reporting='no date here'), prior={'fields': self.STALE})
        f = ex['fields']
        self.assertEqual((f['candidate_name'], f['institution']), (NAME, COLLEGE))
        self.assertEqual((f['campus'], f['programme_code'], f['candidate_nric_source']), ('', '', 'label'))
        self.assertEqual((f['reporting_date'], f['reporting_date_label']), ('1 Jan 2031', 'Tarikh Pendaftaran'))
        self.assertEqual(f['offer_date'], '3 MAC 2031')                # read → it wins
        self.assertEqual(f['reporting_venue'], '')                     # an AI-only key: blank (review L2)
        self.assertEqual(f['_offer_parser_version'], '2.0.1')
        self.assertNotIn('_family', f)

    def test_a_read_reporting_date_wins_with_its_label(self):
        f = merge_over(self.STALE, {'reporting_date': '17 OGOS 2031', 'reporting_date_label': 'Tarikh Kemasukan ke kolej'})
        self.assertEqual((f['reporting_date'], f['reporting_date_label']), ('17 OGOS 2031', 'Tarikh Kemasukan ke kolej'))

    def test_m4_a_parser_date_that_does_not_parse_never_overwrites_one_that_does(self):
        f = merge_over(self.STALE, {'reporting_date': '31/02/2031', 'reporting_date_label': 'x'})
        self.assertEqual((f['reporting_date'], f['reporting_date_label']), ('1 Jan 2031', 'Tarikh Pendaftaran'))
        f = merge_over({}, {'reporting_date': '31/02/2031', 'reporting_date_label': 'x'})
        self.assertEqual(f['reporting_date'], '31/02/2031')              # nothing better to keep

    def test_l2_every_ai_only_field_is_blank_under_an_exact_read(self):
        stale = {**self.STALE, 'candidate_address': 'OLD ADDRESS', 'aliran': 'SJKT',
                 'bidang_pengkhususan': 'X', 'elektif': 'Y'}
        f = exact_offer_read(matric(), prior={'fields': stale})['fields']
        for k in ('candidate_address', 'reporting_venue', 'aliran', 'bidang_pengkhususan', 'elektif'):
            self.assertEqual(f[k], '', k)

    def test_4_a_stored_reporting_date_that_is_not_text_never_raises(self):
        for bad in (None, 20310601, ['8 Jun 2031'], {'d': 1}):
            f = merge_over({'reporting_date': bad}, {'reporting_date': '8 Jun 2031', 'reporting_date_label': 'x'})
            self.assertEqual(f['reporting_date'], '8 Jun 2031')
        f = merge_over({'reporting_date': 20310601}, {'reporting_date': '31/02/2031', 'reporting_date_label': 'x'})
        self.assertEqual(f['reporting_date'], '31/02/2031')

    def test_5_a_pdf_with_no_bytes_never_reads_the_whole_layer_as_page_one(self):
        self.assertIsNone(exact_offer_read(matric(), image=None, content_type='application/pdf'))
        self.assertIsNotNone(exact_offer_read(matric(), image=None, content_type='image/png'))

    def test_no_prior_read(self):
        self.assertEqual(merge_over(None, {})['campus'], '')


class TestPageOne(SimpleTestCase):
    OTHER = 'QORIN A/L VESTRAN\nK/P: 130405100211\n'      # another person's identity lines

    def test_h1_a_vision_read_never_takes_its_identity_from_a_pdf_layer(self):
        # Review H1 probe: the body is Vision's text of letter B; a (hidden, short) page-1 layer names A.
        ex = exact_read(matric(), from_text_layer=False, page1_layer=self.OTHER, profile_nric='130405100211')
        self.assertEqual((ex['fields']['candidate_name'], ex['fields']['candidate_nric']), (NAME, NRIC))
        self.assertEqual(ex['offer_reader_inputs']['nric_check'], 'kept_well_formed')   # never 'match' to A

    def test_h1_a_page_one_identity_that_disagrees_with_the_layer_never_locks(self):
        self.assertIsNone(exact_read(matric(), from_text_layer=True, page1_layer=matric(nric='130405-10-0211')))
        self.assertIsNone(exact_read(matric(), from_text_layer=True,
                                     page1_layer=matric().replace(NAME, 'PAGEONE A/L ONLY')))
        self.assertIsNotNone(exact_read(matric(), from_text_layer=True, page1_layer=matric()))

    def test_h2_a_text_layer_whose_page_one_has_none_goes_to_the_ai_reader(self):
        self.assertIsNone(exact_read(matric(), from_text_layer=True, page1_layer=''))

    def test_production_decides_the_source_from_the_file(self):
        pdf = text_pdf([matric()])
        self.assertIsNotNone(exact_offer_read(matric(), image=pdf, content_type='application/pdf'))
        # Vision text of a PDF whose own layer is something else (a scan app's OCR'd copy): the identity
        # is read from the Vision text, and the layer is never used.
        other = text_pdf([matric().replace(NAME, 'PAGEONE A/L ONLY')])
        ex = exact_offer_read(matric(), image=other, content_type='application/pdf')
        self.assertEqual(ex['fields']['candidate_name'], NAME)

    def test_a_digital_pdf_gives_its_page_one_layer_and_a_photo_none(self):
        pdf = text_pdf(['PAGE ONE OF THE OFFER LETTER WITH ENOUGH REAL WORDS TO COUNT AS A TEXT LAYER HERE',
                        'PAGE TWO REPLY FORM WITH OTHER WORDS THAT MUST NEVER BE READ AS THE IDENTITY'])
        layer = page1_text_layer(pdf, 'application/pdf')
        self.assertIn('PAGE ONE', layer)
        self.assertNotIn('PAGE TWO', layer)
        self.assertEqual(page1_text_layer(png(), 'image/png'), '')
        self.assertEqual(page1_text_layer(None), '')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestTheVisionOfferBranch(TestCase):
    def _doc(self, nric):
        app = make_application('submitted')
        app.profile.nric = nric
        app.profile.save(update_fields=['nric'])
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x', content_type='image/png',
            vision_fields={'fields': {'campus': 'STALE CAMPUS'}}, vision_run_at=timezone.now())

    def test_a_lock_is_stored_as_the_exact_read_without_a_gemini_call(self):
        doc = self._doc(NRIC.replace('-', ''))
        with mock.patch.object(vision, '_call_gemini_json') as gemini:
            vision._run_field_extraction_impl(doc, names=[doc.application.profile.name],
                                              ocr={'text': matric(), 'error': '', 'image': png()})
        gemini.assert_not_called()
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['capture'], 'deterministic')
        self.assertEqual(doc.vision_fields['offer_reader_inputs'], {'reader': 'deterministic', 'nric_check': 'kept_profile'})
        self.assertEqual(doc.vision_fields['fields']['campus'], '')

    def test_an_ic_the_guard_blanks_goes_to_the_ai_reader(self):
        doc = self._doc('020304141111')
        with mock.patch('apps.scholarship.vision.extract_document_fields',
                        return_value={'fields': {}, 'warnings': [], 'error': ''}) as ai:
            vision._run_field_extraction_impl(doc, names=[doc.application.profile.name],
                                              ocr={'text': matric(nric='019999-14-5678'), 'error': '', 'image': png()})
        ai.assert_called_once()
        self.assertEqual(ai.call_args.kwargs['profile_nric'], '020304141111')
