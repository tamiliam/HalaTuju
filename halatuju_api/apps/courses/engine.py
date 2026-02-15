"""
ELIGIBILITY ENGINE — GOLDEN MASTER
===================================

This is a DIRECT PORT of HalaTuju/src/engine.py.
The logic MUST remain identical to preserve the golden master baseline (8280).

CHANGES FROM ORIGINAL:
- Removed load_and_clean_data() - data now comes from Django ORM
- All eligibility logic is UNCHANGED

DO NOT MODIFY THIS FILE WITHOUT RUNNING test_golden_master.py!
"""

import json
import itertools

# ============================================
# GRADE CLASSIFICATION CONSTANTS
# ============================================

PASS_GRADES = {"A+", "A", "A-", "B+", "B", "C+", "C", "D", "E"}
CREDIT_GRADES = {"A+", "A", "A-", "B+", "B", "C+", "C"}
CREDIT_B_GRADES = {"A+", "A", "A-", "B+", "B"}  # Grade B or better (for UA requirements)
DISTINCTION_GRADES = {"A+", "A", "A-"}  # Grade A- or better (for UA requirements)
ATTEMPTED_GRADES = PASS_GRADES | {"G"}

# --- MERIT CALCULATION CONSTANTS (High is Good) ---
MERIT_GRADE_POINTS = {
    "A+": 18, "A": 16, "A-": 14,
    "B+": 12, "B": 10, "C+": 8, "C": 6,
    "D": 4, "E": 2, "G": 0
}

# --- AGGREGATE CALCULATION CONSTANTS (Low is Good) ---
# Used for "tidak melebihi X unit" checks (e.g. STPM Entry)
AGGREGATE_GRADE_POINTS = {
    "A+": 0, "A": 1, "A-": 2,
    "B+": 3, "B": 4, "C+": 5, "C": 6,
    "D": 7, "E": 8, "G": 9
}

# ============================================
# SUBJECT LISTS - Single Source of Truth
# ============================================

# Science Stream Electives
SUBJ_LIST_SCIENCE = ["chem", "phy", "bio", "addmath"]

# Arts Stream Electives (b_arab removed - Islamic school subject)
SUBJ_LIST_ARTS = [
    "b_cina", "b_tamil",
    "ekonomi", "geo",
    "lit_bm", "lit_eng", "lit_cina", "lit_tamil",
    "lukisan", "psv", "business", "poa", "keusahawanan"
]

# Technical/Engineering Subjects
SUBJ_LIST_TECHNICAL = [
    "eng_civil", "eng_mech", "eng_elec",
    "eng_draw", "gkt", "kelestarian", "reka_cipta"
]

# IT/Computing Subjects
SUBJ_LIST_IT = [
    "comp_sci", "multimedia", "digital_gfx"
]

# Vocational Subjects - MPV
SUBJ_LIST_VOCATIONAL = [
    "voc_construct", "voc_plumb", "voc_wiring", "voc_weld",
    "voc_auto", "voc_elec_serv", "voc_food", "voc_landscape",
    "voc_catering", "voc_tailoring"
]

# General Electives (includes compulsory PI/PM)
SUBJ_LIST_EXTRA = [
    "islam", "moral",  # Compulsory: PI for Muslim, PM for non-Muslim
    "pertanian", "sci", "srt", "addsci",
    "sports_sci", "music"
]

# ============================================
# COMPOSITE GROUPS - For Eligibility Logic
# ============================================

SUBJ_GROUP_SCIENCE = ["chem", "phy", "bio", "sci", "addsci"]
SUBJ_GROUP_TECHNICAL = SUBJ_LIST_TECHNICAL + SUBJ_LIST_IT
SUBJ_GROUP_VOCATIONAL = SUBJ_LIST_VOCATIONAL

# Legacy key mapping (for backward compatibility with existing user data)
LEGACY_KEY_MAP = {
    "tech": "eng_civil",
    "voc": "voc_weld",
    "islam": "moral",
    "b_arab": "b_tamil"
}


# ============================================
# HELPER FUNCTIONS
# ============================================

def is_pass(grade):
    return grade in PASS_GRADES


def is_credit(grade):
    return grade in CREDIT_GRADES


def is_credit_b(grade):
    """Grade B or better (B, B+, A-, A, A+)"""
    return grade in CREDIT_B_GRADES


def is_distinction(grade):
    """Grade A- or better (A-, A, A+)"""
    return grade in DISTINCTION_GRADES


def is_attempted(grade):
    return grade in ATTEMPTED_GRADES


def to_int(val):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def map_subject_code(subj_code):
    """Maps CSV/PDF subject codes to internal StudentProfile keys."""
    s = subj_code.upper()
    if s == "BM": return "bm"
    if s == "BI": return "eng"
    if s == "HISTORY": return "hist"
    if s == "MATH": return "math"
    if s == "ADDMATH": return "addmath"
    if s == "PHYSICS": return "phy"
    if s == "CHEMISTRY": return "chem"
    if s == "BIOLOGY": return "bio"
    if s == "SCIENCE": return "sci"
    if s == "PAI": return "islam"
    if s == "BC": return "b_cina"
    if s == "BT": return "b_tamil"
    if s == "BA": return "b_arab"
    if s == "PSV": return "psv"
    if s == "GEO": return "geo"
    if s == "EKONOMI": return "ekonomi"
    return subj_code.lower()


# ============================================
# MERIT CALCULATION
# ============================================

def calculate_merit_score(sec1_grades, sec2_grades, sec3_grades, coq_score):
    """
    Calculates the detailed academic merit and final merit based on the 18-point scale.
    """
    def get_points(g_list):
        return sum(MERIT_GRADE_POINTS.get(g, 0) for g in g_list)

    p1 = get_points(sec1_grades)
    p2 = get_points(sec2_grades)
    p3 = get_points(sec3_grades)

    total_points = p1 + p2 + p3

    # Formula: ((S1 * 40/72) + (S2 * 5/6) + (S3 * 5/18)) * (9/8)
    academic_merit = ((p1 * 5/9) + (p2 * 5/6) + (p3 * 5/18)) * (9/8)
    academic_merit = min(academic_merit, 90.00)
    final_merit = academic_merit + min(max(coq_score, 0), 10.0)

    return {
        "academic_merit": round(academic_merit, 2),
        "final_merit": round(final_merit, 2),
        "total_points": total_points
    }


def check_merit_probability(student_merit, course_cutoff):
    """
    Returns (label, color_hex) based on the gap between student merit and course cutoff.
    """
    try:
        cutoff = float(course_cutoff)
        merit = float(student_merit)
    except:
        return "Unknown", "#95a5a6"

    gap = merit - cutoff

    if gap >= 0:
        return "High", "#2ecc71"
    elif gap >= -5:
        return "Fair", "#f1c40f"
    else:
        return "Low", "#e74c3c"


def prepare_merit_inputs(grades):
    """
    Intelligently splits grades into Sec1 (5 subjs), Sec2 (3 subjs), Sec3 (1 subj)
    for UPU-style merit calculation.
    """
    has_phy = 'phy' in grades
    has_chem = 'chem' in grades
    is_science = has_phy and has_chem

    def get_g(s):
        return grades.get(s, 'G')

    # Section 3: History (Critical for UPU)
    sec3 = [get_g('history')]

    # Section 1: 5 Critical Subjects
    sec1_keys = []
    if is_science:
        candidates = ['math', 'addmath', 'phy', 'chem', 'bio']
        for k in candidates:
            if k in grades:
                sec1_keys.append(k)
    else:
        candidates = ['bm', 'math', 'sci']
        for k in candidates:
            if k in grades:
                sec1_keys.append(k)

    # Fill Sec1 to 5 items with best remaining
    all_keys = list(grades.keys())
    used = set(['history'] + sec1_keys)
    remaining = [k for k in all_keys if k not in used and grades[k] not in ['G', 'E', 'D', 'C', 'C+']]

    remaining.sort(key=lambda k: MERIT_GRADE_POINTS.get(grades[k], 0), reverse=True)

    while len(sec1_keys) < 5 and remaining:
        k = remaining.pop(0)
        sec1_keys.append(k)

    sec1 = [grades.get(k) for k in sec1_keys]

    # Section 2: Next 3 Best
    sec2_keys = []
    while len(sec2_keys) < 3 and remaining:
        k = remaining.pop(0)
        sec2_keys.append(k)

    sec2 = [grades.get(k) for k in sec2_keys]

    return sec1, sec2, sec3


# ============================================
# COMPLEX REQUIREMENT CHECKERS
# ============================================

def check_complex_requirements(student_grades, complex_req_json_str):
    """
    Evaluates university OR-group requirements from complex_requirements JSON.

    Format: {"or_groups": [{"count": N, "grade": "B", "subjects": [...]}]}

    Logic: Each OR group must be satisfied (AND logic between groups).
    Within each group, need 'count' subjects with at least 'grade' (OR logic).
    """
    if complex_req_json_str is None or complex_req_json_str == "":
        return True, None

    if isinstance(complex_req_json_str, float):
        import math
        if math.isnan(complex_req_json_str):
            return True, None

    complex_req_str = str(complex_req_json_str).strip()
    if not complex_req_str or complex_req_str.lower() == "nan":
        return True, None

    try:
        data = json.loads(complex_req_str)
    except json.JSONDecodeError:
        return False, "Invalid Complex Requirement Format"

    or_groups = data.get('or_groups', [])
    if not or_groups:
        return True, None

    for group_idx, group in enumerate(or_groups):
        min_count = group.get('count', 1)
        min_grade = group.get('grade', 'E')
        subjects = group.get('subjects', [])

        if not subjects:
            continue

        count_ok = 0
        for subj in subjects:
            student_key = map_subject_code(subj)
            grade = student_grades.get(student_key)

            if grade:
                pts = AGGREGATE_GRADE_POINTS.get(grade, 10)
                threshold = AGGREGATE_GRADE_POINTS.get(min_grade, 8)

                if pts <= threshold:
                    count_ok += 1

        if count_ok < min_count:
            subj_list = ', '.join(subjects[:5]) + ('...' if len(subjects) > 5 else '')
            return False, f"Complex Req Fail: Need {min_count} from [{subj_list}] with grade {min_grade} (Found {count_ok})"

    return True, None


def check_subject_group_logic(student_grades, rule_json_str, max_agg_units, check_diversity=False):
    """
    Evaluates complex subject group rules from a JSON string.
    """
    if not rule_json_str or rule_json_str.strip() == "":
        return True, None

    try:
        rules = json.loads(rule_json_str)
    except json.JSONDecodeError:
        return False, "Invalid Requirement Format"

    if isinstance(rules, list):
        for rule in rules:
            min_grade = rule.get("min_grade", "E")
            min_count = rule.get("min_count", 1)

            if "allowed_groups" in rule and check_diversity:
                allowed_groups = rule.get("allowed_groups", [])
                valid_entries = []

                for g_idx, subjects_in_group in enumerate(allowed_groups):
                    for subj in subjects_in_group:
                        student_key = map_subject_code(subj)
                        grade = student_grades.get(student_key)

                        if grade and is_attempted(grade):
                            pts = AGGREGATE_GRADE_POINTS.get(grade, 10)
                            threshold_pts = AGGREGATE_GRADE_POINTS.get(min_grade, 8)

                            valid_entries.append({
                                "subj": student_key,
                                "group": g_idx,
                                "points": pts,
                                "grade": grade,
                                "meets_grade": pts <= threshold_pts
                            })

                best_per_group = {}
                for entry in valid_entries:
                    g = entry['group']
                    if g not in best_per_group or entry['points'] < best_per_group[g]['points']:
                        best_per_group[g] = entry

                available_subjects = list(best_per_group.values())

                if len(available_subjects) < min_count:
                    return False, f"Not enough subject groups (Found {len(available_subjects)}, Need {min_count})"

                found_valid_combo = False

                for combo in itertools.combinations(available_subjects, min_count):
                    passes_grade_req = sum(1 for e in combo if e['meets_grade']) == min_count
                    total_pts = sum(e['points'] for e in combo)
                    passes_agg = total_pts <= max_agg_units

                    if passes_grade_req and passes_agg:
                        found_valid_combo = True
                        break

                if not found_valid_combo:
                    return False, f"Diversity/Aggregate Failed (Max Units: {max_agg_units})"

            elif "subjects" in rule:
                subjects = rule.get("subjects", [])
                count_ok = 0
                if not subjects:
                    continue

                for subj in subjects:
                    student_key = map_subject_code(subj)
                    grade = student_grades.get(student_key)
                    if grade:
                        pts = AGGREGATE_GRADE_POINTS.get(grade, 10)
                        threshold = AGGREGATE_GRADE_POINTS.get(min_grade, 8)
                        if pts <= threshold:
                            count_ok += 1

                if count_ok < min_count:
                    return False, f"Subject Count Fail: Need {min_count} from {subjects} with grade {min_grade}"

    return True, None


# ============================================
# STUDENT PROFILE CLASS
# ============================================

class StudentProfile:
    """
    Encapsulates a student's data for eligibility checking.

    IMPORTANT: This class is used by the engine and MUST match the original.
    """

    def __init__(self, grades, gender, nationality, colorblind, disability,
                 other_tech=False, other_voc=False):
        self.grades = grades
        self.gender = gender
        self.nationality = nationality
        self.colorblind = colorblind
        self.disability = disability
        self.other_tech = other_tech
        self.other_voc = other_voc

        self.credits = 0
        self.passes = 0

        for subj, grade in grades.items():
            if is_credit(grade):
                self.credits += 1
            if is_pass(grade):
                self.passes += 1


# ============================================
# THE ELIGIBILITY ENGINE (Golden Master)
# ============================================

def check_eligibility(student, req):
    """
    Checks if a student meets the requirements.

    GOLDEN MASTER FUNCTION - DO NOT MODIFY WITHOUT TESTING!

    Args:
        student: StudentProfile object
        req: Dictionary of requirement flags (from DB or CSV row)

    Returns:
        (bool, list): (is_eligible, audit_trail)
    """
    audit = []

    def check(label, condition, fail_msg=None):
        if condition:
            audit.append({"label": label, "passed": True, "reason": None})
            return True
        else:
            audit.append({"label": label, "passed": False, "reason": fail_msg})
            return False

    # GATEKEEPERS
    if to_int(req.get('req_malaysian')) == 1:
        if not check("chk_malaysian", student.nationality == 'Warganegara', "fail_malaysian"):
            return False, audit

    MALE_VALUES = {'Lelaki', 'Male', 'ஆண்'}
    FEMALE_VALUES = {'Perempuan', 'Female', 'பெண்'}

    if to_int(req.get('req_male')) == 1:
        if not check("chk_male", student.gender in MALE_VALUES, "fail_male"):
            return False, audit
    if to_int(req.get('req_female')) == 1:
        if not check("chk_female", student.gender in FEMALE_VALUES, "fail_female"):
            return False, audit
    if to_int(req.get('no_colorblind')) == 1:
        if not check("chk_colorblind", student.colorblind == 'Tidak', "fail_colorblind"):
            return False, audit
    if to_int(req.get('no_disability')) == 1:
        if not check("chk_disability", student.disability == 'Tidak', "fail_disability"):
            return False, audit

    # Age limit (placeholder)
    age_limit = to_int(req.get('age_limit', 0))
    if age_limit > 0:
        pass

    g = student.grades

    # --- TVET SPECIAL: 3M ONLY ---
    if to_int(req.get('3m_only')) == 1:
        cond = is_attempted(g.get('bm')) and is_attempted(g.get('math'))
        audit.append({
            "label": "chk_3m",
            "passed": cond,
            "reason": None if cond else "fail_3m"
        })
        return cond, audit

    # ACADEMIC CHECKS
    passed_academics = True

    if to_int(req.get('pass_bm')) == 1:
        if not check("chk_pass_bm", is_pass(g.get('bm')), "fail_pass_bm"):
            passed_academics = False
    if to_int(req.get('credit_bm')) == 1:
        if not check("chk_credit_bm", is_credit(g.get('bm')), "fail_credit_bm"):
            passed_academics = False
    if to_int(req.get('pass_history')) == 1:
        if not check("chk_pass_hist", is_pass(g.get('hist')), "fail_pass_hist"):
            passed_academics = False
    if to_int(req.get('pass_eng')) == 1:
        if not check("chk_pass_eng", is_pass(g.get('eng')), "fail_pass_eng"):
            passed_academics = False
    if to_int(req.get('credit_english')) == 1:
        if not check("chk_credit_eng", is_credit(g.get('eng')), "fail_credit_eng"):
            passed_academics = False

    # --- UA Grade B Requirements ---
    if to_int(req.get('credit_bm_b')) == 1:
        if not check("chk_credit_bm_b", is_credit_b(g.get('bm')), "fail_credit_bm_b"):
            passed_academics = False
    if to_int(req.get('credit_eng_b')) == 1:
        if not check("chk_credit_eng_b", is_credit_b(g.get('eng')), "fail_credit_eng_b"):
            passed_academics = False
    if to_int(req.get('credit_math_b')) == 1:
        if not check("chk_credit_math_b", is_credit_b(g.get('math')), "fail_credit_math_b"):
            passed_academics = False
    if to_int(req.get('credit_addmath_b')) == 1:
        if not check("chk_credit_addmath_b", is_credit_b(g.get('addmath')), "fail_credit_addmath_b"):
            passed_academics = False

    # --- UA Distinction Requirements ---
    if to_int(req.get('distinction_bm')) == 1:
        if not check("chk_distinction_bm", is_distinction(g.get('bm')), "fail_distinction_bm"):
            passed_academics = False
    if to_int(req.get('distinction_eng')) == 1:
        if not check("chk_distinction_eng", is_distinction(g.get('eng')), "fail_distinction_eng"):
            passed_academics = False
    if to_int(req.get('distinction_math')) == 1:
        if not check("chk_distinction_math", is_distinction(g.get('math')), "fail_distinction_math"):
            passed_academics = False
    if to_int(req.get('distinction_addmath')) == 1:
        if not check("chk_distinction_addmath", is_distinction(g.get('addmath')), "fail_distinction_addmath"):
            passed_academics = False
    if to_int(req.get('distinction_bio')) == 1:
        if not check("chk_distinction_bio", is_distinction(g.get('bio')), "fail_distinction_bio"):
            passed_academics = False
    if to_int(req.get('distinction_phy')) == 1:
        if not check("chk_distinction_phy", is_distinction(g.get('phy')), "fail_distinction_phy"):
            passed_academics = False
    if to_int(req.get('distinction_chem')) == 1:
        if not check("chk_distinction_chem", is_distinction(g.get('chem')), "fail_distinction_chem"):
            passed_academics = False
    if to_int(req.get('distinction_sci')) == 1:
        if not check("chk_distinction_sci", is_distinction(g.get('sci')), "fail_distinction_sci"):
            passed_academics = False

    # --- PI/PM Requirements ---
    if to_int(req.get('pass_islam')) == 1:
        if not check("chk_pass_islam", is_pass(g.get('islam')), "fail_pass_islam"):
            passed_academics = False
    if to_int(req.get('credit_islam')) == 1:
        if not check("chk_credit_islam", is_credit(g.get('islam')), "fail_credit_islam"):
            passed_academics = False
    if to_int(req.get('pass_moral')) == 1:
        if not check("chk_pass_moral", is_pass(g.get('moral')), "fail_pass_moral"):
            passed_academics = False
    if to_int(req.get('credit_moral')) == 1:
        if not check("chk_credit_moral", is_credit(g.get('moral')), "fail_credit_moral"):
            passed_academics = False

    # --- UA Science Requirements ---
    if to_int(req.get('pass_sci')) == 1:
        if not check("chk_pass_sci", is_pass(g.get('sci')), "fail_pass_sci"):
            passed_academics = False
    if to_int(req.get('credit_sci')) == 1:
        if not check("chk_credit_sci", is_credit(g.get('sci')), "fail_credit_sci"):
            passed_academics = False
    if to_int(req.get('credit_addmath')) == 1:
        if not check("chk_credit_addmath", is_credit(g.get('addmath')), "fail_credit_addmath"):
            passed_academics = False

    # Math checks
    if to_int(req.get('pass_math')) == 1:
        if not check("chk_pass_math", is_pass(g.get('math')), "fail_pass_math"):
            passed_academics = False

    if to_int(req.get('pass_math_addmath')) == 1:
        cond = is_pass(g.get('math')) or is_pass(g.get('addmath'))
        if not check("chk_pass_math_addmath", cond, "fail_pass_math_addmath"):
            passed_academics = False

    if to_int(req.get('credit_math')) == 1:
        cond = is_credit(g.get('math')) or is_credit(g.get('addmath'))
        if not check("chk_credit_math", cond, "fail_credit_math"):
            passed_academics = False

    # Group Logic
    pure_sci = [g.get('phy'), g.get('chem'), g.get('bio')]
    all_sci = pure_sci + [g.get('sci')]
    sci_no_bio = [g.get('phy'), g.get('chem'), g.get('sci')]

    def has_pass(grade_list):
        return any(is_pass(x) for x in grade_list)

    def has_credit(grade_list):
        return any(is_credit(x) for x in grade_list)

    # --- UA Rules ---
    if to_int(req.get('credit_science_group')) == 1:
        all_sci_with_addsci = all_sci + [g.get('addsci'), g.get('comp_sci')]
        cond = has_credit(all_sci_with_addsci)
        if not check("chk_credit_sci_group", cond, "fail_credit_sci_group"):
            passed_academics = False

    if to_int(req.get('credit_math_or_addmath')) == 1:
        cond = is_credit(g.get('math')) or is_credit(g.get('addmath'))
        if not check("chk_credit_math_or_addmath", cond, "fail_credit_math_or_addmath"):
            passed_academics = False

    if to_int(req.get('single')) == 1:
        pass  # Skip - we don't capture marital status yet

    # --- TVET Rules ---
    if to_int(req.get('pass_math_science')) == 1:
        cond = is_pass(g.get('math')) or has_pass(sci_no_bio)
        if not check("chk_pass_math_sci_nb", cond, "fail_pass_math_sci_nb"):
            passed_academics = False

    if to_int(req.get('pass_science_tech')) == 1:
        has_tech_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        legacy_tech_pass = is_pass(g.get('tech'))
        cond = has_pass(sci_no_bio) or has_tech_pass or legacy_tech_pass
        if not check("chk_pass_sci_tech", cond, "fail_pass_sci_tech"):
            passed_academics = False

    if to_int(req.get('credit_math_sci')) == 1:
        cond = is_credit(g.get('math')) or has_credit(all_sci)
        if not check("chk_credit_math_sci", cond, "fail_credit_math_sci"):
            passed_academics = False

    if to_int(req.get('credit_math_sci_tech')) == 1:
        has_tech_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        legacy_tech_credit = is_credit(g.get('tech'))
        cond = is_credit(g.get('math')) or has_credit(all_sci) or has_tech_credit or legacy_tech_credit
        if not check("chk_credit_math_sci_tech", cond, "fail_credit_math_sci_tech"):
            passed_academics = False

    # --- Poly/KK Rules ---
    if to_int(req.get('credit_bmbi')) == 1:
        cond = is_credit(g.get('bm')) or is_credit(g.get('eng'))
        if not check("chk_credit_bmbi", cond, "fail_credit_bmbi"):
            passed_academics = False

    if to_int(req.get('credit_stv')) == 1:
        has_tech_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        has_voc_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_VOCATIONAL)
        legacy_tech_credit = is_credit(g.get('tech'))
        legacy_voc_credit = is_credit(g.get('voc'))
        cond = has_credit(all_sci) or has_tech_credit or has_voc_credit or legacy_tech_credit or legacy_voc_credit
        if not check("chk_credit_stv", cond, "fail_credit_stv"):
            passed_academics = False

    if to_int(req.get('pass_stv')) == 1:
        has_tech_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        has_voc_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_VOCATIONAL)
        legacy_tech_pass = is_pass(g.get('tech'))
        legacy_voc_pass = is_pass(g.get('voc'))
        cond = has_pass(all_sci) or has_tech_pass or has_voc_pass or legacy_tech_pass or legacy_voc_pass
        if not check("chk_pass_stv", cond, "fail_pass_stv"):
            passed_academics = False

    if to_int(req.get('credit_sf')) == 1:
        cond = is_credit(g.get('sci')) or is_credit(g.get('phy'))
        if not check("chk_credit_sf", cond, "fail_credit_sf"):
            passed_academics = False

    if to_int(req.get('credit_sfmt')) == 1:
        cond = is_credit(g.get('sci')) or is_credit(g.get('phy')) or is_credit(g.get('addmath'))
        if not check("chk_credit_sfmt", cond, "fail_credit_sfmt"):
            passed_academics = False

    # --- ADVANCED RULES (JSON Logic) ---
    json_req = req.get('subject_group_req', "")
    if json_req and json_req != "":
        max_agg = to_int(req.get('max_aggregate_units', 100))
        check_div = to_int(req.get('req_group_diversity', 0)) == 1
        passed, reason = check_subject_group_logic(g, json_req, max_agg, check_div)
        if not check("chk_adv_subj_group", passed, reason):
            passed_academics = False

    # --- UNIVERSITY COMPLEX REQUIREMENTS (OR-Groups) ---
    complex_req = req.get('complex_requirements', "")
    if complex_req and complex_req != "":
        passed, reason = check_complex_requirements(g, complex_req)
        if not check("chk_complex_req", passed, reason):
            passed_academics = False

    # Minimum thresholds
    min_c = to_int(req.get('min_credits', 0))
    if min_c > 0:
        if not check("chk_min_credit", student.credits >= min_c, "fail_min_credit"):
            passed_academics = False

    min_p = to_int(req.get('min_pass', 0))
    if min_p > 0:
        if not check("chk_min_pass", student.passes >= min_p, "fail_min_pass"):
            passed_academics = False

    return passed_academics, audit
