"""TD-710: three crafted shapes made pypdf do unbounded work per object lookup inside the gate, uncounted, and held
a web worker for 30 s to minutes: a /Length too short (pypdf walks EVERY cross-reference row to find where each
stream ends; 20,000 streams: 130 s, ACCEPTED), a /Length past the end of the file (each lookup copies the rest of
the file; 5,000 streams: 31 s, ACCEPTED), and a number an object stream does not hold (pypdf parsed the whole
stream index again for every lookup; 2,000 lookups in a 19,000-entry stream: 461 s). `GateReader` now charges that
work to one lookup budget scaled to the file size, and parses an object stream once.

Every PDF here is built in code. The guard is pinned by the operations it counts (rows walked, large reads,
object-stream parses), never by time (TD-693).
"""
import io
import re
import zlib
from unittest import mock

from django.test import SimpleTestCase
from pypdf import PdfReader
from pypdf.errors import LimitReachedError
from pypdf.generic import ArrayObject, DictionaryObject, NullObject

from apps.scholarship import pdf_layer_guards, pdf_render_check, pdf_xref_rows
from apps.scholarship.pdf_layer_guards import GateReader, OverBudget, _CountedBytes

FIRST = 10                          # the first content stream's object number
PAD = 1_000_000                     # bytes after the content streams: each read to the end copies all of them
CAP = 'lookup work past the cap'
SMALL_BASE = 200_000_000            # a thirtieth of the real base, so each hostile file can stay small


STREAM = 'a stream the gate and the renderer may bound differently'


def _lengths_unchecked():
    """OCR-20 review round 3 part 2: the gate now refuses a stream that does not end exactly where its /Length
    says (`pdf_dict_keys._stream_start` / `_stream_end`), so every wrong-length shape here is refused for that
    first. These tests pin the lookup budget that still stands behind it, so they switch the length rule off; each
    also checks that the real gate refuses the file for its length."""
    return mock.patch('apps.scholarship.pdf_dict_keys._stream_start', return_value=None)


def _small_base():
    """The cap with a smaller fixed part: the work charged per lookup is what these tests pin, and the real base
    only adds a fixed amount (about 2 s) before the same refusal."""
    return mock.patch.object(pdf_layer_guards, 'LOOKUP_WORK_BASE', SMALL_BASE)


def _same(obj) -> str:
    """``repr(obj)`` without the reader's id inside each reference."""
    return re.sub(r'IndirectObject\((\d+), (\d+), \d+\)', r'R(\1, \2)', repr(obj))


def _pdf(mode: str, n: int, pad: int = 0) -> bytes:
    """One page whose /Contents lists n content streams ('0 g'), then ``pad`` bytes of comment. 'shortlen': each
    says /Length 1; 'overlen': each says /Length 70000000; 'plain': each length is right."""
    out, rows = bytearray(b'%PDF-1.5\n'), {}

    def obj(num, body):
        rows[num] = len(out)
        out.extend(b'%d 0 obj\n' % num + body + b'\nendobj\n')

    obj(1, b'<< /Type /Catalog /Pages 2 0 R >>')
    obj(2, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    refs = b' '.join(b'%d 0 R' % (FIRST + k) for k in range(n))
    obj(3, b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents [' + refs + b'] >>')
    length = {'shortlen': 1, 'overlen': 70_000_000, 'plain': 3}[mode]
    for k in range(n):
        obj(FIRST + k, b'<< /Length %d >>\nstream\n0 g\nendstream' % length)
    if pad:
        out.extend(b'%' + b' ' * pad + b'\n')
    xref = len(out)
    body = b'xref\n0 1\n0000000000 65535 f \n' + b''.join(
        b'%d 1\n%010d 00000 n \n' % (num, rows[num]) for num in sorted(rows))
    out.extend(body + b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (FIRST + n, xref))
    return bytes(out)


def _rebuild_pdf(n: int) -> bytes:
    """Review round 3: n streams that each say /Length 1, behind a cross-reference table whose size is not a
    number (``0 (x)``), so pypdf REBUILDS the table as it opens the file and reads every object: each short
    /Length walks every row while the file opens (n x n rows)."""
    out = bytearray(b'%PDF-1.5\n')
    out += b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
    out += b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
    out += b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R >>\nendobj\n' % FIRST
    for k in range(n):
        out += b'%d 0 obj\n<< /Length 1 >>\nstream\n0 g\nendstream\nendobj\n' % (FIRST + k)
    xref = len(out)
    out += b'xref\n0 (x)\ntrailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (FIRST + n, xref)
    return bytes(out)


def _rebuild_objstm_pdf(index: bytes, streams: int = 1, n: int = 1) -> bytes:
    """Gap 2: ``streams`` Flate object streams whose decoded data is ``index``, behind a table whose size is not a
    number, so pypdf rebuilds the table as it opens the file and scans each stream's index through its own
    BytesIO copy (_reader.py:1583), a byte at a time. A long index of ``9 1 `` compresses to almost nothing."""
    out = bytearray(b'%PDF-1.5\n')
    out += b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
    out += b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n'
    out += b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R >>\nendobj\n' % FIRST
    out += b'%d 0 obj\n<< /Length 3 >>\nstream\n0 g\nendstream\nendobj\n' % FIRST
    body = zlib.compress(index, 9)
    for j in range(streams):
        out += b'%d 0 obj\n<< /Type /ObjStm /N %d /First %d /Filter /FlateDecode /Length %d >>\nstream\n' % (
            20 + j, n, index.index(b'\n') + 1 if b'\n' in index else 4, len(body))
        out += body + b'\nendstream\nendobj\n'
    xref = len(out)
    out += b'xref\n0 (x)\ntrailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (20 + streams, xref)
    return bytes(out)


def _xref_stream_pdf(n: int) -> bytes:
    """Gap 2: one cross-reference stream of ``n`` entries (W [1 2 1]); pypdf reads each field through its own
    BytesIO copy as it opens the file (_reader.py:1430). Entries past the first five name an absent object stream."""
    import struct
    out, offs = bytearray(b'%PDF-1.5\n'), []
    for body in (b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                 b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>'):
        offs.append(len(out))
        out += b'%d 0 obj\n%s\nendobj\n' % (len(offs), body)
    xref = len(out)
    rows = struct.pack('>BHB', 0, 0, 255) + b''.join(struct.pack('>BHB', 1, o, 0) for o in offs + [xref])
    rows += struct.pack('>BHB', 2, 999, 0) * (n - 5)
    raw = zlib.compress(rows, 9)
    out += b'4 0 obj\n<< /Type /XRef /Size %d /W [1 2 1] /Root 1 0 R /Filter /FlateDecode /Length %d >>\nstream\n' % (
        n, len(raw))
    out += raw + b'\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n' % xref
    return bytes(out)


def _clamped_index_pdf(pairs: int) -> bytes:
    """Gap 3: one cross-reference stream whose /Index adds ``pairs`` pairs ``0 9`` past its 5 rows, each of which
    pypdf clamps with a logger warning (_reader.py:1385). (A catalog key named twice once added a warning each; since
    OCR-20 review round 1 the gate refuses the file at the first one, test_ocr20_dup_keys.)"""
    out = bytearray(b'%PDF-1.5\n')
    offs = []
    for body in (b'<< /Type /Catalog /Pages 2 0 R >>',
                 b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                 b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>'):
        offs.append(len(out))
        out += b'%d 0 obj\n%s\nendobj\n' % (len(offs), body)
    xref = len(out)
    rows = bytes([0, 0, 0, 255]) + b''.join(bytes([1, o >> 8, o & 255, 0]) for o in offs + [xref])
    out += b'4 0 obj\n<< /Type /XRef /Size 5 /W [1 2 1] /Root 1 0 R /Index [0 5%s] /Length %d >>\nstream\n' % (
        b' 0 9' * pairs, len(rows))
    out += rows + b'\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n' % xref
    return bytes(out)


def _metered_reads(fn):
    """(what ``fn`` returned or raised, reads made through `_MeteredData`)."""
    real, reads = pdf_layer_guards._MeteredData.read, []

    def read(self, size=-1):
        got = real(self, size)
        reads.append(len(got))
        return got

    with mock.patch.object(pdf_layer_guards._MeteredData, 'read', read):
        try:
            got = fn()
        except Exception as e:  # noqa: BLE001 - the test reads which
            got = e
    return got, reads


def _objstm_pdf(entries: int, contents: list, page_in_stream: bool = False, first: bytes = b'1',
                type_ref: bool = False, at=None, extra=None) -> bytes:
    """An object stream (object 5) holding ``entries`` small objects numbered 100 on; the cross-reference stream
    maps every number in ``contents`` (the page's /Contents, refs at generation 0) to it. A number of 100 or more
    but not under 100 + entries is mapped there but missing from it. ``page_in_stream``: the catalog, page tree
    and page are packed in the stream too (numbers 1-3), and /Contents points at a real stream (object 4).
    ``first``: the body of object 100 (a large one makes a parse bomb: tiny compressed, huge decoded).
    ``type_ref``: the stream's /Type is a reference (object 7) that resolves to /ObjStm, which pypdf accepts.
    ``at(j)``: the offset index entry j points at instead of its own (None keeps its own). ``extra``: more
    cross-reference entries, {number: (type, field 2, field 3)}."""
    out, rows = bytearray(b'%PDF-1.5\n'), {}

    def obj(num, body):
        rows[num] = len(out)
        out.extend(b'%d 0 obj\n' % num + body + b'\nendobj\n')

    refs = b' '.join(b'%d 0 R' % n for n in contents)
    page = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents [' + refs + b'] >>']
    packed = [(100 + j, first if j == 0 else b'1') for j in range(entries)]
    packed += [(k + 1, b) for k, b in enumerate(page)] if page_in_stream else []
    if not page_in_stream:
        for k, b in enumerate(page):
            obj(k + 1, b)
    obj(4, b'<< /Length 3 >>\nstream\n0 g\nendstream')
    idx, data = [], bytearray()
    for j, (num, b) in enumerate(packed):
        off = at(j) if at else None
        idx.append(b'%d %d' % (num, len(data) if off is None else off))
        data.extend(b + b' ')
    head = b' '.join(idx) + b' '
    comp = zlib.compress(head + bytes(data))
    if type_ref:
        obj(7, b'/ObjStm')
    obj(5, b'<< /Type %s /N %d /First %d /Length %d /Filter /FlateDecode >>\nstream\n'
        % (b'7 0 R' if type_ref else b'/ObjStm', len(packed), len(head), len(comp)) + comp + b'\nendstream')
    entry = {n: (1, rows[n], 0) for n in rows}
    entry.update({num: (2, 5, j) for j, (num, _b) in enumerate(packed)})
    entry.update({n: (2, 5, len(packed) + 5) for n in contents if n not in entry})
    entry.update(extra or {})
    xs = len(out)
    entry[6] = (1, xs, 0)
    keys = sorted(entry)
    table = b''.join(bytes([entry[n][0]]) + entry[n][1].to_bytes(4, 'big') + entry[n][2].to_bytes(2, 'big')
                     for n in keys)
    comp = zlib.compress(table)
    out.extend(b'6 0 obj\n<< /Type /XRef /Size %d /W [1 4 2] /Index [%s] /Root 1 0 R /Length %d /Filter '
               b'/FlateDecode >>\nstream\n' % (keys[-1] + 1, b' '.join(b'%d 1' % n for n in keys), len(comp))
               + comp + b'\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n' % xs)
    return bytes(out)


def _packed_pdf(pages: int = 20, links: int = 30, tags: int = 20, per_stream: int = 100) -> bytes:
    """A genuine-shaped PDF, packed as qpdf packs it by default (100 objects to an object stream, one
    cross-reference stream): each page has its own text content stream, its own font (font, descriptor, widths),
    ``links`` link annotations and ``tags`` structure elements. 20 pages: about 1,100 packed objects, 50 KB."""
    packed, streams, kids, elems = {}, {}, [], []
    nums = iter(range(1, 10 ** 6))
    cat, tree, sroot = next(nums), next(nums), next(nums)

    def refs(ns):
        return b' '.join(b'%d 0 R' % n for n in ns)

    for p in range(pages):
        page, content, font, desc, widths = (next(nums) for _ in range(5))
        streams[content] = b'BT /F1 11 Tf 72 760 Td 14 TL ' + b''.join(
            b'(Line %d of page %d: synthetic text for a size test.) Tj T* ' % (k, p) for k in range(40)) + b'ET'
        packed[desc] = (b'<< /Type /FontDescriptor /FontName /ABCDEF+Font%d /Flags 32 /FontBBox [-500 -300 1300 1000]'
                        b' /ItalicAngle 0 /Ascent 900 /Descent -250 /CapHeight 700 /StemV 80 >>' % p)
        packed[widths] = b'[' + b' '.join(b'%d' % (200 + (k * 37 + p) % 700) for k in range(224)) + b']'
        packed[font] = (b'<< /Type /Font /Subtype /TrueType /BaseFont /ABCDEF+Font%d /FirstChar 32 /LastChar 255 /Widths'
                        b' %d 0 R /FontDescriptor %d 0 R /Encoding /WinAnsiEncoding >>' % (p, widths, desc))
        annots = [next(nums) for _ in range(links)]
        for a, n in enumerate(annots):
            packed[n] = (b'<< /Type /Annot /Subtype /Link /Rect [72 %d 300 %d] /Border [0 0 0] /P %d 0 R /A << /S /URI'
                         b' /URI (https://example.org/p%d/a%d) >> >>' % (700 - 14 * a, 712 - 14 * a, page, p, a))
        for s in range(tags):
            elems.append(next(nums))
            packed[elems[-1]] = b'<< /Type /StructElem /S /P /P %d 0 R /Pg %d 0 R /K %d >>' % (sroot, page, s)
        packed[page] = (b'<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] /Contents %d 0 R /Resources << /Font'
                        b' << /F1 %d 0 R >> >> /Annots [%s] >>' % (tree, content, font, refs(annots)))
        kids.append(page)
    packed[cat] = b'<< /Type /Catalog /Pages %d 0 R /StructTreeRoot %d 0 R /MarkInfo << /Marked true >> >>' % (
        tree, sroot)
    packed[tree] = b'<< /Type /Pages /Kids [%s] /Count %d >>' % (refs(kids), pages)
    packed[sroot] = b'<< /Type /StructTreeRoot /K [%s] >>' % refs(elems)

    out, entry = bytearray(b'%PDF-1.5\n'), {0: (0, 0, 65535)}

    def stream_obj(num, head, raw):
        comp = zlib.compress(raw)
        entry[num] = (1, len(out), 0)
        out.extend(b'%d 0 obj\n<< %s /Length %d /Filter /FlateDecode >>\nstream\n' % (num, head, len(comp)) + comp
                   + b'\nendstream\nendobj\n')

    for num, raw in streams.items():
        stream_obj(num, b'', raw)
    order = sorted(packed)
    for i in range(0, len(order), per_stream):
        group, stm = order[i:i + per_stream], next(nums)
        idx, body = [], bytearray()
        for j, num in enumerate(group):
            idx.append(b'%d %d' % (num, len(body)))
            body.extend(packed[num] + b'\n')
            entry[num] = (2, stm, j)
        head = b' '.join(idx) + b'\n'
        stream_obj(stm, b'/Type /ObjStm /N %d /First %d' % (len(group), len(head)), head + bytes(body))
    xs, size = next(nums), max(entry) + 2
    entry[xs] = (1, len(out), 0)
    table = b''.join(bytes([entry[n][0]]) + entry[n][1].to_bytes(4, 'big') + entry[n][2].to_bytes(2, 'big')
                     for n in range(size))
    comp = zlib.compress(table)
    out.extend(b'%d 0 obj\n<< /Type /XRef /Size %d /W [1 4 2] /Root %d 0 R /Length %d /Filter /FlateDecode >>\n'
               b'stream\n' % (xs, size, cat, len(comp)) + comp + b'\nendstream\nendobj\nstartxref\n%d\n%%%%EOF\n'
               % entry[xs][1])
    return bytes(out)


def _upload_shares(data: bytes) -> tuple:
    """(the gate's verdict, readers opened, the most lookup work any of them used as a share of its cap) for one
    upload: the gate, then each page check that opens its own reader (as the census measures it)."""
    from apps.scholarship import pdf_pages, pdf_rules_pages
    real, opened = _CountedBytes.__init__, []

    def init(self, raw):
        real(self, raw)
        opened.append(self)

    pdf_pages._layer_memo_clear()
    try:
        with mock.patch.object(_CountedBytes, '__init__', init):
            verdict = _gate(data)
            pdf_pages.pdf_page_count(data)
            pdf_pages.pdf_text_layer(data)
            pdf_pages.pdf_page_texts(data, 30)
            pdf_rules_pages.pdf_rules_page_texts(data, 3)
            pdf_rules_pages.pdf_page1_layout(data)
    finally:
        pdf_pages._layer_memo_clear()
    caps = [pdf_layer_guards.LOOKUP_WORK_BASE + pdf_layer_guards.LOOKUP_WORK_PER_BYTE * s.size for s in opened]
    return verdict, len(opened), max(s.work / cap for s, cap in zip(opened, caps))


def _gate(data: bytes):
    """(page count, refusal or None) of the real gate over the first 30 pages."""
    return pdf_render_check.render_refusal(data, lambda k: range(min(k, 30)))


def _walks(data: bytes):
    """(refusal, times pypdf walked the rows to find a stream's end) of the gate over ``data``."""
    real = DictionaryObject._get_next_object_position
    with mock.patch.object(DictionaryObject, '_get_next_object_position', side_effect=real) as walk:
        _n, why = _gate(data)
    return why, walk.call_count


def _big_reads(data: bytes, at_least: int):
    """(refusal, reads of ``at_least`` bytes or more) of the gate over ``data``."""
    real, big = _CountedBytes.read, []

    def read(self, size=-1):
        got = real(self, size)
        if len(got) >= at_least:
            big.append(len(got))
        return got

    with mock.patch.object(_CountedBytes, 'read', read):
        _n, why = _gate(data)
    return why, len(big)


def _stream_parses(fn):
    """(what ``fn`` returned or raised, how often pypdf parsed an object stream)."""
    real = PdfReader._get_object_from_stream
    with mock.patch.object(PdfReader, '_get_object_from_stream', autospec=True, side_effect=real) as parse:
        try:
            got = fn()
        except Exception as e:  # noqa: BLE001 - the test reads which
            got = e
    return got, parse.call_count


def _work(data: bytes) -> tuple:
    """(lookup work, its cap) for opening ``data`` and resolving page 1's /Contents."""
    reader = GateReader(data)
    for ref in reader.pages[0]['/Contents']:
        ref.get_object()
    s = reader.stream
    return s.work, pdf_layer_guards.LOOKUP_WORK_BASE + pdf_layer_guards.LOOKUP_WORK_PER_BYTE * s.size


class HostileLookupsAreBounded(SimpleTestCase):

    def test_short_lengths_are_refused_after_a_few_row_walks(self):
        n = 2000                            # small enough to open inside the small base, so the walks are what refuse
        why, walks = _walks(_pdf('shortlen', n))
        self.assertEqual((why, walks), ('OverBudget: ' + STREAM, 1))   # the length rule: at the first stream
        with _small_base(), _lengths_unchecked():
            why, walks = _walks(_pdf('shortlen', n))
        self.assertIn(CAP, why or '')                                 # was ACCEPTED after one walk per stream
        self.assertGreater(walks, 0)
        self.assertLess(walks, n // 4)

    def test_lengths_past_the_end_are_refused_after_a_few_large_reads(self):
        n = 2000
        self.assertEqual(_big_reads(_pdf('overlen', n, PAD), PAD)[0], 'OverBudget: ' + STREAM)
        with _small_base(), _lengths_unchecked():
            why, big = _big_reads(_pdf('overlen', n, PAD), PAD)
        self.assertIn(CAP, why or '')                                 # was ACCEPTED after a copy per stream
        self.assertLess(big, n // 4)

    def test_object_stream_misses_parse_the_stream_once(self):
        data = _objstm_pdf(5000, [90000] * 300)
        (_n, why), parses = _stream_parses(lambda: _gate(data))
        self.assertEqual(parses, 1)                                   # was one whole parse per lookup
        self.assertIn('object 90000 has a cross-reference row that is not its one copy', why or '')   # round 1

    def test_distinct_misses_in_one_stream_parse_it_once(self):
        data = _objstm_pdf(5000, list(range(90000, 90300)))
        _got, parses = _stream_parses(lambda: _gate(data))
        self.assertEqual(parses, 1)

    def test_each_read_of_an_object_streams_decoded_data_is_charged_as_it_is_made(self):
        from apps.scholarship.pdf_layer_guards import _MeteredData
        reader = GateReader(_objstm_pdf(3, [100], first=b'[' + b'0 ' * 2000 + b']'))
        real, reads = _MeteredData.read, []

        def read(self, size=-1):
            got = real(self, size)
            reads.append(len(got))
            return got

        before = reader.stream.work
        with mock.patch.object(_MeteredData, 'read', read):
            reader.get_object(100)
        self.assertGreater(len(reads), 2000)                          # pypdf reads a byte or a token at a time
        metered = pdf_layer_guards._PARSE_CALL_WORK * len(reads) + sum(reads)
        self.assertGreaterEqual(reader.stream.work - before, metered)  # plus the file reads that load the stream
        self.assertLess(reader.stream.work - before - metered, metered // 100)

    def test_index_entries_at_one_offset_pay_for_each_parse(self):
        """Review round 2 (HIGH): entries all at offset 0 of one array: pypdf parses the array once per entry. The
        charge was per decoded byte, once, so round 1 ran all 40 parses of 40 entries inside the cap."""
        data = _objstm_pdf(120, [100], first=b'[' + b'0 ' * 5000 + b']', at=lambda j: 0)
        self.assertLess(len(data), 2_000)
        real = ArrayObject.read_from_stream
        with mock.patch.object(ArrayObject, 'read_from_stream', side_effect=real) as arrays:
            _n, why = _gate(data)                                     # the real cap
        self.assertIn(CAP, why or '')
        self.assertLess(arrays.call_count, 60)                        # 30 under the 3x cap, of 120

    def test_an_entry_at_each_bracket_of_nested_arrays_pays_depth_times_payload(self):
        depth = 200
        data = _objstm_pdf(depth, [100], first=b'[' * depth + b'0 ' * 2000 + b']' * depth,
                           at=lambda j: j if j < depth else None)
        self.assertIn(CAP, _gate(data)[1] or '')                      # was inside the cap (its bytes charged once)

    def test_an_object_stream_inside_an_object_stream_is_refused_before_any_parse(self):
        """Review round 2 (MEDIUM): object 200 sits in object stream 100, which sits in stream 5. pypdf parsed all
        of 5 to reach 100, uncharged, before `page_tree_check` saw the nesting."""
        inner = b'<< /Type /ObjStm /N 1 /First 6 /Length 8 >>\nstream\n200 0 1 \nendstream'
        data = _objstm_pdf(3, [200], first=inner, extra={200: (2, 100, 0)})
        with self.assertRaisesRegex(OverBudget, STREAM):              # round 3 part 2: a stream in an object
            GateReader(data)                                          # stream refuses the file as it opens
        with _lengths_unchecked():
            reader = GateReader(data)
            got, parses = _stream_parses(lambda: reader.get_object(200))
        self.assertIsInstance(got, OverBudget)
        self.assertEqual(parses, 0)

    def test_a_parse_bomb_inside_an_object_stream_is_refused(self):
        bomb = b'[' + (b'[' + b'0 ' * 50_000 + b']') * 10 + b']'      # 1 MB decoded from about 1 KB
        data = _objstm_pdf(3, [100, 101], first=bomb)
        self.assertLess(len(data), 10_000)
        self.assertIn(CAP, _gate(data)[1] or '')                      # the real cap: was ACCEPTED after the parse
        # OCR-12 (2026-11-24): a /Type by reference (object 7 is the name /ObjStm, which pypdf accepts) puts an
        # /ObjStm name outside any stream the cross-reference names, so the identity check refuses it at open,
        # before any parse, bomb or not
        orphan = 'an object stream the cross-reference does not name'
        for first in (bomb, b'1'):
            with self.subTest(bomb=first == bomb):
                self.assertEqual(_gate(_objstm_pdf(3, [100, 101], first=first, type_ref=True))[1],
                                 'OverBudget: ' + orphan)
        self.assertEqual(PdfReader(io.BytesIO(_objstm_pdf(3, [100, 101], type_ref=True))).get_object(101), 1)

    def test_rows_walked_while_the_file_opens_are_charged(self):
        """Review round 3 (HIGH): the rows were charged through ``reader.stream``, which pypdf sets only once the
        file is open, so a rebuilt table's walks were free (16,000 streams: 60 s to open, at 41 % of the cap;
        8,000: ACCEPTED). Now each walk is charged from the first byte, and the open itself is refused."""
        n = 2000                            # under the small base: about 390 walks of 2,000
        rebuilds, real = [], PdfReader._rebuild_xref_table

        def rebuild(reader, stream):
            rebuilds.append(1)
            return real(reader, stream)

        self.assertEqual(_gate(_rebuild_pdf(n))[1], 'OverBudget: ' + STREAM)   # the real gate: its lengths
        walk = DictionaryObject._get_next_object_position
        with _small_base(), _lengths_unchecked(), mock.patch.object(PdfReader, '_rebuild_xref_table', rebuild), \
                mock.patch.object(DictionaryObject, '_get_next_object_position', side_effect=walk) as walks:
            with self.assertRaisesRegex(OverBudget, CAP):
                GateReader(_rebuild_pdf(n))
        self.assertEqual(len(rebuilds), 1)                            # the shape is the rebuild, as it opens
        self.assertGreater(walks.call_count, 0)
        self.assertLess(walks.call_count, n // 4)                     # was every one of the n walks, then opened
        with _small_base(), _lengths_unchecked():
            self.assertIn(CAP, _gate(_rebuild_pdf(n))[1] or '')       # the budget behind the length rule

    def test_a_refusal_pypdf_swallows_as_it_opens_still_refuses(self):
        """pypdf catches broad exceptions in some recovery paths as it opens (a failed rebuild is dropped,
        _reader.py:1237): an `OverBudget` raised in there is raised again when pypdf returns, even if pypdf
        then reads nothing more. Here the whole open swallows it, the worst case."""
        real = PdfReader.read

        def swallowing(reader, stream):
            try:
                real(reader, stream)
            except Exception:  # noqa: BLE001 - what pypdf's recovery does
                pass

        with _small_base(), _lengths_unchecked(), mock.patch.object(PdfReader, 'read', swallowing):
            with self.assertRaisesRegex(OverBudget, CAP):
                GateReader(_rebuild_pdf(2000))

    def test_a_rebuilt_tables_object_stream_index_is_charged_as_it_opens(self):
        """Gap 2 (review round 4, MAIN): a rebuilt table scans each object stream's index through pypdf's own
        BytesIO copy, a byte at a time, uncounted: 70 MB of ``9 1 `` in a 68 KB file held a reader 70 s and was
        ACCEPTED. Each read is now charged as `_MeteredData`'s are, so the open is refused after a fraction."""
        size = 1_000_000                    # 250,000 index entries, about a million one-byte reads
        data = _rebuild_objstm_pdf(b'9 1 ' * (size // 4))
        self.assertLess(len(data), 5_000)
        with _small_base():
            got, reads = _metered_reads(lambda: GateReader(data))
        self.assertIsInstance(got, OverBudget)                        # was opened, every read free
        self.assertIn(CAP, str(got))
        self.assertGreater(len(reads), 0)
        self.assertLess(len(reads), size // 20)                       # about 16,700 under the small base
        self.assertIsNone(getattr(pdf_layer_guards._PARSING, 'meter', None))   # restored after the refusal
        with _small_base():
            self.assertIn(CAP, _gate(data)[1] or '')                  # the real gate refuses it

    def test_a_cross_reference_streams_entries_are_charged_as_it_opens(self):
        """Gap 2 (SMALL): pypdf reads each field of a cross-reference stream through its own BytesIO copy (it caps
        the entries at 2M; 2M in an 8 KB file held a reader 9.8 s before the gate refused it). Charged now."""
        n = 100_000                         # 300,000 field reads
        data = _xref_stream_pdf(n)
        self.assertLess(len(data), 5_000)
        with _small_base():
            got, reads = _metered_reads(lambda: GateReader(data))
        self.assertIsInstance(got, OverBudget)                        # was opened, every read free
        self.assertIn(CAP, str(got))
        self.assertGreater(len(reads), 0)
        self.assertLess(len(reads), n // 5)                           # about 16,700 under the small base

    def test_pypdf_copies_outside_a_gate_reader_are_plain_and_free(self):
        """The patched name serves all of pypdf: with no `GateReader` opening or parsing on this thread, it is a
        plain BytesIO, so pypdf used directly (invoices, splitting results) is never charged or refused."""
        self.assertIs(type(pdf_layer_guards._bytes_io(b'abc')), io.BytesIO)
        data = _xref_stream_pdf(50_000)
        with _small_base():
            got, reads = _metered_reads(lambda: PdfReader(io.BytesIO(data)))
        self.assertIsInstance(got, PdfReader)
        self.assertEqual(reads, [])

    def test_pypdf_repair_warnings_make_no_log_records(self):
        """Gap 3: pypdf logs a warning for every repair, and a file can repeat one at will (48,000 clamped /Index
        pairs x 5 streams took 18.7 s under production logging, 92 % of the cap, ACCEPTED, ~240k log lines).
        The "pypdf" logger now sits at CRITICAL, which pypdf never uses: the repairs still happen, no record is made."""
        import logging
        import pypdf._reader
        import pypdf.generic._data_structures as ds
        records, calls = [], []

        class Keep(logging.Handler):
            def emit(self, record):
                records.append(record)

        def counted(real):
            def warn(*args, **kwargs):
                calls.append(1)
                return real(*args, **kwargs)
            return warn

        data = _clamped_index_pdf(700)
        keep = Keep(logging.DEBUG)
        log = logging.getLogger('pypdf')
        log.addHandler(keep)
        try:
            with mock.patch.object(pypdf._reader, 'logger_warning', counted(pypdf._reader.logger_warning)), \
                    mock.patch.object(ds, 'logger_warning', counted(ds.logger_warning)):
                reader = GateReader(data)
                self.assertEqual(len(reader.pages), 1)
                self.assertEqual(_gate(data), (1, None))
        finally:
            log.removeHandler(keep)
        self.assertGreaterEqual(len(calls), 700)                       # pypdf still made every repair
        self.assertEqual(sum(r.levelno >= logging.WARNING for r in records), 0)   # was one record per repair
        self.assertFalse(log.isEnabledFor(logging.ERROR))             # _cmap's per-font logger_error too

    def test_no_module_lowers_the_pypdf_logger_below_critical(self):
        """Gap 3 guard: four eval tools once set the "pypdf" logger to ERROR, which undid the gate's CRITICAL in
        any process that imported them (the full suite caught it). Only CRITICAL may ever be set."""
        import pathlib
        apps = pathlib.Path(pdf_layer_guards.__file__).resolve().parents[1]
        found = []
        for path in apps.rglob('*.py'):
            if 'tests' in path.parts:
                continue
            for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                m = re.search(r"getLogger\(\s*['\"]pypdf[\w.]*['\"]\s*\)\.setLevel\(([^)]*)\)", line)
                if m and m.group(1).strip() != 'logging.CRITICAL':
                    found.append('%s:%d' % (path.relative_to(apps), n))
        self.assertEqual(found, [])

    def test_over_budget_is_never_swallowed_inside_a_dictionary_value(self):
        self.assertTrue(issubclass(OverBudget, LimitReachedError))

        class Refusing(io.BytesIO):
            def __init__(self, data, refusal):
                super().__init__(data)
                self.reads, self.refusal = 0, refusal

            def read(self, size=-1):
                self.reads += 1
                if self.reads > 50:
                    raise self.refusal
                return super().read(size)

        text = b'<< /A [' + b'0 ' * 200 + b'] >>'
        with self.assertRaises(OverBudget):                         # pypdf re-raises its own limit errors
            DictionaryObject.read_from_stream(Refusing(text, OverBudget('cap')), None)
        partial = DictionaryObject.read_from_stream(Refusing(text, ValueError('cap')), None)
        self.assertEqual(dict(partial), {})                          # any other error: swallowed, half-read kept


class GenuineShapesAreUnchanged(SimpleTestCase):

    def test_the_control_is_accepted_well_under_the_real_cap(self):
        data = _pdf('plain', 2000)                  # denser than any fixture: about 7 % of the 3x cap
        self.assertEqual(_gate(data), (1, None))
        work, cap = _work(data)
        self.assertLess(work * 4, cap)

    def test_a_small_genuine_file_packed_in_object_streams_is_accepted_with_room(self):
        """Owner decision 23 Nov (cap 3x): 20 pages, ~1,100 objects packed 100 to a stream, used 87 % of the first
        cap. Under the 3x cap: 29 % (measured, the most any of its 4 readers used); pinned under 40 %."""
        data = _packed_pdf(20)
        self.assertLess(len(data), 60_000)
        verdict, readers, share = _upload_shares(data)
        self.assertEqual(verdict, (20, None))
        self.assertEqual(readers, 4)
        self.assertLess(share, 0.40)

    def test_a_few_short_lengths_read_as_pypdf_reads_them(self):
        """Owner's strict rule (round 3 part 2): a wrong /Length is refused, as pdfium may end the stream elsewhere
        (the census and the wider compare on 25 Nov found no genuine file with one). Behind that rule the reader is pypdf's."""
        data = _pdf('shortlen', 5)
        self.assertEqual(_gate(data), (0, 'OverBudget: ' + STREAM))
        self.assertEqual(_gate(_pdf('plain', 5)), (1, None))
        with _lengths_unchecked():
            self.assertEqual(_gate(data), (1, None))
            gate, plain = GateReader(data), PdfReader(io.BytesIO(data))
            for a, b in zip(gate.pages[0]['/Contents'], plain.pages[0]['/Contents']):
                self.assertEqual(a.get_object().get_data(), b.get_object().get_data())
            self.assertEqual(gate.pages[0]['/Contents'][0].get_object().get_data(), b'0 g')

    def test_a_small_rebuilt_table_is_refused_at_the_first_lookup(self):
        """OCR-12 round 1: a table that starts but cannot be read ('0 (x)') may still give pdfium rows the gate
        never saw, so the gate refuses it (no genuine letter in the corpus has one). pypdf's rebuild on open is
        still the reader's own and still metered."""
        data = _rebuild_pdf(5)
        self.assertEqual(_gate(data), (0, 'OverBudget: ' + STREAM))   # its /Length 1 streams, first
        with _lengths_unchecked():
            self.assertEqual(_gate(data), (0, 'OverBudget: a cross-reference section the gate cannot read'))
            with self.assertRaisesRegex(OverBudget, 'a cross-reference section the gate cannot read'):
                GateReader(data).pages[0]['/Contents'].get_object()

    def test_a_rebuilt_table_with_a_small_object_stream_is_refused_and_its_open_is_metered(self):
        """Gap 2 control: the index scan of a table rebuilt on open is metered and charged well under the cap
        (pinned with the row walk and its row check off); with them on, the first lookup refuses the unreadable table (round 1)."""
        data = _rebuild_objstm_pdf(b'100 0 101 4 102 8\n(a) (b) (c)', n=3)
        self.assertEqual(_gate(data), (0, 'OverBudget: a cross-reference section the gate cannot read'))
        gate, reads = _metered_reads(lambda: GateReader(data))
        self.assertGreater(len(reads), 0)                             # the index scan is metered, as it opens
        with self.assertRaisesRegex(OverBudget, 'a cross-reference section the gate cannot read'):
            gate.get_object(100)
        with mock.patch.object(pdf_xref_rows.Walk, 'run', lambda walk, start: None), \
                mock.patch('apps.scholarship.pdf_object_identity.Identity._rows_check'):
            gate, plain = GateReader(data), PdfReader(io.BytesIO(data))
            self.assertEqual(gate.xref_objStm, plain.xref_objStm)
            self.assertEqual(len(gate.xref_objStm), 3)
            for num in (100, 101, 102):
                self.assertEqual(_same(gate.get_object(num)), _same(plain.get_object(num)))
            work, cap = _work(data)
        self.assertLess(work * 100, cap)

    def test_a_length_past_the_end_reads_as_pypdf_reads_it(self):
        data = _pdf('overlen', 3, 10_000)
        self.assertEqual(_gate(data), (0, 'OverBudget: ' + STREAM))   # round 3 part 2: refused for its length
        with _lengths_unchecked():
            self.assertEqual(_gate(data), (1, None))
            gate, plain = GateReader(data), PdfReader(io.BytesIO(data))
            for a, b in zip(gate.pages[0]['/Contents'], plain.pages[0]['/Contents']):
                self.assertEqual(a.get_object().get_data(), b.get_object().get_data())

    def test_packed_objects_read_as_pypdf_reads_them(self):
        data = _objstm_pdf(50, [4], page_in_stream=True)
        self.assertEqual(_gate(data), (1, None))
        gate, plain = GateReader(data), PdfReader(io.BytesIO(data))
        for num in [1, 2, 3, 4] + list(range(100, 150)) + [90000]:
            self.assertEqual(_same(gate.get_object(num)), _same(plain.get_object(num)))
        self.assertIsInstance(gate.get_object(140), int)

    def test_a_row_into_a_stream_that_lacks_it_is_refused(self):
        """pypdf reads null for a number its row packs in a stream that lacks it; pdfium takes whatever sits at
        the row's index. OCR-12 round 1 refuses the row (it is not the one place the streams hold that number)."""
        gate, plain = GateReader(_objstm_pdf(50, [90000, 90001])), PdfReader(io.BytesIO(_objstm_pdf(50, [90000, 90001])))
        self.assertIsInstance(plain.get_object(90000), NullObject)
        with self.assertRaisesRegex(OverBudget, 'object 90000 has a cross-reference row that is not its one copy'):
            gate.get_object(90000)

    def test_the_rows_are_pypdfs_and_a_generation_added_later_is_counted_too(self):
        data = _pdf('plain', 20)
        gate = GateReader(data)
        self.assertEqual(gate.xref, PdfReader(io.BytesIO(data)).xref)
        gate.xref[7] = {}
        self.assertIsInstance(gate.xref[7], pdf_layer_guards._Rows)
        before = gate.stream.work
        list(gate.xref[0].values())
        self.assertEqual(gate.stream.work - before, pdf_layer_guards._ROW_WORK * len(gate.xref[0]))
