import pandas as pd
import streamlit as st
from src.engine import check_eligibility
try:
    from description import course_info # Your uploaded file
except ImportError:
    course_info = {}

def get_institution_type(row):
    # Use the 'type' column from our merged data, or fallback to ID
    t = str(row.get('type', '')).upper()
    code = str(row.get('course_id', '')).upper()
    
    if "POLITEKNIK" in t or "POLY" in code:
        return "Politeknik"
    elif "IKBN" in code or "ILP" in code or "ILKBS" in t:
        return "IKBN / ILP (Skills)"
    elif "KOLEJ" in t or "KK" in code:
        return "Kolej Komuniti"
    else:
        return "TVET / Other"

def calculate_match_quality(student, row):
    try:
        req = int(row.get('min_credits', 0))
    except:
        req = 0
    
    student_credits = student.credits
    if student_credits >= (req + 2): return "Safe Bet 🟢"
    elif student_credits > req: return "Good Match 🔵"
    else: return "Reach 🟡"

def generate_dashboard_data(student, df_master):
    """
    df_master is now the Enriched Data (Offerings).
    It contains multiple rows per course (one for each location).
    """
    eligible_offerings = []
    stats = {"Politeknik": 0, "IKBN / ILP (Skills)": 0, "Kolej Komuniti": 0, "TVET / Other": 0}
    
    # 1. OPTIMIZATION: Check eligibility on UNIQUE courses first
    # We don't want to run the math 50 times for the same course at 50 locations.
    unique_courses = df_master.drop_duplicates(subset=['course_id'])
    eligible_course_ids = set()
    
    for _, course_row in unique_courses.iterrows():
        is_eligible, _ = check_eligibility(student, course_row)
        if is_eligible:
            eligible_course_ids.add(course_row['course_id'])
            
    # 2. FILTER: Grab all offerings for eligible courses
    # Now we get the locations back!
    mask = df_master['course_id'].isin(eligible_course_ids)
    eligible_df = df_master[mask].copy()
    
    # 3. BUILD OUTPUT LIST
    offerings_list = eligible_df.to_dict('records')
    
    for row in offerings_list:
        inst_type = get_institution_type(row)
        if inst_type in stats: stats[inst_type] += 1
        else: stats["TVET / Other"] += 1
        
        quality = calculate_match_quality(student, row)
        
        # Inject "Human" Description from description.py
        cid = row.get('course_id')
        desc_data = course_info.get(cid, {})
        
        eligible_offerings.append({
            "course_name": row.get('course_name', 'Unknown Course'),
            "institution": row.get('institution_name', 'Unknown Inst'),
            "state": row.get('state', 'Malaysia'),
            "fees": row.get('fees', '-'),
            "duration": row.get('duration', '-'),
            "type": inst_type,
            "quality": quality,
            "code": cid,
            # Rich Content
            "headline": desc_data.get('headline', ''),
            "synopsis": desc_data.get('synopsis', '')
        })

    # Logic for Top 3 (Teaser) - Prefer varied Types
    top_picks = []
    # Sort by Quality then Name
    sorted_offerings = sorted(eligible_offerings, key=lambda x: (x['quality'] == "Safe Bet 🟢"), reverse=True)
    
    # Dedup for Top 3 (Don't show same course 3 times)
    seen_codes = set()
    unique_sorted = []
    for x in sorted_offerings:
        if x['code'] not in seen_codes:
            unique_sorted.append(x)
            seen_codes.add(x['code'])
            
    # Pick Top 3 Distinct
    if len(unique_sorted) > 0: top_picks.append(unique_sorted[0])
    if len(unique_sorted) > 1: top_picks.append(unique_sorted[1])
    if len(unique_sorted) > 2: top_picks.append(unique_sorted[2])

    return {
        "user_status": "Eligible" if top_picks else "Not Eligible",
        "total_matches": len(eligible_offerings), # Total OFFERINGS (Course x Location)
        "summary_stats": stats,
        "featured_matches": top_picks,
        "full_list": sorted_offerings, 
        "is_locked": True 
    }