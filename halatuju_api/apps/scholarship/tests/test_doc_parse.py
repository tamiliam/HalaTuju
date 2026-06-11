"""Deterministic capture scaffold — label helpers + dispatcher (apps.scholarship.doc_parse).

Per-doc-type parsers (STR, TNB, KWSP, …) get their own real-file-validated tests as they
land; this covers the shared infrastructure they all build on."""
from django.test import SimpleTestCase

from apps.scholarship import doc_parse
from apps.scholarship.doc_parse import (find_value, has, first_nric, first_amount,
                                        parse_by_labels, register)


class TestFindValue(SimpleTestCase):
    def test_same_line_after_separator(self):
        self.assertEqual(find_value('No. Kad Pengenalan : 800817-07-5636', r'no\.?\s*kad pengenalan'),
                         '800817-07-5636')

    def test_falls_to_next_non_empty_line_when_label_alone(self):
        text = 'Nama\n\nRUSHAINDRA KUMARI A/P JAYARAM\n'
        self.assertEqual(find_value(text, r'nama'), 'RUSHAINDRA KUMARI A/P JAYARAM')

    def test_case_insensitive_and_trims(self):
        self.assertEqual(find_value('STATUS:   Berjaya  ', r'status'), 'Berjaya')

    def test_missing_label_returns_blank(self):
        self.assertEqual(find_value('nothing here', r'jumlah'), '')

    def test_first_match_wins(self):
        self.assertEqual(find_value('Nama: A\nNama: B', r'nama'), 'A')


class TestMarkersAndScalars(SimpleTestCase):
    def test_has_any_pattern(self):
        self.assertTrue(has('… Semakan Status …', r'semakan status'))
        self.assertTrue(has('MySTR portal', r'\bMySTR\b'))
        self.assertFalse(has('plain text', r'dashboard'))

    def test_first_nric_normalises_spacing_and_dashes(self):
        self.assertEqual(first_nric('No 800817 07 5636 here'), '800817-07-5636')
        self.assertEqual(first_nric('800817-07-5636'), '800817-07-5636')
        self.assertEqual(first_nric('no ic at all'), '')

    def test_first_amount_strips_commas(self):
        self.assertEqual(first_amount('Jumlah Bil Anda (RM) 1,234.50'), 'RM1234.50')
        self.assertEqual(first_amount('RM700'), 'RM700')
        self.assertEqual(first_amount('no money'), '')


class TestDispatcher(SimpleTestCase):
    def test_unregistered_doc_type_returns_none(self):
        self.assertIsNone(parse_by_labels('totally_unknown_type', 'some text'))

    def test_blank_text_returns_none(self):
        self.assertIsNone(parse_by_labels('str', '   '))

    def test_a_raising_parser_degrades_to_none(self):
        @register('_test_boom')
        def _boom(_text):
            raise ValueError('kaboom')
        try:
            self.assertIsNone(parse_by_labels('_test_boom', 'x'))
        finally:
            doc_parse._PARSERS.pop('_test_boom', None)

    def test_a_parser_returning_empty_or_nondict_is_none(self):
        @register('_test_empty')
        def _empty(_text):
            return {}
        @register('_test_str')
        def _str(_text):
            return 'not a dict'
        try:
            self.assertIsNone(parse_by_labels('_test_empty', 'x'))
            self.assertIsNone(parse_by_labels('_test_str', 'x'))
        finally:
            doc_parse._PARSERS.pop('_test_empty', None)
            doc_parse._PARSERS.pop('_test_str', None)

    def test_a_valid_parser_result_passes_through(self):
        @register('_test_ok')
        def _ok(_text):
            return {'recipient_name': 'A', 'source_type': 'letter'}
        try:
            self.assertEqual(parse_by_labels('_test_ok', 'x'),
                             {'recipient_name': 'A', 'source_type': 'letter'})
        finally:
            doc_parse._PARSERS.pop('_test_ok', None)
