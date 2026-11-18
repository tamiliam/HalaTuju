"""S-visible (owner decision 2026-11-18): "what we see is what we can defend".

A PDF page whose text is INVISIBLE (a phone scanner app's OCR overlay on a photo: text render mode 3,
or 7) has no text layer: the read takes the scanned-PDF route (page 1 rasterised, one Cloud Vision
read). A PDF whose text is drawn keeps its free text layer (no Vision call). A page that cannot be
checked takes the Vision route, never the hidden text.

Synthetic PDFs built here (fictional words only). Vision is always mocked; nothing reaches the network.
"""
import io
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import offer_exact, offer_reader, pdf_pages, vision
from apps.scholarship.genuineness.results_doc import MODEL_VERSION
from apps.scholarship.vision import field_extraction

SPM_TEXT = 'SIJIL PELAJARAN MALAYSIA KEPUTUSAN PEPERIKSAAN CALON CONTOH'
STPM_TEXT = 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA DENGAN INI DISAHKAN BAHAWA'
VISION_TEXT = 'MAJLIS PEPERIKSAAN MALAYSIA SIJIL TINGGI PERSEKOLAHAN MALAYSIA TAHUN PEPERIKSAAN'


def _show(text, mode=0, prefix=b''):
    """One text object showing ``text`` in render mode ``mode``."""
    return prefix + b'BT /F1 12 Tf ' + str(mode).encode() + b' Tr 20 150 Td (' + text.encode() + b') Tj ET'


def _stream(dict_head, data):
    return dict_head + b' /Length ' + str(len(data)).encode() + b' >>\nstream\n' + data + b'\nendstream'


def _pdf(pages, form=None):
    """A valid PDF, one page per content stream in ``pages``. ``form`` is the content of a Form XObject
    /Fm1 every page may call with ``/Fm1 Do``."""
    objs = {1: b'<< /Type /Catalog /Pages 2 0 R >>',
            3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
            4: (_stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 300 200] '
                        b'/Resources << /Font << /F1 3 0 R >> >>', form) if form is not None else b'null')}
    xobj = b' /XObject << /Fm1 4 0 R >>' if form is not None else b''
    kids = []
    for i, content in enumerate(pages):
        page, body = 5 + 2 * i, 6 + 2 * i
        kids.append(b'%d 0 R' % page)
        objs[page] = (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 3 0 R >>'
                      + xobj + b' >> /Contents %d 0 R >>' % body)
        objs[body] = _stream(b'<<', content)
    objs[2] = b'<< /Type /Pages /Kids [' + b' '.join(kids) + b'] /Count %d >>' % len(pages)
    out = b'%PDF-1.4\n'
    offsets = []
    for num in range(1, max(objs) + 1):
        offsets.append(len(out))
        out += b'%d 0 obj\n' % num + objs[num] + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(offsets) + 1)
    out += b''.join(b'%010d 00000 n \n' % off for off in offsets)
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF' % (len(offsets) + 1, xref)
    return out


def _pdf_forms(page_content, forms):
    """A one-page PDF whose page and every form XObject can call any form by name (``forms``: name ->
    content). A form may call itself, or fan out to the next level many times."""
    names = sorted(forms)
    nums = {name: 4 + i for i, name in enumerate(names)}
    xobj = b'/XObject << ' + b' '.join(b'/%s %d 0 R' % (n.encode(), nums[n]) for n in names) + b' >>'
    res = b'/Resources << /Font << /F1 3 0 R >> ' + xobj + b' >>'
    objs = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [%d 0 R] /Count 1 >>' % (4 + len(names)),
            3: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'}
    for name in names:
        objs[nums[name]] = _stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 300 200] ' + res, forms[name])
    page = 4 + len(names)
    objs[page] = b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] ' + res + b' /Contents %d 0 R >>' % (page + 1)
    objs[page + 1] = _stream(b'<<', page_content)
    out = b'%PDF-1.4\n'
    offsets = []
    for num in range(1, max(objs) + 1):
        offsets.append(len(out))
        out += b'%d 0 obj\n' % num + objs[num] + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(offsets) + 1)
    out += b''.join(b'%010d 00000 n \n' % off for off in offsets)
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF' % (len(offsets) + 1, xref)
    return out


DRAWN = _pdf([_show(SPM_TEXT)])
HIDDEN = _pdf([_show(STPM_TEXT, mode=3)])
MIXED = _pdf([_show(SPM_TEXT), _show(STPM_TEXT, mode=3)])     # page 1 drawn, page 2 an OCR overlay
HIDDEN_FIRST = _pdf([_show(STPM_TEXT, mode=3), _show(SPM_TEXT)])   # page 1 an OCR overlay, page 2 drawn
SCANNED = _pdf([b'q Q'])                                      # no text at all: a plain scanned PDF
#: Under 3 KB of PDF, 40 form calls per level, 4 levels: 2.5 million invocations without the operation budget.
FAN_OUT = _pdf_forms(b'/A Do', {'A': b'/B Do ' * 40, 'B': b'/C Do ' * 40, 'C': b'/D Do ' * 40,
                                'D': b'/E Do ' * 40, 'E': _show(SPM_TEXT)})
SELF_CALL = _pdf_forms(_show(SPM_TEXT) + b' /A Do', {'A': b'/A Do'})


def _raw_layer(data):
    from pypdf import PdfReader
    return '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(data)).pages)


class TheDetectionRule(SimpleTestCase):
    def test_the_hidden_text_is_really_in_the_raw_layer(self):
        # the premise: pypdf extracts invisible text as if it were printed
        self.assertIn('DISAHKAN', _raw_layer(HIDDEN))

    def test_a_drawn_pdf_keeps_its_layer(self):
        self.assertIn('SIJIL PELAJARAN MALAYSIA', pdf_pages.pdf_text_layer(DRAWN))
        self.assertEqual(pdf_pages.pdf_page_texts(DRAWN, 3)[0][:24], 'SIJIL PELAJARAN MALAYSIA')

    def test_render_mode_3_is_no_layer(self):
        self.assertEqual(pdf_pages.pdf_text_layer(HIDDEN), '')
        self.assertEqual(pdf_pages.pdf_page_texts(HIDDEN, 3), [''])

    def test_render_mode_7_is_no_layer(self):
        self.assertEqual(pdf_pages.pdf_text_layer(_pdf([_show(STPM_TEXT, mode=7)])), '')

    def test_a_mode_set_inside_q_is_restored_by_Q(self):
        pdf = _pdf([b'q BT 3 Tr ET Q ' + b'BT /F1 12 Tf 20 150 Td (' + SPM_TEXT.encode() + b') Tj ET'])
        self.assertIn('SIJIL PELAJARAN', pdf_pages.pdf_text_layer(pdf))

    def test_a_mode_left_set_after_ET_still_hides_the_next_text(self):
        pdf = _pdf([b'BT 3 Tr ET ' + b'BT /F1 12 Tf 20 150 Td (' + STPM_TEXT.encode() + b') Tj ET'])
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_blank_hidden_strings_do_not_count(self):
        pdf = _pdf([_show('   ', mode=3) + b' ' + _show(SPM_TEXT)])
        self.assertIn('SIJIL PELAJARAN', pdf_pages.pdf_text_layer(pdf))

    def test_hidden_text_inside_a_form_xobject_is_found(self):
        pdf = _pdf([b'/Fm1 Do'], form=_show(STPM_TEXT, mode=3))
        self.assertIn('DISAHKAN', _raw_layer(pdf))
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_a_form_called_from_mode_3_inherits_it(self):
        pdf = _pdf([b'BT 3 Tr ET /Fm1 Do'], form=b'BT /F1 12 Tf 20 150 Td (' + STPM_TEXT.encode() + b') Tj ET')
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_tj_arrays_are_counted(self):
        pdf = _pdf([b'BT /F1 12 Tf 3 Tr 20 150 Td [(SIJIL TINGGI) -250 (PERSEKOLAHAN MALAYSIA DENGAN)] TJ ET'])
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_a_drawn_page_1_keeps_its_text_and_a_hidden_page_2_is_left_out(self):
        layer = pdf_pages.pdf_text_layer(MIXED)
        self.assertIn('SIJIL PELAJARAN MALAYSIA', layer)
        self.assertNotIn('DISAHKAN', layer)
        self.assertNotIn('PERSEKOLAHAN', layer)

    def test_a_hidden_page_1_is_no_layer_even_with_a_drawn_page_2(self):
        self.assertEqual(pdf_pages.pdf_text_layer(HIDDEN_FIRST), '')

    def test_a_form_that_calls_itself_is_the_vision_route(self):
        self.assertEqual(pdf_pages.pdf_text_layer(SELF_CALL), '')
        self.assertEqual(pdf_pages.pdf_page_texts(SELF_CALL, 1), [''])

    def test_a_fan_out_bomb_stops_fast_on_the_vision_route_and_is_never_extracted(self):
        import time
        from pypdf import PageObject
        t0 = time.perf_counter()
        with patch.object(PageObject, 'extract_text', side_effect=AssertionError('no extraction of a bomb')):
            self.assertEqual(pdf_pages.pdf_text_layer(FAN_OUT), '')
            self.assertEqual(pdf_pages.pdf_page_texts(FAN_OUT, 3), [''])
            self.assertFalse(pdf_pages.first_page_drawn(FAN_OUT))
        self.assertLess(len(FAN_OUT), 4096)
        self.assertLess(time.perf_counter() - t0, 2.0)

    def test_an_over_budget_later_page_stops_extraction_of_the_whole_pdf(self):
        with patch('apps.scholarship.pdf_pages._MAX_PAGE_OPS', 1):
            # page 1 shows one string (within budget), page 2 three: no page of this PDF is extracted
            pdf = _pdf([_show(SPM_TEXT), _show('A') + b' ' + _show('B') + b' ' + _show('C')])
            self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')
            self.assertEqual(pdf_pages.pdf_page_texts(pdf, 2), ['', ''])

    def test_an_encrypted_hidden_pdf_never_gives_its_hidden_text(self):
        from pypdf import PdfReader, PdfWriter
        for user_password in ('', 'secret'):
            writer = PdfWriter()
            for page in PdfReader(io.BytesIO(HIDDEN)).pages:
                writer.add_page(page)
            writer.encrypt(user_password=user_password, owner_password='owner', algorithm='RC4-128')
            buf = io.BytesIO()
            writer.write(buf)
            data = buf.getvalue()
            self.assertEqual(pdf_pages.pdf_text_layer(data), '', user_password)
            self.assertEqual(''.join(pdf_pages.pdf_page_texts(data, 3)), '', user_password)
            self.assertFalse(pdf_pages.first_page_drawn(data), user_password)

    def test_page_texts_decide_per_page(self):
        pages = pdf_pages.pdf_page_texts(MIXED, 5)
        self.assertIn('SIJIL PELAJARAN', pages[0])
        self.assertEqual(pages[1], '')

    def test_a_detection_error_is_the_vision_route(self):
        with patch('apps.scholarship.pdf_pages._walk_text_modes', side_effect=RuntimeError('bad stream')):
            self.assertEqual(pdf_pages.pdf_text_layer(DRAWN), '')
            self.assertEqual(pdf_pages.pdf_page_texts(DRAWN, 2), [''])


def _doc(content_type='application/pdf'):
    return SimpleNamespace(id=1, storage_path='test/doc.pdf', content_type=content_type, application=None)


@patch('apps.scholarship.ocr_keep.keep')
class TheCentralReaders(SimpleTestCase):
    def _full(self, data, content_type='application/pdf'):
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=data), \
                patch('apps.scholarship.vision._vision_words',
                      return_value={'text': VISION_TEXT, 'words': [], 'error': None}) as seam:
            return vision.ocr_document_full(_doc(content_type)), seam

    def test_ocr_document_full_reads_a_hidden_pdf_with_vision_once(self, keep):
        out, seam = self._full(HIDDEN)
        seam.assert_called_once_with(HIDDEN, 'application/pdf')
        self.assertEqual(out['text'], VISION_TEXT)
        self.assertNotIn('DISAHKAN', out['text'])
        self.assertEqual(keep.call_args.kwargs['source'], 'vision_ocr')

    def test_ocr_document_full_keeps_a_drawn_layer_without_vision(self, keep):
        out, seam = self._full(DRAWN)
        seam.assert_not_called()
        self.assertIn('SIJIL PELAJARAN MALAYSIA', out['text'])
        self.assertIsNone(out['words'])
        self.assertEqual(keep.call_args.kwargs['source'], 'pdf_text_layer')

    def test_ocr_document_full_mixed_pdf_keeps_its_drawn_page_only(self, keep):
        out, seam = self._full(MIXED)
        seam.assert_not_called()
        self.assertIn('SIJIL PELAJARAN MALAYSIA', out['text'])
        self.assertNotIn('DISAHKAN', out['text'])
        self.assertNotIn('DISAHKAN', keep.call_args.args[1])

    def test_ocr_document_full_hidden_page_1_goes_to_vision(self, keep):
        out, seam = self._full(HIDDEN_FIRST)
        seam.assert_called_once_with(HIDDEN_FIRST, 'application/pdf')
        self.assertEqual(out['text'], VISION_TEXT)

    def test_ocr_document_full_fan_out_bomb_goes_to_vision(self, keep):
        out, seam = self._full(FAN_OUT)
        seam.assert_called_once()
        self.assertEqual(out['text'], VISION_TEXT)

    def test_a_vision_error_on_a_hidden_pdf_is_the_scanned_pdf_answer(self, keep):
        failed = {'text': '', 'words': None, 'error': 'Vision unavailable'}
        outs = []
        for data in (HIDDEN, SCANNED):
            with patch('apps.scholarship.vision._fetch_image_bytes', return_value=data), \
                    patch('apps.scholarship.vision._vision_words', return_value=dict(failed)):
                out = vision.ocr_document_full(_doc())
            outs.append({k: v for k, v in out.items() if k != 'image'})
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[0]['text'], '')

    def test_a_rasterise_failure_on_a_hidden_pdf_is_the_scanned_pdf_answer(self, keep):
        outs = []
        for data in (HIDDEN, SCANNED):
            with patch('apps.scholarship.vision._fetch_image_bytes', return_value=data), \
                    patch('apps.scholarship.vision._pdf_first_page_png', return_value=None), \
                    patch('apps.scholarship.vision._vision_document_text') as seam:
                outs.append(vision.ocr_document(_doc()))
                self.assertEqual(vision.extract_text(data, 'application/pdf'), outs[-1])
            seam.assert_not_called()
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[0]['text'], '')

    def test_ocr_document_full_detection_error_goes_to_vision(self, keep):
        with patch('apps.scholarship.pdf_pages._walk_text_modes', side_effect=ValueError('x')):
            out, seam = self._full(DRAWN)
        seam.assert_called_once()
        self.assertEqual(out['text'], VISION_TEXT)

    def test_a_photo_is_unchanged(self, keep):
        out, seam = self._full(b'\xff\xd8\xff photo', 'image/jpeg')
        seam.assert_called_once_with(b'\xff\xd8\xff photo', 'image/jpeg')
        self.assertEqual(out['text'], VISION_TEXT)

    def test_ocr_document_reads_page_one_image_of_a_hidden_pdf(self, keep):
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=HIDDEN), \
                patch('apps.scholarship.vision._pdf_first_page_png', return_value=b'PAGE1PNG') as raster, \
                patch('apps.scholarship.vision._vision_document_text',
                      return_value={'text': VISION_TEXT, 'error': None}) as seam:
            out = vision.ocr_document(_doc())
        raster.assert_called_once_with(HIDDEN)
        seam.assert_called_once_with(b'PAGE1PNG')
        self.assertEqual(out['text'], VISION_TEXT)
        self.assertEqual(keep.call_args.kwargs['source'], 'vision_ocr')

    def test_ocr_document_keeps_a_drawn_layer(self, keep):
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=DRAWN), \
                patch('apps.scholarship.vision._vision_document_text') as seam:
            out = vision.ocr_document(_doc())
        seam.assert_not_called()
        self.assertIn('SIJIL PELAJARAN MALAYSIA', out['text'])

    def test_extract_text_on_a_hidden_pdf_and_on_a_photo(self, keep):
        with patch('apps.scholarship.vision._pdf_first_page_png', return_value=b'PAGE1PNG'), \
                patch('apps.scholarship.vision._vision_document_text',
                      return_value={'text': VISION_TEXT, 'error': None}) as seam:
            self.assertEqual(vision.extract_text(HIDDEN, 'application/pdf')['text'], VISION_TEXT)
            seam.assert_called_once_with(b'PAGE1PNG')
            vision.extract_text(b'\xff\xd8\xff photo', 'image/jpeg')
            seam.assert_called_with(b'\xff\xd8\xff photo')


class TheOtherLayerReaders(SimpleTestCase):
    def test_slip_gate_page_one_check_follows_the_rule(self):
        # a hidden PDF has no layer: the text handed in is Vision's page-1 read and is checked as it is
        self.assertEqual(offer_exact.pdf_layers(HIDDEN, 'application/pdf'), ('', ''))
        self.assertEqual(field_extraction._page1_text(VISION_TEXT, HIDDEN, 'application/pdf'), VISION_TEXT)
        # a mixed PDF (drawn page 1): the layer is page 1's drawn text only, cut to page 1 as before
        layer, page1 = offer_exact.pdf_layers(MIXED, 'application/pdf')
        self.assertIn('SIJIL PELAJARAN', page1)
        self.assertNotIn('DISAHKAN', layer)
        self.assertEqual(field_extraction._page1_text(layer, MIXED, 'application/pdf'), page1)
        # hidden page 1 in front of a drawn page: no layer at all, the (Vision) text is checked as it is
        self.assertEqual(offer_exact.pdf_layers(HIDDEN_FIRST, 'application/pdf'), ('', ''))
        self.assertEqual(field_extraction._page1_text(VISION_TEXT, HIDDEN_FIRST, 'application/pdf'), VISION_TEXT)
        # a drawn PDF: its layer IS the text, so page 1's layer is checked (unchanged)
        drawn_layer = pdf_pages.pdf_text_layer(DRAWN)
        self.assertEqual(field_extraction._page1_text(drawn_layer, DRAWN, 'application/pdf'),
                         pdf_pages.pdf_page_texts(DRAWN, 1)[0])

    def test_slip_gate_refuses_a_hidden_pdf_on_its_visible_page_text(self):
        from apps.courses.models import StudentProfile
        doc = SimpleNamespace(application=SimpleNamespace(profile=StudentProfile(supabase_user_id='sv')),
                              content_type='application/pdf')
        with patch('apps.scholarship.vision._vision_words',
                   side_effect=AssertionError('no Vision call for a refused page')):
            ex, diag = vision._extract_slip_deterministic(doc, HIDDEN, text=VISION_TEXT)
        self.assertIsNone(ex)
        self.assertEqual((diag['reason'], diag['exam_type']), ('not_spm_exam', 'stpm'))

    def test_offer_reader_shows_no_hidden_page_text(self):
        with patch('apps.scholarship.pdf_pages.pdf_page_pngs', return_value=[b'P1', b'P2']):
            inputs = offer_reader.offer_inputs(MIXED, 'application/pdf')
        self.assertIn('SIJIL PELAJARAN', inputs['page_texts'][0])
        self.assertEqual(inputs['page_texts'][1], '')
        self.assertNotIn('DISAHKAN', inputs['text_layer'])

    def test_the_offer_branch_layer_test_sees_no_layer_on_a_hidden_pdf(self):
        # offer-scan-ocr's `offer_pdf_layer` is this exact test: a hidden PDF fails it, so that branch
        # scores the Vision text already read (no second call); a drawn PDF passes it, as before.
        def layered(data):
            return len(vision._usable_text_layer(vision._pdf_text_layer(data))) >= vision._MIN_PDF_TEXT
        self.assertFalse(layered(HIDDEN))
        self.assertTrue(layered(DRAWN))

    def test_spm_cert_reader_never_reads_a_hidden_page_1s_own_characters(self):
        # No pre_words (e.g. the Vision read failed): pdfium's text page would hold the invisible text.
        from apps.scholarship import spm_cert_parse
        real = spm_cert_parse._pdf_words
        self.assertTrue(real(HIDDEN))          # the premise: pdfium does see the hidden characters
        with patch.object(spm_cert_parse, '_pdf_words', wraps=real) as spy:
            self.assertIsNone(spm_cert_parse.parse_spm_cert('', None, HIDDEN))
            self.assertIsNone(spm_cert_parse.parse_spm_cert('', None, HIDDEN_FIRST))
            self.assertIsNone(spm_cert_parse.parse_spm_cert('', None, FAN_OUT))
        spy.assert_not_called()
        # a drawn page 1 is still read from its own characters, as before
        with patch.object(spm_cert_parse, '_pdf_words', wraps=real) as spy:
            spm_cert_parse.parse_spm_cert('', None, MIXED)
        spy.assert_called_once()

    def test_model_version(self):
        self.assertEqual(MODEL_VERSION, '1.31.0')
