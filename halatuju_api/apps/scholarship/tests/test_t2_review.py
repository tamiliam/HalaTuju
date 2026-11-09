"""Sprint T2 review round (2026-11-09): B1, S1, N2, N3 and N4.

  * B1 - the stamps the first pass missed now count (a QC user's student note made them deletable).
  * S1 - a TABLE reads every footprint in a fixed number of queries (`footprints`), and the batched
         reading agrees with the single-person one (`footprint`) on a fixture built to trip it:
         one row naming the person in two fields, an email in another case, the self-only verbs.
  * N2 - a row nobody may ever delete carries `delete_never` (the screen draws no Delete at all).
  * N3 - `revocable` is false where the server refuses Revoke: a super, yourself, the sole org admin.
  * N4 - Delete refuses the SOLE active org admin of an organisation, as Revoke does.
"""
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.courses.models import PartnerAdmin
from apps.scholarship import staff_footprint
from apps.scholarship.models import AssignmentEvent, MentorAssignment, StaffActivity, StudentActivity
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_org,
)
from apps.scholarship.tests.test_t2_revoke_delete import DELETE, READ, SUPABASE, _unused


def _queries(fn):
    with CaptureQueriesContext(connection) as captured:
        fn()
    return len(captured.captured_queries)


class TestB1TheMissedStamps(TestCase):

    def test_a_qc_users_student_note_is_work(self):
        qc = make_admin('qc', owning_org=make_org())
        StudentActivity.objects.create(application=make_application('submitted'), kind='note',
                                       actor_email=qc.email.upper(), body='called the family')
        self.assertEqual(staff_footprint.footprint(qc), {'student_notes': 1})
        self.assertEqual(staff_footprint.footprints([qc]), {qc.pk: {'student_notes': 1}})

    def test_every_act_counts_but_arriving(self):
        who = make_admin('admin', owning_org=make_org())
        for verb in staff_footprint.SELF_ONLY_VERBS:
            StaffActivity.objects.create(actor=who, verb=verb)
        self.assertEqual(staff_footprint.footprint(who), {})
        StaffActivity.objects.create(actor=who, verb='contract_countersigned')
        self.assertEqual(staff_footprint.footprint(who), {'other_actions': 1})


class TestS1OneReadingTwoPaths(TestCase):
    """`footprints` (a table) and `footprint` (one person) must give the same answer."""

    @classmethod
    def setUpTestData(cls):
        org = make_org()
        cls.rev = make_admin('reviewer', owning_org=org)
        cls.qc = make_admin('qc', owning_org=org)
        cls.mentor = make_admin('mentor', owning_org=org)
        cls.idle = make_admin('admin', owning_org=org)
        app = make_application('submitted')
        # One event naming the reviewer in BOTH fields counts once; one naming two people counts each.
        AssignmentEvent.objects.create(application=app, from_admin=cls.rev, to_admin=cls.rev)
        AssignmentEvent.objects.create(application=app, from_admin=cls.rev, to_admin=cls.qc)
        AssignmentEvent.objects.create(application=app, from_admin=None, to_admin=cls.qc)
        # An email stamp in two fields of one row counts once, whatever the case of the address.
        MentorAssignment.objects.create(application=app, mentor=cls.mentor.mentor,
                                        started_by_email=cls.rev.email.upper(), ended_by_email=cls.rev.email)
        StudentActivity.objects.create(application=app, kind='note', actor_email=cls.qc.email)
        StaffActivity.objects.create(actor=cls.qc, verb='qc_decision')
        StaffActivity.objects.create(actor=cls.qc, verb='first_sign_in')

    def test_the_two_paths_agree(self):
        people = [self.rev, self.qc, self.mentor, self.idle]
        batched = staff_footprint.footprints(people)
        for p in people:
            with self.subTest(role=p.role):
                self.assertEqual(batched[p.pk], staff_footprint.footprint(p))

    def test_the_fixture_reads_as_built(self):
        batched = staff_footprint.footprints([self.rev, self.qc, self.mentor, self.idle])
        self.assertEqual(batched[self.rev.pk], {'cases_held_before': 2, 'mentoring_changes': 1})
        self.assertEqual(batched[self.qc.pk],
                         {'cases_held_before': 2, 'qc_decisions': 1, 'student_notes': 1})
        self.assertEqual(batched[self.mentor.pk], {'scholars_mentored': 1})
        self.assertEqual(batched[self.idle.pk], {})

    def test_twenty_people_cost_what_two_do(self):
        org = make_org()
        people = [make_admin('reviewer', owning_org=org) for _ in range(20)]
        self.assertEqual(_queries(lambda: staff_footprint.footprints(people[:2])),
                         _queries(lambda: staff_footprint.footprints(people)))
        self.assertEqual(_queries(lambda: staff_footprint.footprints(people)), 1)


@override_settings(**SUPABASE)
class TestS1TheTablesCostTheSameAtAnySize(TestCase):
    """Two staff and twenty: the same number of queries on each Team table."""

    def _reading(self, n, url, role):
        org = make_org()
        lead = make_admin('org_admin', owning_org=org)
        for _ in range(n):
            make_admin(role, owning_org=org)
        client = authed_client(lead)
        self.assertEqual(client.get(url).status_code, 200)        # warm-up
        return _queries(lambda: self.assertEqual(client.get(url).status_code, 200))

    def test_each_table(self):
        for url, role in (('/api/v1/admin/admins/', 'admin'), ('/api/v1/admin/reviewers/', 'reviewer'),
                          ('/api/v1/admin/mentors/', 'mentor')):
            with self.subTest(url=url):
                self.assertEqual(self._reading(2, url, role), self._reading(20, url, role))


@override_settings(**SUPABASE)
class TestN2ToN4WhatTheScreensMayOffer(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cls.super = make_admin('super', super_admin=True)
        cls.other_super = make_admin('super', super_admin=True)
        cls.lead = make_admin('org_admin', owning_org=cls.org)
        cls.staff = make_admin('admin', owning_org=cls.org)

    def _admins(self, caller):
        return {r['id']: r for r in authed_client(caller).get('/api/v1/admin/admins/').json()['admins']}

    def _page(self, caller, target):
        return authed_client(caller).get(f'/api/v1/admin/admins/{target.pk}/permissions/').json()

    def _delete(self, caller, target):
        with patch(READ, side_effect=_unused), patch(DELETE, return_value='deleted'):
            return authed_client(caller).delete(f'/api/v1/admin/admins/{target.pk}/')

    def test_a_super_row_is_never_deletable_even_with_work(self):
        StaffActivity.objects.create(actor=self.other_super, verb='contract_countersigned')
        rows = self._admins(self.super)
        for who in (self.super, self.other_super):
            with self.subTest(who=who.pk):
                self.assertTrue(rows[who.pk]['delete_never'])
                self.assertFalse(rows[who.pk]['deletable'])
                self.assertFalse(rows[who.pk]['revocable'])
        self.assertTrue(rows[self.other_super.pk]['work'])

    def test_a_partner_row_is_never_deletable(self):
        partner = make_admin('partner')
        row = self._admins(self.super)[partner.pk]
        self.assertEqual((row['delete_never'], row['deletable']), (True, False))

    def test_a_deletable_role_with_work_is_greyed_not_hidden(self):
        StaffActivity.objects.create(actor=self.staff, verb='contract_countersigned')
        row = self._admins(self.lead)[self.staff.pk]
        self.assertEqual((row['deletable'], row['delete_never'], row['revocable']), (False, False, True))

    def test_the_person_page_hides_revoke_for_a_super_and_for_yourself(self):
        self.assertFalse(self._page(self.super, self.other_super)['revocable'])
        self.assertFalse(self._page(self.super, self.super)['revocable'])
        self.assertTrue(self._page(self.lead, self.staff)['revocable'])
        self.assertTrue(self._page(self.super, self.staff)['revocable'])

    def test_the_sole_org_admin_offers_neither(self):
        page = self._page(self.super, self.lead)
        self.assertEqual((page['revocable'], page['delete_never'], page['deletable']), (False, True, False))
        row = self._admins(self.super)[self.lead.pk]
        self.assertEqual((row['revocable'], row['delete_never']), (False, True))
        make_admin('org_admin', owning_org=self.org)          # a second one: both may now go
        page = self._page(self.super, self.lead)
        self.assertEqual((page['revocable'], page['delete_never'], page['deletable']), (True, False, True))

    def test_delete_refuses_the_sole_org_admin(self):
        r = self._delete(self.super, self.lead)
        self.assertEqual((r.status_code, r.json().get('code')), (400, 'last_org_admin'))
        self.assertTrue(PartnerAdmin.objects.filter(pk=self.lead.pk).exists())

    def test_delete_takes_an_org_admin_who_is_not_the_only_one(self):
        make_admin('org_admin', owning_org=self.org)
        r = self._delete(self.super, self.lead)
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertFalse(PartnerAdmin.objects.filter(pk=self.lead.pk).exists())

    def test_a_revoked_org_admin_is_not_the_sole_one(self):
        second = make_admin('org_admin', owning_org=self.org)
        PartnerAdmin.objects.filter(pk=second.pk).update(is_active=False)
        r = self._delete(self.super, self.lead)
        self.assertEqual(r.json().get('code'), 'last_org_admin')
        self.assertEqual(self._delete(self.super, PartnerAdmin.objects.get(pk=second.pk)).status_code, 200)


def _locks_taken(fn):
    """Every LOCKING read `fn` issues, in order, as the SQL Postgres would run (`FOR UPDATE` included).

    ⚠ SQLITE CANNOT SHOW THE RACE, OR EVEN THE CLAUSE: Django drops `FOR UPDATE` on a backend without
    it. So each locking query is caught as it executes and compiled against a Postgres connection
    object that never connects. This pins that the lock is ASKED FOR, in which order; it does not
    (cannot, here) prove two real transactions wait on each other."""
    from django.db.backends.postgresql.base import DatabaseWrapper
    from django.db.models.sql.compiler import SQLCompiler
    pg = DatabaseWrapper({**connection.settings_dict, 'ENGINE': 'django.db.backends.postgresql'})
    pg.get_autocommit = lambda: False            # inside the view's transaction; never connects
    seen, real = [], SQLCompiler.execute_sql

    def spy(self, *args, **kwargs):
        if self.query.select_for_update:
            sql, params = self.query.get_compiler(connection=pg).as_sql()
            seen.append((sql, params))
        return real(self, *args, **kwargs)

    with patch.object(SQLCompiler, 'execute_sql', spy):
        fn()
    return seen


@override_settings(**SUPABASE)
class TestTheSoleOrgAdminGuardLocksTheWholeSet(TestCase):
    """Two supers each removing one of an organisation's two org admins at once must not leave it
    with none: the org's active org admins are locked, in id order, BEFORE the target row."""

    def setUp(self):
        self.org = make_org()
        self.super = make_admin('super', super_admin=True)
        self.lead = make_admin('org_admin', owning_org=self.org)
        self.second = make_admin('org_admin', owning_org=self.org)

    def _assert_set_locked_first(self, locks):
        self.assertGreaterEqual(len(locks), 2, locks)
        first_sql, first_params = locks[0]
        self.assertIn('FOR UPDATE', first_sql)
        self.assertIn('org_admin', first_params)
        self.assertIn(self.org.pk, first_params)
        # In id order (`ORDER BY 1` is the selected id column), so two lockers never cross.
        self.assertRegex(first_sql, r'^SELECT "partner_admins"\."id" AS "id" .* ORDER BY 1 ASC FOR UPDATE$')
        # The count itself is taken under the lock too.
        self.assertTrue(any('FOR UPDATE' in sql and 'org_admin' in params for sql, params in locks[2:]),
                        locks)

    def test_delete_locks_the_org_admins_before_the_target(self):
        def go():
            with patch(READ, side_effect=_unused), patch(DELETE, return_value='deleted'):
                r = authed_client(self.super).delete(f'/api/v1/admin/admins/{self.lead.pk}/')
            self.assertEqual(r.status_code, 200, r.content[:200])
        self._assert_set_locked_first(_locks_taken(go))

    def test_revoke_locks_the_org_admins_before_the_target(self):
        def go():
            r = authed_client(self.super).patch(f'/api/v1/admin/admins/{self.lead.pk}/revoke/',
                                                {'action': 'revoke'}, format='json')
            self.assertEqual(r.status_code, 200, r.content[:200])
        self._assert_set_locked_first(_locks_taken(go))

    def test_a_staff_target_locks_no_org_admin_set(self):
        staff = make_admin('admin', owning_org=self.org)
        locks = _locks_taken(lambda: authed_client(self.super).patch(
            f'/api/v1/admin/admins/{staff.pk}/revoke/', {'action': 'revoke'}, format='json'))
        self.assertTrue(locks)
        self.assertEqual([sql for sql, params in locks if 'org_admin' in params], [])
