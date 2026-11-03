"""`eval/offer_parse_check.py` (offer exact-read S5) on a synthetic corpus folder: EXACT / INCOMPLETE /
WRONG / CONTROL-LOCKED / FALLBACK per letter, the pipeline score over a base AI read, the stored Exact
reads that re-lock, the exit code, and no value ever printed. Synthetic twins only
(`test_no_gitignored_corpus.py`)."""
import contextlib
import io
import json
import os
import tempfile

from django.test import SimpleTestCase

from apps.scholarship.eval import offer_parse_check as pc
from apps.scholarship.tests.test_offer_exact import COLLEGE, NAME, NRIC, matric
from apps.scholarship.tests.test_offer_replay import UNIVERSITY_TWIN, _Corpus, _answer


def _ans(**over):
    base = dict(candidate_name=NAME, candidate_nric=NRIC, institution_as_printed=COLLEGE,
                intake='SESI 2031/2032', reporting_date='17 OGOS 2031', family='matriculation')
    base.update(over)
    return _answer(**base)


class TestOfferParseCheck(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.c = _Corpus(self._tmp.name)
        self.split = os.path.join(self._tmp.name, 'split.json')
        with open(self.split, 'w') as f:
            json.dump({'heldout': ['offer_letter__a5__d15']}, f)
        L = self.c.letter
        L('offer_letter__a1__d11', {}, route='vision', text=matric(), answer=_ans())               # EXACT
        L('offer_letter__a2__d12', {}, route='vision', text=matric(), answer=_ans(stream='PERAKAUNAN'))  # WRONG
        L('offer_letter__a3__d13', {}, route='vision', text=matric(), answer=_ans(is_offer_letter='portal_page'))
        L('offer_letter__a4__d14', {}, seen='ua_offer', route='vision', text=UNIVERSITY_TWIN,
          answer=_ans(family='other_university'))                                                   # FALLBACK
        L('offer_letter__a5__d15', {}, route='vision', text=matric(reporting='x'), answer=_ans())   # INCOMPLETE
        self.c._json('offer_letter__a1__d11.fresh_s4d.json', {'fields': {}})                       # pipeline base

    def tearDown(self):
        self._tmp.cleanup()

    def _rows(self):
        return pc.check_corpus(self.c.dir, split_file=self.split)

    def test_each_outcome(self):
        got = {r['key'].split('__')[1]: (r['outcome'], r['fields_bad']) for r in self._rows()}
        self.assertEqual(got['a1'], ('EXACT', []))
        self.assertEqual(got['a2'], ('WRONG', ['programme']))
        self.assertEqual(got['a3'], ('CONTROL-LOCKED', []))
        self.assertEqual(got['a4'], ('FALLBACK', []))
        self.assertEqual(got['a5'], ('INCOMPLETE', ['reporting_date']))

    def test_the_summary_by_split_with_the_pipeline_and_the_stored_exact_reads(self):
        s = pc.summarise(self._rows(), 'dev')
        self.assertEqual(s['outcome']['WRONG'], 1)
        self.assertEqual(s['bad'], {'offer_letter__a2__d12': 'WRONG programme',
                                    'offer_letter__a3__d13': 'CONTROL-LOCKED'})
        self.assertEqual(s['pipeline'], {'letters': 1, 'fully_exact': 1})
        self.assertEqual(pc.summarise(self._rows(), 'heldout')['outcome']['INCOMPLETE'], 1)
        self.assertEqual(s['stored_exact']['total'], 0)

    def test_exit_code_and_no_value_printed(self):
        for split, code in (('dev', 1), ('heldout', 0)):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = pc.main(['--eval-dir', self.c.dir, '--split', split, '--split-file', self.split])
            self.assertEqual(rc, code)
            text = out.getvalue().upper()
            for token in ('ZORBEX', 'QUENTARO', 'ZANTHARION', '010203', 'OGOS'):
                self.assertNotIn(token, text)

    def test_no_corpus(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pc.main(['--eval-dir', os.path.join(self._tmp.name, 'none')]), 2)

    def test_classify_unanswered(self):
        self.assertEqual(pc.classify(None, 'stpm', {'x': 1})[0], 'UNANSWERED')
        self.assertEqual(pc.classify(None, 'stpm', None)[0], 'FALLBACK')
