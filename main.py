import streamlit as st
import pandas as pd
import os
import time
from supabase import create_client, Client
from src.engine import StudentProfile, load_and_clean_data
from src.dashboard import generate_dashboard_data
from src.translations import get_text, LANGUAGES

# --- 1. CONFIGURATION & SECRETS ---
st.set_page_config(page_title="Hala Tuju SPM", page_icon="🎓", layout="centered")

# Custom CSS
st.markdown("""
<style>
    .locked-blur { filter: blur(5px); opacity: 0.6; pointer-events: none; user-select: none; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

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
    project_root = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(project_root, 'data')
    dfs = []
    for f in ['requirements.csv', 'tvet_requirements.csv']:
        path = os.path.join(data_folder, f)
        if os.path.exists(path):
            try:
                dfs.append(load_and_clean_data(path))
            except: pass
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

df_courses = get_data()

# --- 3. HELPER: SAVE TO DB ---
def save_profile(name, email, phone, student, eligible_count):
    if not DB_CONNECTED: return False
    data = {
        "name": name, "email": email, "phone": phone, "gender": student.gender,
        "grades": student.grades, "eligible_count": eligible_count
    }
    try:
        supabase.table("student_profiles").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# --- 4. SIDEBAR (With Language Selector) ---
# Language Switcher
lang_code = st.sidebar.selectbox(
    "🌐 Language / Bahasa / மொழி", 
    options=list(LANGUAGES.keys()), 
    format_func=lambda x: LANGUAGES[x]
)
t = get_text(lang_code)  # Load the correct dictionary

st.sidebar.title(f"📝 {t['sb_title']}")
st.sidebar.caption(t['sb_caption'])

grade_opts = ["A+", "A", "A-", "B+", "B", "C+", "C", "D", "E", "G", "Tidak Ambil"]

with st.sidebar.form("grades_form"):
    bm = st.selectbox("Bahasa Melayu", grade_opts, index=5)
    eng = st.selectbox("Bahasa Inggeris", grade_opts, index=5)
    hist = st.selectbox("Sejarah", grade_opts, index=6)
    math = st.selectbox("Matematik", grade_opts, index=5)
    sci = st.selectbox("Sains", grade_opts, index=5)
    
    st.markdown("---")
    st.caption(t['sb_opt_subject'])
    addmath = st.selectbox("Matematik Tambahan", ["Tidak Ambil"] + grade_opts, index=0)
    phy = st.selectbox("Fizik", ["Tidak Ambil"] + grade_opts, index=0)
    chem = st.selectbox("Kimia", ["Tidak Ambil"] + grade_opts, index=0)
    bio = st.selectbox("Biologi", ["Tidak Ambil"] + grade_opts, index=0)
    
    gender = st.radio(t['sb_gender'], ["Lelaki", "Perempuan"], horizontal=True)
    
    submitted = st.form_submit_button(f"🚀 {t['sb_btn_submit']}")

# --- 5. MAIN PAGE ---
st.title(t['header_title'])
st.write(t['header_subtitle'])

# Initialize Session State
if 'unlocked' not in st.session_state:
    st.session_state['unlocked'] = False

if submitted:
    st.session_state['unlocked'] = False
    grades = {'bm': bm, 'eng': eng, 'hist': hist, 'math': math, 'sci': sci,
              'addmath': addmath, 'phy': phy, 'chem': chem, 'bio': bio}
    grades = {k: v for k, v in grades.items() if v != "Tidak Ambil"}
    
    student = StudentProfile(grades, gender, 'Warganegara', 'Tidak', 'Tidak')
    st.session_state['current_student'] = student
    
    with st.spinner(t['spinner_msg']):
        time.sleep(0.5)
        st.session_state['dash'] = generate_dashboard_data(student, df_courses)

# Display Logic
if 'dash' in st.session_state:
    dash = st.session_state['dash']
    
    if dash['total_matches'] > 0:
        # Hero
        st.success(t['hero_success'].format(count=dash['total_matches']))
        
        # Stats
        c1, c2, c3 = st.columns(3)
        c1.metric(t['stat_poly'], dash['summary_stats'].get('Politeknik', 0))
        c2.metric(t['stat_ikbn'], dash['summary_stats'].get('IKBN / ILP (Skills)', 0))
        c3.metric(t['stat_kk'], dash['summary_stats'].get('Kolej Komuniti', 0))
        
        st.markdown("---")
        
        # IF UNLOCKED: Show Everything
        if st.session_state['unlocked']:
            st.info(t['unlocked_alert'])
            st.subheader(t['table_title'])
            
            all_courses = dash.get('full_list', [])
            if all_courses:
                df_display = pd.DataFrame(all_courses)
                
                # Dynamic Column Rename based on Language
                df_display = df_display.rename(columns={
                    "course_name": t['table_col_course'],
                    "institution": t['table_col_inst'],
                    "type": t['table_col_cat'],
                    "quality": t['table_col_status']
                })
                
                cat_col = t['table_col_cat']
                cat_filter = st.multiselect(
                    t['filter_label'],
                    options=df_display[cat_col].unique(),
                    default=df_display[cat_col].unique()
                )
                
                df_filtered = df_display[df_display[cat_col].isin(cat_filter)]
                
                st.dataframe(
                    df_filtered[[t['table_col_course'], t['table_col_inst'], t['table_col_cat'], t['table_col_status']]],
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )
                st.caption(t['filter_count'].format(shown=len(df_filtered), total=len(df_display)))
                st.write(t['contact_counselor'])
                
        else:
            # LOCKED VIEW (Teaser)
            st.subheader(t['teaser_title'])
            st.write(t['teaser_subtitle'])
            
            for i, pick in enumerate(dash['featured_matches']):
                with st.expander(f"#{i+1}: {pick['course_name']} ({pick['quality']})", expanded=True):
                    st.write(f"🏫 **{pick['institution']}**")
                    st.caption(f"{pick['type']}")
                    if st.button(t['btn_save_course'], key=f"save_{i}"):
                         st.toast(t['btn_saved_toast'].format(course=pick['course_name']))

            st.markdown("---")
            remaining = dash['total_matches'] - 3
            st.write(t['locked_count'].format(remaining=remaining))
            
            # The Gatekeeper Form
            st.warning(f"🔒 **{t['locked_cta_title']}**")
            st.write(t['locked_cta_desc'])
            
            with st.form("lead_capture"):
                c_name, c_phone = st.columns(2)
                name = c_name.text_input(t['form_name'])
                phone = c_phone.text_input(t['form_phone'])
                email = st.text_input(t['form_email'])
                
                confirm = st.form_submit_button(f"🔓 {t['btn_unlock']}")
                
                if confirm:
                    if name and phone:
                        saved = save_profile(name, email, phone, st.session_state['current_student'], dash['total_matches'])
                        if saved:
                            st.session_state['unlocked'] = True
                            st.toast(t['toast_success'])
                            st.rerun()
                    else:
                        st.error(t['err_missing_info'])

    else:
        st.error(t['hero_fail'])
        st.info(t['hero_tip'])

else:
    st.info(t['landing_msg'])