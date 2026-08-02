"""Request #10 — pause: a volunteer steps back from NEW work without losing anything else.

BrightPath's reviewers are unpaid, and the only lever that existed was `is_active` — a revoke. The
requester asked for pause as a distinct, non-pejorative state a reviewer can set on themselves.

**Pause ≠ revoke is the whole test file.** Two flags that nearly mean the same thing will be
confused (lessons.md, IC lock 2026-07-29), so every behaviour that separates them is asserted
rather than described:

  - a paused reviewer can still SIGN IN               (revoke blocks the admin lookup entirely)
  - a paused reviewer is still LISTED, everywhere     (dropping them reproduces bug #66)
  - a paused reviewer takes NO NEW case
  - a paused reviewer can still FINISH one already theirs — propose times, record the verdict
  - un-pause exists, by themselves and by an org_admin

The fourth is the one a careless implementation gets wrong: `services._can_review` and
`scheduling._can_review` look like mirrors, and pause belongs in exactly one of them.
"""
import datetime

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import scheduling, services
from apps.scholarship.models import (
    ReviewerProfile, ScholarshipApplication, ScholarshipCohort,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
LIST = '/api/v1/admin/reviewers/'
PROFILE = '/api/v1/admin/reviewer-profile/'
ASSIGNABLE = '/api/v1/admin/scholarship/assignable-admins/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='pz', name='Pause Org')
        cls.other = PartnerOrganisation.objects.create(code='pz2', name='Other Org')
        cls.cohort = ScholarshipCohort.objects.create(
            code='pz-2026', name='PZ', year=2026, owning_organisation=cls.org)

        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='pz-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='dina@pz.test')
        cls.plain_admin = PartnerAdmin.objects.create(
            supabase_user_id='pz-ad', role='admin', is_active=True,
            owning_organisation=cls.org, name='Ravi', email='ravi@pz.test')
        cls.finance = PartnerAdmin.objects.create(
            supabase_user_id='pz-fi', role='finance', is_active=True,
            owning_organisation=cls.org, name='Fara', email='fara@pz.test')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='pz-r1', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Anand', email='anand@pz.test')
        cls.other_reviewer = PartnerAdmin.objects.create(
            supabase_user_id='pz-r2', role='reviewer', is_active=True,
            owning_organisation=cls.org, name='Kavitha', email='kavitha@pz.test')
        cls.foreign = PartnerAdmin.objects.create(
            supabase_user_id='pz-x', role='reviewer', is_active=True,
            owning_organisation=cls.other, name='Intruder', email='x@pz2.test')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='pz-su', is_super_admin=True, is_active=True,
            name='Super', email='su@pz.test')
        ReviewerProfile.objects.create(partner_admin=cls.reviewer)

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _app(self, *, reviewer=None, status='profile_complete', seed='01'):
        prof = StudentProfile.objects.create(
            supabase_user_id=f'pz-stud-{seed}-{timezone.now().timestamp()}',
            nric=f'0101{seed}-14-0001', name=f'Stud {seed}')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=prof, status=status, assigned_to=reviewer,
            assigned_at=timezone.now() - datetime.timedelta(days=3) if reviewer else None)

    def _pause(self, admin):
        services.set_paused(admin, True)
        admin.refresh_from_db()
        return admin


class TestPauseIsNotRevoke(_Base):
    """Every behaviour where the two flags must part company."""

    def test_it_does_NOT_touch_is_active(self):
        self._pause(self.reviewer)
        self.assertTrue(self.reviewer.is_active)
        self.assertIsNotNone(self.reviewer.paused_at)

    def test_a_paused_reviewer_can_still_SIGN_IN(self):
        # The admin lookup filters on is_active. Had pause been built on that flag, a reviewer
        # could never have reached the switch to un-pause themselves.
        self._pause(self.reviewer)
        self._auth('pz-r1')
        self.assertEqual(self.client.get(PROFILE).status_code, 200)

    def test_a_paused_reviewer_is_still_IN_THE_ASSIGNMENT_DROPDOWN(self):
        # ⚠ Filtering them out reproduces bug #66: the cockpit unions the current assignee in from
        # this list, so a dropped name makes a case read as "Unassigned" when it is not.
        self._pause(self.reviewer)
        self._auth('pz-oa')
        rows = self.client.get(ASSIGNABLE).json()['admins']
        row = next(a for a in rows if a['id'] == self.reviewer.id)
        self.assertTrue(row['paused'])          # flagged, so the option can render disabled

    def test_a_paused_reviewer_is_still_ON_THE_REVIEWERS_TABLE(self):
        self._pause(self.reviewer)
        self._auth('pz-oa')
        row = next(r for r in self.client.get(LIST).json()['reviewers']
                   if r['id'] == self.reviewer.id)
        self.assertTrue(row['paused'])
        self.assertIsNotNone(row['paused_at'])

    def test_a_REVOKED_reviewer_is_absent_where_a_paused_one_is_present(self):
        # The contrast in one assertion: revoke removes, pause annotates.
        self.reviewer.is_active = False
        self.reviewer.save(update_fields=['is_active'])
        self._pause(self.other_reviewer)
        self._auth('pz-oa')
        ids = {r['id'] for r in self.client.get(LIST).json()['reviewers']}
        self.assertNotIn(self.reviewer.id, ids)
        self.assertIn(self.other_reviewer.id, ids)


class TestPauseStopsNewWorkOnly(_Base):
    def test_a_paused_reviewer_cannot_be_ASSIGNED(self):
        # ⚠ AND THE REASON GIVEN IS THE TRUE ONE. Until 2026-08-03 this refusal came back as
        # `not_reviewer` — "You can only assign to a reviewer" — about somebody who IS a reviewer
        # and has simply stepped back. Found by walking pause end-to-end on production, not by any
        # test: every test asserted THAT it refused, none read what it said. The dropdown disables
        # a paused option, so this is reached from a page loaded BEFORE the pause, which is exactly
        # when a wrong reason sends an org_admin looking for a problem that does not exist.
        self._pause(self.reviewer)
        app = self._app(seed='02')
        with self.assertRaises(services.AssignmentError) as ctx:
            services.assign_reviewer(app, reviewer=self.reviewer, by_admin=self.oa)
        self.assertEqual(str(ctx.exception), 'reviewer_paused')

    def test_a_REVOKED_account_still_reads_not_reviewer_even_if_also_paused(self):
        # Revoked is the bigger fact. Someone paused and then revoked has no account to come back
        # to, so "they have paused themselves, they can start again" would be the wrong advice.
        self._pause(self.reviewer)
        self.reviewer.is_active = False
        self.reviewer.save(update_fields=['is_active'])
        app = self._app(seed='07')
        with self.assertRaises(services.AssignmentError) as ctx:
            services.assign_reviewer(app, reviewer=self.reviewer, by_admin=self.oa)
        self.assertEqual(str(ctx.exception), 'not_reviewer')

    def test_someone_who_never_could_review_still_reads_not_reviewer(self):
        # The plain case the message was written for, unchanged. `finance` is the right subject:
        # it has no B40 scope at all, whereas org_admin and admin ARE valid assignment targets
        # (assignment is what grants them selective write access) — a first draft of this test
        # used org_admin and got `not_ready`, which is the readiness gate, not this one.
        app = self._app(seed='08')
        with self.assertRaises(services.AssignmentError) as ctx:
            services.assign_reviewer(app, reviewer=self.finance, by_admin=self.oa)
        self.assertEqual(str(ctx.exception), 'not_reviewer')

    def test_they_KEEP_the_case_they_were_already_holding(self):
        app = self._app(reviewer=self.reviewer, status='interviewing', seed='03')
        self._pause(self.reviewer)
        app.refresh_from_db()
        self.assertEqual(app.assigned_to_id, self.reviewer.id)

    def test_they_can_still_PROPOSE_INTERVIEW_TIMES_for_a_case_already_theirs(self):
        # ⚠ THE ONE THAT BREAKS IF PAUSE IS COPIED INTO scheduling._can_review. Stranding every
        # in-flight interview the moment somebody steps back is the opposite of what pause is for.
        self._pause(self.reviewer)
        self.assertTrue(scheduling._can_review(self.reviewer))

    def test_the_two_can_review_gates_differ_ONLY_over_pause(self):
        # Both permissive before, exactly one refuses after — so a future edit that "tidies" them
        # back into agreement fails here rather than in production.
        self.assertTrue(services._can_review(self.reviewer))
        self.assertTrue(scheduling._can_review(self.reviewer))
        self._pause(self.reviewer)
        self.assertFalse(services._can_review(self.reviewer))
        self.assertTrue(scheduling._can_review(self.reviewer))

    def test_UNPAUSING_makes_them_assignable_again(self):
        self._pause(self.reviewer)
        services.set_paused(self.reviewer, False)
        self.reviewer.refresh_from_db()
        self.assertIsNone(self.reviewer.paused_at)
        self.assertTrue(services._can_review(self.reviewer))
        # The bare fixture application is not itself ready for a first assignment (a pre-existing
        # rule about the STUDENT, nothing to do with pause) — so assert the refusal is no longer
        # about the REVIEWER. Asserting the happy path here would be testing `is_ready_for_assignment`.
        app = self._app(seed='04')
        with self.assertRaises(services.AssignmentError) as ctx:
            services.assign_reviewer(app, reviewer=self.reviewer, by_admin=self.oa)
        self.assertNotEqual(str(ctx.exception), 'not_reviewer')


class TestTheSetter(_Base):
    def test_pausing_twice_keeps_the_ORIGINAL_timestamp(self):
        # A stray second click must not rewrite when somebody stepped back.
        self._pause(self.reviewer)
        first = self.reviewer.paused_at
        services.set_paused(self.reviewer, True)
        self.reviewer.refresh_from_db()
        self.assertEqual(self.reviewer.paused_at, first)

    def test_unpausing_somebody_who_is_not_paused_is_a_no_op(self):
        services.set_paused(self.reviewer, False)
        self.reviewer.refresh_from_db()
        self.assertIsNone(self.reviewer.paused_at)

    def test_it_refuses_somebody_who_is_never_ASSIGNED_work(self):
        # A "Paused" pill on a finance admin would be a control that changes nothing.
        with self.assertRaises(services.PauseError) as ctx:
            services.set_paused(self.finance, True)
        self.assertEqual(ctx.exception.code, 'not_reviewable')

    def test_it_refuses_a_REVOKED_account(self):
        self.reviewer.is_active = False
        self.reviewer.save(update_fields=['is_active'])
        with self.assertRaises(services.PauseError) as ctx:
            services.set_paused(self.reviewer, True)
        self.assertEqual(ctx.exception.code, 'not_active')


class TestTheReviewersOwnSwitch(_Base):
    def test_a_reviewer_pauses_themselves_from_their_own_profile(self):
        self._auth('pz-r1')
        r = self.client.patch(PROFILE, {'paused': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['paused'])
        self.reviewer.refresh_from_db()
        self.assertIsNotNone(self.reviewer.paused_at)

    def test_and_un_pauses_themselves_again(self):
        self._pause(self.reviewer)
        self._auth('pz-r1')
        r = self.client.patch(PROFILE, {'paused': False}, format='json')
        self.assertFalse(r.json()['paused'])

    def test_the_switch_travels_with_the_rest_of_their_profile(self):
        # One screen owns "how I take part"; splitting pause into a second call would be an
        # implementation detail (it lives on a different table) leaking into the UI.
        self._auth('pz-r1')
        r = self.client.patch(
            PROFILE, {'paused': True, 'university': 'UPM'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['paused'])
        self.assertEqual(r.json()['university'], 'UPM')

    def test_a_profile_save_that_says_nothing_about_pause_leaves_it_alone(self):
        self._pause(self.reviewer)
        self._auth('pz-r1')
        r = self.client.patch(PROFILE, {'university': 'UM'}, format='json')
        self.assertTrue(r.json()['paused'])

    def test_pause_never_reaches_the_ReviewerProfile_row(self):
        # It is stored once, on PartnerAdmin. A second copy here would be a second truth to drift.
        self._auth('pz-r1')
        self.client.patch(PROFILE, {'paused': True}, format='json')
        self.assertFalse(hasattr(ReviewerProfile.objects.get(partner_admin=self.reviewer),
                                 'paused'))


class TestTheAdminSwitch(_Base):
    URL = staticmethod(lambda pk: f'/api/v1/admin/reviewers/{pk}/pause/')

    def test_an_org_admin_can_pause_one_of_their_reviewers(self):
        self._auth('pz-oa')
        r = self.client.post(self.URL(self.reviewer.id), {'paused': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['paused'])

    def test_and_can_bring_them_back(self):
        self._pause(self.reviewer)
        self._auth('pz-oa')
        r = self.client.post(self.URL(self.reviewer.id), {'paused': False}, format='json')
        self.assertFalse(r.json()['paused'])

    def test_a_plain_admin_may_READ_the_surface_but_not_change_who_gets_work(self):
        # The list gate admits admin + finance; deciding who gets work is staff management, which
        # the role matrix gives to super + org_admin only. This re-gates rather than inheriting.
        self._auth('pz-ad')
        self.assertEqual(self.client.get(LIST).status_code, 200)
        r = self.client.post(self.URL(self.reviewer.id), {'paused': True}, format='json')
        self.assertEqual(r.status_code, 403)
        self.reviewer.refresh_from_db()
        self.assertIsNone(self.reviewer.paused_at)

    def test_finance_is_refused_too(self):
        self._auth('pz-fi')
        self.assertEqual(
            self.client.post(self.URL(self.reviewer.id), {'paused': True},
                             format='json').status_code, 403)

    def test_another_organisations_reviewer_is_404_not_403(self):
        # A 403 would confirm that another tenant's staff member exists.
        self._auth('pz-oa')
        r = self.client.post(self.URL(self.foreign.id), {'paused': True}, format='json')
        self.assertEqual(r.status_code, 404)
        self.foreign.refresh_from_db()
        self.assertIsNone(self.foreign.paused_at)

    def test_a_super_can_pause_across_organisations(self):
        self._auth('pz-su')
        r = self.client.post(self.URL(self.foreign.id), {'paused': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
