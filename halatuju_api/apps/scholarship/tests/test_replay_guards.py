"""A5 replay, R1: each safety layer refuses on its own (design 3.2, 3.4, 3.6).

Invented data only: the factory's applications on the test database (SQLite, `allow_sqlite`) or a fake
cursor. No live database, no network, no key."""
import datetime
import importlib
import importlib.util
import json
import os
import socket
import sys
import tempfile
import types
import urllib.request
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship import usage, vision
from apps.scholarship.eval import offer_s4_dry_run as s4
from apps.scholarship.eval.replay import clock, guards, netguard, scrub
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.tests.factories import make_application

REPLAY_DIR = os.path.dirname(guards.__file__)
GOOD_URL = 'postgresql://replay_ro.abcdefgh:pw-not-real@pooler.example.test:5432/postgres'


class _FakeCursor:
    def __init__(self, read_only='on', isolation='repeatable read', exported='00000003-0000001B-1'):
        self.sql, self._answers = [], {'SHOW transaction_read_only': read_only,
                                       'SHOW transaction_isolation': isolation,
                                       'SELECT pg_export_snapshot()': exported}
        self._last = None

    def execute(self, sql, params=None):
        self.sql.append(sql)
        self._last = sql

    def fetchone(self):
        return (self._answers.get(self._last),)


class StatementFilterTest(SimpleTestCase):
    """Layer 4: the filter refuses every non-read before it reaches the server."""

    def _pass(self, sql, may_export=False):
        conn = types.SimpleNamespace(_replay_may_export=may_export)
        return guards.refuse_non_reads(lambda *a: 'ran', sql, (), False, {'connection': conn})

    def test_reads_and_the_exact_preamble_pass(self):
        for sql in ('SELECT 1', ' select * from x where a = %s', 'WITH a AS (SELECT 1) SELECT * FROM a',
                    'SHOW transaction_read_only', 'SAVEPOINT s1', 'RELEASE SAVEPOINT s1',
                    'ROLLBACK TO SAVEPOINT s1', guards.ISOLATION_SQL,
                    "SET TRANSACTION SNAPSHOT '00000003-0000001B-1'",
                    'SELECT "t"."into_date" FROM "t"'):
            self.assertEqual(self._pass(sql), 'ran', sql)

    def test_every_write_lock_and_setting_is_refused(self):
        for sql in ('INSERT INTO x VALUES (1)', 'UPDATE x SET a=1', 'DELETE FROM x', 'TRUNCATE x',
                    'CREATE TABLE y (a int)', 'ALTER TABLE x ADD b int', 'DROP TABLE x', 'GRANT ALL ON x TO y',
                    'COPY x TO STDOUT', 'LOCK TABLE x', 'MERGE INTO x USING y ON true WHEN MATCHED THEN DELETE',
                    'WITH d AS (DELETE FROM x RETURNING 1) SELECT * FROM d',
                    'SET default_transaction_read_only = on', 'SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY',
                    'SET TRANSACTION READ WRITE', "SET LOCAL statement_timeout = '1s'", 'SET statement_timeout = 0',
                    'SELECT * FROM x FOR UPDATE', 'SELECT * FROM x FOR NO KEY UPDATE', 'SELECT * FROM x FOR SHARE',
                    'SELECT * FROM x FOR KEY SHARE', 'SELECT * INTO y FROM x', "SELECT nextval('s')",
                    "SELECT set_config('a', 'b', false)", 'SELECT pg_advisory_lock(1)', 'SELECT lo_unlink(1)',
                    'SELECT pg_terminate_backend(1)', 'SELECT pg_export_snapshot()',
                    "SET TRANSACTION SNAPSHOT 'x'; DROP TABLE y",
                    "SET TRANSACTION SNAPSHOT '00000003-0000001B-1'; DROP TABLE y"):
            with self.assertRaises(guards.WriteRefused, msg=sql):
                self._pass(sql)

    def test_only_the_parent_may_export_its_snapshot(self):
        self.assertEqual(self._pass('SELECT pg_export_snapshot()', may_export=True), 'ran')

    def test_more_than_one_statement_is_refused(self):
        for sql in ('SELECT 1; COMMIT; DELETE FROM x', 'SELECT 1; SELECT 2', 'SELECT 1;;', 'SHOW x; RESET ALL'):
            with self.assertRaises(guards.WriteRefused, msg=sql):
                self._pass(sql)
        self.assertEqual(self._pass('SELECT 1;'), 'ran')                # one trailing ; is fine

    def test_quoted_schema_qualified_and_unlisted_function_calls_are_refused(self):
        for sql in ('SELECT "nextval"(1)', 'SELECT "setval"(1, 2)', "SELECT pg_catalog.nextval('s')",
                    'SELECT public.made_up_fn(1)', 'SELECT "public"."made_up_fn"(1)', 'SELECT nextval (1)',
                    'SELECT dblink_exec(1)', 'SELECT pg_sleep(100)', 'SELECT nextval/**/(1)',
                    'SELECT 1 -- a comment', 'SELECT * FROM made_up_fn(1)', 'SELECT U&"nextval"(1)'):
            with self.assertRaises(guards.WriteRefused, msg=sql):
                self._pass(sql)

    def test_listed_functions_and_sql_keywords_still_pass(self):
        for sql in ('SELECT COUNT(*) AS "__count" FROM "t"', 'SELECT "a" FROM "t" WHERE "b" IN (%s, %s)',
                    'SELECT COALESCE(SUM("t"."x"), 0) AS "s" FROM "t"',
                    'SELECT (1) AS "a" FROM "t" WHERE EXISTS (SELECT 1 FROM "u" WHERE ("u"."k" = %s)) LIMIT 1',
                    'SELECT LOWER("t"."c") FROM "t" WHERE NOT ("t"."m" = %s)'):
            self.assertEqual(self._pass(sql), 'ran', sql)

    def test_it_reuses_the_reviewed_dry_run_filter(self):
        self.assertIs(guards.WriteRefused, s4.WriteRefused)
        with mock.patch.object(guards, 'refuse_writes', wraps=s4.refuse_writes) as reused:
            self._pass('SELECT 1')
            with self.assertRaises(guards.WriteRefused):
                self._pass('DELETE FROM x')
        self.assertEqual(reused.call_count, 2)


class TransactionTest(SimpleTestCase):
    """Layer 2: repeatable read and read only for THIS transaction, proved; never a session setting."""

    def test_the_first_statements_make_the_transaction_read_only_and_prove_it(self):
        cur = _FakeCursor()
        self.assertIsNone(guards.begin_snapshot(cur))
        self.assertEqual(cur.sql[0], guards.ISOLATION_SQL)
        self.assertEqual(cur.sql[-2:], ['SHOW transaction_read_only', 'SHOW transaction_isolation'])

    def test_the_transaction_gives_way_with_transaction_level_timeouts(self):
        for export in (False, True):
            cur = _FakeCursor()
            guards.begin_snapshot(cur, export=export)
            sets = [s for s in cur.sql if s.startswith('SET LOCAL')]
            self.assertEqual([s.split(' =')[0] for s in sets],
                             ['SET LOCAL lock_timeout', 'SET LOCAL idle_in_transaction_session_timeout'])
            for s in sets:                                      # the filter lets exactly these through
                self.assertEqual(guards.refuse_non_reads(lambda *a: 'ran', s, (), False, {}), 'ran')
        with self.assertRaises(guards.WriteRefused):
            guards.refuse_non_reads(lambda *a: 'ran', "SET LOCAL lock_timeout = '0'", (), False, {})

    def test_a_child_joins_the_snapshot_before_any_read_and_the_parent_exports_it(self):
        cur = _FakeCursor()
        guards.begin_snapshot(cur, snapshot='00000003-0000001B-1')
        self.assertEqual(cur.sql[:2], [guards.ISOLATION_SQL, "SET TRANSACTION SNAPSHOT '00000003-0000001B-1'"])
        self.assertEqual(guards.begin_snapshot(_FakeCursor(), export=True), '00000003-0000001B-1')

    def test_a_transaction_that_is_not_read_only_or_not_repeatable_read_stops_the_run(self):
        with self.assertRaises(guards.WriteRefused):
            guards.begin_snapshot(_FakeCursor(read_only='off'))
        with self.assertRaises(guards.WriteRefused):
            guards.begin_snapshot(_FakeCursor(isolation='read committed'))
        with self.assertRaises(guards.WriteRefused):
            guards.begin_snapshot(_FakeCursor(), snapshot="1-1'; DROP TABLE x; --")

    def test_no_session_level_setting_anywhere_in_the_harness(self):
        for name in os.listdir(REPLAY_DIR):
            if name.endswith('.py'):
                src = open(os.path.join(REPLAY_DIR, name), encoding='utf-8').read()
                for banned in ('default_transaction_read_only', 'set_session', 'SESSION CHARACTERISTICS',
                               'autocommit'):
                    self.assertNotIn(banned, src, f'{name}: {banned}')

    def test_postgres_is_required_without_the_test_flag(self):
        with self.assertRaises(guards.WriteRefused):
            with guards.read_only_session():
                pass


class PreflightTest(SimpleTestCase):
    """Layer 5 (keys) and the connection rules: role, session pooler 5432, never 6543."""

    def test_a_clean_environment_passes(self):
        self.assertTrue(guards.check_environment({guards.DB_ENV: GOOD_URL, 'PATH': '/bin', 'GEMINI_API_KEY': ''}))

    def test_every_writing_paying_or_sending_key_is_refused_by_name_never_value(self):
        for name in ('GEMINI_API_KEY', 'OPENAI_API_KEY', 'DATABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY',
                     'SUPABASE_URL', 'GOOGLE_APPLICATION_CREDENTIALS', 'BREVO_API_KEY', 'EMAIL_HOST_PASSWORD',
                     'VIRCLE_SHEET_ID', 'CRON_SECRET', 'CRON_SECRET_PAYMENTS', 'TWILIO_AUTH_TOKEN', 'SENTRY_DSN',
                     'DB_HOST', 'DOCUMENT_BACKUP_BUCKET', 'VIRCLE_AIRTABLE_SECRET'):
            with self.assertRaises(guards.WriteRefused, msg=name) as cm:
                guards.check_environment({name: 'secret-value-123'})
            self.assertIn(name, str(cm.exception))
            self.assertNotIn('secret-value-123', str(cm.exception))

    def test_the_replay_url_passes_only_as_replay_ro_on_the_session_pooler(self):
        self.assertEqual(guards.check_database_url(GOOD_URL), ('pooler.example.test', 5432))
        for url in ('', GOOD_URL.replace(':5432', ':6543'), GOOD_URL.replace(':5432', ''),
                    GOOD_URL.replace('replay_ro.abcdefgh', 'postgres.abcdefgh'),
                    GOOD_URL.replace('replay_ro.abcdefgh', 'replay_rogue'),
                    GOOD_URL + '?options=-c%20default_transaction_read_only%3Don',
                    'sqlite:///tmp/x.db', 'mysql://replay_ro@h:5432/x'):
            with self.assertRaises(guards.WriteRefused, msg=url) as cm:
                guards.check_database_url(url)
            self.assertNotIn('pw-not-real', str(cm.exception))

    def test_only_sslmode_require_or_verify_may_ride_in_the_url(self):
        for q in ('sslmode=require', 'sslmode=verify-ca', 'sslmode=verify-full'):
            self.assertEqual(guards.check_database_url(GOOD_URL + '?' + q), ('pooler.example.test', 5432))
        for q in ('assume_role=postgres', 'hostaddr=10.0.0.1', 'service=made-up', 'sslmode=disable',
                  'sslmode=prefer', 'sslmode=require&sslmode=disable', 'sslmode=require&application_name=x',
                  'target_session_attrs=any', 'sslmode', 'passfile=x'):
            with self.assertRaises(guards.WriteRefused, msg=q):
                guards.check_database_url(GOOD_URL + '?' + q)

    def test_a_url_naming_more_than_one_host_is_refused(self):
        for host in ('h1,h2:5432', 'pooler.example.test,other.example.test:5432', 'h1:5432,h2:5432', ',h1:5432'):
            url = f'postgresql://replay_ro.abcdefgh:pw-not-real@{host}/postgres'
            with self.assertRaises(guards.WriteRefused, msg=host) as cm:
                guards.check_database_url(url)
            self.assertNotIn('pw-not-real', str(cm.exception))
        self.assertEqual(guards.check_database_url(GOOD_URL.replace('pw-not-real', 'pw,not,real')),
                         ('pooler.example.test', 5432))                   # a comma in the password is fine

    def test_an_encoded_host_list_socket_path_or_odd_host_is_refused(self):
        # dj_database_url URL-decodes the host: h1%2Ch2 reaches libpq as h1,h2 (two hosts to try).
        for host in ('h1%2Ch2:5432', 'h1%2ch2:5432', 'pooler.example.test%2C:5432', '%2Ch1:5432',
                     '%2Fvar%2Frun%2Fpostgresql:5432', '%2Ftmp:5432', '[::1]:5432', 'h1%20h2:5432',
                     'pooler_example.test:5432', '-pooler.example.test:5432', 'pooler..example.test:5432'):
            url = f'postgresql://replay_ro.abcdefgh:pw-not-real@{host}/postgres'
            with self.assertRaises(guards.WriteRefused, msg=host) as cm:
                guards.check_database_url(url)
            self.assertNotIn('pw-not-real', str(cm.exception))
        for host in ('aws-0-ap-southeast-1.pooler.supabase.com', '127.0.0.1', 'localhost'):
            url = f'postgresql://replay_ro.abcdefgh:pw-not-real@{host}:5432/postgres'
            self.assertEqual(guards.check_database_url(url), (host, 5432))

    def test_libpq_pg_variables_are_refused(self):
        for name in ('PGHOST', 'PGUSER', 'PGPASSWORD', 'PGOPTIONS', 'PGSERVICE', 'PGSSLMODE', 'PGSERVICEFILE'):
            with self.assertRaises(guards.WriteRefused, msg=name):
                guards.check_environment({guards.DB_ENV: GOOD_URL, name: 'made-up'})


class SessionTest(TestCase):
    """Layers 3 to 5 on the test database: refused, rolled back, doors shut, the run goes on."""

    def test_a_write_inside_the_session_is_refused_and_nothing_lands(self):
        app = make_application('submitted')
        with self.assertRaises(guards.WriteRefused):
            with guards.read_only_session(allow_sqlite=True):
                ScholarshipApplication.objects.filter(pk=app.pk).update(status='withdrawn')
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.pk).status, 'submitted')

    def test_the_transaction_is_rolled_back_on_success_and_on_error(self):
        with mock.patch('django.db.transaction.set_rollback') as rb:
            with guards.read_only_session(allow_sqlite=True):
                pass
            rb.assert_called_once_with(True)
        with mock.patch('django.db.transaction.set_rollback') as rb:
            with self.assertRaises(ValueError):
                with guards.read_only_session(allow_sqlite=True):
                    raise ValueError('x')
            rb.assert_called_once_with(True)

    def test_a_refused_write_in_one_case_is_recorded_by_class_and_the_next_case_runs(self):
        app = make_application('submitted')
        with guards.read_only_session(allow_sqlite=True):
            first = guards.run_case(lambda: ScholarshipApplication.objects.filter(pk=app.pk).update(status='closed'))
            second = guards.run_case(lambda: ScholarshipApplication.objects.get(pk=app.pk).status)
        self.assertEqual(first, {'error': 'WriteRefused'})
        self.assertEqual(second, 'submitted')

    def test_each_case_savepoint_is_rolled_back_even_on_success(self):
        app = make_application('submitted')
        guards.run_case(lambda: ScholarshipApplication.objects.filter(pk=app.pk).update(status='closed'))
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.pk).status, 'submitted')

    def test_storage_gemini_the_meter_and_email_are_shut(self):
        with guards.read_only_session(allow_sqlite=True):
            for call in (lambda: vision._fetch_image_bytes('p'), lambda: vision._call_gemini_json('m', 'p'),
                         lambda: usage.record_usage('gemini')):
                self.assertEqual(guards.run_case(call), {'error': 'Unreachable'})
            self.assertEqual(guards.run_case(lambda: mail.send_mail('s', 'b', 'a@example.test', ['b@example.test'])),
                             {'error': 'MailRefused'})

    def test_the_vision_word_reader_is_shut(self):
        # The client is a stand-in, so even with the door open (the bug) nothing can reach Google: gRPC
        # opens its sockets in C, past the socket guard.
        with mock.patch('google.cloud.vision.ImageAnnotatorClient') as client, netguard.refuse_network(), \
                guards.read_only_session(allow_sqlite=True):
            self.assertEqual(guards.run_case(lambda: vision._vision_words(b'not-an-image', 'image/png')),
                             {'error': 'Unreachable'})
        client.assert_not_called()

    def test_an_error_is_recorded_by_class_name_never_its_message(self):
        def boom():
            raise ValueError('Siti binti Ahmad 010203141234')
        rec = guards.run_case(boom)
        self.assertEqual(rec, {'error': 'ValueError'})
        self.assertNotIn('Siti', json.dumps(rec))

    def test_a_refused_connection_inside_a_case_is_recorded_by_class(self):
        with netguard.refuse_network():
            self.assertEqual(guards.run_case(lambda: urllib.request.urlopen('http://127.0.0.1:9/', timeout=1)),
                             {'error': 'NetworkRefused'})


class NetworkGuardTest(SimpleTestCase):
    """Layer 5: no outgoing connection but the database."""

    def test_a_connection_to_anything_else_is_refused(self):
        with netguard.refuse_network(allow={('127.0.0.1', 5432)}):
            with self.assertRaises(netguard.NetworkRefused):
                socket.create_connection(('127.0.0.1', 9), timeout=1)
            with self.assertRaises(netguard.NetworkRefused):
                urllib.request.urlopen('http://127.0.0.1:9/', timeout=1)

    def test_the_allowed_database_address_still_connects_and_the_guard_comes_off(self):
        srv = socket.socket()
        srv.bind(('127.0.0.1', 0))
        srv.listen(2)
        addr = srv.getsockname()
        try:
            with netguard.refuse_network(allow={addr}):
                socket.create_connection(addr, timeout=2).close()
            socket.create_connection(addr, timeout=2).close()
        finally:
            srv.close()


#: What an R2 adapter would register for these tests (made-up record fields and codes).
_TEST_CODES = ('status', 'unresolved', 'app', 'amount', 'merit', 'params', 'course', 'month', 'eligible', 'row', 'total',
               'sum', 'commit', 'ok', 'probable', 'higher_results_not_declared', 'tick:name', 'UP65A')


class ScrubTest(SimpleTestCase):
    """The output scrubber: only registered codes, amounts, hashes and ids leave; other text is hashed."""

    def setUp(self):
        for patcher in (mock.patch.object(scrub, '_REGISTERED', set()),
                        mock.patch.dict(scrub._STATE, frozen=False),       # engine_map froze it on import
                        mock.patch.object(scrub, 'INT_KEYS', scrub.INT_KEYS | {'app'})):  # as R2 would add
            patcher.start()
            self.addCleanup(patcher.stop)
        scrub.register_codes(_TEST_CODES)

    def test_codes_amounts_hashes_ids_and_months_are_kept(self):
        rec = {'status': 'probable', 'unresolved': ['higher_results_not_declared', 'tick:name'], 'app': 278,
               'amount': Decimal('3000'), 'merit': 87.5, 'params': scrub.text_hash('anything'),
               'course': 'UP65A', 'month': '2026-12', 'eligible': True, 'row': None, 'total': '1200.00'}
        out = scrub.scrub(rec)
        self.assertEqual(scrub.count_dropped(out), 0)
        self.assertEqual((out['amount'], out['merit']), ('3000.00', '87.50'))
        self.assertEqual({k: out[k] for k in ('status', 'app', 'course', 'month', 'eligible', 'row', 'total')},
                         {'status': 'probable', 'app': 278, 'course': 'UP65A', 'month': '2026-12',
                          'eligible': True, 'row': None, 'total': '1200.00'})

    def test_names_ics_phones_addresses_dates_and_free_text_are_dropped(self):
        for value in ('Siti binti Ahmad', 'AHMAD', 'Probable', '010203141234', '010203-14-1234', 10203141234,
                      '0123456789', 123456789, 'a.person@example.test', 'No 1, Jalan Mawar', 'A+',
                      datetime.date(2006, 1, 2), b'bytes', 'RM 3000', float('nan'), {'nested': 'Two Words'}):
            out = scrub.scrub({'status': value})
            self.assertGreater(scrub.count_dropped(out), 0, repr(value))
            if isinstance(value, str):
                self.assertNotIn(value, json.dumps(out))

    def test_lowercase_names_ics_phones_and_passports_never_leave_as_written(self):
        for value in ('siti', 'ahmad.bin.ali', 'ic:010203-14-1234', 'applications/123/010203-14-1234',
                      'tel:012-3456789', 'A12345678', 'muthusamy', 'defaced', 'kumar_a_l_raju'):
            out = scrub.scrub({'status': value, 'unresolved': [value]})
            self.assertNotIn(value, json.dumps(out), value)
            self.assertEqual(scrub.count_dropped(out), 2, value)
            self.assertTrue(out['status'].startswith(scrub.SCRUB_HASH_PREFIX), value)
        self.assertEqual(scrub.scrub({'status': 'siti'}), scrub.scrub({'status': 'siti'}))     # still comparable

    def test_a_key_that_is_not_a_code_is_dropped_with_its_value(self):
        out = scrub.scrub({'Siti binti Ahmad': 'probable', 'siti': 1, 'ahmad_bin_ali': 2, 'ok': True})
        self.assertEqual(out, {'!dropped_keys': 3, 'ok': True})
        self.assertEqual(scrub.scrub(out), out)                   # scrubbing twice changes nothing

    def test_only_registered_codes_leave_and_the_registry_takes_codes_only(self):
        self.assertEqual(scrub.scrub({'status': 'made_up_code'})['status'][:3], scrub.SCRUB_HASH_PREFIX)
        scrub.register_codes(['made_up_code'])
        self.assertEqual(scrub.scrub({'status': 'made_up_code'}), {'status': 'made_up_code'})
        for bad in ('Two Words', '', 'x' * 80, 'a\nb'):
            with self.assertRaises(ValueError, msg=bad):
                scrub.register_codes([bad])
        for code in ('event', 'side', 'old', 'new', 'new_again', 'same', 'differs', 'could_not_run', 'noise',
                     'joined', 'totals', 'fatal'):
            self.assertIn(code, scrub.R1_CODES)

    def test_an_error_leaves_as_its_class_name_only(self):
        self.assertEqual(scrub.error_record(KeyError('Siti binti Ahmad')), {'error': 'KeyError'})
        self.assertEqual(scrub.scrub(scrub.error_record(KeyError('x'))), {'error': 'KeyError'})
        self.assertEqual(scrub.scrub({'event': 'fatal', 'error': 'WriteRefused'}),
                         {'event': 'fatal', 'error': 'WriteRefused'})
        for rec in ({'error': 'Siti binti Ahmad 0102'}, {'error': 'Muthusamy'}, {'error': 'muthusamy'},
                    {'status': {'error': 'Muthusamy'}}, {'unresolved': [{'error': 'Muthusamy'}]}):
            self.assertNotIn('uthusamy', json.dumps(scrub.scrub(rec)), rec)
            self.assertNotIn('Siti', json.dumps(scrub.scrub(rec)), rec)
        mixed = scrub.scrub({'status': 'probable', 'error': 'KeyError'})    # not an error record
        self.assertTrue(mixed['error'].startswith(scrub.SCRUB_HASH_PREFIX))

    def test_a_decimal_or_float_at_or_above_the_cap_is_dropped(self):
        for value in (Decimal('990101145678'), Decimal('-990101145678'), 990101145678.0, Decimal('100000000'),
                      Decimal('99999999.999'), Decimal('1E+30')):
            out = scrub.scrub({'amount': value})
            self.assertEqual(out, {'amount': scrub.DROPPED}, repr(value))
            self.assertEqual(scrub.amount(value), scrub.DROPPED, repr(value))
        self.assertEqual(scrub.scrub({'amount': Decimal('99999999.99')}), {'amount': '99999999.99'})

    def test_a_commit_hash_shape_leaves_as_written_only_in_the_top_level_start_event(self):
        start = {'event': 'start', 'old_commit': '442b21f4d', 'new_commit': '5ccd952a7'}
        self.assertEqual(scrub.scrub(start), start)
        out = scrub.scrub({'event': 'start', 'old_commit': '442b21f4d', 'new_commit': '5ccd952a7',
                           'status': 'a12345678', 'commit': '442b21f4d', 'unresolved': ['a12345678']})
        self.assertEqual((out['old_commit'], out['new_commit']), ('442b21f4d', '5ccd952a7'))
        self.assertNotIn('a12345678', json.dumps(out))
        self.assertTrue(out['status'].startswith(scrub.SCRUB_HASH_PREFIX))
        self.assertTrue(out['commit'].startswith(scrub.SCRUB_HASH_PREFIX))
        self.assertEqual(scrub.count_dropped(out), 3)
        self.assertTrue(scrub.scrub({'event': 'start', 'old_commit': 'Siti binti Ahmad'})['old_commit']
                        .startswith('!h:'))
        for rec in ({'fields': {'old_commit': 'a12345678'}}, {'old_commit': 'a12345678'},
                    {'event': 'counts', 'old_commit': 'a12345678'},
                    {'unresolved': [{'event': 'start', 'old_commit': 'a12345678'}]},
                    {'event': 'start', 'fields': {'event': 'start', 'new_commit': 'a12345678'}}):
            self.assertNotIn('a12345678', json.dumps(scrub.scrub(rec)), rec)       # nested or not `start`
        for digits in ('123456789012', '0102031412'):
            out = scrub.scrub({'event': 'start', 'old_commit': digits})
            self.assertNotIn(digits, json.dumps(out), digits)              # all digits is never a commit

    def test_an_int_leaves_only_under_a_count_or_key_field(self):
        kept = {'event': 'counts', 'applications': 12, 'records': 3, 'exit': -9, 'key': [278, 1],
                'same': 4, 'app': 278}
        self.assertEqual(scrub.scrub(kept), kept)
        for rec in ({'status': 41234567}, {'unresolved': [990101, 14, 5678]}, {'row': 12},
                    {'fields': {'status': 123}}, {'sum': (990101, 14)}, {'unresolved': {41234567}}):
            out = scrub.scrub(rec)
            self.assertGreater(scrub.count_dropped(out), 0, rec)
            for n in ('41234567', '990101', '5678', '123'):
                self.assertNotIn(n, json.dumps(out), rec)
        self.assertEqual(scrub.scrub(41234567), scrub.DROPPED)                 # not under any key
        self.assertEqual(scrub.scrub({'key': [{'status': 990101}]}), {'key': [{'status': scrub.DROPPED}]})

    def test_the_dropped_keys_count_is_capped_like_any_int(self):
        out = scrub.scrub({'!dropped_keys': 990101145678, 'ok': 1})
        self.assertNotIn('990101145678', json.dumps(out))
        self.assertLess(out['!dropped_keys'], scrub.MAX_INT)
        self.assertEqual(scrub.scrub({'!dropped_keys': scrub.MAX_INT - 1, 'siti': 1})['!dropped_keys'],
                         scrub.MAX_INT - 1)
        self.assertEqual(scrub.scrub({'!dropped_keys': 2, 'siti': 1}), {'!dropped_keys': 3})

    def test_the_registry_refuses_ic_phone_passport_and_long_number_shapes(self):
        for bad in ('010203141234', '010203-14-1234', 'ic:010203-14-1234', 'tel:012-3456789', '0123456789',
                    '+60123456789', 'A12345678', 'a12345678', 'pp:A1234567', '123456', '99999999',
                    'ic_010203_14_1234', 'ic.010203.14.1234', 'ic/010203/14/1234', 'AB1234567', 'ab12345678',
                    'tel:012-345-6789', 'tel_03_4123_4567', 'd010203', 'x.0102.03', 'UP6500001',
                    'pp_ab_1234_567'):
            with self.assertRaises(ValueError, msg=bad):
                scrub.register_codes([bad])
            self.assertFalse(scrub.is_code(bad), bad)
        scrub.register_codes(['UP65A', 'tick:name', 'payments.schedule_row', '2026', 'row_12345', 'r1_2_3'])


class RegistryFreezeTest(SimpleTestCase):
    """Codes come only from the adapters' import-time literals: frozen once engine_map is imported."""

    def test_the_registry_is_frozen_once_the_engine_map_is_imported(self):
        importlib.import_module('apps.scholarship.eval.replay.engine_map')
        self.assertTrue(scrub._STATE['frozen'])
        with mock.patch.object(scrub, '_REGISTERED', set()):
            with self.assertRaises(scrub.RegistryFrozen):
                scrub.register_codes(['made_up_code'])
            self.assertFalse(scrub.is_code('made_up_code'))

    def test_no_code_under_apps_registers_codes_or_touches_the_registry_except_by_literal_calls(self):
        files = [os.path.join(d, f) for d, dirs, fs in os.walk(APPS_DIR) for f in fs
                 if f.endswith('.py') and not _is_test_file(d, f)]
        self.assertGreater(len(files), 100)
        scrub_file = os.path.normcase(os.path.abspath(scrub.__file__))
        self.assertIn(scrub_file, [os.path.normcase(os.path.abspath(p)) for p in files])
        bad = [f'{os.path.relpath(p, APPS_DIR)}:{line}' for p in files
               for line in _registry_tampering(p, is_scrub=os.path.normcase(os.path.abspath(p)) == scrub_file)]
        self.assertEqual(bad, [])

    def test_the_static_check_catches_a_bad_call_an_alias_and_a_direct_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'adapter.py')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(_BAD_ADAPTER)
            self.assertEqual(_registry_tampering(path),
                             [3, 4, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 24])
            path = os.path.join(tmp, 'scrub.py')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(_BAD_SCRUB)
            self.assertEqual(_registry_tampering(path, is_scrub=True), [11, 13, 15, 16, 18, 20])
        self.assertEqual(_registry_tampering(scrub.__file__, is_scrub=True), [])


#: One line per pattern; the test names the lines that must be caught (1-2, 5-6 and 22-23 are fine).
_BAD_ADAPTER = """from . import scrub
from . import scrub as sc
from .scrub import register_codes as rc
from .scrub import _REGISTERED
scrub.register_codes(("ok_code", "b"))
register_codes(["x"])
scrub.register_codes(names)
register_codes([n for n in x])
scrub.register_codes(("a", 1))
register_codes({"a"}, extra)
rc2 = scrub.register_codes
sc._REGISTERED.add("x")
scrub._REGISTERED.update({"x"})
scrub._REGISTERED |= {"x"}
scrub._STATE["frozen"] = False
sc._STATE.update(frozen=False)
setattr(scrub, "_REGISTERED", set())
apps.scholarship.eval.replay.scrub._STATE["frozen"] = False
importlib.reload(scrub)
scrub.INT_KEYS = frozenset({"phone"})
vars(scrub)["_STATE"]["frozen"] = False
x = scrub.text_hash("a")
y = scrub.SALT_ENV
from apps.scholarship.eval.replay.scrub import _STATE as st
"""

#: A scrub module that unfreezes, mutates or rebinds the registry outside its three owners.
_BAD_SCRUB = """_REGISTERED = set()
_STATE = {'salt': None, 'frozen': False}
def register_codes(codes):
    _REGISTERED.update(codes)
def freeze_registry():
    _STATE['frozen'] = True
def is_code(s):
    return s in _REGISTERED
def new_salt():
    _STATE['salt'] = 'x'
    _STATE['frozen'] = False
def sneak(c):
    _REGISTERED.add(c)
def reset():
    global _STATE
    _STATE = {}
def other():
    _STATE.update(frozen=False)
def freeze_registry_two(k):
    _STATE[k] = False
"""

APPS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(REPLAY_DIR)))
#: Names a non-scrub module may not spell as a string (setattr / getattr / vars tricks).
_REGISTRY_NAMES = frozenset({'register_codes', '_REGISTERED', '_STATE', 'INT_KEYS', 'R1_CODES'})
#: In scrub.py: the only functions that may touch `_REGISTERED`, and the only one that may set `frozen`.
_REGISTRY_OWNERS = frozenset({'register_codes', 'is_code'})


def _is_test_file(directory, name):
    parts = os.path.normpath(directory).split(os.sep)
    return 'tests' in parts or name.startswith('test_') or name in ('tests.py', 'conftest.py')


def _literal_codes_call(node):
    """True when the call's only argument is a literal tuple, set or list of string literals."""
    import ast
    arg = node.args[0] if len(node.args) == 1 and not node.keywords else None
    return isinstance(arg, (ast.Tuple, ast.Set, ast.List)) and all(
        isinstance(e, ast.Constant) and isinstance(e.value, str) for e in arg.elts)


def _registry_tampering(path, *, is_scrub=False):
    """Sorted line numbers in ``path`` that register codes or touch the scrub registry any way but a
    `register_codes(<literal strings>)` call: a non-literal call, an aliased import or reference of
    `register_codes`, any private, rebinding or deleting use of the scrub module's attributes, a reload of
    it, a registry name spelled as a string; and, in scrub.py itself (``is_scrub``), `_REGISTERED` used
    outside `register_codes` / `is_code`, `frozen` set to anything but True or outside `freeze_registry`,
    and `_STATE` rebound, declared global or changed by a method."""
    import ast
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    if not is_scrub and not any(n in src for n in _REGISTRY_NAMES | {'scrub'}):
        return []
    tree = ast.parse(src)
    lines, aliases, call_funcs = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            from_scrub = (node.module or '').split('.')[-1] == 'scrub'
            for a in node.names:
                if a.name == 'scrub':
                    aliases.add(a.asname or 'scrub')
                if from_scrub and (a.name.startswith('_')
                                   or (a.name == 'register_codes' and a.asname not in (None, a.name))):
                    lines.add(node.lineno)
        elif isinstance(node, ast.Import):
            aliases.update(a.asname for a in node.names if a.asname and a.name.split('.')[-1] == 'scrub')
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', None)
            if name == 'register_codes':
                call_funcs.add(id(func))
                if not _literal_codes_call(node):
                    lines.add(node.lineno)

    def is_scrub_module(expr):
        return (isinstance(expr, ast.Name) and expr.id in aliases) or (
            isinstance(expr, ast.Attribute) and expr.attr == 'scrub')

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr == '_REGISTERED' or (is_scrub_module(node.value) and (
                    node.attr.startswith('_') or not isinstance(node.ctx, ast.Load))):
                lines.add(node.lineno)
            elif node.attr == 'register_codes' and id(node) not in call_funcs:
                lines.add(node.lineno)
        elif isinstance(node, ast.Name) and node.id == 'register_codes' and id(node) not in call_funcs:
            lines.add(node.lineno)
        elif isinstance(node, ast.Constant) and not is_scrub and node.value in _REGISTRY_NAMES:
            lines.add(node.lineno)
        elif isinstance(node, ast.Call) and getattr(node.func, 'attr', getattr(node.func, 'id', None)) == 'reload' \
                and any(is_scrub_module(a) for a in node.args):
            lines.add(node.lineno)
    if is_scrub:
        lines |= _scrub_module_tampering(tree)
    return sorted(lines)


def _scrub_module_tampering(tree):
    import ast
    lines = set()
    owners = [(None, stmt) for stmt in tree.body if not isinstance(stmt, ast.FunctionDef)]
    owners += [(stmt.name, stmt) for stmt in tree.body if isinstance(stmt, ast.FunctionDef)]
    for fname, top in owners:
        for node in ast.walk(top):
            if isinstance(node, ast.Global) and {'_STATE', '_REGISTERED'} & set(node.names):
                lines.add(node.lineno)
            elif isinstance(node, ast.Name) and node.id == '_REGISTERED' and fname not in _REGISTRY_OWNERS \
                    and not (fname is None and isinstance(node.ctx, ast.Store)):
                lines.add(node.lineno)
            elif isinstance(node, ast.Name) and node.id == '_STATE' and fname is not None \
                    and not isinstance(node.ctx, ast.Load):
                lines.add(node.lineno)
            elif isinstance(node, ast.Attribute) and getattr(node.value, 'id', None) == '_STATE':
                lines.add(node.lineno)                                  # _STATE.update(...) and kin
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Subscript) and getattr(t.value, 'id', None) == '_STATE':
                        key = t.slice.value if isinstance(t.slice, ast.Constant) else None
                        if key is None or (key == 'frozen' and not (
                                fname == 'freeze_registry' and isinstance(node.value, ast.Constant)
                                and node.value.value is True)):
                            lines.add(node.lineno)
            elif isinstance(node, (ast.AugAssign, ast.Delete)) and any(
                    isinstance(t, ast.Subscript) and getattr(t.value, 'id', None) == '_STATE'
                    for t in getattr(node, 'targets', [getattr(node, 'target', None)])):
                lines.add(node.lineno)
    return lines


_PROBE = '''import datetime
from datetime import date, datetime as dt
from django.utils.timezone import now


def today_a():
    return date.today()


def today_b():
    return datetime.date.today()


def now_c():
    return now()


def now_d():
    return dt.now(datetime.timezone.utc)


def is_date(v):
    return isinstance(v, date)
'''


class ClockTest(SimpleTestCase):
    """The pinned clock: one instant for every clock the engines read."""

    INSTANT = datetime.datetime(2026, 11, 20, 18, 0, tzinfo=datetime.timezone.utc)
    NAME = 'apps.scholarship._replay_clock_probe'

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, 'probe.py')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(_PROBE)
        spec = importlib.util.spec_from_file_location(self.NAME, path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        sys.modules[self.NAME] = self.mod
        self.addCleanup(sys.modules.pop, self.NAME, None)

    def test_every_clock_reads_the_instant_inside_and_the_real_clock_outside(self):
        with clock.pinned_clock(self.INSTANT):
            local = self.INSTANT.astimezone().date()
            self.assertEqual((timezone.now(), self.mod.now_c(), self.mod.now_d()), (self.INSTANT,) * 3)
            self.assertEqual((self.mod.today_a(), self.mod.today_b()), (local, local))
            self.assertTrue(self.mod.is_date(datetime.date(2020, 1, 1)))   # isinstance still true
        self.assertIs(self.mod.date, datetime.date)
        self.assertIs(self.mod.now, timezone.now)
        self.assertGreater(abs(timezone.now() - self.INSTANT), datetime.timedelta(seconds=1))

    def test_a_naive_instant_is_refused(self):
        with self.assertRaises(ValueError):
            with clock.pinned_clock(datetime.datetime(2026, 11, 20)):
                pass


class ReplaySettingsTest(SimpleTestCase):
    """The job's settings: the replay URL only, keys blanked, mail refused, logging off."""

    def test_settings_blank_every_key_and_refuse_mail(self):
        env = {guards.DB_ENV: GOOD_URL, 'GEMINI_API_KEY': 'should-not-survive'}
        with mock.patch.dict(os.environ, env):
            mod = importlib.reload(importlib.import_module('apps.scholarship.eval.replay.settings'))
        self.assertEqual((mod.GEMINI_API_KEY, mod.SUPABASE_SERVICE_ROLE_KEY), ('', ''))
        self.assertTrue(mod.EMAIL_BACKEND.endswith('guards.RefusingEmailBackend'))
        self.assertFalse(mod.DEBUG)
        db = mod.DATABASES['default']
        self.assertEqual((db['PORT'], db['USER'], db['CONN_MAX_AGE']), (5432, 'replay_ro.abcdefgh', 0))
        self.assertEqual(mod.LOGGING['root']['level'], 'CRITICAL')
