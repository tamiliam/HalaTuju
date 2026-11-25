"""TD-740 (25 Nov): text the exact read uses must sit on the page pdfium draws.

Text placed far off the page by a plain ``cm`` or ``Td`` (probe p7: 5000 5000) was read by pypdf, never drawn by
pdfium, and page 1 still counted as drawn; the SPM ``words`` op returned it too. pdfium now judges where it places
every text object (`pdfium_place.outside`): a text object whose box (in page space, through every form's matrix)
reaches past the visible page box (CropBox, else MediaBox, as pdfium draws) by more than `pdfium_place.EDGE_PT`,
or whose centre is off it, hides its page (the Vision route), and the words op gives no words. Fictional words only,
crafted PDFs only.
"""
from django.test import SimpleTestCase

from apps.scholarship import pdf_pages, pdfium_place
from apps.scholarship.tests.test_ocr20_dup_keys import _words

FONT = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
G = b'BT /F1 24 Tf 72 700 Td (GENUINE) Tj ET\n'
PAGE_TWO = b'BT /F1 12 Tf 72 700 Td (PAGE TWO ORDINARY WORDS) Tj ET'
MEDIA = b'/MediaBox [0 0 595 842]'


def _stream(data: bytes, head=b'<<') -> bytes:
    return head + b' /Length %d >>\nstream\n' % len(data) + data + b'\nendstream'


def _form(matrix: bytes, body: bytes, inner=b'') -> bytes:
    return _stream(body, b'<< /Type /XObject /Subtype /Form /BBox [-10000 -10000 10000 10000] /Matrix [' + matrix
                   + b'] /Resources << /Font << /F1 4 0 R >>' + inner + b' >>')


def _pdf(page1: bytes, box=MEDIA, extra=(), page2: bytes = PAGE_TWO, box2=MEDIA) -> bytes:
    """Two pages: page 1 draws object 5 (content ``page1``) in ``box``; page 2 (6, 7) draws ``page2``. ``extra``:
    form XObjects 8, 9, ... (page 1 names them /X1, /X2, ...)."""
    xobj = b''.join(b'/X%d %d 0 R ' % (k, 8 + k - 1) for k in range(1, len(extra) + 1))
    res = b'<< /Font << /F1 4 0 R >>' + (b' /XObject << ' + xobj + b'>>' if extra else b'') + b' >>'
    bodies = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>',
              b'<< /Type /Page /Parent 2 0 R ' + box + b' /Resources ' + res + b' /Contents 5 0 R >>', FONT,
              _stream(page1),
              b'<< /Type /Page /Parent 2 0 R ' + box2 + b' /Resources ' + res + b' /Contents 7 0 R >>',
              _stream(page2), *extra]
    out, off = bytearray(b'%PDF-1.4\n'), []
    for n, body in enumerate(bodies, 1):
        off.append(len(out))
        out += b'%d 0 obj\n' % n + body + b'\nendobj\n'
    x, size = len(out), len(bodies) + 1
    out += b'xref\n0 %d\n0000000000 65535 f \n' % size + b''.join(b'%010d 00000 n \n' % o for o in off)
    return bytes(out + b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, x))


def _texts(pdf: bytes) -> list:
    pdf_pages._layer_memo_clear()
    return [' '.join(t.split()) for t in pdf_pages.pdf_page_texts(pdf, 2)]


def _page1_lost(pdf: bytes) -> bool:
    """Page 1 lost its exact read everywhere: not drawn, no text layer, no page-1 text, no SPM words. Page 2's
    ordinary text still reads (the page is hidden, not the file)."""
    pdf_pages._layer_memo_clear()
    drawn = pdf_pages.first_page_drawn(pdf)
    pdf_pages._layer_memo_clear()
    layer = pdf_pages.pdf_text_layer(pdf)
    return (not drawn and layer == '' and _texts(pdf) == ['', 'PAGE TWO ORDINARY WORDS'] and _words(pdf) == [])


def _reads(pdf: bytes, page1: str) -> bool:
    pdf_pages._layer_memo_clear()
    return pdf_pages.first_page_drawn(pdf) and _texts(pdf) == [page1, 'PAGE TWO ORDINARY WORDS']


class TextPlacedOffThePageHidesThePage(SimpleTestCase):
    def test_probe_p7_a_plain_cm_and_a_plain_td(self):
        for name, body in (('cm', G + b'q 1 0 0 1 5000 5000 cm BT /F1 24 Tf 72 600 Td (LULUS) Tj ET Q'),
                           ('Td', G + b'BT /F1 24 Tf 5000 5000 Td (LULUS) Tj ET'),
                           ('Tm', G + b'BT /F1 24 Tf 1 0 0 1 -3000 600 Tm (LULUS) Tj ET'),
                           ('below', G + b'BT /F1 24 Tf 72 -400 Td (LULUS) Tj ET')):
            with self.subTest(name):
                self.assertTrue(_page1_lost(_pdf(body)))

    def test_partly_off_the_page(self):
        """'LULUS' at x 560 runs about 40 pt past the right edge of a 595 pt page: pdfium draws only 'LU'."""
        for name, body in (('right', b'BT /F1 24 Tf 560 600 Td (LULUS) Tj ET'),
                           ('top', b'BT /F1 24 Tf 72 832 Td (LULUS) Tj ET'),
                           ('left', b'BT /F1 24 Tf -30 600 Td (LULUS) Tj ET')):
            with self.subTest(name):
                self.assertTrue(_page1_lost(_pdf(G + body)))

    def test_text_outside_the_cropbox_but_inside_the_mediabox(self):
        """pdfium draws the CropBox (within the MediaBox): text at y 100 under a CropBox from y 400 is not drawn."""
        crop = MEDIA + b' /CropBox [0 400 595 842]'
        self.assertTrue(_page1_lost(_pdf(G + b'BT /F1 24 Tf 72 100 Td (LULUS) Tj ET', crop)))
        self.assertTrue(_reads(_pdf(G + b'BT /F1 24 Tf 72 600 Td (LULUS) Tj ET', crop), 'GENUINE LULUS'))

    def test_a_sliver_wholly_off_the_page_within_the_tolerance(self):
        """A 2 pt 'I' just left of the page reaches past by less than `EDGE_PT`, but its centre is off the page."""
        self.assertTrue(_page1_lost(_pdf(G + b'BT /F1 2 Tf -1.5 600 Td (I) Tj ET')))

    def test_a_cropbox_larger_than_the_mediabox_is_cut_to_it(self):
        crop = MEDIA + b' /CropBox [0 0 2000 2000]'
        self.assertTrue(_page1_lost(_pdf(G + b'BT /F1 24 Tf 1000 600 Td (LULUS) Tj ET', crop)))

    def test_a_form_whose_matrix_moves_its_text_off_the_page(self):
        for name, matrix in ((b'shift', b'1 0 0 1 5000 5000'), (b'scale', b'40 0 0 40 0 0')):
            with self.subTest(name):
                pdf = _pdf(G + b'/X1 Do', extra=[_form(matrix, b'BT /F1 24 Tf 72 600 Td (LULUS) Tj ET')])
                self.assertTrue(_page1_lost(pdf))

    def test_a_nested_form_off_the_page(self):
        """The outer form calls the inner one through its own resources; each matrix places the inner text."""
        inner = _form(b'1 0 0 1 0 3000', b'BT /F1 24 Tf 72 600 Td (LULUS) Tj ET')
        outer = _form(b'1 0 0 1 0 0', b'q 1 0 0 1 10 10 cm /Y1 Do Q', b' /XObject << /Y1 9 0 R >>')
        self.assertTrue(_page1_lost(_pdf(G + b'/X1 Do', extra=[outer, inner])))
        with self.subTest('both_matrices_count'):     # each matrix alone puts it off the page; together, on it
            inner = _form(b'1 0 0 1 0 3000', b'BT /F1 24 Tf 72 600 Td (LULUS) Tj ET')
            outer = _form(b'1 0 0 1 0 -3000', b'/Y1 Do', b' /XObject << /Y1 9 0 R >>')
            self.assertTrue(_reads(_pdf(G + b'/X1 Do', extra=[outer, inner]), 'GENUINE LULUS'))
            outer = _form(b'1 0 0 1 0 3000', b'/Y1 Do', b' /XObject << /Y1 9 0 R >>')
            self.assertTrue(_page1_lost(_pdf(G + b'/X1 Do', extra=[outer, inner])))

    def test_off_page_text_on_page_2_hides_page_2_only(self):
        pdf = _pdf(G, page2=PAGE_TWO + b' BT /F1 24 Tf 5000 5000 Td (LULUS) Tj ET')
        pdf_pages._layer_memo_clear()
        self.assertTrue(pdf_pages.first_page_drawn(pdf))
        self.assertEqual(_texts(pdf), ['GENUINE', ''])
        pdf_pages._layer_memo_clear()
        self.assertEqual(' '.join(pdf_pages.pdf_text_layer(pdf).split()), 'GENUINE')

    def test_the_rotated_page_judges_in_page_space(self):
        """/Rotate turns the picture, not the page space: the box is still the MediaBox, read before the turn."""
        rot = MEDIA + b' /Rotate 90'
        self.assertTrue(_page1_lost(_pdf(G + b'BT /F1 24 Tf 72 5000 Td (LULUS) Tj ET', rot)))
        self.assertTrue(_reads(_pdf(G + b'BT /F1 24 Tf 72 600 Td (LULUS) Tj ET', rot), 'GENUINE LULUS'))


class TextOnThePageStillReads(SimpleTestCase):
    def test_ordinary_text(self):
        self.assertTrue(_reads(_pdf(G + b'BT /F1 24 Tf 72 600 Td (LULUS) Tj ET'), 'GENUINE LULUS'))
        self.assertEqual(_words(_pdf(G + b'BT /F1 24 Tf 72 600 Td (LULUS) Tj ET')), ['GENUINE', 'LULUS'])

    def test_text_moved_onto_the_page_by_a_cm_or_a_form_matrix(self):
        """Large numbers are not the test: where pdfium PLACES the text is."""
        with self.subTest('cm'):
            self.assertTrue(_reads(_pdf(G + b'q 1 0 0 1 -5000 -5000 cm BT /F1 24 Tf 5072 5600 Td (LULUS) Tj ET Q'),
                                   'GENUINE LULUS'))
        with self.subTest('form'):
            pdf = _pdf(G + b'q 1 0 0 1 -5000 -5000 cm /X1 Do Q',
                       extra=[_form(b'1 0 0 1 0 0', b'BT /F1 24 Tf 5072 5600 Td (LULUS) Tj ET')])
            self.assertTrue(_reads(pdf, 'GENUINE LULUS'))
        with self.subTest('form_matrix'):
            pdf = _pdf(G + b'/X1 Do', extra=[_form(b'1 0 0 1 -5000 -5000', b'BT /F1 24 Tf 5072 5600 Td (LULUS) Tj ET')])
            self.assertTrue(_reads(pdf, 'GENUINE LULUS'))

    def test_text_near_the_edge_within_the_tolerance(self):
        """A glyph box may reach a hair past the edge (side bearings): within `EDGE_PT` it still reads."""
        self.assertGreater(pdfium_place.EDGE_PT, 0)
        self.assertTrue(_reads(_pdf(G + b'BT /F1 24 Tf 0 0 Td (LULUS) Tj ET'), 'GENUINE LULUS'))

    def test_a_page_box_not_at_the_origin(self):
        box = b'/MediaBox [-300 -300 295 542]'
        self.assertTrue(_reads(_pdf(b'BT /F1 24 Tf -200 400 Td (GENUINE) Tj ET', box), 'GENUINE'))
        self.assertTrue(_page1_lost(_pdf(b'BT /F1 24 Tf -200 400 Td (GENUINE) Tj ET'
                                         b' BT /F1 24 Tf 400 400 Td (LULUS) Tj ET', box)))


class TheWorkerRule(SimpleTestCase):
    def test_outside_by_box(self):
        area = (0.0, 0.0, 595.0, 842.0)
        self.assertFalse(pdfium_place.outside((10, 10, 100, 30), area))
        self.assertFalse(pdfium_place.outside((-pdfium_place.EDGE_PT, 0, 595 + pdfium_place.EDGE_PT, 842), area))
        self.assertTrue(pdfium_place.outside((-pdfium_place.EDGE_PT - 0.01, 0, 10, 10), area))
        self.assertTrue(pdfium_place.outside((5000, 5000, 5050, 5020), area))
        self.assertFalse(pdfium_place.outside((300, 400, 596.9, 420), area))     # the genuine template's 1.9 pt
        self.assertTrue(pdfium_place.outside((-2, 400, -0.5, 402), area))        # within EDGE_PT, centre off
        self.assertFalse(pdfium_place.outside((0, 0, 0, 0), area))               # a zero-size box on the corner
        self.assertTrue(pdfium_place.outside((float('nan'),) * 4, area))

    def test_box_through_a_matrix(self):
        box = pdfium_place.through((0, 0, 10, 20), (0, 1, -1, 0, 100, 0))    # turned 90 degrees, then moved
        self.assertEqual(tuple(round(v, 6) for v in box), (80.0, 0.0, 100.0, 10.0))
