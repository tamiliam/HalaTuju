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
        self.assertEqual(coach_grade.GRADES, ('pass', 'fail', 'no_change'))
        self.assertEqual(coach_grade.REASON_CODES, ('coverage_dropped', 'generous_wrong_rose', 'score_up',
                                                    'score_same', 'score_down'))
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
        self.assertEqual(four, {'version': 'v1', 'unknown_version': False, 'month': '2026-03', 'too_few': True})
        five = coach_grade.coach_report(many([(CERTAIN, 'pass', 5)]))['months'][0]
        self.assertEqual(five, {'version': 'v1', 'unknown_version': False, 'month': '2026-03', 'too_few': False,
                                'facts': 5, 'points': 10, 'best': 10, 'score_pct': 100, 'not_scored': 0,
                                'outcomes': {'right_sure': 5, 'right_leaning': 0, 'unsure': 0,
                                             'wrong_leaning': 0, 'wrong_sure': 0}})

    def test_a_month_with_no_marked_fact_has_no_cell(self):
        records = many([(CERTAIN, 'pass', 5)], when=EARLY) + [([], {'identity': 'pass'}, 'v1', LATER, BY, ROW_ID)]
        report = coach_grade.coach_report(records)
        self.assertEqual([(m['month'], m['too_few']) for m in report['months']], [('2026-03', False)])
        self.assertEqual(report['decided_records'], 6)

    def test_a_short_first_month_is_its_own_too_few_cell(self):
        records = many([(CERTAIN, 'pass', 2)], when=EARLY) + many([(PROBABLE, 'pass', 6)], when=LATER)
        months = coach_grade.coach_report(records)['months']
        self.assertEqual([(m['month'], m['too_few'], m.get('facts'), m.get('points')) for m in months],
                         [('2026-03', True, None, None), ('2026-04', False, 6, 6)])

    def test_a_version_across_a_year_change(self):
        records = (many([(CERTAIN, 'pass', 6)], when=datetime.datetime(2027, 1, 10, 3, 0, tzinfo=UTC))
                   + many([(CERTAIN, 'pass', 5)], when=datetime.datetime(2026, 12, 10, 3, 0, tzinfo=UTC)))
        months = coach_grade.coach_report(records)['months']
        self.assertEqual([(m['month'], m['facts']) for m in months], [('2026-12', 5), ('2027-01', 6)])

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

    def test_an_exact_tie_is_no_change(self):
        pair = first_pair([(CERTAIN, 'pass', 40)], [(CERTAIN, 'pass', 40)])
        self.assertEqual((pair['grade'], pair['reasons']), ('no_change', ['score_same']))
        # 40/80 against 80/160: the same fraction at a different size
        pair = first_pair([(PROBABLE, 'pass', 40)], [(PROBABLE, 'pass', 80)])
        self.assertEqual((pair['grade'], pair['reasons']), ('no_change', ['score_same']))

    def test_two_negative_scores_less_negative_is_up(self):
        old = [(CERTAIN, 'fail', 40)]                            # -400 / 80 = -500%
        new = [(CERTAIN, 'fail', 20), (PROBABLE, 'fail', 20)]    # -260 / 80 = -325%
        up = first_pair(old, new)
        self.assertEqual((up['previous']['score_pct'], up['new']['score_pct']), (-500, -325))
        self.assertEqual((up['grade'], up['reasons']), ('pass', ['score_up']))
        self.assertEqual((first_pair(new, old)['grade'], first_pair(new, old)['reasons']),
                         ('fail', ['score_down']))

    def test_the_score_is_compared_as_an_exact_fraction(self):
        # old 39/80 = 48.75% and next 41/84 = 48.81%: both show 49%, and next IS higher
        old = [(CERTAIN, 'pass', 1), (PROBABLE, 'pass', 38), (UNVERIFIABLE, 'pass', 1)]
        new = [(CERTAIN, 'pass', 1), (PROBABLE, 'pass', 40), (UNVERIFIABLE, 'pass', 1)]
        up = first_pair(old, new)
        self.assertEqual((up['previous']['score_pct'], up['new']['score_pct']), (49, 49))
        self.assertEqual((up['grade'], up['reasons']), ('pass', ['score_up']))
        down = first_pair(new, old)
        self.assertEqual((down['grade'], down['reasons']), ('fail', ['score_down']))

    def test_the_coach_floor_is_forty_on_either_side(self):
        for prev, new, waiting in ((39, 40, ['old']), (40, 39, ['next']), (39, 39, ['old', 'next'])):
            report = coach_grade.coach_report(many([(PROBABLE, 'pass', prev)], 'old', EARLY)
                                              + many([(CERTAIN, 'pass', new)], 'next', LATER))
            self.assertEqual(report['coach'], [])
            self.assertEqual([w['version'] for w in report['waiting']], waiting)
        pair = first_pair([(PROBABLE, 'pass', 40)], [(CERTAIN, 'pass', 40)])
        self.assertEqual((pair['grade'], pair['skipped_versions']), ('pass', 0))

    def test_a_waiting_side_under_five_shows_no_figures(self):
        report = coach_grade.coach_report(many([(PROBABLE, 'pass', 4)], 'old', EARLY)
                                          + many([(CERTAIN, 'pass', 40)], 'next', LATER))
        self.assertEqual(report['coach'], [])
        self.assertEqual(report['waiting'], [{'version': 'old', 'too_few': True}])

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

    def test_guard_two_an_equal_non_zero_share_is_not_a_rise(self):
        old = [(CERTAIN, 'pass', 39), (CERTAIN, 'fail', 1)]             # 1 of 40, 68/80
        same = first_pair(old, [(CERTAIN, 'pass', 78), (CERTAIN, 'fail', 2)])   # 2 of 80, 136/160
        self.assertEqual(same['new']['generous_wrong'], {'count': 2, 'of': 80})
        self.assertEqual((same['grade'], same['reasons']), ('no_change', ['score_same']))
        lower = first_pair(old, [(CERTAIN, 'pass', 79), (CERTAIN, 'fail', 1)])  # 1 of 80, 148/160
        self.assertEqual((lower['grade'], lower['reasons']), ('pass', ['score_up']))
        rose = first_pair(old, [(CERTAIN, 'pass', 77), (CERTAIN, 'fail', 3)])   # 3 of 80
        self.assertEqual((rose['grade'], rose['reasons']), ('fail', ['generous_wrong_rose']))

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

    def test_records_with_four_facts_each(self):
        old = [([band_fact(f, PROBABLE) for f in FACTS], {f: 'pass' for f in FACTS}, 'old', EARLY, BY, ROW_ID)
               for _ in range(10)]
        new = [([band_fact(f, CERTAIN) for f in FACTS], {f: 'pass' for f in FACTS}, 'next', LATER, BY, ROW_ID)
               for _ in range(10)]
        pair = coach_grade.coach_report(old + new)['coach'][0]
        self.assertEqual((pair['previous']['facts'], pair['new']['facts']), (40, 40))
        self.assertEqual((pair['previous']['score_pct'], pair['new']['score_pct']), (50, 100))
        self.assertEqual((pair['grade'], pair['reasons']), ('pass', ['score_up']))
        # one record of the new version shows Identity Unsure: coverage 39 of 40 drops
        new[0] = ([band_fact('identity', UNSURE)] + [band_fact(f, CERTAIN) for f in FACTS[1:]],
                  {f: 'pass' for f in FACTS}, 'next', LATER, BY, ROW_ID)
        pair = coach_grade.coach_report(old + new)['coach'][0]
        self.assertEqual(pair['new']['coverage'], {'count': 39, 'of': 40})
        self.assertEqual((pair['grade'], pair['reasons']), ('fail', ['coverage_dropped']))


def at(month, day=6):
    return datetime.datetime(2026, month, day, 3, 0, tzinfo=UTC)


class TestVersions(SimpleTestCase):

    def test_pre_versioning_is_unknown_and_never_graded(self):
        records = (many([(PROBABLE, 'pass', 60)], 'pre-versioning', EARLY)
                   + many([(CERTAIN, 'pass', 60)], '2026-09-19.1', LATER))
        report = coach_grade.coach_report(records)
        self.assertEqual((report['coach'], report['waiting']), ([], []))
        self.assertEqual([(m['version'], m['unknown_version'], m['month'], m['facts']) for m in report['months']],
                         [('2026-09-19.1', False, '2026-04', 60), ('pre-versioning', True, '2026-03', 60)])

    def test_a_label_is_stripped_and_a_blank_one_is_unknown(self):
        records = (many([(CERTAIN, 'pass', 45)], 'v1', EARLY) + many([(CERTAIN, 'pass', 45)], '  ', LATER)
                   + many([(PROBABLE, 'pass', 45)], ' v1 ', LATEST) + many([(CERTAIN, 'pass', 45)], 'v2', LATEST))
        report = coach_grade.coach_report(records)
        self.assertEqual([(m['version'], m['unknown_version'], m['month'], m['facts']) for m in report['months']],
                         [('v1', False, '2026-03', 45), ('v1', False, '2026-05', 45), ('v2', False, '2026-05', 45),
                          ('(unknown version)', True, '2026-04', 45)])
        self.assertEqual([(p['previous']['version'], p['new']['version'], p['previous']['facts'])
                          for p in report['coach']], [('v1', 'v2', 90)])

    def test_an_old_version_decided_again_keeps_its_place(self):
        records = (many([(PROBABLE, 'pass', 50)], 'v1', EARLY) + many([(CERTAIN, 'pass', 50)], 'v2', LATER)
                   + many([(PROBABLE, 'pass', 5)], 'v1', LATEST))
        report = coach_grade.coach_report(records)
        self.assertEqual([(m['version'], m['month']) for m in report['months']],
                         [('v1', '2026-03'), ('v1', '2026-05'), ('v2', '2026-04')])
        pair = report['coach'][0]
        self.assertEqual((pair['previous']['version'], pair['previous']['facts'], pair['new']['version']),
                         ('v1', 55, 'v2'))

    def test_a_same_instant_tie_runs_in_natural_order(self):
        records = (many([(CERTAIN, 'pass', 60)], '2026-11-15.10', EARLY)
                   + many([(PROBABLE, 'pass', 60)], '2026-11-15.9', EARLY))
        pair = coach_grade.coach_report(records)['coach'][0]
        self.assertEqual((pair['previous']['version'], pair['new']['version'], pair['grade']),
                         ('2026-11-15.9', '2026-11-15.10', 'pass'))

    def test_a_label_that_is_not_text_is_unknown(self):
        records = many([(CERTAIN, 'pass', 45)], 7, EARLY) + many([(CERTAIN, 'pass', 45)], 'v2', LATER)
        report = coach_grade.coach_report(records)
        self.assertEqual([(m['version'], m['unknown_version'], m['facts']) for m in report['months']],
                         [('v2', False, 45), ('(unknown version)', True, 45)])
        self.assertEqual((report['coach'], report['waiting']), ([], []))

    def test_pre_versioning_is_matched_exactly_after_the_strip(self):
        records = many([(CERTAIN, 'pass', 5)], ' pre-versioning ', EARLY) + many([(CERTAIN, 'pass', 5)],
                                                                                 'PRE-VERSIONING', LATER)
        months = coach_grade.coach_report(records)['months']
        self.assertEqual([(m['version'], m['unknown_version']) for m in months],
                         [('PRE-VERSIONING', False), ('pre-versioning', True)])

    def test_a_small_unknown_version_does_not_wait(self):
        records = (many([(CERTAIN, 'pass', 3)], 'pre-versioning', EARLY)
                   + many([(CERTAIN, 'pass', 10)], 'v1', LATER))
        report = coach_grade.coach_report(records)
        self.assertEqual(report['months'][-1], {'version': 'pre-versioning', 'unknown_version': True,
                                                'month': '2026-03', 'too_few': True})
        self.assertEqual([w['version'] for w in report['waiting']], ['v1'])

    def test_a_naive_instant_is_read_as_utc(self):
        records = (many([(CERTAIN, 'pass', 5)], when=datetime.datetime(2026, 10, 31, 16, 30))
                   + many([(CERTAIN, 'pass', 6)], when=datetime.datetime(2026, 10, 31, 15, 59)))
        months = coach_grade.coach_report(records)['months']
        self.assertEqual([(m['month'], m['facts']) for m in months], [('2026-10', 6), ('2026-11', 5)])


class TestTheChain(SimpleTestCase):

    def test_a_small_middle_version_is_skipped_and_waits(self):
        middle = ([band_fact(f, CERTAIN) for f in FACTS], {'identity': 'pass', 'academic': 'pass',
                                                            'pathway': 'pass'}, 'v1.1', LATER, BY, ROW_ID)
        records = (many([(PROBABLE, 'pass', 60)], 'v1', EARLY) + [middle]
                   + many([(CERTAIN, 'pass', 60)], 'v2', LATEST))
        report = coach_grade.coach_report(records)
        self.assertEqual([(p['previous']['version'], p['new']['version'], p['grade'], p['skipped_versions'])
                          for p in report['coach']], [('v1', 'v2', 'pass', 1)])
        self.assertEqual(report['waiting'], [{'version': 'v1.1', 'too_few': True}])

    def test_a_newest_version_under_the_floor_waits(self):
        records = (many([(PROBABLE, 'pass', 60)], 'v1', EARLY) + many([(CERTAIN, 'pass', 60)], 'v2', LATER)
                   + many([(CERTAIN, 'pass', 10)], 'v3', LATEST))
        report = coach_grade.coach_report(records)
        self.assertEqual([(p['previous']['version'], p['new']['version']) for p in report['coach']],
                         [('v1', 'v2')])
        self.assertEqual(report['waiting'], [{'version': 'v3', 'too_few': False, 'facts': 10, 'score_pct': 100,
                                              'coverage': {'count': 10, 'of': 10},
                                              'generous_wrong': {'count': 0, 'of': 10}}])

    def test_fewer_than_two_gradeable_versions_grade_nothing(self):
        records = many([(PROBABLE, 'pass', 60)], 'v1', EARLY) + many([(CERTAIN, 'pass', 39)], 'v2', LATER)
        report = coach_grade.coach_report(records)
        self.assertEqual(report['coach'], [])
        self.assertEqual([w['version'] for w in report['waiting']], ['v2'])

    def test_a_version_with_no_marked_fact_has_no_place(self):
        zero = [([], {'identity': 'pass'}, 'v0', LATER, BY, ROW_ID)] * 3   # decided, nothing marked
        records = many([(PROBABLE, 'pass', 60)], 'v1', EARLY) + zero + many([(CERTAIN, 'pass', 60)], 'v2', LATEST)
        report = coach_grade.coach_report(records)
        self.assertEqual((report['decided_records'], report['versions_without_marks']), (123, 1))
        self.assertEqual([m['version'] for m in report['months']], ['v1', 'v2'])
        self.assertEqual(report['waiting'], [])
        self.assertEqual([(p['previous']['version'], p['new']['version'], p['skipped_versions'])
                          for p in report['coach']], [('v1', 'v2', 0)])


def mixed_records():
    """'a' 12 facts over four months, 'b' 45 in one, 'c' 3 over two, 'd' 41 over two; in that first-seen
    order a, b, d, c. Some Fails carry the interview reason."""
    return (many([(CERTAIN, 'pass', 6)], 'a', at(3, 2)) + many([(CERTAIN, 'pass', 2)], 'a', at(4))
            + many([(CERTAIN, 'fail', 3, 'interview_differs')], 'a', at(5))
            + many([(CERTAIN, 'pass', 1)], 'a', at(6))
            + many([(PROBABLE, 'pass', 43), (PROBABLE, 'fail', 2, 'interview_differs')], 'b', at(3, 3))
            + many([(CERTAIN, 'pass', 2)], 'c', at(4, 7)) + many([(CERTAIN, 'pass', 1)], 'c', at(5, 7))
            + many([(CERTAIN, 'pass', 40)], 'd', at(3, 4))
            + many([(CERTAIN, 'fail', 1, 'proof_missing')], 'd', at(4)))


def without_documents_only(report):
    """A deep copy of ``report`` with every ``documents_only`` key and ``left_out_reasons`` taken out."""
    def strip(value):
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k != 'documents_only'}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value
    out = strip(json.loads(json.dumps(report)))
    out.pop('left_out_reasons')
    return out


def lines(report):
    """Every ``documents_only`` value in a report, in order."""
    found = []
    sides = report['waiting'] + [s for p in report['coach'] for s in (p['previous'], p['new'])]
    for item in report['months'] + sides:
        if 'documents_only' in item:
            found.append((item['version'], item.get('month'), item['documents_only']))
    return found


class TestOneMonthOneCell(SimpleTestCase):

    def test_a_small_month_is_its_own_too_few_cell(self):
        records = (many([(CERTAIN, 'pass', 50)], 'v1', EARLY) + many([(CERTAIN, 'fail', 3)], 'v1', LATER)
                   + many([(CERTAIN, 'pass', 50)], 'v2', LATEST))
        report = coach_grade.coach_report(records)
        self.assertEqual([(m['version'], m['month'], m['too_few'], m.get('facts')) for m in report['months']],
                         [('v1', '2026-03', False, 50), ('v1', '2026-04', True, None),
                          ('v2', '2026-05', False, 50)])
        self.assertEqual(report['coach'][0]['previous']['facts'], 53)   # the side is the whole version

    def test_the_mixed_cells_are_exact(self):
        report = coach_grade.coach_report(mixed_records())
        self.assertEqual([(m['version'], m['month'], m['too_few'], m.get('facts'), m.get('points'))
                          for m in report['months']],
                         [('a', '2026-03', False, 6, 12), ('a', '2026-04', True, None, None),
                          ('a', '2026-05', True, None, None), ('a', '2026-06', True, None, None),
                          ('b', '2026-03', False, 45, 37), ('d', '2026-03', False, 40, 80),
                          ('d', '2026-04', True, None, None), ('c', '2026-04', True, None, None),
                          ('c', '2026-05', True, None, None)])
        self.assertEqual([(p['previous']['version'], p['new']['version'], p['grade'], p['skipped_versions'])
                          for p in report['coach']], [('b', 'd', 'pass', 0)])
        self.assertEqual(report['waiting'], [{'version': 'a', 'too_few': False, 'facts': 12, 'score_pct': -50,
                                              'coverage': {'count': 12, 'of': 12},
                                              'generous_wrong': {'count': 3, 'of': 12}},
                                             {'version': 'c', 'too_few': True}])
        self.assertEqual(lines(report), [])


class TestLeaveOutChangesNothingButItsLine(SimpleTestCase):

    def test_the_documents_only_report_is_the_plain_report_plus_lines(self):
        plain = coach_grade.coach_report(mixed_records())
        docs = coach_grade.coach_report(mixed_records(), leave_out_reasons=('interview_differs',))
        self.assertEqual(without_documents_only(docs), without_documents_only(plain))
        self.assertEqual((plain['left_out_reasons'], docs['left_out_reasons']), ([], ['interview_differs']))
        self.assertNotIn('documents_only', json.dumps(plain))
        self.assertEqual(lines(docs), [
            ('a', '2026-03', {'too_few': False, 'facts': 6, 'points': 12, 'best': 12, 'score_pct': 100,
                              'left_out': 0}),
            ('b', '2026-03', {'too_few': False, 'facts': 43, 'points': 43, 'best': 86, 'score_pct': 50,
                              'left_out': 2}),
            ('d', '2026-03', {'too_few': False, 'facts': 40, 'points': 80, 'best': 80, 'score_pct': 100,
                              'left_out': 0}),
            ('a', None, {'too_few': False, 'facts': 9, 'points': 18, 'best': 18, 'score_pct': 100,
                         'left_out': 3}),
            ('b', None, {'too_few': False, 'facts': 43, 'points': 43, 'best': 86, 'score_pct': 50,
                         'left_out': 2}),
            ('d', None, {'too_few': False, 'facts': 41, 'points': 70, 'best': 82, 'score_pct': 85,
                         'left_out': 0}),
        ])

    def test_reviewer_case_p1_cells_hold_with_and_without_the_leave_out(self):
        records = (many([(CERTAIN, 'pass', 4), (CERTAIN, 'fail', 1, 'interview_differs')], 'v1', at(1))
                   + [one(RULE_NOT_MET, 'pass', 'v1', at(2)), one(PROBABLE, 'fail', 'v1', at(2), 'proof_missing')]
                   + many([(CERTAIN, 'pass', 5)], 'v1', at(3)))
        plain = coach_grade.coach_report(records)
        docs = coach_grade.coach_report(records, leave_out_reasons=coach_grade.DOCUMENTS_ONLY)
        want = [('2026-01', False, 5, -2), ('2026-02', True, None, None), ('2026-03', False, 5, 10)]
        for report in (plain, docs):
            self.assertEqual([(m['month'], m['too_few'], m.get('facts'), m.get('points'))
                              for m in report['months']], want)
        self.assertEqual(without_documents_only(docs), without_documents_only(plain))
        self.assertEqual([m.get('documents_only') for m in docs['months']],
                         [{'too_few': True}, None, {'too_few': False, 'facts': 5, 'points': 10, 'best': 10,
                                                    'score_pct': 100, 'left_out': 0}])
        self.assertEqual(docs['waiting'], [{'version': 'v1', 'too_few': False, 'facts': 12, 'score_pct': -21,
                                            'coverage': {'count': 12, 'of': 12},
                                            'generous_wrong': {'count': 2, 'of': 12},
                                            'documents_only': {'too_few': False, 'facts': 11, 'points': 5,
                                                               'best': 22, 'score_pct': 23, 'left_out': 1}}])

    def test_reviewer_case_p2_a_middle_version_of_interview_fails_keeps_its_place(self):
        records = (many([(PROBABLE, 'pass', 50)], 'v1', at(1))
                   + many([(CERTAIN, 'fail', 3, 'interview_differs')], 'v1.1', at(2))
                   + many([(CERTAIN, 'pass', 50)], 'v2', at(3)))
        for leave_out in ((), coach_grade.DOCUMENTS_ONLY):
            report = coach_grade.coach_report(records, leave_out_reasons=leave_out)
            self.assertEqual([m for m in report['months'] if m['version'] == 'v1.1'],
                             [{'version': 'v1.1', 'unknown_version': False, 'month': '2026-02', 'too_few': True}])
            self.assertEqual(report['waiting'], [{'version': 'v1.1', 'too_few': True}], leave_out)
            self.assertEqual([(p['previous']['version'], p['new']['version'], p['grade'], p['skipped_versions'])
                              for p in report['coach']], [('v1', 'v2', 'pass', 1)], leave_out)
            self.assertEqual(report['versions_without_marks'], 0, leave_out)

    def test_the_same_records_a_month_later_show_the_same_old_cells(self):
        base = many([(CERTAIN, 'pass', 5)], 'v1', at(1)) + [one(CERTAIN, 'fail', 'v1', at(2)),
                                                            one(UNVERIFIABLE, 'pass', 'v1', at(2))]
        before = coach_grade.coach_report(base)['months']
        after = coach_grade.coach_report(base + many([(CERTAIN, 'pass', 5)], 'v1', at(3)))['months']
        self.assertEqual(after[:2], before)   # no cell is re-cut when a later month arrives
        self.assertEqual([(m['month'], m['too_few']) for m in after],
                         [('2026-01', False), ('2026-02', True), ('2026-03', False)])


class TestDocumentsOnly(SimpleTestCase):

    def records(self):
        return many([(CERTAIN, 'pass', 5), (CERTAIN, 'fail', 1, 'interview_differs'),
                     (CERTAIN, 'fail', 1, 'proof_missing')])

    def test_the_default_is_the_plain_score(self):
        records = self.records() + many([(PROBABLE, 'pass', 40)], 'v2', LATER)
        self.assertEqual(coach_grade.coach_report(records), coach_grade.coach_report(records, ()))
        cell = coach_grade.coach_report(records)['months'][0]
        self.assertEqual((cell['facts'], cell['points'], cell['best']), (7, -10, 14))
        self.assertNotIn('left_out', cell)
        self.assertNotIn('documents_only', cell)

    def test_an_interview_fail_is_left_out_of_points_and_best_in_its_line(self):
        cell = coach_grade.coach_report(self.records(), leave_out_reasons=coach_grade.DOCUMENTS_ONLY)['months'][0]
        self.assertEqual((cell['facts'], cell['points'], cell['best'], cell['score_pct']), (7, -10, 14, -71))
        self.assertEqual(cell['outcomes']['wrong_sure'], 2)   # the plain cell keeps both Fails
        # the proof_missing Fail still costs in the line; the interview Fail does not
        self.assertEqual(cell['documents_only'], {'too_few': False, 'facts': 6, 'points': 0, 'best': 12,
                                                  'score_pct': 0, 'left_out': 1})

    def test_the_grade_stays_plain_and_each_side_gains_its_line(self):
        old = [(PROBABLE, 'pass', 40)]
        new = [(CERTAIN, 'pass', 40), (CERTAIN, 'fail', 1, 'interview_differs')]
        records = many(old, 'old', EARLY) + many(new, 'next', LATER)
        plain = coach_grade.coach_report(records)['coach'][0]
        self.assertEqual((plain['grade'], plain['reasons']), ('fail', ['generous_wrong_rose']))
        docs = coach_grade.coach_report(records, leave_out_reasons=coach_grade.DOCUMENTS_ONLY)
        pair = docs['coach'][0]
        self.assertEqual((pair['grade'], pair['reasons'], pair['new']['facts'], pair['new']['generous_wrong']),
                         ('fail', ['generous_wrong_rose'], 41, {'count': 1, 'of': 41}))
        self.assertEqual(pair['new']['documents_only'], {'too_few': False, 'facts': 40, 'points': 80, 'best': 80,
                                                         'score_pct': 100, 'left_out': 1})
        self.assertEqual(pair['previous']['documents_only'], {'too_few': False, 'facts': 40, 'points': 40,
                                                              'best': 80, 'score_pct': 50, 'left_out': 0})

    def test_a_side_under_five_left_shows_a_too_few_line(self):
        records = many([(CERTAIN, 'pass', 3), (CERTAIN, 'fail', 3, 'interview_differs')], 'v1', EARLY)
        docs = coach_grade.coach_report(records, leave_out_reasons=coach_grade.DOCUMENTS_ONLY)
        self.assertEqual(docs['waiting'], [{'version': 'v1', 'too_few': False, 'facts': 6, 'score_pct': -200,
                                            'coverage': {'count': 6, 'of': 6},
                                            'generous_wrong': {'count': 3, 'of': 6},
                                            'documents_only': {'too_few': True}}])

    def test_a_left_out_candidate_with_no_band_stays_not_scored(self):
        no_band = ([], {'identity': 'fail', 'fail_reasons': {'identity': 'interview_differs'}}, 'v1', EARLY, BY,
                   ROW_ID)
        records = many([(CERTAIN, 'pass', 6)]) + [no_band]
        cell = coach_grade.coach_report(records, leave_out_reasons=coach_grade.DOCUMENTS_ONLY)['months'][0]
        self.assertEqual((cell['facts'], cell['not_scored']), (6, 1))
        self.assertEqual(cell['documents_only'], {'too_few': False, 'facts': 6, 'points': 12, 'best': 12,
                                                  'score_pct': 100, 'left_out': 0})

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
        self.assertEqual((docs['facts'], docs['points'], docs['best']), (8, -32, 16))
        self.assertEqual(docs['documents_only'], {'too_few': False, 'facts': 6, 'points': -12, 'best': 12,
                                                  'score_pct': -100, 'left_out': 2})
        self.assertEqual(verdict['identity'], 'fail')   # the caller's record is not changed
