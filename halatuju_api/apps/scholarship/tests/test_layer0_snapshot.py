"""Layer 0 — the submit-time requirements snapshot (2026-08-30).

The scenario this exists for, written as the first test: a student submits; an organisation
then switches a question ON; the student must stay submitted. Before this column that path
ended in `revert_if_profile_incomplete` un-submitting them — a configuration change dressed as
a student's own edit.

The seam is `requirements.resolve`, which reads the frozen copy first — so every consumer
(the completeness gate, the payload, the verdict facts, the ticket queue) inherits the freeze
without knowing it exists. These tests pin that seam and its two edges: nothing frozen before
Submit, nothing frozen after a revert.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import requirements, services
from apps.scholarship.models import (
    ApplicantDocument, ApplicationItem, Consent, FundingNeed, Programme,
    ProgrammeApplicationItem, ScholarshipApplication, ScholarshipCohort,
)


class _SnapshotCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='snap-org', name='Snap Org')
        cls.programme = Programme.objects.create(
            organisation=cls.org, code='snap-programme', name_en='Snap Programme')
        cls.cohort = ScholarshipCohort.objects.create(
            code='snap-c', name='Snap', year=2026, programme=cls.programme)
        call_command('seed_application_catalogue', verbosity=0)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'snap-user-{self.id()}', nric='080505-14-7777',
            student_signals={'x': 1}, address='No. 1, Jalan Snap',
            postal_code='62100', city='Putrajaya')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            aspirations='a', plans='p', daily_life='d', fears='f',
            # Gate v2: STR route + father earner so the STR doc satisfies the income route.
            income_route='str', income_earner='father',
            father_name='F', father_occupation='driver',
            mother_name='M', mother_occupation='homemaker',
            siblings_in_school=0, siblings_in_tertiary=0)
        FundingNeed.objects.create(application=self.app, categories=['books'], programme_months=12)
        Consent.objects.create(application=self.app, is_active=True)
        for t in ('ic', 'results_slip', 'offer_letter', 'parent_ic', 'str'):
            ApplicantDocument.objects.create(application=self.app, doc_type=t,
                                             storage_path=f'{t}.pdf')

    def _set(self, code, state, kind='question'):
        item = ApplicationItem.objects.get(kind=kind, code=code)
        ProgrammeApplicationItem.objects.update_or_create(
            programme=self.programme, item=item, defaults={'state': state})

    def _submit(self):
        # Mail + Check-2 are best-effort side effects of confirm_profile; the freeze is not.
        self.assertTrue(services.confirm_profile(self.app))
        self.app.refresh_from_db()


class TestSubmitFreezesTheRequirements(_SnapshotCase):

    def test_submit_writes_both_kinds_and_a_timestamp(self):
        self.assertIsNone(self.app.requirements_snapshot)
        self._submit()
        snap = self.app.requirements_snapshot
        self.assertTrue(snap['captured_at'])
        self.assertEqual(snap['questions']['aspirations'], 'required')
        self.assertEqual(snap['documents']['ic'], 'required')
        self.assertNotIn('justification', [c for c, s in snap['questions'].items() if s == 'required'])

    def test_THE_SCENARIO_a_question_switched_on_after_submit_does_not_regate(self):
        # `justification` is optional in the defaults, and this student never answered it.
        self.assertEqual(self.app.justification, '')
        self._submit()
        # The organisation now makes it required — the change that used to un-submit people.
        self._set('justification', 'required')
        fresh = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertEqual(requirements.resolve(fresh, 'question')['justification'], 'optional')
        self.assertTrue(services.application_completeness(fresh)['complete'])
        self.assertFalse(services.revert_if_profile_incomplete(fresh))
        fresh.refresh_from_db()
        self.assertEqual(fresh.status, 'profile_complete')

    def test_a_student_still_editing_follows_the_live_configuration(self):
        # The control: before Submit, the same change DOES reach the student. (Owner, 2026-08-30:
        # a student halfway through gets the newest form; only Submit freezes it.)
        self._set('justification', 'required')
        self.assertEqual(requirements.resolve(self.app, 'question')['justification'], 'required')
        self.assertIsNone(self.app.requirements_snapshot)

    def test_the_payload_reads_the_frozen_copy(self):
        self._submit()
        self._set('justification', 'required')
        fresh = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertNotIn('justification', requirements.payload_for(fresh, 'question')['required'])

    def test_freeze_is_idempotent_and_never_overwrites(self):
        self._submit()
        first = dict(self.app.requirements_snapshot)
        self._set('justification', 'required')
        fresh = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertEqual(requirements.freeze(fresh), first)

    def test_a_revert_thaws_and_the_next_submit_refreezes(self):
        self._submit()
        # The student's OWN edit breaks completeness (a required answer blanked)…
        fresh = ScholarshipApplication.objects.get(pk=self.app.pk)
        fresh.aspirations = ''
        fresh.save(update_fields=['aspirations'])
        self.assertTrue(services.revert_if_profile_incomplete(fresh))
        fresh.refresh_from_db()
        self.assertEqual(fresh.status, 'shortlisted')
        self.assertIsNone(fresh.requirements_snapshot)
        # …meanwhile the organisation changed the form; the re-submit freezes the NEW form.
        self._set('justification', 'required')
        fresh.aspirations = 'a'
        fresh.justification = 'j'
        fresh.save(update_fields=['aspirations', 'justification'])
        self.assertTrue(services.confirm_profile(fresh))
        fresh.refresh_from_db()
        self.assertEqual(fresh.requirements_snapshot['questions']['justification'], 'required')


class TestBackfillForRowsSubmittedBeforeTheColumn(_SnapshotCase):

    def _legacy_submitted(self):
        # A row submitted before 2026-08-30: stamped, no snapshot.
        from django.utils import timezone
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(
            status='profile_complete', profile_completed_at=timezone.now(),
            requirements_snapshot=None)
        return ScholarshipApplication.objects.get(pk=self.app.pk)

    def test_report_mode_writes_nothing(self):
        app = self._legacy_submitted()
        out = StringIO()
        call_command('backfill_requirements_snapshots', stdout=out)
        app.refresh_from_db()
        self.assertIsNone(app.requirements_snapshot)
        self.assertIn('would freeze: 1', out.getvalue())

    def test_apply_freezes_todays_resolution_and_is_idempotent(self):
        app = self._legacy_submitted()
        call_command('backfill_requirements_snapshots', '--apply', stdout=StringIO())
        app.refresh_from_db()
        self.assertEqual(app.requirements_snapshot['questions']['aspirations'], 'required')
        first = dict(app.requirements_snapshot)
        out = StringIO()
        call_command('backfill_requirements_snapshots', '--apply', stdout=out)
        app.refresh_from_db()
        self.assertEqual(app.requirements_snapshot, first)
        self.assertIn('already frozen: 1', out.getvalue())

    def test_a_student_still_editing_is_not_a_candidate(self):
        self.assertEqual(self.app.status, 'shortlisted')
        call_command('backfill_requirements_snapshots', '--apply', stdout=StringIO())
        self.app.refresh_from_db()
        self.assertIsNone(self.app.requirements_snapshot)
