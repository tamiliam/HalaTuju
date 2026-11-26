"""OCR-20 review round 2 (25 Nov): pypdf's lenient dictionary and array parsing, long names, optional forms.

F1: pypdf ends a dictionary at a null key, skips a non-name key whole, returns what it had at a value it cannot
read, and ends an array silently at the end of the data; pdfium reads on. Page 1 read GENUINE to the gate and drew
FORGED (probe p1 a-d). F2: pdfium cuts a name at about 255 bytes, so a long font name found no font (probe p4).
F3: the ``words`` op and `_paints` missed an /OC on a form XObject (probe p2). Fictional words only.
"""
import io
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import pdf_pages
from apps.scholarship.tests.test_ocr20_dup_keys import FORM, GENUINE, OFF, PAGE_TWO, _doc, _drawn, _texts, _words

FORGED_PAGE = b' /Contents 5 0 R %s /Contents 7 0 R'        # pypdf: 5 (GENUINE); pdfium: 7 (FORGED)
REMAP = (b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding << /Type /Encoding /BaseEncoding'
         b' /WinAnsiEncoding /Differences [69 /X 71 /F 73 /W 78 /Z 85 /Y] >> >>')
FONT = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'


def _refused(pdf) -> bool:
    """The whole file lost its layer: page 1 not drawn and no page text at all."""
    return not _drawn(pdf) and not any(_texts(pdf))


def _long_font(pad: int) -> bytes:
    """Page 1 shows GENUINE in a font named '/F' + 'A' x ``pad`` that re-maps its letters (probe p4)."""
    name = b'/F' + b'A' * pad
    pdf = _doc(content=b'BT ' + name + b' 24 Tf 72 700 Td (GENUINE) Tj ET')
    return pdf.replace(b'/Font << /F1 4 0 R >>', b'/Font << /F1 4 0 R ' + name + b' 4 0 R >>', 1).replace(FONT, REMAP)


def _fix_xref(pdf: bytes) -> bytes:
    """Rewrite the table after an edit changed object lengths (objects 1-12, in order)."""
    import re
    body = pdf[:pdf.index(b'xref\n')]
    offs = [m.start() for m in re.finditer(rb'(?m)^(\d+) 0 obj', body)]
    table = b'xref\n0 13\n0000000000 65535 f \n' + b''.join(b'%010d 00000 n \n' % o for o in offs)
    return body + table + pdf[pdf.index(b'trailer'):pdf.index(b'startxref')] + b'startxref\n%d\n%%%%EOF\n' % len(body)


class ALenientDictionaryReadRefusesTheFile(SimpleTestCase):
    def test_probe_p1_a_to_d(self):
        for name, sep in (('a_null_key', b'null'), ('b_array_key', b'['), ('c_string_key', b'('),
                          ('d_bad_value', b'/Foo )')):
            page = FORGED_PAGE % sep
            if sep in (b'[', b'('):            # the key the parser skips whole holds the second /Contents
                page = b' /Contents 5 0 R ' + sep + b' /Contents 7 0 R ' + {b'[': b']', b'(': b')'}[sep]
            with self.subTest(name):
                self.assertTrue(_refused(_doc(page)))

    def test_other_lenient_paths(self):
        cases = {
            'lone_angle': FORGED_PAGE % b'>',
            'endobj_value': b' /Contents 5 0 R /Foo endobj',
            'falsy_value': b' /Contents 5 0 R /Foo falsy',
            'truex_value': b' /Contents 5 0 R /Foo truex',
            'non_name_key_true': FORGED_PAGE % b'true',
        }
        for name, page in cases.items():
            with self.subTest(name):
                self.assertTrue(_refused(_doc(page)))

    def test_a_content_stream_property_list(self):
        for name, props in (('repeated', b'<< /ActualText (A) /ActualText (B) >>'), ('null_key', b'<< /MCID 0 null >>'),
                            ('long_tag', None)):
            content = (b'/' + b'T' * 128 + b' BMC ' + GENUINE + b' EMC') if props is None else (
                b'/Span ' + props + b' BDC ' + GENUINE + b' EMC')
            with self.subTest(name):
                self.assertTrue(_refused(_fix_xref(_doc(content=content))))

    def test_controls_keep_their_layer(self):
        for name, page in (('plain', b' /Contents 5 0 R'), ('false_value', b' /Contents 5 0 R /Foo false /Bar null'),
                           ('empty_dict', b' /Contents 5 0 R /Foo <<>> /Bar [] /Baz [[1] [2 [3]]]')):
            with self.subTest(name):
                self.assertEqual(_texts(_doc(page)), ['GENUINE', PAGE_TWO])
        content = b'/Span << /ActualText (GENUINE) /MCID 0 >> BDC ' + GENUINE + b' EMC'
        self.assertEqual(_texts(_fix_xref(_doc(content=content))), ['GENUINE', PAGE_TWO])

    def test_the_gate_reader_refuses_by_structure(self):
        from apps.scholarship import pdf_dict_keys
        from apps.scholarship.pdf_layer_guards import OverBudget
        with self.assertRaisesRegex(OverBudget, 'may read differently'):
            pdf_pages._open_pdf(_doc(FORGED_PAGE % b'null'))
        with patch.object(pdf_dict_keys, '_warning', side_effect=AssertionError):   # no warning is needed
            with self.assertRaisesRegex(OverBudget, 'may read differently'):
                pdf_pages._open_pdf(_doc(FORGED_PAGE % b'null'))


class AnArrayMustEndOnItsOwnBracket(SimpleTestCase):
    def _read(self, data: bytes):
        from pypdf.generic import ArrayObject

        from apps.scholarship.pdf_layer_guards import _CountedBytes
        return ArrayObject.read_from_stream(_CountedBytes(data), None)

    def test_an_array_cut_at_the_end_of_the_data(self):
        from apps.scholarship.pdf_layer_guards import OverBudget
        for data in (b'[1 2', b'[1 [2 3]', b'[1 [2 [3]]'):
            with self.subTest(data), self.assertRaisesRegex(OverBudget, 'an array'):
                self._read(data)

    def test_whole_arrays_and_plain_pypdf(self):
        from pypdf.generic import ArrayObject
        self.assertEqual(self._read(b'[1 [2 3]]'), [1, [2, 3]])
        self.assertEqual(self._read(b'[[1] [2]] '), [[1], [2]])
        self.assertEqual(ArrayObject.read_from_stream(io.BytesIO(b'[1 [2 3]'), None), [1, [2, 3]])   # unchanged


class ANameOver127BytesRefusesTheFile(SimpleTestCase):
    def test_probe_p4_and_the_limit(self):
        for pad in (127, 250, 300):                       # '/F' + pad: 128, 251, 301 bytes after the '/'
            with self.subTest(pad):
                self.assertTrue(_refused(_fix_xref(_long_font(pad))))

    def test_a_127_byte_name_still_reads(self):
        self.assertEqual(_texts(_fix_xref(_long_font(126)))[0], 'FXZYWZX')     # pypdf and pdfium agree here

    def test_decoded_length_counts_too(self):
        from pypdf.generic import NameObject

        from apps.scholarship.pdf_layer_guards import OverBudget, _CountedBytes
        with self.assertRaisesRegex(OverBudget, '127-byte'):
            NameObject.read_from_stream(_CountedBytes(b'/' + b'\xe9' * 100 + b' '), None)   # 100 raw, 150 decoded


class AnOptionalFormGivesNoWords(SimpleTestCase):
    def _form(self, oc: bytes, catalog=b''):
        return _fix_xref(_doc(content=b'/X1 Do', resources=b' /XObject << /X1 7 0 R >>', catalog=catalog,
                              sticker=GENUINE.replace(b'72 700', b'10 40')).replace(FORM, FORM + oc))

    def test_probe_p2(self):
        from apps.scholarship import pdf_pdfium_check
        cases = {'ocg_off': self._form(b' /OC 12 0 R', OFF),
                 'ocmd_all_off': self._form(b' /OC << /Type /OCMD /OCGs [12 0 R] /P /AllOff >>')}
        for name, pdf in cases.items():
            with self.subTest(name):
                self.assertEqual(_words(pdf), [])
                self.assertEqual(pdf_pdfium_check.hidden_pages(pdf, 2, {0: 'GENUINE', 1: PAGE_TWO}, False), {0})

    def test_control(self):
        self.assertEqual(_words(self._form(b'')), ['GENUINE'])


class InstallIsSafe(SimpleTestCase):
    def test_install_twice_keeps_an_outer_patch(self):
        from pypdf.generic import _data_structures

        from apps.scholarship import pdf_dict_keys

        def outer(*a, **k):
            return None
        pdf_dict_keys.install()
        with patch.object(_data_structures, 'logger_warning', outer):
            pdf_dict_keys.install()
            self.assertIs(_data_structures.logger_warning, outer)
        self.assertIs(_data_structures.logger_warning, pdf_dict_keys._warning)
        self.assertIs(_data_structures.read_object, pdf_dict_keys._read_object)
