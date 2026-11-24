"""OCR-12 review round 1 (2026-11-24): the reviewer's probes, built here, each with a light control that passes.

A: a row for 3 of a type neither reader agrees on ('x', ' '), pdfium's reading of it in use, pointing at the '3'
   of '13 0 obj' (a heavy page): pypdf skipped it and found the light page 3 by searching. A4 / A5: a NEWER row
   for 3 in another generation (a table, then cross-reference streams): pypdf keeps both generations and reads
   '3 0 R' from generation 0; pdfium keys by number, newest wins. B: '(%) 3 0 %x' then 'obj' on the next line:
   the first '%' sits in a string, the second starts a comment pdfium skips. C: a packed row whose index points
   at another member (or past the stream). D: the scans are charged their real work. Review round 2: E, F, G
   (a walk that ended early switched the row checks off) and the rebuilt-table index. Filled rectangles only.
"""
import time
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import pdf_layer_guards as guards, pdf_object_identity as identity, pdf_render_check, pdf_xref_rows
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


#: Review round 2, finding 1: tails pdfium and pypdf both read to the same start; the old walk found none there
#: and switched its row checks off (E: a comment or a sign before the number; G: a 'startxref' comment after %%EOF).
TAILS_E = {'comment': b'startxref %%c\n%d\n%%%%EOF\n', 'plus': b'startxref\n+%d\n%%%%EOF\n'}
TAILS_G = (b'% startxref\n', b'%startxrefs\n')
UNKNOWN = 'OverBudget: object 3 has a cross-reference row of an unknown type'


def chain(row3, newest=b'/XRefStm 0 '):
    """F: three tables, oldest first: every row; ``row3`` alone; object 1 alone, its trailer given ``newest``
    before its /Prev (review round 2: '/XRefStm 0' stopped the old walk, which never read the 'x' row)."""
    pdf = _doc().table(BASE).table([row3]).table(gen.ents(1)).bytes()
    at = pdf.rindex(b'/Prev ')
    return pdf[:at] + newest + pdf[at:]


def light_tables(trailer=b'', tables=1):
    """One light page; ``tables`` tables (the newer ones repeat object 5), ``trailer`` added to the newest."""
    d = gen._base(gen.GenDoc(), gen.page()).obj(5, 0, gen.gen_stream(LIGHT)).table(gen.ents(1, 2, 3, 5))
    for _ in range(tables - 1):
        d.table(gen.ents(5))
    pdf = d.bytes()
    at = pdf.rindex(b'/Root 1 0 R') + 11
    return pdf[:at] + trailer + pdf[at:]


class E_TheWholeChainOrRefused(SimpleTestCase):
    """Review round 2, finding 1: a walk that ended early left the round-1 attacks accepted. Now the walk reads
    the whole chain from the start pdfium takes (the same as pypdf's) or refuses the file."""

    def test_e_a_comment_or_a_sign_before_the_number_still_finds_the_rows(self):
        for how, tail in TAILS_E.items():
            with self.subTest(how=how):
                self.assertEqual(_verdict(gen.retail(type_row('x'), tail)), (0, UNKNOWN))
                self.assertEqual(_verdict(gen.retail(packed_member(b'4', wrong1=False, index=1), tail)),
                                 (0, 'OverBudget: ' + TWO))

    def test_e_control_the_same_tails_on_light_files_pass(self):
        for how, tail in TAILS_E.items():
            with self.subTest(how=how):
                self.assertEqual(_verdict(gen.retail(type_row('ok'), tail)), (1, None))
                self.assertEqual(_verdict(gen.retail(packed_member(b'4', wrong1=False), tail)), (1, None))

    def test_g_a_startxref_comment_after_the_end_still_finds_the_rows(self):
        for tail in TAILS_G:
            with self.subTest(tail=tail):
                self.assertEqual(_verdict(type_row('x') + tail), (0, UNKNOWN))
                self.assertEqual(_verdict(packed_member(b'4', wrong1=False, index=1) + tail), (0, 'OverBudget: ' + TWO))

    def test_g_control_the_same_tails_on_a_light_file_pass(self):
        for tail in TAILS_G:
            with self.subTest(tail=tail):
                self.assertEqual(_verdict(type_row('ok') + tail), (1, None))

    def test_f_xrefstm_0_is_no_link_and_the_older_sections_are_read(self):
        self.assertEqual(_verdict(chain((3, 'x', 0, ('mid', 0)))), (0, UNKNOWN))

    def test_f_control_xrefstm_0_and_prev_0_on_light_files_pass(self):
        self.assertEqual(_verdict(chain((3, 'n', 0, (3, 0)))), (1, None))
        for trailer in (b' /Prev 0', b' /XRefStm 0', b' /XRefStm 0 /Prev 0'):
            with self.subTest(trailer=trailer):
                self.assertEqual(_verdict(light_tables(trailer)), (1, None))

    def test_a_chain_that_ends_early_is_refused(self):
        pdf = light_tables(tables=2)
        first, last = _tables(pdf)
        word = pdf.index(b'endobj')
        cases = {
            'past the end': (light_tables(b' /Prev 99999999'), 'a cross-reference link to where no section starts'),
            'at a word': (light_tables(b' /XRefStm %d' % word), 'a cross-reference link to where no section starts'),
            'at a number': (light_tables(b' /Prev 10'), 'a cross-reference section the gate cannot read'),
            'a loop': (pdf.replace(b'/Prev %d' % first, b'/Prev %d' % last), 'a cross-reference chain that loops'),
            'no start (pypdf then reads no section)': (gen.retail(pdf, b'startxref\n%d_0\n%%%%EOF\n'),
                                                       'a cross-reference link to where no section starts'),
            'no header within 1024 bytes': (b' ' * 1025 + pdf, 'the renderer finds no file header'),
            'a run-on keyword': (gen.retail(pdf, b'startxrefs\n%d\n%%%%EOF\n'),
                                 'the gate and the renderer start the cross-reference in different places'),
            'a glued number': (gen.retail(pdf, b'startxref%d\n%%%%EOF\n'),
                               'the gate and the renderer start the cross-reference in different places'),
        }
        for name, (data, why) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(_verdict(data), (0, 'OverBudget: ' + why))
        for trailer in (b' /Prev -5', b' /Prev 12.5', b' /Prev /X'):    # pypdf fails first; the walk refuses too
            with self.subTest(trailer=trailer):
                data = light_tables(trailer)
                self.assertEqual(_verdict(data)[0], 0)
                with self.assertRaisesMessage(guards.OverBudget, 'a cross-reference link the gate cannot read'):
                    pdf_xref_rows.Walk(data, _Meter()).run(pdf_xref_rows.pdfium_startxref(data))

    def test_control_a_whole_chain_passes(self):
        pdf = light_tables(tables=3)
        self.assertEqual(_verdict(pdf), (1, None))
        walk = pdf_xref_rows.Walk(pdf, _Meter())
        walk.run(pdf_xref_rows.pdfium_startxref(pdf))
        self.assertEqual(sorted({rank for rows in walk.rows.values() for rank, *_ in rows}), [0, 1, 2])
        first = _tables(pdf)[0]
        self.assertEqual(_verdict(pdf + b'startxref\n%d\n%%%%EOF\n' % first), (1, None))   # both take the older


def _tables(pdf):
    """The offsets of the oldest and the newest table."""
    return pdf.index(b'\nxref\n') + 1, pdf.rindex(b'\nxref\n') + 1


class _Meter:
    def charge(self, units):
        pass

    def _refuse(self, why):
        raise guards.OverBudget(why)


class F_PdfiumStartxref(SimpleTestCase):
    """The start pdfium takes from the tail (probed against pypdfium2 4.30: OCR-12 docs)."""

    def test_the_start_pdfium_takes(self):
        pdf = light_tables(tables=2)
        a, b = _tables(pdf)
        cases = {b'startxref\n%d\n%%%%EOF\n': b, b'startxref %%c\n%d\n%%%%EOF\n': b, b'startxref\n%%c\n%d\n': b,
                 b'startxref\n+%d\n%%%%EOF\n': b, b'startxref\n0%d\n%%%%EOF\n': b, b'startxref\n%d.7\n%%%%EOF\n': b,
                 b'startxref\n\x80%d\n%%%%EOF\n': b, b'startxref\n%d\n%%%%EOF\n%% startxref\n': b,
                 b'startxref\n-%d\n%%%%EOF\n': None, b'startxref\n%d_0\n%%%%EOF\n': None,
                 b'startxref (x) %d\n%%%%EOF\n': None, b'startxref\n%d\n%%%%EOF\n%%' + b'x' * 5000 + b'\n': None,
                 b'xstartxref\n%d\n%%%%EOF\n': a, b'startxref\n%d': a}
        for tail, want in cases.items():
            with self.subTest(tail=tail[:40]):
                self.assertEqual(pdf_xref_rows.pdfium_startxref(gen.retail(pdf, tail)), want)
        self.assertIsNone(pdf_xref_rows.pdfium_startxref(gen.retail(pdf, b'startxref\n9999%d\n%%%%EOF\n')))  # past the end
        self.assertIsNone(pdf_xref_rows.pdfium_startxref(pdf + LONG))           # past the 4096-byte search
        # Round 3: offsets count from the header, the first '%PDF' at 0 to 1024 (probe).
        self.assertEqual(pdf_xref_rows.pdfium_startxref(b' ' + pdf), b + 1)
        self.assertEqual(pdf_xref_rows.pdfium_start(b'x' * 1024 + pdf), (1024, b))
        self.assertEqual(pdf_xref_rows.pdfium_start(b'x' * 1025 + pdf), (None, None))


LONG = b'</aaaa>\r\n' * 460      # a tail past pdfium's 4096-byte search for startxref: pdfium rebuilds (probe)
ROOT13 = b'trailer\n<< /Size 14 /Root 13 0 R >>\n'
XREF13 = (b'30 0 obj\n<< /Type /XRef /Size 31 /W [1 1 1] /Root 13 0 R /Length 0 >>\nstream\n\nendstream\n'
          b'endobj\n')


def before_start(pdf, insert):
    """``insert`` placed just before the last startxref (after every table: no offset moves)."""
    at = pdf.rindex(b'startxref')
    return pdf[:at] + insert + pdf[at:]


def lead(pdf, lead_bytes, absolute=False):
    """``lead_bytes`` before the header; ``absolute``: the startxref number counted from byte 0, not the header."""
    out = lead_bytes + pdf
    if absolute:
        at = pdf.rindex(b'startxref\n') + 10
        end = pdf.index(b'\n', at)
        out = lead_bytes + pdf[:at] + b'%d' % (int(pdf[at:end]) + len(lead_bytes)) + pdf[end:]
    return out


class H_RebuildAndHeader(SimpleTestCase):
    """Round 3 (lead's call): where pdfium finds no start it rebuilds from the headers; the file passes only on
    the one-header rule, pypdf's whole chain walked and checked, and every trailer's /Root (and /Encrypt) the
    one pypdf reads (probe: pdfium's rebuild takes the LAST trailer in the file). Bytes before the header: the
    offsets pdfium follows count from its header."""

    def test_on_a_rebuild_the_row_checks_still_apply(self):
        self.assertEqual(_verdict(type_row('x') + LONG), (0, UNKNOWN))
        self.assertEqual(_verdict(packed_member(b'4', wrong1=False, index=1) + LONG), (0, 'OverBudget: ' + TWO))

    def test_control_a_light_file_with_a_long_tail_passes(self):
        pdf = type_row('ok') + LONG
        self.assertIsNone(pdf_xref_rows.pdfium_startxref(pdf))
        self.assertEqual(_verdict(pdf), (1, None))
        self.assertEqual(_verdict(before_start(type_row('ok'), b'trailer\n<< /Size 14 /Root 1 0 R >>\n') + LONG),
                         (1, None))                         # another trailer, the same /Root

    def test_a_trailer_or_xref_stream_naming_another_root_is_refused(self):
        root = (0, 'OverBudget: a trailer names another document root')
        light = type_row('ok')
        for name, insert in (('trailer', ROOT13), ('xref stream', XREF13), ('escaped', ROOT13.replace(b'/Root', b'/R#6fot'))):
            for tail in (LONG, b''):
                with self.subTest(name=name, rebuilt=bool(tail)):
                    self.assertEqual(_verdict(before_start(light, insert) + tail), root)
        self.assertEqual(_verdict(before_start(light, b'trailer\n<< /Encrypt 13 0 R >>\n') + LONG),
                         (0, 'OverBudget: a trailer names an encryption the gate did not read'))

    def test_control_leading_bytes_with_the_header_start_pass(self):
        for lead_bytes in (b'\n', b'x' * 50, b'x' * 1024):
            with self.subTest(lead=len(lead_bytes)):
                self.assertEqual(_verdict(lead(type_row('ok'), lead_bytes)), (1, None))

    def test_leading_bytes_keep_every_check(self):
        for lead_bytes in (b'\n', b'x' * 50):
            with self.subTest(lead=len(lead_bytes)):
                self.assertEqual(_verdict(lead(type_row('x'), lead_bytes)), (0, UNKNOWN))
                self.assertEqual(_verdict(lead(type_row('ok'), lead_bytes, absolute=True))[0], 0)


def rebuilt(row3=(2, 9, 1), gap=b'\n' * 6):
    """Object stream 9 packs 4 (index 0), then the light page 3 (index 1); the chain's row for 3 is ``row3``.
    startxref points at ``gap`` before the cross-reference stream: pdfium reads the chain, pypdf REBUILDS its
    table (its index for 3 is then a byte offset, 6)."""
    four, page3 = b'<< >>\n', PAGE % 6 + b'\n'
    head = b'4 0 3 %d ' % len(four)
    out, off = bytearray(b'%PDF-1.5\n'), {}
    for n, body in ((1, b'<< /Type /Catalog /Pages 2 0 R >>'), (2, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>'),
                    (6, gen.gen_stream(LIGHT)),
                    (9, gen.gen_stream(head + four + page3, b'<< /Type /ObjStm /N 2 /First %d' % len(head)))):
        off[n] = len(out)
        out += b'%d 0 obj\n' % n + body + b'\nendobj\n'
    x = len(out)
    out += gap
    ent = {0: (0, 0, 255), 1: (1, off[1], 0), 2: (1, off[2], 0), 3: row3, 4: (2, 9, 0), 6: (1, off[6], 0),
           9: (1, off[9], 0), 10: (1, x + len(gap), 0)}
    rows = b''.join(bytes([t]) + a.to_bytes(4, 'big') + bytes([g]) for t, a, g in (ent.get(n, (0, 0, 0))
                                                                                  for n in range(11)))
    out += b'10 0 obj\n' + gen.gen_stream(rows, b'<< /Type /XRef /Size 11 /W [1 4 1] /Root 1 0 R') + b'\nendobj\n'
    return bytes(out + b'startxref\n%d\n%%%%EOF\n' % x)


class G_RebuiltTableIndex(SimpleTestCase):
    """Fix 2's exception: pypdf's (stream, index) is no chain row only when pypdf rebuilt its table; the chain's
    rows, each the one place, are then what is compared (review round 2)."""

    def test_control_a_rebuilt_table_with_the_right_chain_row_passes(self):
        self.assertEqual(guards.GateReader(rebuilt()).xref_objStm[3], (9, 6))      # pypdf did rebuild
        self.assertEqual(_verdict(rebuilt()), (1, None))
        self.assertEqual(_verdict(rebuilt(gap=b'')), (1, None))                      # and without the rebuild

    def test_a_rebuilt_table_does_not_hide_a_wrong_chain_row(self):
        self.assertEqual(_verdict(rebuilt((2, 9, 0))), (0, 'OverBudget: ' + TWO))
        self.assertEqual(_verdict(rebuilt((2, 9, 0), gap=b'')), (0, 'OverBudget: ' + TWO))

    def test_a_rebuilt_table_with_no_chain_row_is_refused(self):
        self.assertEqual(_verdict(rebuilt((0, 0, 0))), (0, 'OverBudget: object 3 has no cross-reference row'))


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
