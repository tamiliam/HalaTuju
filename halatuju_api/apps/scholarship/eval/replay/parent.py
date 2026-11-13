"""The replay's parent process (design 3.5): the job's entry point, `python -m replay.parent`.

1. Preflight: no forbidden key in the environment; the `replay_ro` URL on the session pooler port 5432.
2. Opens ONE `REPEATABLE READ, READ ONLY` transaction (never committed) and exports its snapshot.
3. Prints the case counts (`--counts-only` stops here: R1's first live step).
4. Starts three children - old, new, new_again - each in its own venv and tree with a MINIMAL environment
   (the replay URL, the path, the settings module; nothing else), each joining the snapshot.
5. Compares: per record `same`, `differs` (old against new), `could_not_run` (either side raised) or
   `noise` (new against new_again differ: the engine is not deterministic; left out of A/B). The A/B
   split by the ruling catalogue is R2.
Everything printed goes through the scrubber; an error is printed by class name only.
"""
import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

from . import guards, netguard
from .child import parse_instant
from .scrub import count_dropped, error_record, scrub

RUN_SIDES = ('old', 'new', 'new_again')
TREE_OF = {'old': 'old', 'new': 'new', 'new_again': 'new'}
CHILD_TIMEOUT_S = 3 * 60 * 60


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


def child_env(env, side_root, harness_dir):
    """The child's WHOLE environment: nothing from the parent but the replay URL and the path."""
    return {
        'PATH': env.get('PATH', '/usr/bin:/bin'),
        guards.DB_ENV: env.get(guards.DB_ENV, ''),
        'PYTHONPATH': os.pathsep.join([harness_dir, os.path.join(side_root, 'halatuju_api')]),
        'DJANGO_SETTINGS_MODULE': 'replay.settings',
        'PYTHONDONTWRITEBYTECODE': '1',
        'TZ': 'UTC',
    }


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
                            env=child_env(env, root, args.harness_dir), stdin=subprocess.DEVNULL,
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


def classify(old, new, again):
    if old is None or new is None or again is None:
        return 'could_not_run'
    if new != again:
        return 'noise'
    if _is_error(old) or _is_error(new):
        return 'could_not_run'
    return 'same' if old == new else 'differs'


def changed_fields(old, new):
    if isinstance(old, dict) and isinstance(new, dict):
        return sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
    return ['value']


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
            line.update(fields=fields,
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


def parse_args(argv):
    ap = argparse.ArgumentParser(description='The A5 replay: old engines against new, on one snapshot.')
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
    args = ap.parse_args(argv)
    parse_instant(args.instant)
    if len(args.months.split(',')) != 2:
        ap.error('--months takes exactly two months')
    return args


def run_replay(args, *, env, out=print, spawn=spawn_child, session=None, counts=case_counts):
    guards.check_environment(env)
    host, port = guards.check_database_url(env.get(guards.DB_ENV))
    sess = session or (lambda: guards.read_only_session(export=True))
    os.makedirs(args.workdir, exist_ok=True)
    with netguard.refuse_network(netguard.db_addresses(host, port)), sess() as snapshot:
        emit({'event': 'start', 'old_commit': _commit(args.old_root), 'new_commit': _commit(args.new_root),
              'months': args.months.split(','), 'snapshot_joined': bool(snapshot)}, out)
        emit({'event': 'counts', **counts()}, out)
        if args.counts_only:
            return {}
        paths = {s: os.path.join(args.workdir, f'{s}.jsonl') for s in RUN_SIDES}
        procs = {s: spawn(args, s, snapshot, paths[s], env) for s in RUN_SIDES}
        codes = {s: procs[s].wait(timeout=CHILD_TIMEOUT_S) for s in RUN_SIDES}
    sides = {}
    for s in RUN_SIDES:
        sides[s], events = read_side(paths[s])
        emit({'event': 'side', 'side': s, 'exit': codes[s], 'records': len(sides[s]),
              'fatal': [{'error': e.get('error')} for e in events if e.get('event') == 'fatal'],
              'dropped': count_dropped(list(sides[s].values()))}, out)
    return report(compare_sides(sides), out)


def main(argv=None):
    import logging
    logging.disable(logging.CRITICAL)
    try:
        args = parse_args(argv)
        import django
        django.setup()
        run_replay(args, env=os.environ)
    except SystemExit:
        raise
    except BaseException as exc:                        # by class name only, never the message
        emit({'event': 'fatal', **error_record(exc)})
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
