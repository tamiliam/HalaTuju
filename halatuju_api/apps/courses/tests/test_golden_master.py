"""
GOLDEN MASTER TEST — Eligibility Engine Verification
=====================================================

This test verifies that the ported engine.py produces identical results
to the original Streamlit version.

BASELINE: 8280 total eligible matches (50 students × all courses)

To run:
    cd halatuju_api
    python -m pytest apps/courses/tests/test_golden_master.py -v

Or with unittest:
    python -m unittest apps.courses.tests.test_golden_master

IMPORTANT: This test loads data from CSV files (not DB) to ensure
we can validate the engine port independently of database migration.
"""

import unittest
import os
import sys
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from apps.courses.engine import StudentProfile, check_eligibility


# Data sanitizer (same as original)
def load_and_clean_data(filepath):
    """
    Loads CSV and enforces strict integer types for flag columns.
    """
    REQ_FLAG_COLUMNS = [
        'req_malaysian', 'req_male', 'req_female', 'no_colorblind', 'no_disability',
        '3m_only', 'pass_bm', 'credit_bm', 'pass_history',
        'pass_eng', 'credit_english', 'pass_math', 'credit_math', 'pass_math_addmath',
        'pass_math_science', 'pass_science_tech', 'credit_math_sci',
        'credit_math_sci_tech', 'pass_stv', 'credit_sf', 'credit_sfmt',
        'credit_bmbi', 'credit_stv',
        'req_interview', 'single', 'req_group_diversity',
        'credit_bm_b', 'credit_eng_b', 'credit_math_b', 'credit_addmath_b',
        'distinction_bm', 'distinction_eng', 'distinction_math', 'distinction_addmath',
        'distinction_bio', 'distinction_phy', 'distinction_chem', 'distinction_sci',
        'credit_science_group', 'credit_math_or_addmath',
        'pass_islam', 'credit_islam', 'pass_moral', 'credit_moral',
        'pass_sci', 'credit_sci', 'credit_addmath'
    ]
    REQ_COUNT_COLUMNS = ['min_credits', 'min_pass', 'max_aggregate_units']
    REQ_TEXT_COLUMNS = ['subject_group_req', 'complex_requirements']
    ALL_REQ_COLUMNS = REQ_FLAG_COLUMNS + REQ_COUNT_COLUMNS + REQ_TEXT_COLUMNS

    df = None
    for enc in ['utf-8', 'cp1252', 'latin1']:
        try:
            df = pd.read_csv(filepath, encoding=enc)
            break
        except UnicodeDecodeError:
            continue

    if df is None:
        raise ValueError(f"Could not read {filepath} with supported encodings.")

    # Ensure all columns exist
    for col in ALL_REQ_COLUMNS:
        if col not in df.columns:
            if col in REQ_FLAG_COLUMNS + REQ_COUNT_COLUMNS:
                df[col] = 0
            else:
                df[col] = ""

    for col in REQ_FLAG_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    for col in REQ_COUNT_COLUMNS:
        if col == 'max_aggregate_units':
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(100).astype(int)
            df.loc[df[col] == 0, col] = 100
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    return df


class TestGoldenMaster(unittest.TestCase):
    """
    Golden Master Test: Verify engine produces expected baseline of 8280 matches.
    """

    @classmethod
    def setUpClass(cls):
        """Load all requirements from CSV files."""
        # Find the data folder (in original HalaTuju project)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up to halatuju_api, then up to HalaTuju
        halatuju_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
        data_folder = os.path.join(halatuju_root, 'data')

        if not os.path.exists(data_folder):
            raise unittest.SkipTest(f"Data folder not found: {data_folder}")

        files_to_load = ['requirements.csv', 'kkom_requirements.csv', 'tvet_requirements.csv', 'university_requirements.csv']
        dfs = []

        print(f"\n[*] Loading and Cleaning Data from: {data_folder}")
        for filename in files_to_load:
            full_path = os.path.join(data_folder, filename)

            if os.path.exists(full_path):
                try:
                    df = load_and_clean_data(full_path)
                    dfs.append(df)
                    print(f"   Found {filename}: {len(df)} rows")
                except Exception as e:
                    print(f"   Error reading {filename}: {e}")
            else:
                print(f"   [!] Warning: {filename} not found in {data_folder}")

        if not dfs:
            raise unittest.SkipTest("No requirements files found! Cannot run Golden Master.")

        cls.df_courses = pd.concat(dfs, ignore_index=True)
        print(f"   [OK] Total Combined Courses: {len(cls.df_courses)}")

        # Define the 50 edge case students (THE CONSTANTS)
        cls.students = [
            # --- BASELINE (1-8) ---
            # 1. The Perfect Student
            StudentProfile(
                grades={'bm': 'A+', 'eng': 'A+', 'hist': 'A+', 'math': 'A+', 'sci': 'A+', 'phy': 'A+', 'chem': 'A+'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 2. The "No Math Credit"
            StudentProfile(
                grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'D', 'sci': 'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 3. The "Fail BM"
            StudentProfile(
                grades={'bm': 'G', 'eng': 'A', 'hist': 'A', 'math': 'A', 'sci': 'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 4. The Colorblind Engineer
            StudentProfile(
                grades={'bm': 'A', 'math': 'A', 'sci': 'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Ya', disability='Tidak'
            ),
            # 5. The Non-Citizen
            StudentProfile(
                grades={'bm': 'A', 'math': 'A'},
                gender='Lelaki', nationality='Bukan Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 6. The "3M Only" Candidate
            StudentProfile(
                grades={'bm': 'G', 'math': 'G', 'hist': 'G', 'eng': 'G'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 7. The Ghost
            StudentProfile(
                grades={},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 8. The Female Student
            StudentProfile(
                grades={'bm': 'A', 'math': 'A', 'sci': 'A'},
                gender='Perempuan', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # --- ACADEMIC NUANCES (9-28) ---
            # 9. The Exact-Minimum Credits Student
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'math': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 10. The One-Extra Credit Student
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'math': 'C', 'eng': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 11. The All-Pass-No-Credit Student
            StudentProfile(
                grades={'bm': 'D', 'hist': 'D', 'math': 'D', 'eng': 'D', 'sci': 'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 12. The Science-Only Credit Student
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'phy': 'C', 'chem': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 13. The Technical-Only Credit Student
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'rc': 'C', 'cs': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 14. The Mixed Science + Tech
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'phy': 'C', 'rc': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 15. The Language-Heavy Student
            StudentProfile(
                grades={'bm': 'C', 'eng': 'C', 'lang': 'C', 'lit': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 16. The Math-Pass-Only Student
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'math': 'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 17. The AddMath-Only Credit Student
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'addmath': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 18. The English-Fail Student
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'math': 'C', 'eng': 'G'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 19. The History-Fail High Achiever
            StudentProfile(
                grades={'bm': 'A', 'math': 'A', 'sci': 'A', 'hist': 'G'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 20. The Disabled-But-Academic Star
            StudentProfile(
                grades={'bm': 'A', 'hist': 'A', 'math': 'A', 'sci': 'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Ya'
            ),
            # 21. The Female-in-Male-Heavy-Field
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'math': 'C', 'phy': 'C'},
                gender='Perempuan', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 22. The Colorblind-But-Non-Technical Student
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'eng': 'C', 'biz': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Ya', disability='Tidak'
            ),
            # 23. The Interview-Only Candidate
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 24. The Medical-Restriction Flag Case
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'math': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 25. The Overqualified Academic
            StudentProfile(
                grades={'bm': 'A+', 'hist': 'A+', 'math': 'A+', 'phy': 'A+', 'chem': 'A+', 'bio': 'A+'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 26. The Arts-Only Credit Student
            StudentProfile(
                grades={'bm': 'C', 'hist': 'C', 'psv': 'C', 'lit': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 27. The One-Subject Wonder
            StudentProfile(
                grades={'bm': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 28. The Everything-But-BM Student
            StudentProfile(
                grades={'hist': 'A', 'math': 'A', 'sci': 'A', 'eng': 'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # --- TVET & VOCATIONAL SPECIALISTS (29-32) ---
            # 29. The "Hands-On" Specialist
            StudentProfile(
                grades={'bm': 'D', 'math': 'G', 'sci': 'G', 'rc': 'E'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 30. The "Agro" Expert
            StudentProfile(
                grades={'bm': 'C', 'math': 'D', 'sci': 'D', 'agro': 'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 31. The "Vocational Stream" Student
            StudentProfile(
                grades={'bm': 'C', 'math': 'D', 'sci': 'G'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak',
                other_voc=True
            ),
            # 32. The "Home Science" Student
            StudentProfile(
                grades={'bm': 'C', 'math': 'E', 'sci': 'E', 'srt': 'C'},
                gender='Perempuan', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),

            # --- USER-DEFINED TVET EDGE CASES (33-42) ---
            # 33. The "3M Survivor"
            StudentProfile(
                grades={'bm': 'D', 'math': 'D', 'sci': 'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 34. The "Humanities vs STEM" Student
            StudentProfile(
                grades={'bm': 'C', 'math': 'D', 'sci': 'D', 'acc': 'C', 'geo': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 35. The "Science-but-no-Tech" Candidate
            StudentProfile(
                grades={'bm': 'C', 'math': 'G', 'sci': 'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 36. The "Tech-only Substitute"
            StudentProfile(
                grades={'bm': 'C', 'math': 'G', 'sci': 'G', 'rc': 'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 37. The "Agro Credit Override"
            StudentProfile(
                grades={'bm': 'C', 'math': 'D', 'sci': 'D', 'agro': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 38. The "English Trap"
            StudentProfile(
                grades={'bm': 'C', 'math': 'C', 'sci': 'C', 'eng': 'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 39. The "Pure Skills Entry"
            StudentProfile(
                grades={'rc': 'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak',
                other_voc=True
            ),
            # 40. The "Single-Subject Qualifier"
            StudentProfile(
                grades={'bm': 'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 41. The "Healthy but Colorblind" Reject
            StudentProfile(
                grades={'bm': 'D', 'math': 'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Ya', disability='Tidak'
            ),
            # 42. The "Disability-Only Blocker"
            StudentProfile(
                grades={'rc': 'D'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Ya',
                other_voc=True
            ),

            # --- UNIVERSITY (UA) REQUIREMENTS TESTING (43-50) ---
            # 43. The "Grade B Strong Candidate"
            StudentProfile(
                grades={'bm': 'B', 'eng': 'B', 'hist': 'C', 'math': 'B', 'addmath': 'B+', 'phy': 'A', 'chem': 'B', 'bio': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 44. The "Distinction Achiever"
            StudentProfile(
                grades={'bm': 'A', 'eng': 'B+', 'hist': 'C', 'math': 'A-', 'addmath': 'A+', 'phy': 'A', 'chem': 'A-', 'bio': 'A'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 45. The "Grade B Borderline Fail"
            StudentProfile(
                grades={'bm': 'C+', 'eng': 'C+', 'hist': 'C', 'math': 'C+', 'addmath': 'C+', 'phy': 'B', 'chem': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 46. The "Complex OR-Group Qualifier"
            StudentProfile(
                grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'phy': 'A', 'chem': 'B', 'bio': 'D', 'comp_sci': 'B'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 47. The "Complex OR-Group Fail"
            StudentProfile(
                grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'phy': 'B', 'chem': 'D', 'bio': 'E'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 48. The "Pendidikan Islam Qualifier"
            StudentProfile(
                grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'islam': 'B', 'phy': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 49. The "Pendidikan Moral Qualifier"
            StudentProfile(
                grades={'bm': 'B', 'eng': 'C', 'hist': 'C', 'math': 'C', 'moral': 'B', 'chem': 'C'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            ),
            # 50. The "Mixed UA Requirements"
            StudentProfile(
                grades={'bm': 'A', 'eng': 'D', 'hist': 'C', 'math': 'B', 'phy': 'A-', 'chem': 'B'},
                gender='Lelaki', nationality='Warganegara', colorblind='Tidak', disability='Tidak'
            )
        ]

    def test_total_eligibility_count(self):
        """
        Runs EVERY student against EVERY course.
        Counts the total number of 'True' (Eligible) results.
        """
        total_eligible_matches = 0

        print("\n[*] GOLDEN MASTER: Running Integration Matrix...")
        print(f"   Students: {len(self.students)} | Courses: {len(self.df_courses)}")
        print(f"   Total Checks: {len(self.students) * len(self.df_courses)}")

        for student in self.students:
            for _, row in self.df_courses.iterrows():
                req = row.to_dict()
                is_eligible, _ = check_eligibility(student, req)
                if is_eligible:
                    total_eligible_matches += 1

        print("   ------------------------------------------------")
        print(f"   [***] TOTAL VALID APPLICATIONS: {total_eligible_matches}")
        print("   ------------------------------------------------")

        # --- THE MAGIC NUMBER ---
        EXPECTED_BASELINE = 8280

        if total_eligible_matches != EXPECTED_BASELINE:
            diff = total_eligible_matches - EXPECTED_BASELINE
            direction = "more" if diff > 0 else "fewer"

            error_msg = (
                f"\n\n[X] REGRESSION DETECTED!\n"
                f"   Expected: {EXPECTED_BASELINE}\n"
                f"   Actual:   {total_eligible_matches}\n"
                f"   Diff:     {diff} matches ({abs(diff)} {direction} than expected)\n\n"
                f"   IF THIS WAS INTENTIONAL (e.g. you added new features/courses):\n"
                f"   -> Update the EXPECTED_BASELINE to {total_eligible_matches}.\n"
                f"   IF THIS WAS NOT INTENTIONAL:\n"
                f"   -> You likely broke a logic rule. Check your changes."
            )
            self.fail(error_msg)
        else:
            print("   [OK] Golden Master Verification Passed. System Integrity: 100%")


if __name__ == '__main__':
    unittest.main()
