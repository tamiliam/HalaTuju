"""TD-214 (2026-10-05): an invitation sent by mistake can be cancelled from its row.

`POST admin/invitations/<id>/cancel/` sets `revoked_at` (a status — the row is never deleted), only
while nobody has answered, and the AUDIT line says who did it. What "the link stops working" means
per audience is pinned here: a sponsor invitation no longer closes on registration or files the
registrant into its gift; a staff invitation's never-used account is switched off, so the temporary
password in the letter no longer opens the console.
"""
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import invitations
from apps.scholarship.models import Invitation, Sponsor
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_programme,
)

LIST = '/api/v1/admin/invitations/'


def cancel_url(inv):
    return f'/api/v1/admin/invitations/{inv.pk}/cancel/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestCancelAnInvitation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.other = make_org()
        cls.gift = make_programme(organisation=cls.org, code='td214-gift')
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        cls.super = make_admin('super', super_admin=True)
        cls.plain_admin = make_admin('admin', owning_org=cls.org)
        cls.foreign_admin = make_admin('org_admin', owning_org=cls.other)

    def _sponsor_inv(self, email='donor@example.org', org=None):
        return invitations.create_or_refresh(
            audience='sponsor', email=email, organisation=org or self.org, invited_by=self.org_admin,
            programme=self.gift, ttl_days=60)

    def _staff_inv(self, role='reviewer'):
        account = make_admin(role, owning_org=self.org)
        inv = invitations.create_or_refresh(
            audience='staff', email=account.email, role=role, organisation=self.org,
            invited_by=self.org_admin, partner_admin=account, credential_issued=True, ttl_days=7)
        return inv, account

    def _cancel(self, who, inv):
        return authed_client(who).post(cancel_url(inv), format='json')

    # ── the happy path, both audiences ──────────────────────────────────────────
    def test_an_org_admin_cancels_a_sponsor_invitation_and_the_row_stays(self):
        inv = self._sponsor_inv()
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = self._cancel(self.org_admin, inv)
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertEqual(r.json(), {'id': inv.pk, 'status': 'revoked'})
        inv.refresh_from_db()
        self.assertIsNotNone(inv.revoked_at)            # a status, never a delete
        self.assertTrue(Invitation.objects.filter(pk=inv.pk).exists())
        line = ' '.join(logs.output)
        self.assertIn('AUDIT invitation_cancelled', line)
        self.assertIn(f'id={inv.pk}', line)
        self.assertIn(f'by={self.org_admin.email}', line)

    def test_a_cancelled_sponsor_invitation_leaves_the_waiting_list(self):
        inv = self._sponsor_inv()
        self._cancel(self.org_admin, inv)
        body = authed_client(self.org_admin).get(f'{LIST}?kind=sponsors').json()
        self.assertEqual(body['invitations'], [])
        self.assertEqual(body['waiting']['sponsors'], 0)

    def test_the_sponsor_link_no_longer_closes_or_files_into_the_gift(self):
        from apps.scholarship.sponsorship import signup_programme_for
        from apps.scholarship.views_sponsor import _close_admin_invitation
        make_programme(organisation=self.other, code='td214-second')   # two live gifts
        inv = self._sponsor_inv()
        registrant = Sponsor.objects.create(
            supabase_user_id='td214-donor', name='Donor', email=inv.email, phone='0123',
            source='friend', consent_at=timezone.now(), status='pending')
        self.assertEqual(signup_programme_for(registrant), self.gift)   # before: it files them
        self._cancel(self.org_admin, inv)
        self.assertIsNone(signup_programme_for(registrant))             # after: nothing on file
        _close_admin_invitation(registrant)
        inv.refresh_from_db()
        self.assertIsNone(inv.accepted_at)

    def test_cancelling_a_staff_invitation_switches_the_unused_account_off(self):
        inv, account = self._staff_inv()
        self.assertEqual(authed_client(account).get(LIST).status_code, 403)   # a reviewer: no
        r = self._cancel(self.org_admin, inv)
        self.assertEqual(r.status_code, 200, r.content[:200])
        account.refresh_from_db()
        self.assertFalse(account.is_active)
        inv.refresh_from_db()
        self.assertEqual(invitations.status_of(inv), 'revoked')

    def test_the_address_can_be_invited_again_afterwards(self):
        inv = self._sponsor_inv()
        self._cancel(self.org_admin, inv)
        again = self._sponsor_inv()
        self.assertNotEqual(again.pk, inv.pk)

    # ── only while unanswered ──────────────────────────────────────────────────
    def test_an_accepted_invitation_is_not_open(self):
        inv = self._sponsor_inv()
        Invitation.objects.filter(pk=inv.pk).update(accepted_at=timezone.now())
        r = self._cancel(self.org_admin, inv)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_open'))

    def test_cancelling_twice_is_not_open(self):
        inv = self._sponsor_inv()
        self.assertEqual(self._cancel(self.org_admin, inv).status_code, 200)
        self.assertEqual(self._cancel(self.org_admin, inv).json()['code'], 'not_open')

    def test_a_colleague_who_has_signed_in_is_revoked_on_people_not_here(self):
        inv, account = self._staff_inv()
        type(account).objects.filter(pk=account.pk).update(first_seen_at=timezone.now())
        r = self._cancel(self.org_admin, inv)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_open'))
        account.refresh_from_db()
        self.assertTrue(account.is_active)

    def test_an_answer_landing_between_the_read_and_the_write_wins(self):
        # Review fix (2026-10-05): the writes are conditional. The view READS an open invitation;
        # before it writes, the invitee signs in (accepted + first seen). Nothing may be written.
        from django.db.models.query import QuerySet
        inv, account = self._staff_inv()
        real_first = QuerySet.first

        def first_then_they_arrive(qs):
            row = real_first(qs)
            if isinstance(row, Invitation) and row.pk == inv.pk:
                Invitation.objects.filter(pk=inv.pk).update(accepted_at=timezone.now())
                type(account).objects.filter(pk=account.pk).update(first_seen_at=timezone.now())
            return row

        with mock.patch.object(QuerySet, 'first', first_then_they_arrive):
            r = self._cancel(self.org_admin, inv)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_open'))
        inv.refresh_from_db()
        account.refresh_from_db()
        self.assertIsNone(inv.revoked_at)
        self.assertTrue(account.is_active)

    def test_a_first_sign_in_alone_rolls_the_cancel_back(self):
        # The invitation is still open but the account has arrived: neither write survives.
        from django.db.models.query import QuerySet
        inv, account = self._staff_inv()
        real_first = QuerySet.first

        def first_then_sign_in(qs):
            row = real_first(qs)
            if isinstance(row, Invitation) and row.pk == inv.pk:
                type(account).objects.filter(pk=account.pk).update(first_seen_at=timezone.now())
            return row

        with mock.patch.object(QuerySet, 'first', first_then_sign_in):
            r = self._cancel(self.org_admin, inv)
        self.assertEqual(r.json()['code'], 'not_open')
        inv.refresh_from_db()
        account.refresh_from_db()
        self.assertIsNone(inv.revoked_at)
        self.assertTrue(account.is_active)

    # ── the fence and the role gate ────────────────────────────────────────────
    def test_an_org_admin_cannot_cancel_an_invitee_since_promoted_to_org_admin(self):
        # Review fix (2026-10-05): invited as a reviewer, promoted by a super before signing in.
        inv, account = self._staff_inv(role='reviewer')
        type(account).objects.filter(pk=account.pk).update(role='org_admin')
        self.assertEqual(self._cancel(self.org_admin, inv).status_code, 404)
        account.refresh_from_db()
        self.assertTrue(account.is_active)
        self.assertEqual(self._cancel(self.super, inv).status_code, 200)   # a super still may

    def test_another_organisations_invitation_is_404_never_403(self):
        inv = self._sponsor_inv()
        r = self._cancel(self.foreign_admin, inv)
        self.assertEqual(r.status_code, 404)
        inv.refresh_from_db()
        self.assertIsNone(inv.revoked_at)

    def test_an_org_admin_cannot_cancel_an_organisation_admin_invitation(self):
        inv, account = self._staff_inv(role='org_admin')
        self.assertEqual(self._cancel(self.org_admin, inv).status_code, 404)
        account.refresh_from_db()
        self.assertTrue(account.is_active)

    def test_a_super_may_cancel_any_organisations(self):
        inv = self._sponsor_inv(org=self.other)
        self.assertEqual(self._cancel(self.super, inv).status_code, 200)

    def test_a_plain_admin_may_look_but_not_cancel(self):
        inv = self._sponsor_inv()
        self.assertEqual(self._cancel(self.plain_admin, inv).status_code, 403)
        inv.refresh_from_db()
        self.assertIsNone(inv.revoked_at)

    def test_an_unknown_id_is_404(self):
        self.assertEqual(authed_client(self.org_admin)
                         .post('/api/v1/admin/invitations/999999/cancel/').status_code, 404)
