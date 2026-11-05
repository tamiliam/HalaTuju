"""Student maintenance S7a (2026-10-31): mentors sign in — every door that makes, changes or ends a mentor's
sign-in, the Mentors page's list and fence, and the mentor's own profile writes.

Doors, each driven through the real endpoints:

- BECOME a mentor: invite (super / org_admin; the three account branches: temp password, Google, an
  address that already has a login), resend, first sign-in closing the invitation, Reactivate of a
  mentor who never signed in (the invitation again);
- REFUSED: an address with any sign-in (409 `already_staff`); admin, finance, reviewer, a mentor;
  another organisation's mentor (404); staff editing after the first sign-in (409 `managed_by_mentor`);
- LOSE ACCESS: revoke (invited), deactivate (never a delete), and the way back, reactivate;
- WHAT A MENTOR WRITES: `mentoring_area` (mentor only, required, 120), the phone (required), "share my
  phone with students", the reviewer cards (`admin/reviewer-profile/`);
- the ONLY email a mentor is ever sent is the invitation (and its resend);
- a mentor invitation is on the Mentors page, never the Invitations page.
"""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import mentor_invite
from apps.scholarship.models import Invitation, Mentor, ReviewerProfile
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org,
)

INVITE = '/api/v1/admin/invitations/'
MENTORS = '/api/v1/admin/mentors/'
NEW_LOGIN = 'apps.courses.staff_reinvite._new_login'
ISSUE = 'apps.courses.supabase_admin.issue_temp_password'
KILL = 'apps.courses.supabase_admin.kill_temp_password'
READ = 'apps.courses.supabase_admin.read_auth_user'
DELETE = 'apps.courses.supabase_admin.delete_auth_user'

#: TD-440: a Resend reads the live login first — one nobody has used yet.
UNTOUCHED = {'id': 'x', 'last_sign_in_at': None, 'app_metadata': {}}

SUPABASE = dict(SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, **SUPABASE)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org(name='BrightPath Test')
        cls.other_org = make_org(name='Other Tenant')
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.viewer = make_admin('admin', owning_org=cls.org)
        cls.other_lead = make_admin('org_admin', owning_org=cls.other_org)

    def invite(self, caller=None, new_login=('uid-new', False, None), query='', **body):
        body.setdefault('audience', 'mentor')
        body.setdefault('name', 'Priya Devi')
        body.setdefault('email', 'priya@example.org')
        with patch(NEW_LOGIN, return_value=new_login) as made:
            r = authed_client(caller or self.lead).post(INVITE + query, body, format='json')
        self.new_login = made
        return r
        return r

    def login(self, email='priya@example.org'):
        return PartnerAdmin.objects.get(email=email)

    def act(self, mentor_id, action, caller=None):
        with patch(ISSUE, return_value=True), patch(KILL, return_value='killed'), \
                patch(READ, return_value=UNTOUCHED):
            return authed_client(caller or self.lead).post(f'{MENTORS}{mentor_id}/{action}/',
                                                           {}, format='json')

    def sign_in(self, login):
        return authed_client(login).get('/api/v1/admin/role/')


class TestInvite(_Base):
    def test_an_org_admin_invites_and_a_mentor_with_a_login_is_made(self):
        r = self.invite()
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        login = self.login()
        mentor = Mentor.objects.get(pk=body['mentor']['id'])
        self.assertEqual((login.role, login.mentor_id, login.owning_organisation_id, login.is_active,
                          login.supabase_user_id, login.is_super_admin),
                         ('mentor', mentor.pk, self.org.pk, True, 'uid-new', False))
        self.assertEqual((mentor.organisation_id, mentor.area, mentor.created_by_email),
                         (self.org.pk, '', self.lead.email))
        inv = Invitation.objects.get(pk=body['id'])
        self.assertEqual((inv.audience, inv.role, inv.organisation_id, inv.mentor_id,
                          inv.partner_admin_id, inv.credential_issued, inv.send_count),
                         ('mentor', 'mentor', self.org.pk, mentor.pk, login.pk, True, 1))
        self.assertEqual((body['mentor']['status'], body['mentor']['signed_in'], body['emailed']),
                         ('invited', False, True))

    def test_the_invite_and_its_resend_are_on_the_inviters_own_activity_list(self):
        """Common profile S3/S4: whoever pressed Invite / Resend gets an `invitation_sent` row; the
        mentor gets none for being invited."""
        from apps.scholarship.models import StaffActivity
        r = self.invite()
        self.act(r.json()['mentor']['id'], 'resend')
        rows = list(StaffActivity.objects.filter(verb='invitation_sent').order_by('id')
                    .values_list('actor_id', 'subject_type', 'meta'))
        self.assertEqual([(a, t) for a, t, _ in rows], [(self.lead.pk, 'invitation')] * 2)
        self.assertEqual([(m['audience'], m['resend']) for _, _, m in rows],
                         [('mentor', False), ('mentor', True)])
        self.assertFalse(StaffActivity.objects.filter(actor=self.login()).exists())

    def test_the_mentor_letter_is_the_only_email_and_carries_the_password(self):
        self.invite()
        self.assertEqual(len(mail.outbox), 1)
        letter = mail.outbox[0]
        self.assertEqual(letter.to, ['priya@example.org'])
        self.assertIn('mentor', letter.subject)
        self.assertIn('BrightPath Test', letter.subject)
        self.assertIn('Dear Priya Devi', letter.body)
        self.assertIn('/admin/login', letter.body)
        self.assertIn('temporary password', letter.body)

    def test_a_google_address_is_issued_no_password(self):
        r = self.invite(email='priya@gmail.com')
        self.assertEqual(r.status_code, 201, r.content)
        self.new_login.assert_not_called()
        self.assertTrue(r.json()['google'])
        self.assertIsNone(self.login('priya@gmail.com').supabase_user_id)
        self.assertFalse(Invitation.objects.get(pk=r.json()['id']).credential_issued)
        self.assertIn('Sign in with Google', mail.outbox[-1].body)

    def test_a_students_or_sponsors_login_may_be_a_mentor(self):
        """Owner ruling 2026-10-31 (replacing review fix 1): the admin side and the student/sponsor
        side are separate domains, as for staff. The address keeps its own login: no UID on the row,
        no password issued, a letter saying "sign in the way you normally do"."""
        r = self.invite(new_login=(None, True, None))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['already_registered'])
        login = self.login()
        self.assertEqual((login.role, login.supabase_user_id, login.first_seen_at), ('mentor', None, None))
        self.assertFalse(Invitation.objects.get(pk=r.json()['id']).credential_issued)
        self.assertEqual(r.json()['mentor']['status'], 'invited')
        self.assertIn('You already have a HalaTuju account', mail.outbox[-1].body)
        self.assertNotIn('temporary password', mail.outbox[-1].body)

    def test_their_own_login_is_never_reset_killed_or_deleted(self):
        """Resend, Revoke, a re-invite and an email move before they sign in: the row has no UID and
        the invitation issued no password, so nothing reaches the person's own login."""
        self.invite(new_login=(None, True, None))
        mentor = Mentor.objects.get()
        with patch(ISSUE, return_value=True) as issued, patch(KILL, return_value='killed') as killed,                 patch(DELETE, return_value='deleted') as deleted:
            for action in ('resend', 'revoke'):
                r = authed_client(self.lead).post(f'{MENTORS}{mentor.pk}/{action}/', {}, format='json')
                self.assertEqual(r.status_code, 200, (action, r.content))
            # S7b follow-up review: the way back is a re-invite on Invitations → Mentor, not Reactivate.
            self.assertEqual(self.invite(new_login=(None, True, None)).status_code, 201)
            with patch(NEW_LOGIN, return_value=(None, True, None)):
                r = authed_client(self.lead).patch(f'{MENTORS}{mentor.pk}/', {'email': 'other@example.org'},
                                                   format='json')
            self.assertEqual(r.status_code, 200, r.content)
        issued.assert_not_called()
        killed.assert_not_called()
        deleted.assert_not_called()
        login = self.login('other@example.org')
        self.assertEqual((login.supabase_user_id, login.mentor_id), (None, mentor.pk))
        self.assertIn('You already have a HalaTuju account', mail.outbox[-1].body)

    def test_any_existing_sign_in_is_refused(self):
        for email in (self.viewer.email, self.lead.email.upper()):
            r = self.invite(email=email)
            self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'), email)
        self.invite()
        again = self.invite(name='Someone Else')
        self.assertEqual((again.status_code, again.json()['code']), (409, 'already_staff'))
        self.assertEqual(Mentor.objects.count(), 1)

    def test_a_failed_login_leaves_nothing_behind(self):
        r = self.invite(new_login=(None, False, 'create_failed'))
        self.assertEqual((r.status_code, r.json()['code']), (502, 'create_failed'))
        self.assertFalse(Mentor.objects.exists())
        self.assertFalse(PartnerAdmin.objects.filter(role='mentor').exists())
        self.assertFalse(Invitation.objects.filter(audience='mentor').exists())
        self.assertEqual(mail.outbox, [])

    def test_bad_input_is_400(self):
        for body, code in (({'email': 'nope'}, 'bad_email'), ({'name': ' '}, 'name_required'),
                           ({'name': ['x']}, 'bad_request')):
            r = self.invite(**body)
            self.assertEqual((r.status_code, r.json()['code']), (400, code), body)

    def test_only_super_and_org_admin_invite(self):
        for role in ('admin', 'finance', 'reviewer', 'qc'):
            r = self.invite(caller=make_admin(role, owning_org=self.org))
            self.assertEqual(r.status_code, 403, role)
        self.assertFalse(Mentor.objects.exists())

    def test_a_super_names_the_organisation(self):
        r = self.invite(caller=self.super, query=f'?org={self.other_org.code}')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Mentor.objects.get().organisation_id, self.other_org.pk)
        # An org admin's ?org= naming another organisation never widens: the mentor is its own.
        r = self.invite(email='b@example.org', query=f'?org={self.other_org.code}',
                        new_login=('uid-2', False, None))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Mentor.objects.get(pk=r.json()['mentor']['id']).organisation_id, self.org.pk)
        # A super naming an organisation that does not exist: 404.
        r = self.invite(caller=self.super, email='c@example.org', query='?org=nope')
        self.assertEqual(r.status_code, 404)


class TestTheMentorsPage(_Base):
    def setUp(self):
        self.invite()
        self.mentor = Mentor.objects.get()
        self.mine = self.login()

    def test_super_org_admin_and_admin_read_it_and_only_two_may_invite(self):
        for caller, can in ((self.super, True), (self.lead, True), (self.viewer, False)):
            body = authed_client(caller).get(MENTORS).json()
            self.assertEqual([m['id'] for m in body['mentors']], [self.mentor.pk], caller.role)
            self.assertEqual(body['can_invite'], can)
            self.assertEqual(body['mentors'][0]['manageable'], can)
        for role in ('finance', 'reviewer', 'qc'):
            r = authed_client(make_admin(role, owning_org=self.org)).get(MENTORS)
            self.assertEqual(r.status_code, 403, role)

    def test_another_organisation_sees_none_and_cannot_act(self):
        self.assertEqual(authed_client(self.other_lead).get(MENTORS).json()['mentors'], [])
        for action in ('resend', 'revoke', 'deactivate', 'reactivate'):
            self.assertEqual(self.act(self.mentor.pk, action, self.other_lead).status_code, 404)
        r = authed_client(self.other_lead).patch(f'{MENTORS}{self.mentor.pk}/', {'name': 'X'},
                                                 format='json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.act(self.mentor.pk, 'deactivate', self.viewer).status_code, 403)

    def test_the_row_and_the_counts(self):
        ReviewerProfile.objects.create(
            partner_admin=self.mine, phone='12-345 6789', english_fluency='fluent',
            bm_fluency='conversational', tamil_fluency='', other_language='Mandarin',
            other_language_fluency='')
        Mentor.objects.filter(pk=self.mentor.pk).update(area='Accounting, finance')
        body = authed_client(self.lead).get(MENTORS).json()
        row = body['mentors'][0]
        self.assertEqual(set(row), {
            'id', 'name', 'email', 'phone', 'status', 'area', 'languages', 'other_language',
            'invited_at', 'signed_in', 'last_seen_at', 'deactivated_at', 'manageable',
            'scholars_now', 'staff_role',   # S7b; S7d
            # Team tables T3: the Team -> Mentors table's own columns (`mentor_rows(team=True)`).
            'tables', 'lead', 'meetings_90', 'last_meeting', 'concerns_open'})
        self.assertIsNone(row['staff_role'])   # a mentor login, not a staff member
        self.assertEqual((row['name'], row['email'], row['phone'], row['area']),
                         ('Priya Devi', 'priya@example.org', '12-345 6789', 'Accounting, finance'))
        self.assertEqual(row['languages'], {'en': 'fluent', 'ms': 'conversational', 'ta': ''})
        # The fourth language shows only when spoken conversationally or better.
        self.assertEqual(row['other_language'], '')
        ReviewerProfile.objects.filter(partner_admin=self.mine).update(other_language_fluency='fluent')
        self.assertEqual(authed_client(self.lead).get(MENTORS).json()['mentors'][0]['other_language'],
                         'Mandarin')
        self.assertEqual(body['counts'], {'active': 0, 'invited': 1, 'inactive': 0})

    def test_the_first_sign_in_makes_it_active_and_closes_the_invitation(self):
        self.assertEqual(self.sign_in(self.mine).status_code, 200)
        row = authed_client(self.lead).get(MENTORS).json()['mentors'][0]
        self.assertEqual((row['status'], row['signed_in']), ('active', True))
        self.assertIsNotNone(Invitation.objects.get(audience='mentor').accepted_at)

    def test_a_mentor_invitation_is_only_under_its_own_kind_and_cancel_still_refuses_it(self):
        """S7b follow-up (owner, 2026-11-01) supersedes S7a's "not on the Invitations page": a mentor
        invitation is listed under the Mentor kind ONLY; the generic Cancel still 404s it (Revoke is
        the mentor action)."""
        body = authed_client(self.lead).get(INVITE + '?kind=admins').json()
        self.assertEqual(body['invitations'], [])
        self.assertEqual(body['waiting'], {'admins': 0, 'reviewers': 0, 'source': 0, 'mentor': 1, 'sponsors': 0})
        inv = Invitation.objects.get(audience='mentor')
        r = authed_client(self.lead).post(f'{INVITE}{inv.pk}/cancel/', {}, format='json')
        self.assertEqual(r.status_code, 404)


class TestActions(_Base):
    def setUp(self):
        self.invite()
        self.mentor = Mentor.objects.get()
        self.mine = self.login()
        mail.outbox.clear()

    def test_resend_while_invited_only(self):
        r = self.act(self.mentor.pk, 'resend')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Invitation.objects.get(audience='mentor').send_count, 2)
        self.sign_in(self.mine)
        r = self.act(self.mentor.pk, 'resend')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'already_joined'))
        self.assertEqual(len(mail.outbox), 1)

    def test_revoke_withdraws_the_invitation_and_switches_the_login_off(self):
        with patch(ISSUE, return_value=True), patch(KILL, return_value='killed') as kill, \
                patch('apps.scholarship.staff_lifecycle.login_used_elsewhere', return_value=False):
            r = authed_client(self.lead).post(f'{MENTORS}{self.mentor.pk}/revoke/', {},
                                              format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['status'], 'inactive')
        kill.assert_called_once()
        self.mine.refresh_from_db()
        self.mentor.refresh_from_db()
        self.assertFalse(self.mine.is_active)
        self.assertEqual(self.mentor.deactivated_by_email, self.lead.email)
        self.assertIsNotNone(Invitation.objects.get(audience='mentor').revoked_at)
        # The login is refused from the next request.
        self.assertFalse(self.sign_in(self.mine).json()['is_admin'])
        self.assertEqual(mail.outbox, [])

    def test_revoke_after_sign_in_is_refused_deactivate_instead(self):
        self.sign_in(self.mine)
        r = self.act(self.mentor.pk, 'revoke')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'already_joined'))
        r = self.act(self.mentor.pk, 'deactivate')
        self.assertEqual((r.status_code, r.json()['status']), (200, 'inactive'))
        self.assertTrue(Mentor.objects.filter(pk=self.mentor.pk).exists())   # never deleted
        self.assertEqual(authed_client(self.mine).get('/api/v1/admin/me/').status_code, 403)
        again = self.act(self.mentor.pk, 'deactivate')
        self.assertEqual((again.status_code, again.json()['code']), (400, 'not_active'))

    def test_reactivate_a_mentor_who_signed_in_sends_nothing(self):
        self.sign_in(self.mine)
        self.act(self.mentor.pk, 'deactivate')
        r = self.act(self.mentor.pk, 'reactivate')
        self.assertEqual((r.status_code, r.json()['status'], r.json()['emailed']),
                         (200, 'active', False))
        self.mine.refresh_from_db()
        self.assertTrue(self.mine.is_active)
        self.assertEqual(mail.outbox, [])
        again = self.act(self.mentor.pk, 'reactivate')
        self.assertEqual((again.status_code, again.json()['code']), (400, 'active'))

    def test_reactivate_is_refused_for_a_mentor_who_never_signed_in(self):
        """S7b follow-up review (owner): the Mentors page never invites. A mentor revoked before
        arriving comes back by a re-invite on Invitations → Mentor, never by Reactivate."""
        self.act(self.mentor.pk, 'revoke')
        mail.outbox.clear()
        r = self.act(self.mentor.pk, 'reactivate')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_arrived'))
        self.assertEqual(mail.outbox, [])
        self.mentor.refresh_from_db()
        self.assertIsNotNone(self.mentor.deactivated_at)

    def test_an_unknown_action_is_404(self):
        self.assertEqual(self.act(self.mentor.pk, 'delete').status_code, 404)


class TestStaffEditUntilFirstSignIn(_Base):
    def setUp(self):
        self.invite()
        self.mentor = Mentor.objects.get()
        self.mine = self.login()
        mail.outbox.clear()

    def patch(self, body, caller=None):
        return authed_client(caller or self.lead).patch(f'{MENTORS}{self.mentor.pk}/', body,
                                                        format='json')

    def test_the_name_is_corrected_before_sign_in(self):
        r = self.patch({'name': 'Ms Priya Devi'})
        self.assertEqual((r.status_code, r.json()['name']), (200, 'Ms Priya Devi'))
        self.assertEqual(Invitation.objects.get(audience='mentor').name, 'Ms Priya Devi')
        self.assertEqual(mail.outbox, [])

    def test_a_new_address_is_a_new_sign_in_and_gets_the_invitation(self):
        account = {'id': 'uid-new', 'email': 'priya@example.org', 'last_sign_in_at': None,
                   'app_metadata': {'providers': ['email']}, 'identities': []}
        with patch(READ, return_value=account), patch(DELETE, return_value=True) as deleted, \
                patch(NEW_LOGIN, return_value=('uid-2', False, None)), \
                patch('apps.scholarship.staff_lifecycle.login_used_elsewhere', return_value=False):
            r = self.patch({'email': 'Priya.D@Example.org'})
        self.assertEqual(r.status_code, 200, r.content)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.email, self.mine.supabase_user_id), ('priya.d@example.org', 'uid-2'))
        deleted.assert_called_once_with('uid-new')
        invs = Invitation.objects.filter(audience='mentor').order_by('id')
        self.assertIsNotNone(invs[0].revoked_at)
        self.assertEqual((invs[1].email, invs[1].revoked_at, invs[1].mentor_id),
                         ('priya.d@example.org', None, self.mentor.pk))
        self.assertEqual([m.to for m in mail.outbox], [['priya.d@example.org']])

    def test_an_address_with_a_sign_in_is_refused(self):
        r = self.patch({'email': self.viewer.email})
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'))

    def test_after_the_first_sign_in_the_details_are_the_mentors(self):
        self.sign_in(self.mine)
        for body in ({'name': 'Renamed'}, {'email': 'new@example.org'}):
            r = self.patch(body)
            self.assertEqual((r.status_code, r.json()['code']), (409, 'managed_by_mentor'), body)
        self.mine.refresh_from_db()
        self.assertEqual((self.mine.name, self.mine.email), ('Priya Devi', 'priya@example.org'))

    def test_only_name_and_email_and_only_super_or_org_admin(self):
        self.assertEqual(self.patch({'area': 'x'}).status_code, 400)
        self.assertEqual(self.patch({'name': 'X'}, caller=self.viewer).status_code, 403)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheMentorsOwnProfile(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.mentor_login = make_admin('mentor', owning_org=cls.org, first_seen_at=timezone.now())
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.admin = make_admin('admin', owning_org=cls.org)

    def me(self, who, body=None):
        client = authed_client(who)
        if body is None:
            return client.get('/api/v1/admin/me/')
        return client.patch('/api/v1/admin/me/', body, format='json')

    def test_the_area_is_the_mentors_to_write(self):
        r = self.me(self.mentor_login, {'mentoring_area': '  Accounting, finance '})
        self.assertEqual((r.status_code, r.json()['mentoring_area']), (200, 'Accounting, finance'))
        self.assertEqual(Mentor.objects.get(pk=self.mentor_login.mentor_id).area,
                         'Accounting, finance')
        self.assertEqual(self.me(self.mentor_login).json()['mentoring_area'], 'Accounting, finance')

    def test_the_area_is_required_and_capped(self):
        for value, code in (('  ', 'mentoring_area_required'),
                            ('x' * 121, 'mentoring_area_too_long'), (5, 'bad_request')):
            r = self.me(self.mentor_login, {'mentoring_area': value})
            self.assertEqual((r.status_code, r.json()['code']), (400, code), value)

    def test_no_other_role_writes_or_reads_an_area(self):
        for who in (self.reviewer, self.admin):
            r = self.me(who, {'mentoring_area': 'Engineering'})
            self.assertEqual((r.status_code, r.json()['code'], r.json()['fields']),
                             (400, 'not_editable', ['mentoring_area']), who.role)
            self.assertNotIn('mentoring_area', self.me(who).json())

    def test_a_mentor_keeps_a_phone_and_may_share_it_with_students(self):
        r = self.me(self.mentor_login, {'phone': '12-345 6789', 'share_phone_with_students': False})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['phone'], r.json()['share_phone_with_students']),
                         ('12-345 6789', False))
        r = self.me(self.mentor_login, {'phone': ''})
        self.assertEqual((r.status_code, r.json()['code']), (400, 'phone_required'))

    def test_a_new_profile_shares_the_phone_with_students_by_default(self):
        self.me(self.mentor_login, {'job_title': 'Audit partner'})
        profile = ReviewerProfile.objects.get(partner_admin=self.mentor_login)
        self.assertTrue(profile.share_phone_with_students)

    def test_the_reviewer_cards_save_for_a_mentor_but_never_a_pause(self):
        client = authed_client(self.mentor_login)
        r = client.patch('/api/v1/admin/reviewer-profile/',
                         {'highest_qualification': 'Masters', 'english_fluency': 'fluent'},
                         format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ReviewerProfile.objects.get(partner_admin=self.mentor_login).english_fluency,
                         'fluent')
        r = client.patch('/api/v1/admin/reviewer-profile/',
                         {'paused': True, 'english_fluency': 'conversational'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_reviewable'))
        self.assertEqual(ReviewerProfile.objects.get(partner_admin=self.mentor_login).english_fluency,
                         'fluent')

    def test_the_status_rule(self):
        m = Mentor(organisation=self.org)
        self.assertEqual(mentor_invite.status_of(m, None), 'invited')
        self.assertEqual(mentor_invite.status_of(m, self.mentor_login), 'active')
        m.deactivated_at = timezone.now()
        self.assertEqual(mentor_invite.status_of(m, self.mentor_login), 'inactive')


# ── Review fixes (adversarial review of 7a, 2026-10-31) ─────────────────────────────────────────
def _verified_token(sub, email):
    """A bearer token carrying an email — what a Google sign-in presents. `get_admin` links a row with
    no UID to it by that email once the SERVER confirms it (`email_confirmed_at`; audit SEC-02)."""
    import jwt
    from apps.scholarship.tests.factories import TEST_JWT_SECRET as SECRET
    return jwt.encode({'sub': sub, 'aud': 'authenticated', 'role': 'authenticated', 'email': email},
                      SECRET, algorithm='HS256')


def _confirmed(sub, email):
    """The mocked admin-API read of a login whose address Supabase confirmed (audit SEC-02)."""
    return patch('apps.courses.supabase_admin.read_auth_user', return_value={
        'id': sub, 'email': email, 'email_confirmed_at': '2026-11-01T00:00:00Z'})


class TestReviewFixes(_Base):
    OLD_ACCOUNT = {'id': 'uid-new', 'email': 'priya@example.org', 'last_sign_in_at': None,
                   'app_metadata': {'providers': ['email']}, 'identities': []}

    def _google_mentor_who_signed_in_on_a_refused_route(self):
        """A Google invitee (no UID, no password issued) whose verified-email sign-in hits a route a
        mentor is REFUSED: `get_admin` still links the UID, and nothing stamps `first_seen_at`."""
        self.invite(email='priya@gmail.com')
        mentor = Mentor.objects.get()
        from rest_framework.test import APIClient
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_verified_token("google-uid", "priya@gmail.com")}')
        with _confirmed('google-uid', 'priya@gmail.com'):
            self.assertEqual(client.get(MENTORS).status_code, 403)
        login = self.login('priya@gmail.com')
        self.assertEqual((login.supabase_user_id, login.first_seen_at), ('google-uid', None))
        mail.outbox.clear()
        return mentor, login

    def test_fix2_a_linked_login_counts_as_signed_in_everywhere(self):
        mentor, login = self._google_mentor_who_signed_in_on_a_refused_route()
        row = authed_client(self.lead).get(MENTORS).json()['mentors'][0]
        self.assertEqual((row['status'], row['signed_in']), ('active', True))
        with patch(ISSUE, return_value=True) as issued:
            for action in ('resend', 'revoke'):
                r = authed_client(self.lead).post(f'{MENTORS}{mentor.pk}/{action}/', {}, format='json')
                self.assertEqual((r.status_code, r.json()['code']), (400, 'already_joined'), action)
            r = authed_client(self.lead).patch(f'{MENTORS}{mentor.pk}/', {'email': 'x@example.org'},
                                               format='json')
            self.assertEqual((r.status_code, r.json()['code']), (409, 'managed_by_mentor'))
            # Deactivate and Reactivate: their own login is theirs — no password, no letter.
            self.act(mentor.pk, 'deactivate')
            r = authed_client(self.lead).post(f'{MENTORS}{mentor.pk}/reactivate/', {}, format='json')
            self.assertEqual((r.status_code, r.json()['emailed']), (200, False))
        issued.assert_not_called()
        self.assertEqual(mail.outbox, [])
        login.refresh_from_db()
        self.assertEqual(login.email, 'priya@gmail.com')

    def test_fix2_a_password_is_reissued_only_where_one_was_issued(self):
        self.invite(email='priya@gmail.com')
        mentor = Mentor.objects.get()
        login = self.login('priya@gmail.com')
        with patch(ISSUE, return_value=True) as issued:
            r = authed_client(self.lead).post(f'{MENTORS}{mentor.pk}/resend/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        issued.assert_not_called()
        self.assertIn('Sign in with Google', mail.outbox[-1].body)
        # Defence in depth, under the signed-in rule: even with a UID on the row (somebody's own
        # login), the letter's own step reissues nothing — the newest invitation issued no password.
        PartnerAdmin.objects.filter(pk=login.pk).update(supabase_user_id='their-own-uid')
        login.refresh_from_db()
        with patch(ISSUE, return_value=True) as issued:
            mentor_invite._send_again(self.lead, mentor, login)
        issued.assert_not_called()
        PartnerAdmin.objects.filter(pk=login.pk).update(supabase_user_id=None)
        login.refresh_from_db()
        # And a temp-password mentor's Resend still rotates its password.
        self.invite(new_login=('uid-tp', False, None), email='tp@example.org')
        tp = Mentor.objects.exclude(pk=mentor.pk).get()
        with patch(ISSUE, return_value=True) as issued, patch(READ, return_value=UNTOUCHED):
            r = authed_client(self.lead).post(f'{MENTORS}{tp.pk}/resend/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        issued.assert_called_once()
        self.assertIsNone(login.supabase_user_id)

    def test_an_email_move_to_a_students_address_keeps_their_login(self):
        """Owner ruling 2026-10-31: the new address may be a student's or a sponsor's. Our unused
        login at the OLD address is retired; theirs is never touched (the row carries no UID)."""
        self.invite()
        mentor = Mentor.objects.get()
        mail.outbox.clear()
        with patch(READ, return_value=self.OLD_ACCOUNT), patch(DELETE, return_value='deleted') as deleted,                 patch(NEW_LOGIN, return_value=(None, True, None)),                 patch('apps.scholarship.staff_lifecycle.login_used_elsewhere', return_value=False):
            r = authed_client(self.lead).patch(f'{MENTORS}{mentor.pk}/', {'email': 'student@example.org'},
                                               format='json')
        self.assertEqual(r.status_code, 200, r.content)
        deleted.assert_called_once_with('uid-new')        # ours, at the old address — never theirs
        login = self.login('student@example.org')
        self.assertIsNone(login.supabase_user_id)
        inv = Invitation.objects.get(audience='mentor', revoked_at__isnull=True)
        self.assertFalse(inv.credential_issued)
        self.assertIn('You already have a HalaTuju account', mail.outbox[-1].body)

    def test_fix3_the_database_allows_one_login_per_mentor(self):
        from django.db import IntegrityError, transaction
        self.invite()
        mentor = Mentor.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PartnerAdmin.objects.create(email='second@example.org', name='Second', role='mentor',
                                        owning_organisation=self.org, mentor=mentor)

    def test_fix4_a_move_that_loses_the_race_writes_nothing_and_drops_its_new_login(self):
        self.invite()
        mentor = Mentor.objects.get()
        stale = self.login()                              # read before the mentor signs in…
        PartnerAdmin.objects.filter(pk=stale.pk).update(first_seen_at=timezone.now())   # …who now has
        mail.outbox.clear()
        with patch(READ, return_value=self.OLD_ACCOUNT), patch(DELETE, return_value='deleted') as deleted, \
                patch(NEW_LOGIN, return_value=('uid-2', False, None)), \
                patch('apps.scholarship.staff_lifecycle.login_used_elsewhere', return_value=False):
            done = mentor_invite.edit(self.lead, mentor, stale, email='new@example.org')
        self.assertEqual(done, (False, False, 'managed_by_mentor'))
        deleted.assert_called_once_with('uid-2')          # the new login, never the mentor's own
        login = self.login()
        self.assertEqual((login.email, login.supabase_user_id), ('priya@example.org', 'uid-new'))
        self.assertEqual(Invitation.objects.filter(audience='mentor', revoked_at__isnull=True).count(), 1)
        self.assertEqual(mail.outbox, [])


class TestAGoogleAddressThatAlreadyHasALogin(_Base):
    """Owner ruling 2026-10-31: a student who signs in with Google may be a mentor too. A Google
    address is never provisioned and never looked up; the row links on their next Google sign-in."""

    def test_an_invite_to_a_google_address_is_not_looked_up(self):
        with patch('apps.courses.supabase_admin.http_requests.get') as asked:
            r = self.invite(email='Priya@Gmail.com')
        self.assertEqual(r.status_code, 201, r.content)
        asked.assert_not_called()
        self.assertIsNone(self.login('priya@gmail.com').supabase_user_id)

class TestNoResendResetsAStudentsOrSponsorsLogin(_Base):
    """S7a follow-up review (2026-10-31): `staff_reinvite.reissue_credential` — the one door every
    Resend (staff, source, mentor) rotates a password through — never writes onto a login that is
    also a student's profile or a sponsor's account, however the UID got onto the row."""

    def test_their_login_is_never_reset_ours_still_is(self):
        from apps.courses import staff_reinvite
        from apps.courses.models import StudentProfile
        StudentProfile.objects.create(supabase_user_id='stu-uid')
        theirs = make_admin('reviewer', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=theirs.pk).update(supabase_user_id='stu-uid')
        theirs.refresh_from_db()
        ours = make_admin('reviewer', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=ours.pk).update(supabase_user_id='ours-uid')
        ours.refresh_from_db()
        from apps.scholarship import invitations
        for row in (theirs, ours):   # both look like logins WE made (TD-440); only the student check differs
            invitations.create_or_refresh(audience='staff', email=row.email, name=row.name,
                                          role='reviewer', organisation=self.org, partner_admin=row,
                                          credential_issued=True)
        with patch(ISSUE, return_value=True) as issued, patch(READ, return_value=UNTOUCHED):
            self.assertEqual(staff_reinvite.reissue_credential(theirs), (None, None))
            issued.assert_not_called()
            temp, err = staff_reinvite.reissue_credential(ours)
        self.assertIsNone(err)
        self.assertTrue(temp)
        issued.assert_called_once()


class TestTheMentorKindOnInvitations(_Base):
    """S7b follow-up (owner, 2026-11-01): mentors are invited from Invitations, like sources. The
    Mentor kind lists the WAITING mentor invitations of the caller's organisation, with the Mentors
    page's own rows (`manageable`) for the roster's Resend / Revoke; never under another kind."""

    def test_the_mentor_kind_lists_the_waiting_ones_with_their_mentor_rows(self):
        self.invite()
        mentor = Mentor.objects.get()
        body = authed_client(self.lead).get(INVITE + '?kind=mentor').json()
        self.assertEqual(body['kind'], 'mentor')
        self.assertEqual([(r['email'], r['mentor_id']) for r in body['invitations']],
                         [('priya@example.org', mentor.pk)])
        self.assertEqual(body['waiting']['mentor'], 1)
        self.assertEqual([(m['id'], m['manageable'], m['status']) for m in body['mentors']],
                         [(mentor.pk, True, 'invited')])
        for kind in ('admins', 'reviewers', 'source', 'sponsors'):
            with self.subTest(kind=kind):
                rows = authed_client(self.lead).get(INVITE + f'?kind={kind}').json()['invitations']
                self.assertNotIn('priya@example.org', [r['email'] for r in rows])

    def test_another_organisation_sees_none_of_it(self):
        self.invite()
        body = authed_client(self.other_lead).get(INVITE + '?kind=mentor').json()
        self.assertEqual((body['invitations'], body['waiting']['mentor'], body['mentors']), ([], 0, []))

    def test_a_signed_in_or_revoked_mentor_is_no_longer_waiting(self):
        self.invite()
        mentor = Mentor.objects.get()
        with patch(KILL, return_value='killed'):
            self.assertEqual(authed_client(self.lead).post(f'{MENTORS}{mentor.pk}/revoke/', {},
                                                           format='json').status_code, 200)
        body = authed_client(self.lead).get(INVITE + '?kind=mentor').json()
        self.assertEqual((body['invitations'], body['waiting']['mentor']), ([], 0))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheMentorInvitationIsEditable(TestCase):
    """S7b follow-up (owner, 2026-11-01): the mentor's invitation — the only email a mentor is ever
    sent — is the stored `invite_mentor` template; the sign-in paragraph stays ours."""

    def setUp(self):
        from django.core.management import call_command
        import io as _io
        call_command('seed_partner_email_templates', stdout=_io.StringIO())

    def _build(self):
        from apps.scholarship import emails
        return emails.build_mentor_invitation_email(
            org_name='BrightPath', name='Priya Devi', login_link='https://example.org/admin/login',
            access='ACCESS PARAGRAPH')

    def test_the_seed_is_byte_identical_to_the_built_in_letter(self):
        from apps.scholarship.models import PartnerEmailTemplate
        stored = self._build()
        PartnerEmailTemplate.objects.filter(kind='invite_mentor').delete()
        self.assertEqual(stored, self._build())

    def test_the_edited_wording_is_what_the_mentor_is_sent(self):
        from apps.scholarship.emails import send_mentor_invitation_email
        from apps.scholarship.models import PartnerEmailTemplate
        PartnerEmailTemplate.objects.filter(kind='invite_mentor').update(
            subject='Mentor with {org_name}?',
            body='Hello {name},\n\nWe would love your help.\n\n{login_link}\n\n{access}\n\n{team_signoff}')
        ok, _err = send_mentor_invitation_email('priya@example.org', name='Priya Devi', org_name='BrightPath',
                                                temp_password='Kx7m-Pq4t-Rd92')
        self.assertTrue(ok)
        letter = mail.outbox[-1]
        self.assertEqual((letter.subject, letter.to), ('Mentor with BrightPath?', ['priya@example.org']))
        self.assertIn('We would love your help.', letter.body)
        self.assertIn('Kx7m-Pq4t-Rd92', letter.body)             # the access paragraph is ours, always
        self.assertIn('/admin/login', letter.body)

    def test_a_stored_body_without_the_way_in_falls_back_and_the_editor_refuses_it(self):
        from apps.scholarship import partner_comms
        from apps.scholarship.models import PartnerEmailTemplate
        PartnerEmailTemplate.objects.filter(kind='invite_mentor').update(body='Hello {name}. {team_signoff}')
        _s, body = self._build()
        self.assertIn('ACCESS PARAGRAPH', body)
        self.assertIn('fill in your profile', body)              # the built-in letter
        self.assertEqual(set(partner_comms.missing_required_placeholders(
            'invite_mentor', 'S', 'Hello {name}. {team_signoff}')), {'access', 'login_link'})

    def test_it_is_listed_with_the_invitation_emails(self):
        sup = make_admin('super', super_admin=True)
        kinds = [t['kind'] for t in authed_client(sup).get(
            '/api/v1/admin/scholarship/partner-emails/?family=invite').json()['templates']]
        self.assertIn('invite_mentor', kinds)
        others = [t['kind'] for t in authed_client(sup).get(
            '/api/v1/admin/scholarship/partner-emails/').json()['templates']]
        self.assertNotIn('invite_mentor', others)


class TestFollowUpReviewFixes(_Base):
    """The adversarial review of the S7b follow-up (2026-11-01): four findings, a test each."""

    # ── 1. finance never reads mentors through Invitations ─────────────────────────────────
    def test_finance_gets_nothing_of_the_mentor_kind(self):
        self.invite()
        finance = make_admin('finance', owning_org=self.org)
        body = authed_client(finance).get(INVITE + '?kind=mentor').json()
        self.assertEqual((body['invitations'], body['waiting']['mentor'], body['totals']['mentor']), ([], 0, 0))
        self.assertNotIn('mentors', body)
        self.assertNotIn('Priya', str(body))
        # The roster's own readers still see it.
        self.assertEqual(authed_client(self.viewer).get(INVITE + '?kind=mentor').json()['waiting']['mentor'], 1)

    # ── 2. no structural token in an invitation's subject ─────────────────────────────────
    def test_a_subject_carrying_a_block_is_refused_at_save_for_every_invitation_kind(self):
        from django.core.management import call_command
        import io as _io
        call_command('seed_partner_email_templates', stdout=_io.StringIO())
        for kind in ('invite_admin', 'invite_source', 'invite_mentor'):
            with self.subTest(kind=kind):
                r = authed_client(self.lead).patch(f'/api/v1/admin/scholarship/partner-emails/{kind}/', {
                    'subject': 'Your password: {access}',
                    'body': 'Hello.\n\n{login_link}\n\n{access}\n\n{team_signoff}'}, format='json')
                self.assertEqual((r.status_code, r.json()['code']), (400, 'structural_in_subject'))

    def test_a_stored_subject_carrying_a_block_falls_back_at_send(self):
        from django.core.management import call_command
        import io as _io
        from apps.scholarship import emails
        from apps.scholarship.models import PartnerEmailTemplate
        call_command('seed_partner_email_templates', stdout=_io.StringIO())
        PartnerEmailTemplate.objects.filter(kind__in=('invite_admin', 'invite_source', 'invite_mentor')).update(
            subject='Your password: {access}')
        letters = {
            'invite_admin': emails.build_partner_welcome_email('x@example.org', 'Priya', 'admin',
                                                               temp_password='Kx7m-Pq4t-Rd92'),
            'invite_source': emails.build_source_invitation_email(
                org_name='Centre', contact_person='Devi', login_link='https://e.org/admin/login',
                access='Your temporary password: Kx7m-Pq4t-Rd92'),
            'invite_mentor': emails.build_mentor_invitation_email(
                org_name='BrightPath', name='Priya', login_link='https://e.org/admin/login',
                access='Your temporary password: Kx7m-Pq4t-Rd92'),
        }
        for kind, (subject, _body) in letters.items():
            with self.subTest(kind=kind):
                self.assertNotIn('Kx7m-Pq4t-Rd92', subject)
                self.assertNotIn('Your password', subject)          # the built-in letter, not the stored one

    # ── 4. the Mentors page never invites; a re-invite brings a mentor back ────────────────
    def _revoked_before_arriving(self):
        self.invite()
        mentor = Mentor.objects.get()
        self.act(mentor.pk, 'revoke')
        mail.outbox.clear()
        return mentor

    def test_a_re_invite_brings_back_a_mentor_revoked_before_arriving(self):
        mentor = self._revoked_before_arriving()
        with patch(ISSUE, return_value=True) as issued, patch(READ, return_value=UNTOUCHED):
            r = self.invite(name='Priya D')
        self.assertEqual(r.status_code, 201, r.content)
        mentor.refresh_from_db()
        login = self.login()
        self.assertIsNone(mentor.deactivated_at)
        self.assertEqual((login.is_active, login.name, login.mentor_id), (True, 'Priya D', mentor.pk))
        self.assertEqual((Mentor.objects.count(), PartnerAdmin.objects.filter(role='mentor').count()), (1, 1))
        issued.assert_called_once()
        self.assertEqual([m.to for m in mail.outbox], [['priya@example.org']])
        self.assertEqual(Invitation.objects.filter(audience='mentor', accepted_at__isnull=True,
                                                   revoked_at__isnull=True).count(), 1)
        self.assertEqual(r.json()['mentor']['status'], 'invited')

    def test_a_re_invite_never_resets_a_login_the_person_brought(self):
        mentor = self._revoked_before_arriving()
        PartnerAdmin.objects.filter(mentor=mentor).update(supabase_user_id=None)
        with patch(ISSUE) as issued:
            r = self.invite()
        self.assertEqual(r.status_code, 201, r.content)
        issued.assert_not_called()
        self.assertFalse(Invitation.objects.filter(audience='mentor', revoked_at__isnull=True)
                         .get().credential_issued)

    def test_a_signed_in_or_another_organisations_mentor_stays_409(self):
        mentor = self._revoked_before_arriving()
        r = self.invite(caller=self.other_lead)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'))
        PartnerAdmin.objects.filter(mentor=mentor).update(first_seen_at=timezone.now())
        r = self.invite()
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'))
        self.assertEqual(Mentor.objects.count(), 1)
