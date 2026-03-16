"""
STPM eligibility engine — checks STPM student grades against degree course requirements.
"""

# STPM CGPA scale (official MQA scale)
STPM_CGPA_POINTS = {
    'A': 4.00, 'A-': 3.67,
    'B+': 3.33, 'B': 3.00, 'B-': 2.67,
    'C+': 2.33, 'C': 2.00, 'C-': 1.67,
    'D+': 1.33, 'D': 1.00,
    'F': 0.00,
}

# Grade hierarchy for "meets minimum grade" checks
# E and G kept as legacy aliases (parsed data uses them, real STPM scale does not)
STPM_GRADE_ORDER = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'E', 'F', 'G']


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


# ---------------------------------------------------------------------------
# SPM grade constants and helpers
# ---------------------------------------------------------------------------

SPM_GRADE_ORDER = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']
SPM_CREDIT_GRADES = {'A+', 'A', 'A-', 'B+', 'B', 'C+', 'C'}
SPM_PASS_GRADES = SPM_CREDIT_GRADES | {'D', 'E'}

# Map CSV subject codes (used in spm_subject_group JSON) to engine keys
SPM_CODE_MAP = {
    'MATH': 'math', 'ADD_MATH': 'addmath', 'BM': 'bm', 'BI': 'eng',
    'SCIENCE': 'sci', 'PHYSICS_SPM': 'phy', 'CHEMISTRY_SPM': 'chem',
    'BIOLOGY_SPM': 'bio', 'ACCOUNTING_SPM': 'poa', 'ECONOMICS_SPM': 'ekonomi',
    'COMMERCE': 'business', 'GEOGRAPHY_SPM': 'geo', 'SEJARAH': 'hist',
}

# Map StpmRequirement boolean field suffixes to STPM grade dict keys
STPM_SUBJECT_BOOL_MAP = {
    'stpm_req_pa': 'PA',
    'stpm_req_math_t': 'MATH_T',
    'stpm_req_math_m': 'MATH_M',
    'stpm_req_physics': 'PHYSICS',
    'stpm_req_chemistry': 'CHEMISTRY',
    'stpm_req_biology': 'BIOLOGY',
    'stpm_req_economics': 'ECONOMICS',
    'stpm_req_accounting': 'ACCOUNTING',
    'stpm_req_business': 'BUSINESS',
}


def meets_spm_grade(grade, min_grade):
    """Check if an SPM grade meets or exceeds the minimum threshold.

    Uses SPM_GRADE_ORDER where lower index = better grade.
    Returns False for unrecognised grades.
    """
    try:
        grade_idx = SPM_GRADE_ORDER.index(grade)
        min_idx = SPM_GRADE_ORDER.index(min_grade)
    except ValueError:
        return False
    return grade_idx <= min_idx


def check_spm_prerequisites(req, spm_grades):
    """Check all SPM prerequisite flags on an StpmRequirement.

    Returns True if the student satisfies every required SPM condition.
    """
    # Simple boolean checks: field → (engine key, required grade set)
    SIMPLE_CHECKS = [
        ('spm_credit_bm', 'bm', SPM_CREDIT_GRADES),
        ('spm_pass_sejarah', 'hist', SPM_PASS_GRADES),
        ('spm_credit_bi', 'eng', SPM_CREDIT_GRADES),
        ('spm_pass_bi', 'eng', SPM_PASS_GRADES),
        ('spm_credit_math', 'math', SPM_CREDIT_GRADES),
        ('spm_pass_math', 'math', SPM_PASS_GRADES),
        ('spm_credit_addmath', 'addmath', SPM_CREDIT_GRADES),
        ('spm_credit_science', 'sci', SPM_CREDIT_GRADES),
    ]
    for field, key, grade_set in SIMPLE_CHECKS:
        if getattr(req, field, False):
            student_grade = spm_grades.get(key)
            if not student_grade or student_grade not in grade_set:
                return False

    # Flexible SPM subject group (JSON) — supports both dict and list formats
    group = req.spm_subject_group
    if group:
        groups = group if isinstance(group, list) else [group]
        for g in groups:
            min_count = g.get('min_count', 1)
            min_grade = g.get('min_grade', 'C')
            subjects = g.get('subjects')
            exclude = g.get('exclude', [])
            matched = 0
            if subjects:
                # Specific subject list — check only these
                for csv_code in subjects:
                    engine_key = SPM_CODE_MAP.get(csv_code, csv_code.lower())
                    student_grade = spm_grades.get(engine_key)
                    if student_grade and meets_spm_grade(student_grade, min_grade):
                        matched += 1
            else:
                # No subject list — match ANY subject not in exclude list
                exclude_keys = {SPM_CODE_MAP.get(c, c.lower()) for c in exclude}
                for engine_key, student_grade in spm_grades.items():
                    if engine_key in exclude_keys:
                        continue
                    if student_grade and meets_spm_grade(student_grade, min_grade):
                        matched += 1
            if matched < min_count:
                return False

    return True


def check_stpm_subject_requirements(req, stpm_grades):
    """Check individual STPM subject boolean requirements.

    If req.stpm_req_pa is True, the student must have 'PA' in stpm_grades
    (any passing grade — presence is enough, grade threshold handled elsewhere).
    """
    for field, subject_key in STPM_SUBJECT_BOOL_MAP.items():
        if getattr(req, field, False):
            if subject_key not in stpm_grades:
                return False
    return True


def check_stpm_min_subjects(req, stpm_grades):
    """Check the student has at least N STPM subjects at or above the minimum grade."""
    min_subjects = req.stpm_min_subjects
    min_grade = req.stpm_min_grade
    if not min_subjects or min_subjects <= 0:
        return True
    matched = 0
    for grade in stpm_grades.values():
        if meets_stpm_grade(grade, min_grade):
            matched += 1
    return matched >= min_subjects


def check_stpm_subject_group(req, stpm_grades):
    """Check flexible STPM subject group JSON requirement.

    Supports both single dict and list-of-dicts formats (backward compatible).
    Single dict: {"min_count": N, "min_grade": "C", "subjects": ["PHYSICS", ...]}
    List: [{"min_count": 1, ...}, {"min_count": 1, ...}]
    With list format, student must satisfy ALL groups (AND semantics).
    """
    group = req.stpm_subject_group
    if not group:
        return True
    # Support both old (dict) and new (list) formats
    groups = group if isinstance(group, list) else [group]
    for g in groups:
        min_count = g.get('min_count', 1)
        min_grade = g.get('min_grade', 'C')
        subjects = g.get('subjects')
        # Count matching subjects
        matched = 0
        for subj_key, student_grade in stpm_grades.items():
            if subjects and subj_key.upper() not in [s.upper() for s in subjects]:
                continue
            if meets_stpm_grade(student_grade, min_grade):
                matched += 1
        if matched < min_count:
            return False
    return True


def check_stpm_eligibility(stpm_grades, spm_grades, cgpa, muet_band,
                            gender='', nationality='Warganegara',
                            colorblind='Tidak', disability='Tidak'):
    """Check which STPM degree courses a student qualifies for.

    Args:
        stpm_grades: {'PA': 'A', 'MATH_T': 'B+', ...}
        spm_grades: {'bm': 'A', 'eng': 'B+', 'math': 'A', ...}  (engine keys)
        cgpa: float 0.0-4.0
        muet_band: int 1-6
        gender, nationality, colorblind, disability: demographic strings

    Returns:
        List of dicts, each with: course_id, course_name, university, stream,
        min_cgpa, min_muet_band, req_interview, no_colorblind
    """
    # Import inside function to avoid circular imports and keep pure functions testable
    from apps.courses.models import StpmRequirement

    eligible = []
    all_reqs = StpmRequirement.objects.select_related('course').all()

    for req in all_reqs:
        # 1. CGPA check
        if cgpa < req.min_cgpa:
            continue

        # 2. MUET band check
        if muet_band < req.min_muet_band:
            continue

        # 3. Demographic checks
        if req.req_malaysian and nationality != 'Warganegara':
            continue
        if req.no_colorblind and colorblind == 'Ya':
            continue
        if req.no_disability and disability == 'Ya':
            continue
        if req.req_male and gender != 'Lelaki':
            continue
        if req.req_female and gender != 'Perempuan':
            continue
        # Bumiputera-only courses (e.g. UiTM) are out of scope
        if req.req_bumiputera:
            continue

        # 4. Individual STPM subject requirements
        if not check_stpm_subject_requirements(req, stpm_grades):
            continue

        # 5. Minimum N STPM subjects at min grade
        if not check_stpm_min_subjects(req, stpm_grades):
            continue

        # 6. STPM subject group (JSON)
        if not check_stpm_subject_group(req, stpm_grades):
            continue

        # 7. SPM prerequisites
        if not check_spm_prerequisites(req, spm_grades):
            continue

        # All checks passed — add to eligible list
        course = req.course
        eligible.append({
            'course_id': course.course_id,
            'course_name': course.course_name,
            'university': course.university,
            'stream': course.stream,
            'field': course.field or '',
            'field_key': course.field_key_id or '',
            'min_cgpa': req.min_cgpa,
            'min_muet_band': req.min_muet_band,
            'req_interview': req.req_interview,
            'no_colorblind': req.no_colorblind,
            'merit_score': course.merit_score,
        })

    return eligible
