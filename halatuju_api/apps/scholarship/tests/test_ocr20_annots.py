"""OCR-20 (24 Nov): an annotation painted over the page text (the "sticker" gap).

pdfium draws an annotation ON TOP of the page; pypdf's text layer never reads it. A white box and the word FORGED
drawn over GENUINE by a /Square, /Stamp, /FreeText or /Link appearance stream left the text layer reading GENUINE
as an exact read. Owner rule (strict): a page's text is read only when every annotation it lists is a /Link with
no /AP (`pdf_annots`); pdfium checks the same rule on its own reading (`pdfium_worker._plain_link`).
Fictional words only.
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import pdf_annots, pdf_pages, pdf_rules_pages, pdfium_worker

FONT = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
STICKER = b'1 g 0 0 400 100 re f 0 g BT /F1 24 Tf 10 40 Td (FORGED) Tj ET'
FORM = b'<< /Type /XObject /Subtype /Form /BBox [0 0 400 100] /Resources << /Font << /F1 4 0 R >> >>'
RECT = b' /Rect [60 680 460 780] /F 4'
AP = b' /AP << /N 7 0 R >>'
LINK = b'<< /Type /Annot /Subtype /Link' + RECT + b' /Border [0 0 0] >>'
SQUARE = b'<< /Type /Annot /Subtype /Square' + RECT + AP + b' >>'


def _stream(head, data):
    return head + b' /Length %d >>\nstream\n' % len(data) + data + b'\nendstream'


def _pdf(annot=None, page_annots=b' /Annots [6 0 R]', pages_extra=b'', root_extra=b'', extra=(), page2=None,
         page1=b''):
    """Page 1 shows GENUINE and lists ``page_annots`` (object 6 = ``annot``; object 7 = the FORGED sticker form).
    ``page2``: a second page showing GENUINE2 that lists these /Annots instead (page 1 then lists ``page1``)."""
    out, off = bytearray(b'%PDF-1.4\n'), {}

    def obj(n, body):
        off[n] = len(out)
        out.extend(b'%d 0 obj\n' % n + body + b'\nendobj\n')

    listed = page_annots if annot is not None else b''
    kids = b'[3 0 R 8 0 R]' if page2 else b'[3 0 R]'
    obj(1, b'<< /Type /Catalog /Pages 2 0 R' + root_extra + b' >>')
    obj(2, b'<< /Type /Pages /Kids ' + kids + b' /Count %d' % (2 if page2 else 1) + pages_extra + b' >>')
    page = b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents '
    obj(3, page + b'5 0 R' + (page1 if page2 else listed) + b' >>')
    obj(4, FONT)
    obj(5, _stream(b'<<', b'BT /F1 24 Tf 72 700 Td (GENUINE) Tj ET'))
    obj(6, annot if annot is not None else b'null')
    obj(7, _stream(FORM, STICKER))
    bodies = [page + b'9 0 R' + listed + b' >>', _stream(b'<<', b'BT /F1 24 Tf 72 700 Td (GENUINE2) Tj ET')] \
        if page2 else []
    for n, body in enumerate(bodies + list(extra), start=8):
        obj(n, body)
    size = 8 + len(bodies) + len(extra)
    x = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % size + b''.join(b'%010d 00000 n \n' % off[k] for k in range(1, size))
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, x)
    return bytes(out)


def _raw(pdf):
    import io

    from pypdf import PdfReader
    return PdfReader(io.BytesIO(pdf)).pages[0].extract_text().strip()


def _layer(pdf):
    pdf_pages._layer_memo_clear()
    return pdf_pages.pdf_text_layer(pdf)


def _texts(pdf, n=1):
    pdf_pages._layer_memo_clear()
    return pdf_pages.pdf_page_texts(pdf, n)


HOSTILE = {
    'square_with_ap': dict(annot=SQUARE),
    'stamp_with_ap': dict(annot=b'<< /Type /Annot /Subtype /Stamp' + RECT + AP + b' >>'),
    'freetext_with_ap': dict(annot=b'<< /Type /Annot /Subtype /FreeText' + RECT + AP + b' /DA (/F1 24 Tf 0 g) >>'),
    'freetext_no_ap': dict(annot=b'<< /Type /Annot /Subtype /FreeText' + RECT + b' /DA (/Helv 24 Tf 0 g)'
                                 b' /Contents (FORGED) /IC [1 1 1] >>'),
    # pdfium makes this one's appearance itself: a white filled box over GENUINE (probe, 24 Nov)
    'square_no_ap_white_fill': dict(annot=b'<< /Type /Annot /Subtype /Square' + RECT + b' /IC [1 1 1] /C [1 1 1] >>'),
    'widget_with_ap': dict(annot=b'<< /Type /Annot /Subtype /Widget /FT /Tx /T (a)' + RECT + AP + b' >>'),
    'widget_need_appearances': dict(
        annot=b'<< /Type /Annot /Subtype /Widget /FT /Tx /T (a) /V (FORGED) /DA (/Helv 24 Tf 0 g)' + RECT + b' >>',
        root_extra=b' /AcroForm << /Fields [6 0 R] /NeedAppearances true /DA (/Helv 24 Tf 0 g) >>'),
    'link_with_ap': dict(annot=b'<< /Type /Annot /Subtype /Link' + RECT + AP + b' >>'),
    'link_with_null_ap': dict(annot=b'<< /Type /Annot /Subtype /Link' + RECT + b' /AP null >>'),
    'popup_with_ap': dict(annot=b'<< /Type /Annot /Subtype /Popup /Open true' + RECT + AP + b' >>'),
    'text_note_no_ap': dict(annot=b'<< /Type /Annot /Subtype /Text' + RECT + b' >>'),
    'no_subtype': dict(annot=b'<< /Type /Annot' + RECT + AP + b' >>'),
    'no_subtype_no_ap': dict(annot=b'<< /Type /Annot' + RECT + b' >>'),
    'subtype_a_string': dict(annot=b'<< /Type /Annot /Subtype (Link)' + RECT + b' >>'),
    'indirect_annots_array': dict(annot=SQUARE, page_annots=b' /Annots 8 0 R', extra=(b'[6 0 R]',)),
    'direct_dict_in_the_array': dict(annot=b'null', page_annots=b' /Annots [' + SQUARE + b']'),
    'a_null_entry': dict(annot=b'null'),
    'a_link_then_a_square': dict(annot=LINK, page_annots=b' /Annots [6 0 R ' + SQUARE + b']'),
    'annots_on_the_parent': dict(annot=SQUARE, page_annots=b'', pages_extra=b' /Annots [6 0 R]'),
    'annots_not_an_array': dict(annot=SQUARE, page_annots=b' /Annots 6 0 R'),
    'hidden_flag': dict(annot=b'<< /Type /Annot /Subtype /Square /Rect [60 680 460 780] /F 2' + AP + b' >>'),
    'optional_content_off': dict(annot=b'<< /Type /Annot /Subtype /Square' + RECT + AP + b' /OC 8 0 R >>',
                                 root_extra=b' /OCProperties << /OCGs [8 0 R] /D << /OFF [8 0 R] >> >>',
                                 extra=(b'<< /Type /OCG /Name (x) >>',)),
}


class EveryAnnotationButAPlainLinkHidesThePage(SimpleTestCase):
    def test_each_kind_is_read_by_pypdf_but_refused(self):
        for name, kw in HOSTILE.items():
            with self.subTest(name):
                pdf = _pdf(**kw)
                self.assertEqual(_raw(pdf), 'GENUINE')          # the hole: the raw layer still reads GENUINE
                self.assertEqual(_layer(pdf), '')
                self.assertEqual(_texts(pdf), [''])
                pdf_pages._layer_memo_clear()
                self.assertFalse(pdf_pages.first_page_drawn(pdf))

    def test_the_rules_lane_gets_no_page_text_and_no_layout(self):
        for name in ('square_with_ap', 'link_with_ap', 'freetext_no_ap'):
            with self.subTest(name):
                pdf = _pdf(**HOSTILE[name])
                pdf_pages._layer_memo_clear()
                self.assertEqual(pdf_rules_pages.pdf_rules_page_texts(pdf, 3), [''])
                pdf_pages._layer_memo_clear()
                self.assertEqual(pdf_rules_pages.pdf_page1_layout(pdf), '')

    def test_a_sticker_on_page_2_hides_page_2_only(self):
        pdf = _pdf(SQUARE, page2=True)
        self.assertEqual(_texts(pdf, 2), ['GENUINE', ''])

    def test_pdfium_alone_hides_it_when_the_pypdf_check_is_bypassed(self):
        for name in ('square_with_ap', 'link_with_ap', 'stamp_with_ap', 'text_note_no_ap'):
            with self.subTest(name), patch.object(pdf_pages, 'annots_hide', return_value=False):
                self.assertEqual(_layer(_pdf(**HOSTILE[name])), '')


class APlainLinkOrNoAnnotationKeepsTheLayer(SimpleTestCase):
    def test_controls(self):
        cases = {
            'no_annots': dict(),
            'link_no_ap': dict(annot=LINK),
            'link_no_ap_white_border': dict(annot=b'<< /Type /Annot /Subtype /Link' + RECT
                                            + b' /Border [0 0 40] /C [1 1 1] >>'),
            'annots_null': dict(annot=LINK, page_annots=b' /Annots null'),
            'annots_empty': dict(annot=LINK, page_annots=b' /Annots []'),
            'indirect_array_of_links': dict(annot=LINK, page_annots=b' /Annots 8 0 R', extra=(b'[6 0 R 6 0 R]',)),
        }
        for name, kw in cases.items():
            with self.subTest(name):
                pdf = _pdf(**kw)
                self.assertEqual(_layer(pdf), 'GENUINE')
                self.assertEqual(_texts(pdf), ['GENUINE'])

    def test_pdfium_agrees_on_a_plain_link_and_refuses_one_with_an_appearance(self):
        import pypdfium2 as pdfium
        for annot, plain in ((LINK, True), (HOSTILE['link_with_ap']['annot'], False), (SQUARE, False)):
            with self.subTest(plain=plain):
                doc = pdfium.PdfDocument(_pdf(annot))
                page = doc[0]
                try:
                    self.assertIs(pdfium_worker._plain_link(page.raw, 0), plain)
                finally:
                    page.close()
                    doc.close()


class TheAnnotationReadIsCharged(SimpleTestCase):
    def test_too_many_annotations_is_over_budget_before_any_is_read(self):
        many = b' /Annots [' + b'6 0 R ' * (pdf_annots.MAX_DOC_ANNOTS + 1) + b']'
        pdf = _pdf(LINK, page_annots=many)
        reader = pdf_pages._open_pdf(pdf)
        with patch.object(pdf_annots, '_plain_link', side_effect=AssertionError('read')) as read:
            self.assertEqual(pdf_pages._visibilities(reader), (pdf_pages.OVER_BUDGET,))
        read.assert_not_called()
        self.assertEqual(_layer(pdf), '')

    def test_the_budget_is_one_per_document(self):
        half = b' /Annots [' + b'6 0 R ' * (pdf_annots.MAX_DOC_ANNOTS // 2 + 1) + b']'
        self.assertEqual(_texts(_pdf(LINK, page_annots=half, page2=True), 2), ['GENUINE', 'GENUINE2'])   # one page: in
        pdf = _pdf(LINK, page_annots=half, page2=True, page1=half)                                    # both: past it
        self.assertEqual(pdf_pages._visibilities(pdf_pages._open_pdf(pdf)), (pdf_pages.DRAWN, pdf_pages.OVER_BUDGET))
        self.assertEqual(_texts(pdf, 2), ['', ''])

    def test_a_long_parent_chain_hides(self):
        from pypdf.generic import DictionaryObject, NameObject
        node = DictionaryObject()
        for _ in range(pdf_annots._MAX_PARENT_DEPTH + 1):
            node = DictionaryObject({NameObject('/Parent'): node})
        self.assertTrue(pdf_annots.annots_hide(node, pdf_pages._Budget()))
        short = DictionaryObject({NameObject('/Parent'): DictionaryObject()})
        self.assertFalse(pdf_annots.annots_hide(short, pdf_pages._Budget()))
