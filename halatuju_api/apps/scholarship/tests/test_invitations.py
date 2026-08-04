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


# ── the four kinds, and the endpoint behind the page ─────────────────────────────
import jwt  # noqa: E402
from django.test import override_settings  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
URL = '/api/v1/admin/invitations/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheFourKinds(TestCase):
    """The page shows ONE kind at a time, so what lands in which table is load-bearing."""

    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='k1', name='Kind Org')
        cls.other = PartnerOrganisation.objects.create(code='k2', name='Other Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='k-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='dina@k.test')

        def staff(email, role):
            pa = PartnerAdmin.objects.create(
                supabase_user_id=f'k-{email}', role=role, is_active=True,
                owning_organisation=cls.org, name=email.split('@')[0], email=email)
            return invitations.create_or_refresh(
                audience='staff', email=email, name=pa.name, role=role,
                organisation=cls.org, partner_admin=pa)

        staff('rev@k.test', 'reviewer')
        staff('qc@k.test', 'qc')
        staff('adm@k.test', 'admin')
        staff('fin@k.test', 'finance')
        # An organisation admin: LISTED under admins, never invitable here.
        staff('oa2@k.test', 'org_admin')
        Invitation.objects.create(audience='sponsor', email='donor@k.test', name='Donor',
                                  code='spon-1', organisation=cls.org)
        # Another organisation's invitation — must never appear.
        Invitation.objects.create(audience='sponsor', email='intruder@k2.test',
                                  code='spon-x', organisation=cls.other)

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("k-oa")}')

    def _get(self, kind):
        r = self.client.get(f'{URL}?kind={kind}')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_reviewers_holds_reviewer_and_qc(self):
        emails = {x['email'] for x in self._get('reviewers')['invitations']}
        self.assertEqual(emails, {'rev@k.test', 'qc@k.test'})

    def test_admins_holds_admin_finance_AND_org_admin(self):
        # An organisation admin is an admin, so they belong in the table (owner, 2026-08-03).
        emails = {x['email'] for x in self._get('admins')['invitations']}
        self.assertEqual(emails, {'adm@k.test', 'fin@k.test', 'oa2@k.test'})

    def test_org_admin_is_LISTED_but_NOT_INVITABLE_here(self):
        # ⚠ The whole distinction: appointing an organisation admin is a platform act a super
        # performs. Reading the roster as the invite list would let an org_admin appoint their own
        # successor; reading it the other way would hide them from their own table.
        payload = self._get('admins')
        self.assertIn('oa2@k.test', {x['email'] for x in payload['invitations']})
        self.assertEqual(sorted(payload['invitable_roles']), ['admin', 'finance'])

    def test_sponsors_holds_sponsor_invitations_with_no_account_behind_them(self):
        rows = self._get('sponsors')['invitations']
        self.assertEqual([x['email'] for x in rows], ['donor@k.test'])
        # A sponsor invitation creates nothing — that is the point of it.
        self.assertIsNone(rows[0]['admin_id'])

    def test_source_is_empty_today(self):
        # No Source Partner has ever been invited; the role does not exist yet.
        self.assertEqual(self._get('source')['invitations'], [])

    def test_another_organisations_invitation_is_never_visible(self):
        for kind in invitations.KINDS:
            emails = {x['email'] for x in self._get(kind)['invitations']}
            self.assertNotIn('intruder@k2.test', emails)

    def test_the_waiting_count_covers_every_kind_not_just_the_one_on_screen(self):
        # ⚠ Only one table is on screen, so an invitation waiting under an unselected kind would
        # otherwise be invisible — which is exactly what this page exists to prevent.
        waiting = self._get('reviewers')['waiting']
        self.assertEqual(waiting['reviewers'], 2)
        self.assertEqual(waiting['admins'], 3)
        self.assertEqual(waiting['sponsors'], 1)
        self.assertEqual(waiting['source'], 0)

    def test_an_accepted_invitation_stops_counting_as_waiting(self):
        pa = PartnerAdmin.objects.get(email='rev@k.test')
        invitations.accept_for_admin(pa)
        self.assertEqual(self._get('reviewers')['waiting']['reviewers'], 1)

    def test_an_unknown_kind_falls_back_rather_than_erroring(self):
        self.assertEqual(self.client.get(f'{URL}?kind=nonsense').json()['kind'], 'admins')

    def test_a_reviewer_may_not_read_it(self):
        rev = PartnerAdmin.objects.create(
            supabase_user_id='k-rv', role='reviewer', is_active=True,
            owning_organisation=self.org, name='Rev', email='plainrev@k.test')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("k-rv")}')
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertTrue(rev.pk)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestInvitingASponsor(TestCase):
    """Admin-extended sponsor invitations. ⚠ NOTHING IS SKIPPED — owner's constraint."""

    def setUp(self):
        self.org = PartnerOrganisation.objects.create(code='sp', name='Sponsor Org')
        self.oa = PartnerAdmin.objects.create(
            supabase_user_id='sp-oa', role='org_admin', is_active=True,
            owning_organisation=self.org, name='Dina', email='dina@sp.test')
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("sp-oa")}')

    def _invite(self, email='donor@example.org', **extra):
        return self.client.post(URL, {'audience': 'sponsor', 'email': email, **extra},
                                format='json')

    def test_it_creates_an_invitation_and_NO_sponsor_account(self):
        from apps.scholarship.models import Sponsor
        r = self._invite()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Invitation.objects.filter(audience='sponsor').count(), 1)
        # ⚠ The whole point: an invitation is a prompt, not a way round consent, terms or vetting.
        self.assertEqual(Sponsor.objects.count(), 0)

    def test_the_email_carries_the_ordinary_public_registration_link(self):
        from django.core import mail
        mail.outbox = []
        self._invite()
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        inv = Invitation.objects.get(audience='sponsor')
        self.assertIn(f'/sponsor?ref={inv.code}', body)
        # It must not promise them anything that has not happened.
        self.assertNotIn('approved', body.lower())

    def test_a_bounce_is_recorded_rather_than_swallowed(self):
        from unittest.mock import patch
        with patch('apps.scholarship.emails.EmailMessage.send', side_effect=RuntimeError('boom')):
            r = self._invite()
        self.assertEqual(r.status_code, 502)
        inv = Invitation.objects.get(audience='sponsor')
        self.assertFalse(inv.last_send_ok)
        self.assertIn('boom', inv.last_send_error)

    def test_registering_closes_the_invitation_but_does_NOT_approve_them(self):
        from apps.scholarship.models import Sponsor
        from apps.scholarship.views_sponsor import _close_admin_invitation
        self._invite('donor@example.org')
        sponsor = Sponsor.objects.create(
            supabase_user_id='new-sp', name='Donor', email='donor@example.org', status='pending')
        _close_admin_invitation(sponsor)
        inv = Invitation.objects.get(audience='sponsor')
        self.assertEqual(invitations.status_of(inv), 'accepted')
        self.assertEqual(inv.sponsor_id, sponsor.id)
        # ⚠ Accepted means "they registered", never "they were approved". Vetting is untouched.
        sponsor.refresh_from_db()
        self.assertEqual(sponsor.status, 'pending')

    def test_it_refuses_somebody_who_is_already_a_sponsor(self):
        from apps.scholarship.models import Sponsor
        Sponsor.objects.create(supabase_user_id='has', name='Has', email='has@example.org')
        r = self._invite('has@example.org')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'already_a_sponsor')

    def test_it_refuses_a_nonsense_address(self):
        self.assertEqual(self._invite('not-an-address').status_code, 400)

    def test_STAFF_cannot_be_invited_through_this_door(self):
        # Staff invitations provision Supabase accounts and carry passwords; that logic has one
        # home, and a second door into it is a second place for the role rules to drift.
        r = self.client.post(URL, {'audience': 'staff', 'email': 'x@y.org', 'role': 'admin'},
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'unsupported_audience')

    def test_a_plain_admin_may_not_invite_a_sponsor(self):
        PartnerAdmin.objects.create(
            supabase_user_id='sp-ad', role='admin', is_active=True,
            owning_organisation=self.org, name='Ravi', email='ravi@sp.test')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("sp-ad")}')
        self.assertEqual(self._invite().status_code, 403)


class TestTheInvitationEmailsAreEditable(TestCase):
    """Owner, 2026-08-04: the invitation emails should be properly editable.

    Two safety rules make that safe, and both are asserted here:

    1. **The access paragraph is OURS.** It carries the temporary password and takes three shapes
       prose cannot express. It is a structural block injected whole, so no edit can reword it, and
       the save guard refuses a body that has dropped it — an invitation without it is a warm letter
       containing no way to sign in, and nothing would report that.

    2. **There is no switch.** `_invite_render` never asks whether the template is enabled. A
       reviewer email that is switched off must STOP; an invitation that is switched off would mean
       "Send invite" creates the account, issues the password and tells nobody.
    """

    def setUp(self):
        from apps.scholarship.models import PartnerEmailTemplate
        self.T = PartnerEmailTemplate

    def _seed(self):
        from django.core.management import call_command
        import io as _io
        call_command('seed_partner_email_templates', stdout=_io.StringIO())

    def test_the_seed_is_byte_identical_to_what_already_sends(self):
        # Adopting live mail into a template must change nothing anybody receives. Compare the
        # built-in body against the seeded one BEFORE any editing.
        from apps.scholarship import emails
        before_subject, before_body = emails.build_partner_welcome_email(
            'x@example.org', 'Priya', 'reviewer', temp_password='Kx7m-Pq4t-Rd92')
        self._seed()
        after_subject, after_body = emails.build_partner_welcome_email(
            'x@example.org', 'Priya', 'reviewer', temp_password='Kx7m-Pq4t-Rd92')
        self.assertEqual(after_subject, before_subject)
        self.assertEqual(after_body, before_body)

    def test_an_edit_changes_the_letter_but_never_the_access_paragraph(self):
        from apps.scholarship import emails
        self._seed()
        tpl = self.T.objects.get(kind='invite_reviewer')
        tpl.body = 'Welcome aboard {name}!\n\n{login_link}\n\n{access}\n\n{team_signoff}'
        tpl.save(update_fields=['body'])
        _s, body = emails.build_partner_welcome_email(
            'x@example.org', 'Priya', 'reviewer', temp_password='Kx7m-Pq4t-Rd92')
        self.assertIn('Welcome aboard Priya!', body)          # their words
        self.assertIn('Kx7m-Pq4t-Rd92', body)                 # ⚠ ours, and still there
        self.assertIn('valid for 7 days', body)

    def test_the_access_block_adapts_to_a_GOOGLE_invitee_with_no_password(self):
        from apps.scholarship import emails
        self._seed()
        _s, body = emails.build_partner_welcome_email(
            'someone@gmail.com', 'Priya', 'reviewer', temp_password=None, google=True)
        self.assertIn('Sign in with Google', body)
        self.assertNotIn('temporary password', body)

    def test_a_template_edited_into_nonsense_falls_back_rather_than_stranding_anybody(self):
        from apps.scholarship import emails
        self._seed()
        tpl = self.T.objects.get(kind='invite_reviewer')
        # A body the renderer cannot resolve. The invitation must still go.
        tpl.body = '{this_token_does_not_exist}'
        tpl.save(update_fields=['body'])
        _s, body = emails.build_partner_welcome_email(
            'x@example.org', 'Priya', 'reviewer', temp_password='Kx7m-Pq4t-Rd92')
        self.assertIn('Kx7m-Pq4t-Rd92', body)

    def test_SWITCHING_IT_OFF_DOES_NOT_SILENCE_IT(self):
        # ⚠ The deliberate difference from every other template kind. Off would mean the account is
        # created, the password issued, and nobody told — with nothing to report the silence.
        from apps.scholarship import emails
        self._seed()
        self.T.objects.filter(kind='invite_reviewer').update(enabled=False)
        _s, body = emails.build_partner_welcome_email(
            'x@example.org', 'Priya', 'reviewer', temp_password='Kx7m-Pq4t-Rd92')
        self.assertIn('Kx7m-Pq4t-Rd92', body)
        self.assertIn('Priya', body)

    def test_the_save_guard_refuses_a_body_that_has_lost_the_access_block(self):
        from apps.scholarship import partner_comms
        missing = partner_comms.missing_required_placeholders(
            'invite_reviewer', 'A subject', 'Dear {name}, welcome. {team_signoff}')
        self.assertIn('access', missing)
        self.assertIn('login_link', missing)

    def test_the_save_guard_passes_a_body_that_keeps_it(self):
        from apps.scholarship import partner_comms
        self.assertEqual(partner_comms.missing_required_placeholders(
            'invite_reviewer', 'S', 'Hi {name} {login_link} {access} {team_signoff}'), ())

    def test_a_kind_with_no_required_tokens_is_unaffected(self):
        from apps.scholarship import partner_comms
        self.assertEqual(
            partner_comms.missing_required_placeholders('weekly_summary', 'S', 'B'), ())


class TestOneInvitationLetterPerGroup(TestCase):
    """Four kinds, one per table on the Invitations page (owner, 2026-08-04).

    The claims worth guarding are about SEPARATION — that editing one letter does not move
    another, and that a role this page never invites reads none of them. A source-shape guard
    cannot see either.
    """

    def setUp(self):
        from apps.scholarship.models import PartnerEmailTemplate
        self.T = PartnerEmailTemplate
        from django.core.management import call_command
        import io as _io
        call_command('seed_partner_email_templates', stdout=_io.StringIO())

    def _welcome(self, role):
        from apps.scholarship import emails
        return emails.build_partner_welcome_email(
            'x@example.org', 'Priya', role, temp_password='Kx7m-Pq4t-Rd92')

    def _rewrite(self, kind, marker):
        tpl = self.T.objects.get(kind=kind)
        tpl.body = marker + '\n\n{login_link}\n\n{access}\n\n{team_signoff}'
        tpl.save(update_fields=['body'])

    def test_an_admin_reads_the_admin_letter_and_a_reviewer_the_reviewer_one(self):
        self._rewrite('invite_admin', 'ADMIN WORDING')
        self._rewrite('invite_reviewer', 'REVIEWER WORDING')
        self.assertIn('ADMIN WORDING', self._welcome('admin')[1])
        self.assertIn('REVIEWER WORDING', self._welcome('reviewer')[1])

    def test_EDITING_ONE_DOES_NOT_MOVE_THE_OTHER(self):
        # The entire point of the split. Before today both roles shared one row, so this is the
        # assertion that would have failed yesterday and must never fail again.
        self._rewrite('invite_admin', 'ADMIN WORDING')
        self.assertNotIn('ADMIN WORDING', self._welcome('reviewer')[1])

    def test_the_grouping_is_READ_from_KIND_ROLES_not_hand_written_here(self):
        # ⚠ finance sits under Admins and qc under Reviewers on the page. If the email ever stops
        # reading `invitations.KIND_ROLES`, somebody is written to as one thing while listed as
        # another — so assert the two SPECIALISATIONS, which are exactly the roles a hand-written
        # map forgets.
        self._rewrite('invite_admin', 'ADMIN WORDING')
        self._rewrite('invite_reviewer', 'REVIEWER WORDING')
        self.assertIn('ADMIN WORDING', self._welcome('finance')[1])
        self.assertIn('REVIEWER WORDING', self._welcome('qc')[1])

    def test_an_organisation_admin_reads_the_admin_letter(self):
        # Listed under Admins even though appointing one is a super's act — they belong to the
        # organisation, so the organisation's wording is right for them.
        self._rewrite('invite_admin', 'ADMIN WORDING')
        self.assertIn('ADMIN WORDING', self._welcome('org_admin')[1])

    def test_A_REFERRAL_PARTNER_READS_NO_STORED_TEMPLATE(self):
        # ⚠ A platform-level account on a different product relationship (decisions.md 2026-08-03).
        # If it fell through to the admin template, an org_admin editing "the admin invitation"
        # would silently change what a platform account is told.
        self._rewrite('invite_admin', 'ADMIN WORDING')
        body = self._welcome('partner')[1]
        self.assertNotIn('ADMIN WORDING', body)
        self.assertIn('Kx7m-Pq4t-Rd92', body)          # still invited, on the built-in wording

    def test_a_super_reads_no_stored_template_either(self):
        self._rewrite('invite_admin', 'ADMIN WORDING')
        self.assertNotIn('ADMIN WORDING', self._welcome('super')[1])

    def test_the_seed_is_byte_identical_to_what_already_sends_for_both_staff_letters(self):
        # Splitting one template into two must change nothing anybody receives.
        from apps.scholarship import emails
        for role in ('admin', 'reviewer'):
            with self.subTest(role=role):
                self.T.objects.all().delete()
                before = emails.build_partner_welcome_email(
                    'x@example.org', 'Priya', role, temp_password='Kx7m-Pq4t-Rd92')
                from django.core.management import call_command
                import io as _io
                call_command('seed_partner_email_templates', stdout=_io.StringIO())
                after = emails.build_partner_welcome_email(
                    'x@example.org', 'Priya', role, temp_password='Kx7m-Pq4t-Rd92')
                self.assertEqual(after, before)


class TestTheSourceInvitationIsWrittenButNotWired(TestCase):
    """Wording agreed ahead of the Source console (owner, 2026-08-04)."""

    def setUp(self):
        from django.core.management import call_command
        import io as _io
        call_command('seed_partner_email_templates', stdout=_io.StringIO())

    def test_the_seed_is_byte_identical_to_the_builder(self):
        from apps.scholarship import emails
        from apps.scholarship.models import PartnerEmailTemplate
        stored = emails.build_source_invitation_email(
            org_name='Sri Murugan Centre', contact_person='Devi',
            login_link='https://example.org/admin/login', access='ACCESS PARAGRAPH')
        PartnerEmailTemplate.objects.filter(kind='invite_source').delete()
        builtin = emails.build_source_invitation_email(
            org_name='Sri Murugan Centre', contact_person='Devi',
            login_link='https://example.org/admin/login', access='ACCESS PARAGRAPH')
        self.assertEqual(stored, builtin)

    def test_it_carries_the_access_paragraph_and_the_link(self):
        from apps.scholarship import emails
        _s, body = emails.build_source_invitation_email(
            org_name='Sri Murugan Centre', contact_person='Devi',
            login_link='https://example.org/admin/login', access='ACCESS PARAGRAPH')
        self.assertIn('ACCESS PARAGRAPH', body)
        self.assertIn('https://example.org/admin/login', body)

    def test_the_save_guard_refuses_a_body_that_has_dropped_the_way_in(self):
        from apps.scholarship import partner_comms
        missing = partner_comms.missing_required_placeholders(
            'invite_source', 'S', 'Dear {contact_person}, hello. {team_signoff}')
        self.assertIn('access', missing)
        self.assertIn('login_link', missing)

    def test_NOTHING_SENDS_IT(self):
        # ⚠ The letter describes a console that does not exist. If a sender is ever added, this
        # test should fail and be replaced deliberately — not deleted in passing.
        from apps.scholarship import emails
        self.assertFalse(hasattr(emails, 'send_source_invitation_email'))


class TestTheSponsorInvitationIsTheORGANISATIONPitching(TestCase):
    """Owner, 2026-08-04: this letter is the organisation asking, not a peer.

    *"They are invited to become a donor of the organisation so they could sponsor deserving
    students. They do not become the sponsor of the org."*
    """

    def _pitch(self):
        from apps.scholarship import emails
        return emails.build_sponsor_invitation_email(
            org_name='BrightPath', invited_by='Suresh', code='abc123')

    def test_it_invites_them_to_become_a_DONOR_not_a_sponsor_OF_the_organisation(self):
        subject, body = self._pitch()
        self.assertIn('donor of BrightPath', body)
        self.assertIn('donor of BrightPath', subject)
        # ⚠ The exact phrasing the owner corrected. Asserted as ABSENCE because the wrong version
        # reads perfectly well and nothing else would catch its return.
        self.assertNotIn('sponsor of BrightPath', body)
        self.assertNotIn('sponsor of BrightPath', subject)

    def test_it_makes_the_case_rather_than_just_linking(self):
        # A pitch that omits the pitch is the failure mode here — it would still render, still
        # link, and still read like a competent email.
        _s, body = self._pitch()
        self.assertIn('no way to pay for it', body)
        self.assertIn('the place goes unclaimed', body)

    def test_IT_KEEPS_THE_NOMINATION_CLAUSE(self):
        # ⚠ decisions.md 2026-07-28: a sponsor NOMINATES and the programme AWARDS. Directive
        # framing would make this a conduit passing earmarked money to a named beneficiary, which
        # undercuts both reallocation and AutoSponsor. All three clauses stay together.
        _s, body = self._pitch()
        self.assertIn('who you would like your gift to help', body)
        self.assertIn('we follow your choice wherever we can', body)
        self.assertIn('final decision on each award rests with the programme', body)

    def test_it_says_registering_skips_nothing(self):
        _s, body = self._pitch()
        self.assertIn('agree to our terms', body)
        self.assertIn('the same for everybody', body)

    def test_the_pitch_passes_its_own_voice_guard(self):
        from apps.scholarship import partner_comms
        subject, body = self._pitch()
        self.assertEqual(partner_comms.banned_phrases(subject, body), ())


class TestTheDonorPitchIsGuardedAgainstATaxClaim(TestCase):
    """⚠ THE GAP THIS SPRINT CLOSED, 2026-08-04.

    The tax ban lived in `sponsor_comms`; the organisation's sponsor invitation is a
    `PartnerEmailTemplate`, so it was validated by `partner_comms`, which never banned it. The one
    surface on the platform that is explicitly a donor pitch was the one not checking for the one
    sentence that can cost the reader money. HalaTuju holds no LHDN s44(6) approval.
    """

    def test_a_tax_claim_is_refused_on_the_PARTNER_family(self):
        from apps.scholarship import partner_comms
        found = partner_comms.banned_phrases(
            'An invitation', 'Your gift is tax deductible. {link}')
        self.assertIn('tax deductible', found)

    def test_every_tax_wording_is_refused_not_just_the_common_one(self):
        from apps.scholarship import partner_comms
        for phrase in ('tax-deductible', 'tax exempt', 'tax-exempt', 'tax relief'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, partner_comms.banned_phrases('S', f'We are {phrase}.'))

    def test_urgency_copy_is_refused_too(self):
        from apps.scholarship import partner_comms
        self.assertIn('act now', partner_comms.banned_phrases('S', 'Act now to help. {link}'))

    def test_the_SPONSOR_family_still_refuses_everything_it_always_did(self):
        # The tax entries MOVED to the shared list; nothing that family refused may have been lost.
        from apps.scholarship import sponsor_comms
        self.assertIn('tax deductible', sponsor_comms.banned_phrases('S', 'tax deductible'))
        self.assertIn('your student', sponsor_comms.banned_phrases('S', 'your student'))
        self.assertIn('limited time', sponsor_comms.banned_phrases('S', 'limited time'))

    def test_the_partner_family_still_refuses_its_own_conduit_phrasings(self):
        from apps.scholarship import partner_comms
        self.assertIn('students you send',
                     partner_comms.banned_phrases('S', 'the students you send us'))

    def test_BOTH_FAMILIES_SHARE_ONE_LIST_so_they_cannot_drift_again(self):
        # The bite: point either family's list away from `UNIVERSAL_BANNED` and this fails.
        from apps.scholarship import email_templates, partner_comms, sponsor_comms
        for phrase in email_templates.UNIVERSAL_BANNED:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, partner_comms.BANNED_PHRASES)
                self.assertIn(phrase, sponsor_comms.BANNED_PHRASES)


class TestARewrittenBuiltInCanBePushedThroughSafely(TestCase):
    """⚠ THE SEED KEEPS AN EXISTING ROW — SO A REWRITTEN BUILT-IN REACHES NOBODY BY ITSELF.

    Found in production on 2026-08-04: the sponsor letter was rewritten as a donor pitch, the deploy
    went green, the seed reported success — and the OLD wording was still what would send, because
    the row already existed and "kept" is the correct default (an org_admin may have edited it).

    A blanket `--reset` is not the answer: six rows on production carry real human edits. So the
    reset is scopeable, and these tests pin both halves — the named kind IS rewritten, and every
    other row is left exactly as it was.
    """

    def setUp(self):
        from apps.scholarship.models import PartnerEmailTemplate
        self.T = PartnerEmailTemplate
        self._seed()

    def _seed(self, **kwargs):
        from django.core.management import call_command
        import io as _io
        out = _io.StringIO()
        call_command('seed_partner_email_templates', stdout=out, **kwargs)
        return out.getvalue()

    def _edit(self, kind, body):
        self.T.objects.filter(kind=kind).update(body=body, updated_by_email='owner@example.org')

    def test_a_plain_run_KEEPS_a_rewritten_builtin_out_of_production(self):
        # The defect itself, pinned. Not a bug to fix — the reason the scoped reset has to exist.
        self._edit('invite_sponsor', 'THE OLD WORDING')
        self._seed()
        self.assertEqual(self.T.objects.get(kind='invite_sponsor').body, 'THE OLD WORDING')

    def test_a_scoped_reset_rewrites_only_the_kind_it_names(self):
        self._edit('invite_sponsor', 'THE OLD WORDING')
        self._edit('weekly_summary', 'AN OWNER EDIT')
        self._seed(reset=True, kind=['invite_sponsor'])
        self.assertIn('donor of', self.T.objects.get(kind='invite_sponsor').body)
        self.assertEqual(self.T.objects.get(kind='weekly_summary').body, 'AN OWNER EDIT')

    def test_THE_ENV_SCOPE_IS_HOW_THE_CRON_DOES_IT(self):
        # ⚠ `CronRunView` calls `call_command(name, stdout=…)` and passes nothing else, so without
        # this the scoped reset would be unreachable on the deployed service — which is the only
        # place it matters.
        from django.test import override_settings
        self._edit('invite_sponsor', 'THE OLD WORDING')
        self._edit('awarded', 'AN OWNER EDIT')
        with override_settings(PARTNER_EMAIL_RESET_KINDS='invite_sponsor'):
            self._seed()
        self.assertIn('donor of', self.T.objects.get(kind='invite_sponsor').body)
        self.assertEqual(self.T.objects.get(kind='awarded').body, 'AN OWNER EDIT')

    def test_a_bare_reset_still_rewrites_everything(self):
        # Unchanged behaviour — the flag did not quietly become narrower.
        self._edit('weekly_summary', 'AN OWNER EDIT')
        self._seed(reset=True)
        self.assertNotEqual(self.T.objects.get(kind='weekly_summary').body, 'AN OWNER EDIT')

    def test_an_unknown_kind_writes_NOTHING_rather_than_silently_doing_less(self):
        # A typo'd kind on a production one-off must not read as "done" while having skipped the row
        # it was meant to fix.
        self._edit('invite_sponsor', 'THE OLD WORDING')
        out = self._seed(reset=True, kind=['invite_sponsr'])
        self.assertEqual(self.T.objects.get(kind='invite_sponsor').body, 'THE OLD WORDING')
        self.assertNotIn('reset', out)

    def test_the_run_says_out_loud_which_kinds_it_will_overwrite(self):
        out = self._seed(reset=True, kind=['invite_sponsor'])
        self.assertIn('resetting wording for: invite_sponsor', out)
