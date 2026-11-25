"""LL6 phase P2b - the EXAM HOME: the parent's glue to the store child (`exam_store`), used only with
`--human-lens-exam-bucket`. Standard library only. It never speaks to the network itself: every fetch
and every upload is ONE store child (`python -P -m replay.exam_store fetch|put ...`), started with no
shell, the same Python, a fixed folder, the environment `exam_store.store_env` builds from nothing
(checked by `guards.check_environment`), no stdin, stderr to /dev/null and a 120 s limit (the child is
killed when it runs over).

THE FLOW (`parent.main`):
1. `fetch` makes a PRIVATE temp folder (``tempfile.mkdtemp``, 0700) inside the workdir and asks the store
   child to fetch exam-1 and exam-old into it. Each must answer ``fetched`` (and the file is there) or
   ``absent`` (and it is not). Anything else - a failure code, ``refused``, a line not in the one fixed
   form, a timeout - raises `ExamFetchFailed` (exit 3) before any replay child starts: never "treat it
   as absent and freeze a new one". The lens then reads its exams from that folder.
2. `keep`, after the run, and ONLY on a `--human-lens-freeze` run: an exam is uploaded only when it was
   ``absent`` at fetch, its file is in the temp folder now, and the CHECKED lens result (the schema
   again) shows it frozen with no refusal. The child gets the block's own digest (12), size and frozen
   time; it proves the file before it sends anything. ``kept`` = the score stands. ``frozen_elsewhere``
   = another run won the race: the block becomes that refusal (no score), exit 0. Every other answer
   (or a new exam whose block is a refusal, or a coach error) = the block becomes ``not_kept`` and the
   run exits 4. An exam that was ``fetched`` is never uploaded; a lens result that fails its check, is
   an error or is the DEBUG refusal uploads nothing.
3. `clean` removes the temp folder (``finally``: on success, exit 3, exit 4, or a run that raised).

WHAT IS PRINTED: only the fixed lines in `ALL_HOME_LINES`, by `parent.main`. Never the bucket name, a
child's output, an exception message, an id or a path. `ExamFetchFailed` carries one fixed word.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

from . import exam_store, guards, lens_human, lens_result_schema, report_lens
from .exam_store import bucket_name_ok, store_env

__all__ = ['bucket_name_ok', 'store_env', 'fetch', 'keep', 'clean', 'ExamFetchFailed', 'ExamHomeError']

#: The result's two keys (`parent.HUMAN_LENS_KEY`, `parent.COACH_GRADE_KEY`; a test holds them equal).
HUMAN_LENS_KEY, COACH_GRADE_KEY = 'human_lens', 'coach_grade'
#: The store child, run as a module of the harness's `replay` package.
STORE_MODULE = 'replay.exam_store'
#: Seconds the parent waits for one store child; then it is killed and the answer is a failure.
STORE_TIMEOUT_S = 120
#: The most a store child's answer may hold (the longest fixed line is far shorter).
MAX_ANSWER_BYTES = 64
#: The codes each subcommand may answer (the child's own sets, never retyped), and the fetch answers
#: that let the run go on. ``refused`` and every failure code are in the sets and are still failures.
FETCH_ANSWERS = frozenset(exam_store.FETCH_CODES)
PUT_ANSWERS = frozenset(exam_store.PUT_CODES)
FETCH_OK = frozenset({exam_store.FETCHED, exam_store.ABSENT})
KEPT, FROZEN_ELSEWHERE, NOT_KEPT = exam_store.KEPT, lens_human.FROZEN_ELSEWHERE, lens_human.NOT_KEPT

#: The ONLY lines the exam home prints, one per (exam, outcome). Fixed words and the exam's own name.
_LINE_TEXT = {
    KEPT: 'exam home: {exam} frozen and kept in the bucket',
    FROZEN_ELSEWHERE: 'exam home: {exam} was frozen by another run first; the next run sits that one',
    NOT_KEPT: 'exam home: {exam} NOT kept in the bucket. BLOCKING. Run again with --human-lens-freeze.',
}
HOME_LINES = {(name, code): text.format(exam=name)
              for name in lens_human.EXAM_NAMES for code, text in _LINE_TEXT.items()}
ALL_HOME_LINES = frozenset(HOME_LINES.values())


class ExamHomeError(Exception):
    """A fixed refusal of the exam home: one fixed word, never a value, a path or a child's output."""
    WORD = 'exam_home'

    def __init__(self):
        super().__init__(self.WORD)


class ExamFetchFailed(ExamHomeError):
    """The exams could not be fetched: the run stops (exit 3) before any replay child starts."""
    WORD = 'fetch_failed'


class ExamHome:
    """The run's temp folder and what the fetch found there: ``{exam: 'fetched' | 'absent'}``."""
    __slots__ = ('folder', 'found')

    def __init__(self, folder):
        self.folder, self.found = folder, {}

    def __repr__(self):
        return '<exam home>'


# ── the store child ───────────────────────────────────────────────────────────────────────────────────
def store_command(argv) -> list:
    """The store child's command: this same Python, ``-P`` (no script or working folder on the path)."""
    return [sys.executable, '-P', '-m', STORE_MODULE, *argv]


def spawn_store(argv, *, harness_dir, env):
    """Run ONE store child to its end; ``subprocess.TimeoutExpired`` (the child killed) after
    `STORE_TIMEOUT_S`. Its stdout is captured; nothing else of it is kept."""
    return subprocess.run(store_command(argv), cwd=harness_dir, env=env, shell=False,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          timeout=STORE_TIMEOUT_S, check=False)


def _once_each(pairs):
    if len({k for k, _v in pairs}) != len(pairs):
        raise ValueError('a key repeats')
    return dict(pairs)


def _no_constant(_text):
    raise ValueError('not plain JSON')


def read_answer(returncode, stdout, allowed):
    """The child's code, or None. Accepted ONLY: stdout is exactly one line, ``{"code": "<code>"}`` in the
    child's own form (`exam_store.result_line`), one key, the code in ``allowed``, and the exit status the
    child gives that code (0 for a good code, else 1). Anything else - more or less text, another key,
    an unknown code, a status that does not match - is None."""
    if type(stdout) is not bytes or len(stdout) > MAX_ANSWER_BYTES:
        return None
    try:
        text = stdout.decode('ascii')
        data = json.loads(text, object_pairs_hook=_once_each, parse_constant=_no_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    if type(data) is not dict or set(data) != {exam_store.RESULT_KEY}:
        return None
    code = data[exam_store.RESULT_KEY]
    if type(code) is not str or code not in allowed or text != exam_store.result_line(code):
        return None
    if returncode != (0 if code in exam_store.GOOD_CODES else 1):
        return None
    return code


def ask_store(argv, allowed, *, harness_dir, env):
    """ONE store child's code from ``allowed``, or None for every failure: a refused environment, a start
    that failed, a timeout, an answer `read_answer` does not accept. Never a message."""
    try:
        child_env = store_env(env, harness_dir)
        guards.check_environment(child_env)
        done = spawn_store(argv, harness_dir=harness_dir, env=child_env)
        return read_answer(done.returncode, done.stdout, allowed)
    except Exception:       # a timeout (the child was killed), OSError, a refused env: one fixed failure
        return None


def _harness_dir(args) -> str:
    return os.path.abspath(args.harness_dir)


def _exam_path(home, name) -> str:
    return os.path.join(home.folder, f'{name}.json')


def _file_says(home, name):
    """FETCHED when the exam is a regular file (not a link), ABSENT when nothing has its name, else None."""
    path = _exam_path(home, name)
    if not os.path.lexists(path):
        return exam_store.ABSENT
    return exam_store.FETCHED if os.path.isfile(path) and not os.path.islink(path) else None


# ── the three steps ───────────────────────────────────────────────────────────────────────────────────
def fetch(args, *, env=None) -> ExamHome:
    """Make the run's private temp folder in the workdir, fetch both exams into it and point
    ``args.human_lens_exam_folder`` at it. `ExamFetchFailed` (the folder removed) on any failure."""
    env = os.environ if env is None else env
    workdir = os.path.abspath(args.workdir)
    os.makedirs(workdir, exist_ok=True)
    home = ExamHome(tempfile.mkdtemp(prefix='exams-', dir=workdir))
    done = False
    try:
        for name in lens_human.EXAM_NAMES:
            code = ask_store([exam_store.FETCH, '--bucket', args.human_lens_exam_bucket, '--exam', name,
                              '--folder', home.folder], FETCH_ANSWERS, harness_dir=_harness_dir(args), env=env)
            if code not in FETCH_OK or _file_says(home, name) != code:
                raise ExamFetchFailed()
            home.found[name] = code
        done = True
    finally:
        if not done:
            clean(home)
    args.human_lens_exam_folder = home.folder
    return home


def _put(home, args, name, block, env) -> str:
    code = ask_store([exam_store.PUT, '--bucket', args.human_lens_exam_bucket, '--exam', name,
                      '--folder', home.folder, '--digest', block['digest'], '--size', str(block['size']),
                      '--frozen-at', block['frozen_at']], PUT_ANSWERS, harness_dir=_harness_dir(args), env=env)
    return code if code in (KEPT, FROZEN_ELSEWHERE) else NOT_KEPT


def _debug_shape(data) -> bool:
    return any(frozenset(block) == lens_result_schema.EXAM_DEBUG_KEYS for block in data['exams'].values())


def keep(home, args, result, *, env=None):
    """``(result, lines, failed)`` after the run. Returns at once, changing nothing, unless this is a
    bucket run (``home``) with `--human-lens-freeze`. Then uploads each NEW exam (``absent`` at fetch, its
    file there now, its checked block frozen with no refusal) and turns each answer into the block, a
    fixed line (`HOME_LINES`) and ``failed`` (exit 4: an exam frozen here and not kept)."""
    if home is None or getattr(args, 'human_lens_freeze', False) is not True:
        return result, [], False
    env = os.environ if env is None else env
    absent = [n for n in lens_human.EXAM_NAMES if home.found.get(n) == exam_store.ABSENT]
    lens = result.get(HUMAN_LENS_KEY) if isinstance(result, dict) else None
    lens_error, data = report_lens.lens_result_checked(lens)
    if lens_error is not None or _debug_shape(data):     # no exam block to trust: upload nothing
        names = [n for n in absent if os.path.lexists(_exam_path(home, n))]
        return result, [HOME_LINES[(n, NOT_KEPT)] for n in names], bool(names)
    coach_error, _coach = report_lens.coach_result_checked(result.get(COACH_GRADE_KEY))
    lines, failed, changed = [], False, False
    for name in absent:
        block, new_file = data['exams'][name], os.path.lexists(_exam_path(home, name))
        if not new_file and block['frozen'] is not True:
            continue                                     # nothing was frozen: nothing to keep
        if new_file and block['frozen'] is True and block['refusal'] is None and coach_error is None:
            code = _put(home, args, name, block, env)
        else:
            code = NOT_KEPT
        lines.append(HOME_LINES[(name, code)])
        if code == KEPT:
            continue
        failed = failed or code == NOT_KEPT
        data['exams'][name] = lens_human.refused_exam(name, data['engine_version'], code)
        changed = True
    if not changed:
        return result, lines, failed
    if not lens_result_schema.human_lens_result_allowed(data):
        data, failed = {'error': lens_result_schema.SCHEMA}, True
    return {**result, HUMAN_LENS_KEY: data}, lines, failed


def clean(home) -> None:
    """Remove the run's temp folder and everything in it (links are removed, never followed)."""
    if home is not None:
        shutil.rmtree(home.folder, ignore_errors=True)
