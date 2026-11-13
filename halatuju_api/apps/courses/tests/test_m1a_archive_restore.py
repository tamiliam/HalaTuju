"""Sprint M1a (2026-11-10): Delete as archive, and the re-invite that restores the same row (owner O7).

Brief `docs/plans/2026-11-10-m1-staff-list-brief.md` §5 and §12. The staff door (`AdminDeleteView` with
`{"archive": true}`, `staff_archive`) and the mentor door (`AdminMentorDetailView.delete`,
`mentor_archive`): no records → erased as today; records and no flag → today's 409 `has_work`; records
and the flag → archived (row, name, footprint kept; login retired; invitations cancelled; off by id);
anything still waiting on them → 409 `has_unfinished_work`. A re-invite of an archived address brings
back THE SAME ROW with a new login, and QC separation still knows them. Every Supabase call is mocked.
"""
import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_reinvite, staff_tables
from apps.courses.models import PartnerAdmin
from apps.scholarship import invitations, qc_separation
from apps.scholarship.models import (
    Invitation, Mentor, MentorAssignment, PaymentRun, ScholarshipApplication, StaffActivity,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_org, unique_suffix,
)

READ = 'apps.courses.supabase_admin.read_auth_user'
DELETE = 'apps.courses.supabase_admin.delete_auth_user'
NEW_LOGIN = 'apps.courses.staff_reinvite._new_login'
PLAN = 'apps.scholarship.staff_lifecycle.plan_login_retirement'
SUPABASE = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                SUPABASE_URL='https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY='svc-key')
ARCHIVE = {'archive': True}


def _unused(uid):
    login = PartnerAdmin.objects.filter(supabase_user_id=uid).first()
    return {'id': uid, 'email': login.email if login else '', 'last_sign_in_at': None,
            'identities': [{'provider': 'email'}], 'app_metadata': {'must_change_password': True}}


def no_group(target):
    """Sprint M2c (owner R2): Delete only from "No group". The end state of the Removes, set directly: a
    staff row becomes a `member` with no keys, and its Mentor (if any) is stamped deactivated."""
    if target.mentor_id:
        Mentor.objects.filter(pk=target.mentor_id).update(deactivated_at=timezone.now())
    if not target.is_mentor:
        PartnerAdmin.objects.filter(pk=target.pk).update(role=PartnerAdmin.MEMBER_ROLE, permissions=None)
    target.refresh_from_db()
    return target


def _reviewed(target, app=None):
    """A closed trace (footprint, nothing waiting): ``target`` recorded a verdict on ``app``."""
    app = app or make_application('submitted')
    StaffActivity.objects.create(actor=target, verb='verdict_recorded', subject_type='application',
                                 subject_id=app.pk)
    return app


@override_settings(**SUPABASE)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)

    def delete(self, caller, target, body=None, url=None):
        with patch(READ, side_effect=_unused), patch(DELETE, return_value='deleted') as gone:
            r = authed_client(caller).delete(url or f'/api/v1/admin/admins/{target.pk}/', body,
                                             format='json')
        self.gone = gone
        return r

    def invite(self, caller, email, *, role='reviewer', name='Kavitha Back', new_login=('uid-new', False, None)):
        body = {'email': email, 'name': name, 'role': role, 'gift_scope': 'every'}
        with patch(NEW_LOGIN, return_value=new_login):
            return authed_client(caller).post('/api/v1/admin/invite/', body, format='json')


# Sprint M2c: public names for a test in another app (`test_cross_app_private_imports` refuses a `_x` there).
ArchiveCase, reviewed = _Base, _reviewed


class TestStaffDeleteErasesOrArchives(_Base):
    def test_no_records_is_erased_as_today_even_with_the_flag(self):
        target = make_admin('reviewer', owning_org=self.org)
        r = self.delete(self.lead, target, ARCHIVE)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn('archived', r.json())
        self.assertFalse(PartnerAdmin.objects.filter(pk=target.pk).exists())

    def test_records_without_the_flag_keep_today_s_409(self):
        target = make_admin('reviewer', owning_org=self.org)
        _reviewed(target)
        r = self.delete(self.lead, target)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'has_work'))
        target.refresh_from_db()
        self.assertIsNone(target.archived_at)
        self.gone.assert_not_called()

    def test_records_with_the_flag_archive_the_row(self):
        target = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())
        uid = target.supabase_user_id
        _reviewed(no_group(target))
        inv = invitations.create_or_refresh(audience='staff', email=target.email, name=target.name,
                                            role='reviewer', organisation=self.org, invited_by=self.lead,
                                            partner_admin=target)
        with self.assertLogs('apps.courses.views_admin', 'INFO') as logs:
            r = self.delete(self.lead, target, ARCHIVE)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['archived'], r.json()['login']), (True, 'deleted'))
        self.assertTrue(any('AUDIT staff_archived' in line for line in logs.output))
        target.refresh_from_db()
        self.assertIsNotNone(target.archived_at)
        self.assertEqual((target.is_active, target.supabase_user_id, target.archived_by_email),
                         (False, None, self.lead.email))
        self.assertEqual(target.role, 'member')                      # kept as it was (M2c: "No group")
        self.assertEqual(StaffActivity.objects.filter(actor=target).count(), 1)
        self.gone.assert_called_once()
        self.assertEqual(self.gone.call_args[0][0], uid)
        inv.refresh_from_db()
        self.assertIsNotNone(inv.revoked_at)

    def test_a_staff_mentor_s_mentor_is_switched_off_and_the_link_kept(self):
        mentor = Mentor.objects.create(organisation=self.org)
        target = make_admin('reviewer', owning_org=self.org, mentor=mentor)
        _reviewed(target)
        self.assertEqual(self.delete(self.lead, target, ARCHIVE).status_code, 200)
        target.refresh_from_db()
        mentor.refresh_from_db()
        self.assertEqual(target.mentor_id, mentor.pk)
        self.assertIsNotNone(mentor.deactivated_at)

    def test_self_delete_is_refused_with_or_without_the_flag(self):
        for body in (None, ARCHIVE):
            with self.subTest(body=body):
                r = self.delete(self.lead, self.lead, body)
                self.assertEqual((r.status_code, r.json()['code']), (403, 'self'))
        self.assertTrue(PartnerAdmin.objects.filter(pk=self.lead.pk, archived_at__isnull=True).exists())

    def test_only_json_true_asks_for_an_archive(self):
        target = make_admin('reviewer', owning_org=self.org)
        _reviewed(target)
        for value in ('true', 1, 'yes'):
            with self.subTest(value=value):
                r = self.delete(self.lead, target, {'archive': value})
                self.assertEqual(r.json()['code'], 'has_work')

    def test_the_sole_org_admin_is_never_archived(self):
        org = make_org()
        sole = make_admin('org_admin', owning_org=org)
        _reviewed(sole)
        r = self.delete(self.super, sole, ARCHIVE)
        self.assertNotEqual(r.status_code, 200)
        sole.refresh_from_db()
        self.assertIsNone(sole.archived_at)

    def test_a_login_that_cannot_be_checked_writes_nothing(self):
        target = make_admin('reviewer', owning_org=self.org)
        _reviewed(target)
        with patch(PLAN, return_value=('failed', None)):
            r = self.delete(self.lead, target, ARCHIVE)
        self.assertEqual((r.status_code, r.json()['code']), (502, 'login_cleanup_failed'))
        target.refresh_from_db()
        self.assertIsNone(target.archived_at)
        self.assertTrue(target.is_active)


class TestUnfinishedWorkRefusesDelete(_Base):
    """Owner O7: refused while anything is still waiting on them in ANY group; nothing is written."""

    def _refused(self, target, group, field):
        r = self.delete(self.lead, target, ARCHIVE)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'has_unfinished_work'), r.content)
        self.assertGreaterEqual(r.json()['work'][group][field], 1)
        target.refresh_from_db()
        self.assertIsNone(target.archived_at)
        self.assertTrue(target.is_active)
        self.gone.assert_not_called()

    def test_an_open_case(self):
        target = make_admin('reviewer', owning_org=self.org)
        make_application('assigned', reviewer=target)
        self._refused(target, 'reviewers', 'open_cases')

    def test_a_payment_run_in_progress(self):
        target = make_admin('admin', owning_org=self.org)
        PaymentRun.objects.create(organisation=self.org, payment_date=datetime.date(2026, 9, 1),
                                  reference=unique_suffix('M1A-'), created_by=target.email)
        self._refused(target, 'admins', 'runs_in_progress')

    def test_a_scholar_mentored_now(self):
        mentor = Mentor.objects.create(organisation=self.org)
        target = make_admin('reviewer', owning_org=self.org, mentor=mentor)
        MentorAssignment.objects.create(application=make_application('active'), mentor=mentor)
        self._refused(target, 'mentors', 'scholars_now')


class TestAnArchivedRowIsOutOfReach(_Base):
    def setUp(self):
        self.target = make_admin('reviewer', owning_org=self.org)
        _reviewed(self.target)
        self.assertEqual(self.delete(self.lead, self.target, ARCHIVE).status_code, 200)

    def test_every_door_by_id_answers_404(self):
        client = authed_client(self.super)
        pk = self.target.pk
        doors = [
            ('delete', f'/api/v1/admin/admins/{pk}/', ARCHIVE),
            ('patch', f'/api/v1/admin/admins/{pk}/revoke/', {'action': 'restore'}),
            ('post', f'/api/v1/admin/admins/{pk}/resend/', {}),
            ('get', f'/api/v1/admin/admins/{pk}/permissions/', None),
            ('patch', f'/api/v1/admin/admins/{pk}/role/', {'role': 'admin'}),
            ('post', '/api/v1/admin/team/admins/', {'admin_id': pk, 'action': 'add'}),
        ]
        for method, url, body in doors:
            with self.subTest(method=method, url=url):
                r = getattr(client, method)(url, body, format='json')
                self.assertEqual(r.status_code, 404, r.content[:200])
        self.target.refresh_from_db()
        self.assertEqual((self.target.role, self.target.is_active), ('reviewer', False))


class TestReinviteRestoresTheSameRow(_Base):
    def _archived(self, role='reviewer', **kw):
        target = make_admin(role, owning_org=self.org, first_seen_at=timezone.now(),
                            permissions=['review', 'spending'], **kw)
        app = _reviewed(no_group(target))
        self.assertEqual(self.delete(self.lead, target, ARCHIVE).status_code, 200)
        target.refresh_from_db()
        return target, app

    def test_the_same_row_comes_back_with_a_new_login_and_fresh_defaults(self):
        target, _ = self._archived()
        with self.assertLogs('apps.courses.views_admin', 'INFO') as logs:
            r = self.invite(self.lead, target.email, role='admin', name='Kavitha Again')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(any('AUDIT staff_restored' in line for line in logs.output))
        self.assertEqual(PartnerAdmin.objects.filter(email__iexact=target.email).count(), 1)
        row = PartnerAdmin.objects.get(pk=target.pk)
        self.assertIsNone(row.archived_at)
        self.assertEqual((row.is_active, row.supabase_user_id, row.first_seen_at, row.role, row.name),
                         (True, 'uid-new', None, 'admin', 'Kavitha Again'))
        self.assertEqual(row.permissions, staff_tables.invite_permissions('admin'))
        self.assertEqual(StaffActivity.objects.filter(actor=row).count(), 1)   # history still theirs
        waiting = invitations.open_only(Invitation.objects.filter(partner_admin=row))
        self.assertEqual(waiting.count(), 1)

    def test_a_google_address_comes_back_without_a_login_until_they_sign_in(self):
        target, _ = self._archived()
        PartnerAdmin.objects.filter(pk=target.pk).update(email='kavitha.m1a@gmail.com')
        r = self.invite(self.lead, 'kavitha.m1a@gmail.com')
        self.assertEqual(r.status_code, 201, r.content)
        row = PartnerAdmin.objects.get(pk=target.pk)
        self.assertEqual((row.is_active, row.supabase_user_id, row.archived_at), (True, None, None))

    def test_another_organisation_cannot_restore_them(self):
        target, _ = self._archived()
        other_lead = make_admin('org_admin', owning_org=make_org())
        r = self.invite(other_lead, target.email)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'not_invitable'))
        target.refresh_from_db()
        self.assertIsNotNone(target.archived_at)

    def test_bring_back_never_takes_an_archived_row(self):
        target, _ = self._archived()
        account, _, err = staff_reinvite.bring_back(target, name='X', role='reviewer', org=None,
                                                    owning_org=self.org)
        self.assertEqual((account, err), (None, 'not_reusable'))
        target.refresh_from_db()
        self.assertIsNotNone(target.archived_at)

    def test_qc_separation_survives_archive_and_restore(self):
        target, app = self._archived()
        app = ScholarshipApplication.objects.get(pk=app.pk)
        r = self.invite(self.super, target.email, role='qc')
        self.assertEqual(r.status_code, 201, r.content)
        row = PartnerAdmin.objects.get(pk=target.pk)
        self.assertEqual(row.role, 'qc')
        self.assertEqual(qc_separation.refusal(row, app), qc_separation.SELF_REVIEW)
        self.assertIn(app.pk, qc_separation.barred_ids(row, ScholarshipApplication.objects.all()))


class TestMentorDoorArchiveAndRestore(_Base):
    def _mentor(self, *, open_assignment=False):
        login = make_admin('mentor', owning_org=self.org, first_seen_at=timezone.now())
        MentorAssignment.objects.create(application=make_application('active'), mentor=login.mentor,
                                        ended_at=None if open_assignment else timezone.now())
        return login if open_assignment else no_group(login)   # M2c (R2): Deactivated before a Delete

    def _delete_mentor(self, login, body=None):
        return self.delete(self.lead, login, body, url=f'/api/v1/admin/mentors/{login.mentor_id}/')

    def test_without_the_flag_today_s_409_stands(self):
        login = self._mentor()
        r = self._delete_mentor(login)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'has_work'))

    def test_with_the_flag_the_login_is_archived_and_the_mentor_kept_switched_off(self):
        login = self._mentor()
        r = self._delete_mentor(login, ARCHIVE)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['archived'])
        login.refresh_from_db()
        mentor = Mentor.objects.get(pk=login.mentor_id)
        self.assertIsNotNone(login.archived_at)
        self.assertEqual((login.is_active, login.supabase_user_id), (False, None))
        self.assertIsNotNone(mentor.deactivated_at)
        self.gone.assert_called_once()

    def test_a_scholar_mentored_now_refuses(self):
        # M2c (owner R2): a scholar now keeps them in Mentors, and "in a group" is asked first.
        login = self._mentor(open_assignment=True)
        r = self._delete_mentor(login, ARCHIVE)
        self.assertEqual((r.status_code, r.json()['code'], r.json()['groups']), (409, 'in_a_group', ['mentors']))
        login.refresh_from_db()
        self.assertIsNone(login.archived_at)

    def _mentor_invite(self, caller, email):
        body = {'audience': 'mentor', 'name': 'Arul Back', 'email': email}
        with patch(NEW_LOGIN, return_value=('uid-mentor-new', False, None)):
            return authed_client(caller).post('/api/v1/admin/invitations/', body, format='json')

    def test_the_mentor_invite_restores_the_same_login_and_mentor(self):
        login = self._mentor()
        self.assertEqual(self._delete_mentor(login, ARCHIVE).status_code, 200)
        r = self._mentor_invite(self.lead, login.email)
        self.assertEqual(r.status_code, 201, r.content)
        row = PartnerAdmin.objects.get(pk=login.pk)
        mentor = Mentor.objects.get(pk=login.mentor_id)
        self.assertEqual((row.archived_at, row.is_active, row.supabase_user_id, row.first_seen_at),
                         (None, True, 'uid-mentor-new', None))
        self.assertEqual((row.mentor_id, mentor.deactivated_at), (mentor.pk, None))
        self.assertEqual(Mentor.objects.filter(organisation=self.org).count(), 1)
        self.assertEqual(MentorAssignment.objects.filter(mentor=mentor).count(), 1)   # history kept

    def test_an_archived_staff_member_is_sent_to_the_staff_invite(self):
        target = make_admin('reviewer', owning_org=self.org)
        _reviewed(target)
        self.assertEqual(self.delete(self.lead, target, ARCHIVE).status_code, 200)
        r = self._mentor_invite(self.lead, target.email)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'use_staff_invite'))
        target.refresh_from_db()
        self.assertIsNotNone(target.archived_at)

    def test_another_organisation_s_archived_mentor_is_already_staff(self):
        login = self._mentor()
        self.assertEqual(self._delete_mentor(login, ARCHIVE).status_code, 200)
        other_lead = make_admin('org_admin', owning_org=make_org())
        r = self._mentor_invite(other_lead, login.email)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_staff'))
