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


# ── Fix round 4 (`pdf_layer_guards`): operand counts, font maps, optional content, long documents ────────
def _res(fonts=b'/F1 3 0 R', extra=b''):
    return b'/Resources << /Font << ' + fonts + b' >> ' + extra + b' >>'


class TheOperandCounts(SimpleTestCase):
    """pdfium takes an operator's LAST operands, pypdf the FIRST: a wrong count is hidden, even in mode 0."""

    def test_a_wrong_operand_count_or_kind_is_hidden(self):
        s = b'(' + SECRET + b')'
        for show in (b'0 3 Tr ' + s + b' Tj', b'0 7 Tr ' + s + b' Tj', s + b' ( ) Tj', b'0 0 ' + s + b' ( ) "',
                     b'[' + s + b'] [( )] TJ', s + b' TJ', b'[/DISAHKAN] TJ', b'/F1 9 12 Tf ' + s + b' Tj'):
            with self.subTest(show=show[:12]):
                pdf = _doc(b'BT /F1 12 Tf 20 150 Td ' + show + b' ET ' + _show(SPM_TEXT))
                self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')
                self.assertFalse(pdf_pages.first_page_drawn(pdf))

    def test_two_forms_named_by_one_do_is_hidden(self):
        # pypdf extracts /Fm1 (the first operand); a viewer paints /Fm2 (the last)
        pdf = _doc(_show(SPM_TEXT) + b' /Fm1 /Fm2 Do', {6: _xobj(b'/Subtype /Form', _show(SECRET.decode())),
                                                        7: _xobj(b'/Subtype /Form', b'')},
                   page_res=_res(extra=b'/XObject << /Fm1 6 0 R /Fm2 7 0 R >>'))
        self.assertIn('DISAHKAN', _raw_layer(pdf))
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_well_formed_operators_keep_the_layer(self):
        pdf = _doc(b"BT /F1 12 Tf 20 150 Td [(SIJIL) -20 ( PELAJARAN)] TJ (MALAYSIA) ' 1 2 (SPM) \" <4142> Tj ET")
        self.assertIn('SIJIL', pdf_pages.pdf_text_layer(pdf))


def _to_unicode(lo, hi):
    return _stream(b'<<', b'/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n1 begincodespacerange\n<'
                   + lo + b'> <' + hi + b'>\nendcodespacerange\n1 beginbfrange\n<' + lo + b'> <' + hi
                   + b'> <0041>\nendbfrange\nendcmap\nend\nend')


BIG_FONT = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 6 0 R >>'
NAMES_40 = b' '.join(b'/F%d 3 0 R' % i for i in range(1, 41))


class TheFontMaps(SimpleTestCase):
    """pypdf rebuilds every listed font's maps on each extraction call: charged per name, per call."""
    _hostile = TheDocumentBudgets._hostile

    def _form_fan_out(self, calls, fonts):
        form = _stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 300 200] ' + _res(fonts),
                       b'BT /F1 12 Tf 20 150 Td (A) Tj ET')
        return _doc(b'/Fm1 Do ' * calls + _show(SPM_TEXT), {6: _to_unicode(b'0000', b'FFFF'), 7: form, 8: FONT},
                    font=BIG_FONT, page_res=_res(b'/F1 8 0 R', b'/XObject << /Fm1 7 0 R >>'))

    def test_one_tiny_form_called_150_times(self):
        self._hostile(self._form_fan_out(150, b'/F1 3 0 R'))

    def test_40_font_names_for_one_font(self):
        self._hostile(_doc(_show(SPM_TEXT), {6: _to_unicode(b'0000', b'FFFF')}, font=BIG_FONT, page_res=_res(NAMES_40)))

    def test_40_font_names_in_a_form_called_150_times(self):
        self._hostile(self._form_fan_out(150, NAMES_40))

    def test_one_font_past_its_own_limit(self):
        huge_range = {6: _to_unicode(b'00000000', b'FFFFFFFF')}            # pypdf 5.9 would map 4 billion codes
        wide = (b'<< /Type /Font /Subtype /Type0 /BaseFont /X /Encoding /Identity-H /DescendantFonts [<< /Type /Font '
                b'/Subtype /CIDFontType2 /BaseFont /X /W [' + b'1 2 3 ' * 7_000 + b'] >>] >>')
        long_range = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /FirstChar 0 /LastChar 900000000 >>'
        for objs, font in ((huge_range, BIG_FONT), ({}, wide), ({}, long_range)):
            with self.subTest(font=font[-30:]):
                self._hostile(_doc(_show(SPM_TEXT), objs, font=font))

    def test_a_real_sized_map_called_a_few_times_keeps_the_layer(self):
        pdf = self._form_fan_out(3, b'/F1 3 0 R')
        self.assertTrue(pdf_pages.first_page_drawn(pdf))
        self.assertIn('SIJIL', pdf_pages.pdf_text_layer(pdf))


def _oc_doc(content, default, objs=None, extra=b'/Properties << /MC0 6 0 R >>'):
    catalog = b'<< /Type /Catalog /Pages 2 0 R /OCProperties << /OCGs [6 0 R] /D ' + default + b' >> >>'
    return _doc(content + b' ' + _show(SPM_TEXT), {1: catalog, 6: b'<< /Type /OCG /Name (L) >>', **(objs or {})},
                page_res=_res(extra=extra))


ALL_ON = b'<< /ON [6 0 R] >>'
MARKED = b'/OC /MC0 BDC ' + _show(SECRET.decode()) + b' EMC'


class TheOptionalContent(SimpleTestCase):
    def test_text_in_a_layer_the_document_may_switch_off_is_hidden(self):
        for default in (b'<< /OFF [6 0 R] >>', b'<< /BaseState /OFF >>', b'<< /BaseState /Unchanged >>',
                        b'<< /AS [<< /Event /View /Category [/View] /OCGs [6 0 R] >>] >>', b'null'):
            with self.subTest(default=default):
                pdf = _oc_doc(MARKED, default)
                self.assertIn('DISAHKAN', _raw_layer(pdf))
                self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_a_form_with_an_oc_entry_in_a_document_that_switches_it_off(self):
        form = _xobj(b'/Subtype /Form /OC 6 0 R', _show(SECRET.decode()))
        pdf = _oc_doc(b'/Fm1 Do', b'<< /OFF [6 0 R] >>', {7: form}, b'/XObject << /Fm1 7 0 R >>')
        self.assertIn('DISAHKAN', _raw_layer(pdf))
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_a_membership_dictionary_or_an_unknown_name_is_hidden(self):
        for objs, content in (({7: b'<< /Type /OCMD /OCGs [6 0 R] >>'}, MARKED.replace(b'/MC0', b'/MC1')),
                              ({}, MARKED.replace(b'/MC0', b'/MC9'))):
            with self.subTest(content=content[:9]):
                pdf = _oc_doc(content, ALL_ON, objs, b'/Properties << /MC0 6 0 R /MC1 7 0 R >>')
                self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_a_plain_layer_that_is_on_or_other_marked_content_keeps_the_layer(self):
        span = b'/Span << /ActualText (X) >> BDC ' + _show('MAJLIS') + b' EMC'
        for content, default in ((MARKED, ALL_ON), (span, b'<< /OFF [6 0 R] >>')):
            with self.subTest(default=default):
                pdf_pages._layer_memo_clear()
                self.assertIn('SIJIL', pdf_pages.pdf_text_layer(_oc_doc(content, default)))


class TheLongDocuments(SimpleTestCase):
    def test_past_the_page_cap_the_first_and_the_last_pages_are_read(self):
        # a KWSP statement's latest contribution is on its LAST page
        pdf = _pdf([_show('HALAMAN%02dX' % i) for i in range(1, 26)])
        text = pdf_pages.pdf_text_layer(pdf)
        for i in range(1, 26):
            with self.subTest(page=i):
                self.assertEqual('HALAMAN%02dX' % i in text, i <= 10 or i >= 16)
        self.assertEqual([t[:10] for t in pdf_pages.pdf_page_texts(pdf, 3)], ['HALAMAN01X', 'HALAMAN02X', 'HALAMAN03X'])
