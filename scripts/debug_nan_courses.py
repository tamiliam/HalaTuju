
import sys
import os
import pandas as pd

# Add the project root to sys.path so we can import from src
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from src.data_manager import load_master_data

def debug():
    # 1. Load data using the actual manager
    print("Loading Master Data...")
    df = load_master_data()
    
    # 2. Check for NaNs
    col_name = 'course_name' if 'course_name' in df.columns else 'course'
    
    nan_courses = df[df[col_name].isna() | (df[col_name].astype(str).str.lower() == 'nan')]
    
    print(f"\nTotal rows: {len(df)}")
    print(f"Rows with NaN/Null {col_name}: {len(nan_courses)}")
    
    if not nan_courses.empty:
        print("\nSample of problematic rows:")
        print(nan_courses[['course_id', 'institution_name', 'state', 'type']].head())
        
        # Check specific example if possible (from screenshot: Politeknik Nilai, Landscape?)
        # Let's try to match by partial string if course name is missing
        # We can look at 'jobs' or 'notes' if they exist?
        pass

    # 3. Check underlying files directly to isolate source
    data_dir = os.path.join(project_root, 'data')
    
    print("\n--- Checking Source Files ---")
    
    # Requirements
    req_path = os.path.join(data_dir, 'requirements.csv')
    try:
        df_req = pd.read_csv(req_path, encoding='cp1252')
        print(f"requirements.csv: {len(df_req)} rows")
        if 'course' in df_req.columns:
            print(f"  Null 'course' in req: {df_req['course'].isna().sum()}")
        else:
            print("  'course' column MISSING in requirements.csv")
    except Exception as e:
        print(f"Error reading requirements.csv: {e}")

    # Courses
    course_path = os.path.join(data_dir, 'courses.csv')
    try:
        df_c = pd.read_csv(course_path, encoding='cp1252')
        print(f"courses.csv: {len(df_c)} rows")
        if 'course_name' in df_c.columns:
            print(f"  Null 'course_name' in courses: {df_c['course_name'].isna().sum()}")
        elif 'course' in df_c.columns:
            print(f"  Null 'course' in courses: {df_c['course'].isna().sum()}")
        else:
             print("  'course'/'course_name' column MISSING in courses.csv")
             print(f"  Columns: {df_c.columns.tolist()}")
    except Exception as e:
        print(f"Error reading courses.csv: {e}")

if __name__ == "__main__":
    debug()
