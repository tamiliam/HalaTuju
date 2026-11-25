"""The replay's parent process (design 3.5): the job's entry point, `python -m replay.parent`.

1. Preflight, BEFORE Django is set up (its setup would query): no forbidden key in the environment; the
   `replay_ro` URL on the session pooler port 5432.
2. Opens ONE `REPEATABLE READ, READ ONLY` transaction (never committed) and exports its snapshot.
   `--counts-only` prints the case counts and stops here (R1's first live step).
3. Deletes the three side files (`old.jsonl`, `new.jsonl`, `new_again.jsonl`) an earlier run left in the
   workdir, then starts three children - old, new, new_again - each in its own venv and tree with a
   MINIMAL environment (the replay URL, the path, the settings module, the run's scrub salt; nothing
   else), each joining the snapshot. The JOIN HANDSHAKE: the parent waits until each child has written
   `joined` (or exited, or is killed after `JOIN_TIMEOUT_S`). Its transaction has read NO table yet, so
   the wait holds no table lock (a migration's ALTER is never queued behind it). Only then does it count
   the cases (same snapshot) and roll its transaction back at once, so it is not held open while the
   engines run.
4. Waits for the children. On any error or timeout once a child has started, every child still running
   is killed.
5. Compares: per record `same`, `differs` (old against new), `could_not_run` (either side raised) or
   `noise` (new against new_again differ: the engine is not deterministic; left out of A/B). The A/B
   split by the ruling catalogue is R2.
Everything printed goes through the scrubber; an error is printed by class name only. One exception:
the fixed line `HUMAN_LENS_ON_LINE` (a constant, no data in it; the scrubber has no code for it).

THE HUMAN LENS (LL5 phase C1), OFF by default. Only `--human-lens` turns it on; then ONLY the `new` child
gets the lens names (`human_lens_env`: the switch, the exam folder, the freeze flag, and
`REPLAY_FINGERPRINT_KEY` copied from this process's environment). Off, every child's environment is
exactly as before and the result has no new key. The `new` child writes the lens's counts and codes to
`human_lens.json` in the workdir; `run_replay` returns them under the one key ``human_lens``. They are
not printed in this phase. SAFETY (phase C1c): `--human-lens` without `--human-lens-exam-folder` is an
argument error; so are `--human-lens` with `--counts-only`, and a relative exam folder (the child's own
`os.path.isabs` rule; the child still refuses it too, as `folder_not_absolute`); the file is checked
again here against the allow-list (`lens_result_schema`); a lens
result that is an error (``{"error": ...}``) makes `main` exit `HUMAN_LENS_FAILED_EXIT` (4), never 0.

THE COACH GRADE (LL5 phase C2), under the SAME switch, with no new environment name (`child_env` is
unchanged). The `new` child also writes the coach grade's report to `coach_grade.json` in the workdir.
This process deletes an old copy before the run, reads it after the children exit, checks it again
against its own allow-list (`coach_result_schema`) and returns it under the one more key ``coach_grade``.
The same error rules as the lens; an error in either result makes `main` exit 4. `run_replay` prints
neither result.

THE LL5 BLOCK (LL5 phase C2d). With `--human-lens` only, once `run_replay` has printed its JSON lines and
returned, `main` prints the two results as `report_lens` renders them (the same allow-list re-check and
label tables as the markdown report; this file formats nothing from them) between the fixed lines
`LENS_REPORT_START` and `LENS_REPORT_END`, in ONE print to stdout, the stream of the JSON lines. A block
that holds a failure (either result failed its check), or a render that raised one of
`report_lens.RENDER_ERRORS` (then the block is only `report_lens.RENDER_FAILED_LINE`), makes `main` exit 4
even when the run would exit 0: a report that cannot be shown is not a pass. No block with the lens off
(the output is as before), on the fatal path (exit 3) or on an argument error (exit 2, which
`--counts-only` with `--human-lens` is): there is no result to show. Any other error in the render is
the fatal path.

THE EXAM HOME IN A BUCKET (LL6). `--human-lens-exam-bucket NAME` (a CLI argument only; never with
`--human-lens-exam-folder`) keeps the exams in one private bucket instead of a folder. `main` asks
`exam_home.fetch` for them (a private temp folder in the workdir, set as the exam folder; any failure is
the fatal path, exit 3, before any child starts), runs as before, then `exam_home.keep` uploads a NEWLY
frozen exam, ONLY with `--human-lens-freeze`; its fixed lines (`exam_home.ALL_HOME_LINES`) follow the
LL5 block, and an exam frozen here but not kept exits 4. The temp folder is removed in a ``finally``.
Without the flag nothing of this runs and the output is as before.
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict

from . import coach_result_schema, exam_home, guards, lens_result_schema, netguard, report_lens
from . import scrub as scrub_module
from .child import (COACH_GRADE_FILE, HUMAN_LENS_ENV, HUMAN_LENS_FILE, HUMAN_LENS_FOLDER_ENV,
                    HUMAN_LENS_FREEZE_ENV, parse_instant, setup_django)
from .scrub import count_dropped, error_record, scrub

RUN_SIDES = ('old', 'new', 'new_again')
TREE_OF = {'old': 'old', 'new': 'new', 'new_again': 'new'}
#: The derived fingerprint key's variable (`replay.settings`); it reaches a child only with the lens on.
FINGERPRINT_KEY_ENV = 'REPLAY_FINGERPRINT_KEY'
#: The one side that runs the human lens: one freeze at most, and the key reaches one child only.
HUMAN_LENS_SIDE = 'new'
#: The result's one new key, present only with the lens on.
HUMAN_LENS_KEY = 'human_lens'
#: The coach grade's key (LL5 phase C2), present only with the lens switch on.
COACH_GRADE_KEY = 'coach_grade'
#: The run's one line saying the lens is on: a fixed text, never the key or a folder.
HUMAN_LENS_ON_LINE = '{"event": "human_lens_on"}'
#: ``main``'s exit code when the lens result is an error. 0 is a finished run, 2 an argument error
#: (argparse), 3 a fatal error; 4 is new and means only this.
HUMAN_LENS_FAILED_EXIT = 4
#: The two fixed lines around the LL5 block (`lens_report_block`); nothing else is printed between them.
LENS_REPORT_START = '=== LL5 lens report start ==='
LENS_REPORT_END = '=== LL5 lens report end ==='
CHILD_TIMEOUT_S = 3 * 60 * 60
#: How long the parent waits for every child to join; below the parent's idle-in-transaction limit.
JOIN_TIMEOUT_S = 10 * 60


def emit(obj, out=print):
    out(json.dumps(scrub(obj), sort_keys=True))


def case_counts():
    """How many cases each family holds (design 3.1). Counts only."""
    from apps.courses.models import StudentProfile
    from apps.scholarship.maintenance_scope import PAYABLE_STATUSES
    from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, Sponsor
    profiles = StudentProfile.objects
    return {
        'applications': ScholarshipApplication.objects.count(),
        'documents_live': ApplicantDocument.objects.filter(superseded_at__isnull=True).count(),
        'payable': ScholarshipApplication.objects.filter(status__in=PAYABLE_STATUSES).count(),
        'profiles_spm': profiles.exclude(grades__isnull=True).exclude(grades={}).count(),
        'profiles_stpm': profiles.exclude(stpm_grades__isnull=True).exclude(stpm_grades={}).count(),
        'sponsors': Sponsor.objects.count(),
    }


def child_env(env, side_root, harness_dir, lens=None):
    """The child's WHOLE environment: nothing from the parent but the replay URL, the path and the run's
    scrub salt (so every side hashes alike). ``lens`` (`human_lens_env`, the lens side only) adds the
    lens names; None (the default) adds nothing."""
    out = {
        'PATH': env.get('PATH', '/usr/bin:/bin'),
        guards.DB_ENV: env.get(guards.DB_ENV, ''),
        scrub_module.SALT_ENV: env.get(scrub_module.SALT_ENV, ''),
        'PYTHONPATH': os.pathsep.join([harness_dir, os.path.join(side_root, 'halatuju_api')]),
        'DJANGO_SETTINGS_MODULE': 'replay.settings',
        'PYTHONDONTWRITEBYTECODE': '1',
        'TZ': 'UTC',
    }
    if lens is not None:
        out.update(lens)
    return out


def human_lens_env(args, env, side):
    """The lens names for ``side``'s child, or None: the lens is off (no `--human-lens`), or this is not
    the lens side. The key is copied from ``env`` ('' when absent: the lens then answers `key_blank`)."""
    if not getattr(args, 'human_lens', False) or side != HUMAN_LENS_SIDE:
        return None
    return {HUMAN_LENS_ENV: '1', HUMAN_LENS_FOLDER_ENV: args.human_lens_exam_folder,
            HUMAN_LENS_FREEZE_ENV: '1' if args.human_lens_freeze else '0',
            FINGERPRINT_KEY_ENV: env.get(FINGERPRINT_KEY_ENV, '')}


def child_command(args, side, snapshot, out_path):
    tree = TREE_OF[side]
    cmd = [getattr(args, f'{tree}_python'), '-m', 'replay.child', '--side', side,
           '--instant', args.instant, '--months', args.months, '--out', out_path]
    if snapshot:
        cmd += ['--snapshot', snapshot]
    if args.engines:
        cmd += ['--engines', args.engines]
    return cmd


def spawn_child(args, side, snapshot, out_path, env):
    """Start one child; its stdout and stderr are discarded (it writes only to ``out_path``)."""
    root = getattr(args, f'{TREE_OF[side]}_root')
    return subprocess.Popen(child_command(args, side, snapshot, out_path), cwd=os.path.join(root, 'halatuju_api'),
                            env=child_env(env, root, args.harness_dir, human_lens_env(args, env, side)),
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def read_side(path):
    """({(engine, key): record}, [side events]) from one child's output file."""
    records, events = {}, []
    if not os.path.exists(path):
        return records, [{'event': 'no_output'}]
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            row = json.loads(line)
            if 'record' in row:
                records[(row['engine'], json.dumps(row['key']))] = row['record']
            else:
                events.append(row)
    return records, events


def _is_error(record):
    return isinstance(record, dict) and 'error' in record


def answer(record):
    """The engine's answer: the record without `facts` (the case facts the rulings read, which are never
    compared: a tree that lacks a helper reads a fact as None without the engine changing)."""
    if isinstance(record, dict) and 'facts' in record:
        return {k: v for k, v in record.items() if k != 'facts'}
    return record


def classify(old, new, again):
    if old is None or new is None or again is None:
        return 'could_not_run'
    if new != again:
        return 'noise'
    if _is_error(old) or _is_error(new):
        return 'could_not_run'
    return 'same' if answer(old) == answer(new) else 'differs'


def changed_fields(old, new):
    old, new = answer(old), answer(new)
    if isinstance(old, dict) and isinstance(new, dict):
        return sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
    return ['value']


def explain(engine, old, new):
    """A `differs` record as ('expected', ruling ids) - class A - or ('unexplained', ids) - class B."""
    from .rulings import classify_difference
    return classify_difference(engine, old, new)


def compare_sides(sides):
    """[(engine, key, outcome, old, new)] over every key any side produced, sorted."""
    keys = sorted(set().union(*(set(s) for s in sides.values())))
    rows = []
    for k in keys:
        old, new, again = (sides[s].get(k) for s in RUN_SIDES)
        rows.append((k[0], json.loads(k[1]), classify(old, new, again), old, new))
    return rows


def _failure(record):
    """`{"error": "<ClassName>"}` for a side that raised, `{"error": "Missing"}` for one with no record."""
    if record is None:
        return {'error': 'Missing'}
    return {'error': record['error']} if _is_error(record) else None


def report(rows, out=print):
    """One line per record that is not `same`, then totals per engine. Values are already scrubbed."""
    totals = defaultdict(Counter)
    for engine, key, outcome, old, new in rows:
        totals[engine][outcome] += 1
        if outcome == 'same':
            continue
        line = {'engine': engine, 'key': key, 'outcome': outcome}
        if outcome == 'differs':
            fields = changed_fields(old, new)
            klass, ids = explain(engine, old, new)
            totals[engine][klass] += 1
            line.update(fields=fields, **{'class': klass, 'rulings': ids},
                        old={f: (old.get(f) if isinstance(old, dict) else old) for f in fields},
                        new={f: (new.get(f) if isinstance(new, dict) else new) for f in fields})
        elif outcome == 'could_not_run':
            line.update(old=_failure(old), new=_failure(new))
        emit(line, out)
    for engine in sorted(totals):
        emit({'event': 'totals', 'engine': engine, **totals[engine]}, out)
    return totals


def _commit(root):
    try:
        with open(os.path.join(root, 'COMMIT'), encoding='utf-8') as fh:
            return fh.read().strip()[:40]
    except OSError:
        return 'unknown'


#: ``parse_args``'s own refusals: fixed words, never a value. The ONLY texts `_QuietParser` lets through.
MONTHS_NOT_TWO = '--months takes exactly two months'
LENS_FLAGS_NEED_SWITCH = '--human-lens-freeze, --human-lens-exam-folder and --human-lens-exam-bucket need --human-lens'
ONE_EXAM_HOME = 'use one of --human-lens-exam-folder or --human-lens-exam-bucket'
SWITCH_NEEDS_EXAM_HOME = '--human-lens needs --human-lens-exam-folder or --human-lens-exam-bucket'
COUNTS_ONLY_WITH_LENS = '--counts-only and --human-lens cannot be used together'
FOLDER_ARG_NOT_ABSOLUTE = '--human-lens-exam-folder must be an absolute path'
BUCKET_NOT_PLAIN = '--human-lens-exam-bucket is not a plain bucket name'
OWN_ARG_ERRORS = frozenset({MONTHS_NOT_TWO, LENS_FLAGS_NEED_SWITCH, ONE_EXAM_HOME, SWITCH_NEEDS_EXAM_HOME,
                            COUNTS_ONLY_WITH_LENS, FOLDER_ARG_NOT_ABSOLUTE, BUCKET_NOT_PLAIN})
#: Every other argument error (argparse's own: unrecognized arguments, ambiguous option, expected one
#: argument, invalid value, missing required ones, and whatever a later Python adds) can carry what was
#: typed, so it is replaced by these fixed words.
ARGS_WITHHELD = 'bad arguments (details withheld)'


class _QuietParser(argparse.ArgumentParser):
    """An allow-list on argument errors: one of `OWN_ARG_ERRORS` passes unchanged, anything else becomes
    `ARGS_WITHHELD`. Then as argparse: the usage line and ``prog: error: <words>`` on stderr, exit 2."""

    def error(self, message):
        super().error(message if message in OWN_ARG_ERRORS else ARGS_WITHHELD)


def parse_args(argv):
    ap = _QuietParser(description='The A5 replay: old engines against new, on one snapshot.')
    ap.add_argument('--instant', required=True, help='the pinned clock, ISO with a timezone')
    ap.add_argument('--months', required=True, help='two pinned payment months, YYYY-MM,YYYY-MM')
    ap.add_argument('--old-root', default='/replay/old')
    ap.add_argument('--new-root', default='/replay/new')
    ap.add_argument('--old-python', default='/replay/old/venv/bin/python')
    ap.add_argument('--new-python', default='/replay/new/venv/bin/python')
    ap.add_argument('--harness-dir', default='/replay/harness')
    ap.add_argument('--workdir', default='/tmp/replay')
    ap.add_argument('--engines', default='')
    ap.add_argument('--counts-only', action='store_true')
    ap.add_argument('--human-lens', action='store_true', help='run the human lens (off by default)')
    ap.add_argument('--human-lens-exam-folder', default='', help='the exam folder: absolute, outside git')
    ap.add_argument('--human-lens-freeze', action='store_true', help='freeze a missing exam file')
    ap.add_argument('--human-lens-exam-bucket', default=None, metavar='NAME',
                    help='the exam home: a private Cloud Storage bucket (LL6), instead of an exam folder')
    args = ap.parse_args(argv)
    parse_instant(args.instant)
    if len(args.months.split(',')) != 2:
        ap.error(MONTHS_NOT_TWO)
    folder, bucket = args.human_lens_exam_folder, args.human_lens_exam_bucket   # bucket: None = not given
    if (args.human_lens_freeze or folder or bucket is not None) and not args.human_lens:
        ap.error(LENS_FLAGS_NEED_SWITCH)
    if folder and bucket is not None:                           # one exam home, never two
        ap.error(ONE_EXAM_HOME)
    if args.human_lens and not (folder or bucket is not None):  # fail fast, not after hours of engines
        ap.error(SWITCH_NEEDS_EXAM_HOME)
    if args.human_lens and args.counts_only:                    # no lens would run: refuse, not a silent 0
        ap.error(COUNTS_ONLY_WITH_LENS)
    if args.human_lens and folder and not os.path.isabs(folder):    # the child's own rule (isabs)
        ap.error(FOLDER_ARG_NOT_ABSOLUTE)                       # fixed words: never the value
    if bucket is not None and not exam_home.bucket_name_ok(bucket):
        ap.error(BUCKET_NOT_PLAIN)                              # fixed words: never the value
    return args


def _has_joined(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return any(json.loads(line).get('event') == 'joined' for line in fh if line.strip())
    except (OSError, ValueError):                       # not written yet, or a half-written line
        return False


def wait_for_joins(paths, procs, *, timeout=JOIN_TIMEOUT_S, sleep=time.sleep, now=time.monotonic, poll=0.5):
    """{side: 'joined' | 'exited' | 'timed_out'}: waits until every child has written `joined` (it is inside
    the snapshot) or has exited. A child still waiting after ``timeout`` seconds is killed."""
    status, start = {}, now()
    while True:
        for s in procs:
            if s in status:
                continue
            if _has_joined(paths[s]):
                status[s] = 'joined'
            elif procs[s].poll() is not None:
                status[s] = 'exited'
        if len(status) == len(procs):
            return status
        if now() - start >= timeout:
            for s in procs:
                if s not in status:
                    procs[s].kill()
                    status[s] = 'timed_out'
            return status
        sleep(poll)


def clear_side_files(workdir):
    """{side: path}, after deleting those three side files if an earlier run left them, so a side that
    writes nothing can never be read as an old run's records. Nothing else in ``workdir`` is touched."""
    paths = {s: os.path.join(workdir, f'{s}.jsonl') for s in RUN_SIDES}
    for path in paths.values():
        if os.path.lexists(path):
            os.remove(path)
    return paths


def clear_human_lens_file(workdir, name=HUMAN_LENS_FILE):
    """The lens file's path (or the coach file's, by ``name``), after deleting the one an earlier run
    left, so a side that writes nothing is never read as an old run's result."""
    path = os.path.join(workdir, name)
    if os.path.lexists(path):
        os.remove(path)
    return path


def read_human_lens(path):
    """The lens side's counts and codes, checked again against the allow-list (`lens_result_schema`):
    ``{"error": "no_output"}`` when it wrote none, ``{"error": "bad_output"}`` when the file cannot be
    read or is not a JSON object, ``{"error": "schema"}`` when the object fails the allow-list. Never
    raises on the file and never echoes its content."""
    if not os.path.exists(path):
        return {'error': lens_result_schema.NO_OUTPUT}
    try:
        with open(path, 'rb') as fh:
            raw = fh.read(lens_result_schema.MAX_RESULT_BYTES + 1)
    except OSError:                                     # a folder, or no read permission
        return {'error': lens_result_schema.BAD_OUTPUT}
    return lens_result_schema.parse_human_lens_bytes(raw)


def read_coach_grade(path):
    """The coach grade's report, checked again against its allow-list (`coach_result_schema`), with the
    lens's error rules: ``no_output``, ``bad_output``, ``schema``. Never raises on the file, never echoes."""
    if not os.path.exists(path):
        return {'error': coach_result_schema.NO_OUTPUT}
    try:
        with open(path, 'rb') as fh:
            raw = fh.read(coach_result_schema.MAX_RESULT_BYTES + 1)
    except OSError:                                     # a folder, or no read permission
        return {'error': coach_result_schema.BAD_OUTPUT}
    return coach_result_schema.parse_coach_grade_bytes(raw)


def replay_exit_code(result):
    """``main``'s exit code for a finished run: `HUMAN_LENS_FAILED_EXIT` when the lens was on and its
    result or the coach grade's is an error (``{"error": ...}``: no output, a bad file, the allow-list, a
    caught error), else 0. A REFUSAL (a code inside an exam, the coach's ``refusal``) is a result: 0."""
    if not isinstance(result, dict):
        return 0
    for key in (HUMAN_LENS_KEY, COACH_GRADE_KEY):
        value = result.get(key)
        if isinstance(value, dict) and 'error' in value:
            return HUMAN_LENS_FAILED_EXIT
    return 0


def stop_children(procs):
    """Kill every child still running (its `poll()` is None)."""
    for proc in procs.values():
        if proc.poll() is None:
            proc.kill()


def run_replay(args, *, env, out=print, spawn=spawn_child, session=None, counts=case_counts):
    """The exporting transaction reads no table while it waits for every child to join its snapshot
    (`joins`), so the wait holds no table lock; the case counts run AFTER the joins, in the same snapshot,
    and the transaction is rolled back BEFORE the children run their engines (`--counts-only`: the counts
    and stop). Whatever goes wrong once a child has started, every child still running is killed.
    With `--human-lens` only: one fixed line says so, and the totals come back with ``human_lens``."""
    lens_on = bool(getattr(args, 'human_lens', False))
    guards.check_environment(env)
    host, port = guards.check_database_url(env.get(guards.DB_ENV))
    sess = session or (lambda: guards.read_only_session(export=True))
    importlib.import_module(f'{__package__}.engine_map')   # R2 adapters register their codes, as in each child
    os.makedirs(args.workdir, exist_ok=True)
    child_vars = {**env, scrub_module.SALT_ENV: scrub_module.new_salt()}   # one keyed hash on all three sides
    procs = {}
    try:
        with netguard.refuse_network(netguard.db_addresses(host, port)):
            with sess() as snapshot:
                emit({'event': 'start', 'old_commit': _commit(args.old_root), 'new_commit': _commit(args.new_root),
                      'months': args.months.split(','), 'snapshot_joined': bool(snapshot)}, out)
                if args.counts_only:
                    emit({'event': 'counts', **counts()}, out)
                    return {}
                paths = clear_side_files(args.workdir)
                if lens_on:
                    lens_path = clear_human_lens_file(args.workdir)
                    coach_path = clear_human_lens_file(args.workdir, COACH_GRADE_FILE)
                    out(HUMAN_LENS_ON_LINE)
                for s in RUN_SIDES:
                    procs[s] = spawn(args, s, snapshot, paths[s], child_vars)
                emit({'event': 'joins', **wait_for_joins(paths, procs)}, out)
                emit({'event': 'counts', **counts()}, out)      # after the joins: no lock held while waiting
            codes = {s: procs[s].wait(timeout=CHILD_TIMEOUT_S) for s in RUN_SIDES}
    finally:
        stop_children(procs)
    sides = {}
    for s in RUN_SIDES:
        sides[s], events = read_side(paths[s])
        emit({'event': 'side', 'side': s, 'exit': codes[s], 'records': len(sides[s]),
              'fatal': [{'error': e.get('error')} for e in events if e.get('event') == 'fatal'],
              'dropped': count_dropped(list(sides[s].values()))}, out)
    totals = report(compare_sides(sides), out)
    if lens_on:
        return {**totals, HUMAN_LENS_KEY: read_human_lens(lens_path), COACH_GRADE_KEY: read_coach_grade(coach_path)}
    return totals


def lens_report_block(result):
    """(text, failed): the LL5 block - `LENS_REPORT_START`, the lines `report_lens` renders from the two
    results, `LENS_REPORT_END` - and True when it shows a failure. When the render raises one of
    `report_lens.RENDER_ERRORS`, the lines are only `report_lens.RENDER_FAILED_LINE` (failed: True)."""
    try:
        lines, failed = report_lens.lens_coach_report(result.get(HUMAN_LENS_KEY), result.get(COACH_GRADE_KEY))
    except report_lens.RENDER_ERRORS:                   # never the message, never the result
        lines, failed = [report_lens.RENDER_FAILED_LINE], True
    return '\n'.join([LENS_REPORT_START, *lines, LENS_REPORT_END]), failed


def main(argv=None):
    import logging
    logging.disable(logging.CRITICAL)
    try:
        args = parse_args(argv)
        guards.check_environment(os.environ)            # the checks come BEFORE Django: its setup queries
        guards.check_database_url(os.environ.get(guards.DB_ENV))
        setup_django()
        home = exam_home.fetch(args) if args.human_lens_exam_bucket is not None else None   # LL6: exit 3
        try:
            result = run_replay(args, env=os.environ)
            result, home_lines, home_failed = exam_home.keep(home, args, result)   # no home: as before
            code = replay_exit_code(result)
            if args.human_lens and not args.counts_only:    # after the JSON lines; built whole, then one print
                block, failed = lens_report_block(result)
                print(block)
                if failed:
                    code = HUMAN_LENS_FAILED_EXIT
            if home_lines:                                  # fixed lines only (`exam_home.ALL_HOME_LINES`)
                print('\n'.join(home_lines))
            if home_failed:
                code = HUMAN_LENS_FAILED_EXIT
        finally:
            exam_home.clean(home)                           # the temp folder, whatever happened
    except SystemExit:
        raise
    except BaseException as exc:                        # by class name only, never the message
        emit({'event': 'fatal', **error_record(exc)})
        return 3
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
