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
            # V4: 2 school siblings → described household (student + 2 parents + 2 siblings) = 5 =
            # household_size, so the base app is roster-CONSISTENT (household_roster_undercount, a
            # V4 clarify, does not fire by default and crowd out the gap a test is focused on).
            siblings_in_school=2,
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
        # Only CLARIFIES are capped — V4 doc-requests (uncapped) don't count toward MAX_CLARIFY.
        clarify_codes = self._codes(
            self.app.resolution_items.filter(source='check2', kind='clarify', status='open'))
        self.assertLessEqual(len(clarify_codes), MAX_CLARIFY)

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

    def test_no_new_query_when_locked(self):
        # V3 (#6): once the interview is concluded (interviewed = querying_locked) NO new query is
        # raised — no item, no notify email inviting an answer the resolve endpoint now refuses.
        self.app.status = 'interviewed'
        self.app.save()
        sync_check2_queries(self.app)
        self.assertEqual(self.app.resolution_items.filter(source='check2').count(), 0)

    def test_locked_still_auto_resolves_existing(self):
        # V3 (#6): the reconcile still runs post-lock so an item raised while unlocked auto-resolves
        # when its gap clears (housekeeping) — only CREATE/RE-OPEN is gated.
        sync_check2_queries(self.app)                       # unlocked → device/transport raised
        item = self.app.resolution_items.get(code='device_status_unknown')
        self.app.status = 'interviewed'
        self.app.save()
        FundingNeed.objects.create(application=self.app, categories=['device'])   # gap clears
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')

    def test_cap_counts_open_so_resolving_frees_a_slot(self):
        # V3 (#7): the cap counts CONCURRENTLY-OPEN clarifies — resolving one frees a slot for a
        # crowded-out gap (before V3 the lifetime count kept it permanently blocked).
        self.app.field_of_study = ''
        self.app.siblings_in_tertiary = None
        self.app.siblings_studying_count = 2
        self.app.save()
        sync_check2_queries(self.app)
        self.assertEqual(
            self.app.resolution_items.filter(kind='clarify', status='open').count(), MAX_CLARIFY)
        first = self.app.resolution_items.filter(kind='clarify', status='open').first()
        first.status = 'resolved'
        first.resolved_by = 'student'
        first.save()
        sync_check2_queries(self.app)                       # a freed slot → a crowded-out gap fills it
        self.assertEqual(
            self.app.resolution_items.filter(kind='clarify', status='open').count(), MAX_CLARIFY)

    def test_clarify_overflow_count(self):
        from apps.scholarship.check2_queries import clarify_overflow_count
        self.assertEqual(clarify_overflow_count(self.app), 0)   # 2 gaps < cap → nothing crowded out
        self.app.field_of_study = ''
        self.app.siblings_in_tertiary = None
        self.app.siblings_studying_count = 2
        self.app.save()
        sync_check2_queries(self.app)
        self.assertGreater(clarify_overflow_count(self.app), 0)  # >3 gaps → some crowded out


class TestDeclaredIncomeDocRequest(_Base):
    """Phase 2A — a declared informal income with no valid STR + no supporting doc raises an
    uncapped income_support_doc request; it clears when the support doc arrives."""

    def setUp(self):
        super().setUp()
        # Salary route, father declares an informal wage, no payslip/EPF/STR on file.
        self.app.documents.filter(doc_type='salary_slip').delete()
        self.app.income_route = 'salary'
        self.app.income_working_members = ['father']
        self.app.income_declared = {'father': 1500}
        self.app.father_occupation = 'informal'
        self.app.save()

    def test_raises_evidence_doc_request(self):
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='declared_income_evidence_missing')
        self.assertEqual((item.source, item.kind, item.status), ('check2', 'doc', 'open'))
        self.assertEqual(item.doc_type, 'income_support_doc')

    def test_outside_the_clarify_cap(self):
        # A doc-request never eats a clarify slot.
        sync_check2_queries(self.app)
        self.assertTrue(self.app.resolution_items.filter(
            code='declared_income_evidence_missing', kind='doc').exists())

    def test_auto_resolves_when_support_doc_uploaded(self):
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='declared_income_evidence_missing')
        # V1 (#2): the request clears only on a support doc that READ (student_verdict='ok').
        ApplicantDocument.objects.create(
            application=self.app, doc_type='income_support_doc', household_member='father',
            storage_path='x/support',
            vision_fields={'fields': {'name': 'ABU', 'amount': 'RM1,200'}, 'student_verdict': 'ok'})
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        self.assertEqual(item.resolved_by, 'system')

    def test_not_resolved_by_blank_support_doc(self):
        # V1 (#2): a blank/wrong image (student_verdict='wrong_doc') read nothing → the request
        # stays OPEN, so Check 2 keeps asking for real evidence instead of silently clearing.
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='declared_income_evidence_missing')
        ApplicantDocument.objects.create(
            application=self.app, doc_type='income_support_doc', household_member='father',
            storage_path='x/blank',
            vision_fields={'fields': {}, 'student_verdict': 'wrong_doc'})
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')

    def test_not_raised_when_valid_str_on_file(self):
        # A valid STR accepts the declared amount → no evidence request.
        ApplicantDocument.objects.create(
            application=self.app, doc_type='str', storage_path='x/str',
            vision_fields={'fields': {'status': 'Lulus', 'source_type': ''}},
            vision_run_at=timezone.now())
        sync_check2_queries(self.app)
        self.assertFalse(self.app.resolution_items.filter(
            code='declared_income_evidence_missing').exists())


class TestUnemploymentQueries(_Base):
    """Phase 2B — an 'unemployed' roster member raises a reason/since clarify + a soft EPF
    doc-request; both clear when the detail is captured / an EPF is uploaded."""

    def setUp(self):
        super().setUp()
        self.app.father_occupation = 'unemployed'   # father now non-earning, status known
        self.app.income_nonearning = {}
        self.app.save()

    def test_detail_clarify_raised_and_within_cap(self):
        sync_check2_queries(self.app)
        codes = self._codes()
        self.assertIn('unemployment_detail_unknown', codes)
        self.assertLessEqual(
            self.app.resolution_items.filter(source='check2', kind='clarify', status='open').count(),
            MAX_CLARIFY)

    def test_detail_clarify_clears_when_captured(self):
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='unemployment_detail_unknown')
        self.app.income_nonearning = {'father': {'reason': 'retrenched', 'since': '2025-03'}}
        self.app.save()
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        self.assertEqual(item.resolved_by, 'system')

    def test_epf_doc_request_raised_and_clears(self):
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='unemployment_epf_missing')
        self.assertEqual((item.source, item.kind, item.doc_type), ('check2', 'doc', 'epf'))
        ApplicantDocument.objects.create(
            application=self.app, doc_type='epf', household_member='father', storage_path='x/epf')
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')

    def test_no_queries_when_member_employed(self):
        self.app.father_occupation = 'gov'
        self.app.save()
        sync_check2_queries(self.app)
        self.assertFalse(self.app.resolution_items.filter(
            code__in=('unemployment_detail_unknown', 'unemployment_epf_missing')).exists())


class TestHouseholdProofQueries(_Base):
    """Phase 2C (P2) — an income-proof request generalised to a working non-parent roster earner
    (guardian/brother/sister), same pattern as the parents; clears when their payslip arrives."""

    def setUp(self):
        super().setUp()   # father='gov' + a father salary_slip on file → father satisfied
        self.app.other_family_members = [{'role': 'guardian', 'occupation': 'driver'}]
        self.app.save()

    def test_working_guardian_proof_request_raised_and_clears(self):
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='guardian_income_proof_missing')
        self.assertEqual((item.source, item.kind, item.doc_type), ('check2', 'doc', 'salary_slip'))
        # V1 (F2/F3): the request now carries the household_member so the Action-Centre upload
        # lands tagged to the right earner (salary route was blank-tagging → the ~29-doc residue
        # + the "Earner's IC" mislabel). Before V1 params was {}.
        self.assertEqual(item.params.get('household_member'), 'guardian')
        ApplicantDocument.objects.create(
            application=self.app, doc_type='salary_slip', household_member='guardian',
            storage_path='x/guardian')
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        self.assertEqual(item.resolved_by, 'system')

    def test_non_earning_member_no_request(self):
        self.app.other_family_members = [{'role': 'brother', 'occupation': 'unemployed'}]
        self.app.save()
        sync_check2_queries(self.app)
        self.assertFalse(self.app.resolution_items.filter(
            code__in=('brother_income_proof_missing', 'guardian_income_proof_missing')).exists())

    def test_resolved_proof_request_reraises_when_gap_refires(self):
        # V2 (#4): a doc-request resolved by an upload, then the proof is REMOVED → the gap
        # re-fires → the request is RE-OPENED (doc-kind items are re-raisable). Before V2 a
        # resolved item stayed silently closed even though the proof was gone again.
        sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code='guardian_income_proof_missing')
        slip = ApplicantDocument.objects.create(
            application=self.app, doc_type='salary_slip', household_member='guardian',
            storage_path='x/guardian2')
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'resolved')
        slip.delete()                       # proof removed → the guardian's income gap re-fires
        sync_check2_queries(self.app)
        item.refresh_from_db()
        self.assertEqual(item.status, 'open')
        self.assertIsNone(item.resolved_at)


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
        # Several clarify gaps PLUS a clash → the confirm is extra, never eats a slot. V3 (#7):
        # reporting_date_unknown is UNCAPPED (a sponsor-profile input of equal standing), so the
        # CAPPED clarifies number MAX_CLARIFY and reporting_date rides alongside them.
        self.app.field_of_study = ''
        self.app.siblings_in_tertiary = None
        self.app.siblings_studying_count = 2
        self._clash()
        sync_check2_queries(self.app)
        capped = (self.app.resolution_items.filter(kind='clarify')
                  .exclude(code='reporting_date_unknown').count())
        self.assertEqual(capped, MAX_CLARIFY)
        self.assertTrue(self.app.resolution_items.filter(code='reporting_date_unknown').exists())
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


class TestV4PromotedAsks(_Base):
    """V4 — the nine promoted human ask-themes (audit §E). Raise-condition + auto-resolve.
    The _Base app is roster-consistent, exam_type spm (default), father employed with a payslip
    but no EPF, no results slip, no bills — so several V4 items fire by default."""

    def test_school_leaving_cert_raised_and_clears(self):
        sync_check2_queries(self.app)                       # spm, no results slip → raise
        self.assertIn('school_leaving_cert_missing', self._codes())
        ApplicantDocument.objects.create(application=self.app, doc_type='results_slip',
                                         storage_path='x/rs')
        sync_check2_queries(self.app)
        self.assertEqual(self.app.resolution_items.get(
            code='school_leaving_cert_missing').status, 'resolved')

    def test_semester_result_for_continuing_student_only(self):
        self.profile.exam_type = 'stpm'
        self.profile.save()
        sync_check2_queries(self.app)
        codes = self._codes()
        self.assertIn('semester_result_missing', codes)
        self.assertNotIn('school_leaving_cert_missing', codes)   # spm-only ask

    def test_employed_epf_optional_raised_and_clears(self):
        sync_check2_queries(self.app)                       # father gov + slip, no EPF → raise
        self.assertIn('epf_statement_missing', self._codes())
        ApplicantDocument.objects.create(application=self.app, doc_type='epf',
                                         household_member='father', storage_path='x/epf')
        sync_check2_queries(self.app)
        self.assertEqual(self.app.resolution_items.get(
            code='epf_statement_missing').status, 'resolved')

    def test_utility_bill_missing_clears_on_either_bill(self):
        sync_check2_queries(self.app)                       # no bills → raise
        self.assertIn('utility_bill_missing', self._codes())
        ApplicantDocument.objects.create(application=self.app, doc_type='electricity_bill',
                                         storage_path='x/eb')
        sync_check2_queries(self.app)
        self.assertEqual(self.app.resolution_items.get(
            code='utility_bill_missing').status, 'resolved')

    def test_deceased_parent_detail(self):
        self.app.father_occupation = 'deceased'
        self.app.save()
        sync_check2_queries(self.app)
        self.assertIn('deceased_parent_detail', self._codes())

    def test_informal_work_detail(self):
        self.app.income_declared = {'father': 1200}
        self.app.save()
        sync_check2_queries(self.app)
        self.assertIn('informal_work_detail', self._codes())

    def test_household_roster_undercount(self):
        self.profile.household_size = 8      # described = 5 (student + 2 parents + 2 school) → gap 3
        self.profile.save()
        sync_check2_queries(self.app)
        self.assertIn('household_roster_undercount', self._codes())

    def test_other_scholarships_followup(self):
        self.app.other_scholarships = ['MARA loan']
        self.app.save()
        sync_check2_queries(self.app)
        self.assertIn('other_scholarships_followup', self._codes())

    def test_high_utility_expense(self):
        # Two bills in the student's name (no holder query), RM200 each → 400/5 = 80/head > 60 → high.
        for dt in ('water_bill', 'electricity_bill'):
            ApplicantDocument.objects.create(
                application=self.app, doc_type=dt, storage_path=f'x/{dt}',
                vision_fields={'fields': {'amount': 'RM200', 'name': 'Priya Devi'},
                               'student_verdict': 'ok'})
        sync_check2_queries(self.app)
        self.assertIn('high_utility_expense', self._codes())
