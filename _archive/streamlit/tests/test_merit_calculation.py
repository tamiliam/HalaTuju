
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine import calculate_merit_score, check_merit_probability, prepare_merit_inputs, MERIT_GRADE_POINTS

def test_merit_calculation_basics():
    # Test case: All A+ (18 points)
    # Sec1 (5 sub) = 5 * 18 = 90
    # Sec2 (3 sub) = 3 * 18 = 54
    # Sec3 (1 sub) = 1 * 18 = 18
    # Total = 162
    # Formula: ((90 * 40/72) + (54 * 5/6) + (18 * 5/18)) * (9/8)
    # = ((90 * 0.555) + (45) + (5)) * 1.125
    # = (50 + 45 + 5) * 1.125 = 100 * 1.125 = 112.5 -> max capped at 90 for Academic?
    # Wait, max academic merit is 90.
    
    sec1 = ['A+'] * 5
    sec2 = ['A+'] * 3
    sec3 = ['A+']
    coq = 10.0
    
    res = calculate_merit_score(sec1, sec2, sec3, coq)
    assert res['academic_merit'] == 90.00
    assert res['final_merit'] == 100.00 # 90 + 10

def test_merit_calculation_mid():
    # Test Mixed Grades
    # Sec1: 5 * C (6 pts) = 30
    # Sec2: 3 * C (6 pts) = 18
    # Sec3: C (6 pts) = 6
    
    # Calc:
    # T1 = 30 * 40/72 = 16.666
    # T2 = 18 * 5/6 = 15
    # T3 = 6 * 5/18 = 1.666
    # Sum = 33.333
    # Final Academic = 33.333 * 9/8 = 37.5
    
    sec1 = ['C'] * 5
    sec2 = ['C'] * 3
    sec3 = ['C']
    coq = 5.0
    
    res = calculate_merit_score(sec1, sec2, sec3, coq)
    assert 37.0 <= res['academic_merit'] <= 38.0
    assert res['final_merit'] == res['academic_merit'] + 5.0

def test_probability_logic():
    # Gap >= 0 -> High
    assert check_merit_probability(80, 80) == ("High", "#2ecc71")
    assert check_merit_probability(85, 80) == ("High", "#2ecc71")
    
    # Gap >= -5 -> Fair
    assert check_merit_probability(79, 80) == ("Fair", "#f1c40f")
    assert check_merit_probability(75, 80) == ("Fair", "#f1c40f")
    
    # Gap < -5 -> Low
    assert check_merit_probability(74, 80) == ("Low", "#e74c3c")
    assert check_merit_probability(50, 80) == ("Low", "#e74c3c")

def test_prepare_inputs_science():
    # Mock grades
    grades = {
        'math': 'A', 'addmath': 'A', 'phy': 'A', 'chem': 'A', 'bio': 'A', # Core Sci
        'history': 'B', # Sec 3
        'eng': 'B', 'bm': 'B' # Others (Updated to B to pass 'remaining' filter)
    }
    # prepare_merit_inputs(grades)
    s1, s2, s3 = prepare_merit_inputs(grades)
    
    # Sec3 must be history
    assert s3 == ['B']
    
    # Sec1 must be 5 subjects from Science stream prio
    # math, addmath, phy, chem, bio -> All present
    assert len(s1) == 5
    assert set(s1) == {'A'} # All A
    
    # Sec2 should be remaining best
    # eng(B), bm(B)
    assert len(s2) == 2
    assert set(s2) == {'B'}

if __name__ == "__main__":
    test_merit_calculation_basics()
    test_merit_calculation_mid()
    test_probability_logic()
    test_prepare_inputs_science()
    print("All tests passed!")
