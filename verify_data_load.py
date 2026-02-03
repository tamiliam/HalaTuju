
import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.abspath('c:/Users/tamil/Python/HalaTuju'))

from src.data_manager import load_master_data

def verify():
    print("Loading Master Data...")
    try:
        df = load_master_data()
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    print(f"Total Rows: {len(df)}")
    
    # Check UA
    ua_df = df[df['type'] == 'UA']
    print(f"UA Rows: {len(ua_df)}")
    
    # Check Merit
    if 'merit_cutoff' not in df.columns:
        print("ERROR: merit_cutoff column missing!")
        return
        
    merit_df = df[df['merit_cutoff'] > 0]
    print(f"Rows with Merit > 0: {len(merit_df)}")
    
    # Breakdown
    print("\nMerit Breakdown by Type:")
    print(merit_df['type'].value_counts())
    
    # Check specific KK mapping
    print("\nChecking Specific Mappings:")
    check_ids = ['KKOM-CET-002', 'KKOM-CET-022', 'POLY-DIP-072']
    subset = df[df['course_id'].isin(check_ids)]
    print(subset[['course_id', 'merit_cutoff', 'type']].to_string())

if __name__ == "__main__":
    verify()
