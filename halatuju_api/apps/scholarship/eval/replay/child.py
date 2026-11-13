"""One side of the replay (design 3.5, 3.7): the OLD tree, the NEW tree, or the new tree AGAIN (the
determinism control). The parent starts it as `python -m replay.child` with the side's own venv and tree.

It joins the parent's exported snapshot in its own read-only, always-rolled-back transaction, pins the
clock, refuses the network, and runs every adapter's cases, each in its own savepoint. It writes one
scrubbed JSON line per record to ``--out``; its own stdout and stderr go to /dev/null, so nothing an
engine prints or logs (or a traceback) leaves the process.
"""
import argparse
import datetime
import json
import os
import sys

from . import clock, guards, netguard
from .scrub import error_record, scrub

TREE_OF = {'old': 'old', 'new': 'new', 'new_again': 'new'}


def parse_instant(value):
    dt = datetime.datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError('the instant must carry a timezone')
    return dt


def _key(key):
    return list(key) if isinstance(key, (tuple, list)) else [key]


def run_engines(engines, *, months, write):
    """Every case of every engine, each in its own savepoint. Returns the number of records written."""
    n = 0
    for engine in engines:
        keys = guards.run_case(lambda: list(engine.cases()))
        if isinstance(keys, dict):                      # the case query itself failed
            write({'engine': engine.name, 'cases': keys})
            continue
        for key in keys:
            record = guards.run_case(lambda: engine.run(key, months=months))
            write({'engine': engine.name, 'key': _key(key), 'record': scrub(record)})
            n += 1
    return n


def run(*, side, engines, instant, months, write, snapshot=None, session=None, allow=()):
    """One side's run inside every guard. ``session`` is for the tests (the SQLite test database)."""
    sess = session or (lambda: guards.read_only_session(snapshot=snapshot))
    with netguard.refuse_network(allow), sess(), clock.pinned_clock(instant):
        write({'side': side, 'event': 'start'})
        n = run_engines(engines, months=months, write=write)
        write({'side': side, 'event': 'done', 'records': n})
    return n


def _silence_stdio():
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)


def main(argv=None, env=None):
    ap = argparse.ArgumentParser(description='One side of the A5 replay.')
    ap.add_argument('--side', choices=sorted(TREE_OF), required=True)
    ap.add_argument('--instant', required=True)
    ap.add_argument('--months', required=True, help='two pinned payment months, YYYY-MM,YYYY-MM')
    ap.add_argument('--out', required=True)
    ap.add_argument('--snapshot', default='')
    ap.add_argument('--engines', default='', help='adapter names, comma separated (default: all)')
    args = ap.parse_args(argv)
    env = os.environ if env is None else env
    with open(args.out, 'w', encoding='utf-8') as fh:
        def write(obj):
            fh.write(json.dumps(scrub(obj), sort_keys=True) + '\n')
            fh.flush()
        try:
            guards.check_environment(env)
            host, port = guards.check_database_url(env.get(guards.DB_ENV))
            import django
            django.setup()
            failed = clock.preload()
            from . import engine_map
            resolved = engine_map.resolve(TREE_OF[args.side])
            names = [n for n in args.engines.split(',') if n] or sorted(engine_map.ADAPTERS)
            engines = [engine_map.ADAPTERS[n](resolved) for n in names]
            write({'side': args.side, 'event': 'preload', 'failed_modules': len(failed)})
            run(side=args.side, engines=engines, instant=parse_instant(args.instant),
                months=args.months.split(','), write=write, snapshot=args.snapshot or None,
                allow=netguard.resolve(host, port))
        except BaseException as exc:                    # by class name only, never the message
            write({'side': args.side, 'event': 'fatal', **error_record(exc)})
            return 3
    return 0


if __name__ == '__main__':
    _silence_stdio()
    sys.exit(main(sys.argv[1:]))
