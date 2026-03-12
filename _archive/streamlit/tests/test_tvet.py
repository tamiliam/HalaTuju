import unittest
import sys
import os

# Add the parent directory (project root) to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import StudentProfile, check_eligibility

class TestTVETRequirements(unittest.TestCase):

    def setUp(self):
        # Base Requirement Template for TVET
        self.base_req = {
            'min_credits': 0, 'req_malaysian': 1,
            'pass_bm': 0, 'pass_history': 0,
            'pass_eng': 0, 'pass_math': 0,
            'no_colorblind': 0, 'no_disability': 0,
            'req_male': 0, 'req_female': 0,
            '3m_only': 0
        }

    def verify_application(self, test_label, student, requirements, expected_result, expected_reason_keyword=None):
        print(f"\n🔹 TVET TEST: {test_label}")
        print("=" * 60)
        
        is_eligible, audit_log = check_eligibility(student, requirements)

        for i, check in enumerate(audit_log, 1):
            status_icon = "✅ PASS" if check['passed'] else "❌ FAIL"
            reason_str = f" >> {check['reason']}" if check['reason'] else ""
            print(f"   Step {i}: {check['label']:<30} : {status_icon}{reason_str}")
        
        print("-" * 60)
        print(f"   🏁 FINAL VERDICT: {'ELIGIBLE' if is_eligible else 'REJECTED'}")
        print("=" * 60)

        if expected_result:
            self.assertTrue(is_eligible, f"[{test_label}] Expected ELIGIBLE but got REJECTED.")
        else:
            self.assertFalse(is_eligible, f"[{test_label}] Expected REJECTED but got ELIGIBLE.")
            
            if expected_reason_keyword:
                failures = [item['reason'] for item in audit_log if not item['passed']]
                found = any(expected_reason_keyword in (f or "") for f in failures)
                if not found:
                    self.fail(f"[{test_label}] Expected reason '{expected_reason_keyword}', got: {failures}")

    # --- TEST 1: The 'Tidak Ambil' Scenario (Ghost Student) ---
    def test_01_ghost_student_fails_3m(self):
        student = StudentProfile(
            grades={}, # Empty grades
            gender='Lelaki', nationality='Warganegara', 
            colorblind='Tidak', disability='Tidak'
        )
        req = self.base_req.copy()
        req['3m_only'] = 1
        
        # Should FAIL because they didn't even get a 'G'
        self.verify_application("Ghost Student (No Exams)", student, req, False, "BM dan Matematik")

    # --- TEST 2: The 'Bare Minimum' 3M Student ---
    def test_02_bare_minimum_3m_student(self):
        student = StudentProfile(
            grades={'bm': 'G', 'math': 'G'}, # Just attempted
            gender='Lelaki', nationality='Warganegara', 
            colorblind='Tidak', disability='Tidak'
        )
        req = self.base_req.copy()
        req['3m_only'] = 1
        
        self.verify_application("Bare Min 3M (G in BM/Math)", student, req, True)

    # --- TEST 3: Partial 3M (Missing Math) ---
    def test_03_partial_3m_failure(self):
        student = StudentProfile(
            grades={'bm': 'G'}, # Took BM, but skipped Math
            gender='Lelaki', nationality='Warganegara', 
            colorblind='Tidak', disability='Tidak'
        )
        req = self.base_req.copy()
        req['3m_only'] = 1
        
        self.verify_application("Partial 3M (No Math)", student, req, False, "BM dan Matematik")

    # --- TEST 4: IKBN Diploma (Eligible) ---
    def test_04_ikbn_diploma_req(self):
        # Simulating IKBN-DIP-001: 1 Credit, 2 Passes, Credit Math/Sci/Tech
        student = StudentProfile(
            grades={'bm': 'C', 'math': 'C', 'hist': 'E'}, 
            gender='Lelaki', nationality='Warganegara', 
            colorblind='Tidak', disability='Tidak'
        )
        req = self.base_req.copy()
        req['min_credits'] = 1
        req['min_pass'] = 2
        req['credit_math_sci_tech'] = 1 
        
        self.verify_application("IKBN Diploma (Eligible)", student, req, True)

    # --- TEST 5: IKBN Diploma (Fail Tech Req) ---
    def test_05_ikbn_diploma_fail(self):
        # Good grades but only PASS in Math (needs Credit for this course)
        student = StudentProfile(
            grades={'bm': 'A', 'hist': 'A', 'math': 'D'}, 
            gender='Lelaki', nationality='Warganegara', 
            colorblind='Tidak', disability='Tidak'
        )
        req = self.base_req.copy()
        req['min_credits'] = 1
        req['credit_math_sci_tech'] = 1
        
        self.verify_application("IKBN Diploma (Fail Tech Credit)", student, req, False, "Kredit Math/Sains/Teknikal")

    # --- TEST 6: Colorblind Check for TVET ---
    def test_06_tvet_colorblind(self):
        student = StudentProfile(
            grades={'bm': 'A', 'math': 'A'},
            gender='Lelaki', nationality='Warganegara', 
            colorblind='Ya', # Colorblind
            disability='Tidak'
        )
        req = self.base_req.copy()
        req['no_colorblind'] = 1
        
        self.verify_application("TVET Colorblind Block", student, req, False, "rabun warna")

if __name__ == '__main__':
    unittest.main()