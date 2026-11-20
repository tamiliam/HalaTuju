"""TD-692: the fixture corpus through the REAL render gate (`pdf_render_check.render_refusal`, pages up to 30).

The real letters are gitignored, and a committed test never reads them by default (`test_no_gitignored_corpus`):
the corpus test reads only the root $HALATUJU_FIXTURES_ROOT names (set it to the real fixtures to measure them;
`eval/render_check_corpus.py` is the hand-run census). Unset (CI, the deploy gate, the usual suite) the corpus
test measures an empty root and passes trivially (the skip budget is 0, so it cannot be a skip); the synthetic
corpus below pins the census itself everywhere. A failure names reasons and counts only, never a file.
"""
import os
import tempfile
from collections import Counter
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.scholarship.eval import render_check_corpus
from apps.scholarship.tests.test_pdf_render_check import HOSTILE, PHOTO
from apps.scholarship.tests.test_pdf_render_jpx import _jpx, _jpx_bytes, _jpx_page

#: Refusals of genuine (non-empty) fixture letters that are known and left for later, by reason. Each is a real
#: letter stored unreadable: remove the entry when its fix lands. One since TD-692 (measured 2026-11-21, 870
#: fixture PDFs): f0450bfc, a genuine letter whose JPX image has a /JBIG2Decode mask (TD-697). The other refusal
#: is b36e232b, the empty file, which is never counted here. Ids: the first 8 hex digits of the sha1 of the path
#: relative to the root as Windows writes it (backslash separators, UTF-8): os.path.relpath on Windows.
KNOWN_GAPS = Counter({"Refused: an image filter outside the whitelist ('/JBIG2Decode')": 1})


class TheFixtureCorpusThroughTheRenderGate(SimpleTestCase):
    def test_only_known_unreadable_files_are_refused(self):
        """With HALATUJU_FIXTURES_ROOT unset this measures an empty root and passes trivially: the real letters
        are gitignored, so only a run that sets the root measures anything."""
        with tempfile.TemporaryDirectory() as empty:
            root = os.environ.get(render_check_corpus.ROOT_ENV) or empty
            census = render_check_corpus.census(root)
        if os.environ.get(render_check_corpus.ROOT_ENV):
            self.assertGreater(census['files'], 0, 'HALATUJU_FIXTURES_ROOT names no PDFs: nothing was measured')
        unknown = census['refused_not_empty'] - KNOWN_GAPS
        self.assertFalse(unknown, f"{census['files']} PDFs; refused beyond the empty files and known gaps, by "
                                  f"reason: {dict(unknown)}")

    def test_the_census_on_a_synthetic_corpus(self):
        """Recursive, any case of .pdf, other files ignored; an empty file is refused but known unreadable; a
        refused letter is counted by its reason."""
        files = {'photo.pdf': PHOTO, os.path.join('sub', 'SCAN.PDF'): _jpx_page(_jpx(300, 200, _jpx_bytes(300, 200))),
                 os.path.join('sub', 'deeper', 'empty.pdf'): b'', 'notes.txt': b'not a pdf',
                 'refused.Pdf': HOSTILE['an image filter outside the whitelist']}
        with tempfile.TemporaryDirectory() as root:
            for name, data in files.items():
                os.makedirs(os.path.dirname(os.path.join(root, name)), exist_ok=True)
                with open(os.path.join(root, name), 'wb') as f:
                    f.write(data)
            census = render_check_corpus.census(root)
        self.assertEqual((census['files'], census['empty'], census['pages']), (4, 1, 2))
        self.assertEqual(sum(census['refused'].values()), 2)
        self.assertEqual(census['refused_not_empty'],
                         Counter({"Refused: an image filter outside the whitelist ('/ASCIIHexDecode')": 1}))

    def test_the_root_comes_from_the_environment(self):
        with patch.dict(os.environ, {render_check_corpus.ROOT_ENV: 'elsewhere'}):
            self.assertEqual(render_check_corpus.fixtures_root(), 'elsewhere')
        with patch.dict(os.environ):
            os.environ.pop(render_check_corpus.ROOT_ENV, None)
            self.assertEqual(render_check_corpus.fixtures_root(),
                             os.path.join(render_check_corpus.HERE, 'fixtures'))   # the hand-run default
