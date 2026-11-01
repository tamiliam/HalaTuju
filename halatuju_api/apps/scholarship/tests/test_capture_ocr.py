"""The eval OCR-capture script's pure helpers (eval/capture_ocr.py): the text-layer-vs-Vision
choice mirrors vision.ocr_document_full, word boxes keep production's shape, and nested folder
arguments resolve under fixtures/. Synthetic input only — no real documents."""
import importlib.util
import os

from django.test import SimpleTestCase

_PATH = os.path.join(os.path.dirname(__file__), '..', 'eval', 'capture_ocr.py')
_spec = importlib.util.spec_from_file_location('eval_capture_ocr', _PATH)
cap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cap)


class TestCapturePathChoice(SimpleTestCase):
    def test_digital_pdf_with_enough_text_uses_the_text_layer(self):
        self.assertEqual(cap.choose_path(True, 'x' * 25), 'text_layer')

    def test_pdf_with_too_little_text_goes_to_vision(self):
        self.assertEqual(cap.choose_path(True, 'x' * 24), 'vision')
        self.assertEqual(cap.choose_path(True, ''), 'vision')

    def test_an_image_always_goes_to_vision(self):
        self.assertEqual(cap.choose_path(False, 'x' * 500), 'vision')

    def test_threshold_matches_production(self):
        from apps.scholarship import vision
        self.assertEqual(cap.MIN_PDF_TEXT, vision._MIN_PDF_TEXT)

    def test_pdf_is_recognised_by_extension_or_magic(self):
        self.assertTrue(cap.is_pdf('a.PDF', b''))
        self.assertTrue(cap.is_pdf('a.bin', b'%PDF-1.7 ...'))
        self.assertFalse(cap.is_pdf('a.jpg', b'\xff\xd8\xff'))


class TestCaptureHelpers(SimpleTestCase):
    def test_raster_scale_matches_production(self):
        from apps.scholarship import pdf_pages
        for w, h in [(595, 842), (5000, 7000), (0, 842), (30000, 10)]:
            self.assertEqual(cap.raster_scale(w, h), pdf_pages.raster_scale(w, h))

    def test_word_box_has_production_keys_and_bounds(self):
        w = cap.word_box('PNGK', [(10, 20), (50, 20), (50, 30), (10, 30)])
        self.assertEqual((w['cx'], w['cy'], w['h'], w['angle']), (30, 25, 10, 0.0))
        self.assertEqual((w['x0'], w['y0'], w['x1'], w['y1']), (10, 20, 50, 30))
        self.assertEqual(w['text'], 'PNGK')

    def test_word_box_reports_a_sideways_baseline(self):
        w = cap.word_box('A', [(0, 0), (0, 40), (-10, 40), (-10, 0)])
        self.assertAlmostEqual(w['angle'], 90.0)

    def test_nested_folder_argument_resolves_under_fixtures(self):
        fx, cx = cap.doc_folders('results_split/stpm_cert')
        self.assertEqual(os.path.normpath(fx), os.path.normpath(
            os.path.join(cap.HERE, 'fixtures', 'results_split', 'stpm_cert')))
        self.assertTrue(os.path.normpath(cx).endswith(
            os.path.normpath('counter_examples/results_split/stpm_cert')))

    def test_plain_doc_type_argument_still_works(self):
        fx, _ = cap.doc_folders('results_slip')
        self.assertEqual(os.path.normpath(fx),
                         os.path.normpath(os.path.join(cap.HERE, 'fixtures', 'results_slip')))


class TestCorpusCapturePlan(SimpleTestCase):
    """offer exact-read S2: a corpus folder (--corpus), an earlier page-1 capture reused instead of
    a second Vision call (--reuse-from), and a dry count that writes and calls nothing."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.snap = os.path.join(self._tmp.name, 'snapshots')
        self.earlier = os.path.join(self._tmp.name, 'earlier')
        self.docs = os.path.join(self._tmp.name, 'fixtures', 'offer_letter')
        for d in (self.snap, self.earlier, self.docs):
            os.makedirs(d)

    def tearDown(self):
        self._tmp.cleanup()

    def _doc(self, name, data=b'\xff\xd8\xff synthetic'):
        path = os.path.join(self.docs, name)
        with open(path, 'wb') as fh:
            fh.write(data)
        return path

    def _txt(self, folder, key, text='synthetic page one text'):
        with open(os.path.join(folder, key + '.ocr.txt'), 'w', encoding='utf-8') as fh:
            fh.write(text)

    def test_a_corpus_reads_only_its_own_fixtures_folder(self):
        self.assertEqual(cap.doc_folders('offer_letter', self._tmp.name), [self.docs])

    def test_routes_cached_earlier_vision_and_unreadable(self):
        cached, earlier, photo = self._doc('k1.jpg'), self._doc('k2.jpg'), self._doc('k3.png')
        broken = self._doc('k4.pdf', b'<html>not a pdf</html>')
        self._txt(self.snap, 'k1')
        self._txt(self.earlier, 'k2')
        plans = [cap.plan_one(p, self.snap, self.earlier) for p in (cached, earlier, photo, broken)]
        self.assertEqual([p['route'] for p in plans], ['cached', 'earlier', 'vision', 'unreadable'])
        self.assertEqual(cap.plan_summary(plans), {
            'docs': 4, 'routes': {'cached': 1, 'earlier': 1, 'unreadable': 1, 'vision': 1},
            'vision_calls': 1, 'vision_usd': round(cap.VISION_USD_PER_PAGE, 4)})

    def test_without_reuse_an_earlier_capture_is_not_taken(self):
        path = self._doc('k2.jpg')
        self._txt(self.earlier, 'k2')
        self.assertEqual(cap.plan_one(path, self.snap)['route'], 'vision')

    def test_reuse_copies_the_text_with_an_earlier_vision_meta(self):
        import json
        self._txt(self.earlier, 'k2', 'abc')
        self.assertEqual(cap.reuse_earlier('k2', self.snap, self.earlier), 3)
        with open(os.path.join(self.snap, 'k2.ocr.meta.json'), encoding='utf-8') as fh:
            meta = json.load(fh)
        self.assertEqual((meta['path'], meta['vision_calls'], meta['production_reads_page']),
                         ('earlier_vision', 0, 1))

    def test_a_dry_run_writes_nothing_and_makes_no_call(self):
        import contextlib
        import io
        self._doc('k3.png')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cap.main(['offer_letter', '--corpus', self._tmp.name, '--reuse-from', self.earlier,
                      '--dry-run'])
        self.assertIn('vision 1', out.getvalue())
        self.assertEqual(os.listdir(self.snap), [])


class TestCaptureUsesProductionPdfLibraries(SimpleTestCase):
    """The capture reads PDFs with production's own pdf_pages functions, and warns when the installed
    pypdf / pypdfium2 differ from requirements.lock (another version lays a text layer out differently)."""

    def test_the_text_layer_is_production_s_own_reader(self):
        from apps.scholarship import pdf_pages
        self.assertIs(cap._pdf_text_layer, pdf_pages.pdf_text_layer)
        self.assertIs(cap.raster_scale, pdf_pages.raster_scale)

    def test_locked_versions_are_read_from_the_lock_text(self):
        lock = 'Django==5.0\npypdf==5.9.0  # pinned\npypdfium2==4.30.0\npillow==10.0\n'
        self.assertEqual(cap.locked_versions(lock), {'pypdf': '5.9.0', 'pypdfium2': '4.30.0'})

    def test_a_version_drift_is_reported(self):
        locked = {'pypdf': '5.9.0', 'pypdfium2': '4.30.0'}
        self.assertEqual(cap.version_mismatches({'pypdf': '5.9.0', 'pypdfium2': '4.30.0'}, locked), [])
        drift = cap.version_mismatches({'pypdf': '6.19.0', 'pypdfium2': None}, locked)
        self.assertEqual(len(drift), 2)
        self.assertIn('pypdf installed 6.19.0, requirements.lock 5.9.0', drift[0])

    def test_the_real_lock_pins_both_libraries(self):
        with open(cap.LOCK, encoding='utf-8') as fh:
            self.assertEqual(set(cap.locked_versions(fh.read())), {'pypdf', 'pypdfium2'})
