
import pandas as pd
import re
import os

# --- MAPPING CONFIGURATION ---
GENERIC_IT_MAP = {
    'SOURCE_CODE': 'FB4482001', # Diploma Teknologi Maklumat
    'TARGET_IDS': [
        'POLY-DIP-072', 'POLY-DIP-073', 'POLY-DIP-074', 
        'POLY-DIP-075', 'POLY-DIP-076', 'POLY-DIP-077'
    ]
}

KK_MANUAL_MAP = {
    'KKOM-CET-002': 'FC3811006', # Certificate in F&B
    'KKOM-CET-022': 'FC3215001'  # Sijil Seni Visual
}

def normalize_name(name):
    if not isinstance(name, str):
        return ""
    name = name.upper().strip()
    name = re.sub(r'[#*]', '', name).strip()
    name = name.replace('REKABENTUK', 'REKA BENTUK')
    return name

def read_csv_safe(path):
    for enc in ['utf-8', 'cp1252', 'latin1']:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    print(f"Failed to read {path}")
    return pd.DataFrame()

def process_data():
    base_path = 'c:/Users/tamil/Python'
    mohe_path = os.path.join(base_path, 'Random/archive/spm/intermediate/mohe_programs_with_kampus.csv')
    ht_req_path = os.path.join(base_path, 'HalaTuju/data/requirements.csv')
    ht_courses_path = os.path.join(base_path, 'HalaTuju/data/courses.csv')
    output_path = os.path.join(base_path, 'HalaTuju/data/merit_cutoffs.csv')

    print("Loading data...")
    df_mohe = read_csv_safe(mohe_path)
    df_req = read_csv_safe(ht_req_path)
    df_courses = read_csv_safe(ht_courses_path) # Need names for mapping

    # 1. Clean MOHE Data
    # Extract Merit
    df_mohe['merit_score'] = pd.to_numeric(df_mohe['merit'].astype(str).str.replace('%','', regex=False), errors='coerce')
    df_mohe['norm_name'] = df_mohe['program_name'].apply(normalize_name)
    df_mohe['code'] = df_mohe['code'].astype(str).str.strip()
    
    # Create lookup dicts
    # Code -> Merit
    code_merit_map = df_mohe.set_index('code')['merit_score'].to_dict()
    # NormName -> Merit (Avg if multiple? Usually unique per program name if we ignore campus)
    # MOHE file has multiple rows per program (campus). We want the AVG or MIN?
    # Usually merit is per program-campus. But for general eligibility, maybe AVG?
    # Wait, the user said "mohe_programs_with_khas" has "merit".
    # Let's check if merit varies by campus for same code.
    # Group by code and take MEAN.
    merit_by_code = df_mohe.groupby('code')['merit_score'].mean().to_dict()
    
    # Group by NormName and take MEAN (for Poly fuzzy match)
    merit_by_name = df_mohe.groupby('norm_name')['merit_score'].mean().to_dict()

    print(f"Loaded {len(merit_by_code)} generic merit codes.")

    # 2. Map HalaTuju Courses
    results = []

    # Get all HT courses (Req + Courses)
    # We iterate through requirements because that's our master list for the engine
    # But wait, UA courses aren't in requirements.csv yet.
    # So we process:
    # A. Existing Poly/KK in requirements.csv
    # B. New UA courses from MOHE (to be added)
    
    # --- PART A: POLY & KK ---
    print("Processing Poly/KK...")
    
    # Merge req with names
    df_poly_kk = df_req[df_req['course_id'].str.contains('POLY|KKOM')].copy()
    df_poly_kk = df_poly_kk.merge(df_courses[['course_id', 'course']], on='course_id', how='left')
    
    for _, row in df_poly_kk.iterrows():
        cid = row['course_id']
        cname = row['course']
        norm_cname = normalize_name(cname)
        merit = 0.0
        
        # 1. Manual Map
        if cid in KK_MANUAL_MAP:
            target_code = KK_MANUAL_MAP[cid]
            merit = merit_by_code.get(target_code, 0.0)
            
        # 2. Generic IT Map
        elif cid in GENERIC_IT_MAP['TARGET_IDS']:
            target_code = GENERIC_IT_MAP['SOURCE_CODE']
            merit = merit_by_code.get(target_code, 0.0)
            
        # 3. Direct/Fuzzy Name Match
        else:
            merit = merit_by_name.get(norm_cname, 0.0)
            
        if merit > 0:
            results.append({'course_id': cid, 'merit_cutoff': round(merit, 2), 'type': 'POLY_KK'})
            
    # --- PART B: UA (University) Generation ---
    print("\nProcessing UA Requirements...")
    
    # Filter UA
    ua_df = df_mohe[df_mohe['code'].str.startswith('U')].copy()
    
    # We need to map MOHE columns to Requirement columns
    # mohe columns (inferred from previous view): code, program_name, university, requirement, etc?
    # Actually need to check MOHE columns first. Assuming standard names from previous views.
    # We will generate a DF compatible with requirements.csv
    
    # Define Default Columns
    new_rows = []
    
    for _, row in ua_df.iterrows():
        code = row['code']
        # Lookup Merit
        merit = merit_by_code.get(code, 0.0)
        
        # Parse Requirements (Placeholders for now, or basic mapping)
        # Assuming we need to fill: requirements columns like credit_bm, pass_history etc.
        # Since parsing text requirements is complex (Task 5), we will set defaults for now
        # and create the file structure.
        
        entry = {
            'type': 'UA',
            'course_id': code,
            'merit_cutoff': round(merit, 2),
            # Defaults for UA (Standard Syarat Am usually)
            'min_credits': 5, # Usually 5 credits including BM
            'pass_history': 1,
            'pass_bm': 1, # Actually Credit BM usually
            'credit_bm': 1,
            'pass_eng': 0, # Varies
            'credit_english': 0,
            'credit_math': 0,
            'credit_science': 0,
            'req_malaysian': 1,
            'age_limit': 100, # None
            'subject_group_req': '[]', # Complex parsing later
            'notes': row['program_name'] + " | " + str(row['university'])
        }
        
        new_rows.append(entry)
        
    ua_req_df = pd.DataFrame(new_rows)
    print(f"Generated {len(ua_req_df)} UA Requirement rows.")
    
    # Save UA File
    ua_out_path = os.path.join(base_path, 'HalaTuju/data/university_requirements.csv')
    ua_req_df.to_csv(ua_out_path, index=False)
    print(f"Saved UA Requirements to {ua_out_path}")
    
    # Also need to add to courses.csv (ID -> Name)
    # We should generate a partial courses.csv update
    ua_courses_df = ua_df[['code', 'program_name']].rename(columns={'code': 'course_id', 'program_name': 'course'})
    ua_courses_df['wbl'] = 0
    ua_courses_df['industry_demand'] = 0
    ua_courses_df['salary_range'] = ''
    ua_courses_out_path = os.path.join(base_path, 'HalaTuju/data/university_courses_update.csv')
    ua_courses_df.to_csv(ua_courses_out_path, index=False)
    print(f"Saved UA Courses Update to {ua_courses_out_path}")

    # 3. Save Output (Merit)
    result_df = pd.DataFrame(results)
    print(f"Generated {len(result_df)} merit entries.")
    
    # Analyze coverage
    poly_res = result_df[result_df['type'] == 'POLY_KK']
    print(f"Mapped Poly/KK: {len(poly_res)} / {len(df_poly_kk)}")
    
    result_df.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    process_data()
