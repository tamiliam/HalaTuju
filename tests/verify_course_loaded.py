import sys
import os
import pandas as pd

# Add Project Root (one level up)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_manager import load_master_data

def verify_course():
    print("Loading master data...")
    df = load_master_data()
    print(f"Total Rows: {len(df)}")
    
    target_id = "IKBN-DIP-003"
    match = df[df['course_id'] == target_id]
    
    if not match.empty:
        print(f"SUCCESS: Found {target_id}")
        print(match[['course_id', 'course_name']].to_string(index=False))
    else:
        print(f"FAILURE: {target_id} NOT found.")

if __name__ == "__main__":
    verify_course()
