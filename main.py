import streamlit as st
import pandas as pd
import re # VALIDATION FIX
import os
import time
from supabase import create_client, Client
from src.engine import StudentProfile, load_and_clean_data
from src.dashboard import generate_dashboard_data
from src.translations import get_text, LANGUAGES
from src.data_manager import load_master_data


# --- 1. CONFIGURATION & SECRETS ---
st.set_page_config(page_title="Hala Tuju SPM", page_icon="🎓", layout="centered")

def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("assets/style.css") # <--- Inject the styles

# Supabase Setup
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    DB_CONNECTED = True
except Exception:
    DB_CONNECTED = False

# --- 2. DATA LOADER ---
@st.cache_data
def get_data():
    # Use our new Data Manager to get the enriched dataset
    return load_master_data()

df_courses = get_data()

# --- 3. HELPER: DATABASE OPS ---
# --- 3. HELPER: DATABASE OPS ---
def save_profile(name, email, phone, student, eligible_count):
    if not DB_CONNECTED: return False
    
    # 1. Prepare Data
    data = {
        "name": name, 
        "email": email, 
        "phone": phone, 
        "gender": student.gender,
        "grades": student.grades, 
        "eligible_count": eligible_count
        # "updated_at": "now()" <--- REMOVED due to Schema Error
    }
    
    try:
        # 2. Upsert (Insert or Update based on 'phone' if it's unique, otherwise we might need logic)
        # Assuming 'phone' is a unique key or we use it to query first. 
        # For robustness, let's try to find existing user by phone first.
        existing = supabase.table("student_profiles").select("id").eq("phone", phone).execute()
        
        if existing.data:
            # Update
            uid = existing.data[0]['id']
            supabase.table("student_profiles").update(data).eq("id", uid).execute()
        else:
            # Insert
            supabase.table("student_profiles").insert(data).execute()
            
        return True
    except Exception as e:
        st.error(f"Save Error: {e}")
        return False

def login_user(phone):
    """Retrieve user profile by phone number."""
    if not DB_CONNECTED: return None
    try:
        # Normalize phone? For now exact match
        res = supabase.table("student_profiles").select("*").eq("phone", phone).execute()
        if res.data:
            return res.data[0] # Return latest/first match
    except Exception as e:
        st.error(f"Login Error: {e}")
    return None

def validate_submission(name, email, phone, t):
    """Validates user input with robust Malaysian context regex."""
    errors = []
    
    # 1. Validate Name (Malaysian Context: A/L, A/P, @, spaces, etc)
    # Regex: Starts with letter, allows spaces, ', /, ., @, -
    name_pattern = r"^[A-Za-z\s'\/\.\@\-]+$"
    if not name or len(name.strip()) < 2:
        errors.append(t.get('err_name_short', "Name is too short"))
    elif not re.match(name_pattern, name):
        errors.append(t.get('err_name_invalid', "Invalid characters in Name"))

    # 2. Validate Email (Standard Robust)
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not email or not re.match(email_pattern, email):
        errors.append(t.get('err_email_invalid', "Invalid Email Address"))

    # 3. Validate Phone (Malaysia Mobile: 01x-xxxxxxx or +601x)
    # Prefix: +601 or 01, digit after 1, 7-8 digits following
    phone_pattern = r"^(?:\+?60|0)1[0-9]{1}-?[0-9]{7,8}$"
    if not phone:
        errors.append(t.get('err_phone_short', "Phone number required"))
    elif not re.match(phone_pattern, phone.strip().replace(" ", "")): # Strip spaces before regex if needed, or regex handles it?
        # User regex was: ^(?:\+?60|0)1[0-9]{1}-?[0-9]{7,8}$
        # It handles optional hyphen. We should probably strip spaces to be safe given user input habits.
        errors.append(t.get('err_phone_invalid', "Invalid Malaysia Phone Number"))

    if errors:
        return False, errors
    return True, []

def get_leads():
    """Fetch all leads for the Admin Panel"""
    if not DB_CONNECTED: return pd.DataFrame()
    try:
        response = supabase.table("student_profiles").select("*").order("created_at", desc=True).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        return pd.DataFrame()

# --- 4. SIDEBAR (Inputs & Admin) ---
lang_code = st.sidebar.selectbox(
    "🌐 Language / Bahasa / மொழி", 
    options=list(LANGUAGES.keys()), 
    format_func=lambda x: LANGUAGES[x]
)
t = get_text(lang_code)

st.sidebar.title(f"📝 {t['sb_title']}")
st.sidebar.caption(t['sb_caption'])

# Options
grade_opts = [t["opt_not_taken"], "A+", "A", "A-", "B+", "B", "C+", "C", "D", "E", "G"]

#gender_map = {t['gender_male']: "Lelaki", t['gender_female']: "Perempuan"}
# --- LOGIN / RESUME SESSION ---
if not st.session_state.get('unlocked'):
    with st.sidebar.expander("👤 Existing User? Login"):
        login_phone = st.text_input("Phone Number", key="login_phone")
        if st.button("Resume Session"):
            user_data = login_user(login_phone)
            if user_data:
                st.session_state['restored_user'] = user_data
                st.session_state['unlocked'] = False # Let them see inputs first
                st.toast(f"Welcome back, {user_data['name']}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("User not found.")

# Helper to restore grades
def get_restored_index(subject_key, opts, default_idx=0):
    """
    Determines the selectbox index.
    If 'restored_user' exists: use DB value (or 0 if missing).
    Else: use default_idx.
    """
    user = st.session_state.get('restored_user')
    if user:
        grades = user.get('grades', {})
        val = grades.get(subject_key)
        # If val is found in current opts (e.g. 'A+'), return its index
        # Note: opts[0] is localized "Not Taken". DB stores VALID grades only.
        if val in opts:
            return opts.index(val)
        return 0 # Not found/Not Taken
    return default_idx

with st.sidebar.form("grades_form"):

    # Core Subjects
    st.subheader(t['sb_core_subjects'])
    bm = st.selectbox(t['subj_bm'], grade_opts, index=get_restored_index('bm', grade_opts, 7))
    eng = st.selectbox(t['subj_eng'], grade_opts, index=get_restored_index('eng', grade_opts, 7))
    hist = st.selectbox(t['subj_hist'], grade_opts, index=get_restored_index('hist', grade_opts, 7))
    math = st.selectbox(t['subj_math'], grade_opts, index=get_restored_index('math', grade_opts, 7))
    moral = st.selectbox(t['subj_moral'], grade_opts, index=get_restored_index('moral', grade_opts, 7))
    
    # Science Stream
    with st.expander(t['sb_science_stream'], expanded=False):
        addmath = st.selectbox(t['subj_addmath'], grade_opts, index=get_restored_index('addmath', grade_opts, 0))
        phy = st.selectbox(t['subj_phy'], grade_opts, index=get_restored_index('phy', grade_opts, 0))
        chem = st.selectbox(t['subj_chem'], grade_opts, index=get_restored_index('chem', grade_opts, 0))
        bio = st.selectbox(t['subj_bio'], grade_opts, index=get_restored_index('bio', grade_opts, 0))
    # Arts Stream
    with st.expander(t['sb_arts_stream'], expanded=False):
        sci = st.selectbox(t['subj_sci'], grade_opts, index=get_restored_index('sci', grade_opts, 0))
        ekonomi = st.selectbox(t['subj_ekonomi'], grade_opts, index=get_restored_index('ekonomi', grade_opts, 0))
        business = st.selectbox(t['subj_business'], grade_opts, index=get_restored_index('business', grade_opts, 0))
        poa = st.selectbox(t['subj_poa'], grade_opts, index=get_restored_index('poa', grade_opts, 0))
        geo = st.selectbox(t['subj_geo'], grade_opts, index=get_restored_index('geo', grade_opts, 0))
        psv = st.selectbox(t['subj_psv'], grade_opts, index=get_restored_index('psv', grade_opts, 0))

    #selected_gender_label = st.radio(t['sb_gender'], list(gender_map.keys()), horizontal=True)
    #internal_gender = gender_map[selected_gender_label]
    gender = st.radio(t["sb_gender"], [t["gender_male"], t["gender_female"]])
    
    submitted = st.form_submit_button(f"🚀 {t['sb_btn_submit']}")

# --- SECRET ADMIN SECTION ---
st.sidebar.markdown("---")
with st.sidebar.expander(f"🔒 {t['admin_login']}"):
    admin_pwd = st.text_input("Password", type="password")
    
    # Verify against Streamlit Secrets
    secret_pwd = st.secrets.get("ADMIN_PASSWORD", "admin123") # Fallback if secret not set
    
    if admin_pwd == secret_pwd:
        st.success(t['admin_success'])
        if st.button(t['admin_view_leads']):
            st.session_state['show_admin'] = True

# --- 5. MAIN PAGE ---
st.title(t['header_title'])
st.write(t['header_subtitle'])

# Check for Admin Mode
if st.session_state.get('show_admin'):
    st.markdown("---")
    st.subheader("🕵️‍♂️ Admin Dashboard")
    df_leads = get_leads()
    if not df_leads.empty:
        st.dataframe(df_leads)
        st.caption(f"Total Leads: {len(df_leads)}")
    else:
        st.warning("No leads found yet.")
    
    if st.button("❌ Close Admin"):
        st.session_state['show_admin'] = False
        st.rerun()
    st.stop() # Stop rendering the rest of the page if in Admin mode

# ... [REST OF THE APP LOGIC] ...
if 'unlocked' not in st.session_state:
    st.session_state['unlocked'] = False

if submitted:
    st.session_state['unlocked'] = False
    grades = {
        'bm': bm, 'eng': eng, 'hist': hist, 'math': math, 'moral': moral,
        'addmath': addmath, 'phy': phy, 'chem': chem, 'bio': bio,
        'sci': sci, 'ekonomi': ekonomi, 'business': business, 
        'poa': poa, 'geo': geo, 'psv': psv
    }
    grades = {k: v for k, v in grades.items() if v != t['opt_not_taken']}
    student = StudentProfile(grades, gender, 'Warganegara', 'Tidak', 'Tidak')
    st.session_state['current_student'] = student
    
    with st.spinner(t['spinner_msg']):
        time.sleep(0.5)
        st.session_state['dash'] = generate_dashboard_data(student, df_courses, lang_code=lang_code)

if 'dash' in st.session_state:
    dash = st.session_state['dash']
    if dash['total_matches'] > 0:
        # Use dynamic message if available, otherwise fallback
        if 'hero_eligible_dynamic' in t:
            msg = t['hero_eligible_dynamic'].format(
                courses=dash.get('total_unique_courses', 0), 
                locs=dash['total_matches']
            )
        else:
            msg = t['hero_success'].format(count=dash['total_matches'])
            
        st.success(msg)
        c1, c2, c3 = st.columns(3)
        c1.metric(t['inst_poly'], dash['summary_stats'].get('inst_poly', 0))
        c2.metric(t['inst_ikbn'], dash['summary_stats'].get('inst_ikbn', 0))
        c3.metric(t['inst_kk'], dash['summary_stats'].get('inst_kk', 0))
        st.markdown("---")
        
        if st.session_state['unlocked']:
            st.info(t['unlocked_alert'])
            st.subheader(t['table_title'])
            all_courses = dash.get('full_list', [])
            if all_courses:
                df_display = pd.DataFrame(all_courses)
                df_display = df_display.rename(columns={
                    "course_name": t['table_col_course'],
                    "institution": t['table_col_inst'],
                    "type": t['table_col_cat'],
                    "quality": t['table_col_status']
                })
                # 3. Interactive Filters
                c_filter1, c_filter2 = st.columns(2)
                
                # Filter A: Category
                cat_col = t['table_col_cat']
                cat_filter = c_filter1.multiselect(
                    t['filter_label'],
                    options=df_display[cat_col].unique(),
                    default=df_display[cat_col].unique()
                )
                
                # Filter B: State (NEW!)
                state_opts = sorted([str(x) for x in df_display["state"].unique() if x])
                state_filter = c_filter2.multiselect(
                    f"📍 {t.get('filter_state', 'Filter Location:')}", 
                    options=state_opts,
                    default=state_opts
                )
                
                # Apply Filters
                mask = (df_display[cat_col].isin(cat_filter)) & (df_display["state"].isin(state_filter))
                df_filtered = df_display[mask]
                
                # Show Enriched Table
                st.dataframe(
                    df_filtered[[
                        t['table_col_course'], 
                        t['table_col_inst'], 
                        "state",   # New Column
                        "fees",    # New Column
                        t['table_col_cat'], 
                        t['table_col_status']
                    ]],
                    use_container_width=True,
                    hide_index=True,
                    height=500
                )
                st.caption(t['filter_count'].format(shown=len(df_filtered), total=len(df_display)))
                st.write(t['contact_counselor'])
        else:
            # LOCKED VIEW (Teaser)
            st.subheader(t['teaser_title'])
            st.write(t['teaser_subtitle'])
            
            for i, pick in enumerate(dash['featured_matches']):
                # 1. Use the catchy Headline if available, otherwise standard name
                display_title = pick.get('headline') if pick.get('headline') else pick['course_name']
                
                with st.expander(f"#{i+1}: {display_title}", expanded=True):
                    # 2. Show the human-friendly synopsis
                    if pick.get('synopsis'):
                        st.info(pick['synopsis'])
                        
                    # 2b. Show Jobs (If available)
                    if pick.get('jobs'):
                        st.markdown(f"**💼 Career:** {', '.join(pick['jobs'])}")
                    
                    # 3. Show Real Data (Location, Fees, Inst)
                    st.markdown(f"**🏫 {pick['institution']}**")
                    
                    # 4. THE 2x2 STATS GRID (Using CSS Classes)
                    stats_html = f"""
                    <div class="badge-container">
                        <div class="badge-base badge-time">
                            ⏱️ <b>Duration:</b><br>{pick.get('duration', '-')}
                        </div>
                        <div class="badge-base badge-mode">
                            🛠️ <b>Mode:</b><br>{pick.get('type', 'Full-time')}
                        </div>
                        <div class="badge-base badge-money">
                            💰 <b>Fees:</b><br>{pick.get('fees', '-')}
                        </div>
                        <div class="badge-base badge-hostel">
                            🏠 <b>Hostel:</b><br>Available
                        </div>
                    </div>
                    """
                    st.markdown(stats_html, unsafe_allow_html=True)
                    
                    if st.button(t['btn_save_course'], key=f"save_{i}"):
                         st.toast(t['btn_saved_toast'].format(course=pick['course_name']))

            st.markdown("---")
            st.write(t['locked_count'].format(remaining=dash['total_matches'] - 3))
            st.warning(f"🔒 **{t['locked_cta_title']}**")
            st.write(t['locked_cta_desc'])
            
            # --- GOOGLE LOGIN (NEW) ---
            from src.auth import render_google_login
            g_user, g_err = render_google_login()
            
            if g_user:
                # Loophole: If logged in via Google, auto-unlock!
                # In real flow, we might still want to ask for Phone number if missing
                st.success(f"✅ Welcome, {g_user['name']}!")
                if st.button("🔓 Continue to Results"):
                     # Auto-save google profile
                     save_profile(g_user['name'], g_user['email'], "Google-Auth", st.session_state['current_student'], dash['total_matches'])
                     st.session_state['unlocked'] = True
                     st.rerun()

            # --- MANUAL FORM ---
            st.write("Or enter details manually:")
            with st.form("lead_capture"):
                c_name, c_phone = st.columns(2)
                name = c_name.text_input(
                    t['form_name'], 
                    placeholder="e.g. Ali Bin Abu",
                    help="Nama Penuh seperti dalam KP / Full Name as per IC"
                )
                phone = c_phone.text_input(
                    t['form_phone'], 
                    placeholder="e.g. 012-3456789",
                    help="Format: 01x-xxxxxxx"
                )
                email = st.text_input(
                    t['form_email'], 
                    placeholder="e.g. ali@gmail.com"
                )
                if st.form_submit_button(f"🔓 {t['btn_unlock']}"):
                    # Validate Inputs
                    is_valid, err_list = validate_submission(name, email, phone, t)
                    
                    if is_valid:
                        if save_profile(name, email, phone, st.session_state['current_student'], dash['total_matches']):
                            st.session_state['unlocked'] = True
                            st.toast(t['toast_success'])
                            st.rerun()
                    else:
                        for err in err_list:
                             st.error(err)
    else:
        st.error(t['hero_fail'])
        st.info(t['hero_tip'])
else:
    st.info(t['landing_msg'])

# --- 6. FOOTER (Trust Signals) ---
st.markdown("---")
with st.expander(t['about_title']):
    st.markdown(t['about_desc'])
    st.caption(t['footer_credits'])