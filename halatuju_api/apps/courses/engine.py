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

# The SPM merit calculation (UPU formula, stream pools, `prepare_merit_inputs`, the probability
# label) moved verbatim to `engine_merit.py` (Bumi coverage Sprint D1, a moves-only split: this file
# is a ledgered oversize file and sat at its budget). Re-exported here, so every
# `from apps.courses.engine import ...` is unchanged.
from .engine_merit import (
    ARTS_POOL, MERIT_COLORS, MERIT_GAP_FAIR, MERIT_GAP_HIGH, MERIT_GRADE_POINTS, SCIENCE_POOL,
    TECHNICAL_POOL, calculate_merit_score, check_merit_probability, prepare_merit_inputs,
)

# The grade classes, subject lists and grade helpers moved verbatim to `engine_grades.py`, and the
# two JSON requirement checkers to `engine_subject_rules.py` (audit sprint A3.6, a moves-only split).
# Re-exported here, so every `from apps.courses.engine import ...` is unchanged.
from .engine_grades import (  # noqa: F401  (re-exports)
    AGGREGATE_GRADE_POINTS, ATTEMPTED_GRADES, CREDIT_B_GRADES, CREDIT_GRADES, DISTINCTION_GRADES,
    PASS_GRADES, SUBJ_GROUP_SCIENCE, SUBJ_GROUP_TECHNICAL, SUBJ_GROUP_VOCATIONAL, SUBJ_LIST_ARTS,
    SUBJ_LIST_EXTRA, SUBJ_LIST_IT, SUBJ_LIST_SCIENCE, SUBJ_LIST_TECHNICAL, SUBJ_LIST_VOCATIONAL,
    is_attempted, is_credit, is_credit_b, is_distinction, is_pass, map_subject_code, to_int,
)
from .engine_subject_rules import (  # noqa: F401  (re-exports)
    check_complex_requirements, check_subject_group_logic,
)

# ============================================
# STUDENT PROFILE CLASS
# ============================================

class StudentProfile:
    """
    Encapsulates a student's data for eligibility checking.

    IMPORTANT: This class is used by the engine and MUST match the original.
    """

    def __init__(self, grades, gender, nationality, colorblind, disability,
                 other_tech=False, other_voc=False, bumiputera=False):
        self.grades = grades
        self.gender = gender
        self.nationality = nationality
        self.colorblind = colorblind
        self.disability = disability
        self.other_tech = other_tech
        self.other_voc = other_voc
        self.bumiputera = bumiputera  # course guide only: the caller resolves it (bumiputera.py)

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

    Audit sprint A3.6 broke the body into the named steps below, in the same order, with the same
    labels and the same early returns: the gatekeepers and the PISMP language gate stop the check,
    the 3M-only rule answers it alone, and every academic step records its rows and carries on.

    Args:
        student: StudentProfile object
        req: Dictionary of requirement flags (from DB or CSV row)

    Returns:
        (bool, list): (is_eligible, audit_trail)
    """
    audit = []

    # GATEKEEPERS
    if not _gatekeepers_pass(student, req, audit):
        return False, audit

    # Age limit (placeholder)
    age_limit = to_int(req.get('age_limit', 0))
    if age_limit > 0:
        pass

    g = student.grades

    if not _pismp_language_gate_passes(g, req, audit):
        return False, audit

    # --- TVET SPECIAL: 3M ONLY ---
    if to_int(req.get('three_m_only')) == 1:
        cond = is_attempted(g.get('bm')) and is_attempted(g.get('math'))
        audit.append({
            "label": "chk_3m",
            "passed": cond,
            "reason": None if cond else "fail_3m"
        })
        return cond, audit

    # ACADEMIC CHECKS: every step runs, each records its rows; one failure fails the academics.
    passed_academics = True
    for step in (_single_subject_checks, _math_and_ua_group_checks, _tvet_and_poly_checks,
                 _json_rule_checks):
        if not step(g, req, audit):
            passed_academics = False
    if not _minimum_count_checks(student, req, audit):
        passed_academics = False

    return passed_academics, audit


def _check(audit, label, condition, fail_msg=None):
    """Record one audit row; True when the condition held (the old inner `check`)."""
    if condition:
        audit.append({"label": label, "passed": True, "reason": None})
        return True
    else:
        audit.append({"label": label, "passed": False, "reason": fail_msg})
        return False


MALE_VALUES = {'Lelaki', 'Male', 'ஆண்'}
FEMALE_VALUES = {'Perempuan', 'Female', 'பெண்'}


def _gatekeepers_pass(student, req, audit):
    """The gatekeepers, in order. The first that fails stops the check (False)."""
    if to_int(req.get('req_malaysian')) == 1:
        if not _check(audit, "chk_malaysian", student.nationality == 'Warganegara', "fail_malaysian"):
            return False

    if to_int(req.get('req_male')) == 1:
        if not _check(audit, "chk_male", student.gender in MALE_VALUES, "fail_male"):
            return False
    if to_int(req.get('req_female')) == 1:
        if not _check(audit, "chk_female", student.gender in FEMALE_VALUES, "fail_female"):
            return False
    if to_int(req.get('no_colorblind')) == 1:
        if not _check(audit, "chk_colorblind", not student.colorblind, "fail_colorblind"):
            return False
    if to_int(req.get('no_disability')) == 1:
        if not _check(audit, "chk_disability", not student.disability, "fail_disability"):
            return False
    # MBPK (special-needs) intake — only students who declared a disability qualify.
    if to_int(req.get('req_disability')) == 1:
        if not _check(audit, "chk_req_disability", student.disability, "fail_req_disability"):
            return False
    # Bumiputera-only (UiTM; Bumi Sprint D1) — only a real True opens it, never a truthy string.
    if to_int(req.get('req_bumiputera')) == 1:
        if not _check(audit, "chk_bumiputera", student.bumiputera is True, "fail_bumiputera"):
            return False
    return True


def _pismp_language_gate_passes(g, req, audit):
    """PISMP medium-of-instruction gate: Chinese-stream (zone 03) requires
    credit in Bahasa Cina, Tamil-stream (zone 04) requires credit in
    Bahasa Tamil. This is a universal rule regardless of CSV data.
    False stops the check."""
    course_id = str(req.get('course_id', ''))
    if req.get('source_type') == 'pismp' and len(course_id) >= 6:
        zone = course_id[4:6]
        if zone == '03':
            if not _check(audit, "chk_pismp_lang_bc", is_credit(g.get('b_cina')), "fail_pismp_lang_bc"):
                return False
        elif zone == '04':
            if not _check(audit, "chk_pismp_lang_bt", is_credit(g.get('b_tamil')), "fail_pismp_lang_bt"):
                return False
    return True


# The one-subject academic checks, in the order the engine has always run them:
# (requirement flag, audit label, grade test, subject key, failure reason).
_SINGLE_SUBJECT_CHECKS = (
    ('pass_bm', "chk_pass_bm", is_pass, 'bm', "fail_pass_bm"),
    ('credit_bm', "chk_credit_bm", is_credit, 'bm', "fail_credit_bm"),
    ('pass_history', "chk_pass_hist", is_pass, 'hist', "fail_pass_hist"),
    ('pass_eng', "chk_pass_eng", is_pass, 'eng', "fail_pass_eng"),
    ('credit_english', "chk_credit_eng", is_credit, 'eng', "fail_credit_eng"),
    # --- UA Grade B Requirements ---
    ('credit_bm_b', "chk_credit_bm_b", is_credit_b, 'bm', "fail_credit_bm_b"),
    ('credit_eng_b', "chk_credit_eng_b", is_credit_b, 'eng', "fail_credit_eng_b"),
    ('credit_math_b', "chk_credit_math_b", is_credit_b, 'math', "fail_credit_math_b"),
    ('credit_addmath_b', "chk_credit_addmath_b", is_credit_b, 'addmath', "fail_credit_addmath_b"),
    # --- UA Distinction Requirements ---
    ('distinction_bm', "chk_distinction_bm", is_distinction, 'bm', "fail_distinction_bm"),
    ('distinction_eng', "chk_distinction_eng", is_distinction, 'eng', "fail_distinction_eng"),
    ('distinction_math', "chk_distinction_math", is_distinction, 'math', "fail_distinction_math"),
    ('distinction_addmath', "chk_distinction_addmath", is_distinction, 'addmath',
     "fail_distinction_addmath"),
    ('distinction_bio', "chk_distinction_bio", is_distinction, 'bio', "fail_distinction_bio"),
    ('distinction_phy', "chk_distinction_phy", is_distinction, 'phy', "fail_distinction_phy"),
    ('distinction_chem', "chk_distinction_chem", is_distinction, 'chem', "fail_distinction_chem"),
    ('distinction_sci', "chk_distinction_sci", is_distinction, 'sci', "fail_distinction_sci"),
    # --- PI/PM Requirements ---
    ('pass_islam', "chk_pass_islam", is_pass, 'islam', "fail_pass_islam"),
    ('credit_islam', "chk_credit_islam", is_credit, 'islam', "fail_credit_islam"),
    ('pass_moral', "chk_pass_moral", is_pass, 'moral', "fail_pass_moral"),
    ('credit_moral', "chk_credit_moral", is_credit, 'moral', "fail_credit_moral"),
    # --- UA Science Requirements ---
    ('pass_sci', "chk_pass_sci", is_pass, 'sci', "fail_pass_sci"),
    ('credit_sci', "chk_credit_sci", is_credit, 'sci', "fail_credit_sci"),
    ('credit_addmath', "chk_credit_addmath", is_credit, 'addmath', "fail_credit_addmath"),
    # Math checks
    ('pass_math', "chk_pass_math", is_pass, 'math', "fail_pass_math"),
)


def _single_subject_checks(g, req, audit):
    ok = True
    for flag, label, test, subject, fail_msg in _SINGLE_SUBJECT_CHECKS:
        if to_int(req.get(flag)) == 1:
            if not _check(audit, label, test(g.get(subject)), fail_msg):
                ok = False
    return ok


def _has_pass(grade_list):
    return any(is_pass(x) for x in grade_list)


def _has_credit(grade_list):
    return any(is_credit(x) for x in grade_list)


def _math_and_ua_group_checks(g, req, audit):
    ok = True
    if to_int(req.get('pass_math_addmath')) == 1:
        cond = is_pass(g.get('math')) or is_pass(g.get('addmath'))
        if not _check(audit, "chk_pass_math_addmath", cond, "fail_pass_math_addmath"):
            ok = False

    if to_int(req.get('credit_math')) == 1:
        cond = is_credit(g.get('math')) or is_credit(g.get('addmath'))
        if not _check(audit, "chk_credit_math", cond, "fail_credit_math"):
            ok = False

    # Group Logic
    pure_sci = [g.get('phy'), g.get('chem'), g.get('bio')]
    all_sci = pure_sci + [g.get('sci')]

    # --- UA Rules ---
    if to_int(req.get('credit_science_group')) == 1:
        all_sci_with_addsci = all_sci + [g.get('addsci'), g.get('comp_sci')]
        cond = _has_credit(all_sci_with_addsci)
        if not _check(audit, "chk_credit_sci_group", cond, "fail_credit_sci_group"):
            ok = False

    if to_int(req.get('credit_math_or_addmath')) == 1:
        cond = is_credit(g.get('math')) or is_credit(g.get('addmath'))
        if not _check(audit, "chk_credit_math_or_addmath", cond, "fail_credit_math_or_addmath"):
            ok = False

    if to_int(req.get('single')) == 1:
        pass  # Skip - we don't capture marital status yet
    return ok


def _tvet_and_poly_checks(g, req, audit):
    ok = True
    pure_sci = [g.get('phy'), g.get('chem'), g.get('bio')]
    all_sci = pure_sci + [g.get('sci')]
    sci_no_bio = [g.get('phy'), g.get('chem'), g.get('sci')]

    # --- TVET Rules ---
    if to_int(req.get('pass_math_science')) == 1:
        cond = is_pass(g.get('math')) or _has_pass(sci_no_bio)
        if not _check(audit, "chk_pass_math_sci_nb", cond, "fail_pass_math_sci_nb"):
            ok = False

    if to_int(req.get('pass_science_tech')) == 1:
        has_tech_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        legacy_tech_pass = is_pass(g.get('tech'))
        cond = _has_pass(sci_no_bio) or has_tech_pass or legacy_tech_pass
        if not _check(audit, "chk_pass_sci_tech", cond, "fail_pass_sci_tech"):
            ok = False

    if to_int(req.get('credit_math_sci')) == 1:
        cond = is_credit(g.get('math')) or _has_credit(all_sci)
        if not _check(audit, "chk_credit_math_sci", cond, "fail_credit_math_sci"):
            ok = False

    if to_int(req.get('credit_math_sci_tech')) == 1:
        has_tech_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        legacy_tech_credit = is_credit(g.get('tech'))
        cond = is_credit(g.get('math')) or _has_credit(all_sci) or has_tech_credit or legacy_tech_credit
        if not _check(audit, "chk_credit_math_sci_tech", cond, "fail_credit_math_sci_tech"):
            ok = False

    # --- Poly/KK Rules ---
    if to_int(req.get('credit_bmbi')) == 1:
        cond = is_credit(g.get('bm')) or is_credit(g.get('eng'))
        if not _check(audit, "chk_credit_bmbi", cond, "fail_credit_bmbi"):
            ok = False

    if to_int(req.get('credit_stv')) == 1:
        has_tech_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        has_voc_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_VOCATIONAL)
        legacy_tech_credit = is_credit(g.get('tech'))
        legacy_voc_credit = is_credit(g.get('voc'))
        cond = _has_credit(all_sci) or has_tech_credit or has_voc_credit or legacy_tech_credit or legacy_voc_credit
        if not _check(audit, "chk_credit_stv", cond, "fail_credit_stv"):
            ok = False

    if to_int(req.get('pass_stv')) == 1:
        has_tech_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
        has_voc_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_VOCATIONAL)
        legacy_tech_pass = is_pass(g.get('tech'))
        legacy_voc_pass = is_pass(g.get('voc'))
        cond = _has_pass(all_sci) or has_tech_pass or has_voc_pass or legacy_tech_pass or legacy_voc_pass
        if not _check(audit, "chk_pass_stv", cond, "fail_pass_stv"):
            ok = False

    if to_int(req.get('credit_sf')) == 1:
        cond = is_credit(g.get('sci')) or is_credit(g.get('phy'))
        if not _check(audit, "chk_credit_sf", cond, "fail_credit_sf"):
            ok = False

    if to_int(req.get('credit_sfmt')) == 1:
        cond = is_credit(g.get('sci')) or is_credit(g.get('phy')) or is_credit(g.get('addmath'))
        if not _check(audit, "chk_credit_sfmt", cond, "fail_credit_sfmt"):
            ok = False
    return ok


def _json_rule_checks(g, req, audit):
    ok = True
    # --- ADVANCED RULES (JSON Logic) ---
    json_req = req.get('subject_group_req', "")
    if json_req and json_req != "":
        max_agg = to_int(req.get('max_aggregate_units', 100))
        check_div = to_int(req.get('req_group_diversity', 0)) == 1
        passed, reason = check_subject_group_logic(g, json_req, max_agg, check_div)
        if not _check(audit, "chk_adv_subj_group", passed, reason):
            ok = False

    # --- UNIVERSITY COMPLEX REQUIREMENTS (OR-Groups) ---
    complex_req = req.get('complex_requirements', "")
    if complex_req and complex_req != "":
        passed, reason = check_complex_requirements(g, complex_req)
        if not _check(audit, "chk_complex_req", passed, reason):
            ok = False
    return ok


def _minimum_count_checks(student, req, audit):
    ok = True
    # Minimum thresholds
    min_c = to_int(req.get('min_credits', 0))
    if min_c > 0:
        if not _check(audit, "chk_min_credit", student.credits >= min_c, "fail_min_credit"):
            ok = False

    min_p = to_int(req.get('min_pass', 0))
    if min_p > 0:
        if not _check(audit, "chk_min_pass", student.passes >= min_p, "fail_min_pass"):
            ok = False
    return ok
