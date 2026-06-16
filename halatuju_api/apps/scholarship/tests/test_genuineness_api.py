"""Characterization tests for the genuineness PUBLIC SURFACE — the contract a relocation
(moving the checks into a genuineness/ package) must preserve. Green before the move and
must stay green after: same import paths, same patch seam, same stored-dict shape.

Behaviour is covered by test_genuineness.py; this file pins the SURFACE, so a refactor that
silently breaks an import or drops a dict key is caught immediately.
"""
from unittest.mock import patch
from django.test import SimpleTestCase


class TestBackwardCompatibleImports(SimpleTestCase):
    """These import paths are used across the codebase (vision.py upload path, tests) and
    MUST keep resolving after the checks move into a package (via re-export shims)."""

    def test_vision_exposes_ic_and_doc_genuineness(self):
        from apps.scholarship import vision
        self.assertTrue(callable(vision.ic_genuineness))
        self.assertTrue(callable(vision.doc_genuineness))

    def test_from_vision_import_still_works(self):
        from apps.scholarship.vision import ic_genuineness, doc_genuineness  # noqa: F401
        self.assertTrue(callable(ic_genuineness) and callable(doc_genuineness))

    def test_signature_scorer_importable(self):
        from apps.scholarship.doc_signatures import signature_genuineness, score_signatures  # noqa: F401
        self.assertTrue(callable(signature_genuineness) and callable(score_signatures))

    def test_genuineness_doc_types_set_still_on_vision(self):
        # vision.run_field_extraction gates the genuineness call on `doc.doc_type in
        # _GENUINENESS_DOCS` (only reached when the flag is ON — off in tests). Pin that the
        # name still resolves on the vision module after the move, or prod would NameError.
        from apps.scholarship import vision
        self.assertIn('results_slip', vision._GENUINENESS_DOCS)
        self.assertIn('str', vision._GENUINENESS_DOCS)

    def test_genuineness_package_entry_point(self):
        from apps.scholarship import genuineness
        self.assertTrue(callable(genuineness.assess))
        for n in ('ic_genuineness', 'doc_genuineness', 'signature_genuineness', 'band_for'):
            self.assertTrue(callable(getattr(genuineness, n)))


class TestPatchSeamPreserved(SimpleTestCase):
    """The whole test-suite mocks Gemini at apps.scholarship.vision._call_gemini_json.
    After the move, the checks must STILL route through that name (call it as a module
    attribute, not a bound local) or every genuineness test would silently hit a live call."""

    def test_patching_vision_seam_controls_ic_genuineness(self):
        from apps.scholarship import vision
        with patch('apps.scholarship.vision._call_gemini_json',
                   return_value={'verdict': 'genuine', 'has_face_photo': True}):
            self.assertEqual(vision.ic_genuineness(b'x', 'image/png')['status'], 'genuine')

    def test_patching_vision_seam_controls_doc_genuineness(self):
        from apps.scholarship import vision
        with patch('apps.scholarship.vision._call_gemini_json',
                   return_value={'verdict': 'suspect', 'is_official': False,
                                 'is_expected_type': True, 'doc_seen': 'typed', 'reason': 'r'}):
            self.assertEqual(vision.doc_genuineness(b'x', 'image/png', 'str')['status'], 'suspect')


class TestStoredDictContract(SimpleTestCase):
    """The authenticity dict is read by the serializer, anomaly engine, and verdict cap via
    fixed keys. Pin the shape so a relocation can't quietly drop one."""

    def test_ic_dict_has_status_markers_reason(self):
        from apps.scholarship import vision
        with patch('apps.scholarship.vision._call_gemini_json',
                   return_value={'verdict': 'suspect', 'has_chip': False, 'reason': 'typed'}):
            r = vision.ic_genuineness(b'x', 'image/png')
        self.assertEqual(set(r), {'status', 'markers', 'reason'})

    def test_doc_dict_has_status_docseen_reason(self):
        from apps.scholarship import vision
        with patch('apps.scholarship.vision._call_gemini_json',
                   return_value={'verdict': 'genuine', 'is_official': True,
                                 'is_expected_type': True, 'doc_seen': 'STR', 'reason': 'r'}):
            r = vision.doc_genuineness(b'x', 'image/png', 'str')
        self.assertEqual(set(r), {'status', 'doc_seen', 'reason'})
