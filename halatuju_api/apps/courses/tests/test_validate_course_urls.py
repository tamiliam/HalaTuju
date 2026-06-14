"""Tests for validate_course_urls (catalogue link reachability) + the audit link-health section.

`check_url` is unit-tested by mocking `urlopen` (no network). The command + audit are
exercised against small DB fixtures with `check_url` mocked.
"""
import urllib.error
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.courses.models import Course, CourseInstitution, FieldTaxonomy, Institution
from apps.courses.management.commands.validate_course_urls import check_url, _error_kind
from apps.courses.models import CourseDataStatus

CMD = 'apps.courses.management.commands.validate_course_urls'


class ErrorKindTest(SimpleTestCase):
    def test_dns(self):
        self.assertEqual(_error_kind(urllib.error.URLError('[Errno 11001] getaddrinfo failed')), 'dns')

    def test_timeout(self):
        self.assertEqual(_error_kind(TimeoutError('timed out')), 'timeout')

    def test_conn(self):
        self.assertEqual(_error_kind(urllib.error.URLError('Connection refused')), 'conn')

    def test_badurl(self):
        self.assertEqual(_error_kind(ValueError('unknown url type')), 'badurl')


class CheckUrlTest(SimpleTestCase):
    @patch(f'{CMD}.urllib.request.urlopen')
    def test_alive_2xx(self, uo):
        r = MagicMock()
        r.status = 200
        uo.return_value.__enter__.return_value = r
        self.assertEqual(check_url('http://x'), ('alive', 200))

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_404_is_dead(self, uo):
        uo.side_effect = urllib.error.HTTPError('u', 404, 'nf', {}, None)
        self.assertEqual(check_url('http://x'), ('dead', 404))

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_500_is_dead(self, uo):
        uo.side_effect = urllib.error.HTTPError('u', 500, 'err', {}, None)
        self.assertEqual(check_url('http://x'), ('dead', 500))

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_403_is_gated_not_silently_alive(self, uo):
        # 401/403 is AMBIGUOUS (login wall vs wrong path, e.g. Port Dickson's old URL) → its own
        # 'gated' status, surfaced for review rather than counted as plainly alive.
        uo.side_effect = urllib.error.HTTPError('u', 403, 'forbidden', {}, None)
        self.assertEqual(check_url('http://x'), ('gated', 403))

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_401_is_gated(self, uo):
        uo.side_effect = urllib.error.HTTPError('u', 401, 'unauthorized', {}, None)
        self.assertEqual(check_url('http://x'), ('gated', 401))

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_url_error_is_error(self, uo):
        uo.side_effect = urllib.error.URLError('dns fail')
        self.assertEqual(check_url('http://x')[0], 'error')

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_schemeless_url_normalised_to_https(self, uo):
        # A stored hyperlink without a scheme (e.g. 'kkpasirsalak.mypolycc.edu.my') is normalised to
        # https:// and checked — not errored. (Was a live crash before the Request moved inside try.)
        r = MagicMock(); r.status = 200
        uo.return_value.__enter__.return_value = r
        self.assertEqual(check_url('kkpasirsalak.mypolycc.edu.my'), ('alive', 200))
        req = uo.call_args[0][0]
        self.assertTrue(req.full_url.startswith('https://'))

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_ssl_failure_retries_unverified_as_insecure(self, uo):
        import ssl as _ssl
        ok = MagicMock()
        ok.__enter__ = MagicMock(return_value=MagicMock(status=200))
        ok.__exit__ = MagicMock(return_value=False)
        # 1st (verifying) call: TLS cert rejection; 2nd (no-verify) call: reachable.
        uo.side_effect = [urllib.error.URLError(_ssl.SSLError('bad cert')), ok]
        self.assertEqual(check_url('https://gov-with-bad-cert.edu.my'), ('insecure', 200))

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_non_ssl_url_error_stays_error(self, uo):
        # A plain DNS/connection URLError is NOT retried — stays 'error'.
        uo.side_effect = urllib.error.URLError('getaddrinfo failed')
        self.assertEqual(check_url('https://nope.invalid')[0], 'error')

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_transient_timeout_is_retried_then_succeeds(self, uo):
        # A slow MY gov/edu portal: first attempt times out, retry succeeds → 'alive'
        # (this is what stops slow-but-live sites being false-flagged as broken).
        ok = MagicMock()
        ok.__enter__ = MagicMock(return_value=MagicMock(status=200))
        ok.__exit__ = MagicMock(return_value=False)
        uo.side_effect = [TimeoutError('timed out'), ok]
        self.assertEqual(check_url('http://slow.edu.my', retries=1), ('alive', 200))
        self.assertEqual(uo.call_count, 2)

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_dns_failure_is_not_retried(self, uo):
        # DNS-not-found won't change on a retry, so don't waste a second attempt.
        uo.side_effect = urllib.error.URLError('getaddrinfo failed')
        self.assertEqual(check_url('https://nope.invalid', retries=1), ('error', 'dns'))
        self.assertEqual(uo.call_count, 1)


def _fake_check(url, timeout=10, retries=1):
    if 'dead' in url:
        return ('dead', 404)
    if 'err' in url:
        return ('error', 'URLError')
    return ('alive', 200)


class ValidateCourseUrlsCommandTest(TestCase):
    def setUp(self):
        ft = FieldTaxonomy.objects.create(
            key='k', name_en='K', name_ms='K', name_ta='K', image_slug='k', sort_order=1)
        self.course = Course.objects.create(
            course_id='C1', course='X', level='Diploma', department='D', field='F', field_key=ft)
        self.alive = Institution.objects.create(
            institution_id='I1', institution_name='Alive U', type='IPTA', state='Selangor',
            url='http://alive.test')
        self.dead = Institution.objects.create(
            institution_id='I2', institution_name='Dead U', type='IPTA', state='Selangor',
            url='http://dead.test')
        CourseInstitution.objects.create(
            course=self.course, institution=self.dead, hyperlink='http://offer-dead.test')

    @patch(f'{CMD}.check_url', side_effect=_fake_check)
    def test_reports_counts(self, _c):
        out = StringIO()
        call_command('validate_course_urls', stdout=out)
        s = out.getvalue()
        self.assertIn('Alive:        1', s)
        self.assertIn('Broken:       2', s)  # dead.test + offer-dead.test (both 'gone')

    @patch(f'{CMD}.check_url', side_effect=_fake_check)
    def test_summary_splits_broken_and_unverified(self, _c):
        # A dead link is BROKEN (actionable); a transient error is COULDN'T-VERIFY (likely alive).
        Institution.objects.create(
            institution_id='I3', institution_name='Slow U', type='IPTA', state='S',
            url='http://err.test')  # _fake_check → ('error', 'URLError') → unverified
        call_command('validate_course_urls', stdout=StringIO())
        s = CourseDataStatus.objects.get(key='link_health').summary
        self.assertEqual(s['broken'], 2)       # dead.test + offer-dead.test
        self.assertEqual(s['unverified'], 1)   # err.test

    @patch(f'{CMD}.check_url', side_effect=lambda u, t=10, retries=1: ('gated', 403) if 'gate' in u else _fake_check(u, t))
    def test_gated_403_surfaced_as_own_severity(self, _c):
        # A 401/403 link is neither 'broken' nor 'couldn't-verify' — it gets its own 'gated' bucket
        # and is recorded in failures for a human to eyeball (the Port Dickson lesson).
        Institution.objects.create(
            institution_id='I4', institution_name='Gated U', type='IPTA', state='S',
            url='http://gate.test')
        call_command('validate_course_urls', stdout=StringIO())
        s = CourseDataStatus.objects.get(key='link_health').summary
        self.assertEqual(s['gated'], 1)
        self.assertEqual(s['broken'], 2)        # gated is NOT folded into broken
        gated = next(f for f in s['failures'] if f['url'] == 'http://gate.test')
        self.assertEqual(gated['kind'], 'gated')
        self.assertIn('Gated U', gated['institutions'])

    @patch(f'{CMD}.check_url', side_effect=_fake_check)
    def test_dry_run_does_not_clear(self, _c):
        call_command('validate_course_urls', stdout=StringIO())
        self.dead.refresh_from_db()
        self.assertEqual(self.dead.url, 'http://dead.test')  # unchanged without --fix

    @patch(f'{CMD}.check_url', side_effect=_fake_check)
    def test_fix_clears_dead_only(self, _c):
        call_command('validate_course_urls', fix=True, stdout=StringIO())
        self.alive.refresh_from_db()
        self.dead.refresh_from_db()
        self.assertEqual(self.alive.url, 'http://alive.test')  # alive untouched
        self.assertEqual(self.dead.url, '')                    # dead cleared
        self.assertEqual(CourseInstitution.objects.get(course=self.course).hyperlink, '')  # dead offer cleared

    @patch(f'{CMD}.check_url', side_effect=_fake_check)
    def test_limit_restricts_count(self, _c):
        out = StringIO()
        call_command('validate_course_urls', limit=1, stdout=out)
        self.assertIn('Checking 1 distinct', out.getvalue())

    @patch(f'{CMD}.check_url', side_effect=_fake_check)
    def test_workers_concurrent_same_classification(self, _c):
        # Concurrency must produce identical counts to the sequential path (read-only GETs).
        out = StringIO()
        call_command('validate_course_urls', workers=8, stdout=out)
        s = out.getvalue()
        self.assertIn('8 workers', s)
        self.assertIn('Alive:        1', s)
        self.assertIn('Broken:       2', s)

    @patch(f'{CMD}.check_url', side_effect=_fake_check)
    def test_workers_never_clears_without_fix(self, _c):
        call_command('validate_course_urls', workers=8, stdout=StringIO())
        self.dead.refresh_from_db()
        self.assertEqual(self.dead.url, 'http://dead.test')  # concurrent path is still read-only

    @patch(f'{CMD}.check_url', side_effect=_fake_check)
    def test_retries_option_is_passed_through(self, _c):
        # The bulk dashboard run uses retries=0 (the timeout already catches slow sites; a retry
        # would double the slow tail and risk the Cloud Run request limit).
        call_command('validate_course_urls', retries=0, stdout=StringIO())
        self.assertTrue(_c.call_args_list)
        for call in _c.call_args_list:
            self.assertEqual(call.kwargs.get('retries'), 0)

    @patch(f'{CMD}.check_url', side_effect=_fake_check)
    def test_records_failures_with_institution_and_kind(self, _c):
        call_command('validate_course_urls', stdout=StringIO())
        failures = CourseDataStatus.objects.get(key='link_health').summary['failures']
        by_url = {f['url']: f for f in failures}
        # the dead institution URL is captured, tagged 'gone', with its institution name
        self.assertIn('http://dead.test', by_url)
        self.assertEqual(by_url['http://dead.test']['kind'], 'gone')
        self.assertIn('Dead U', by_url['http://dead.test']['institutions'])
        # the dead OFFERING url is captured too (backed by ≥1 row)
        self.assertIn('http://offer-dead.test', by_url)
        self.assertGreaterEqual(by_url['http://offer-dead.test']['refs'], 1)


class AuditLinkHealthTest(TestCase):
    def test_audit_reports_link_health_section(self):
        ft = FieldTaxonomy.objects.create(
            key='k', name_en='K', name_ms='K', name_ta='K', image_slug='k', sort_order=1)
        Institution.objects.create(
            institution_id='I1', institution_name='U', type='IPTA', state='S', url='http://x.test')
        out = StringIO()
        call_command('audit_data', stdout=out)
        s = out.getvalue()
        self.assertIn('LINK HEALTH', s)
        self.assertIn('validate_course_urls', s)
        self.assertIn('distinct external URLs: 1', s)
