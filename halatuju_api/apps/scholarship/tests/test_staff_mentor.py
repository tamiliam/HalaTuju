"""Student maintenance S7d (2026-11-01): a STAFF member may ALSO be a mentor, on the same login.

Doors, each driven through the real endpoints where one exists:

- ADD (`admin/mentors/staff/`): org_admin / admin / reviewer / qc of the caller's organisation only; finance,
  a super, a source user, a mentor login, a revoked row → refused; already a mentor → 409; another
  organisation's staff → 404; an admin (read-only) and a reviewer → 403. No email; no invitation.
- IN: the staff mentor reaches the 7c desk AND keeps every staff route of their role; a staff member
  WITHOUT a mentor record is refused the desk; `admin/role/` says `mentoring`.
- OUT, each ending the open assignments ("Mentor stopped mentoring", no email, a line on each file), the
  staff login exactly as it was unless the staff action itself changes it: Stop mentoring; People →
  Revoke; a staff invitation's Cancel; People → Delete (refused once they have mentored); Admin →
  Finance. Mentor again brings the mentor back, never an assignment; a Restore or a role change back
  brings nothing back.
- 7a's mentor doors refuse a staff mentor, and `_switch_off` is NEVER reached for one.
- A FINANCE ROW IS NEVER AN ACTIVE MENTOR through any door (lead ruling).
- READERS: the Mentors list's tag and counts, the student's tab (the phone only once switched on),
  the profile's rules (`works_with_students`, `mentoring_area`), the self-mentor rule.
"""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import invitations, mentor_invite, mentoring, staff_mentor
from apps.scholarship.models import (
    Invitation, Mentor, MentorAssignment, ReviewerProfile, StudentActivity,
)
from apps.scholarship.staff_contact import new_profile_defaults, works_with_students
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org, make_student,
)
from apps.scholarship.tests.test_mentoring import _scholar, make_mentor

MENTORS = '/api/v1/admin/mentors/'
STAFF = '/api/v1/admin/mentors/staff/'
DESK = '/api/v1/admin/mentor/students/'
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
SUPABASE = ('apps.courses.supabase_admin.kill_temp_password', 'apps.courses.supabase_admin.set_password',
            'apps.courses.supabase_admin.delete_auth_user', 'apps.courses.supabase_admin.issue_temp_password')


def tab(app_id):
    return f'/api/v1/admin/scholarship/scholars/{app_id}/mentoring/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@LOCMEM
class _Base(TestCase):
    def setUp(self):
        self.app = _scholar(student=make_student(name='NUR AISYAH', contact_email='aisyah@example.test'))
        self.org = self.app.owning_organisation
        self.lead = make_admin('org_admin', owning_org=self.org, name='Siti Rahmah')
        self.lead2 = make_admin('org_admin', owning_org=self.org)   # so a revoke is never the last one
        self.officer = make_admin('admin', owning_org=self.org, name='Encik Faizal')
        self.reviewer = make_admin('reviewer', owning_org=self.org, name='Ravi Kumar')
        self.qc = make_admin('qc', owning_org=self.org)
        self.finance = make_admin('finance', owning_org=self.org)
        self.kavitha = make_mentor(self.org)
        mail.outbox.clear()

    def add(self, target, caller=None):
        return authed_client(caller or self.lead).post(STAFF, {'admin_id': target.pk}, format='json')

    def added(self, target):
        r = self.add(target)
        self.assertEqual(r.status_code, 201, r.content)
        target.refresh_from_db()
        return target.mentor

    def act(self, mentor, action, caller=None):
        return authed_client(caller or self.lead).post(f'{MENTORS}{mentor.pk}/{action}/', {}, format='json')

    def assign(self, mentor, app=None):
        r = authed_client(self.lead).post(tab((app or self.app).id) + 'assign/',
                                          {'mentor_id': mentor.pk, 'email_student': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def open_count(self, mentor):
        return MentorAssignment.objects.filter(mentor=mentor, ended_at__isnull=True).count()

    def login_snapshot(self, login):
        login.refresh_from_db()
        return (login.is_active, login.role, login.supabase_user_id, login.email, login.permissions,
                login.paused_at, list(Invitation.objects.filter(partner_admin=login)
                                      .values_list('pk', 'revoked_at', 'accepted_at')))


class TestAdding(_Base):
    def test_an_eligible_staff_member_is_added_with_no_email(self):
        invites = Invitation.objects.count()
        before = self.login_snapshot(self.officer)
        r = self.add(self.officer)
        self.assertEqual(r.status_code, 201, r.content)
        row = r.json()
        self.assertEqual((row['staff_role'], row['status'], row['name']), ('admin', 'active', 'Encik Faizal'))
        self.officer.refresh_from_db()
        self.assertEqual(self.officer.mentor.organisation_id, self.org.pk)
        self.assertTrue(self.officer.mentors_now)
        self.assertTrue(self.officer.is_staff_mentor and not self.officer.is_mentor)
        self.assertEqual(self.login_snapshot(self.officer), before)   # role, sign-in, invitations untouched
        self.assertEqual(Invitation.objects.count(), invites)
        self.assertEqual(mail.outbox, [])

    def test_every_eligible_role(self):
        for who in (self.lead2, self.officer, self.reviewer, self.qc):
            self.assertEqual(self.add(who).status_code, 201, who.role)

    def test_the_candidates_are_the_eligible_staff_of_the_organisation(self):
        other = make_admin('reviewer', owning_org=make_org())
        revoked = make_admin('reviewer', owning_org=self.org, is_active=False)
        source = make_admin('source_partner', owning_org=self.org)
        self.added(self.qc)
        ids = {s['id'] for s in authed_client(self.lead).get(STAFF).json()['staff']}
        self.assertEqual(ids, {self.lead.pk, self.lead2.pk, self.officer.pk, self.reviewer.pk})
        for absent in (other, revoked, source, self.finance, self.qc, mentoring._login(self.kavitha)):
            self.assertNotIn(absent.pk, ids)

    def test_the_refusals(self):
        revoked = make_admin('reviewer', owning_org=self.org, is_active=False)
        source = make_admin('source_partner', owning_org=self.org)
        org_super = make_admin('super', owning_org=self.org, super_admin=True)
        for who in (self.finance, revoked, source, org_super, mentoring._login(self.kavitha)):
            r = self.add(who)
            self.assertEqual((r.status_code, r.json().get('code')), (400, 'not_eligible'), who.role)
            who.refresh_from_db()
            self.assertIsNone(who.mentor_id if who.role != 'mentor' else None)
        self.added(self.reviewer)
        r = self.add(self.reviewer)
        self.assertEqual((r.status_code, r.json().get('code')), (409, 'already_mentor'))
        # Stopped is still a mentor record: "Mentor again", never a second record.
        self.assertEqual(self.act(self.reviewer.mentor, 'stop').status_code, 200)
        self.assertEqual(self.add(self.reviewer).status_code, 409)
        self.assertEqual(Mentor.objects.filter(organisation=self.org).count(), 2)

    def test_who_may_add(self):
        other_lead = make_admin('org_admin', owning_org=make_org())
        self.assertEqual(self.add(self.reviewer, other_lead).status_code, 404)
        self.assertEqual(authed_client(other_lead).get(STAFF).json()['staff'][0]['id'], other_lead.pk)
        for caller in (self.officer, self.reviewer, self.qc, self.finance, mentoring._login(self.kavitha)):
            self.assertEqual(self.add(self.qc, caller).status_code, 403, caller.role)
            self.assertEqual(authed_client(caller).get(STAFF).status_code, 403, caller.role)
        sup = make_admin('super', super_admin=True)
        self.assertEqual(self.add(self.qc, sup).status_code, 201)
        self.qc.refresh_from_db()
        self.assertIsNotNone(self.qc.mentor_id)

    def test_a_bad_body(self):
        for body in ({}, {'admin_id': 'x'}, {'admin_id': True}):
            self.assertEqual(authed_client(self.lead).post(STAFF, body, format='json').status_code, 400)
        self.assertEqual(authed_client(self.lead).post(STAFF, {'admin_id': 999999}, format='json')
                         .status_code, 404)

    def test_an_existing_profile_stops_sharing_the_phone_unless_they_review(self):
        ReviewerProfile.objects.create(partner_admin=self.officer, phone='012-777 8899',
                                       share_phone_with_students=True)
        ReviewerProfile.objects.create(partner_admin=self.reviewer, phone='019-111 2222',
                                       share_phone_with_students=True)
        self.added(self.officer)
        self.added(self.reviewer)
        self.assertFalse(ReviewerProfile.objects.get(partner_admin=self.officer).share_phone_with_students)
        self.assertTrue(ReviewerProfile.objects.get(partner_admin=self.reviewer).share_phone_with_students)
        # A NEW profile for a staff mentor starts off too; a pure mentor keeps 7a's ON.
        self.assertEqual(new_profile_defaults(self.lead2), {'share_phone_with_students': False})
        self.added(self.lead2)
        self.assertEqual(new_profile_defaults(self.lead2), {'share_phone_with_students': False})
        self.assertEqual(new_profile_defaults(mentoring._login(self.kavitha)), {'share_phone_with_students': True})


class TestTheDesk(_Base):
    def test_a_staff_mentor_reaches_the_desk_and_keeps_their_staff_routes(self):
        mentor = self.added(self.officer)
        self.assign(mentor)
        client = authed_client(self.officer)
        r = client.get(DESK)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([s['id'] for s in r.json()['students']], [self.app.pk])
        self.assertEqual(client.get(f'{DESK}{self.app.pk}/').status_code, 200)
        r = client.post(f'{DESK}{self.app.pk}/sessions/', {'met_on': timezone.localdate().isoformat(),
                                                           'mode': 'video', 'notes': 'Hello.'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        # … and every staff page of an admin still answers.
        self.assertEqual(client.get('/api/v1/admin/admins/').status_code, 200)
        self.assertEqual(client.get(MENTORS).status_code, 200)
        self.assertEqual(client.get(tab(self.app.pk)).status_code, 200)
        role = client.get('/api/v1/admin/role/').json()
        self.assertEqual((role['role'], role['mentoring']), ('admin', True))

    def test_staff_without_a_mentor_record_are_refused_the_desk(self):
        for who in (self.lead, self.officer, self.reviewer, self.qc, self.finance):
            client = authed_client(who)
            self.assertEqual(client.get(DESK).status_code, 403, who.role)
            self.assertEqual(client.get(f'{DESK}{self.app.pk}/').status_code, 403, who.role)
            self.assertFalse(client.get('/api/v1/admin/role/').json()['mentoring'])

    def test_a_staff_mentor_never_mentors_themself(self):
        self.officer.email = 'aisyah@example.test'
        self.officer.save(update_fields=['email'])
        mentor = self.added(self.officer)
        r = authed_client(self.lead).post(tab(self.app.id) + 'assign/', {'mentor_id': mentor.pk}, format='json')
        self.assertEqual(r.json().get('code'), 'own_application')

    def test_a_pause_keeps_mentoring(self):
        mentor = self.added(self.reviewer)
        self.assign(mentor)
        PartnerAdmin.objects.filter(pk=self.reviewer.pk).update(paused_at=timezone.now())
        self.reviewer.refresh_from_db()
        self.assertTrue(self.reviewer.mentors_now)
        self.assertEqual(authed_client(self.reviewer).get(DESK).json()['students'][0]['id'], self.app.pk)


class TestTheWaysOut(_Base):
    def _stopped(self, mentor, login):
        mentor.refresh_from_db()
        login.refresh_from_db()
        self.assertIsNotNone(mentor.deactivated_at)
        self.assertEqual(self.open_count(mentor), 0)
        self.assertFalse(login.mentors_now)
        ended = MentorAssignment.objects.filter(mentor=mentor).latest('id')
        self.assertEqual(ended.end_reason, mentoring.REASON_STOPPED)
        line = StudentActivity.objects.filter(application=self.app, event='mentor_ended').latest('id')
        self.assertEqual(line.meta['cause'], 'mentor_stopped')
        self.assertEqual(mail.outbox, [])
        self.assertEqual(authed_client(login).get(DESK).status_code, 403)

    def test_stop_mentoring_never_touches_the_staff_login(self):
        mentor = self.added(self.officer)
        self.assign(mentor)
        before = self.login_snapshot(self.officer)
        with patch(SUPABASE[0]) as kill, patch(SUPABASE[1]) as setpw, patch(SUPABASE[2]) as drop, \
                patch(SUPABASE[3]) as issue:
            r = self.act(mentor, 'stop')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['status'], r.json()['ended']), ('inactive', 1))
        for m in (kill, setpw, drop, issue):
            m.assert_not_called()
        self.assertEqual(self.login_snapshot(self.officer), before)
        self._stopped(mentor, self.officer)
        self.assertEqual(authed_client(self.officer).get('/api/v1/admin/admins/').status_code, 200)
        self.assertEqual(self.act(mentor, 'stop').json().get('code'), 'not_active')

    def test_mentor_again_restores_the_mentor_and_no_assignment(self):
        mentor = self.added(self.officer)
        self.assign(mentor)
        self.act(mentor, 'stop')
        r = self.act(mentor, 'resume')
        self.assertEqual((r.status_code, r.json()['status']), (200, 'active'))
        self.officer.refresh_from_db()
        self.assertTrue(self.officer.mentors_now)
        self.assertEqual(self.open_count(mentor), 0)
        self.assertEqual(self.act(mentor, 'resume').json().get('code'), 'active')
        self.assertEqual(mail.outbox, [])

    def test_seven_a_doors_refuse_a_staff_mentor_and_switch_off_is_never_reached(self):
        mentor = self.added(self.officer)
        before = self.login_snapshot(self.officer)
        with patch.object(mentor_invite, '_switch_off', side_effect=AssertionError('reached')) as off:
            for action in ('deactivate', 'revoke', 'resend', 'reactivate'):
                r = self.act(mentor, action)
                self.assertEqual((r.status_code, r.json().get('code')), (400, 'staff_mentor'), action)
            r = authed_client(self.lead).patch(f'{MENTORS}{mentor.pk}/', {'name': 'X'}, format='json')
            self.assertEqual((r.status_code, r.json().get('code')), (400, 'staff_mentor'))
            # … and the functions themselves, should any later door call them.
            self.assertEqual(mentor_invite.deactivate(self.lead, mentor, self.officer), (False, 'staff_mentor'))
            self.assertEqual(mentor_invite.revoke_invite(self.lead, mentor, self.officer), (False, 'staff_mentor'))
            self.assertEqual(mentor_invite.reactivate(self.lead, mentor, self.officer)[2], 'staff_mentor')
            self.assertEqual(mentor_invite.resend_invite(self.lead, mentor, self.officer)[1], 'staff_mentor')
            self.assertEqual(mentor_invite.edit(self.lead, mentor, self.officer, name='X')[2], 'staff_mentor')
            off.assert_not_called()
        self.assertEqual(mentor_invite._switch_off(self.lead, mentor, self.officer), (False, 'staff_mentor'))
        self.assertEqual(self.login_snapshot(self.officer), before)
        mentor.refresh_from_db()
        self.assertIsNone(mentor.deactivated_at)

    def test_a_pure_mentor_keeps_its_own_doors(self):
        for action in ('stop', 'resume'):
            r = self.act(self.kavitha, action)
            self.assertEqual((r.status_code, r.json().get('code')), (400, 'not_staff'))

    def test_a_revoke_stops_mentoring_and_a_restore_does_not_bring_it_back(self):
        mentor = self.added(self.officer)
        self.assign(mentor)
        r = authed_client(self.lead).patch(f'/api/v1/admin/admins/{self.officer.pk}/revoke/',
                                           {'action': 'revoke'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self._stopped(mentor, self.officer)
        self.assertFalse(self.officer.is_active)   # the staff action's own change
        authed_client(self.lead).patch(f'/api/v1/admin/admins/{self.officer.pk}/revoke/',
                                       {'action': 'restore'}, format='json')
        self.officer.refresh_from_db()
        mentor.refresh_from_db()
        self.assertTrue(self.officer.is_active)
        self.assertIsNotNone(mentor.deactivated_at)
        self.assertFalse(self.officer.mentors_now)
        self.assertEqual(self.act(mentor, 'resume').status_code, 200)   # by hand, it can

    def test_mentor_again_is_refused_for_a_revoked_login(self):
        mentor = self.added(self.reviewer)
        authed_client(self.lead).patch(f'/api/v1/admin/admins/{self.reviewer.pk}/revoke/',
                                       {'action': 'revoke'}, format='json')
        self.assertEqual(self.act(mentor, 'resume').json().get('code'), 'not_eligible')

    def test_cancelling_a_staff_invitation_stops_mentoring(self):
        invitee = make_admin('reviewer', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=invitee.pk).update(first_seen_at=None)
        inv = invitations.create_or_refresh(audience='staff', email=invitee.email, name=invitee.name,
                                            role='reviewer', organisation=self.org, partner_admin=invitee,
                                            invited_by=self.lead, credential_issued=False)
        mentor = self.added(invitee)
        self.assign(mentor)
        r = authed_client(self.lead).post(f'/api/v1/admin/invitations/{inv.pk}/cancel/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self._stopped(mentor, invitee)

    def test_a_re_invite_of_a_switched_off_staff_mentor_is_a_new_start(self):
        from apps.courses import staff_reinvite
        invitee = make_admin('admin', owning_org=self.org)
        mentor = self.added(invitee)
        staff_mentor.leave(invitee, by='x')
        PartnerAdmin.objects.filter(pk=invitee.pk).update(is_active=False, first_seen_at=None,
                                                          supabase_user_id=None)
        invitee.refresh_from_db()
        # Even to a role or an organisation the old mentor record could never bind to.
        row, _, err = staff_reinvite.bring_back(invitee, name='N', role='partner', org=None,
                                                owning_org=make_org(), temp_password=None)
        self.assertIsNone(err)
        self.assertIsNone(row.mentor_id)
        self.assertFalse(row.mentors_now)
        mentor.refresh_from_db()
        self.assertIsNotNone(mentor.deactivated_at)

    def test_delete_is_refused_once_they_have_mentored(self):
        mentor = self.added(self.officer)
        self.assign(mentor)
        self.act(mentor, 'stop')
        r = authed_client(self.lead).delete(f'/api/v1/admin/admins/{self.officer.pk}/')
        self.assertEqual((r.status_code, r.json().get('code')), (409, 'has_work'))
        self.assertEqual(r.json()['work'], {'scholars_mentored': 1})
        self.assertTrue(PartnerAdmin.objects.filter(pk=self.officer.pk).exists())

    def test_a_never_assigned_staff_mentor_may_be_deleted(self):
        mentor = self.added(self.officer)
        r = authed_client(self.lead).delete(f'/api/v1/admin/admins/{self.officer.pk}/')
        self.assertEqual(r.status_code, 200, r.content)
        mentor.refresh_from_db()
        self.assertIsNotNone(mentor.deactivated_at)
        listed = {m['id'] for m in authed_client(self.lead).get(MENTORS).json()['mentors']}
        self.assertNotIn(mentor.pk, listed)

    def test_admin_to_finance_stops_mentoring_and_keeps_the_link(self):
        mentor = self.added(self.officer)
        self.assign(mentor)
        url = f'/api/v1/admin/admins/{self.officer.pk}/role/'
        dry = authed_client(self.lead).patch(url, {'role': 'finance', 'dry_run': True}, format='json')
        self.assertTrue(dry.json()['stops_mentoring'])
        self.assertEqual(self.open_count(mentor), 1)   # a dry run writes nothing
        r = authed_client(self.lead).patch(url, {'role': 'finance'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self._stopped(mentor, self.officer)
        self.assertEqual((self.officer.role, self.officer.mentor_id), ('finance', mentor.pk))
        # The history keeps the mentor's name (the login is kept).
        hist = authed_client(self.lead).get(tab(self.app.pk)).json()['history']
        self.assertEqual(hist[0]['name'], 'Encik Faizal')
        self.assertEqual(self.act(mentor, 'resume').json().get('code'), 'not_eligible')
        # Back to Admin brings nothing back by itself; Mentor again does.
        authed_client(self.lead).patch(url, {'role': 'admin'}, format='json')
        self.officer.refresh_from_db()
        self.assertFalse(self.officer.mentors_now)
        self.assertEqual(self.act(mentor, 'resume').status_code, 200)

    def test_reviewer_to_qc_keeps_mentoring(self):
        mentor = self.added(self.reviewer)
        self.assign(mentor)
        url = f'/api/v1/admin/admins/{self.reviewer.pk}/role/'
        self.assertFalse(authed_client(self.lead).patch(url, {'role': 'qc', 'dry_run': True},
                                                        format='json').json()['stops_mentoring'])
        self.assertEqual(authed_client(self.lead).patch(url, {'role': 'qc'}, format='json').status_code, 200)
        self.reviewer.refresh_from_db()
        self.assertTrue(self.reviewer.mentors_now)
        self.assertEqual(self.open_count(mentor), 1)


class TestFinanceIsNeverAnActiveMentor(_Base):
    """Lead ruling 2026-11-01: a finance row may KEEP a link (deactivated), never an active mentor."""

    def test_through_every_door(self):
        # Add: refused.
        self.assertEqual(self.add(self.finance).json().get('code'), 'not_eligible')
        # The role change: deactivated in the same write.
        mentor = self.added(self.officer)
        authed_client(self.lead).patch(f'/api/v1/admin/admins/{self.officer.pk}/role/', {'role': 'finance'},
                                       format='json')
        mentor.refresh_from_db()
        self.assertIsNotNone(mentor.deactivated_at)
        # Mentor again: refused, and nothing written.
        self.assertEqual(self.act(mentor, 'resume').json().get('code'), 'not_eligible')
        mentor.refresh_from_db()
        self.assertIsNotNone(mentor.deactivated_at)
        # 7a's Reactivate: refused (a staff login).
        self.assertEqual(self.act(mentor, 'reactivate').json().get('code'), 'staff_mentor')
        # Even with the mentor record forced active, the readers say no.
        Mentor.objects.filter(pk=mentor.pk).update(deactivated_at=None)
        self.officer.refresh_from_db()
        self.assertFalse(self.officer.mentors_now)
        self.assertFalse(works_with_students(self.officer))
        self.assertEqual(authed_client(self.officer).get(DESK).status_code, 403)
        self.assertFalse(authed_client(self.officer).get('/api/v1/admin/role/').json()['mentoring'])
        self.assertNotIn(mentor.pk, [m['id'] for m in mentoring.assignable_mentors(self.app)])
        self.assertEqual(mentoring.refusal_for_mentor(self.app, mentor), 'mentor_inactive')


class TestTheReaders(_Base):
    def test_the_mentors_list_tags_and_counts(self):
        mentor = self.added(self.officer)
        self.assign(mentor)
        rows = {m['id']: m for m in authed_client(self.lead).get(MENTORS).json()['mentors']}
        self.assertEqual((rows[mentor.pk]['staff_role'], rows[mentor.pk]['scholars_now'],
                          rows[mentor.pk]['manageable']), ('admin', 1, True))
        self.assertIsNone(rows[self.kavitha.pk]['staff_role'])
        self.act(mentor, 'stop')
        body = authed_client(self.lead).get(MENTORS).json()
        self.assertEqual({m['id']: m['status'] for m in body['mentors']}[mentor.pk], 'inactive')
        self.assertEqual(body['counts']['inactive'], 1)
        # An admin reads the list and the tag, and acts on nothing.
        row = [m for m in authed_client(self.officer).get(MENTORS).json()['mentors'] if m['id'] == mentor.pk][0]
        self.assertFalse(row['manageable'])
        self.assertEqual(self.act(mentor, 'resume', self.officer).status_code, 403)

    def test_the_student_sees_the_phone_only_once_switched_on(self):
        ReviewerProfile.objects.create(partner_admin=self.officer, phone='012-777 8899', about='Programme lead.',
                                       english_fluency='fluent', share_phone_with_students=True)
        mentor = self.added(self.officer)
        self.assign(mentor)
        student = authed_client(self.app.profile.supabase_user_id)
        body = student.get('/api/v1/scholarship/bursary/mentoring/').json()
        self.assertEqual(set(body['mentor']), {'name', 'area', 'languages', 'other_language', 'about', 'email',
                                               'phone', 'since'})   # 7b's allowlist, unchanged
        self.assertEqual((body['mentor']['name'], body['mentor']['phone'], body['mentor']['about']),
                         ('Encik Faizal', '', 'Programme lead.'))
        r = authed_client(self.officer).patch('/api/v1/admin/me/', {'share_phone_with_students': True},
                                              format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(student.get('/api/v1/scholarship/bursary/mentoring/').json()['mentor']['phone'],
                         '012-777 8899')

    def test_the_profile_rules(self):
        client = authed_client(self.officer)
        self.assertNotIn('mentoring_area', client.get('/api/v1/admin/me/').json())
        self.assertEqual(client.patch('/api/v1/admin/me/', {'mentoring_area': 'X'}, format='json')
                         .json().get('code'), 'not_editable')
        self.assertEqual(client.get('/api/v1/admin/reviewer-profile/').status_code, 403)
        mentor = self.added(self.officer)
        me = client.get('/api/v1/admin/me/').json()
        self.assertEqual((me['mentoring_area'], me['share_phone_with_students'], me['role']), ('', False, 'admin'))
        r = client.patch('/api/v1/admin/me/', {'mentoring_area': 'Accounting, finance'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        mentor.refresh_from_db()
        self.assertEqual(mentor.area, 'Accounting, finance')
        self.assertEqual(client.patch('/api/v1/admin/me/', {'phone': ''}, format='json').json().get('code'),
                         'phone_required')
        self.assertEqual(client.get('/api/v1/admin/reviewer-profile/').status_code, 200)
        self.assertEqual(client.patch('/api/v1/admin/reviewer-profile/', {'paused': True}, format='json')
                         .json().get('code'), 'not_reviewable')
        # Stopped: back to their staff rule.
        self.act(mentor, 'stop')
        self.assertEqual(client.patch('/api/v1/admin/me/', {'phone': ''}, format='json').status_code, 200)
        self.assertEqual(client.get('/api/v1/admin/reviewer-profile/').status_code, 403)

    def test_the_mentoring_tab_names_the_staff_mentor(self):
        mentor = self.added(self.officer)
        self.assign(mentor)
        current = authed_client(self.lead).get(tab(self.app.pk)).json()['current']
        self.assertEqual((current['mentor_id'], current['name'], current['status']),
                         (mentor.pk, 'Encik Faizal', 'active'))
        offered = [m['id'] for m in mentoring.assignable_mentors(self.app)]
        self.assertIn(mentor.pk, offered)
        self.act(mentor, 'stop')
        self.assertNotIn(mentor.pk, [m['id'] for m in mentoring.assignable_mentors(self.app)])

    def test_leave_writes_nothing_for_anybody_but_a_staff_mentor(self):
        mentor = self.added(self.officer)
        self.assertEqual(staff_mentor.leave(self.reviewer), 0)
        self.assertEqual(staff_mentor.leave(mentoring._login(self.kavitha)), 0)
        self.kavitha.refresh_from_db()
        self.assertIsNone(self.kavitha.deactivated_at)
        self.assertEqual(PartnerAdmin.objects.filter(mentor=mentor).count(), 1)
