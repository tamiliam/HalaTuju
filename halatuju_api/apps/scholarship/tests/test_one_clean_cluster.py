"""Owner 2026-07-08 — "one complete, clean earner cluster is enough to submit".

On the salary route, once ONE selected working member is fully + coherently documented, every
OTHER member's missing docs and document errors (e.g. an extraneous, misread second-parent IC)
become soft Check-2 follow-ups, not submission blockers. Plus the OCR name-guard that stops a
header-fragment fused into a name (e.g. "RAJAANMALAYS") reading as a confident wrong name.
"""
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import income_engine, services
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.vision import _name_looks_garbled, _extract_name


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='occ', name='B40', year=2026)

    def _app(self, suffix, **kw):
        p = StudentProfile.objects.create(
            supabase_user_id=f'occ-{suffix}', name='Anbu A/L Raj', nric='030101-14-1234',
            household_income=1500, household_size=5)
        defaults = dict(cohort=self.cohort, profile=p, status='shortlisted',
                        income_route='salary', income_working_members=['mother', 'father'])
        defaults.update(kw)
        return ScholarshipApplication.objects.create(**defaults)

    def _doc(self, app, doc_type, member='', **fields):
        return ApplicantDocument.objects.create(
            application=app, doc_type=doc_type, household_member=member,
            storage_path=f'x/{doc_type}/{member}', vision_run_at=timezone.now(), **fields)


class TestMemberClusterComplete(_Base):
    def test_complete_clean_father_cluster_qualifies(self):
        # Father needs no relationship doc (the patronymic on the IC proves it): IC + salary slip.
        app = self._app('a')
        self._doc(app, 'parent_ic', 'father', vision_name='RAJ KUMAR')
        self._doc(app, 'salary_slip', 'father', vision_name='RAJ KUMAR')
        with mock.patch('apps.scholarship.income_engine.student_income_ic_check',
                        return_value={'readable': True, 'name_status': 'match'}), \
             mock.patch('apps.scholarship.income_engine.student_income_proof_check',
                        return_value={'name_status': 'match', 'nric_status': 'match'}):
            self.assertTrue(income_engine.member_cluster_complete(app, 'father'))
            self.assertTrue(income_engine.salary_income_satisfied(app))

    def test_missing_salary_slip_does_not_qualify(self):
        app = self._app('b')
        self._doc(app, 'parent_ic', 'father', vision_name='RAJ KUMAR')  # IC only, no slip, no STR
        with mock.patch('apps.scholarship.income_engine.student_income_ic_check',
                        return_value={'readable': True, 'name_status': 'match'}):
            self.assertFalse(income_engine.member_cluster_complete(app, 'father'))

    def test_ic_name_mismatch_does_not_qualify(self):
        app = self._app('c')
        self._doc(app, 'parent_ic', 'father', vision_name='WRONG')
        self._doc(app, 'salary_slip', 'father')
        with mock.patch('apps.scholarship.income_engine.student_income_ic_check',
                        return_value={'readable': True, 'name_status': 'mismatch'}):
            self.assertFalse(income_engine.member_cluster_complete(app, 'father'))

    def test_off_salary_route_is_not_satisfied(self):
        app = self._app('d', income_route='str', income_earner='mother')
        self.assertFalse(income_engine.salary_income_satisfied(app))


class TestGateSuppression(_Base):
    """With one clean cluster, a SECOND member's missing/mismatched docs stop blocking."""

    def test_income_doc_blockers_clear_when_one_cluster_complete(self):
        app = self._app('e')  # mother + father selected; only mother will "qualify"
        with mock.patch('apps.scholarship.income_engine.member_cluster_complete',
                        side_effect=lambda a, m: m == 'mother'):
            self.assertEqual(services.income_doc_blockers(app), [])

    def test_extraneous_parent_ic_mismatch_suppressed_when_cluster_complete(self):
        app = self._app('f')
        # A misread father IC that fails the person check (the NATHIYAA case).
        self._doc(app, 'parent_ic', 'father', vision_name='RAJAANMALAYS')
        mismatch = {'name_status': 'mismatch', 'proof_name_status': 'no_ref',
                    'proof_nric_status': 'no_ref'}
        with mock.patch('apps.scholarship.income_engine.student_income_ic_check',
                        return_value=mismatch):
            # No clean cluster → the mismatch BLOCKS.
            with mock.patch('apps.scholarship.income_engine.member_cluster_complete',
                            return_value=False):
                self.assertIn('parent_ic_person_mismatch', services.document_red_blockers(app))
            # One clean cluster → the same mismatch is a soft Check-2 item, NOT a blocker.
            with mock.patch('apps.scholarship.income_engine.member_cluster_complete',
                            side_effect=lambda a, m: m == 'mother'):
                self.assertNotIn('parent_ic_person_mismatch', services.document_red_blockers(app))


class TestOcrNameGuard(TestCase):
    def test_fused_header_fragment_is_garbled(self):
        self.assertTrue(_name_looks_garbled('RAJAANMALAYS'))      # MALAYSIA header bled in
        self.assertTrue(_name_looks_garbled('SITIWARGANEGARA'))

    def test_clean_names_are_not_garbled(self):
        self.assertFalse(_name_looks_garbled('MAHENDIRAN A/L MUTHIAIAH'))
        self.assertFalse(_name_looks_garbled('RAJ KUMAR'))
        self.assertFalse(_name_looks_garbled('NIRMALA DEVI'))     # contains MALA, not MALAYS

    def test_extract_name_blanks_a_garbled_read(self):
        text = '750101105279\nRAJAANMALAYS\nKAD PENGENALAN'
        self.assertEqual(_extract_name(text), '')
