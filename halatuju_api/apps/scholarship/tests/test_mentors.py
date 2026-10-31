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
EXISTS = 'apps.courses.supabase_admin.auth_user_exists'

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

    def invite(self, caller=None, new_login=('uid-new', False, None), query='', exists=False, **body):
        body.setdefault('audience', 'mentor')
        body.setdefault('name', 'Priya Devi')
        body.setdefault('email', 'priya@example.org')
        # `exists`: what Supabase Auth answers for a GOOGLE address (`auth_user_exists`); never the
        # network in a test.
        with patch(NEW_LOGIN, return_value=new_login) as made,                 patch(EXISTS, return_value=exists) as asked:
            r = authed_client(caller or self.lead).post(INVITE + query, body, format='json')
        self.new_login, self.asked = made, asked
        return r

    def login(self, email='priya@example.org'):
        return PartnerAdmin.objects.get(email=email)

    def act(self, mentor_id, action, caller=None):
        with patch(ISSUE, return_value=True), patch(KILL, return_value='killed'):
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

    def test_an_address_that_already_has_a_login_is_refused(self):
        """Review fix 1 (owner rule: ANY existing sign-in is refused). It used to be 201
        `already_registered` with a mentor row that `get_admin` would later attach to that person's
        own login — a student's or a sponsor's."""
        r = self.invite(new_login=(None, True, None))
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'))
        self.assertFalse(Mentor.objects.exists())
        self.assertFalse(PartnerAdmin.objects.filter(role='mentor').exists())
        self.assertFalse(Invitation.objects.filter(audience='mentor').exists())
        self.assertEqual(mail.outbox, [])

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
            'invited_at', 'signed_in', 'last_seen_at', 'deactivated_at', 'manageable'})
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

    def test_a_mentor_invitation_is_not_on_the_invitations_page(self):
        body = authed_client(self.lead).get(INVITE + '?kind=admins').json()
        self.assertEqual(body['invitations'], [])
        self.assertEqual(body['waiting'], {'admins': 0, 'reviewers': 0, 'source': 0, 'sponsors': 0})
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

    def test_reactivate_a_mentor_who_never_signed_in_sends_the_invitation_again(self):
        self.act(self.mentor.pk, 'revoke')
        r = self.act(self.mentor.pk, 'reactivate')
        self.assertEqual((r.status_code, r.json()['status'], r.json()['emailed']),
                         (200, 'invited', True))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('mentor', mail.outbox[0].subject)
        waiting = Invitation.objects.filter(audience='mentor', accepted_at__isnull=True,
                                            revoked_at__isnull=True)
        self.assertEqual(waiting.count(), 1)

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
    """A bearer token carrying a VERIFIED email — what a Google sign-in presents. `get_admin` links a
    row with no UID to it by that email (`PartnerAdminMixin._find_admin`)."""
    import jwt
    from apps.scholarship.tests.factories import TEST_JWT_SECRET as SECRET
    return jwt.encode({'sub': sub, 'aud': 'authenticated', 'role': 'authenticated', 'email': email,
                       'email_verified': True}, SECRET, algorithm='HS256')


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
        with patch(ISSUE, return_value=True) as issued:
            r = authed_client(self.lead).post(f'{MENTORS}{tp.pk}/resend/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        issued.assert_called_once()
        self.assertIsNone(login.supabase_user_id)

    def test_fix1_an_email_move_to_an_address_with_a_sign_in_is_refused(self):
        self.invite()
        mentor = Mentor.objects.get()
        mail.outbox.clear()
        with patch(READ, return_value=self.OLD_ACCOUNT), patch(DELETE, return_value='deleted') as deleted, \
                patch(NEW_LOGIN, return_value=(None, True, None)), \
                patch('apps.scholarship.staff_lifecycle.login_used_elsewhere', return_value=False):
            r = authed_client(self.lead).patch(f'{MENTORS}{mentor.pk}/', {'email': 'student@example.org'},
                                               format='json')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'))
        deleted.assert_not_called()
        login = self.login()
        self.assertEqual((login.email, login.supabase_user_id), ('priya@example.org', 'uid-new'))
        self.assertEqual(Invitation.objects.filter(audience='mentor', revoked_at__isnull=True).count(), 1)
        self.assertEqual(mail.outbox, [])

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
    """Lead check of the review fix (2026-10-31): a GOOGLE address is never provisioned, so
    `already_registered` cannot catch it — Supabase Auth is asked (`auth_user_exists`)."""

    def test_an_invite_to_a_google_address_with_a_login_is_refused(self):
        r = self.invite(email='Priya@Gmail.com', exists=True)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'))
        self.asked.assert_called_once_with('priya@gmail.com')
        self.assertFalse(Mentor.objects.exists())
        self.assertFalse(PartnerAdmin.objects.filter(role='mentor').exists())
        self.assertFalse(Invitation.objects.filter(audience='mentor').exists())
        self.assertEqual(mail.outbox, [])

    def test_a_failed_lookup_fails_closed(self):
        from apps.courses import supabase_admin
        r = self.invite(email='priya@gmail.com', exists=supabase_admin.FAILED)
        self.assertEqual((r.status_code, r.json()['code']), (502, 'create_failed'))
        self.assertFalse(Mentor.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_a_non_google_address_is_not_looked_up(self):
        self.assertEqual(self.invite().status_code, 201)
        self.asked.assert_not_called()

    def _move(self, email, exists):
        account = {'id': 'uid-new', 'email': 'priya@example.org', 'last_sign_in_at': None,
                   'app_metadata': {'providers': ['email']}, 'identities': []}
        mentor = Mentor.objects.get()
        with patch(READ, return_value=account), patch(DELETE, return_value='deleted') as deleted,                 patch(EXISTS, return_value=exists), patch(NEW_LOGIN, return_value=('uid-2', False, None)) as made,                 patch('apps.scholarship.staff_lifecycle.login_used_elsewhere', return_value=False):
            r = authed_client(self.lead).patch(f'{MENTORS}{mentor.pk}/', {'email': email}, format='json')
        deleted.assert_not_called()
        made.assert_not_called()
        return r

    def test_an_email_move_to_a_google_address_with_a_login_is_refused(self):
        from apps.courses import supabase_admin
        self.invite()
        mail.outbox.clear()
        for exists, code, http in ((True, 'already_staff', 409), (supabase_admin.FAILED, 'create_failed', 502)):
            r = self._move('student@gmail.com', exists)
            self.assertEqual((r.status_code, r.json()['code']), (http, code), exists)
        login = self.login()
        self.assertEqual((login.email, login.supabase_user_id), ('priya@example.org', 'uid-new'))
        self.assertEqual(Invitation.objects.filter(audience='mentor', revoked_at__isnull=True).count(), 1)
        self.assertEqual(mail.outbox, [])


@override_settings(**SUPABASE)
class TestAuthUserExists(TestCase):
    """`supabase_admin.auth_user_exists` itself — the network mocked."""

    def answer(self, status=200, users=None, raises=False):
        from unittest.mock import MagicMock
        resp = MagicMock(status_code=status)
        resp.json.return_value = {'users': users if users is not None else []}
        return patch('apps.courses.supabase_admin.http_requests.get',
                     side_effect=OSError('down') if raises else None, return_value=resp)

    def test_the_three_answers(self):
        from apps.courses import supabase_admin
        with self.answer(users=[{'id': 'a', 'email': 'Priya@gmail.com'}]):
            self.assertIs(supabase_admin.auth_user_exists('priya@gmail.com'), True)
        # GoTrue's filter is a SUBSTRING match: a near-miss is not the same login.
        with self.answer(users=[{'id': 'b', 'email': 'xpriya@gmail.com'}]):
            self.assertIs(supabase_admin.auth_user_exists('priya@gmail.com'), False)
        for kw in ({'status': 500}, {'raises': True}):
            with self.answer(**kw):
                self.assertEqual(supabase_admin.auth_user_exists('priya@gmail.com'), supabase_admin.FAILED)
        # A FULL page of near-misses: the exact address could be on the next page — fail closed.
        page = [{'id': str(i), 'email': f'{i}priya@gmail.com'} for i in range(3)]
        with self.answer(users=page):
            self.assertEqual(supabase_admin.auth_user_exists('priya@gmail.com', per_page=3),
                             supabase_admin.FAILED)
        with override_settings(SUPABASE_SERVICE_ROLE_KEY=''):
            self.assertEqual(supabase_admin.auth_user_exists('priya@gmail.com'), supabase_admin.FAILED)
