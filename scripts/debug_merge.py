
import pandas as pd
import os
import sys

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from src.engine import load_and_clean_data


from src.data_manager import load_master_data

def debug():
    print("--- Loading Files using REAL Logic ---")
    df = load_master_data()
    
    print(f"Master DF: {len(df)} rows")
    if 'course_name' in df.columns:
        print(f"NaN course_name: {df['course_name'].isna().sum()}")
        # Check Nilai
        nilai = df[df['institution_name'].astype(str).str.contains("Nilai")]
        print("Nilai Sample:")
        print(nilai[['course_id', 'course_name']].head())
    elif 'course' in df.columns:
         print(f"NaN course: {df['course'].isna().sum()}")
         
    return

    print("\n--- Step 1: Merge Details (Simulation) ---")
    if not df_details.empty:
        poly_details = df_details[df_details['source_type'] == 'poly'].copy()
        poly_details = poly_details.drop(columns=['source_type', 'institution_id'], errors='ignore')
        
        print(f"Poly Details: {len(poly_details)} rows. Cols: {poly_details.columns.tolist()}")
        
        df_req = pd.merge(df_req, poly_details, on='course_id', how='left', suffixes=('', '_details'))
        print(f"After Details Merge: {len(df_req)} rows. Cols: {df_req.columns.tolist()}")
        if 'course' in df_req.columns:
            print("  ALERT: 'course' column exists in df_req now!")

    print("\n--- Step 2: Merge Courses (The Failure Point?) ---")
    # Simulate df_req is poly_merged (skipping links/inst for brevity if irrelevant to course name)
    poly_merged = df_req.copy()
    
    poly_merged = pd.merge(poly_merged, df_courses, on='course_id', how='left')
    print(f"After Courses Merge: {len(poly_merged)} rows. Cols: {poly_merged.columns.tolist()}")
    
    print("\n--- Inspection ---")
    if 'course_x' in poly_merged.columns:
        print("  course_x found!")
        print(poly_merged['course_x'].head())
    if 'course_y' in poly_merged.columns:
        print("  course_y found!")
        print(poly_merged['course_y'].head())
    if 'course' in poly_merged.columns:
        print("  course found!")
        print(poly_merged['course'].head())

    # Check match rate
    matched = poly_merged[poly_merged['course_y'].notna()] if 'course_y' in poly_merged.columns else poly_merged[poly_merged['course'].notna()]
    print(f"Rows with valid course name from match: {len(matched)}")
    
    # Search for Nilai
    print("\n--- Searching for 'Nilai' ---")
    if 'institution_name' in poly_merged.columns:
        nilai = poly_merged[poly_merged['institution_name'].str.contains("Nilai", case=False, na=False)]
        print(f"Found {len(nilai)} rows with 'Nilai' in institution_name")
        print(nilai[['course_id', 'course'] if 'course' in nilai.columns else ['course_id']].head())
    
    print("\n--- TVET Check ---")
    df_tvet_req = load('tvet_requirements.csv', clean=True)
    df_tvet_courses = load('tvet_courses.csv')
    print(f"TVET Req: {len(df_tvet_req)} rows")
    print(f"TVET Courses: {len(df_tvet_courses)} rows")
    
    tvet_merged = pd.merge(df_tvet_req, df_tvet_courses, on='course_id', how='left')
    print(f"TVET Merged Cols: {tvet_merged.columns.tolist()}")
    
    if 'course' in tvet_merged.columns:
        print(f"TVET NaNs in 'course': {tvet_merged['course'].isna().sum()}")
    elif 'course_name' in tvet_merged.columns:
        print(f"TVET NaNs in 'course_name': {tvet_merged['course_name'].isna().sum()}")
    else:
        print("TVET has NO course column!")

if __name__ == "__main__":
    debug()
