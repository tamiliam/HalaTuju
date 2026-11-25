"""OCR-20 review round 3 part 3 (25 Nov): white space the two readers disagree on inside a reference.

H5, found by the round-3 short check: pypdf counts 0x0b as white space (its reference pattern uses \\s, its array
loop ``bytes.isspace``), pdfium reads it as an ordinary byte. '/Contents [5 0 R 8\\x0b0\\x0bR]' and
'[5 0 R 8 0 R\\x0b]' were two content streams to pypdf and one to pdfium (probes c_arr_ref_vt_inside,
c_arr_ref_vt_after_last: the gate read GENUINE LULUS, pdfium drew GENUINE); '/XObject << /X1 8\\x0b0\\x0bR >>' the
same through a form (c_dict_xobj_ref_vt). The other way round: NUL is white space to pdfium and to pypdf's
WHITESPACES but not to \\s; 0x80 and 0xff are white space to pdfium only. Crafted files, fictional words only.
"""
import re

from django.test import SimpleTestCase
from pypdf._utils import WHITESPACES

from apps.scholarship import pdf_dict_keys
from apps.scholarship.tests.test_ocr20_dup_keys import _words
from apps.scholarship.tests.test_ocr20_round3_parse import G, KEEP, L, _pdf, _refused, _stream, _texts

DISAGREE = b'\x00\x0b\x80\xff'
FORM = b'<< /Type /XObject /Subtype /Form /BBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >>'


def _array(ref: bytes) -> bytes:
    """Page 1 draws object 5 (GENUINE) and, through ``ref``, object 8 (LULUS)."""
    return _pdf(_stream(G), b'[5 0 R ' + ref + b']', extra=[_stream(L)])


def _form(ref: bytes) -> bytes:
    """Page 1 draws GENUINE, then form /X1 (object 8, LULUS) named by ``ref``."""
    return _pdf(_stream(G + b'q /X1 Do Q\n'), resources=b' /XObject << /X1 ' + ref + b' >>',
                extra=[_stream(L, head=FORM)])


class TheRefusedBytesAreWhereTheReadersDisagree(SimpleTestCase):
    def test_the_set_is_every_pypdf_white_space_against_pdfiums(self):
        self.assertEqual(pdf_dict_keys._PYPDF_SPACE, frozenset(b''.join(WHITESPACES)))
        isspace = frozenset(b for b in range(256) if bytes([b]).isspace())
        regex = frozenset(b for b in range(256) if re.match(rb'\s', bytes([b])))
        pdfium = frozenset(b'\x00\t\n\x0c\r \x80\xff')
        expected = (pdf_dict_keys._PYPDF_SPACE ^ pdfium) | (isspace ^ pdfium) | (regex ^ pdfium)
        self.assertEqual(pdf_dict_keys._DISAGREE, expected)
        self.assertEqual(pdf_dict_keys._DISAGREE, frozenset(DISAGREE))


class AReferenceWithABytePdfiumReadsAnotherWayRefusesTheFile(SimpleTestCase):
    def test_the_three_probes_draw_one_stream_in_pdfium(self):
        for name, pdf in (('c_arr_ref_vt_inside', _array(b'8\x0b0\x0bR')),
                          ('c_arr_ref_vt_after_last', _array(b'8 0 R\x0b')),
                          ('c_dict_xobj_ref_vt', _form(b'8\x0b0\x0bR'))):
            with self.subTest(name):
                self.assertEqual(_words(pdf), ['GENUINE'])          # what is drawn: the hole is real
                self.assertTrue(_refused(pdf))

    def test_every_disagreeing_byte_at_every_place(self):
        for b in DISAGREE:
            x = bytes([b])
            shapes = {
                'array_between_numbers': _array(b'8' + x + b'0 R'),
                'array_before_r': _array(b'8 0' + x + b'R'),
                'array_both': _array(b'8' + x + b'0' + x + b'R'),
                'array_after_r_last': _array(b'8 0 R' + x),
                'array_after_r_middle': _pdf(_stream(G), b'[8 0 R' + x + b' 5 0 R]', extra=[_stream(L)]),
                'dict_between_numbers': _form(b'8' + x + b'0 R'),
                'dict_before_r': _form(b'8 0' + x + b'R'),
                'dict_after_r': _form(b'8 0 R' + x),
                'dict_number_end': _pdf(_stream(G + L), resources=b' /Foo 0' + x),
            }
            for name, pdf in shapes.items():
                with self.subTest(byte=hex(b), place=name):
                    self.assertTrue(_refused(pdf))

    def test_controls_keep_the_exact_read(self):
        for name, pdf in (('array_spaces', _array(b'8 0 R')),
                          ('array_agreed_white_space', _array(b'8\t0\x0cR\r\n')),
                          ('array_tight', _pdf(_stream(G), b'[5 0 R 8 0 R]/Foo[1 2]', extra=[_stream(L)])),
                          ('dict_spaces', _form(b'8 0 R')),
                          ('dict_newlines', _form(b'8\n0\nR\n')),
                          ('dict_number', _pdf(_stream(G + L), resources=b' /Foo 0/Bar [1 2.5 -3]'))):
            with self.subTest(name):
                self.assertEqual(_texts(pdf), KEEP)
