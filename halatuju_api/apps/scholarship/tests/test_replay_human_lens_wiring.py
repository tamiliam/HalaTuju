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
    extra = ('--human-lens', '--human-lens-freeze', '--human-lens-exam-folder', str(tmp_path))
    before = sorted(os.listdir(REPO_FOLDER))
    args = _args(tmp_path / 'work', *extra)
    # set after parsing: the parent refuses a relative folder itself (an argument error); this checks
    # the child's own refusal, the second lock, as if a folder got past the parent
    args.human_lens_exam_folder = folder
    result, lines, _seen = harness(args, _parent_env())
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


# ── fix round: counts-only with the lens, and a relative exam folder, are argument errors ─────────────
@pytest.fixture
def main_recorded(monkeypatch, request, capsys):
    """``run(*argv)`` -> (exit code, stdout, stderr, calls): the real ``main`` and ``parse_args``, with the
    preflight and Django set-up stubbed and ``run_replay`` / ``spawn_child`` recording any call."""
    import logging
    request.addfinalizer(lambda level=logging.root.manager.disable: logging.disable(level))
    monkeypatch.setattr(guards, 'check_environment', lambda env: True)
    monkeypatch.setattr(guards, 'check_database_url', lambda url: ('localhost', 5432))
    monkeypatch.setattr(parent, 'setup_django', lambda: None)
    calls = []
    monkeypatch.setattr(parent, 'spawn_child', lambda *a, **k: calls.append('spawn'))

    def run_replay(args, env):
        calls.append('run_replay')
        return {}
    monkeypatch.setattr(parent, 'run_replay', run_replay)

    def run(*argv):
        capsys.readouterr()
        try:
            code = parent.main(['--instant', INSTANT, '--months', '2026-11,2026-12', *argv])
        except SystemExit as stop:                                  # main lets argparse's exit through
            code = stop.code
        out, err = capsys.readouterr()
        return code, out, err, calls
    return run


def test_counts_only_with_the_lens_is_an_argument_error_before_any_child_or_file(main_recorded, tmp_path):
    work = tmp_path / 'work'
    work.mkdir()
    old = work / child.HUMAN_LENS_FILE
    old.write_text('{"error": "schema"}', encoding='utf-8')        # an earlier run's file stays untouched
    for flags in (('--counts-only', '--human-lens', '--human-lens-exam-folder', str(tmp_path)),
                  ('--human-lens', '--human-lens-exam-folder', str(tmp_path), '--counts-only')):
        code, out, err, calls = main_recorded('--workdir', str(work), *flags)
        assert code == 2 and calls == [] and out == ''
        assert parent.LENS_REPORT_START not in out + err and parent.LENS_REPORT_END not in out + err
        assert '--counts-only and --human-lens cannot be used together' in err
    assert old.read_text(encoding='utf-8') == '{"error": "schema"}'


def test_counts_only_alone_runs_as_before(harness, tmp_path):
    make_application('submitted')
    args = _args(tmp_path / 'work', '--counts-only')
    assert (args.counts_only, args.human_lens) == (True, False)
    result, lines, seen = harness(args, _parent_env())
    assert result == {} and seen == {} and [json.loads(x)['event'] for x in lines] == ['start', 'counts']
    before = types.SimpleNamespace(**{k: v for k, v in vars(args).items() if not k.startswith('human_lens')})
    assert harness(before, _parent_env()) == (result, lines, seen)     # the args as before this phase


def test_main_with_counts_only_alone_runs_and_exits_0(main_recorded):
    code, out, err, calls = main_recorded('--counts-only')
    assert (code, out, err, calls) == (0, '', '', ['run_replay'])


RELATIVE_FOLDERS = ('exams', '.', './exams', '../exams', '~/exams', 'Siti_Aminah_exams', 'exams/')


@pytest.mark.parametrize('folder', RELATIVE_FOLDERS)
def test_a_relative_exam_folder_is_an_argument_error_with_fixed_words(main_recorded, tmp_path, folder):
    code, out, err, calls = main_recorded('--workdir', str(tmp_path / 'work'), '--human-lens',
                                          '--human-lens-exam-folder', folder)
    assert code == 2 and calls == [] and out == ''
    assert err.rstrip('\n').endswith('error: --human-lens-exam-folder must be an absolute path')
    assert 'Siti_Aminah' not in err and not (tmp_path / 'work').exists()


def test_the_parent_and_the_child_agree_on_absolute(tmp_path):
    for folder in (*RELATIVE_FOLDERS, str(tmp_path), '/nonexistent-exam-folder', REPO_FOLDER, '/'):
        child_says_relative = lens_human.exam_folder_refusal(folder) == lens_human.FOLDER_NOT_ABSOLUTE
        try:
            _args(tmp_path, '--human-lens', '--human-lens-exam-folder', folder)
            parent_refused = False
        except SystemExit as stop:
            parent_refused = stop.code == 2
        assert parent_refused is child_says_relative, folder
    args = _args(tmp_path, '--human-lens', '--human-lens-exam-folder', str(tmp_path))   # absolute: as today
    assert (args.human_lens, args.human_lens_exam_folder) == (True, str(tmp_path))


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

    from apps.scholarship.eval.replay import coach_rows, lens_human_rows
    with override_settings(DEBUG=True):                            # every exam refused: debug_on
        refused = lens_human_rows.run_human_lens_on_database(str(tmp_path), child.parse_instant(INSTANT))
    lens_flags = ['--human-lens', '--human-lens-exam-folder', str(tmp_path)]
    assert lens_result_schema.human_lens_result_allowed(refused)
    # C2d: with the lens on, a run returns both keys; a missing coach grade is a no_output failure (exit 4).
    coach_refused = coach_rows.coach_debug_refusal()
    assert main_stubbed({'same': {'same': 1}, parent.HUMAN_LENS_KEY: refused,
                         parent.COACH_GRADE_KEY: coach_refused}, lens_flags) == 0
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
    from django.test import override_settings

    from apps.scholarship.eval.replay import lens_human_rows
    lens_flags = ['--human-lens', '--human-lens-exam-folder', str(tmp_path)]
    with override_settings(DEBUG=True):     # C2d: main renders the lens, so it must pass the allow-list
        clean_lens = lens_human_rows.run_human_lens_on_database(str(tmp_path), child.parse_instant(INSTANT))
    result = {'same': {'same': 1}, parent.HUMAN_LENS_KEY: clean_lens, parent.COACH_GRADE_KEY: coach}
    assert main_stubbed(result, lens_flags) == code


# ── LL6 P2b: the exam home in a bucket (`exam_home`), wired into ``main`` ─────────────────────────────
SECRET_BUCKET = 'exams-sitiaminah-987654321'       # a valid name that must never be echoed


def test_the_bucket_flag_rules_in_order_with_fixed_words(main_recorded, tmp_path):
    from apps.scholarship.eval.replay import exam_home
    assert exam_home.bucket_name_ok(SECRET_BUCKET)
    work = str(tmp_path / 'work')
    cases = [
        (('--human-lens-exam-bucket', SECRET_BUCKET),
         '--human-lens-freeze, --human-lens-exam-folder and --human-lens-exam-bucket need --human-lens'),
        (('--human-lens', '--human-lens-exam-folder', str(tmp_path), '--human-lens-exam-bucket', SECRET_BUCKET),
         'use one of --human-lens-exam-folder or --human-lens-exam-bucket'),
        (('--human-lens', '--human-lens-freeze'),
         '--human-lens needs --human-lens-exam-folder or --human-lens-exam-bucket'),
        (('--human-lens', '--human-lens-exam-bucket', SECRET_BUCKET, '--counts-only'),
         '--counts-only and --human-lens cannot be used together'),
        (('--human-lens', '--human-lens-exam-folder', 'Siti_Aminah_exams'),
         '--human-lens-exam-folder must be an absolute path'),
    ]
    for bad in ('Siti_Aminah', 'Siti Aminah', 'gs://sitiaminah', 'sitiaminah/987654321', '', 'ab',
                'sitiaminah..987654321', '-sitiaminah'):
        cases.append((('--human-lens', f'--human-lens-exam-bucket={bad}'),
                      '--human-lens-exam-bucket is not a plain bucket name'))
    for flags, words in cases:
        code, out, err, calls = main_recorded('--workdir', work, *flags)
        assert code == 2 and calls == [] and out == ''
        assert err.rstrip('\n').endswith('error: ' + words), flags
        assert 'siti' not in err.lower() and '987654321' not in err and 'gs:' not in err
    assert not (tmp_path / 'work').exists()


def test_the_bucket_comes_from_the_command_line_only(tmp_path, monkeypatch):
    monkeypatch.setenv('HUMAN_LENS_EXAM_BUCKET', SECRET_BUCKET)
    with pytest.raises(SystemExit):
        _args(tmp_path, '--human-lens')
    args = _args(tmp_path, '--human-lens', '--human-lens-exam-bucket', SECRET_BUCKET)
    assert (args.human_lens_exam_bucket, args.human_lens_exam_folder) == (SECRET_BUCKET, '')
    assert _args(tmp_path).human_lens_exam_bucket is None
    assert _args(tmp_path, '--human-lens', '--human-lens-exam-folder', str(tmp_path)).human_lens_exam_bucket is None


@pytest.fixture
def main_bucket(monkeypatch, request, capsys, caplog, tmp_path):
    """``run(*flags, replay=None)`` -> (exit code, stdout, stderr, calls, store): the real ``main`` on a
    bucket run, the store child faked, ``run_replay`` running the real lens on the fetched folder."""
    import logging

    from apps.scholarship.eval.replay import exam_home
    from apps.scholarship.tests.test_replay_exam_home import EVAL_DIR, FakeStore, coach
    from apps.scholarship.tests.test_replay_lens_result_schema import cases_rich, run as lens_run
    request.addfinalizer(lambda level=logging.root.manager.disable: logging.disable(level))
    monkeypatch.setattr(guards, 'check_environment', lambda env: True)
    monkeypatch.setattr(guards, 'check_database_url', lambda url: ('localhost', 5432))
    monkeypatch.setattr(parent, 'setup_django', lambda: None)
    store, calls = FakeStore(), []
    monkeypatch.setattr(exam_home, 'spawn_store', store)
    work = tmp_path / 'work'

    def default_replay(args):
        lens = lens_run(cases_rich(), args.human_lens_exam_folder, freeze=args.human_lens_freeze)
        return {'same': {'same': 1}, parent.HUMAN_LENS_KEY: lens, parent.COACH_GRADE_KEY: coach()}

    def run(*flags, replay=default_replay):
        def run_replay(args, env):
            calls.append(('run_replay', args.human_lens_exam_folder))
            return replay(args)
        monkeypatch.setattr(parent, 'run_replay', run_replay)
        capsys.readouterr()
        caplog.clear()
        try:
            code = parent.main(['--instant', INSTANT, '--months', '2026-11,2026-12', '--workdir', str(work),
                                '--harness-dir', str(EVAL_DIR), '--human-lens',
                                '--human-lens-exam-bucket', SECRET_BUCKET, *flags])
        except SystemExit as stop:
            code = stop.code
        out, err = capsys.readouterr()
        text = out + err + caplog.text
        assert SECRET_BUCKET not in text and 'sitiaminah' not in text       # never the bucket's name
        assert all(line in exam_home.ALL_HOME_LINES for line in out.splitlines() if 'exam home' in line)
        assert list(work.glob('exams-*')) == []                             # the temp folder, always gone
        return code, out, err
    run.store, run.calls, run.work = store, calls, work
    return run


def _home_lines(out):
    return [line for line in out.splitlines() if 'exam home' in line]


def _never(_args):
    raise AssertionError('a replay child was started')


@pytest.mark.parametrize('answer', ['fetch_failed', 'refused', 'timeout', 'bad_line'])
def test_main_a_failed_fetch_exits_3_before_any_replay_child(main_bucket, answer):
    import subprocess
    raw = {'timeout': subprocess.TimeoutExpired(['x'], 120),
           'bad_line': (0, b'{"code": "absent", "id": 987654321}\n')}
    main_bucket.store.answers[('fetch', lens_human.EXAM_1)] = raw.get(answer, answer)
    code, out, err = main_bucket('--human-lens-freeze', replay=_never)
    assert code == 3 and err == '' and _home_lines(out) == [] and main_bucket.calls == []
    fatal = json.loads(out.splitlines()[-1])
    assert fatal['event'] == 'fatal' and 'ExamFetchFailed' in json.dumps(fatal)
    assert '987654321' not in out and 'fetch_failed' not in json.dumps(fatal)
    assert main_bucket.store.asked() == [('fetch', lens_human.EXAM_1)]


def test_main_a_freeze_run_on_an_empty_bucket_keeps_both_and_exits_0(main_bucket):
    code, out, err = main_bucket('--human-lens-freeze')
    assert code == 0 and err == '' and parent.LENS_REPORT_START in out
    assert _home_lines(out) == ['exam home: exam-1 frozen and kept in the bucket',
                                'exam home: exam-old frozen and kept in the bucket']
    assert out.rstrip('\n').splitlines()[-2:] == _home_lines(out)          # after the report block
    assert main_bucket.store.asked('put') == [('put', n) for n in lens_human.EXAM_NAMES]
    folder = main_bucket.calls[0][1]                                       # the lens read the temp folder
    assert os.path.dirname(folder) == os.path.abspath(str(main_bucket.work))
    assert os.path.basename(folder).startswith('exams-') and not os.path.exists(folder)


def test_main_a_lost_race_withholds_the_score_and_exits_0(main_bucket):
    main_bucket.store.answers[('put', lens_human.EXAM_1)] = 'frozen_elsewhere'
    code, out, err = main_bucket('--human-lens-freeze')
    assert code == 0 and 'another run froze this exam first' in out
    assert _home_lines(out) == ['exam home: exam-1 was frozen by another run first; the next run sits that one',
                                'exam home: exam-old frozen and kept in the bucket']


@pytest.mark.parametrize('answer', ['put_failed', 'not_verified', 'refused', 'timeout'])
def test_main_a_put_that_fails_is_blocking_exit_4(main_bucket, answer):
    import subprocess
    timeout = subprocess.TimeoutExpired(['x'], 120)
    main_bucket.store.answers[('put', lens_human.EXAM_OLD)] = timeout if answer == 'timeout' else answer
    code, out, err = main_bucket('--human-lens-freeze')
    assert code == parent.HUMAN_LENS_FAILED_EXIT == 4 and err == ''
    assert _home_lines(out) == ['exam home: exam-1 frozen and kept in the bucket',
                                'exam home: exam-old NOT kept in the bucket. BLOCKING. '
                                'Run again with --human-lens-freeze.']
    assert 'the frozen exam was not kept in the bucket' in out


def test_main_a_coach_error_on_a_freeze_run_uploads_nothing_and_exits_4(main_bucket):
    from apps.scholarship.tests.test_replay_lens_result_schema import cases_rich, run as lens_run

    def coach_broke(args):
        lens = lens_run(cases_rich(), args.human_lens_exam_folder, freeze=True)
        return {'same': {'same': 1}, parent.HUMAN_LENS_KEY: lens, parent.COACH_GRADE_KEY: {'error': 'schema'}}
    code, out, err = main_bucket('--human-lens-freeze', replay=coach_broke)
    assert code == 4 and main_bucket.store.asked('put') == []
    assert len(_home_lines(out)) == 2 and all('NOT kept' in line for line in _home_lines(out))


def test_main_a_replay_that_raises_uploads_nothing_and_still_removes_the_folder(main_bucket):
    import subprocess

    def boom(args):
        assert os.path.isdir(args.human_lens_exam_folder)
        raise subprocess.TimeoutExpired(['child'], 1)
    code, out, err = main_bucket('--human-lens-freeze', replay=boom)
    assert code == 3 and _home_lines(out) == [] and 'TimeoutExpired' in out
    assert main_bucket.store.asked('put') == [] and len(main_bucket.store.asked('fetch')) == 2


def test_main_a_normal_bucket_run_scores_the_stored_exams_and_uploads_nothing(main_bucket, tmp_path):
    from apps.scholarship.tests.test_replay_exam_home import copies_from, frozen_source
    src = frozen_source(tmp_path)
    for name in lens_human.EXAM_NAMES:
        main_bucket.store.answers[('fetch', name)] = copies_from(src)
    for flags in ((), ('--human-lens-freeze',)):                           # nothing new: nothing to keep
        code, out, err = main_bucket(*flags)
        assert code == 0 and err == '' and _home_lines(out) == [] and parent.LENS_REPORT_START in out
    assert main_bucket.store.asked('put') == []


def test_main_a_normal_run_on_an_empty_bucket_uploads_nothing(main_bucket):
    code, out, err = main_bucket()
    assert _home_lines(out) == [] and main_bucket.store.asked('put') == [] and err == ''
