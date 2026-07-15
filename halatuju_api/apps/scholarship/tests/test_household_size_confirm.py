"""The household-size confirmation STUDENT query (a one-tap 'confirm', like pathway_confirm):
raised when the itemised roster outnumbers the stated size; never re-asked once the student has
confirmed (the over-count persists by design — we don't rewrite the stated size)."""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.check2_queries import _sync_household_size_confirm


def _existing(app):
    return {r.code: r for r in app.resolution_items.filter(source='check2')}


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, *, size, siblings_school=2):
        p = StudentProfile.objects.create(
            supabase_user_id=f'hsc-{self.id()}', name='X', nric='080101-05-1234',
            household_income=2000, household_size=size, receives_str=False, receives_jkm=False,
        )
        # described = student(1) + father + mother (both in-household) + siblings_in_school
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='profile_complete',
            father_occupation='driver', mother_occupation='homemaker',
            siblings_in_school=siblings_school, siblings_in_tertiary=0, other_family_members=[],
        )


class TestSyncHouseholdSizeConfirm(_Base):
    def test_raises_on_overcount(self):
        app = self._app(size=2)   # described = 1+2+2 = 5 > stated 2
        self.assertTrue(_sync_household_size_confirm(app, _existing(app), timezone.now()))
        item = app.resolution_items.get(code='household_size_confirm')
        self.assertEqual(item.kind, 'confirm')
        self.assertEqual(item.source, 'check2')
        self.assertEqual(item.params['described'], 5)
        self.assertEqual(item.params['size'], 2)

    def test_not_raised_when_no_overcount(self):
        app = self._app(size=5)   # described 5 == stated 5 → no shortfall
        self.assertFalse(_sync_household_size_confirm(app, _existing(app), timezone.now()))
        self.assertFalse(app.resolution_items.filter(code='household_size_confirm').exists())

    def test_idempotent_while_open(self):
        app = self._app(size=2)
        _sync_household_size_confirm(app, _existing(app), timezone.now())
        _sync_household_size_confirm(app, _existing(app), timezone.now())   # no duplicate
        self.assertEqual(app.resolution_items.filter(code='household_size_confirm').count(), 1)

    def test_student_confirmed_is_not_re_asked(self):
        app = self._app(size=2)
        _sync_household_size_confirm(app, _existing(app), timezone.now())
        item = app.resolution_items.get(code='household_size_confirm')
        item.status = 'resolved'
        item.resolved_by = 'student'
        item.save(update_fields=['status', 'resolved_by'])
        # Over-count still exists, but a student-confirmed query must NOT re-ask.
        self.assertFalse(_sync_household_size_confirm(app, _existing(app), timezone.now()))
        self.assertEqual(app.resolution_items.filter(code='household_size_confirm').count(), 1)

    def test_auto_resolves_when_overcount_gone(self):
        app = self._app(size=2)
        _sync_household_size_confirm(app, _existing(app), timezone.now())
        # Student fixed their size to match the roster → no more shortfall → open query auto-closes.
        app.profile.household_size = 5
        app.profile.save(update_fields=['household_size'])
        _sync_household_size_confirm(app, _existing(app), timezone.now())
        item = app.resolution_items.get(code='household_size_confirm')
        self.assertEqual(item.status, 'resolved')
        self.assertEqual(item.resolved_by, 'system')
