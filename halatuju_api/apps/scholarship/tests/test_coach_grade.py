"""LL5 phase A - the monthly score and the coach grade (`coach_grade`, pure). Synthetic records only.

Every expected value is worked out by hand in the comments (points: Certain +2 / -10, Probable +1 / -3,
Unsure 0, Can't verify -1 / +1, Rule not met -10 / +2 for pass / fail). The score margin: clear when
(m2 - m1)^2 > 4 x (v1/n1 + v2/n2), v = (sum of squares - n m^2) / (n - 1)."""
import datetime
import json
import random
from fractions import Fraction
from unittest import mock

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

    def test_the_margin(self):
        self.assertEqual(coach_grade.GUARD_ALPHA, Fraction(1, 20))
        self.assertEqual(coach_grade.SCORE_Z, 2)

    def test_the_report_names_the_floors_and_the_margin(self):
        report = coach_grade.coach_report([])
        self.assertEqual((report['cell_min_facts'], report['coach_min_facts'], report['guard_alpha'],
                          report['score_z'], report['malformed_records']),
                         (5, 40, {'count': 1, 'of': 20}, 2, 0))
        json.dumps(report)   # JSON-safe

    def test_the_closed_sets(self):
        self.assertEqual(coach_grade.GRADES, ('pass', 'fail', 'no_change'))
        self.assertEqual(coach_grade.REASON_CODES, ('coverage_dropped', 'generous_wrong_rose', 'score_up',
                                                    'no_clear_change', 'score_down'))
        self.assertEqual(coach_grade.INTERVIEW_FAILS, ('interview_differs',))
        self.assertFalse(hasattr(coach_grade, 'DOCUMENTS_ONLY'))
        self.assertFalse(hasattr(coach_grade, 'SCORE_SAME'))


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
        for leave_out in ((), coach_grade.INTERVIEW_FAILS):
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

    def test_an_exact_tie_is_no_clear_change(self):
        pair = first_pair([(CERTAIN, 'pass', 40)], [(CERTAIN, 'pass', 40)])
        self.assertEqual((pair['grade'], pair['reasons']), ('no_change', ['no_clear_change']))
        # 40/80 against 80/160: the same mean (1) at a different size
        pair = first_pair([(PROBABLE, 'pass', 40)], [(PROBABLE, 'pass', 80)])
        self.assertEqual((pair['grade'], pair['reasons']), ('no_change', ['no_clear_change']))

    def test_two_negative_scores_less_negative_is_up(self):
        old = [(CERTAIN, 'fail', 40)]                            # -400 / 80 = -500%
        new = [(CERTAIN, 'fail', 20), (PROBABLE, 'fail', 20)]    # -260 / 80 = -325%
        up = first_pair(old, new)
        self.assertEqual((up['previous']['score_pct'], up['new']['score_pct']), (-500, -325))
        self.assertEqual((up['grade'], up['reasons']), ('pass', ['score_up']))
        self.assertEqual((first_pair(new, old)['grade'], first_pair(new, old)['reasons']),
                         ('fail', ['score_down']))

    def test_a_small_difference_inside_two_standard_errors_is_no_clear_change(self):
        # old 39/80 = 48.75% and next 41/84 = 48.81%: next is higher by a hair, far inside the margin
        # (means 39/40 = 0.975 and 41/42 = 0.976; v/n is about 0.0032 and 0.0029, so 4 x (v1/n1 + v2/n2)
        # is about 0.024 against a squared difference of about 0.0000014)
        old = [(CERTAIN, 'pass', 1), (PROBABLE, 'pass', 38), (UNVERIFIABLE, 'pass', 1)]
        new = [(CERTAIN, 'pass', 1), (PROBABLE, 'pass', 40), (UNVERIFIABLE, 'pass', 1)]
        up = first_pair(old, new)
        self.assertEqual((up['previous']['score_pct'], up['new']['score_pct']), (49, 49))
        self.assertEqual((up['grade'], up['reasons']), ('no_change', ['no_clear_change']))
        down = first_pair(new, old)
        self.assertEqual((down['grade'], down['reasons']), ('no_change', ['no_clear_change']))

    def test_the_score_margin_edge_is_exact(self):
        # old: 40 Probable passes, every fact +1: mean 1, variance 0. next: k Certain passes (+2) and
        # 40 - k Probable passes (+1): mean 1 + k/40, variance (k (40 - k) / 40) / 39.
        # Clear  <=>  (k/40)^2 > 4 k (40 - k) / (40^2 x 39)  <=>  39 k > 4 (40 - k)  <=>  k > 160/43 = 3.72.
        old = [(PROBABLE, 'pass', 40)]
        three = [(CERTAIN, 'pass', 3), (PROBABLE, 'pass', 37)]   # 43/80 = 54% against 50%: not clear
        four = [(CERTAIN, 'pass', 4), (PROBABLE, 'pass', 36)]    # 44/80 = 55%: clear
        self.assertEqual(first_pair(old, three)['reasons'], ['no_clear_change'])
        self.assertEqual((first_pair(old, four)['grade'], first_pair(old, four)['reasons']),
                         ('pass', ['score_up']))
        # the mirror: the same spread on the OLD side, the score falls
        self.assertEqual(first_pair(three, old)['reasons'], ['no_clear_change'])
        self.assertEqual((first_pair(four, old)['grade'], first_pair(four, old)['reasons']),
                         ('fail', ['score_down']))

    def test_unequal_sides_use_separate_variances_not_a_pooled_one(self):
        # wide (40 facts): 38 Certain passes (+2) and 2 Rule-not-met passes (-10): points 76 - 20 = 56,
        #   mean 7/5; squares 38 x 4 + 2 x 100 = 352; v1 = (352 - 40 x 49/25) / 39 = (1368/5) / 39
        #   = 456/65 (about 7.02); v1/n1 = 57/325.
        # narrow (400 facts): 380 Probable passes (+1) and 20 Certain passes (+2): points 420, mean 21/20;
        #   squares 380 + 80 = 460; v2 = (460 - 441) / 399 = 1/21 (about 0.048); v2/n2 = 1/8400.
        # Difference 7/5 - 21/20 = 7/20, squared 49/400 (0.1225).
        # SEPARATE (the rule): 4 x (57/325 + 1/8400) = 4 x 19165/109200 = 3833/5460 (about 0.702)
        #   > 49/400: NOT clear.
        # POOLED (a wrong rule): vp = (39 v1 + 399 v2) / 438 = (1368/5 + 19) / 438 = 1463/2190;
        #   4 x vp x (1/40 + 1/400) = 4 x 1463/2190 x 11/400 = 16093/219000 (about 0.073) < 49/400: clear.
        # Neither guard moves: every fact on both sides is covered and none is generous-wrong.
        wide = [(CERTAIN, 'pass', 38), (RULE_NOT_MET, 'pass', 2)]
        narrow = [(PROBABLE, 'pass', 380), (CERTAIN, 'pass', 20)]
        self.assertGreater(Fraction(3833, 5460), Fraction(49, 400))
        self.assertLess(Fraction(16093, 219000), Fraction(49, 400))
        for prev, new in ((narrow, wide), (wide, narrow)):
            pair = first_pair(prev, new)
            self.assertEqual((pair['previous']['generous_wrong']['count'], pair['new']['generous_wrong']['count'],
                              pair['previous']['coverage']['count'] == pair['previous']['facts'],
                              pair['new']['coverage']['count'] == pair['new']['facts']), (0, 0, True, True))
            self.assertEqual((pair['grade'], pair['reasons']), ('no_change', ['no_clear_change']))
        self.assertEqual(first_pair(narrow, wide)['new']['facts'], 40)
        self.assertEqual(first_pair(wide, narrow)['new']['facts'], 400)

    def test_the_variance_is_the_sample_variance(self):
        # wide (40 facts): 39 Certain passes (+2) and 1 Rule-not-met pass (-10): points 68, mean 17/10;
        #   squares 39 x 4 + 100 = 256; 256 - 40 x 289/100 = 702/5.
        # narrow (400 facts): 360 Probable passes (+1) and 40 Certain passes (+2): points 440, mean
        #   11/10; squares 360 + 160 = 520; 520 - 400 x 121/100 = 36.
        # Difference 6/10, squared 9/25 = 3600/10000.
        # SAMPLE (divisor n - 1, the rule): v1 = 702/195 = 18/5, v1/n1 = 9/100; v2 = 36/399 = 12/133,
        #   v2/n2 = 3/13300; 4 x (9/100 + 3/13300) = 4 x 12/133 = 48/133 (about 0.3609) > 9/25: NOT clear.
        # POPULATION (divisor n, a wrong rule): v1 = 702/200, v1/n1 = 351/4000; v2 = 36/400, v2/n2 =
        #   9/40000; 4 x 3519/40000 = 3519/10000 < 3600/10000: clear.
        wide = [(CERTAIN, 'pass', 39), (RULE_NOT_MET, 'pass', 1)]
        narrow = [(PROBABLE, 'pass', 360), (CERTAIN, 'pass', 40)]
        self.assertGreater(Fraction(48, 133), Fraction(9, 25))
        self.assertLess(Fraction(3519, 10000), Fraction(9, 25))
        for prev, new in ((narrow, wide), (wide, narrow)):
            pair = first_pair(prev, new)
            self.assertEqual((pair['grade'], pair['reasons']), ('no_change', ['no_clear_change']))

    def test_both_variances_zero_any_difference_is_clear(self):
        # every fact on a side scores the same, so 4 x (v1/n1 + v2/n2) = 0: Can't verify Fails (+1 each)
        # against Rule not met Fails (+2 each); coverage 40 of 40 and generous-wrong 0 on both sides
        low, high = [(UNVERIFIABLE, 'fail', 40)], [(RULE_NOT_MET, 'fail', 40)]
        self.assertEqual((first_pair(low, high)['grade'], first_pair(low, high)['reasons']),
                         ('pass', ['score_up']))
        self.assertEqual((first_pair(high, low)['grade'], first_pair(high, low)['reasons']),
                         ('fail', ['score_down']))
        # Probable passes (+1 each) against Can't verify Fails (+1 each): the same mean, no clear change
        same = first_pair([(PROBABLE, 'pass', 40)], low)
        self.assertEqual((same['grade'], same['reasons']), ('no_change', ['no_clear_change']))

    def test_a_version_that_firms_up_its_answers_is_not_punished(self):
        # old: 40 Probable passes, +40, mean 1, variance 0, generous-wrong 0 of 40.
        # next: 39 Certain passes and 1 Certain Fail: 78 - 10 = 68, mean 17/10; squares 39 x 4 + 100 = 256;
        # variance (256 - 40 x (17/10)^2) / 39 = (256 - 115.6) / 39 = 18/5; v/n = 9/100;
        # 4 x 9/100 = 36/100 < (7/10)^2 = 49/100: score up.
        # generous-wrong 0 of 40 against 1 of 40: chance C(40,1)/C(80,1) = 1/2, not broken.
        pair = first_pair([(PROBABLE, 'pass', 40)], [(CERTAIN, 'pass', 39), (CERTAIN, 'fail', 1)])
        self.assertEqual(pair['new']['generous_wrong'], {'count': 1, 'of': 40})
        self.assertEqual((pair['grade'], pair['reasons']), ('pass', ['score_up']))

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

    def test_the_fisher_tail_hand_checks(self):
        # previous 0 of 40, new k of 40, generous-wrong: with k in all, the new side holds all k only
        # one way in C(80,k)/C(40,k): k = 4 is C(40,4)/C(80,4) = 91390/1581580, about 0.058 (not below
        # 1 in 20); k = 5 is C(40,5)/C(80,5) = 658008/24040016, about 0.027 (below)
        self.assertEqual(coach_grade._new_side_tail(0, 40, 4, 40, low=False), Fraction(91390, 1581580))
        self.assertEqual(coach_grade._new_side_tail(0, 40, 5, 40, low=False), Fraction(658008, 24040016))
        # the coverage mirror: covered 40 of 40 then 36 (or 35) of 40 is the same count of Unsure
        self.assertEqual(coach_grade._new_side_tail(40, 40, 36, 40, low=True), Fraction(91390, 1581580))
        self.assertEqual(coach_grade._new_side_tail(40, 40, 35, 40, low=True), Fraction(658008, 24040016))
        # one of 40 against none: C(40,1)/C(80,1) = 1/2
        self.assertEqual(coach_grade._new_side_tail(0, 40, 1, 40, low=False), Fraction(1, 2))

    def test_guard_one_coverage_drop_fails_even_when_the_score_rose(self):
        old = [(UNVERIFIABLE, 'pass', 40)]                       # -50%, coverage 40/40, mean -1
        # 35 Certain passes, 5 Unsure: 70/80 = 88%, coverage 35/40, chance 0.027: broken
        pair = first_pair(old, [(CERTAIN, 'pass', 35), (UNSURE, 'pass', 5)])
        self.assertGreater(pair['new']['score_pct'], pair['previous']['score_pct'])
        self.assertEqual(pair['new']['coverage'], {'count': 35, 'of': 40})
        self.assertEqual((pair['grade'], pair['reasons']), ('fail', ['coverage_dropped']))
        # 36 and 4: coverage 36/40, chance 0.058, inside the margin; mean 1.8 against -1, variance
        # (144 - 129.6)/39 = 0.369, 4 x 0.369/40 = 0.037 < 2.8^2: score up
        pair = first_pair(old, [(CERTAIN, 'pass', 36), (UNSURE, 'pass', 4)])
        self.assertEqual((pair['grade'], pair['reasons']), ('pass', ['score_up']))
        # one Unsure (39/40, chance 1/2) is far inside the margin
        self.assertEqual(first_pair(old, [(CERTAIN, 'pass', 39), (UNSURE, 'pass', 1)])['reasons'], ['score_up'])

    def test_guard_one_a_small_drop_is_inside_the_margin(self):
        old = [(PROBABLE, 'pass', 39), (UNSURE, 'pass', 1)]      # 39/40 covered, mean 0.975
        new = [(CERTAIN, 'pass', 78), (UNSURE, 'pass', 2)]       # 78/80, the same share
        self.assertEqual(first_pair(old, new)['reasons'], ['score_up'])
        # 77/80 is a lower share, but by chance: (C(80,4) + C(80,3) x C(40,1)) / C(120,4)
        # = (1581580 + 3286400) / 8214570, about 0.59; mean 1.925 against 0.975, clearly up
        pair = first_pair(old, [(CERTAIN, 'pass', 77), (UNSURE, 'pass', 3)])
        self.assertEqual(pair['new']['coverage'], {'count': 77, 'of': 80})
        self.assertEqual((pair['grade'], pair['reasons']), ('pass', ['score_up']))

    def test_a_guard_that_moves_the_right_way_never_breaks(self):
        # generous-wrong 40 of 40 (all Certain Fails, mean -10) to 0 of 40 (all Certain passes, mean 2)
        pair = first_pair([(CERTAIN, 'fail', 40)], [(CERTAIN, 'pass', 40)])
        self.assertEqual((pair['grade'], pair['reasons']), ('pass', ['score_up']))
        # coverage 0 of 40 (all Unsure, mean 0) to 40 of 40 (all Certain passes, mean 2)
        pair = first_pair([(UNSURE, 'pass', 40)], [(CERTAIN, 'pass', 40)])
        self.assertEqual((pair['grade'], pair['reasons']), ('pass', ['score_up']))

    def test_guard_two_generous_wrong_rise_fails_even_when_the_score_rose(self):
        old = [(UNVERIFIABLE, 'pass', 40)]                       # -50%, generous-wrong 0/40, mean -1
        for wrong_band in (CERTAIN, PROBABLE):
            # 5 of 40: chance 0.027, broken. The score still rose: with Certain Fails mean
            # (70 - 50)/40 = 0.5, variance (640 - 10)/39 = 16.15, 4 x 16.15/40 = 1.62 < 1.5^2 = 2.25
            pair = first_pair(old, [(CERTAIN, 'pass', 35), (wrong_band, 'fail', 5)])
            self.assertGreater(pair['new']['score_pct'], pair['previous']['score_pct'])
            self.assertEqual(pair['new']['generous_wrong'], {'count': 5, 'of': 40})
            self.assertEqual((pair['grade'], pair['reasons']), ('fail', ['generous_wrong_rose']), wrong_band)
            # 4 of 40: chance 0.058, inside the margin; with Certain Fails mean 0.8, variance
            # (544 - 25.6)/39 = 13.29, 4 x 13.29/40 = 1.33 < 1.8^2 = 3.24: score up
            pair = first_pair(old, [(CERTAIN, 'pass', 36), (wrong_band, 'fail', 4)])
            self.assertEqual((pair['grade'], pair['reasons']), ('pass', ['score_up']), wrong_band)

    def test_a_clear_worsening_is_caught(self):
        # generous-wrong 1 of 100 against 15 of 100: chance (C(100,15) x 100 + C(100,16)) / C(200,16),
        # about 0.00016, far below 1 in 20
        pair = first_pair([(CERTAIN, 'pass', 99), (CERTAIN, 'fail', 1)],
                          [(CERTAIN, 'pass', 85), (CERTAIN, 'fail', 15)])
        self.assertEqual((pair['grade'], pair['reasons']), ('fail', ['generous_wrong_rose']))

    def test_guard_two_counts_only_a_generous_band_the_reviewer_failed(self):
        old = [(PROBABLE, 'pass', 40)]
        for band, says in ((RULE_NOT_MET, 'pass'), (UNVERIFIABLE, 'pass'), (RULE_NOT_MET, 'fail')):
            pair = first_pair(old, [(CERTAIN, 'pass', 39), (band, says, 1)])
            self.assertEqual(pair['new']['generous_wrong'], {'count': 0, 'of': 40}, (band, says))
            self.assertEqual(pair['grade'], 'pass', (band, says))

    def test_guard_two_from_a_non_zero_share_small_moves_are_no_clear_change(self):
        old = [(CERTAIN, 'pass', 39), (CERTAIN, 'fail', 1)]   # 1 of 40, mean 17/10, v/n 9/100 (see above)
        # 2 of 80: the same share and the same mean 136/80 = 17/10
        same = first_pair(old, [(CERTAIN, 'pass', 78), (CERTAIN, 'fail', 2)])
        self.assertEqual(same['new']['generous_wrong'], {'count': 2, 'of': 80})
        self.assertEqual((same['grade'], same['reasons']), ('no_change', ['no_clear_change']))
        # 1 of 80: mean 148/80 = 1.85; v = (416 - 273.8)/79 = 1.8, v/n = 0.0225;
        # 4 x (0.09 + 0.0225) = 0.45 > 0.15^2 = 0.0225: not clear
        lower = first_pair(old, [(CERTAIN, 'pass', 79), (CERTAIN, 'fail', 1)])
        self.assertEqual((lower['grade'], lower['reasons']), ('no_change', ['no_clear_change']))
        # 3 of 80: a higher share, chance (C(80,3) x C(40,1) + C(80,4)) / C(120,4), about 0.59: not
        # broken; mean 1.55, v = (608 - 192.2)/79 = 5.26, 4 x (0.09 + 0.066) = 0.62 > 0.0225: not clear
        rose = first_pair(old, [(CERTAIN, 'pass', 77), (CERTAIN, 'fail', 3)])
        self.assertEqual((rose['grade'], rose['reasons']), ('no_change', ['no_clear_change']))

    def test_both_guards_are_named(self):
        old = [(PROBABLE, 'pass', 40)]
        # coverage 35 of 40 and generous-wrong 5 of 40: each chance 0.027
        new = [(CERTAIN, 'pass', 30), (UNSURE, 'pass', 5), (CERTAIN, 'fail', 5)]
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
        # one record of the new version shows Identity Unsure: coverage 39 of 40, inside the margin
        unsure_identity = ([band_fact('identity', UNSURE)] + [band_fact(f, CERTAIN) for f in FACTS[1:]],
                           {f: 'pass' for f in FACTS}, 'next', LATER, BY, ROW_ID)
        new[0] = unsure_identity
        pair = coach_grade.coach_report(old + new)['coach'][0]
        self.assertEqual(pair['new']['coverage'], {'count': 39, 'of': 40})
        self.assertEqual((pair['grade'], pair['reasons']), ('pass', ['score_up']))
        # five such records: coverage 35 of 40, chance 0.027, broken
        new[:5] = [unsure_identity] * 5
        pair = coach_grade.coach_report(old + new)['coach'][0]
        self.assertEqual(pair['new']['coverage'], {'count': 35, 'of': 40})
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

    def test_the_display_label_itself_is_the_unknown_version(self):
        records = (many([(CERTAIN, 'pass', 50)], '(unknown version)', EARLY)
                   + many([(CERTAIN, 'pass', 10)], ' (unknown version) ', EARLY)
                   + many([(PROBABLE, 'pass', 50)], 'v2', LATER) + many([(CERTAIN, 'pass', 50)], '', LATEST))
        report = coach_grade.coach_report(records)
        self.assertEqual([(m['version'], m['unknown_version'], m['month'], m['facts']) for m in report['months']],
                         [('v2', False, '2026-04', 50), ('(unknown version)', True, '2026-03', 60),
                          ('(unknown version)', True, '2026-05', 50)])
        self.assertEqual((report['coach'], report['waiting']), ([], []))

    def test_a_very_long_digit_run_does_not_raise(self):
        # int() refuses more than 4,300 digits; the order reads a run by its length, then its text
        long_small, long_big = 'v' + '9' * 4400, 'v' + '1' * 5000
        records = (many([(CERTAIN, 'pass', 45)], long_big, EARLY) + many([(PROBABLE, 'pass', 45)], long_small, EARLY)
                   + many([(PROBABLE, 'pass', 5)], 'v8', LATER) + many([(PROBABLE, 'pass', 5)], 'v007', LATER))
        report = coach_grade.coach_report(records)
        self.assertEqual([m['version'] for m in report['months']], [long_small, long_big, 'v007', 'v8'])
        self.assertEqual(report['coach'][0]['grade'], 'pass')

    def test_leading_zeros_do_not_change_the_order(self):
        records = (many([(CERTAIN, 'pass', 5)], 'r10', EARLY) + many([(CERTAIN, 'pass', 5)], 'r009', EARLY)
                   + many([(CERTAIN, 'pass', 5)], 'r9', EARLY))
        months = coach_grade.coach_report(records)['months']
        # 009 and 9 are the same number, then the label text decides; 10 comes last
        self.assertEqual([m['version'] for m in months], ['r009', 'r9', 'r10'])


class TestMalformedRecords(SimpleTestCase):

    def test_a_malformed_record_is_left_out_and_counted(self):
        good = many([(CERTAIN, 'pass', 45)], 'v1', EARLY) + many([(PROBABLE, 'pass', 45)], 'v2', LATER)
        bad_evidence = ([{'fact': 'identity', 'status': 'review', 'evidence': 5, 'unresolved': [],
                          'note': 'SENTINEL-NOTE-M4P2'}], {'identity': 'pass'}, 'SENTINEL-VERSION-M4P2', LATER,
                        BY, ROW_ID)
        bad_unresolved = ([{'fact': 'identity', 'status': 'review', 'evidence': [], 'unresolved': 7}],
                          {'identity': 'fail'}, 'v2', LATER, BY, ROW_ID)
        bad_snapshot = (5, {'identity': 'pass'}, 'v2', LATER, BY, ROW_ID)
        bad_instant = one(CERTAIN, 'pass', 'v2', '2026-04-06')
        bad_date = one(CERTAIN, 'pass', 'v2', datetime.date(2026, 4, 6))
        not_a_record = None
        records = good + [bad_evidence, bad_unresolved, bad_snapshot, bad_instant, bad_date, not_a_record]
        report = coach_grade.coach_report(records, leave_out_reasons=coach_grade.INTERVIEW_FAILS)
        self.assertEqual((report['malformed_records'], report['decided_records']), (6, 90))
        self.assertEqual(report['malformed_by_error'], {'TypeError': 4, 'not_a_datetime': 2})
        clean = coach_grade.coach_report(good, leave_out_reasons=coach_grade.INTERVIEW_FAILS)
        report.pop('malformed_records')
        report.pop('malformed_by_error')
        self.assertEqual((clean.pop('malformed_records'), clean.pop('malformed_by_error')), (0, {}))
        self.assertEqual(report, clean)   # nothing of a malformed record reaches any figure
        dump = json.dumps(report)
        self.assertNotIn('SENTINEL', dump)
        self.assertIn('"v2"', dump)

    def test_an_undecided_record_is_not_malformed(self):
        report = coach_grade.coach_report([one(CERTAIN, 'pass', when=None), one(CERTAIN, 'pass', when=None)[:4]])
        self.assertEqual((report['malformed_records'], report['decided_records'], report['malformed_by_error']),
                         (0, 0, {}))

    def test_a_record_of_fewer_than_four_fields_is_malformed(self):
        good = many([(CERTAIN, 'pass', 5)])
        short = [(), (5, 'x', 'v1'), 'abc', {}, one(CERTAIN, 'pass')[:3]]
        report = coach_grade.coach_report(good + short)
        self.assertEqual((report['malformed_records'], report['decided_records'], report['malformed_by_error']),
                         (5, 5, {'too_short': 5}))
        self.assertEqual(report, dict(coach_grade.coach_report(good), malformed_records=5,
                                      malformed_by_error={'too_short': 5}))

    def test_a_record_of_four_or_five_fields_is_read_like_a_full_one(self):
        full = many([(CERTAIN, 'pass', 5)])
        short = [record[:4] for record in full[:2]] + [record[:5] for record in full[2:]]
        self.assertEqual(coach_grade.coach_report(short), coach_grade.coach_report(full))

    def test_a_decided_time_at_the_edge_of_the_calendar_is_left_out_and_counted(self):
        # The reviewer's four: each overflows on the move to UTC or to Malaysia time (UTC+8).
        edges = (datetime.datetime(9999, 12, 31, 20, tzinfo=UTC), datetime.datetime(9999, 12, 31, 20),
                 datetime.datetime.max,
                 datetime.datetime(1, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=14))))
        good = many([(CERTAIN, 'pass', 5)])
        records = good + [one(CERTAIN, 'pass', 'SENTINEL-EDGE', when) for when in edges]
        for leave_out in ((), coach_grade.INTERVIEW_FAILS):
            report = coach_grade.coach_report(records, leave_out_reasons=leave_out)
            self.assertEqual((report['malformed_records'], report['decided_records'], report['malformed_by_error']),
                             (4, 5, {'OverflowError': 4}), leave_out)
            self.assertEqual([(m['version'], m['month'], m['facts']) for m in report['months']],
                             [('v1', '2026-03', 5)])
            self.assertNotIn('SENTINEL', json.dumps(report))

    def test_a_zone_that_cannot_say_its_offset_is_malformed(self):
        class NoOffset(datetime.tzinfo):
            def utcoffset(self, dt):
                return None

        class RaisingOffset(datetime.tzinfo):
            def utcoffset(self, dt):
                raise ValueError('no offset')

        class TextOffset(datetime.tzinfo):        # datetime itself refuses it (TypeError)
            def utcoffset(self, dt):
                return '+08:00'

        class DayLongOffset(datetime.tzinfo):     # datetime itself refuses 24 hours or more (ValueError)
            def utcoffset(self, dt):
                return datetime.timedelta(hours=25)

        good = many([(CERTAIN, 'pass', 5)])
        odd = [one(CERTAIN, 'pass', when=datetime.datetime(2026, 3, 2, 3, tzinfo=zone()))
               for zone in (NoOffset, RaisingOffset, TextOffset, DayLongOffset)]
        report = coach_grade.coach_report(good + odd)
        kinds = {'TypeError': 1, 'ValueError': 2, 'no_offset': 1}
        self.assertEqual((report['malformed_records'], report['decided_records'], report['malformed_by_error']),
                         (4, 5, kinds))
        self.assertEqual(report, dict(coach_grade.coach_report(good), malformed_records=4,
                                      malformed_by_error=kinds))

    def test_any_ordinary_error_from_a_zone_is_malformed(self):
        class Raising(datetime.tzinfo):
            def __init__(self, error):
                self.error = error

            def utcoffset(self, dt):
                raise self.error

        good = many([(CERTAIN, 'pass', 5)])
        zones = (datetime.tzinfo(),   # the base class: its utcoffset raises NotImplementedError
                 Raising(RuntimeError('CANARY-ZONE-R7')), Raising(ZeroDivisionError('CANARY-ZONE-Z8')))
        odd = [one(CERTAIN, 'pass', when=datetime.datetime(2026, 3, 2, 3, tzinfo=zone)) for zone in zones]
        kinds = {'NotImplementedError': 1, 'RuntimeError': 1, 'ZeroDivisionError': 1}
        report = coach_grade.coach_report(good + odd)
        self.assertEqual(report, dict(coach_grade.coach_report(good), malformed_records=3,
                                      malformed_by_error=kinds))
        self.assertNotIn('CANARY', repr(report))

    def test_a_record_whose_length_or_fields_raise_is_malformed(self):
        class SixThatRaise:
            def __len__(self):
                return 6

            def __getitem__(self, i):
                raise IndexError('CANARY-ITEM-I4')

        class NoLength:
            def __len__(self):
                raise RuntimeError('CANARY-LEN-L2')

        good = many([(CERTAIN, 'pass', 5)])
        report = coach_grade.coach_report(good + [SixThatRaise(), NoLength(), None])
        kinds = {'IndexError': 1, 'RuntimeError': 1, 'TypeError': 1}
        self.assertEqual(report, dict(coach_grade.coach_report(good), malformed_records=3,
                                      malformed_by_error=kinds))
        self.assertNotIn('CANARY', repr(report))

    def test_a_datetime_subclass_cannot_break_the_order(self):
        class Hostile(datetime.datetime):
            def __lt__(self, other):
                raise RuntimeError('CANARY-LT')

            __gt__ = __le__ = __ge__ = __lt__

        # two rows of one version: the first-instant comparison runs on rebuilt PLAIN times
        records = (many([(CERTAIN, 'pass', 7)], 'v2', Hostile(2026, 3, 15, 3, 0))
                   + many([(CERTAIN, 'pass', 5)], 'v1', Hostile(2026, 3, 31, 17, 0, tzinfo=UTC))
                   + many([(CERTAIN, 'pass', 6)], 'v1', Hostile(2026, 3, 1, 3, 0, tzinfo=UTC)))
        report = coach_grade.coach_report(records)
        # 31 Mar 17:00 UTC is 1 Apr in Malaysia; v1 first decided 1 Mar, before v2 (15 Mar)
        self.assertEqual([(m['version'], m['month'], m['facts']) for m in report['months']],
                         [('v1', '2026-03', 6), ('v1', '2026-04', 5), ('v2', '2026-03', 7)])
        self.assertEqual((report['malformed_records'], report['malformed_by_error']), (0, {}))

    def test_malformed_kinds_add_up_and_never_carry_a_message(self):
        class Canary(Exception):
            pass

        class RaisingZone(datetime.tzinfo):
            def utcoffset(self, dt):
                raise Canary('CANARY-MESSAGE-K5')

        good = many([(CERTAIN, 'pass', 45)], 'v1', EARLY) + many([(PROBABLE, 'pass', 45)], 'v2', LATER)
        bad = [(), 'ab', one(CERTAIN, 'pass', 'v2', '2026-04-06'),
               one(CERTAIN, 'pass', 'v2', datetime.datetime(2026, 4, 6, tzinfo=RaisingZone())),
               one(CERTAIN, 'pass', 'v2', datetime.datetime.max),
               (5, {'identity': 'pass'}, 'v2', LATER, BY, ROW_ID)]
        kinds = {'Canary': 1, 'OverflowError': 1, 'TypeError': 1, 'not_a_datetime': 1, 'too_short': 2}
        plain = coach_grade.coach_report(good + bad)
        lined = coach_grade.coach_report(good + bad, leave_out_reasons=coach_grade.INTERVIEW_FAILS)
        for report in (plain, lined):
            self.assertEqual(report['malformed_by_error'], kinds)
            self.assertEqual(list(report['malformed_by_error']), sorted(kinds))
            self.assertEqual(sum(report['malformed_by_error'].values()), report['malformed_records'])
            self.assertNotIn('CANARY', repr(report))
            json.dumps(report)
        self.assertEqual(coach_grade.coach_report(good)['malformed_by_error'], {})

    def test_a_bug_in_a_helper_is_not_swallowed(self):
        # The catch wraps only the reads of a record's own values: a helper that breaks must RAISE,
        # never turn every record into a "malformed" one.
        records = many([(CERTAIN, 'pass', 5)])
        for helper in ('_version_key', '_natural', '_plain_tally'):
            with mock.patch.object(coach_grade, helper, side_effect=TypeError('a helper bug')):
                with self.assertRaises(TypeError, msg=helper):
                    coach_grade.coach_report(records)
        self.assertEqual(coach_grade.coach_report(records)['malformed_records'], 0)

    def test_any_error_after_the_row_is_built_raises(self):
        # Only the read block is wide: an ordinary error in the tally or the grade maths is a bug.
        # Coverage 45/45 then 43/45 moves the wrong way, so the Fisher test runs; its chance (990/4005)
        # is over 1/20, so the score comparison runs too.
        records = (many([(CERTAIN, 'pass', 45)], 'v1', EARLY)
                   + many([(PROBABLE, 'pass', 43), (UNSURE, 'pass', 2)], 'v2', LATER))
        for helper in ('_plain_tally', '_new_side_tail', '_score_change', '_coach_verdict'):
            with mock.patch.object(coach_grade, helper, side_effect=RuntimeError('a helper bug')):
                with self.assertRaises(RuntimeError, msg=helper):
                    coach_grade.coach_report(records)
        self.assertEqual(len(coach_grade.coach_report(records)['coach']), 1)

    def test_odd_version_labels_never_raise(self):
        class OddText(str):
            def strip(self, *args):
                raise TypeError('odd strip')

            def __eq__(self, other):
                raise TypeError('odd eq')

            __hash__ = str.__hash__

        odd_labels = (b'v1', 7.5, float('nan'), ['v1'], {'v': 1}, ('v1',), object(), True, Fraction(1, 3))
        for label in odd_labels:
            report = coach_grade.coach_report(many([(CERTAIN, 'pass', 5)], label))
            self.assertEqual([(m['version'], m['unknown_version']) for m in report['months']],
                             [(coach_grade.UNKNOWN_VERSION, True)], repr(label))
        # a text subclass is text: str's own strip is used, and the label shown is plain text
        report = coach_grade.coach_report(many([(CERTAIN, 'pass', 5)], OddText(' v9 ')))
        self.assertEqual([(m['version'], type(m['version']), m['unknown_version']) for m in report['months']],
                         [('v9', str, False)])


class TestTheChain(SimpleTestCase):

    def test_the_chain_runs_by_first_decided_instant_not_input_place(self):
        records = (many([(PROBABLE, 'pass', 40)], 'listed-first', LATEST)
                   + many([(PROBABLE, 'pass', 40)], 'listed-second', EARLY)
                   + many([(CERTAIN, 'pass', 40)], 'listed-third', LATER))
        coach = coach_grade.coach_report(records)['coach']
        self.assertEqual([(p['previous']['version'], p['new']['version'], p['grade']) for p in coach],
                         [('listed-second', 'listed-third', 'pass'), ('listed-third', 'listed-first', 'fail')])

    def test_an_unknown_version_between_two_known_ones_neither_breaks_nor_joins_the_chain(self):
        for label in ('', None, 'pre-versioning', '(unknown version)'):
            records = (many([(PROBABLE, 'pass', 50)], 'v1', EARLY)
                       + many([(CERTAIN, 'fail', 50)], label, LATER)
                       + many([(CERTAIN, 'pass', 50)], 'v2', LATEST))
            report = coach_grade.coach_report(records)
            self.assertEqual([(p['previous']['version'], p['new']['version'], p['grade'], p['skipped_versions'])
                              for p in report['coach']], [('v1', 'v2', 'pass', 0)], label)
            self.assertEqual(report['waiting'], [], label)

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


def without_extra_lines(report):
    """A deep copy of ``report`` with every ``without_left_out`` key and ``left_out_reasons`` taken out."""
    def strip(value):
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items() if k != 'without_left_out'}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value
    out = strip(json.loads(json.dumps(report)))
    out.pop('left_out_reasons')
    return out


def lines(report):
    """Every ``without_left_out`` value in a report, in order."""
    found = []
    sides = report['waiting'] + [s for p in report['coach'] for s in (p['previous'], p['new'])]
    for item in report['months'] + sides:
        if 'without_left_out' in item:
            found.append((item['version'], item.get('month'), item['without_left_out']))
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

    def test_the_report_with_a_leave_out_is_the_plain_report_plus_lines(self):
        plain = coach_grade.coach_report(mixed_records())
        left_out = coach_grade.coach_report(mixed_records(), leave_out_reasons=('interview_differs',))
        self.assertEqual(without_extra_lines(left_out), without_extra_lines(plain))
        self.assertEqual((plain['left_out_reasons'], left_out['left_out_reasons']), ([], ['interview_differs']))
        self.assertNotIn('without_left_out', json.dumps(plain))
        self.assertEqual(lines(left_out), [
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
        left_out = coach_grade.coach_report(records, leave_out_reasons=coach_grade.INTERVIEW_FAILS)
        want = [('2026-01', False, 5, -2), ('2026-02', True, None, None), ('2026-03', False, 5, 10)]
        for report in (plain, left_out):
            self.assertEqual([(m['month'], m['too_few'], m.get('facts'), m.get('points'))
                              for m in report['months']], want)
        self.assertEqual(without_extra_lines(left_out), without_extra_lines(plain))
        self.assertEqual([m.get('without_left_out') for m in left_out['months']],
                         [{'too_few': True}, None, {'too_few': False, 'facts': 5, 'points': 10, 'best': 10,
                                                    'score_pct': 100, 'left_out': 0}])
        self.assertEqual(left_out['waiting'], [{'version': 'v1', 'too_few': False, 'facts': 12, 'score_pct': -21,
                                            'coverage': {'count': 12, 'of': 12},
                                            'generous_wrong': {'count': 2, 'of': 12},
                                            'without_left_out': {'too_few': False, 'facts': 11, 'points': 5,
                                                               'best': 22, 'score_pct': 23, 'left_out': 1}}])

    def test_reviewer_case_p2_a_middle_version_of_interview_fails_keeps_its_place(self):
        records = (many([(PROBABLE, 'pass', 50)], 'v1', at(1))
                   + many([(CERTAIN, 'fail', 3, 'interview_differs')], 'v1.1', at(2))
                   + many([(CERTAIN, 'pass', 50)], 'v2', at(3)))
        for leave_out in ((), coach_grade.INTERVIEW_FAILS):
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


class TestTheExtraLine(SimpleTestCase):
    """``without_left_out``: the same figures with the left-out Fails taken out, to see the score both
    ways. The grade and the guards always count every Fail."""

    def records(self):
        return many([(CERTAIN, 'pass', 5), (CERTAIN, 'fail', 1, 'interview_differs'),
                     (CERTAIN, 'fail', 1, 'proof_missing')])

    def test_the_default_is_the_plain_score(self):
        records = self.records() + many([(PROBABLE, 'pass', 40)], 'v2', LATER)
        self.assertEqual(coach_grade.coach_report(records), coach_grade.coach_report(records, ()))
        cell = coach_grade.coach_report(records)['months'][0]
        self.assertEqual((cell['facts'], cell['points'], cell['best']), (7, -10, 14))
        self.assertNotIn('left_out', cell)
        self.assertNotIn('without_left_out', cell)

    def test_an_interview_fail_is_left_out_of_points_and_best_in_its_line(self):
        cell = coach_grade.coach_report(self.records(), leave_out_reasons=coach_grade.INTERVIEW_FAILS)['months'][0]
        self.assertEqual((cell['facts'], cell['points'], cell['best'], cell['score_pct']), (7, -10, 14, -71))
        self.assertEqual(cell['outcomes']['wrong_sure'], 2)   # the plain cell keeps both Fails
        # the proof_missing Fail still costs in the line; the interview Fail does not
        self.assertEqual(cell['without_left_out'], {'too_few': False, 'facts': 6, 'points': 0, 'best': 12,
                                                  'score_pct': 0, 'left_out': 1})

    def test_interview_fails_count_in_the_grade_and_each_side_gains_its_line(self):
        # R2: the AI also asks the student questions (Check 2), so an interview Fail is a Fail like any
        # other in the grade and both guards. Generous-wrong 0 of 40 against 5 of 45: the chance is
        # C(45,5)/C(85,5) = 1221759/32801517, about 0.037, below 1 in 20: broken.
        old = [(PROBABLE, 'pass', 40)]
        new = [(CERTAIN, 'pass', 40), (CERTAIN, 'fail', 5, 'interview_differs')]
        records = many(old, 'old', EARLY) + many(new, 'next', LATER)
        plain = coach_grade.coach_report(records)['coach'][0]
        self.assertEqual((plain['grade'], plain['reasons']), ('fail', ['generous_wrong_rose']))
        left_out = coach_grade.coach_report(records, leave_out_reasons=coach_grade.INTERVIEW_FAILS)
        pair = left_out['coach'][0]
        self.assertEqual((pair['grade'], pair['reasons'], pair['new']['facts'], pair['new']['generous_wrong']),
                         ('fail', ['generous_wrong_rose'], 45, {'count': 5, 'of': 45}))
        # the line shows the score both ways: without the five interview Fails it is 80/80
        self.assertEqual(pair['new']['without_left_out'], {'too_few': False, 'facts': 40, 'points': 80, 'best': 80,
                                                         'score_pct': 100, 'left_out': 5})
        self.assertEqual(pair['previous']['without_left_out'], {'too_few': False, 'facts': 40, 'points': 40,
                                                              'best': 80, 'score_pct': 50, 'left_out': 0})

    def test_a_side_under_five_left_shows_a_too_few_line(self):
        records = many([(CERTAIN, 'pass', 3), (CERTAIN, 'fail', 3, 'interview_differs')], 'v1', EARLY)
        left_out = coach_grade.coach_report(records, leave_out_reasons=coach_grade.INTERVIEW_FAILS)
        self.assertEqual(left_out['waiting'], [{'version': 'v1', 'too_few': False, 'facts': 6, 'score_pct': -200,
                                            'coverage': {'count': 6, 'of': 6},
                                            'generous_wrong': {'count': 3, 'of': 6},
                                            'without_left_out': {'too_few': True}}])

    def test_a_left_out_candidate_with_no_band_stays_not_scored(self):
        no_band = ([], {'identity': 'fail', 'fail_reasons': {'identity': 'interview_differs'}}, 'v1', EARLY, BY,
                   ROW_ID)
        records = many([(CERTAIN, 'pass', 6)]) + [no_band]
        cell = coach_grade.coach_report(records, leave_out_reasons=coach_grade.INTERVIEW_FAILS)['months'][0]
        self.assertEqual((cell['facts'], cell['not_scored']), (6, 1))
        self.assertEqual(cell['without_left_out'], {'too_few': False, 'facts': 6, 'points': 12, 'best': 12,
                                                  'score_pct': 100, 'left_out': 0})

    def test_an_unknown_code_is_refused(self):
        with self.assertRaises(ValueError):
            coach_grade.coach_report(self.records(), leave_out_reasons=('not_a_code',))
        with self.assertRaises(ValueError):   # a bare string is not a set of codes
            coach_grade.coach_report(self.records(), leave_out_reasons='interview_differs')
        for bad in (5, [['interview_differs']], [5], [None], b'interview_differs', object()):
            with self.assertRaises(ValueError, msg=repr(bad)):
                coach_grade.coach_report(self.records(), leave_out_reasons=bad)
        # None and an empty set are the plain report
        self.assertEqual(coach_grade.coach_report(self.records(), leave_out_reasons=None),
                         coach_grade.coach_report(self.records()))

    def test_a_record_with_all_four_facts_loses_only_the_interview_fail(self):
        verdict = {f: 'pass' for f in FACTS}
        verdict.update(identity='fail', income='fail',
                       fail_reasons={'identity': 'interview_differs', 'income': 'documents_differ'})
        snapshot = [band_fact(f, CERTAIN) for f in FACTS]
        records = [(snapshot, verdict, 'v1', EARLY, BY, ROW_ID)] * 2
        plain = coach_grade.coach_report(records)['months'][0]
        left_out = coach_grade.coach_report(records, leave_out_reasons=coach_grade.INTERVIEW_FAILS)['months'][0]
        self.assertEqual((plain['facts'], plain['points'], plain['best']), (8, -32, 16))
        self.assertEqual((left_out['facts'], left_out['points'], left_out['best']), (8, -32, 16))
        self.assertEqual(left_out['without_left_out'], {'too_few': False, 'facts': 6, 'points': -12, 'best': 12,
                                                  'score_pct': -100, 'left_out': 2})
        self.assertEqual(verdict['identity'], 'fail')   # the caller's record is not changed


#: One fixed AI's answers, (band, reviewer, weight out of 100): mostly Certain and right, some Unsure,
#: and rare Certain Fails so that the -10 tail is present.
NULL_BEHAVIOUR = ((CERTAIN, 'pass', 70), (CERTAIN, 'fail', 3), (PROBABLE, 'pass', 10), (PROBABLE, 'fail', 2),
                  (UNSURE, 'pass', 8), (UNSURE, 'fail', 3), (UNVERIFIABLE, 'pass', 2), (UNVERIFIABLE, 'fail', 2))
NULL_SEED = 20261124
NULL_TRIALS = 300


class TestAnUnchangedAiIsRarelyGraded(SimpleTestCase):

    def test_both_sides_drawn_from_the_same_ai(self):
        """The reviewer's finding: zero tolerance graded an UNCHANGED AI ``fail`` about 3 times in 4.
        With the margin, an unchanged AI is graded ``fail`` under 15 in 100 and ``pass`` under 10 in 100
        at 40, 100 and 400 facts a side."""
        population = [(band, says) for band, says, weight in NULL_BEHAVIOUR for _ in range(weight)]
        rng = random.Random(NULL_SEED)

        def draw(version, when, n):
            return [one(*rng.choice(population), version=version, when=when) for _ in range(n)]

        for n in (40, 100, 400):
            grades = {'pass': 0, 'fail': 0, 'no_change': 0}
            for _ in range(NULL_TRIALS):
                pair = coach_grade.coach_report(draw('old', EARLY, n) + draw('next', LATER, n))['coach'][0]
                grades[pair['grade']] += 1
            self.assertLess(grades['fail'] * 100, 15 * NULL_TRIALS, (n, grades))
            self.assertLess(grades['pass'] * 100, 10 * NULL_TRIALS, (n, grades))
