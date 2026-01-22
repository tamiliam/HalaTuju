import pandas as pd
import sys
import os
# Add the project root directory to Python's path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
from src.engine import check_eligibility, ALL_REQ_COLUMNS
from src.translations import get_text

try:
    from src.description import course_info
except ImportError:
    # Fallback/Debug
    print("WARNING: Could not import src.description. Using empty dict.")
    print("WARNING: Could not import src.description. Using empty dict.")
    course_info = {}

BATCH_SIZE = 10 # Configurable

def render_pagination(total_items, items_per_page, current_page_key, unique_id="main"):
    import math
    if total_items <= items_per_page: return 1
    
    total_pages = math.ceil(total_items / items_per_page)
    
    # Get Current Page from Session (safe get)
    if current_page_key not in st.session_state:
        st.session_state[current_page_key] = 1
        
    current = st.session_state[current_page_key]
    
    # Render Controls
    c1, c2, c3, c4, c5 = st.columns([1,1,2,1,1])
    
    def set_page(p):
        st.session_state[current_page_key] = max(1, min(p, total_pages))
    
    with c1:
        if st.button("<<", key=f"{current_page_key}_{unique_id}_first", disabled=(current==1)):
            set_page(1)
            st.rerun()
    with c2:
        if st.button("<", key=f"{current_page_key}_{unique_id}_prev", disabled=(current==1)):
            set_page(current - 1)
            st.rerun()
            
    with c3:
        st.markdown(f"<div style='text-align:center; padding-top: 5px;'>Page <b>{current}</b> of <b>{total_pages}</b></div>", unsafe_allow_html=True)
        
    with c4:
        if st.button(">", key=f"{current_page_key}_{unique_id}_next", disabled=(current==total_pages)):
            set_page(current + 1)
            st.rerun()
    with c5:
        if st.button(">>", key=f"{current_page_key}_{unique_id}_last", disabled=(current==total_pages)):
            set_page(total_pages)
            st.rerun()
            
    return current

def get_institution_type(row):
    # Returns a translation KEY based on the category
    # Categories: Politeknik, Kolej Komuniti, ILKBS, ILJTM
    t = str(row.get('type', '')).upper()
    code = str(row.get('course_id', '')).upper()
    name = str(row.get('institution_name', '')).upper()
    acronym = str(row.get('acronym', '')).upper() # Added for robust ID
    
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
          any(x in name for x in ["IKBN", "IKTBN", "ILP", "ADTEC", "JMTI", "JAPAN", "JEPUN"]) or
          "JMTI" in acronym):
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
            "course_id": cid, # REQUIRED for Ranking Engine
            # Rich Content
            "headline": desc_data.get('headline', ''),
            "synopsis": desc_data.get('synopsis', ''),
            "jobs": desc_data.get('jobs', []),
            "institution_id": row.get('institution_id'), # CRITICAL: Required for Ranking Engine
            # Meta
            "inst_url": row.get('inst_url', '#'),
            "hostel_fee": row.get('hostel_fee', 'N/A'),
            "details_url": row.get('details_url', '#')
        })
        
    # Calculate Unique Courses
    unique_ids = set()
    for item in eligible_offerings:
        if item.get('course_id'):
            unique_ids.add(item['course_id'])

    return {
        "featured_matches": [], # Will be populated by Ranking Engine in main.py
        "full_list": eligible_offerings,
        "summary_stats": stats,
        "total_unique_courses": len(unique_ids),
        "total_matches": stats["inst_poly"] + stats["inst_ikbn"] + stats["inst_kk"] + stats["inst_other"]
    }

def group_courses_by_id(flat_list):
    """
    Aggregates a flat list of course/location offerings into unique valid courses.
    Returns a list of course dictionaries, each containing a 'locations' list.
    """
    grouped = {}
    
    for item in flat_list:
        cid = item.get('course_id')
        if not cid: continue
        
        # Initialize Group if new
        if cid not in grouped:
            grouped[cid] = {
                'course_id': cid,
                'course_name': item.get('course_name'),
                'duration': item.get('duration'), # Added Duration
                'fit_reasons': item.get('fit_reasons', []),
                'headline': item.get('headline', ''),
                'synopsis': item.get('synopsis', ''),
                'jobs': item.get('jobs', []),
                'max_score': -999, # Sentinel
                'locations': []
            }
        
        # Add Location Entry
        score = item.get('fit_score', 0)
        grouped[cid]['locations'].append({
            'institution_name': item.get('institution'),
             'score': score,
             'state': item.get('state'),
             'fees': item.get('fees'),
             'type': item.get('type'),
             'inst_url': item.get('inst_url'),
             'hostel_fee': item.get('hostel_fee'),
             'details_url': item.get('details_url')
        })
        
        # Update Max Score for the Group
        if score > grouped[cid]['max_score']:
            grouped[cid]['max_score'] = score
            # Optional: Capture the 'best fit reasons' from the highest scoring location?
            # Usually reasons are similar for same course, but Institution modifiers might add some.
            if item.get('fit_reasons'):
                grouped[cid]['fit_reasons'] = item.get('fit_reasons')

    # Convert to list and Sort by Max Score Descending
    final_list = list(grouped.values())
    final_list.sort(key=lambda x: x['max_score'], reverse=True)
    
    # Internal Sort: Sort locations within each group by score descending
    for group in final_list:
        group['locations'].sort(key=lambda x: x['score'], reverse=True)
        
    return final_list
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
    # Pick Top 10 Distinct (Frontend will slice 3 or 5)
    top_picks = unique_sorted[:10]

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
# --- UI HELPERS ---
def display_course_card(pick, t=None, show_trigger=True, show_title=True):
    """
    Renders a single "Product Card" for a course recommendation.
    Uses 'course-card' CSS class for modern styling (Gen Z appeal).
    Returns True if the 'See why' button is clicked.
    """
    import streamlit as st
    import textwrap
    
    # 1. Setup Data
    c_name = pick.get('course_name', 'Unknown Course')
    score = pick.get('max_score', 0)
    synopsis = pick.get('synopsis', '')
    
    # Fit Reasons Logic
    reasons = pick.get('fit_reasons', [])
    reasons_html = ""
    if reasons:
        reasons_list = "".join([f"<li>{r}</li>" for r in reasons[:3]])
        reasons_html = f"<ul style='margin: 5px 0 10px 15px; color: #555;'>{reasons_list}</ul>"
    
    locs = pick.get('locations', [])
    loc0 = locs[0] if locs else {}
    
    dur = pick.get('duration') or "N/A"
    fees = loc0.get('fees', 'N/A')
    hostel = loc0.get('hostel_fee', 'N/A')
    det_url = loc0.get('details_url', '#')
    
    # 2. Career HTML
    career_html = ""
    if pick.get('jobs'):
         career_html = f'<div class="career-box">💼 {", ".join(pick["jobs"])}</div>'
    
    # 3. Table HTML (Preserved as Visible)
    tbl_html = ""
    if locs:
         container_style = "margin-top: 8px;"
         scroll_class = ""
         
         # Logic: Scroll if > 5 items
         if len(locs) > 5:
              container_style += " max-height: 250px; overflow-y: auto; padding-right: 4px;"
              scroll_class = "scroll-box"
         
         rows = ""
         for loc in locs:
             name = loc.get('institution_name', 'Unknown')
             url = loc.get('inst_url', '#')
             state = loc.get('state', '-')
             score_loc = loc.get('score', 0)
             
             rows += f"""
<tr style="border-bottom: 1px solid #f1f2f6;">
<td style="padding: 8px;"><a href="{url}" target="_blank" class="inst-link">{name}</a></td>
<td style="padding: 8px; color: #636e72;">{state}</td>
<td style="padding: 8px; text-align:right; font-weight:bold; color:#6C5CE7;">{score_loc}</td>
</tr>
"""
             
         tbl_html = f"""
<div class="inst-table-container {scroll_class}" style="{container_style}">
<table style="width:100%; border-collapse: collapse; font-size: 0.9em;">
<thead>
<tr style="border-bottom: 2px solid #e1e1e1; background: #fafafa;">
<th style="padding: 8px; text-align:left; color:#6C5CE7; font-weight:700;">Institution</th>
<th style="padding: 8px; text-align:left; color:#6C5CE7; font-weight:700;">State</th>
<th style="padding: 8px; text-align:right; color:#6C5CE7; font-weight:700;">Fit</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>
"""

    # 4. Construct Card Parts
    
    # Part A: Header
    # Conditionally render Title
    title_html = f'<h3 class="card-title">{c_name}</h3>' if show_title else ''
    
    # Logic: If NOT interactive (show_trigger=False), we embed the table INSIDE the card.
    
    if not show_trigger:
        # EMBEDDED MODE
        card_html = textwrap.dedent(f"""
<div class="course-card" style="margin-bottom: 20px; padding-bottom: 5px;">
{title_html}
<div class="card-id">Fit Score: {score}</div>
<div class="card-desc">
{synopsis}
</div>
<div class="meta-row">
<span class="meta-pill pill-dur">🕒 {dur}</span>
<span class="meta-pill pill-fees">💰 {fees}</span>
<span class="meta-pill pill-hostel">🏠 {hostel}</span>
<a href="{det_url}" target="_blank" class="meta-pill pill-link">More details ↗</a>
</div>
{career_html}
{tbl_html}
</div>
        """)
        st.markdown(card_html, unsafe_allow_html=True)
        return False
        
    else:
        # INTERACTIVE MODE (Standard)
        card_header_html = textwrap.dedent(f"""
<div class="course-card" style="margin-bottom: 10px; padding-bottom: 5px;">
{title_html}
<div class="card-id">Fit Score: {score}</div>
<div class="card-desc">
{synopsis}
</div>
<div class="meta-row">
<span class="meta-pill pill-dur">🕒 {dur}</span>
<span class="meta-pill pill-fees">💰 {fees}</span>
<span class="meta-pill pill-hostel">🏠 {hostel}</span>
<a href="{det_url}" target="_blank" class="meta-pill pill-link">More details ↗</a>
</div>
{career_html}
</div>
        """)
        
        st.markdown(card_header_html, unsafe_allow_html=True)
        
        # Part B: Native Interaction Trigger
        clicked = False
        if show_trigger:
            # Using a unique key for every card is crucial
            clicked = st.button(f"✨ Key Matching Factors ({len(reasons)} reason{'s' if len(reasons)!=1 else ''})", key=f"btn_why_{pick.get('course_id')}_{pick.get('institution_id', 'gen')}")
            
            if clicked:
                # Show reasons dynamically if clicked (or could be used just as a trigger)
                 if reasons_html:
                     st.markdown(f"<div style='background:#f8f9fa; padding:10px; border-radius:8px; border:1px dashed #6C5CE7;'><strong>Why match?</strong>{reasons_html}</div>", unsafe_allow_html=True)
                 else:
                     st.info("High alignment with your academic strengths and interest profile.")

        # Part C: Footer (Table) - Rendered OUTSIDE in Interactive Mode (Wait, usually Tier 1 doesn't show table until expand? Or Tier 2?)
        # Actually Tier 1 shows table. Tier 2 shows table.
        # Original code rendered table OUTSIDE card.
        st.markdown(tbl_html, unsafe_allow_html=True)
        
        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
        
        return clicked
