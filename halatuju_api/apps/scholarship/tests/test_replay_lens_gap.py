"""LL7 - the gap table in the human lens's result (`eval/replay/lens_gap.py`), its allow-list check
(`lens_result_schema`) and its report lines (`report_lens`). Made-up data only; every exam folder is a
pytest temp folder outside the repository."""
import copy
import json

import pytest

from apps.scholarship import ai_score, coach_grade
from apps.scholarship.eval.replay import lens_gap as G
from apps.scholarship.eval.replay import lens_human as L
from apps.scholarship.eval.replay import lens_result_schema as S
from apps.scholarship.eval.replay import lens_score
from apps.scholarship.eval.replay import report_lens as R
from apps.scholarship.fact_bands import BANDS
from apps.scholarship.tests.test_replay_lens_human import case, exold, run, snap
from apps.scholarship.tests.test_replay_lens_result_schema import VERSION
from apps.scholarship.tests.test_verdict_item_i18n import _scan

PLANT = 'Siti Aminah binti Ahmad'
CANARY = 987654000
#: The four codes of the engine's two variable ``_item`` call sites (verdict_academic, verdict_income_salary).
DYNAMIC_CODES = {'academic_grade_band_mismatch', 'academic_grade_mismatch',
                 'income_declared_accepted_str', 'income_declared_accepted_evidenced'}


def old(aid, verdict, snapshot, programme=None):
    """An exam-old case (empty stored context) with a made-up id far from any real one, and an engine
    version in the shape the allow-list takes."""
    return case(CANARY + aid, ctx={}, verdict=verdict, snapshot=snapshot, programme=programme, version=VERSION)


def mixed_cases():
    """65 marked facts in exam-old: six groups of 10 or more, one group of 1, two doubt-code cases."""
    out, aid = [], 0

    def add(n, verdict, snapshot, programme=None):
        nonlocal aid
        for _ in range(n):
            aid += 1
            out.append(old(aid, verdict, snapshot, programme))
    add(10, {'identity': 'fail'}, snap(identity='certain'), 7)
    add(11, {'identity': 'pass'}, snap(identity='ruleNotMet'), 3)
    add(10, {'identity': 'fail'}, snap(identity='probable'))
    add(10, {'identity': 'pass'}, snap(identity='unverifiable'), 3)
    add(10, {'identity': 'fail'}, snap(identity='unverifiable'))
    add(12, {'identity': 'pass'}, snap(identity='certain'), 7)
    # an Unsure academic Fail whose doubt codes are not in the closed list (a name and a number)
    add(1, {'academic': 'fail'}, [{'fact': 'academic', 'status': 'recommend',
                                   'unresolved': [{'code': PLANT}, {'code': 5}]}])
    # an Unverifiable income Pass that lists one code twice, and a fact the reviewer marked with no AI entry
    add(1, {'income': 'pass', 'pathway': 'pass'},
        [{'fact': 'income', 'status': 'gap', 'unresolved': [{'code': 'household_size_confirm'}] * 2}], 3)
    return out


@pytest.fixture
def mixed(tmp_path):
    return run(mixed_cases(), tmp_path)


def _cells(gap):
    return [(band, answer, cell) for band, row in gap['groups'].items() for answer, cell in row.items()]


# ── the invariant ─────────────────────────────────────────────────────────────────────────────────────
def test_the_lost_points_add_up_to_twice_the_facts_less_the_score(mixed):
    e = exold(mixed)
    gap, score = e['gap'], e['score']
    assert (score['facts'], score['points'], score['not_scored']) == (65, -217, 1)
    cells = _cells(gap)
    assert sum(c['facts'] for _b, _a, c in cells) == score['facts']
    assert sum(c['points'] for _b, _a, c in cells) == score['points']
    assert sum(c['lost'] for _b, _a, c in cells) == 2 * score['facts'] - score['points'] == 347
    assert G.gap_sums_hold(gap, score['facts'], score['points'])
    assert not G.gap_sums_hold(gap, score['facts'], score['points'] + 1)


def test_each_group_takes_its_points_from_the_house_table():
    for band in BANDS:
        for answer in G.ANSWERS:
            cell = G.gap_cell(band, answer, 4)
            assert cell['points'] == 4 * ai_score.POINTS[(band, answer)]
            assert cell['lost'] == ai_score.BEST_PER_FACT * 4 - cell['points'] >= 0
    assert set(G.ANSWERS) == {answer for _band, answer in ai_score.POINTS}


def test_a_gap_that_does_not_match_the_score_stops_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr(G, 'gap_sums_hold', lambda *_a: False)
    with pytest.raises(ValueError, match='do not add up'):
        run(mixed_cases(), tmp_path)
    with pytest.raises(ValueError, match='one programme per case'):
        G.gap_block([([], {}, 'v')], [])
    rows = [{'snapshot': snap(identity='certain'), 'answer': {'identity': 'pass'}, 'version': 'v', 'programme': None}]
    with pytest.raises(ValueError):
        lens_score.exam_score(rows)


# ── each table ────────────────────────────────────────────────────────────────────────────────────────
def test_the_groups_table(mixed):
    groups = exold(mixed)['gap']['groups']
    assert set(groups) == set(BANDS) and all(set(row) == set(G.ANSWERS) for row in groups.values())
    want = {('certain', 'pass'): (12, 24, 0, False), ('certain', 'fail'): (10, -100, 120, False),
            ('probable', 'pass'): (0, 0, 0, True), ('probable', 'fail'): (10, -30, 50, False),
            ('unsure', 'pass'): (0, 0, 0, True), ('unsure', 'fail'): (1, 0, 2, True),
            ('unverifiable', 'pass'): (11, -11, 33, False), ('unverifiable', 'fail'): (10, 10, 10, False),
            ('ruleNotMet', 'pass'): (11, -110, 132, False), ('ruleNotMet', 'fail'): (0, 0, 0, True)}
    got = {(b, a): (c['facts'], c['points'], c['lost'], c['too_small']) for b, a, c in _cells(exold(mixed)['gap'])}
    assert got == want


def _nonzero(table):
    return {(band, answer): n for band, row in table.items() for answer, n in row.items() if n}


def test_the_by_fact_table(mixed):
    by_fact = exold(mixed)['gap']['by_fact']
    assert set(by_fact) == set(ai_score.FACTS)
    assert _nonzero(by_fact['identity']) == {('certain', 'pass'): 12, ('certain', 'fail'): 10, ('probable', 'fail'): 10,
                                             ('unverifiable', 'pass'): 10, ('unverifiable', 'fail'): 10,
                                             ('ruleNotMet', 'pass'): 11}
    assert _nonzero(by_fact['academic']) == {('unsure', 'fail'): 1}
    assert _nonzero(by_fact['income']) == {('unverifiable', 'pass'): 1}
    assert _nonzero(by_fact['pathway']) == {}            # marked, but no AI entry: not scored, not in the gap


def test_the_by_doubt_code_table_counts_each_listing_on_facts_not_certain(mixed):
    doubt = exold(mixed)['gap']['by_doubt_code']
    assert doubt == {'identity': {'income_above_b40_line': {'passed': 11, 'failed': 0}},
                     'academic': {G.OTHER_DOUBT_CODE: {'passed': 0, 'failed': 2}},
                     'pathway': {},
                     'income': {'household_size_confirm': {'passed': 2, 'failed': 0}}}


def test_a_certain_fact_adds_no_doubt_code(tmp_path):
    verified = [{'fact': 'identity', 'status': 'verified', 'unresolved': [{'code': 'name_match'}]}]
    e = exold(run([old(1, {'identity': 'fail'}, verified)], tmp_path))
    assert e['gap']['groups']['certain']['fail']['facts'] == 1
    assert e['gap']['by_doubt_code']['identity'] == {}


def test_the_by_programme_table(mixed):
    by_programme = exold(mixed)['gap']['by_programme']
    assert {k: _nonzero(t) for k, t in by_programme.items()} == {
        '7': {('certain', 'pass'): 12, ('certain', 'fail'): 10},
        '3': {('unverifiable', 'pass'): 11, ('ruleNotMet', 'pass'): 11},
        G.NO_PROGRAMME: {('probable', 'fail'): 10, ('unsure', 'fail'): 1, ('unverifiable', 'fail'): 10}}


def test_the_top_table_ranks_by_lost_and_keeps_three(mixed):
    assert exold(mixed)['gap']['top'] == [
        {'band': 'ruleNotMet', 'answer': 'pass', 'facts': 11, 'lost': 132},
        {'band': 'certain', 'answer': 'fail', 'facts': 10, 'lost': 120},
        {'band': 'probable', 'answer': 'fail', 'facts': 10, 'lost': 50}]
    assert G.TOP_GROUPS == 3


def test_a_tie_in_lost_keeps_band_order(tmp_path):
    cases = [old(i, {'identity': 'pass'}, snap(identity='ruleNotMet')) for i in range(1, 11)]
    cases += [old(i, {'identity': 'fail'}, snap(identity='certain')) for i in range(11, 21)]
    top = exold(run(cases, tmp_path))['gap']['top']
    assert [(t['band'], t['answer'], t['lost']) for t in top] == [('certain', 'fail', 120), ('ruleNotMet', 'pass', 120)]


# ── the under-10 rule ─────────────────────────────────────────────────────────────────────────────────
def test_a_group_under_ten_facts_is_shown_but_never_ranked(tmp_path):
    assert G.GAP_MIN_FACTS == 10
    nine = tmp_path / 'nine'
    nine.mkdir()
    e = exold(run([old(i, {'identity': 'fail'}, snap(identity='certain')) for i in range(1, 10)], nine))
    cell = e['gap']['groups']['certain']['fail']
    assert (cell['facts'], cell['lost'], cell['too_small']) == (9, 108, True) and e['gap']['top'] == []
    ten = tmp_path / 'ten'
    ten.mkdir()
    e = exold(run([old(i, {'identity': 'fail'}, snap(identity='certain')) for i in range(1, 11)], ten))
    assert e['gap']['groups']['certain']['fail']['too_small'] is False
    assert e['gap']['top'] == [{'band': 'certain', 'answer': 'fail', 'facts': 10, 'lost': 120}]


def test_a_group_that_lost_nothing_is_never_ranked(tmp_path):
    e = exold(run([old(i, {'identity': 'pass'}, snap(identity='certain')) for i in range(1, 21)], tmp_path))
    assert e['gap']['groups']['certain']['pass'] == {'facts': 20, 'points': 40, 'lost': 0, 'too_small': False}
    assert e['gap']['top'] == []


# ── an empty exam and a one-fact exam ─────────────────────────────────────────────────────────────────
def test_an_empty_exam_has_a_gap_of_zeros(tmp_path):
    run([old(i, {'identity': 'pass'}, snap(identity='certain')) for i in range(1, 4)], tmp_path)
    out = run([], tmp_path, freeze=False)
    e = exold(out)
    assert e['frozen'] is True and e['validity']['valid'] == 0 and e['score']['facts'] == 0
    gap = e['gap']
    assert all(c == G.gap_cell(b, a, 0) for b, a, c in _cells(gap)) and gap['top'] == []
    assert gap['by_programme'] == {} and all(v == {} for v in gap['by_doubt_code'].values())
    assert all(not _nonzero(t) for t in gap['by_fact'].values())
    assert S.human_lens_result_allowed(out)
    lines = R._gap_lines(gap)
    assert '- Largest gaps: none ranked (each group is too small or lost nothing).' in lines
    assert '- Gap by programme: none.' in lines and '- Gap by fact, Identity: none.' in lines


def test_a_one_fact_exam(tmp_path):
    out = run([old(1, {'identity': 'pass'}, snap(identity='certain'), 2)], tmp_path)
    gap = exold(out)['gap']
    assert gap['groups']['certain']['pass'] == {'facts': 1, 'points': 2, 'lost': 0, 'too_small': True}
    assert sum(c['facts'] for _b, _a, c in _cells(gap)) == 1 and gap['top'] == []
    assert {k: _nonzero(t) for k, t in gap['by_programme'].items()} == {'2': {('certain', 'pass'): 1}}
    assert exold(out)['score']['too_few'] is True and S.human_lens_result_allowed(out)


# ── the closed code list and the unknown-code rule ────────────────────────────────────────────────────
def test_the_closed_list_is_every_code_the_engine_writes():
    literals, dynamic = _scan()
    assert len(dynamic) == 2                       # the two variable call sites; their codes are listed here
    assert G.DOUBT_CODES == literals | DYNAMIC_CODES
    assert G.OTHER_DOUBT_CODE not in G.DOUBT_CODES


def test_an_unknown_or_non_text_code_counts_under_the_one_other_key(mixed):
    assert G._gap_code(PLANT) == G._gap_code(5) == G._gap_code(None) == G.OTHER_DOUBT_CODE
    assert G._gap_code('nric_match') == 'nric_match'
    text = json.dumps(mixed)
    assert PLANT not in text and 'Siti' not in text


def test_an_unreadable_unresolved_list_is_left_out_of_the_doubt_codes_only(tmp_path):
    odd = [{'fact': 'identity', 'status': 'gap', 'unresolved': 'income_above_b40_line'}]
    e = exold(run([old(1, {'identity': 'pass'}, odd)], tmp_path))
    assert e['gap']['groups']['unverifiable']['pass']['facts'] == 1
    assert e['gap']['by_doubt_code']['identity'] == {}


# ── the allow-list refuses a bad gap ──────────────────────────────────────────────────────────────────
GAP = ('exams', L.EXAM_OLD, 'gap')


def _gap_planted(result, path, value):
    out = copy.deepcopy(result)
    target = out
    for key in path[:-1]:
        target = target[key]
    if value is ...:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return out


def _rename_programme(result, new_key):
    out = copy.deepcopy(result)
    table = out['exams'][L.EXAM_OLD]['gap']['by_programme']
    table[new_key] = table.pop('7')
    return out


@pytest.mark.parametrize('path, value', [
    ((*GAP, 'by_doubt_code', 'identity', PLANT), {'passed': 1, 'failed': 0}),
    ((*GAP, 'by_doubt_code', 'identity', 'income_above_b40_line'), {'passed': 0, 'failed': 0}),
    ((*GAP, 'by_doubt_code', 'identity', 'income_above_b40_line', 'passed'), PLANT),
    ((*GAP, 'by_doubt_code', 'identity', 'income_above_b40_line', 'note'), 1),
    ((*GAP, 'by_doubt_code', 'pathway', 'nric_match'), {'passed': -1, 'failed': 2}),
    ((*GAP, 'groups', 'certain', 'fail', 'lost'), 0),
    ((*GAP, 'groups', 'certain', 'fail', 'too_small'), 0),
    ((*GAP, 'groups', 'certain', 'pass', 'facts'), 13),
    ((*GAP, 'by_fact', 'identity', 'certain', 'pass'), 11),
    ((*GAP, 'by_programme', '3', 'ruleNotMet', 'pass'), PLANT),
    ((*GAP, 'top'), []), ((*GAP, 'top', 0, 'note'), PLANT), ((*GAP, 'note'), 1),
    (GAP, ...), (GAP, None),
])
def test_a_bad_gap_gives_the_schema_error_and_nothing_of_it(mixed, path, value):
    planted = _gap_planted(mixed, path, value)
    assert not S.human_lens_result_allowed(planted)
    assert S.checked_result_text(planted) == S.SCHEMA_TEXT
    assert S.human_lens_result_allowed(mixed)


@pytest.mark.parametrize('key', [PLANT, '07', '0', ' 7', '7a', '1' * 20, 'NONE'])
def test_a_programme_key_that_is_not_digits_or_none_is_refused(mixed, key):
    assert not S.human_lens_result_allowed(_rename_programme(mixed, key))
    assert S.human_lens_result_allowed(_rename_programme(mixed, '12'))


def test_more_programmes_than_the_cap_are_refused(tmp_path):
    cases = [old(i, {'identity': 'pass'}, snap(identity='certain'), i) for i in range(1, G.GAP_MAX_PROGRAMMES + 2)]
    over, at_cap = tmp_path / 'over', tmp_path / 'at_cap'
    over.mkdir()
    at_cap.mkdir()
    out = run(cases, over)
    assert len(exold(out)['gap']['by_programme']) == G.GAP_MAX_PROGRAMMES + 1
    assert not S.human_lens_result_allowed(out)
    assert S.human_lens_result_allowed(run(cases[:-1], at_cap))


@pytest.mark.parametrize('value', [0, -3, True, '3', 2.0])
def test_a_wrong_programme_id_raises_naming_the_field(tmp_path, value):
    with pytest.raises(L.BadCaseRow) as err:
        run([dict(case(1, ctx={}), programme_id=value)], tmp_path)
    assert err.value.field == 'programme_id'


# ── the report lines ──────────────────────────────────────────────────────────────────────────────────
def _gap_report_text(lens):
    return '\n'.join(R.lens_coach_section_lines(lens, coach_grade.coach_report([])))


def test_the_report_prints_the_gap_once_per_sat_exam_counts_only(mixed):
    text = _gap_report_text(mixed)
    assert text.count('- Gap: points lost against a perfect AI') == 1   # exam-1 has not sat
    want = [
        '',
        '- Gap: points lost against a perfect AI (lost = 2 x facts - points). A group under 10 facts is too '
        'small and is not ranked.',
        '- Largest gaps: 1. Rule not met, Pass: 132 lost on 11 facts; 2. Certain, Fail: 120 lost on 10 facts; '
        '3. Probable, Fail: 50 lost on 10 facts.',
        '',
        '| Band | Answer | Facts | Points | Lost | Too small |', '|---|---|---|---|---|---|',
        '| Certain | Pass | 12 | 24 | 0 | no |', '| Certain | Fail | 10 | -100 | 120 | no |',
        '| Probable | Pass | 0 | 0 | 0 | yes |', '| Probable | Fail | 10 | -30 | 50 | no |',
        '| Unsure | Pass | 0 | 0 | 0 | yes |', '| Unsure | Fail | 1 | 0 | 2 | yes |',
        '| Unverifiable | Pass | 11 | -11 | 33 | no |', '| Unverifiable | Fail | 10 | 10 | 10 | no |',
        '| Rule not met | Pass | 11 | -110 | 132 | no |', '| Rule not met | Fail | 0 | 0 | 0 | yes |',
        '',
        '- Gap by fact, Identity: Certain Pass 12, Certain Fail 10, Probable Fail 10, Unverifiable Pass 10, '
        'Unverifiable Fail 10, Rule not met Pass 11.',
        '- Gap by fact, Academic: Unsure Fail 1.',
        '- Gap by fact, Pathway: none.',
        '- Gap by fact, Income: Unverifiable Pass 1.',
        '- Doubt codes, Identity (facts not Certain): income_above_b40_line 11 passed, 0 failed.',
        '- Doubt codes, Academic (facts not Certain): unlisted kind 0 passed, 2 failed.',
        '- Doubt codes, Pathway (facts not Certain): none.',
        '- Doubt codes, Income (facts not Certain): household_size_confirm 2 passed, 0 failed.',
        '- Gap by programme, 3: Unverifiable Pass 11, Rule not met Pass 11.',
        '- Gap by programme, 7: Certain Pass 12, Certain Fail 10.',
        '- Gap by programme, no programme: Probable Fail 10, Unsure Fail 1, Unverifiable Fail 10.',
    ]
    assert R._gap_lines(exold(mixed)['gap']) == want
    lines = text.splitlines()
    share = next(i for i, line in enumerate(lines) if line.startswith('- Share of "other" among the Fails'))
    assert lines[share + 1:share + 1 + len(want)] == want
    assert PLANT not in text and str(CANARY)[:5] not in text


def test_an_unlisted_code_that_reached_the_report_prints_as_fixed_words():
    assert R._doubt_code_words(PLANT) == R._doubt_code_words(G.OTHER_DOUBT_CODE) == R.OTHER_WORDS
    assert R._doubt_code_words(5) == R.OTHER_WORDS and R._doubt_code_words('nric_match') == 'nric_match'


def test_every_old_line_is_unchanged(mixed, tmp_path, monkeypatch):
    new = _gap_report_text(mixed).splitlines()
    gap_lines = R._gap_lines(exold(mixed)['gap'])
    monkeypatch.setattr(R, '_gap_lines', lambda _gap: [])
    old_lines = _gap_report_text(mixed).splitlines()
    start = next(i for i in range(len(new)) if new[i:i + len(gap_lines)] == gap_lines)
    assert new[:start] + new[start + len(gap_lines):] == old_lines


def test_the_label_tables_are_pinned():
    assert tuple(R.ANSWER_WORDS) == G.ANSWERS and tuple(R.FACT_WORDS) == ai_score.FACTS
