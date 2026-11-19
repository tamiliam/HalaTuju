"""S-visible fix round 8: pdfium runs in a child process (`pdfium_run` -> `pdfium_worker`) with a hard time limit.

A crafted PDF that keeps pdfium busy, a child that crashes, prints garbage or hangs: each ends in the safe answer
(hidden -> the Vision route; no render -> "cannot read"), never the hidden text, within the (shortened) limit.
Real-shaped PDFs read and render exactly as pdfium does in-process. Fictional words only.
"""
import io
import os
import tempfile
import time
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship import pdf_pages, pdfium_run, pdfium_worker, spm_cert_parse
from apps.scholarship.tests.test_ocr_visible import DRAWN, SPM_TEXT, _pdf, _show
from apps.scholarship.tests.test_ocr_visible_paths import _doc
from apps.scholarship.tests.test_ocr_visible_round6 import BOMB_GLYPH, _flate

TEXT = _show(SPM_TEXT)
SHORT = 1.0          # the patched time limit: each crafted file below keeps pdfium busy 2-5 s on the dev machine


def _fresh():
    pdf_pages._layer_memo_clear()            # clears the child-answer memo too


def _annotation(fills):
    """Round 8 finding 1: a square annotation whose appearance stream fills the page ``fills`` times."""
    return _doc(TEXT, {6: b'<< /Type /Annot /Subtype /Square /Rect [0 0 300 200] /AP << /N 7 0 R >> >>',
                       7: _flate(b'<< /Type /XObject /Subtype /Form /BBox [0 0 300 200]', b'0 0 300 200 re f ' * fills)},
                page_res=b'/Resources << /Font << /F1 3 0 R >> >> /Annots [6 0 R]', filtered=True)


def _huge_text(chars):
    """Finding 2: Helvetica at 3000 pt, -2166 Tc, render mode 2, three runs of ``chars`` '@'."""
    run = b'BT /F1 3000 Tf -2166 Tc 2 Tr 0 0 Td (' + b'@' * chars + b') Tj ET '
    return _doc(run * 3 + TEXT, filtered=True)


def _clips(count):
    """Finding 3, nested: ``count`` triangle clips, each filling a 1 x 1 square inside all the clips before it
    (under the render check's caps; 10,500 of them ran past 25 s; side by side, 10,500 took 2 s here)."""
    return _doc(b'q 0 0 m 300 0 l 150 200 l h W n 0 0 1 1 re f ' * count + b'Q ' * count + TEXT, filtered=True)


def _type3_spaces(glyphs):
    """Finding 4: a Type3 font mapping every code to a /space glyph of 2.8 MB (pypdf's text is blank)."""
    procs = b' '.join(b'/space%d %d 0 R' % (i, 7 + i) for i in range(glyphs))
    diff = b' '.join(b'%d /space%d' % (c, c) for c in range(glyphs))
    font = (b'<< /Type /Font /Subtype /Type3 /FontBBox [0 0 1000 1000] /FontMatrix [0.001 0 0 0.001 0 0] '
            b'/CharProcs << ' + procs + b' >> /Encoding << /Type /Encoding /Differences [' + diff + b'] >> '
            b'/FirstChar 0 /LastChar %d /Widths [' % (glyphs - 1) + b'500 ' * glyphs + b'] >>')
    glyph = _flate(b'<<', BOMB_GLYPH)
    shown = b'BT /T3 12 Tf 20 100 Td <' + b''.join(b'%02x' % c for c in range(glyphs)) + b'> Tj ET'
    return _doc(shown, {6: font, **{7 + i: glyph for i in range(glyphs)}},
                page_res=b'/Resources << /Font << /F1 3 0 R /T3 6 0 R >> >>', filtered=True)


@patch.object(pdfium_run, 'TIMEOUT_S', SHORT)
class TheFourCraftedFiles(SimpleTestCase):
    def setUp(self):
        _fresh()

    def _no_render(self, pdf):
        t0 = time.perf_counter()
        self.assertIsNone(pdf_pages.pdf_first_page_png(pdf))
        self.assertEqual(pdf_pages.pdf_page_pngs(pdf, 1), [])         # the same question: the memo answers
        self.assertIsNone(pdf_pages.pdf_pages_png(pdf))
        self.assertLess(time.perf_counter() - t0, 2 * SHORT + 3.0)

    def test_an_annotation_appearance_stream(self):
        self._no_render(_annotation(40_000))

    def test_huge_spaced_text(self):
        self._no_render(_huge_text(6_000))

    def test_clip_paths(self):
        self._no_render(_clips(2_000))

    def test_type3_glyphs_behind_blank_text_are_load_checked(self):
        pdf = _type3_spaces(120)
        t0 = time.perf_counter()
        with patch.object(pdfium_run, '_spawn', wraps=pdfium_run._spawn) as spawned:
            self.assertFalse(pdf_pages.first_page_drawn(pdf))    # the load check now judges a blank-text page
            self.assertIsNone(spm_cert_parse.parse_spm_cert('', pdf=pdf))
            self.assertIsNone(pdf_pages.pdf_first_page_png(pdf))
        self.assertEqual(spawned.call_count, 0)                    # the pre-filter refused it: no child at all
        self.assertIsNone(pdfium_run.ask(pdf, [{'op': 'words'}]))  # and past the pre-filter, the time limit
        self.assertLess(time.perf_counter() - t0, SHORT + 4.0)


class AChildThatFails(SimpleTestCase):
    """A stand-in worker script: each failure is the safe answer for every caller."""

    def setUp(self):
        _fresh()
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(_fresh)

    def _worker(self, body):
        path = os.path.join(self.dir.name, 'worker.py')
        with open(path, 'w') as fh:
            fh.write('import sys, time\n' + body + '\n')
        return patch.object(pdfium_run, '_WORKER', path)

    def _all_safe(self):
        self.assertIsNone(pdfium_run.ask(DRAWN, [{'op': 'count'}]))
        _fresh()
        self.assertEqual(pdf_pages.pdf_text_layer(DRAWN), '')            # hidden: never the text
        self.assertFalse(pdf_pages.first_page_drawn(DRAWN))
        self.assertIsNone(pdf_pages.pdf_first_page_png(DRAWN))
        self.assertEqual(pdf_pages.pdf_page_pngs(DRAWN, 3), [])
        self.assertEqual(pdf_pages.pdf_page_count(DRAWN), 0)
        self.assertIsNone(pdf_pages.pdf_pages_png(DRAWN))
        self.assertIsNone(spm_cert_parse._pdf_words(DRAWN))

    def test_a_crash(self):
        with self._worker('sys.exit(3)'):
            self._all_safe()

    def test_garbage_on_stdout(self):
        with self._worker('sys.stdout.write("not a header\\n%PNG garbage"); sys.exit(0)'):
            self._all_safe()

    def test_a_header_that_does_not_match_the_bytes(self):
        with self._worker('sys.stdin.buffer.read(); '
                          'sys.stdout.write(\'{"results": [{"count": 1}], "blobs": [99]}\\n\'); sys.exit(0)'):
            self._all_safe()

    def test_a_child_that_hangs_is_killed(self):
        with self._worker('time.sleep(60)'), patch.object(pdfium_run, 'TIMEOUT_S', 0.5):
            t0 = time.perf_counter()
            self.assertIsNone(pdfium_run.ask(DRAWN, [{'op': 'count'}]))
            self.assertLess(time.perf_counter() - t0, 5.0)

    def test_after_a_timeout_the_same_upload_spawns_nothing(self):
        with self._worker('time.sleep(60)'), patch.object(pdfium_run, 'TIMEOUT_S', 0.5), \
                patch.object(pdfium_run, '_spawn', wraps=pdfium_run._spawn) as spawned:
            self.assertIsNone(pdfium_run.ask(DRAWN, [{'op': 'count'}]))
            t0 = time.perf_counter()
            self.assertIsNone(pdf_pages.pdf_first_page_png(DRAWN))      # another question: answered at once
            self.assertIsNone(spm_cert_parse._pdf_words(DRAWN))
            self.assertLess(time.perf_counter() - t0, 0.5)
        self.assertEqual(spawned.call_count, 1)

    def test_pdfium_refusing_the_bytes(self):
        self.assertIsNone(pdfium_run.ask(b'%PDF-1.4 not a pdf', [{'op': 'count'}]))

    def test_a_failure_is_remembered(self):
        with self._worker('sys.exit(3)'), patch.object(pdfium_run, '_spawn', wraps=pdfium_run._spawn) as spawned:
            self.assertIsNone(pdfium_run.ask(DRAWN, [{'op': 'count'}]))
            self.assertIsNone(pdfium_run.ask(DRAWN, [{'op': 'count'}]))
        self.assertEqual(spawned.call_count, 1)


class TheSameAnswersAsInProcess(SimpleTestCase):
    """What the child returns is what pypdfium2 gives in this process (the tests may import it)."""

    def setUp(self):
        _fresh()

    def _in_process(self, pdf, indices):
        import pypdfium2
        doc = pypdfium2.PdfDocument(pdf)
        try:
            out = []
            for i in indices:
                page = doc[i]
                scale = pdf_pages.raster_scale(page.get_width(), page.get_height())
                out.append(pdfium_worker._png(page.render(scale=scale).to_pil()))
            words = pdfium_worker._op_words(doc, {}, [])['words']
            return out, len(doc), words
        finally:
            doc.close()

    def test_renders_count_and_word_boxes(self):
        three = _pdf([_show(SPM_TEXT), _show('HALAMAN DUA'), _show('HALAMAN TIGA')])
        for pdf, n in ((DRAWN, 1), (three, 3)):
            with self.subTest(pages=n):
                pngs, count, words = self._in_process(pdf, range(n))
                self.assertEqual(pdf_pages.pdf_first_page_png(pdf), pngs[0])
                self.assertEqual(pdf_pages.pdf_page_pngs(pdf, 3), pngs)
                self.assertEqual(pdf_pages.pdf_page_count(pdf), count)
                self.assertEqual(spm_cert_parse._pdf_words(pdf), words)
                self.assertTrue(words)

    def test_the_stacked_render_is_one_png_of_all_pages(self):
        from PIL import Image
        three = _pdf([_show(SPM_TEXT), _show('HALAMAN DUA'), _show('HALAMAN TIGA')])
        sheet = Image.open(io.BytesIO(pdf_pages.pdf_pages_png(three)))
        first = Image.open(io.BytesIO(pdf_pages.pdf_first_page_png(three)))
        self.assertGreater(sheet.height, 2 * sheet.width * first.height / first.width)

    def test_the_text_check_keeps_a_drawn_layer(self):
        self.assertIn('SIJIL', pdf_pages.pdf_text_layer(DRAWN))
        self.assertTrue(pdf_pages.first_page_drawn(DRAWN))

    def test_one_child_answers_the_render_and_the_count(self):
        three = _pdf([_show(SPM_TEXT), _show('HALAMAN DUA'), _show('HALAMAN TIGA')])
        with patch.object(pdfium_run, '_spawn', wraps=pdfium_run._spawn) as spawned:
            pdf_pages.pdf_page_pngs(three, 3)
            self.assertEqual(pdf_pages.pdf_page_count(three), 3)
            pdf_pages.pdf_first_page_png(three)     # a different render question (page 1 only)
        self.assertEqual(spawned.call_count, 2)
