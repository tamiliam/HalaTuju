"""Grade classes, subject lists and the small grade helpers of the eligibility engine.

Moved verbatim out of `engine.py` (audit sprint A3.6, a moves-only split: `engine.py` was a ledgered
oversize file). `engine.py` re-exports every name, so every `from apps.courses.engine import ...` is
unchanged. Nothing here changed.
"""

# ============================================
# GRADE CLASSIFICATION CONSTANTS
# ============================================

PASS_GRADES = {"A+", "A", "A-", "B+", "B", "C+", "C", "D", "E"}
CREDIT_GRADES = {"A+", "A", "A-", "B+", "B", "C+", "C"}
CREDIT_B_GRADES = {"A+", "A", "A-", "B+", "B"}  # Grade B or better (for UA requirements)
DISTINCTION_GRADES = {"A+", "A", "A-"}  # Grade A- or better (for UA requirements)
ATTEMPTED_GRADES = PASS_GRADES | {"G"}

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
