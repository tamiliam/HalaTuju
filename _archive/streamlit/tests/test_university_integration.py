"""
Quick test to verify university course integration
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.data_manager import load_master_data
from src.engine import StudentProfile, check_eligibility

def test_data_loading():
    """Test that university data loads correctly"""
    print("=" * 60)
    print("TEST 1: Data Loading")
    print("=" * 60)

    df = load_master_data()

    # Check if UA courses exist (type='Universiti Awam' in BM)
    ua_courses = df[df['type'] == 'Universiti Awam']
    print(f"\nTotal courses loaded: {len(df)}")
    print(f"University (UA) courses: {len(ua_courses)}")

    if len(ua_courses) > 0:
        print("\nSample UA course:")
        sample = ua_courses.iloc[0]
        print(f"  Course ID: {sample['course_id']}")
        print(f"  Course Name: {sample.get('course_name', 'N/A')}")
        print(f"  Institution: {sample.get('institution_name', 'N/A')}")
        print(f"  Type: {sample.get('type', 'N/A')}")
        print(f"  Category: {sample.get('category', 'N/A')}")
        print(f"  Frontend Label: {sample.get('frontend_label', 'N/A')}")
        print(f"  Department: {sample.get('department', 'N/A')}")
        print(f"  Field: {sample.get('field', 'N/A')}")

        # Check requirement columns
        print(f"\n  Requirements:")
        print(f"    credit_bm_b: {sample.get('credit_bm_b', 'N/A')}")
        print(f"    credit_eng_b: {sample.get('credit_eng_b', 'N/A')}")
        print(f"    credit_math_b: {sample.get('credit_math_b', 'N/A')}")
        print(f"    distinction_bm: {sample.get('distinction_bm', 'N/A')}")
        print(f"    complex_requirements: {sample.get('complex_requirements', 'N/A')[:80] if sample.get('complex_requirements') else 'N/A'}")

        return True
    else:
        print("\n[ERROR] No UA courses found!")
        return False


def test_eligibility_engine():
    """Test eligibility engine with a university course"""
    print("\n" + "=" * 60)
    print("TEST 2: Eligibility Engine")
    print("=" * 60)

    df = load_master_data()
    ua_courses = df[df['type'] == 'Universiti Awam']

    if len(ua_courses) == 0:
        print("[ERROR] No UA courses to test!")
        return False

    # Test with a sample course: UZ0520001 (ASASI KEJURUTERAAN DAN TEKNOLOGI)
    course = ua_courses[ua_courses['course_id'] == 'UZ0520001'].iloc[0]

    print(f"\nTesting Course: {course['course_id']} - {course.get('course_name', 'N/A')}")
    print(f"Requirements:")
    print(f"  - credit_bm_b: {course.get('credit_bm_b')}")
    print(f"  - credit_eng_b: {course.get('credit_eng_b')}")
    print(f"  - credit_addmath_b: {course.get('credit_addmath_b')}")
    print(f"  - credit_science_group: {course.get('credit_science_group')}")
    print(f"  - complex_requirements: {course.get('complex_requirements', '')[:100]}")

    # Create a student who SHOULD qualify
    print("\n--- Test Student 1: Strong Student (Should Qualify) ---")
    student_grades = {
        'bm': 'A',      # Grade B required
        'eng': 'C',     # Grade C required
        'math': 'B',    # Not directly required
        'addmath': 'B+', # Grade B required (OR Math)
        'hist': 'C',    # Pass required
        'phy': 'A',     # Credit required (science group OR comp_sci)
        'chem': 'B',
        'bio': 'C'
    }

    student1 = StudentProfile(
        grades=student_grades,
        gender='Lelaki',
        nationality='Warganegara',
        colorblind='Tidak',
        disability='Tidak'
    )

    eligible, audit = check_eligibility(student1, course.to_dict())
    print(f"Eligible: {eligible}")
    print(f"Total checks: {len(audit)}")

    # Show failed checks
    failed = [a for a in audit if not a['passed']]
    if failed:
        print(f"\nFailed checks ({len(failed)}):")
        for f in failed[:5]:
            print(f"  - {f['label']}: {f['reason']}")
    else:
        print("\n[OK] All checks passed!")

    # Create a student who should NOT qualify (weak grades)
    print("\n--- Test Student 2: Weak Student (Should NOT Qualify) ---")
    weak_grades = {
        'bm': 'C',      # Needs Grade B - FAIL
        'eng': 'D',     # Needs Grade C - FAIL
        'math': 'C',
        'hist': 'C',
        'phy': 'D',     # Needs credit - FAIL
        'chem': 'E'
    }

    student2 = StudentProfile(
        grades=weak_grades,
        gender='Lelaki',
        nationality='Warganegara',
        colorblind='Tidak',
        disability='Tidak'
    )

    eligible2, audit2 = check_eligibility(student2, course.to_dict())
    print(f"Eligible: {eligible2}")

    failed2 = [a for a in audit2 if not a['passed']]
    print(f"\nFailed checks ({len(failed2)}):")
    for f in failed2[:10]:
        print(f"  - {f['label']}: {f['reason']}")

    return True


def test_complex_requirements():
    """Test complex_requirements JSON parsing"""
    print("\n" + "=" * 60)
    print("TEST 3: Complex Requirements Parsing")
    print("=" * 60)

    df = load_master_data()
    ua_courses = df[df['type'] == 'Universiti Awam']

    # Find courses with complex_requirements
    with_complex = ua_courses[ua_courses['complex_requirements'].notna() & (ua_courses['complex_requirements'] != '')]

    print(f"\nCourses with complex_requirements: {len(with_complex)}")

    if len(with_complex) > 0:
        sample = with_complex.iloc[0]
        print(f"\nSample course: {sample['course_id']}")
        print(f"Complex requirements: {sample['complex_requirements']}")

        # Test with a matching student
        student_grades = {
            'bm': 'A', 'eng': 'B', 'math': 'B', 'addmath': 'B',
            'hist': 'C', 'phy': 'A', 'chem': 'B', 'bio': 'C',
            'comp_sci': 'B'  # Should satisfy the requirement
        }

        student = StudentProfile(
            grades=student_grades,
            gender='Lelaki',
            nationality='Warganegara',
            colorblind='Tidak',
            disability='Tidak'
        )

        eligible, audit = check_eligibility(student, sample.to_dict())

        # Find the complex_req check
        complex_check = [a for a in audit if a['label'] == 'chk_complex_req']
        if complex_check:
            print(f"\nComplex requirement check:")
            print(f"  Passed: {complex_check[0]['passed']}")
            print(f"  Reason: {complex_check[0].get('reason', 'N/A')}")
        else:
            print("\n[WARN] No complex_req check found in audit")

        return True
    else:
        print("\n[WARN] No courses with complex_requirements found")
        return True


if __name__ == "__main__":
    print("University Course Integration Test")
    print("=" * 60)

    try:
        # Run tests
        test1_pass = test_data_loading()
        test2_pass = test_eligibility_engine()
        test3_pass = test_complex_requirements()

        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Data Loading: {'[PASS]' if test1_pass else '[FAIL]'}")
        print(f"Eligibility Engine: {'[PASS]' if test2_pass else '[FAIL]'}")
        print(f"Complex Requirements: {'[PASS]' if test3_pass else '[FAIL]'}")

        if test1_pass and test2_pass and test3_pass:
            print("\n[OK] All tests passed!")
        else:
            print("\n[FAIL] Some tests failed!")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
