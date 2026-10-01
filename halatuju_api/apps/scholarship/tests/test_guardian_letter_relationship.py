"""TD-089: a guardian earner's relationship is read off the guardianship letter's EXTRACTED name.

The extraction stores the letter's guardian as `vision_fields['fields']['guardian_name']` (the
field `doc_checks.student_guardianship_check` reads for the officer's card); the relationship
input read `vision_name`, which only the IC path sets — so a guardian with a perfectly good
letter stayed `pending` for ever. `vision_name` is still read for old rows.
"""
from django.test import TestCase

from apps.scholarship.income_engine import _relationship_inputs, student_income_ic_check
from apps.scholarship.tests.factories import make_application, make_cohort, make_student
from apps.scholarship.tests.test_income_evidence_homes import _doc

WARD = 'Divashini A/P Murugan'
GUARDIAN = 'Raja A/L Kumar'


class TestTheGuardianshipLetterIsRead(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(year=2026)

    def setUp(self):
        self.app = make_application('submitted', cohort=self.cohort,
                                    student=make_student(name=WARD),
                                    income_route='str', income_earner='guardian')
        self.ic = _doc(self.app, 'parent_ic', 'guardian', name=GUARDIAN, nric='700101-14-5555')

    def _status(self):
        return student_income_ic_check(self.ic)['name_status']

    def test_a_letter_naming_the_guardian_links_them(self):
        _doc(self.app, 'guardianship_letter',
             fields={'guardian_name': GUARDIAN, 'ward_name': WARD})
        self.assertEqual(self._status(), 'match')

    def test_a_letter_naming_SOMEONE_ELSE_is_a_mismatch_not_pending(self):
        _doc(self.app, 'guardianship_letter',
             fields={'guardian_name': 'Somebody Else', 'ward_name': WARD})
        self.assertEqual(self._status(), 'mismatch')

    # ── Review F1: the letter must be about THIS student (its ward), as a BC's child must ──
    def _letter(self, ward):
        return _doc(self.app, 'guardianship_letter',
                    fields={'guardian_name': GUARDIAN, 'ward_name': ward})

    def test_right_guardian_WRONG_ward_is_a_mismatch(self):
        letter = self._letter('Kavitha A/P Selvam')
        self.assertEqual(self._status(), 'mismatch')
        # …and the officer's cockpit row for the same letter says the same thing.
        from apps.scholarship.income_engine import student_guardianship_check
        self.assertEqual(student_guardianship_check(letter)['ward_status'], 'mismatch')

    def test_right_guardian_right_ward_is_a_match(self):
        letter = self._letter(WARD.upper())
        self.assertEqual(self._status(), 'match')
        from apps.scholarship.income_engine import student_guardianship_check
        self.assertEqual(student_guardianship_check(letter)['ward_status'], 'match')

    def test_ward_UNREAD_is_as_before(self):
        self._letter('')
        self.assertEqual(self._status(), 'match')

    def test_an_old_row_with_only_vision_name_still_reads(self):
        _doc(self.app, 'guardianship_letter', name=GUARDIAN)
        self.assertEqual(self._status(), 'match')

    def test_no_letter_is_still_pending(self):
        self.assertEqual(self._status(), 'pending')

    # ── The VERDICT engine reads the same letter (found while fixing review F1): three sites
    # (`verdict_engine` STR precedence + STR route, `verdict_income_salary`) read `vision_name`.
    def test_verdict_STR_ROUTE_LOGIC_reads_the_letter_too(self):
        """The STR precedence settles the fact when the STR names the guardian; when its recipient
        did not read, the ROUTE logic decides — a separate reader of the same letter (a bite
        that blanked it there stayed green until this test)."""
        evidence, _ = self._verdict_codes('str', WARD, recipient='')
        self.assertIn('relationship_confirmed', evidence)
        evidence, unresolved = self._verdict_codes('str', 'Kavitha A/P Selvam', recipient='')
        self.assertNotIn('relationship_confirmed', evidence)

    def _verdict_codes(self, route, ward, slip=False, recipient=GUARDIAN):
        from apps.scholarship.verdict_engine import build_verdict
        self.app.income_route = route
        self.app.income_earner = 'guardian' if route == 'str' else ''
        self.app.income_working_members = ['guardian'] if route == 'salary' else []
        self.app.save()
        self.ic.vision_fields = {}
        self.ic.save(update_fields=['vision_fields'])
        _doc(self.app, 'guardianship_letter', fields={'guardian_name': GUARDIAN, 'ward_name': ward})
        if route == 'str':
            _doc(self.app, 'str', fields={'recipient_name': recipient, 'status': 'Lulus',
                                          'year': '2026', 'source_type': 'letter'})
        if slip:
            d = _doc(self.app, 'salary_slip', 'guardian',
                     fields={'name': GUARDIAN, 'gross_income': 'RM2,000'})
            d.vision_fields['student_verdict'] = 'ok'
            d.save(update_fields=['vision_fields'])
        fact = {f['fact']: f for f in build_verdict(self.app)}['income']
        return ([i['code'] for i in fact['evidence']], [i['code'] for i in fact['unresolved']])

    def test_verdict_STR_route_confirms_a_guardian_off_the_letters_extracted_name(self):
        evidence, _ = self._verdict_codes('str', WARD)
        self.assertIn('relationship_confirmed', evidence)

    def test_verdict_STR_route_a_letter_for_another_child_confirms_nothing(self):
        evidence, _ = self._verdict_codes('str', 'Kavitha A/P Selvam')
        self.assertNotIn('relationship_confirmed', evidence)

    def test_verdict_SALARY_route_confirms_a_guardian_off_the_letter(self):
        evidence, _ = self._verdict_codes('salary', WARD, slip=True)
        self.assertIn('relationship_confirmed', evidence)

    def test_verdict_SALARY_route_a_letter_for_another_child_confirms_nothing(self):
        evidence, _ = self._verdict_codes('salary', 'Kavitha A/P Selvam', slip=True)
        self.assertNotIn('relationship_confirmed', evidence)

    def test_the_verdict_engine_version_records_the_change(self):
        # Review F4: the guardian link now reads the letter's guardian AND ward names, which can
        # move a fact — so it bumped (0 guardian-route households on 2026-10-01, the lead's count).
        from apps.scholarship import verdict_engine
        self.assertGreaterEqual(verdict_engine.VERDICT_ENGINE_VERSION, '2026-10-01.1')

    def test_the_birth_certificate_path_is_unchanged(self):
        _doc(self.app, 'birth_certificate', fields={
            'bc_child_name': WARD, 'bc_mother_name': 'Kamala A/P Suppiah',
            'bc_father_name': 'Murugan A/L Rajan'})
        _doc(self.app, 'guardianship_letter', fields={'guardian_name': GUARDIAN})
        self.assertEqual(_relationship_inputs(self.app, 'mother', 'Kamala A/P Suppiah'),
                         (WARD, 'Kamala A/P Suppiah', 'Murugan A/L Rajan', '', ''))
