"""The AI offer reader (`offer_reader.py`, offer exact-read S4, 2026-11-01): its schema, the owner's
reading rules in its prompt, what Gemini is shown (up to 3 pages, one image each, high media
resolution, a digital PDF's text layer), the clean-up, and the version stamped on the stored read.

Synthetic twins only: every letter is built here and every value is invented — nothing reads the
gitignored corpus (`test_no_gitignored_corpus.py`). Gemini is never called (the seam is patched, or
the genai client is a fake)."""
import io
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.scholarship import offer_reader as orr
from apps.scholarship import vision
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application

_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
NAME, NRIC = 'ZORBEX A/L QUENTARO', '010203-14-5678'


def text_pdf(pages, size=(595, 842)):
    """A valid PDF with ONE page per string in ``pages``, each carrying that string as real text
    (a text layer pypdf reads back)."""
    n = len(pages)
    objs = [b'<< /Type /Catalog /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [%s] /Count %d >>' % (
                b' '.join(b'%d 0 R' % (4 + 2 * i) for i in range(n)), n),
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    for i, text in enumerate(pages):
        stream = b'BT /F1 11 Tf 40 780 Td (%s) Tj ET' % text.encode('latin-1')
        objs.append(b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 3 0 R '
                    b'>> >> /Contents %d 0 R >>' % (size[0], size[1], 5 + 2 * i))
        objs.append(b'<< /Length %d >>\nstream\n%s\nendstream' % (len(stream), stream))
    out, offsets = b'%PDF-1.4\n', []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b'%d 0 obj\n' % i + body + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    out += b''.join(b'%010d 00000 n \n' % off for off in offsets)
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF' % (len(objs) + 1, xref)
    return out


def png(size=(900, 1200)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', size, 'white').save(buf, format='PNG')
    return buf.getvalue()


def blank_pdf():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (600, 800), 'white').save(buf, format='PDF')
    return buf.getvalue()


PAGE_TEXT = ['SURAT TAWARAN QORVANE ' + 'MAKLUMAT PROGRAM PENGAJIAN ' * 3,
             'TARIKH PENDAFTARAN DAN TEMPAT LAPOR DIRI ' * 3,
             'SYARAT TAWARAN DAN YURAN PENGAJIAN ' * 3,
             'BORANG SETUJU TERIMA TAWARAN PAGE FOUR ' * 3]


class SchemaTest(SimpleTestCase):
    def test_the_schema_carries_the_new_fields_beside_the_old(self):
        props = orr.OFFER_SCHEMA['properties']
        for f in ('candidate_name', 'candidate_nric', 'programme', 'institution', 'issuer', 'offer_date',
                  'intake', 'candidate_address', 'stream', 'reporting_date', 'reporting_date_label',
                  'bidang_pengkhususan', 'elektif', 'aliran', 'campus', 'reporting_venue',
                  'programme_code'):
            self.assertEqual(props[f], {'type': 'string'}, f)
        self.assertEqual(props['warnings'], {'type': 'array', 'items': {'type': 'string'}})

    def test_vision_points_at_the_one_schema_and_keeps_no_old_offer_hint(self):
        self.assertIs(vision._FIELD_SCHEMAS['offer_letter'], orr.OFFER_SCHEMA)
        self.assertNotIn('offer_letter', vision._DOC_HINTS)

    def test_the_version_is_semantic_and_major_two(self):
        major, minor, patch = (int(x) for x in orr.OFFER_READER_VERSION.split('.'))
        self.assertEqual(major, 2)          # 2.0.0: `institution` no longer carries the campus


class PromptRulesTest(SimpleTestCase):
    """Each owner ruling of 2026-11-01 is in the words Gemini reads."""

    def test_each_reading_rule_is_stated(self):
        p = orr.image_prompt(1)
        for phrase in (
                'READ EXACTLY AS PRINTED', 'never correct, translate, expand or shorten',
                '"institution" = the institution\'s NAME only',
                '"campus" = the campus / branch of that institution as printed',
                'empty when the letter names no campus',
                'NEVER put a hostel', 'goes in\n"reporting_venue"'.replace('\n', ' '),
                '"programme" = the programme / course title as printed, WITHOUT a course code',
                'goes in "programme_code"', 'IJAZAH SARJANA MUDA PERGURUAN', '"bidang_pengkhususan"',
                'exactly as printed WITH its label', 'SESI 1-2026/2027', 'SEMESTER 1 TAHUN 2026',
                'without its weekday or time', 'ONLY the date the student must REPORT / REGISTER',
                'NEVER a commencement', 'Tarikh Mula Kuliah',
                'ONLY inside its reference line', 'never guess one', 'reply or acceptance form',
                '"issuer" = the body that issued the letter'):
            self.assertIn(phrase, p, phrase)

    def test_the_issuer_rule_is_the_letterhead_as_before(self):
        self.assertIn('from its letterhead', orr.OFFER_HINT)

    def test_pages_and_the_text_layer_are_named_in_the_prompt(self):
        one, three = orr.image_prompt(1), orr.image_prompt(3, 'LAYER TEXT QORVANE')
        self.assertIn('These are an image of a Malaysian offer letter', one)
        self.assertNotIn('TEXT LAYER', one)
        self.assertIn('the first 3 pages', three)
        self.assertTrue(three.endswith('LAYER TEXT QORVANE'))
        self.assertIn('TEXT LAYER of the same pages', three)

    def test_the_text_only_prompt_caps_the_ocr_text(self):
        p = orr.text_prompt('§' * (orr.MAX_OCR_CHARS + 500))
        self.assertIn('OCR TEXT:', p)
        self.assertEqual(p.count('§'), orr.MAX_OCR_CHARS)


class InputsTest(SimpleTestCase):
    def test_a_four_page_pdf_shows_its_first_three_pages_one_image_each(self):
        shown = orr.offer_inputs(text_pdf(PAGE_TEXT), 'application/pdf')
        self.assertEqual(shown['kind'], 'pdf')
        self.assertEqual(len(shown['images']), orr.MAX_PAGES)
        self.assertTrue(all(img.startswith(_PNG_MAGIC) and mime == 'image/png' for img, mime in shown['images']))
        self.assertIn('TARIKH PENDAFTARAN', shown['text_layer'])        # page 2's own text
        self.assertIn('SYARAT TAWARAN', shown['text_layer'])            # page 3
        self.assertNotIn('PAGE FOUR', shown['text_layer'])              # page 4 is not shown

    def test_each_page_keeps_its_own_full_resolution(self):
        from PIL import Image
        img = orr.offer_inputs(text_pdf(PAGE_TEXT[:2]), 'application/pdf')['images'][1][0]
        self.assertGreater(Image.open(io.BytesIO(img)).size[1], 2300)   # A4 at 200 DPI, not a shared raster

    def test_a_scanned_pdf_has_no_text_layer(self):
        shown = orr.offer_inputs(blank_pdf(), 'application/pdf')
        self.assertEqual((len(shown['images']), shown['text_layer']), (1, ''))

    def test_a_scanner_stamp_is_no_layer(self):
        shown = orr.offer_inputs(text_pdf(['CamScanner']), 'application/pdf')
        self.assertEqual(shown['text_layer'], '')

    def test_the_text_layer_is_capped(self):
        shown = orr.offer_inputs(text_pdf(['WORD ' * 1200, 'MORE ' * 1200]), 'application/pdf')
        self.assertEqual(len(shown['text_layer']), orr.MAX_TEXT_CHARS)

    def test_a_photo_is_shown_as_itself(self):
        data = png()
        self.assertEqual(orr.offer_inputs(data, 'image/png'),
                         {'images': [(data, 'image/png')], 'text_layer': '', 'kind': 'image'})

    def test_nothing_to_show(self):
        self.assertEqual(orr.offer_inputs(b'', 'image/png')['images'], [])
        self.assertEqual(orr.offer_inputs(b'%PDF-1.4 broken', 'application/pdf')['images'], [])


GOOD = {'candidate_name': NAME, 'candidate_nric': NRIC, 'programme': 'IJAZAH SARJANA MUDA QORVANE',
        'institution': 'UNIVERSITI QORVANE', 'campus': 'KAMPUS PERLAK', 'reporting_date': '17 Ogos 2031',
        'warnings': ['The intake is not printed on the letter.']}


@mock.patch('apps.scholarship.vision._call_gemini_json')
class ReadOfferTest(SimpleTestCase):
    def test_the_seam_gets_every_page_at_high_resolution(self, gem):
        gem.return_value = dict(GOOD)
        ex = orr.read_offer('', image=text_pdf(PAGE_TEXT), content_type='application/pdf')
        (prompt, schema), kw = gem.call_args
        self.assertIs(schema, orr.OFFER_SCHEMA)
        self.assertEqual(len(kw['images']), 3)
        self.assertEqual(kw['media_resolution'], 'MEDIA_RESOLUTION_HIGH')
        self.assertIn('TEXT LAYER of the same pages', prompt)
        self.assertEqual(ex['error'], '')
        self.assertEqual(ex['fields']['reporting_date'], '17 Aug 2031')   # vision's clean-up still runs
        self.assertEqual(ex['warnings'], [])                               # an optional field's note dropped
        self.assertEqual(ex['offer_reader_version'], orr.OFFER_READER_VERSION)
        self.assertEqual(ex['offer_reader_inputs']['pages'], 3)
        self.assertGreater(ex['offer_reader_inputs']['text_layer_chars'], 50)

    def test_extract_document_fields_sends_every_offer_here(self, gem):
        gem.return_value = dict(GOOD)
        ex = vision.extract_document_fields('', 'offer_letter', image=png(), content_type='image/png')
        self.assertEqual(ex['offer_reader_inputs'],
                         {'pages': 1, 'text_layer_chars': 0, 'media_resolution': 'MEDIA_RESOLUTION_HIGH',
                          'ocr_text': False})
        self.assertEqual(gem.call_args.kwargs['images'][0][1], 'image/png')

    def test_the_text_only_read_is_stamped_too(self, gem):
        gem.return_value = dict(GOOD)
        ex = vision.extract_document_fields('SURAT TAWARAN QORVANE', 'offer_letter')
        self.assertNotIn('images', gem.call_args.kwargs)
        self.assertEqual((ex['offer_reader_version'], ex['offer_reader_inputs']['ocr_text']),
                         (orr.OFFER_READER_VERSION, True))

    def test_nothing_to_show_is_an_error_without_a_call(self, gem):
        ex = orr.read_offer('', image=b'%PDF-1.4 broken', content_type='application/pdf')
        gem.assert_not_called()
        self.assertEqual((ex['error'], ex['fields']), ('no image for extraction', {}))
        self.assertEqual(orr.read_offer('  ')['error'], 'no text')

    def test_an_ai_error_keeps_its_message_and_the_stamp(self, gem):
        gem.return_value = {'_error': 'All AI models failed: x'}
        ex = orr.read_offer('', image=png(), content_type='image/png')
        self.assertEqual((ex['error'], ex['fields']), ('All AI models failed: x', {}))
        self.assertEqual(ex['offer_reader_version'], orr.OFFER_READER_VERSION)


class CleanTest(SimpleTestCase):
    def test_a_printed_code_moves_to_programme_code(self):
        f = orr.clean_offer_fields({'programme': 'Sarjana Muda Qorvane dengan Kepujian - UW6526001'})
        self.assertEqual((f['programme'], f['programme_code']), ('Sarjana Muda Qorvane dengan Kepujian', 'UW6526001'))
        f = orr.clean_offer_fields({'programme': 'BA272 SARJANA MUDA QORVANE (KEPUJIAN)'})
        self.assertEqual((f['programme'], f['programme_code']), ('SARJANA MUDA QORVANE (KEPUJIAN)', 'BA272'))
        f = orr.clean_offer_fields({'programme': 'DIPLOMA QORVANE (UH4520001)', 'programme_code': 'UH4520001'})
        self.assertEqual((f['programme'], f['programme_code']), ('DIPLOMA QORVANE', 'UH4520001'))

    def test_a_programme_without_a_code_is_untouched(self):
        f = orr.clean_offer_fields({'programme': 'IJAZAH SARJANA MUDA PERGURUAN', 'programme_code': ''})
        self.assertEqual(f, {'programme': 'IJAZAH SARJANA MUDA PERGURUAN', 'programme_code': ''})

    def test_an_ic_read_is_kept_only_when_its_digits_can_be_an_ic(self):
        for kept in (NRIC, '010203145678', '01020314567', '0102031456789'):   # 12, and one digit either way
            self.assertEqual(orr.clean_offer_fields({'candidate_nric': kept})['candidate_nric'], kept)
        for refused in ('UPM/BPA/S/3-1', 'UP/2031/0001', '010203145678/UP/2031/123'):
            self.assertEqual(orr.clean_offer_fields({'candidate_nric': refused})['candidate_nric'], '')
        self.assertEqual(orr.clean_offer_fields({'candidate_nric': ''})['candidate_nric'], '')


class _FakeModels:
    def __init__(self, seen):
        self.seen = seen

    def generate_content(self, *, model, contents, config=None):
        self.seen.append((contents, config))
        return SimpleNamespace(text='{}', usage_metadata=None)


@override_settings(GEMINI_API_KEY='fake-key-for-tests')
class SeamTest(SimpleTestCase):
    def _call(self, **kw):
        seen = []
        with mock.patch('google.genai.Client', lambda **k: SimpleNamespace(models=_FakeModels(seen))), \
                mock.patch('apps.scholarship.usage.record_usage'):
            self.assertEqual(vision._call_gemini_json('PROMPT', {'type': 'object'}, **kw), {})
        return seen[0]

    def test_several_images_go_first_then_the_prompt_with_the_resolution(self):
        contents, config = self._call(images=[(png(), 'image/png'), (png(), 'image/png')],
                                      media_resolution='MEDIA_RESOLUTION_HIGH')
        self.assertEqual(len(contents), 3)
        self.assertEqual(contents[-1], 'PROMPT')
        self.assertEqual(str(getattr(config.media_resolution, 'value', config.media_resolution)),
                         'MEDIA_RESOLUTION_HIGH')

    def test_the_other_callers_are_unchanged(self):
        contents, config = self._call()
        self.assertEqual((contents, config.media_resolution), ('PROMPT', None))
        contents, config = self._call(image=png(), mime_type='image/png')
        self.assertEqual((len(contents), contents[-1], config.media_resolution), (2, 'PROMPT', None))


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class StoredRecordTest(TestCase):
    """The version and what was shown reach the STORED record (`vision_fields`)."""

    def _doc(self):
        app = make_application('submitted')
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x', content_type='image/png',
            vision_fields={}, vision_run_at=timezone.now())

    @mock.patch('apps.scholarship.vision._call_gemini_json')
    def test_an_ai_read_is_stamped_on_the_record(self, gem):
        gem.return_value = dict(GOOD)
        doc = self._doc()
        ocr = {'text': '', 'error': '', 'image': png()}
        vision._run_field_extraction_impl(doc, names=[doc.application.profile.name], ocr=ocr)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['capture'], 'ai')
        self.assertEqual(doc.vision_fields['offer_reader_version'], orr.OFFER_READER_VERSION)
        self.assertEqual(doc.vision_fields['offer_reader_inputs']['pages'], 1)
        self.assertEqual(doc.vision_fields['fields']['campus'], 'KAMPUS PERLAK')
