"""Today's AI offer reader on local letter files (`eval/offer_fresh_read.py`) — offer exact-read
S3, 2026-11-01. Synthetic twins and a FAKE Gemini client only: no network, every letter invented
and built in a temp folder; nothing reads the gitignored corpus (`test_no_gitignored_corpus.py`)."""
import io
import json
import os
import tempfile
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.scholarship import usage, vision
from apps.scholarship.eval import offer_fresh_read as fr
from apps.scholarship.eval import offer_read_check as orc

#: Invented values. None may appear in any printed output.
SECRET_NAME = 'ZORBEX A/L QUENTARO'
SECRET_NRIC = '010203-14-5678'
SECRET_INST = 'UNIVERSITI QORVANE PERLAK'
SECRET_PROG = 'IJAZAH SARJANA MUDA ZANTHARION'

FIELDS = {'candidate_name': SECRET_NAME, 'candidate_nric': SECRET_NRIC,
          'institution': SECRET_INST, 'programme': SECRET_PROG, 'intake': 'SESI 2031/2032',
          'reporting_date': '17 Ogos 2031', 'offer_date': '3 Mac 2031', 'issuer': SECRET_INST,
          'warnings': []}
VERSIONS = {'git_head': 'test', 'vision_py_sha256': 'x', 'schema_sha256': 'y', 'genai_sdk': 't'}


def _png(size=(900, 1200)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', size, 'white').save(buf, format='PNG')
    return buf.getvalue()


def _pdf():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (600, 800), 'white').save(buf, format='PDF')
    return buf.getvalue()


def _answer(**over):
    a = {'candidate_name': SECRET_NAME, 'candidate_nric': SECRET_NRIC,
         'institution_as_printed': SECRET_INST, 'institution_campus': None,
         'programme': SECRET_PROG, 'stream': None, 'specialisation': None,
         'intake': 'SESI 2031/2032', 'reporting_date': '17 Ogos 2031', 'offer_date': '3 Mac 2031',
         'issuer': SECRET_INST, 'duration': None, 'fees': None, 'is_offer_letter': 'yes',
         'pages': 1, 'unsure_fields': [], 'labeller_note': None, 'family': 'other_university'}
    a.update(over)
    return a


class FakeError(Exception):
    def __init__(self, code):
        super().__init__(f'{code} fake provider error')
        self.code = code


def _resp(text=None, prompt=1500, out=250, think=900, version='gemini-2.5-flash-001'):
    md = SimpleNamespace(prompt_token_count=prompt, candidates_token_count=out,
                         thoughts_token_count=think, total_token_count=prompt + out + think,
                         cached_content_token_count=None,
                         prompt_tokens_details=[SimpleNamespace(modality='TEXT', token_count=1200),
                                                SimpleNamespace(modality='IMAGE',
                                                                token_count=prompt - 1200)])
    return SimpleNamespace(text=json.dumps(FIELDS) if text is None else text, usage_metadata=md,
                           model_version=version)


class FakeGemini:
    """A stand-in for `google.genai.Client`: `script` is a list of responses or exceptions,
    consumed one per `generate_content` call; `log` keeps the models asked."""

    def __init__(self, script):
        self.script, self.log = list(script), []

    def __call__(self, *a, **k):          # the factory: genai.Client(api_key=...)
        return SimpleNamespace(models=self)

    def generate_content(self, *, model, contents, config=None, **kw):
        self.log.append(model)
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class _Corpus:
    def __init__(self, root):
        self.dir = root
        self.snap = os.path.join(root, 'snapshots')
        self.files = os.path.join(root, 'fixtures', 'offer_letter')
        os.makedirs(self.snap)
        os.makedirs(self.files)

    def letter(self, key, ext='png', data=None, stored=None, answer=True):
        with open(os.path.join(self.files, f'{key}.{ext}'), 'wb') as fh:
            fh.write(data if data is not None else (_pdf() if ext == 'pdf' else _png()))
        with open(os.path.join(self.snap, key + '.json'), 'w', encoding='utf-8') as fh:
            json.dump({'vision_fields': {'fields': stored if stored is not None else {},
                                         'capture': 'ai'}}, fh)
        if answer:
            with open(os.path.join(self.snap, key + orc.ANSWER_SUFFIX), 'w', encoding='utf-8') as fh:
                json.dump(_answer(), fh)

    def split(self, heldout=()):
        p = os.path.join(self.dir, 'split.json')
        with open(p, 'w', encoding='utf-8') as fh:
            json.dump({'heldout': list(heldout)}, fh)
        return p

    def listing(self):
        return sorted(os.path.relpath(os.path.join(d, n), self.dir)
                      for d, _, names in os.walk(self.dir) for n in names)


@override_settings(GEMINI_API_KEY='fake-key-for-tests')
class TestFreshRead(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.c = _Corpus(self._tmp.name)
        self.c.letter('offer_letter__a1__d11', ext='png')
        self.c.letter('offer_letter__a2__d12', ext='pdf')
        self.keys = ['offer_letter__a1__d11', 'offer_letter__a2__d12']
        self.lines = []

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, fake, keys=None, force=False):
        return fr.read_letters(self.c.dir, keys or self.keys, client_factory=fake, force=force,
                      out=self.lines.append, versions=VERSIONS)

    def test_reads_through_production_and_caches_the_scorer_shape(self):
        fake = FakeGemini([_resp(), _resp()])
        code, done = self._run(fake)
        self.assertEqual((code, len(done)), (0, 2))
        self.assertEqual(fake.log, ['gemini-2.5-flash', 'gemini-2.5-flash'])
        rec = orc.read_json_file(fr.fresh_path(self.c.dir, 'offer_letter__a2__d12'))
        self.assertEqual(rec['model'], 'gemini-2.5-flash')
        self.assertEqual(rec['image']['mime'], 'image/png')          # a PDF is shown as page 1 PNG
        self.assertEqual(rec['calls'][0]['thinking_tokens'], 900)
        self.assertEqual(rec['calls'][0]['input_by_modality'], {'TEXT': 1200, 'IMAGE': 300})
        self.assertEqual(rec['calls'][0]['model_version'], 'gemini-2.5-flash-001')
        fields, capture = orc.read_source('file:' + fr.FRESH_SUFFIX)(self.c.dir, 'offer_letter__a1__d11')
        self.assertEqual((fields['institution'], capture), (SECRET_INST, 'ai_fresh'))
        # production's clean-up ran: the reporting date is normalised to D Mon YYYY
        self.assertEqual(fields['reporting_date'], '17 Aug 2031')

    def test_cache_first_a_cached_letter_is_not_read_again_unless_forced(self):
        self._run(FakeGemini([_resp(), _resp()]))
        again = FakeGemini([])
        code, done = self._run(again)
        self.assertEqual((code, done, again.log), (0, [], []))
        self.assertIn('cached already (skipped): 2 | to read now: 0', self.lines[-1])
        forced = FakeGemini([_resp()])
        self._run(forced, keys=['offer_letter__a1__d11'], force=True)
        self.assertEqual(forced.log, ['gemini-2.5-flash'])

    def test_writes_nothing_but_the_cache_and_the_log(self):
        before = self.c.listing()
        with mock.patch('apps.scholarship.models.UsageEvent.objects') as events, \
                mock.patch.object(vision, '_fetch_image_bytes') as storage:
            self._run(FakeGemini([_resp(), _resp()]))
        events.create.assert_not_called()
        storage.assert_not_called()
        added = sorted(set(self.c.listing()) - set(before))
        self.assertEqual(added, sorted([fr.LOG_NAME,
                                        os.path.join('snapshots', 'offer_letter__a1__d11.fresh.json'),
                                        os.path.join('snapshots', 'offer_letter__a2__d12.fresh.json')]))
        self.assertEqual((usage.record_usage.__module__, usage.record_usage.__name__),
                         ('apps.scholarship.usage', 'record_usage'))           # patch undone

    def test_the_meter_figures_are_kept_and_leave_out_thinking(self):
        self._run(FakeGemini([_resp(prompt=1500, out=250, think=900)]), keys=['offer_letter__a1__d11'])
        rec = orc.read_json_file(fr.fresh_path(self.c.dir, 'offer_letter__a1__d11'))
        self.assertEqual(rec['meter'], [{'service': 'gemini', 'model': 'gemini-2.5-flash',
                                         'input_tokens': 1500, 'output_tokens': 250}])
        self.assertEqual(rec['usage']['thinking_tokens'], 900)        # billed, not metered

    def test_a_database_query_inside_the_run_is_refused(self):
        from django.db import connections
        with fr.guarded_production_read(FakeGemini([]), [], []):
            for alias in connections:
                self.assertIn(fr._refuse_db, connections[alias].execute_wrappers)
        for alias in connections:
            self.assertNotIn(fr._refuse_db, connections[alias].execute_wrappers)
        with self.assertRaises(fr.DatabaseRefused):
            fr._refuse_db(None, 'SELECT 1', (), False, {})

    def test_a_402_stops_the_whole_run_without_fall_through(self):
        fake = FakeGemini([FakeError(402), _resp(), _resp()])
        code, done = self._run(fake)
        self.assertEqual((code, done), (fr.EXIT_STOPPED, []))
        self.assertEqual(fake.log, ['gemini-2.5-flash'])             # no flash-lite, no 2nd letter
        self.assertFalse([n for n in os.listdir(self.c.snap) if n.endswith(fr.FRESH_SUFFIX)])
        with open(os.path.join(self.c.dir, fr.LOG_NAME), encoding='utf-8') as fh:
            entry = json.loads(fh.readline())
        self.assertEqual((entry['outcome'], entry['code']), ('STOPPED', 402))

    def test_a_429_in_the_message_also_stops(self):
        fake = FakeGemini([RuntimeError('429 RESOURCE_EXHAUSTED quota'), _resp()])
        code, _ = self._run(fake)
        self.assertEqual((code, fake.log), (fr.EXIT_STOPPED, ['gemini-2.5-flash']))

    def test_another_error_walks_the_production_cascade(self):
        fake = FakeGemini([FakeError(503), _resp(version='lite-001')])
        code, done = self._run(fake, keys=['offer_letter__a1__d11'])
        self.assertEqual(fake.log, ['gemini-2.5-flash', 'gemini-2.5-flash-lite'])
        self.assertEqual((code, done[0]['model']), (0, 'gemini-2.5-flash-lite'))
        lite = fr.PRICES['gemini-2.5-flash-lite']
        self.assertAlmostEqual(done[0]['usage']['cost_usd'],
                               (1500 * lite['input'] + 250 * lite['output'] + 900 * lite['thinking']) / 1e6)

    def test_the_real_client_is_kept_alive_while_its_models_are_used(self):
        """Regression (2026-11-01 pilot, nothing billed): the wrapper kept only `client.models`,
        the genai.Client was garbage-collected and closed its HTTP session, and every call failed
        with "the client has been closed"."""
        import weakref

        class _Models:
            def __init__(self, owner):
                self.owner = weakref.ref(owner)

            def generate_content(self, **kw):
                if self.owner() is None:
                    raise RuntimeError('Cannot send a request, as the client has been closed.')
                return _resp()

        class _ClosingClient:
            def __init__(self, *a, **k):
                self.models = _Models(self)

        code, done = self._run(_ClosingClient, keys=['offer_letter__a1__d11'])
        self.assertEqual((code, done[0]['model']), (0, 'gemini-2.5-flash'))

    def test_every_call_raising_is_not_cached(self):
        code, done = self._run(FakeGemini([FakeError(503), FakeError(500)]),
                               keys=['offer_letter__a1__d11'])
        self.assertEqual((code, done), (fr.EXIT_FAILED, []))
        self.assertFalse(os.path.exists(fr.fresh_path(self.c.dir, 'offer_letter__a1__d11')))

    def test_no_value_is_ever_printed_or_logged(self):
        self._run(FakeGemini([_resp(), _resp()]))
        with open(os.path.join(self.c.dir, fr.LOG_NAME), encoding='utf-8') as fh:
            text = ('\n'.join(self.lines) + fh.read()).upper()
        for token in ('ZORBEX', 'QUENTARO', 'QORVANE', 'ZANTHARION', '010203', '2031'):
            self.assertNotIn(token, text)


class TestCost(SimpleTestCase):
    def test_each_part_is_priced_from_the_table(self):
        c = fr.call_cost_usd('gemini-2.5-flash', 1000, 200, 800)
        self.assertAlmostEqual(c['input'], 1000 * 0.30 / 1e6)
        self.assertAlmostEqual(c['output'], 200 * 2.50 / 1e6)
        self.assertAlmostEqual(c['thinking'], 800 * 2.50 / 1e6)
        self.assertAlmostEqual(c['total'], 0.0028)
        self.assertAlmostEqual(fr.usd_to_myr(c['total']), 0.0028 * 4.4)

    def test_model_names_resolve_to_the_right_row(self):
        self.assertIs(fr.price_for('gemini-2.5-flash-lite'), fr.PRICES['gemini-2.5-flash-lite'])
        self.assertIs(fr.price_for('models/gemini-2.5-flash'), fr.PRICES['gemini-2.5-flash'])
        self.assertIsNone(fr.price_for('gemini-9-ultra'))
        self.assertIsNone(fr.call_cost_usd('gemini-9-ultra', 1, 1, 1))

    def test_missing_counts_cost_nothing(self):
        self.assertEqual(fr.call_cost_usd('gemini-2.5-flash', None, None, None)['total'], 0)

    def test_image_token_rule(self):
        self.assertEqual(fr.image_tokens_estimate(300, 384), 258)
        self.assertEqual(fr.image_tokens_estimate(2114, 2992), 258)   # measured: one tile, any size

    def test_error_code(self):
        self.assertEqual(fr.error_code(FakeError(402)), 402)
        self.assertEqual(fr.error_code(RuntimeError('HTTP 429 Too Many')), 429)
        self.assertIsNone(fr.error_code(RuntimeError('boom')))


class TestDryRunAndCompare(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.c = _Corpus(self._tmp.name)
        self.c.letter('offer_letter__a1__d11', ext='png',
                      stored={**FIELDS, 'candidate_nric': ''})
        self.c.letter('offer_letter__a2__d12', ext='pdf', stored=FIELDS)
        self.c.letter('offer_letter__a3__d13', ext='png', answer=False)    # not answered
        self.split = self.c.split(heldout=['offer_letter__a1__d11'])

    def tearDown(self):
        self._tmp.cleanup()

    def test_dry_run_counts_answered_letters_and_calls_nothing(self):
        before = self.c.listing()
        fake = FakeGemini([])
        lines = []
        rc = fr.main(['--eval-dir', self.c.dir, '--split-file', self.split, '--dry-run'],
                     client_factory=fake, out=lines.append)
        self.assertEqual((rc, fake.log, self.c.listing()), (0, [], before))
        self.assertIn('letters: 2', lines[0])
        e = fr.estimate(self.c.dir, fr.select_keys(self.c.dir, split='heldout',
                                                   split_file=self.split))
        self.assertEqual((e['letters'], e['calls_estimated']), (1, 1))
        self.assertGreater(e['prompt_text_tokens_est'], 100)
        self.assertLess(e['estimate']['low']['usd'], e['estimate']['high']['usd'])

    @override_settings(GEMINI_API_KEY='fake-key-for-tests')
    def test_compare_scores_stored_and_fresh_on_the_same_letters(self):
        fr.read_letters(self.c.dir, ['offer_letter__a1__d11'], client_factory=FakeGemini([_resp()]),
               out=lambda *_: None, versions=VERSIONS)
        c = fr.compare(self.c.dir, 'all', self.split)
        self.assertEqual(c['letters'], 1)
        self.assertEqual(c['fields']['stored']['nric']['missing'], 1)
        self.assertEqual(c['fields']['fresh']['nric']['exact'], 1)
        self.assertEqual(c['changed']['nric'], {'fixed': 1, 'broke': 0, 'same': 0})
        self.assertEqual(c['fully_exact'], {'stored': 0, 'fresh': 1})

    def test_the_scorer_skips_letters_with_no_fresh_file(self):
        with open(fr.fresh_path(self.c.dir, 'offer_letter__a1__d11'), 'w', encoding='utf-8') as fh:
            json.dump({'fields': FIELDS, 'capture': 'ai_fresh'}, fh)
        out = io.StringIO()
        with mock.patch('sys.stdout', out):
            orc.main(['--eval-dir', self.c.dir, '--split-file', self.split, '--split', 'all',
                      '--read', 'file:' + fr.FRESH_SUFFIX])
        text = out.getvalue()
        self.assertIn('answered letters with no read file (not scored): 1', text)
        self.assertIn('FULLY EXACT (every core field exact or blank_correct): 1 of 1', text)
