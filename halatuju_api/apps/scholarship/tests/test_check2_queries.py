"""Tests for Check 2 STEP 2 — the AI clarify-query stream (``check2_queries.py``)."""
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import StudentProfile

from apps.scholarship.check2_queries import MAX_CLARIFY, sync_check2_queries
from apps.scholarship.models import (
    ApplicantDocument, FundingNeed, ResolutionItem, ScholarshipApplication, ScholarshipCohort,
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
            # Household-income completeness satisfied by default (S1): father earns + has a
            # payslip on file, mother is a homemaker (status known) — so the parent-income
            # gaps don't fire in tests focused on the OTHER clarify gaps.
            father_occupation='gov', mother_occupation='homemaker',
        )
        ApplicantDocument.objects.create(
            application=self.app, doc_type='salary_slip', household_member='father',
            storage_path='x/slip')

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


class TestUtilityClarifyQueries(_Base):
    """#8: the utility holder/address consistency checks also surface as student
    clarify queries (dark until CHECK2_STUDENT_QUERIES_ENABLED gates the call sites)."""

    def _add_water_bill(self, *, name='', address_match=''):
        from apps.scholarship.models import ApplicantDocument
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='water_bill', storage_path=f'{self.app.id}/water/u',
            vision_fields={'fields': {'amount': '20', 'name': name}},
            vision_address_match=address_match, vision_fields_run_at=timezone.now(),
        )

    def test_stranger_bill_raises_holder_query(self):
        self._add_water_bill(name='STRANGER PERSON')
        sync_check2_queries(self.app)
        self.assertIn('utility_holder_unknown', self._codes())

    def test_address_mismatch_raises_address_query(self):
        self._add_water_bill(address_match='mismatch')
        sync_check2_queries(self.app)
        self.assertIn('utility_address_mismatch', self._codes())

    def test_no_utility_query_when_bill_clean(self):
        self._add_water_bill(name=self.profile.name, address_match='found')
        sync_check2_queries(self.app)
        codes = self._codes()
        self.assertNotIn('utility_holder_unknown', codes)
        self.assertNotIn('utility_address_mismatch', codes)

    def test_holder_query_auto_resolves_when_bill_replaced(self):
        self._add_water_bill(name='STRANGER PERSON')
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='utility_holder_unknown')
        self.assertEqual(item.status, 'open')
        # The stranger bill is swept and a parent's bill uploaded → the gap clears.
        self.app.documents.filter(doc_type='water_bill').delete()
        self._add_water_bill(name=self.profile.name)
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        self.assertEqual(item.resolved_by, 'system')


class TestPathwayConfirmQuery(_Base):
    """The offer-vs-declared clash confirmation ("is this offer your final course?"),
    routed through Check 2 (source='check2', kind='confirm') so the flag governs it and it
    rides the query email — instead of being a hidden source='system' verdict item."""

    _OFFER = {'candidate_name': 'Priya Devi', 'candidate_nric': '030101141234',
              'programme': 'Tingkatan Enam', 'institution': 'SMK Temerloh'}

    def _add_offer(self, **over):
        from apps.scholarship.models import ApplicantDocument
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter', storage_path=f'{self.app.id}/offer/x',
            vision_fields={'fields': {**self._OFFER, **over}, 'student_verdict': 'ok',
                           'warnings': [], 'error': ''},
            vision_run_at=timezone.now())

    def _clash(self):
        self.app.pre_u_institution = 'SMK Mentakab'   # declared a genuinely different school
        self.app.save()
        self._add_offer()

    def test_clash_creates_check2_confirm(self):
        self._clash()
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='pathway_confirm')
        self.assertEqual(item.source, 'check2')   # NOT 'system' → it reaches the student
        self.assertEqual(item.kind, 'confirm')
        self.assertEqual(item.status, 'open')
        self.assertEqual(item.params.get('institution'), 'SMK Temerloh')

    def test_no_confirm_without_clash(self):
        # Offer agrees with the declared school → nothing to confirm.
        self.app.pre_u_institution = 'SMK Temerloh'
        self.app.save()
        self._add_offer()
        sync_check2_queries(self.app)
        self.assertFalse(self.app.resolution_items.filter(code='pathway_confirm').exists())

    def test_confirm_is_outside_the_clarify_cap(self):
        # All four clarify gaps PLUS a clash → the confirm is extra, never eats a slot.
        self.app.field_of_study = ''
        self.app.siblings_in_tertiary = None
        self.app.siblings_studying_count = 2
        self._clash()
        sync_check2_queries(self.app)
        self.assertEqual(self.app.resolution_items.filter(kind='clarify').count(), MAX_CLARIFY)
        self.assertTrue(self.app.resolution_items.filter(
            code='pathway_confirm', kind='confirm').exists())

    def test_confirm_auto_resolves_once_settled(self):
        self._clash()
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='pathway_confirm')
        self.assertEqual(item.status, 'open')
        # The student confirms (or a matching offer arrives) → no more clash.
        self.app.pathway_confirmed_at = timezone.now()
        self.app.save()
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        self.assertEqual(item.resolved_by, 'system')

    def test_not_created_as_a_system_item(self):
        # sync_resolution_items (the verdict→system path) must NOT make a pathway_confirm —
        # it moved to Check 2, so a duplicate would otherwise appear.
        from apps.scholarship.resolution import sync_resolution_items
        self._clash()
        sync_resolution_items(self.app)
        self.assertFalse(self.app.resolution_items.filter(
            source='system', code='pathway_confirm').exists())


@override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestReNotifyOnNewCheck2Item(_Base):
    """A query raised AFTER the one-time notify must re-announce (clear query_raised_notified_at),
    so the student isn't left sitting on a silent new request for days. The _Base app has standing
    device + transport clarify gaps."""
    def test_new_query_clears_the_notify_stamp(self):
        self.app.query_raised_notified_at = timezone.now()
        self.app.save(update_fields=['query_raised_notified_at'])
        sync_check2_queries(self.app)                 # creates device/transport clarifies (new)
        self.app.refresh_from_db()
        self.assertIsNone(self.app.query_raised_notified_at)   # re-notify armed

    def test_no_new_item_leaves_the_stamp(self):
        sync_check2_queries(self.app)                 # first pass creates the items
        self.app.query_raised_notified_at = timezone.now()
        self.app.save(update_fields=['query_raised_notified_at'])
        sync_check2_queries(self.app)                 # second pass — nothing new created
        self.app.refresh_from_db()
        self.assertIsNotNone(self.app.query_raised_notified_at)   # NOT reset (no spam)

    def test_flag_off_leaves_the_stamp(self):
        with override_settings(CHECK2_STUDENT_QUERIES_ENABLED=False):
            self.app.query_raised_notified_at = timezone.now()
            self.app.save(update_fields=['query_raised_notified_at'])
            sync_check2_queries(self.app)
            self.app.refresh_from_db()
            self.assertIsNotNone(self.app.query_raised_notified_at)

    def test_never_notified_is_left_none(self):
        # Not yet notified → the initial sweep will cover the new item; don't touch the stamp.
        self.assertIsNone(self.app.query_raised_notified_at)
        sync_check2_queries(self.app)
        self.app.refresh_from_db()
        self.assertIsNone(self.app.query_raised_notified_at)
