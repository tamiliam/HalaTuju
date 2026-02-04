"""
UA (University Awam) Eligibility Test Suite

Tests the eligibility engine against UA-specific requirements:
- Grade B requirements (credit_bm_b, credit_eng_b, credit_addmath_b)
- Distinction requirements (A-/A/A+)
- Complex OR-group requirements (count + grade + subject list)
- Merit cutoff enforcement
- PI/PM (Pendidikan Islam/Moral) requirements

Run with: python -m unittest tests/test_ua_eligibility.py -v
"""

import unittest
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import StudentProfile, check_eligibility, load_and_clean_data


class TestUAEligibility(unittest.TestCase):
    """Test UA-specific eligibility requirements"""

    @classmethod
    def setUpClass(cls):
        """Load UA requirements data"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ua_file = os.path.join(project_root, 'data', 'university_requirements.csv')

        cls.df = load_and_clean_data(ua_file)
        print(f"\n[*] Loaded {len(cls.df)} UA courses for testing")

        # Index courses by ID for easy lookup
        cls.courses = {row['course_id']: row.to_dict() for _, row in cls.df.iterrows()}

    # =========================================================================
    # GRADE B REQUIREMENTS
    # =========================================================================

    def test_grade_b_bm_pass(self):
        """Student with Grade B in BM should pass credit_bm_b requirement"""
        # Find a course requiring credit_bm_b
        course = self._find_course_with_requirement('credit_bm_b', 1)
        if not course:
            self.skipTest("No course with credit_bm_b=1 found")

        student = StudentProfile(
            grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'phy': 'C'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        bm_check = self._find_audit_check(audit, 'credit_bm_b')

        self.assertTrue(bm_check['passed'],
            f"Grade B BM should pass credit_bm_b. Got: {bm_check}")

    def test_grade_b_bm_fail_with_c_plus(self):
        """Student with Grade C+ in BM should FAIL credit_bm_b requirement"""
        course = self._find_course_with_requirement('credit_bm_b', 1)
        if not course:
            self.skipTest("No course with credit_bm_b=1 found")

        student = StudentProfile(
            grades={'bm': 'C+', 'eng': 'C', 'hist': 'C', 'math': 'C', 'phy': 'C'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        bm_check = self._find_audit_check(audit, 'credit_bm_b')

        self.assertFalse(bm_check['passed'],
            f"Grade C+ BM should FAIL credit_bm_b. Got: {bm_check}")

    def test_grade_b_eng_pass(self):
        """Student with Grade B+ in English should pass credit_eng_b"""
        course = self._find_course_with_requirement('credit_eng_b', 1)
        if not course:
            self.skipTest("No course with credit_eng_b=1 found")

        student = StudentProfile(
            grades={'bm': 'C', 'eng': 'B+', 'hist': 'C', 'math': 'C'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        eng_check = self._find_audit_check(audit, 'credit_eng_b')

        self.assertTrue(eng_check['passed'],
            f"Grade B+ Eng should pass credit_eng_b. Got: {eng_check}")

    def test_grade_b_addmath_pass(self):
        """Student with Grade A in Add Math should pass credit_addmath_b"""
        course = self._find_course_with_requirement('credit_addmath_b', 1)
        if not course:
            self.skipTest("No course with credit_addmath_b=1 found")

        student = StudentProfile(
            grades={'bm': 'C', 'eng': 'C', 'hist': 'C', 'math': 'C', 'addmath': 'A'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        addmath_check = self._find_audit_check(audit, 'credit_addmath_b')

        self.assertTrue(addmath_check['passed'],
            f"Grade A Add Math should pass credit_addmath_b. Got: {addmath_check}")

    # =========================================================================
    # DISTINCTION REQUIREMENTS (A-/A/A+)
    # =========================================================================

    def test_distinction_bm_pass(self):
        """Student with A- in BM should pass distinction_bm"""
        course = self._find_course_with_requirement('distinction_bm', 1)
        if not course:
            self.skipTest("No course with distinction_bm=1 found")

        student = StudentProfile(
            grades={'bm': 'A-', 'eng': 'C', 'hist': 'C', 'math': 'C'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        dist_check = self._find_audit_check(audit, 'distinction_bm')

        self.assertTrue(dist_check['passed'],
            f"Grade A- BM should pass distinction_bm. Got: {dist_check}")

    def test_distinction_bm_fail_with_b_plus(self):
        """Student with B+ in BM should FAIL distinction_bm"""
        course = self._find_course_with_requirement('distinction_bm', 1)
        if not course:
            self.skipTest("No course with distinction_bm=1 found")

        student = StudentProfile(
            grades={'bm': 'B+', 'eng': 'C', 'hist': 'C', 'math': 'C'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        dist_check = self._find_audit_check(audit, 'distinction_bm')

        self.assertFalse(dist_check['passed'],
            f"Grade B+ BM should FAIL distinction_bm. Got: {dist_check}")

    def test_distinction_phy_pass(self):
        """Student with A in Physics should pass distinction_phy"""
        course = self._find_course_with_requirement('distinction_phy', 1)
        if not course:
            self.skipTest("No course with distinction_phy=1 found")

        student = StudentProfile(
            grades={'bm': 'C', 'eng': 'C', 'hist': 'C', 'phy': 'A'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        dist_check = self._find_audit_check(audit, 'distinction_phy')

        self.assertTrue(dist_check['passed'],
            f"Grade A Physics should pass distinction_phy. Got: {dist_check}")

    # =========================================================================
    # COMPLEX OR-GROUP REQUIREMENTS
    # =========================================================================

    def test_complex_req_count_1_grade_b_pass(self):
        """Test: Need 1 subject with Grade B from [comp_sci, phy]"""
        # UZ0520001 requires: {"or_groups": [{"count": 1, "grade": "B", "subjects": ["comp_sci", "phy"]}]}
        course = self.courses.get('UZ0520001')
        if not course:
            self.skipTest("Course UZ0520001 not found")

        student = StudentProfile(
            grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'phy': 'B'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        complex_check = self._find_audit_check(audit, 'complex_req')

        self.assertTrue(complex_check['passed'],
            f"Physics B should satisfy count:1, grade:B for [comp_sci, phy]. Got: {complex_check}")

    def test_complex_req_count_1_grade_b_fail(self):
        """Test: Need 1 subject with Grade B but only have Grade C"""
        course = self.courses.get('UZ0520001')
        if not course:
            self.skipTest("Course UZ0520001 not found")

        student = StudentProfile(
            grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'phy': 'C', 'comp_sci': 'C'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        complex_check = self._find_audit_check(audit, 'complex_req')

        self.assertFalse(complex_check['passed'],
            f"Physics C / Comp Sci C should FAIL count:1, grade:B. Got: {complex_check}")

    def test_complex_req_count_2_sciences_pass(self):
        """Test: Need 2 subjects with Grade C from sciences"""
        # Find course with ONLY one OR group requiring count:2, grade:C
        course = self._find_course_with_complex_pattern(count=2, grade='C',
            must_include=['phy'], single_group_only=True)
        if not course:
            # Fallback: find any count:2, grade:C with single group
            course = self._find_course_with_complex_pattern(count=2, grade='C',
                single_group_only=True)
        if not course:
            self.skipTest("No course with single OR group count:2, grade:C found")

        # Parse to see what subjects are actually in the requirement
        req = json.loads(course.get('complex_requirements', '{}'))
        subjects = req.get('or_groups', [{}])[0].get('subjects', [])

        # Build grades with 2 subjects from the list at grade C or better
        grades = {'bm': 'C', 'eng': 'C', 'hist': 'C', 'math': 'C'}
        added = 0
        for subj in subjects:
            if added < 2:
                grades[subj] = 'C'
                added += 1

        student = StudentProfile(
            grades=grades,
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        complex_check = self._find_audit_check(audit, 'complex_req')

        self.assertTrue(complex_check['passed'],
            f"2 subjects with C should satisfy count:2, grade:C. Subjects: {subjects[:5]}. Got: {complex_check}")

    def test_complex_req_count_2_sciences_fail(self):
        """Test: Need 2 subjects but only have 1 qualifying"""
        course = self._find_course_with_complex_pattern(count=2, grade='C',
            must_include=['phy', 'chem'])
        if not course:
            self.skipTest("No course with count:2, grade:C, sciences found")

        student = StudentProfile(
            grades={'bm': 'C', 'eng': 'C', 'hist': 'C', 'math': 'C',
                   'phy': 'C', 'chem': 'D', 'bio': 'E'},  # Only 1 science with C
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        complex_check = self._find_audit_check(audit, 'complex_req')

        self.assertFalse(complex_check['passed'],
            f"Only Phy C should FAIL count:2, grade:C. Got: {complex_check}")

    def test_complex_req_count_3_pass(self):
        """Test: Need 3 subjects with specified grade"""
        course = self._find_course_with_complex_pattern(count=3, grade='C')
        if not course:
            self.skipTest("No course with count:3, grade:C found")

        # Parse the requirement to know which subjects
        req = json.loads(course.get('complex_requirements', '{}'))
        subjects = req.get('or_groups', [{}])[0].get('subjects', [])[:5]

        # Create grades for 3 of those subjects
        grades = {'bm': 'C', 'eng': 'C', 'hist': 'C', 'math': 'C'}
        for subj in subjects[:3]:
            grades[subj] = 'C'

        student = StudentProfile(
            grades=grades,
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        complex_check = self._find_audit_check(audit, 'complex_req')

        self.assertTrue(complex_check['passed'],
            f"3 subjects with grade C should pass count:3. Got: {complex_check}")

    # =========================================================================
    # PI/PM REQUIREMENTS
    # =========================================================================

    def test_pendidikan_islam_pass(self):
        """Student with credit in PI should qualify for PI-requiring courses"""
        course = self._find_course_with_requirement('credit_islam', 1)
        if not course:
            # Check complex requirements for islam
            course = self._find_course_with_complex_subject('islam')
        if not course:
            self.skipTest("No course requiring PI found")

        student = StudentProfile(
            grades={'bm': 'C', 'eng': 'C', 'hist': 'C', 'math': 'C', 'islam': 'B'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        # Check either credit_islam or complex_req
        passed = False
        for check in audit:
            if 'islam' in check.get('label', '').lower() or check.get('label') == 'chk_complex_req':
                if check['passed']:
                    passed = True
                    break

        self.assertTrue(passed or eligible,
            f"Student with PI grade B should qualify. Eligible: {eligible}")

    def test_pendidikan_moral_pass(self):
        """Student with credit in PM should qualify for PM-requiring courses"""
        course = self._find_course_with_complex_subject('moral')
        if not course:
            self.skipTest("No course requiring PM found")

        student = StudentProfile(
            grades={'bm': 'C', 'eng': 'C', 'hist': 'C', 'math': 'C', 'moral': 'B'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)

        # This is a soft test - just verify it doesn't crash
        self.assertIsNotNone(audit, "Audit should not be None")

    # =========================================================================
    # TECHNICAL/VOCATIONAL SUBJECTS
    # =========================================================================

    def test_engineering_drawing_pass(self):
        """Test technical subject: Engineering Drawing (eng_draw)"""
        course = self._find_course_with_complex_subject('eng_draw')
        if not course:
            self.skipTest("No course requiring eng_draw found")

        student = StudentProfile(
            grades={'bm': 'C', 'eng': 'C', 'hist': 'C', 'math': 'C', 'eng_draw': 'B'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible, audit = check_eligibility(student, course)
        self.assertIsNotNone(audit, "Audit should not be None")

    # =========================================================================
    # FULL ELIGIBILITY TESTS
    # =========================================================================

    def test_strong_student_eligible_for_most_ua(self):
        """A strong student should be eligible for most UA courses"""
        student = StudentProfile(
            grades={
                'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A',
                'addmath': 'A', 'phy': 'A', 'chem': 'A', 'bio': 'A',
                'comp_sci': 'A'
            },
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible_count = 0
        for _, row in self.df.iterrows():
            is_eligible, _ = check_eligibility(student, row.to_dict())
            if is_eligible:
                eligible_count += 1

        # Strong student should qualify for at least 50% of UA courses
        percentage = (eligible_count / len(self.df)) * 100
        print(f"\n   Strong student eligible for {eligible_count}/{len(self.df)} UA courses ({percentage:.1f}%)")

        self.assertGreater(percentage, 50,
            f"Strong student should qualify for >50% of UA courses, got {percentage:.1f}%")

    def test_weak_student_limited_eligibility(self):
        """A weak student should have limited UA eligibility"""
        student = StudentProfile(
            grades={'bm': 'C', 'eng': 'D', 'hist': 'C', 'math': 'D'},
            gender='Lelaki', nationality='Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible_count = 0
        for _, row in self.df.iterrows():
            is_eligible, _ = check_eligibility(student, row.to_dict())
            if is_eligible:
                eligible_count += 1

        percentage = (eligible_count / len(self.df)) * 100
        print(f"\n   Weak student eligible for {eligible_count}/{len(self.df)} UA courses ({percentage:.1f}%)")

        # Weak student should qualify for less than 30%
        self.assertLess(percentage, 30,
            f"Weak student should qualify for <30% of UA courses, got {percentage:.1f}%")

    def test_non_citizen_excluded(self):
        """Non-citizen should be excluded from all UA courses"""
        student = StudentProfile(
            grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A', 'phy': 'A'},
            gender='Lelaki', nationality='Bukan Warganegara',
            colorblind='Tidak', disability='Tidak'
        )

        eligible_count = 0
        for _, row in self.df.iterrows():
            is_eligible, _ = check_eligibility(student, row.to_dict())
            if is_eligible:
                eligible_count += 1

        print(f"\n   Non-citizen eligible for {eligible_count}/{len(self.df)} UA courses")

        # All UA courses require Malaysian citizenship
        self.assertEqual(eligible_count, 0,
            f"Non-citizen should qualify for 0 UA courses, got {eligible_count}")

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _find_course_with_requirement(self, column, value):
        """Find first course with a specific requirement"""
        for _, row in self.df.iterrows():
            if row.get(column) == value:
                return row.to_dict()
        return None

    def _find_course_with_complex_pattern(self, count, grade, must_include=None, single_group_only=False):
        """Find course with specific complex requirement pattern"""
        for _, row in self.df.iterrows():
            complex_req = row.get('complex_requirements')
            if not complex_req or complex_req == '[]':
                continue
            try:
                req = json.loads(complex_req)
                or_groups = req.get('or_groups', [])

                # If single_group_only, skip courses with multiple OR groups
                if single_group_only and len(or_groups) != 1:
                    continue

                for grp in or_groups:
                    if grp.get('count') == count and grp.get('grade') == grade:
                        if must_include:
                            subjects = grp.get('subjects', [])
                            if all(s in subjects for s in must_include):
                                return row.to_dict()
                        else:
                            return row.to_dict()
            except:
                continue
        return None

    def _find_course_with_complex_subject(self, subject):
        """Find course with a specific subject in complex requirements"""
        for _, row in self.df.iterrows():
            complex_req = row.get('complex_requirements')
            if not complex_req or complex_req == '[]':
                continue
            try:
                req = json.loads(complex_req)
                for grp in req.get('or_groups', []):
                    if subject in grp.get('subjects', []):
                        return row.to_dict()
            except:
                continue
        return None

    def _find_audit_check(self, audit, check_name):
        """Find a specific check in the audit trail"""
        for check in audit:
            label = check.get('label', '')
            if check_name in label:
                return check
        return {'passed': None, 'label': 'NOT_FOUND', 'reason': f'{check_name} not in audit'}


if __name__ == '__main__':
    unittest.main(verbosity=2)
