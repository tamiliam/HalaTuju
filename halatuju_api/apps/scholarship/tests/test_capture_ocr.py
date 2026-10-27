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
