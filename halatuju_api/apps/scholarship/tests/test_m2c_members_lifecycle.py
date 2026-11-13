"""Sprint M2c (2026-11-13): the lifecycle rules behind the Members tab (owner R1, R2, R3, R5).

Brief `docs/plans/2026-11-13-m2c-members-tab-brief.md`, decisions C2, C4, C5, C6:
- C2 (R5): a case is open from submitted to recommended, or while its decision is reopened. The three
  readers (`staff_lifecycle.open_cases`, `staff_tables_admin.open_case_counts`, the Reviewers list's own
  count) agree on every status, and the reviewer still lists an awarded case assigned to them.
- C4 (R1, banner fallback): `suspended_cases` on `GET admin/staff/`, for a viewer holding `manage_team`.
- C5 (R2): Delete only from "No group" (`in_a_group`), on the list and at every Delete door.
- C6 (R3): Remove from a group while suspended, under the same work checks; Add and permission edits still
  refuse `not_active`.
"""
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.courses import staff_tables
from apps.courses.models import PartnerAdmin
from apps.courses.tests.test_m1a_archive_restore import ARCHIVE, _Base, _no_group, _reviewed
from apps.scholarship import staff_lifecycle, staff_mentor, staff_permissions_admin
from apps.scholarship import staff_tables_admin as sta
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.tests.factories import authed_client, make_admin, make_application, make_org

STAFF = '/api/v1/admin/staff/'
TEAM = '/api/v1/admin/team/'
NOW = timezone.now
OPEN = {'submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed', 'recommended'}


def _joined(role, org, **kw):
    return make_admin(role, owning_org=org, first_seen_at=NOW(), **kw)


def _holding(reviewer, status, *, reopened=False):
    """An application of the reviewer's organisation, assigned to them, AT ``status``."""
    app = make_application('submitted', reviewer=reviewer)
    ScholarshipApplication.objects.filter(pk=app.pk).update(
        status=status, owning_organisation=reviewer.owning_organisation,
        decision_reopened_at=NOW() if reopened else None)
    return app


class TestOneRuleForOpenCases(_Base):
    """C2: the three copies of the rule, at every status (one parametrised test)."""

    def _readings(self, reviewer):
        lists = authed_client(self.lead).get('/api/v1/admin/reviewers/')
        self.assertEqual(lists.status_code, 200, lists.content[:200])
        row = {r['id']: r for r in lists.json()['reviewers']}[reviewer.pk]
        staff = authed_client(self.lead).get(STAFF).json()['staff']
        return (staff_lifecycle.open_cases(reviewer), sta.open_case_counts([reviewer.pk]).get(reviewer.pk, 0),
                row['remove']['reviewers'], {r['id']: r for r in staff}[reviewer.pk]['work']['reviewers'])

    def test_open_is_submitted_to_recommended_or_reopened(self):
        cases = [(s, False) for s, _ in ScholarshipApplication.STATUS_CHOICES] + [('awarded', True),
                                                                                 ('rejected', True)]
        for status, reopened in cases:
            with self.subTest(status=status, reopened=reopened):
                reviewer = _joined('reviewer', self.org)
                _holding(reviewer, status, reopened=reopened)
                is_open = status in OPEN or reopened
                n = 1 if is_open else 0
                self.assertEqual(self._readings(reviewer),
                                 (n, n, sta.HAS_OPEN_CASES if is_open else sta.LAST_TABLE, {'open_cases': n}))
                self.assertEqual(staff_lifecycle.is_open_case(status, NOW() if reopened else None), is_open)

    def test_the_apply_gate_list_is_not_the_open_list(self):
        from apps.scholarship.services.apply_gate import IN_PLAY_STATUSES
        self.assertTrue(set(staff_lifecycle.OPEN_CASE_STATUSES) < IN_PLAY_STATUSES)
        self.assertIn('awarded', IN_PLAY_STATUSES)
        self.assertEqual(set(staff_lifecycle.OPEN_CASE_STATUSES), OPEN)

    def test_the_reviewer_still_lists_an_awarded_case(self):
        reviewer = _joined('reviewer', self.org)
        app = _holding(reviewer, 'awarded')
        r = authed_client(reviewer).get('/api/v1/admin/scholarship/applications/')
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertIn(app.pk, [a['id'] for a in r.json()['applications']])
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.pk).assigned_to_id, reviewer.pk)


class TestSuspendedCasesBanner(_Base):
    """C4 (owner R1): the open cases held by suspended people, served with the list (brief C4 fallback)."""

    def _body(self, caller):
        r = authed_client(caller).get(STAFF)
        self.assertEqual(r.status_code, 200, r.content[:200])
        return r.json()

    def test_the_count(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(first_seen_at=NOW())
        away = _joined('reviewer', self.org, is_active=False)
        _holding(away, 'interviewing')
        _holding(away, 'recommended')
        _holding(away, 'awarded')                                    # awarded: not open (R5)
        _holding(away, 'rejected', reopened=True)                    # a reopened decision: open
        _holding(_joined('reviewer', self.org), 'submitted')         # an active holder: not counted
        _holding(_joined('reviewer', make_org(), is_active=False), 'submitted')   # another organisation
        self.assertEqual(self._body(self.lead)['suspended_cases'], 3)

    def test_nothing_held_is_zero(self):
        self.assertEqual(self._body(self.lead)['suspended_cases'], 0)

    def test_only_a_viewer_who_manages_the_team_sees_it(self):
        reader = _joined('admin', self.org)                          # reads the list, manages nobody
        self.assertNotIn('suspended_cases', self._body(reader))
        self.assertIn('suspended_cases', self._body(self.super))

    def test_the_query_count_does_not_change(self):
        def count():
            with CaptureQueriesContext(connection) as ctx:
                self._body(self.lead)
            return len(ctx.captured_queries)
        _holding(_joined('reviewer', self.org), 'submitted')
        before = count()
        _holding(_joined('reviewer', self.org, is_active=False), 'submitted')
        self.assertEqual(count(), before)


class TestDeleteOnlyFromNoGroup(_Base):
    """C5 (owner R2): `in_a_group`, after sole_org_admin and before has_unfinished_work."""

    def _row(self, caller, target):
        rows = {r['id']: r for r in authed_client(caller).get(STAFF).json()['staff']}
        return rows[target.pk]['delete_never'], rows[target.pk]['deletable']

    def test_in_a_group_is_refused_on_the_list_and_at_the_door(self):
        target = _joined('reviewer', self.org)
        self.assertEqual(self._row(self.lead, target), ('in_a_group', False))
        for body in (None, ARCHIVE):
            with self.subTest(body=body):
                r = self.delete(self.lead, target, body)
                self.assertEqual((r.status_code, r.json()['code'], r.json()['groups']),
                                 (409, 'in_a_group', ['reviewers']))
                self.assertIn('Remove them from every group first.', r.json()['error'])
        self.assertTrue(PartnerAdmin.objects.filter(pk=target.pk, archived_at=None).exists())
        self.gone.assert_not_called()

    def test_no_group_is_deletable(self):
        target = _no_group(_joined('reviewer', self.org))
        self.assertEqual(self._row(self.lead, target), (None, True))
        self.assertEqual(self.delete(self.lead, target).status_code, 200)
        self.assertFalse(PartnerAdmin.objects.filter(pk=target.pk).exists())

    def test_a_suspended_person_still_in_a_group_is_refused(self):
        target = _joined('admin', self.org, is_active=False)
        self.assertEqual(self._row(self.lead, target), ('in_a_group', False))
        self.assertEqual(self.delete(self.lead, target, ARCHIVE).json()['code'], 'in_a_group')

    def test_in_a_group_comes_before_unfinished_work(self):
        target = _joined('reviewer', self.org)
        _holding(target, 'submitted')
        self.assertEqual(self._row(self.lead, target), ('in_a_group', False))

    def test_a_mentor_login_in_mentors_is_refused_at_the_mentor_door(self):
        login = _joined('mentor', self.org)
        r = self.delete(self.lead, login, url=f'/api/v1/admin/mentors/{login.mentor_id}/')
        self.assertEqual((r.status_code, r.json()['code'], r.json()['groups']), (409, 'in_a_group', ['mentors']))
        _no_group(login)
        r = self.delete(self.lead, login, url=f'/api/v1/admin/mentors/{login.mentor_id}/')
        self.assertEqual(r.status_code, 200, r.content[:200])

    def test_someone_who_never_signed_in_keeps_the_narrow_delete(self):
        waiting = make_admin('reviewer', owning_org=self.org)
        self.assertEqual(staff_tables.groups_to_leave(waiting), [])
        self.assertEqual(self.delete(self.lead, waiting).status_code, 200)

    def test_an_org_admin_s_own_admins_seat_does_not_count(self):
        # Brief C5: until M3 the lead tier's seat at Admins cannot be removed, so it never blocks a Delete.
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(first_seen_at=NOW())
        second = _joined('org_admin', self.org)
        self.assertEqual(staff_tables.groups_to_leave(second), [])
        self.assertEqual(self._row(self.super, second), (None, True))
        PartnerAdmin.objects.filter(pk=second.pk).update(permissions=['review'])   # joined Reviewers
        second.refresh_from_db()
        self.assertEqual(staff_tables.groups_to_leave(second), ['reviewers'])
        self.assertEqual(self._row(self.super, second), ('in_a_group', False))

    def test_the_old_rules_still_come_first(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(first_seen_at=NOW())
        self.assertEqual(self._row(self.lead, self.lead), ('self', False))
        self.assertEqual(self._row(self.super, self.lead), ('sole_org_admin', False))


class TestRemoveWhileSuspended(_Base):
    """C6 (owner R3): Remove for a suspended person, with today's work checks."""

    def _remove(self, table, target, **extra):
        return authed_client(self.lead).post(f'{TEAM}{table}/', {'admin_id': target.pk, 'action': 'remove',
                                                                 **extra}, format='json')

    def _list_remove(self, target):
        rows = {r['id']: r for r in authed_client(self.lead).get('/api/v1/admin/reviewers/').json()['reviewers']}
        return rows[target.pk]['remove']

    def test_no_open_cases_the_remove_works_and_they_stay_suspended(self):
        target = _joined('reviewer', self.org, is_active=False)
        _reviewed(target)
        self.assertEqual(self._list_remove(target), {'reviewers': sta.LAST_TABLE})
        r = self._remove('reviewers', target, to_no_group=True)
        self.assertEqual(r.status_code, 200, r.content[:300])
        target.refresh_from_db()
        self.assertEqual((target.role, target.is_active), (PartnerAdmin.MEMBER_ROLE, False))
        self.assertEqual(staff_tables.groups_to_leave(target), [])

    def test_open_cases_refuse_with_today_s_code(self):
        target = _joined('reviewer', self.org, is_active=False)
        _holding(target, 'interviewing')
        self.assertEqual(self._list_remove(target), {'reviewers': sta.HAS_OPEN_CASES})
        r = self._remove('reviewers', target, to_no_group=True)
        self.assertEqual((r.status_code, r.json()['code']), (409, sta.HAS_OPEN_CASES))
        target.refresh_from_db()
        self.assertEqual(target.role, 'reviewer')

    def test_an_awarded_case_no_longer_blocks(self):
        target = _joined('reviewer', self.org, is_active=False)
        _holding(target, 'awarded')
        self.assertEqual(self._remove('reviewers', target, to_no_group=True).status_code, 200)

    def test_add_and_permission_edits_still_refuse_not_active(self):
        target = _joined('reviewer', self.org, is_active=False)
        r = authed_client(self.lead).post(f'{TEAM}admins/', {'admin_id': target.pk, 'action': 'add'},
                                          format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'not_active'))
        with self.assertRaises(staff_permissions_admin.PermissionChangeRefused) as keys:
            staff_permissions_admin.change_permissions(target.pk, ['review', 'see_all'], by=self.lead)
        self.assertEqual(keys.exception.code, 'not_active')

    def test_a_suspended_mentor_login_may_leave_mentors(self):
        login = _joined('mentor', self.org, is_active=False)
        self.assertEqual(staff_mentor.remove_mentor_login(self.lead, login.mentor, login), (0, None))
        login.refresh_from_db()
        self.assertEqual((login.role, login.is_active), (PartnerAdmin.MEMBER_ROLE, False))
        login.mentor.refresh_from_db()
        self.assertIsNotNone(login.mentor.deactivated_at)

    def test_the_mentor_check_still_applies(self):
        with patch('apps.scholarship.mentoring.scholars_now', side_effect=lambda ids: {i: 2 for i in ids}):
            login = _joined('mentor', self.org, is_active=False)
            self.assertEqual(staff_mentor.remove_mentor_login(self.lead, login.mentor, login),
                             (2, staff_mentor.HAS_SCHOLARS))
