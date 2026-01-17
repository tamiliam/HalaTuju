import streamlit as st
import pandas as pd
import time
from supabase import create_client, Client
from src.engine import StudentProfile
from src.dashboard import generate_dashboard_data
from src.translations import get_text, LANGUAGES
from src.data_manager import load_master_data
from src.auth import AuthManager

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Hala Tuju SPM", page_icon="🎓", layout="centered")

def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("assets/style.css")

# --- 2. SETUP ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    auth = AuthManager(supabase)
    DB_CONNECTED = True
except Exception:
    st.error("Database Connection Failed")
    DB_CONNECTED = False

@st.cache_data
def get_data():
    return load_master_data()

df_courses = get_data()

# --- 3. HELPER: GRADE RESTORATION ---
def get_restored_index(subject_key, opts, user_grades, default_idx=0):
    val = user_grades.get(subject_key)
    if val in opts:
        return opts.index(val)
    return default_idx

# --- 4. VIEW: LANDING (Login/Register) ---
def render_landing(t):
    st.title("🔐 Hala Tuju Login")
    st.write(t['landing_msg'])
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            l_phone = st.text_input("Phone Number", placeholder="e.g. 012-3456789")
            l_pin = st.text_input("6-Digit PIN", type="password", max_chars=6)
            if st.form_submit_button("Login"):
                success, val = auth.login_user(l_phone, l_pin)
                if success:
                    st.toast(f"Welcome back, {val['full_name']}!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(val)

    with tab2:
        st.write("First time here? Create an account.")
        with st.form("reg_form"):
            r_name = st.text_input("Full Name", placeholder="Ali Bin Abu")
            r_phone = st.text_input("Phone Number", placeholder="e.g. 012-3456789")
            r_pin = st.text_input("Create 6-Digit PIN", type="password", max_chars=6, help="Remember this PIN!")
            
            if st.form_submit_button("Create Account"):
                success, val = auth.register_user(r_name, r_phone, r_pin)
                if success:
                    st.success("Account Created!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(val)

    # Footer
    st.markdown("---")
    with st.expander(t['about_title']):
        st.markdown(t['about_desc'])

# --- 5. VIEW: DASHBOARD (Main App) ---
def render_dashboard(user, t):
    # --- SIDEBAR ---
    st.sidebar.title(f"👤 {user.get('full_name', 'Student')}")
    if st.sidebar.button("Log Out"):
        auth.logout()

    st.sidebar.markdown("---")
    st.sidebar.title(f"📝 {t['sb_title']}")
    
    # Language Selector (Keep persistence)
    lang_code = st.session_state.get('lang_code', 'en')
    
    # Grades Logic
    grade_opts = [t["opt_not_taken"], "A+", "A", "A-", "B+", "B", "C+", "C", "D", "E", "G"]
    saved_grades = user.get('grades', {}) or {}
    
    with st.sidebar.form("grades_form"):
        st.subheader(t['sb_core_subjects'])
        bm = st.selectbox(t['subj_bm'], grade_opts, index=get_restored_index('bm', grade_opts, saved_grades, 7))
        eng = st.selectbox(t['subj_eng'], grade_opts, index=get_restored_index('eng', grade_opts, saved_grades, 7))
        hist = st.selectbox(t['subj_hist'], grade_opts, index=get_restored_index('hist', grade_opts, saved_grades, 7))
        math = st.selectbox(t['subj_math'], grade_opts, index=get_restored_index('math', grade_opts, saved_grades, 7))
        moral = st.selectbox(t['subj_moral'], grade_opts, index=get_restored_index('moral', grade_opts, saved_grades, 7))
        
        with st.expander(t['sb_science_stream'], expanded=False):
            addmath = st.selectbox(t['subj_addmath'], grade_opts, index=get_restored_index('addmath', grade_opts, saved_grades, 0))
            phy = st.selectbox(t['subj_phy'], grade_opts, index=get_restored_index('phy', grade_opts, saved_grades, 0))
            chem = st.selectbox(t['subj_chem'], grade_opts, index=get_restored_index('chem', grade_opts, saved_grades, 0))
            bio = st.selectbox(t['subj_bio'], grade_opts, index=get_restored_index('bio', grade_opts, saved_grades, 0))
        
        with st.expander(t['sb_arts_stream'], expanded=False):
            sci = st.selectbox(t['subj_sci'], grade_opts, index=get_restored_index('sci', grade_opts, saved_grades, 0))
            ekonomi = st.selectbox(t['subj_ekonomi'], grade_opts, index=get_restored_index('ekonomi', grade_opts, saved_grades, 0))
            business = st.selectbox(t['subj_business'], grade_opts, index=get_restored_index('business', grade_opts, saved_grades, 0))
            poa = st.selectbox(t['subj_poa'], grade_opts, index=get_restored_index('poa', grade_opts, saved_grades, 0))
            geo = st.selectbox(t['subj_geo'], grade_opts, index=get_restored_index('geo', grade_opts, saved_grades, 0))
            psv = st.selectbox(t['subj_psv'], grade_opts, index=get_restored_index('psv', grade_opts, saved_grades, 0))

        gender = st.radio(t["sb_gender"], [t["gender_male"], t["gender_female"]])
        submitted = st.form_submit_button(f"🚀 {t['sb_btn_submit']}")

    # --- CALCULATION TRIGGER ---
    # Trigger if submitted OR if no dash exists (First Load)
    if submitted or 'dash' not in st.session_state:
        # Save updates to DB
        new_grades = {
            'bm': bm, 'eng': eng, 'hist': hist, 'math': math, 'moral': moral,
            'addmath': addmath, 'phy': phy, 'chem': chem, 'bio': bio,
            'sci': sci, 'ekonomi': ekonomi, 'business': business, 
            'poa': poa, 'geo': geo, 'psv': psv
        }
        clean_grades = {k: v for k, v in new_grades.items() if v != t['opt_not_taken']}
        
        # Update User Object
        user['grades'] = clean_grades
        user['gender'] = gender
        
        # DB Update (Silent Background Save)
        if submitted:
            try:
                supabase.table("student_profiles").update({
                    "grades": clean_grades,
                    "gender": gender, # Note: DB schema might need gender text col or store in JSON
                    # "updated_at": "now()" <--- REMOVED
                }).eq("id", user['id']).execute()
                st.session_state['user'] = user # Update Local State
                st.toast("Profile Updated!")
            except Exception as e:
                st.error(f"Save Failed: {e}")

        # Run Engine
        student_obj = StudentProfile(clean_grades, gender, 'Warganegara', 'Tidak', 'Tidak')
        with st.spinner("Analyzing..."):
            st.session_state['dash'] = generate_dashboard_data(student_obj, df_courses, lang_code=lang_code)

    # --- MAIN CONTENT ---
    render_dashboard_content(st.session_state['dash'], t)

def render_dashboard_content(dash, t):
    st.title(t['header_title'])
    
    # Hero / Summary
    if dash['total_matches'] > 0:
        if 'hero_eligible_dynamic' in t:
            msg = t['hero_eligible_dynamic'].format(courses=dash.get('total_unique_courses', 0), locs=dash['total_matches'])
        else:
            msg = t['hero_success'].format(count=dash['total_matches'])
        st.success(msg)
        
        c1, c2, c3 = st.columns(3)
        c1.metric(t['inst_poly'], dash['summary_stats'].get('inst_poly', 0))
        c2.metric(t['inst_ikbn'], dash['summary_stats'].get('inst_ikbn', 0))
        c3.metric(t['inst_kk'], dash['summary_stats'].get('inst_kk', 0))
    else:
        st.error(t['hero_fail'])
        st.info(t['hero_tip'])
        return

    st.markdown("---")
    
    # Full Table Logic (Now always unlocked because you are logged in)
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
        
        # Filters
        c_filter1, c_filter2 = st.columns(2)
        cat_col = t['table_col_cat']
        cat_filter = c_filter1.multiselect(t['filter_label'], options=df_display[cat_col].unique(), default=df_display[cat_col].unique())
        state_opts = sorted([str(x) for x in df_display["state"].unique() if x])
        state_filter = c_filter2.multiselect(f"📍 {t.get('filter_state', 'Filter Location:')}", options=state_opts, default=state_opts)
        
        mask = (df_display[cat_col].isin(cat_filter)) & (df_display["state"].isin(state_filter))
        df_filtered = df_display[mask]
        
        st.dataframe(
            df_filtered[[t['table_col_course'], t['table_col_inst'], "state", "fees", t['table_col_cat'], t['table_col_status']]],
            use_container_width=True, hide_index=True, height=500
        )
        st.caption(t['filter_count'].format(shown=len(df_filtered), total=len(df_display)))

# --- 6. MAIN ROUTER ---
lang_code = st.sidebar.selectbox("🌐 Language", list(LANGUAGES.keys()), format_func=lambda x: LANGUAGES[x], key="lang_code")
t = get_text(lang_code)

if auth.check_session():
    # Logged In
    user = st.session_state['user']
    render_dashboard(user, t)
else:
    # Guest / Login
    render_landing(t)