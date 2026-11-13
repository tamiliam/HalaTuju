"""Sprint M2d (D7, ruling 7): the Engagement pages need Scholars, and the Permissions tab is TOLD.

- The GET serves `v2_gaps`: the pages short of Scholars for the person as held, read through `ALIASES`
  (the old key `scholars` IS `scholars.view`).
- The dry run and the save answer `v2_gaps` for the asked set and end `consequences` with
  `scholars_needed` whenever that set has a gap — a gap in `after` only: a gap the change closes says
  nothing. A note, never a refusal.
- The role and table changes that share `consequences` do not grow the code.
"""
from django.test import TestCase, override_settings

from apps.scholarship import staff_permissions_admin as spa
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org


def _url(target):
    return f'/api/v1/admin/admins/{target.pk}/permissions/'


def _patch(who, target, keys, **extra):
    return authed_client(who).patch(_url(target), {'permissions': keys, 'v2': True, **extra}, format='json')


class Gaps(TestCase):
    def test_pages_in_catalogue_order_once_each(self):
        self.assertEqual(spa.scholars_gaps(['review', 'mentoring.view', 'surveys.view', 'surveys.edit']),
                         ['surveys', 'mentoring'])

    def test_the_old_scholars_key_closes_the_gap_through_its_alias(self):
        self.assertEqual(spa.scholars_gaps(['scholars', 'announcements.view', 'development.edit']), [])

    def test_applications_alone_does_not_close_it(self):
        # `see_all` is Applications (`students.view`) since S1, not the scholars' files.
        self.assertEqual(spa.scholars_gaps(['see_all', 'qc', 'development.view']), ['development'])

    def test_no_engagement_page_no_gap(self):
        self.assertEqual(spa.scholars_gaps(['see_all', 'spending', 'team.view', 'sources.edit']), [])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class Served(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org)

    def test_the_get_serves_the_gaps_as_held(self):
        rev = make_admin('reviewer', owning_org=self.org, permissions=['review', 'surveys.view', 'mentoring.view'])
        body = authed_client(self.lead).get(_url(rev)).json()
        self.assertEqual(body['v2_gaps'], ['surveys', 'mentoring'])
        admin = make_admin('admin', owning_org=self.org)          # the post-0097 shape: holds Scholars
        self.assertEqual(authed_client(self.lead).get(_url(admin)).json()['v2_gaps'], [])
        self.assertEqual(authed_client(self.lead).get(_url(self.lead)).json()['v2_gaps'], [])

    def test_a_dry_run_with_a_gap_names_it_and_still_saves(self):
        rev = make_admin('reviewer', owning_org=self.org)
        dry = _patch(self.lead, rev, ['review', 'announcements.edit'], dry_run=True).json()
        self.assertEqual(dry['v2_gaps'], ['announcements'])
        self.assertEqual(dry['consequences'][-1], spa.SCHOLARS_NEEDED)
        r = _patch(self.lead, rev, ['review', 'announcements.edit'])
        self.assertEqual(r.status_code, 200, r.content[:300])           # not a refusal
        self.assertTrue(r.json()['changed'])
        self.assertIn(spa.SCHOLARS_NEEDED, r.json()['consequences'])

    def test_a_gap_in_before_only_says_nothing(self):
        rev = make_admin('reviewer', owning_org=self.org, permissions=['review', 'surveys.view'])
        dry = _patch(self.lead, rev, ['review', 'scholars', 'surveys.view'], dry_run=True).json()
        self.assertEqual(dry['v2_gaps'], [])
        self.assertNotIn(spa.SCHOLARS_NEEDED, dry['consequences'])
        gone = _patch(self.lead, rev, ['review'], dry_run=True).json()     # the page goes instead
        self.assertNotIn(spa.SCHOLARS_NEEDED, gone['consequences'])

    def test_taking_scholars_from_an_admin_names_the_engagement_pages(self):
        admin = make_admin('admin', owning_org=self.org)
        asked = [k for k in spa.held_set(admin) if k != 'scholars']
        dry = _patch(self.lead, admin, asked, dry_run=True).json()
        self.assertEqual(dry['v2_gaps'], ['announcements', 'surveys', 'development', 'mentoring'])
        self.assertIn(spa.SCHOLARS_NEEDED, dry['consequences'])

    def test_the_shared_consequences_do_not_carry_the_code(self):
        rev = make_admin('reviewer', owning_org=self.org)
        self.assertNotIn(spa.SCHOLARS_NEEDED, spa.consequences(rev, ['review'], ['review', 'surveys.view']))
