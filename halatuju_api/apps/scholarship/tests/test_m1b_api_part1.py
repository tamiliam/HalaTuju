"""Sprint M1b, API part 1 (2026-11-11): TD-606's first two gaps.

- OWNER O18 ON THE MENTOR-ONLY LOGIN: the Staff list's Suspend of a mentor login is the mentor action
  `deactivate` (`mentor_invite.deactivate`). It is now REFUSED 409 `has_scholars` with `scholars_now` while
  they mentor anybody — the staff Revoke's body (`staff_mentor.has_scholars_body`), counted by the same
  `mentoring.scholars_now` under the MENTOR row's lock (M1a's order) — and never ends mentoring. Revoke of
  an invited mentor (the invitation's Cancel) still ends theirs, as the staff invitation Cancel does.
- `not_arrived` ON THE GROUP-TABLE ROWS: a row's `remove` code is what the screen's Remove meets as the
  screen sends it (`to_no_group` exactly when the row says `last_table`), so a never-signed-in person's
  last group reads `not_arrived`, the action's own answer (`staff_tables_admin.row_refusal`).

⚠ SQLite drops `FOR UPDATE`; the lock order is pinned by the queries as they are ASKED FOR
(`test_m1a_review_fixes._queries`).
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import mentor_invite, mentoring, staff_mentor
from apps.scholarship import staff_tables_admin as sta
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort,
)
from apps.scholarship.tests.test_m1a_review_fixes import _first, _queries
from apps.scholarship.tests.test_mentoring import _scholar, make_mentor

MENTORS = '/api/v1/admin/mentors/'
TEAM = '/api/v1/admin/team/'
KILL = 'apps.courses.supabase_admin.kill_temp_password'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.app = _scholar()
        self.org = self.app.owning_organisation
        self.lead = make_admin('org_admin', owning_org=self.org)


class TestDeactivateRefusesWhileMentoring(_Base):
    def setUp(self):
        super().setUp()
        self.mentor = make_mentor(self.org)
        self.login = mentoring._login(self.mentor)
        PartnerAdmin.objects.filter(pk=self.login.pk).update(first_seen_at=timezone.now())
        self.login.refresh_from_db()

    def deactivate(self):
        with patch(KILL, return_value='killed') as killed:
            r = authed_client(self.lead).post(f'{MENTORS}{self.mentor.pk}/deactivate/', {}, format='json')
        return r, killed

    def test_refused_with_a_scholar_and_nothing_changes(self):
        mentoring.assign(self.lead, self.app, self.mentor, email_student=False)
        r, killed = self.deactivate()
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.json(), staff_mentor.has_scholars_body(self.login.name, 1))
        self.assertEqual(mentoring.scholars_now([self.mentor.pk]), {self.mentor.pk: 1})
        self.mentor.refresh_from_db()
        self.login.refresh_from_db()
        self.assertIsNone(self.mentor.deactivated_at)
        self.assertTrue(self.login.is_active)
        killed.assert_not_called()

    def test_the_service_answers_the_count(self):
        mentoring.assign(self.lead, self.app, self.mentor, email_student=False)
        self.assertEqual(mentor_invite.deactivate(self.lead, self.mentor, self.login),
                         (1, staff_mentor.HAS_SCHOLARS))

    def test_allowed_with_none(self):
        r, _ = self.deactivate()
        self.assertEqual(r.status_code, 200, r.content)
        self.mentor.refresh_from_db()
        self.login.refresh_from_db()
        self.assertIsNotNone(self.mentor.deactivated_at)
        self.assertFalse(self.login.is_active)

    def test_allowed_once_each_scholar_has_moved(self):
        mentoring.assign(self.lead, self.app, self.mentor, email_student=False)
        mentoring.end(self.lead, self.app)
        self.assertEqual(self.deactivate()[0].status_code, 200)

    def test_the_409_is_the_staff_revokes_shape(self):
        # The staff Revoke of a staff mentor with one scholar, beside the mentor login's Deactivate.
        officer = make_admin('admin', owning_org=self.org, first_seen_at=timezone.now())
        staff, _ = staff_mentor.add(self.lead, officer)
        other = _scholar(cohort=self.app.cohort)
        mentoring.assign(self.lead, other, staff, email_student=False)
        mentoring.assign(self.lead, self.app, self.mentor, email_student=False)
        revoke = authed_client(self.lead).patch(f'/api/v1/admin/admins/{officer.pk}/revoke/',
                                                {'action': 'revoke'}, format='json')
        mine, _ = self.deactivate()
        self.assertEqual((revoke.status_code, mine.status_code), (409, 409))
        self.assertEqual(set(revoke.json()), set(mine.json()))
        self.assertEqual((mine.json()['code'], mine.json()['scholars_now']), ('has_scholars', 1))

    def test_the_mentor_row_is_locked_before_the_count_and_the_login(self):
        mentoring.assign(self.lead, self.app, self.mentor, email_student=False)
        mentoring.end(self.lead, self.app)
        seen, result = _queries(lambda: mentor_invite.deactivate(self.lead, self.mentor, self.login))
        self.assertEqual(result, (True, None))
        lock = _first(seen, 'mentors', locks=True)
        self.assertIsNotNone(lock, seen)
        self.assertLess(lock, _first(seen, 'mentor_assignments'), seen)
        self.assertLess(lock, _first(seen, 'partner_admins'), seen)

    def test_refused_under_the_lock_too(self):
        mentoring.assign(self.lead, self.app, self.mentor, email_student=False)
        seen, result = _queries(lambda: mentor_invite.deactivate(self.lead, self.mentor, self.login))
        self.assertEqual(result, (1, 'has_scholars'))
        self.assertLess(_first(seen, 'mentors', locks=True), _first(seen, 'mentor_assignments'), seen)
        self.assertIsNone(_first(seen, 'partner_admins'), seen)   # the login is never touched

    def test_revoking_an_invited_mentor_still_ends_their_mentoring(self):
        # The invitation's Cancel (never signed in) is unchanged: it ends what they had, as the staff
        # invitation Cancel does (`staff_mentor.leave`).
        PartnerAdmin.objects.filter(pk=self.login.pk).update(first_seen_at=None, supabase_user_id=None)
        mentoring.assign(self.lead, self.app, self.mentor, email_student=False)
        with patch(KILL, return_value='killed'):
            r = authed_client(self.lead).post(f'{MENTORS}{self.mentor.pk}/revoke/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(mentoring.scholars_now([self.mentor.pk]), {})


class TestTheRowSaysWhatTheRemoveAnswers(_Base):
    """Each row's `remove` code against the endpoint's answer to the Remove the web sends from that row."""

    def setUp(self):
        super().setUp()
        self.cohort = make_cohort(owning_organisation=self.org)
        now = timezone.now()
        self.never_rev = make_admin('reviewer', owning_org=self.org)
        self.never_adm = make_admin('admin', owning_org=self.org)
        self.never_busy = make_admin('reviewer', owning_org=self.org)
        self.arrived_rev = make_admin('reviewer', owning_org=self.org, first_seen_at=now)
        self.busy_rev = make_admin('reviewer', owning_org=self.org, first_seen_at=now)
        self.never_both = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'scholars'])
        for who in (self.never_busy, self.busy_rev):
            make_application('assigned', reviewer=who, cohort=self.cohort)

    def rows(self, path, key):
        return {a['id']: a['remove'] for a in authed_client(self.lead).get(path).json()[key]}

    def answer(self, table, person, **extra):
        body = {'admin_id': person.pk, 'action': 'remove', 'dry_run': True, **extra}
        r = authed_client(self.lead).post(f'{TEAM}{table}/', body, format='json')
        return None if r.status_code == 200 else r.json()['code']

    def final_answer(self, table, person):
        """The Remove as the screen ends up sending it: a `last_table` answer is offered as the move to
        No group (`RemoveControl`'s `onRemove(last)`), so that is asked next."""
        code = self.answer(table, person)
        return self.answer(table, person, to_no_group=True) if code == sta.LAST_TABLE else code

    def test_a_never_signed_in_last_group_reads_not_arrived(self):
        fields = sta.row_fields(self.lead, [self.never_rev, self.never_adm, self.never_busy])
        self.assertEqual(fields[self.never_rev.pk]['remove'], {'reviewers': sta.NOT_ARRIVED})
        self.assertEqual(fields[self.never_adm.pk]['remove'], {'admins': sta.NOT_ARRIVED})
        # `_refuse_no_group`'s order: not signed in is said before the open case.
        self.assertEqual(sta.row_fields(self.lead, [self.never_busy], open_counts={self.never_busy.pk: 1})
                         [self.never_busy.pk]['remove'], {'reviewers': sta.NOT_ARRIVED})

    def test_every_row_matches_the_action(self):
        expected = {
            self.never_rev.pk: {'reviewers': sta.NOT_ARRIVED},
            self.never_adm.pk: {'admins': sta.NOT_ARRIVED},
            self.never_busy.pk: {'reviewers': sta.NOT_ARRIVED},
            self.arrived_rev.pk: {'reviewers': sta.LAST_TABLE},
            self.busy_rev.pk: {'reviewers': sta.HAS_OPEN_CASES},
            self.never_both.pk: {'admins': None, 'reviewers': None},    # not their last group
        }
        for path, key in (('/api/v1/admin/admins/', 'admins'), ('/api/v1/admin/reviewers/', 'reviewers')):
            rows = self.rows(path, key)
            for person in (self.never_rev, self.never_adm, self.never_busy, self.arrived_rev, self.busy_rev,
                           self.never_both):
                if person.pk not in rows:
                    continue
                with self.subTest(path=path, person=person.name):
                    self.assertEqual(rows[person.pk], expected[person.pk])
                    for table, code in rows[person.pk].items():
                        want = None if code == sta.LAST_TABLE else code     # accepted as the move
                        self.assertEqual(self.final_answer(table, person), want)
