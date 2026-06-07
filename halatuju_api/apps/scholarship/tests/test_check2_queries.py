"""Tests for Check 2 STEP 2 — the AI clarify-query stream (``check2_queries.py``)."""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.check2_queries import MAX_CLARIFY, sync_check2_queries
from apps.scholarship.models import (
    FundingNeed, ResolutionItem, ScholarshipApplication, ScholarshipCohort,
)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'c2q-{self.id()}', name='Priya Devi', nric='030101-14-1234',
            household_income=1200, household_size=5,
        )
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            profile_completed_at=timezone.now(),  # submitted
            aspirations='I want to teach.', field_of_study='Education',
            siblings_in_tertiary=0,  # sibling level known
            chosen_pathway='stpm', pathway_certainty='sure',  # STPM → transport asked
        )

    def _codes(self, qs=None):
        qs = qs if qs is not None else self.app.resolution_items.filter(source='check2', status='open')
        return {r.code for r in qs}


class TestSyncCheck2Queries(_Base):
    def test_no_queries_before_submission(self):
        self.app.profile_completed_at = None
        self.app.save()
        self.assertEqual(sync_check2_queries(self.app).count(), 0)
        self.assertEqual(self.app.resolution_items.filter(source='check2').count(), 0)

    def test_creates_clarify_for_gaps_capped(self):
        # With course + sibling-level known, the standing gaps are device + transport (2).
        sync_check2_queries(self.app)
        codes = self._codes()
        self.assertIn('device_status_unknown', codes)
        self.assertIn('transport_cost_unknown', codes)
        self.assertLessEqual(len(codes), MAX_CLARIFY)

    def test_cap_is_respected(self):
        # Force all four gaps: no course, legacy-only siblings, no funding device tick.
        self.app.field_of_study = ''
        self.app.siblings_in_tertiary = None
        self.app.siblings_studying_count = 2
        self.app.save()
        sync_check2_queries(self.app)
        raised = self.app.resolution_items.filter(source='check2', kind='clarify').count()
        self.assertEqual(raised, MAX_CLARIFY)
        # Highest priority (course) is always among those raised.
        self.assertIn('course_unspecified', self._codes())

    def test_idempotent(self):
        sync_check2_queries(self.app)
        n1 = self.app.resolution_items.filter(source='check2').count()
        sync_check2_queries(self.app)
        n2 = self.app.resolution_items.filter(source='check2').count()
        self.assertEqual(n1, n2)

    def test_auto_resolves_when_gap_clears(self):
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='device_status_unknown')
        self.assertEqual(item.status, 'open')
        # Student ticks 'device' under funding → the device gap clears.
        FundingNeed.objects.create(application=self.app, categories=['device'])
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        self.assertEqual(item.resolved_by, 'system')

    def test_answered_query_not_reraised(self):
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='transport_cost_unknown')
        item.status = 'resolved'
        item.resolution_text = 'Bus, about RM80/month.'
        item.resolved_by = 'student'
        item.save()
        sync_check2_queries(self.app)  # gap still present, but it was answered
        self.assertEqual(
            self.app.resolution_items.filter(code='transport_cost_unknown').count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
