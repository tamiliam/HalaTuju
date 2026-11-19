"""Sprint S1b (owner, 2026-11-19; closes TD-615): Cancel invitation ARCHIVES the never-signed-in invitee.

Owner: "a person invited into a group who never accepts and never signs in is removed by Cancel invitation
alone; the system removes them from the group and cancels the invitation." So `POST
admin/invitations/<id>/cancel/` on a STAFF invitation archives the account in the same step
(`staff_archive.archive_locked`, the archive Delete uses): off the group tables and pickers, the address
free to be invited again (the re-invite restores the same row), refused 409 `has_unfinished_work` while
they hold open cases, and refused as before once they have signed in. A source invitation is NOT
archived (it would have no way back). Every Supabase call is mocked; every test drives the real doors.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import invitations
from apps.scholarship.models import Invitation, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_org,
)

READ = 'apps.courses.supabase_admin.read_auth_user'
DELETE = 'apps.courses.supabase_admin.delete_auth_user'
KILL = 'apps.courses.supabase_admin.kill_temp_password'
NEW_LOGIN = 'apps.courses.staff_reinvite._new_login'
SUPABASE = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                SUPABASE_URL='https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY='svc-key')
EMAIL = 'kavitha.s1b@example.org'
NAME = 'Kavitha Invitee'


def _unused(uid):
    """The Supabase login WE made for an invitee who never signed in (email only, password owed)."""
    login = PartnerAdmin.objects.filter(supabase_user_id=uid).first()
    return {'id': uid, 'email': login.email if login else EMAIL, 'last_sign_in_at': None,
            'identities': [{'provider': 'email'}], 'app_metadata': {'must_change_password': True}}


@override_settings(**SUPABASE)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.other = make_org()
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org, first_seen_at=timezone.now())
        cls.foreign_lead = make_admin('org_admin', owning_org=cls.other, first_seen_at=timezone.now())
        cls.colleague = make_admin('reviewer', owning_org=cls.org, first_seen_at=timezone.now())

    def invite(self, caller=None, *, email=EMAIL, role='reviewer', uid='uid-s1b-1'):
        body = {'email': email, 'name': NAME, 'role': role, 'gift_scope': 'every'}
        with patch(NEW_LOGIN, return_value=(uid, False, None)):
            r = authed_client(caller or self.lead).post('/api/v1/admin/invite/', body, format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:300])
        account = PartnerAdmin.objects.get(email__iexact=email)
        inv = Invitation.objects.filter(partner_admin=account, revoked_at__isnull=True).latest('id')
        return inv, account

    def cancel(self, caller, inv):
        with patch(READ, side_effect=_unused), patch(DELETE, return_value='deleted') as gone, \
                patch(KILL, return_value='rotated') as killed:
            r = authed_client(caller).post(f'/api/v1/admin/invitations/{inv.pk}/cancel/', {}, format='json')
        self.gone, self.killed = gone, killed
        return r

    def reviewer_ids(self):
        r = authed_client(self.lead).get('/api/v1/admin/reviewers/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        return {row['id'] for row in r.json()['reviewers']}


class TestCancelArchivesTheInvitee(_Base):
    def test_cancel_archives_a_never_signed_in_staff_invitee(self):
        inv, account = self.invite()
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = self.cancel(self.lead, inv)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r.json(), {'id': inv.pk, 'status': 'revoked', 'login': 'deleted'})
        inv.refresh_from_db()
        account.refresh_from_db()
        self.assertIsNotNone(inv.revoked_at)                       # a status, never a delete
        self.assertTrue(Invitation.objects.filter(pk=inv.pk).exists())
        self.assertIsNotNone(account.archived_at)                  # archived in the same step
        self.assertFalse(account.is_active)
        self.assertIsNone(account.supabase_user_id)                # the login link is cleared ...
        self.gone.assert_called_once_with('uid-s1b-1')             # ... and the unused login retired
        self.killed.assert_not_called()
        line = ' '.join(o for o in logs.output if 'AUDIT invitation_cancelled' in o)
        self.assertIn(f'id={inv.pk}', line)
        self.assertIn(f'account={account.pk}', line)
        self.assertIn('archived=yes', line)
        self.assertIn('login=deleted', line)

    def test_the_audit_lines_carry_ids_never_the_invitee(self):
        inv, account = self.invite()
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as cancelled, \
                self.assertLogs('apps.courses.views_admin', level='INFO') as archived:
            self.assertEqual(self.cancel(self.lead, inv).status_code, 200)
        audit = ' '.join(o for o in cancelled.output + archived.output if 'AUDIT' in o)
        self.assertIn('AUDIT invitation_cancelled', audit)
        self.assertIn(f'AUDIT staff_archived by={self.lead.email} target={account.pk}', audit)
        self.assertNotIn(EMAIL, audit)
        self.assertNotIn(NAME, audit)
        self.assertNotIn('Kavitha', audit)

    def test_the_same_address_can_be_invited_again_through_the_invite_door(self):
        inv, account = self.invite()
        self.assertEqual(self.cancel(self.lead, inv).status_code, 200)
        again, back = self.invite(uid='uid-s1b-2')
        self.assertEqual(back.pk, account.pk)                      # the same row, restored
        self.assertNotEqual(again.pk, inv.pk)
        self.assertIsNone(back.archived_at)
        self.assertTrue(back.is_active)
        self.assertIsNone(back.first_seen_at)                      # waiting on Invitations again
        self.assertEqual(back.supabase_user_id, 'uid-s1b-2')
        self.assertEqual(invitations.status_of(again), 'invited')

    def test_the_archived_invitee_leaves_the_group_table(self):
        inv, account = self.invite()
        self.assertIn(account.pk, self.reviewer_ids())             # invited into Reviewers
        self.assertEqual(self.cancel(self.lead, inv).status_code, 200)
        ids = self.reviewer_ids()
        self.assertNotIn(account.pk, ids)                          # before S1b: listed, switched off
        self.assertIn(self.colleague.pk, ids)

    def test_the_archived_invitee_is_on_no_picker(self):
        from apps.scholarship import staff_mentor, staff_tables_admin
        inv, account = self.invite()
        self.assertEqual(self.cancel(self.lead, inv).status_code, 200)
        offered = {a.pk for a, _ in staff_tables_admin.candidates(self.lead, 'admins', self.org.pk)}
        self.assertNotIn(account.pk, offered)                      # the Add sheet
        self.assertNotIn(account.pk, {a.pk for a in staff_mentor.candidates([self.org.pk])})
        r = authed_client(self.lead).post(f'/api/v1/admin/invitations/{inv.pk}/cancel/', {}, format='json')
        self.assertEqual(r.status_code, 404)                       # out of reach by id

    def test_open_cases_refuse_409_and_nothing_changes(self):
        inv, account = self.invite()
        app = make_application('submitted')
        ScholarshipApplication.objects.filter(pk=app.pk).update(assigned_to=account)
        r = self.cancel(self.lead, inv)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'has_unfinished_work'), r.content[:300])
        self.assertEqual(r.json()['work']['reviewers']['open_cases'], 1)
        inv.refresh_from_db()
        account.refresh_from_db()
        self.assertIsNone(inv.revoked_at)                          # rolled back: still open
        self.assertIsNone(account.archived_at)
        self.assertTrue(account.is_active)
        self.assertEqual(account.supabase_user_id, 'uid-s1b-1')
        self.gone.assert_not_called()
        self.killed.assert_not_called()

    def test_an_invitee_who_has_signed_in_keeps_todays_refusal(self):
        inv, account = self.invite()
        PartnerAdmin.objects.filter(pk=account.pk).update(first_seen_at=timezone.now())
        r = self.cancel(self.lead, inv)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_open'))
        inv.refresh_from_db()
        account.refresh_from_db()
        self.assertIsNone(inv.revoked_at)
        self.assertIsNone(account.archived_at)
        self.assertTrue(account.is_active)
        self.gone.assert_not_called()


class TestTheFenceHolds(_Base):
    def test_another_organisations_invitation_is_404_and_untouched(self):
        inv, account = self.invite()
        r = self.cancel(self.foreign_lead, inv)
        self.assertEqual(r.status_code, 404)
        account.refresh_from_db()
        self.assertIsNone(account.archived_at)
        self.assertTrue(account.is_active)

    def test_an_org_admin_cannot_cancel_an_org_admin_invitation(self):
        account = make_admin('org_admin', owning_org=self.org, uid='uid-s1b-oa')
        inv = invitations.create_or_refresh(
            audience='staff', email=account.email, role='org_admin', organisation=self.org,
            invited_by=self.super, partner_admin=account, credential_issued=True, ttl_days=7)
        r = self.cancel(self.lead, inv)
        self.assertEqual(r.status_code, 404)
        account.refresh_from_db()
        self.assertIsNone(account.archived_at)
        self.assertTrue(account.is_active)


class TestASourceInvitationIsNotArchived(_Base):
    def test_a_source_invitee_is_switched_off_as_before_never_archived(self):
        account = make_admin('source_partner', owning_org=self.org, uid='uid-s1b-src')
        inv = invitations.create_or_refresh(
            audience='source_partner', email=account.email, role='source_partner', organisation=self.org,
            invited_by=self.lead, partner_admin=account, credential_issued=True, ttl_days=7)
        r = self.cancel(self.super, inv)
        self.assertEqual(r.status_code, 200, r.content[:300])
        account.refresh_from_db()
        self.assertFalse(account.is_active)
        self.assertIsNone(account.archived_at)
        self.killed.assert_called_once()
        self.gone.assert_not_called()
