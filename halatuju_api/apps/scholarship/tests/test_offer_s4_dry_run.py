"""The S4 production dry run (`eval/offer_s4_dry_run.py`): one read-only transaction, always rolled
back, no write ever sent, Storage / Gemini / the meter unreachable, ids and outcomes only in its output.

Synthetic twins only (`test_no_gitignored_corpus.py`): invented people and letters in a temp corpus; the
"database" is the test SQLite (with `--allow-sqlite`) or a fake cursor. Never production."""
import json
import os
import tempfile
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship import vision
from apps.scholarship.eval import offer_s4_dry_run as dr
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_course_match import BPP, UPM, seed_realign_catalogue


class _FakeCursor:
    def __init__(self, read_only='on'):
        self.sql, self.read_only = [], read_only

    def execute(self, sql, params=None):
        self.sql.append(sql)

    def fetchone(self):
        return (self.read_only,)


class GuardTest(SimpleTestCase):
    def _pass(self, sql):
        return dr.refuse_writes(lambda *a: 'ran', sql, (), False, {})

    def test_reads_pass(self):
        for sql in ('SELECT 1', '  select * from x', 'WITH a AS (SELECT 1) SELECT * FROM a', 'SHOW x',
                    'SET TRANSACTION READ ONLY', 'SAVEPOINT s1', 'RELEASE SAVEPOINT s1'):
            self.assertEqual(self._pass(sql), 'ran', sql)

    def test_every_write_and_any_other_set_is_refused_before_the_server(self):
        for sql in ('INSERT INTO x VALUES (1)', 'UPDATE x SET a=1', 'DELETE FROM x', 'TRUNCATE x',
                    'CREATE TABLE y (a int)', 'ALTER TABLE x ADD b int', 'DROP TABLE x', 'GRANT ALL ON x TO y',
                    'SET default_transaction_read_only = on', 'SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY',
                    'WITH d AS (DELETE FROM x RETURNING 1) SELECT * FROM d', 'COPY x TO STDOUT', 'LOCK TABLE x'):
            with self.assertRaises(dr.WriteRefused, msg=sql):
                self._pass(sql)

    def test_the_first_statement_makes_the_transaction_read_only_and_proves_it(self):
        cur = _FakeCursor()
        dr.begin_read_only(cur)
        self.assertEqual(cur.sql, ['SET TRANSACTION READ ONLY', 'SHOW transaction_read_only'])
        with self.assertRaises(dr.WriteRefused):
            dr.begin_read_only(_FakeCursor(read_only='off'))

    def test_no_session_level_setting_is_ever_sent(self):
        src = open(dr.__file__, encoding='utf-8').read()
        self.assertNotIn('default_transaction_read_only', src)
        self.assertNotIn('set_session', src)
        self.assertNotIn('autocommit', src)

    def test_postgres_is_required_without_the_test_flag(self):
        with self.assertRaises(dr.WriteRefused):
            with dr.read_only_rollback():
                pass


class SessionTest(TestCase):
    def test_a_write_inside_the_session_is_refused(self):
        app = make_application('submitted')
        with self.assertRaises(dr.WriteRefused):
            with dr.read_only_rollback(allow_sqlite=True):
                ApplicantDocument.objects.create(application=app, doc_type='offer_letter', storage_path='x')
        self.assertFalse(ApplicantDocument.objects.filter(storage_path='x').exists())

    def test_the_transaction_is_rolled_back_on_success_and_on_error(self):
        with mock.patch('django.db.transaction.set_rollback') as rb:
            with dr.read_only_rollback(allow_sqlite=True):
                pass
            rb.assert_called_once_with(True)
        with mock.patch('django.db.transaction.set_rollback') as rb:
            with self.assertRaises(RuntimeError):
                with dr.read_only_rollback(allow_sqlite=True):
                    raise RuntimeError('boom')
            rb.assert_called_once_with(True)

    def test_storage_gemini_and_the_meter_are_unreachable(self):
        from apps.scholarship import usage
        with dr.read_only_rollback(allow_sqlite=True):
            for call in (lambda: vision._fetch_image_bytes('x'), lambda: vision._call_gemini_json('p', {}),
                         lambda: usage.record_usage('gemini')):
                with self.assertRaises(dr.Unreachable):
                    call()


class RunTest(TestCase):
    """End to end on invented letters: stored vs S4, ids and outcomes only, the rows untouched."""

    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self._tmp.name, 'snapshots'))
        self.app = make_application('submitted', chosen_pathway='university', chosen_programme={
            'course_id': 'UP4310001', 'course_name': 'Diploma Pembangunan Manusia'})
        prof = self.app.profile
        self.stored = {'candidate_name': prof.name, 'candidate_nric': prof.nric.replace('-', ''),
                       'programme': 'DIPLOMA PEMBANGUNAN MANUSIA', 'institution': 'KOLEJ SRI RAJANG',
                       'issuer': BPP}
        self.doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter', storage_path=f'{self.app.id}/offer/x',
            vision_fields={'fields': dict(self.stored), 'authenticity': {'status': 'genuine'},
                           'student_verdict': 'ok', 'warnings': [], 'error': ''},
            vision_run_at=timezone.now())
        self.key = f'offer_letter__a{self.app.id}__d{self.doc.id}'
        s4 = {**self.stored, 'institution': UPM, 'campus': 'KAMPUS BINTULU',
              'reporting_venue': 'KOLEJ SRI RAJANG'}
        with open(os.path.join(self._tmp.name, 'snapshots', self.key + dr.S4_SUFFIX), 'w', encoding='utf-8') as fh:
            json.dump({'fields': s4}, fh)

    def tearDown(self):
        self._tmp.cleanup()

    def test_stored_and_s4_are_planned_side_by_side_and_nothing_changes(self):
        lines = []
        rc = dr.main(['--eval-dir', self._tmp.name, '--allow-sqlite'], out=lines.append)
        self.assertEqual(rc, 0)
        self.doc.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual(self.doc.vision_fields['fields'], self.stored)          # the row is untouched
        self.assertEqual(self.app.chosen_programme['course_id'], 'UP4310001')
        rows, totals = dr.dry_run(self._tmp.name, [self.key], session=lambda: dr.read_only_rollback(allow_sqlite=True),
                              out=lambda *_: None)
        r = rows[self.key]
        self.assertEqual((r['doc'], r['app'], r['live']), (self.doc.id, self.app.id, True))
        self.assertEqual(r['stored']['ticks']['name'], r['s4']['ticks']['name'])
        self.assertEqual(r['stored']['ticks']['ic'], r['s4']['ticks']['ic'])
        self.assertEqual(totals['letters'], 1)
        self.assertEqual((r['stored']['not_offer_dated'], totals['not_offer_dated:s4']), (False, 0))
        self.assertEqual(dr.S4_SUFFIX, '.fresh_s4c.json')               # the final reader's caches
        text = '\n'.join(lines).upper()
        prof = self.app.profile
        for secret in (prof.name.upper(), prof.nric.replace('-', ''), 'SRI RAJANG', 'BINTULU', 'PEMBANGUNAN'):
            self.assertNotIn(secret, text)
        self.assertIn(f'doc={self.doc.id}', text.lower())
        self.assertTrue(lines[-1].startswith('totals: '))

    def test_the_money_ruling_reach_is_counted(self):
        self.doc.vision_fields = {**self.doc.vision_fields, 'authenticity': {'status': 'not_offer_letter'},
                                  'fields': {**self.stored, 'intake': 'SESI 2025/2026'}}
        self.doc.save(update_fields=['vision_fields'])
        rows, totals = dr.dry_run(self._tmp.name, [self.key], session=lambda: dr.read_only_rollback(allow_sqlite=True),
                                  out=lambda *_: None)
        self.assertTrue(rows[self.key]['stored']['not_offer_dated'])
        self.assertEqual(totals['not_offer_dated:stored'], 1)

    def test_a_key_with_no_document_is_counted_not_guessed(self):
        lines = []
        dr.dry_run(self._tmp.name, ['offer_letter__a1__d999999'],
               session=lambda: dr.read_only_rollback(allow_sqlite=True), out=lines.append)
        self.assertIn('no_document=1', lines[-1])

    def test_campus_tokens_never_print_a_name(self):
        self.assertEqual(dr.campus_token({'institution_id': 'RA-UPM', 'institution': UPM}), 'RA-UPM')
        tok = dr.campus_token({'institution': UPM})
        self.assertTrue(tok.startswith('h:') and 'PUTRA' not in tok.upper())
        self.assertEqual(dr.campus_token({}), '-')
