import streamlit as st
import pandas as pd
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

with st.sidebar.form("grades_form"):

    # Core Subjects
    st.subheader(t['sb_core_subjects'])
    bm = st.selectbox(t['subj_bm'], grade_opts, index=7)
    eng = st.selectbox(t['subj_eng'], grade_opts, index=7)
    hist = st.selectbox(t['subj_hist'], grade_opts, index=7)
    math = st.selectbox(t['subj_math'], grade_opts, index=7)
    moral = st.selectbox(t['subj_moral'], grade_opts, index=7)
    
    # Science Stream
    with st.expander(t['sb_science_stream'], expanded=False):
        addmath = st.selectbox(t['subj_addmath'], grade_opts, index=0)
        phy = st.selectbox(t['subj_phy'], grade_opts, index=0)
        chem = st.selectbox(t['subj_chem'], grade_opts, index=0)
        bio = st.selectbox(t['subj_bio'], grade_opts, index=0)
    # Arts Stream
    with st.expander(t['sb_arts_stream'], expanded=False):
        sci = st.selectbox(t['subj_sci'], grade_opts, index=0)

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
    grades = {'bm': bm, 'eng': eng, 'hist': hist, 'math': math, 'sci': sci,
              'addmath': addmath, 'phy': phy, 'chem': chem, 'bio': bio}
    grades = {k: v for k, v in grades.items() if v != t['opt_not_taken']}
    # student = StudentProfile(grades, internal_gender, 'Warganegara', 'Tidak', 'Tidak')
    student = StudentProfile(grades, gender, 'Warganegara', 'Tidak', 'Tidak')
    st.session_state['current_student'] = student
    
    with st.spinner(t['spinner_msg']):
        time.sleep(0.5)
        st.session_state['dash'] = generate_dashboard_data(student, df_courses, lang_code=lang_code)

if 'dash' in st.session_state:
    dash = st.session_state['dash']
    if dash['total_matches'] > 0:
        st.success(t['hero_success'].format(count=dash['total_matches']))
        c1, c2, c3 = st.columns(3)
        c1.metric(t['stat_poly'], dash['summary_stats'].get('inst_poly', 0))
        c2.metric(t['stat_ikbn'], dash['summary_stats'].get('inst_ikbn', 0))
        c3.metric(t['stat_kk'], dash['summary_stats'].get('inst_kk', 0))
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
            with st.form("lead_capture"):
                c_name, c_phone = st.columns(2)
                name = c_name.text_input(t['form_name'])
                phone = c_phone.text_input(t['form_phone'])
                email = st.text_input(t['form_email'])
                if st.form_submit_button(f"🔓 {t['btn_unlock']}"):
                    if name and phone:
                        if save_profile(name, email, phone, st.session_state['current_student'], dash['total_matches']):
                            st.session_state['unlocked'] = True
                            st.toast(t['toast_success'])
                            st.rerun()
                    else: st.error(t['err_missing_info'])
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