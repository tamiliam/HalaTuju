"""Sprint S1 team leftovers: TD-627, TD-634, TD-616 and TD-630, each through its real door.

  * TD-627 — `may_hand_to` refuses a caller of NO organisation, even towards a target of no organisation
    (`None == None` used to pass the organisation test);
  * TD-634 — a super handing a case to another organisation's reviewer is told `wrong_organisation`,
    not `not_reviewer`; the picker with `?application=` serves `assignable` false for that reviewer
    while still LISTING them (bug #66), and ignores a case the caller cannot read;
  * TD-616 — every `delete_fields` caller (the Admins table, the person page, the Reviewers table and
    page, the Staff list) and the Mentors row say not `deletable` while the person is in a group, as
    every Delete door refuses `in_a_group`;
  * TD-630 — the Staff list's `suspended_cases` banner counts the open cases held by DELETED (archived)
    people of the listed organisation too, inside the same query (the pinned counts are unchanged).
"""
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.courses.tests.test_m1a_archive_restore import ArchiveCase, no_group
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import assignment
from apps.scholarship.services.assignment import AssignmentError
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)

PICKER = '/api/v1/admin/scholarship/assignable-admins/'
STAFF = '/api/v1/admin/staff/'
NOW = timezone.now


def _joined(role, org, **kw):
    return make_admin(role, owning_org=org, first_seen_at=NOW(), **kw)


def _holding(holder, status='interviewing'):
    app = make_application('submitted', reviewer=holder)
    ScholarshipApplication.objects.filter(pk=app.pk).update(
        status=status, owning_organisation=holder.owning_organisation)
    return app


# ── TD-627 ────────────────────────────────────────────────────────────────────────────────────────
class TD627NoOrganisationIsNoMatch(TestCase):
    def test_a_caller_of_no_organisation_hands_to_nobody(self):
        caller = _joined('org_admin', None)
        target = _joined('reviewer', None)
        self.assertIsNone(caller.owning_organisation_id)
        self.assertFalse(assignment.may_hand_to(caller, target))
        self.assertFalse(assignment.may_assign_to(caller, target))

    def test_the_same_organisation_still_matches(self):
        org = make_org()
        self.assertTrue(assignment.may_hand_to(_joined('org_admin', org), _joined('reviewer', org)))

    def test_the_service_refuses_it(self):
        caller = _joined('org_admin', None)
        target = _joined('reviewer', None)
        app = make_application('profile_complete', cohort=make_cohort(owning_organisation=None))
        with patch('apps.scholarship.services.assignment.is_ready_for_assignment', return_value=True), \
                self.assertRaises(AssignmentError) as raised:
            assignment.assign_reviewer(app, reviewer=target, by_admin=caller)
        self.assertEqual(raised.exception.code, 'not_reviewer')


# ── TD-634 ────────────────────────────────────────────────────────────────────────────────────────
@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TD634AnotherOrganisationIsSaid(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a, cls.org_b = make_org(), make_org()
        cls.cohort = make_cohort(owning_organisation=cls.org_a)
        cls.super = make_admin(super_admin=True)
        cls.lead_b = _joined('org_admin', cls.org_b)
        cls.near = _joined('reviewer', cls.org_a)
        cls.far = _joined('reviewer', cls.org_b)

    def picker(self, caller, app=None):
        r = authed_client(caller).get(PICKER, {'application': app} if app is not None else {})
        self.assertEqual(r.status_code, 200, r.content[:200])
        return {row['id']: row['assignable'] for row in r.json()['admins']}

    def test_the_assign_door_says_wrong_organisation(self):
        app = make_application('profile_complete', cohort=self.cohort)
        with patch('apps.scholarship.services.assignment.is_ready_for_assignment', return_value=True):
            r = authed_client(self.super).post(f'/api/v1/admin/scholarship/applications/{app.id}/assign/',
                                               {'reviewer_id': self.far.id}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'wrong_organisation'))
        app.refresh_from_db()
        self.assertIsNone(app.assigned_to_id)

    def test_the_picker_with_the_case_greys_the_other_organisation_and_keeps_it_listed(self):
        app = make_application('profile_complete', cohort=self.cohort)
        rows = self.picker(self.super, app.id)
        self.assertEqual((rows[self.near.id], rows[self.far.id]), (True, False))
        # Without the case the super's rule asks no organisation (the list page's bulk assign).
        rows = self.picker(self.super)
        self.assertEqual((rows[self.near.id], rows[self.far.id]), (True, True))

    def test_a_case_the_caller_cannot_read_is_ignored(self):
        app = make_application('profile_complete', cohort=self.cohort)
        self.assertEqual(self.picker(self.lead_b, app.id), self.picker(self.lead_b))
        self.assertEqual(self.picker(self.lead_b, 99999999), self.picker(self.lead_b))
        self.assertEqual(self.picker(self.lead_b, 'not-an-id'), self.picker(self.lead_b))


# ── TD-616 ────────────────────────────────────────────────────────────────────────────────────────
class TD616NotDeletableWhileInAGroup(ArchiveCase):
    def rows(self, url, key):
        r = authed_client(self.lead).get(url)
        self.assertEqual(r.status_code, 200, r.content[:200])
        return {row['id']: row for row in r.json()[key]}

    def answers(self, target, *, listed=True):
        """Every place that serves `deletable` for ``target`` (a staff row). The Staff list shows only
        people who signed in (``listed``); the other four also serve someone invited."""
        out = {
            'admins table': self.rows('/api/v1/admin/admins/', 'admins')[target.pk]['deletable'],
            'person page': authed_client(self.lead).get(
                f'/api/v1/admin/admins/{target.pk}/permissions/').json()['deletable'],
            'reviewers table': self.rows('/api/v1/admin/reviewers/', 'reviewers')[target.pk]['deletable'],
            'reviewer page': authed_client(self.lead).get(
                f'/api/v1/admin/reviewers/{target.pk}/').json()['deletable'],
        }
        if listed:
            out['staff list'] = self.rows(STAFF, 'staff')[target.pk]['deletable']
        return out

    def test_in_a_group_is_not_deletable_anywhere_and_the_door_agrees(self):
        target = _joined('reviewer', self.org)
        answers = self.answers(target)
        self.assertEqual((len(answers), set(answers.values())), (5, {False}))
        self.assertEqual(self.delete(self.lead, target).json()['code'], 'in_a_group')

    def test_out_of_every_group_is_deletable_everywhere(self):
        # "No group" makes them a member with no keys: off the Reviewers table, still on the other three.
        target = no_group(_joined('reviewer', self.org))
        self.assertEqual((self.rows('/api/v1/admin/admins/', 'admins')[target.pk]['deletable'],
                          authed_client(self.lead).get(
                              f'/api/v1/admin/admins/{target.pk}/permissions/').json()['deletable'],
                          self.rows(STAFF, 'staff')[target.pk]['deletable']), (True, True, True))

    def test_someone_who_never_signed_in_keeps_the_narrow_delete(self):
        # TD-615 (owner 19 Nov): an invitee is removed by Cancel (S1b); Delete asks them no group step.
        waiting = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(set(self.answers(waiting, listed=False).values()), {True})

    def test_the_mentors_row(self):
        login = _joined('mentor', self.org)
        mentors = self.rows('/api/v1/admin/mentors/', 'mentors')
        self.assertIs(mentors[login.mentor_id]['deletable'], False)
        r = self.delete(self.lead, login, url=f'/api/v1/admin/mentors/{login.mentor_id}/')
        self.assertEqual(r.json()['code'], 'in_a_group')
        no_group(login)
        self.assertIs(self.rows('/api/v1/admin/mentors/', 'mentors')[login.mentor_id]['deletable'], True)


# ── TD-630 ────────────────────────────────────────────────────────────────────────────────────────
class TD630ADeletedHolderIsCounted(ArchiveCase):
    def body(self, caller, **params):
        r = authed_client(caller).get(STAFF, params)
        self.assertEqual(r.status_code, 200, r.content[:200])
        return r.json()

    def archived(self, org):
        gone = _joined('reviewer', org)
        PartnerAdmin.objects.filter(pk=gone.pk).update(archived_at=NOW(), is_active=False)
        return gone

    def test_an_archived_holder_s_open_cases_are_in_the_banner(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(first_seen_at=NOW())
        gone = self.archived(self.org)
        _holding(gone, 'interviewing')
        _holding(gone, 'recommended')
        _holding(gone, 'awarded')                                    # not open (R5): not counted
        away = _joined('reviewer', self.org, is_active=False)        # suspended, listed: counted as before
        _holding(away, 'submitted')
        _holding(self.archived(make_org()), 'submitted')             # another organisation: not counted
        self.assertNotIn(gone.pk, [r['id'] for r in self.body(self.lead)['staff']])
        self.assertEqual(self.body(self.lead)['suspended_cases'], 3)

    def test_a_super_counts_every_organisation_or_the_one_asked(self):
        other = make_org()
        _holding(self.archived(self.org), 'submitted')
        _holding(self.archived(other), 'submitted')
        self.assertEqual(self.body(self.super)['suspended_cases'], 2)
        self.assertEqual(self.body(self.super, organisation=other.pk)['suspended_cases'], 1)

    def test_the_query_count_does_not_change(self):
        def count():
            with CaptureQueriesContext(connection) as ctx:
                self.body(self.lead)
            return len(ctx.captured_queries)
        _holding(_joined('reviewer', self.org), 'submitted')
        before = count()
        _holding(self.archived(self.org), 'submitted')
        self.assertEqual(count(), before)
