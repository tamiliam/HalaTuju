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
from apps.courses.management.commands.validate_course_urls import check_url

CMD = 'apps.courses.management.commands.validate_course_urls'


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
    def test_403_auth_gated_is_alive(self, uo):
        uo.side_effect = urllib.error.HTTPError('u', 403, 'forbidden', {}, None)
        self.assertEqual(check_url('http://x'), ('alive', 403))

    @patch(f'{CMD}.urllib.request.urlopen')
    def test_url_error_is_error(self, uo):
        uo.side_effect = urllib.error.URLError('dns fail')
        self.assertEqual(check_url('http://x')[0], 'error')

    def test_schemeless_url_is_error_not_raise(self):
        # Real bug from a live run: a stored hyperlink without http:// (e.g. a mypolycc subdomain)
        # must classify as 'error', never raise — a malformed URL can't be allowed to abort the run.
        self.assertEqual(check_url('kkpasirsalak.mypolycc.edu.my')[0], 'error')


def _fake_check(url, timeout=10):
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
        self.assertIn('Alive:  1', s)
        self.assertIn('Dead:   2', s)  # dead.test + offer-dead.test

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
        self.assertIn('Alive:  1', s)
        self.assertIn('Dead:   2', s)

    @patch(f'{CMD}.check_url', side_effect=_fake_check)
    def test_workers_never_clears_without_fix(self, _c):
        call_command('validate_course_urls', workers=8, stdout=StringIO())
        self.dead.refresh_from_db()
        self.assertEqual(self.dead.url, 'http://dead.test')  # concurrent path is still read-only


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
