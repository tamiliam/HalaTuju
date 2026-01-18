
import pandas as pd
import os

REQ_PATH = "data/requirements.csv"
TVET_PATH = "data/tvet_requirements.csv"
NEW_REQ_PATH = "data/requirements_clean.csv"
NEW_TVET_PATH = "data/tvet_requirements_clean.csv"
DETAILS_CLEAN_PATH = "data/details_clean.csv"

# 1. Define Logic Columns (TO KEEP in Logic Files)
# Keys + Logic Flags/Counts
LOGIC_COLS_WHITELIST = [
    # Keys
    "course_id", "institution_id", 
    
    # Requirements
    "min_credits", "min_pass", "3m_only",
    
    # Identity
    "req_malaysian", "req_male", "req_female", "no_colorblind", "no_disability","req_academic", "medical_restrictions",
    
    # Specific Subjects
    "pass_bm", "pass_history", "pass_eng", "pass_math", "pass_math_or_addmath", "pass_science_tech", "pass_math_sci",
    "credit_bm", "credit_english", "credit_eng", "credit_math", 
    "credit_math_sci", "credit_math_sci_tech",
    "pass_stv", "credit_stv", "credit_sf", "credit_sfmt", "credit_bmbi"
    
    # Any other logic columns will need to be added here if missed, 
    # but based on audit, this covers the engine.py usage.
]

# 2. Logic to process a file
def process_file(path, source_type, rename_map=None):
    if not os.path.exists(path):
        print(f"Skipping {path}, not found.")
        return None, None
        
    df = pd.read_csv(path)
    
    # Rename Columns (Normalization)
    if rename_map:
        df = df.rename(columns=rename_map)
    
    # Separate Logic vs Details
    
    # Identify Logic Columns present in this file
    logic_cols = [c for c in df.columns if c in LOGIC_COLS_WHITELIST]
    # Identify Detail Columns (Everything else)
    # We MUST keep keys in details too for joining!
    # Primary Key for Poly: course_id
    # Primary Key for TVET: course_id + institution_id (or some combo).
    # To be safe, we keep course_id and institution_id in BOTH.
    
    detail_cols = [c for c in df.columns if c not in LOGIC_COLS_WHITELIST]
    # Ensure keys are in details
    if "course_id" not in detail_cols and "course_id" in df.columns: detail_cols.insert(0, "course_id")
    if "institution_id" not in detail_cols and "institution_id" in df.columns: detail_cols.insert(1, "institution_id")
    
    df_logic = df[logic_cols].copy()
    df_details = df[detail_cols].copy()
    
    # Add source type to details to help with debugging/merging if needed
    df_details['source_type'] = source_type
    
    return df_logic, df_details

# 3. Main Execution
print("Processing Requirements...")
# Poly Renames: Normalize credit_eng -> credit_english
df_req_logic, df_req_details = process_file(REQ_PATH, "poly", rename_map={"credit_eng": "credit_english"})

print("Processing TVET Requirements...")
# TVET Renames: Distinguish loose math rule
df_tvet_logic, df_tvet_details = process_file(TVET_PATH, "tvet", rename_map={"pass_math": "pass_math_or_addmath"})

# 4. Save Logic Files (Clean)
if df_req_logic is not None:
    df_req_logic.to_csv(NEW_REQ_PATH, index=False)
    print(f"Saved cleaned Poly logic to {NEW_REQ_PATH}")

if df_tvet_logic is not None:
    df_tvet_logic.to_csv(NEW_TVET_PATH, index=False)
    print(f"Saved cleaned TVET logic to {NEW_TVET_PATH}")

# 5. Merge and Save Details
# We concat them. Columns that don't exist in one will be NaN (as expected).
if df_req_details is not None and df_tvet_details is not None:
    df_details_merged = pd.concat([df_req_details, df_tvet_details], ignore_index=True)
    df_details_merged.to_csv(DETAILS_CLEAN_PATH, index=False)
    print(f"Saved merged details to {DETAILS_CLEAN_PATH}")
elif df_req_details is not None:
    df_req_details.to_csv(DETAILS_CLEAN_PATH, index=False)
elif df_tvet_details is not None:
    df_tvet_details.to_csv(DETAILS_CLEAN_PATH, index=False)

print("Refactoring Complete.")
