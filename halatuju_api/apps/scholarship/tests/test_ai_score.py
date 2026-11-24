"""F4 — the AI score in marks (`ai_score`, pure): the 10-cell table, the 5 outcomes, the percent, the
top-2 reasons, "not scored" rows and the per-version split."""
from django.test import SimpleTestCase

from apps.scholarship import ai_score
from apps.scholarship.audit import FACTS
from apps.scholarship.fact_bands import (
    CERTAIN, PROBABLE, RULE_NOT_MET, UNSURE, UNVERIFIABLE, fact_band,
)

DISQUALIFIER = 'pathway_offer_private'


def fact(name, band):
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
            'unresolved': [{'code': DISQUALIFIER, 'params': {}}]}


def snap(**bands):
    return [fact(f, bands.get(f, CERTAIN)) for f in FACTS]


def officer(reasons=None, **kw):
    v = {f: 'pass' for f in FACTS}
    v.update(kw)
    if reasons:
        v['fail_reasons'] = reasons
    return v


class TestTheTable(SimpleTestCase):

    def test_the_fixture_bands_are_what_the_case_page_shows(self):
        for band in (CERTAIN, PROBABLE, UNSURE, UNVERIFIABLE, RULE_NOT_MET):
            self.assertEqual(fact_band(fact('pathway', band)), band)

    def test_the_ten_cells(self):
        expected = {
            (CERTAIN, 'pass'): (2, 'right_sure'), (CERTAIN, 'fail'): (-10, 'wrong_sure'),
            (PROBABLE, 'pass'): (1, 'right_leaning'), (PROBABLE, 'fail'): (-3, 'wrong_leaning'),
            (UNSURE, 'pass'): (0, 'unsure'), (UNSURE, 'fail'): (0, 'unsure'),
            (UNVERIFIABLE, 'pass'): (-1, 'wrong_leaning'), (UNVERIFIABLE, 'fail'): (1, 'right_leaning'),
            (RULE_NOT_MET, 'pass'): (-10, 'wrong_sure'), (RULE_NOT_MET, 'fail'): (2, 'right_sure'),
        }
        self.assertEqual(set(ai_score.POINTS), set(expected))
        for cell, want in expected.items():
            self.assertEqual(ai_score.mark(*cell), want, cell)

    def test_the_five_outcomes_group_the_ten_cells(self):
        groups = {}
        for cell, outcome in ai_score.OUTCOME.items():
            groups.setdefault(outcome, set()).add(cell)
        self.assertEqual(tuple(sorted(groups, key=ai_score.OUTCOMES.index)), ai_score.OUTCOMES)
        self.assertEqual(groups['right_sure'], {(CERTAIN, 'pass'), (RULE_NOT_MET, 'fail')})
        self.assertEqual(groups['wrong_sure'], {(CERTAIN, 'fail'), (RULE_NOT_MET, 'pass')})
        self.assertEqual(groups['wrong_leaning'], {(PROBABLE, 'fail'), (UNVERIFIABLE, 'pass')})


class TestThePercent(SimpleTestCase):

    def test_points_over_best_rounded_half_away_from_zero(self):
        self.assertEqual(ai_score.percent(736, 1550), 47)
        self.assertEqual(ai_score.percent(1, 8), 13)       # 12.5 -> 13
        self.assertEqual(ai_score.percent(-1, 8), -13)     # it can go below 0%
        self.assertEqual(ai_score.percent(0, 4), 0)
        self.assertIsNone(ai_score.percent(0, 0))

    def test_unsure_facts_count_in_best(self):
        m = ai_score.score_marks([(snap(identity=UNSURE, academic=UNSURE, pathway=UNSURE, income=UNSURE),
                             officer(), 'v1')])
        self.assertEqual((m['facts'], m['points'], m['best'], m['score_pct']), (4, 0, 8, 0))
        self.assertEqual(m['unsure'], 4)

    def test_all_sure_and_right_is_100(self):
        m = ai_score.score_marks([(snap(), officer(), 'v1')])
        self.assertEqual((m['points'], m['best'], m['score_pct'], m['lost']), (8, 8, 100, 0))
        self.assertIsNone(m['most_lost'])

    def test_a_score_below_zero(self):
        m = ai_score.score_marks([(snap(), officer(identity='fail', academic='fail'), 'v1')])
        self.assertEqual((m['points'], m['best'], m['score_pct'], m['lost']), (-16, 8, -200, -20))


class TestByFactAndReasons(SimpleTestCase):

    def test_by_fact_counts_points_and_lost(self):
        records = [
            (snap(pathway=RULE_NOT_MET), officer(), 'v1'),                                   # -10
            (snap(pathway=RULE_NOT_MET), officer(pathway='fail'), 'v1'),                     # +2
            (snap(pathway=UNVERIFIABLE), officer(), 'v1'),                                   # -1
            (snap(), officer(pathway='fail', reasons={'pathway': 'proof_missing'}), 'v1'),   # -10
        ]
        m = ai_score.score_marks(records)
        p = m['by_fact']['pathway']
        self.assertEqual((p['facts'], p['points'], p['best'], p['lost']), (4, -19, 8, -21))
        self.assertEqual(p['score_pct'], -238)
        self.assertEqual((p['right_sure'], p['right_leaning'], p['unsure'], p['wrong_leaning'], p['wrong_sure']),
                         (1, 0, 0, 1, 2))
        # the top two reasons, most points lost first; ties by key
        self.assertEqual(p['top_reasons'], [{'key': 'fail:proof_missing', 'points': -10},
                                            {'key': 'pass:ruleNotMet', 'points': -10}])
        self.assertEqual(m['most_lost'], {'fact': 'pathway', 'points': -21})

    def test_a_fail_with_no_reason_is_not_given_and_a_pass_reason_is_what_the_ai_said(self):
        m = ai_score.score_marks([(snap(income=PROBABLE), officer(income='fail'), 'v1'),
                            (snap(income=UNVERIFIABLE), officer(), 'v1')])
        self.assertEqual(m['by_fact']['income']['top_reasons'],
                         [{'key': 'fail:not_given', 'points': -3}, {'key': 'pass:unverifiable', 'points': -1}])

    def test_only_two_reasons_are_kept(self):
        records = [(snap(), officer(identity='fail', reasons={'identity': c}), 'v1')
                   for c in ('proof_missing', 'proof_missing', 'document_false', 'other')]
        reasons = ai_score.score_marks(records)['by_fact']['identity']['top_reasons']
        self.assertEqual(reasons, [{'key': 'fail:proof_missing', 'points': -20},
                                   {'key': 'fail:document_false', 'points': -10}])


class TestWhatIsNotScored(SimpleTestCase):

    def test_undecided_facts_are_skipped(self):
        m = ai_score.score_marks([(snap(), {'identity': 'pass', 'academic': ''}, 'v1')])
        self.assertEqual(m['facts'], 1)
        self.assertEqual(m['not_scored'], 0)

    def test_a_decided_fact_without_a_snapshot_band_is_not_scored(self):
        m = ai_score.score_marks([([], officer(), ''), (None, officer(identity='fail'), '')])
        self.assertEqual((m['facts'], m['not_scored'], m['best']), (0, 8, 0))
        self.assertIsNone(m['score_pct'])

    def test_a_malformed_snapshot_item_never_raises(self):
        m = ai_score.score_marks([([{'fact': ['x']}, 'odd', fact('income', CERTAIN)], officer(), 'v1')])
        self.assertEqual((m['facts'], m['not_scored']), (1, 3))

    def test_the_public_reader_and_score_marks_agree_on_malformed_input(self):
        junk = {'identity': 'fail', 'academic': 'PASS', 'pathway': 'pass', 'income': 'pass',
                'fail_reasons': 'junk'}
        snapshot = [None, 'x', {'fact': 3}, {'fact': ['x']}, fact('identity', CERTAIN), fact('income', UNSURE)]
        records = [(snapshot, junk, 'v1'),
                   ([fact('income', CERTAIN)], 'not a dict', 'v1'),
                   (None, {'identity': 'pass'}, 'v1')]
        read = [ai_score.decided_facts(r[0], r[1]) for r in records]
        self.assertEqual(read, [[('identity', CERTAIN, 'fail'), ('pathway', None, 'pass'),
                                 ('income', UNSURE, 'pass')],
                                [], [('identity', None, 'pass')]])
        m = ai_score.score_marks(records)
        self.assertEqual((m['facts'], m['points'], m['best'], m['score_pct'], m['not_scored']),
                         (2, -10, 4, -250, 2))
        self.assertEqual((m['wrong_sure'], m['unsure']), (1, 1))
        self.assertEqual(m['by_fact']['identity']['top_reasons'], [{'key': 'fail:not_given', 'points': -10}])


class TestByVersion(SimpleTestCase):

    def test_split_and_sorted_by_version(self):
        m = ai_score.score_marks([(snap(), officer(), 'v2'), (snap(), officer(identity='fail'), 'v1'),
                            (snap(), officer(), '')])
        self.assertEqual([(v['version'], v['facts'], v['points'], v['best'], v['score_pct'])
                          for v in m['by_version']],
                         [('', 4, 8, 8, 100), ('v1', 4, -4, 8, -50), ('v2', 4, 8, 8, 100)])
