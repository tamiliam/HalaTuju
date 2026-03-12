"""
STPM eligibility engine — checks STPM student grades against degree programme requirements.
"""

# STPM CGPA scale (official MQA scale)
STPM_CGPA_POINTS = {
    'A': 4.00, 'A-': 3.67,
    'B+': 3.33, 'B': 3.00, 'B-': 2.67,
    'C+': 2.33, 'C': 2.00, 'C-': 2.00,
    'D': 1.67, 'E': 1.00,
    'F': 0.00, 'G': 0.00,
}

# Grade hierarchy for "meets minimum grade" checks
STPM_GRADE_ORDER = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'E', 'F', 'G']


def calculate_stpm_cgpa(grades):
    """Calculate CGPA from STPM grades dict.

    Args:
        grades: Dict mapping STPM subject codes to grade strings.
                e.g. {'PA': 'A', 'MATH_T': 'B+', 'PHYSICS': 'A-'}

    Returns:
        Float CGPA (0.0-4.0), rounded to 2 decimal places.
    """
    if not grades:
        return 0.0
    total_points = 0.0
    count = 0
    for grade in grades.values():
        pts = STPM_CGPA_POINTS.get(grade)
        if pts is not None:
            total_points += pts
            count += 1
    if count == 0:
        return 0.0
    return round(total_points / count, 2)


def meets_stpm_grade(grade, min_grade):
    """Check if a grade meets or exceeds the minimum threshold.

    Lower index in STPM_GRADE_ORDER = better grade.
    """
    try:
        grade_idx = STPM_GRADE_ORDER.index(grade)
        min_idx = STPM_GRADE_ORDER.index(min_grade)
    except ValueError:
        return False
    return grade_idx <= min_idx
