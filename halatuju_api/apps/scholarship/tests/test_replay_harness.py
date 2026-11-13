"""A5 replay, R1: the harness end to end on the test database with FAKE engines (design 3.5 to 3.7).

The parent runs in-process with an in-process "spawn": each side is `child.run` inside the same guards
the job uses (the SQLite test database stands in for the snapshot, `allow_sqlite`). The engine map is
checked against THIS tree. No live database, no network, no key, no real engine adapter (R2)."""
import datetime
import json
import os
import re
import tempfile
import types
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship.eval.replay import child, engine_map, guards, parent
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


def _spawn(args, side, snapshot, out_path, env):
    """In-process stand-in for `parent.spawn_child`: the side's run inside the job's own guards."""
    engines = [_Engine(n, side, ANSWERS[n]) for n in sorted(ANSWERS)]
    with open(out_path, 'w', encoding='utf-8') as fh:
        def write(obj):
            fh.write(json.dumps(child.scrub(obj), sort_keys=True) + '\n')
        child.run_side(side=side, engines=engines, instant=child.parse_instant(args.instant),
                  months=args.months.split(','), write=write, snapshot=snapshot,
                  session=lambda: guards.read_only_session(snapshot=snapshot, allow_sqlite=True))
    return types.SimpleNamespace(wait=lambda timeout=None: 0)


class HarnessEndToEndTest(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workdir = tmp.name
        self.apps = [make_application('submitted'), make_application('submitted')]
        _CALLS['n'] = 0

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
        self.assertEqual(dict(totals['differs']), {'differs': n})
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
