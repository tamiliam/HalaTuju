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


DRAWN = _pdf([_show(SPM_TEXT)])
HIDDEN = _pdf([_show(STPM_TEXT, mode=3)])
MIXED = _pdf([_show(SPM_TEXT), _show(STPM_TEXT, mode=3)])     # page 1 drawn, page 2 an OCR overlay


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

    def test_any_hidden_page_sends_the_whole_layer_to_vision(self):
        self.assertEqual(pdf_pages.pdf_text_layer(MIXED), '')

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

    def test_ocr_document_full_mixed_pdf_goes_to_vision(self, keep):
        out, seam = self._full(MIXED)
        seam.assert_called_once()
        self.assertEqual(out['text'], VISION_TEXT)

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
        # a mixed PDF: the whole layer is no layer, so the (Vision) text is kept, never cut to a layer
        layer, page1 = offer_exact.pdf_layers(MIXED, 'application/pdf')
        self.assertEqual(layer, '')
        self.assertIn('SIJIL PELAJARAN', page1)
        self.assertEqual(field_extraction._page1_text(VISION_TEXT, MIXED, 'application/pdf'), VISION_TEXT)
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

    def test_model_version(self):
        self.assertEqual(MODEL_VERSION, '1.31.0')
