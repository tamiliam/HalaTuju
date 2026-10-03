"""TD-290 + TD-294 (2026-10-03): our own log lines reach Cloud Logging WITH a severity.

Cloud Run stores a JSON stdout line as `jsonPayload` and lifts its `severity` field into the entry's
severity. The old console format was a JSON-shaped format STRING with `level` and no `severity`, so
every warning and error we wrote was stored at DEFAULT and no alert could fire on one; and a message
with a quote, or a traceback, was not JSON at all. `halatuju/logging_json.py` replaced it.

What is pinned here, through the formatter BUILT FROM THE SETTINGS DICT (not a hand-made one):
  * each Python level carries the matching Cloud Logging `severity`;
  * `message` is byte-for-byte `record.getMessage()` — the `applicant_record_reads` metric regexes
    `jsonPayload.message` for `^AUDIT applicant_detail_read`, so an audit line may not change;
  * a quote, a newline and a traceback still make ONE valid JSON object, the traceback in
    `stack_trace` and never in `message`;
  * production really uses it: `base.py` routes the console handler through `json`, and neither
    `production.py` nor anything but `development.py` re-points it.
TD-294: the auth.users lookup failure names its caller and is logged at ERROR, with its traceback.
"""
import ast
import json
import logging
import logging.config
import os
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from apps.scholarship.tests.source_walk import read_source

SETTINGS_DIR = os.path.join(settings.BASE_DIR, 'halatuju', 'settings')
AUDIT = 'AUDIT applicant_detail_read admin_id=7 app_id=42'


def _base_logging():
    """`LOGGING` exactly as `base.py` WRITES it — read from the source, because `development.py`
    (which the test run imports) re-points the console handler at `simple` in place."""
    tree = ast.parse(read_source(os.path.join(SETTINGS_DIR, 'base.py'),
                                 'TD-290: the production LOGGING dict lives in settings/base.py'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'LOGGING' for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError('settings/base.py no longer assigns LOGGING — TD-290 reads it there')


def _formatter():
    cfg = _base_logging()
    return logging.config.DictConfigurator(cfg).configure_formatter(cfg['formatters']['json'])


def _line(level, msg, *args, exc_info=None, name='apps.scholarship.views_admin'):
    record = logging.LogRecord(name, level, __file__, 1, msg, args, exc_info)
    out = _formatter().format(record)
    return out, json.loads(out)


class TheProductionFormatterCarriesSeverity(SimpleTestCase):

    def test_production_routes_the_console_through_the_json_formatter(self):
        cfg = _base_logging()
        self.assertEqual(cfg['handlers']['console']['formatter'], 'json')
        self.assertEqual(cfg['formatters']['json']['()'], 'halatuju.logging_json.CloudRunJsonFormatter')
        prod = read_source(os.path.join(SETTINGS_DIR, 'production.py'), 'TD-290: production settings')
        self.assertIn('from .base import *', prod)
        self.assertNotIn('LOGGING', prod, 'production.py must not re-point the console formatter')

    def test_each_level_carries_its_severity(self):
        for level, severity in ((logging.DEBUG, 'DEBUG'), (logging.INFO, 'INFO'),
                                (logging.WARNING, 'WARNING'), (logging.ERROR, 'ERROR'),
                                (logging.CRITICAL, 'CRITICAL')):
            with self.subTest(severity=severity):
                _out, body = _line(level, 'x')
                self.assertEqual(body['severity'], severity)
                self.assertEqual(body['level'], severity)

    def test_an_unnamed_level_is_default_never_dropped(self):
        self.assertEqual(_line(25, 'x')[1]['severity'], 'DEFAULT')

    def test_the_audit_line_is_byte_identical_and_keeps_the_old_keys_in_order(self):
        out, body = _line(logging.INFO, AUDIT)
        self.assertEqual(body['message'], AUDIT)
        self.assertEqual(list(body), ['timestamp', 'level', 'logger', 'message', 'severity'])
        self.assertEqual(body['logger'], 'apps.scholarship.views_admin')
        self.assertNotIn('\n', out)

    def test_a_quote_and_a_newline_still_make_one_json_object(self):
        msg = 'Vircle said "no"\nsecond line — ரவி'
        out, body = _line(logging.WARNING, '%s', msg)
        self.assertEqual(body['message'], msg)
        self.assertNotIn('\n', out)

    def test_a_traceback_goes_to_stack_trace_not_message(self):
        try:
            1 / 0
        except ZeroDivisionError:
            import sys
            out, body = _line(logging.ERROR, 'Failed to fetch auth.users data for %s',
                              'the applicant login email', exc_info=sys.exc_info())
        self.assertEqual(body['severity'], 'ERROR')
        self.assertEqual(body['message'], 'Failed to fetch auth.users data for the applicant login email')
        self.assertIn('ZeroDivisionError', body['stack_trace'])
        self.assertNotIn('\n', out)


class TheAuthLookupFailureNamesItsCaller(SimpleTestCase):
    """TD-294: the officer's applicant-detail GET used to log a 'CSV export' failure."""

    def test_the_failure_is_an_error_naming_the_purpose(self):
        from apps.courses import views_admin
        with mock.patch.object(views_admin, 'connection') as conn, \
                self.assertLogs('apps.courses.views_admin', level='ERROR') as cm:
            conn.cursor.side_effect = RuntimeError('auth schema unreachable')
            self.assertEqual(views_admin._fetch_auth_data(['u1'], purpose='the applicant login email'), {})
        self.assertEqual(cm.records[0].levelname, 'ERROR')
        self.assertEqual(cm.records[0].getMessage(),
                         'Failed to fetch auth.users data for the applicant login email')
        self.assertIsNotNone(cm.records[0].exc_info)

    def test_the_csv_export_keeps_its_own_words(self):
        from apps.courses import views_admin
        with mock.patch.object(views_admin, 'connection') as conn, \
                self.assertLogs('apps.courses.views_admin', level='ERROR') as cm:
            conn.cursor.side_effect = RuntimeError('x')
            views_admin._fetch_auth_data(['u1'])
        self.assertEqual(cm.records[0].getMessage(), 'Failed to fetch auth.users data for CSV export')

    def test_the_applicant_detail_serializer_names_itself(self):
        src = read_source(os.path.join(settings.BASE_DIR, 'apps', 'scholarship', 'serializers_admin.py'),
                          'TD-294: the detail serializer is the second caller of _fetch_auth_data')
        self.assertEqual(src.count("purpose='the applicant login email'"), 1)
