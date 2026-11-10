"""Sprint S1 (owner 2026-11-09) — a Scholars permission of its own (`scholars`).

Brief `docs/plans/2026-11-09-s1-scholars-access.md`; decisions.md "S1". Pinned here through the real
endpoints:
  * S1-c — `review`, `qc` and `see_all` (Applications) alone are 403 on the Scholars list, the file,
    every tab and every write; `scholars_scope` answers 'none' for them;
  * S1-a — `scholars` alone reads Scholars and is 403 on Applications (the two doors are apart);
  * S1-e — union by keys: the label `reviewer` holding `review + see_all + scholars` reads both;
  * S1-f — a mentor login is 403 on Applications;
  * the old image (a catalogue without `scholars`) drops the stored key, so a rollback is safe.
The result-review writer (S1-d) is pinned in `test_results_review.py`, letters in `test_letters.py`.
"""
from unittest import mock

from django.test import TestCase, override_settings

from apps.courses import staff_permissions as sp
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)
from apps.scholarship.views_admin.base import scholars_scope

API = '/api/v1/admin/scholarship/scholars/'
APPS = '/api/v1/admin/scholarship/applications/'
NO_ROW = 999999          # a letter / result id nobody has: the door answers before the lookup


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Access(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort()
        org = cls.cohort.owning_organisation
        cls.reviewer = make_admin('reviewer', owning_org=org)
        cls.qc = make_admin('qc', owning_org=org)
        cls.see_all = make_admin('admin', owning_org=org, permissions=['see_all'])
        cls.scholars_only = make_admin('admin', owning_org=org, permissions=['scholars'])
        cls.union = make_admin('reviewer', owning_org=org, permissions=['review', 'see_all', 'scholars'])
        cls.scholar = make_application('maintenance', cohort=cls.cohort, reviewer=cls.reviewer)
        cls.applicant = make_application('interviewing', cohort=cls.cohort)


class TestReviewQcAndApplicationsAloneAreShut(_Access):
    def _reads(self):
        pk = self.scholar.pk
        return (API, f'{API}{pk}/', f'{API}{pk}/activity/', f'{API}{pk}/results/', f'{API}{pk}/money/',
                f'{API}{pk}/contract/', f'{API}{pk}/letters/', f'{API}{pk}/letters/{NO_ROW}/pdf/',
                f'{API}{pk}/development/', f'{API}{pk}/surveys/', f'{API}{pk}/mentoring/')

    def _writes(self):
        pk = self.scholar.pk
        return ((f'{API}{pk}/activity/', {'kind': 'note', 'body': 'x'}),
                (f'{API}{pk}/results/{NO_ROW}/review/', {'decision': 'accepted'}),
                (f'{API}{pk}/letters/', {'kind': 'general', 'language': 'en'}),
                (f'{API}{pk}/letters/preview/', {'kind': 'general', 'language': 'en'}),
                (f'{API}{pk}/letters/{NO_ROW}/resend/', {}),
                (f'{API}{pk}/mentoring/assign/', {'mentor_id': NO_ROW}),
                (f'{API}{pk}/mentoring/sessions/', {}))

    def test_every_read_and_write_is_403(self):
        for who in (self.reviewer, self.qc, self.see_all):
            self.assertEqual(scholars_scope(who), 'none')
            client = authed_client(who)
            for url in self._reads():
                with self.subTest(who=who.permission_set, get=url):
                    self.assertEqual(client.get(url).status_code, 403)
            for url, body in self._writes():
                with self.subTest(who=who.permission_set, post=url):
                    self.assertEqual(client.post(url, body, format='json').status_code, 403)

    def test_they_still_read_applications(self):
        for who in (self.reviewer, self.qc, self.see_all):
            with self.subTest(who=who.permission_set):
                self.assertEqual(authed_client(who).get(APPS).status_code, 200)


class TestTheTwoDoorsAreApart(_Access):
    def test_scholars_alone_reads_scholars_and_not_applications(self):
        client = authed_client(self.scholars_only)
        self.assertEqual(scholars_scope(self.scholars_only), 'all')
        self.assertEqual(client.get(API).status_code, 200)
        self.assertEqual(client.get(f'{API}{self.scholar.pk}/').status_code, 200)
        self.assertEqual(client.get(APPS).status_code, 403)
        self.assertEqual(client.get(f'{APPS}{self.applicant.pk}/').status_code, 403)

    def test_the_union_shape_reads_both_by_its_keys(self):
        client = authed_client(self.union)
        self.assertEqual(self.union.permission_set, ('review', 'see_all', 'scholars'))
        ids = [r['id'] for r in client.get(API).json()['results']]
        self.assertIn(self.scholar.pk, ids)                       # not assigned to them: still read
        self.assertEqual(client.get(APPS).status_code, 200)

    def test_a_mentor_login_is_refused_applications(self):
        mentor = make_admin('mentor', owning_org=self.cohort.owning_organisation)
        client = authed_client(mentor)
        self.assertEqual(client.get(APPS).status_code, 403)
        self.assertEqual(client.get(f'{APPS}{self.applicant.pk}/').status_code, 403)


class TestTheOldImageIgnoresTheKey(TestCase):
    def test_a_catalogue_without_scholars_drops_it_from_a_saved_set(self):
        old = tuple(k for k in sp.CATALOGUE if k != 'scholars')
        with mock.patch.object(sp, 'CATALOGUE', old):
            self.assertEqual(sp.clean(['see_all', 'scholars']), ('see_all',))
