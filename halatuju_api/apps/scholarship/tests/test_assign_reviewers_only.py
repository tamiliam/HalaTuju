"""T1 (owner D7, 2026-11-09) — a case is given only to someone in the REVIEWERS table.

Before T1 the R1 override let a SUPER hand a case to any admin, qc or org admin keeping `see_all`,
and a super could hand one to another super. Now every caller, a super included, may give a case
only to someone `staff_tables.in_reviewers` admits; an org admin only to their own organisation's.
The refusal codes are unchanged: `not_reviewer` from the service, `bad_assignee` from the org admin's
own gate. R1 still decides who may HOLD a case (`is_review_target`), so a case an admin held before
T1 stays theirs and re-picking them is a no-op (T1-d).

A reviewer of another gift is still refused `gift_mismatch` — `test_assign_gift_mismatch.py`.

No real people: every name and address here is synthetic.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_tables
from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import scheduling
from apps.scholarship.models import AssignmentEvent, ScholarshipApplication
from apps.scholarship.services.assignment import is_review_target, may_assign_to
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)

READY = 'apps.scholarship.services.assignment.is_ready_for_assignment'
LIST = '/api/v1/admin/scholarship/assignable-admins/'


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bp = PartnerOrganisation.objects.get(code='brightpath')
        cls.other = make_org()
        cls.gift = make_programme(organisation=cls.bp, name_en='Gift T1')
        cls.boss = make_admin('super', super_admin=True, uid='t1-su')
        cls.oa = make_admin('org_admin', owning_org=cls.bp, uid='t1-oa')
        cls.reviewer = make_admin('reviewer', owning_org=cls.bp, uid='t1-rv', first_seen_at=timezone.now())
        cls.far_reviewer = make_admin('reviewer', owning_org=cls.other, uid='t1-far')
        # Outside Reviewers — every one an R1 super target before T1 (bar the super).
        cls.seer = make_admin('admin', owning_org=cls.bp, permissions=['see_all'], uid='t1-ad')
        cls.lead = make_admin('org_admin', owning_org=cls.bp, uid='t1-lead')
        cls.other_super = make_admin('super', super_admin=True, uid='t1-su2')

    def _case(self, **kw):
        return make_application('profile_complete', cohort=make_cohort(programme=self.gift), **kw)

    def _post(self, caller, app, target):
        with patch(READY, return_value=True):
            return authed_client(caller).post(
                f'/api/v1/admin/scholarship/applications/{app.id}/assign/',
                {'reviewer_id': target.id}, format='json')

    def _rows(self, caller):
        return {r['id']: r for r in authed_client(caller).get(LIST).json()['admins']}


class TestASuperGivesCasesOnlyToReviewers(_Base):
    def _refused(self, target):
        self.assertFalse(staff_tables.in_reviewers(target))
        self.assertFalse(may_assign_to(self.boss, target))
        row = self._rows(self.boss).get(target.id)
        if row is not None:                       # listed (bug #66) but never offered
            self.assertFalse(row['assignable'])
        app = self._case()
        r = self._post(self.boss, app, target)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_reviewer'))
        app.refresh_from_db()
        self.assertIsNone(app.assigned_to_id)
        self.assertFalse(AssignmentEvent.objects.filter(application=app).exists())

    def test_an_admin_with_see_all_is_refused(self):
        self._refused(self.seer)

    def test_an_org_admin_not_in_reviewers_is_refused(self):
        self._refused(self.lead)

    def test_another_super_is_refused(self):
        self._refused(self.other_super)

    def test_a_reviewer_is_taken(self):
        self.assertTrue(self._rows(self.boss)[self.reviewer.id]['assignable'])
        app = self._case()
        r = self._post(self.boss, app, self.reviewer)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['assigned_to_id'], self.reviewer.id)


class TestAQcPersonWithoutReviewOrQc(_Base):
    """The brief asked for "a qc-role person without review/qc" outside Reviewers. By the LABEL they
    are in Reviewers (`REVIEWER_ROLES` names qc), so that person cannot be built. What T1 adds: such
    a person who cannot hold a case either (no `review`, no `see_all`) is not offered and is refused,
    because `may_assign_to` also asks `is_review_target` — the picker and the server agree."""

    def test_a_qc_with_nothing_is_in_reviewers_yet_not_assignable(self):
        bare = make_admin('qc', owning_org=self.bp, permissions=[], uid='t1-qc0')
        self.assertTrue(staff_tables.in_reviewers(bare))
        self.assertFalse(is_review_target(bare))
        self.assertFalse(self._rows(self.boss)[bare.id]['assignable'])
        r = self._post(self.boss, self._case(), bare)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_reviewer'))

    def test_a_qc_keeping_see_all_stays_assignable(self):
        seeing = make_admin('qc', owning_org=self.bp, permissions=['see_all'], uid='t1-qc1',
                            first_seen_at=timezone.now())
        self.assertTrue(self._rows(self.boss)[seeing.id]['assignable'])
        self.assertTrue(self._rows(self.oa)[seeing.id]['assignable'])


class TestAnOrgAdminGivesCasesToTheirOwnReviewers(_Base):
    def test_an_own_organisation_reviewer_is_taken(self):
        self.assertTrue(self._rows(self.oa)[self.reviewer.id]['assignable'])
        app = self._case()
        r = self._post(self.oa, app, self.reviewer)
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.reviewer.id)

    def test_another_organisation_s_reviewer_is_refused(self):
        self.assertNotIn(self.far_reviewer.id, self._rows(self.oa))
        self.assertFalse(may_assign_to(self.oa, self.far_reviewer))
        app = self._case()
        r = self._post(self.oa, app, self.far_reviewer)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_assignee'))
        app.refresh_from_db()
        self.assertIsNone(app.assigned_to_id)

    def test_an_admin_with_see_all_is_refused_as_before(self):
        r = self._post(self.oa, self._case(), self.seer)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_assignee'))


class TestAnOrgAdminWhoJoinedReviewers(_Base):
    def test_they_are_assignable_and_taken(self):
        joined = make_admin('org_admin', owning_org=self.bp, permissions=['review'], uid='t1-jn',
                            first_seen_at=timezone.now())
        self.assertTrue(staff_tables.in_reviewers(joined))
        self.assertTrue(self._rows(self.boss)[joined.id]['assignable'])
        self.assertTrue(self._rows(self.oa)[joined.id]['assignable'])
        app = self._case()
        r = self._post(self.oa, app, joined)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['assigned_to_id'], joined.id)


class TestACaseHeldBeforeT1IsKept(_Base):
    """T1-d. A case an admin (or a super) held before T1 is not taken away: the holder is still
    listed and may still work it. Re-picking an ACTIVE holder is the existing no-op and writes
    nothing; a paused or revoked holder is refused as before (the web never sends a same-value pick)."""

    def _held_by(self, holder):
        app = self._case()
        ScholarshipApplication.objects.filter(pk=app.pk).update(assigned_to=holder)
        app.refresh_from_db()
        return app

    def test_the_admin_holder_is_listed_and_may_still_work_it(self):
        self._held_by(self.seer)
        self.assertIn(self.seer.id, self._rows(self.boss))
        self.assertIn(self.seer.id, self._rows(self.oa))
        self.assertTrue(is_review_target(self.seer))
        self.assertTrue(scheduling._can_review(self.seer))

    def test_a_super_re_picking_the_admin_holder_is_a_no_op(self):
        app = self._held_by(self.seer)
        r = self._post(self.boss, app, self.seer)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['assigned_to_id'], self.seer.id)
        self.assertFalse(AssignmentEvent.objects.filter(application=app).exists())

    def test_an_org_admin_re_picking_the_admin_holder_is_a_no_op(self):
        app = self._held_by(self.seer)
        r = self._post(self.oa, app, self.seer)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['assigned_to_id'], self.seer.id)
        self.assertFalse(AssignmentEvent.objects.filter(application=app).exists())

    def test_a_case_held_by_a_super_is_kept_on_a_re_pick(self):
        app = self._held_by(self.other_super)
        r = self._post(self.boss, app, self.other_super)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['assigned_to_id'], self.other_super.id)

    def test_a_paused_holder_re_picked_is_refused_as_before(self):
        app = self._held_by(self.seer)
        PartnerAdmin.objects.filter(pk=self.seer.pk).update(paused_at=timezone.now())
        r = self._post(self.boss, app, self.seer)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'reviewer_paused'))
        self.assertFalse(AssignmentEvent.objects.filter(application=app).exists())

    def test_the_holder_may_be_replaced_by_a_reviewer(self):
        app = self._held_by(self.seer)
        r = self._post(self.oa, app, self.reviewer)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['assigned_to_id'], self.reviewer.id)


class TestTheHolderSkipIsOnlyForTheHolder(_Base):
    """T1-d's skip (`assign_reviewer` and the org admin's gate) spares the CURRENT holder alone. On a
    case an admin with `see_all` holds, every other target outside the rule is still refused — this
    fails if the skip ever widens to "any case somebody holds"."""

    def _held_by_the_seer(self):
        self.assertFalse(staff_tables.in_reviewers(self.seer))
        app = self._case()
        ScholarshipApplication.objects.filter(pk=app.pk).update(assigned_to=self.seer)
        app.refresh_from_db()
        return app

    def _still_held(self, app, r, code):
        self.assertEqual((r.status_code, r.json()['code']), (400, code))
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.seer.id)
        self.assertFalse(AssignmentEvent.objects.filter(application=app).exists())

    def test_a_super_still_may_not_pick_an_org_admin_outside_reviewers(self):
        app = self._held_by_the_seer()
        self._still_held(app, self._post(self.boss, app, self.lead), 'not_reviewer')

    def test_a_super_still_may_not_pick_another_super(self):
        app = self._held_by_the_seer()
        self._still_held(app, self._post(self.boss, app, self.other_super), 'not_reviewer')

    def test_an_org_admin_still_may_not_pick_another_organisation_s_reviewer(self):
        app = self._held_by_the_seer()
        self._still_held(app, self._post(self.oa, app, self.far_reviewer), 'bad_assignee')


class TestTheListRowsCarryTheCaseGifts(_Base):
    """T1-e: the applications list hides a Reviewer of another gift, so each row names its gifts."""

    def test_a_row_names_its_gift(self):
        app = self._case()
        rows = authed_client(self.boss).get('/api/v1/admin/scholarship/applications/').json()
        rows = rows['applications']
        row = next(r for r in rows if r['id'] == app.id)
        self.assertEqual(row['gift_ids'], [self.gift.id])

    def test_a_moved_case_names_both_gifts_sorted(self):
        # A case moved to another gift keeps its old cohort: its own `programme` and its cohort's
        # differ, and either one lets a reviewer of that gift take it (`case_gifts`).
        moved_to = make_programme(organisation=self.bp, name_en='Gift T1 moved')
        app = self._case()
        ScholarshipApplication.objects.filter(pk=app.pk).update(programme=moved_to)
        rows = authed_client(self.boss).get('/api/v1/admin/scholarship/applications/').json()
        row = next(r for r in rows['applications'] if r['id'] == app.id)
        self.assertEqual(row['gift_ids'], sorted([self.gift.id, moved_to.id]))
        self.assertEqual(len(row['gift_ids']), 2)
