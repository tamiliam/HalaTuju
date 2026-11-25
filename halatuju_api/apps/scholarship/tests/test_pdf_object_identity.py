"""OCR-12 new design (2026-11-24): a number the PDF gate uses resolves to ONE object (`pdf_object_identity`).

The round-4 repros come first: the gate (pypdf) reads a LIGHT page 3, pdfium, rebuilding the table (the first
entry is wrong), a HEAVY page 3 written '(%) 3. 0 obj' after a stream whose /Length the old rebuild walk read
differently from pdfium. pdfium draws the heavy page in every one of them, controls included (the controls were
the same file WITHOUT the walk desync, which the old design refused): all are refused. Then the earlier rounds'
hides (T1 a cut number word, T2 a '%' in a string or stream, T3 an object stream no entry names) and the
generation sites. Every file is built here: filled rectangles only, no personal data.
"""
import io
import threading
import zlib
from unittest import mock

from django.test import SimpleTestCase
from pypdf import PdfReader
from pypdf.generic import NameObject

from apps.scholarship import pdf_layer_guards as guards, pdf_object_identity as identity, pdf_render_check
from apps.scholarship.tests import _pdf_generations as gen
from apps.scholarship.tests import _timing

HEAVY = b'0 g 0 0 595 842 re f\n' * 20_000
LIGHT = b'0 g 72 700 300 1 re f'
PAGE = b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << >> /Contents %d 0 R >>'
LONG = b'0' * 255 + b'3000'          # pdfium keeps 255 zeros and '3': object 3; pypdf reads 3000
ODD = 'an object header the gate cannot read'
ROW1 = 'object 1 has a cross-reference row that is not its one copy'     # round 1: a first entry that is wrong
#: Round 1: a number with two headers is now met first by its row (a row cannot sit on the ONE header of a
#: number that has two); before, 'object 3 has more than one copy'.
TWO = 'object 3 has a cross-reference row that is not its one copy'


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


def r4(tail=b'\n%c\nendstream', head=b'(%) 3. 0 obj', data=b'xendobj ( ', dict_=None, heavy=HEAVY,
       first_wrong=True):
    """Round 4: stream 8 (``dict_``, else a right /Length) holds ``data`` then ``tail``; a second page 3 after
    it (contents 7: ``heavy``). ``first_wrong``: the first entry is wrong (pdfium rebuilds); since review round 1
    that row alone refuses (`ROW1`), so the checks after it are pinned with ``first_wrong=False``."""
    d = dict_ or b'<< /Length %d >>' % len(data)
    parts = _base(heavy) + [('8', b'8 0 obj\n' + d + b'\nstream\n' + data + tail), ('heavy3', head + b'\n' + PAGE % 7)]
    return _table_file(parts, R4_ENTRIES, first_wrong=first_wrong)


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
                self.assertEqual(_verdict(r4(head=b'(%) 3 0 obj', first_wrong=False, **kw)), (0, 'OverBudget: ' + TWO))
                self.assertEqual(_verdict(r4(head=b'(%) 3 0 obj', **kw)), (0, 'OverBudget: ' + ROW1))

    def test_light_twins_are_decided_by_the_identity_check_both_ways(self):
        """Contents 7 light: no other check refuses. The control (second header names 9) passes; each twin
        (a second page 3) is refused by the identity check alone."""
        for name, kw in {**R4, **R4_CONTROLS}.items():
            with self.subTest(name):
                self.assertEqual(_verdict(r4(head=b'(%) 9 0 obj', heavy=LIGHT, first_wrong=False, **kw)), (1, None))
                self.assertEqual(_verdict(r4(head=b'(%) 3 0 obj', heavy=LIGHT, first_wrong=False, **kw)),
                                 (0, 'OverBudget: ' + TWO))
                self.assertEqual(_verdict(r4(heavy=LIGHT, **kw)), (0, 'OverBudget: ' + ODD))
                with mock.patch.object(identity.Identity, 'build'), mock.patch.object(identity.Identity, 'check'):
                    for head in (b'(%) 3 0 obj', b'(%) 3. 0 obj'):     # identity off: nothing else refuses
                        self.assertEqual(_verdict(r4(head=head, heavy=LIGHT, **kw)), (1, None))

    def test_the_same_file_without_a_second_page_passes(self):
        for name, kw in {**R4, **R4_CONTROLS}.items():
            with self.subTest(name):
                self.assertEqual(_verdict(r4(head=b'(%) 9 0 obj', first_wrong=False, **kw)), (1, None))
                self.assertEqual(_verdict(r4(head=b'(%) 9 0 obj', **kw)), (0, 'OverBudget: ' + ROW1))


def long_number(num=LONG, gen_word=b'0', row='heavy3'):
    """T1: a second page 3 (heavy) whose header is ``num gen_word obj``; the entry for 3 points at ``row``."""
    parts = _base() + [('heavy3', num + b' ' + gen_word + b' obj\n' + PAGE % 7)]
    return _table_file(parts, {1: '1', 2: '2', 3: row, 6: '6', 7: '7'})


def string_percent(lead=b'(%)', num=b'3.', first_wrong=True):
    parts = _base() + [('heavy3', lead + b' ' + num + b' 0 obj\n' + PAGE % 7)]
    return _table_file(parts, {1: '1', 2: '2', 3: 'light3', 6: '6', 7: '7'}, first_wrong=first_wrong)


def stream_percent(data=b'%X'):
    parts = _base() + [('8', b'8 0 obj\n<< /Length %d >>\nstream\n' % len(data) + data
                        + b'endstream endobj 3 0 obj\n' + PAGE % 7)]
    return _table_file(parts, {1: '1', 2: '2', 3: 'light3', 6: '6', 7: '7', 8: '8'})


def hidden_object_stream(decoy=b'/X (%) ', name=b'/ObjStm'):
    """T3: an object stream no entry names packing a second page 3 (heavy); ``decoy`` before its /Type."""
    member = b'3 0 ' + PAGE % 7 + b'\n'
    parts = _base() + [('9', b'9 0 obj\n' + _stream(member, b'<< ' + decoy + b'/Type ' + name + b' /N 1 /First 4'))]
    return _table_file(parts, {1: '1', 2: '2', 3: 'light3', 6: '6', 7: '7'})


def packed_member(word=LONG, wrong1=True, index=0):
    """Object stream 9 packs '3' (light page) then ``word`` (heavy); the entry for 3 says (9, ``index``)."""
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
    ent = {0: (0, 0, 255), 1: (1, off[2] if wrong1 else off[1], 0), 2: (1, off[2], 0), 3: (2, 9, index),
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
        self.assertEqual(_verdict(long_number(b'3000', row='light3')), (1, None))

    def test_a_row_on_another_numbers_header_is_refused(self):
        """Round 1: pypdf repairs a row for 3 that sits on '3000 0 obj' by searching; pdfium follows the row."""
        self.assertEqual(_verdict(long_number(b'3000')), (0, 'OverBudget: ' + TWO))

    def test_a_second_generation_is_a_second_copy(self):
        self.assertEqual(_verdict(long_number(b'3', b'1')), (0, 'OverBudget: ' + TWO))

    def test_object_stream_members(self):
        for wrong1 in (True, False):
            with self.subTest(rebuilds=wrong1):
                self.assertEqual(_verdict(packed_member(LONG, wrong1))[0], 0)     # pypdf's own word limit, or ours
        self.assertEqual(_verdict(packed_member(b'3', wrong1=False)), (0, 'OverBudget: ' + TWO))
        self.assertEqual(_verdict(packed_member(b'4', wrong1=False)), (1, None))
        self.assertEqual(_verdict(packed_member(b'4')), (0, 'OverBudget: ' + ROW1))


class T2PercentInAString(SimpleTestCase):
    def test_a_percent_in_a_string_or_hex_string_is_refused(self):
        for lead in (b'(%)', b'<%>', b'(a\\) %)', b'(x)', b'<ab>'):
            with self.subTest(lead=lead):
                self.assertEqual(_verdict(string_percent(lead)), (0, 'OverBudget: ' + ODD))
                self.assertEqual(_verdict(string_percent(lead, b'3', first_wrong=False)), (0, 'OverBudget: ' + TWO))

    def test_a_percent_in_a_string_before_a_unique_number_still_passes(self):
        self.assertEqual(_verdict(string_percent(b'(100%)', b'8', first_wrong=False)), (1, None))

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
        one.headers, one.owners, one.breaks, one.reader._counted.refused = {}, [], None, None
        one.reader._counted.getvalue = lambda: body
        one.build()
        self.assertEqual(len(one.headers[7]), identity.MAX_CANDIDATES)


class HighByteWhiteSpace(SimpleTestCase):
    """Review round 3, finding 1: pdfium reads 0x80 and 0xff as white space; the scans did not. Each file: pypdf
    reads the light page, pdfium (rebuilding, or after one bad row for an unused number, I5) the heavy one. The
    old gate accepted every one of them; the plain-space twins were already refused."""

    def test_a_header_split_or_ended_by_a_high_byte_is_a_second_copy(self):
        cases = {'I1': {'sep': b'\x80'}, 'I2': {'sep': b'\xff'}, 'I6': {'sep': b' ', 'after': b'\x80'},
                 'I6f': {'sep': b' ', 'after': b'\xff'}, 'I5': {'sep': b'\x80', 'rebuild': False},
                 'I5_ff': {'sep': b'\xff', 'rebuild': False},
                 'I5_after': {'sep': b' ', 'after': b'\x80', 'rebuild': False},
                 'I1_vt': {'sep': b'\x0b'}, 'I1_control': {'sep': b' '}}
        for name, kw in cases.items():
            with self.subTest(case=name):
                self.assertEqual(_verdict(gen.high_byte_header(**kw)), (0, 'OverBudget: ' + TWO))

    def test_a_good_row_does_not_make_it_pass(self):
        """I5g: no bad row, so pdfium does not rebuild and draws the light page too. Refused all the same (one
        number, two headers): an over-refusal kept on purpose."""
        pdf = gen.high_byte_header(b'\x80', rebuild=False, row6=b'0000000000 65535 f \n')
        self.assertEqual(_verdict(pdf), (0, 'OverBudget: ' + TWO))

    def test_a_trailer_key_ended_by_a_high_byte_is_read(self):
        for sep in (b'\x80', b'\xff', b'\x0b', b' '):
            with self.subTest(key='/Root', sep=sep):
                self.assertEqual(_verdict(gen.high_byte_trailer(b'/Root', sep)),
                                 (0, 'OverBudget: a trailer names another document root'))
            with self.subTest(key='/Encrypt', sep=sep):
                self.assertEqual(_verdict(gen.high_byte_trailer(b'/Encrypt', sep)),
                                 (0, 'OverBudget: a trailer names an encryption the gate did not read'))

    def test_an_object_stream_type_ended_by_a_high_byte_is_read(self):
        for type_name in (b'/ObjStm\x80', b'/ObjStm\xff', b'/Obj#53tm\x80', b'/ObjStm'):
            with self.subTest(type_name=type_name):
                self.assertEqual(_verdict(gen.orphan_object_stream(type_name) + gen.LONG_TAIL),
                                 (0, 'OverBudget: an object stream the cross-reference does not name'))

    def test_a_lone_header_with_high_byte_gaps_is_never_used(self):
        for sep in (b'\x80', b'\xff'):
            with self.subTest(sep=sep):
                self.assertEqual(_verdict(gen.gap_only_copy(sep))[0], 0)
        self.assertEqual(identity._PLAIN.match(b'\n5\x800 obj\n', 1), None)
        self.assertEqual(identity._PLAIN.match(b'\n5 0 obj\x80', 1), None)
        self.assertEqual(identity._PLAIN.match(b'\x0b5 0 obj\n', 1), None)
        self.assertEqual(identity._PLAIN.match(b'\x805 0 obj\n', 1).end(), 8)

    def test_light_controls_still_pass(self):
        """High bytes where no header, 'obj' word or watched name can form: inside stream data, after a word."""
        self.assertEqual(_verdict(gen.junk_in_stream(b'\x80\xff\x0b obj\x80 /Rootx\x80 ' * 500)), (1, None))
        self.assertEqual(_verdict(gen.names_in_comment(b'/Root 1 0 R \x80', 50)), (1, None))
        self.assertEqual(_verdict(gen.many_headers(1)), (1, None))

    def test_a_reference_ended_by_a_high_byte_is_refused(self):
        """`_REF` and `_LEAD` accept, so they stay strict: 'R<80>' and '/Root<80>1 0 R' are over-refused."""
        for name in (b'/Root 1 0 R\x80', b'/Root\x801 0 R'):
            with self.subTest(name=name):
                self.assertEqual(_verdict(gen.names_in_comment(name, 1)),
                                 (0, 'OverBudget: a trailer names another document root'))


class NameWork(SimpleTestCase):
    """Review round 3, finding 2: each watched name, and each '#' name, is charged about one judged word; each
    escape decoded about two more. Measured (probe J): a 8.8 MB file of 800,000 '/Root 1 0 R' took ~1.7 s and was
    charged ~2.6e8 units (~0.08 s); it is now charged ~4.8e9 (~1.4 s at ~0.3 ns a unit)."""

    @staticmethod
    def _work(pdf):
        reader = guards.GateReader(pdf)
        reader.pages[0].get_contents()               # the first lookup after open runs the name scan
        return reader._counted.work

    def _extra(self, name, n=1000):
        return self._work(gen.names_in_comment(name, n)) - self._work(gen.names_in_comment(name, 0))

    def test_a_watched_name_costs_two_judged_words(self):
        self.assertGreaterEqual(self._extra(b'/Root 1 0 R'), 1000 * 2 * identity._WORD_WORK)

    def test_an_escaped_name_costs_its_escapes(self):
        self.assertGreaterEqual(self._extra(b'/R#6f#6ft 1 0 R'), 1000 * (2 + 2 * 2) * identity._WORD_WORK)
        self.assertGreaterEqual(self._extra(b'/R#6f#6f#74#41 '), 1000 * (1 + 2 * 4) * identity._WORD_WORK)

    def test_a_long_escaped_name_is_charged_but_not_decoded(self):
        extra = self._extra(b'/#41#41#41#41#41#41#41#41#41 ')
        self.assertGreaterEqual(extra, 1000 * identity._WORD_WORK)
        self.assertLess(extra, 1000 * 2 * identity._WORD_WORK)

    def test_other_names_cost_only_their_bytes(self):
        self.assertLess(self._extra(b'/Rooty /A /ObjStmX '), 1000 * identity._WORD_WORK)

    def test_a_file_of_watched_names_is_refused_past_the_budget(self):
        """Without the base allowance, each '/Root 1 0 R' (11 bytes: 3,300 units of budget) costs more than it
        brings, so such a file is refused near the budget, whatever its size."""
        with mock.patch.object(guards, 'LOOKUP_WORK_BASE', 0):
            n, why = _verdict(gen.names_in_comment(b'/Root 1 0 R', 20_000))
        self.assertEqual(n, 0)
        self.assertIn('OverBudget', why)


class NameEscapes(SimpleTestCase):
    """Review round 4 (R8, probe C): pdfium decodes '#' and ANY two bytes, a non-hex byte counting as 0, so
    '/Encry#7Gt' is '/Encrypt' to pdfium only. The old gate accepted that RC4 forge (pypdf drew GENUINE, pdfium
    FORGED). A name with a '#' that is not two hex digits is now refused: as pypdf parses it (any object, the
    trailer too), or, in raw bytes, where some reader would read it as a watched name."""

    BAD_NAME = 'OverBudget: a name the gate and the renderer may decode differently'

    def test_a_trailer_key_with_a_non_hex_escape_is_refused(self):
        """The regression: the old gate accepted it as a plain light file, (1, None)."""
        self.assertEqual(_verdict(gen.named_trailer(b'/Encry#7Gt')), (0, self.BAD_NAME))

    def test_one_hex_digit_then_a_non_hex_byte_in_a_page_key_is_refused(self):
        for key in (b'/Ty#7Ge', b'/Ty#7\x0be', b'/X#7G'):
            with self.subTest(key=key):
                pdf = gen.page_key(key) if key.startswith(b'/Ty') else gen.named_trailer(key)
                self.assertEqual(_verdict(pdf), (0, self.BAD_NAME))

    def test_a_hash_at_the_end_of_a_token_is_refused(self):
        """pdfium keeps a '#' with fewer than two bytes after it; pypdf decodes '#7' as 0x07. Strict: refused."""
        for key in (b'/Ty#7', b'/Type#'):
            with self.subTest(key=key):
                self.assertEqual(_verdict(gen.page_key(key)), (0, self.BAD_NAME))
        for key in (b'/Encry#7', b'/Encry#7\x80t'):
            with self.subTest(key=key):
                self.assertEqual(_verdict(gen.named_trailer(key)), (0, self.BAD_NAME))

    def test_raw_bytes_a_reader_reads_as_a_watched_name_are_refused(self):
        """A stray trailer (pdfium rebuilds and merges it) and the file's last bytes: no parse reaches them."""
        for key in (b'/Encry#7Gt', b'/Encry#7\x0bt'):
            with self.subTest(stray=key):
                self.assertEqual(_verdict(gen.high_byte_trailer(key, b' ')),
                                 (0, 'OverBudget: a name the renderer may read as /Encrypt'))
        self.assertEqual(_verdict(gen.named_trailer(b'/X', b'%/Encry#7Gt')),
                         (0, 'OverBudget: a name the renderer may read as /Encrypt'))

    def test_a_hash_at_the_end_of_the_file_that_no_reader_reads_as_watched_passes(self):
        for tail in (b'%/Encrypt#7', b'%/Encrypt#', b'%/Encry#7G'):
            with self.subTest(tail=tail):
                self.assertEqual(_verdict(gen.named_trailer(b'/X', tail)), (1, None))

    def test_valid_escapes_behave_as_before(self):
        for key in (b'/Ty#70e', b'/T#79pe', b'/Type'):
            with self.subTest(key=key):
                self.assertEqual(_verdict(gen.page_key(key)), (1, None))
        for key in (b'/Encry#70t', b'/Encrypt'):
            with self.subTest(key=key):
                self.assertEqual(_verdict(gen.named_trailer(key)),
                                 (0, 'FileNotDecryptedError: File has not been decrypted'))
        self.assertEqual(_verdict(gen.high_byte_trailer(b'/Encry#70t', b' ')),
                         (0, 'OverBudget: a trailer names an encryption the gate did not read'))

    def test_the_two_decoders(self):
        self.assertEqual(identity._pdfium_name(b'/Encry#7Gt'), b'/Encrypt')
        self.assertEqual(identity._pdfium_name(b'/Encry#70t'), b'/Encrypt')
        self.assertEqual(identity._pdfium_name(b'/X#3\x0b'), b'/X0')
        self.assertEqual(identity._pdfium_name(b'/Ty#7'), b'/Ty#7')          # fewer than two bytes: kept
        self.assertEqual(identity._pdfium_name(b'/Type#'), b'/Type#')
        self.assertEqual(identity._gate_name(b'/Encry#7Gt'), b'/Encry#7Gt')
        self.assertEqual(identity._gate_name(b'/Encry#70t'), b'/Encrypt')

    def test_name_disagrees(self):
        for name, after in (('/Encry#7Gt', b' '), ('/Ty\x07', b' '), ('/X', b'\x0b'), ('/A#', b' '), ('/\n', b'')):
            with self.subTest(name=name, after=after):
                self.assertTrue(identity.name_disagrees(name, after))
        for name, after in (('/Type', b' '), ('/Type', b'/'), ('/Type', b''), ('/', b' ')):
            with self.subTest(name=name, after=after):
                self.assertFalse(identity.name_disagrees(name, after))

    def test_the_name_check_is_the_gate_s_own(self):
        """The hook on pypdf's name read is installed once, process-wide (as `_bytes_io` is), and holds no state:
        it acts only on a `GateReader`'s own bytes (`_CountedBytes`, or `_MeteredData` charged to one), so no thread
        can switch it on or off for another. A plain PdfReader reads '/Ty#7Ge' as pypdf always did: after a gate
        read, and in another thread while a gate read is held inside its check of that very name."""
        bad = gen.page_key(b'/Ty#7Ge')

        def plain_keys():
            return set(PdfReader(io.BytesIO(bad)).pages[0].keys())

        hook = NameObject.read_from_stream
        self.assertEqual(_verdict(bad), (0, self.BAD_NAME))
        self.assertIn('/Ty#7Ge', plain_keys())                     # after a gate read
        self.assertIs(NameObject.read_from_stream, hook)          # nothing installed or removed per read

        inside, done, seen, real = threading.Event(), threading.Event(), [], identity.name_disagrees

        def held(name, after):                                    # the gate thread waits here, mid-check
            if name == '/Ty#7Ge' and not inside.is_set():
                inside.set()
                done.wait(10)
            return real(name, after)

        def gate():
            try:
                guards.GateReader(bad).pages[0].keys()
            except guards.OverBudget as e:
                seen.append(str(e))

        with mock.patch.object(guards, 'name_disagrees', held):
            t = threading.Thread(target=gate)
            t.start()
            try:
                self.assertTrue(inside.wait(10))
                self.assertIn('/Ty#7Ge', plain_keys())             # another thread, during the gate read
            finally:
                done.set()
                t.join(10)
        self.assertEqual(seen, ['a name the gate and the renderer may decode differently'])
        self.assertIn('/Ty#7Ge', plain_keys())
