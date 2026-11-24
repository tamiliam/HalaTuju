"""OCR-20 review round 1 (25 Nov): a key named twice, a page pypdf reads as blank, and the SPM ``words`` op.

pypdf keeps the FIRST value of a repeated dictionary key, pdfium the LAST. Page 1 naming /Contents and /Annots twice
read as blank with one plain /Link to the gate, while pdfium drew GENUINE under a /Square sticker painting FORGED
(e1, d2), or GENUINE in render mode 3 (e2). pdfium's second check skipped pages pypdf read as blank, so
`first_page_drawn` was True and the SPM certificate reader read ['GENUINE'] from pdfium's ``words`` op. Three fixes,
each tested on its own here: the gate refuses the FILE on a repeated key (`pdf_dict_keys`); pdfium judges every
judged page, a blank one too (`pdf_pdfium_check` rule f); the ``words`` op refuses a page that does not paint in
full (`pdfium_worker._op_words`). Fictional words only.
"""
import io
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import pdf_pages, pdfium_run

FONT = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
STICKER = b'1 g 0 0 400 100 re f 0 g BT /F1 24 Tf 10 40 Td (FORGED) Tj ET'
FORM = b'<< /Type /XObject /Subtype /Form /BBox [0 0 400 100] /Resources << /Font << /F1 4 0 R >> >>'
RECT = b' /Rect [60 680 460 780]'
GENUINE = b'BT /F1 24 Tf 72 700 Td (GENUINE) Tj ET'
PAGE_TWO = 'PAGE TWO ORDINARY TEXT LAYER WORDS'


def _head(resources=b''):
    return (b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >>'
            + resources + b' >>')


def _stream(head, data):
    return head + b' /Length %d >>\nstream\n' % len(data) + data + b'\nendstream'


def _doc(page1=b' /Contents 5 0 R', content=GENUINE, *, sticker=STICKER, resources=b'', catalog=b'', trailer=b''):
    """Two pages. Page 1 is ``_head(resources) + page1``; object 5 holds ``content``, 6 a plain /Link, 7 the
    ``sticker`` form, 8 a /Square sticker with an /AP, 9 a blank stream, 12 an optional-content group; page 2
    (10, 11) an ordinary text layer."""
    out, off = bytearray(b'%PDF-1.4\n'), {}

    def obj(n, body):
        off[n] = len(out)
        out.extend(b'%d 0 obj\n' % n + body + b'\nendobj\n')

    obj(1, b'<< /Type /Catalog /Pages 2 0 R' + catalog + b' >>')
    obj(2, b'<< /Type /Pages /Kids [3 0 R 10 0 R] /Count 2 >>')
    obj(3, _head(resources) + page1 + b' >>')
    obj(4, FONT)
    obj(5, _stream(b'<<', content))
    obj(6, b'<< /Type /Annot /Subtype /Link' + RECT + b' /Border [0 0 0] >>')
    obj(7, _stream(FORM, sticker))
    obj(8, b'<< /Type /Annot /Subtype /Square' + RECT + b' /F 4 /AP << /N 7 0 R >> >>')
    obj(9, _stream(b'<<', b'q Q'))
    obj(10, _head() + b' /Contents 11 0 R >>')
    obj(11, _stream(b'<<', b'BT /F1 12 Tf 72 700 Td (' + PAGE_TWO.encode() + b') Tj ET'))
    obj(12, b'<< /Type /OCG /Name (Layer) >>')
    x = len(out)
    out += b'xref\n0 13\n0000000000 65535 f \n' + b''.join(b'%010d 00000 n \n' % off[k] for k in range(1, 13))
    out += b'trailer\n<< /Size 13 /Root 1 0 R' + trailer + b' >>\nstartxref\n%d\n%%%%EOF\n' % x
    return bytes(out)


#: The review's probes. e1 (= d2): pypdf reads a blank page with one plain /Link, pdfium GENUINE under a FORGED
#: /Square sticker. e2: only /Contents named twice, pdfium's GENUINE in render mode 3. d3: only /Contents named
#: twice, pdfium's GENUINE plainly drawn — the two engines still read different pages, so it is refused too.
PROBES = {
    'e1_d2_sticker': _doc(b' /Contents 9 0 R /Annots [6 0 R] /Contents 5 0 R /Annots [8 0 R]'),
    'e2_invisible': _doc(b' /Contents 9 0 R /Contents 5 0 R', b'BT 3 Tr /F1 24 Tf 72 700 Td (GENUINE) Tj ET'),
    'd3_contents_only': _doc(b' /Contents 9 0 R /Contents 5 0 R'),
}
OFF = b' /OCProperties << /OCGs [12 0 R] /D << /OFF [12 0 R] >> >>'


def _drawn(pdf):
    pdf_pages._layer_memo_clear()
    return pdf_pages.first_page_drawn(pdf)


def _texts(pdf, n=2):
    pdf_pages._layer_memo_clear()
    return pdf_pages.pdf_page_texts(pdf, n)


def _words(pdf):
    answer = pdfium_run.ask(pdf, [{'op': 'words'}])
    return [w['text'] for w in answer[0]['words']] if answer else None


class AKeyNamedTwiceRefusesTheFile(SimpleTestCase):
    def test_the_probes_lose_page_1_and_the_whole_file(self):
        for name, pdf in PROBES.items():
            with self.subTest(name):
                self.assertFalse(_drawn(pdf))
                self.assertFalse(any(_texts(pdf)))        # the file is refused: page 2's ordinary layer too
                pdf_pages._layer_memo_clear()
                self.assertEqual(pdf_pages.pdf_text_layer(pdf), '')

    def test_the_gate_reader_refuses_and_a_plain_pypdf_reader_does_not(self):
        from pypdf import PdfReader

        from apps.scholarship import pdf_dict_keys
        from apps.scholarship.pdf_layer_guards import OverBudget
        pdf = PROBES['e1_d2_sticker']
        with self.assertRaisesRegex(OverBudget, 'a key named twice'):
            pdf_pages._open_pdf(pdf)
        self.assertEqual(PdfReader(io.BytesIO(pdf)).pages[0].extract_text().strip(), '')  # pypdf: the FIRST /Contents
        self.assertEqual(pdf_dict_keys.DUPLICATE_KEY_WARNING, 'Multiple definitions in dictionary')

    def test_anywhere_in_the_file_and_identical_values_too(self):
        cases = {
            'trailer': _doc(trailer=b' /Size 13'),
            'catalog': _doc(catalog=b' /Pages 2 0 R'),
            'nested_font_map': _doc().replace(b'/F1 4 0 R >> >> /Contents 5', b'/F1 4 0 R /F1 4 0 R >> >> /Contents 5'),
            'font': _doc().replace(b'/BaseFont /Helvetica >>', b'/BaseFont /Helvetica /BaseFont /Courier >>'),
            'page_2': _doc().replace(b'/Contents 11 0 R >>', b'/Contents 11 0 R /Contents 11 0 R >>'),
            'annotation': _doc(b' /Contents 5 0 R /Annots [6 0 R]').replace(b'/Border [0 0 0] >>',
                                                                            b'/Border [0 0 0] /Border [0 0 0] >>'),
        }
        for name, pdf in cases.items():
            with self.subTest(name):
                self.assertFalse(any(_texts(pdf)))

    def test_controls_keep_their_layer(self):
        self.assertTrue(_drawn(_doc()))
        self.assertEqual(_texts(_doc()), ['GENUINE', PAGE_TWO])
        self.assertEqual(_texts(_doc(b' /Contents 5 0 R /Annots [6 0 R]')), ['GENUINE', PAGE_TWO])

    def test_a_non_gate_parse_only_warns_and_the_hook_does_not_leak(self):
        from pypdf.generic import DictionaryObject
        parsed = DictionaryObject.read_from_stream(io.BytesIO(b'<< /A 1 /A 2 >>'), None)
        self.assertEqual(parsed['/A'], 1)                  # pypdf's own answer, unchanged
        self.assertFalse(any(_texts(PROBES['e1_d2_sticker'])))
        self.assertEqual(_texts(_doc()), ['GENUINE', PAGE_TWO])   # a refusal never sticks to the next file

    def test_a_refusal_pypdf_swallows_still_refuses(self):
        from apps.scholarship import pdf_pdfium_check
        from apps.scholarship.pdf_layer_guards import OverBudget

        def swallowed(data, n, judged, oc_off, reader):
            try:
                reader._counted._refuse('a refusal a lenient pypdf path caught')
            except OverBudget:
                pass
            return set()
        with patch.object(pdf_pdfium_check, 'hidden_pages', side_effect=swallowed):
            self.assertFalse(_drawn(_doc()))
            self.assertFalse(any(_texts(_doc())))


class PdfiumJudgesABlankPageToo(SimpleTestCase):
    """Fix 2 on its own: the repeated-key refusal is switched off (its warning text never matches)."""

    def test_the_probes_are_hidden_by_pdfium(self):
        from apps.scholarship import pdf_dict_keys
        for name, pdf in PROBES.items():
            with self.subTest(name), patch.object(pdf_dict_keys, 'DUPLICATE_KEY_WARNING', '\x00never'):
                self.assertFalse(_drawn(pdf))
                self.assertEqual(_texts(pdf), ['', PAGE_TWO])

    def test_a_blank_page_where_pdfium_finds_text_is_hidden(self):
        from apps.scholarship import pdf_pdfium_check
        for name, pdf in PROBES.items():
            with self.subTest(name):
                self.assertEqual(pdf_pdfium_check.hidden_pages(pdf, 2, {0: '', 1: PAGE_TWO}, False), {0})

    def test_controls(self):
        from apps.scholarship import pdf_pdfium_check
        blank = _doc(b' /Contents 9 0 R /Annots [6 0 R]')       # a blank page with a plain /Link: nothing hidden
        self.assertEqual(pdf_pdfium_check.hidden_pages(blank, 2, {0: '', 1: PAGE_TWO}, False), set())
        self.assertTrue(_drawn(blank))
        self.assertEqual(pdf_pdfium_check.hidden_pages(_doc(), 2, {0: 'GENUINE', 1: PAGE_TWO}, False), set())


class TheWordsOpChecksItsOwnPage(SimpleTestCase):
    """Fix 3 on its own: the SPM certificate reader's pdfium ``words`` op, asked directly."""

    def test_the_probes_give_no_words(self):
        for name, pdf in PROBES.items():
            if name != 'd3_contents_only':                 # pdfium alone cannot see d3's disagreement
                with self.subTest(name):
                    self.assertEqual(_words(pdf), [])

    def test_hidden_text_and_stickers_give_no_words(self):
        form = b' /XObject << /X1 7 0 R >>'
        cases = {
            'mode_7': _doc(content=b'BT 7 Tr /F1 24 Tf 72 700 Td (GENUINE) Tj ET'),
            'sticker_only': _doc(b' /Contents 5 0 R /Annots [8 0 R]'),
            'oc_off': _doc(content=b'/OC /L1 BDC ' + GENUINE + b' EMC',
                           resources=b' /Properties << /L1 12 0 R >>', catalog=OFF),
            'oc_marked_on': _doc(content=b'/OC /L1 BDC ' + GENUINE + b' EMC',
                                 resources=b' /Properties << /L1 12 0 R >>'),
            'form_mode_3': _doc(content=GENUINE + b' /X1 Do', resources=form,
                                sticker=STICKER.replace(b'(FORGED)', b'3 Tr (FORGED)')),
        }
        for name, pdf in cases.items():
            with self.subTest(name):
                self.assertEqual(_words(pdf), [])

    def test_controls_keep_their_words(self):
        self.assertEqual(_words(_doc()), ['GENUINE'])
        self.assertEqual(_words(_doc(b' /Contents 5 0 R /Annots [6 0 R]')), ['GENUINE'])
        self.assertEqual(_words(_doc(content=GENUINE + b' /X1 Do', resources=b' /XObject << /X1 7 0 R >>')),
                         ['GENUINE', 'FORGED'])
