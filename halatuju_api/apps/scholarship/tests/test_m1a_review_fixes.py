"""Sprint M1a review fixes (2026-11-10): lock order, "refuse, never end" under a lock, any-case email twins.

- LOCK ORDER: every M1a door that locks both a Mentor and a login takes the MENTOR row first (Mentor →
  PartnerAdmin), the order `delete_mentor`, `mentor_archive.archive` and Deactivate take — so two doors
  never deadlock (`staff_mentor.remove_mentor_login`, `staff_mentor.stop`, the staff archive door).
- REFUSE, NEVER END (owner O5/O7): the scholars are counted only once the Mentor row is locked.
  `mentoring.assign` locks that row too, so an assignment committed between the count and the stamp can
  never be ended silently by Remove from Mentors or by an archive.
- ANY-CASE TWINS: `staff_archive.restore` and `staff_reinvite.bring_back` refuse a re-invite when another
  row holds the same address in a different case (the invite finds rows case-insensitively).

⚠ SQLite drops `FOR UPDATE`, so the order is pinned by catching each query as it is ASKED FOR (its table
and whether it locks); this cannot prove two real transactions wait on each other (see `test_t2_review`).
"""
from unittest.mock import patch

from django.db.models.sql.compiler import SQLCompiler
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses import staff_archive, staff_reinvite
from apps.courses.models import PartnerAdmin
from apps.scholarship import mentoring, staff_mentor
from apps.scholarship.models import Mentor
from apps.courses.tests.test_m1a_archive_restore import DELETE, READ, SUPABASE, _no_group, _reviewed, _unused
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_org
from apps.scholarship.tests.test_m1a_remove_rules import _signed_in
from apps.scholarship.tests.test_mentoring import _scholar, make_mentor

PLAN = 'apps.scholarship.staff_lifecycle.plan_login_retirement'


def _queries(fn):
    """``[(table, locks)]`` for every SELECT ``fn`` asks for, in order."""
    seen, real = [], SQLCompiler.execute_sql

    def spy(self, *args, **kwargs):
        model = getattr(self.query, 'model', None)
        if model is not None:
            seen.append((model._meta.db_table, bool(self.query.select_for_update)))
        return real(self, *args, **kwargs)

    with patch.object(SQLCompiler, 'execute_sql', spy):
        result = fn()
    return seen, result


def _first(seen, table, locks=None):
    for i, (t, lk) in enumerate(seen):
        if t == table and (locks is None or lk == locks):
            return i
    return None


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.app = _scholar()
        self.org = self.app.owning_organisation
        self.lead = make_admin('org_admin', owning_org=self.org)

    def assert_mentor_locked_first(self, seen):
        mentor_lock = _first(seen, 'mentors', locks=True)
        login_lock = _first(seen, 'partner_admins', locks=True)
        self.assertIsNotNone(mentor_lock, seen)
        self.assertIsNotNone(login_lock, seen)
        self.assertLess(mentor_lock, login_lock, seen)

    def assert_counted_under_the_mentor_lock(self, seen):
        mentor_lock = _first(seen, 'mentors', locks=True)
        count = _first(seen, 'mentor_assignments')
        self.assertIsNotNone(count, seen)
        self.assertIsNotNone(mentor_lock, seen)
        self.assertLess(mentor_lock, count, seen)


class TestRemoveMentorLogin(_Base):
    def setUp(self):
        super().setUp()
        self.mentor = make_mentor(self.org)
        self.login = mentoring._login(self.mentor)
        PartnerAdmin.objects.filter(pk=self.login.pk).update(first_seen_at=timezone.now())
        self.login.refresh_from_db()

    def test_the_mentor_row_is_locked_before_the_login(self):
        seen, result = _queries(lambda: staff_mentor.remove_mentor_login(self.lead, self.mentor, self.login))
        self.assertEqual(result, (0, None))
        self.assert_mentor_locked_first(seen)
        self.assert_counted_under_the_mentor_lock(seen)

    def test_a_deactivated_mentor_is_still_not_active(self):
        Mentor.objects.filter(pk=self.mentor.pk).update(deactivated_at=timezone.now())
        self.assertEqual(staff_mentor.remove_mentor_login(self.lead, self.mentor, self.login), (0, 'not_active'))


class TestStopUnderTheMentorLock(_Base):
    def setUp(self):
        super().setUp()
        self.officer = _signed_in('admin', self.org)
        self.mentor, _ = staff_mentor.add(self.lead, self.officer)
        self.officer.refresh_from_db()

    def test_the_mentor_row_is_locked_before_the_login_and_the_count(self):
        seen, result = _queries(lambda: staff_mentor.stop(self.lead, self.mentor, self.officer))
        self.assertEqual(result, (0, None))
        self.assert_mentor_locked_first(seen)
        self.assert_counted_under_the_mentor_lock(seen)

    def test_a_scholar_still_refuses_and_nothing_ends(self):
        mentoring.assign(self.lead, self.app, self.mentor, email_student=False)
        self.assertEqual(staff_mentor.stop(self.lead, self.mentor, self.officer), (1, staff_mentor.HAS_SCHOLARS))
        self.assertEqual(mentoring.scholars_now([self.mentor.pk]), {self.mentor.pk: 1})


class TestArchiveUnderTheMentorLock(_Base):
    def setUp(self):
        super().setUp()
        self.mentor = Mentor.objects.create(organisation=self.org)
        self.target = _no_group(make_admin('reviewer', owning_org=self.org, mentor=self.mentor,
                                           first_seen_at=timezone.now()))   # M2c (R2): Delete from No group

    def test_archive_locked_counts_the_scholars_under_the_mentor_lock(self):
        with patch(PLAN, return_value=('none', None)):
            seen, done = _queries(lambda: staff_archive.archive_locked(self.lead, self.target))
        self.assertIsNone(done.error)
        self.assert_counted_under_the_mentor_lock(seen)

    def test_lock_mentor_of_locks_the_mentor_and_no_login(self):
        seen, _ = _queries(lambda: staff_archive.lock_mentor_of(self.target.pk))
        self.assertEqual(seen[-1], ('mentors', True))
        self.assertIsNone(_first(seen, 'partner_admins', locks=True))

    @override_settings(**SUPABASE)
    def test_the_staff_archive_door_locks_the_mentor_before_any_login(self):
        _reviewed(self.target)

        def go():
            with patch(READ, side_effect=_unused), patch(DELETE, return_value='deleted'):
                return authed_client(self.lead).delete(f'/api/v1/admin/admins/{self.target.pk}/',
                                                       {'archive': True}, format='json')
        seen, r = _queries(go)
        self.assertEqual(r.status_code, 200, r.content[:200])
        self.assertEqual(r.json()['archived'], True)
        self.assert_mentor_locked_first(seen)

    def test_a_login_without_a_mentor_locks_no_mentor(self):
        other = make_admin('reviewer', owning_org=self.org)
        seen, _ = _queries(lambda: staff_archive.lock_mentor_of(other.pk))
        self.assertIsNone(_first(seen, 'mentors', locks=True))


class TestAnyCaseTwinRefusesTheReinvite(TestCase):
    def setUp(self):
        self.org = make_org()

    def test_restore_refuses_a_live_row_holding_the_address_in_another_case(self):
        archived = make_admin('reviewer', owning_org=self.org, email='twin.m1a@example.test')
        PartnerAdmin.objects.filter(pk=archived.pk).update(archived_at=timezone.now(), is_active=False)
        make_admin('reviewer', owning_org=self.org, email='Twin.M1a@Example.test')
        archived.refresh_from_db()
        row, _, err = staff_archive.restore(archived, name='Twin Back', role='reviewer', org=None,
                                            owning_org=self.org, email='twin.m1a@example.test')
        self.assertEqual((row, err), (None, 'not_reusable'))
        archived.refresh_from_db()
        self.assertIsNotNone(archived.archived_at)

    def test_bring_back_refuses_a_live_row_holding_the_address_in_another_case(self):
        waiting = make_admin('reviewer', owning_org=self.org, email='bring.m1a@example.test')
        PartnerAdmin.objects.filter(pk=waiting.pk).update(is_active=False, first_seen_at=None,
                                                          supabase_user_id=None)
        make_admin('reviewer', owning_org=self.org, email='BRING.m1a@example.test')
        waiting.refresh_from_db()
        row, _, err = staff_reinvite.bring_back(waiting, name='Bring Back', role='reviewer', org=None,
                                                owning_org=self.org, email='bring.m1a@example.test')
        self.assertEqual((row, err), (None, 'not_reusable'))
        waiting.refresh_from_db()
        self.assertFalse(waiting.is_active)


class TestSuspendRefusesWhileMentoring(_Base):
    """Owner O18: Suspend (the staff Revoke) is refused ``has_scholars`` while they mentor anyone."""

    def setUp(self):
        super().setUp()
        self.officer = _signed_in('admin', self.org)
        self.mentor, _ = staff_mentor.add(self.lead, self.officer)
        self.officer.refresh_from_db()

    def revoke(self):
        return authed_client(self.lead).patch(f'/api/v1/admin/admins/{self.officer.pk}/revoke/',
                                              {'action': 'revoke'}, format='json')

    def test_refused_with_a_scholar_and_mentoring_is_untouched(self):
        mentoring.assign(self.lead, self.app, self.mentor, email_student=False)
        r = self.revoke()
        self.assertEqual((r.status_code, r.json()['code'], r.json()['scholars_now']), (409, 'has_scholars', 1))
        self.assertIn(self.officer.name, r.json()['error'])
        self.assertEqual(mentoring.scholars_now([self.mentor.pk]), {self.mentor.pk: 1})
        self.officer.refresh_from_db()
        self.mentor.refresh_from_db()
        self.assertTrue(self.officer.is_active)
        self.assertIsNone(self.mentor.deactivated_at)

    def test_allowed_with_none_and_the_mentor_is_only_stamped(self):
        r = self.revoke()
        self.assertEqual(r.status_code, 200, r.content)
        self.officer.refresh_from_db()
        self.mentor.refresh_from_db()
        self.assertFalse(self.officer.is_active)
        self.assertIsNotNone(self.mentor.deactivated_at)

    def test_the_mentor_row_is_locked_before_the_login_and_the_count(self):
        seen, r = _queries(self.revoke)
        self.assertEqual(r.status_code, 200, r.content)
        self.assert_mentor_locked_first(seen)
        self.assert_counted_under_the_mentor_lock(seen)
