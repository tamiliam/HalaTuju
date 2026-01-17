import pandas as pd
import streamlit as st
from src.engine import check_eligibility
from src.translations import get_text

try:
    from description import course_info # Your uploaded file
except ImportError:
    course_info = {}

def get_institution_type(row):
    # Returns a translation KEY instead of a hardcoded string
    t = str(row.get('type', '')).upper()
    code = str(row.get('course_id', '')).upper()
    
    if "POLITEKNIK" in t or "POLY" in code:
        return "inst_poly"
    elif "IKBN" in code or "ILP" in code or "ILKBS" in t:
        return "inst_ikbn"
    elif "KOLEJ" in t or "KK" in code:
        return "inst_kk"
    else:
        return "inst_other"

def calculate_match_quality(student, row):
    # Returns a translation KEY
    try:
        req = int(row.get('min_credits', 0))
    except:
        req = 0
    
    student_credits = student.credits
    if student_credits >= (req + 2): return "quality_safe"
    elif student_credits > req: return "quality_good"
    else: return "quality_reach"

def generate_dashboard_data(student, df_master, lang_code="en"):
    """
    df_master is now the Enriched Data (Offerings).
    It contains multiple rows per course (one for each location).
    """
    txt = get_text(lang_code)
    eligible_offerings = []
    
    # Initialize stats using translation keys
    stats_keys = ["inst_poly", "inst_ikbn", "inst_kk", "inst_other"]
    stats = {txt[k]: 0 for k in stats_keys}
    
    # 1. OPTIMIZATION: Check eligibility on UNIQUE courses first
    unique_courses = df_master.drop_duplicates(subset=['course_id'])
    eligible_course_ids = set()
    
    for _, course_row in unique_courses.iterrows():
        is_eligible, _ = check_eligibility(student, course_row)
        if is_eligible:
            eligible_course_ids.add(course_row['course_id'])
            
    # 2. FILTER: Grab all offerings for eligible courses
    mask = df_master['course_id'].isin(eligible_course_ids)
    eligible_df = df_master[mask].copy()
    
    # 3. BUILD OUTPUT LIST
    offerings_list = eligible_df.to_dict('records')
    
    for row in offerings_list:
        inst_key = get_institution_type(row)
        inst_type_name = txt.get(inst_key, txt["inst_other"])
        
        if inst_type_name in stats: 
            stats[inst_type_name] += 1
        else: 
            stats[txt["inst_other"]] += 1
        
        quality_key = calculate_match_quality(student, row)
        quality_name = txt.get(quality_key, "Unknown")
        
        # Inject "Human" Description from description.py
        cid = row.get('course_id')
        desc_data = course_info.get(cid, {})
        
        eligible_offerings.append({
            "course_name": row.get('course_name', txt["unknown_course"]),
            "institution": row.get('institution_name', txt["unknown_inst"]),
            "state": row.get('state', txt["unknown_state"]),
            "fees": row.get('fees', '-'),
            "duration": row.get('duration', '-'),
            "type": inst_type_name,
            "quality": quality_name,
            "quality_key": quality_key, # Keep key for logic if needed
            "code": cid,
            # Rich Content
            "headline": desc_data.get('headline', ''),
            "synopsis": desc_data.get('synopsis', '')
        })

    # Logic for Top 3 (Teaser) - Prefer varied Types
    top_picks = []
    # Sort by Quality then Name (Safe Bet first)
    sorted_offerings = sorted(eligible_offerings, key=lambda x: (x['quality_key'] == "quality_safe"), reverse=True)
    
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
        "user_status": txt["status_eligible"] if top_picks else txt["status_not_eligible"],
        "total_matches": len(eligible_offerings),
        "summary_stats": stats,
        "featured_matches": top_picks,
        "full_list": sorted_offerings, 
        "is_locked": True 
    }