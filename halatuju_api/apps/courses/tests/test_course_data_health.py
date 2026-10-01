"""TD-047: a failed startup load of the course data is retried by the next request, and
`GET /api/v1/health/` says whether this instance can answer an eligibility check."""
from unittest import mock

from django.apps import apps
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses import apps as courses_apps
from apps.courses.tests.conftest import load_requirements_df

_STATE = ('requirements_df', 'course_tags_df', 'course_tags_map', 'inst_modifiers_map',
          'inst_subcategories', 'course_pathway_map', '_last_retry_at')

STUDENT = {'grades': {'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+',
                      'sci': 'A+', 'phy': 'A+', 'chem': 'A+'},
           'gender': 'male', 'nationality': 'malaysian'}


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestCourseDataRetryAndHealth(TestCase):
    fixtures = ['courses', 'requirements']

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_requirements_df()

    def setUp(self):
        self.config = apps.get_app_config('courses')
        saved = {k: self.config.__dict__.get(k, mock.sentinel.absent) for k in _STATE}

        def restore():
            for k, v in saved.items():
                if v is mock.sentinel.absent:
                    self.config.__dict__.pop(k, None)
                else:
                    setattr(self.config, k, v)
        self.addCleanup(restore)
        # The startup load "failed": the frame is empty, and no retry has happened yet.
        self.config.requirements_df = None
        self.config._last_retry_at = None
        # Fresh maps, so a reload can only ever mutate THIS test's dicts (restored above).
        for name in ('course_tags_map', 'inst_modifiers_map', 'inst_subcategories',
                     'course_pathway_map'):
            setattr(self.config, name, {})
        self.client = APIClient()

    def _check(self):
        return self.client.post('/api/v1/eligibility/check/', STUDENT, format='json')

    def test_empty_data_is_RETRIED_by_the_request_and_the_check_answers(self):
        response = self._check()
        self.assertEqual(response.status_code, 200, response.content[:200])
        self.assertGreater(response.json()['total_count'], 100)
        self.assertTrue(self.config.data_loaded())
        health = self.client.get('/api/v1/health/')
        self.assertEqual((health.status_code, health.json()),
                         (200, {'status': 'ok', 'course_data_loaded': True}))

    def test_a_FAILED_retry_answers_503_and_health_says_degraded(self):
        with mock.patch.object(self.config, '_load_data', side_effect=RuntimeError('db down')):
            self.assertEqual(self._check().status_code, 503)
        health = self.client.get('/api/v1/health/')
        self.assertEqual((health.status_code, health.json()),
                         (503, {'status': 'degraded', 'course_data_loaded': False}))

    def test_the_retry_is_RATE_LIMITED_not_once_per_request(self):
        with mock.patch.object(self.config, '_load_data', side_effect=RuntimeError('db down')) as load:
            for _ in range(3):
                self.assertEqual(self._check().status_code, 503)
        self.assertEqual(load.call_count, 1)
        # Once the interval has passed, the next request tries again.
        self.config._last_retry_at -= courses_apps.DATA_RETRY_INTERVAL_SECONDS + 1
        with mock.patch.object(self.config, '_load_data', side_effect=RuntimeError('db down')) as load:
            self._check()
        self.assertEqual(load.call_count, 1)

    def test_a_load_that_fails_LATE_publishes_nothing(self):
        """Review F5a: the frames are built into locals and `requirements_df` is assigned LAST, so
        a request never sees an eligibility frame beside half-built ranking maps."""
        from apps.courses.models import CourseInstitution
        broken = mock.Mock()
        broken.filter.side_effect = RuntimeError('db dropped mid-load')
        with mock.patch.object(CourseInstitution, 'objects', broken):
            self.assertIsNone(self.config.ensure_data())
        broken.filter.assert_called()                      # the load got that far …
        self.assertFalse(self.config.data_loaded())         # … and published nothing
        self.assertEqual((self.config.course_tags_map, self.config.inst_subcategories,
                          self.config.course_pathway_map), ({}, {}, {}))

    def test_the_interval_is_RE_CHECKED_inside_the_lock(self):
        """Review F5b: a thread that read the stale `_last_retry_at`, then waited while another
        thread ran the retry, must not reload again once it holds the lock."""
        import time
        config = self.config

        class OtherThreadRetriedMeanwhile:
            def acquire(self, blocking=True):
                config._last_retry_at = time.monotonic()    # the other thread's retry, just now
                return True

            def release(self):
                pass

        with mock.patch.object(config, '_retry_lock', OtherThreadRetriedMeanwhile()), \
                mock.patch.object(config, '_load_data') as load:
            config.ensure_data()
        load.assert_not_called()

    def test_health_is_UNAUTHENTICATED_and_CHEAP(self):
        load_requirements_df()
        with self.assertNumQueries(0):
            response = APIClient().get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {'status', 'course_data_loaded'})

    def test_health_never_retries_the_load_itself(self):
        """An unauthenticated route must not be a way to make the service hit the database."""
        with mock.patch.object(self.config, '_load_data') as load, self.assertNumQueries(0):
            self.assertEqual(self.client.get('/api/v1/health/').status_code, 503)
        load.assert_not_called()

    def test_health_is_GET_only(self):
        self.assertEqual(self.client.post('/api/v1/health/').status_code, 405)
