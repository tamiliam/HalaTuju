"""LL6 phase P2b - the exam home (`eval/replay/exam_home.py`): the parent's fetch, its guarded keep and its
clean, with the store child faked (`FakeStore`), except one real start of the child that is refused before
any network. Made-up data only; every exam folder is a pytest temp folder outside the repository."""
import json
import os
import pathlib
import stat
import subprocess
import sys
import types

import pytest

from apps.scholarship.eval.replay import exam_home as EH
from apps.scholarship.eval.replay import exam_store as S
from apps.scholarship.eval.replay import guards, lens_human as L, parent, scrub
from apps.scholarship.eval.replay import lens_result_schema as LS
from apps.scholarship.eval.replay import report_lens as R
from apps.scholarship.fact_bands import CERTAIN
from apps.scholarship.tests.test_replay_exam_store import BUCKET, EVAL_DIR
from apps.scholarship.tests.test_replay_lens_result_schema import cases_rich, run
from apps.scholarship.tests.test_replay_report_lens import coach_one_pair

PLANTED_ID = '987654321'


# ── the fake store child ──────────────────────────────────────────────────────────────────────────────
def answer_of(code):
    """What the real child would print and exit with for ``code``."""
    return subprocess.CompletedProcess([], 0 if code in S.GOOD_CODES else 1, stdout=S.result_line(code).encode())


class FakeStore:
    """Stands in for `exam_home.spawn_store`. ``answers[(mode, exam)]`` is a code, a raw ``(status, bytes)``,
    an exception to raise, or ``f(folder, exam)`` returning one of those (it may write the file first).
    Unset: a fetch answers ``absent``, a put ``kept``. Every call is recorded (argv, folder, env)."""

    def __init__(self):
        self.answers, self.calls = {}, []

    def __call__(self, argv, *, harness_dir, env):
        argv = list(argv)
        mode, exam, folder = argv[0], argv[argv.index('--exam') + 1], argv[argv.index('--folder') + 1]
        self.calls.append(types.SimpleNamespace(argv=argv, harness_dir=harness_dir, env=dict(env)))
        answer = self.answers.get((mode, exam), S.ABSENT if mode == S.FETCH else S.KEPT)
        if callable(answer):
            answer = answer(folder, exam)
        if isinstance(answer, BaseException):
            raise answer
        if isinstance(answer, tuple):
            return subprocess.CompletedProcess(argv, answer[0], stdout=answer[1])
        return answer_of(answer)

    def asked(self, mode=None):
        return [(c.argv[0], c.argv[c.argv.index('--exam') + 1]) for c in self.calls
                if mode is None or c.argv[0] == mode]


def copies_from(src, code=S.FETCHED, change=None):
    """A fetch answer that copies ``src/<exam>.json`` into the temp folder (``change`` may alter it)."""
    def fetch(folder, exam):
        raw = (pathlib.Path(src) / f'{exam}.json').read_bytes()
        if change is not None:
            data = json.loads(raw)
            change(data)
            raw = json.dumps(data).encode('utf-8')
        (pathlib.Path(folder) / f'{exam}.json').write_bytes(raw)
        return code
    return fetch


def frozen_source(tmp_path):
    """A folder holding both exams, frozen by a real lens run (what a bucket would hold)."""
    src = tmp_path / 'src'
    src.mkdir()
    run(cases_rich(), src)
    return src


def coach():
    return coach_one_pair([(CERTAIN, 'pass', 40)], [(CERTAIN, 'pass', 40)])


def result_of(lens, coach_result=None):
    return {'same': {'same': 1}, EH.HUMAN_LENS_KEY: lens,
            EH.COACH_GRADE_KEY: coach() if coach_result is None else coach_result}


def debug_shape():
    """The lens's DEBUG refusal shape (`lens_human_rows`), built by hand: no ids, no scores."""
    top = {k: None for k in ('engine_version', 'cases_read', 'not_decided', 'no_human_verdict',
                             'context_failed', 'context_failed_line')}
    exams = {n: {'exam': n, 'refusal': L.DEBUG_ON, 'status': f'refused: {L.DEBUG_ON}'} for n in L.EXAM_NAMES}
    return {**top, 'exams': exams}


@pytest.fixture
def store(monkeypatch):
    fake = FakeStore()
    monkeypatch.setattr(EH, 'spawn_store', fake)
    return fake


def bucket_args(tmp_path, freeze=True):
    return types.SimpleNamespace(workdir=str(tmp_path / 'work'), harness_dir=str(EVAL_DIR),
                                 human_lens_exam_bucket=BUCKET, human_lens_freeze=freeze,
                                 human_lens_exam_folder='')


def fixed(lines):
    assert all(line in EH.ALL_HOME_LINES for line in lines)
    return lines


def left_over(tmp_path):
    return list((tmp_path / 'work').glob('exams-*'))


# ── fetch ─────────────────────────────────────────────────────────────────────────────────────────────
def test_fetch_makes_a_private_folder_in_the_workdir_and_points_the_lens_at_it(store, tmp_path):
    args = bucket_args(tmp_path)
    home = EH.fetch(args)
    folder = pathlib.Path(home.folder)
    assert folder.parent == (tmp_path / 'work').resolve() or folder.parent == tmp_path / 'work'
    assert folder.name.startswith('exams-') and args.human_lens_exam_folder == home.folder
    if os.name == 'posix':
        assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert home.found == {n: S.ABSENT for n in L.EXAM_NAMES} and repr(home) == '<exam home>'
    assert store.asked() == [(S.FETCH, n) for n in L.EXAM_NAMES]
    for call, name in zip(store.calls, L.EXAM_NAMES):
        assert call.argv == [S.FETCH, '--bucket', BUCKET, '--exam', name, '--folder', home.folder]
        assert call.harness_dir == str(EVAL_DIR)
    EH.clean(home)
    assert not folder.exists() and left_over(tmp_path) == []
    EH.clean(None)                                                  # no bucket run: nothing to remove


BAD_LINES = [
    (0, b''), (0, b'\n'), (0, b'{"code": "absent"}'), (0, b'{"code":"absent"}\n'),
    (0, b'{"code": "absent"}\n{"code": "absent"}\n'), (0, b'{"code": "absent", "x": 1}\n'),
    (0, b'{"x": "absent"}\n'), (0, b'{"code": "kept"}\n'), (0, b'{"code": "nope"}\n'), (0, b'absent\n'),
    (0, b'["absent"]\n'), (0, b'{"code": 1}\n'), (0, b'{"code": "absent", "code": "absent"}\n'),
    (1, b'{"code": "absent"}\n'), (2, b'{"code": "absent"}\n'), (0, b'{"code": "fetch_failed"}\n'),
    (0, b'x' * 200), (0, '{"code": "absént"}\n'.encode()), (0, b'{"code": "absent"}\n' + PLANTED_ID.encode()),
]


@pytest.mark.parametrize('answer', [
    S.FETCH_FAILED, S.REFUSED, subprocess.TimeoutExpired(['x'], 120), OSError('Siti Aminah ' + PLANTED_ID),
    S.FETCHED,                                                      # "fetched" with no file there
    lambda folder, exam: (pathlib.Path(folder, f'{exam}.json').write_text('{}') and S.ABSENT),  # absent, a file
    *BAD_LINES])
def test_every_failed_fetch_stops_the_run_with_one_fixed_word_and_removes_the_folder(store, tmp_path, answer):
    store.answers[(S.FETCH, L.EXAM_1)] = answer
    args = bucket_args(tmp_path)
    with pytest.raises(EH.ExamFetchFailed) as caught:
        EH.fetch(args)
    assert caught.value.args == ('fetch_failed',) and str(caught.value) == 'fetch_failed'
    assert isinstance(caught.value, EH.ExamHomeError)
    assert store.asked() == [(S.FETCH, L.EXAM_1)]                   # exam-old never asked: never "absent"
    assert left_over(tmp_path) == [] and args.human_lens_exam_folder == ''


def test_a_failed_fetch_of_the_second_exam_also_stops_and_removes_the_first(store, tmp_path):
    src = frozen_source(tmp_path)
    store.answers[(S.FETCH, L.EXAM_1)] = copies_from(src)
    store.answers[(S.FETCH, L.EXAM_OLD)] = S.FETCH_FAILED
    with pytest.raises(EH.ExamFetchFailed):
        EH.fetch(bucket_args(tmp_path))
    assert store.asked() == [(S.FETCH, n) for n in L.EXAM_NAMES] and left_over(tmp_path) == []


def test_read_answer_takes_only_the_childs_one_fixed_line():
    for code in S.FETCH_CODES:
        assert EH.read_answer(answer_of(code).returncode, answer_of(code).stdout, EH.FETCH_ANSWERS) == code
    for code in S.PUT_CODES:
        assert EH.read_answer(answer_of(code).returncode, answer_of(code).stdout, EH.PUT_ANSWERS) == code
    for status, out in BAD_LINES:
        if (status, out) != (0, b'{"code": "kept"}\n') and (status, out) != (0, b'{"code": "fetch_failed"}\n'):
            assert EH.read_answer(status, out, EH.FETCH_ANSWERS | EH.PUT_ANSWERS) is None
    assert EH.read_answer(0, b'{"code": "fetched"}\n', EH.PUT_ANSWERS) is None     # a fetch code on a put
    assert EH.read_answer(0, S.result_line(S.KEPT), EH.PUT_ANSWERS) is None       # text, not bytes
    assert EH.read_answer(0, None, EH.PUT_ANSWERS) is None
    assert EH.read_answer(0, b'{"code": NaN}\n', EH.PUT_ANSWERS) is None
    assert EH.FETCH_ANSWERS == frozenset(S.FETCH_CODES) and EH.PUT_ANSWERS == frozenset(S.PUT_CODES)


# ── keep ──────────────────────────────────────────────────────────────────────────────────────────────
def test_without_the_freeze_flag_nothing_is_ever_uploaded(store, tmp_path):
    args = bucket_args(tmp_path, freeze=False)
    home = EH.fetch(args)
    result = result_of(run(cases_rich(), home.folder, freeze=False))      # an empty bucket: exam_missing
    assert {b['refusal'] for b in result[EH.HUMAN_LENS_KEY]['exams'].values()} == {L.EXAM_MISSING}
    assert EH.keep(home, args, result) == (result, [], False)
    frozen = result_of(run(cases_rich(), home.folder, freeze=True))       # even a frozen block and a new file
    assert EH.keep(home, args, frozen) == (frozen, [], False)
    args.human_lens_freeze = 'yes'                                        # only True itself is the flag
    assert EH.keep(home, args, frozen) == (frozen, [], False)
    assert EH.keep(None, bucket_args(tmp_path), frozen) == (frozen, [], False)   # not a bucket run
    assert store.asked(S.PUT) == []
    EH.clean(home)


def test_an_empty_bucket_and_a_freeze_run_put_both_with_the_blocks_own_values(store, tmp_path):
    args = bucket_args(tmp_path)
    home = EH.fetch(args)
    result = result_of(run(cases_rich(), home.folder))
    blocks = result[EH.HUMAN_LENS_KEY]['exams']
    assert all(blocks[n]['frozen'] is True and blocks[n]['refusal'] is None for n in L.EXAM_NAMES)
    kept, lines, failed = EH.keep(home, args, result)
    assert kept is result and failed is False
    assert fixed(lines) == [f'exam home: {n} frozen and kept in the bucket' for n in L.EXAM_NAMES]
    puts = [c.argv for c in store.calls if c.argv[0] == S.PUT]
    assert puts == [[S.PUT, '--bucket', BUCKET, '--exam', n, '--folder', home.folder,
                     '--digest', blocks[n]['digest'], '--size', str(blocks[n]['size']),
                     '--frozen-at', blocks[n]['frozen_at']] for n in L.EXAM_NAMES]
    assert all(len(blocks[n]['digest']) == 12 for n in L.EXAM_NAMES)
    EH.clean(home)


def test_a_fetched_exam_is_never_uploaded_only_the_new_one(store, tmp_path):
    src = frozen_source(tmp_path)
    store.answers[(S.FETCH, L.EXAM_1)] = copies_from(src)
    args = bucket_args(tmp_path)
    home = EH.fetch(args)
    assert home.found == {L.EXAM_1: S.FETCHED, L.EXAM_OLD: S.ABSENT}
    result = result_of(run(cases_rich(), home.folder))
    kept, lines, failed = EH.keep(home, args, result)
    assert store.asked(S.PUT) == [(S.PUT, L.EXAM_OLD)] and failed is False
    assert fixed(lines) == [EH.HOME_LINES[(L.EXAM_OLD, S.KEPT)]] and kept is result
    EH.clean(home)


def test_a_corrupt_stored_exam_is_refused_by_the_lens_and_never_replaced(store, tmp_path):
    src = frozen_source(tmp_path)

    def corrupt(data):
        data['digest'] = ('0' if data['digest'][0] != '0' else '1') + data['digest'][1:]
    store.answers[(S.FETCH, L.EXAM_1)] = copies_from(src, change=corrupt)
    args = bucket_args(tmp_path)
    home = EH.fetch(args)
    stored = pathlib.Path(home.folder, 'exam-1.json').read_bytes()
    result = result_of(run(cases_rich(), home.folder))
    assert result[EH.HUMAN_LENS_KEY]['exams'][L.EXAM_1]['refusal'] == L.DIGEST_MISMATCH
    kept, lines, failed = EH.keep(home, args, result)
    assert (S.PUT, L.EXAM_1) not in store.asked(S.PUT)
    assert pathlib.Path(home.folder, 'exam-1.json').read_bytes() == stored
    assert fixed(lines) == [EH.HOME_LINES[(L.EXAM_OLD, S.KEPT)]] and failed is False
    EH.clean(home)


def test_a_lost_race_withholds_that_score_prints_a_fixed_line_and_is_not_a_failure(store, tmp_path):
    store.answers[(S.PUT, L.EXAM_1)] = S.FROZEN_ELSEWHERE
    args = bucket_args(tmp_path)
    home = EH.fetch(args)
    result = result_of(run(cases_rich(), home.folder))
    kept, lines, failed = EH.keep(home, args, result)
    lens = kept[EH.HUMAN_LENS_KEY]
    assert failed is False and LS.human_lens_result_allowed(lens)
    assert lens['exams'][L.EXAM_1] == L.refused_exam(L.EXAM_1, lens['engine_version'], L.FROZEN_ELSEWHERE)
    assert lens['exams'][L.EXAM_OLD] == result[EH.HUMAN_LENS_KEY]['exams'][L.EXAM_OLD]
    assert result[EH.HUMAN_LENS_KEY]['exams'][L.EXAM_1]['refusal'] is None        # the input is not changed
    assert fixed(lines) == ['exam home: exam-1 was frozen by another run first; the next run sits that one',
                            EH.HOME_LINES[(L.EXAM_OLD, S.KEPT)]]
    report, report_failed = R.lens_coach_report(lens, kept[EH.COACH_GRADE_KEY])
    assert report_failed is False and 'another run froze this exam first' in '\n'.join(report)
    EH.clean(home)


@pytest.mark.parametrize('answer', [S.PUT_FAILED, S.NOT_VERIFIED, S.REFUSED, subprocess.TimeoutExpired(['x'], 120),
                                    OSError('Siti Aminah ' + PLANTED_ID), (0, S.result_line(S.KEPT).encode() * 2),
                                    (1, S.result_line(S.KEPT).encode()), (0, b'{"code": "fetched"}\n'),
                                    (0, b'{"code": "kept", "id": 987654321}\n'), (0, b'')])
def test_every_failed_put_is_not_kept_and_blocking(store, tmp_path, answer):
    store.answers[(S.PUT, L.EXAM_1)] = answer
    args = bucket_args(tmp_path)
    home = EH.fetch(args)
    result = result_of(run(cases_rich(), home.folder))
    kept, lines, failed = EH.keep(home, args, result)
    lens = kept[EH.HUMAN_LENS_KEY]
    assert failed is True and LS.human_lens_result_allowed(lens)
    assert lens['exams'][L.EXAM_1] == L.refused_exam(L.EXAM_1, lens['engine_version'], L.NOT_KEPT)
    assert fixed(lines)[0] == 'exam home: exam-1 NOT kept in the bucket. BLOCKING. Run again with --human-lens-freeze.'
    assert R.lens_coach_report(lens, kept[EH.COACH_GRADE_KEY])[1] is False      # the report: a plain refusal
    EH.clean(home)


def test_the_error_shape_and_the_debug_shape_upload_nothing(store, tmp_path):
    assert LS.human_lens_result_allowed(debug_shape())
    args = bucket_args(tmp_path)
    for lens in ({'error': LS.SCHEMA}, debug_shape(), {'exams': 'Siti Aminah'}, None):
        home = EH.fetch(args)
        result = result_of(lens)
        assert EH.keep(home, args, result) == (result, [], False)        # no new file: nothing to say
        pathlib.Path(home.folder, 'exam-1.json').write_text('{}', encoding='utf-8')
        kept, lines, failed = EH.keep(home, args, result)
        assert kept is result and failed is True
        assert fixed(lines) == [EH.HOME_LINES[(L.EXAM_1, L.NOT_KEPT)]]
        EH.clean(home)
    assert store.asked(S.PUT) == []


def test_a_coach_error_uploads_nothing_and_blocks(store, tmp_path):
    args = bucket_args(tmp_path)
    home = EH.fetch(args)
    result = result_of(run(cases_rich(), home.folder), {'error': 'schema'})
    kept, lines, failed = EH.keep(home, args, result)
    assert store.asked(S.PUT) == [] and failed is True
    assert fixed(lines) == [EH.HOME_LINES[(n, L.NOT_KEPT)] for n in L.EXAM_NAMES]
    assert {kept[EH.HUMAN_LENS_KEY]['exams'][n]['refusal'] for n in L.EXAM_NAMES} == {L.NOT_KEPT}
    EH.clean(home)


def test_a_block_that_says_frozen_with_no_file_is_not_kept(store, tmp_path):
    args = bucket_args(tmp_path)
    home = EH.fetch(args)
    result = result_of(run(cases_rich(), home.folder))
    os.remove(os.path.join(home.folder, 'exam-1.json'))
    kept, lines, failed = EH.keep(home, args, result)
    assert store.asked(S.PUT) == [(S.PUT, L.EXAM_OLD)] and failed is True
    assert fixed(lines) == [EH.HOME_LINES[(L.EXAM_1, L.NOT_KEPT)], EH.HOME_LINES[(L.EXAM_OLD, S.KEPT)]]
    EH.clean(home)


# ── the child's start, its environment and the fixed words ───────────────────────────────────────────
def test_the_store_env_carries_no_database_key_or_salt_and_passes_the_guard(store, tmp_path):
    secrets = {guards.DB_ENV: 'postgres://u:pw@db.example/x', parent.FINGERPRINT_KEY_ENV: 'k' * 32,
               scrub.SALT_ENV: 's' * 32, 'PATH': '/usr/bin:/bin', 'GOOGLE_APPLICATION_CREDENTIALS': '/x.json'}
    home = EH.fetch(bucket_args(tmp_path), env=secrets)
    for call in store.calls:
        assert tuple(sorted(call.env)) == tuple(sorted(S.STORE_ENV_NAMES))
        assert call.env == S.store_env(secrets, str(EVAL_DIR))
        guards.check_environment(call.env)                          # the real guard: no exception
        assert not set(call.env) & {guards.DB_ENV, parent.FINGERPRINT_KEY_ENV, scrub.SALT_ENV}
        assert not {secrets[k] for k in (guards.DB_ENV, parent.FINGERPRINT_KEY_ENV, scrub.SALT_ENV)} \
            & set(call.env.values())
    EH.clean(home)


def test_the_store_child_is_started_with_no_shell_no_stdin_no_stderr_and_a_limit(monkeypatch):
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout=b'')
    monkeypatch.setattr(EH.subprocess, 'run', fake_run)
    EH.spawn_store([S.FETCH, '--exam', L.EXAM_1], harness_dir='/h', env={'PATH': '/bin'})
    assert seen == [([sys.executable, '-P', '-m', 'replay.exam_store', S.FETCH, '--exam', L.EXAM_1],
                     {'cwd': '/h', 'env': {'PATH': '/bin'}, 'shell': False, 'stdin': subprocess.DEVNULL,
                      'stdout': subprocess.PIPE, 'stderr': subprocess.DEVNULL, 'timeout': 120, 'check': False})]


@pytest.mark.skipif(sys.version_info < (3, 11), reason='-P is Python 3.11+')
def test_the_real_child_refuses_a_bad_request_in_its_one_line(tmp_path):
    assert EH.ask_store([], EH.FETCH_ANSWERS, harness_dir=str(EVAL_DIR), env=os.environ) == S.REFUSED
    assert EH.ask_store([], EH.PUT_ANSWERS, harness_dir=str(EVAL_DIR), env=os.environ) == S.REFUSED


def test_every_line_is_fixed_and_the_names_agree_with_the_parent_and_the_store():
    assert EH.ALL_HOME_LINES == frozenset(EH.HOME_LINES.values()) and len(EH.ALL_HOME_LINES) == 6
    assert EH.HOME_LINES[(L.EXAM_1, S.KEPT)] == 'exam home: exam-1 frozen and kept in the bucket'
    assert EH.HOME_LINES[(L.EXAM_1, L.FROZEN_ELSEWHERE)] == \
        'exam home: exam-1 was frozen by another run first; the next run sits that one'
    assert EH.HOME_LINES[(L.EXAM_1, L.NOT_KEPT)] == \
        'exam home: exam-1 NOT kept in the bucket. BLOCKING. Run again with --human-lens-freeze.'
    assert (EH.HUMAN_LENS_KEY, EH.COACH_GRADE_KEY) == (parent.HUMAN_LENS_KEY, parent.COACH_GRADE_KEY)
    assert EH.bucket_name_ok is S.bucket_name_ok and EH.store_env is S.store_env
    assert (EH.FROZEN_ELSEWHERE, EH.KEPT) == (S.FROZEN_ELSEWHERE, S.KEPT)
    assert {L.FROZEN_ELSEWHERE, L.NOT_KEPT} <= set(L.PLAIN_REFUSALS)
    assert EH.STORE_TIMEOUT_S == 120 and EH.ExamFetchFailed().args == ('fetch_failed',)
    source = pathlib.Path(EH.__file__).read_text(encoding='utf-8')
    assert 'print(' not in source and 'logging' not in source and 'environ.get(' not in source
