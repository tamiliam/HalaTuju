"""WHEN a case may change hands (owner, 2026-07-13).

A reviewer is assigned to DO the review, so assignment only makes sense while there is a review
to do:

    shortlisted / rejected  ✗   not ready, or never will be — nothing to review
    Completed               ✓   waiting for a reviewer
    interviewing            ✓   a reviewer is working it; a super may hand it over
    Awaiting QC onward      ✗   the review is OVER — retargeting it would detach finished work
                                from the person who did it

The hole this closes: only the FIRST assignment of an unassigned application was gated (on
is_ready_for_assignment). REASSIGNMENT was explicitly allowed at any status — so every awarded and
rejected student was silently retargetable from the list dropdown, one stray click away.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import (AssignmentError, assign_reviewer,
                                       is_assignable)

_ASSIGNABLE = {'profile_complete', 'interviewing'}
_ALL = ['shortlisted', 'profile_complete', 'interviewing', 'interviewed', 'recommended',
        'awarded', 'active', 'maintenance', 'rejected', 'withdrawn', 'expired', 'closed']


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='s', email='s@x.com', name='Super',
            is_super_admin=True, is_active=True, role='super')
        cls.r1 = PartnerAdmin.objects.create(
            supabase_user_id='r1', email='r1@x.com', name='R1',
            is_active=True, role='reviewer')
        cls.r2 = PartnerAdmin.objects.create(
            supabase_user_id='r2', email='r2@x.com', name='R2',
            is_active=True, role='reviewer')

    def _app(self, status, *, assigned=None):
        profile = StudentProfile.objects.create(
            supabase_user_id=f'p-{status}-{bool(assigned)}', name='KAVITHA A/P SURESH',
            nric='080214-08-1234', preferred_state='Perak', household_income=1500,
            household_size=4, receives_str=False, receives_jkm=False,
        )
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status=status,
            profile_completed_at=None if status == 'shortlisted' else timezone.now(),
            assigned_to=assigned,
            assigned_at=timezone.now() if assigned else None,
        )


class TestIsAssignable(_Base):
    def test_only_completed_and_interviewing(self):
        for stage in _ALL:
            with self.subTest(stage=stage):
                self.assertEqual(is_assignable(self._app(stage)), stage in _ASSIGNABLE)


class TestAssignReviewerRespectsTheStage(_Base):
    def test_can_assign_a_completed_case(self):
        app = self._app('profile_complete')
        assign_reviewer(app, reviewer=self.r1, by_admin=self.super)
        self.assertEqual(app.assigned_to, self.r1)

    def test_can_hand_over_a_case_being_interviewed(self):
        app = self._app('interviewing', assigned=self.r1)
        assign_reviewer(app, reviewer=self.r2, by_admin=self.super)
        self.assertEqual(app.assigned_to, self.r2)

    def test_cannot_reassign_an_awarded_case(self):
        # THE hole: reassignment used to be allowed at ANY status. All 31 awarded students were
        # one stray dropdown click from being retargeted.
        app = self._app('awarded', assigned=self.r1)
        with self.assertRaises(AssignmentError) as cm:
            assign_reviewer(app, reviewer=self.r2, by_admin=self.super)
        self.assertEqual(cm.exception.code, 'not_assignable')
        app.refresh_from_db()
        self.assertEqual(app.assigned_to, self.r1)   # untouched

    def test_cannot_reassign_a_rejected_case(self):
        app = self._app('rejected', assigned=self.r1)
        with self.assertRaises(AssignmentError) as cm:
            assign_reviewer(app, reviewer=self.r2, by_admin=self.super)
        self.assertEqual(cm.exception.code, 'not_assignable')

    def test_cannot_assign_at_awaiting_qc(self):
        # The review is over — the verdict is in.
        app = self._app('interviewed', assigned=self.r1)
        with self.assertRaises(AssignmentError) as cm:
            assign_reviewer(app, reviewer=self.r2, by_admin=self.super)
        self.assertEqual(cm.exception.code, 'not_assignable')

    def test_cannot_assign_a_shortlisted_case(self):
        # Was already refused (not_ready, no submission); now refused earlier and for the right
        # reason — there is nothing to review yet.
        app = self._app('shortlisted')
        with self.assertRaises(AssignmentError) as cm:
            assign_reviewer(app, reviewer=self.r1, by_admin=self.super)
        self.assertEqual(cm.exception.code, 'not_assignable')

    def test_cannot_unassign_a_recommended_case(self):
        # Unassign is gated too — not just assign/reassign. The refusal is the MORE SPECIFIC
        # 'findings_submitted' (a verdict exists; reopen the decision first) rather than the
        # generic 'not_assignable': it tells the super what to do, not merely that they can't.
        app = self._app('recommended', assigned=self.r1)
        with self.assertRaises(AssignmentError) as cm:
            assign_reviewer(app, reviewer=None, by_admin=self.super)
        self.assertEqual(cm.exception.code, 'findings_submitted')
        app.refresh_from_db()
        self.assertEqual(app.assigned_to, self.r1)   # untouched either way

    def test_unassigning_an_interviewing_case_still_works(self):
        # The existing teardown path (returns the case to the pool) must survive the new gate.
        app = self._app('interviewing', assigned=self.r1)
        assign_reviewer(app, reviewer=None, by_admin=self.super)
        app.refresh_from_db()
        self.assertIsNone(app.assigned_to)
        self.assertEqual(app.status, 'profile_complete')

    def test_a_no_op_is_still_a_no_op_even_when_blocked(self):
        # Re-selecting the SAME reviewer on a closed case must not raise — nothing is changing.
        app = self._app('awarded', assigned=self.r1)
        assign_reviewer(app, reviewer=self.r1, by_admin=self.super)
        self.assertEqual(app.assigned_to, self.r1)
