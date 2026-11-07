"""TD-421 (A1.9): an admin people-search term travels in the X-Search-Term header, never the URL.

The request line (path + query string) is what Cloud Run and Django write to the logs, so an IC
typed into a search box must not be in it. The web sends the term URI-encoded in the header (so a
Tamil name survives HTTP's latin-1 header rule); the old `?q=` / `?search=` still works while an
older web bundle is live. Pinned on the three lists that take a people search: Applications,
Scholars and Students.
"""
from urllib.parse import quote

from django.test import TestCase, override_settings

from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_student,
)

IC = '080918-08-1813'
TAMIL = 'தமிழ்செல்வி'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestApplicationsAndStudents(TestCase):
    @classmethod
    def setUpTestData(cls):
        cohort = make_cohort()
        cls.org_admin = make_admin('org_admin', owning_org=cohort.owning_organisation)
        cls.super = make_admin('super', super_admin=True)    # the Students directory is super-only
        for name, nric in (('SHUHAN RAJ', IC), (TAMIL, '070707-07-0707'), ('AISYAH', '060606-06-0606')):
            make_application('submitted', cohort=cohort, student=make_student(name=name, nric=nric))

    def _get(self, url, term=None, **params):
        headers = {} if term is None else {'HTTP_X_SEARCH_TERM': quote(term)}
        admin = self.super if 'students' in url else self.org_admin
        return authed_client(admin).get(url, params, **headers)

    def _check(self, url, key):
        r = self._get(url, IC)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r.json()['count'], 1)
        self.assertNotIn('080918', r.wsgi_request.get_full_path())      # the logged request line
        r = self._get(url, TAMIL)
        self.assertEqual([row['name'] for row in r.json()[key]], [TAMIL])
        self.assertEqual(self._get(url, q='aisyah').json()['count'], 1)  # the old ?q= still works

    def test_applications(self):
        self._check('/api/v1/admin/scholarship/applications/', 'applications')

    def test_students(self):
        self._check('/api/v1/admin/students/', 'students')

    def test_the_header_wins_over_the_query_string(self):
        r = self._get('/api/v1/admin/scholarship/applications/', 'aisyah', q='shuhan')
        self.assertEqual(r.json()['count'], 1)
        self.assertEqual(r.json()['applications'][0]['name'], 'AISYAH')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestScholars(TestCase):
    API = '/api/v1/admin/scholarship/scholars/'

    @classmethod
    def setUpTestData(cls):
        cohort = make_cohort()
        cls.org_admin = make_admin('org_admin', owning_org=cohort.owning_organisation)
        make_application('active', cohort=cohort, student=make_student(name='BALA', nric=IC))
        make_application('active', cohort=cohort, student=make_student(name='CHEN'))

    def _names(self, r):
        self.assertEqual(r.status_code, 200, r.content[:300])
        return [row['name'] for row in r.json()['results']]

    def test_the_header_searches_and_stays_out_of_the_url(self):
        r = authed_client(self.org_admin).get(self.API, HTTP_X_SEARCH_TERM=quote(IC))
        self.assertEqual(self._names(r), ['BALA'])
        self.assertNotIn('080918', r.wsgi_request.get_full_path())

    def test_the_old_search_param_still_works(self):
        r = authed_client(self.org_admin).get(self.API, {'search': 'chen'})
        self.assertEqual(self._names(r), ['CHEN'])
