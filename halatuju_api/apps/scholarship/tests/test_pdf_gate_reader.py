"""TD-702: pypdf copies and searches the WHOLE file for each object it cannot place, and nothing counted those
searches, so a crafted PDF held a web worker for minutes (100 numbers with no row: about 120 s on a 7.5 MB file;
100 rows of the wrong generation: 34-52 s, and the file was ACCEPTED). `GateReader` now counts every whole-file
read and refuses past `MAX_WHOLE_FILE_READS`, and answers a number the file holds no header for at once.

Every PDF here is built in code: one page whose /Contents lists N small content streams, after a padding stream
that makes each whole-file search cost something. The guard is pinned by the searches it counts, not by time
(TD-693): a spy counts pypdf's whole-file searches (`get_stream_data`, the helper each search calls).
"""
import io
from unittest import mock

import pypdf
import pypdf._reader
from django.test import SimpleTestCase

from apps.scholarship import pdf_layer_guards, pdf_render_check
from apps.scholarship.pdf_layer_guards import MAX_WHOLE_FILE_READS, GateReader

FIRST = 10                          # the first content stream's object number
PAD = 2_000_000                     # padding bytes: each whole-file search copies and scans all of them


def _pdf(mode: str, n: int, pad: int = PAD) -> bytes:
    """A one-page PDF whose /Contents names objects FIRST..FIRST+n-1, built so each lookup takes the shape
    ``mode`` names. 'missing': none of them is in the file. 'gen': each header says generation 1, its row 0.
    'comment': each row points at a ' %c' comment line just before the header. 'shifted': each row points one
    byte into its header (a real repair: pypdf finds the header by searching). 'unlisted': each object is in
    the file with no row. 'plain': every row is right (the control)."""
    out, rows = bytearray(b'%PDF-1.5\n'), {}

    def obj(num, body, gen=0, at=None):
        rows[num] = len(out) if at is None else at
        out.extend(b'%d %d obj\n' % (num, gen) + body + b'\nendobj\n')

    obj(1, b'<< /Type /Catalog /Pages 2 0 R >>')
    obj(2, b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    refs = b' '.join(b'%d 0 R' % (FIRST + k) for k in range(n))
    obj(3, b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents [' + refs + b'] >>')
    obj(4, b'<< /Length %d >>\nstream\n' % pad + b' ' * pad + b'\nendstream')
    content = b'<< /Length 3 >>\nstream\n0 g\nendstream'
    for k in range(n if mode != 'missing' else 0):
        num = FIRST + k
        if mode == 'comment':
            at = len(out)
            out.extend(b' %c\n')
            obj(num, content, at=at)
        else:
            obj(num, content, gen=1 if mode == 'gen' else 0, at=len(out) + 1 if mode == 'shifted' else None)
        if mode == 'unlisted':
            del rows[num]
    xref = len(out)
    body = b'xref\n0 1\n0000000000 65535 f \n'
    for num in sorted(rows):
        body += b'%d 1\n%010d 00000 n \n' % (num, rows[num])
    size = FIRST + n if mode != 'missing' else 5
    out.extend(body + b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (size, xref))
    return bytes(out)


def _gate(data: bytes):
    """(page count, refusal or None, whole-file searches pypdf made) of the real gate over the first 30 pages."""
    with mock.patch.object(pypdf._reader, 'get_stream_data', wraps=pypdf._reader.get_stream_data) as search:
        n, why = pdf_render_check.render_refusal(data, lambda k: range(min(k, 30)))
    return n, why, search.call_count


def _whole_reads(data: bytes) -> int:
    """The whole-file reads a reader makes opening ``data`` and resolving its page's /Contents (cap lifted)."""
    with _cap(10 ** 9):
        reader = GateReader(data)
        for ref in reader.pages[0]['/Contents']:
            ref.get_object()
        return reader.stream.whole_reads


class _cap:
    def __init__(self, n):
        self.n = n

    def __enter__(self):
        self.old, pdf_layer_guards.MAX_WHOLE_FILE_READS = pdf_layer_guards.MAX_WHOLE_FILE_READS, self.n

    def __exit__(self, *exc):
        pdf_layer_guards.MAX_WHOLE_FILE_READS = self.old


class HostileLookupsAreBounded(SimpleTestCase):
    """Each shape made pypdf search the whole file once per lookup, uncounted. Now: fast, and refused where
    the lookups are searches."""

    def test_numbers_the_file_never_defines_cost_one_read_not_one_each(self):
        self.assertEqual(_whole_reads(_pdf('missing', 200)), 1)       # the one header scan

    def test_numbers_the_file_never_defines_are_refused_with_no_search(self):
        _n, why, searches = _gate(_pdf('missing', 200))
        self.assertIsNotNone(why)                                     # a content stream that is not a stream
        self.assertEqual(searches, 0)                                 # was one whole-file search per number

    def test_rows_of_the_wrong_generation_are_refused_at_the_first(self):
        _n, why, searches = _gate(_pdf('gen', 200))
        # OCR-12 round 1: the row (generation 0) is not on the number's one header (generation 1)
        self.assertEqual(why, 'OverBudget: object 10 has a cross-reference row that is not its one copy')
        self.assertEqual(searches, 1)                                 # was ACCEPTED after one search per row

    def test_rows_on_a_comment_before_the_header_are_refused_at_the_cap(self):
        _n, why, searches = _gate(_pdf('comment', 200))
        self.assertIn('whole-file reads past the cap', why or '')     # was ACCEPTED after one search per row
        self.assertEqual(searches, MAX_WHOLE_FILE_READS)              # one header scan, then searches to the cap

    def test_each_unplaceable_row_is_one_counted_search(self):
        with self.assertRaisesRegex(pdf_layer_guards.OverBudget, 'object 10 has a cross-reference row'):   # first
            _whole_reads(_pdf('gen', 7))
        # pypdf drops a row on a comment when it opens the file ("wrong pointing object"), so these numbers have
        # no row: one header scan, then one search each (their headers are there)
        self.assertEqual(_whole_reads(_pdf('comment', 7)), 1 + 7)


class GenuineFilesAreUnchanged(SimpleTestCase):

    def test_the_control_is_accepted_with_no_whole_file_read(self):
        data = _pdf('plain', 200)
        self.assertEqual(_gate(data), (1, None, 0))
        self.assertEqual(_whole_reads(data), 0)

    def test_repairs_pypdf_makes_by_searching_are_refused_at_the_first(self):
        """OCR-12 round 1: pypdf repairs a row one byte into its header, or a number with no row, by searching;
        pdfium follows the row as written (or finds no row). The gate may not use a row that is not on the one
        header, nor an object pdfium has no row for: both are refused at the first lookup, one search at most
        (no genuine letter in the corpus has either shape)."""
        for mode, why in (('shifted', 'object 10 has a cross-reference row that is not its one copy'),
                          ('unlisted', 'object 10 has no cross-reference row')):
            for count in (1, MAX_WHOLE_FILE_READS + 1):
                with self.subTest(mode=mode, count=count):
                    self.assertEqual(_gate(_pdf(mode, count)), (0, 'OverBudget: ' + why, 1))

    def test_an_object_with_no_row_is_found_by_pypdf_but_refused_by_the_gate(self):
        data = _pdf('unlisted', 1)
        plain = pypdf.PdfReader(io.BytesIO(data))
        self.assertEqual(plain.pages[0]['/Contents'][0].get_object().get_data(), b'0 g')
        with self.assertRaisesRegex(pdf_layer_guards.OverBudget, 'object 10 has no cross-reference row'):
            GateReader(data).pages[0]['/Contents'][0].get_object()

    def test_a_number_with_no_header_reads_as_pypdf_reads_it(self):
        reader = GateReader(_pdf('missing', 3))
        self.assertIsNone(reader.get_object(FIRST))
        self.assertIsNone(reader.get_object(FIRST))                   # cached: no second scan
        self.assertEqual(reader.stream.whole_reads, 1)
