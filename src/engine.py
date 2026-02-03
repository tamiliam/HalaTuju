"""
ELIGIBILITY ENGINE — POLICY & INTERPRETATION NOTES
=================================================

This engine evaluates student eligibility for courses using two datasets:
1) requirements.csv          (Polytechnic / KK courses)
2) tvet_requirements.csv     (ILKBS / ILJTM courses)

The logic implemented here MUST follow the policy below. Any deviation
should be treated as a bug unless the policy itself is explicitly updated.

-----------------------------------------------------------------------
GENERAL PRINCIPLES
-----------------------------------------------------------------------

1. All requirements are conjunctive unless explicitly stated otherwise.
   - If a column exists and is set (e.g. 1 / True), the student must satisfy it.
   - 0 / Empty / null values impose no constraint.

2. Eligibility is binary.
   - A student either qualifies or does not qualify for a course.
   - Each failed requirement should be tracked for explanation purposes.

3. "Pass" and "Credit" are distinct.
   - Credit implies pass, but pass does not imply credit.
   - Credit-level requirements are stricter than pass-level requirements.

4. Composite subject requirements are OR-based.
   - Where a requirement refers to a group of subjects, satisfying ANY ONE
     of the listed subjects is sufficient.

5. Interview requirements do NOT disqualify a student.
   - They are advisory flags only (e.g. "Eligible, subject to interview").

-----------------------------------------------------------------------
requirements.csv (Polytechnic / KK)
-----------------------------------------------------------------------

Identity & minimums:
- course_id        : unique course identifier
- min_credits      : minimum total number of credits required

Citizenship & gender:
- req_malaysian    : student must be Malaysian
- req_male         : course open to males only
- req_female       : course open to females only
  (These two must never both be set.)

Core pass requirements:
- pass_bm          : pass Bahasa Malaysia
- pass_history     : pass History
- pass_eng         : pass English
- pass_math        : pass Mathematics

Credit-level requirements:
- credit_math      : credit in Mathematics
- credit_bm        : credit in Bahasa Malaysia
- credit_english   : credit in English

Composite subject groups (OR conditions):
- pass_stv         : pass at least one Science, Technical, OR Vocational subject
- credit_stv       : credit in at least one Science, Technical, OR Vocational subject
- credit_sf        : credit in Science (General) OR Physics
- credit_sfmt      : credit in Science (General), Physics, OR Additional Mathematics
- credit_bmbi      : credit in Bahasa Malaysia OR English

Medical / physical constraints:
- no_colorblind    : student must NOT be colourblind
- no_disability    : student must be physically fit (not blind, deaf, dumb, have physical or learning difficulties or other disabilities that will impede practical work)

Interview:
- req_interview    : interview required; does NOT disqualify eligibility

Remarks:
- remarks          : free-text notes, not machine-enforced

-----------------------------------------------------------------------
tvet_requirements.csv (ILKBS / ILJTM)
-----------------------------------------------------------------------

Minimum academic requirements:
- min_credits      : minimum number of credits
- min_pass         : minimum number of passes

Core pass requirements:
- pass_bm          : pass Bahasa Malaysia
- pass_history     : pass History
- pass_math_addmath: pass Mathematics OR Additional Mathematics
- pass_science_tech: pass Science (Chemistry/Physics/General) OR Technical subject
- pass_math_science: pass Mathematics OR Science (Chemistry/Physics/General)

Credit requirements (OR conditions):
- credit_math_sci_tech : credit in Math, any Science, OR Technical subject
- credit_math_sci      : credit in Math OR any Science subject
- credit_english       : credit in English

Literacy & social constraints:
- 3m_only          : able to read, write, AND count
- single           : student must be unmarried

Medical / physical constraints:
- no_colorblind    : student must not be colourblind
- no_disability    : student must be physically fit

Remarks:
- remarks          : free-text notes, not machine-enforced

-----------------------------------------------------------------------
IMPLEMENTATION WARNING
-----------------------------------------------------------------------
Common implementation errors to avoid:
- Treating OR-based composite requirements as AND conditions
- Treating interview requirements as disqualifying
- Requiring multiple credits where only one qualifying subject is needed
- Failing silently without recording which rule caused rejection

This text is the authoritative description of how the eligibility rules
are intended to work.
"""

import pandas as pd
import numpy as np
import json
import itertools

PASS_GRADES = {"A+", "A", "A-", "B+", "B", "C+", "C", "D", "E"}
CREDIT_GRADES = {"A+", "A", "A-", "B+", "B", "C+", "C"}
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

# Technical/Engineering Subjects (NEW)
SUBJ_LIST_TECHNICAL = [
    "eng_civil", "eng_mech", "eng_elec",
    "eng_draw", "gkt", "kelestarian", "reka_cipta"
]

# IT/Computing Subjects (NEW)
SUBJ_LIST_IT = [
    "comp_sci", "multimedia", "digital_gfx"
]

# Vocational Subjects - MPV (NEW)
SUBJ_LIST_VOCATIONAL = [
    "voc_construct", "voc_plumb", "voc_wiring", "voc_weld",
    "voc_auto", "voc_elec_serv", "voc_food", "voc_landscape",
    "voc_catering", "voc_tailoring"
]

# General Electives (moral kept, islam removed - Islamic school subject)
SUBJ_LIST_EXTRA = [
    "moral", "pertanian", "sci", "srt", "addsci",
    "sports_sci", "music"
]

# ============================================
# COMPOSITE GROUPS - For Eligibility Logic
# ============================================
# These groups are used for STV and similar composite checks

SUBJ_GROUP_SCIENCE = ["chem", "phy", "bio", "sci", "addsci"]
SUBJ_GROUP_TECHNICAL = SUBJ_LIST_TECHNICAL + SUBJ_LIST_IT
SUBJ_GROUP_VOCATIONAL = SUBJ_LIST_VOCATIONAL

# Legacy key mapping (for backward compatibility with existing user data)
LEGACY_KEY_MAP = {
    "tech": "eng_civil",  # Map generic 'tech' to most common technical subject
    "voc": "voc_weld",    # Map generic 'voc' to most common vocational subject
    "islam": "moral",     # Map removed subject to moral (neutral fallback)
    "b_arab": "b_tamil"   # Map removed Arabic to Tamil (neutral fallback)
}

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

# Define all columns used for requirement checking
REQ_FLAG_COLUMNS = [
    'req_malaysian', 'req_male', 'req_female', 'no_colorblind', 'no_disability',
    '3m_only', 'pass_bm', 'credit_bm', 'pass_history', 
    'pass_eng', 'credit_english', 'pass_math', 'credit_math', 'pass_math_addmath',
    'pass_math_science', 'pass_science_tech', 'credit_math_sci',
    'credit_math_sci_tech', 'pass_stv', 'credit_sf', 'credit_sfmt',
    'credit_bmbi', 'credit_stv',
    'req_interview', 'single', 'req_group_diversity'
]

REQ_COUNT_COLUMNS = ['min_credits', 'min_pass', 'max_aggregate_units']
REQ_TEXT_COLUMNS = ['subject_group_req']

ALL_REQ_COLUMNS = REQ_FLAG_COLUMNS + REQ_COUNT_COLUMNS + REQ_TEXT_COLUMNS

# --- 1. DATA SANITIZER (The Bouncer) ---
def load_and_clean_data(filepath):
    """
    Loads CSV and enforces strict integer types for flag columns.
    """
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
        # Default max_aggregate_units to 100 (loose) if 0/missing
        if col == 'max_aggregate_units':
             df[col] = pd.to_numeric(df[col], errors='coerce').fillna(100).astype(int)
             df.loc[df[col] == 0, col] = 100 # Treat 0 as "No Limit" (100)
        else:
             df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
    return df

# --- 2. HELPER FUNCTIONS ---
def is_pass(grade):
    return grade in PASS_GRADES

def is_credit(grade):
    return grade in CREDIT_GRADES

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
    # Fallback to lowercase
    return subj_code.lower()

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

    # If it's a list, we treat it as AND conditions (match ALL rules in the list)
    if isinstance(rules, list):
        for rule in rules:
            min_grade = rule.get("min_grade", "E")
            min_count = rule.get("min_count", 1)
            
            # --- AGGREGATE UNIT & DIVERSITY CHECK (STPM STYLE) ---
            if "allowed_groups" in rule and check_diversity:
                allowed_groups = rule.get("allowed_groups", [])
                valid_entries = []
                
                for g_idx, subjects_in_group in enumerate(allowed_groups):
                    for subj in subjects_in_group:
                        student_key = map_subject_code(subj)
                        
                        grade = student_grades.get(student_key)
                        
                        if grade and is_attempted(grade):
                            pts = AGGREGATE_GRADE_POINTS.get(grade, 10)
                            threshold_pts = AGGREGATE_GRADE_POINTS.get(min_grade, 8) # E=8 default
                            
                            valid_entries.append({
                                "subj": student_key,
                                "group": g_idx, 
                                "points": pts,
                                "grade": grade,
                                "meets_grade": pts <= threshold_pts
                            })

                # 2. Find a valid combination of 'min_count' subjects
                # Optimization: Group valid subjects by group_index, picking best per group
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

            # --- SIMPLE LIST CHECK (PISMP STYLE) ---
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

class StudentProfile:
    def __init__(self, grades, gender, nationality, colorblind, disability, other_tech=False, other_voc=False):
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
            if is_credit(grade): self.credits += 1
            if is_pass(grade): self.passes += 1

# --- 3. THE ENGINE (Pure Logic) ---
def check_eligibility(student, req):
    """
    Checks if a student meets the requirements.
    Expects 'req' to be a CLEAN dictionary (integers only).
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
    # Notice: We removed 'safe_int'. We trust the data is clean now.
    if to_int(req.get('req_malaysian')) == 1:
        if not check("chk_malaysian", student.nationality == 'Warganegara', "fail_malaysian"): return False, audit
    # Gender normalization: Accept any language (EN/MS/TA)
    MALE_VALUES = {'Lelaki', 'Male', 'ஆண்'}
    FEMALE_VALUES = {'Perempuan', 'Female', 'பெண்'}
    
    if to_int(req.get('req_male')) == 1:
        if not check("chk_male", student.gender in MALE_VALUES, "fail_male"): return False, audit
    if to_int(req.get('req_female')) == 1:
        if not check("chk_female", student.gender in FEMALE_VALUES, "fail_female"): return False, audit
    if to_int(req.get('no_colorblind')) == 1:
        if not check("chk_colorblind", student.colorblind == 'Tidak', "fail_colorblind"): return False, audit
    if to_int(req.get('no_disability')) == 1:
        if not check("chk_disability", student.disability == 'Tidak', "fail_disability"): return False, audit

    # NEW: Age Limit Check
    age_limit = to_int(req.get('age_limit', 0))
    if age_limit > 0:
        # Assuming student age is valid (TODO: Add age to StudentProfile, default pass for now)
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
        if not check("chk_pass_bm", is_pass(g.get('bm')), "fail_pass_bm"): passed_academics = False
    if to_int(req.get('credit_bm')) == 1:
        if not check("chk_credit_bm", is_credit(g.get('bm')), "fail_credit_bm"): passed_academics = False
    if to_int(req.get('pass_history')) == 1:
        if not check("chk_pass_hist", is_pass(g.get('hist')), "fail_pass_hist"): passed_academics = False
    if to_int(req.get('pass_eng')) == 1:
        if not check("chk_pass_eng", is_pass(g.get('eng')), "fail_pass_eng"): passed_academics = False
    if to_int(req.get('credit_english')) == 1:
        if not check("chk_credit_eng", is_credit(g.get('eng')), "fail_credit_eng"): passed_academics = False

    # Logic: Passing Add Math satisfies the "Math" requirement.
    if to_int(req.get('pass_math')) == 1:
        # Check Modern Math ONLY (Poly Policy)
        if not check("chk_pass_math", is_pass(g.get('math')), "fail_pass_math"): passed_academics = False

    if to_int(req.get('pass_math_addmath')) == 1:
        # Check Modern Math OR Add Math (TVET Policy)
        cond = is_pass(g.get('math')) or is_pass(g.get('addmath'))
        if not check("chk_pass_math_addmath", cond, "fail_pass_math_addmath"): passed_academics = False

    if to_int(req.get('credit_math')) == 1:
        # Check Credit in Modern Math OR Add Math
        cond = is_credit(g.get('math')) or is_credit(g.get('addmath'))
        if not check("chk_credit_math", cond, "fail_credit_math"): passed_academics = False

    # Group Logic
    pure_sci = [g.get('phy'), g.get('chem'), g.get('bio')]
    all_sci = pure_sci + [g.get('sci')]
    
    # TVET Special: Science excluding Biology (Phys, Chem, General Sci)
    sci_no_bio = [g.get('phy'), g.get('chem'), g.get('sci')]

    # Tech/Voc logic: Checks the generic 'tech' and 'voc' inputs
    def has_pass(grade_list): return any(is_pass(x) for x in grade_list)
    def has_credit(grade_list): return any(is_credit(x) for x in grade_list)
    
    # --- TVET Rules (ILKBS/ILJTM) ---

    if to_int(req.get('pass_math_science')) == 1:
        cond = is_pass(g.get('math')) or has_pass(sci_no_bio)
        if not check("chk_pass_math_sci_nb", cond, "fail_pass_math_sci_nb"): passed_academics = False
        
    if to_int(req.get('pass_science_tech')) == 1:
        # Check any technical subject (including IT) for pass
        has_tech_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        legacy_tech_pass = is_pass(g.get('tech'))
        cond = has_pass(sci_no_bio) or has_tech_pass or legacy_tech_pass
        if not check("chk_pass_sci_tech", cond, "fail_pass_sci_tech"): passed_academics = False

    if to_int(req.get('credit_math_sci')) == 1:
        cond = is_credit(g.get('math')) or has_credit(all_sci)
        if not check("chk_credit_math_sci", cond, "fail_credit_math_sci"): passed_academics = False

    if to_int(req.get('credit_math_sci_tech')) == 1:
        # Check any technical subject (including IT) for credit
        has_tech_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        legacy_tech_credit = is_credit(g.get('tech'))
        cond = is_credit(g.get('math')) or has_credit(all_sci) or has_tech_credit or legacy_tech_credit
        if not check("chk_credit_math_sci_tech", cond, "fail_credit_math_sci_tech"): passed_academics = False

    # --- Poly/KK Rules ---
    
    if to_int(req.get('credit_bmbi')) == 1:
        cond = is_credit(g.get('bm')) or is_credit(g.get('eng'))
        if not check("chk_credit_bmbi", cond, "fail_credit_bmbi"): passed_academics = False

    if to_int(req.get('credit_stv')) == 1:
        # Check any technical subject (including IT) or vocational subject for credit
        has_tech_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        has_voc_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_VOCATIONAL)
        # Also check legacy 'tech'/'voc' keys for backward compatibility
        legacy_tech_credit = is_credit(g.get('tech'))
        legacy_voc_credit = is_credit(g.get('voc'))
        cond = has_credit(all_sci) or has_tech_credit or has_voc_credit or legacy_tech_credit or legacy_voc_credit
        if not check("chk_credit_stv", cond, "fail_credit_stv"): passed_academics = False

    if to_int(req.get('pass_stv')) == 1:
        # Check any technical subject (including IT) or vocational subject for pass
        has_tech_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        has_voc_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_VOCATIONAL)
        # Also check legacy 'tech'/'voc' keys for backward compatibility
        legacy_tech_pass = is_pass(g.get('tech'))
        legacy_voc_pass = is_pass(g.get('voc'))
        cond = has_pass(all_sci) or has_tech_pass or has_voc_pass or legacy_tech_pass or legacy_voc_pass
        if not check("chk_pass_stv", cond, "fail_pass_stv"): passed_academics = False

    if to_int(req.get('credit_sf')) == 1:
        cond = is_credit(g.get('sci')) or is_credit(g.get('phy'))
        if not check("chk_credit_sf", cond, "fail_credit_sf"): passed_academics = False

    if to_int(req.get('credit_sfmt')) == 1:
        cond = is_credit(g.get('sci')) or is_credit(g.get('phy')) or is_credit(g.get('addmath'))
        if not check("chk_credit_sfmt", cond, "fail_credit_sfmt"): passed_academics = False

    # --- ADVANCED RULES (JSON Logic) ---
    json_req = req.get('subject_group_req', "")
    if json_req and json_req != "":
        max_agg = to_int(req.get('max_aggregate_units', 100))
        # Don't let 0 mean fail, 0 means no limit check usually? 
        # But our loader logic already set it to 100 if user input was 0/missing.
        
        check_div = to_int(req.get('req_group_diversity', 0)) == 1
        
        passed, reason = check_subject_group_logic(g, json_req, max_agg, check_div)
        if not check("chk_adv_subj_group", passed, reason): passed_academics = False

    min_c = to_int(req.get('min_credits', 0))
    if min_c > 0:
        if not check(f"chk_min_credit", student.credits >= min_c, f"fail_min_credit"): passed_academics = False

    min_p = to_int(req.get('min_pass', 0))
    if min_p > 0:
        if not check(f"chk_min_pass", student.passes >= min_p, f"fail_min_pass"): passed_academics = False

    return passed_academics, audit

# --- MERIT HELPER ---
def check_merit_probability(student_merit, course_cutoff):
    """
    Returns (label, color_hex) based on the gap between student merit and course cutoff.
    """
    try:
        cutoff = float(course_cutoff)
        merit = float(student_merit)
    except:
        return "Unknown", "#95a5a6" # Grey

    # Logic from Plan
    # >= Cutoff : High (Green)
    # >= Cutoff - 5 : Fair (Yellow)
    # < Cutoff - 5 : Low (Red)

    gap = merit - cutoff
    
    if gap >= 0:
        return "High", "#2ecc71" # Green
    elif gap >= -5:
        return "Fair", "#f1c40f" # Yellow
    else:
        return "Low", "#e74c3c" # Red

# --- MERIT PREPARATION ---
def prepare_merit_inputs(grades):
    """
    Intelligently splits grades into Sec1 (5 subjs), Sec2 (3 subjs), Sec3 (1 subj)
    for UPU-style merit calculation.
    """
    # 1. Identify Stream (Heuristic)
    has_phy = 'phy' in grades
    has_chem = 'chem' in grades
    has_bio = 'bio' in grades
    is_science = has_phy and has_chem
    
    # helper
    def get_g(s): return grades.get(s, 'G')
    
    # 2. Section 3: History (Critical for UPU)
    sec3 = [get_g('history')]
    
    # 3. Section 1: 5 Critical Subjects
    sec1_keys = []
    if is_science:
        # Math, AddMath, Phy, Chem, Bio/Others
        candidates = ['math', 'addmath', 'phy', 'chem', 'bio']
        for k in candidates:
            if k in grades: sec1_keys.append(k)
    else:
        # BM, Math, Sci, + Best 2
        candidates = ['bm', 'math', 'sci']
        for k in candidates:
             if k in grades: sec1_keys.append(k)
             
    # Fill Sec1 to 5 items with best remaining
    # Sort remaining by grade point
    all_keys = list(grades.keys())
    used = set(['history'] + sec1_keys)
    remaining = [k for k in all_keys if k not in used and grades[k] not in ['G', 'E', 'D', 'C', 'C+']] # Prioritize high grades
    
    # Sort logic: A+ > A ...
    # Reuse MERIT_GRADE_POINTS
    remaining.sort(key=lambda k: MERIT_GRADE_POINTS.get(grades[k], 0), reverse=True)
    
    while len(sec1_keys) < 5 and remaining:
        k = remaining.pop(0)
        sec1_keys.append(k)
        
    sec1 = [grades.get(k) for k in sec1_keys]
    
    # 4. Section 2: Next 3 Best
    sec2_keys = []
    while len(sec2_keys) < 3 and remaining:
        k = remaining.pop(0)
        sec2_keys.append(k)
        
    sec2 = [grades.get(k) for k in sec2_keys]
    
    return sec1, sec2, sec3
