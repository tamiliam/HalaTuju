"""The OCR-first dry-run harness (`eval/ocr_first_dryrun.py`) on three INVENTED letters in a temp folder
(S0, 2026-11-18). No real person, no corpus (`test_no_gitignored_corpus.py`), no database: the course
matcher is a fake."""
import contextlib
import io
import json
import os
import tempfile

from django.test import SimpleTestCase

from apps.scholarship.eval import ocr_first_dryrun as dr
from apps.scholarship.tests.test_offer_exact import COLLEGE, NAME, NRIC, matric
from apps.scholarship.tests.test_offer_replay import UNIVERSITY_TWIN, _answer, _Corpus

K1, K2, K3 = 'offer_letter__a1__d1', 'offer_letter__a2__d2', 'offer_letter__a3__d3'


def _stored():
    return {'candidate_name': NAME, 'candidate_nric': NRIC, 'institution_as_printed': COLLEGE}


class DryRunHarnessTests(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        c = _Corpus(tmp.name)
        c.letter(K1, _stored(), route='vision', text=matric(), answer=_answer(institution_as_printed=COLLEGE))
        c.letter(K2, _stored(), route='vision', text=matric(),
                 answer=_answer(institution_as_printed='KOLEJ MATRIKULASI LAIN'))      # rules read it wrong
        c.letter(K3, _stored(), seen='ua_offer', route='vision', text=UNIVERSITY_TWIN,
                 answer=_answer(institution_as_printed='Universiti Qorvane', programme='Ijazah'))
        self.c = c
        self.split = os.path.join(tmp.name, 'split.json')
        with open(self.split, 'w', encoding='utf-8') as f:
            json.dump({'heldout': [K1, K2, K3]}, f)

    def summary(self, split='heldout'):
        return dr.dryrun_summary(self.c.dir, self.c.snap, split, self.split, matcher=lambda *a, **k: None)

    def test_lane_table_counts_and_buckets(self):
        lanes = {row['lane']: row for row in self.summary()['offers']}
        matric_lane = lanes['matriculation']
        self.assertEqual((matric_lane['docs'], matric_lane['locked']), (2, 2))
        self.assertEqual(matric_lane['status'], 'fail')                      # 2 documents: far below 20
        self.assertIn("only 2 held-out documents locked", matric_lane["why"])
        self.assertEqual(matric_lane['fields']['institution']['exact'], 1)
        self.assertEqual(matric_lane['fields']['institution']['wrong'], 1)
        self.assertEqual(matric_lane['wrong'], {'institution': 1})
        self.assertIn('1 wrong institution', matric_lane['why'])

    def test_issuer_without_parser_is_no_rules_yet(self):
        lane = next(r for r in self.summary()['offers'] if r['lane'] != 'matriculation')
        self.assertEqual(lane['status'], 'no rules yet')
        self.assertEqual(lane['locked'], 0)

    def test_dev_only_lane_is_informational_never_pass(self):
        with open(self.split, 'w', encoding='utf-8') as f:
            json.dump({'heldout': []}, f)
        lane = next(r for r in self.summary('dev')['offers'] if r['lane'] == 'matriculation')
        self.assertEqual(lane['status'], 'informational (not held-out)')

    def test_dev_split_is_empty_when_all_are_heldout(self):
        self.assertEqual(self.summary('dev')['offers'], [])

    def test_report_prints_counts_only(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            dr.print_report(self.summary())
        text = out.getvalue()
        self.assertIn('LANE TABLE', text)
        self.assertIn('no rules yet', text)
        for secret in (NAME, NRIC, COLLEGE):
            self.assertNotIn(secret, text)


class GateLaneTests(SimpleTestCase):
    """`gate_lane` on hand-made lane totals: course not measured, and the split."""

    def lane(self, **over):
        lane = dr._new_lane('universiti qorvane', True)
        lane.update({'docs': 30, 'locked': 30, 'core_right': 180, 'core_total': 180})
        lane['course']['unique'] = 30
        lane.update(over)
        return lane

    def test_clean_lane_passes_on_heldout(self):
        self.assertEqual(dr.gate_lane(self.lane())[0], 'pass')

    def test_course_not_run_fails_a_university_lane(self):
        lane = self.lane()
        lane['course']['unique'], lane['course']['not_run'] = 0, 30
        status, why = dr.gate_lane(lane)
        self.assertEqual(status, 'fail')
        self.assertIn('course match not run', why)

    def test_not_heldout_never_passes(self):
        status, why = dr.gate_lane(self.lane(), heldout=False)
        self.assertEqual(status, 'informational (not held-out)')
        self.assertEqual(why, 'would pass Gate 1')

    def test_coverage_floor_counts_locked_not_docs(self):
        status, why = dr.gate_lane(self.lane(docs=40, locked=19))
        self.assertEqual(status, 'fail')
        self.assertIn('only 19', why)
