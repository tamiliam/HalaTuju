"""OCR-12 new design (2026-11-24): a number the PDF gate uses resolves to ONE object (`pdf_object_identity`).

The round-4 repros come first: the gate (pypdf) reads a LIGHT page 3, pdfium, rebuilding the table (the first
entry is wrong), a HEAVY page 3 written '(%) 3. 0 obj' after a stream whose /Length the old rebuild walk read
differently from pdfium. pdfium draws the heavy page in every one of them, controls included (the controls were
the same file WITHOUT the walk desync, which the old design refused): all are refused. Then the earlier rounds'
hides (T1 a cut number word, T2 a '%' in a string or stream, T3 an object stream no entry names) and the
generation sites. Every file is built here: filled rectangles only, no personal data.
"""
import zlib
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import pdf_layer_guards as guards, pdf_object_identity as identity, pdf_render_check
from apps.scholarship.tests import _pdf_generations as gen
from apps.scholarship.tests import _timing

HEAVY = b'0 g 0 0 595 842 re f\n' * 20_000
LIGHT = b'0 g 72 700 300 1 re f'
PAGE = b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> /Contents %d 0 R >>'
LONG = b'0' * 255 + b'3000'          # pdfium keeps 255 zeros and '3': object 3; pypdf reads 3000
ODD = 'an object header the gate cannot read'
TWO = 'object 3 has more than one copy'


def _verdict(pdf):
    return pdf_render_check.render_refusal(pdf, lambda n: range(min(n, 30)))


def _stream(data, head=b'<<'):
    return head + b' /Length %d >>\nstream\n' % len(data) + data + b'\nendstream'


def _table_file(parts, entries, first_wrong=False):
    """``parts``: [(key, raw object bytes)]; ``entries``: {number: key its table entry points at}. With
    ``first_wrong`` the first entry points at the second's object, so pdfium's table check fails and it rebuilds."""
    out, at = bytearray(b'%PDF-1.5\n%\xe2\xe3\xcf\xd3\n'), {}
    for key, raw in parts:
        at[key] = len(out)
        out += raw + b'\nendobj\n'
    x, nums = len(out), sorted(entries)
    body = b'xref\n0 1\n0000000000 65535 f \n'
    for n in nums:
        off = at[entries[nums[1] if first_wrong and n == nums[0] else n]]
        body += b'%d 1\n%010d 00000 n \n' % (n, off)
    out += body + b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (max(nums) + 1, x)
    return bytes(out)


def _base(heavy=HEAVY):
    return [('1', b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>'),
            ('2', b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>'),
            ('light3', b'3 0 obj\n' + PAGE % 6), ('6', b'6 0 obj\n' + _stream(LIGHT)),
            ('7', b'7 0 obj\n' + _stream(heavy))]


R4_ENTRIES = {1: '1', 2: '2', 3: 'light3', 6: '6', 7: '7', 8: '8'}


def r4(tail=b'\n%c\nendstream', head=b'(%) 3. 0 obj', data=b'xendobj ( ', dict_=None, heavy=HEAVY):
    """Round 4: stream 8 (``dict_``, else a right /Length) holds ``data`` then ``tail``; a second page 3 after
    it (contents 7: ``heavy``)."""
    d = dict_ or b'<< /Length %d >>' % len(data)
    parts = _base(heavy) + [('8', b'8 0 obj\n' + d + b'\nstream\n' + data + tail), ('heavy3', head + b'\n' + PAGE % 7)]
    return _table_file(parts, R4_ENTRIES, first_wrong=True)


R4 = {'r4_comment_before_endstream': {}, 'r4_ff_before_endstream': {'tail': b'\n\x0c\nendstream'},
      'r4_nul_before_endstream': {'tail': b'\n\x00\nendstream'},
      'r4b_length_dotted': {'tail': b'\nendstream', 'dict_': b'<< /Length 10.0 >>'},
      'r4b_length_nested': {'tail': b'\nendstream', 'dict_': b'<< /Length 10 /DecodeParms << /Length 99 >> >>'},
      'r4b_length_plus': {'tail': b'\nendstream', 'dict_': b'<< /Length +10 >>'}}
R4_CONTROLS = {'r4_control_no_comment': {'tail': b'\nendstream'}, 'r4_control_no_desync': {'data': b'plain data'},
               'r4b_control_plain': {'tail': b'\nendstream', 'dict_': b'<< /Length 10 >>'}}


class RoundFourRepros(SimpleTestCase):
    def test_each_hostile_file_is_refused(self):
        for name, kw in R4.items():
            with self.subTest(name):
                self.assertEqual(_verdict(r4(**kw)), (0, 'OverBudget: ' + ODD))

    def test_each_control_is_refused_too(self):
        for name, kw in R4_CONTROLS.items():
            with self.subTest(name):
                self.assertEqual(_verdict(r4(**kw)), (0, 'OverBudget: ' + ODD))

    def test_a_plain_second_header_is_refused_as_a_second_copy(self):
        for name, kw in {**R4, **R4_CONTROLS}.items():
            with self.subTest(name):
                self.assertEqual(_verdict(r4(head=b'(%) 3 0 obj', **kw)), (0, 'OverBudget: ' + TWO))

    def test_light_twins_are_decided_by_the_identity_check_both_ways(self):
        """Contents 7 light: no other check refuses. The control (second header names 9) passes; each twin
        (a second page 3) is refused by the identity check alone."""
        for name, kw in {**R4, **R4_CONTROLS}.items():
            with self.subTest(name):
                self.assertEqual(_verdict(r4(head=b'(%) 9 0 obj', heavy=LIGHT, **kw)), (1, None))
                self.assertEqual(_verdict(r4(head=b'(%) 3 0 obj', heavy=LIGHT, **kw)), (0, 'OverBudget: ' + TWO))
                self.assertEqual(_verdict(r4(heavy=LIGHT, **kw)), (0, 'OverBudget: ' + ODD))
                with mock.patch.object(identity.Identity, 'build'), mock.patch.object(identity.Identity, 'check'):
                    for head in (b'(%) 3 0 obj', b'(%) 3. 0 obj'):     # identity off: nothing else refuses
                        self.assertEqual(_verdict(r4(head=head, heavy=LIGHT, **kw)), (1, None))

    def test_the_same_file_without_a_second_page_passes(self):
        for name, kw in {**R4, **R4_CONTROLS}.items():
            with self.subTest(name):
                self.assertEqual(_verdict(r4(head=b'(%) 9 0 obj', **kw)), (1, None))


def long_number(num=LONG, gen_word=b'0'):
    """T1: a second page 3 (heavy) whose header is ``num gen_word obj``; the entry for 3 points at it."""
    parts = _base() + [('heavy3', num + b' ' + gen_word + b' obj\n' + PAGE % 7)]
    return _table_file(parts, {1: '1', 2: '2', 3: 'heavy3', 6: '6', 7: '7'})


def string_percent(lead=b'(%)', num=b'3.'):
    parts = _base() + [('heavy3', lead + b' ' + num + b' 0 obj\n' + PAGE % 7)]
    return _table_file(parts, {1: '1', 2: '2', 3: 'light3', 6: '6', 7: '7'}, first_wrong=True)


def stream_percent(data=b'%X'):
    parts = _base() + [('8', b'8 0 obj\n<< /Length %d >>\nstream\n' % len(data) + data
                        + b'endstream endobj 3 0 obj\n' + PAGE % 7)]
    return _table_file(parts, {1: '1', 2: '2', 3: 'light3', 6: '6', 7: '7', 8: '8'}, first_wrong=True)


def hidden_object_stream(decoy=b'/X (%) ', name=b'/ObjStm'):
    """T3: an object stream no entry names packing a second page 3 (heavy); ``decoy`` before its /Type."""
    member = b'3 0 ' + PAGE % 7 + b'\n'
    parts = _base() + [('9', b'9 0 obj\n' + _stream(member, b'<< ' + decoy + b'/Type ' + name + b' /N 1 /First 4'))]
    return _table_file(parts, {1: '1', 2: '2', 3: 'light3', 6: '6', 7: '7'})


def packed_member(word=LONG, wrong1=True):
    """Object stream 9 packs '3' (light page) then ``word`` (heavy); the entry for 3 says (9, 0)."""
    a, b = PAGE % 6 + b'\n', PAGE % 7 + b'\n'
    head = b'3 0 ' + word + b' %d ' % len(a)
    comp = zlib.compress(head + a + b)
    out, off = bytearray(b'%PDF-1.5\n'), {}
    for n, body in ((1, b'<< /Type /Catalog /Pages 2 0 R >>'), (2, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>'),
                    (6, _stream(LIGHT)), (7, _stream(HEAVY))):
        off[n] = len(out)
        out += b'%d 0 obj\n' % n + body + b'\nendobj\n'
    off[9] = len(out)
    out += (b'9 0 obj\n<< /Type /ObjStm /N 2 /First %d /Filter /FlateDecode /Length %d >>\nstream\n'
            % (len(head), len(comp)) + comp + b'\nendstream\nendobj\n')
    x = len(out)
    ent = {0: (0, 0, 255), 1: (1, off[2] if wrong1 else off[1], 0), 2: (1, off[2], 0), 3: (2, 9, 0),
           6: (1, off[6], 0), 7: (1, off[7], 0), 9: (1, off[9], 0), 10: (1, x, 0)}
    rows = b''.join(bytes([t]) + v.to_bytes(4, 'big') + bytes([g]) for t, v, g in (ent.get(n, (0, 0, 0))
                                                                                   for n in range(11)))
    xs = zlib.compress(rows)
    out += (b'10 0 obj\n<< /Type /XRef /Size 11 /W [1 4 1] /Root 1 0 R /Filter /FlateDecode /Length %d >>\n'
            b'stream\n' % len(xs) + xs + b'\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n' % x)
    return bytes(out)


class T1NumberCut(SimpleTestCase):
    def test_a_number_word_pdfium_may_cut_is_refused(self):
        for num, gen_word in ((LONG, b'0'), (b'0' * 251 + b'3000', b'0'), (b'3', b'0' * 255 + b'1'), (b'03', b'0')):
            with self.subTest(size=len(num + gen_word)):
                n, why = _verdict(long_number(num, gen_word))
                self.assertEqual(n, 0)
                self.assertIn('may read differently', why)

    def test_control_a_plain_3000_passes(self):
        self.assertEqual(_verdict(long_number(b'3000')), (1, None))

    def test_a_second_generation_is_a_second_copy(self):
        self.assertEqual(_verdict(long_number(b'3', b'1')), (0, 'OverBudget: ' + TWO))

    def test_object_stream_members(self):
        for wrong1 in (True, False):
            with self.subTest(rebuilds=wrong1):
                self.assertEqual(_verdict(packed_member(LONG, wrong1))[0], 0)     # pypdf's own word limit, or ours
        self.assertEqual(_verdict(packed_member(b'3')), (0, 'OverBudget: ' + TWO))
        self.assertEqual(_verdict(packed_member(b'4')), (1, None))


class T2PercentInAString(SimpleTestCase):
    def test_a_percent_in_a_string_or_hex_string_is_refused(self):
        for lead in (b'(%)', b'<%>', b'(a\\) %)', b'(x)', b'<ab>'):
            with self.subTest(lead=lead):
                self.assertEqual(_verdict(string_percent(lead)), (0, 'OverBudget: ' + ODD))
                self.assertEqual(_verdict(string_percent(lead, b'3')), (0, 'OverBudget: ' + TWO))

    def test_a_percent_in_a_string_before_a_unique_number_still_passes(self):
        self.assertEqual(_verdict(string_percent(b'(100%)', b'8')), (1, None))

    def test_a_header_in_stream_data_is_a_copy(self):
        for data in (b'%X', b'XX'):
            with self.subTest(data=data):
                self.assertEqual(_verdict(stream_percent(data)), (0, 'OverBudget: ' + TWO))

    def test_a_header_split_by_a_comment_is_refused(self):
        for name, head in gen.COMMENT_SPLIT.items():
            with self.subTest(header=name):
                self.assertEqual(_verdict(gen.comment_split(head))[0], 0)


class T3ObjectStreamNoEntryNames(SimpleTestCase):
    def test_it_is_refused_whatever_comes_before_it(self):
        for decoy in (b'/X (%) ', b'/X <%> ', b'/X (x) ', b''):
            with self.subTest(decoy=decoy):
                self.assertEqual(_verdict(hidden_object_stream(decoy)),
                                 (0, 'OverBudget: an object stream the cross-reference does not name'))

    def test_an_escaped_name_counts(self):
        self.assertEqual(_verdict(hidden_object_stream(b'', b'/Obj#53tm'))[0], 0)


class Generations(SimpleTestCase):
    """The old branch's generation sites: pdfium follows the NUMBER; pypdf found nothing, or another copy."""

    def test_a_wrong_generation_is_refused(self):
        for site in ('contents', 'annots', 'ap', 'xobject'):
            with self.subTest(site=site):
                n, why = _verdict(gen.wrong_generation(site))
                self.assertEqual(n, 0)
                self.assertIn('exists but the gate did not read it', why)

    def test_each_single_object_site_with_two_copies_is_refused(self):
        for name, build in (('page', gen.page_node), ('matrix', gen.matrix), ('bbox', gen.bbox), ('rect', gen.rect),
                            ('objstm', gen.object_stream), ('parent', gen.parent), ('length', gen.length),
                            ('filter', gen.filters), ('fontfile', gen.font_file)):
            with self.subTest(site=name):
                self.assertEqual(_verdict(build())[0], 0)

    def test_incremental_copies_are_refused(self):
        for ref in (b'5 0 R', b'5 1 R'):
            with self.subTest(ref=ref):
                self.assertEqual(_verdict(gen.newer_section(ref))[0], 0)
        self.assertEqual(_verdict(gen.incremental())[0], 0)
        self.assertEqual(_verdict(gen.incremental(bump=True))[0], 0)

    def test_an_ordinary_file_passes(self):
        self.assertEqual(_verdict(gen.many_headers(1)), (1, None))


class Work(SimpleTestCase):
    """The scan's work is charged to the reader's lookup budget, in counts, never by the clock."""

    def test_the_scan_charges_the_file_and_each_obj_word(self):
        small, big = gen.many_headers(1), gen.many_headers(1001)
        extra = guards.GateReader(big)._counted.work - guards.GateReader(small)._counted.work
        self.assertGreaterEqual(extra, len(big) - len(small) + identity._WORD_WORK * 1000)

    def test_twenty_thousand_headers_cost_linear_work(self):
        self.assertEqual(_verdict(gen.many_headers(20_000)), (1, None))
        _timing.assert_linear(self, _verdict, gen.many_headers, 10_000, 'headers')

    def test_a_long_run_of_odd_words_is_linear(self):
        def odd(k):
            return gen.junk_in_stream(b'(%) x obj ' * k)
        _timing.assert_linear(self, _verdict, odd, 5_000, 'odd words')

    def test_candidates_per_number_stop_at_the_cap(self):
        body = b''.join(b'7 0 obj null endobj\n' for _ in range(100))
        one = identity.Identity.__new__(identity.Identity)
        one.reader = guards.GateReader(gen.many_headers(1))
        one.headers, one.reader._counted.refused = {}, None
        one.reader._counted.getvalue = lambda: body
        one.build()
        self.assertEqual(len(one.headers[7]), identity.MAX_CANDIDATES)
