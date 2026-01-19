
import sys
import os
import json
import pandas as pd

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from data_manager import load_master_data
from ranking_engine import COURSE_TAGS

def check():
    print("--- Loading Master Data ---")
    df = load_master_data()
    print(f"Total Rows: {len(df)}")
    
    # Search for KKOM-CET-005
    target = 'KKOM-CET-005'
    print(f"\n--- Checking Tags for {target} ---")
    tags = COURSE_TAGS.get(target)
    if tags:
        print(json.dumps(tags, indent=2))
    else:
        print("NO TAGS FOUND.")
        
if __name__ == "__main__":
    check()
