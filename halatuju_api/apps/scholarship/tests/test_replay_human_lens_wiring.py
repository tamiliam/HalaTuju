"""LL5 phase C1 - the human lens wired into the replay harness, OFF by default (`parent.human_lens_env`,
`child.human_lens_settings`, `child.write_human_lens`).

The parent runs in-process with an in-process "spawn" that builds each child's environment with the
REAL `parent.child_env`, then runs `child.run_side` inside the job's own guards on the test database.
The derived key is made up (`KEY`, the rows tests' key) and doubles as the canary. Made-up cases only;
every exam folder is a pytest temp folder outside the repository."""
import json
import os
import pathlib
import types
from unittest import mock

import pytest

from apps.scholarship import verdict_context
from apps.scholarship.eval.replay import child, guards, lens_human, lens_result_schema, parent, scrub
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_replay_harness import (
    ANSWERS, INSTANT, LOCAL_URL, _done_proc, _Engine, _register_fake_codes,
)
from apps.scholarship.tests.test_replay_lens_human_rows import decide, desk, keyed  # noqa: F401 (fixtures)
from apps.scholarship.tests.test_replay_lens_human_rows import KEY

pytestmark = pytest.mark.django_db

KEY_ENV = parent.FINGERPRINT_KEY_ENV
#: The names every child had before this phase: the lens adds none of them, and none when it is off.
BEFORE = {'PATH', guards.DB_ENV, scrub.SALT_ENV, 'PYTHONPATH', 'DJANGO_SETTINGS_MODULE',
          'PYTHONDONTWRITEBYTECODE', 'TZ'}
LENS_NAMES = {child.HUMAN_LENS_ENV, child.HUMAN_LENS_FOLDER_ENV, child.HUMAN_LENS_FREEZE_ENV, KEY_ENV}
REPO_FOLDER = str(pathlib.Path(__file__).resolve().parent)   # a folder inside this git repository


def _args(workdir, *extra):
    return parent.parse_args(['--instant', INSTANT, '--months', '2026-11,2026-12', '--workdir', str(workdir),
                              '--old-root', str(workdir), '--new-root', str(workdir), *extra])


def _parent_env(key=KEY):
    env = {guards.DB_ENV: LOCAL_URL, 'PATH': '/bin'}
    if key is not None:
        env[KEY_ENV] = key
    return env


@pytest.fixture
def harness(keyed, request, monkeypatch):
    """``run(args, env)`` -> (result, printed lines, {side: child env}). Each in-process child gets the
    environment the REAL `parent.child_env` builds, and the derived key setting `replay.settings` would
    read from it; one fake engine (`same`) runs on every side."""
    _register_fake_codes(types.SimpleNamespace(addCleanup=request.addfinalizer))
    monkeypatch.setattr(scrub, 'new_salt', lambda: 'a' * 64)       # the same salt on every run here

    def run(args, env):
        seen, lines = {}, []

        def spawn(args, side, snapshot, out_path, env):
            built = parent.child_env(env, args.new_root, args.harness_dir, parent.human_lens_env(args, env, side))
            guards.check_environment(built)                     # the child's own first check passes
            seen[side] = built
            keyed.VERDICT_FINGERPRINT_DERIVED_KEY = built.get(KEY_ENV, '')
            with open(out_path, 'w', encoding='utf-8') as fh:
                def write(obj):
                    fh.write(json.dumps(child.scrub(obj), sort_keys=True) + '\n')
                child.run_side(side=side, engines=[_Engine('same', side, ANSWERS['same'])],
                               instant=child.parse_instant(args.instant), months=args.months.split(','),
                               write=write, snapshot=snapshot, load=lambda: None,
                               session=lambda: guards.read_only_session(snapshot=snapshot, allow_sqlite=True),
                               lens=child.human_lens_settings(built, side),
                               lens_path=os.path.join(os.path.dirname(out_path), child.HUMAN_LENS_FILE))
            return _done_proc()

        result = parent.run_replay(args, env=env, out=lines.append, spawn=spawn,
                                   session=lambda: guards.read_only_session(export=True, allow_sqlite=True))
        return result, lines, seen
    return run


# ── the switch is off by default ──────────────────────────────────────────────────────────────────
def test_off_by_default_the_child_env_and_the_output_are_as_before(harness, tmp_path):
    make_application('submitted')
    args = _args(tmp_path / 'work')
    assert (args.human_lens, args.human_lens_exam_folder, args.human_lens_freeze) == (False, '', False)
    result, lines, seen = harness(args, _parent_env())
    for side in parent.RUN_SIDES:
        assert set(seen[side]) == BEFORE and KEY not in json.dumps(seen[side])
    assert parent.HUMAN_LENS_KEY not in result and parent.HUMAN_LENS_ON_LINE not in lines
    assert not (tmp_path / 'work' / child.HUMAN_LENS_FILE).exists()
    before = types.SimpleNamespace(**{k: v for k, v in vars(args).items() if not k.startswith('human_lens')})
    old_result, old_lines, old_seen = harness(before, _parent_env())     # the args as before this phase
    assert (old_result, old_lines, old_seen) == (result, lines, seen)


def test_spawn_child_passes_the_lens_names_to_the_new_side_only_and_only_when_on(tmp_path):
    env = {**_parent_env(), 'OTHER_NAME': 'x'}
    for extra, lens_side in ((), None), (('--human-lens', '--human-lens-exam-folder', str(tmp_path)), 'new'):
        args = _args(tmp_path, *extra)
        for side in parent.RUN_SIDES:
            with mock.patch.object(parent.subprocess, 'Popen') as popen:
                parent.spawn_child(args, side, 'snap', str(tmp_path / 'x.jsonl'), env)
            given = popen.call_args.kwargs['env']
            assert given == parent.child_env(env, str(tmp_path), args.harness_dir,
                                             parent.human_lens_env(args, env, side))
            if side == lens_side:
                assert set(given) - BEFORE == LENS_NAMES and given[KEY_ENV] == KEY
            else:
                assert set(given) == BEFORE


def test_the_lens_flags_without_the_switch_are_refused(tmp_path):
    for extra in (('--human-lens-freeze',), ('--human-lens-exam-folder', str(tmp_path))):
        with pytest.raises(SystemExit):
            _args(tmp_path, *extra)


def test_the_child_takes_the_lens_from_the_switch_on_the_new_side_only():
    on = {child.HUMAN_LENS_ENV: '1', child.HUMAN_LENS_FOLDER_ENV: '/x', child.HUMAN_LENS_FREEZE_ENV: '1'}
    assert child.human_lens_settings(on, 'new') == ('/x', True)
    assert child.human_lens_settings({**on, child.HUMAN_LENS_FREEZE_ENV: '0'}, 'new') == ('/x', False)
    for side in ('old', 'new_again'):
        assert child.human_lens_settings(on, side) is None
    for switch in ('', '0', 'yes', 'true'):
        assert child.human_lens_settings({**on, child.HUMAN_LENS_ENV: switch}, 'new') is None
    assert child.human_lens_settings({}, 'new') is None


def test_env_names_are_compared_upper_case_against_the_forbidden_names():
    for name in ('SECRET_KEY', 'secret_key', 'Secret_Key'):
        with pytest.raises(guards.WriteRefused):
            guards.check_environment({name: 'x'})
    assert guards.check_environment({KEY_ENV: KEY, child.HUMAN_LENS_ENV: '1', child.HUMAN_LENS_FOLDER_ENV: '/x',
                                     child.HUMAN_LENS_FREEZE_ENV: '1'})


# ── refusals stay refusals ─────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize('folder, code', [
    ('exams', lens_human.FOLDER_NOT_ABSOLUTE),
    ('/nonexistent-exam-folder', lens_human.FOLDER_MISSING), (REPO_FOLDER, lens_human.INSIDE_GIT_REPO)])
def test_a_bad_folder_is_the_lens_refusal_even_with_the_freeze_flag(harness, tmp_path, folder, code):
    make_application('submitted')
    extra = ('--human-lens', '--human-lens-freeze', '--human-lens-exam-folder', folder)
    before = sorted(os.listdir(REPO_FOLDER))
    result, lines, _seen = harness(_args(tmp_path / 'work', *extra), _parent_env())
    lens = result[parent.HUMAN_LENS_KEY]
    assert {exam['refusal'] for exam in lens['exams'].values()} == {code}
    assert dict(result['same']) == {'same': 1}                     # the other lenses still report
    assert lines.count(parent.HUMAN_LENS_ON_LINE) == 1 and sorted(os.listdir(REPO_FOLDER)) == before
    assert parent.replay_exit_code(result) == 0                     # a refusal is a result, not an error


def test_a_normal_run_with_no_exam_file_answers_exam_missing_and_writes_nothing(harness, desk, tmp_path):
    decide(desk)
    folder = tmp_path / 'exams'
    folder.mkdir()
    result, _lines, _seen = harness(_args(tmp_path / 'work', '--human-lens', '--human-lens-exam-folder',
                                          str(folder)), _parent_env())
    lens = result[parent.HUMAN_LENS_KEY]
    assert {exam['refusal'] for exam in lens['exams'].values()} == {lens_human.EXAM_MISSING}
    assert os.listdir(folder) == []


def test_a_caught_lens_error_is_reported_by_class_name_and_the_side_finishes(harness, tmp_path, monkeypatch):
    from apps.scholarship.eval.replay import lens_human_rows
    make_application('submitted')

    def broken(*_a, **_k):
        raise lens_human.BadCaseRow('application_id', 'repeats')
    monkeypatch.setattr(lens_human_rows, 'run_human_lens_on_database', broken)
    result, lines, _seen = harness(_args(tmp_path / 'work', '--human-lens', '--human-lens-exam-folder',
                                         str(tmp_path)), _parent_env())
    assert result[parent.HUMAN_LENS_KEY] == {'error': 'BadCaseRow'}
    new_side = next(json.loads(x) for x in lines if '"side": "new"' in x and '"event": "side"' in x)
    assert new_side['exit'] == 0 and new_side['fatal'] == []
    assert parent.replay_exit_code(result) == parent.HUMAN_LENS_FAILED_EXIT


# ── a dry run: freeze, then a normal run, then a blank key; the canary key never leaves ───────────
def _breaks_fingerprint_for(pk, real):
    def broken(app):
        if app.pk == pk:
            raise TypeError('made-up')
        return real(app)
    return broken


def _everything_written(*folders):
    text = ''
    for folder in folders:
        for root, _dirs, files in os.walk(folder):
            for name in files:
                text += pathlib.Path(root, name).read_text(encoding='utf-8')
    return text


def test_dry_run_freeze_then_score_then_a_blank_key(harness, desk, tmp_path, capfd, monkeypatch):
    work, folder = tmp_path / 'work', tmp_path / 'exams'
    folder.mkdir()
    full = [decide(desk) for _ in range(lens_human.EXAM_1_SIZE)]
    for _ in range(2):
        make_application('awaiting_qc', outcome='recommend', cohort=desk[0])   # decided before LL4: {}
    lens_flags = ('--human-lens', '--human-lens-exam-folder', str(folder))
    capfd.readouterr()
    frozen, lines_1, seen = harness(_args(work, *lens_flags, '--human-lens-freeze'), _parent_env())
    lens = frozen[parent.HUMAN_LENS_KEY]
    assert sorted(os.listdir(folder)) == ['exam-1.json', 'exam-old.json']
    assert lens['exams']['exam-1']['still_valid'] == '50 of 50 still valid'
    assert lens['exams']['exam-old']['still_valid'] == '2 of 2 still valid'
    assert seen['new'][KEY_ENV] == KEY and KEY_ENV not in seen['old'] and KEY_ENV not in seen['new_again']

    ApplicantDocument.objects.create(application=full[0], doc_type='offer_letter', storage_path='test/offer')
    ScholarshipApplication.objects.filter(pk=full[1].pk).update(status='recommended')   # its twin recovers it
    monkeypatch.setattr(verdict_context, 'build_verdict_context',
                        _breaks_fingerprint_for(full[2].pk, verdict_context.build_verdict_context))
    files_before = sorted(os.listdir(folder))
    scored, lines_2, _seen = harness(_args(work, *lens_flags), _parent_env())
    exam_1 = scored[parent.HUMAN_LENS_KEY]['exams']['exam-1']
    assert exam_1['refusal'] is None and sorted(os.listdir(folder)) == files_before
    assert {k: v for k, v in exam_1['validity'].items() if v} == {
        'valid': 48, 'evidence_changed': 1, 'could_not_recompute': 1}
    assert exam_1['valid_split'] == {'matched_directly': 47, 'recovered_by_twin': 1}
    assert {k: v for k, v in exam_1['could_not_recompute_reasons'].items() if v} == {'recompute_error': 1}

    blank, lines_3, _seen = harness(_args(work, *lens_flags), _parent_env(key=None))
    blank_exams = blank[parent.HUMAN_LENS_KEY]['exams']
    assert blank_exams['exam-1']['refusal'] == lens_human.KEY_BLANK and blank_exams['exam-1']['score'] is None
    assert blank_exams['exam-old']['still_valid'] == '2 of 2 still valid'
    assert dict(blank['same']) == {'same': lens_human.EXAM_1_SIZE + 2}   # the other lenses still report
    for run in (frozen, scored, blank):                            # real shapes pass the allow-list as they are
        assert lens_result_schema.human_lens_result_allowed(run[parent.HUMAN_LENS_KEY])
        assert parent.replay_exit_code(run) == 0

    captured = capfd.readouterr()                                  # fd level: the whole run's stdout, stderr
    text = '\n'.join([captured.out, captured.err, *lines_1, *lines_2, *lines_3,
                      json.dumps([frozen, scored, blank], default=str), _everything_written(work, folder)])
    for secret in (KEY, KEY.upper()):
        assert secret not in text


# ── C1c: fail fast, and a lens error never looks like a result ───────────────────────────────────────
PLANTED_NAME = 'Siti Aminah binti Ahmad'


def test_the_lens_without_an_exam_folder_is_an_argument_error_before_any_run(tmp_path):
    for extra in (('--human-lens',), ('--human-lens', '--human-lens-freeze'),
                  ('--human-lens', '--human-lens-exam-folder', '')):
        with pytest.raises(SystemExit) as caught:
            _args(tmp_path, *extra)
        assert caught.value.code == 2
    assert _args(tmp_path, '--human-lens', '--human-lens-exam-folder', str(tmp_path)).human_lens


def _writes_no_file(lens, *, now, path):
    return None


def _writes_a_broken_file(lens, *, now, path):
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('{"exams": ')


def _plants_a_name(*_a, **_k):
    return {'error': PLANTED_NAME}


@pytest.mark.parametrize('where, name, value, error', [
    ('child', 'write_human_lens', _writes_no_file, lens_result_schema.NO_OUTPUT),
    ('child', 'write_human_lens', _writes_a_broken_file, lens_result_schema.BAD_OUTPUT),
    ('rows', 'run_human_lens_on_database', _plants_a_name, lens_result_schema.SCHEMA)])
def test_each_lens_error_kind_exits_non_zero(harness, tmp_path, monkeypatch, where, name, value, error):
    from apps.scholarship.eval.replay import lens_human_rows
    make_application('submitted')
    monkeypatch.setattr(child if where == 'child' else lens_human_rows, name, value)
    work = tmp_path / 'work'
    result, lines, _seen = harness(_args(work, '--human-lens', '--human-lens-exam-folder', str(tmp_path)),
                                   _parent_env())
    assert result[parent.HUMAN_LENS_KEY] == {'error': error}
    assert dict(result['same']) == {'same': 1}                     # the engines still report
    assert parent.replay_exit_code(result) == parent.HUMAN_LENS_FAILED_EXIT
    assert PLANTED_NAME not in _everything_written(work) + '\n'.join(lines)


@pytest.fixture
def main_stubbed(monkeypatch, request):
    """``main`` with the preflight and Django set-up stubbed, and ``run_replay`` answering ``result``."""
    import logging
    request.addfinalizer(lambda level=logging.root.manager.disable: logging.disable(level))
    monkeypatch.setattr(guards, 'check_environment', lambda env: True)
    monkeypatch.setattr(guards, 'check_database_url', lambda url: ('localhost', 5432))
    monkeypatch.setattr(parent, 'setup_django', lambda: None)

    def run(result, argv):
        monkeypatch.setattr(parent, 'run_replay', lambda args, env: result)
        return parent.main(['--instant', INSTANT, '--months', '2026-11,2026-12', *argv])
    return run


@pytest.mark.parametrize('error', [lens_result_schema.NO_OUTPUT, lens_result_schema.BAD_OUTPUT,
                                   lens_result_schema.SCHEMA, 'BadCaseRow', 'ValueError', 'TypeError', 'OSError'])
def test_main_exits_4_on_every_lens_error(main_stubbed, tmp_path, error):
    lens_flags = ['--human-lens', '--human-lens-exam-folder', str(tmp_path)]
    assert main_stubbed({'same': {'same': 1}, parent.HUMAN_LENS_KEY: {'error': error}}, lens_flags) == 4
    assert parent.HUMAN_LENS_FAILED_EXIT == 4


def test_main_exits_0_on_a_clean_lens_run_a_refusal_and_with_the_lens_off(main_stubbed, tmp_path):
    from django.test import override_settings

    from apps.scholarship.eval.replay import lens_human_rows
    with override_settings(DEBUG=True):                            # every exam refused: debug_on
        refused = lens_human_rows.run_human_lens_on_database(str(tmp_path), child.parse_instant(INSTANT))
    lens_flags = ['--human-lens', '--human-lens-exam-folder', str(tmp_path)]
    assert lens_result_schema.human_lens_result_allowed(refused)
    assert main_stubbed({'same': {'same': 1}, parent.HUMAN_LENS_KEY: refused}, lens_flags) == 0
    assert main_stubbed({'same': {'same': 1}}, []) == 0             # the lens off: as before
    assert main_stubbed({}, []) == 0                                # --counts-only returns {}


# ── C2: the coach grade under the same switch, its own file and allow-list ──────────────────────────
def _lens_on(tmp_path):
    return _args(tmp_path / 'work', '--human-lens', '--human-lens-exam-folder', str(tmp_path))


def test_the_coach_grade_runs_under_the_same_switch_with_no_new_env_name(harness, desk, tmp_path):
    from apps.scholarship.eval.replay import coach_result_schema
    decide(desk)
    result, _lines, seen = harness(_lens_on(tmp_path), _parent_env())
    coach = result[parent.COACH_GRADE_KEY]
    assert coach_result_schema.coach_result_allowed(coach) and coach['decided_records'] == 1
    assert coach['left_out_reasons'] == ['interview_differs']
    assert set(seen['new']) - BEFORE == LENS_NAMES and set(seen['old']) == BEFORE
    assert (tmp_path / 'work' / child.COACH_GRADE_FILE).exists()
    assert parent.HUMAN_LENS_KEY in result and parent.replay_exit_code(result) == 0


def test_with_the_switch_off_there_is_no_coach_file_and_no_key(harness, tmp_path):
    make_application('submitted')
    result, _lines, _seen = harness(_args(tmp_path / 'work'), _parent_env())
    assert parent.COACH_GRADE_KEY not in result
    assert not (tmp_path / 'work' / child.COACH_GRADE_FILE).exists()


def test_a_lens_error_does_not_stop_the_coach_grade_and_the_other_way_round(harness, tmp_path, monkeypatch):
    from apps.scholarship.eval.replay import coach_rows, lens_human_rows
    make_application('submitted')
    real = lens_human_rows.run_human_lens_on_database

    def broken(*_a, **_k):
        raise lens_human.BadCaseRow('application_id', 'repeats')
    monkeypatch.setattr(lens_human_rows, 'run_human_lens_on_database', broken)
    result, _lines, _seen = harness(_lens_on(tmp_path), _parent_env())
    assert result[parent.HUMAN_LENS_KEY] == {'error': 'BadCaseRow'}
    assert result[parent.COACH_GRADE_KEY]['decided_records'] == 0
    monkeypatch.setattr(lens_human_rows, 'run_human_lens_on_database', real)

    def broken_coach():
        raise KeyError(PLANTED_NAME)
    monkeypatch.setattr(coach_rows, 'coach_grade_on_database', broken_coach)
    result, lines, _seen = harness(_lens_on(tmp_path), _parent_env())
    assert result[parent.COACH_GRADE_KEY] == {'error': 'LookupError'}
    assert 'exams' in result[parent.HUMAN_LENS_KEY] and dict(result['same']) == {'same': 1}
    new_side = next(json.loads(x) for x in lines if '"side": "new"' in x and '"event": "side"' in x)
    assert new_side['exit'] == 0 and new_side['fatal'] == []
    assert parent.replay_exit_code(result) == parent.HUMAN_LENS_FAILED_EXIT
    assert PLANTED_NAME not in _everything_written(tmp_path / 'work') + '\n'.join(lines)


def _coach_writes_no_file(*, path):
    return None


def _coach_writes_a_broken_file(*, path):
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('{"months": ')


def _coach_plants_a_name():
    return {'refusal': PLANTED_NAME}


@pytest.mark.parametrize('where, name, value, error', [
    ('child', 'write_coach_grade', _coach_writes_no_file, lens_result_schema.NO_OUTPUT),
    ('child', 'write_coach_grade', _coach_writes_a_broken_file, lens_result_schema.BAD_OUTPUT),
    ('rows', 'coach_grade_on_database', _coach_plants_a_name, lens_result_schema.SCHEMA)])
def test_each_coach_error_kind_exits_non_zero(harness, tmp_path, monkeypatch, where, name, value, error):
    from apps.scholarship.eval.replay import coach_rows
    make_application('submitted')
    monkeypatch.setattr(child if where == 'child' else coach_rows, name, value)
    result, lines, _seen = harness(_lens_on(tmp_path), _parent_env())
    assert result[parent.COACH_GRADE_KEY] == {'error': error}
    assert 'exams' in result[parent.HUMAN_LENS_KEY] and dict(result['same']) == {'same': 1}
    assert parent.replay_exit_code(result) == parent.HUMAN_LENS_FAILED_EXIT
    assert PLANTED_NAME not in _everything_written(tmp_path / 'work') + '\n'.join(lines)


def test_an_old_coach_file_is_deleted_before_the_run(harness, tmp_path, monkeypatch):
    make_application('submitted')
    work = tmp_path / 'work'
    work.mkdir()
    (work / child.COACH_GRADE_FILE).write_text('{"refusal": "debug_on"}', encoding='utf-8')
    monkeypatch.setattr(child, 'write_coach_grade', _coach_writes_no_file)
    result, _lines, _seen = harness(_lens_on(tmp_path), _parent_env())
    assert result[parent.COACH_GRADE_KEY] == {'error': lens_result_schema.NO_OUTPUT}


@pytest.mark.parametrize('coach, code', [
    ({'error': 'schema'}, 4), ({'error': 'no_output'}, 4), ({'error': 'LookupError'}, 4),
    ({'refusal': 'debug_on'}, 0)])
def test_main_exits_4_on_a_coach_error_and_0_on_its_refusal(main_stubbed, tmp_path, coach, code):
    lens_flags = ['--human-lens', '--human-lens-exam-folder', str(tmp_path)]
    clean_lens = {'engine_version': None}                          # main reads only the error key
    result = {'same': {'same': 1}, parent.HUMAN_LENS_KEY: clean_lens, parent.COACH_GRADE_KEY: coach}
    assert main_stubbed(result, lens_flags) == code
