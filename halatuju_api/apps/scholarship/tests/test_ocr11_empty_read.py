"""OCR-11 (owner 2026-11-21): an AI read with every real field empty is a FAILED read (cannot read, the
retry path), never a stored 'ok' and never a checked-but-unapproved approval.

* Offer: `candidate_nric_source` (the IC guard writes 'none' on every IC-less read) no longer fills a read;
  an all-empty answer is `read_errors.EMPTY_ANSWER`, judged before the IC guard and its text backstop.
* Results slip / higher results: `_slip_ocr_diag` and the `results_kind_*` routing detection no longer
  fill a read; an all-empty AI answer is `EMPTY_ANSWER` (the slip's diagnostic is kept on the failed read).
  A list or dict counts only if something inside it is filled.
* Income approval (review round 1): judged on the IMAGE, not the answer. A (nearly) white page image
  (`approval_page_white`, also with a footer or a thin bar) is a failed read with no paid call: still
  checking, ONE sweep retry, then the officer's. A genuine unmarked document with text answers "nothing"
  too and stays a checked, unapproved read (`approval_missing`).
* The marked white page (TD row 2, item 1): a page white apart from a footer mark passes the blank-page
  guard, reaches the model, and its empty answer is a failed read too.

Synthetic data only: invented names, a made-up IC, drawn pages.
"""
import io
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.scholarship import offer_reader as orr
from apps.scholarship import vision
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.read_errors import EMPTY_ANSWER
from apps.scholarship.tests.factories import create_document, make_application
from apps.scholarship.tests.test_offer_reader import text_pdf
from apps.scholarship.vision.field_extraction import _build_read_result
from apps.scholarship.vision.judge import BOOKKEEPING_FIELDS, doc_student_verdict

FAKE_IC = '010203-14-5678'
#: What a model answers for a white page: every offer field blank, the IC source 'none'.
EMPTY_OFFER = {**{f: '' for f in orr._FIELDS}, 'candidate_nric_source': 'none', 'warnings': []}


def _png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (600, 800), 'white').save(buf, format='PNG')
    return buf.getvalue()


def _answer(answer):
    """A fake `_call_gemini_json` that gives ``answer`` (a fresh copy) to every call."""
    return mock.patch.object(vision, '_call_gemini_json',
                             side_effect=lambda *a, **k: {**answer, '_model': 'gemini-3.8-flash'})


def _verdict(doc_type, ex):
    return _build_read_result(ApplicantDocument(doc_type=doc_type), ex, names=['ZORBEX A/L QUENTARO'],
                              postcode='', city='', street='', check_address=False)


class BookkeepingNeverFillsARead(SimpleTestCase):

    def test_each_bookkeeping_key_alone_is_not_a_filled_read(self):
        alone = {'offer_letter': {'candidate_nric_source': 'none'},
                 'results_slip': {'_slip_ocr_diag': {'reason': 'no_table'}, 'exam': '', 'results': []},
                 'higher_results': {'results_kind_detected': 'stpm', 'results_kind_markers': ['stpm'],
                                    'results_kind_issuer': 'MPM', 'candidate_name': '', 'results': []}}
        for doc_type, fields in alone.items():
            with self.subTest(doc_type):
                self.assertEqual(doc_student_verdict(doc_type, fields, names=['X']), 'wrong_doc')
        self.assertEqual(BOOKKEEPING_FIELDS, {'candidate_nric_source', '_slip_ocr_diag', 'results_kind_detected',
                                              'results_kind_markers', 'results_kind_issuer'})

    def test_one_real_field_still_fills_it(self):
        self.assertEqual(doc_student_verdict('offer_letter', {'candidate_nric_source': 'none',
                                                              'programme': 'DIPLOMA QORVANE'}, names=['X']), 'ok')


class AnEmptyOfferAnswerIsAFailedRead(SimpleTestCase):

    def test_an_all_empty_answer_is_cannot_read_not_ok(self):
        with _answer(EMPTY_OFFER) as gem:
            ex = orr.read_offer('', image=_png(), content_type='image/png')
        self.assertGreaterEqual(gem.call_count, 1)
        self.assertEqual((ex['error'], ex['fields']), (EMPTY_ANSWER, {}))
        self.assertEqual(ex['offer_reader_version'], '2.10.0')
        self.assertEqual(_verdict('offer_letter', ex)['student_verdict'], 'unreadable')

    def test_the_marked_white_page_with_an_ic_in_its_footer_is_still_a_failed_read(self):
        """TD row 2 item 1: white apart from a "Page 1 of 1" footer (and an IC the text backstop could copy).
        The blank-page guard lets it through (it has a mark); the model sees nothing; the read fails."""
        page = text_pdf([f'Page 1 of 1   {FAKE_IC}'])
        with _answer({**EMPTY_OFFER, 'warnings': ['Only a page footer is visible.']}) as gem:
            ex = orr.read_offer('', image=page, content_type='application/pdf', profile_nric=FAKE_IC)
        self.assertGreaterEqual(gem.call_count, 1)                    # the page reached the model
        self.assertEqual((ex['error'], ex['fields'], ex['warnings']), (EMPTY_ANSWER, {}, []))
        self.assertEqual(_verdict('offer_letter', ex)['student_verdict'], 'unreadable')

    def test_a_read_with_one_field_is_still_an_ok_read(self):
        with _answer({**EMPTY_OFFER, 'programme': 'DIPLOMA QORVANE', 'institution': 'KOLEJ QORVANE'}):
            ex = orr.read_offer('', image=_png(), content_type='image/png')
        self.assertEqual(ex['error'], '')
        self.assertEqual(ex['fields']['programme'], 'DIPLOMA QORVANE')


class AnEmptyResultsAnswerIsAFailedRead(TestCase):

    def _upload(self, doc_type, text):
        app = make_application('profile_complete')
        doc = create_document(application=app, doc_type=doc_type, storage_path=f'{app.id}/r/x')
        empty = {'fields': {'candidate_name': '', 'exam': '', 'results': []}, 'warnings': [], 'error': ''}
        with mock.patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img'), \
             mock.patch('apps.scholarship.vision._extract_slip_deterministic', return_value=(None, {'reason': 'x'})), \
             mock.patch('apps.scholarship.higher_results._exact_read', return_value=(None, '')), \
             mock.patch('apps.scholarship.vision.extract_document_fields', return_value=empty), \
             mock.patch('apps.scholarship.vision.ocr_document', return_value={'text': text, 'error': None}):
            return vision.run_field_extraction_for_document(doc, names=['ZORBEX A/L QUENTARO'])

    def test_an_empty_slip_answer_is_cannot_read_though_the_diag_and_year_backfill_are_there(self):
        vf = self._upload('results_slip', 'SIJIL PELAJARAN MALAYSIA\nPEPERIKSAAN TAHUN 2030\nPage 1 of 1')
        self.assertEqual((vf['student_verdict'], vf['error'], vf['fields']), ('unreadable', EMPTY_ANSWER, {}))
        self.assertEqual(vf['_slip_ocr_diag'], {'reason': 'x'})      # review round 1: the diagnostic is kept

    def test_an_empty_higher_results_answer_is_cannot_read_though_the_kind_was_detected(self):
        vf = self._upload('higher_results', 'MAJLIS PEPERIKSAAN MALAYSIA\nSIJIL TINGGI PERSEKOLAHAN MALAYSIA')
        self.assertEqual((vf['student_verdict'], vf['error'], vf['fields']), ('unreadable', EMPTY_ANSWER, {}))


def _page(*, footer=False, bar=False, typed=False):
    """A synthetic A4-sized page at 150 dpi (1240 x 1754), the size `pdf_pages` renders: white, plus a
    "Page 1 of 1" footer, a thin bar, or eight typed lines of an invented unsigned self-declaration."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new('RGB', (1240, 1754), 'white')
    d = ImageDraw.Draw(im)
    if footer:
        d.text((560, 1694), 'Page 1 of 1', fill='black', font=ImageFont.load_default(size=18))
    if bar:
        d.rectangle((495, 1714, 745, 1722), fill='black')
    if typed:
        lines = ('PENGAKUAN PENDAPATAN SENDIRI', '', 'Saya yang bernama ZORBEX A/L QUENTARO',
                 f'No. K/P {FAKE_IC} mengaku bahawa pendapatan', 'bulanan saya ialah RM800 sebagai',
                 'penoreh getah di Kampung Contoh.', '', 'Tarikh: 1 November 2026')
        for i, line in enumerate(lines):
            d.text((120, 160 + i * 40), line, fill='black', font=ImageFont.load_default(size=24))
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    return buf.getvalue()


class AWhiteApprovalPageIsAFailedRead(SimpleTestCase):
    """The income path, judged on the IMAGE the approval read would send (review round 1): a white page is
    a failed read with no paid call; a genuine unmarked document is still a checked, unapproved read."""

    NOTHING = {'issuer_header': '', 'approver_name': '', 'approver_title': '', 'has_stamp_or_signature': 'no',
               'has_signature': 'no', 'has_stamp': 'no'}

    def _read(self, image, answer=None, prior=None):
        from apps.scholarship.income_declaration import read_approval
        doc = ApplicantDocument(doc_type='income_support_doc', content_type='image/png', vision_fields=prior or {})
        ex = {'fields': {'amount': 'RM800'}, 'warnings': [], 'error': ''}
        with _answer(answer or self.NOTHING) as gem:
            out = read_approval(doc, ex, 'PENGAKUAN PENDAPATAN SENDIRI\nRM800', lambda: image)
        doc.vision_fields = {**out, 'fields': out['fields']}
        return doc, out, gem.call_count

    def test_a_genuine_unmarked_document_stays_a_checked_unapproved_read(self):
        from apps.scholarship.income_declaration import (APPROVAL_ERROR, APPROVAL_FIELDS, approval_missing,
                                                         approval_page_white, approval_unchecked)
        page = _page(typed=True)
        self.assertFalse(approval_page_white(page))
        for answer in (self.NOTHING, {k: '' for k in self.NOTHING}):
            with self.subTest(marks=answer['has_stamp']):
                doc, out, calls = self._read(page, answer)
                self.assertEqual(calls, 1)
                self.assertNotIn(APPROVAL_ERROR, out)
                self.assertLessEqual(set(APPROVAL_FIELDS), set(out['fields']))
                self.assertFalse(approval_unchecked(doc))
                self.assertNotEqual(approval_missing(doc), ())         # checked, and unapproved

    def test_a_white_page_and_a_white_page_with_a_footer_or_a_bar_fail_with_no_paid_call(self):
        from apps.scholarship.income_declaration import (APPROVAL_ERROR, APPROVAL_FIELDS, approval_expired,
                                                         approval_missing, approval_unchecked)
        for marks in ({}, {'footer': True}, {'bar': True}, {'footer': True, 'bar': True}):
            with self.subTest(**marks):
                doc, out, calls = self._read(_page(**marks))
                self.assertEqual(calls, 0)
                self.assertEqual(out[APPROVAL_ERROR], EMPTY_ANSWER)
                self.assertFalse(set(APPROVAL_FIELDS) & set(out['fields']))
                self.assertEqual(out['fields']['amount'], 'RM800')
                self.assertTrue(approval_unchecked(doc))               # still checking: the sweep retries it
                self.assertFalse(approval_expired(doc))
                self.assertEqual(approval_missing(doc), ())

    def test_the_one_retry_that_sees_a_white_page_again_closes_the_window(self):
        """The paid-read cap: the sweep's one retry finds the same white page, so the window is shut at once
        and the document is the officer's (`approval_expired`); the sweep excludes a shut window."""
        import time
        from apps.scholarship.income_declaration import APPROVAL_ERROR, APPROVAL_UNTIL, approval_expired
        prior = {APPROVAL_ERROR: EMPTY_ANSWER, APPROVAL_UNTIL: int(time.time()) + 3600, 'fields': {}}
        doc, out, calls = self._read(_page(footer=True), prior=prior)
        self.assertEqual((calls, out[APPROVAL_ERROR]), (0, EMPTY_ANSWER))
        self.assertLessEqual(out[APPROVAL_UNTIL], time.time())
        self.assertTrue(approval_expired(doc))
        _, other, _ = self._read(_page(), prior={**prior, APPROVAL_ERROR: 'no image'})   # another failure first
        self.assertEqual(other[APPROVAL_UNTIL], prior[APPROVAL_UNTIL])               # keeps its window

    def test_an_image_pil_cannot_open_is_not_white_and_any_one_mark_is_still_a_checked_read(self):
        from apps.scholarship.income_declaration import APPROVAL_ERROR, approval_missing, approval_page_white
        self.assertFalse(approval_page_white(b'not an image'))
        for key, value in (('issuer_header', 'JKKK KAMPUNG CONTOH'), ('has_stamp', 'yes'),
                           ('has_signature', 'yes'), ('approver_name', 'QORVA BIN ZELT')):
            with self.subTest(key):
                doc, out, _ = self._read(_page(typed=True), {**self.NOTHING, key: value})
                self.assertNotIn(APPROVAL_ERROR, out)
                self.assertEqual(out['fields'][key], value)
                self.assertNotEqual(approval_missing(doc), ())


def _png_header_only(width, height, bit_depth=8):
    """A one-colour (white) greyscale PNG of this size whose IDAT holds only its first rows: PIL reads the
    size off the header, and any decode of the whole image would be needed to judge it."""
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    row = b'\x00' + b'\xff' * (width * bit_depth // 8)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, bit_depth, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(row * 4)) + chunk(b'IEND', b''))


def _ink_page(mode):
    """A 1000 x 1400 page with a dark text block (about 10% ink), in the given PIL mode, as PNG bytes."""
    from PIL import Image, ImageDraw
    im = Image.new('L', (1000, 1400), 255)
    ImageDraw.Draw(im).rectangle([100, 100, 900, 280], fill=30)
    if mode != 'L':
        im = im.point(lambda v: v * 257, 'I').convert(mode)        # 16-bit: 0..65535, the ink stays dark
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    return buf.getvalue()


class TheWhiteCheckGuards(SimpleTestCase):
    """Review round 2: the white check runs in the request's own process on an uploaded image."""

    def test_an_image_over_the_pixel_cap_is_not_white_and_is_never_decoded(self):
        from PIL import Image, ImageFile
        from apps.scholarship.income_declaration import WHITE_CHECK_MAX_PIXELS, approval_page_white
        big = _png_header_only(5000, 4000)                     # 20 MP: over the 16 MP cap, ~1 kB of bytes
        with Image.open(io.BytesIO(big)) as im:
            self.assertGreater(im.width * im.height, WHITE_CHECK_MAX_PIXELS)
        with mock.patch.object(ImageFile.ImageFile, 'load') as load, \
                mock.patch.object(Image.Image, 'convert') as convert:
            self.assertFalse(approval_page_white(big))
        load.assert_not_called()
        convert.assert_not_called()
        self.assertTrue(approval_page_white(_page()))                          # under the cap: still judged

    def test_a_16_bit_greyscale_page_with_ink_is_not_white(self):
        from PIL import Image
        from apps.scholarship.income_declaration import approval_page_white
        self.assertFalse(approval_page_white(_ink_page('L')))                  # the 8-bit control
        page = _ink_page('I;16')
        with Image.open(io.BytesIO(page)) as im:
            self.assertTrue(im.mode == 'I' or im.mode.startswith('I;'), im.mode)
        self.assertFalse(approval_page_white(page))

    def _never_decoded(self, data):
        """``approval_page_white(data)`` with every decode patched out: False, and nothing was decoded."""
        from PIL import IcoImagePlugin, Image, ImageFile
        from apps.scholarship.income_declaration import approval_page_white
        with mock.patch.object(ImageFile.ImageFile, 'load') as load, \
                mock.patch.object(IcoImagePlugin.IcoImageFile, 'load') as ico_load, \
                mock.patch.object(Image.Image, 'convert') as convert:
            self.assertFalse(approval_page_white(data))
        load.assert_not_called()
        ico_load.assert_not_called()
        convert.assert_not_called()

    def test_an_ico_wrapping_a_huge_png_is_not_white_and_is_never_decoded(self):
        """Review round 3, B1: PIL's ICO opener decodes the whole image inside `open`, before any size
        check (a 580 kB ICO of a 12000 x 12000 PNG took ~600 MB). ICO is not an allowed format."""
        import struct
        from PIL import IcoImagePlugin, Image
        png = _png_header_only(12000, 12000)
        ico = struct.pack('<HHH', 0, 1, 1) + struct.pack('<BBBBHHII', 0, 0, 0, 0, 1, 32, len(png), 22) + png
        self.assertTrue(IcoImagePlugin._accept(ico[:16]))      # PIL's ICO driver would take it ...
        with Image.open(io.BytesIO(png)) as im:
            self.assertEqual(im.size, (12000, 12000))           # ... and decode this PNG inside `open`
        self._never_decoded(ico)

    def test_a_huge_progressive_jpeg_is_not_white_and_is_never_decoded(self):
        """Review round 3, B2: libjpeg holds a progressive JPEG's full-size buffer whatever the draft scale
        (a 2 MB 13000 x 13000 one took ~1 GB), so the cap is judged on the HEADER size, before the draft."""
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (64, 64), 'white').save(buf, format='JPEG', progressive=True)
        data = bytearray(buf.getvalue())
        sof = data.index(b'\xff\xc2')                          # SOF2: marker, length, precision, height, width
        data[sof + 5:sof + 9] = (13000).to_bytes(2, 'big') * 2
        with Image.open(io.BytesIO(bytes(data))) as im:
            self.assertEqual((im.size, bool(im.info.get('progressive'))), ((13000, 13000), True))
        self._never_decoded(bytes(data))

    def test_a_12_mp_phone_photo_is_judged_as_before_baseline_and_progressive(self):
        from PIL import Image, ImageDraw
        from apps.scholarship.income_declaration import approval_page_white
        for progressive in (False, True):
            for inked in (False, True):
                with self.subTest(progressive=progressive, inked=inked):
                    im = Image.new('RGB', (4000, 3000), 'white')
                    if inked:
                        ImageDraw.Draw(im).rectangle([400, 400, 3600, 900], fill=(30, 30, 30))
                    buf = io.BytesIO()
                    im.save(buf, format='JPEG', quality=85, progressive=progressive)
                    self.assertLess(len(buf.getvalue()), 2_000_000)
                    self.assertEqual(approval_page_white(buf.getvalue()), not inked)


class NestedValuesAreLookedInside(SimpleTestCase):

    def test_blank_slip_rows_are_not_a_filled_read_and_one_filled_cell_is(self):
        from apps.scholarship.vision.judge import _any_field_filled
        blank = {'results': [{'subject': '', 'grade': ' ', 'band': ''}], 'exam': {'year': ''}}
        self.assertFalse(_any_field_filled(blank))
        self.assertEqual(doc_student_verdict('results_slip', blank, names=['X']), 'wrong_doc')
        self.assertTrue(_any_field_filled({'results': [{'subject': 'BAHASA MELAYU', 'grade': ''}]}))
        self.assertTrue(_any_field_filled({'exam': {'year': '2030'}}))
        self.assertTrue(_any_field_filled({'count': 3}))
