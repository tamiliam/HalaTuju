import pandas as pd
import streamlit as st
from src.engine import check_eligibility, ALL_REQ_COLUMNS
from src.translations import get_text

try:
    from description import course_info # Your uploaded file
except ImportError:
    course_info = {}

def get_institution_type(row):
    # Returns a translation KEY based on the category
    # Categories: Politeknik, Kolej Komuniti, ILKBS, ILJTM
    t = str(row.get('type', '')).upper()
    code = str(row.get('course_id', '')).upper()
    name = str(row.get('institution_name', '')).upper()
    cat = str(row.get('category', '')).upper() # Some files might have this
    
    # 1. Politeknik
    if "POLITEKNIK" in t or "POLY" in code or "POLITEKNIK" in name:
        return "inst_poly"
        
    # 2. Kolej Komuniti
    elif "KOLEJ" in t or "KK" in code or "KOMUNITI" in name:
        return "inst_kk"
        
    # 3. TVET Agencies (ILKBS & ILJTM) -> Map to IKBN/Skills bucket
    # ILKBS = Institut Latihan KBS (IKBN, IKTBN)
    # ILJTM = Institut Latihan Jabatan Tenaga Manusia (ILP, ADTEC, JMTI)
    elif (any(x in t for x in ["ILKBS", "ILJTM", "TVET"]) or 
          any(x in name for x in ["IKBN", "IKTBN", "ILP", "ADTEC", "JMTI"])):
        return "inst_ikbn"
        
    else:
        # Fallback: If it's none of the above, but we need to classify it.
        # Given the 3-bucket display, we treat residuals as 'Other' (which maps to Skills in stats).
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
    
    # Initialize stats using stable internal keys (matching get_institution_type)
    stats_keys = ["inst_poly", "inst_ikbn", "inst_kk", "inst_other"]
    stats = {k: 0 for k in stats_keys}
    
    # 1. OPTIMIZATION: Check eligibility by Requirement Signature (not just Course ID)
    # Different locations for the same course might have slightly different requirements (rare but possible).
    # We create a "signature" of the requirements columns to verify unique sets.
    
    # We import the list of columns from engine.py to avoid duplication.
    # checking logic resides in engine.py, so the list of relevant columns should too.
    
    # Only use columns that actually exist in the dataframe
    valid_req_cols = [c for c in ALL_REQ_COLUMNS if c in df_master.columns]
    
    # Create a temporary signature for deduplication
    # We toggle 'copy' to avoid SettingWithCopy warnings if df_master is a slice
    df_work = df_master.copy()
    
    # Fill NAs with -1 just for the signature creation to ensure consistency
    df_work['req_signature'] = df_work[valid_req_cols].fillna(-1).apply(tuple, axis=1)
    
    # Find unique requirement sets
    unique_req_sets = df_work.drop_duplicates(subset=['req_signature'])
    eligible_signatures = set()
    
    for _, row in unique_req_sets.iterrows():
        is_eligible, _ = check_eligibility(student, row)
        if is_eligible:
            eligible_signatures.add(row['req_signature'])
            
    # 2. FILTER: Keep all offerings that match an eligible signature
    mask = df_work['req_signature'].isin(eligible_signatures)
    eligible_df = df_work[mask].copy()
    
    # 3. BUILD OUTPUT LIST
    offerings_list = eligible_df.to_dict('records')
    
    for row in offerings_list:
        inst_key = get_institution_type(row)
        inst_type_name = txt.get(inst_key, txt.get("inst_other", "TVET"))
        
        # Consistent key usage
        # Consistent key usage
        if inst_key in stats:
            stats[inst_key] += 1
        else:
            # Fallback: If it's undefined (Other), we group it under Skills (IKBN/TVET) for display simplicity
            # unless it explicitly looks like something else. 
            # For now, let's assume 'Other' -> 'inst_ikbn' (General TVET/Skills)
            stats["inst_ikbn"] += 1
        
        quality_key = calculate_match_quality(student, row)
        quality_name = txt.get(quality_key, "Unknown")
        
        # Inject "Human" Description from description.py
        cid = str(row.get('course_id', '')).strip().upper() # Normalize ID
        desc_data = course_info.get(cid, {})
        
        # DEBUG LOGGING (Check Streamlit Cloud Logs)
        # if not desc_data:
        #    print(f"MISSING DESC for Course ID: {cid}")
        # else:
        #    print(f"FOUND DESC for {cid}: {desc_data.get('headline')}")
        
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
            "synopsis": desc_data.get('synopsis', f"DEBUG: Model has no data for ID: {cid}"),
            "jobs": desc_data.get('jobs', [])
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

    # Calculate Unique Courses Count
    unique_course_count = len(set(o['code'] for o in eligible_offerings))

    return {
        "user_status": txt["status_eligible"] if top_picks else txt["status_not_eligible"],
        "total_matches": len(eligible_offerings),
        "total_unique_courses": unique_course_count,
        "summary_stats": stats,
        "featured_matches": top_picks,
        "full_list": sorted_offerings, 
        "is_locked": True 
    }