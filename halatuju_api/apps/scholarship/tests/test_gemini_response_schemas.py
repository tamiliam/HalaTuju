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
    out.update({f'ai_model.ask[3.8]({k})': v for k, v in _schemas_sent_on_38().items()})
    return out


#: OCR-16: the four genuineness checks, by the name the 3.8 walk files their schema under.
_CHECKS_38 = ('ic', 'results_doc', 'sample_stamp', 'supporting_doc')


def _schemas_sent_on_38():
    """{check: schema} as `ai_model.ask` SENDS it on the 3.8 path (`_with_enum` adds the verdict enum), caught
    at the mocked `vision._call_gemini_json`. A service error ends each ask after one call. No network."""
    from unittest import mock

    from apps.scholarship import vision
    from apps.scholarship.genuineness import ic, results_doc, sample_stamp, supporting_doc
    model = 'gemini-3.8-flash'
    runs = {
        'ic': lambda: ic.ic_genuineness(b'x', 'image/png', model=model),
        'results_doc': lambda: results_doc.results_visual_markers(b'x', 'image/png', model=model),
        'sample_stamp': lambda: sample_stamp._ask_model(b'x', 'image/png', model=model),
        'supporting_doc': lambda: supporting_doc.doc_genuineness(b'x', 'image/png', 'str', model=model),
    }
    sent = {}
    for name in _CHECKS_38:
        def caught(prompt, schema, *a, _name=name, **k):
            sent[_name] = schema
            return {'_error': 'service down'}
        with mock.patch.object(vision, '_as_image_for_gemini', return_value=(b'x', 'image/png')), \
                mock.patch.object(vision, '_call_gemini_json', caught):
            runs[name]()
    return sent


#: Every `_call_gemini_json(prompt, <schema>)` call site in apps/ (tests excluded), and (OCR-16) every
#: `ai_model.ask(prompt, <schema>)` call site: file → the schema expressions it passes. 'schema' is a
#: variable: `_FIELD_SCHEMAS` (gemini_read), OFFER_SCHEMA / LATER_SCHEMA (offer_reader), and in ai_model
#: the schema an ask site passes (the four genuineness entries) or, on 3.8, 'schema38' (that schema with
#: the verdict enum, walked as sent by `_schemas_sent_on_38`); all in `_all_schemas`.
_CALL_SITES = {
    'scholarship/genuineness/ai_model.py': {'schema', 'schema38'},
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


def _ai_model_names(tree):
    """(names bound to `ai_model.ask`, names bound to the `ai_model` module) by the imports of one module."""
    asks, modules = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (node.module or '').split('.')[-1] == 'ai_model' and alias.name == 'ask':
                    asks.add(alias.asname or alias.name)
                elif alias.name == 'ai_model':
                    modules.add(alias.asname or alias.name)
    return asks, modules


def _is_ai_model_ask(func, asks, modules):
    """True for a call of `ask` imported from ai_model, or of `ai_model.ask`."""
    if isinstance(func, ast.Name):
        return func.id in asks
    return (isinstance(func, ast.Attribute) and func.attr == 'ask' and isinstance(func.value, ast.Name)
            and func.value.id in modules)


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
            asks, modules = _ai_model_names(tree)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
                if fn == '_call_gemini_json' or _is_ai_model_ask(node.func, asks, modules):
                    arg = node.args[1] if len(node.args) > 1 else next(
                        (k.value for k in node.keywords if k.arg == 'schema'), None)
                    sites.setdefault(rel, set()).add(ast.unparse(arg) if arg is not None else '<none>')
                for k in node.keywords:
                    if k.arg == 'response_schema':
                        keywords.setdefault(rel, set()).add(ast.unparse(k.value))
    return sites, keywords


class EverySchemaIsOneGeminiAccepts(SimpleTestCase):
    maxDiff = None   # a missing call site must show by name

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

    def test_the_38_genuineness_schemas_are_walked_as_sent(self):
        """OCR-16: all four checks' 3.8 schemas are caught; the IC and supporting ones carry the verdict enum."""
        sent = _schemas_sent_on_38()
        self.assertEqual(set(sent), set(_CHECKS_38))
        for name in ('ic', 'supporting_doc'):
            self.assertTrue(sent[name]['properties']['verdict'].get('enum'), name)

    def test_the_scan_sees_an_ai_model_ask_however_it_is_imported(self):
        src = ('from .ai_model import ask as a\nfrom apps.scholarship.genuineness import ai_model\n'
               'a(p, S1, image=i)\nai_model.ask(p, schema=S2, image=i)\nother.ask(p, S3)\n')
        tree = ast.parse(src)
        asks, modules = _ai_model_names(tree)
        hits = {ast.unparse(n.args[1] if len(n.args) > 1 else n.keywords[0].value) for n in ast.walk(tree)
                if isinstance(n, ast.Call) and _is_ai_model_ask(n.func, asks, modules)}
        self.assertEqual(hits, {'S1', 'S2'})


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

    def test_a_keyword_the_check_does_not_know_is_flagged(self):
        """Short-check LOW-6: nothing vouches for an unknown keyword, so it is flagged, deep too."""
        for word, value in (('additionalProperties', False), ('$ref', '#/defs/x'),
                            ('anyOf', [{'type': 'string'}]), ('format', 'date')):
            with self.subTest(word=word):
                problems = self._problems({'type': 'string', word: value})
                self.assertTrue(any(f'properties[f].{word}' in p for p in problems))
                top = gemini_schema_problems({'type': 'object', 'properties': {
                    'f': {'type': 'string'}}, word: value})
                self.assertTrue(any(f'schema.{word}' in p for p in top))
        deep = {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                           'properties': {'g': {'type': 'string'}}}}
        self.assertTrue(any('items.additionalProperties' in p for p in self._problems(deep)))

    def test_problems_deep_in_the_tree_are_found(self):
        deep = {'type': 'array', 'items': {'type': 'object', 'properties': {
            'g': {'type': 'string', 'enum': ['A', '']}}}}
        self.assertTrue(any('items.properties[g].enum[1]' in p for p in self._problems(deep)))
