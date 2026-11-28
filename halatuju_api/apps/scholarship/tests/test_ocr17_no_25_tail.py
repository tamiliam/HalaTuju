"""OCR-17: the fallback tails no longer reach a Gemini 2.5 model.

Three things are pinned: the order of every changed cascade, a guard that no `gemini-2.5` string
creeps back into api source (outside tests, docs, migrations and a short, reasoned exception list),
and the safe "AI unavailable" outcome when every model of the cascade fails. No network, no paid call.
"""
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

NEW_TAIL = ['gemini-3.8-flash', 'gemini-3.6-flash', 'gemini-3.5-flash-lite']
API_ROOT = Path(__file__).resolve().parents[3]

#: path (relative to halatuju_api, forward slashes) -> (the number of lines allowed to say
#: `gemini-2.5`, why). Keep this list as short as it can be; remove a row when its reason goes.
EXCEPTIONS = {
    'apps/scholarship/profile_engine.py': (
        1, 'FLASH_25_CASCADE: the genuineness jobs stay on 2.5 until OCR-16 is switched on; remove then'),
    'apps/scholarship/offer_reader.py': (
        1, 'the refusal guard: the offer reader will not ask a 2.5 model for a missing reporting date'),
    'apps/scholarship/eval/offer_fresh_gemini.py': (
        2, 'eval PRICES rows for 2.5, kept so past eval runs and the genuineness cascade still price'),
    'apps/scholarship/eval/offer_fresh_read.py': (
        1, 'EST_MODEL: the dry-run estimate is built on the measured 2.5 Flash token counts'),
}
SKIP_DIRS = {'tests', 'migrations', 'node_modules', '__pycache__', 'venv', '.venv', 'docs'}


def _source_files():
    for path in API_ROOT.rglob('*.py'):
        rel = path.relative_to(API_ROOT)
        if SKIP_DIRS & set(rel.parts) or path.name.startswith('test_'):
            continue
        yield rel.as_posix(), path


class TheNoTwoPointFiveGuard(SimpleTestCase):
    def test_no_gemini_2_5_string_remains_outside_the_exception_list(self):
        found = {}
        for rel, path in _source_files():
            n = sum(1 for line in path.read_text(encoding='utf-8', errors='replace').splitlines()
                    if re.search(r'gemini-2\.5', line, re.I))
            if n:
                found[rel] = n
        stray = {rel: n for rel, n in found.items() if rel not in EXCEPTIONS}
        self.assertEqual(stray, {}, 'a gemini-2.5 string is back in api source (OCR-17 guard)')
        for rel, (allowed, reason) in EXCEPTIONS.items():
            with self.subTest(path=rel):
                self.assertTrue(reason)
                self.assertLessEqual(found.get(rel, 0), allowed, f'more gemini-2.5 lines than allowed: {reason}')
                self.assertGreater(found.get(rel, 0), 0, 'exception no longer needed: remove its row')

    def test_the_genuineness_files_do_not_name_a_2_5_model_themselves(self):
        # they read FLASH_25_CASCADE; the string lives only in profile_engine
        for rel, path in _source_files():
            if '/genuineness/' in rel:
                self.assertNotRegex(path.read_text(encoding='utf-8', errors='replace'), r'gemini-2\.5')


class TheChangedCascadesAreExactlyTheNewTail(SimpleTestCase):
    def test_every_changed_cascade_is_3_8_3_6_3_5_lite(self):
        from apps.courses.management.commands import generate_stpm_headlines, map_course_careers
        from apps.reports import report_engine
        from apps.scholarship import profile_engine
        cascades = {
            'profile_engine': profile_engine.MODEL_CASCADE,
            'report_engine': report_engine.MODEL_CASCADE,
            'map_course_careers': map_course_careers.MODEL_CASCADE,
            'generate_stpm_headlines': generate_stpm_headlines.MODEL_CASCADE,
        }
        for name, cascade in cascades.items():
            with self.subTest(cascade=name):
                self.assertEqual(cascade, NEW_TAIL)
                self.assertFalse([m for m in cascade if '2.5' in m])

    def test_the_derived_cascades_carry_no_2_5_model(self):
        from apps.scholarship import profile_engine
        self.assertFalse([m for m in profile_engine.PRO_CASCADE if '2.5' in m])
        self.assertFalse([m for m in profile_engine.cascade_from('gemini-3.8-flash') if '2.5' in m])

    def test_the_new_models_are_priced_for_the_paid_eval(self):
        from apps.scholarship.eval.offer_fresh_gemini import price_for
        for model in ('gemini-3.6-flash', 'gemini-3.5-flash-lite'):
            with self.subTest(model=model):
                self.assertIsNotNone(price_for(model))


class WhenEveryModelOfTheCascadeFails(TestCase):
    def _down(self):
        client = MagicMock()
        asked = []

        def generate_content(model, contents, config=None):
            asked.append(model)
            raise RuntimeError('503 UNAVAILABLE: the model is overloaded')
        client.models.generate_content.side_effect = generate_content
        return client, asked

    def test_the_prose_seam_gives_the_service_error_and_asks_each_model_once(self):
        from django.test import override_settings
        from apps.scholarship import read_errors
        from apps.scholarship.profile_engine import _call_gemini_text
        client, asked = self._down()
        with override_settings(GEMINI_API_KEY='k'), patch('google.genai.Client', return_value=client):
            err = _call_gemini_text('prompt', 'English')['error']
        self.assertEqual(asked, NEW_TAIL)
        self.assertTrue(read_errors.is_ai_service_error(err))

    def test_the_json_seam_gives_the_service_error_and_asks_each_model_once(self):
        from django.test import override_settings
        from apps.scholarship import read_errors, vision
        client, asked = self._down()
        with override_settings(GEMINI_API_KEY='k'), patch('google.genai.Client', return_value=client), \
                patch('apps.scholarship.usage.record_usage'):
            result = vision._call_gemini_json('prompt', {'type': 'object'})
        self.assertEqual(asked, NEW_TAIL)
        self.assertTrue(read_errors.is_ai_service_error(result['_error']))
