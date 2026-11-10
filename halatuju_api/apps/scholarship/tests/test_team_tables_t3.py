"""Team tables T3 (2026-11-03): Mentors under Team, and the mentor detail page.

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md` (ruling 6, T3); decisions.md "Team tables T3". The doors:

- THE TABLE (`GET admin/mentors/`) carries its own work columns — meetings in the last 90 days, the last
  meeting, the open concerns — counted for THIS organisation's mentors only, in a fixed number of queries.
- THE DETAIL PAGE (`GET admin/mentors/<id>/`): the table's own readers (super, org_admin, admin); another
  organisation's mentor, a mentor with no login and an unknown id are 404; a reviewer, QC, finance, a pure
  mentor and a reviewer seated at Admins by keys are 403. The figures are computed as `mentor_detail` says.
  NO meeting note, next step, minutes, end reason or logger ever appears. No N+1 (query count fixed).
- T2's "only Mentors would be left" refusal is LIFTED only where the shape is a 7a mentor login: an admin,
  reviewer or QC who mentors now, has signed in and holds no open case becomes role `mentor` (the link kept,
  permissions NULL, the sign-in untouched, no email); anyone else is still refused `mentors_only`. The way
  back is T2's (a mentor login added to a table becomes staff).
"""
import datetime
import json

from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.courses import staff_tables as st
from apps.courses.models import PartnerAdmin
from apps.scholarship import mentor_detail
from apps.scholarship.models import Mentor, MentorAssignment, MentoringSession
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org, make_student,
)

MENTORS = '/api/v1/admin/mentors/'
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
NOTE = 'SECRET-MEETING-NOTE'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@LOCMEM
class _Base(TestCase):
    def setUp(self):
        mail.outbox = []
        self.org = make_org()
        self.other = make_org()
        self.cohort = make_cohort(owning_organisation=self.org)
        self.lead = make_admin('org_admin', owning_org=self.org)
        self.officer = make_admin('admin', owning_org=self.org)
        self.kavitha = make_admin('mentor', owning_org=self.org, name='Kavitha Raman',
                                  first_seen_at=timezone.now())
        self.mentor = self.kavitha.mentor

    def scholar(self, name='NUR AISYAH', status='maintenance', cohort=None):
        return make_application(status, cohort=cohort or self.cohort,
                                active_at=timezone.now() - datetime.timedelta(days=200),
                                student=make_student(name=name))

    def assign(self, app, mentor=None, *, days_ago=100, ended_days_ago=None):
        a = MentorAssignment.objects.create(application=app, mentor=mentor or self.mentor)
        now = timezone.now()
        MentorAssignment.objects.filter(pk=a.pk).update(
            started_at=now - datetime.timedelta(days=days_ago),
            ended_at=(now - datetime.timedelta(days=ended_days_ago)) if ended_days_ago is not None else None,
            end_reason='STAFF-ONLY-REASON' if ended_days_ago is not None else '')
        a.refresh_from_db()
        return a

    def meet(self, assignment, days_ago, *, concern=False, handled=False):
        return MentoringSession.objects.create(
            application=assignment.application, mentor=assignment.mentor, assignment=assignment,
            met_on=timezone.localdate() - datetime.timedelta(days=days_ago), mode='video', minutes=45,
            notes=NOTE, next_step='NEXT-STEP-SECRET', logged_by_email='logger@example.test',
            concern=concern, concern_handled_at=timezone.now() if handled else None)

    def detail(self, caller, mentor=None):
        return authed_client(caller).get(f'{MENTORS}{(mentor or self.mentor).pk}/')


class TheDetailPage(_Base):
    def setUp(self):
        super().setUp()
        self.aisyah = self.scholar('NUR AISYAH')
        self.thivya = self.scholar('THIVYA MURUGAN')
        self.closed = self.scholar('PAST SCHOLAR')
        a1 = self.assign(self.aisyah, days_ago=100)
        a2 = self.assign(self.thivya, days_ago=10)
        a3 = self.assign(self.closed, days_ago=300, ended_days_ago=150)
        # Aisyah: meetings 60, 40, 10 days ago (gaps 20 and 30); a concern open on the last one.
        self.meet(a1, 60)
        self.meet(a1, 40, concern=True, handled=True)
        self.meet(a1, 10, concern=True)
        # The past scholar: 250 and 200 days ago (gap 50) — outside the 90 days.
        self.meet(a3, 250)
        self.meet(a3, 200)
        self.a1, self.a2, self.a3 = a1, a2, a3

    def test_the_figures_and_the_scholars(self):
        r = self.detail(self.lead)
        self.assertEqual(r.status_code, 200, r.content[:300])
        body = r.json()
        self.assertEqual(body['mentor']['name'], 'Kavitha Raman')
        self.assertEqual(body['figures'], {
            'scholars_now': 2, 'meetings_90': 3,
            'average_gap_days': round((20 + 30 + 50) / 3),   # per scholar, all time
            'concerns_raised': 2, 'concerns_open': 1,
            'last_meeting': (timezone.localdate() - datetime.timedelta(days=10)).isoformat()})
        self.assertEqual([s['name'] for s in body['current']], ['THIVYA MURUGAN', 'NUR AISYAH'])
        aisyah = body['current'][1]
        self.assertEqual((aisyah['meetings'], aisyah['concern'], aisyah['has_file'], aisyah['ended']),
                         (3, 'open', True, None))
        self.assertEqual(aisyah['standing'], 'no_result_yet')
        thivya = body['current'][0]
        self.assertEqual((thivya['meetings'], thivya['last_meeting'], thivya['concern']), (0, None, None))
        [past] = body['past']
        self.assertEqual((past['name'], past['meetings'], past['concern']), ('PAST SCHOLAR', 2, None))
        self.assertIsNotNone(past['ended'])
        self.assertIsNotNone(body['mentoring_since'])

    def test_no_note_no_next_step_no_reason_no_logger_ever(self):
        text = json.dumps(self.detail(self.lead).json())
        for secret in (NOTE, 'NEXT-STEP-SECRET', 'STAFF-ONLY-REASON', 'logger@example.test'):
            self.assertNotIn(secret, text)
        for row in self.detail(self.lead).json()['current']:
            self.assertEqual(set(row), {'application_id', 'name', 'since', 'ended', 'meetings', 'last_meeting',
                                        'standing', 'has_file', 'concern'})

    def test_a_handled_concern_reads_handled_and_a_closed_file_is_never_open(self):
        MentoringSession.objects.filter(application=self.aisyah).update(concern_handled_at=timezone.now())
        self.assertEqual(self.detail(self.lead).json()['current'][1]['concern'], 'handled')
        MentoringSession.objects.filter(application=self.aisyah, met_on__gte=timezone.localdate()
                                        - datetime.timedelta(days=11)).update(concern_handled_at=None)
        type(self.aisyah).objects.filter(pk=self.aisyah.pk).update(status='closed')
        body = self.detail(self.lead).json()
        self.assertEqual(body['current'][1]['concern'], 'closed')
        self.assertEqual(body['figures']['concerns_open'], 0)

    def test_the_gap_is_none_until_one_scholar_has_two_meetings(self):
        other = make_admin('mentor', owning_org=self.org, first_seen_at=timezone.now())
        b1 = self.assign(self.scholar('A'), other.mentor)
        b2 = self.assign(self.scholar('B'), other.mentor)
        self.meet(b1, 5)
        self.meet(b2, 3)
        self.assertIsNone(self.detail(self.lead, other.mentor).json()['figures']['average_gap_days'])

    def test_who_may_read_it(self):
        sup = make_admin('super', super_admin=True)
        for caller in (self.lead, self.officer, sup):
            self.assertEqual(self.detail(caller).status_code, 200)
        refused = {
            'reviewer': make_admin('reviewer', owning_org=self.org),
            'qc': make_admin('qc', owning_org=self.org),
            'finance': make_admin('finance', owning_org=self.org),
            'mentor itself': self.kavitha,
            'another mentor': make_admin('mentor', owning_org=self.org, first_seen_at=timezone.now()),
            'reviewer seated at Admins by keys': make_admin('reviewer', owning_org=self.org,
                                                            permissions=['review', 'see_all', 'spending']),
            'reviewer who mentors': make_admin('reviewer', owning_org=self.org,
                                               mentor=Mentor.objects.create(organisation=self.org)),
        }
        for who, caller in refused.items():
            self.assertEqual(self.detail(caller).status_code, 403, who)

    def test_another_organisation_never_opens_or_counts_it(self):
        their_lead = make_admin('org_admin', owning_org=self.other)
        self.assertEqual(self.detail(their_lead).status_code, 404)
        self.assertEqual(authed_client(their_lead).get(MENTORS).json()['mentors'], [])
        # A mentor record with no login (never listed) and an unknown id: 404 too.
        bare = Mentor.objects.create(organisation=self.org)
        self.assertEqual(self.detail(self.lead, bare).status_code, 404)
        self.assertEqual(authed_client(self.lead).get(f'{MENTORS}999999/').status_code, 404)

    def test_a_fixed_number_of_queries_whatever_the_scholars(self):
        def count():
            with CaptureQueriesContext(connection) as q:
                self.assertEqual(self.detail(self.lead).status_code, 200)
            return len(q.captured_queries)
        before = count()
        for i in range(4):
            a = self.assign(self.scholar(f'MORE {i}'), days_ago=20)
            self.meet(a, 5, concern=True)
            self.meet(a, 2)
        self.assertEqual(count(), before)


class TheTable(_Base):
    def test_the_work_columns_and_also_in(self):
        app = self.scholar()
        a = self.assign(app)
        self.meet(a, 100)
        self.meet(a, 30, concern=True)
        self.meet(a, 3)
        staff = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now(),
                           mentor=Mentor.objects.create(organisation=self.org))
        rows = {r['id']: r for r in authed_client(self.lead).get(MENTORS).json()['mentors']}
        k = rows[self.mentor.pk]
        self.assertEqual((k['meetings_90'], k['concerns_open'], k['tables'], k['lead']),
                         (2, 1, ['mentors'], False))
        self.assertEqual(k['last_meeting'], (timezone.localdate() - datetime.timedelta(days=3)).isoformat())
        s = rows[staff.mentor_id]
        self.assertEqual((s['meetings_90'], s['last_meeting'], s['concerns_open'], s['tables']),
                         (0, None, 0, ['reviewers', 'mentors']))

    def test_the_figures_agree_with_the_detail_page(self):
        a = self.assign(self.scholar())
        self.meet(a, 89)
        self.meet(a, 90)   # day 90 is outside "the last 90 days, today included"
        row = authed_client(self.lead).get(MENTORS).json()['mentors'][0]
        figures = self.detail(self.lead).json()['figures']
        self.assertEqual((row['meetings_90'], row['concerns_open']),
                         (figures['meetings_90'], figures['concerns_open']))
        self.assertEqual(row['meetings_90'], 1)

    def test_a_fixed_number_of_queries_whatever_the_mentors(self):
        def count():
            with CaptureQueriesContext(connection) as q:
                self.assertEqual(authed_client(self.lead).get(MENTORS).status_code, 200)
            return len(q.captured_queries)
        before = count()
        for i in range(3):
            m = make_admin('mentor', owning_org=self.org, first_seen_at=timezone.now())
            self.meet(self.assign(self.scholar(f'S{i}'), m.mentor), 4, concern=True)
            make_admin('admin', owning_org=self.org, first_seen_at=timezone.now(),
                       mentor=Mentor.objects.create(organisation=self.org))
        self.assertEqual(count(), before)

    def test_team_columns_is_one_query(self):
        with CaptureQueriesContext(connection) as q:
            mentor_detail.team_columns([self.mentor.pk])
        self.assertEqual(len(q.captured_queries), 1)


class LeavingTheLastStaffTable(_Base):
    """T2 refused it ("until T3"); T3 accepts it only as a 7a mentor login."""

    def act(self, table, target, action='remove', dry_run=False, caller=None):
        return authed_client(caller or self.lead).post(f'/api/v1/admin/team/{table}/', {
            'admin_id': target.pk, 'action': action, 'dry_run': dry_run}, format='json')

    def staff_mentor(self, role, **kw):
        return make_admin(role, owning_org=self.org, first_seen_at=timezone.now(),
                          mentor=Mentor.objects.create(organisation=self.org), **kw)

    def test_an_admin_who_mentors_leaves_admins_as_a_mentor_login(self):
        adm = self.staff_mentor('admin', uid='uid-adm')
        dry = self.act('admins', adm, dry_run=True)
        self.assertEqual(dry.status_code, 200, dry.content[:300])
        self.assertTrue(dry.json()['becomes_mentor'])
        self.assertEqual(dry.json()['role'], 'mentor')
        self.assertEqual(PartnerAdmin.objects.get(pk=adm.pk).role, 'admin')    # a dry run writes nothing
        r = self.act('admins', adm)
        self.assertEqual(r.status_code, 200, r.content[:300])
        adm = PartnerAdmin.objects.get(pk=adm.pk)
        self.assertEqual((adm.role, adm.permissions, adm.is_active, adm.supabase_user_id),
                         ('mentor', None, True, 'uid-adm'))
        self.assertTrue(adm.mentors_now)
        self.assertEqual(st.tables(adm), ('mentors',))
        self.assertEqual(mail.outbox, [])
        # The Mentors table now reads them as a mentor login (Deactivate is theirs), still active.
        row = next(m for m in authed_client(self.lead).get(MENTORS).json()['mentors'] if m['id'] == adm.mentor_id)
        self.assertEqual((row['staff_role'], row['status'], row['tables']), (None, 'active', ['mentors']))
        # …and they are no staff any more: the admin pages refuse them; My students is theirs.
        client = authed_client(adm)
        self.assertEqual(client.get('/api/v1/admin/scholarship/announcements/').status_code, 403)
        self.assertEqual(client.get('/api/v1/admin/mentor/students/').status_code, 200)

    def test_a_reviewer_and_a_qc_leave_reviewers_the_same_way_and_come_back_by_t2(self):
        for role in ('reviewer', 'qc'):
            rev = self.staff_mentor(role)
            self.assertEqual(self.act('reviewers', rev).status_code, 200, role)
            self.assertEqual(PartnerAdmin.objects.get(pk=rev.pk).role, 'mentor', role)
            # The way back is T2's door: a mentor login added to Reviewers becomes staff again.
            self.assertEqual(self.act('reviewers', rev, 'add').status_code, 200, role)
            rev = PartnerAdmin.objects.get(pk=rev.pk)
            self.assertEqual(rev.role, 'reviewer')
            self.assertEqual(st.tables(rev), ('reviewers', 'mentors'))

    def test_still_refused_where_the_shape_is_not_safe(self):
        never = make_admin('admin', owning_org=self.org, mentor=Mentor.objects.create(organisation=self.org))
        self.assertEqual(self.act('admins', never).json()['code'], 'mentors_only')       # never signed in
        busy = self.staff_mentor('reviewer')
        make_application('assigned', reviewer=busy, cohort=self.cohort)
        r = self.act('reviewers', busy)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'has_open_cases'))
        self.assertEqual(PartnerAdmin.objects.get(pk=busy.pk).role, 'reviewer')
        stopped = self.staff_mentor('admin')
        Mentor.objects.filter(pk=stopped.mentor_id).update(deactivated_at=timezone.now())
        self.assertEqual(self.act('admins', stopped).json()['code'], 'last_table')     # not mentoring now
        fin = make_admin('finance', owning_org=self.org, first_seen_at=timezone.now(),
                         mentor=Mentor.objects.create(organisation=self.org))
        self.assertEqual(self.act('admins', fin).json()['code'], 'last_table')         # finance never mentors

    def test_the_lead_still_never_leaves_admins(self):
        Mentor.objects.create(organisation=self.org)
        self.lead.mentor = Mentor.objects.create(organisation=self.org)
        self.lead.first_seen_at = timezone.now()
        self.lead.save()
        sup = make_admin('super', super_admin=True)
        self.assertEqual(self.act('admins', self.lead, caller=sup).status_code, 404)   # may_act: fixed

    def test_the_row_offers_remove_only_where_the_endpoint_accepts(self):
        from apps.scholarship import staff_tables_admin as sta
        ok = self.staff_mentor('admin')
        never = make_admin('admin', owning_org=self.org, mentor=Mentor.objects.create(organisation=self.org))
        fields = sta.row_fields(self.lead, [ok, never])
        self.assertEqual(fields[ok.pk]['remove'], {'admins': None})
        self.assertEqual(fields[never.pk]['remove'], {'admins': 'mentors_only'})

    def test_a_stop_landing_first_wins(self):
        from apps.scholarship import staff_tables_admin as sta
        adm = self.staff_mentor('admin')
        plan_target = PartnerAdmin.objects.get(pk=adm.pk)
        sta.plan_table_change(plan_target, 'admins', 'remove')                  # accepted while mentoring
        Mentor.objects.filter(pk=adm.mentor_id).update(deactivated_at=timezone.now())   # Stop lands
        r = self.act('admins', adm)
        self.assertEqual(r.json()['code'], 'last_table')
        self.assertEqual(PartnerAdmin.objects.get(pk=adm.pk).role, 'admin')


class ThePermissionsTabKnowsTheTables(_Base):
    """T3 scope addition (owner): the Permissions tab shows one section per table the person sits in, so the
    GET serves `tables` (read-only; who may read or edit is unchanged)."""

    def test_the_get_serves_the_tables(self):
        rev = make_admin('reviewer', owning_org=self.org)
        both = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'spending'])
        qc = make_admin('qc', owning_org=self.org)
        for person, tables in ((rev, ['reviewers']), (both, ['admins', 'reviewers']), (qc, ['reviewers']),
                               (self.officer, ['admins'])):
            r = authed_client(self.lead).get(f'/api/v1/admin/admins/{person.pk}/permissions/')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['tables'], tables)

    def test_who_may_read_it_is_unchanged(self):
        rev = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(authed_client(self.officer).get(
            f'/api/v1/admin/admins/{rev.pk}/permissions/').status_code, 403)


class ScholarDataNeedsTheReadKey(_Base):
    """T3 review (CONFIRMED hole): the Mentors table's gate is a ROLE (admin), but scholar data elsewhere needs
    the Scholars list's read key (since sprint S1 `scholars`; until then `see_all`). An admin holding only money
    keys, or only `see_all`, reads the mentor's own row, never their scholars, standing, meetings or concerns."""

    def setUp(self):
        super().setUp()
        a = self.assign(self.scholar('NUR AISYAH'))
        self.meet(a, 5, concern=True)

    def test_a_money_only_admin_sees_the_mentor_but_no_scholar(self):
        for keys in (['payments_approve'], ['spending'], ['see_all']):   # S1: see_all is Applications only
            money = make_admin('admin', owning_org=self.org, permissions=keys)
            r = self.detail(money)
            self.assertEqual(r.status_code, 200, keys)
            body = r.json()
            self.assertEqual((body['sees_scholars'], body['figures'], body['current'], body['past']),
                             (False, None, [], []), keys)
            self.assertIsNone(body['mentor']['concerns_open'])
            self.assertNotIn('NUR AISYAH', json.dumps(body))
            listed = authed_client(money).get(MENTORS).json()
            self.assertFalse(listed['sees_scholars'])
            self.assertEqual([m['concerns_open'] for m in listed['mentors']], [None])

    def test_scholars_admin_org_admin_and_super_see_the_scholars(self):
        for caller in (make_admin('admin', owning_org=self.org, permissions=['scholars']), self.officer,
                       self.lead, make_admin('super', super_admin=True)):
            body = self.detail(caller).json()
            self.assertTrue(body['sees_scholars'])
            self.assertEqual([s['name'] for s in body['current']], ['NUR AISYAH'])
            self.assertEqual(body['figures']['concerns_open'], 1)
            listed = authed_client(caller).get(MENTORS).json()
            self.assertTrue(listed['sees_scholars'])
            self.assertEqual(listed['mentors'][0]['concerns_open'], 1)


class StopAndRemoveSerialise(_Base):
    """T3 review: Stop mentoring and the Remove that makes a mentor login lock the SAME login row and judge
    again under it, so the second sees the first's result — never a live mentor login whose mentor is
    deactivated and who sits in no table."""

    def staff_mentor(self):
        return make_admin('admin', owning_org=self.org, first_seen_at=timezone.now(),
                          mentor=Mentor.objects.create(organisation=self.org))

    def test_remove_first_then_stop_is_refused_and_the_mentor_stays_live(self):
        from apps.scholarship import staff_mentor
        adm = self.staff_mentor()
        stale = PartnerAdmin.objects.get(pk=adm.pk)        # the Stop's copy, read before the Remove
        r = authed_client(self.lead).post('/api/v1/admin/team/admins/',
                                          {'admin_id': adm.pk, 'action': 'remove'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(stale.role, 'admin')                # still says staff in memory
        ended, refusal = staff_mentor.stop(self.lead, stale.mentor, stale)
        self.assertEqual((ended, refusal), (0, 'not_staff'))   # re-judged on the locked row
        login = PartnerAdmin.objects.get(pk=adm.pk)
        self.assertEqual(login.role, 'mentor')
        self.assertIsNone(Mentor.objects.get(pk=adm.mentor_id).deactivated_at)
        self.assertEqual(st.tables(login), ('mentors',))
        # …and over the wire: Stop on that row is refused; Deactivate is now theirs.
        r = authed_client(self.lead).post(f'{MENTORS}{adm.mentor_id}/stop/', {}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_staff'))

    def test_stop_first_then_remove_is_refused(self):
        adm = self.staff_mentor()
        r = authed_client(self.lead).post(f'{MENTORS}{adm.mentor_id}/stop/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        r = authed_client(self.lead).post('/api/v1/admin/team/admins/',
                                          {'admin_id': adm.pk, 'action': 'remove'}, format='json')
        self.assertEqual(r.json()['code'], 'last_table')
        self.assertEqual(PartnerAdmin.objects.get(pk=adm.pk).role, 'admin')

    def test_stop_takes_the_login_row_lock(self):
        from unittest import mock
        from apps.scholarship import staff_mentor
        adm = self.staff_mentor()
        real = PartnerAdmin.objects.select_for_update
        with mock.patch.object(PartnerAdmin.objects, 'select_for_update', side_effect=real) as locked:
            staff_mentor.stop(self.lead, adm.mentor, adm)
        self.assertTrue(locked.called)
