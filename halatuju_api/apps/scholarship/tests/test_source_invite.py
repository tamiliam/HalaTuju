"""Source sign-in S2 (2026-10-30): inviting a source's person, and every door S2 opens or closes.

Roadmap `docs/plans/2026-10-30-source-sign-in-roadmap.md`, Doors list. Covered here, each driven
through the real endpoints:

- BECOME a source user: invite for an existing source / a NEW source (the old Add source's rules),
  the three account branches (temp password, Google, already registered), resend, re-invite after a
  revoke (same source → back; another source → refused), first sign-in closing the invitation,
  set-password opted in, the temp-password expiry job still sweeping a source user;
- CHANGE ROLE: a staff invite of a source user's address never turns it into staff;
- LOSE ACCESS: cancel, revoke, the source switched off;
- the Sources API: Add retired (410), Edit locked once joined (409), `sign_in` / `user_count`;
- who may act: super and org_admin only; another organisation's source or user is 404.
"""
import datetime
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import invitations, source_access
from apps.scholarship.models import Invitation, ReferralSource
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_source,
)

INVITE = '/api/v1/admin/invitations/'
SOURCES = '/api/v1/admin/scholarship/sources/'
NEW_LOGIN = 'apps.courses.staff_reinvite._new_login'
ISSUE = 'apps.courses.supabase_admin.issue_temp_password'
KILL = 'apps.courses.supabase_admin.kill_temp_password'

SUPABASE = dict(SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, **SUPABASE)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org(name='BrightPath Test')
        cls.other_org = make_org(name='Other Tenant')
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.other_lead = make_admin('org_admin', owning_org=cls.other_org)
        cls.source = make_source(organisation=cls.org, code='smc', name='Sri Murugan Centre')
        cls.other_source = make_source(organisation=cls.other_org, code='far', name='Far Away')

    def invite(self, caller=None, url=INVITE, new_login=('uid-new', False, None), **body):
        body.setdefault('audience', 'source_partner')
        body.setdefault('name', 'Devi')
        body.setdefault('email', 'devi@smc.example.org')
        if 'source_name' not in body:
            body.setdefault('source_id', self.source.pk)
        with patch(NEW_LOGIN, return_value=new_login) as made:
            r = authed_client(caller or self.lead).post(url, body, format='json')
        self.new_login = made
        return r

    def user(self, email='devi@smc.example.org'):
        return PartnerAdmin.objects.get(email=email)

    def sign_in(self, user):
        """The first sign-in as the console makes it: GET admin/role/ with the user's own token."""
        return authed_client(user).get('/api/v1/admin/role/')


class TestInviteForAnExistingSource(_Base):
    def test_an_org_admin_invites_and_a_source_user_is_made(self):
        r = self.invite()
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        user = self.user()
        self.assertEqual((user.role, user.source_id, user.owning_organisation_id, user.is_active),
                         ('source_partner', self.source.pk, self.org.pk, True))
        self.assertEqual(user.supabase_user_id, 'uid-new')
        self.assertFalse(user.is_super_admin)
        inv = Invitation.objects.get(pk=body['id'])
        self.assertEqual((inv.audience, inv.role, inv.organisation_id, inv.referral_source_id,
                          inv.partner_admin_id, inv.credential_issued, inv.send_count),
                         ('source_partner', 'source_partner', self.org.pk, self.source.pk,
                          user.pk, True, 1))
        self.assertEqual(body['admin_id'], user.pk)
        self.assertEqual((body['emailed'], body['google'], body['already_registered'],
                          body['reactivated']), (True, False, False, False))
        self.assertEqual((body['source']['sign_in'], body['source']['user_count']), ('invited', 1))

    def test_the_source_letter_goes_with_a_temporary_password(self):
        self.invite()
        letter = mail.outbox[-1]
        self.assertEqual(letter.to, ['devi@smc.example.org'])
        self.assertIn('Sri Murugan Centre', letter.subject)
        self.assertIn('Dear Devi', letter.body)
        self.assertIn('/admin/login', letter.body)
        self.assertIn('temporary password', letter.body)

    def test_a_blank_contact_email_is_filled_with_the_invitee(self):
        self.invite()
        self.source.refresh_from_db()
        self.assertEqual(self.source.contact_email, 'devi@smc.example.org')

    def test_a_contact_email_already_on_file_is_never_overwritten(self):
        ReferralSource.objects.filter(pk=self.source.pk).update(contact_email='office@smc.org')
        self.invite()
        self.source.refresh_from_db()
        self.assertEqual(self.source.contact_email, 'office@smc.org')

    def test_a_google_address_is_issued_no_password(self):
        r = self.invite(email='devi@gmail.com')
        self.assertEqual(r.status_code, 201, r.content)
        self.new_login.assert_not_called()
        self.assertTrue(r.json()['google'])
        inv = Invitation.objects.get(pk=r.json()['id'])
        self.assertFalse(inv.credential_issued)
        self.assertIsNone(self.user('devi@gmail.com').supabase_user_id)
        self.assertIn('Sign in with Google', mail.outbox[-1].body)

    def test_an_address_that_already_has_a_login_keeps_it(self):
        r = self.invite(new_login=(None, True, None))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['already_registered'])
        self.assertFalse(Invitation.objects.get(pk=r.json()['id']).credential_issued)
        self.assertIn('You already have a HalaTuju account', mail.outbox[-1].body)

    def test_several_people_may_sign_in_for_one_source(self):
        self.invite()
        r = self.invite(email='ravi@smc.example.org', name='Ravi', new_login=('uid-2', False, None))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['source']['user_count'], 2)

    def test_a_super_invites_for_any_organisations_source(self):
        r = self.invite(self.super, source_id=self.other_source.pk)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.user().owning_organisation_id, self.other_org.pk)


class TestInviteForANewSource(_Base):
    def new(self, caller=None, url=INVITE, **extra):
        return self.invite(caller, url=url, source_name='Kovil Seva', source_code=' KOVIL ',
                           **extra)

    def test_it_creates_the_source_in_the_callers_organisation(self):
        r = self.new(phone='012-3456789', contact_person='Mr Raj')
        self.assertEqual(r.status_code, 201, r.content)
        src = ReferralSource.objects.get(organisation=self.org, code='kovil')
        self.assertEqual((src.name, src.phone, src.contact_person, src.contact_email,
                          src.show_in_apply, src.is_active),
                         ('Kovil Seva', '012-3456789', 'Mr Raj', 'devi@smc.example.org', False, True))
        self.assertEqual(src.gift_links.count(), 0)     # a new source joins no gift
        self.assertEqual(self.user().source_id, src.pk)
        self.assertEqual(r.json()['source']['code'], 'kovil')

    def test_a_super_names_the_organisation_with_the_crumb(self):
        r = self.new(self.super, url=f'{INVITE}?org={self.other_org.code}')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(ReferralSource.objects.filter(organisation=self.other_org,
                                                      code='kovil').exists())

    def test_the_old_add_source_rules_still_apply(self):
        for code, expected in (('other', 'code_reserved'), ('halatuju', 'code_reserved'),
                               ('brightpath', 'code_reserved'), ('smc', 'code_taken'),
                               ('', 'code_and_name_required')):
            with self.subTest(code=code):
                r = self.invite(source_name='X', source_code=code)
                self.assertEqual((r.status_code, r.json()['code']), (400, expected))
        r = self.invite(source_name='', source_code='fresh')
        self.assertEqual(r.json()['code'], 'code_and_name_required')
        self.assertFalse(PartnerAdmin.objects.filter(role='source_partner').exists())

    def test_another_organisations_code_is_not_a_clash(self):
        r = self.invite(source_name='Far', source_code='far')
        self.assertEqual(r.status_code, 201, r.content)

    def test_a_refused_invite_leaves_no_source_behind(self):
        make_admin('reviewer', owning_org=self.org, email='devi@smc.example.org')
        self.assertEqual(self.new().status_code, 409)
        r = self.new(email='new@smc.example.org', new_login=(None, False, 'create_failed'))
        self.assertEqual((r.status_code, r.json()['code']), (502, 'create_failed'))
        self.assertFalse(ReferralSource.objects.filter(code='kovil').exists())


class TestInviteRefusals(_Base):
    def test_an_address_with_any_staff_row_is_refused(self):
        rows = [
            make_admin('reviewer', owning_org=self.org, email='rev@x.org'),
            make_admin('reviewer', owning_org=self.org, email='gone@x.org', is_active=False),
            make_admin('partner', email='ref@x.org'),
            make_admin('admin', owning_org=self.other_org, email='far@x.org'),
            make_admin('source_partner', owning_org=self.org, source=self.source, email='on@x.org'),
        ]
        for row in rows:
            with self.subTest(role=row.role, active=row.is_active):
                before = (row.role, row.source_id, row.is_active, row.owning_organisation_id)
                r = self.invite(email=row.email.upper())
                self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'))
                row.refresh_from_db()
                self.assertEqual((row.role, row.source_id, row.is_active,
                                  row.owning_organisation_id), before)

    def test_a_revoked_user_of_ANOTHER_source_is_refused(self):
        second = make_source(organisation=self.org)
        make_admin('source_partner', owning_org=self.org, source=second, email='devi@smc.example.org',
                   is_active=False, first_seen_at=timezone.now())
        r = self.invite()
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'))
        self.assertEqual(self.user().source_id, second.pk)

    def test_another_organisations_source_is_404(self):
        r = self.invite(source_id=self.other_source.pk)
        self.assertEqual((r.status_code, r.json()['code']), (404, 'not_found'))
        self.assertEqual(self.invite(source_id='nonsense').status_code, 404)

    def test_a_switched_off_source_is_refused(self):
        off = make_source(organisation=self.org, is_active=False)
        r = self.invite(source_id=off.pk)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'source_inactive'))

    def test_only_a_super_or_an_organisation_admin_may_invite(self):
        for role in ('admin', 'finance', 'reviewer', 'qc'):
            with self.subTest(role=role):
                r = self.invite(make_admin(role, owning_org=self.org))
                self.assertEqual(r.status_code, 403)
        user = make_admin('source_partner', owning_org=self.org, source=self.source)
        self.assertEqual(self.invite(user).status_code, 403)
        self.assertFalse(PartnerAdmin.objects.filter(email='devi@smc.example.org').exists())

    def test_bad_input(self):
        self.assertEqual(self.invite(email='nope').json()['code'], 'bad_email')
        self.assertEqual(self.invite(name='  ').json()['code'], 'name_required')

    @override_settings(SUPABASE_URL='')
    def test_nothing_is_written_without_the_login_side(self):
        r = self.invite()
        self.assertEqual(r.status_code, 500)
        self.assertFalse(PartnerAdmin.objects.filter(email='devi@smc.example.org').exists())


class TestTheSourceTab(_Base):
    def test_waiting_invitations_roster_and_choices_fenced_to_the_organisation(self):
        self.invite()
        self.invite(self.super, email='far@far.example.org', source_id=self.other_source.pk,
                    new_login=('uid-far', False, None))
        body = authed_client(self.lead).get(f'{INVITE}?kind=source').json()
        self.assertEqual([i['email'] for i in body['invitations']], ['devi@smc.example.org'])
        row = body['invitations'][0]
        self.assertEqual((row['source_id'], row['source_name'], row['source_code'], row['role']),
                         (self.source.pk, 'Sri Murugan Centre', 'smc', 'source_partner'))
        self.assertEqual(body['waiting']['source'], 1)
        self.assertEqual(body['invitable_roles'], ['source_partner'])
        self.assertEqual([u['email'] for u in body['source_users']], ['devi@smc.example.org'])
        u = body['source_users'][0]
        self.assertEqual((u['source_name'], u['is_active'], u['first_seen_at'], u['manageable']),
                         ('Sri Murugan Centre', True, None, True))
        self.assertEqual(u['invitation']['status'], 'invited')
        self.assertEqual([s['code'] for s in body['sources']], ['smc'])
        # A super sees every organisation's.
        body = authed_client(self.super).get(f'{INVITE}?kind=source').json()
        self.assertEqual(len(body['source_users']), 2)

    def test_an_admin_may_read_the_tab_and_act_on_nothing(self):
        self.invite()
        admin = make_admin('admin', owning_org=self.org)
        body = authed_client(admin).get(f'{INVITE}?kind=source').json()
        self.assertFalse(body['source_users'][0]['manageable'])

    def test_a_source_invitation_is_not_listed_under_staff_kinds(self):
        self.invite()
        for kind in ('admins', 'reviewers', 'sponsors'):
            body = authed_client(self.lead).get(f'{INVITE}?kind={kind}').json()
            self.assertNotIn('devi@smc.example.org', [i['email'] for i in body['invitations']])
            self.assertNotIn('source_users', body)


class TestFirstSignIn(_Base):
    def test_the_first_sign_in_closes_the_invitation(self):
        inv_id = self.invite().json()['id']
        user = self.user()
        r = self.sign_in(user)
        self.assertEqual((r.status_code, r.json()['role'], r.json()['source_id']),
                         (200, 'source_partner', self.source.pk))
        inv = Invitation.objects.get(pk=inv_id)
        self.assertEqual(invitations.status_of(inv), invitations.ACCEPTED)
        body = authed_client(self.lead).get(f'{INVITE}?kind=source').json()
        self.assertEqual(body['invitations'], [])
        self.assertEqual(body['waiting']['source'], 0)
        rows = authed_client(self.lead).get(SOURCES).json()['sources']
        self.assertEqual({r['code']: r['sign_in'] for r in rows}['smc'], 'joined')

    def test_a_dead_invitation_of_a_source_user_is_never_scrubbed(self):
        inv = Invitation.objects.get(pk=self.invite().json()['id'])
        Invitation.objects.filter(pk=inv.pk).update(
            expires_at=timezone.now() - datetime.timedelta(days=400))
        invitations.purge_expired()
        inv.refresh_from_db()
        self.assertEqual((inv.email, inv.name, inv.pii_purged_at), ('devi@smc.example.org', 'Devi', None))

    def test_a_temp_password_source_user_may_set_their_password(self):
        self.invite()
        user = self.user()
        account = {'app_metadata': {'must_change_password': True, 'temp_password_issued_at': 'x'}}
        with patch('apps.courses.views_admin.http_requests.get') as g, \
                patch('apps.courses.views_admin.http_requests.put') as p:
            g.return_value = MagicMock(status_code=200, json=lambda: account)
            p.return_value = MagicMock(status_code=200, text='ok')
            r = authed_client(user).post('/api/v1/admin/set-password/', {'password': 'a-long-one'},
                                         format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('/admin/users/uid-new', p.call_args[0][0])   # their OWN login only
        # …and the same row is still denied a GET of anything not opted in.
        self.assertEqual(authed_client(user).get('/api/v1/admin/admins/').status_code, 403)

    def test_the_expiry_job_still_sweeps_a_source_users_temp_password(self):
        self.invite()
        stale = (timezone.now() - datetime.timedelta(days=30)).isoformat()
        mod = 'apps.courses.management.commands.expire_temp_passwords.http_requests'
        account = {'app_metadata': {'must_change_password': True, 'temp_password_issued_at': stale}}
        with patch(f'{mod}.get') as g, patch(f'{mod}.put') as p:
            g.return_value = MagicMock(status_code=200, json=lambda: account)
            p.return_value = MagicMock(status_code=200, text='ok')
            call_command('expire_temp_passwords', stdout=MagicMock())
        rotated = [c[0][0] for c in p.call_args_list]
        self.assertTrue(any(url.endswith('/admin/users/uid-new') for url in rotated), rotated)


class TestResendCancelRevoke(_Base):
    def setUp(self):
        self.inv_id = self.invite().json()['id']
        self.user_row = self.user()

    def post(self, caller, verb, user=None):
        user = user or self.user_row
        client = authed_client(caller)
        with patch(ISSUE, return_value=True) as issued, patch(KILL, return_value='killed') as kill:
            if verb == 'resend':
                r = client.post(f'/api/v1/admin/source-users/{user.pk}/resend/', {}, format='json')
            else:
                r = client.post(f'/api/v1/admin/source-users/{user.pk}/revoke/', {}, format='json')
        self.issued, self.kill = issued, kill
        return r

    def test_resend_rotates_the_password_and_refreshes_the_same_invitation(self):
        r = self.post(self.lead, 'resend')
        self.assertEqual((r.status_code, r.json()['emailed']), (200, True), r.content)
        self.issued.assert_called_once()
        inv = Invitation.objects.get(pk=self.inv_id)
        self.assertEqual((inv.send_count, inv.credential_issued), (2, True))
        self.assertEqual(Invitation.objects.filter(audience='source_partner').count(), 1)
        self.assertIn('Sri Murugan Centre', mail.outbox[-1].subject)

    def test_resend_refusals(self):
        self.assertEqual(self.post(self.other_lead, 'resend').status_code, 404)
        self.assertEqual(self.post(make_admin('admin', owning_org=self.org), 'resend').status_code,
                         403)
        # The STAFF endpoints still refuse a source user (S1), so there is one door, not two.
        r = authed_client(self.lead).post(f'/api/v1/admin/admins/{self.user_row.pk}/resend/', {})
        self.assertEqual(r.status_code, 404)
        self.sign_in(self.user_row)
        r = self.post(self.lead, 'resend')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'already_joined'))
        self.issued.assert_not_called()

    def test_cancel_withdraws_the_invitation_and_switches_the_account_off(self):
        url = f'{INVITE}{self.inv_id}/cancel/'
        self.assertEqual(authed_client(self.other_lead).post(url).status_code, 404)
        self.assertEqual(authed_client(make_admin('finance', owning_org=self.org)).post(url)
                         .status_code, 403)
        with patch(KILL, return_value='killed') as kill:
            r = authed_client(self.lead).post(url)
        self.assertEqual((r.status_code, r.json()['status']), (200, 'revoked'), r.content)
        kill.assert_called_once_with('uid-new')
        self.user_row.refresh_from_db()
        self.assertFalse(self.user_row.is_active)
        self.assertEqual(self.sign_in(self.user_row).json()['is_admin'], False)

    def test_revoke_takes_everything_away(self):
        self.sign_in(self.user_row)
        self.assertEqual(self.post(self.other_lead, 'revoke').status_code, 404)
        r = self.post(self.lead, 'revoke')
        self.assertEqual((r.status_code, r.json()['is_active']), (200, False), r.content)
        self.user_row.refresh_from_db()
        self.assertFalse(self.user_row.is_active)
        self.assertIsNone(source_access.source_of(self.user_row))
        self.assertFalse(source_access.applications_for(self.user_row).exists())
        self.assertFalse(self.sign_in(self.user_row).json()['is_admin'])
        self.assertEqual(self.post(self.lead, 'revoke').json()['code'], 'not_active')
        # …and the Sources page sees nobody signed in for it any more.
        rows = authed_client(self.lead).get(SOURCES).json()['sources']
        self.assertEqual({r['code']: r['sign_in'] for r in rows}['smc'], 'none')

    def test_revoking_somebody_still_waiting_withdraws_their_invitation(self):
        r = self.post(self.lead, 'revoke')
        self.assertEqual(r.status_code, 200)
        self.kill.assert_called_once_with('uid-new')
        inv = Invitation.objects.get(pk=self.inv_id)
        self.assertEqual(invitations.status_of(inv), invitations.REVOKED)

    def test_the_staff_revoke_still_refuses_a_source_user(self):
        r = authed_client(self.lead).patch(f'/api/v1/admin/admins/{self.user_row.pk}/revoke/',
                                           {'action': 'revoke'}, format='json')
        self.assertEqual(r.status_code, 404)


class TestReInviteAfterRevoke(_Base):
    def setUp(self):
        self.invite()
        self.user_row = self.user()

    def revoke(self):
        with patch(KILL, return_value='killed'):
            authed_client(self.lead).post(f'/api/v1/admin/source-users/{self.user_row.pk}/revoke/')

    def test_a_signed_in_user_of_the_same_source_comes_back_without_a_new_password(self):
        self.sign_in(self.user_row)
        self.revoke()
        with patch(ISSUE) as issued:
            r = self.invite(name='Devi R')
        self.assertEqual(r.status_code, 201, r.content)
        issued.assert_not_called()
        self.new_login.assert_not_called()
        body = r.json()
        self.assertEqual((body['reactivated'], body['admin_id']), (True, self.user_row.pk))
        self.user_row.refresh_from_db()
        self.assertEqual((self.user_row.is_active, self.user_row.name, self.user_row.role),
                         (True, 'Devi R', 'source_partner'))
        # Nothing left waiting: there is no first sign-in left to close it.
        inv = Invitation.objects.get(pk=body['id'])
        self.assertEqual(invitations.status_of(inv), invitations.ACCEPTED)
        self.assertIn('You already have a HalaTuju account', mail.outbox[-1].body)
        self.assertTrue(self.sign_in(self.user_row).json()['is_admin'])

    def test_a_cancelled_invitee_is_brought_back_with_a_fresh_password(self):
        PartnerAdmin.objects.filter(pk=self.user_row.pk).update(supabase_user_id=None)
        self.revoke()
        r = self.invite(new_login=('uid-fresh', False, None))
        self.assertEqual(r.status_code, 201, r.content)
        self.new_login.assert_called_once()
        self.user_row.refresh_from_db()
        self.assertEqual((self.user_row.is_active, self.user_row.supabase_user_id),
                         (True, 'uid-fresh'))
        self.assertEqual(PartnerAdmin.objects.filter(email='devi@smc.example.org').count(), 1)
        inv = Invitation.objects.get(pk=r.json()['id'])
        self.assertEqual((invitations.status_of(inv), inv.credential_issued),
                         (invitations.INVITED, True))

    def test_another_source_may_not_take_the_revoked_user(self):
        self.revoke()
        second = make_source(organisation=self.org)
        r = self.invite(source_id=second.pk)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'))
        self.user_row.refresh_from_db()
        self.assertEqual((self.user_row.source_id, self.user_row.is_active),
                         (self.source.pk, False))

    def test_a_staff_invite_never_turns_a_source_user_into_staff(self):
        self.revoke()
        for caller in (self.super, self.lead):
            with self.subTest(caller=caller.role), patch(NEW_LOGIN, return_value=('u', False, None)):
                r = authed_client(caller).post('/api/v1/admin/invite/', {
                    'email': 'devi@smc.example.org', 'name': 'Devi', 'role': 'reviewer'},
                    format='json')
            self.assertEqual(r.status_code, 409, r.content)
        self.user_row.refresh_from_db()
        self.assertEqual((self.user_row.role, self.user_row.source_id, self.user_row.is_active),
                         ('source_partner', self.source.pk, False))


class TestSourceSwitchedOff(_Base):
    def test_its_users_see_nothing_and_it_cannot_be_invited_for(self):
        self.invite()
        user = self.user()
        self.sign_in(user)
        self.assertIsNotNone(source_access.source_of(user))
        r = authed_client(self.lead).patch(f'{SOURCES}{self.source.pk}/', {'is_active': False},
                                           format='json')
        self.assertEqual(r.status_code, 200, r.content)    # switching off stays the org's
        user.refresh_from_db()
        self.assertIsNone(source_access.source_of(user))
        r = self.invite(email='late@smc.example.org')
        self.assertEqual(r.json()['code'], 'source_inactive')


class TestTheSourcesApi(_Base):
    def test_add_source_is_retired_into_the_invite(self):
        r = authed_client(self.lead).post(SOURCES, {'code': 'new', 'name': 'New'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (410, 'use_source_invitation'))
        self.assertFalse(ReferralSource.objects.filter(code='new').exists())
        r = authed_client(make_admin('reviewer', owning_org=self.org)).post(
            SOURCES, {'code': 'new', 'name': 'New'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_the_list_says_who_signs_in(self):
        rows = {r['code']: r for r in authed_client(self.lead).get(SOURCES).json()['sources']}
        self.assertEqual((rows['smc']['sign_in'], rows['smc']['user_count']), ('none', 0))
        self.invite()
        rows = {r['code']: r for r in authed_client(self.lead).get(SOURCES).json()['sources']}
        self.assertEqual((rows['smc']['sign_in'], rows['smc']['user_count']), ('invited', 1))

    def test_edit_locks_once_the_source_has_signed_in(self):
        url = f'{SOURCES}{self.source.pk}/'
        client = authed_client(self.lead)
        self.assertEqual(client.patch(url, {'phone': '011'}, format='json').status_code, 200)
        self.invite()
        # Invited, not yet signed in: still the organisation's to edit.
        self.assertEqual(client.patch(url, {'phone': '012'}, format='json').status_code, 200)
        self.sign_in(self.user())
        self.source.refresh_from_db()
        for field in ('name', 'contact_person', 'contact_email', 'phone'):
            with self.subTest(field=field):
                r = client.patch(url, {field: 'changed@x.org'}, format='json')
                self.assertEqual((r.status_code, r.json()['code'], r.json()['fields']),
                                 (409, 'managed_by_source', [field]))
        # The Active toggles stay the organisation's, and re-sending the same values is not a change.
        r = client.patch(url, {'show_in_apply': False, 'name': self.source.name,
                               'phone': self.source.phone}, format='json')
        self.assertEqual((r.status_code, r.json()['show_in_apply']), (200, False), r.content)
        self.source.refresh_from_db()
        self.assertEqual(self.source.phone, '012')
