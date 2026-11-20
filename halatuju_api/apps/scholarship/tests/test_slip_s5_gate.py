"""The OCR-first S5 slip gate script (`eval/slip_s5_gate.py`), on a SYNTHETIC corpus.

The dry run reads every slip through the production read with the model mocked; the live path is
driven with a fake genai client (no network, no key, no database); scoring reads synthetic caches.
"""
import io
import json
import os
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from apps.scholarship.eval import slip_s5_gate as gate

_GOOD = {'candidate_name': 'CALON CONTOH', 'exam': 'SPM 2025',
         'results': [{'subject': 'BAHASA MELAYU', 'grade': 'A', 'band': 'CEMERLANG TINGGI'},
                     {'subject': 'SEJARAH', 'grade': 'B+', 'band': 'KEPUJIAN TERTINGGI'}],
         'warnings': []}


def _png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (40, 40), 'white').save(buf, format='PNG')
    return buf.getvalue()


class _Corpus(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        os.makedirs(os.path.join(self.dir, 'fixtures', 'results_slip'))
        os.makedirs(os.path.join(self.dir, 'snapshots'))
        self.keys = ['results_slip__a1__d1', 'results_slip__a2__d2']
        for k in self.keys:
            with open(os.path.join(self.dir, 'fixtures', 'results_slip', f'{k}.png'), 'wb') as fh:
                fh.write(_png())
        typed = {'bm': 'A', 'hist': 'B+'}
        self._write('applicants.json', {'1': {'profile': {'grades': typed}}, '2': {'profile': {'grades': typed}}})
        stored = {'fields': {**_GOOD, 'results': [{'subject': 'BAHASA MELAYU', 'grade': 'A', 'band': ''},
                                                  {'subject': 'SEJARAH', 'grade': 'C', 'band': ''}]},
                  'error': '', 'capture': 'ai'}
        for k in self.keys:
            self._write(os.path.join('snapshots', f'{k}.json'), {'vision_fields': stored})

    def _write(self, rel, data):
        with open(os.path.join(self.dir, rel), 'w', encoding='utf-8') as fh:
            json.dump(data, fh)


class TheDryRun(_Corpus):
    def test_every_slip_is_read_on_3_8_with_the_model_mocked(self):
        lines = []
        self.assertEqual(gate.main(['--eval-dir', self.dir], out=lines.append), 0)
        self.assertIn("models ['gemini-3.8-flash']", lines[0])
        self.assertIn('2 slips', lines[0])
        self.assertIn('2-4 calls', lines[1])
        self.assertIn('235-470 calls', lines[2])
        self.assertFalse(os.path.exists(os.path.join(self.dir, gate.CACHE_DIR)))   # nothing written

    def test_the_estimate(self):
        self.assertEqual(gate.estimate(98), {'slips': 98, 'calls_min': 98, 'calls_max': 196,
                                             'usd_low': 0.39, 'usd_high': 1.57})

    def test_no_corpus_reads_nothing(self):
        lines = []
        self.assertEqual(gate.main(['--eval-dir', tempfile.gettempdir() + '/no-such-corpus'],
                                   out=lines.append), 2)


_USAGE = SimpleNamespace(prompt_token_count=300, candidates_token_count=40, thoughts_token_count=0,
                         total_token_count=340, cached_content_token_count=None, prompt_tokens_details=None)


class TheLiveRunOnAFakeClient(_Corpus):
    def _factory(self, answer, usage=_USAGE, raises=None):
        self.asked = []

        def generate_content(model, contents, config=None):
            self.asked.append(model)
            if raises is not None:
                raise raises
            return SimpleNamespace(text=json.dumps(answer), usage_metadata=usage)
        client = MagicMock()
        client.models.generate_content.side_effect = generate_content
        return lambda *a, **k: client

    def _cached(self):
        return sorted(os.listdir(os.path.join(self.dir, gate.CACHE_DIR)))

    def test_a_service_failure_is_not_cached(self):
        """Review round 1: a 503 / 404-model answer is our side, so the next run reads it again."""
        factory = self._factory(None, raises=RuntimeError('503 UNAVAILABLE: the model is overloaded'))
        lines = []
        with override_settings(GEMINI_API_KEY='test-key'):
            self.assertEqual(gate.main(['--eval-dir', self.dir, '--live'], client_factory=factory,
                                       out=lines.append), 0)
        self.assertEqual(self.asked, ['gemini-3.8-flash', 'gemini-3.8-flash'])   # one per slip, no retry
        self.assertEqual(self._cached(), [])
        self.assertIn('2 service failure(s) not cached', lines[-1])

    def test_a_response_with_no_token_counts_stops_the_run(self):
        """Review round 1: with no token counts the --max-usd cap cannot be kept."""
        factory = self._factory(_GOOD, usage=None)
        lines = []
        with override_settings(GEMINI_API_KEY='test-key'):
            self.assertEqual(gate.main(['--eval-dir', self.dir, '--live'], client_factory=factory,
                                       out=lines.append), 4)
        self.assertEqual(self.asked, ['gemini-3.8-flash'])          # the second slip is never read
        self.assertEqual(self._cached(), [f'{self.keys[0]}.json'])  # the real read is still kept
        self.assertTrue(lines[-1].startswith('STOP: 1 call(s) reported no token counts'))

    def test_the_cap_stops_the_run(self):
        factory = self._factory(_GOOD)
        lines = []
        with override_settings(GEMINI_API_KEY='test-key'):
            code = gate.main(['--eval-dir', self.dir, '--live', '--max-usd', '0.0001'],
                             client_factory=factory, out=lines.append)
        self.assertEqual(self.asked, ['gemini-3.8-flash'])
        self.assertTrue(any(l.startswith('STOP: the run has cost') for l in lines))
        self.assertEqual(code, gate.EXIT_CAP)       # review round 2: a capped run exits non-zero
        self.assertEqual(gate.EXIT_CAP, 5)

    def test_the_exit_codes_are_in_the_help_text(self):
        buf = io.StringIO()
        with patch('sys.stdout', buf), self.assertRaises(SystemExit):
            gate.main(['--help'])
        self.assertIn('5 --live stopped at its --max-usd cap', ' '.join(buf.getvalue().split()))

    def test_a_look_alike_model_is_refused_before_any_read(self):
        """Review round 2: the gate keeps the slip read's allow-list (`slip_read.is_slip_model`)."""
        for cascade in (['gemini-3.8-flash-lite'], ['gemini-3.81-pro', 'gemini-2.5-flash']):
            factory = self._factory(_GOOD)
            lines = []
            with self.subTest(cascade=cascade), override_settings(GEMINI_API_KEY='test-key'), \
                    patch('apps.scholarship.profile_engine.MODEL_CASCADE', cascade):
                self.assertEqual(gate.main(['--eval-dir', self.dir, '--live'], client_factory=factory,
                                           out=lines.append), 2)
                self.assertEqual(self.asked, [])
                self.assertFalse(os.path.exists(os.path.join(self.dir, gate.CACHE_DIR)))

    def test_it_reads_on_3_8_only_caches_and_never_rereads(self):
        factory = self._factory(_GOOD)
        with override_settings(GEMINI_API_KEY='test-key'):
            self.assertEqual(gate.main(['--eval-dir', self.dir, '--live'], client_factory=factory,
                                       out=lambda *_: None), 0)
            self.assertEqual(self.asked, ['gemini-3.8-flash', 'gemini-3.8-flash'])
            gate.main(['--eval-dir', self.dir, '--live'], client_factory=factory, out=lambda *_: None)
        self.assertEqual(len(self.asked), 2)                    # cache first: no second read
        lines = []
        gate.main(['--eval-dir', self.dir, '--score'], out=lines.append)
        s = json.loads(lines[0])
        self.assertEqual((s['s5_on_ai']['wrong'], s['stored_ai']['wrong']), (0, 2))
        self.assertEqual(s['s5_all']['malformed'], 0)
        self.assertEqual(s['gate'], 'PASS')

    def test_a_malformed_answer_twice_is_a_refusal_never_a_grade(self):
        factory = self._factory({**_GOOD, 'results': [{'subject': 'SEJARAH', 'grade': 'Bplus}', 'band': ''}]})
        with override_settings(GEMINI_API_KEY='test-key'):
            gate.main(['--eval-dir', self.dir, '--live', '--keys', self.keys[0]], client_factory=factory,
                      out=lambda *_: None)
        self.assertEqual(self.asked, ['gemini-3.8-flash', 'gemini-3.8-flash'])   # one retry only
        lines = []
        gate.main(['--eval-dir', self.dir, '--score'], out=lines.append)
        s = json.loads(lines[0])
        self.assertEqual((s['s5_all']['refused'], s['s5_all']['malformed']), (1, 0))

    def test_without_a_key_nothing_is_read(self):
        lines = []
        with override_settings(GEMINI_API_KEY=''):
            self.assertEqual(gate.main(['--eval-dir', self.dir, '--live'], out=lines.append), 2)


class TheScore(SimpleTestCase):
    def test_a_grade_outside_the_set_counts_as_malformed(self):
        s = gate.score_read({'results': [{'subject': 'SEJARAH', 'grade': 'Aplus', 'band': ''}]}, {'hist': 'A+'})
        self.assertEqual(s['malformed'], 1)

    def test_no_read_is_a_refusal(self):
        self.assertEqual(gate.score_read(None, {'bm': 'A'})['refused'], 1)
