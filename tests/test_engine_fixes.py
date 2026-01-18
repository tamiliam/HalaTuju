import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import check_eligibility, StudentProfile

class TestEngineFixes(unittest.TestCase):
    
    def make_student(self, grades, tech=False, voc=False):
        # Defaults
        defaults = {
            'bm': 'C', 'eng': 'C', 'hist': 'C', 'math': 'C', 
            'sci': 'C', 'phy': 'G', 'chem': 'G', 'bio': 'G', 'addmath': 'G'
        }
        defaults.update(grades)
        return StudentProfile(
            grades=defaults, 
            gender='Lelaki', 
            nationality='Warganegara', 
            colorblind='Tidak', 
            disability='Tidak',
            other_tech=tech,
            other_voc=voc
        )

    def test_credit_bmbi(self):
        # Policy: Credit BM OR Credit English
        req = {'credit_bmbi': 1}
        
        # 1. Credit BM only -> Pass
        s1 = self.make_student({'bm': 'C', 'eng': 'D'}) # C is credit, D is pass
        passed, _ = check_eligibility(s1, req)
        self.assertTrue(passed, "Should pass with Credit BM")

        # 2. Credit Eng only -> Pass
        s2 = self.make_student({'bm': 'D', 'eng': 'C'})
        passed, _ = check_eligibility(s2, req)
        self.assertTrue(passed, "Should pass with Credit English")

        # 3. No Credit -> Fail
        s3 = self.make_student({'bm': 'D', 'eng': 'D'})
        passed, audit = check_eligibility(s3, req)
        self.assertFalse(passed, "Should fail without Credit BM or English")

    def test_credit_stv(self):
        # Policy: Credit Science (ANY) OR Technical OR Vocational
        req = {'credit_stv': 1}

        # 1. Credit Bio (Science) -> Pass
        s1 = self.make_student({'bio': 'C'})
        passed, _ = check_eligibility(s1, req)
        self.assertTrue(passed, "Should pass with Credit Bio")

        # 2. Credit Tech -> Pass
        # Assuming 'tech' grade is used.
        s2 = self.make_student({'tech': 'C'})
        passed, _ = check_eligibility(s2, req)
        self.assertTrue(passed, "Should pass with Credit Tech")

        # 3. Credit Voc -> Pass
        s3 = self.make_student({'voc': 'C'})
        passed, _ = check_eligibility(s3, req)
        self.assertTrue(passed, "Should pass with Credit Voc")
        
        # 4. Pass only (No Credit) -> Fail
        s4 = self.make_student({'bio': 'D', 'tech': 'D', 'voc': 'D', 'sci': 'D'})
        passed, _ = check_eligibility(s4, req)
        self.assertFalse(passed, "Should fail with only Passes (requires Credit)")

    def test_pass_math_science_tvet(self):
        # Policy: Pass Math OR Science (NO BIO)
        req = {'pass_math_science': 1}

        # 1. Pass Bio only -> Fail
        s1 = self.make_student({'math': 'G', 'bio': 'D', 'sci': 'G'}) # G is fail, D is pass
        passed, _ = check_eligibility(s1, req)
        self.assertFalse(passed, "Should fail if only Bio is passed (Bio excluded)")

        # 2. Pass Physics -> Pass
        s2 = self.make_student({'math': 'G', 'phy': 'D'})
        passed, _ = check_eligibility(s2, req)
        self.assertTrue(passed, "Should pass with Physics")

        # 3. Pass Math -> Pass
        s3 = self.make_student({'math': 'D'})
        passed, _ = check_eligibility(s3, req)
        self.assertTrue(passed, "Should pass with Math")

    def test_pass_science_tech_tvet(self):
        # Policy: Pass Science (NO BIO) OR Technical Subject
        req = {'pass_science_tech': 1}

        # 1. Pass Bio only -> Fail
        s1 = self.make_student({'bio': 'D', 'sci': 'G', 'chem': 'G'})
        passed, _ = check_eligibility(s1, req)
        self.assertFalse(passed, "Should fail if only Bio is passed (Bio excluded)")

        # 2. Pass Tech -> Pass
        s2 = self.make_student({'tech': 'D'})
        passed, _ = check_eligibility(s2, req)
        self.assertTrue(passed, "Should pass with Tech subject")

        # 3. Pass Physics -> Pass
        s3 = self.make_student({'phy': 'D'})
        passed, _ = check_eligibility(s3, req)
        self.assertTrue(passed, "Should pass with Physics")

    def test_pass_stv_poly(self):
        # Policy: Pass Science (ANY, including Bio) OR Tech OR Voc
        req = {'pass_stv': 1}

        # 1. Pass Bio -> Pass (Poly allows Bio here)
        s1 = self.make_student({'bio': 'D', 'sci': 'G'}) 
        passed, _ = check_eligibility(s1, req)
        self.assertTrue(passed, "Should pass with Bio (StV Poly rule includes all Science)")

        # 2. Pass Tech -> Pass
        s2 = self.make_student({'tech': 'D'})
        passed, _ = check_eligibility(s2, req)
        self.assertTrue(passed, "Should pass with Tech")

        # 3. Pass Voc -> Pass
        s3 = self.make_student({'voc': 'D'})
        passed, _ = check_eligibility(s3, req)
        self.assertTrue(passed, "Should pass with Voc")

if __name__ == '__main__':
    unittest.main()
