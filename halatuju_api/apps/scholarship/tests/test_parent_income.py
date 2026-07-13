"""Reviewer-query automation S1 — full-household-income completeness.

The sponsor counts the FULL household income, but apply collects only the ONE declared
earner. These rules auto-raise what reviewers now type by hand: a PROOF doc-request when an
earning parent has no payslip, and a STATUS clarify when a parent's slot is blank. A parent
marked non-earning (homemaker/deceased/…) or already income-evidenced is satisfied.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import income_engine
from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def _app(self, suffix='1', **kw):
        p = StudentProfile.objects.create(
            supabase_user_id=f'pi-{suffix}', name='Anbu A/L Raj', nric='030101-14-1234',
            household_income=1500, household_size=5)
        defaults = dict(cohort=self.cohort, profile=p, status='profile_complete',
                        profile_completed_at=timezone.now())
        defaults.update(kw)
        return ScholarshipApplication.objects.create(**defaults)

    def _slip(self, app, member):
        return ApplicantDocument.objects.create(
            application=app, doc_type='salary_slip', household_member=member, storage_path=f'x/{member}')


class TestParentIncomeStatus(_Base):
    def test_non_earning_status_is_satisfied(self):
        app = self._app('a', father_occupation='deceased', mother_occupation='homemaker')
        self.assertEqual(income_engine.parent_income_status(app, 'father'), 'satisfied')
        self.assertEqual(income_engine.parent_income_status(app, 'mother'), 'satisfied')

    def test_earning_parent_without_proof_needs_proof(self):
        app = self._app('b', father_occupation='private', mother_occupation='homemaker')
        self.assertEqual(income_engine.parent_income_status(app, 'father'), 'need_proof')

    def test_earning_parent_with_payslip_is_satisfied(self):
        app = self._app('c', father_occupation='private', mother_occupation='homemaker')
        self._slip(app, 'father')
        self.assertEqual(income_engine.parent_income_status(app, 'father'), 'satisfied')

    def test_blank_parent_needs_status(self):
        # Mother is the STR earner; father's slot is entirely blank → ask his status.
        app = self._app('d', mother_occupation='homemaker', father_occupation='')
        self.assertEqual(income_engine.parent_income_status(app, 'father'), 'need_status')

    def test_str_earner_is_satisfied(self):
        app = self._app('e', mother_occupation='odd_jobs', father_occupation='deceased',
                        income_route='str', income_earner='mother')
        ApplicantDocument.objects.create(application=app, doc_type='str', storage_path='x/str')
        self.assertEqual(income_engine.parent_income_status(app, 'mother'), 'satisfied')

    def test_gaps_list(self):
        app = self._app('f', father_occupation='private', mother_occupation='')
        gaps = income_engine.parent_income_gaps(app)
        self.assertIn({'member': 'father', 'need': 'proof'}, gaps)
        self.assertIn({'member': 'mother', 'need': 'status'}, gaps)


class TestCheck2Integration(_Base):
    def _codes(self, app):
        return {r.code: r for r in app.resolution_items.filter(source='check2', status='open')}

    def test_proof_raises_doc_status_raises_clarify(self):
        app = self._app('g', father_occupation='private', mother_occupation='')
        sync_check2_queries(app)
        items = self._codes(app)
        self.assertIn('father_income_proof_missing', items)
        self.assertEqual(items['father_income_proof_missing'].kind, 'doc')
        self.assertIn('mother_status_unknown', items)
        self.assertEqual(items['mother_status_unknown'].kind, 'clarify')

    def test_proof_doc_is_uncapped(self):
        # Both parents earning, neither with a payslip → BOTH doc requests raised even though
        # doc requests sit outside MAX_CLARIFY (decision #1).
        app = self._app('h', father_occupation='private', mother_occupation='factory')
        sync_check2_queries(app)
        items = self._codes(app)
        self.assertIn('father_income_proof_missing', items)
        self.assertIn('mother_income_proof_missing', items)
        self.assertTrue(all(items[c].kind == 'doc'
                            for c in ('father_income_proof_missing', 'mother_income_proof_missing')))

    def test_auto_resolves_when_proof_arrives(self):
        app = self._app('i', father_occupation='private', mother_occupation='homemaker')
        sync_check2_queries(app)
        self.assertIn('father_income_proof_missing', self._codes(app))
        self._slip(app, 'father')                       # the payslip arrives
        sync_check2_queries(app)
        self.assertNotIn('father_income_proof_missing', self._codes(app))

    def test_satisfied_household_raises_nothing(self):
        app = self._app('j', father_occupation='gov', mother_occupation='homemaker')
        self._slip(app, 'father')
        sync_check2_queries(app)
        codes = set(self._codes(app))
        self.assertNotIn('father_income_proof_missing', codes)
        self.assertNotIn('father_status_unknown', codes)
        self.assertNotIn('mother_status_unknown', codes)
