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


class TestTheFatherFallbackReadsTheChildRow(_Base):
    """Owner, 23 Nov 2026: the certificate's CHILD row on the mononym father fallback is the same
    row score as the mother path and the chip; the FATHER row stays the name alone."""

    FATHER = 'MURUGAN A/L RAJAN'
    FATHER_IC = '710303-10-5559'

    def _status(self, child_nric):
        app = make_application('submitted', cohort=self.cohort,
                               student=make_student(name='DIVYA', nric=STUDENT_IC),
                               income_route='salary', income_working_members=['father'])
        ic = _doc(app, 'parent_ic', 'father', name=self.FATHER, nric=self.FATHER_IC)
        bc = _doc(app, 'birth_certificate', fields={
            'bc_child_name': 'DIVA', 'bc_child_nric': child_nric,
            'bc_father_name': self.FATHER, 'bc_mother_name': MOTHER})
        return student_income_ic_check(ic)['name_status'], student_bc_check(bc)['child_status']

    def test_case_177_shape_on_the_father_path_is_a_match(self):
        # One-word name, a letter dropped (under today's 5-letter floor), the child's IC exact.
        self.assertEqual(self._status(STUDENT_IC), ('match', 'match'))

    def test_no_child_number_is_the_name_alone_as_today(self):
        self.assertEqual(self._status(''), ('mismatch', 'mismatch'))


class TestTheChainStandsInForTheParentRowOnly(_Base):
    """Review round 2, Finding 1: the IC-number chain (#9) checks the certificate's child by name
    alone, so it may vouch for the PARENT row only. The link is the child row's own score with a
    green parent row, in the chip and in the decision alike: an exact child name beside a far
    child number stays amber (the owner's table), whether or not the mother's IC is uploaded."""

    def _str(self, app, nric):
        _doc(app, 'str', fields={'recipient_name': MOTHER, 'recipient_nric': nric, 'status': 'Lulus',
                                 'year': str(timezone.localdate().year),
                                 'source_type': 'semakan_status'})

    def _case(self, child_nric, with_ic=True, ic_nric=MOTHER_IC, deferred=False, child=STUDENT):
        app = self._app('str', earner='mother')
        ic = _doc(app, 'parent_ic', 'mother', name=MOTHER, nric=ic_nric) if with_ic else None
        if deferred:
            from apps.scholarship.models import ApplicantDocument
            from apps.scholarship.read_errors import IC_SECOND_OPINION_ERROR, IC_SECOND_OPINION_UNTIL
            ApplicantDocument.objects.filter(id=ic.id).update(vision_fields={
                IC_SECOND_OPINION_ERROR: 'outage',
                IC_SECOND_OPINION_UNTIL: timezone.now().timestamp() + 3600})
            ic.refresh_from_db()
        bc = self._bc(app, child=child, child_nric=child_nric)
        self._str(app, MOTHER_IC)              # the certificate's mother number is the STR's
        return app, ic, bc

    def test_the_proving_case_is_pending_in_the_decision_and_amber_on_the_chip(self):
        app, ic, bc = self._case(FAR_IC)
        self.assertEqual(student_bc_check(bc)['link'], 'amber')
        self.assertEqual(student_income_ic_check(ic)['name_status'], 'pending')
        evidence, unresolved = self._income(app)
        self.assertNotIn('relationship_confirmed', evidence)
        self.assertNotIn('birth_cert_mismatch', unresolved)

    def test_the_chip_and_the_decision_agree_with_and_without_the_mothers_ic(self):
        # Before: amber with the right IC uploaded, the student's green tick without it.
        for with_ic in (True, False):
            with self.subTest(with_ic=with_ic):
                app, _, bc = self._case(FAR_IC, with_ic=with_ic)
                self.assertEqual(student_bc_check(bc)['link'], 'amber')
                evidence, _ = self._income(app)
                self.assertNotIn('relationship_confirmed', evidence)

    def test_the_chain_still_confirms_when_the_child_row_is_green(self):
        # The card in the mother's slot carries another number; the chain vouches for her row.
        app, ic, bc = self._case(STUDENT_IC, ic_nric=FAR_IC)
        self.assertEqual(student_bc_check(bc)['link'], 'green')
        self.assertEqual(student_income_ic_check(ic)['name_status'], 'match')
        evidence, _ = self._income(app)
        self.assertIn('relationship_confirmed', evidence)

    def test_another_childs_certificate_is_red_and_the_chain_does_not_hold(self):
        # Another child on the certificate (far name, far number). The chain needs a child name
        # that passes (`_bc_parent_identity`), so it does not hold here and the plain mother link
        # decides: red in the chip and the decision alike. Under the chain the child row is never
        # red or grey (review round 3).
        app, ic, bc = self._case(FAR_IC, child='SITI NUR AISYAH BINTI AHMAD')
        self.assertEqual(student_bc_check(bc)['link'], 'red')
        chk = student_income_ic_check(ic)
        self.assertFalse(chk['chain_verified'])
        self.assertEqual(chk['name_status'], 'mismatch')
        evidence, _ = self._income(app)
        self.assertNotIn('relationship_confirmed', evidence)

    def test_the_chain_still_works_with_the_unread_card_deferral(self):
        # TD-390: the card in the slot is half-read. A green child row still confirms; an amber
        # child row stays pending; neither turns red.
        for child_nric, link, status in ((STUDENT_IC, 'green', 'match'), (FAR_IC, 'amber', 'pending')):
            with self.subTest(child_nric=child_nric):
                app, ic, bc = self._case(child_nric, ic_nric=FAR_IC, deferred=True)
                self.assertEqual(student_bc_check(bc)['link'], link)
                self.assertEqual(student_income_ic_check(ic)['name_status'], status)
                _, unresolved = self._income(app)
                self.assertNotIn('birth_cert_mismatch', unresolved)

    def test_the_father_chain_reads_the_child_row_too(self):
        father, father_ic = 'MURUGAN A/L SELVAM', '710303-10-5559'  # the patronymic disagrees
        for child_nric, confirmed in ((STUDENT_IC, True), (FAR_IC, False)):
            with self.subTest(child_nric=child_nric):
                app = self._app('str', earner='father')
                ic = _doc(app, 'parent_ic', 'father', name=father, nric=father_ic)
                _doc(app, 'birth_certificate', fields={
                    'bc_child_name': STUDENT, 'bc_child_nric': child_nric,
                    'bc_father_name': father, 'bc_father_nric': father_ic})
                _doc(app, 'str', fields={'recipient_name': father, 'recipient_nric': father_ic,
                                         'status': 'Lulus', 'year': str(timezone.localdate().year),
                                         'source_type': 'semakan_status'})
                self.assertEqual(student_income_ic_check(ic)['name_status'],
                                 'match' if confirmed else 'pending')
                evidence, unresolved = self._income(app)
                self.assertEqual('relationship_confirmed' in evidence, confirmed)
                self.assertNotIn('father_patronymic_mismatch', unresolved)


    def test_a_patronymic_father_keeps_the_match_when_the_chain_holds(self):
        # Review round 3: the patronymic already links the father, and the certificate's father
        # number is the STR's / the payslip's, so the chain holds. A far child number must not
        # pull the IC check down to pending while the decision confirms; the two agree on match,
        # and the father's cluster stays complete.
        from apps.scholarship.income_engine import member_cluster_complete
        father, father_ic = 'RAMAN A/L GOPAL', '710303-10-5559'    # the patronymic agrees
        for route in ('str', 'salary'):
            with self.subTest(route=route):
                app = self._app(route, earner='father',
                                members=['father'] if route == 'salary' else ())
                ic = _doc(app, 'parent_ic', 'father', name=father, nric=father_ic)
                _doc(app, 'birth_certificate', fields={
                    'bc_child_name': STUDENT, 'bc_child_nric': FAR_IC,
                    'bc_father_name': father, 'bc_father_nric': father_ic})
                if route == 'str':
                    _doc(app, 'str', fields={'recipient_name': father, 'recipient_nric': father_ic,
                                             'status': 'Lulus',
                                             'year': str(timezone.localdate().year),
                                             'source_type': 'semakan_status'})
                else:
                    _doc(app, 'salary_slip', 'father', fields={
                        'name': father, 'nric': father_ic, 'gross_income': '2000'})
                chk = student_income_ic_check(ic)
                self.assertTrue(chk['chain_verified'])
                self.assertEqual(chk['name_status'], 'match')
                evidence, _ = self._income(app)
                self.assertIn('relationship_confirmed', evidence)
                self.assertTrue(member_cluster_complete(app, 'father'))


class TestATypedOnlyNameIsAmber(_Base):
    """Review round 2, Finding 2 (the lead's ruling): with no number, the IC-aware link name the
    decision has always used decides; a name only the typed profile name passes is AMBER in the
    chip and pending in the decision (before: the decision said mismatch, the chip green)."""

    def test_a_child_only_the_typed_name_passes_is_amber_in_both(self):
        app = make_application('submitted', cohort=self.cohort,
                               student=make_student(name='DEVI', nric=STUDENT_IC),
                               income_route='salary', income_working_members=['mother'])
        _doc(app, 'ic', name='DEVI A/P RAJAGOPAL', nric=STUDENT_IC)     # the link name
        ic = _doc(app, 'parent_ic', 'mother', name=MOTHER, nric=MOTHER_IC)
        bc = self._bc(app, child='DEVI KUMARI', child_nric='', mother_nric='')
        chip = student_bc_check(bc)
        self.assertEqual((chip['child_status'], chip['link']), ('check_one', 'amber'))
        self.assertEqual(student_income_ic_check(ic)['name_status'], 'pending')
