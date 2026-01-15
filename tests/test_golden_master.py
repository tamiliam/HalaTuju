import unittest
import pandas as pd
import sys
import os

# Add parent directory to path to import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import StudentProfile, check_eligibility, load_and_clean_data

class TestGoldenMaster(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 1. Determine Project Root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_folder = os.path.join(project_root, 'data')
        
        files_to_load = ['requirements.csv', 'tvet_requirements.csv']
        dfs = []
        
        print(f"\n🔹 Loading and Cleaning Data from: {data_folder}")
        for filename in files_to_load:
            full_path = os.path.join(data_folder, filename)
            
            if os.path.exists(full_path):
                try:
                    # USE THE SANITIZER!
                    df = load_and_clean_data(full_path)
                    
                    dfs.append(df)
                    print(f"   Found {filename}: {len(df)} rows")
                except Exception as e:
                    print(f"   Error reading {filename}: {e}")
            else:
                print(f"   ⚠️  Warning: {filename} not found in {data_folder}")
        
        if not dfs:
            raise unittest.SkipTest("No requirements files found! Cannot run Golden Master.")
            
        cls.df_courses = pd.concat(dfs, ignore_index=True)
        print(f"   ✅ Total Combined Courses: {len(cls.df_courses)}")

        # 2. Define The Edge Case Squad (The Constants)
        cls.students = [
            # --- BASELINE (1-8) ---
            # 1. The Perfect Student
            StudentProfile(
                grades={'bm':'A+', 'eng':'A+', 'hist':'A+', 'math':'A+', 'sci':'A+', 'phy':'A+', 'chem':'A+'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 2. The "No Math Credit"
            StudentProfile(
                grades={'bm':'A', 'eng':'A', 'hist':'A', 'math':'D', 'sci':'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 3. The "Fail BM"
            StudentProfile(
                grades={'bm':'G', 'eng':'A', 'hist':'A', 'math':'A', 'sci':'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 4. The Colorblind Engineer
            StudentProfile(
                grades={'bm':'A', 'math':'A', 'sci':'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Ya', disability='Tidak'
            ),
            # 5. The Non-Citizen
            StudentProfile(
                grades={'bm':'A', 'math':'A'},
                gender='Lelaki', nationality='Bukan Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 6. The "3M Only" Candidate
            StudentProfile(
                grades={'bm':'G', 'math':'G', 'hist':'G', 'eng':'G'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 7. The Ghost
            StudentProfile(
                grades={}, 
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 8. The Female Student
            StudentProfile(
                grades={'bm':'A', 'math':'A', 'sci':'A'},
                gender='Perempuan', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            
            # --- ACADEMIC NUANCES (9-28) ---
            # 9. The Exact-Minimum Credits Student
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'math':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 10. The One-Extra Credit Student
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'math':'C', 'eng':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 11. The All-Pass-No-Credit Student
            StudentProfile(
                grades={'bm':'D', 'hist':'D', 'math':'D', 'eng':'D', 'sci':'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 12. The Science-Only Credit Student
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'phy':'C', 'chem':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 13. The Technical-Only Credit Student
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'rc':'C', 'cs':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 14. The Mixed Science + Tech
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'phy':'C', 'rc':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 15. The Language-Heavy Student
            StudentProfile(
                grades={'bm':'C', 'eng':'C', 'lang':'C', 'lit':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 16. The Math-Pass-Only Student
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'math':'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 17. The AddMath-Only Credit Student
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'addmath':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 18. The English-Fail Student
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'math':'C', 'eng':'G'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 19. The History-Fail High Achiever
            StudentProfile(
                grades={'bm':'A', 'math':'A', 'sci':'A', 'hist':'G'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 20. The Disabled-But-Academic Star
            StudentProfile(
                grades={'bm':'A', 'hist':'A', 'math':'A', 'sci':'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Ya'
            ),
            # 21. The Female-in-Male-Heavy-Field
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'math':'C', 'phy':'C'},
                gender='Perempuan', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 22. The Colorblind-But-Non-Technical Student
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'eng':'C', 'biz':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Ya', disability='Tidak'
            ),
            # 23. The Interview-Only Candidate
            StudentProfile(
                grades={'bm':'C', 'hist':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 24. The Medical-Restriction Flag Case
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'math':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 25. The Overqualified Academic
            StudentProfile(
                grades={'bm':'A+', 'hist':'A+', 'math':'A+', 'phy':'A+', 'chem':'A+', 'bio':'A+'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 26. The Arts-Only Credit Student
            StudentProfile(
                grades={'bm':'C', 'hist':'C', 'psv':'C', 'lit':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 27. The One-Subject Wonder
            StudentProfile(
                grades={'bm':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 28. The Everything-But-BM Student
            StudentProfile(
                grades={'hist':'A', 'math':'A', 'sci':'A', 'eng':'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # --- TVET & VOCATIONAL SPECIALISTS (29-32) ---
            # 29. The "Hands-On" Specialist
            StudentProfile(
                grades={'bm':'D', 'math':'G', 'sci':'G', 'rc':'E'}, 
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 30. The "Agro" Expert
            StudentProfile(
                grades={'bm':'C', 'math':'D', 'sci':'D', 'agro':'A'}, 
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 31. The "Vocational Stream" Student
            StudentProfile(
                grades={'bm':'C', 'math':'D', 'sci':'G'}, 
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak',
                other_voc=True
            ),
            # 32. The "Home Science" Student
            StudentProfile(
                grades={'bm':'C', 'math':'E', 'sci':'E', 'srt':'C'}, 
                gender='Perempuan', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            
            # --- USER-DEFINED TVET EDGE CASES (33-42) ---

            # 33. The "3M Survivor"
            # Scenario: Passes BM, Math, Science only. Zero credits.
            StudentProfile(
                grades={'bm':'D', 'math':'D', 'sci':'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # 34. The "Humanities vs STEM" Student (Replaces redundant "False Positive Guard")
            # Scenario: Has credits (Accounts, Geography) but NO Math/Sci credit.
            # Ensures they don't accidentally qualify for Engineering Diplomas just because they have "Credits".
            StudentProfile(
                grades={'bm':'C', 'math':'D', 'sci':'D', 'acc':'C', 'geo':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # 35. The "Science-but-no-Tech" Candidate
            # Scenario: Tests pass_math_sci failing when only science is passed (needs Math or Pure Sci)
            StudentProfile(
                grades={'bm':'C', 'math':'G', 'sci':'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # 36. The "Tech-only Substitute"
            # Scenario: Tests pass_science_tech = 1 accepting RC instead of science
            StudentProfile(
                grades={'bm':'C', 'math':'G', 'sci':'G', 'rc':'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # 37. The "Agro Credit Override"
            # Scenario: Tests credit_math_sci_tech = 1 (Agro credit overrides Math/Sci)
            StudentProfile(
                grades={'bm':'C', 'math':'D', 'sci':'D', 'agro':'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # 38. The "English Trap"
            # Scenario: English credit required (rare but present)
            StudentProfile(
                grades={'bm':'C', 'math':'C', 'sci':'C', 'eng':'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # 39. The "Pure Skills Entry"
            # Scenario: Tests req_academic = 0 (No academic subjects, vocational only)
            StudentProfile(
                grades={'rc':'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak',
                other_voc=True
            ),

            # 40. The "Single-Subject Qualifier"
            # Scenario: Tests single = 1 logic
            StudentProfile(
                grades={'bm':'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # 41. The "Healthy but Colorblind" Reject
            # Scenario: Low academic, but blocked by no_colorblind
            StudentProfile(
                grades={'bm':'D', 'math':'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Ya', disability='Tidak'
            ),

            # 42. The "Disability-Only Blocker"
            # Scenario: Confirms no_disability enforced even on skills-only courses
            StudentProfile(
                grades={'rc':'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Ya',
                other_voc=True
            )
        ]

    def test_total_eligibility_count(self):
        """
        Runs EVERY student against EVERY course.
        Counts the total number of 'True' (Eligible) results.
        """
        total_eligible_matches = 0
        
        print("\n🔹 GOLDEN MASTER: Running Integration Matrix...")
        print(f"   Students: {len(self.students)} | Courses: {len(self.df_courses)}")
        print(f"   Total Checks: {len(self.students) * len(self.df_courses)}")

        for student in self.students:
            for _, row in self.df_courses.iterrows():
                req = row.to_dict()
                is_eligible, _ = check_eligibility(student, req)
                if is_eligible:
                    total_eligible_matches += 1

        print("   ------------------------------------------------")
        print(f"   🏆 TOTAL VALID APPLICATIONS: {total_eligible_matches}")
        print("   ------------------------------------------------")

        # --- THE MAGIC NUMBER ---
        EXPECTED_BASELINE = 5368  # <--- Ensure this is your set baseline

        if total_eligible_matches != EXPECTED_BASELINE:
            # Create a clean error message
            diff = total_eligible_matches - EXPECTED_BASELINE
            direction = "more" if diff > 0 else "fewer"
            
            error_msg = (
                f"\n\n❌ REGRESSION DETECTED!\n"
                f"   Expected: {EXPECTED_BASELINE}\n"
                f"   Actual:   {total_eligible_matches}\n"
                f"   Diff:     {diff} matches ({abs(diff)} {direction} than expected)\n\n"
                f"   IF THIS WAS INTENTIONAL (e.g. you added new features/courses):\n"
                f"   -> Update the EXPECTED_BASELINE in 'tests/test_golden_master.py' to {total_eligible_matches}.\n"
                f"   IF THIS WAS NOT INTENTIONAL:\n"
                f"   -> You likely broke a logic rule. Undo your changes."
            )
            self.fail(error_msg)
        else:
            print("   ✅ Golden Master Verification Passed. System Integrity: 100%")

if __name__ == '__main__':
    unittest.main()