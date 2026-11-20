"""2026-11-21: the pdfium child renders ONE page per call (`pdf_pages._render`).

A 3-page A4 400 dpi colour scan stored as JPEG2000 took the Linux child (address space capped at its size + 256 MiB)
past its cap when all three pages were rendered in one child: it died after 9-11 s and the offer reader got no page
at all. Measured by hand with full-size files (the hand-back of this change); here the per-call behaviour is pinned
with small pages of the same shape and encodings, so it runs in CI: one page per child, a failed page keeps the
pages before it, and every page call is charged to the document's ONE time budget. Synthetic files only.
"""
import io
import json
import zlib
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import pdf_pages, pdf_render_check, pdfium_run
from apps.scholarship.tests._timing import wall_backstop
from apps.scholarship.tests.test_ocr_visible import _stream
from apps.scholarship.tests.test_pdf_render_check import FULL_PAGE, _a4
from apps.scholarship.tests.test_pdfium_child import _fresh, _script

#: An A4 page at 40 dpi: the shape of a 400 dpi scan (3307 x 4677) at a tenth of the side, so CI stays fast.
W, H = 331, 468
#: Each page's own colour, so a PNG proves which page it is.
COLOURS = [(200, 30, 30), (30, 160, 40), (40, 60, 190)]
#: The raster an A4 page gets (`pdf_pages.raster_scale`: 200 dpi).
A4_RASTER = (1653, 2339)


def _image(colour, encoding):
    """One page's scan as an image XObject: JPEG2000 with 5 decomposition levels (NL5, as a scanner writes it),
    baseline JPEG at quality 85, or raw RGB under Flate."""
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (W, H), colour)
    ImageDraw.Draw(im).rectangle((W // 8, H // 8, W // 2, H // 6), fill=(20, 20, 20))     # a line of "text"
    head = b'<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB /BitsPerComponent 8 ' % (
        W, H)
    buf = io.BytesIO()
    if encoding == 'jpx':
        im.save(buf, 'JPEG2000', num_resolutions=6)
        return _stream(head + b'/Filter /JPXDecode', buf.getvalue())
    if encoding == 'dct':
        im.save(buf, 'JPEG', quality=85)
        return _stream(head + b'/Filter /DCTDecode', buf.getvalue())
    return _stream(head + b'/Filter /FlateDecode', zlib.compress(im.tobytes()))


def _letter(encoding, pages=3):
    """A ``pages``-page A4 scan, each page one full-page image in ``encoding``."""
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter()
    for colour in COLOURS[:pages]:
        one = _a4(b'q ' + FULL_PAGE + b'/Im0 Do Q', b'/XObject << /Im0 6 0 R >>', {6: _image(colour, encoding)})
        writer.add_page(PdfReader(io.BytesIO(one)).pages[0])
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _centre(png):
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert('RGB')
    return im.size, im.getpixel((im.width // 2, im.height // 2))


def _rendered_pages(asked):
    """The pages each child call asked to render, one list per call."""
    return [op['pages'] for call in asked.call_args_list for op in call.args[1] if op['op'] == 'render']


class AThreePageColourScan(SimpleTestCase):
    def setUp(self):
        _fresh()
        self.addCleanup(_fresh)

    def test_each_encoding_renders_every_page_one_page_per_child(self):
        for encoding in ('jpx', 'dct', 'flate'):
            with self.subTest(encoding):
                _fresh()
                letter = _letter(encoding)
                with patch.object(pdfium_run, 'ask', wraps=pdfium_run.ask) as asked, \
                        patch.object(pdf_render_check, 'render_refusal', wraps=pdf_render_check.render_refusal) as gate:
                    pngs = pdf_pages.pdf_page_pngs(letter, 3)
                self.assertEqual(gate.call_count, 1)                    # the pre-filter: once per document
                self.assertEqual(_rendered_pages(asked), [[0], [1], [2]])
                self.assertEqual(len(pngs), 3)
                for png, colour in zip(pngs, COLOURS):
                    size, centre = _centre(png)
                    self.assertEqual(size, A4_RASTER)
                    self.assertTrue(all(abs(a - b) <= 12 for a, b in zip(centre, colour)), (encoding, centre))

    def test_page_one_and_the_count_come_from_the_first_page_call(self):
        letter = _letter('dct')
        with patch.object(pdfium_run, '_spawn', wraps=pdfium_run._spawn) as spawned:
            pngs = pdf_pages.pdf_page_pngs(letter, 3)
            self.assertEqual(pdf_pages.pdf_first_page_png(letter), pngs[0])
            self.assertEqual(pdf_pages.pdf_page_count(letter), 3)
        self.assertEqual(spawned.call_count, 3)                         # one child per page, nothing more


# ── A child that fails on one page: the stand-in worker renders "PNG<i>" for page i and dies as out of memory
#    (`pdfium_worker.OUT_OF_MEMORY`) when asked for page ``BAD``, the way a page past the cap ends.
_FAILS_ON = '''import os
BAD = {bad}
req = json.loads(sys.stdin.buffer.readline())
sys.stdin.buffer.read()
results, blobs = [], []
for op in req['ops']:
    if op['op'] == 'count':
        results.append({{'count': 3}})
        continue
    if BAD in op['pages']:
        time.sleep({sleep})
        os._exit(86)
    results.append({{'pngs': [], 'stop': None}})
    for i in op['pages']:
        blobs.append(b'PNG%d' % i)
        results[-1]['pngs'].append(len(blobs) - 1)
sys.stdout.buffer.write(json.dumps({{'results': results, 'blobs': [len(b) for b in blobs]}}).encode() + b'\\n')
sys.stdout.buffer.write(b''.join(blobs))
'''


class OneBadPage(SimpleTestCase):
    def setUp(self):
        import tempfile
        _fresh()
        self.addCleanup(_fresh)
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.letter = _letter('dct')

    def _pngs(self, bad, sleep=0):
        path = _script(self.dir.name, _FAILS_ON.format(bad=bad, sleep=sleep))
        with patch.object(pdfium_run, '_WORKER', path), \
                patch.object(pdfium_run, '_spawn', wraps=pdfium_run._spawn) as spawned:
            pngs = pdf_pages.pdf_page_pngs(self.letter, 3)
            first = pdf_pages.pdf_first_page_png(self.letter)
        return pngs, first, spawned.call_count

    def test_a_bad_last_page_keeps_the_pages_before_it(self):
        self.assertEqual(self._pngs(bad=2), ([b'PNG0', b'PNG1'], b'PNG0', 3))

    def test_a_bad_middle_page_ends_the_list_there(self):
        # the offer reader labels the k-th PNG page k: page 3 never moves up into page 2's place, nor is it asked
        self.assertEqual(self._pngs(bad=1), ([b'PNG0'], b'PNG0', 2))

    def test_a_bad_first_page_is_no_page(self):
        self.assertEqual(self._pngs(bad=0), ([], None, 1))

    def test_a_page_that_hangs_is_killed_within_the_document_budget(self):
        with patch.object(pdfium_run, 'DOC_BUDGET_S', 3.0), wall_backstop(self), \
                patch.object(pdfium_run, '_run_child', wraps=pdfium_run._run_child) as run:
            pngs, first, children = self._pngs(bad=1, sleep=60)
        self.assertEqual((pngs, first, children), ([b'PNG0'], b'PNG0', 2))
        # page 2's child was given only the budget page 1 left (not TIMEOUT_S), and was killed there
        self.assertLess(run.call_args_list[1].args[1], 3.0)
        self.assertGreaterEqual(pdfium_run._BUDGET[pdfium_run.hashlib.sha256(self.letter).digest()][0], 3.0)


class TheDocumentTimeBudget(SimpleTestCase):
    """Every page call is charged to the document's ONE budget (`pdfium_run.DOC_BUDGET_S`): each child's limit is
    the budget left, so N pages never get N x `pdfium_run.TIMEOUT_S`, and a hostile file holds a child slot no
    longer than one call could before."""

    def setUp(self):
        _fresh()
        self.addCleanup(_fresh)

    def test_three_slow_pages_share_one_budget(self):
        limits = []

        def child(payload, timeout, n_ops, max_blobs, used):
            limits.append(timeout)
            if timeout < 8.0:                                           # this page needs 8 s: killed at its limit
                used[0] = timeout
                raise pdfium_run._TimedOut
            used[0] = 8.0
            ops = json.loads(payload.split(b'\n', 1)[0])['ops']
            return [{'count': 3} if op['op'] == 'count' else {'pngs': [b'PNG%d' % i for i in op['pages']],
                                                               'stop': None} for op in ops]

        letter = _letter('dct')
        with patch.object(pdfium_run, '_run_child', child), patch.object(pdfium_run, 'TIMEOUT_S', 20.0), \
                patch.object(pdfium_run, 'DOC_BUDGET_S', 20.0):
            self.assertEqual(pdf_pages.pdf_page_pngs(letter, 3), [b'PNG0', b'PNG1'])
            self.assertEqual(limits, [20.0, 12.0, 4.0])                 # each page's limit: the budget left
            self.assertIsNone(pdf_pages.pdf_pages_png(letter))         # spent: another reader spawns nothing
            self.assertEqual(pdf_pages.pdf_first_page_png(letter), b'PNG0')     # page 1 already answered
        self.assertEqual(len(limits), 3)
        self.assertAlmostEqual(pdfium_run._BUDGET[pdfium_run.hashlib.sha256(letter).digest()][0], 20.0)
