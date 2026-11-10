"""Sprint M1a (2026-11-10): `GET admin/staff/`, the Staff list (owner O1-O3, O7, O9). Brief §3 and §12.

Who is listed (and the neighbours who are not), the fields (no phone, no email), the read fence (a super
everywhere or narrowed by `?organisation=`, an org admin their own organisation, a `team_read` reader with
`manageable: false`), every Delete answer (self, not_manageable, sole_org_admin, has_unfinished_work, erase,
archive) for staff and mentor logins, and a query count that does not grow with the rows.
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.courses.tests.test_m1a_archive_restore import _Base, _reviewed
from apps.scholarship.models import MentorAssignment
from apps.scholarship.models import StaffProfile
from apps.scholarship.tests.factories import authed_client, make_admin, make_application, make_org

URL = '/api/v1/admin/staff/'
NOW = timezone.now


def _joined(role, org, **kw):
    return make_admin(role, owning_org=org, first_seen_at=NOW(), **kw)


class _StaffList(_Base):
    def rows(self, caller, query=''):
        r = authed_client(caller).get(URL + query)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return {row['id']: row for row in r.json()['staff']}


class TestWhoIsListed(_StaffList):
    def setUp(self):
        self.reviewer = _joined('reviewer', self.org)
        self.suspended = _joined('reviewer', self.org, is_active=False)
        self.member = _joined('member', self.org)
        self.mentor = _joined('mentor', self.org)
        self.waiting = make_admin('reviewer', owning_org=self.org)                  # never signed in
        self.archived = _joined('reviewer', self.org)
        PartnerAdmin.objects.filter(pk=self.archived.pk).update(archived_at=NOW(), is_active=False)
        self.partner = _joined('partner', self.org)
        self.elsewhere = _joined('reviewer', make_org())

    def test_an_org_admin_sees_their_own_team_and_nobody_else(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(first_seen_at=NOW())
        ids = set(self.rows(self.lead))
        self.assertEqual(ids, {self.lead.pk, self.reviewer.pk, self.suspended.pk, self.member.pk,
                               self.mentor.pk})

    def test_a_super_sees_every_organisation_but_never_a_super(self):
        PartnerAdmin.objects.filter(pk=self.super.pk).update(first_seen_at=NOW())
        ids = set(self.rows(self.super))
        self.assertIn(self.elsewhere.pk, ids)
        self.assertNotIn(self.super.pk, ids)
        for gone in (self.waiting, self.archived, self.partner):
            self.assertNotIn(gone.pk, ids)

    def test_a_super_narrows_with_organisation(self):
        ids = set(self.rows(self.super, f'?organisation={self.elsewhere.owning_organisation_id}'))
        self.assertEqual(ids, {self.elsewhere.pk})
        client = authed_client(self.super)
        self.assertEqual(client.get(URL + '?organisation=nope').status_code, 400)
        self.assertEqual(client.get(URL + '?organisation=999999999').status_code, 404)

    def test_an_org_admin_cannot_widen_with_organisation(self):
        ids = set(self.rows(self.lead, f'?organisation={self.elsewhere.owning_organisation_id}'))
        self.assertNotIn(self.elsewhere.pk, ids)
        self.assertIn(self.reviewer.pk, ids)

    def test_the_fields_carry_no_phone_and_no_email(self):
        StaffProfile.objects.create(partner_admin=self.reviewer, phone='+60 12-000 0000', share_phone_with_team=True)
        row = self.rows(self.lead)[self.reviewer.pk]
        self.assertEqual(set(row), {'id', 'kind', 'mentor_id', 'name', 'photo_url', 'last_seen_at', 'groups',
                                    'lead', 'suspended', 'manageable', 'work', 'deletable', 'delete_never',
                                    'delete_outcome', 'revocable'})
        self.assertEqual(row['work'], {'admins': {'runs_in_progress': 0}, 'reviewers': {'open_cases': 0},
                                       'mentors': {'scholars_now': 0}})
        self.assertNotIn('+60', str(self.rows(self.super)))

    def test_kinds_groups_and_states(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(first_seen_at=NOW())
        rows = self.rows(self.lead)
        self.assertEqual((rows[self.reviewer.pk]['kind'], rows[self.reviewer.pk]['groups']), ('staff', ['reviewers']))
        self.assertEqual(rows[self.member.pk]['groups'], [])
        self.assertEqual((rows[self.mentor.pk]['kind'], rows[self.mentor.pk]['groups']), ('mentor', ['mentors']))
        self.assertEqual(rows[self.mentor.pk]['mentor_id'], self.mentor.mentor_id)
        # Lead (M1a): a suspended row shows the groups a Restore gives back, and says it is suspended.
        self.assertEqual((rows[self.suspended.pk]['groups'], rows[self.suspended.pk]['suspended']),
                         (['reviewers'], True))
        self.assertTrue(rows[self.lead.pk]['lead'])

    def test_a_team_read_reader_gets_every_row_and_may_act_on_none(self):
        reader = _joined('admin', self.org)
        rows = self.rows(reader)
        self.assertIn(self.reviewer.pk, rows)
        for row in rows.values():
            self.assertFalse(row['manageable'])
            self.assertFalse(row['deletable'])
            self.assertFalse(row['revocable'])

    def test_a_reviewer_is_refused(self):
        self.assertEqual(authed_client(self.reviewer).get(URL).status_code, 403)

    def test_a_member_is_refused(self):
        self.assertIn(authed_client(self.member).get(URL).status_code, (401, 403))


class TestDeleteAnswers(_StaffList):
    def _answer(self, caller, target):
        row = self.rows(caller)[target.pk]
        return row['delete_never'], row['delete_outcome'], row['deletable']

    def test_self(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(first_seen_at=NOW())
        self.assertEqual(self._answer(self.lead, self.lead), ('self', None, False))
        self.assertFalse(self.rows(self.lead)[self.lead.pk]['revocable'])

    def test_a_fellow_org_admin_is_not_manageable(self):
        fellow = _joined('org_admin', self.org)
        self.assertEqual(self._answer(self.lead, fellow), ('not_manageable', None, False))
        self.assertFalse(self.rows(self.lead)[fellow.pk]['manageable'])

    def test_the_sole_org_admin(self):
        PartnerAdmin.objects.filter(pk=self.lead.pk).update(first_seen_at=NOW())
        self.assertEqual(self._answer(self.super, self.lead), ('sole_org_admin', None, False))

    def test_no_records_erases(self):
        target = _joined('reviewer', self.org)
        self.assertEqual(self._answer(self.lead, target), (None, 'erase', True))

    def test_records_archive(self):
        target = _joined('reviewer', self.org)
        _reviewed(target)
        self.assertEqual(self._answer(self.lead, target), (None, 'archive', True))

    def test_an_open_case_is_unfinished_work(self):
        target = _joined('reviewer', self.org)
        make_application('assigned', reviewer=target)
        self.assertEqual(self._answer(self.lead, target), ('has_unfinished_work', None, False))
        self.assertEqual(self.rows(self.lead)[target.pk]['work']['reviewers']['open_cases'], 1)

    def test_a_mentor_login_with_no_records_erases(self):
        login = _joined('mentor', self.org)
        self.assertEqual(self._answer(self.lead, login), (None, 'erase', True))
        self.assertTrue(self.rows(self.lead)[login.pk]['revocable'])

    def test_a_mentor_login_with_a_past_scholar_archives(self):
        login = _joined('mentor', self.org)
        MentorAssignment.objects.create(application=make_application('active'), mentor=login.mentor,
                                        ended_at=NOW())
        self.assertEqual(self._answer(self.lead, login), (None, 'archive', True))

    def test_a_mentor_login_with_a_scholar_now_is_unfinished_work(self):
        login = _joined('mentor', self.org)
        MentorAssignment.objects.create(application=make_application('active'), mentor=login.mentor)
        self.assertEqual(self._answer(self.lead, login), ('has_unfinished_work', None, False))
        self.assertEqual(self.rows(self.lead)[login.pk]['work']['mentors']['scholars_now'], 1)

    def test_another_organisation_s_mentor_is_not_the_lead_s(self):
        login = _joined('mentor', make_org())
        self.assertEqual(self.rows(self.super)[login.pk]['delete_never'], None)
        self.assertNotIn(login.pk, self.rows(self.lead))


class TestQueryBudget(_StaffList):
    """lessons.md (TD-285): a shared predicate needs a budget of its own. The count is FIXED: more rows of
    every kind cost no more queries."""

    def _page(self, n):
        for _ in range(n):
            _reviewed(_joined('reviewer', self.org))
            _joined('member', self.org)
            _joined('admin', self.org)
            login = _joined('mentor', self.org)
            MentorAssignment.objects.create(application=make_application('active'), mentor=login.mentor)

    def _count(self, caller):
        client = authed_client(caller)
        with CaptureQueriesContext(connection) as ctx:
            r = client.get(URL)
        self.assertEqual(r.status_code, 200)
        return len(ctx.captured_queries), len(r.json()['staff'])

    def test_the_count_does_not_grow_with_the_rows(self):
        self._page(1)
        small, small_rows = self._count(self.super)
        self._page(4)
        big, big_rows = self._count(self.super)
        self.assertGreater(big_rows, small_rows)
        self.assertEqual(big, small)
        self.assertEqual(big, 10)   # measured 2026-11-10 (a super, every kind of row on the page)
        self.assertEqual(self._count(self.lead)[0], small)
