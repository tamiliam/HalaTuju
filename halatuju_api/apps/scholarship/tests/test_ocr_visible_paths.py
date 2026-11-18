"""S-visible fix round 3: the visibility walk judges EVERY character pypdf's ``extract_text`` can give.

Each test hides text a way the round-2 walk missed (a string operand it did not read, an XObject it did not
follow, resources it did not inherit, a render mode it took for drawn) or feeds a content stream that is
costly to parse. ``*_premise`` checks show pypdf really extracts the hidden words. Fictional words only.
"""
import time
import zlib
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import pdf_pages
from apps.scholarship.tests.test_ocr_visible import DRAWN, SPM_TEXT, _pdf, _raw_layer, _show, _stream

FONT = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
FONT_RES = b'/Font << /F1 3 0 R >>'
SECRET = b'DISAHKAN BAHAWA'


def _doc(content, objs=None, page_res=b'/Resources << ' + FONT_RES + b' >>', pages_res=b'', font=FONT,
         filtered=False):
    """A one-page PDF: 1 catalog, 2 pages (``pages_res`` inherited by the page), 3 font /F1, 4 the page,
    5 its content (FlateDecode when ``filtered``), 6+ ``objs``."""
    body = _stream(b'<< /Filter /FlateDecode', zlib.compress(content)) if filtered else _stream(b'<<', content)
    objs = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 2: b'<< /Type /Pages /Kids [4 0 R] /Count 1 ' + pages_res + b' >>',
            3: font, 4: b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] ' + page_res + b' /Contents 5 0 R >>',
            5: body, **(objs or {})}
    out, offsets = b'%PDF-1.4\n', []
    for num in range(1, max(objs) + 1):
        offsets.append(len(out))
        out += b'%d 0 obj\n' % num + objs[num] + b'\nendobj\n'
    xref = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(offsets) + 1)
    out += b''.join(b'%010d 00000 n \n' % off for off in offsets)
    return out + b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF' % (len(offsets) + 1, xref)


def _hidden_op(show):
    """Mode-3 text shown by the operator ``show``, then drawn text: the page must be hidden."""
    return b'BT /F1 12 Tf 3 Tr 20 150 Td ' + show + b' ET ' + _show(SPM_TEXT)


def _xobj(head, content):
    return _stream(b'<< /Type /XObject ' + head + b' /BBox [0 0 300 200] /Resources << ' + FONT_RES + b' >>', content)


class TheStringOperandsPypdfReads(SimpleTestCase):
    def _assert_hidden(self, show, premise=True):
        pdf = _doc(_hidden_op(show))
        if premise:
            self.assertIn('DISAHKAN', _raw_layer(pdf))
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')
        self.assertFalse(pdf_pages.first_page_drawn(pdf))

    def test_tj_with_a_trailing_empty_string(self):
        self._assert_hidden(b'(' + SECRET + b') () Tj')

    def test_quote_with_a_trailing_space_string(self):
        self._assert_hidden(b'(' + SECRET + b') ( ) \'')

    def test_double_quote_with_a_trailing_empty_string(self):
        self._assert_hidden(b'0 0 (' + SECRET + b') () "')

    def test_tj_array_with_a_trailing_empty_string(self):
        self._assert_hidden(b'[(' + SECRET + b')] () TJ')

    def test_tj_with_a_plain_string_operand(self):
        # pypdf 5.9 reads a TJ string operand character by character; 6.x ignores it. Either way: hidden.
        self._assert_hidden(b'(' + SECRET + b') TJ', premise=False)

    def test_blanks_an_encoding_maps_to_letters_are_hidden_text(self):
        font = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding << /Type /Encoding /Differences [32 /Z] >> >>'
        pdf = _doc(b'BT /F1 12 Tf 3 Tr 20 150 Td (   ) Tj ET ' + _show(SPM_TEXT), font=font)
        self.assertIn('ZZZ', _raw_layer(pdf))
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')


class TheXObjectsPypdfReads(SimpleTestCase):
    def test_drawn_text_in_a_non_form_xobject_is_hidden(self):
        # pypdf extracts every XObject that is not an /Image; a viewer paints only forms and images
        pdf = _doc(_show(SPM_TEXT) + b' /X1 Do', {6: _xobj(b'/Subtype /PS', _show(SECRET.decode()))},
                   page_res=b'/Resources << ' + FONT_RES + b' /XObject << /X1 6 0 R >> >>')
        self.assertIn('DISAHKAN', _raw_layer(pdf))
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_text_in_an_xobject_without_a_subtype_is_hidden(self):
        pdf = _doc(_show(SPM_TEXT) + b' /X1 Do', {6: _xobj(b'', _show(SECRET.decode()))},
                   page_res=b'/Resources << ' + FONT_RES + b' /XObject << /X1 6 0 R >> >>')
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_an_image_xobject_is_not_text(self):
        image = _stream(b'<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray '
                        b'/BitsPerComponent 8', b'\x00')
        pdf = _doc(_show(SPM_TEXT) + b' q 10 0 0 10 0 0 cm /Im1 Do Q', {6: image},
                   page_res=b'/Resources << ' + FONT_RES + b' /XObject << /Im1 6 0 R >> >>')
        self.assertIn('SIJIL PELAJARAN', pdf_pages.pdf_text_layer(pdf))

    def test_a_form_named_in_inherited_page_resources_is_walked(self):
        # the page has no /Resources: pypdf takes the /Pages node's, and so does the walk
        pdf = _doc(_show(SPM_TEXT) + b' /Fm1 Do', {6: _xobj(b'/Subtype /Form', _show(SECRET.decode(), mode=3))},
                   page_res=b'', pages_res=b'/Resources << ' + FONT_RES + b' /XObject << /Fm1 6 0 R >> >>')
        self.assertIn('DISAHKAN', _raw_layer(pdf))
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')


class TheRenderModes(SimpleTestCase):
    def test_a_mode_outside_0_to_7_or_not_an_integer_is_hidden(self):
        for tr in (b'9', b'-1', b'0.5', b'/X'):
            with self.subTest(tr=tr):
                pdf = _doc(b'BT /F1 12 Tf ' + tr + b' Tr 20 150 Td (' + SECRET + b') Tj ET')
                self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_every_painting_mode_keeps_the_layer(self):
        for tr in (0, 1, 2, 4, 5, 6):
            with self.subTest(tr=tr):
                pdf_pages._layer_memo_clear()
                self.assertIn('SIJIL', pdf_pages.pdf_text_layer(_doc(_show(SPM_TEXT, mode=tr))))


class TheDocumentBudgets(SimpleTestCase):
    def _hostile(self, data):
        """Every reader gives the Vision route, never extracts, and the whole check is fast (< 3 s)."""
        from pypdf import PageObject
        pdf_pages._layer_memo_clear()
        t0 = time.perf_counter()
        with patch.object(PageObject, 'extract_text', side_effect=AssertionError('no extraction of a bomb')):
            self.assertEqual(pdf_pages.pdf_text_layer(data), '')
            self.assertEqual(''.join(pdf_pages.pdf_page_texts(data, 3)), '')
            self.assertFalse(pdf_pages.first_page_drawn(data))
        self.assertLess(time.perf_counter() - t0, 3.0)

    def test_decompressed_bytes_past_the_cap_are_refused_unparsed(self):
        data = _doc(b' ' * 9_000_000, filtered=True)
        self.assertLess(len(data), 64_000)
        self._hostile(data)

    def test_a_4_mb_string(self):
        self._hostile(_doc(b'BT /F1 12 Tf 20 150 Td (' + b'A' * 4_000_000 + b') Tj ET', filtered=True))

    def test_one_huge_token_of_any_kind_is_refused_unparsed(self):
        # pypdf parses one huge token in worse than linear time; blanks inside do not hide a string's size
        for body in (b'(' + b'A ' * 1_000_000 + b') Tj', b'(' + b'A(B)' * 500_000 + b') Tj',
                     b'<' + b'41 ' * 700_000 + b'> Tj', b'/' + b'N' * 2_000_000 + b' gs', b'7' * 2_000_000 + b' Tz'):
            with self.subTest(body=body[:4]):
                self._hostile(_doc(b'BT /F1 12 Tf 20 150 Td ' + body + b' ET', filtered=True))

    def test_200k_inline_images(self):
        self._hostile(_doc(b'BI /W 1 /H 1 /BPC 8 /CS /G ID \x00 EI ' * 200_000, filtered=True))

    def test_inline_images_past_their_own_cap(self):
        self._hostile(_doc(b'BI /W 1 /H 1 /BPC 8 /CS /G ID \x00 EI ' * 3_000))

    def test_a_token_bomb_under_the_byte_cap(self):
        self._hostile(_doc(b'0 g ' * 1_500_000, filtered=True))

    def test_streams_each_just_under_the_stream_token_cap(self):
        # 3 pages of 190,000 operations (380,000 tokens each): page 2 is past the document's tokens, unparsed
        self._hostile(_pdf([b'0 g ' * 190_000 + _show(SPM_TEXT)] * 3))

    def test_a_read_with_more_text_than_the_memo_limit_is_not_kept(self):
        with patch('apps.scholarship.pdf_pages._MEMO_MAX_TEXT', 10):
            self.assertIn('SIJIL', pdf_pages.pdf_text_layer(DRAWN))
            self.assertEqual(len(pdf_pages._LAYER_MEMO), 0)
        self.assertIn('SIJIL', pdf_pages.pdf_text_layer(DRAWN))
        self.assertEqual(len(pdf_pages._LAYER_MEMO), 1)
