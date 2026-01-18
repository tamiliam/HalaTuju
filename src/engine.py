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

PASS_GRADES = {"A+", "A", "A-", "B+", "B", "C+", "C", "D", "E"}
CREDIT_GRADES = {"A+", "A", "A-", "B+", "B", "C+", "C"}
ATTEMPTED_GRADES = PASS_GRADES | {"G"}

# Define all columns used for requirement checking
# This acts as the Single Source of Truth for other modules (like dashboard.py)
REQ_FLAG_COLUMNS = [
    'req_malaysian', 'req_male', 'req_female', 'no_colorblind', 'no_disability',
    '3m_only', 'pass_bm', 'credit_bm', 'pass_history', 
    'pass_eng', 'credit_english', 'pass_math', 'credit_math', 'pass_math_addmath',
    'pass_math_science', 'pass_science_tech', 'credit_math_sci',
    'credit_math_sci_tech', 'pass_stv', 'credit_sf', 'credit_sfmt',
    'credit_bmbi', 'credit_stv'
]

REQ_COUNT_COLUMNS = ['min_credits', 'min_pass']

ALL_REQ_COLUMNS = REQ_FLAG_COLUMNS + REQ_COUNT_COLUMNS

# --- 1. DATA SANITIZER (The Bouncer) ---
def load_and_clean_data(filepath):
    """
    Loads CSV and enforces strict integer types for flag columns.
    Converts '1.0', 'Yes', 'True' -> 1
    Converts '0', 'No', 'False', NaN -> 0
    """
    df = pd.read_csv(filepath)
    
    # List of columns that MUST be integers (0 or 1)
    # flag_columns = [ ... ] (Moved to module constant REQ_FLAG_COLUMNS)
    
    for col in REQ_FLAG_COLUMNS:
        if col in df.columns:
            # Force numeric, turning errors (like 'Yes') into NaN
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    # Handle 'min_credits' and 'min_pass' separately (they are counts, not flags)
    for col in REQ_COUNT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
    return df

# --- 2. HELPER FUNCTIONS ---
def is_pass(grade):
    return grade in PASS_GRADES

def is_credit(grade):
    return grade in CREDIT_GRADES

def is_attempted(grade):
    return grade in ATTEMPTED_GRADES

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
    if req.get('req_malaysian') == 1:
        if not check("Warganegara", student.nationality == 'Warganegara', "Hanya untuk Warganegara"): return False, audit
    if req.get('req_male') == 1:
        if not check("Jantina (Lelaki)", student.gender == 'Lelaki', "Lelaki Sahaja"): return False, audit
    if req.get('req_female') == 1:
        if not check("Jantina (Wanita)", student.gender == 'Perempuan', "Wanita Sahaja"): return False, audit
    if req.get('no_colorblind') == 1:
        if not check("Bebas Buta Warna", student.colorblind == 'Tidak', "Tidak boleh rabun warna"): return False, audit
    if req.get('no_disability') == 1:
        if not check("Sihat Tubuh Badan", student.disability == 'Tidak', "Syarat fizikal tidak dipenuhi"): return False, audit

    g = student.grades

    # --- TVET SPECIAL: 3M ONLY ---
    # Definition: Course only requires BM and Math to be ATTEMPTED (any grade incl. G).
    # This overrides all other academic requirements.

    if req.get('3m_only') == 1:
        cond = is_attempted(g.get('bm')) and is_attempted(g.get('math'))
        audit.append({
        "label": "Syarat 3M",
        "passed": cond,
        "reason": None if cond else "Perlu sekurang-kurangnya Gred G dalam BM dan Matematik"
        })
        return cond, audit

    # ACADEMIC CHECKS
    passed_academics = True

    if req.get('pass_bm') == 1:
        if not check("Lulus BM", is_pass(g.get('bm')), "Gagal Bahasa Melayu"): passed_academics = False
    if req.get('credit_bm') == 1:
        if not check("Kredit BM", is_credit(g.get('bm')), "Tiada Kredit Bahasa Melayu"): passed_academics = False
    if req.get('pass_history') == 1:
        if not check("Lulus Sejarah", is_pass(g.get('hist')), "Gagal Sejarah"): passed_academics = False
    if req.get('pass_eng') == 1:
        if not check("Lulus BI", is_pass(g.get('eng')), "Gagal Bahasa Inggeris"): passed_academics = False
    if req.get('credit_english') == 1:
        if not check("Kredit BI", is_credit(g.get('eng')), "Tiada Kredit Bahasa Inggeris"): passed_academics = False

    # Logic: Passing Add Math satisfies the "Math" requirement.
    if req.get('pass_math') == 1:
        # Check Modern Math ONLY (Poly Policy)
        if not check("Lulus Matematik", is_pass(g.get('math')), "Gagal Matematik"): passed_academics = False

    if req.get('pass_math_addmath') == 1:
        # Check Modern Math OR Add Math (TVET Policy)
        cond = is_pass(g.get('math')) or is_pass(g.get('addmath'))
        if not check("Lulus Matematik/AddMath", cond, "Gagal Matematik & Add Math"): passed_academics = False

    if req.get('credit_math') == 1:
        # Check Credit in Modern Math OR Add Math
        cond = is_credit(g.get('math')) or is_credit(g.get('addmath'))
        if not check("Kredit Matematik", cond, "Tiada Kredit Matematik atau Add Math"): passed_academics = False

    # Group Logic
    pure_sci = [g.get('phy'), g.get('chem'), g.get('bio')]
    all_sci = pure_sci + [g.get('sci')]
    
    # TVET Special: Science excluding Biology (Phys, Chem, General Sci)
    sci_no_bio = [g.get('phy'), g.get('chem'), g.get('sci')]

    # Tech/Voc logic: Checks the generic 'tech' and 'voc' inputs
    # We no longer hardcode specific subjects like RC/CS/Agro/SRT 
    # because the UI allows generic selection.
    
    def has_pass(grade_list): return any(is_pass(x) for x in grade_list)
    def has_credit(grade_list): return any(is_credit(x) for x in grade_list)
    
    # --- TVET Rules (ILKBS/ILJTM) ---

    if req.get('pass_math_science') == 1:
        # Pass Math OR Science (Excluding Biology)
        cond = is_pass(g.get('math')) or has_pass(sci_no_bio)
        if not check("Lulus Matemaik ATAU Sains (No Bio)", cond, "Perlu Lulus Math/Sains (Tiada Bio)"): passed_academics = False
        
    if req.get('pass_science_tech') == 1:
        # Pass Science (Excluding Bio) OR Technical Subject
        cond = has_pass(sci_no_bio) or is_pass(g.get('tech'))
        if not check("Lulus Sains (No Bio) ATAU Teknikal", cond, "Perlu Lulus Sains (Tiada Bio)/Teknikal"): passed_academics = False
        
    if req.get('credit_math_sci') == 1:
        # Normal TVET: Credit Math OR Science (Any)
        # Note: Policy doc said "Credit in Math OR any Science subject". 
        # Typically TVET is strict on Bio, but the doc said "any Science". 
        # Leaving as 'all_sci' unless specified otherwise.
        cond = is_credit(g.get('math')) or has_credit(all_sci)
        if not check("Kredit Matematik ATAU Sains", cond, "Perlu Kredit Math/Sains"): passed_academics = False
        
    if req.get('credit_math_sci_tech') == 1:
        cond = is_credit(g.get('math')) or has_credit(all_sci) or is_credit(g.get('tech'))
        if not check("Kredit Math/Sains/Teknikal", cond, "Perlu Kredit Math/Sains/Teknikal"): passed_academics = False

    # --- Poly/KK Rules ---
    
    # NEW: Credit BM or English
    if req.get('credit_bmbi') == 1:
        cond = is_credit(g.get('bm')) or is_credit(g.get('eng'))
        if not check("Kredit BM ATAU BI", cond, "Perlu Kredit BM atau BI"): passed_academics = False

    # NEW: Credit Science/Technical/Vocational
    if req.get('credit_stv') == 1:
        # All Science (Inc Bio) OR Tech OR Voc
        cond = has_credit(all_sci) or is_credit(g.get('tech')) or is_credit(g.get('voc'))
        if not check("Kredit Sains/Vokasional", cond, "Perlu Kredit Sains/Vokasional"): passed_academics = False

    if req.get('pass_stv') == 1:
        # Pass Science (Inc Bio) OR Tech OR Voc
        cond = has_pass(all_sci) or is_pass(g.get('tech')) or is_pass(g.get('voc'))
        if not check("Aliran Sains/Vokasional", cond, "Perlu Lulus Sains/Vokasional"): passed_academics = False

    # Specific Science/Math Groupings
    if req.get('credit_sf') == 1:
        # Credit in Science (General) OR Physics
        cond = is_credit(g.get('sci')) or is_credit(g.get('phy'))
        if not check("Kredit Sains/Fizik", cond, "Perlu Kredit Sains atau Fizik"): passed_academics = False

    if req.get('credit_sfmt') == 1:
        # Credit in Science (General) OR Physics OR Add Math
        cond = is_credit(g.get('sci')) or is_credit(g.get('phy')) or is_credit(g.get('addmath'))
        if not check("Kredit Sains/Fizik/Add Math", cond, "Perlu Kredit Sains/Fizik/Add Math"): passed_academics = False

    min_c = req.get('min_credits', 0)
    if min_c > 0:
        if not check(f"Minimum {min_c} Kredit", student.credits >= min_c, f"Hanya {student.credits} Kredit (Perlu {min_c})"): passed_academics = False

    min_p = req.get('min_pass', 0)
    if min_p > 0:
        if not check(f"Minimum {min_p} Lulus", student.passes >= min_p, f"Hanya {student.passes} Lulus"): passed_academics = False

    return passed_academics, audit