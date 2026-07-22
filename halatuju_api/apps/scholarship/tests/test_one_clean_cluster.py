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

    def test_no_cluster_is_not_satisfied_whatever_the_route(self):
        # Replaces the old `test_off_salary_route_is_not_satisfied` (owner 2026-07-22): it is the
        # EVIDENCE that decides now, not the declared route — but with no documents on file there
        # is still nothing to satisfy.
        app = self._app('d', income_route='str', income_earner='mother')
        self.assertFalse(income_engine.salary_income_satisfied(app))
        self.assertFalse(income_engine.income_established(app))


class TestEitherRouteSatisfies(_Base):
    """Owner 2026-07-22 — "it is either STR or salary; students may fulfil both but are not
    required to". #116: the STR failed the FORMAT gate (a BSN payment receipt classified
    source_type='unknown' → wrong_type → RED) while the mother was fully documented, and the
    salary evidence was never even inspected because `salary_income_satisfied` early-returned off
    the declared route. The complete cluster must carry the application through."""

    def _shape_116(self, suffix):
        """#116: declared the STR route, so never touched the salary checkboxes — the earners are
        discoverable only from the tags on the documents she actually uploaded."""
        app = self._app(suffix, income_route='str', income_earner='mother',
                        income_working_members=[])
        self._doc(app, 'parent_ic', 'mother', vision_name='VIGINESWARY A/P BATUMALAI')
        self._doc(app, 'salary_slip', 'mother', vision_name='VIGINESWARY A/P BATUMALAI')
        self._doc(app, 'birth_certificate')      # mother → birth certificate links her to the student
        return app

    def _clean_checks(self):
        return (mock.patch('apps.scholarship.income_engine.student_income_ic_check',
                           return_value={'readable': True, 'name_status': 'match'}),
                mock.patch('apps.scholarship.income_engine.student_income_proof_check',
                           return_value={'name_status': 'match', 'nric_status': 'match'}))

    def _failed_str(self, app):
        """A genuine bank STR receipt the format gate can't place → wrong_type (RED)."""
        return self._doc(app, 'str', 'mother', vision_fields={
            'fields': {'recipient_name': '', 'recipient_nric': '791128-08-6530',
                       'status': '', 'year': '2026', 'source_type': 'unknown'},
            'authenticity': {'status': 'genuine'},
        })

    def test_complete_salary_cluster_satisfies_on_the_str_route(self):
        app = self._shape_116('e116a')
        ic, proof = self._clean_checks()
        with ic, proof:
            self.assertTrue(income_engine.salary_income_satisfied(app))
            self.assertTrue(income_engine.income_established(app))

    def test_str_triplet_not_demanded_when_salary_is_complete(self):
        # No STR on file at all: the STR branch falls through instead of asking for str_missing.
        app = self._shape_116('e116b')
        ic, proof = self._clean_checks()
        with ic, proof:
            self.assertEqual(services.income_doc_blockers(app), [])

    def test_failed_str_does_not_block_when_salary_is_complete(self):
        # The #116 regression: the wrong_type STR must not hard-block submission.
        app = self._shape_116('e116c')
        self._failed_str(app)
        ic, proof = self._clean_checks()
        with ic, proof:
            self.assertNotIn('str_person_mismatch', services.document_red_blockers(app))
            self.assertEqual(services.income_doc_blockers(app), [])

    def test_failed_str_still_blocks_when_there_is_no_salary_cluster(self):
        # The guard-rail: without a complete cluster the failed STR must STILL block, else the
        # relaxation would wave through a student with no income evidence at all.
        app = self._app('e116d', income_route='str', income_earner='mother',
                        income_working_members=[])
        self._failed_str(app)
        self.assertFalse(income_engine.income_established(app))
        self.assertIn('str_person_mismatch', services.document_red_blockers(app))


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

    def test_str_route_dispositive_str_suppresses_extraneous_ic_mismatch(self):
        # #28: a valid father's STR + an extraneous MOTHER IC, whose cross-check against the
        # single-recipient STR 'mismatches' meaninglessly. A dispositive STR makes it soft.
        app = self._app('g', income_route='str', income_earner='father')
        self._doc(app, 'parent_ic', 'mother', vision_name='JEYASUTHA A/P JAGANATHAN')
        proof_mismatch = {'name_status': 'match', 'proof_name_status': 'mismatch',
                          'proof_nric_status': 'mismatch'}
        with mock.patch('apps.scholarship.income_engine.student_income_ic_check',
                        return_value=proof_mismatch):
            # No dispositive STR → the extraneous IC mismatch BLOCKS.
            with mock.patch('apps.scholarship.income_engine.household_str_status',
                            return_value=(None, None)):
                self.assertIn('parent_ic_person_mismatch', services.document_red_blockers(app))
            # Dispositive STR (matched to the father) → the mismatch is soft, NOT a blocker.
            with mock.patch('apps.scholarship.income_engine.household_str_status',
                            return_value=('current', 'father')):
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


class TestPatronymicFromIc(_Base):
    """#88: a typed profile name WITHOUT the A/P connector must not lose the father link when
    the student's own verified IC carries it — `student_name_for_link` prefers the IC read
    (same identity, anchored) so a dispositive STR settles income Certain, not Unsure."""

    def _app88(self, suffix, profile_name='THIVYA THANGARAJAN', ic_name='THIVYA A/P THANGARAJAN'):
        p = StudentProfile.objects.create(
            supabase_user_id=f'pat-{suffix}', name=profile_name, nric='080131-08-0788')
        app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='shortlisted',
            income_route='str', income_earner='father')
        if ic_name:
            self._doc(app, 'ic', '', vision_name=ic_name)
        self._doc(app, 'parent_ic', 'father', vision_name='THANGARAJAN A/L CHANDARIAH')
        return app

    def test_prefers_ic_read_when_typed_name_lacks_marker(self):
        app = self._app88('a')
        self.assertEqual(income_engine.student_name_for_link(app), 'THIVYA A/P THANGARAJAN')

    def test_keeps_typed_name_when_it_has_marker(self):
        app = self._app88('b', profile_name='THIVYA A/P THANGARAJAN')
        self.assertEqual(income_engine.student_name_for_link(app), 'THIVYA A/P THANGARAJAN')

    def test_ignores_ic_read_of_a_different_person(self):
        # The IC-name substitution is anchored on SAME-person agreement — a mismatching IC
        # read must never be adopted for the patronymic.
        app = self._app88('c', ic_name='KAVITHA A/P RAJAN')
        self.assertEqual(income_engine.student_name_for_link(app), 'THIVYA THANGARAJAN')

    def test_no_ic_uploaded_falls_back_to_typed_name(self):
        app = self._app88('d', ic_name='')
        self.assertEqual(income_engine.student_name_for_link(app), 'THIVYA THANGARAJAN')

    def test_str_precedence_fires_for_marker_less_typed_name(self):
        # The #88 regression end-to-end: dispositive current STR (father) + father IC + a
        # typed name without the connector -> income VERIFIED with the relationship
        # confirmed (was: 'recommend' + income_unverified_needs_interview).
        from apps.scholarship.verdict_engine import build_verdict
        app = self._app88('e')
        with mock.patch('apps.scholarship.income_engine.household_str_status',
                        return_value=('current', 'father')):
            income = next(f for f in build_verdict(app) if f['fact'] == 'income')
        self.assertEqual(income['status'], 'verified')
        codes = [e['code'] for e in income['evidence']]
        self.assertIn('relationship_confirmed', codes)
        self.assertIn('str_verified', codes)
        self.assertEqual(income['unresolved'], [])
