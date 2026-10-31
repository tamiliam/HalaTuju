"""Student maintenance S7a (2026-10-31): A MENTOR IS NOT STAFF.

The source user's test (`test_source_user_is_not_staff.py`), for the mentor role. `PartnerAdmin` holds
staff, source users and, since S7a, mentor logins (`role='mentor'`), and a mentor carries its
organisation as `owning_organisation` — so every list that reads `PartnerAdmin` rows to mean "our
staff" could pick one up. Each staff reader is driven here with a SIGNED-IN mentor planted in the same
organisation as a full team, and must leave it out; every staff write path refuses the row, none can
make one; and no seat, billing or payment-chain count moves because a mentor exists.
"""
import types
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_permissions, staff_reinvite
from apps.courses.models import PartnerAdmin
from apps.courses.views_admin import _staff_target_manageable
from apps.scholarship import bursary, payments_chain, staff_lifecycle, staff_permissions_admin
from apps.scholarship.emails import payment_mail
from apps.scholarship.services.assignment import _can_review, is_review_target, may_assign_to
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org,
)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAMentorIsInNoStaffList(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.team = [make_admin(role, owning_org=cls.org)
                    for role in ('admin', 'reviewer', 'qc', 'finance')]
        # Signed in, so a "has signed in" filter (the payments chain's) cannot hide it by luck.
        cls.user = make_admin('mentor', owning_org=cls.org, first_seen_at=timezone.now())

    def ids(self, rows, key='id'):
        return {r[key] if isinstance(r, dict) else r.pk for r in rows}

    def test_the_team_roster(self):
        for caller in (self.super, self.lead):
            body = authed_client(caller).get('/api/v1/admin/admins/').json()
            self.assertNotIn(self.user.pk, self.ids(body['admins']), caller.role)
            self.assertIn(self.team[0].pk, self.ids(body['admins']))

    def test_the_reviewers_tab_and_the_assignment_picker(self):
        for caller in (self.super, self.lead):
            client = authed_client(caller)
            reviewers = client.get('/api/v1/admin/reviewers/').json()['reviewers']
            picker = client.get('/api/v1/admin/scholarship/assignable-admins/').json()['admins']
            self.assertNotIn(self.user.pk, self.ids(reviewers), caller.role)
            self.assertNotIn(self.user.pk, self.ids(picker), caller.role)

    def test_nobody_may_hand_it_a_case(self):
        self.assertFalse(is_review_target(self.user))
        self.assertFalse(_can_review(self.user))
        self.assertFalse(may_assign_to(self.super, self.user))
        self.assertFalse(may_assign_to(self.lead, self.user))

    def test_it_holds_no_key_so_no_chain_or_list_counts_it(self):
        self.assertEqual(self.user.permission_set, ())
        for key in staff_permissions.CATALOGUE:
            self.assertNotIn(self.user, staff_permissions.holders(self.org, key), key)
        team = PartnerAdmin.objects.filter(
            staff_permissions.team_holding(staff_permissions.CATALOGUE))
        self.assertNotIn(self.user, team)

    def test_payment_chain_and_notify_recipients(self):
        run = types.SimpleNamespace(organisation_id=self.org.pk, admin_signed_email='',
                                    finance_signed_email='', org_admin_signed_email='')
        self.assertNotIn(self.user, payments_chain.eligible_approvers(run))
        self.assertNotIn(self.user, payments_chain.fallback_approvers(run))
        self.assertNotIn(self.user.email, payment_mail._instruction_cc(run))
        self.assertNotIn(self.user.email, bursary.foundation_notify_emails())

    def test_seat_and_staff_counts_do_not_move(self):
        """The organisation's staff count (the roster a seat or a bill would be read from) is the
        same with the mentor as without it."""
        roster = authed_client(self.lead).get('/api/v1/admin/admins/').json()['admins']
        before = len(roster)
        make_admin('mentor', owning_org=self.org, first_seen_at=timezone.now())
        roster = authed_client(self.lead).get('/api/v1/admin/admins/').json()['admins']
        self.assertEqual(len(roster), before)
        staff = PartnerAdmin.objects.filter(owning_organisation=self.org, is_active=True).exclude(
            role__in=PartnerAdmin.NOT_STAFF_ROLES)
        self.assertEqual(staff.count(), 1 + len(self.team))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestNoStaffPathReachesAMentor(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.user = make_admin('mentor', owning_org=cls.org)

    def test_nobody_manages_it_as_staff(self):
        self.assertFalse(_staff_target_manageable(self.super, self.user))
        self.assertFalse(_staff_target_manageable(self.lead, self.user))

    def test_every_staff_write_answers_not_found(self):
        base = f'/api/v1/admin/admins/{self.user.pk}/'
        for caller in (self.super, self.lead):
            client = authed_client(caller)
            calls = (('post', base + 'resend/', {}), ('patch', base + 'revoke/', {'action': 'revoke'}),
                     ('delete', base, {}), ('patch', base + 'role/', {'role': 'reviewer'}),
                     ('get', base + 'permissions/', None),
                     ('patch', base + 'permissions/', {'permissions': ['review']}))
            for method, url, body in calls:
                resp = getattr(client, method)(url, body, format='json')
                self.assertEqual(resp.status_code, 404, f'{caller.role} {method} {url}')
        self.user.refresh_from_db()
        self.assertEqual((self.user.role, self.user.is_active, self.user.permissions),
                         ('mentor', True, None))

    def test_no_role_switch_reaches_or_leaves_the_role(self):
        for old in staff_lifecycle.ROLE_PAIRS:
            self.assertNotEqual(staff_lifecycle.ROLE_PAIRS[old], 'mentor')
        with self.assertRaises(staff_lifecycle.RoleChangeRefused):
            staff_lifecycle.plan_role_change(self.user, 'reviewer')
        reviewer = make_admin('reviewer', owning_org=self.org)
        with self.assertRaises(staff_lifecycle.RoleChangeRefused):
            staff_lifecycle.plan_role_change(reviewer, 'mentor')

    def test_the_permission_editor_refuses_it(self):
        with self.assertRaises(staff_permissions_admin.PermissionChangeRefused):
            staff_permissions_admin.plan_change(self.user, ['review'], by=self.super)

    def test_a_deactivated_mentor_is_never_re_invited_as_staff(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertFalse(staff_reinvite.may_reuse(self.super, self.user))
        self.assertFalse(staff_reinvite.may_reuse(self.lead, self.user))

    @override_settings(SUPABASE_SERVICE_ROLE_KEY='k', SUPABASE_URL='https://example.invalid')
    def test_the_staff_invite_cannot_grant_the_role(self):
        body = {'email': 'newmentor@gmail.com', 'name': 'New Mentor', 'role': 'mentor'}
        refused = authed_client(self.lead).post('/api/v1/admin/invite/', body, format='json')
        self.assertEqual((refused.status_code, refused.json()['code']), (403, 'role_not_allowed'))
        # A super's unknown role falls back to reviewer, as it always has — never the mentor role.
        with mock.patch('apps.courses.views_staff.send_partner_welcome_email', return_value=True):
            made = authed_client(self.super).post('/api/v1/admin/invite/', body, format='json')
        self.assertEqual(made.status_code, 201, made.content)
        row = PartnerAdmin.objects.get(email='newmentor@gmail.com')
        self.assertEqual((row.role, row.mentor_id), ('reviewer', None))

    def test_the_staff_letter_refuses_a_mentor(self):
        from apps.scholarship import emails
        with self.assertRaises(ValueError):
            emails.send_partner_welcome_email('m@example.test', 'M', 'mentor')

    def test_the_database_holds_the_binding(self):
        from django.core.exceptions import ValidationError
        from django.db import IntegrityError, transaction
        # A mentor login with no mentor, or a staff row with one, is refused by `save` …
        with self.assertRaises(ValidationError):
            PartnerAdmin(email='a@example.test', name='A', role='mentor',
                         owning_organisation=self.org).save()
        with self.assertRaises(ValidationError):
            PartnerAdmin(email='b@example.test', name='B', role='reviewer',
                         owning_organisation=self.org, mentor=self.user.mentor).save()
        # … another organisation's mentor too …
        with self.assertRaises(ValidationError):
            PartnerAdmin(email='c@example.test', name='C', role='mentor',
                         owning_organisation=make_org(), mentor=self.user.mentor).save()
        # … and by the database check, which an `.update()` cannot step round.
        with self.assertRaises(IntegrityError), transaction.atomic():
            PartnerAdmin.objects.filter(pk=self.user.pk).update(role='reviewer')
