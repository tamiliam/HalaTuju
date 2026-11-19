"""The UMS rules read (OCR-first S1, 2026-11-19): `offer_parse_university.read_ums`, its hook in
`offer_parse.diagnose`, the lane name on the Exact read, and Gate 2's last checks
(`offer_exact.rules_lane_open`: the lane switch + a unique catalogue match) in the vision offer branch.

Synthetic twins only — invented names, ICs and hostels (`test_no_gitignored_corpus.py`)."""
import os
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.scholarship import vision
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.offer_exact import exact_read, ocr_first_lanes, rules_lane_open
from apps.scholarship.offer_parse import diagnose, parse_govt_offer
from apps.scholarship.offer_parse_university import LANE, read_ums
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_reader import png

NAME, NRIC = 'ZORBEX A/L QUENTARO', '010203-14-5678'
PROG = 'Ijazah Sarjana Muda Sains Komputer Dengan Kepujian'
HOSTEL = 'Kolej Kediaman Zantharion'
MATCH = 'apps.scholarship.offer_course_match.match_offer_course'


def ums(name=NAME, nric=NRIC, prog_line=PROG, said=PROG, report='28-29 September 2031', extra_head='',
        title='TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH SESI I-2031/2032', top=''):
    """A synthetic UMS letter in the layout shape (label and value on one line, padded columns)."""
    return f"""{top}UNIVERSITI MALAYSIA SABAH
Rujukan Kami :      UMS/PPA/100-1/2/3
Tarikh :      15 Ogos 2031
{name}
No. Kad Pengenalan :      {nric}
No. Pelajar :      BK31110410
{extra_head}Jalan Zantharion 7, 88000 Kota Kinabalu
{title}
Dengan sukacitanya dimaklumkan bahawa saudara ditawarkan kemasukan untuk mendapat
{said} dan sebanyak 128 jam kredit diperlukan.
Program :      {prog_line}
Kod Program :      UH6481001
Fakulti :      Fakulti Komputeran dan Informatik
Kampus :      Kota Kinabalu
Tarikh Lapor Diri :      {report}
Tempat / Kolej :      {HOSTEL}
"""


class TestTheRulesRead(SimpleTestCase):
    def test_a_well_formed_letter_reads_every_field(self):
        f, reason = read_ums(ums())
        self.assertEqual(reason, '')
        self.assertEqual(f['candidate_name'], NAME)
        self.assertEqual(f['candidate_nric'], NRIC)
        self.assertEqual(f['candidate_nric_source'], 'label')
        self.assertEqual(f['programme'], PROG)
        self.assertEqual(f['programme_code'], 'UH6481001')
        self.assertEqual(f['intake'], 'SESI I-2031/2032')
        self.assertEqual(f['campus'], 'Kota Kinabalu')
        self.assertEqual(f['offer_date'], '15 Ogos 2031')

    def test_the_institution_is_the_title_and_the_hostel_is_only_the_venue(self):
        f, _r = read_ums(ums())
        self.assertEqual(f['institution'], 'Universiti Malaysia Sabah')
        self.assertEqual(f['issuer'], 'Universiti Malaysia Sabah')
        self.assertEqual(f['reporting_venue'], HOSTEL)

    def test_a_day_range_reports_on_its_first_day_and_a_full_range_too(self):
        self.assertTrue(read_ums(ums())[0]['reporting_date'].startswith('28'))
        f, reason = read_ums(ums(report='12 September 2031 - 13 September 2031'))
        self.assertEqual(reason, '')
        self.assertTrue(f['reporting_date'].startswith('12'))

    def test_a_scanned_letter_one_item_per_line_reads_the_same(self):
        text = ums().replace('Tarikh :      15 Ogos 2031', 'Tarikh :\n15 Ogos 2031')
        self.assertEqual(read_ums(text)[1], '')

    def test_a_status_letter_never_locks(self):
        self.assertEqual(read_ums(ums(top='SURAT PENGESAHAN PELAJAR\n'))[1], 'status_letter')

    def test_the_blank_template_does_not_lock(self):
        f, reason = read_ums(ums(name='', nric='', report=''))
        self.assertTrue(reason.startswith('empty:'))
        self.assertIn('candidate_name', reason)

    def test_an_ic_without_its_label_is_never_read(self):
        text = ums().replace('No. Kad Pengenalan :      ' + NRIC, 'No. Kad Pengenalan :') + NRIC + '\n'
        f, reason = read_ums(text)
        self.assertEqual(f['candidate_nric'], '')
        self.assertIn('candidate_nric', reason)

    def test_a_second_ic_in_the_head_refuses_the_ic(self):
        f, _r = read_ums(ums(extra_head='Waris : 750101-12-9999\n'))
        self.assertEqual(f['candidate_nric'], '')

    def test_a_programme_line_that_disagrees_with_the_sentence_is_not_read(self):
        f, reason = read_ums(ums(said='Ijazah Sarjana Muda Sains Marin Dengan Kepujian'))
        self.assertEqual(f['programme'], '')
        self.assertIn('programme', reason)

    def test_a_reporting_date_outside_the_intake_is_not_sane(self):
        self.assertEqual(read_ums(ums(report='28 September 2035'))[1], 'dates_not_sane')

    def test_a_certifier_stamp_line_is_never_the_name(self):
        f, _r = read_ums(ums(name='DISAHKAN SALINAN SEBENAR'))
        self.assertEqual(f['candidate_name'], '')


class TestTheDiagnoseHook(SimpleTestCase):
    def test_a_scanned_letter_locks_with_its_lane(self):
        lock = parse_govt_offer(ums())
        self.assertEqual(lock['rules_lane'], LANE)
        self.assertEqual(lock['_family'], 'ums')

    def test_a_text_layer_without_its_layout_never_locks(self):
        d = diagnose(ums(), page1_text=ums())
        self.assertEqual(d['guard'], 'no_layout')
        self.assertIsNone(d['locked'])

    def test_a_text_layer_reads_from_its_layout(self):
        glued = ums().replace('\n', ' ')
        self.assertIsNone(diagnose(glued, page1_text=glued)['locked'])
        self.assertEqual(diagnose(glued, page1_text=glued, page1_layout=ums())['locked']['candidate_name'], NAME)

    def test_the_exact_read_names_the_lane(self):
        ex = exact_read(ums())
        self.assertEqual(ex['rules_lane'], LANE)
        self.assertEqual(ex['offer_reader_inputs']['rules_lane'], LANE)
        self.assertNotIn('rules_lane', ex['fields'])


class TestGateTwo(SimpleTestCase):
    def test_the_switch_is_read_from_the_environment_and_is_off_by_default(self):
        with mock.patch.dict(os.environ, {'OCR_FIRST_LANES': ' ua:UMS , '}):
            self.assertEqual(ocr_first_lanes(), ('ua:UMS',))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ocr_first_lanes(), ())

    def test_a_government_read_is_unaffected(self):
        self.assertTrue(rules_lane_open({'fields': {}, 'rules_lane': ''}))

    @override_settings(OCR_FIRST_LANES=())
    def test_a_lane_switched_off_goes_to_the_ai(self):
        self.assertFalse(rules_lane_open(exact_read(ums())))

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_a_lane_switched_on_needs_a_unique_course(self):
        ex = exact_read(ums())
        with mock.patch(MATCH, return_value=None):
            self.assertFalse(rules_lane_open(ex))
        with mock.patch(MATCH, return_value=object()) as match:
            self.assertTrue(rules_lane_open(ex))
        self.assertEqual(match.call_args.args[2], 'Universiti Malaysia Sabah')


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestTheVisionOfferBranch(TestCase):
    def _run(self, ai):
        app = make_application('submitted')
        app.profile.nric = NRIC.replace('-', '')
        app.profile.save(update_fields=['nric'])
        doc = ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x', content_type='image/png',
            vision_fields={'fields': {}}, vision_run_at=timezone.now())
        vision._run_field_extraction_impl(doc, names=[app.profile.name], ocr={'text': ums(), 'error': '', 'image': png()})
        doc.refresh_from_db()
        return doc

    @override_settings(OCR_FIRST_LANES=())
    def test_lane_off_falls_through_to_the_ai(self):
        with mock.patch('apps.scholarship.vision.extract_document_fields',
                        return_value={'fields': {}, 'warnings': [], 'error': ''}) as ai:
            self._run(ai)
        ai.assert_called_once()

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_lane_on_with_no_unique_course_falls_through_to_the_ai(self):
        with mock.patch(MATCH, return_value=None), mock.patch(
                'apps.scholarship.vision.extract_document_fields',
                return_value={'fields': {}, 'warnings': [], 'error': ''}) as ai:
            self._run(ai)
        ai.assert_called_once()

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_lane_on_with_a_unique_course_is_the_rules_read(self):
        with mock.patch(MATCH, return_value=object()), mock.patch.object(vision, '_call_gemini_json') as gemini:
            doc = self._run(None)
        gemini.assert_not_called()
        self.assertEqual(doc.vision_fields['capture'], 'deterministic')
        self.assertEqual(doc.vision_fields['offer_reader_inputs']['rules_lane'], LANE)
        self.assertEqual(doc.vision_fields['fields']['institution'], 'Universiti Malaysia Sabah')
