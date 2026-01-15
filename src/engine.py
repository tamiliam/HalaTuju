import pandas as pd
import numpy as np

# --- 1. DATA SANITIZER (The Bouncer) ---
def load_and_clean_data(filepath):
    """
    Loads CSV and enforces strict integer types for flag columns.
    Converts '1.0', 'Yes', 'True' -> 1
    Converts '0', 'No', 'False', NaN -> 0
    """
    df = pd.read_csv(filepath)
    
    # List of columns that MUST be integers (0 or 1)
    flag_columns = [
        'req_malaysian', 'req_male', 'req_female', 'no_colorblind', 'no_disability',
        '3m_only', 'pass_bm', 'credit_bm', 'pass_history', 
        'pass_eng', 'credit_english', 'pass_math', 'credit_math',
        'pass_math_sci', 'pass_science_tech', 'credit_math_sci',
        'credit_math_sci_tech', 'pass_stv'
    ]
    
    for col in flag_columns:
        if col in df.columns:
            # Force numeric, turning errors (like 'Yes') into NaN
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    # Handle 'min_credits' and 'min_pass' separately (they are counts, not flags)
    for col in ['min_credits', 'min_pass']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
    return df

# --- 2. HELPER FUNCTIONS ---
def is_pass(grade):
    """Returns True if grade is A+ through E (Pass)."""
    if grade in ["Tidak Ambil", None, "", "nan"]: return False
    return grade in ["A+", "A", "A-", "B+", "B", "C+", "C", "D", "E"]

def is_credit(grade):
    """Returns True if grade is A+ through C (Credit)."""
    if grade in ["Tidak Ambil", None, "", "nan"]: return False
    return grade in ["A+", "A", "A-", "B+", "B", "C+", "C"]

def is_attempted(grade):
    """Returns True if grade is A+ through G (Attempted)."""
    if grade in ["Tidak Ambil", None, "", "nan"]: return False
    return grade in ["A+", "A", "A-", "B+", "B", "C+", "C", "D", "E", "G"]

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

    # TVET SPECIAL (3M)
    # Notice: Clean and Simple again!
    if req.get('3m_only') == 1:
        has_bm = is_attempted(g.get('bm'))
        has_math = is_attempted(g.get('math'))
        if check("Syarat 3M (BM & Math)", has_bm and has_math, "Perlu sekurang-kurangnya Gred G dalam BM dan Matematik"):
            return True, audit
        else:
            return False, audit

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
        # Check Modern Math OR Add Math
        cond = is_pass(g.get('math')) or is_pass(g.get('addmath'))
        if not check("Lulus Matematik", cond, "Gagal Matematik & Add Math"): passed_academics = False
    if req.get('credit_math') == 1:
        # Check Credit in Modern Math OR Add Math
        cond = is_credit(g.get('math')) or is_credit(g.get('addmath'))
        if not check("Kredit Matematik", cond, "Tiada Kredit Matematik atau Add Math"): passed_academics = False

    # Group Logic
    pure_sci = [g.get('phy'), g.get('chem'), g.get('bio')]
    all_sci = pure_sci + [g.get('sci')]
    tech_subjs = [g.get('rc'), g.get('cs'), g.get('agro'), g.get('srt')]
    if student.other_tech: tech_subjs.append('C')

    def has_pass(grade_list): return any(is_pass(x) for x in grade_list)
    def has_credit(grade_list): return any(is_credit(x) for x in grade_list)

    if req.get('pass_math_sci') == 1:
        cond = is_pass(g.get('math')) or has_pass(pure_sci)
        if not check("Lulus Matemaik ATAU Sains Tulen", cond, "Perlu Lulus Math/Sains Tulen"): passed_academics = False
    if req.get('pass_science_tech') == 1:
        cond = has_pass(all_sci) or has_pass(tech_subjs)
        if not check("Lulus Sains ATAU Teknikal", cond, "Perlu Lulus Sains/Teknikal"): passed_academics = False
    if req.get('credit_math_sci') == 1:
        cond = is_credit(g.get('math')) or has_credit(pure_sci)
        if not check("Kredit Matematik ATAU Sains Tulen", cond, "Perlu Kredit Math/Sains Tulen"): passed_academics = False
    if req.get('credit_math_sci_tech') == 1:
        cond = is_credit(g.get('math')) or has_credit(all_sci) or has_credit(tech_subjs)
        if not check("Kredit Math/Sains/Teknikal", cond, "Perlu Kredit Math/Sains/Teknikal"): passed_academics = False
    if req.get('pass_stv') == 1:
        cond = has_pass(all_sci) or has_pass(tech_subjs) or student.other_voc
        if not check("Aliran Sains/Vokasional", cond, "Perlu Lulus Sains/Vokasional"): passed_academics = False

    min_c = req.get('min_credits', 0)
    if min_c > 0:
        if not check(f"Minimum {min_c} Kredit", student.credits >= min_c, f"Hanya {student.credits} Kredit (Perlu {min_c})"): passed_academics = False

    min_p = req.get('min_pass', 0)
    if min_p > 0:
        if not check(f"Minimum {min_p} Lulus", student.passes >= min_p, f"Hanya {student.passes} Lulus"): passed_academics = False

    return passed_academics, audit