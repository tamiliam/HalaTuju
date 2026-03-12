
import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.getcwd())

from src.data_manager import load_master_data

def debug_data():
    print("Loading Master Data...")
    df = load_master_data()
    
    print(f"Total Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    
    if 'merit_cutoff' in df.columns:
        print("\n--- Merit Cutoff Analysis ---")
        print(f"Non-zero cutoffs: {len(df[df['merit_cutoff'] > 0])}")
        
        # Check UA
        ua_courses = df[df['type'] == 'UA']
        print(f"UA Courses: {len(ua_courses)}")
        print(f"UA with Cutoff: {len(ua_courses[ua_courses['merit_cutoff'] > 0])}")
        print("Sample UA:")
        print(ua_courses[['course_id', 'course_name', 'merit_cutoff']].head())
        
        # Check IPTA (Poly/KK/TVET) - type is 'IPTA', not 'Politeknik'
        ipta_courses = df[df['type'] == 'IPTA']
        print(f"\nIPTA Courses (Poly/KK/TVET): {len(ipta_courses)}")
        print(f"IPTA with Cutoff: {len(ipta_courses[ipta_courses['merit_cutoff'] > 0])}")

        # Sample by course_id prefix
        poly_sample = ipta_courses[ipta_courses['course_id'].str.startswith('POLY')]
        print(f"\nPOLY courses: {len(poly_sample)}, with cutoff: {len(poly_sample[poly_sample['merit_cutoff'] > 0])}")
        print(poly_sample[['course_id', 'course_name', 'merit_cutoff']].drop_duplicates('course_id').head())
    else:
        print("CRITICAL: 'merit_cutoff' column NOT FOUND in master_df")

if __name__ == "__main__":
    debug_data()
