"""A5 replay, R1: the harness end to end on the test database with FAKE engines (design 3.5 to 3.7).

The parent runs in-process with an in-process "spawn": each side is `child.run` inside the same guards
the job uses (the SQLite test database stands in for the snapshot, `allow_sqlite`). The engine map is
checked against THIS tree. No live database, no network, no key, no real engine adapter (R2)."""
import contextlib
import datetime
import io
import json
import logging
import os
import re
import subprocess
import tempfile
import types
from unittest import mock

from django.apps import apps as django_apps
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.scholarship.eval.replay import child, engine_map, guards, parent, scrub
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.tests.factories import make_application

LOCAL_URL = 'postgresql://replay_ro.abcdefgh:pw-not-real@127.0.0.1:5432/postgres'
INSTANT = '2026-11-20T18:00:00+00:00'


class EngineMapTest(SimpleTestCase):
    """Every engine named in design section 1 resolves in this (the new) tree; a miss is named."""

    def test_every_engine_resolves_in_the_new_tree(self):
        found = engine_map.resolve_tree('new')
        self.assertEqual(set(found), set(engine_map.ENGINES))
        self.assertTrue(all(callable(f) for f in found.values()))

    def test_a_path_that_does_not_resolve_is_named_and_the_build_check_fails(self):
        bogus = dict(engine_map.ENGINES, **{'bogus.engine': ('apps.scholarship.nope:x',) * 2})
        with mock.patch.object(engine_map, 'ENGINES', bogus):
            with self.assertRaises(engine_map.Unresolved) as cm:
                engine_map.resolve_tree('new')
            self.assertIn('bogus.engine', str(cm.exception))
            lines = []
            self.assertEqual(engine_map.main(['--side', 'new'], out=lines.append), 1)
        self.assertEqual(engine_map.main(['--side', 'new'], out=lines.append), 0)


class _Engine:
    """A fake adapter: `.name`, `.cases()`, `.run(key, months)`; ``answer(side, app, months)``."""

    def __init__(self, name, side, answer):
        self.name, self.side, self.answer = name, side, answer

    def cases(self):
        return list(ScholarshipApplication.objects.order_by('pk').values_list('pk', flat=True))

    def run(self, key, *, months):
        return self.answer(self.side, ScholarshipApplication.objects.get(pk=key), months)


_CALLS = {'n': 0}


def _noisy(side, app, months):
    _CALLS['n'] += 1
    return {'n': _CALLS['n']}


def _write(side, app, months):
    ScholarshipApplication.objects.filter(pk=app.pk).update(status='closed')
    return {'status': 'unreachable'}


def _old_raises(side, app, months):
    if side == 'old':
        raise KeyError(app.profile.name)
    return {'status': 'probable'}


ANSWERS = {
    'same': lambda side, app, months: {'status': app.status, 'app': app.pk, 'amount': 3000},
    'differs': lambda side, app, months: {'status': 'probable' if side == 'old' else 'unclear', 'app': app.pk},
    'noise': _noisy,
    'raises': _old_raises,
    'writes': _write,
    'clock': lambda side, app, months: {'month': timezone.localdate().strftime('%Y-%m'), 'months': months},
    'leaks': lambda side, app, months: {'name': app.profile.name, 'status': 'probable'},
}


#: What the fake adapters register, as an R2 adapter would (engine names, record fields, statuses).
FAKE_CODES = tuple(ANSWERS) + ('status', 'app', 'amount', 'n', 'month', 'months', 'probable', 'unclear',
                               'submitted', 'unreachable')
#: The fake records' int fields, added to `scrub.INT_KEYS` as an R2 adapter's would be (by review).
FAKE_INT_KEYS = frozenset({'app', 'amount', 'n'})


def _register_fake_codes(test):
    for patcher in (mock.patch.object(scrub, '_REGISTERED', set()),
                    mock.patch.dict(scrub._STATE, frozen=False),           # engine_map froze it on import
                    mock.patch.object(scrub, 'INT_KEYS', scrub.INT_KEYS | FAKE_INT_KEYS)):
        patcher.start()
        test.addCleanup(patcher.stop)
    scrub.register_codes(FAKE_CODES)


def _done_proc():
    return types.SimpleNamespace(wait=lambda timeout=None: 0, poll=lambda: 0, kill=lambda: None)


def _spawn(args, side, snapshot, out_path, env):
    """In-process stand-in for `parent.spawn_child`: the side's run inside the job's own guards."""
    engines = [_Engine(n, side, ANSWERS[n]) for n in sorted(ANSWERS)]
    with open(out_path, 'w', encoding='utf-8') as fh:
        def write(obj):
            fh.write(json.dumps(child.scrub(obj), sort_keys=True) + '\n')
        child.run_side(side=side, engines=engines, instant=child.parse_instant(args.instant),
                       months=args.months.split(','), write=write, snapshot=snapshot, load=lambda: None,
                       session=lambda: guards.read_only_session(snapshot=snapshot, allow_sqlite=True))
    return _done_proc()


class HarnessEndToEndTest(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workdir = tmp.name
        self.apps = [make_application('submitted'), make_application('submitted')]
        _CALLS['n'] = 0
        _register_fake_codes(self)

    def _run(self, *extra):
        args = parent.parse_args(['--instant', INSTANT, '--months', '2026-11,2026-12', '--workdir', self.workdir,
                                  '--old-root', self.workdir, '--new-root', self.workdir, *extra])
        lines = []
        totals = parent.run_replay(args, env={guards.DB_ENV: LOCAL_URL, 'PATH': '/bin'}, out=lines.append,
                            spawn=_spawn, session=lambda: guards.read_only_session(export=True, allow_sqlite=True))
        return totals, [json.loads(line) for line in lines]

    def test_each_outcome_is_classified_and_nothing_lands(self):
        totals, lines = self._run()
        n = len(self.apps)
        self.assertEqual(dict(totals['same']), {'same': n})
        self.assertEqual(dict(totals['differs']), {'differs': n, 'unexplained': n})  # R2: a differs record with no ruling is B
        self.assertEqual(dict(totals['noise']), {'noise': n})
        self.assertEqual(dict(totals['raises']), {'could_not_run': n})
        self.assertEqual(dict(totals['writes']), {'could_not_run': n})     # refused; the run went on
        self.assertEqual(dict(totals['clock']), {'same': n})
        self.assertEqual(dict(totals['leaks']), {'same': n})
        refused = [x for x in lines if x.get('engine') == 'writes' and x.get('outcome') == 'could_not_run']
        self.assertEqual(refused[0]['old'], {'error': 'WriteRefused'})
        raised = [x for x in lines if x.get('engine') == 'raises' and x.get('outcome') == 'could_not_run']
        self.assertEqual((raised[0]['old'], raised[0]['new']), ({'error': 'KeyError'}, None))
        differs = [x for x in lines if x.get('engine') == 'differs']
        self.assertEqual((differs[0]['fields'], differs[0]['old'], differs[0]['new']),
                         (['status'], {'status': 'probable'}, {'status': 'unclear'}))
        self.assertTrue(all(a.status == ScholarshipApplication.objects.get(pk=a.pk).status for a in self.apps))
        sides = [x for x in lines if x.get('event') == 'side']
        self.assertEqual([(s['side'], s['exit'], s['fatal']) for s in sides],
                         [('old', 0, []), ('new', 0, []), ('new_again', 0, [])])
        joins = next(x for x in lines if x.get('event') == 'joins')
        self.assertEqual({joins[s] for s in parent.RUN_SIDES}, {'joined'})

    def test_the_clock_engine_reads_the_pinned_month(self):
        self._run()
        with open(os.path.join(self.workdir, 'new.jsonl'), encoding='utf-8') as fh:
            rows = [json.loads(line) for line in fh]
        clock_rows = [r['record'] for r in rows if r.get('engine') == 'clock']
        self.assertEqual({r['month'] for r in clock_rows}, {'2026-11'})
        self.assertEqual(clock_rows[0]['months'], ['2026-11', '2026-12'])

    def test_no_personal_text_leaves_in_the_report_or_the_side_files(self):
        _, lines = self._run()
        names = [a.profile.name for a in self.apps]
        blob = json.dumps(lines)
        for side in parent.RUN_SIDES:
            with open(os.path.join(self.workdir, f'{side}.jsonl'), encoding='utf-8') as fh:
                blob += fh.read()
        for name in names:
            self.assertNotIn(name, blob)
        self.assertIn('!dropped', blob)
        side_lines = [x for x in lines if x.get('event') == 'side']
        self.assertTrue(all(s['dropped'] >= len(self.apps) for s in side_lines))

    def test_counts_only_stops_after_the_counts(self):
        spawn = mock.Mock()
        args = parent.parse_args(['--instant', INSTANT, '--months', '2026-11,2026-12', '--workdir', self.workdir,
                                  '--counts-only'])
        lines = []
        parent.run_replay(args, env={guards.DB_ENV: LOCAL_URL}, out=lines.append, spawn=spawn,
                   session=lambda: guards.read_only_session(export=True, allow_sqlite=True))
        spawn.assert_not_called()
        counts = json.loads(lines[1])
        self.assertEqual(counts['event'], 'counts')
        self.assertEqual(counts['applications'], len(self.apps))
        self.assertEqual(set(counts) - {'event'},
                         {'applications', 'documents_live', 'payable', 'profiles_spm', 'profiles_stpm', 'sponsors'})

    def test_the_parent_refuses_to_start_with_a_key_or_the_wrong_port(self):
        args = parent.parse_args(['--instant', INSTANT, '--months', '2026-11,2026-12', '--workdir', self.workdir])
        for env in ({guards.DB_ENV: LOCAL_URL, 'GEMINI_API_KEY': 'x'},
                    {guards.DB_ENV: LOCAL_URL.replace(':5432', ':6543')}):
            with self.assertRaises(guards.WriteRefused):
                parent.run_replay(args, env=env, out=lambda s: None, spawn=mock.Mock())


class JoinHandshakeTest(SimpleTestCase):
    """The parent's exporting transaction ends as soon as every child has joined the snapshot."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workdir = tmp.name
        _register_fake_codes(self)

    def test_the_parent_rolls_back_once_every_child_joined_and_before_any_child_finishes(self):
        state = {'open': False, 'open_at_wait': [], 'open_at_counts': None}

        def counts():
            state['open_at_counts'] = state['open']
            return {'applications': 0}

        @contextlib.contextmanager
        def session():
            state['open'] = True
            try:
                yield '00000003-0000001B-1'
            finally:
                state['open'] = False

        def spawn(args, side, snapshot, out_path, env):
            with open(out_path, 'w', encoding='utf-8') as fh:
                fh.write(json.dumps({'event': 'joined', 'side': side}, sort_keys=True) + '\n')

            def wait(timeout=None):
                state['open_at_wait'].append(state['open'])
                return 0
            return types.SimpleNamespace(wait=wait, poll=lambda: None, kill=mock.Mock())

        args = parent.parse_args(['--instant', INSTANT, '--months', '2026-11,2026-12', '--workdir', self.workdir,
                                  '--old-root', self.workdir, '--new-root', self.workdir])
        lines = []
        parent.run_replay(args, env={guards.DB_ENV: LOCAL_URL, 'PATH': '/bin'}, out=lines.append, spawn=spawn,
                          session=session, counts=counts)
        self.assertEqual(state['open_at_wait'], [False, False, False])
        self.assertTrue(state['open_at_counts'])                    # counted inside the same snapshot
        events = [json.loads(line).get('event') for line in lines]
        self.assertLess(events.index('joins'), events.index('counts'))

    def _args(self):
        return parent.parse_args(['--instant', INSTANT, '--months', '2026-11,2026-12', '--workdir', self.workdir,
                                  '--old-root', self.workdir, '--new-root', self.workdir])

    @staticmethod
    @contextlib.contextmanager
    def _session():
        yield '00000003-0000001B-1'

    def test_the_counts_run_only_after_every_child_has_joined_so_the_wait_holds_no_table_lock(self):
        order = []

        def counts():
            order.append('counts')
            return {'applications': 0}

        def spawn(args, side, snapshot, out_path, env):
            order.append('spawn')
            with open(out_path, 'w', encoding='utf-8') as fh:
                fh.write(json.dumps({'event': 'joined', 'side': side}) + '\n')
            return _done_proc()

        real_wait = parent.wait_for_joins

        def wait(paths, procs, **kw):
            order.append('wait')
            return real_wait(paths, procs, **kw)

        lines = []
        with mock.patch.object(parent, 'wait_for_joins', wait):
            parent.run_replay(self._args(), env={guards.DB_ENV: LOCAL_URL}, out=lines.append, spawn=spawn,
                              session=self._session, counts=counts)
        self.assertEqual(order, ['spawn', 'spawn', 'spawn', 'wait', 'counts'])
        events = [json.loads(line).get('event') for line in lines]
        self.assertLess(events.index('joins'), events.index('counts'))

    def test_only_the_three_side_files_of_an_earlier_run_are_deleted_before_any_child_starts(self):
        for name in ('old.jsonl', 'new.jsonl', 'new_again.jsonl', 'stale.jsonl', 'notes.jsonl'):
            with open(os.path.join(self.workdir, name), 'w', encoding='utf-8') as fh:
                fh.write('{"engine": "same", "key": [1], "record": {"status": "probable"}}\n')
        seen = []

        def spawn(args, side, snapshot, out_path, env):
            seen.append(sorted(f for f in os.listdir(self.workdir) if f.endswith('.jsonl')))
            return _done_proc()                         # writes nothing: an old file would read as records

        lines = []
        parent.run_replay(self._args(), env={guards.DB_ENV: LOCAL_URL}, out=lines.append, spawn=spawn,
                          session=self._session, counts=dict)
        self.assertEqual(seen[0], ['notes.jsonl', 'stale.jsonl'])      # nothing but the side files
        sides = [json.loads(x) for x in lines if json.loads(x).get('event') == 'side']
        self.assertEqual([s['records'] for s in sides], [0, 0, 0])

    def test_every_running_child_is_killed_when_the_parent_fails_after_they_start(self):
        for failure in ('wait_timeout', 'join_error'):
            procs = {}

            def spawn(args, side, snapshot, out_path, env):
                def wait(timeout=None):
                    raise subprocess.TimeoutExpired('child', timeout)
                running = side != 'new'                 # `new` has already exited: not killed
                procs[side] = types.SimpleNamespace(wait=wait, poll=lambda r=running: None if r else 3,
                                                    kill=mock.Mock())
                return procs[side]

            patch = (mock.patch.object(parent, 'wait_for_joins', side_effect=RuntimeError('made-up'))
                     if failure == 'join_error' else mock.patch.object(parent, 'wait_for_joins', return_value={}))
            with patch, self.assertRaises((subprocess.TimeoutExpired, RuntimeError), msg=failure):
                parent.run_replay(self._args(), env={guards.DB_ENV: LOCAL_URL}, out=lambda s: None, spawn=spawn,
                                  session=self._session, counts=dict)
            self.assertEqual(set(procs), set(parent.RUN_SIDES), failure)
            procs['old'].kill.assert_called_once_with()
            procs['new_again'].kill.assert_called_once_with()
            procs['new'].kill.assert_not_called()

    def test_a_child_that_never_joins_is_stopped_and_the_wait_ends(self):
        paths = {s: os.path.join(self.workdir, f'{s}.jsonl') for s in parent.RUN_SIDES}
        with open(paths['old'], 'w', encoding='utf-8') as fh:
            fh.write('{"event": "joined", "side": "old"}\n')
        procs = {'old': types.SimpleNamespace(poll=lambda: None, kill=mock.Mock()),
                 'new': types.SimpleNamespace(poll=lambda: 3, kill=mock.Mock()),          # exited, never joined
                 'new_again': types.SimpleNamespace(poll=lambda: None, kill=mock.Mock())}  # never joins
        ticks = iter(range(0, 10 ** 6, 10))
        status = parent.wait_for_joins(paths, procs, timeout=60, sleep=lambda s: None, now=lambda: next(ticks))
        self.assertEqual(status, {'old': 'joined', 'new': 'exited', 'new_again': 'timed_out'})
        procs['new_again'].kill.assert_called_once_with()
        procs['old'].kill.assert_not_called()


class ParentMainTest(TestCase):
    def test_a_bad_url_is_refused_before_django_setup_and_before_any_query(self):
        level = logging.root.manager.disable
        self.addCleanup(logging.disable, level)
        for url in (LOCAL_URL.replace(':5432', ':6543'), LOCAL_URL.replace('replay_ro.abcdefgh', 'postgres.abcdefgh')):
            buf = io.StringIO()
            with tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.dict(os.environ, {guards.DB_ENV: url, 'PATH': os.environ.get('PATH', '')}, clear=True), \
                    mock.patch('django.setup') as setup, CaptureQueriesContext(connection) as queries, \
                    contextlib.redirect_stdout(buf):
                code = parent.main(['--instant', INSTANT, '--months', '2026-11,2026-12', '--workdir', tmp])
            self.assertEqual(code, 3, url)
            setup.assert_not_called()
            self.assertEqual(len(queries), 0)
            self.assertEqual(json.loads(buf.getvalue()), {'event': 'fatal', 'error': 'WriteRefused'})


class CourseDataTest(TestCase):
    """The engines' course data comes from the snapshot: loaded inside the session, never at start-up."""

    def setUp(self):
        self.cfg = django_apps.get_app_config('courses')
        saved = dict(vars(self.cfg))

        def restore():
            self.cfg.__dict__.clear()
            self.cfg.__dict__.update(saved)
        self.addCleanup(restore)

    def test_course_data_is_loaded_after_the_snapshot_join_never_before(self):
        order = []

        @contextlib.contextmanager
        def session():
            order.append('join')
            yield None
            order.append('rollback')

        child.run_side(side='new', engines=[], instant=child.parse_instant(INSTANT), months=['2026-11', '2026-12'],
                       write=lambda obj: order.append(obj.get('event')), session=session,
                       load=lambda: order.append('load'))
        self.assertEqual(order, ['join', 'joined', 'load', 'done', 'rollback'])

    def test_the_startup_course_load_is_held_back(self):
        with mock.patch('django.setup', side_effect=self.cfg.ready), CaptureQueriesContext(connection) as queries:
            child.setup_django()
        self.assertEqual(len(queries), 0)

    def test_course_data_loads_through_the_read_only_filter_and_nothing_stale_survives(self):
        self.cfg.course_pathway_map = {'MADE-UP-STALE': 'tvet'}
        with CaptureQueriesContext(connection) as queries, guards.read_only_session(allow_sqlite=True):
            child.load_course_data()
        self.assertGreater(len(queries), 0)
        self.assertNotIn('MADE-UP-STALE', self.cfg.course_pathway_map)


class ChildMainTest(SimpleTestCase):
    def test_a_key_in_the_environment_is_fatal_by_class_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'old.jsonl')
            code = child.main(['--side', 'old', '--instant', INSTANT, '--months', '2026-11,2026-12', '--out', out],
                              env={guards.DB_ENV: LOCAL_URL, 'GEMINI_API_KEY': 'secret-value-123'})
            with open(out, encoding='utf-8') as fh:
                text = fh.read()
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(text), {'side': 'old', 'event': 'fatal', 'error': 'WriteRefused'})
        self.assertNotIn('secret-value-123', text)
        self.assertNotIn('GEMINI', text)

    def test_a_child_without_the_parents_salt_refuses_to_start(self):
        argv = ['--side', 'old', '--instant', INSTANT, '--months', '2026-11,2026-12']
        for salt in (None, '', 'too-short'):
            env = {guards.DB_ENV: LOCAL_URL}
            if salt is not None:
                env[scrub.SALT_ENV] = salt
            with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(scrub._STATE, salt=None), \
                    mock.patch.object(child, 'setup_django', side_effect=AssertionError) as setup:
                out = os.path.join(tmp, 'old.jsonl')
                self.assertEqual(child.main(argv + ['--out', out], env=env), 3)
                with open(out, encoding='utf-8') as fh:
                    self.assertEqual(json.loads(fh.read()), {'side': 'old', 'event': 'fatal', 'error': 'SaltMissing'})
                self.assertIsNone(scrub._STATE['salt'])
            setup.assert_not_called()
        given = 'f' * 32
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(scrub._STATE, salt=None), \
                mock.patch.object(child, 'setup_django', side_effect=KeyError) as setup:
            child.main(argv + ['--out', os.path.join(tmp, 'old.jsonl')],
                       env={guards.DB_ENV: LOCAL_URL, scrub.SALT_ENV: given})
            self.assertEqual(scrub._STATE['salt'], given)       # the parent's salt is the one used
        setup.assert_called_once_with()

    def test_the_instant_must_carry_a_timezone(self):
        with self.assertRaises(ValueError):
            child.parse_instant('2026-11-20T18:00:00')
        self.assertEqual(child.parse_instant(INSTANT), datetime.datetime(2026, 11, 20, 18, tzinfo=datetime.timezone.utc))


OWNER_DIR = os.path.join(os.path.dirname(guards.__file__), 'owner')
STEPS_DOC = os.path.join(os.path.dirname(guards.__file__), *(['..'] * 5), 'docs', 'plans',
                         '2026-11-13-a5-replay-owner-steps.md')


def _sql_statements(name):
    with open(os.path.join(OWNER_DIR, name), encoding='utf-8') as fh:
        code = '\n'.join(line.split('--')[0] for line in fh)
    return [' '.join(s.split()) for s in code.split(';') if s.strip()]


class OwnerFilesTest(SimpleTestCase):
    """The owner steps are written, not run: the role gets SELECT only; the gcloud rules hold."""

    def test_the_role_is_granted_select_and_schema_usage_and_nothing_else(self):
        stmts = _sql_statements('replay_ro_create.sql')
        grants = [s for s in stmts if s.upper().startswith('GRANT')]
        self.assertEqual(grants, ['GRANT USAGE ON SCHEMA public TO replay_ro',
                                  'GRANT SELECT ON ALL TABLES IN SCHEMA public TO replay_ro'])
        role = next(s for s in stmts if s.upper().startswith('CREATE ROLE'))
        for word in ('NOSUPERUSER', 'NOCREATEDB', 'NOCREATEROLE', 'NOREPLICATION', 'CONNECTION LIMIT'):
            self.assertIn(word, role)
        self.assertIn("PASSWORD 'REPLACE-WITH-A-LONG-RANDOM-PASSWORD'", role)    # a placeholder, never a real one
        text = ' '.join(stmts).upper()
        for banned in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'GRANT ALL', 'DEFAULT PRIVILEGES',
                       'DEFAULT_TRANSACTION_READ_ONLY', ' SUPERUSER', 'GRANT POSTGRES', 'SERVICE_ROLE'):
            self.assertNotIn(banned, text)

    def test_the_role_expires_and_the_checks_cover_create_definer_functions_and_bypassrls(self):
        stmts = _sql_statements('replay_ro_create.sql')
        role = next(s for s in stmts if s.upper().startswith('CREATE ROLE'))
        self.assertIn("VALID UNTIL 'REPLACE-WITH-RUN-DATE-PLUS-7-DAYS'", role)
        begin, commit = stmts.index('BEGIN'), stmts.index('COMMIT')
        prechecks, checks = stmts[:begin], stmts[commit + 1:]
        self.assertTrue(prechecks and checks)
        self.assertTrue(all(s.upper().startswith('SELECT') for s in prechecks + checks), prechecks + checks)
        self.assertIn('version()', ' '.join(prechecks))
        self.assertIn("rolname = 'postgres'", ' '.join(prechecks))
        self.assertIn('rolbypassrls', ' '.join(prechecks))
        text = ' '.join(checks)
        for needle in ("has_schema_privilege('replay_ro', 'public', 'CREATE')", 'prosecdef',
                       "has_function_privilege('replay_ro', p.oid, 'EXECUTE')"):
            self.assertIn(needle, text)
        with open(os.path.join(OWNER_DIR, 'replay_ro_create.sql'), encoding='utf-8') as fh:
            self.assertIn('per-table read policy fallback', fh.read())

    def test_the_steps_forbid_deploys_during_the_run_and_name_the_timeouts(self):
        with open(STEPS_DOC, encoding='utf-8') as fh:
            text = fh.read()
        for needle in ('No deploy and no migration', 'SET LOCAL lock_timeout',
                       'SET LOCAL idle_in_transaction_session_timeout',
                       'HARD RULE: no deploy, no migration, no ALTER while the replay job runs', 'quiet window',
                       'stop the job first', 'gcloud run jobs executions cancel', 'TD-669'):
            self.assertIn(needle, text)

    def test_the_drop_file_removes_the_role(self):
        self.assertIn('DROP ROLE replay_ro', _sql_statements('replay_ro_drop.sql'))

    def test_the_image_checks_both_engine_maps_and_bakes_in_no_key(self):
        with open(os.path.join(OWNER_DIR, 'Dockerfile.replay'), encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn('replay.engine_map --side old', text)
        self.assertIn('replay.engine_map --side new', text)
        self.assertIn('ENTRYPOINT ["/replay/new/venv/bin/python", "-m", "replay.parent"]', text)
        envs = ' '.join(line for line in text.splitlines() if not line.startswith('#'))
        for banned in ('DATABASE_URL', 'GEMINI', 'SUPABASE', 'SECRET', 'GOOGLE_', 'BREVO', 'VIRCLE'):
            self.assertNotIn(banned, envs)

    def test_every_gcloud_command_names_account_and_project_and_never_sets_config_or_env(self):
        with open(STEPS_DOC, encoding='utf-8') as fh:
            text = fh.read()
        commands = [line.strip('`') for line in text.splitlines() if line.lstrip('`').startswith('gcloud ')]
        self.assertGreaterEqual(len(commands), 10)
        for cmd in commands:
            self.assertIn('--account tamiliam@gmail.com', cmd)
            self.assertIn('--project gen-lang-client-0871147736', cmd)
            self.assertNotIn('config set', cmd)
            self.assertNotIn('--set-env-vars', cmd)
        self.assertIsNone(re.search(r':6543\b', text))
