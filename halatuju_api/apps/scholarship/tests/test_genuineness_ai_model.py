"""OCR-16: the four genuineness checks behind GENUINENESS_MODEL. Default = today's 2.5 call, byte for byte;
set to 3.8 Flash = one model, the answer checked, one retry, a malformed answer = no signal.
Gemini is mocked throughout (no network); synthetic bytes only."""
import json
import pathlib
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.scholarship.genuineness import ai_model, ic, results_doc, sample_stamp, supporting_doc
from apps.scholarship.profile_engine import FLASH_25_CASCADE
from apps.scholarship.read_errors import CASCADE_FAILED, DOCUMENT_FAILED

SEAM = 'apps.scholarship.vision._call_gemini_json'
IMG = 'apps.scholarship.vision._as_image_for_gemini'
M38 = 'gemini-3.8-flash'
VERSIONS = pathlib.Path(__file__).resolve().parents[1] / 'model_versions'

GOOD_IC = {**{m: True for m in ic._IC_GENUINENESS_MARKERS}, 'verdict': 'genuine', 'reason': 'ok'}
GOOD_DOC = {'is_official': True, 'is_expected_type': True, 'doc_seen': 'STR', 'verdict': 'genuine', 'reason': 'ok'}
GOOD_VISUAL = {'has_qr_code': True, 'has_jata_negara_crest': False}
GOOD_SAMPLE = {'is_sample': False, 'reason': 'ok'}

# (name, call the check, a good answer, its parsed result, today's AI-failure outcome)
SITES = [
    ('ic', lambda **k: ic.ic_genuineness(b'img', 'image/jpeg', **k), GOOD_IC,
     lambda r: r['status'] == 'genuine' and all(r['markers'].values()), {}),
    ('supporting', lambda **k: supporting_doc.doc_genuineness(b'img', 'image/jpeg', 'str', **k), GOOD_DOC,
     lambda r: r['status'] == 'genuine' and r['doc_seen'] == 'STR', {}),
    ('results_visual', lambda **k: results_doc.results_visual_markers(b'img', 'image/jpeg', **k), GOOD_VISUAL,
     lambda r: r == {'has_qr': True, 'has_crest': False}, {}),
    ('sample', lambda **k: sample_stamp._ask_model(b'img', 'image/jpeg', **k), GOOD_SAMPLE,
     lambda r: r is False, None),
]


def _img():
    return patch(IMG, return_value=(b'i', 'image/jpeg'))


class TestTheSettingDefaultKeepsToday(SimpleTestCase):
    def test_unset_means_the_25_cascade_one_call_no_retry(self):
        for name, call, good, ok, _fail in SITES:
            with self.subTest(site=name), _img(), patch(SEAM, return_value=good) as m:
                self.assertTrue(ok(call()))
                self.assertEqual(m.call_count, 1)
                self.assertEqual(m.call_args.kwargs['models'], FLASH_25_CASCADE)
                self.assertNotIn('enum', json.dumps(m.call_args.args[1]))   # the schema as today

    def test_unset_does_not_retry_a_malformed_answer(self):
        for name, call, good, _ok, _fail in SITES:
            bad = {k: v for k, v in good.items() if k != list(good)[0]}
            with self.subTest(site=name), _img(), patch(SEAM, return_value=bad) as m:
                call()
                self.assertEqual(m.call_count, 1)

    def test_a_refused_value_stays_on_25(self):
        for value in ('gemini-2.5-flash', 'gemini-3.8-flash-lite', 'gemini-3.8', 'typo'):
            with self.subTest(value=value), override_settings(GENUINENESS_MODEL=value), \
                    self.assertLogs(ai_model.logger, 'WARNING'):
                self.assertEqual(ai_model.chosen_model(), '')
                self.assertEqual(ai_model.genuineness_models(), list(FLASH_25_CASCADE))

    def test_the_env_var_is_read_when_no_setting(self):
        with patch.dict('os.environ', {'GENUINENESS_MODEL': M38}):
            self.assertEqual(ai_model.chosen_model(), M38)
        self.assertEqual(ai_model.chosen_model(), '')


@override_settings(GENUINENESS_MODEL=M38)
class TestTheSettingOnCalls38(SimpleTestCase):
    def test_on_means_38_only_with_a_closed_verdict(self):
        for name, call, good, ok, _fail in SITES:
            with self.subTest(site=name), _img(), patch(SEAM, return_value=good) as m:
                self.assertTrue(ok(call()))
                self.assertEqual(m.call_count, 1)
                self.assertEqual(m.call_args.kwargs['models'], [M38])
                schema = m.call_args.args[1]
                if 'verdict' in schema['properties']:
                    self.assertIn('enum', schema['properties']['verdict'])
        self.assertEqual(ai_model.genuineness_models(), [M38])

    def test_one_retry_on_a_malformed_answer_then_the_good_one(self):
        for name, call, good, ok, _fail in SITES:
            bad = {**good, list(good)[0]: 'yes'}              # wrong JSON type on a required key
            with self.subTest(site=name), _img(), patch(SEAM, side_effect=[bad, good]) as m:
                self.assertTrue(ok(call()))
                self.assertEqual(m.call_count, 2)

    def test_still_malformed_after_the_retry_is_todays_no_signal(self):
        for name, call, good, _ok, fail in SITES:
            missing = {k: v for k, v in good.items() if k != list(good)[-1]}   # a required key missing
            with self.subTest(site=name), _img(), patch(SEAM, return_value=missing) as m:
                self.assertEqual(call(), fail)
                self.assertEqual(m.call_count, ai_model.MAX_CALLS)

    def test_a_verdict_outside_the_words_is_malformed(self):
        with _img(), patch(SEAM, return_value={**GOOD_IC, 'verdict': 'probably'}) as m:
            self.assertEqual(ic.ic_genuineness(b'img', 'image/jpeg'), {})
            self.assertEqual(m.call_count, 2)
        with _img(), patch(SEAM, side_effect=[{**GOOD_DOC, 'verdict': 'maybe'}, {**GOOD_DOC, 'verdict': 'Wrong_Type'}]):
            self.assertEqual(supporting_doc.doc_genuineness(b'img', 'image/jpeg', 'epf')['status'], 'not_epf')

    def test_a_document_refusal_is_retried_once(self):
        refused = {'_error': DOCUMENT_FAILED + ': x'}
        with _img(), patch(SEAM, side_effect=[refused, GOOD_IC]) as m:
            self.assertEqual(ic.ic_genuineness(b'img', 'image/jpeg')['status'], 'genuine')
            self.assertEqual(m.call_count, 2)
        with _img(), patch(SEAM, return_value=refused) as m:
            self.assertIsNone(sample_stamp._ask_model(b'img', 'image/jpeg'))
            self.assertEqual(m.call_count, 2)

    def test_a_service_error_is_not_retried(self):
        for name, call, _good, _ok, fail in SITES:
            with self.subTest(site=name), _img(), patch(SEAM, return_value={'_error': CASCADE_FAILED + ': 429'}) as m:
                self.assertEqual(call(), fail)
                self.assertEqual(m.call_count, 1)

    def test_a_non_dict_answer_is_malformed(self):
        with _img(), patch(SEAM, side_effect=[['x'], GOOD_VISUAL]) as m:
            self.assertEqual(results_doc.results_visual_markers(b'img'), {'has_qr': True, 'has_crest': False})
            self.assertEqual(m.call_count, 2)


class TestTheForcedModel(SimpleTestCase):
    def test_the_eval_can_force_38_while_the_setting_is_unset(self):
        for name, call, good, ok, _fail in SITES:
            with self.subTest(site=name), _img(), patch(SEAM, return_value=good) as m:
                self.assertTrue(ok(call(model=M38)))
                self.assertEqual(m.call_args.kwargs['models'], [M38])

    def test_a_forced_non_38_model_makes_no_call(self):
        with _img(), patch(SEAM) as m:
            self.assertEqual(ic.ic_genuineness(b'img', 'image/jpeg', model='gemini-2.5-flash'), {})
            m.assert_not_called()


class TestTheSchemas(SimpleTestCase):
    def test_every_field_the_code_reads_is_required(self):
        for schema in (ic._IC_GENUINENESS_SCHEMA, supporting_doc._DOC_GENUINENESS_SCHEMA,
                       results_doc._VISUAL_SCHEMA, sample_stamp._SCHEMA):
            with self.subTest(schema=sorted(schema['properties'])):
                self.assertEqual(sorted(schema['required']), sorted(schema['properties']))

    def test_the_38_schema_keeps_every_key_required(self):
        s = ai_model._with_enum(ic._IC_GENUINENESS_SCHEMA, set(ic._GENUINENESS_STATUS))
        self.assertEqual(s['required'], ic._IC_GENUINENESS_SCHEMA['required'])
        self.assertEqual(s['properties']['verdict']['enum'], ['genuine', 'not_an_ic', 'suspect'])
        self.assertNotIn('enum', ic._IC_GENUINENESS_SCHEMA['properties']['verdict'])   # never mutated


class TestTheVersionBumps(SimpleTestCase):
    def test_each_check_moved_to_a_new_logged_version(self):
        for key, version, old in (('ic', ic.MODEL_VERSION, '1.0.0'),
                                  ('supporting_doc', supporting_doc.MODEL_VERSION, '1.0.0'),
                                  ('sample_stamp', sample_stamp.SAMPLE_CHECK_VERSION, '1.0.0'),
                                  ('results_doc', results_doc.MODEL_VERSION, '1.36.0')):
            with self.subTest(model=key):
                log = json.loads((VERSIONS / f'{key}.json').read_text(encoding='utf-8'))
                self.assertIn(old, log)
                self.assertEqual(list(log)[-1], version)
                self.assertNotEqual(version, old)
        self.assertEqual((ic.MODEL_VERSION, supporting_doc.MODEL_VERSION, sample_stamp.SAMPLE_CHECK_VERSION,
                          results_doc.MODEL_VERSION), ('1.1.0', '1.1.0', '1.1.0', '1.37.0'))
