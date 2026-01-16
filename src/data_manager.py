import pandas as pd
import os
from src.engine import load_and_clean_data

def load_master_data():
    """
    Loads and merges all CSVs into a single 'Enriched' DataFrame.
    Returns: df_offerings (One row per Course-Location pair)
    """
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_folder = os.path.join(base_path, 'data')

    # --- 1. LOAD RAW FILES ---
    # Helper to load CSV safely
    def load(filename):
        path = os.path.join(data_folder, filename)
        if os.path.exists(path):
            return load_and_clean_data(path)
        return pd.DataFrame()

    # Poly Files
    df_req = load('requirements.csv')
    df_links = load('links.csv')
    df_inst = load('institutions.csv')
    df_courses = load('courses.csv')

    # TVET Files
    df_tvet_req = load('tvet_requirements.csv')
    df_tvet_inst = load('tvet_institutions.csv')
    df_tvet_courses = load('tvet_courses.csv')

    # --- 2. MERGE POLYTECHNIC DATA ---
    # Logic: Req (Eligibility) -> Links (Where offered) -> Inst (Location) -> Course (Names)
    if not df_req.empty and not df_links.empty:
        # Merge Links to get Institution IDs for each course
        poly_merged = pd.merge(df_req, df_links, on='course_id', how='left')
        
        # Merge Institution Details (Name, State)
        poly_merged = pd.merge(poly_merged, df_inst, on='institution_id', how='left')
        
        # Merge Course Details (Name, Duration)
        poly_merged = pd.merge(poly_merged, df_courses, on='course_id', how='left')
        
        # Standardize Columns
        poly_merged['type'] = poly_merged['type'].fillna('Politeknik')
        poly_merged['fees'] = "RM 200 - RM 600 / sem (Subsidized)" # Placeholder as Poly fees are standard
        poly_merged['duration'] = poly_merged['semesters'].astype(str) + " Semesters"
        
        # Select final columns
        poly_final = poly_merged
    else:
        poly_final = pd.DataFrame()

    # --- 3. MERGE TVET DATA ---
    # Logic: TVET Req already has Inst ID and Course ID
    if not df_tvet_req.empty:
        tvet_merged = df_tvet_req.copy()
        
        # Merge Inst Details
        tvet_merged = pd.merge(tvet_merged, df_tvet_inst, on='institution_id', how='left')
        
        # Merge Course Details
        tvet_merged = pd.merge(tvet_merged, df_tvet_courses, on='course_id', how='left')
        
        # Standardize Columns
        tvet_merged['type'] = tvet_merged['type'].fillna('TVET')
        tvet_merged['fees'] = tvet_merged['tuition_fee'] # From CSV
        tvet_merged['course'] = tvet_merged['course_x'] # Handle merge collision if any
        
        # Select final columns
        tvet_final = tvet_merged
    else:
        tvet_final = pd.DataFrame()

    # --- 4. COMBINE & CLEAN ---
    # We unite them into one big table
    cols_to_keep = [
        'course_id', 'course', 'institution_name', 'State', 
        'type', 'category', 'fees', 'duration', 'hyperlink',
        # Keep the requirements columns for the Engine to check!
        'min_credits', 'req_malaysian', 'pass_bm', 'pass_history', 'pass_eng', 
        'pass_math', 'pass_science_tech', 'credit_math', 'credit_bm', 'credit_eng'
    ]
    
    # Align columns (fill missing with NaN)
    master_df = pd.concat([poly_final, tvet_final], ignore_index=True)
    
    # Ensure all crucial columns exist
    for col in cols_to_keep:
        if col not in master_df.columns:
            master_df[col] = None
            
    # Rename for consistency
    master_df = master_df.rename(columns={
        'course': 'course_name',
        'State': 'state'
    })

    return master_df