"""OCR-12 review round 1 (2026-11-24): the reviewer's probes, built here, each with a light control that passes.

A: a row for 3 of a type neither reader agrees on ('x', ' '), pdfium's reading of it in use, pointing at the '3'
   of '13 0 obj' (a heavy page): pypdf skipped it and found the light page 3 by searching. A4 / A5: a NEWER row
   for 3 in another generation (a table, then cross-reference streams): pypdf keeps both generations and reads
   '3 0 R' from generation 0; pdfium keys by number, newest wins. B: '(%) 3 0 %x' then 'obj' on the next line:
   the first '%' sits in a string, the second starts a comment pdfium skips. C: a packed row whose index points
   at another member (or past the stream). D: the scans are charged their real work. Filled rectangles only.
"""
import time
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import pdf_layer_guards as guards, pdf_object_identity as identity, pdf_render_check
from apps.scholarship.tests import _pdf_generations as gen
from apps.scholarship.tests import _timing
from apps.scholarship.tests.test_pdf_object_identity import HEAVY, LIGHT, ODD, ROW1, TWO, packed_member, r4

PAGE = b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> /Contents %d 0 R >>'
BASE = gen.ents(1, 2, 3, 6, 7, 13)


def _verdict(pdf):
    return pdf_render_check.render_refusal(pdf, lambda n: range(min(n, 30)))


def _doc():
    """Page 3 (light, contents 6); object 13 a heavy page (contents 7) no page tree names; 'mid' is the '3' of
    '13 0 obj', where a row pdfium follows for 3 finds a header '3 0 obj' and the heavy page."""
    d = gen.GenDoc()
    d.obj(1, 0, b'<< /Type /Catalog /Pages 2 0 R >>').obj(2, 0, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    d.obj(3, 0, PAGE % 6).obj(6, 0, gen.gen_stream(LIGHT)).obj(7, 0, gen.gen_stream(HEAVY)).obj(13, 0, PAGE % 7)
    d.off[('mid', 0)] = d.off[(13, 0)] + 1
    return d


def type_row(kind):
    """A: one table; the row for 3 has type ``kind``; a type 'n' row sits on the light page 3."""
    key = (3, 0) if kind == 'ok' else ('mid', 0)
    return _doc().table([e for e in BASE if e[0] != 3] + [(3, 'n' if kind == 'ok' else kind, 0, key)]).bytes()


def newer_generation(streams, generation=5):
    """A4 (tables) / A5 (cross-reference streams): the newer section's row for 3 is in ``generation`` and points
    at 'mid'; generation 0 (the control) points at the light page 3 again."""
    d = _doc()
    row = [(3, 'n', generation, ('mid', 0) if generation else (3, 0))]
    if streams:
        return d.xstm(20, BASE).xstm(21, row).bytes()
    return d.table(BASE).table(row).bytes()


class A_RowsOnlyPdfiumFollows(SimpleTestCase):
    def test_a_row_of_an_unknown_type_is_refused(self):
        for kind in ('x', ' '):
            with self.subTest(kind=kind):
                self.assertEqual(_verdict(type_row(kind)),
                                 (0, 'OverBudget: object 3 has a cross-reference row of an unknown type'))

    def test_a_row_in_use_off_the_one_header_is_refused(self):
        self.assertEqual(_verdict(type_row('n')), (0, 'OverBudget: ' + TWO))

    def test_control_the_row_on_the_light_page_passes(self):
        self.assertEqual(_verdict(type_row('ok')), (1, None))

    def test_a_newer_row_in_another_generation_is_refused(self):
        for streams in (False, True):
            with self.subTest(streams=streams):
                self.assertEqual(_verdict(newer_generation(streams)),
                                 (0, 'OverBudget: object 3 is in use in more than one generation'))

    def test_control_a_newer_row_in_the_same_generation_passes(self):
        for streams in (False, True):
            with self.subTest(streams=streams):
                self.assertEqual(_verdict(newer_generation(streams, 0)), (1, None))


class B_EveryPercentOnTheLine(SimpleTestCase):
    def test_a_comment_after_a_string_percent_is_refused(self):
        for head in (b'(%) 3 0 %x\nobj', b'3 0 %x\nobj', b'/K (100%) 3 0 % /\nobj'):
            with self.subTest(head=head):
                self.assertEqual(_verdict(r4(head=head, heavy=LIGHT, first_wrong=False)), (0, 'OverBudget: ' + ODD))

    def test_control_a_unique_number_after_a_string_percent_passes(self):
        self.assertEqual(_verdict(r4(head=b'(%) 9 0 obj', heavy=LIGHT, first_wrong=False)), (1, None))


class C_PackedIndex(SimpleTestCase):
    def test_a_packed_row_at_another_index_is_refused(self):
        for index in (1, 7):                                  # object 4 there; past the stream
            with self.subTest(index=index):
                self.assertEqual(_verdict(packed_member(b'4', wrong1=False, index=index)), (0, 'OverBudget: ' + TWO))

    def test_the_lookup_check_holds_the_index_too(self):
        """Finding 2, the rows check aside: pypdf's (stream, index) must be exactly the one place."""
        with mock.patch.object(identity.Identity, '_rows_check'):
            self.assertEqual(_verdict(packed_member(b'4', wrong1=False, index=1)),
                             (0, 'OverBudget: object 3 is not where the cross-reference packs it'))

    def test_control_the_right_index_passes(self):
        self.assertEqual(_verdict(packed_member(b'4', wrong1=False)), (1, None))
        self.assertEqual(_verdict(packed_member(b'4')), (0, 'OverBudget: ' + ROW1))


def light_file(junk=b'', pack_names=0):
    """D: object 6 (never referenced) holds ``junk``; object stream 8 (holding 9) has ``pack_names`` extra
    '/ObjStm' names in its data; a cross-reference stream (10) lists every object."""
    out, off = bytearray(b'%PDF-1.5\n'), {}

    def obj(n, body):
        off[n] = len(out)
        out.extend(b'%d 0 obj\n' % n + body + b'\nendobj\n')

    obj(1, b'<< /Type /Catalog /Pages 2 0 R >>')
    obj(2, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    obj(3, b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources 9 0 R /Contents 5 0 R >>')
    obj(5, gen.gen_stream(LIGHT))
    obj(6, gen.gen_stream(junk))
    obj(8, gen.gen_stream(b'9 0 << >>\n' + b'/ObjStm ' * pack_names, b'<< /Type /ObjStm /N 1 /First 4'))
    at = len(out)
    rows = {0: (0, 0, 65535), 1: (1, off[1], 0), 2: (1, off[2], 0), 3: (1, off[3], 0), 4: (0, 0, 0),
            5: (1, off[5], 0), 6: (1, off[6], 0), 7: (0, 0, 0), 8: (1, off[8], 0), 9: (2, 8, 0), 10: (1, at, 0)}
    data = b''.join(bytes([t]) + a.to_bytes(4, 'big') + b.to_bytes(2, 'big') for _, (t, a, b) in sorted(rows.items()))
    out += b'10 0 obj\n' + gen.gen_stream(data, b'<< /Type /XRef /Size 11 /W [1 4 2] /Root 1 0 R') + b'\nendobj\n'
    out += b'startxref\n%d\n%%%%EOF\n' % at
    return bytes(out)


def _work(pdf):
    reader = guards.GateReader(pdf)
    reader.get_object(9)
    return reader._counted.work


class D_ScansAreCharged(SimpleTestCase):
    def test_object_stream_names_are_charged_and_linear(self):
        """D2: each '/ObjStm' name finds its owner by bisect (finding 4), charged one word each."""
        def make(k):
            return light_file(b''.join(b'%d 0 obj\n' % (100 + i) for i in range(k)), pack_names=k)
        small, big = _work(make(5_000)), _work(make(10_000))
        self.assertGreaterEqual(big - small, 5_000 * 2 * identity._WORD_WORK)     # a header and a name each
        self.assertEqual(_verdict(make(10_000)), (1, None))
        _timing.assert_linear(self, _verdict, make, 5_000, '/ObjStm names')

    def test_odd_words_one_per_line_are_charged_and_linear(self):
        """D1b: line starts are found once (finding 5); each odd word is charged its own scan."""
        def make(k):
            return light_file(b'x obj\n' * k)
        small, big = _work(make(25_000)), _work(make(50_000))
        self.assertGreaterEqual(big - small, 25_000 * identity._WORD_WORK)
        _timing.assert_linear(self, _verdict, make, 25_000, 'odd words, one a line')

    def test_odd_words_on_one_line_are_charged_what_they_scan(self):
        """D1c: on one long line each word scans back to the line start; the charge grows with that scan (about
        4x for twice the words), and a long enough line is refused by the budget, in bounded time."""
        def make(k):
            return light_file(b'x obj ' * k)
        base = _work(make(0))
        small, big = _work(make(10_000)) - base, _work(make(20_000)) - base
        self.assertGreater(big, 3 * small)
        t = time.perf_counter()
        n, why = _verdict(make(120_000))
        self.assertEqual((n, why), (0, 'OverBudget: pypdf lookup work past the cap'))
        self.assertLess(time.perf_counter() - t, _timing.WALL_BACKSTOP_S)
