
import pandas as pd
from src.engine import check_eligibility, StudentProfile

# 1. Define the specific requirement row for POLY-DIP-034
# Based on my read of requirements.csv line 35:
# POLY-DIP-034,5,1,0,1,0,0,1,1,1,0,0,0,1,0,1,0,1,1
req_row = {
    'course_id': 'POLY-DIP-034',
    'min_credits': 5,
    'req_malaysian': 1,
    'pass_bm': 0,
    'pass_history': 1,
    'pass_eng': 0,
    'pass_math': 0,
    'credit_math': 1,
    'credit_bm': 1,
    'credit_english': 1,
    'pass_stv': 0,
    'credit_stv': 0,
    'credit_sf': 0,
    'credit_sfmt': 1,
    'credit_bmbi': 0,
    'req_male': 1,
    'req_female': 0,
    'no_colorblind': 1,
    'no_disability': 1
}

# 2. Define the Student
# "A in BM, English, Math, Add Math, Chemistry, History, Physics. Male"
grades = {
    'bm': 'A',
    'eng': 'A',
    'math': 'A',
    'addmath': 'A',
    'chem': 'A',
    'hist': 'A',
    'phy': 'A',
    # Missing others (should match defaults or be ignored properly)
    'sci': 'G', # Assuming stream students don't take General Science
    'bio': 'G', 
    'tech': 'G',
    'voc': 'G'
}

student = StudentProfile(
    grades=grades,
    gender='Lelaki', # Male
    nationality='Warganegara',
    colorblind='Tidak',
    disability='Tidak'
)

# 3. Run Check
is_eligible, audit = check_eligibility(student, req_row)

print(f"Eligible: {is_eligible}")
print("Audit Log:")
for item in audit:
    print(item)
