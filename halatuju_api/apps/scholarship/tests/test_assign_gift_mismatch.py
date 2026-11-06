"""TD-501 (audit fix A1.3, owner ruling 2026-11-06) — the gift blocks ASSIGNMENT.

Before, a reviewer's gift only greyed their row in the picker; `assign_reviewer` took the
assignment anyway, so a gift-A reviewer could be handed (and then read) a gift-B case. Now the
server refuses `gift_mismatch` (400). An every-gift reviewer (programme NULL) or a case of unknown
gift is still allowed, and a case already held is not taken away.

No real student data: every name and address here is synthetic.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import services
from apps.scholarship.models import AssignmentEvent, ScholarshipApplication
from apps.scholarship.services.assignment import case_gift, gift_allows, reviewer_gifts
from apps.courses.models import PartnerOrganisation
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
)

READY = 'apps.scholarship.services.assignment.is_ready_for_assignment'


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bp = PartnerOrganisation.objects.get(code='brightpath')
        cls.gift_a = make_programme(organisation=cls.bp, name_en='Gift A')
        cls.gift_b = make_programme(organisation=cls.bp, name_en='Gift B')
        cls.oa = make_admin('org_admin', owning_org=cls.bp, uid='gm-oa')
        cls.boss = make_admin('super', super_admin=True, uid='gm-su')
        cls.rev_a = make_admin('reviewer', owning_org=cls.bp, programme=cls.gift_a, uid='gm-ra')
        cls.rev_every = make_admin('reviewer', owning_org=cls.bp, uid='gm-re')

    def _case(self, programme, **kw):
        return make_application('profile_complete', cohort=make_cohort(programme=programme), **kw)

    def _post(self, caller, app, reviewer):
        with patch(READY, return_value=True):
            return authed_client(caller).post(
                f'/api/v1/admin/scholarship/applications/{app.id}/assign/',
                {'reviewer_id': reviewer.id}, format='json')


class TestTheServiceRefusesAnotherGift(_Base):
    def test_a_gift_a_reviewer_cannot_be_given_a_gift_b_case_and_nothing_is_written(self):
        app = self._case(self.gift_b)
        with patch(READY, return_value=True), self.assertRaises(services.AssignmentError) as ctx:
            services.assign_reviewer(app, reviewer=self.rev_a, by_admin=self.oa)
        self.assertEqual(str(ctx.exception), 'gift_mismatch')
        app.refresh_from_db()
        self.assertIsNone(app.assigned_to_id)
        self.assertFalse(AssignmentEvent.objects.filter(application=app).exists())

    def test_the_cohort_gift_is_used_when_the_case_carries_none(self):
        app = self._case(self.gift_b)
        ScholarshipApplication.objects.filter(pk=app.pk).update(programme=None)
        app.refresh_from_db()
        self.assertEqual(case_gift(app), self.gift_b.id)
        with patch(READY, return_value=True), self.assertRaises(services.AssignmentError) as ctx:
            services.assign_reviewer(app, reviewer=self.rev_a, by_admin=self.oa)
        self.assertEqual(str(ctx.exception), 'gift_mismatch')


class TestTheEndpointSays400(_Base):
    def test_an_org_admin_is_refused_gift_mismatch(self):
        app = self._case(self.gift_b)
        r = self._post(self.oa, app, self.rev_a)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'gift_mismatch'))
        app.refresh_from_db()
        self.assertIsNone(app.assigned_to_id)

    def test_a_super_is_refused_too(self):
        app = self._case(self.gift_b)
        r = self._post(self.boss, app, self.rev_a)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'gift_mismatch'))

    def test_the_same_gift_is_allowed(self):
        app = self._case(self.gift_a)
        r = self._post(self.oa, app, self.rev_a)
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.rev_a.id)

    def test_an_every_gift_reviewer_is_allowed(self):
        app = self._case(self.gift_b)
        r = self._post(self.oa, app, self.rev_every)
        self.assertEqual(r.status_code, 200, r.content)

    def test_a_case_of_unknown_gift_is_allowed(self):
        app = self._case(None)
        self.assertIsNone(case_gift(app))
        # A super: a case with no gift has no organisation either, so an org_admin's fence 404s it.
        r = self._post(self.boss, app, self.rev_a)
        self.assertEqual(r.status_code, 200, r.content)

    def test_a_case_already_held_is_not_taken_away(self):
        # Assigned before the rule (the factory writes it directly): re-sending the same person is
        # a no-op, and the case stays theirs.
        app = make_application('assigned', cohort=make_cohort(programme=self.gift_b),
                               reviewer=self.rev_a)
        r = self._post(self.oa, app, self.rev_a)
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.rev_a.id)


class TestTheRuleHasOneHome(_Base):
    def test_reviewer_gifts_is_a_set_or_none_for_every_gift(self):
        # Written as membership so multi-gift tagging (a later sprint) changes `reviewer_gifts` only.
        self.assertEqual(reviewer_gifts(self.rev_a), frozenset({self.gift_a.id}))
        self.assertIsNone(reviewer_gifts(self.rev_every))

    def test_gift_allows(self):
        a, b, none = self._case(self.gift_a), self._case(self.gift_b), self._case(None)
        self.assertTrue(gift_allows(self.rev_a, a))
        self.assertFalse(gift_allows(self.rev_a, b))
        self.assertTrue(gift_allows(self.rev_a, none))
        self.assertTrue(gift_allows(self.rev_every, b))
