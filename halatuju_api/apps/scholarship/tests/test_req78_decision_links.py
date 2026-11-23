"""Request #78: the DECISION readers score the mother / guardian link on name + IC number.

`student_income_ic_check`, the STR-precedence block, the declared STR route and the salary route
all pass `link_numbers` into `member_relationship_status`, so they read the same row score as the
case-page chips (`income_engine.match_bands`). Owner rulings, 23 Nov 2026: only RED blocks; with
no number on the document the name decides, as before. All names and IC numbers are made up.
"""
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.income_engine import _bc_link, student_bc_check, student_income_ic_check
from apps.scholarship.tests.factories import make_application, make_cohort, make_student
from apps.scholarship.tests.test_income_evidence_homes import _doc

STUDENT = 'DIVYA A/P RAMAN'
STUDENT_IC = '080808-14-0808'
MOTHER = 'KAMALA A/P SUPPIAH'
MOTHER_IC = '700101-14-5556'
FAR_IC = '650505-08-1234'          # a different person's number: many digits out
GUARDIAN = 'RAJA A/L KUMAR'
GUARDIAN_IC = '690202-10-5557'


class _Base(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(year=2026)

    def _app(self, route, earner='', members=()):
        return make_application('submitted', cohort=self.cohort,
                                student=make_student(name=STUDENT, nric=STUDENT_IC),
                                income_route=route, income_earner=earner,
                                income_working_members=list(members))

    def _bc(self, app, child=STUDENT, child_nric=STUDENT_IC, mother=MOTHER, mother_nric=MOTHER_IC):
        return _doc(app, 'birth_certificate', fields={
            'bc_child_name': child, 'bc_child_nric': child_nric,
            'bc_mother_name': mother, 'bc_mother_nric': mother_nric})

    def _income(self, app):
        from apps.scholarship.verdict_engine import build_verdict
        fact = {f['fact']: f for f in build_verdict(app)}['income']
        return ([i['code'] for i in fact['evidence']], [i['code'] for i in fact['unresolved']])


class TestTheParentIcCheckReadsBothRows(_Base):

    def _status(self, **bc):
        app = self._app('salary', members=['mother'])
        ic = _doc(app, 'parent_ic', 'mother', name=MOTHER, nric=MOTHER_IC)
        self._bc(app, **bc)
        return student_income_ic_check(ic)['name_status']

    def test_case_177_shape_is_a_match(self):
        # A 5-letter word of the surname with one letter dropped, the child's IC exact: green.
        # Before #78 the name-only link refused it, and the owed line blamed the parent's IC.
        self.assertEqual(_bc_link('DIVYA A/P RAMN', MOTHER, STUDENT, MOTHER), 'mismatch')
        self.assertEqual(self._status(child='DIVYA A/P RAMN'), 'match')

    def test_both_rows_exact_is_a_match(self):
        self.assertEqual(self._status(), 'match')

    def test_exact_name_far_child_number_is_pending_not_match(self):
        # The owner's table: exact name + far number is AMBER (a name is not unique) → no claim.
        self.assertEqual(self._status(child_nric=FAR_IC), 'pending')

    def test_exact_name_far_mother_number_is_pending_not_match(self):
        self.assertEqual(self._status(mother_nric=FAR_IC), 'pending')

    def test_far_name_exact_number_is_pending_never_red(self):
        # BLUE (a name change, a bad read) shows amber; it never asks the student to act.
        self.assertEqual(self._status(mother='LATHA A/P GOPAL'), 'pending')

    def test_both_far_is_a_mismatch(self):
        self.assertEqual(self._status(mother='LATHA A/P GOPAL', mother_nric=FAR_IC), 'mismatch')

    def test_no_numbers_on_the_certificate_is_the_name_alone(self):
        # Owner ruling 23 Nov 2026: no number on the document → the name decides, as before.
        self.assertEqual(self._status(child_nric='', mother_nric=''), 'match')
        self.assertEqual(self._status(child_nric='', mother_nric='', mother='LATHA A/P GOPAL'),
                         'mismatch')

    def test_the_chip_and_the_decision_agree(self):
        app = self._app('salary', members=['mother'])
        ic = _doc(app, 'parent_ic', 'mother', name=MOTHER, nric=MOTHER_IC)
        bc = self._bc(app, child='DIVYA A/P RAMN')
        self.assertEqual(student_bc_check(bc)['link'], 'green')
        self.assertEqual(student_income_ic_check(ic)['name_status'], 'match')


class TestTheVerdictRoutesReadBothRows(_Base):

    def _str(self, app, nric=MOTHER_IC, name=MOTHER):
        _doc(app, 'str', fields={'recipient_name': name, 'recipient_nric': nric, 'status': 'Lulus',
                                 'year': str(timezone.localdate().year),
                                 'source_type': 'semakan_status'})

    def test_str_route_confirms_the_case_177_shape(self):
        app = self._app('str', earner='mother')
        _doc(app, 'parent_ic', 'mother', name=MOTHER, nric=MOTHER_IC)
        self._bc(app, child='DIVYA A/P RAMN')
        self._str(app)
        evidence, unresolved = self._income(app)
        self.assertIn('relationship_confirmed', evidence)
        self.assertNotIn('birth_cert_mismatch', unresolved)

    def test_str_route_exact_names_far_number_confirms_nothing_and_blocks_nothing(self):
        app = self._app('str', earner='mother')
        _doc(app, 'parent_ic', 'mother', name=MOTHER, nric=MOTHER_IC)
        self._bc(app, child_nric=FAR_IC)
        self._str(app, nric='', name='')        # no recipient read: the route logic decides
        evidence, unresolved = self._income(app)
        self.assertNotIn('relationship_confirmed', evidence)
        self.assertNotIn('birth_cert_mismatch', unresolved)

    def test_the_number_chain_still_rescues_a_far_mother_row(self):
        # #9: the certificate's mother number IS the STR recipient's, so the earner is confirmed
        # even though the card in her slot carries another number.
        app = self._app('str', earner='mother')
        _doc(app, 'parent_ic', 'mother', name=MOTHER, nric=FAR_IC)
        self._bc(app)
        self._str(app, nric=MOTHER_IC)
        evidence, _ = self._income(app)
        self.assertIn('relationship_confirmed', evidence)

    def test_salary_route_guardian_far_number_confirms_nothing_and_blocks_nothing(self):
        app = self._app('salary', members=['guardian'])
        _doc(app, 'parent_ic', 'guardian', name=GUARDIAN, nric=GUARDIAN_IC)
        _doc(app, 'guardianship_letter', fields={'guardian_name': GUARDIAN,
                                                 'guardian_nric': FAR_IC, 'ward_name': STUDENT})
        evidence, unresolved = self._income(app)
        self.assertNotIn('relationship_confirmed', evidence)
        self.assertFalse([c for c in unresolved if 'mismatch' in c], unresolved)

    def test_salary_route_guardian_exact_number_confirms(self):
        app = self._app('salary', members=['guardian'])
        _doc(app, 'parent_ic', 'guardian', name=GUARDIAN, nric=GUARDIAN_IC)
        _doc(app, 'guardianship_letter', fields={'guardian_name': GUARDIAN,
                                                 'guardian_nric': GUARDIAN_IC, 'ward_name': STUDENT})
        evidence, _ = self._income(app)
        self.assertIn('relationship_confirmed', evidence)

    def test_salary_route_mother_both_far_is_still_red(self):
        app = self._app('salary', members=['mother'])
        _doc(app, 'parent_ic', 'mother', name=MOTHER, nric=MOTHER_IC)
        self._bc(app, mother='LATHA A/P GOPAL', mother_nric=FAR_IC)
        _, unresolved = self._income(app)
        self.assertIn('birth_cert_mismatch', unresolved)
