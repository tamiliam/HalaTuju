import pandas as pd
import os
import streamlit as st
from src.engine import load_and_clean_data

@st.cache_data(ttl=3600)
def load_master_data():
    """
    Loads and merges all data files into a single master dataframe.
    """
    # 1. SETUP PATHS
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, 'data')

    def load(filename, clean=False):
        p = os.path.join(data_dir, filename)
        if os.path.exists(p):
            if clean:
                return load_and_clean_data(p)
            else:
                for enc in ['utf-8', 'cp1252', 'latin1']:
                    try:
                        # Revert to standard engine (C-based) which aligns with v1.0 behavior
                        return pd.read_csv(p, encoding=enc)
                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        print(f"Warning: Failed to load {filename} with {enc}: {e}")
                        continue
        return pd.DataFrame()

    # Load Base Logic Files (Sanitized)
    df_req = load('requirements.csv', clean=True)
    df_tvet_req = load('tvet_requirements.csv', clean=True)

    # Load Metadata Files (Raw)
    df_links = load('links.csv')
    df_inst = load('institutions.csv')  # Now includes Poly/KK/TVET/UA institutions
    df_courses = load('courses.csv')

    # df_tvet_inst removed - now in institutions.csv
    df_tvet_courses = load('tvet_courses.csv')

    # NEW: Load Details
    df_details = load('details.csv')

    # NOTE: merit_cutoffs.csv is no longer loaded separately.
    # Merit data is already in requirements.csv (merit_cutoff column).

    # Merge Details back into Logic Files
    if not df_details.empty:
        try:
            # 1. Merge Poly (Source: 'poly') - ON course_id only (Poly reqs are per-program)
            if not df_req.empty:
                poly_details = df_details[df_details['source_type'] == 'poly'].copy()
                # Drop source_type column before merge to avoid pollution
                poly_details = poly_details.drop(columns=['source_type', 'institution_id'], errors='ignore')
                
                # Check if columns overlap
                cols_to_use = list(poly_details.columns)
                if 'course_id' not in cols_to_use:
                     print("WARNING: details.csv missing course_id")
                else:
                    df_req = pd.merge(df_req, poly_details, on='course_id', how='left', suffixes=('', '_details'))
                    # Clean up _details suffixes if any collision
        
            # 2. Merge TVET (Source: 'tvet')
            if not df_tvet_req.empty:
                tvet_details = df_details[df_details['source_type'] == 'tvet'].copy()
                tvet_details = tvet_details.drop(columns=['source_type'], errors='ignore')
                
                merge_keys = ['course_id']
                if 'institution_id' in df_tvet_req.columns and 'institution_id' in tvet_details.columns:
                    merge_keys.append('institution_id')
                    
                df_tvet_req = pd.merge(df_tvet_req, tvet_details, on=merge_keys, how='left', suffixes=('', '_details'))
        except Exception as e:
            print(f"Error merging details.csv: {e}")


    # --- 2. MERGE POLYTECHNIC DATA ---
    if not df_req.empty and not df_links.empty:
        # Merge Links to get Institution IDs for each course
        poly_merged = pd.merge(df_req, df_links, on='course_id', how='left')
        
    # Merge Institution Details (Name, State, URL)
        poly_merged = pd.merge(poly_merged, df_inst, on='institution_id', how='left')
        
        # Merge Course Details (Name, Duration, Hostel)
        poly_merged = pd.merge(poly_merged, df_courses, on='course_id', how='left')
        
        # Standardize Columns
        poly_merged['type'] = poly_merged['type'].fillna('Politeknik')
        
        # Fees & Hostel (Prefer details.csv, fallback to defaults)
        if 'tuition_fee_semester' in poly_merged.columns:
             poly_merged['fees'] = poly_merged['tuition_fee_semester'].fillna("RM 200/sem (Subsidized)")
        else:
             poly_merged['fees'] = "RM 200/sem (Subsidized)"

        if 'hostel_fee_semester' in poly_merged.columns:
             poly_merged['hostel_fee'] = poly_merged['hostel_fee_semester'].fillna("RM 60/sem")
        else:
             poly_merged['hostel_fee'] = "RM 60/sem"

        if 'hyperlink' in poly_merged.columns:
            poly_merged['details_url'] = poly_merged['hyperlink'].fillna('#')
        else:
            poly_merged['details_url'] = '#'

        # Duration
        if 'semesters' in poly_merged.columns:
            poly_merged['duration'] = poly_merged['semesters'].astype(str) + " Semesters"
        else:
            poly_merged['duration'] = "N/A"
        
        # Rename URL if exists
        if 'url' in poly_merged.columns:
            poly_merged['inst_url'] = poly_merged['url']
        else:
            poly_merged['inst_url'] = "https://ambilan.mypolycc.edu.my"

        # Fix Course Name Collision (course mixed with details causes _x, _y)
        # Priority: course_y (from courses.csv) > course_x (from details/req) > course
        if 'course_y' in poly_merged.columns:
            poly_merged['course'] = poly_merged['course_y'].fillna(poly_merged.get('course_x', poly_merged.get('course', '')))
        elif 'course_x' in poly_merged.columns:
            poly_merged['course'] = poly_merged['course_x']

        # Fallback if still empty/NaN
        if 'course' not in poly_merged.columns:
             poly_merged['course'] = poly_merged['course_id'] # Last resort

        # NOTE: Merit cutoffs are already in requirements.csv (merit_cutoff column).
        # Removed redundant merge with df_merit to avoid column collision
        # (merit_cutoff_x, merit_cutoff_y). See merit_integration_plan.md.

        poly_final = poly_merged
    else:
        poly_final = pd.DataFrame()

    # --- 3. MERGE TVET DATA ---
    if not df_tvet_req.empty:
        tvet_merged = df_tvet_req.copy()

        # Merge Inst Details (from unified institutions.csv)
        tvet_merged = pd.merge(tvet_merged, df_inst, on='institution_id', how='left')
        
        # Merge Course Details
        tvet_merged = pd.merge(tvet_merged, df_tvet_courses, on='course_id', how='left')
        
        # Standardize Columns
        tvet_merged['type'] = tvet_merged['type'].fillna('TVET')
        
        # Map Duration (TVET uses 'months')
        if 'months' in tvet_merged.columns:
             # Ensure string and append " Months" if it's a number
             tvet_merged['duration'] = tvet_merged['months'].astype(str) + " Months"
        
        # Map Fees (Priority: details > tvet_courses > default)
        if 'tuition_fee_semester' in tvet_merged.columns:
            tvet_merged['fees'] = tvet_merged['tuition_fee_semester']
        elif 'tuition_fee' in tvet_merged.columns:
            tvet_merged['fees'] = tvet_merged['tuition_fee']
        else:
            tvet_merged['fees'] = "Free / Subsidized"

        # Map Hostel (Priority: details.hostel_fee_semester > tvet_courses.hostel_fee > N/A)
        if 'hostel_fee_semester' in tvet_merged.columns:
             tvet_merged['hostel_fee'] = tvet_merged['hostel_fee_semester']
        elif 'hostel_fee' in tvet_merged.columns:
            tvet_merged['hostel_fee'] = tvet_merged['hostel_fee']
        else:
            tvet_merged['hostel_fee'] = "N/A"

        # Map Inst URL
        if 'url' in tvet_merged.columns:
            tvet_merged['inst_url'] = tvet_merged['url']
        else:
            tvet_merged['inst_url'] = "#"
            
        # Map Details URL (TVET)
        if 'hyperlink' in tvet_merged.columns:
            tvet_merged['details_url'] = tvet_merged['hyperlink'].fillna('#')
        else:
            tvet_merged['details_url'] = '#'
            
        # --- THE FIX IS HERE ---
        # We REMOVED the line: tvet_merged['course'] = tvet_merged['course_x']
        # Instead, we check if we need to rename or fill anything.
        if 'course_x' in tvet_merged.columns:
            tvet_merged['course'] = tvet_merged['course_x'].fillna(tvet_merged.get('course_y', 'Unknown'))
        
        # Select final columns
        tvet_final = tvet_merged
    else:
        tvet_final = pd.DataFrame()

    # --- 3b. MERGE NEW PATHWAYS (PISMP, STPM, etc.) ---
    # DISABLED: Not ready for production yet. Only Poly/KK/TVET are active.
    # See implementation_plan.md and pismp_stpm_integration_plan.md for future integration.
    pathways_final = pd.DataFrame()

    # --- 3c. MERGE PUBLIC UNIVERSITY (UA) DATA ---
    # Load UA requirements from parsed MOHE data
    df_ua_req = load('university_requirements.csv', clean=True)
    # df_ua_courses removed - now merged into unified courses.csv

    if not df_ua_req.empty and not df_links.empty:
        # Follow same pattern as Poly/KK: links.csv → institutions.csv → courses.csv
        # Merge Links to get Institution IDs for each course
        ua_merged = pd.merge(df_ua_req, df_links, on='course_id', how='left')

        # Merge Institution Details (Name, State, URL)
        ua_merged = pd.merge(ua_merged, df_inst, on='institution_id', how='left')

        # Merge Course Details (Name, Duration, etc.)
        ua_merged = pd.merge(ua_merged, df_courses, on='course_id', how='left')

        # Handle column name conflicts (course_x, course_y from merges)
        if 'course_y' in ua_merged.columns:
            # Prefer course_y (from courses.csv)
            ua_merged['course'] = ua_merged['course_y'].fillna(ua_merged.get('course_x', ''))
        elif 'course_x' in ua_merged.columns:
            ua_merged['course'] = ua_merged['course_x']
        # else: 'course' column already exists from merge

        # Set type and category based on level column
        # Use consistent type naming (Bahasa Melayu) for filter compatibility
        ua_merged['type'] = ua_merged['type'].fillna('Universiti Awam')
        if 'level' in ua_merged.columns:
            ua_merged['category'] = ua_merged['level'].fillna('Asasi / Foundation')
        else:
            ua_merged['category'] = 'Asasi / Foundation'

        # Map fees and duration
        ua_merged['fees'] = 'Contact Institution'

        if 'semesters' in ua_merged.columns:
            ua_merged['duration'] = ua_merged['semesters'].astype(str) + " Semesters"
        else:
            ua_merged['duration'] = '1-2 Semesters'

        # Map URLs
        if 'url' in ua_merged.columns:
            ua_merged['inst_url'] = ua_merged['url'].fillna('#')
        else:
            ua_merged['inst_url'] = '#'

        ua_merged['details_url'] = '#'
        ua_merged['hyperlink'] = '#'

        ua_final = ua_merged
    else:
        ua_final = pd.DataFrame()

    # --- 4. COMBINE & CLEAN ---
    # Define explicitly all cols we need. Add more if engine needs them.
    from src.engine import ALL_REQ_COLUMNS
    
    # Base metadata columns
    base_cols = [
        'course_id', 'course', 'institution_name', 'State', 
        'type', 'category', 'fees', 'duration', 'hyperlink',
        'inst_url', 'hostel_fee', 'details_url', 'level', 'merit_cutoff'
    ]
    
    # Combine lists
    cols_to_keep = base_cols + ALL_REQ_COLUMNS
    
    master_df = pd.concat([poly_final, tvet_final, pathways_final, ua_final], ignore_index=True)
    
    # Final Safety: Fill N/A details_url with '#'
    if 'details_url' in master_df.columns:
        master_df['details_url'] = master_df['details_url'].fillna('#')
    
    # Ensure all crucial columns exist
    for col in cols_to_keep:
        if col not in master_df.columns:
            master_df[col] = 0 if col in ALL_REQ_COLUMNS else None
            
    # Rename for consistency
    # First, drop any existing 'course_name' column to avoid duplicates
    if 'course_name' in master_df.columns and 'course' in master_df.columns:
        # Use 'course' as the canonical source, drop old 'course_name'
        master_df = master_df.drop(columns=['course_name'])

    master_df = master_df.rename(columns={
        'course': 'course_name',
        'State': 'state'
    })

    return master_df