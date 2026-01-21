import sys
import os
import pandas as pd
from unittest.mock import MagicMock

# Path Setup
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.modules['streamlit'] = MagicMock()

from src.data_manager import load_master_data
from src.dashboard import group_courses_by_id, display_course_card

def test_ui_data_flow():
    # 1. Load Master Data & Check Columns
    print("Loading Master Data...")
    df = load_master_data()
    
    required = ['fees', 'hostel_fee', 'details_url', 'inst_url']
    for req in required:
        if req not in df.columns:
            print(f"FAILED: Column {req} missing from master_df")
            return
            
    # 2. Test Grouping Logic with Dummy Data
    dummy_input = [
        {
            "course_id": "C001", "course_name": "Course A", "duration": "6 Sem",
            "institution": "Poly A", "state": "Johor",
            "fees": "RM 200", # Mapped value
            "inst_url": "http://polya.com",
            "hostel_fee": "RM 60",
            "details_url": "http://details.com/a",
            "fit_score": 100
        }
    ]
    
    grouped = group_courses_by_id(dummy_input)
    if not grouped:
        print("FAILED: Grouping returned empty")
        return
        
    pick = grouped[0]
    
    # Check if UI Component runs (Validation of keys accessed)
    print("Testing display_course_card execution...")
    try:
        display_course_card(pick, {})
        print("PASSED: display_course_card ran without error")
    except Exception as e:
        print(f"FAILED: display_course_card crashed: {e}")
        import traceback
        traceback.print_exc()
        
    # Check Metadata Accessibility
    loc0 = pick['locations'][0]
    if loc0.get('fees') == "RM 200" and loc0.get('inst_url') == "http://polya.com":
        print("PASSED: Metadata Propagation")
    else:
        print("FAILED: Metadata mismatch")

if __name__ == "__main__":
    test_ui_data_flow()
