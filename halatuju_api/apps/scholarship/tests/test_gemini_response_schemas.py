"""Every Gemini response schema in the app is one Gemini accepts (OCR-first S5, fix round 4).

The paid S5 gate lost all 98 slip calls to ``400 INVALID_ARGUMENT ... grade.enum[11]: cannot be
empty``: the slip schema's enum held ''. The SDK sends a schema unchecked and every model call is
mocked in tests, so nothing local caught it. These tests walk EVERY schema passed to Gemini and fail
on what Gemini refuses (`vision.schemas.gemini_schema_problems`), and a source scan fails when a new
call site appears that this walk does not cover. No network.
"""
import ast
import os

from django.test import SimpleTestCase

from apps.scholarship.vision.schemas import gemini_schema_problems

_APPS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))   # halatuju_api/apps


def _all_schemas():
    """{name: schema} for every response schema the app sends to Gemini."""
    from apps.scholarship import gap_engine, help_engine, higher_results, income_declaration, offer_reader
    from apps.scholarship import spend_category
    from apps.scholarship.genuineness import ic, results_doc, sample_stamp, supporting_doc
    from apps.scholarship.vision import gemini_read
    from apps.scholarship.vision.schemas import _FIELD_SCHEMAS
    out = {f'_FIELD_SCHEMAS[{k}]': v for k, v in _FIELD_SCHEMAS.items()}
    out.update({
        'gemini_read._IC_GEMINI_SCHEMA': gemini_read._IC_GEMINI_SCHEMA,
        'genuineness.ic._IC_GENUINENESS_SCHEMA': ic._IC_GENUINENESS_SCHEMA,
        'genuineness.results_doc._VISUAL_SCHEMA': results_doc._VISUAL_SCHEMA,
        'genuineness.sample_stamp._SCHEMA': sample_stamp._SCHEMA,
        'genuineness.supporting_doc._DOC_GENUINENESS_SCHEMA': supporting_doc._DOC_GENUINENESS_SCHEMA,
        'income_declaration._APPROVAL_SCHEMA': income_declaration._APPROVAL_SCHEMA,
        'help_engine._RELEVANCE_SCHEMA': help_engine._RELEVANCE_SCHEMA,
        'gap_engine.GAP_SCHEMA': gap_engine.GAP_SCHEMA,
        'spend_category._AI_SCHEMA': spend_category._AI_SCHEMA,
        'offer_reader.OFFER_SCHEMA': offer_reader.OFFER_SCHEMA,
        'offer_reader.LATER_SCHEMA': offer_reader.LATER_SCHEMA,
        'higher_results.SCHEMA': higher_results.SCHEMA,
    })
    return out


#: Every `_call_gemini_json(prompt, <schema>)` call site in apps/ (tests excluded): file → the
#: schema expressions it passes. 'schema' is a variable: `_FIELD_SCHEMAS` (gemini_read) and
#: OFFER_SCHEMA / LATER_SCHEMA (offer_reader), all in `_all_schemas`.
_CALL_SITES = {
    'scholarship/gap_engine.py': {'GAP_SCHEMA'},
    'scholarship/help_engine.py': {'_RELEVANCE_SCHEMA'},
    'scholarship/income_declaration.py': {'_APPROVAL_SCHEMA'},
    'scholarship/spend_category.py': {'_AI_SCHEMA'},
    'scholarship/offer_reader.py': {'schema'},
    'scholarship/genuineness/ic.py': {'_IC_GENUINENESS_SCHEMA'},
    'scholarship/genuineness/results_doc.py': {'_VISUAL_SCHEMA'},
    'scholarship/genuineness/sample_stamp.py': {'_SCHEMA'},
    'scholarship/genuineness/supporting_doc.py': {'_DOC_GENUINENESS_SCHEMA'},
    'scholarship/vision/gemini_read.py': {'_IC_GEMINI_SCHEMA', 'schema'},
}


def _scan_call_sites():
    """(call sites, response_schema= keywords) found in the source of apps/, tests excluded."""
    sites, keywords = {}, {}
    for root, dirs, names in os.walk(_APPS):
        dirs[:] = [d for d in dirs if d not in ('tests', 'migrations', '__pycache__', 'node_modules')]
        for name in names:
            if not name.endswith('.py'):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, _APPS).replace(os.sep, '/')
            with open(path, encoding='utf-8') as fh:
                tree = ast.parse(fh.read(), filename=rel)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
                if fn == '_call_gemini_json':
                    arg = node.args[1] if len(node.args) > 1 else next(
                        (k.value for k in node.keywords if k.arg == 'schema'), None)
                    sites.setdefault(rel, set()).add(ast.unparse(arg) if arg is not None else '<none>')
                for k in node.keywords:
                    if k.arg == 'response_schema':
                        keywords.setdefault(rel, set()).add(ast.unparse(k.value))
    return sites, keywords


class EverySchemaIsOneGeminiAccepts(SimpleTestCase):
    def test_no_schema_has_an_empty_or_non_string_enum_member(self):
        """The bug the paid gate found: '' in the slip grade enum (and any non-string member)."""
        for name, schema in _all_schemas().items():
            with self.subTest(schema=name):
                self.assertEqual(gemini_schema_problems(schema, name), [])

    def test_the_walk_covers_every_call_site(self):
        """A new `_call_gemini_json` call (or a new `response_schema=`) must be added to the walk."""
        sites, keywords = _scan_call_sites()
        self.assertEqual(sites, _CALL_SITES)
        self.assertEqual(keywords, {'scholarship/vision/gemini_read.py': {'schema'}})

    def test_the_slip_schema_is_walked(self):
        self.assertIn('_FIELD_SCHEMAS[results_slip]', _all_schemas())


class TheSchemaCheck(SimpleTestCase):
    """`gemini_schema_problems` finds what Gemini refuses."""

    def _problems(self, field):
        return gemini_schema_problems({'type': 'object', 'properties': {'f': field}})

    def test_a_good_schema_has_no_problems(self):
        self.assertEqual(self._problems({'type': 'string', 'enum': ['a', 'b']}), [])
        self.assertEqual(self._problems({'type': 'array', 'items': {'type': 'string'}}), [])

    def test_an_empty_enum_member_is_refused(self):
        problems = self._problems({'type': 'string', 'enum': ['A', '']})
        self.assertTrue(any('enum[1]' in p for p in problems))
        self.assertTrue(self._problems({'type': 'string', 'enum': ['A', '  ']}))

    def test_a_non_string_enum_member_is_refused(self):
        for bad in (None, 1, True, ['A']):
            with self.subTest(bad=bad):
                self.assertTrue(self._problems({'type': 'string', 'enum': ['A', bad]}))

    def test_an_empty_or_misplaced_enum_is_refused(self):
        self.assertTrue(self._problems({'type': 'string', 'enum': []}))
        self.assertTrue(self._problems({'type': 'string', 'enum': 'A'}))
        self.assertTrue(self._problems({'type': 'integer', 'enum': ['1']}))
        self.assertTrue(self._problems({'type': 'string', 'enum': ['A', 'A']}))

    def test_an_empty_properties_object_is_refused(self):
        self.assertTrue(gemini_schema_problems({'type': 'object', 'properties': {}}))
        self.assertTrue(gemini_schema_problems({'type': 'object'}))
        self.assertTrue(self._problems({'type': 'object', 'properties': {}}))

    def test_a_required_key_the_object_lacks_is_refused(self):
        self.assertTrue(gemini_schema_problems(
            {'type': 'object', 'properties': {'a': {'type': 'string'}}, 'required': ['b']}))

    def test_an_array_with_no_items_or_an_unknown_type_is_refused(self):
        self.assertTrue(self._problems({'type': 'array'}))
        self.assertTrue(self._problems({'type': 'text'}))
        self.assertTrue(self._problems({'enum': ['a']}))

    def test_problems_deep_in_the_tree_are_found(self):
        deep = {'type': 'array', 'items': {'type': 'object', 'properties': {
            'g': {'type': 'string', 'enum': ['A', '']}}}}
        self.assertTrue(any('items.properties[g].enum[1]' in p for p in self._problems(deep)))
