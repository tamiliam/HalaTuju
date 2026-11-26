"""OCR-20 review round 3 part 2 (25 Nov): stream bounds, word ends in arrays, /ActualText in the SPM words op.

H4: a wrong /Length with 'endobj' in the data: pypdf searched on to 'endstream', pdfium stopped at the first of
'endstream' / 'endobj' (probes p2d, p2e: the gate read GENUINE LULUS, pdfium drew GENUINE). A stream must now end
exactly where /Length says (`pdf_dict_keys._stream_end`), or the FILE is refused. H5: pypdf's 'null' shortcut in an
array skipped the word check ('[5 0 R nulltrue 6 0 R]', probe p2l). H6: pdfium's text page (the SPM words op) gives
a marked-content /ActualText, not the glyphs drawn (probes p4a, p4b: drawn 'D', words 'A+'). Fictional words only.
"""
from django.test import SimpleTestCase

from apps.scholarship import pdf_pages
from apps.scholarship.tests.test_ocr20_dup_keys import _words

FONT = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
G = b'BT /F1 24 Tf 72 700 Td (GENUINE) Tj ET\n'
L = b'BT /F1 24 Tf 72 600 Td (LULUS) Tj ET\n'
PAGE_TWO = b'BT /F1 12 Tf 72 700 Td (PAGE TWO ORDINARY WORDS) Tj ET'


def _stream(data: bytes, length=None, head=b'<<', tail=b'\nendstream') -> bytes:
    length = b'%d' % len(data) if length is None else length
    return head + b' /Length ' + length + b' >>\nstream\n' + data + tail


def _pdf(obj5: bytes, contents=b'5 0 R', resources=b'', extra=()) -> bytes:
    """Two pages: page 1 draws object 5 (raw body ``obj5``), page 2 (6, 7) an ordinary text layer; ``extra``
    bodies are objects 8, 9, ..."""
    res = b'<< /Font << /F1 4 0 R >>' + resources + b' >>'
    bodies = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>',
              b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources ' + res + b' /Contents ' + contents
              + b' >>', FONT, obj5,
              b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources ' + res + b' /Contents 7 0 R >>',
              _stream(PAGE_TWO), *extra]
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


def _refused(pdf: bytes) -> bool:
    """The whole file lost its exact read: page 1 not drawn, and no page text at all (page 2's ordinary one too)."""
    pdf_pages._layer_memo_clear()
    return not pdf_pages.first_page_drawn(pdf) and not any(_texts(pdf))


KEEP = ['GENUINE LULUS', 'PAGE TWO ORDINARY WORDS']


class AStreamMustEndWhereItsLengthSays(SimpleTestCase):
    def test_probes_p2d_p2e_a_wrong_length_and_endobj_in_the_data(self):
        body = G + b'endobj\n' + L
        for name, length in (('p2d_short', b'10'), ('p2e_long', b'%d' % (len(body) + 40))):
            with self.subTest(name):
                self.assertTrue(_refused(_pdf(_stream(body, length))))

    def test_endobj_where_the_content_reader_does_not_look(self):
        """In a comment: pdfium's search still stops there (GENUINE only), pypdf read both."""
        body = G + b'% endobj\n' + L
        self.assertTrue(_refused(_pdf(_stream(body, b'%d' % (len(body) - 5)))))

    def test_a_wrong_length_with_no_endobj_word(self):
        for name, length in (('short', b'10'), ('one_long', b'%d' % (len(G + L) + 2)), ('missing', None)):
            obj = _stream(G + L, length) if length else b'<< >>\nstream\n' + G + L + b'\nendstream'
            with self.subTest(name):
                self.assertTrue(_refused(_pdf(obj)))

    def test_an_indirect_length(self):
        body = G + L
        self.assertEqual(_texts(_pdf(_stream(body, b'8 0 R'), extra=[b'%d' % len(body)])), KEEP)
        for name, value in (('wrong', b'10'), ('not_a_number', b'(80)'), ('missing_object', None)):
            with self.subTest(name):
                self.assertTrue(_refused(_pdf(_stream(body, b'9 0 R' if value is None else b'8 0 R'),
                                              extra=[value or b'null'])))
        with self.subTest('endobj_in_data'):         # right length, but pdfium could fall back to its search
            body = G + b'% endobj\n' + L
            self.assertTrue(_refused(_pdf(_stream(body, b'8 0 R'), extra=[b'%d' % len(body)])))

    def test_a_stream_keyword_the_two_readers_find_differently(self):
        body = G + L
        for name, obj in (('comment_before', b'<< /Length %d >>%%c\nstream\n' % len(body) + body + b'\nendstream'),
                          ('x80_before', b'<< /Length %d >>\x80stream\n' % len(body) + body + b'\nendstream'),
                          ('tab_after', b'<< /Length %d >>\nstream\t\n' % len(body) + body + b'\nendstream'),
                          ('text_after', b'<< /Length %d >>\nstream x\n' % len(body) + body + b'\nendstream'),
                          ('in_content', _stream(G + b'<< /Length 37 >> stream\n' + L[:-1] + b'\nendstream\n'))):
            with self.subTest(name):
                self.assertTrue(_refused(_pdf(obj)))

    def test_controls_keep_the_exact_read(self):
        body = G + L
        cases = {
            'lf': _stream(body),
            'crlf': _stream(body, tail=b'\r\nendstream'),
            'cr': _stream(body, tail=b'\rendstream'),
            'eol_counted_in_length': _stream(body + b'\n', tail=b'endstream'),
            'spaces_then_lf': _stream(body, tail=b'  \n\nendstream'),
            'crlf_after_keyword': b'<< /Length %d >>\r\nstream\r\n' % len(body) + body + b'\r\nendstream',
        }
        for name, obj in cases.items():
            with self.subTest(name):
                self.assertEqual(_texts(_pdf(obj)), KEEP)


class AWordInAnArrayMustEndOnWhiteSpaceOrADelimiter(SimpleTestCase):
    def test_probe_p2l_nulltrue(self):
        for name, contents in (('nulltrue', b'[5 0 R nulltrue 8 0 R]'), ('nullnull', b'[5 0 R nullnull 8 0 R]'),
                               ('number_into_null', b'[5 0 R 8 0 R1null]')):
            with self.subTest(name):
                self.assertTrue(_refused(_pdf(_stream(G), contents, extra=[_stream(L)])))

    def test_controls_keep_the_exact_read(self):
        pdf = _pdf(_stream(G), b'[5 0 R 8 0 R] /Foo [null true null/N null(s)null[null]false]', extra=[_stream(L)])
        self.assertEqual(_texts(pdf), KEEP)
        pdf = _pdf(_stream(b'BT /F1 24 Tf 72 700 Td [(GEN)-20(UINE)] TJ ET\n' + L + b'[ 1 2 ] 0 d\n'))
        self.assertEqual(_texts(pdf), KEEP)


class ActualTextGivesTheSpmWordsOpNoWords(SimpleTestCase):
    def test_probes_p4a_p4b(self):
        for name, props in (('p4a_literal', b'<< /ActualText (A+) >>'),
                            ('p4b_utf16', b'<< /ActualText <FEFF0041002B> >>')):
            content = b'BT /F1 24 Tf 72 700 Td (MATEMATIK) Tj ET\n/Span ' + props + b' BDC ' + L + b'EMC\n'
            with self.subTest(name):
                pdf = _pdf(_stream(content))
                self.assertEqual(_texts(pdf)[0], 'MATEMATIK LULUS')        # the exact read: the glyphs drawn
                self.assertEqual(_words(pdf), [])

    def test_a_properties_resource_and_a_form(self):
        resources = b' /Properties << /P0 << /ActualText (A+) >> >> /XObject << /Fm0 8 0 R >>'
        form = _stream(L, head=b'<< /Type /XObject /Subtype /Form /BBox [0 0 595 842] /Resources << /Font << /F1 4 0 R'
                                b' >> >>')
        for name, content in (('properties', G + b'/Span /P0 BDC ' + L + b'EMC\n'),
                              ('around_a_form', G + b'/Span << /ActualText (A+) >> BDC /Fm0 Do EMC\n')):
            with self.subTest(name):
                self.assertEqual(_words(_pdf(_stream(content), resources=resources, extra=[form])), [])

    def test_control_a_mark_without_actualtext(self):
        pdf = _pdf(_stream(G + b'/Span << /MCID 0 /Lang (ms) >> BDC ' + L + b'EMC\n'))
        self.assertEqual(_words(pdf), ['GENUINE', 'LULUS'])
