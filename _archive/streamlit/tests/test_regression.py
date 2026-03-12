import unittest
import sys
import os

# Add parent directory to path to import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import StudentProfile, check_eligibility

class TestAdmissionsAudit(unittest.TestCase):

    def setUp(self):
        # 1. Define Standard Requirements (using INTEGERS now!)
        self.req_diploma = {
            'min_credits': 3,          # Changed '3' to 3
            'pass_bm': 1,              # Changed '1' to 1
            'pass_history': 1,
            'req_malaysian': 1,
            'req_male': 0,             # 0 means "Not required", not "False"
            'req_female': 0,
            'no_colorblind': 1,
            'no_disability': 1,
            
            # Specific Subject Credits
            'credit_math': 0, 
            'credit_science': 0
        }

        # 2. Define Standard Student (Ali)
        self.student_ali = StudentProfile(
            grades={'bm': 'C', 'eng': 'C', 'math': 'C', 'hist': 'C', 'sci': 'C'},
            gender='Lelaki', 
            nationality='Warganegara',
            colorblind='Tidak',
            disability='Tidak'
        )

    # --- TEST 1: Logic Check (Internal) ---
    def test_01_credit_calculation_completeness(self):
        """Test if the system correctly counts credits for all passing grades"""
        grades = {
            'A+': 'A+', 'A': 'A', 'A-': 'A-', 
            'B+': 'B+', 'B': 'B', 'C+': 'C+', 'C': 'C'
        }
        student = StudentProfile(grades, 'Lelaki', 'Warganegara', 'Tidak', 'Tidak')
        
        # Verify credits count
        self.assertEqual(student.credits, 7, f"Expected 7 Credits, got {student.credits}")
        print("\n🔹 TEST: Credit Calculation Completeness (Internal Unit Test)")
        print(f"   Subjects Tested: {len(grades)}")
        print(f"   Credits Counted: {student.credits}")
        print("   ✅ PASS")

    # --- TEST 2: Boundary Check ---
    def test_02_credit_boundary_c_vs_d(self):
        """Test strictly that C counts as credit but D does not"""
        student = StudentProfile(
            grades={'math': 'C', 'bm': 'C', 'hist': 'D'}, # 2 Credits
            gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
        )
        self.assertEqual(student.credits, 2)
        print("\n🔹 TEST: Credit Boundary (C vs D)")
        print("   Math(C) + BM(C) + Hist(D) = 2 Credits")
        print("   ✅ PASS")

    # --- TEST 3: Fail BM Gatekeeper ---
    def test_03_fail_bm_gatekeeper(self):
        # Ali fails BM
        self.student_ali.grades['bm'] = 'G'
        
        is_eligible, audit = check_eligibility(self.student_ali, self.req_diploma)
        
        self.assertFalse(is_eligible)
        print("\n🔹 TEST: Fail BM Gatekeeper")
        print("="*60)
        for log in audit:
            status = "✅ PASS" if log['passed'] else f"❌ FAIL >> {log['reason']}"
            print(f"   Step {audit.index(log)+1}: {log['label']:<30} : {status}")
        print("-" * 60)
        print("   🏁 FINAL VERDICT: REJECTED")
        print("="*60)

    # --- TEST 4: Gender Checks (Male Only) ---
    def test_04_male_only_requirement(self):
        req = self.req_diploma.copy()
        req['req_male'] = 1 # Strict Male Requirement
        
        # Student is Female
        student_female = StudentProfile(
            grades={'bm':'C', 'hist':'C', 'math':'C'},
            gender='Perempuan', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
        )
        
        is_eligible, audit = check_eligibility(student_female, req)
        self.assertFalse(is_eligible)
        print("\n🔹 TEST: Male Only Check")
        print("="*60)
        for log in audit:
            status = "✅ PASS" if log['passed'] else f"❌ FAIL >> {log['reason']}"
            print(f"   Step {audit.index(log)+1}: {log['label']:<30} : {status}")
        print("-" * 60)
        print("   🏁 FINAL VERDICT: REJECTED")
        print("="*60)

    # --- TEST 5: Gender Checks (Female Only) ---
    def test_05_female_only_requirement(self):
        req = self.req_diploma.copy()
        req['req_female'] = 1
        
        student_male = StudentProfile(
            grades={'bm':'C', 'hist':'C', 'math':'C'},
            gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
        )
        
        is_eligible, audit = check_eligibility(student_male, req)
        self.assertFalse(is_eligible)
        print("\n🔹 TEST: Female Only Check")
        print("="*60)
        for log in audit:
            status = "✅ PASS" if log['passed'] else f"❌ FAIL >> {log['reason']}"
            print(f"   Step {audit.index(log)+1}: {log['label']:<30} : {status}")
        print("-" * 60)
        print("   🏁 FINAL VERDICT: REJECTED")
        print("="*60)

    # --- TEST 6: Colorblind Blocker ---
    def test_06_colorblind_blocker(self):
        req = self.req_diploma.copy()
        req['no_colorblind'] = 1
        
        student = StudentProfile(
            grades={'bm':'C', 'hist':'C', 'math':'C'},
            gender='Lelaki', nationality='Warganegara', 
            colorblind='Ya', # Is Colorblind
            disability='Tidak'
        )
        
        is_eligible, audit = check_eligibility(student, req)
        self.assertFalse(is_eligible)
        print("\n🔹 TEST: Colorblind Blocker")
        print("="*60)
        for log in audit:
            status = "✅ PASS" if log['passed'] else f"❌ FAIL >> {log['reason']}"
            print(f"   Step {audit.index(log)+1}: {log['label']:<30} : {status}")
        print("-" * 60)
        print("   🏁 FINAL VERDICT: REJECTED")
        print("="*60)

    # --- TEST 7: Disability Blocker ---
    def test_07_disability_blocker(self):
        req = self.req_diploma.copy()
        req['no_disability'] = 1
        
        student = StudentProfile(
            grades={'bm':'C', 'hist':'C', 'math':'C'},
            gender='Lelaki', nationality='Warganegara', 
            colorblind='Tidak', 
            disability='Ya' # Has Disability
        )
        
        is_eligible, audit = check_eligibility(student, req)
        self.assertFalse(is_eligible)
        print("\n🔹 TEST: Disability Blocker")
        print("="*60)
        for log in audit:
            status = "✅ PASS" if log['passed'] else f"❌ FAIL >> {log['reason']}"
            print(f"   Step {audit.index(log)+1}: {log['label']:<30} : {status}")
        print("-" * 60)
        print("   🏁 FINAL VERDICT: REJECTED")
        print("="*60)

    # --- TEST 8: Specific Subject Credit ---
    def test_08_specific_credit_requirement(self):
        req = self.req_diploma.copy()
        req['credit_math'] = 1 # Must have Credit in Math
        
        # Student has D in Math
        student = StudentProfile(
            grades={'bm':'C', 'hist':'C', 'math':'D'},
            gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
        )
        
        is_eligible, audit = check_eligibility(student, req)
        self.assertFalse(is_eligible)
        print("\n🔹 TEST: Specific Credit (Math)")
        print("="*60)
        for log in audit:
            status = "✅ PASS" if log['passed'] else f"❌ FAIL >> {log['reason']}"
            print(f"   Step {audit.index(log)+1}: {log['label']:<30} : {status}")
        print("-" * 60)
        print("   🏁 FINAL VERDICT: REJECTED")
        print("="*60)

    # --- TEST 9: Min Credits Logic ---
    def test_09_min_credits_fail(self):
        req = self.req_diploma.copy()
        req['min_credits'] = 3
        
        # Student has only 2 credits
        student = StudentProfile(
            grades={'bm':'C', 'hist':'C', 'math':'D'}, # 2 Credits
            gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
        )
        
        is_eligible, audit = check_eligibility(student, req)
        self.assertFalse(is_eligible)
        print("\n🔹 TEST: Min Credits Fail")
        print("="*60)
        for log in audit:
            status = "✅ PASS" if log['passed'] else f"❌ FAIL >> {log['reason']}"
            print(f"   Step {audit.index(log)+1}: {log['label']:<30} : {status}")
        print("-" * 60)
        print("   🏁 FINAL VERDICT: REJECTED")
        print("="*60)

    # --- TEST 10: Perfect Student (Should Pass) ---
    def test_10_perfect_student(self):
        req = self.req_diploma.copy()
        req['min_credits'] = 3
        req['credit_math'] = 0 # No specific Math credit needed
        
        # Student has 3 Credits
        student = StudentProfile(
            grades={'bm':'C', 'hist':'C', 'math':'C'}, # 3 Credits
            gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
        )
        
        is_eligible, audit = check_eligibility(student, req)
        
        self.assertTrue(is_eligible)
        print("\n🔹 TEST: Perfect Student")
        print("="*60)
        for log in audit:
            status = "✅ PASS" if log['passed'] else f"❌ FAIL >> {log['reason']}"
            print(f"   Step {audit.index(log)+1}: {log['label']:<30} : {status}")
        print("-" * 60)
        print("   🏁 FINAL VERDICT: ELIGIBLE")
        print("="*60)

if __name__ == '__main__':
    unittest.main()