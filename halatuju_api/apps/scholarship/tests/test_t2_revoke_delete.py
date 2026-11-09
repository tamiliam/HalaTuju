"""Sprint T2 (owner, 2026-11-08; ruling D6): Revoke and Delete on every team table and person page.

*"Each must have Revoke and Delete. The delete however will be greyed out if there is work on record
... For org admins, the delete button should be visible only to super admin."* D6 REVERSES the
2026-09-09 "never delete a reviewer": reviewers, QC and mentors are deletable under the SAME test as an
admin — no work on record (`staff_footprint`).

The matrix: a super / an organisation admin deleting an admin / finance / reviewer / QC / organisation
admin / mentor, each with and without work. Then the payloads (`deletable` + `work` on all three
tables and the person pages) and the mentor door's own rules: a refused delete leaves every row; a
delete removes the login, the mentor record and its invitations together; a staff member who also
mentors is deleted from the staff door, where their mentoring is work. Every Supabase call is mocked.
"""
import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import (
    Invitation, Mentor, MentorAssignment, MentoringSession, PaymentRun, StaffActivity,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_org, unique_suffix,
)

READ = 'apps.courses.supabase_admin.read_auth_user'
DELETE = 'apps.courses.supabase_admin.delete_auth_user'
SUPABASE = dict(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                SUPABASE_URL='https://x.supabase.co', SUPABASE_SERVICE_ROLE_KEY='svc-key')


def _unused(uid):
    """GoTrue's answer for a login we provisioned and nobody has used — so the delete removes it."""
    login = PartnerAdmin.objects.filter(supabase_user_id=uid).first()
    return {'id': uid, 'email': login.email if login else '', 'last_sign_in_at': None,
            'identities': [{'provider': 'email'}], 'app_metadata': {'must_change_password': True}}


def _give_work(target):
    """One trace of the work each role really leaves; returns the footprint key it shows under."""
    if target.role == 'reviewer':
        make_application('assigned', reviewer=target)
        return 'assigned_applications'
    if target.role == 'qc':
        StaffActivity.objects.create(actor=target, verb='qc_decision')
        return 'qc_decisions'
    if target.role == 'mentor':
        app = make_application('submitted')
        MentorAssignment.objects.create(application=app, mentor=target.mentor)
        return 'scholars_mentored'
    field = {'admin': 'created_by', 'finance': 'finance_signed_email',
             'org_admin': 'org_admin_signed_email'}[target.role]
    PaymentRun.objects.create(organisation=target.owning_organisation,
                              payment_date=datetime.date(2026, 9, 1), reference=unique_suffix('T2-'),
                              **{field: target.email})
    return {'admin': 'payment_runs_made', 'finance': 'payment_runs_checked',
            'org_admin': 'payment_runs_countersigned'}[target.role]


def _url(target):
    if target.role == 'mentor':
        return f'/api/v1/admin/mentors/{target.mentor_id}/'
    return f'/api/v1/admin/admins/{target.pk}/'


@override_settings(**SUPABASE)
class TestTheDeleteMatrix(TestCase):
    """super / org_admin caller × admin / finance / reviewer / qc / org_admin / mentor × work / none."""

    ROLES = ('admin', 'finance', 'reviewer', 'qc', 'org_admin', 'mentor')

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)

    def _delete(self, caller, target):
        with patch(READ, side_effect=_unused), patch(DELETE, return_value='deleted') as gone:
            r = authed_client(caller).delete(_url(target))
        return r, gone

    def _expected(self, caller, role, worked):
        if caller.role == 'org_admin' and role == 'org_admin':
            return 404     # a fellow organisation admin: only a super deletes one (no existence leak)
        return 409 if worked else 200

    def test_the_matrix(self):
        for caller in (self.super, self.lead):
            for role in self.ROLES:
                for worked in (False, True):
                    with self.subTest(caller=caller.role, target=role, work=worked):
                        target = make_admin(role, owning_org=self.org)
                        mentor_id = target.mentor_id
                        key = _give_work(target) if worked else None
                        r, gone = self._delete(caller, target)
                        want = self._expected(caller, role, worked)
                        self.assertEqual(r.status_code, want, r.content[:300])
                        still_there = PartnerAdmin.objects.filter(pk=target.pk).exists()
                        self.assertEqual(still_there, want != 200)
                        if want == 409:
                            self.assertEqual(r.json()['code'], 'has_work')
                            self.assertGreaterEqual(r.json()['work'][key], 1)
                            gone.assert_not_called()
                        if want == 200:
                            self.assertTrue(gone.call_args[0][0] == target.supabase_user_id)
                        if role == 'mentor':
                            self.assertEqual(Mentor.objects.filter(pk=mentor_id).exists(), want != 200)

    def test_a_super_is_never_deleted(self):
        other_super = make_admin('super', super_admin=True)
        r, gone = self._delete(self.super, other_super)
        self.assertIn(r.status_code, (400, 404))
        self.assertTrue(PartnerAdmin.objects.filter(pk=other_super.pk).exists())
        r, _ = self._delete(self.lead, other_super)
        self.assertEqual(r.status_code, 404)
        gone.assert_not_called()

    def test_another_organisations_people_404(self):
        elsewhere = make_org()
        for role in ('reviewer', 'mentor'):
            with self.subTest(role=role):
                target = make_admin(role, owning_org=elsewhere)
                self.assertEqual(self._delete(self.lead, target)[0].status_code, 404)
                self.assertTrue(PartnerAdmin.objects.filter(pk=target.pk).exists())

    def test_only_a_super_or_an_organisation_admin_may_delete(self):
        target = make_admin('mentor', owning_org=self.org)
        for role in ('admin', 'finance', 'reviewer', 'qc'):
            with self.subTest(caller=role):
                caller = make_admin(role, owning_org=self.org)
                self.assertEqual(self._delete(caller, target)[0].status_code, 403)
        self.assertTrue(PartnerAdmin.objects.filter(pk=target.pk).exists())


@override_settings(**SUPABASE)
class TestTheMentorDoor(TestCase):
    """The pure mentor's own delete door (`DELETE admin/mentors/<id>/`)."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.lead = make_admin('org_admin', owning_org=cls.org)

    def _delete(self, mentor_id):
        with patch(READ, side_effect=_unused), patch(DELETE, return_value='deleted') as gone:
            r = authed_client(self.lead).delete(f'/api/v1/admin/mentors/{mentor_id}/')
        return r, gone

    def test_a_delete_takes_the_login_the_record_and_its_invitations_together(self):
        login = make_admin('mentor', owning_org=self.org)
        Invitation.objects.create(audience='mentor', email=login.email, name=login.name,
                                  role='mentor', organisation=self.org, partner_admin=login,
                                  mentor=login.mentor, code=unique_suffix('t2-'))
        mentor_id = login.mentor_id
        r, gone = self._delete(mentor_id)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r.json()['login'], 'deleted')
        gone.assert_called_once_with(login.supabase_user_id)
        self.assertFalse(PartnerAdmin.objects.filter(pk=login.pk).exists())
        self.assertFalse(Mentor.objects.filter(pk=mentor_id).exists())
        self.assertFalse(Invitation.objects.filter(mentor_id=mentor_id).exists())

    def test_a_refused_delete_leaves_every_row(self):
        # The footprint refuses BEFORE `PROTECT` would fire — and nothing is half-removed.
        for what in ('ended_assignment', 'session', 'concern'):
            with self.subTest(work=what):
                login = make_admin('mentor', owning_org=self.org)
                mentor = login.mentor
                app = make_application('submitted')
                inv = Invitation.objects.create(
                    audience='mentor', email=login.email, name=login.name, role='mentor',
                    organisation=self.org, partner_admin=login, mentor=mentor,
                    code=unique_suffix('t2-'))
                if what == 'ended_assignment':
                    MentorAssignment.objects.create(application=app, mentor=mentor,
                                                    ended_at=datetime.datetime(2026, 10, 1,
                                                                               tzinfo=datetime.UTC))
                else:
                    MentoringSession.objects.create(application=app, mentor=mentor,
                                                    met_on=datetime.date(2026, 10, 1), mode='phone',
                                                    concern=(what == 'concern'))
                r, gone = self._delete(mentor.pk)
                self.assertEqual(r.status_code, 409, r.content[:300])
                self.assertEqual(r.json()['code'], 'has_work')
                if what == 'concern':
                    self.assertEqual(r.json()['work']['concerns_raised'], 1)
                gone.assert_not_called()
                self.assertTrue(PartnerAdmin.objects.filter(pk=login.pk).exists())
                self.assertTrue(Mentor.objects.filter(pk=mentor.pk).exists())
                self.assertTrue(Invitation.objects.filter(pk=inv.pk).exists())
                self.assertEqual(MentorAssignment.objects.filter(mentor=mentor).count()
                                 + MentoringSession.objects.filter(mentor=mentor).count(), 1)

    def test_a_staff_member_who_mentors_is_not_deleted_through_the_mentor_door(self):
        reviewer = make_admin('reviewer', owning_org=self.org,
                              mentor=Mentor.objects.create(organisation=self.org))
        r, gone = self._delete(reviewer.mentor_id)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'staff_mentor'))
        gone.assert_not_called()
        self.assertTrue(PartnerAdmin.objects.filter(pk=reviewer.pk).exists())

    def test_their_mentoring_is_work_at_the_staff_door(self):
        reviewer = make_admin('reviewer', owning_org=self.org,
                              mentor=Mentor.objects.create(organisation=self.org))
        MentorAssignment.objects.create(application=make_application('submitted'),
                                        mentor=reviewer.mentor)
        with patch(READ, side_effect=_unused), patch(DELETE) as gone:
            r = authed_client(self.lead).delete(f'/api/v1/admin/admins/{reviewer.pk}/')
        self.assertEqual(r.status_code, 409, r.content[:300])
        self.assertEqual(r.json()['work']['scholars_mentored'], 1)
        gone.assert_not_called()


@override_settings(**SUPABASE)
class TestEveryTableSaysSoFirst(TestCase):
    """`deletable` and `work` on the Admins, Reviewers and Mentors tables and the person pages, by the
    delete's own rule — so the screen never offers a refused button."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.fellow = make_admin('org_admin', owning_org=cls.org)
        cls.fresh_rev = make_admin('reviewer', owning_org=cls.org)
        cls.busy_rev = make_admin('reviewer', owning_org=cls.org)
        make_application('assigned', reviewer=cls.busy_rev)
        cls.fresh_mentor = make_admin('mentor', owning_org=cls.org)
        cls.busy_mentor = make_admin('mentor', owning_org=cls.org)
        MentoringSession.objects.create(application=make_application('submitted'),
                                        mentor=cls.busy_mentor.mentor,
                                        met_on=datetime.date(2026, 10, 1), mode='phone')
        cls.staff_mentor = make_admin('qc', owning_org=cls.org,
                                      mentor=Mentor.objects.create(organisation=cls.org))

    def _rows(self, caller, url, key):
        return {r['id']: r for r in authed_client(caller).get(url).json()[key]}

    def test_the_admins_table(self):
        rows = self._rows(self.lead, '/api/v1/admin/admins/', 'admins')
        self.assertTrue(rows[self.fresh_rev.pk]['deletable'])
        self.assertFalse(rows[self.busy_rev.pk]['deletable'])
        self.assertEqual(rows[self.busy_rev.pk]['work'], {'assigned_applications': 1})
        # A fellow organisation admin: listed, but only a super may delete them.
        self.assertFalse(rows[self.fellow.pk]['deletable'])
        self.assertTrue(self._rows(self.super, '/api/v1/admin/admins/', 'admins')
                        [self.fellow.pk]['deletable'])

    def test_the_reviewers_table_and_page(self):
        rows = self._rows(self.lead, '/api/v1/admin/reviewers/', 'reviewers')
        self.assertEqual((rows[self.fresh_rev.pk]['deletable'], rows[self.fresh_rev.pk]['work']),
                         (True, {}))
        self.assertFalse(rows[self.busy_rev.pk]['deletable'])
        self.assertEqual(rows[self.busy_rev.pk]['work'], {'assigned_applications': 1})
        page = authed_client(self.lead).get(f'/api/v1/admin/reviewers/{self.busy_rev.pk}/').json()
        self.assertEqual((page['deletable'], page['work']), (False, {'assigned_applications': 1}))

    def test_the_mentors_table_and_page(self):
        rows = self._rows(self.lead, '/api/v1/admin/mentors/', 'mentors')
        self.assertTrue(rows[self.fresh_mentor.mentor_id]['deletable'])
        busy = rows[self.busy_mentor.mentor_id]
        self.assertEqual((busy['deletable'], busy['work']), (False, {'mentoring_sessions': 1}))
        # A staff member who mentors is deleted from their staff table, never from here.
        self.assertFalse(rows[self.staff_mentor.mentor_id]['deletable'])
        page = authed_client(self.lead).get(
            f'/api/v1/admin/mentors/{self.busy_mentor.mentor_id}/').json()
        self.assertEqual(page['mentor']['work'], {'mentoring_sessions': 1})
        self.assertFalse(page['mentor']['deletable'])

    def test_the_admin_person_page(self):
        fresh = make_admin('admin', owning_org=self.org)
        busy = make_admin('finance', owning_org=self.org)
        make_application('assigned', reviewer=busy)
        url = '/api/v1/admin/admins/{}/permissions/'
        page = authed_client(self.lead).get(url.format(fresh.pk)).json()
        self.assertEqual((page['deletable'], page['work']), (True, {}))
        page = authed_client(self.lead).get(url.format(busy.pk)).json()
        self.assertEqual((page['deletable'], page['work']), (False, {'assigned_applications': 1}))

    def test_a_read_only_admin_is_offered_no_delete(self):
        viewer = make_admin('admin', owning_org=self.org)
        rows = self._rows(viewer, '/api/v1/admin/mentors/', 'mentors')
        self.assertFalse(any(r['deletable'] for r in rows.values()))
