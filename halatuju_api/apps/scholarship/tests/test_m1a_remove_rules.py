"""Sprint M1a (2026-11-10): per-group Remove refusals and the last group's road to "No group".

Brief `docs/plans/2026-11-10-m1-staff-list-brief.md` §2 items 7-8, §4 and §12; owner O5 (Remove is refused
while there is unfinished work IN THAT GROUP) and O6 (the last group goes only to "No group", and only when
the caller asks for it: `{to_no_group: true}`). Without the opt-in field every door answers exactly as it
did before M1a (`last_table`), which the "unchanged" tests below pin.

The "waiting on them" registry (`staff_work`) is proven here too: one person's count and a page's count
agree, and a page is counted in a fixed number of queries.
"""
import datetime

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.courses import staff_permissions, staff_tables
from apps.courses.models import PartnerAdmin
from apps.scholarship import mentoring, staff_mentor, staff_work
from apps.scholarship import staff_tables_admin as sta
from apps.scholarship.models import Mentor, PaymentRun
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_student,
)
from apps.scholarship.tests.test_mentoring import _scholar, make_mentor

TEAM = '/api/v1/admin/team/'
MENTORS = '/api/v1/admin/mentors/'
STAFF = '/api/v1/admin/mentors/staff/'


def _signed_in(role, org, **kw):
    return make_admin(role, owning_org=org, first_seen_at=timezone.now(), **kw)


def _run(org, *, by='', signed='', status='draft'):
    return PaymentRun.objects.create(organisation=org, payment_date=datetime.date(2026, 11, 1),
                                     reference=f'PR-M1A-{PaymentRun.objects.count() + 1}', status=status,
                                     created_by=by, admin_signed_email=signed)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.app = _scholar(student=make_student(name='NUR AISYAH', contact_email='aisyah@example.test'))
        self.org = self.app.owning_organisation
        self.lead = make_admin('org_admin', owning_org=self.org, name='Siti Rahmah')

    def remove(self, table, target, **extra):
        return authed_client(self.lead).post(f'{TEAM}{table}/', {'admin_id': target.pk, 'action': 'remove',
                                                                 **extra}, format='json')

    def code(self, resp):
        return resp.status_code, resp.json().get('code')


class RemoveFromAdminsTest(_Base):
    def test_an_unfinished_run_refuses_the_remove(self):
        officer = _signed_in('admin', self.org)
        _run(self.org, by=officer.email.upper())
        resp = self.remove('admins', officer, to_no_group=True)
        self.assertEqual(self.code(resp), (409, 'run_in_progress'))
        self.assertEqual(resp.json()['runs_in_progress'], 1)
        officer.refresh_from_db()
        self.assertEqual((officer.role, staff_tables.tables(officer)), ('admin', ('admins',)))

    def test_a_signed_run_counts_whether_or_not_they_still_hold_the_key(self):
        # Lead ruling: the key names the kind of work; it does not decide whether the work counts.
        officer = _signed_in('admin', self.org, permissions=['see_all'])
        self.assertNotIn('payments_prepare', staff_permissions.resolve(officer))
        _run(self.org, by='someone@example.test', signed=officer.email, status='admin_signed')
        self.assertEqual(self.code(self.remove('admins', officer, to_no_group=True)), (409, 'run_in_progress'))

    def test_a_finished_run_does_not_count(self):
        officer = _signed_in('admin', self.org)
        _run(self.org, by=officer.email, status='completed')
        _run(self.org, by=officer.email, status='cancelled')
        resp = self.remove('admins', officer, to_no_group=True)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['becomes_member'])

    def test_the_run_refusal_comes_before_last_table(self):
        officer = _signed_in('admin', self.org)
        _run(self.org, by=officer.email)
        self.assertEqual(self.code(self.remove('admins', officer)), (409, 'run_in_progress'))


class LastGroupTest(_Base):
    def test_without_the_flag_the_last_group_is_refused_as_today(self):
        for role, table in (('admin', 'admins'), ('reviewer', 'reviewers')):
            with self.subTest(table=table):
                person = _signed_in(role, self.org)
                for extra in ({}, {'to_no_group': 'true'}, {'to_no_group': 1}):
                    self.assertEqual(self.code(self.remove(table, person, **extra)), (400, 'last_table'))
                person.refresh_from_db()
                self.assertEqual(person.role, role)

    def test_with_the_flag_they_stay_on_as_no_group(self):
        person = _signed_in('reviewer', self.org)
        uid = person.supabase_user_id
        resp = self.remove('reviewers', person, to_no_group=True)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual((resp.json()['role'], resp.json()['becomes_member'], resp.json()['becomes_mentor']),
                         ('member', True, False))
        person.refresh_from_db()
        self.assertEqual((person.role, person.permissions, person.is_active, person.supabase_user_id),
                         ('member', None, True, uid))
        self.assertEqual(staff_tables.tables(person), ())

    def test_a_dry_run_says_so_and_writes_nothing(self):
        person = _signed_in('admin', self.org)
        resp = self.remove('admins', person, to_no_group=True, dry_run=True)
        self.assertEqual((resp.status_code, resp.json()['becomes_member']), (200, True))
        person.refresh_from_db()
        self.assertEqual(person.role, 'admin')

    def test_open_cases_refuse_the_last_reviewers_remove(self):
        person = _signed_in('reviewer', self.org)
        make_application('assigned', cohort=self.app.cohort, reviewer=person)
        resp = self.remove('reviewers', person, to_no_group=True)
        self.assertEqual(self.code(resp), (409, 'has_open_cases'))
        self.assertEqual(resp.json()['open_cases'], 1)

    def test_somebody_who_never_signed_in_is_refused(self):
        person = make_admin('reviewer', owning_org=self.org, first_seen_at=None)
        self.assertEqual(self.code(self.remove('reviewers', person, to_no_group=True)), (400, 'not_arrived'))

    def test_the_kept_mentor_link_stays_with_its_mentor_deactivated(self):
        mentor = Mentor.objects.create(organisation=self.org, deactivated_at=timezone.now())
        person = _signed_in('reviewer', self.org, mentor=mentor)
        self.assertEqual(self.remove('reviewers', person, to_no_group=True).status_code, 200)
        person.refresh_from_db()
        self.assertEqual((person.role, person.mentor_id), ('member', mentor.pk))
        self.assertFalse(person.mentors_now)

    def test_a_staff_mentor_still_goes_to_mentors_flag_or_not(self):
        # T3 unchanged: in Mentors too, the last staff group leaves them a mentor login, not "No group".
        person = _signed_in('reviewer', self.org)
        staff_mentor.add(self.lead, person)
        resp = self.remove('reviewers', person, to_no_group=True)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual((resp.json()['becomes_mentor'], resp.json()['becomes_member']), (True, False))
        person.refresh_from_db()
        self.assertEqual(person.role, 'mentor')

    def test_the_row_fields_agree_with_the_write(self):
        cases = (('reviewer', None, False, sta.LAST_TABLE), ('reviewer', None, True, None),
                 ('reviewer', 'never', True, sta.NOT_ARRIVED))
        for role, seen, flag, expected in cases:
            with self.subTest(seen=seen, flag=flag):
                person = make_admin(role, owning_org=self.org,
                                    first_seen_at=None if seen == 'never' else timezone.now())
                self.assertEqual(sta._cheap_refusal(person, sta.REVIEWERS, 0, to_no_group=flag), expected)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class MentorsGroupTest(_Base):
    def setUp(self):
        super().setUp()
        self.kavitha = make_mentor(self.org)
        self.login = mentoring._login(self.kavitha)
        PartnerAdmin.objects.filter(pk=self.login.pk).update(first_seen_at=timezone.now())

    def act(self, mentor, action, **body):
        return authed_client(self.lead).post(f'{MENTORS}{mentor.pk}/{action}/', body, format='json')

    def assign(self, mentor):
        r = authed_client(self.lead).post(f'/api/v1/admin/scholarship/scholars/{self.app.pk}/mentoring/assign/',
                                          {'mentor_id': mentor.pk, 'email_student': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_a_mentor_login_remove_needs_the_flag(self):
        self.assertEqual(self.code(self.act(self.kavitha, 'remove')), (400, 'last_table'))
        self.login.refresh_from_db()
        self.assertEqual(self.login.role, 'mentor')

    def test_a_mentor_login_with_a_scholar_is_refused_and_nothing_ends(self):
        self.assign(self.kavitha)
        resp = self.act(self.kavitha, 'remove', to_no_group=True)
        self.assertEqual((*self.code(resp), resp.json()['scholars_now']), (409, 'has_scholars', 1))
        self.assertEqual(mentoring.scholars_now([self.kavitha.pk]), {self.kavitha.pk: 1})
        self.kavitha.refresh_from_db()
        self.assertIsNone(self.kavitha.deactivated_at)

    def test_a_mentor_login_becomes_no_group_and_joins_mentors_again(self):
        uid = self.login.supabase_user_id
        resp = self.act(self.kavitha, 'remove', to_no_group=True)
        self.assertEqual((resp.status_code, resp.json()['becomes_member']), (200, True))
        self.login.refresh_from_db()
        self.kavitha.refresh_from_db()
        self.assertEqual((self.login.role, self.login.mentor_id, self.login.is_active, self.login.supabase_user_id),
                         ('member', self.kavitha.pk, True, uid))
        self.assertIsNotNone(self.kavitha.deactivated_at)
        self.assertFalse(self.login.mentors_now)
        # The add sheet offers them; adding brings back THEIR mentor record, not a new one.
        self.assertIn(self.login.pk, [s['id'] for s in authed_client(self.lead).get(STAFF).json()['staff']])
        resp = authed_client(self.lead).post(STAFF, {'admin_id': self.login.pk}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.login.refresh_from_db()
        self.kavitha.refresh_from_db()
        self.assertEqual((self.login.role, self.login.mentor_id, self.login.permissions),
                         ('mentor', self.kavitha.pk, None))
        self.assertIsNone(self.kavitha.deactivated_at)
        self.assertTrue(self.login.mentors_now)

    def test_a_mentor_login_never_signed_in_is_refused(self):
        PartnerAdmin.objects.filter(pk=self.login.pk).update(first_seen_at=None)
        self.assertEqual(self.code(self.act(self.kavitha, 'remove', to_no_group=True)), (400, 'not_arrived'))

    def test_a_member_without_a_link_gets_a_new_mentor(self):
        member = _signed_in('member', self.org)
        mentor, err = staff_mentor.add_member(self.lead, member)
        self.assertIsNone(err)
        member.refresh_from_db()
        self.assertEqual((member.role, member.mentor_id, mentor.organisation_id), ('mentor', mentor.pk, self.org.pk))

    def test_add_member_refuses_anybody_else(self):
        for person in (_signed_in('reviewer', self.org), make_admin('member', owning_org=self.org),
                       _signed_in('member', self.org, is_active=False)):
            with self.subTest(role=person.role, active=person.is_active):
                self.assertEqual(staff_mentor.add_member(self.lead, person), (None, 'not_eligible'))

    def test_a_staff_mentor_remove_is_refused_while_they_mentor(self):
        officer = _signed_in('admin', self.org)
        mentor, _ = staff_mentor.add(self.lead, officer)
        self.assign(mentor)
        resp = self.act(mentor, 'stop')
        self.assertEqual((*self.code(resp), resp.json()['scholars_now']), (409, 'has_scholars', 1))
        self.assertEqual(mentoring.scholars_now([mentor.pk]), {mentor.pk: 1})


class RegistryTest(TestCase):
    def setUp(self):
        from apps.scholarship.tests.factories import make_org
        self.org = make_org()

    def test_the_admins_table_keys_derive_from_the_one_shared_list(self):
        self.assertEqual(sta.ADMIN_TABLE_KEYS, tuple(k for k in staff_tables.ADMIN_KEYS if k != 'manage_team'))

    def test_every_registry_entry_is_complete(self):
        for key, entry in staff_work.ADMIN_WAITING.items():
            with self.subTest(key=key):
                self.assertIn(key, sta.ADMIN_TABLE_KEYS)   # an Admins key, from the one shared list
                self.assertTrue(entry.field and entry.code and callable(entry.one) and callable(entry.many))
                self.assertIn('Test', entry.message('Test', 2))

    def test_a_page_counts_like_one_person_in_a_fixed_number_of_queries(self):
        a = _signed_in('admin', self.org, mentor=Mentor.objects.create(organisation=self.org))
        b = _signed_in('admin', self.org)
        c = _signed_in('reviewer', self.org, mentor=Mentor.objects.create(organisation=self.org))
        _run(self.org, by=a.email.upper(), signed=a.email)      # once for a, made AND signed
        _run(self.org, by=a.email, signed=b.email, status='finance_checked')
        _run(self.org, by=b.email, status='completed')           # finished: nobody's
        make_application('assigned', reviewer=c)
        people = [a, b, c]
        with CaptureQueriesContext(connection) as page:
            counts = staff_work.unfinished_counts(people)
        self.assertEqual(len(page.captured_queries), 3)
        for person in people:
            with self.subTest(person=person.role):
                self.assertEqual(counts[person.pk], staff_work.unfinished(person))
        self.assertEqual(counts[a.pk]['admins'], {'runs_in_progress': 2})
        self.assertEqual(counts[b.pk]['admins'], {'runs_in_progress': 1})
        self.assertEqual(counts[c.pk]['reviewers'], {'open_cases': 1})
        self.assertEqual([staff_work.any_work(counts[p.pk]) for p in people], [True, True, True])
        self.assertFalse(staff_work.any_work(staff_work.unfinished(_signed_in('admin', self.org))))
