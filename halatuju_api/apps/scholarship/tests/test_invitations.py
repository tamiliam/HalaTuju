"""The invitation as a record — who was asked, whether the email went, what became of it.

Before this table an invitation was a side effect of creating a `PartnerAdmin`, so three different
facts were indistinguishable on screen: an invitation nobody acted on, an invitation whose password
had lapsed, and a colleague of a year. All three read "Active".

Three claims carry the weight:

1. **`no_reply` is not `expired`, and the difference is not cosmetic.** A Google or
   already-registered invitee is never issued a password, so nothing of theirs CAN expire — they
   simply have not come. Saying "expired" sends an org_admin looking for a credential that never
   existed. `credential_issued` is what separates them, written at the one moment the branch is
   known.

2. **A re-send refreshes; it never starts a rival row.** Two open invitations to one address would
   put the same person on the screen twice with neither of them wrong.

3. **Acceptance fires exactly once**, off the first-arrival rowcount, so an invitation cannot be
   re-accepted after it was superseded or revoked.

⚠ The status tests assert fixed inputs against LITERAL expected words. A test that recomputed the
rule would agree with a broken rule — the billing-month lesson, which cost eight hours of red tests
for exactly that reason.
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import invitations
from apps.scholarship.models import Invitation


class TestWhatTheStatusSays(TestCase):
    """Fixed rows in, literal words out."""

    def _inv(self, **kw):
        kw.setdefault('audience', 'staff')
        kw.setdefault('email', 'x@example.org')
        kw.setdefault('code', f'c{timezone.now().timestamp()}{len(kw)}')
        return Invitation(**kw)

    def test_sent_and_still_in_date_is_invited(self):
        inv = self._inv(expires_at=timezone.now() + timedelta(days=3))
        self.assertEqual(invitations.status_of(inv), 'invited')

    def test_a_lapsed_password_is_EXPIRED(self):
        inv = self._inv(expires_at=timezone.now() - timedelta(days=1), credential_issued=True)
        self.assertEqual(invitations.status_of(inv), 'expired')

    def test_a_google_invitee_who_never_came_is_NO_REPLY_not_expired(self):
        # The load-bearing distinction. Nothing was issued, so nothing lapsed.
        inv = self._inv(expires_at=timezone.now() - timedelta(days=1), credential_issued=False)
        self.assertEqual(invitations.status_of(inv), 'no_reply')
        self.assertNotEqual(invitations.status_of(inv), 'expired')

    def test_accepted_beats_everything(self):
        inv = self._inv(expires_at=timezone.now() - timedelta(days=30), credential_issued=True,
                        accepted_at=timezone.now())
        self.assertEqual(invitations.status_of(inv), 'accepted')

    def test_revoked_beats_an_open_clock(self):
        inv = self._inv(expires_at=timezone.now() + timedelta(days=3),
                        revoked_at=timezone.now())
        self.assertEqual(invitations.status_of(inv), 'revoked')

    def test_only_an_unanswered_invitation_is_open(self):
        self.assertTrue(invitations.is_open(self._inv()))
        self.assertFalse(invitations.is_open(self._inv(accepted_at=timezone.now())))
        self.assertFalse(invitations.is_open(self._inv(revoked_at=timezone.now())))


class TestWritingOne(TestCase):
    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='inv', name='Invite Org')
        self.admin = PartnerAdmin.objects.create(
            supabase_user_id='inv-1', role='reviewer', is_active=True,
            name='Newcomer', email='newcomer@example.org', owning_organisation=self.org)

    def test_it_records_who_was_asked_and_as_what(self):
        inv = invitations.create_or_refresh(
            audience='staff', email='Newcomer@Example.org', name='Newcomer', role='reviewer',
            organisation=self.org, partner_admin=self.admin, credential_issued=True)
        self.assertEqual(inv.email, 'newcomer@example.org')   # normalised
        self.assertEqual(inv.role, 'reviewer')
        self.assertTrue(inv.code)
        self.assertIsNotNone(inv.expires_at)

    def test_a_RESEND_refreshes_the_same_row_and_moves_the_clock(self):
        first = invitations.create_or_refresh(
            audience='staff', email='newcomer@example.org', partner_admin=self.admin)
        was = first.expires_at
        second = invitations.create_or_refresh(
            audience='staff', email='newcomer@example.org', partner_admin=self.admin,
            now=timezone.now() + timedelta(days=2))
        self.assertEqual(first.pk, second.pk, 'a re-send must not start a rival invitation')
        self.assertGreater(second.expires_at, was)
        self.assertEqual(Invitation.objects.filter(email='newcomer@example.org').count(), 1)

    def test_the_expiry_tracks_the_temp_password_ttl_rather_than_copying_it(self):
        # A different number here would let the screen say "still valid" about a password the login
        # gate already refuses.
        with override_settings(PARTNER_TEMP_PASSWORD_TTL_DAYS=3):
            inv = invitations.create_or_refresh(
                audience='staff', email='ttl@example.org', partner_admin=self.admin)
            self.assertEqual((inv.expires_at - timezone.now()).days, 2)   # 3 days, minus rounding

    def test_a_send_is_remembered_including_a_failure(self):
        inv = invitations.create_or_refresh(
            audience='staff', email='newcomer@example.org', partner_admin=self.admin)
        invitations.record_send(inv, False, 'SMTP 550 mailbox unavailable')
        inv.refresh_from_db()
        self.assertEqual(inv.send_count, 1)
        self.assertFalse(inv.last_send_ok)
        # A bounce is usually the whole explanation for an invitation nobody acted on, so it is
        # kept verbatim rather than reduced to a flag.
        self.assertIn('550', inv.last_send_error)
        invitations.record_send(inv, True)
        inv.refresh_from_db()
        self.assertEqual(inv.send_count, 2)
        self.assertTrue(inv.last_send_ok)
        self.assertEqual(inv.last_send_error, '')

    def test_recording_a_send_can_never_raise_into_the_caller(self):
        # The email has already gone; failing the request over our own bookkeeping would be absurd.
        invitations.record_send(None, True)   # deliberately wrong type


class TestAccepting(TestCase):
    def setUp(self):
        self.admin = PartnerAdmin.objects.create(
            supabase_user_id='acc-1', role='reviewer', is_active=True,
            name='Arriving', email='arriving@example.org')
        self.inv = invitations.create_or_refresh(
            audience='staff', email='arriving@example.org', partner_admin=self.admin)

    def test_arriving_closes_the_invitation(self):
        self.assertEqual(invitations.accept_for_admin(self.admin), 1)
        self.inv.refresh_from_db()
        self.assertEqual(invitations.status_of(self.inv), 'accepted')

    def test_it_cannot_close_the_same_invitation_twice(self):
        invitations.accept_for_admin(self.admin)
        self.assertEqual(invitations.accept_for_admin(self.admin), 0)

    def test_it_never_reopens_a_revoked_invitation(self):
        invitations.revoke(self.inv)
        self.assertEqual(invitations.accept_for_admin(self.admin), 0)
        self.inv.refresh_from_db()
        self.assertEqual(invitations.status_of(self.inv), 'revoked')


class TestThePiiPurge(TestCase):
    """A sponsor or source-partner invitee consented to nothing. Staff are different."""

    def _dead(self, audience, email):
        return Invitation.objects.create(
            audience=audience, email=email, name='Somebody', code=f'k{audience}{email}',
            expires_at=timezone.now() - timedelta(days=90))

    def test_it_scrubs_a_dead_sponsor_invitation_but_keeps_the_row(self):
        inv = self._dead('sponsor', 'stranger@example.org')
        self.assertEqual(invitations.purge_expired(), 1)
        inv.refresh_from_db()
        self.assertEqual(inv.email, '')
        self.assertEqual(inv.name, '')
        self.assertIsNotNone(inv.pii_purged_at)   # the count survives, the person does not

    def test_STAFF_are_exempt(self):
        # Their address is on their own PartnerAdmin row regardless, so scrubbing here would delete
        # half a record and leave the other half.
        inv = self._dead('staff', 'colleague@example.org')
        invitations.purge_expired()
        inv.refresh_from_db()
        self.assertEqual(inv.email, 'colleague@example.org')

    def test_an_ACCEPTED_invitation_is_never_scrubbed(self):
        inv = self._dead('sponsor', 'joined@example.org')
        inv.accepted_at = timezone.now()
        inv.save(update_fields=['accepted_at'])
        invitations.purge_expired()
        inv.refresh_from_db()
        self.assertEqual(inv.email, 'joined@example.org')
