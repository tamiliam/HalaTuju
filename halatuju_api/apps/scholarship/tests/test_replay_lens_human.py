"""LL5 phase B2a - the replay's human lens (`eval/replay/lens_human.py`). Synthetic data only: no
database, no production fixture. Every exam folder is a fresh temp folder outside any git repository."""
import ast
import datetime
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from unittest import mock

import pytest
from django.test import override_settings

from apps.scholarship.coach_grade import CELL_MIN_FACTS
from apps.scholarship.eval.replay import lens_human as L

UTC = datetime.timezone.utc
T0 = datetime.datetime(2026, 11, 1, tzinfo=UTC)
NOW = datetime.datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
KC = 'abcd1234'
LENS_FILE = L.__file__
BAND_FACT = {
    'certain': {'status': 'verified'},
    'probable': {'status': 'review', 'evidence': [{'code': 'ic_read'}]},
    'unsure': {'status': 'recommend'},
    'unverifiable': {'status': 'gap'},
    'ruleNotMet': {'status': 'review', 'unresolved': [{'code': 'income_above_b40_line'}]},
}


def full_ctx(fp='fp', kc=KC):
    return {'schema': 1, 'documents': [], 'models': {}, 'fingerprint': fp, 'key_check': kc}


FAILED_CTX = {'schema': 1, 'error': 'build_failed'}


def snap(**bands):
    return [dict(BAND_FACT[band], fact=fact) for fact, band in bands.items()]


def case(aid, minute=None, ctx=None, recomputed='fp', verdict=None, qc=None, snapshot=None,
         version='v-test', decided=True):
    when = T0 + datetime.timedelta(minutes=aid if minute is None else minute) if decided else None
    return {'application_id': aid, 'verdict_decided_at': when,
            'stored_context': full_ctx() if ctx is None else ctx, 'recomputed_fingerprint': recomputed,
            'human_verdict': {'identity': 'pass'} if verdict is None else verdict, 'qc_answers': qc,
            'fresh_snapshot': snap(identity='certain') if snapshot is None else snapshot,
            'engine_version': version}


def run(cases, folder, blank=False, kc=KC):
    return L.run_human_lens(cases, exam_folder=str(folder), key_is_blank=blank, current_key_check=kc,
                            now=NOW)


def ex1(out):
    return out['exams'][L.EXAM_1]


def exold(out):
    return out['exams'][L.EXAM_OLD]


def read_exam(folder, name=L.EXAM_1):
    with open(os.path.join(folder, f'{name}.json'), encoding='utf-8') as fh:
        return json.load(fh)


def write_raw(folder, data, name=L.EXAM_1):
    with open(os.path.join(folder, f'{name}.json'), 'w', encoding='utf-8') as fh:
        fh.write(data if isinstance(data, str) else json.dumps(data))


@pytest.fixture
def folder(tmp_path):
    assert L.exam_folder_refusal(tmp_path) is None   # the temp folder is outside any git repository
    return tmp_path


# --- E1: the two exams and the freeze at 50 ------------------------------------------------------

def test_49_full_cases_is_not_frozen_and_has_no_score(folder):
    e = ex1(run([case(i) for i in range(1, 50)], folder))
    assert (e['frozen'], e['status'], e['score'], e['size']) == (False, 'not frozen yet: 49 of 50', None, None)
    assert not os.path.exists(folder / 'exam-1.json')


def test_50_full_cases_freeze_and_score(folder):
    e = ex1(run([case(i) for i in range(1, 51)], folder))
    assert (e['frozen'], e['status'], e['size'], e['refusal']) == (True, 'frozen', 50, None)
    assert e['still_valid'] == '50 of 50 still valid'
    assert (e['score']['facts'], e['score']['points'], e['score']['best'], e['score']['score_pct']) == (50, 100, 100, 100)
    assert e['digest'] == read_exam(folder)['digest'][:12] and len(e['digest']) == 12
    assert e['engine_version'] == 'v-test' and e['label'] == L.EXAM_1_LABEL


def test_51_eligible_freezes_the_first_50_by_time_ties_by_id(folder):
    cases = [case(i, minute=0) for i in range(2, 52)] + [case(1, minute=99)]   # 1 is the latest
    run(cases, folder)
    assert read_exam(folder)['application_ids'] == list(range(2, 52))
    other = folder / 'b'
    other.mkdir()
    run([case(i, minute=0) for i in range(51, 0, -1)], other)                  # all tie: by id
    assert read_exam(other)['application_ids'] == list(range(1, 51))


def test_a_frozen_list_never_grows_nor_reorders(folder):
    run([case(i) for i in range(10, 60)], folder)
    before = (folder / 'exam-1.json').read_bytes()
    later = [case(i) for i in range(10, 60)] + [case(i, minute=-5) for i in range(1, 9)]
    e = ex1(run(later, folder))
    assert (folder / 'exam-1.json').read_bytes() == before
    assert e['size'] == 50 and e['still_valid'] == '50 of 50 still valid'


def test_exam_old_freezes_on_its_first_run_with_every_old_case(folder):
    out = run([case(i, ctx={}) for i in range(1, 4)], folder)
    e = exold(out)
    assert (e['frozen'], e['size'], e['label']) == (True, 3, 'weaker exam: evidence state unknown')
    assert 'weaker exam: evidence state unknown' in e['known_limits']
    assert ex1(out)['status'] == 'not frozen yet: 0 of 50'
    e2 = exold(run([case(i, ctx={}) for i in range(1, 9)], folder))
    assert e2['size'] == 3 and read_exam(folder, L.EXAM_OLD)['application_ids'] == [1, 2, 3]


def test_no_old_case_means_exam_old_is_not_frozen(folder):
    e = exold(run([case(1)], folder))
    assert (e['frozen'], e['status']) == (False, 'not frozen yet: 0 cases')
    assert not os.path.exists(folder / 'exam-old.json')


def test_a_failed_context_is_in_neither_exam_and_counted(folder):
    cases = [case(i, ctx=FAILED_CTX) for i in range(1, 4)] + [case(10, ctx={}), case(11, ctx={})]
    out = run(cases, folder)
    assert out['context_failed'] == 3
    assert out['context_failed_line'].endswith(': 3')
    assert exold(out)['size'] == 2 and ex1(out)['status'] == 'not frozen yet: 0 of 50'


def test_undecided_and_unverdicted_cases_never_enter(folder):
    cases = ([case(i, ctx={}) for i in range(1, 3)]
             + [case(5, ctx={}, decided=False), case(6, ctx={}, verdict={}), case(7, ctx={}, verdict={'overall': 'decline'})]
             + [case(i, decided=False) for i in range(100, 160)] + [case(i, verdict={}) for i in range(200, 260)])
    out = run(cases, folder)
    assert (out['not_decided'], out['no_human_verdict']) == (61, 62)
    assert read_exam(folder, L.EXAM_OLD)['application_ids'] == [1, 2]
    assert ex1(out)['status'] == 'not frozen yet: 0 of 50'


# --- E2: the exam file -----------------------------------------------------------------------------

def test_the_exam_file_holds_exactly_the_allowed_fields_and_the_digest_recipe(folder):
    run([case(i) for i in range(1, 51)] + [case(99, ctx={})], folder)
    one, old = read_exam(folder), read_exam(folder, L.EXAM_OLD)
    assert set(one) == {'exam', 'format', 'application_ids', 'size', 'frozen_at', 'key_check', 'digest'}
    assert set(old) == {'exam', 'format', 'application_ids', 'size', 'frozen_at', 'digest'}
    for exam in (one, old):
        body = {k: v for k, v in exam.items() if k != 'digest'}
        canon = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        assert exam['digest'] == hashlib.sha256(canon.encode('ascii')).hexdigest()
    assert (one['format'], one['key_check'], one['frozen_at']) == (1, KC, '2026-11-24T12:00:00.000000Z')


def _tamper(exam, field=None, value=None, drop=None, add=None, redigest=True):
    exam = dict(exam)
    if field:
        exam[field] = value
    if drop:
        del exam[drop]
    if add:
        exam[add] = 1
    if redigest:
        exam['digest'] = L.exam_digest(exam)
    return exam


@pytest.mark.parametrize('change, code', [
    (dict(field='application_ids', value=list(range(2, 52)), redigest=False), 'digest_mismatch'),
    (dict(field='size', value=49), 'size_mismatch'),
    (dict(field='application_ids', value=[1] * 50), 'duplicate_id'),
    (dict(field='application_ids', value=[1.0] + list(range(2, 51))), 'non_integer_id'),
    (dict(field='application_ids', value=['1'] + list(range(2, 51))), 'non_integer_id'),
    (dict(field='application_ids', value=[True] + list(range(2, 51))), 'non_integer_id'),
    (dict(add='scores'), 'unknown_field'),
    (dict(drop='frozen_at'), 'missing_field'),
    (dict(drop='key_check'), 'missing_field'),
    (dict(field='exam', value='exam-old'), 'wrong_exam_name'),
    (dict(field='format', value=2), 'wrong_format_version'),
    (dict(field='format', value=True), 'wrong_format_version'),
    (dict(field='frozen_at', value=5), 'bad_field_type'),
])
def test_every_load_refusal(folder, change, code):
    run([case(i) for i in range(1, 51)], folder)
    write_raw(folder, _tamper(read_exam(folder), **change))
    assert L.load_exam(folder, L.EXAM_1) == (None, code)
    e = ex1(run([case(i) for i in range(1, 51)], folder))
    assert (e['refusal'], e['score'], e['validity']) == (code, None, None)


def test_a_file_that_is_not_plain_json_is_refused(folder):
    for text in ('not json', '[1, 2]', '{"exam": "exam-1", "exam": "exam-1"}', '{"size": NaN}'):
        write_raw(folder, text)
        assert L.load_exam(folder, L.EXAM_1) == (None, 'file_unreadable')


def test_a_key_check_field_in_exam_old_is_refused(folder):
    run([case(1, ctx={})], folder)
    write_raw(folder, _tamper(read_exam(folder, L.EXAM_OLD), add='key_check'), L.EXAM_OLD)
    assert L.load_exam(folder, L.EXAM_OLD) == (None, 'unknown_field')


def test_a_freeze_never_overwrites_and_leaves_no_temp_file(folder):
    exam, refusal = L.freeze_exam(folder, L.EXAM_OLD, [3, 1, 2], NOW)
    assert refusal is None and exam['application_ids'] == [3, 1, 2]
    before = (folder / 'exam-old.json').read_bytes()
    assert L.freeze_exam(folder, L.EXAM_OLD, [9], NOW) == (None, 'already_frozen')
    assert (folder / 'exam-old.json').read_bytes() == before
    assert sorted(os.listdir(folder)) == ['exam-old.json']


def test_a_name_taken_between_the_check_and_the_link_is_refused_not_replaced(folder):
    def taken(src, dst):
        with open(dst, 'w', encoding='utf-8') as fh:
            fh.write('someone else')
        raise FileExistsError
    with mock.patch.object(L.os, 'link', side_effect=taken):
        assert L.freeze_exam(folder, L.EXAM_OLD, [1], NOW) == (None, 'already_frozen')
    assert (folder / 'exam-old.json').read_text(encoding='utf-8') == 'someone else'
    assert sorted(os.listdir(folder)) == ['exam-old.json']


# --- E3: never inside a git repository -------------------------------------------------------------

@pytest.mark.parametrize('kind', ['dir', 'file'])
def test_a_folder_inside_a_git_repository_is_refused(tmp_path, kind):
    (tmp_path / '.git').mkdir() if kind == 'dir' else (tmp_path / '.git').write_text('gitdir: x')
    inner = tmp_path / 'a' / 'b'
    inner.mkdir(parents=True)
    for place in (tmp_path, inner):
        assert L.freeze_exam(place, L.EXAM_OLD, [1], NOW) == (None, 'inside_git_repo')
        assert not os.path.exists(place / 'exam-old.json')
    out = run([case(1, ctx={})], inner)
    assert exold(out)['refusal'] == 'inside_git_repo'


def test_the_real_repository_is_refused():
    here = os.path.dirname(os.path.abspath(__file__))
    assert L.exam_folder_refusal(here) == 'inside_git_repo'
    assert L.freeze_exam(here, L.EXAM_OLD, [1], NOW) == (None, 'inside_git_repo')
    assert not os.path.exists(os.path.join(here, 'exam-old.json'))


def test_a_link_is_resolved_first_and_a_missing_folder_is_refused(tmp_path):
    repo = tmp_path / 'repo'
    (repo / '.git').mkdir(parents=True)
    (repo / 'sub').mkdir()
    outside = tmp_path / 'out'
    outside.mkdir()
    os.symlink(repo / 'sub', outside / 'link')   # only the RESOLVED path has a .git parent
    assert L.exam_folder_refusal(outside / 'link') == 'inside_git_repo'
    assert L.exam_folder_refusal(tmp_path / 'nowhere') == 'folder_missing'
    (outside / 'f').write_text('x')
    assert L.exam_folder_refusal(outside / 'f') == 'folder_missing'


# --- E4: validity per case --------------------------------------------------------------------------

def test_each_validity_count(folder):
    run([case(i) for i in range(1, 51)], folder)
    now = [case(i) for i in range(7, 51)]
    now += [case(1, recomputed='moved'), case(2, recomputed=None), case(4, ctx=FAILED_CTX),
            case(5, ctx={}), case(6, decided=False)]                                   # 3 is missing
    e = ex1(run(now, folder))
    assert e['validity'] == {'valid': 44, 'evidence_changed': 1, 'could_not_recompute': 1, 'missing': 1,
                             'context_changed': 2, 'no_longer_decided': 1}
    assert e['still_valid'] == '44 of 50 still valid' and e['size'] == 50
    assert e['score']['facts'] == 44
    assert 'drop-outs shrink the exam' in e['known_limits'] and 'a score on 44 facts' in e['known_limits']


# --- E5: the key check ------------------------------------------------------------------------------

def test_a_blank_key_refuses_exam_1_and_exam_old_still_runs(folder):
    cases = [case(i) for i in range(1, 51)] + [case(i, ctx={}) for i in range(60, 66)]
    run(cases, folder)
    out = run(cases, folder, blank=True)
    assert (ex1(out)['refusal'], ex1(out)['score'], ex1(out)['validity']) == ('key_blank', None, None)
    assert exold(out)['refusal'] is None and exold(out)['score']['facts'] == 6


def test_a_current_key_check_unlike_the_exams_is_refused(folder):
    run([case(i) for i in range(1, 51)], folder)
    for kc in ('99999999', None):
        e = ex1(run([case(i) for i in range(1, 51)], folder, kc=kc))
        assert (e['refusal'], e['score']) == ('key_check_differs_from_exam', None)


def test_listed_cases_with_another_key_check_refuse_and_are_counted(folder):
    run([case(i) for i in range(1, 51)], folder)
    now = [case(i) for i in range(3, 51)] + [case(i, ctx=full_ctx(kc='ffffffff')) for i in (1, 2)]
    e = ex1(run(now, folder))
    assert (e['refusal'], e['cases_with_other_key_check'], e['score']) == ('key_check_differs_from_cases', 2, None)


def test_the_freeze_is_refused_on_a_blank_key_or_mixed_key_checks(folder):
    assert ex1(run([case(i) for i in range(1, 51)], folder, blank=True))['refusal'] == 'key_blank'
    mixed = [case(i) for i in range(1, 50)] + [case(50, ctx=full_ctx(kc='ffffffff'))]
    e = ex1(run(mixed, folder))
    assert (e['refusal'], e['cases_with_other_key_check']) == ('candidate_key_checks_differ', 1)
    assert ex1(run([case(i) for i in range(1, 51)], folder, kc=None))['refusal'] == 'candidate_key_checks_differ'
    assert not os.path.exists(folder / 'exam-1.json')


# --- E6/E7: the human answer and the score -------------------------------------------------------

def _fail(reason, fact='identity'):
    return {fact: 'fail', 'fail_reasons': {fact: reason}}


def test_the_qc_answer_wins(folder):
    cases = [case(1, ctx={}, verdict=_fail('other'), qc={'identity': 'disagreed'}),
             case(2, ctx={}, verdict=_fail('other'), qc={'identity': 'agreed'}),
             case(3, ctx={}, verdict={'identity': 'pass'}, qc={'identity': 'disagreed'})]
    cases += [case(i, ctx={}) for i in range(4, 8)]
    e = exold(run(cases, folder))
    # 1: QC overturned the Fail -> a Certain pass (+2); 2: the Fail stands (-10); 3: a pass stays (+2)
    assert (e['score']['facts'], e['score']['points']) == (7, 2 - 10 + 2 + 8)
    assert e['qc_turned_to_pass'] == 1 and e['fails']['fails'] == 1


def test_interview_fails_stay_in_the_score_and_the_extra_line_leaves_them_out(folder):
    cases = [case(i, ctx={}, verdict=_fail('interview_differs')) for i in range(1, 3)]
    cases += [case(i, ctx={}) for i in range(3, 9)]
    e = exold(run(cases, folder))
    assert (e['score']['facts'], e['score']['points']) == (8, -20 + 12)
    extra = e['score_without_interview_fails']
    assert extra['label'] == 'score without interview Fails'
    assert (extra['facts'], extra['points'], extra['left_out'], extra['score_pct']) == (6, 12, 2, 100)
    assert e['score']['generous_wrong'] == {'count': 2, 'of': 8}


def test_the_fails_table_counts_band_by_reason_and_the_share_of_other(folder):
    plan = [('certain', 'other'), ('probable', 'other'), ('unsure', 'proof_missing'),
            ('ruleNotMet', 'document_false'), ('certain', 'interview_differs'), ('unverifiable', None)]
    cases = []
    for i, (band, reason) in enumerate(plan, start=1):
        verdict = {'identity': 'fail'} if reason is None else _fail(reason)
        cases.append(case(i, ctx={}, verdict=verdict, snapshot=snap(identity=band)))
    f = exold(run(cases, folder))['fails']
    assert f['fails'] == 6
    assert f['by_band_and_reason']['certain']['other'] == 1 and f['by_band_and_reason']['probable']['other'] == 1
    assert f['by_band_and_reason']['unsure']['proof_missing'] == 1
    assert f['by_band_and_reason']['ruleNotMet']['document_false'] == 1
    assert f['by_band_and_reason']['unverifiable']['not_given'] == 1
    assert 'interview_differs' not in f['by_band_and_reason']['certain']
    assert f['interview_by_band']['certain'] == 1
    assert f['share_other'] == {'count': 2, 'of': 6, 'too_few': False, 'pct': 33}


def test_coverage_counts_every_band_but_unsure(folder):
    cases = [case(1, ctx={}, snapshot=snap(identity='unsure'))] + [case(i, ctx={}) for i in range(2, 7)]
    s = exold(run(cases, folder))['score']
    assert s['coverage'] == {'count': 5, 'of': 6} and s['outcomes']['unsure'] == 1


def test_small_numbers_show_the_count_only(folder):
    cases = [case(i, ctx={}, verdict=_fail('interview_differs')) for i in range(1, CELL_MIN_FACTS)]
    e = exold(run(cases, folder))
    assert e['score'] == {'label': 'score', 'facts': CELL_MIN_FACTS - 1, 'too_few': True}
    assert e['score_without_interview_fails'] == {'label': 'score without interview Fails', 'facts': 0,
                                                  'too_few': True}
    assert e['fails']['share_other'] == {'count': 0, 'of': CELL_MIN_FACTS - 1, 'too_few': True}
    again = exold(run([case(i, ctx={}) for i in range(1, CELL_MIN_FACTS + 1)], folder))
    assert again['score']['facts'] == CELL_MIN_FACTS - 1 and again['size'] == CELL_MIN_FACTS - 1


def test_a_score_line_at_the_floor_shows_figures(folder):
    e = exold(run([case(i, ctx={}) for i in range(1, CELL_MIN_FACTS + 1)], folder))
    assert e['score']['too_few'] is False and e['score']['score_pct'] == 100


# --- E9: privacy, E11: bad rows ---------------------------------------------------------------------

CANARY_ID = 987654321


def test_no_application_id_in_the_output_the_errors_or_the_logs(folder, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    cases = [case(CANARY_ID + i) for i in range(50)] + [case(CANARY_ID + 99, ctx={})]
    out = run(cases, folder)
    later = run(cases[2:40] + [case(CANARY_ID + 1, recomputed='moved')], folder)
    assert ex1(later)['validity']['evidence_changed'] == 1
    text = json.dumps([out, later], default=str)
    assert str(CANARY_ID)[:6] not in text
    for bad in (cases + [case(CANARY_ID)], [dict(case(1), engine_version=CANARY_ID)],
                [dict(case(1), stored_context={'x': CANARY_ID})], [dict(case(1), human_verdict=CANARY_ID)]):
        with pytest.raises(L.BadCaseRow) as err:
            run(bad, folder)
        assert str(CANARY_ID)[:6] not in str(err.value) and str(CANARY_ID)[:6] not in repr(err.value.args)
    captured = capsys.readouterr()
    assert str(CANARY_ID)[:6] not in captured.out + captured.err + caplog.text


def test_no_key_appears_anywhere(folder, caplog, capsys, monkeypatch):
    canary = 'c0ffee' * 10 + 'beef'
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv('REPLAY_FINGERPRINT_KEY', canary)
    monkeypatch.setenv('VERDICT_FINGERPRINT_DERIVED_KEY', canary)
    with override_settings(VERDICT_FINGERPRINT_DERIVED_KEY=canary):
        out = run([case(i) for i in range(1, 51)] + [case(70, ctx={})], folder)
    files = ''.join(p.read_text(encoding='utf-8') for p in folder.iterdir())
    captured = capsys.readouterr()
    for place in (json.dumps(out, default=str), files, captured.out + captured.err, caplog.text):
        assert canary[:16] not in place.lower()
    assert ex1(out)['key_check'] == KC


@pytest.mark.parametrize('row, field', [
    ({k: v for k, v in case(1).items() if k != 'qc_answers'}, 'qc_answers'),
    (dict(case(1), extra=1), 'row'),
    (dict(case(1), application_id='1'), 'application_id'),
    (dict(case(1), application_id=True), 'application_id'),
    (dict(case(1), verdict_decided_at='2026-11-01'), 'verdict_decided_at'),
    (dict(case(1), stored_context=None), 'stored_context'),
    (dict(case(1), stored_context={'schema': 1}), 'stored_context'),
    (dict(case(1), stored_context={'fingerprint': 'x'}), 'stored_context.key_check'),
    (dict(case(1), recomputed_fingerprint=5), 'recomputed_fingerprint'),
    (dict(case(1), qc_answers={'identity': 'maybe'}), 'qc_answers'),
    (dict(case(1), fresh_snapshot={}), 'fresh_snapshot'),
    (dict(case(1), engine_version=None), 'engine_version'),
    ('not a row', 'row'),
])
def test_a_wrong_shaped_row_raises_naming_the_field(folder, row, field):
    with pytest.raises(L.BadCaseRow) as err:
        run([row], folder)
    assert err.value.field == field and field in str(err.value)
    assert os.listdir(folder) == []


def test_mixed_engine_versions_and_repeated_ids_raise(folder):
    with pytest.raises(L.BadCaseRow, match='engine_version'):
        run([case(1), case(2, version='other')], folder)
    with pytest.raises(L.BadCaseRow, match='application_id'):
        run([case(1), case(1)], folder)


def test_a_naive_decision_time_is_read_as_utc(folder):
    naive = dict(case(1, ctx={}), verdict_decided_at=datetime.datetime(2026, 11, 1, 0, 2))
    run([naive, case(2, ctx={}, minute=1)], folder)
    assert read_exam(folder, L.EXAM_OLD)['application_ids'] == [2, 1]


def test_now_must_carry_a_zone(folder):
    with pytest.raises(ValueError):
        L.run_human_lens([], exam_folder=str(folder), key_is_blank=False, current_key_check=KC,
                         now=datetime.datetime(2026, 11, 24))


# --- E10: pure, light imports; words ----------------------------------------------------------------

STDLIB = {'__future__', 'datetime', 'hashlib', 'json', 'os', 'pathlib', 'tempfile'}


def test_module_level_imports_are_plain_standard_library_only():
    with open(LENS_FILE, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split('.')[0] for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split('.')[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert all(not (isinstance(n, ast.ImportFrom) and n.level) for n in top)
    assert names <= STDLIB


def test_importing_the_lens_loads_no_django_and_no_app_module(tmp_path):
    package = tmp_path / 'replay'
    package.mkdir()
    (package / '__init__.py').write_text('')
    with open(LENS_FILE, encoding='utf-8') as fh:
        (package / 'lens_human.py').write_text(fh.read(), encoding='utf-8')
    probe = ('import sys; sys.path.insert(0, sys.argv[1]); import replay.lens_human; '
             'print(sorted(m for m in sys.modules if m.split(".")[0] in ("django", "apps")))')
    done = subprocess.run([sys.executable, '-I', '-c', probe, str(tmp_path)], capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 0 and done.stdout.strip() == '[]'


def test_the_banned_phrase_appears_in_neither_file():
    pattern = re.compile('document' + r's[\s_\-]*only', re.IGNORECASE)
    for path in (LENS_FILE, __file__):
        with open(path, encoding='utf-8') as fh:
            assert not pattern.search(fh.read()), path
