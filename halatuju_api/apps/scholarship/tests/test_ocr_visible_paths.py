"""S-visible fix round 3: the visibility walk judges EVERY character pypdf's ``extract_text`` can give.

Each test hides text a way the round-2 walk missed (a string operand it did not read, an XObject it did not
follow, resources it did not inherit, a render mode it took for drawn) or feeds a content stream that is
costly to parse. ``*_premise`` checks show pypdf really extracts the hidden words. Fictional words only.
"""
import io
import time
import zlib
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import pdf_pages
from apps.scholarship.pdf_layer_guards import OverBudget, page_tree_check
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
    def _hostile(self, data, limit=3.0):
        """Every reader gives the Vision route, never extracts, and the whole check is fast (< ``limit`` s)."""
        from pypdf import PageObject
        pdf_pages._layer_memo_clear()
        t0 = time.perf_counter()
        with patch.object(PageObject, 'extract_text', side_effect=AssertionError('no extraction of a bomb')):
            self.assertEqual(pdf_pages.pdf_text_layer(data), '')
            self.assertEqual(''.join(pdf_pages.pdf_page_texts(data, 3)), '')
            self.assertFalse(pdf_pages.first_page_drawn(data))
        self.assertLess(time.perf_counter() - t0, limit)

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
        # 3 pages of 190,000 operations (380,000 tokens each): page 2 is past the document's tokens, unparsed.
        # Page 1 is parsed by design (about 3 s of pypdf on the dev machine, so a wall-clock limit of 3 s was
        # flaky): the guard is pinned by what pypdf parses, ONE stream; the time limit only catches all three.
        from pypdf.generic import ContentStream
        parse = ContentStream._parse_content_stream
        with patch.object(ContentStream, '_parse_content_stream', autospec=True, side_effect=parse) as parsed:
            self._hostile(_pdf([b'0 g ' * 190_000 + _show(SPM_TEXT)] * 3), limit=8.0)
        self.assertEqual(parsed.call_count, 1)

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

    def test_a_blank_line_marks_the_pages_left_out(self):
        text = pdf_pages.pdf_text_layer(_pdf([_show('HALAMAN%02dX' % i) for i in range(1, 26)]))
        self.assertIn('\n\n', text.split('HALAMAN10X')[1].split('HALAMAN16X')[0])
        self.assertNotIn('\n\n', text.split('HALAMAN09X')[1].split('HALAMAN10X')[0])


# ── Fix round 5: raw tokens, inline images, text before a font, page trees, form calls, pdfium's own view ────
USAGE_OCG = b'<< /Type /OCG /Name (L) /Usage << /View << /ViewState /OFF >> >> >>'


class TheRawTokens(SimpleTestCase):
    def _hidden(self, content):
        pdf_pages._layer_memo_clear()
        pdf = _doc(content + b' ' + _show(SPM_TEXT))
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')
        self.assertFalse(pdf_pages.first_page_drawn(pdf))

    def test_a_tr_not_written_as_one_clean_digit_is_hidden(self):
        # pypdf reads "3-0" as 0 where pdfium reads 3: only a lone digit 0-7 is trusted
        for tr in (b'3-0', b'03', b'+0', b'0.0', b'1e0'):
            with self.subTest(tr=tr):
                self._hidden(b'BT /F1 12 Tf ' + tr + b' Tr 20 150 Td (' + SECRET + b') Tj ET')

    def test_a_name_that_decodes_to_a_control_byte_is_hidden(self):
        for op in (b'/F#01 12 Tf', b'/F1 12 Tf /GS#05 gs'):
            with self.subTest(op=op):
                self._hidden(b'BT ' + op + b' 20 150 Td (' + SECRET + b') Tj ET')

    def test_control_bytes_inside_a_string_keep_the_layer(self):
        pdf = _doc(b'BT /F1 12 Tf 20 150 Td (\x01\x02) Tj ET ' + _show(SPM_TEXT))
        self.assertIn('SIJIL', pdf_pages.pdf_text_layer(pdf))

    def test_one_inline_image_is_hidden(self):
        self._hidden(b'q 10 0 0 10 0 0 cm BI /W 1 /H 1 /BPC 8 /CS /G ID \x00 EI Q')

    def test_text_shown_before_any_font_is_hidden(self):
        # pdfium paints nothing before a Tf; a Tf inside q ... Q is gone after the Q
        for content in (b'BT 20 150 Td (' + SECRET + b') Tj ET',
                        b'q BT /F1 12 Tf ET Q BT 20 150 Td (' + SECRET + b') Tj ET'):
            with self.subTest(content=content[:8]):
                self._hidden(content)

    def test_an_ocg_with_a_usage_is_never_provably_shown(self):
        pdf = _oc_doc(MARKED, ALL_ON, {6: USAGE_OCG})
        self.assertIn('DISAHKAN', _raw_layer(pdf))
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')


def _be(n):
    return n.to_bytes(4, 'big')


def _page_tree(count, mids=990, fan=100):
    """``mids`` x ``fan`` page leaves (99,000 by default) in ONE object stream, under a two-level tree whose
    root claims ``count`` pages. The leaves a depth-first walk meets first come first in the stream."""
    leaf0 = 4 + mids
    ostm, xstm = leaf0 + mids * fan, leaf0 + mids * fan + 1
    leaves = range(ostm - 1, leaf0 - 1, -1)
    head, body, offset = [], [], 0
    for num in leaves:
        obj = b'<</Type/Page/Parent %d 0 R/MediaBox[0 0 300 200]>>\n' % (4 + (num - leaf0) // fan)
        head.append(b'%d %d' % (num, offset))
        body.append(obj)
        offset += len(obj)
    first = b' '.join(head) + b'\n'
    objs = {1: b'<< /Type /Catalog /Pages 2 0 R >>', 3: FONT,
            2: b'<< /Type /Pages /Kids [' + b' '.join(b'%d 0 R' % (4 + m) for m in range(mids)) + b'] /Count %d >>' % count,
            ostm: _stream(b'<< /Type /ObjStm /N %d /First %d /Filter /FlateDecode' % (mids * fan, len(first)),
                          zlib.compress(first + b''.join(body)))}
    for m in range(mids):
        kids = b' '.join(b'%d 0 R' % (leaf0 + m * fan + k) for k in range(fan))
        objs[4 + m] = b'<< /Type /Pages /Parent 2 0 R /Kids [' + kids + b'] /Count %d >>' % fan
    out, entries = b'%PDF-1.5\n', {0: b'\x00' * 5 + _be(65535)}
    for num in sorted(objs):
        entries[num] = b'\x01' + _be(len(out)) + _be(0)
        out += b'%d 0 obj\n' % num + objs[num] + b'\nendobj\n'
    for i, num in enumerate(leaves):
        entries[num] = b'\x02' + _be(ostm) + _be(i)
    entries[xstm] = b'\x01' + _be(len(out)) + _be(0)
    table = zlib.compress(b''.join(entries[k] for k in range(xstm + 1)))
    xref = len(out)
    out += b'%d 0 obj\n' % xstm + _stream(b'<< /Type /XRef /Size %d /W [1 4 4] /Root 1 0 R /Filter /FlateDecode'
                                          % (xstm + 1), table) + b'\nendobj\n'
    return out + b'startxref\n%d\n%%%%EOF' % xref


def _many_objects(n):
    """One page: ``n`` - 1 painted rectangles (one pdfium path object each) and one line of drawn text."""
    return _doc(b'0 0 1 1 re f\n' * (n - 1) + _show(SPM_TEXT), filtered=True)


class TheHostileShapes(SimpleTestCase):
    """Each the Vision route (or kept) in under 3 seconds; none flattens or extracts what it must not."""
    _hostile = TheDocumentBudgets._hostile

    def test_99000_pages_in_one_object_stream_are_refused_before_pypdf_reads_them(self):
        # pypdf 6 parses a whole object stream on its first read (2.5 s here): refused on its /N, unread
        from pypdf import PdfReader
        self.assertEqual(len(PdfReader(io.BytesIO(_page_tree(6, mids=3, fan=2))).pages), 6)   # a valid file
        for count in (99_000, 1):                     # an honest count past the cap; a /Count that lies
            with self.subTest(count=count):
                data = _page_tree(count)
                with self.assertRaisesRegex(OverBudget, 'object streams'):
                    page_tree_check(PdfReader(io.BytesIO(data)))
                with patch.object(PdfReader, '_flatten', side_effect=AssertionError('flattened')):
                    self._hostile(data)

    def test_a_page_count_past_the_cap_or_a_lie_meets_the_node_cap(self):
        from pypdf import PdfReader
        pdf = _pdf([b''] * 1_200)
        lie = pdf.replace(b'/Count 1200', b'/Count 1')
        self.assertNotEqual(lie, pdf)
        for data, why in ((pdf, 'page count'), (lie, 'node cap')):
            with self.subTest(why=why):
                with self.assertRaisesRegex(OverBudget, why):
                    page_tree_check(PdfReader(io.BytesIO(data)))
                self._hostile(data)

    def test_a_page_tree_with_one_node_twice_is_no_layer(self):
        pdf = _doc(_show(SPM_TEXT)).replace(b'/Kids [4 0 R] /Count 1', b'/Kids [4 0 R 4 0 R] /Count 2')
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_350k_empty_form_calls(self):
        self._hostile(_pdf([b'/Fm1 Do ' * 350_000 + _show(SPM_TEXT)], form=b''))

    def test_each_form_call_costs_20_operations(self):
        # 24,000 calls: 24,000 operations + 20 x 24,000 = 504,000, past the 500,000 budget, never extracted
        self._hostile(_pdf([b'/Fm1 Do ' * 24_000 + _show(SPM_TEXT)], form=b''))

    def test_form_calls_at_the_budget_edge(self):
        # a form with no font (no font-map charge): 23,000 calls stay within the walk's operation budget
        # (483,000), pypdf extracts the page, and pdfium's object cap then hides it, all fast
        form = _stream(b'<< /Type /XObject /Subtype /Form /BBox [0 0 300 200] /Resources << /ProcSet [/PDF] >>', b'')
        data = _doc(b'/Fm1 Do ' * 23_000 + _show(SPM_TEXT), {6: form}, filtered=True,
                    page_res=b'/Resources << ' + FONT_RES + b' /XObject << /Fm1 6 0 R >> >>')
        pdf_pages._layer_memo_clear()
        with patch('apps.scholarship.pdf_pdfium_check.hidden_pages', return_value=set()):
            self.assertIn('SIJIL', pdf_pages.pdf_text_layer(data))         # the walk and pypdf: within budget
        pdf_pages._layer_memo_clear()
        # The time is pypdf's extraction of the 23,000 calls, by design (2-4 s with pypdf 6.21.4 on a busy dev
        # machine, so a 3 s limit was flaky, round 9): pdfium is pinned to ONE child for both readers; the time
        # limit only catches a gross regression.
        from apps.scholarship import pdfium_run
        t0 = time.perf_counter()
        with patch.object(pdfium_run, '_spawn', side_effect=pdfium_run._spawn) as spawned:
            self.assertEqual(pdf_pages.pdf_text_layer(data), '')
            self.assertEqual(''.join(pdf_pages.pdf_page_texts(data, 3)), '')
        self.assertLess(time.perf_counter() - t0, 8.0)
        self.assertEqual(spawned.call_count, 1)

    def test_pdfium_objects_at_the_cap_keep_the_layer_and_one_more_hides_it(self):
        from apps.scholarship.pdf_pdfium_check import MAX_OBJECTS
        for n, kept in ((MAX_OBJECTS, True), (MAX_OBJECTS + 1, False)):
            with self.subTest(n=n):
                pdf_pages._layer_memo_clear()
                t0 = time.perf_counter()
                self.assertEqual('SIJIL' in pdf_pages.pdf_text_layer(_many_objects(n)), kept)
                # about 1.8 s alone (a pdfium child); 6.4 s in a loaded full -n auto run (19 Nov), as round 9's 8 s limits.
                self.assertLess(time.perf_counter() - t0, 8.0)

    def test_one_call_opens_the_pdf_once(self):
        with patch('apps.scholarship.pdf_pages._open_pdf', wraps=pdf_pages._open_pdf) as opened:
            pdf_pages.pdf_page_texts(_pdf([_show(SECRET.decode(), mode=3), _show(SPM_TEXT)]), 3)
        self.assertEqual(opened.call_count, 1)


class PdfiumJudgesEachObject(SimpleTestCase):
    """pdfium's own page objects judge every page pypdf read, even when the walk is fooled (patched here)."""

    def _leaks_without_pdfium(self, pdf):
        with patch('apps.scholarship.pdf_pdfium_check.hidden_pages', return_value=set()):
            pdf_pages._layer_memo_clear()
            self.assertIn('DISAHKAN', pdf_pages.pdf_text_layer(pdf))      # the premise: the walk was fooled
        pdf_pages._layer_memo_clear()
        self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')
        self.assertFalse(pdf_pages.first_page_drawn(pdf))

    def test_an_invisible_mode_the_walk_missed(self):
        for mode in (3, 7):
            with self.subTest(mode=mode), patch.object(pdf_pages, '_DRAWN_MODES', frozenset(range(8))):
                self._leaks_without_pdfium(_doc(_show(SECRET.decode(), mode=mode) + b' ' + _show(SPM_TEXT)))

    def test_an_oc_marked_text_object_the_walk_let_through(self):
        for objs, default in (({}, b'<< /OFF [6 0 R] >>'), ({6: USAGE_OCG}, ALL_ON)):
            with self.subTest(default=default), patch.object(pdf_pages, 'oc_hides', return_value=False):
                self._leaks_without_pdfium(_oc_doc(MARKED, default, objs))

    def test_text_inside_an_oc_marked_form(self):
        form = _xobj(b'/Subtype /Form', _show(SECRET.decode()))
        pdf = _oc_doc(b'/OC /MC0 BDC /Fm1 Do EMC', b'<< /OFF [6 0 R] >>', {7: form},
                      b'/Properties << /MC0 6 0 R >> /XObject << /Fm1 7 0 R >>')
        with patch.object(pdf_pages, 'oc_hides', return_value=False):
            self._leaks_without_pdfium(pdf)

    def test_pypdf_text_where_pdfium_places_no_text_object(self):
        # a non-form XObject pypdf extracts and pdfium never draws; the walk patched to call it drawn
        pdf = _doc(b'/X1 Do', {6: _xobj(b'/Subtype /PS', _show(SECRET.decode()))},
                   page_res=b'/Resources << ' + FONT_RES + b' /XObject << /X1 6 0 R >> >>')
        with patch.object(pdf_pages, '_page_visibility', return_value=pdf_pages.DRAWN):
            self._leaks_without_pdfium(pdf)

    def test_what_hidden_pages_judges(self):
        from apps.scholarship.pdf_pdfium_check import hidden_pages
        from apps.scholarship.tests.test_ocr_visible import SCANNED
        self.assertEqual(hidden_pages(SCANNED, 1, {0: 'ABC'}, False), {0})       # letters, no text object
        self.assertEqual(hidden_pages(SCANNED, 1, {0: ' - '}, False), set())     # no letters: nothing placed
        self.assertEqual(hidden_pages(SCANNED, 1, {0: ' \n'}, False), set())     # blank: not judged
        self.assertEqual(hidden_pages(DRAWN, 1, {0: 'SIJIL'}, False), set())
        self.assertEqual(hidden_pages(DRAWN, 1, {0: 'SIJIL'}, True), set())      # no OC mark: nothing to switch
        self.assertEqual(hidden_pages(DRAWN, 2, {0: 'SIJIL'}, False), {0})       # another page count
        self.assertEqual(hidden_pages(b'%PDF-1.4 nonsense', 1, {0: 'SIJIL'}, False), {0})   # pdfium cannot open
        with patch('apps.scholarship.pdf_pdfium_check.MAX_OBJECTS', 0):
            self.assertEqual(hidden_pages(DRAWN, 1, {0: 'SIJIL'}, False), {0})   # past the object cap

    def test_a_plain_layer_that_is_on_keeps_the_layer_for_pdfium_too(self):
        pdf_pages._layer_memo_clear()
        self.assertIn('DISAHKAN', pdf_pages.pdf_text_layer(_oc_doc(MARKED, ALL_ON)))
