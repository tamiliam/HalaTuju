"""The admin System health light (2026-10-28): the five detectors, each threshold, and the endpoint.

The recorders (email backend, cron) have their own file, `test_system_health_recorders.py`.
"""
from datetime import timedelta

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.scholarship import system_health_store as store
from apps.scholarship.cron_health import DAILY, EVERY_15_MIN, EXPECTED_CADENCE, HOURLY, WEEKLY
from apps.scholarship.models import ApplicantDocument, SystemHealthStatus
from apps.scholarship.services import system_health as sh
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application,
)
from apps.scholarship.views import CronRunView

_402 = ('All AI models failed: gemini-2.5-flash: 402 RESOURCE_EXHAUSTED. Your prepayment credits '
        'are depleted.')
_SERVICE_DOWN = 'All AI models failed: gemini-2.5-flash: 503 UNAVAILABLE'


def _iso(dt):
    return dt.isoformat()


# ── Email ──────────────────────────────────────────────────────────────────────────────────

class EmailRow(SimpleTestCase):
    def setUp(self):
        self.now = timezone.now()

    def row(self, **data):
        return sh.email_row(self.now, data)

    def test_nothing_recorded_is_green(self):
        r = sh.email_row(self.now, None)
        self.assertEqual((r['status'], r['code']), ('green', 'no_record'))

    def test_all_sent_is_green_with_last_ok(self):
        ok = self.now - timedelta(minutes=5)
        r = self.row(last_ok_at=_iso(ok), consecutive_failures=0)
        self.assertEqual((r['status'], r['code']), ('green', 'ok'))
        self.assertEqual(r['last_ok_at'], ok.isoformat())

    def test_three_failures_running_is_red(self):
        r = self.row(last_ok_at=_iso(self.now - timedelta(minutes=30)),
                     last_fail_at=_iso(self.now), consecutive_failures=3)
        self.assertEqual((r['status'], r['code']), ('red', 'failing'))
        self.assertEqual(r['params']['count'], '3')

    def test_two_failures_running_within_the_hour_is_only_amber(self):
        r = self.row(last_ok_at=_iso(self.now - timedelta(minutes=30)),
                     last_fail_at=_iso(self.now - timedelta(minutes=10)), consecutive_failures=2)
        self.assertEqual((r['status'], r['code']), ('amber', 'recent_failure'))

    def test_failures_and_no_success_in_24h_is_red(self):
        r = self.row(last_ok_at=_iso(self.now - timedelta(hours=30)),
                     last_fail_at=_iso(self.now - timedelta(hours=5)), consecutive_failures=1)
        self.assertEqual((r['status'], r['code']), ('red', 'no_success'))

    def test_failures_and_never_a_success_is_red(self):
        r = self.row(last_fail_at=_iso(self.now - timedelta(hours=2)), consecutive_failures=1)
        self.assertEqual(r['status'], 'red')

    def test_an_old_failure_with_sends_since_is_green(self):
        r = self.row(last_ok_at=_iso(self.now - timedelta(minutes=5)),
                     last_fail_at=_iso(self.now - timedelta(hours=3)), consecutive_failures=0)
        self.assertEqual(r['status'], 'green')


# ── Scheduled jobs ─────────────────────────────────────────────────────────────────────────

class JobState(SimpleTestCase):
    def setUp(self):
        self.now = timezone.now()
        self.long_ago = self.now - timedelta(days=30)

    def state(self, cadence, since=None, **data):
        return sh.job_state(self.now, cadence, data or None, since)[:2]

    def test_on_time_is_green(self):
        self.assertEqual(self.state(HOURLY, last_ok_at=_iso(self.now - timedelta(minutes=50))),
                         ('green', 'ok'))

    def test_inside_the_grace_is_still_green(self):
        # hourly: grace is the 10-minute floor, so 69 minutes is on time
        self.assertEqual(self.state(HOURLY, last_ok_at=_iso(self.now - timedelta(minutes=69))),
                         ('green', 'ok'))

    def test_one_missed_run_is_amber(self):
        self.assertEqual(self.state(HOURLY, last_ok_at=_iso(self.now - timedelta(minutes=75))),
                         ('amber', 'late'))

    def test_two_missed_runs_is_red(self):
        self.assertEqual(self.state(HOURLY, last_ok_at=_iso(self.now - timedelta(minutes=131))),
                         ('red', 'missed'))

    def test_daily_grace_is_a_tenth_of_the_day(self):
        self.assertEqual(self.state(DAILY, last_ok_at=_iso(self.now - timedelta(hours=26))),
                         ('green', 'ok'))
        self.assertEqual(self.state(DAILY, last_ok_at=_iso(self.now - timedelta(hours=27))),
                         ('amber', 'late'))

    def test_last_run_errored_is_amber(self):
        self.assertEqual(self.state(HOURLY, last_ok_at=_iso(self.now - timedelta(minutes=50)),
                                    consecutive_errors=1), ('amber', 'errored'))

    def test_errored_twice_running_is_red(self):
        self.assertEqual(self.state(HOURLY, last_ok_at=_iso(self.now - timedelta(minutes=50)),
                                    consecutive_errors=2), ('red', 'errored_twice'))

    def test_no_record_soon_after_deploy_is_waiting(self):
        since = self.now - timedelta(minutes=100)  # under 2 x hourly + grace
        self.assertEqual(self.state(HOURLY, since=since), ('green', 'waiting'))

    def test_no_record_and_no_since_is_waiting(self):
        self.assertEqual(self.state(WEEKLY), ('green', 'waiting'))

    def test_no_record_long_after_deploy_is_red_never(self):
        self.assertEqual(self.state(HOURLY, since=self.now - timedelta(hours=3)), ('red', 'never'))


class CronRow(SimpleTestCase):
    def setUp(self):
        self.now = timezone.now()

    def fresh_records(self):
        """Every expected job ran OK a minute ago."""
        recs = {store.SINCE_KEY: {'at': _iso(self.now - timedelta(days=400))}}
        for job in EXPECTED_CADENCE:
            recs[store.CRON_PREFIX + job] = {'last_ok_at': _iso(self.now - timedelta(minutes=1))}
        return recs

    def test_every_job_on_time_is_green(self):
        r = sh.cron_row(self.now, self.fresh_records())
        self.assertEqual((r['status'], r['code']), ('green', 'ok'))
        self.assertEqual(r['params']['count'], str(len(EXPECTED_CADENCE)))

    def test_nothing_recorded_yet_is_waiting(self):
        r = sh.cron_row(self.now, {})
        self.assertEqual((r['status'], r['code']), ('green', 'waiting'))

    def test_the_line_names_the_worst_job(self):
        recs = self.fresh_records()
        recs['cron:query-reminders'] = {'last_ok_at': _iso(self.now - timedelta(hours=27))}   # amber
        recs['cron:query-emails'] = {'last_ok_at': _iso(self.now - timedelta(hours=26))}      # red
        r = sh.cron_row(self.now, recs)
        self.assertEqual((r['status'], r['code']), ('red', 'missed'))
        self.assertEqual(r['params'], {'job': 'query-emails', 'cadence': 'hourly',
                                       'amount': '26', 'unit': 'hours'})

    def test_amber_when_one_job_is_late(self):
        recs = self.fresh_records()
        recs['cron:interview-reminders'] = {'last_ok_at': _iso(self.now - timedelta(minutes=30))}
        r = sh.cron_row(self.now, recs)
        self.assertEqual((r['status'], r['params']['job'], r['params']['cadence']),
                         ('amber', 'interview-reminders', 'every15'))

    def test_a_job_missing_after_deploy_turns_red_only_after_two_cadences(self):
        recs = self.fresh_records()
        del recs['cron:application-nudges']
        recs[store.SINCE_KEY] = {'at': _iso(self.now - timedelta(minutes=20))}
        self.assertEqual(sh.cron_row(self.now, recs)['status'], 'green')
        recs[store.SINCE_KEY] = {'at': _iso(self.now - timedelta(minutes=45))}
        r = sh.cron_row(self.now, recs)
        self.assertEqual((r['status'], r['code'], r['params']['job']), ('red', 'never', 'application-nudges'))


class CadenceRegistry(SimpleTestCase):
    def test_every_expected_job_is_a_real_cron_job(self):
        self.assertEqual(set(EXPECTED_CADENCE) - set(CronRunView.JOBS), set())

    def test_the_fleet_cadences(self):
        self.assertEqual(EXPECTED_CADENCE['interview-reminders'], EVERY_15_MIN)
        self.assertEqual(EXPECTED_CADENCE['read-outage-start'], HOURLY)
        self.assertEqual(EXPECTED_CADENCE['sync-vircle-sheet'], DAILY)
        self.assertEqual(EXPECTED_CADENCE['backup-documents'], WEEKLY)

    def test_age_never_says_one_of_a_plural_unit(self):
        self.assertEqual(sh.age_params(timedelta(minutes=75)), {'amount': '75', 'unit': 'minutes'})
        self.assertEqual(sh.age_params(timedelta(hours=26)), {'amount': '26', 'unit': 'hours'})
        self.assertEqual(sh.age_params(timedelta(days=9)), {'amount': '9', 'unit': 'days'})

    def test_every_job_and_code_has_words_in_all_three_locales(self):
        # The web turns `code` + `params.job` into words from these catalogues; a job added to
        # EXPECTED_CADENCE or a code added below without a string would show its raw key.
        import json
        import os
        codes = {
            'read': {'ok', 'idle', 'failures', 'down'},
            'email': {'ok', 'no_record', 'recent_failure', 'failing', 'no_success'},
            'cron': {'ok', 'waiting', 'late', 'missed', 'never', 'errored', 'errored_twice'},
            'credit': {'ok', 'payment_error', 'recovered'},
        }
        here = os.path.dirname(__file__)
        for locale in ('en', 'ms', 'ta'):
            path = os.path.normpath(os.path.join(
                here, '..', '..', '..', '..', 'halatuju-web', 'src', 'messages', f'{locale}.json'))
            # The deploy build checks out the whole repository, so the catalogues are always here.
            with open(path, encoding='utf-8') as fh:
                block = json.load(fh)['admin']['systemHealth']
            self.assertEqual(set(block['job']), set(EXPECTED_CADENCE), locale)
            for group, expected in codes.items():
                self.assertEqual(set(block['line'][group]), expected, f'{locale} {group}')

    def test_overall_is_the_worst_row(self):
        self.assertEqual(sh.overall([{'status': 'green'}, {'status': 'amber'}]), 'amber')
        self.assertEqual(sh.overall([{'status': 'red'}, {'status': 'amber'}]), 'red')
        self.assertEqual(sh.overall([{'status': 'green'}]), 'green')


# ── Gemini, Vision and the AI credit — from the stamps on real documents ───────────────────

class ReadServiceRows(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.apps = [make_application('shortlisted'), make_application('shortlisted')]

    def gemini_read(self, app, minutes_ago, error=''):
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'x/{ApplicantDocument.objects.count()}',
            content_type='image/jpeg', vision_fields_run_at=self.now - timedelta(minutes=minutes_ago),
            vision_fields={'capture': 'ai', 'error': error, 'fields': {} if error else {'a': 1}})

    def vision_read(self, app, minutes_ago, error='', nric=''):
        return ApplicantDocument.objects.create(
            application=app, doc_type='ic', storage_path=f'v/{ApplicantDocument.objects.count()}',
            content_type='image/jpeg', vision_run_at=self.now - timedelta(minutes=minutes_ago),
            vision_error=error, vision_nric=nric)

    def gemini(self):
        return sh.read_service_row('gemini', self.now, sh._gemini_events(self.now))

    def vision(self):
        return sh.read_service_row('vision', self.now, sh._vision_events(self.now))

    def credit(self):
        return sh.credit_row(self.now, sh._gemini_events(self.now))

    def test_no_reads_is_green_idle(self):
        self.assertEqual((self.gemini()['code'], self.vision()['code']), ('idle', 'idle'))
        self.assertEqual(self.gemini()['status'], 'green')

    def test_working_reads_are_green_with_last_ok(self):
        self.gemini_read(self.apps[0], 10)
        r = self.gemini()
        self.assertEqual((r['status'], r['code'], r['params']['count']), ('green', 'ok', '1'))
        self.assertIsNotNone(r['last_ok_at'])

    def test_one_failure_among_successes_is_amber(self):
        self.gemini_read(self.apps[0], 10)
        self.gemini_read(self.apps[1], 20, _SERVICE_DOWN)
        r = self.gemini()
        self.assertEqual((r['status'], r['code'], r['params']['count']), ('amber', 'failures', '1'))

    def test_every_read_failing_for_two_hours_is_red(self):
        self.gemini_read(self.apps[0], 10, _SERVICE_DOWN)
        self.gemini_read(self.apps[1], 90, _SERVICE_DOWN)
        self.gemini_read(self.apps[0], 60 * 30)       # a success the day before: last OK, not "up"
        r = self.gemini()
        self.assertEqual((r['status'], r['code']), ('red', 'down'))
        self.assertIsNotNone(r['last_ok_at'])

    def test_a_document_problem_is_not_a_service_failure(self):
        self.gemini_read(self.apps[0], 10, 'No model could read this document: x')
        self.assertEqual(self.gemini()['status'], 'green')

    def test_vision_rows_follow_the_outage_rules(self):
        self.vision_read(self.apps[0], 10, nric='700101-14-5003')
        self.assertEqual(self.vision()['status'], 'green')
        self.vision_read(self.apps[1], 15, error='quota exceeded')
        self.assertEqual(self.vision()['status'], 'amber')

    def test_vision_down_is_red_and_a_poor_image_is_not(self):
        self.vision_read(self.apps[0], 10, error='empty image')
        self.assertEqual(self.vision()['status'], 'green')
        self.vision_read(self.apps[1], 20, error='503 Service Unavailable')
        self.assertEqual(self.vision()['status'], 'red')

    def test_credit_is_green_without_a_payment_error(self):
        self.gemini_read(self.apps[0], 10, _SERVICE_DOWN)
        self.assertEqual((self.credit()['status'], self.credit()['code']), ('green', 'ok'))

    def test_a_402_with_no_read_working_since_is_red(self):
        self.gemini_read(self.apps[0], 60 * 5)
        self.gemini_read(self.apps[1], 30, _402)
        r = self.credit()
        self.assertEqual((r['status'], r['code']), ('red', 'payment_error'))
        self.assertIn('time', r['params'])

    def test_a_402_followed_by_working_reads_is_amber(self):
        self.gemini_read(self.apps[1], 30, _402)
        self.gemini_read(self.apps[0], 5)
        self.assertEqual((self.credit()['status'], self.credit()['code']), ('amber', 'recovered'))

    def test_a_402_older_than_a_day_is_forgotten(self):
        self.gemini_read(self.apps[1], 60 * 30, _402)
        self.assertEqual(self.credit()['status'], 'green')

    def test_snapshot_has_five_rows_and_the_worst_colour(self):
        self.gemini_read(self.apps[1], 30, _402)
        snap = sh.snapshot(self.now)
        self.assertEqual([r['key'] for r in snap['rows']], list(sh.ROW_KEYS))
        self.assertEqual(snap['overall'], 'red')


# ── The endpoint ───────────────────────────────────────────────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class SystemHealthEndpoint(TestCase):
    URL = '/api/v1/admin/scholarship/system-health/'

    def setUp(self):
        cache.clear()

    def test_super_admin_gets_the_rows(self):
        r = authed_client(make_admin('super', super_admin=True)).get(self.URL)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body['rows']), 5)
        self.assertIn(body['overall'], ('green', 'amber', 'red'))
        self.assertIn('checked_at', body)
        for row in body['rows']:
            self.assertEqual(set(row), {'key', 'status', 'code', 'params', 'last_ok_at'})

    def test_every_other_admin_is_refused(self):
        for role in ('admin', 'org_admin', 'reviewer', 'qc', 'finance', 'partner'):
            with self.subTest(role=role):
                self.assertEqual(authed_client(make_admin(role)).get(self.URL).status_code, 403)

    def test_a_non_admin_is_refused(self):
        self.assertEqual(authed_client('someone-else').get(self.URL).status_code, 403)

    def test_anonymous_is_401(self):
        from rest_framework.test import APIClient
        self.assertEqual(APIClient().get(self.URL).status_code, 401)

    def test_it_is_read_only(self):
        client = authed_client(make_admin('super', super_admin=True))
        self.assertEqual(client.post(self.URL, {}).status_code, 405)
        client.get(self.URL)
        self.assertFalse(SystemHealthStatus.objects.exists())

    def test_cached_until_refreshed(self):
        client = authed_client(make_admin('super', super_admin=True))
        first = client.get(self.URL).json()
        SystemHealthStatus.objects.create(key=store.EMAIL_KEY, data={
            'last_fail_at': timezone.now().isoformat(), 'consecutive_failures': 5})
        self.assertEqual(client.get(self.URL).json(), first)
        fresh = client.get(self.URL + '?fresh=1').json()
        self.assertEqual(fresh['rows'][2]['status'], 'red')
        self.assertEqual(fresh['overall'], 'red')
