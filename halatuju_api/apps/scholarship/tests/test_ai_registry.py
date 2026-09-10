"""The AI registry, and the guard that stops it going stale.

`halatuju/ai_registry.py` answers "which AI version is each job set to". It is only worth having
if it is COMPLETE, and a hand-maintained list is complete for about a month. So the load-bearing
test here is not that the list is right today — it is that a NEW AI job cannot be added without
appearing on it.
"""
import pathlib
import re

from django.test import TestCase, override_settings

from halatuju import ai_registry

API_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: A file "calls AI" if it reaches a provider directly, or through one of the two shared seams.
#: Kept as separate patterns rather than one alternation so a failure message can say WHICH.
_CALLS_AI = re.compile(
    r'genai\.Client\('                     # its own provider client
    r'|_call_gemini_json\('                # the structured-read seam
    r'|_call_gemini_text\('                # the prose seam
    r'|record_usage\(\s*usage\.(GEMINI|OPENAI)'   # metered as an AI call
)

#: Files that match the pattern and are NOT jobs, each for a stated reason. A bare exclude list
#: rots as quietly as the registry would, so every entry says why it is here.
_NOT_A_JOB = {
    # Defines the constants the pattern looks for; meters everything, calls nothing.
    'apps/scholarship/usage.py',
    # The seams themselves are named by the jobs that use them, not listed as jobs.
    # (`vision.py` and `profile_engine.py` ARE jobs as well, so they are not excluded.)
}


def _source_files():
    """Every non-test, non-eval Python file under the app tree."""
    for p in API_ROOT.rglob('*.py'):
        rel = p.relative_to(API_ROOT).as_posix()
        if not rel.startswith('apps/'):
            continue
        if '/tests/' in rel or '/eval/' in rel or '/migrations/' in rel:
            continue
        yield rel, p


def _files_that_call_ai():
    out = set()
    for rel, p in _source_files():
        try:
            src = p.read_text(encoding='utf-8')
        except OSError:            # pragma: no cover — unreadable file is not a test failure
            continue
        if _CALLS_AI.search(src):
            out.add(rel)
    return out - _NOT_A_JOB


class TestTheRegistryCannotGoStale(TestCase):
    def test_every_file_that_calls_AI_is_a_registered_job(self):
        """⚠ THE POINT OF THE WHOLE SPRINT. Without this the list is a snapshot of 2026-09-11 and
        the next AI job ships invisible — which is exactly the state the sprint was called to end
        (the model name was already recorded on every call and nothing read it back).

        ⚠ COUNTED BY FILE, NOT BY NAME. A guard asking "does the registry mention gemini?" is
        satisfied by an import line (lessons.md, 2026-09-07); this asks whether each file that can
        reach a model is accounted for, which an import cannot fake.
        """
        registered = {j['module'] for j in ai_registry.JOBS}
        calling = _files_that_call_ai()
        missing = sorted(calling - registered)
        self.assertEqual(missing, [], (
            'These files reach an AI model and are not in halatuju/ai_registry.JOBS. Add an entry '
            '(or, if it genuinely is not a job, add it to _NOT_A_JOB WITH A REASON):\n  '
            + '\n  '.join(missing)))

    def test_and_the_guard_would_actually_notice(self):
        """Drive over the bump: prove the scanner finds a real seam rather than returning an
        empty set, which would make the assertion above pass for ever."""
        calling = _files_that_call_ai()
        self.assertIn('apps/scholarship/vision.py', calling)
        self.assertIn('apps/scholarship/profile_engine.py', calling)
        self.assertGreaterEqual(len(calling), 10)

    def test_no_registered_job_points_at_a_file_that_is_gone(self):
        """The other direction: a job whose module was deleted or renamed would leave the screen
        naming something that no longer exists."""
        for job in ai_registry.JOBS:
            with self.subTest(job=job['key']):
                self.assertTrue((API_ROOT / job['module']).exists(),
                                f"{job['key']} names {job['module']}, which is not there")


class TestItResolvesRatherThanRemembers(TestCase):
    def test_a_setting_backed_job_reads_the_setting_live(self):
        """⚠ THE REASON THE REGISTRY STORES NO MODEL NAMES. If it kept its own copy, this screen
        would keep saying 2.5-pro after somebody moved the setting, and the reader would have no
        way to tell. Overriding the setting must move the answer."""
        with override_settings(CONTRACT_QUIZ_MODEL='gemini-9.9-imaginary'):
            job = next(j for j in ai_registry.snapshot() if j['key'] == 'contract_quiz')
            self.assertEqual(job['model'], 'gemini-9.9-imaginary')

    def test_a_cascade_backed_job_reads_the_live_list(self):
        job = next(j for j in ai_registry.snapshot() if j['key'] == 'doc_read')
        from apps.scholarship.profile_engine import MODEL_CASCADE
        self.assertEqual([job['model']] + job['fallbacks'], list(MODEL_CASCADE))

    def test_a_fallback_list_never_repeats_the_first_model(self):
        # Otherwise the screen reads "gemini-2.5-flash, then gemini-2.5-flash" — which looks like
        # a bug in the cascade rather than a bug in the display.
        for job in ai_registry.snapshot():
            with self.subTest(job=job['key']):
                self.assertNotIn(job['model'], job['fallbacks'])

    def test_a_hardcoded_job_is_flagged_as_fixed(self):
        """⚠ NOT HIDDEN. Two batch commands write the model into the source, so changing them
        needs a deploy. That is the single most useful thing this list can tell somebody planning
        an upgrade, so it is a flag on the row rather than a footnote."""
        fixed = {j['key'] for j in ai_registry.snapshot() if j['fixed']}
        self.assertEqual(fixed, {'course_careers', 'stpm_headlines'})

    def test_the_one_job_with_a_second_provider_says_so(self):
        # The counsellor report falls through to OpenAI — a different key, a different bill. It
        # has never fired on production, which is exactly why an upgrade pass would walk past it.
        job = next(j for j in ai_registry.snapshot() if j['key'] == 'counsellor_report')
        self.assertEqual(job['fallback_provider'], 'openai')
        self.assertEqual(job['fallback_model'], 'gpt-4o-mini')

    def test_models_in_use_covers_the_fallbacks_and_the_other_provider(self):
        models = ai_registry.models_in_use()
        self.assertIn('gemini-2.5-pro', models)        # the pro cascade + three settings
        self.assertIn('gemini-2.0-flash', models)      # bottom of the cascade; a real reachable
        self.assertIn('gpt-4o-mini', models)           # the OpenAI fallback
