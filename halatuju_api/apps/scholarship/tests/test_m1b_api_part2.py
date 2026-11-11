"""Sprint M1b, API part 2 (2026-11-11): TD-606 fix (2) and the part 1 review.

- THE ADMINS LIST SERVES EACH ROW'S UNFINISHED PAYMENT RUNS: a flat `runs_in_progress` on every
  `GET admin/admins/` row — `staff_work.runs_counts`, the Staff list's `work.admins.runs_in_progress` rule,
  counted for the page in ONE query (`staff_lifecycle.team_table_fields`) — and the row's `remove.admins`
  says `run_in_progress` as the Remove would (`staff_tables_admin.row_refusal`, `_plan_remove`'s order).
- The mentor Deactivate's 409 names "This mentor" when the login has no name.
- A mentor login made staff after the action read it is refused `staff_mentor` under the lock.

⚠ SQLite drops `FOR UPDATE`; the lock order is pinned by the queries as they are ASKED FOR.
"""
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import mentor_invite, mentoring, staff_mentor
from apps.scholarship import staff_tables_admin as sta
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org
from apps.scholarship.tests.test_m1a_remove_rules import _run
from apps.scholarship.tests.test_m1a_review_fixes import _first, _queries
from apps.scholarship.tests.test_mentoring import _scholar, make_mentor
from apps.scholarship.views_admin.mentors import _has_scholars

ADMINS = '/api/v1/admin/admins/'
RUNS_COUNTS = 'apps.scholarship.staff_work.runs_counts'
# The Admins list for an organisation admin: the same count for 2 staff as for 5 (no per-row query).
# Before part 2 it was one fewer (`test_the_count_is_the_one_extra_query`).
ADMINS_LIST_QUERIES = 9


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.app = _scholar()
        self.org = self.app.owning_organisation
        self.lead = make_admin('org_admin', owning_org=self.org)
        self.now = timezone.now()

    def rows(self, caller=None):
        r = authed_client(caller or self.lead).get(ADMINS)
        self.assertEqual(r.status_code, 200, r.content)
        return {a['id']: a for a in r.json()['admins']}


class TestTheAdminsRowCountsRuns(_Base):
    def setUp(self):
        super().setUp()
        self.idle = make_admin('admin', owning_org=self.org, first_seen_at=self.now)
        self.busy = make_admin('admin', owning_org=self.org, first_seen_at=self.now)

    def test_none_reads_zero(self):
        rows = self.rows()
        self.assertEqual(rows[self.idle.pk]['runs_in_progress'], 0)
        self.assertEqual(rows[self.lead.pk]['runs_in_progress'], 0)

    def test_each_unfinished_run_counts_once(self):
        _run(self.org, by=self.busy.email)
        _run(self.org, by=self.lead.email, signed=self.busy.email.upper(), status='admin_signed')
        _run(self.org, by=self.busy.email, signed=self.busy.email, status='finance_checked')
        rows = self.rows()
        self.assertEqual(rows[self.busy.pk]['runs_in_progress'], 3)
        self.assertEqual(rows[self.lead.pk]['runs_in_progress'], 1)
        self.assertEqual(rows[self.idle.pk]['runs_in_progress'], 0)

    def test_finished_runs_are_not_counted(self):
        for done in ('paid', 'cancelled'):
            _run(self.org, by=self.busy.email, signed=self.busy.email, status=done)
        self.assertEqual(self.rows()[self.busy.pk]['runs_in_progress'], 0)

    def test_no_other_organisations_runs_leak_in(self):
        other_org = make_org()
        stranger = make_admin('admin', owning_org=other_org, first_seen_at=self.now)
        _run(other_org, by=stranger.email, signed=stranger.email)
        _run(other_org, by='', signed='')
        rows = self.rows()
        self.assertNotIn(stranger.pk, rows)
        self.assertEqual({pk: row['runs_in_progress'] for pk, row in rows.items()},
                         {pk: 0 for pk in rows})

    def test_the_row_greys_remove_with_the_actions_code(self):
        _run(self.org, by=self.busy.email)
        rows = self.rows()
        self.assertEqual(rows[self.busy.pk]['remove'], {'admins': 'run_in_progress'})
        self.assertNotEqual(rows[self.idle.pk]['remove'], {'admins': 'run_in_progress'})
        r = authed_client(self.lead).post('/api/v1/admin/team/admins/', {
            'admin_id': self.busy.pk, 'action': 'remove', 'dry_run': True}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'run_in_progress'))

    def test_the_reviewers_list_is_unchanged(self):
        # Its frozen query budget and its screen (`remove.reviewers` only) need no run count.
        reviewer = make_admin('reviewer', owning_org=self.org, first_seen_at=self.now)
        r = authed_client(self.lead).get('/api/v1/admin/reviewers/')
        row = {a['id']: a for a in r.json()['reviewers']}[reviewer.pk]
        self.assertNotIn('runs_in_progress', row)

    def test_row_refusal_reads_the_pages_count(self):
        self.assertEqual(sta.row_refusal(self.busy, sta.ADMINS, 0, 2), 'run_in_progress')
        # None runs, or not counted: the next rule answers (their last group).
        self.assertEqual(sta.row_refusal(self.busy, sta.ADMINS, 0, 0), sta.LAST_TABLE)
        self.assertEqual(sta.row_refusal(self.busy, sta.ADMINS, 0), sta.LAST_TABLE)


class TestTheAdminsListQueries(_Base):
    def count(self):
        client = authed_client(self.lead)
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(client.get(ADMINS).status_code, 200)
        return len(ctx)

    def staff(self, n):
        for i in range(n):
            who = make_admin('admin', owning_org=self.org, first_seen_at=self.now)
            _run(self.org, by=who.email)

    def test_flat_in_the_page_size(self):
        self.staff(1)
        two = self.count()
        self.staff(3)
        self.assertEqual((two, self.count()), (ADMINS_LIST_QUERIES, ADMINS_LIST_QUERIES))

    def test_the_count_is_the_one_extra_query(self):
        self.staff(2)
        with patch(RUNS_COUNTS, return_value={}):
            before = self.count()
        self.assertEqual(self.count() - before, 1)


class TestTheMentorReviewFixes(_Base):
    def setUp(self):
        super().setUp()
        self.mentor = make_mentor(self.org)
        self.login = mentoring._login(self.mentor)
        PartnerAdmin.objects.filter(pk=self.login.pk).update(first_seen_at=self.now)
        self.login.refresh_from_db()

    def test_a_nameless_mentor_reads_this_mentor(self):
        self.assertEqual(_has_scholars(None, 2).data, staff_mentor.has_scholars_body('This mentor', 2))
        PartnerAdmin.objects.filter(pk=self.login.pk).update(name='')
        mentoring.assign(self.lead, self.app, self.mentor, email_student=False)
        r = authed_client(self.lead).post(f'/api/v1/admin/mentors/{self.mentor.pk}/deactivate/', {},
                                          format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.json(), staff_mentor.has_scholars_body('This mentor', 1))

    def test_made_staff_after_the_read_is_refused_under_the_lock(self):
        stale = self.login                                   # read as a mentor login
        PartnerAdmin.objects.filter(pk=self.login.pk).update(role='admin')
        seen, result = _queries(lambda: mentor_invite.deactivate(self.lead, self.mentor, stale))
        self.assertEqual(result, (False, 'staff_mentor'))
        self.assertLess(_first(seen, 'mentors', locks=True), _first(seen, 'partner_admins', locks=True), seen)
        self.mentor.refresh_from_db()
        self.assertIsNone(self.mentor.deactivated_at)
        self.assertTrue(PartnerAdmin.objects.get(pk=self.login.pk).is_active)
