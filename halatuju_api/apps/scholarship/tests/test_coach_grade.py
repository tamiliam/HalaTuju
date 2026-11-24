"""LL5 phase A - the monthly score and the coach grade (`coach_grade`, pure). Synthetic records only."""
import datetime
import json

from django.test import SimpleTestCase

from apps.scholarship import ai_score, coach_grade
from apps.scholarship.audit import FACTS
from apps.scholarship.fact_bands import CERTAIN, PROBABLE, RULE_NOT_MET, UNSURE, UNVERIFIABLE

UTC = datetime.timezone.utc
EARLY = datetime.datetime(2026, 3, 2, 3, 0, tzinfo=UTC)
LATER = datetime.datetime(2026, 4, 6, 3, 0, tzinfo=UTC)
LATEST = datetime.datetime(2026, 5, 4, 3, 0, tzinfo=UTC)
BY = 'SENTINEL-DECIDER-Q7X3'
ROW_ID = 'SENTINEL-ROW-Z9K1'
INT_ID = 918273645


def band_fact(name, band):
    """A snapshot fact dict that `fact_band` reads as ``band``."""
    if band == CERTAIN:
        return {'fact': name, 'status': 'verified', 'evidence': [{'code': 'ic_match'}], 'unresolved': []}
    if band == PROBABLE:
        return {'fact': name, 'status': 'review', 'evidence': [{'code': 'ic_match'}], 'unresolved': []}
    if band == UNSURE:
        return {'fact': name, 'status': 'recommend', 'evidence': [], 'unresolved': []}
    if band == UNVERIFIABLE:
        return {'fact': name, 'status': 'gap', 'evidence': [], 'unresolved': []}
    return {'fact': name, 'status': 'review', 'evidence': [],
            'unresolved': [{'code': 'pathway_offer_private', 'params': {}}]}


def one(band, says, version='v1', when=EARLY, reason=None, row_id=ROW_ID):
    """A decided record with ONE marked fact (identity)."""
    verdict = {'identity': says}
    if reason:
        verdict['fail_reasons'] = {'identity': reason}
    return ([band_fact('identity', band)], verdict, version, when, BY, row_id)


def many(spec, version='v1', when=EARLY):
    """``spec``: ``[(band, says, count[, reason])]`` -> one single-fact record per count."""
    out = []
    for item in spec:
        band, says, count = item[:3]
        reason = item[3] if len(item) > 3 else None
        out += [one(band, says, version, when, reason) for _ in range(count)]
    return out


def first_pair(prev, new):
    """The coach grade of version 'old' (decided EARLY) then 'next' (decided LATER)."""
    report = coach_grade.coach_report(many(prev, 'old', EARLY) + many(new, 'next', LATER))
    return report['coach'][0]


class TestTheConstants(SimpleTestCase):

    def test_the_floors(self):
        self.assertEqual(coach_grade.CELL_MIN_FACTS, 5)
        self.assertEqual(coach_grade.COACH_MIN_FACTS, 40)
        self.assertGreaterEqual(coach_grade.COACH_MIN_FACTS, coach_grade.CELL_MIN_FACTS)

    def test_the_closed_sets(self):
        self.assertEqual(coach_grade.GRADES, ('pass', 'fail', 'not_enough'))
        self.assertEqual(len(set(coach_grade.REASON_CODES)), 6)
        self.assertEqual(coach_grade.DOCUMENTS_ONLY, ('interview_differs',))


class TestTheMonthlyScore(SimpleTestCase):

    def test_the_month_is_malaysian(self):
        # 16:30 UTC on 31 October is 00:30 on 1 November in Malaysia; 15:59 UTC is still 31 October.
        records = (many([(CERTAIN, 'pass', 5)], when=datetime.datetime(2026, 10, 31, 16, 30, tzinfo=UTC))
                   + many([(CERTAIN, 'pass', 6)], when=datetime.datetime(2026, 10, 31, 15, 59, tzinfo=UTC)))
        months = coach_grade.coach_report(records)['months']
        self.assertEqual([(m['month'], m['facts']) for m in months], [('2026-10', 6), ('2026-11', 5)])

    def test_the_score_is_ai_score_s_own(self):
        records = many([(CERTAIN, 'pass', 3), (PROBABLE, 'fail', 1), (UNVERIFIABLE, 'pass', 2),
                        (RULE_NOT_MET, 'fail', 1), (UNSURE, 'fail', 1)])
        records.append(([], {'identity': 'pass'}, 'v1', EARLY, BY, ROW_ID))   # decided, no band
        plain = ai_score.score_marks(records)
        cell = coach_grade.coach_report(records)['months'][0]
        self.assertEqual((cell['facts'], cell['points'], cell['best'], cell['score_pct'], cell['not_scored']),
                         (plain['facts'], plain['points'], plain['best'], plain['score_pct'],
                          plain['not_scored']))
        self.assertEqual((cell['facts'], cell['points'], cell['best'], cell['not_scored']), (8, 3, 16, 1))
        self.assertEqual(cell['outcomes'], {o: plain[o] for o in ai_score.OUTCOMES})
        # it moves with the input: one Certain pass turned into a Certain fail costs 12 points
        records[0] = one(CERTAIN, 'fail')
        self.assertEqual(coach_grade.coach_report(records)['months'][0]['points'], -9)

    def test_the_floor_is_five_marked_facts(self):
        four = coach_grade.coach_report(many([(CERTAIN, 'pass', 4)]))['months'][0]
        self.assertEqual(four, {'version': 'v1', 'unknown_version': False, 'month': '2026-03',
                                'too_few': True})
        five = coach_grade.coach_report(many([(CERTAIN, 'pass', 5)]))['months'][0]
        self.assertFalse(five['too_few'])
        self.assertEqual((five['facts'], five['points'], five['best'], five['score_pct']), (5, 10, 10, 100))

    def test_not_scored_facts_do_not_lift_a_cell_over_the_floor(self):
        records = many([(CERTAIN, 'pass', 4)]) + [([], {'identity': 'pass'}, 'v1', EARLY, BY, ROW_ID)]
        self.assertTrue(coach_grade.coach_report(records)['months'][0]['too_few'])

    def test_undecided_records_are_dropped_here(self):
        undecided = [one(CERTAIN, 'pass', when=None) for _ in range(4)]
        report = coach_grade.coach_report(many([(CERTAIN, 'pass', 4)]) + undecided)
        self.assertEqual(report['decided_records'], 4)
        self.assertTrue(report['months'][0]['too_few'])
        # the same four, decided, lift the cell over the floor
        report = coach_grade.coach_report(many([(CERTAIN, 'pass', 8)]))
        self.assertEqual((report['decided_records'], report['months'][0]['facts']), (8, 8))

    def test_versions_run_by_first_decided_instant_then_month(self):
        records = (many([(CERTAIN, 'pass', 5)], 'alpha', LATER) + many([(CERTAIN, 'pass', 5)], 'zeta', EARLY)
                   + many([(CERTAIN, 'pass', 5)], 'zeta', LATEST))
        months = coach_grade.coach_report(records)['months']
        self.assertEqual([(m['version'], m['month']) for m in months],
                         [('zeta', '2026-03'), ('zeta', '2026-05'), ('alpha', '2026-04')])

    def test_unknown_version_is_its_own_bucket_last_and_never_graded(self):
        records = (many([(CERTAIN, 'pass', 50)], '', EARLY) + many([(PROBABLE, 'pass', 3)], None, EARLY)
                   + many([(CERTAIN, 'pass', 50)], 'v2', LATER))
        report = coach_grade.coach_report(records)
        self.assertEqual([(m['version'], m['unknown_version'], m['month'], m['facts']) for m in report['months']],
                         [('v2', False, '2026-04', 50), (coach_grade.UNKNOWN_VERSION, True, '2026-03', 53)])
        self.assertEqual(report['coach'], [])

    def test_the_output_does_not_depend_on_the_input_order(self):
        records = (many([(CERTAIN, 'pass', 30), (UNSURE, 'pass', 12)], 'a', EARLY)
                   + many([(PROBABLE, 'fail', 7), (CERTAIN, 'pass', 40)], 'b', LATER)
                   + many([(RULE_NOT_MET, 'fail', 6)], '', LATEST))
        forward = json.dumps(coach_grade.coach_report(records), sort_keys=True)
        self.assertEqual(json.dumps(coach_grade.coach_report(list(reversed(records))), sort_keys=True), forward)
        mixed = records[1::2] + records[::2]
        self.assertEqual(json.dumps(coach_grade.coach_report(mixed), sort_keys=True), forward)

    def test_no_decider_and_no_row_id_in_the_output(self):
        records = (many([(CERTAIN, 'pass', 45)], 'a', EARLY) + many([(CERTAIN, 'pass', 45)], 'b', LATER)
                   + [one(CERTAIN, 'pass', 'b', LATER, row_id=INT_ID) for _ in range(5)])
        for leave_out in ((), coach_grade.DOCUMENTS_ONLY):
            dump = json.dumps(coach_grade.coach_report(records, leave_out_reasons=leave_out))
            self.assertNotIn(BY, dump)
            self.assertNotIn(ROW_ID, dump)
            self.assertNotIn(str(INT_ID), dump)
        self.assertIn('"b"', dump)   # the scan reads the real dump


class TestTheCoachGrade(SimpleTestCase):

    def test_score_up_with_both_guards_held_passes(self):
        pair = first_pair([(PROBABLE, 'pass', 40)], [(CERTAIN, 'pass', 40)])
        self.assertEqual((pair['grade'], pair['reasons']), ('pass', ['score_up']))
        self.assertEqual(pair['previous'], {'version': 'old', 'too_few': False, 'facts': 40, 'score_pct': 50,
                                            'coverage': {'count': 40, 'of': 40},
                                            'generous_wrong': {'count': 0, 'of': 40}})
        self.assertEqual((pair['new']['version'], pair['new']['score_pct']), ('next', 100))

    def test_a_tie_is_not_up(self):
        pair = first_pair([(CERTAIN, 'pass', 40)], [(CERTAIN, 'pass', 40)])
        self.assertEqual((pair['grade'], pair['reasons']), ('fail', ['score_not_up']))

    def test_the_score_is_compared_as_an_exact_fraction(self):
        # old 39/80 = 48.75% and next 41/84 = 48.81%: both show 49%, and next IS higher
        old = [(CERTAIN, 'pass', 1), (PROBABLE, 'pass', 38), (UNVERIFIABLE, 'pass', 1)]
        new = [(CERTAIN, 'pass', 1), (PROBABLE, 'pass', 40), (UNVERIFIABLE, 'pass', 1)]
        up = first_pair(old, new)
        self.assertEqual((up['previous']['score_pct'], up['new']['score_pct']), (49, 49))
        self.assertEqual((up['grade'], up['reasons']), ('pass', ['score_up']))
        down = first_pair(new, old)
        self.assertEqual((down['grade'], down['reasons']), ('fail', ['score_not_up']))

    def test_the_coach_floor_is_forty_on_either_side(self):
        for prev, new, reasons in ((39, 40, ['previous_too_few']), (40, 39, ['new_too_few']),
                                   (39, 39, ['previous_too_few', 'new_too_few'])):
            pair = first_pair([(PROBABLE, 'pass', prev)], [(CERTAIN, 'pass', new)])
            self.assertEqual((pair['grade'], pair['reasons']), ('not_enough', reasons))
        self.assertEqual(first_pair([(PROBABLE, 'pass', 40)], [(CERTAIN, 'pass', 40)])['grade'], 'pass')

    def test_a_side_under_five_shows_no_figures(self):
        pair = first_pair([(PROBABLE, 'pass', 4)], [(CERTAIN, 'pass', 40)])
        self.assertEqual(pair['previous'], {'version': 'old', 'too_few': True})
        self.assertEqual(pair['grade'], 'not_enough')

    def test_guard_one_coverage_drop_fails_even_when_the_score_rose(self):
        old = [(UNVERIFIABLE, 'pass', 40)]                       # -50%, coverage 40/40
        new = [(CERTAIN, 'pass', 39), (UNSURE, 'pass', 1)]       # 98%, coverage 39/40
        pair = first_pair(old, new)
        self.assertGreater(pair['new']['score_pct'], pair['previous']['score_pct'])
        self.assertEqual(pair['new']['coverage'], {'count': 39, 'of': 40})
        self.assertEqual((pair['grade'], pair['reasons']), ('fail', ['coverage_dropped']))
        # the Unsure turned Certain: coverage holds and the grade passes
        self.assertEqual(first_pair(old, [(CERTAIN, 'pass', 40)])['grade'], 'pass')

    def test_guard_one_an_equal_share_is_not_a_drop(self):
        old = [(PROBABLE, 'pass', 39), (UNSURE, 'pass', 1)]      # 39/40 covered
        new = [(CERTAIN, 'pass', 78), (UNSURE, 'pass', 2)]       # 78/80, the same share
        self.assertEqual(first_pair(old, new)['grade'], 'pass')
        self.assertEqual(first_pair(old, [(CERTAIN, 'pass', 77), (UNSURE, 'pass', 3)])['reasons'],
                         ['coverage_dropped'])

    def test_guard_two_generous_wrong_rise_fails_even_when_the_score_rose(self):
        old = [(PROBABLE, 'pass', 40)]                           # 50%, generous-wrong 0/40
        for wrong_band in (CERTAIN, PROBABLE):
            pair = first_pair(old, [(CERTAIN, 'pass', 39), (wrong_band, 'fail', 1)])
            self.assertGreater(pair['new']['score_pct'], pair['previous']['score_pct'])
            self.assertEqual(pair['new']['generous_wrong'], {'count': 1, 'of': 40})
            self.assertEqual((pair['grade'], pair['reasons']), ('fail', ['generous_wrong_rose']))

    def test_guard_two_counts_only_a_generous_band_the_reviewer_failed(self):
        old = [(PROBABLE, 'pass', 40)]
        for band, says in ((RULE_NOT_MET, 'pass'), (UNVERIFIABLE, 'pass'), (RULE_NOT_MET, 'fail')):
            pair = first_pair(old, [(CERTAIN, 'pass', 39), (band, says, 1)])
            self.assertEqual(pair['new']['generous_wrong'], {'count': 0, 'of': 40}, (band, says))
            self.assertEqual(pair['grade'], 'pass', (band, says))

    def test_both_guards_are_named(self):
        old = [(PROBABLE, 'pass', 40)]
        new = [(CERTAIN, 'pass', 38), (UNSURE, 'pass', 1), (CERTAIN, 'fail', 1)]
        pair = first_pair(old, new)
        self.assertEqual((pair['grade'], pair['reasons']), ('fail', ['coverage_dropped', 'generous_wrong_rose']))

    def test_each_consecutive_pair_is_graded_on_its_own_cases(self):
        records = (many([(PROBABLE, 'pass', 40)], 'v1', EARLY) + many([(CERTAIN, 'pass', 40)], 'v2', LATER)
                   + many([(PROBABLE, 'pass', 40)], 'v3', LATEST))
        coach = coach_grade.coach_report(records)['coach']
        self.assertEqual([(p['previous']['version'], p['new']['version'], p['grade']) for p in coach],
                         [('v1', 'v2', 'pass'), ('v2', 'v3', 'fail')])


class TestDocumentsOnly(SimpleTestCase):

    def records(self):
        return many([(CERTAIN, 'pass', 5), (CERTAIN, 'fail', 1, 'interview_differs'),
                     (CERTAIN, 'fail', 1, 'proof_missing')])

    def test_the_default_is_the_plain_score(self):
        records = self.records() + many([(PROBABLE, 'pass', 40)], 'v2', LATER)
        self.assertEqual(coach_grade.coach_report(records), coach_grade.coach_report(records, ()))
        cell = coach_grade.coach_report(records)['months'][0]
        self.assertEqual((cell['facts'], cell['points'], cell['best'], cell['left_out']), (7, -10, 14, 0))

    def test_an_interview_fail_is_left_out_of_points_and_best(self):
        cell = coach_grade.coach_report(self.records(), leave_out_reasons=coach_grade.DOCUMENTS_ONLY)['months'][0]
        self.assertEqual((cell['facts'], cell['points'], cell['best'], cell['left_out']), (6, 0, 12, 1))
        self.assertEqual(cell['outcomes']['wrong_sure'], 1)   # the proof_missing Fail still costs

    def test_it_applies_to_the_coach_grade_too(self):
        old = [(PROBABLE, 'pass', 40)]
        new = [(CERTAIN, 'pass', 40), (CERTAIN, 'fail', 1, 'interview_differs')]
        records = many(old, 'old', EARLY) + many(new, 'next', LATER)
        plain = coach_grade.coach_report(records)['coach'][0]
        self.assertEqual((plain['grade'], plain['reasons']), ('fail', ['generous_wrong_rose']))
        docs = coach_grade.coach_report(records, leave_out_reasons=coach_grade.DOCUMENTS_ONLY)
        self.assertEqual(docs['left_out_reasons'], ['interview_differs'])
        pair = docs['coach'][0]
        self.assertEqual((pair['grade'], pair['new']['facts'], pair['new']['generous_wrong']),
                         ('pass', 40, {'count': 0, 'of': 40}))

    def test_an_unknown_code_is_refused(self):
        with self.assertRaises(ValueError):
            coach_grade.coach_report(self.records(), leave_out_reasons=('not_a_code',))
        with self.assertRaises(ValueError):   # a bare string is not a set of codes
            coach_grade.coach_report(self.records(), leave_out_reasons='interview_differs')

    def test_a_record_with_all_four_facts_loses_only_the_interview_fail(self):
        verdict = {f: 'pass' for f in FACTS}
        verdict.update(identity='fail', income='fail',
                       fail_reasons={'identity': 'interview_differs', 'income': 'documents_differ'})
        snapshot = [band_fact(f, CERTAIN) for f in FACTS]
        records = [(snapshot, verdict, 'v1', EARLY, BY, ROW_ID)] * 2
        plain = coach_grade.coach_report(records)['months'][0]
        docs = coach_grade.coach_report(records, leave_out_reasons=coach_grade.DOCUMENTS_ONLY)['months'][0]
        self.assertEqual((plain['facts'], plain['points'], plain['best']), (8, -32, 16))
        self.assertEqual((docs['facts'], docs['points'], docs['best'], docs['left_out']), (6, -12, 12, 2))
        self.assertEqual(verdict['identity'], 'fail')   # the caller's record is not changed
