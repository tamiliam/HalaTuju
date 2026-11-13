"""Sprint M2d A1 (owner, 2026-11-13) — a NEW case goes only to somebody who has SIGNED IN.

"Signed in" is `first_seen_at` set, and it has ONE home, `staff_lifecycle.has_signed_in`: the payment
chain (`payments_chain._signed_in`) asks the same function. The picker (`assignable-admins`) serves
`assignable` False for a reviewer who never has, so neither picker offers them — the row itself stays,
because the cockpit names the CURRENT holder from that list (bug #66). `assign_reviewer` refuses
`not_signed_in`, after revoked and paused and before the gift. Re-picking the current holder is still
the no-op (T1-d), and a case they already hold is never touched.

No real people: every name and address here is synthetic.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import payments_chain, staff_lifecycle
from apps.scholarship.models import AssignmentEvent, ScholarshipApplication
from apps.scholarship.services.assignment import may_assign_to
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
)

READY = 'apps.scholarship.services.assignment.is_ready_for_assignment'
LIST = '/api/v1/admin/scholarship/assignable-admins/'


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bp = PartnerOrganisation.objects.get(code='brightpath')
        cls.gift = make_programme(organisation=cls.bp, name_en='Gift A1')
        cls.other_gift = make_programme(organisation=cls.bp, name_en='Gift A1 other')
        cls.boss = make_admin('super', super_admin=True, uid='a1-su')
        cls.oa = make_admin('org_admin', owning_org=cls.bp, uid='a1-oa')
        cls.arrived = make_admin('reviewer', owning_org=cls.bp, uid='a1-in', first_seen_at=timezone.now())
        cls.never = make_admin('reviewer', owning_org=cls.bp, uid='a1-never')

    def _case(self, **kw):
        return make_application('profile_complete', cohort=make_cohort(programme=self.gift), **kw)

    def _post(self, caller, app, target):
        with patch(READY, return_value=True):
            return authed_client(caller).post(
                f'/api/v1/admin/scholarship/applications/{app.id}/assign/',
                {'reviewer_id': target.id}, format='json')

    def _rows(self, caller):
        return {r['id']: r for r in authed_client(caller).get(LIST).json()['admins']}

    def _refused(self, caller, target, code):
        app = self._case()
        r = self._post(caller, app, target)
        self.assertEqual((r.status_code, r.json()['code']), (400, code))
        app.refresh_from_db()
        self.assertIsNone(app.assigned_to_id)
        self.assertFalse(AssignmentEvent.objects.filter(application=app).exists())


class TestOneHomeForSignedIn(_Base):
    def test_the_payment_chain_asks_the_same_function(self):
        for admin in (self.arrived, self.never):
            self.assertEqual(payments_chain._signed_in(admin), staff_lifecycle.has_signed_in(admin))
        self.assertTrue(staff_lifecycle.has_signed_in(self.arrived))
        self.assertFalse(staff_lifecycle.has_signed_in(self.never))
        with patch('apps.scholarship.staff_lifecycle.has_signed_in', return_value=True) as asked:
            self.assertTrue(payments_chain._signed_in(self.never))
        asked.assert_called_once_with(self.never)


class TestThePickerLeavesThemOut(_Base):
    def test_a_never_signed_in_reviewer_is_not_offered(self):
        for caller in (self.boss, self.oa):
            row = self._rows(caller)[self.never.id]          # listed (bug #66), never offered
            self.assertFalse(row['assignable'])
            self.assertFalse(may_assign_to(caller, self.never))

    def test_a_signed_in_reviewer_is_unchanged(self):
        for caller in (self.boss, self.oa):
            self.assertTrue(self._rows(caller)[self.arrived.id]['assignable'])
            self.assertTrue(may_assign_to(caller, self.arrived))

    def test_they_are_offered_the_moment_they_sign_in(self):
        PartnerAdmin.objects.filter(pk=self.never.pk).update(first_seen_at=timezone.now())
        self.assertTrue(self._rows(self.oa)[self.never.id]['assignable'])


class TestAssignRefusesNotSignedIn(_Base):
    def test_a_super_is_refused(self):
        self._refused(self.boss, self.never, 'not_signed_in')

    def test_an_org_admin_is_refused_with_the_same_code(self):
        self._refused(self.oa, self.never, 'not_signed_in')

    def test_a_signed_in_reviewer_is_taken(self):
        app = self._case()
        r = self._post(self.oa, app, self.arrived)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['assigned_to_id'], self.arrived.id)

    def test_a_holder_re_pick_is_still_a_no_op(self):
        app = self._case()
        ScholarshipApplication.objects.filter(pk=app.pk).update(assigned_to=self.never)
        for caller in (self.boss, self.oa):
            r = self._post(caller, app, self.never)
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(r.json()['assigned_to_id'], self.never.id)
        self.assertFalse(AssignmentEvent.objects.filter(application=app).exists())

    def test_a_held_case_may_go_to_a_signed_in_reviewer(self):
        app = self._case()
        ScholarshipApplication.objects.filter(pk=app.pk).update(assigned_to=self.never)
        r = self._post(self.oa, app, self.arrived)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['assigned_to_id'], self.arrived.id)


class TestTheRefusalOrder(_Base):
    """Revoked, then paused, then not signed in, then the gift: the bigger fact is named first."""

    def test_paused_is_named_before_not_signed_in(self):
        PartnerAdmin.objects.filter(pk=self.never.pk).update(paused_at=timezone.now())
        self._refused(self.boss, self.never, 'reviewer_paused')

    def test_not_signed_in_is_named_before_the_gift(self):
        from apps.courses import staff_gift
        staff_gift.set_gifts(self.never, [self.other_gift])
        self._refused(self.boss, self.never, 'not_signed_in')

    def test_revoked_is_named_before_not_signed_in(self):
        from apps.scholarship.services import AssignmentError
        from apps.scholarship.services import assign_reviewer
        PartnerAdmin.objects.filter(pk=self.never.pk).update(is_active=False)
        self.never.refresh_from_db()
        app = self._case()
        with patch(READY, return_value=True), self.assertRaises(AssignmentError) as e:
            assign_reviewer(app, reviewer=self.never, by_admin=None)
        self.assertEqual(e.exception.code, 'not_reviewer')
