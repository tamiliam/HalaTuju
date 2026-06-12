"""Tests for the refresh_stpm wrapper + its archive helpers + send_refresh_reminder.

The wrapper orchestrates other management commands, so we patch its module-level
`call_command` and assert the ORDER + the dry-run/apply pass-through + that a
scrape failure aborts before the sync (the catalogue-wipe safety property). No
Playwright/Selenium/DB is touched (sub-commands are mocked); archive logic is a
pure helper tested against a temp dir.
"""
import datetime
import os
import tempfile

from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from apps.courses.management.commands.refresh_stpm import dated_archive_name, prune_archive

CMD = 'apps.courses.management.commands.refresh_stpm'
RCMD = 'apps.courses.management.commands.send_refresh_reminder'


class ArchiveHelpersTest(SimpleTestCase):
    def test_dated_archive_name(self):
        self.assertEqual(dated_archive_name(datetime.datetime(2026, 6, 12)), 'mohe_2026-06-12.csv')

    def test_prune_keeps_newest_and_ignores_other_files(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ('mohe_2026-01-01.csv', 'mohe_2026-02-01.csv', 'mohe_2026-03-01.csv'):
                open(os.path.join(d, name), 'w').close()
            open(os.path.join(d, 'notes.txt'), 'w').close()  # non-matching, must survive
            deleted = prune_archive(d, keep=2)
            self.assertEqual(deleted, ['mohe_2026-01-01.csv'])  # oldest dropped (ISO names sort chronologically)
            remaining = set(os.listdir(d))
            self.assertEqual(remaining, {'mohe_2026-02-01.csv', 'mohe_2026-03-01.csv', 'notes.txt'})

    def test_prune_keep_zero_is_noop(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, 'mohe_2026-01-01.csv'), 'w').close()
            self.assertEqual(prune_archive(d, keep=0), [])
            self.assertTrue(os.path.exists(os.path.join(d, 'mohe_2026-01-01.csv')))


class OrchestrationTest(SimpleTestCase):
    @patch(f'{CMD}.prune_archive', return_value=[])
    @patch(f'{CMD}.os.makedirs')
    @patch(f'{CMD}.call_command')
    def test_scrape_then_sync_dryrun_then_audit(self, cc, _mk, _pr):
        call_command('refresh_stpm')
        names = [c.args[0] for c in cc.call_args_list]
        self.assertEqual(names, ['scrape_mohe_stpm', 'sync_stpm_mohe', 'audit_data'])
        self.assertNotIn('apply', cc.call_args_list[1].kwargs)  # sync is dry-run by default

    @patch(f'{CMD}.prune_archive', return_value=[])
    @patch(f'{CMD}.os.makedirs')
    @patch(f'{CMD}.call_command')
    def test_apply_passes_through_to_sync(self, cc, _mk, _pr):
        call_command('refresh_stpm', apply=True)
        self.assertTrue(cc.call_args_list[1].kwargs.get('apply'))

    @patch(f'{CMD}.prune_archive', return_value=[])
    @patch(f'{CMD}.os.makedirs')
    @patch(f'{CMD}.call_command')
    def test_validate_urls_runs_only_when_flagged(self, cc, _mk, _pr):
        call_command('refresh_stpm', validate_urls=True)
        names = [c.args[0] for c in cc.call_args_list]
        self.assertEqual(names, ['scrape_mohe_stpm', 'validate_stpm_urls', 'sync_stpm_mohe', 'audit_data'])

    @patch(f'{CMD}.call_command')
    def test_csv_skips_scrape(self, cc):
        call_command('refresh_stpm', csv='given.csv')
        names = [c.args[0] for c in cc.call_args_list]
        self.assertEqual(names, ['sync_stpm_mohe', 'audit_data'])  # no scrape, no archive

    @patch(f'{CMD}.prune_archive', return_value=[])
    @patch(f'{CMD}.os.makedirs')
    @patch(f'{CMD}.call_command')
    def test_scrape_failure_aborts_before_sync(self, cc, _mk, _pr):
        def boom(name, *a, **k):
            if name == 'scrape_mohe_stpm':
                raise CommandError('Scrape looks INCOMPLETE')
        cc.side_effect = boom
        with self.assertRaises(CommandError):
            call_command('refresh_stpm')
        names = [c.args[0] for c in cc.call_args_list]
        self.assertEqual(names, ['scrape_mohe_stpm'])  # sync + audit never reached

    @patch(f'{CMD}.prune_archive', return_value=[])
    @patch(f'{CMD}.os.makedirs')
    @patch(f'{CMD}.call_command')
    def test_sync_guard_block_aborts_before_audit(self, cc, _mk, _pr):
        def boom(name, *a, **k):
            if name == 'sync_stpm_mohe':
                raise CommandError('Refusing to apply: would deactivate 80%')
        cc.side_effect = boom
        with self.assertRaises(CommandError):
            call_command('refresh_stpm', apply=True)
        names = [c.args[0] for c in cc.call_args_list]
        self.assertEqual(names, ['scrape_mohe_stpm', 'sync_stpm_mohe'])  # audit never reached


class ReminderTest(SimpleTestCase):
    @override_settings(COURSE_REFRESH_REMINDER_EMAIL='admin@example.com', DEFAULT_FROM_EMAIL='noreply@example.com')
    @patch(f'{RCMD}.send_mail', return_value=1)
    def test_sends_to_configured_recipient(self, sm):
        call_command('send_refresh_reminder')
        sm.assert_called_once()
        self.assertEqual(sm.call_args.args[3], ['admin@example.com'])  # recipient list

    @override_settings(COURSE_REFRESH_REMINDER_EMAIL='', DEFAULT_FROM_EMAIL='fallback@example.com')
    @patch(f'{RCMD}.send_mail', return_value=1)
    def test_falls_back_to_default_from_email(self, sm):
        call_command('send_refresh_reminder')
        self.assertEqual(sm.call_args.args[3], ['fallback@example.com'])

    @override_settings(COURSE_REFRESH_REMINDER_EMAIL='', DEFAULT_FROM_EMAIL='')
    @patch(f'{RCMD}.send_mail')
    def test_noop_without_recipient(self, sm):
        call_command('send_refresh_reminder')
        sm.assert_not_called()
