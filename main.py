import streamlit as st
import pandas as pd
import time
from supabase import create_client, Client
from src.engine import StudentProfile
from src.dashboard import generate_dashboard_data
from src.translations import get_text, LANGUAGES
from src.quiz_manager import QuizManager
from src.auth import AuthManager

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Hala Tuju SPM", page_icon="🎓", layout="centered")

# --- 2. CONFIGURATION & SETUP ---
auth = None
quiz_manager = None
DB_CONNECTED = False

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    auth = AuthManager(supabase)
    quiz_manager = QuizManager()
    DB_CONNECTED = True
except Exception as e:
    st.error(f"🚨 Connection Error: {e}")
    DB_CONNECTED = False

# ... (Helper Functions) ...

# --- NEW: QUIZ PAGE RENDERER ---
def render_quiz_page(lang_code, user):
    st.title("🧭 Discovery Quiz")
    
    # Get Current Question
    q = quiz_manager.get_current_question(lang_code)
    total = quiz_manager.get_total_questions(lang_code)
    step = st.session_state['quiz_step']
    
    # Progress Bar
    progress = min(max(step / total, 0.0), 1.0) if total > 0 else 0
    st.progress(progress)
    
    if q:
        # Render Question Card
        with st.container():
            st.markdown(f"**Question {step + 1} of {total}**")
            st.markdown(f"### {q['prompt']}")
            st.markdown("") # Spacer
            
            # Render Options as large buttons
            for i, opt in enumerate(q['options']):
                # Use a unique key for every option/step combo
                if st.button(opt['text'], key=f"q{step}_opt{i}", use_container_width=True):
                    quiz_manager.handle_answer(opt)
                    st.rerun()
                    
            st.markdown("---")
            if step > 0:
                if st.button("⬅️ Back"):
                    quiz_manager.go_back()
                    st.rerun()
                    
    elif quiz_manager.is_complete(lang_code):
        # Quiz Complete Transition
        with st.spinner("Generating your fit..."):
            time.sleep(1.5)
            
        # Get Results
        results = quiz_manager.get_final_results()
        
        # Save to DB if User
        if user:
            try:
                success, msg = auth.save_quiz_results(user['id'], results['student_signals'])
                if success:
                    st.toast("Results Saved!")
                else:
                    st.error(f"Save Failed: {msg}")
            except Exception as e:
                st.error(f"Could not save results: {e}")
        
        # Display Results
        st.success("Analysis Complete!")
        st.json(results)
        
        # Save to Session
        st.session_state['student_signals'] = results['student_signals']
        
        if st.button("Return to Dashboard", use_container_width=True):
            st.session_state['view_mode'] = 'dashboard'
            st.rerun()

# --- SIDEBAR LOGIC ---
# ...
# Inside render_sidebar or main logic:

# ... (After Profile Button) ...
# ... (Main Router) ...

def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("assets/style.css")

@st.cache_data
def get_data():
    return load_master_data()

df_courses = get_data()

# --- 3. HELPER: GRADE RESTORATION ---
def get_grade_index(key, opts, user_grades):
    """
    Priority:
    1. Logged In User Data (DB)
    2. Session State (Guest Input)
    3. Default (7 / 'C' or 0 / 'Not Taken')
    """
    # 1. Check DB (User)
    if user_grades and key in user_grades:
         if user_grades[key] in opts: return opts.index(user_grades[key])
         
    # 2. Check Session (Guest)
    guest_grades = st.session_state.get('guest_grades', {})
    if key in guest_grades:
        if guest_grades[key] in opts: return opts.index(guest_grades[key])
        
    # 3. Defaults
    # Default to 0 (Not Taken) to avoid assuming "C" grades which skews results
    return 0



# --- 5. AUTH BLOCK (THE GATE) ---
def render_auth_gate(t, current_grades):
    st.markdown("---")
    st.warning(f"🔒 **{t['locked_cta_title']}**")
    st.write(t['locked_cta_desc'])
    
    st.write("Ready to see everything? Unlock your full report now.")
    
# --- 4. DATA MODEL HELPER ---
def render_grade_inputs(t, current_grades, key_suffix=""):
    grade_opts = [t["opt_not_taken"], "A+", "A", "A-", "B+", "B", "C+", "C", "D", "E", "G"]
    
    st.markdown(f"**{t['sb_core_subjects']}**")
    bm = st.selectbox(t['subj_bm'], grade_opts, index=get_grade_index('bm', grade_opts, current_grades), key=f"bm{key_suffix}")
    eng = st.selectbox(t['subj_eng'], grade_opts, index=get_grade_index('eng', grade_opts, current_grades), key=f"eng{key_suffix}")
    hist = st.selectbox(t['subj_hist'], grade_opts, index=get_grade_index('hist', grade_opts, current_grades), key=f"hist{key_suffix}")
    math = st.selectbox(t['subj_math'], grade_opts, index=get_grade_index('math', grade_opts, current_grades), key=f"math{key_suffix}")
    moral = st.selectbox(t['subj_moral'], grade_opts, index=get_grade_index('moral', grade_opts, current_grades), key=f"moral{key_suffix}")
    
    with st.expander(t['sb_science_stream'], expanded=False):
        addmath = st.selectbox(t['subj_addmath'], grade_opts, index=get_grade_index('addmath', grade_opts, current_grades), key=f"addmath{key_suffix}")
        phy = st.selectbox(t['subj_phy'], grade_opts, index=get_grade_index('phy', grade_opts, current_grades), key=f"phy{key_suffix}")
        chem = st.selectbox(t['subj_chem'], grade_opts, index=get_grade_index('chem', grade_opts, current_grades), key=f"chem{key_suffix}")
        bio = st.selectbox(t['subj_bio'], grade_opts, index=get_grade_index('bio', grade_opts, current_grades), key=f"bio{key_suffix}")
    
    with st.expander(t['sb_arts_stream'], expanded=False):
        sci = st.selectbox(t['subj_sci'], grade_opts, index=get_grade_index('sci', grade_opts, current_grades), key=f"sci{key_suffix}")
        ekonomi = st.selectbox(t['subj_ekonomi'], grade_opts, index=get_grade_index('ekonomi', grade_opts, current_grades), key=f"ekonomi{key_suffix}")
        business = st.selectbox(t['subj_business'], grade_opts, index=get_grade_index('business', grade_opts, current_grades), key=f"business{key_suffix}")
        poa = st.selectbox(t['subj_poa'], grade_opts, index=get_grade_index('poa', grade_opts, current_grades), key=f"poa{key_suffix}")
        geo = st.selectbox(t['subj_geo'], grade_opts, index=get_grade_index('geo', grade_opts, current_grades), key=f"geo{key_suffix}")
        psv = st.selectbox(t['subj_psv'], grade_opts, index=get_grade_index('psv', grade_opts, current_grades), key=f"psv{key_suffix}")

    return {
        'bm': bm, 'eng': eng, 'hist': hist, 'math': math, 'moral': moral,
        'addmath': addmath, 'phy': phy, 'chem': chem, 'bio': bio,
        'sci': sci, 'ekonomi': ekonomi, 'business': business, 
        'poa': poa, 'geo': geo, 'psv': psv
    }

# --- 5. AUTH BLOCK (THE GATE) ---
def render_auth_gate(t, current_grades):
    st.markdown("---")
    st.warning(f"🔒 **{t['locked_cta_title']}**")
    st.write(t['locked_cta_desc'])
    
    st.write("Ready to see everything? Unlock your full report now.")
    
    with st.form("reg_form"):
        st.write("Create a secure PIN to save your results.")
        r_name = st.text_input("Full Name", placeholder="Ali Bin Abu")
        r_phone = st.text_input("Phone Number", placeholder="e.g. 012-3456789")
        r_pin = st.text_input("Create 6-Digit PIN", type="password", max_chars=6, help="Remember this PIN!")
        
        if st.form_submit_button("Unlock & Save Results"):
            # Clean Grades first
            grade_map = {k: v for k, v in current_grades.items() if v != t['opt_not_taken']} if current_grades else {}
            
            success, val = auth.register_user(r_name, r_phone, r_pin, grades=grade_map)
            if success:
                st.success("Account Created! Unlocking...")
                time.sleep(1)
                st.rerun()
            else:
                st.error(val)

# --- 5b. PROFILE PAGE ---
def render_profile_page(user, t):
    st.title(f"👤 My Profile")
    
    with st.container():
        # Read-Only Section
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown(f"**Name:**\n\n{user.get('full_name', '-')}")
        with c2:
            st.markdown(f"**Phone:**\n\n{user.get('phone', '-')}")
            
        st.markdown("---")
        
        # Edit Form
        with st.expander("✏️ Edit Details"):
            with st.form("edit_profile"):
                new_name = st.text_input("Full Name", value=user.get('full_name', ''))
                
                if st.form_submit_button("Save Changes"):
                    success, msg = auth.update_profile(user['id'], {"full_name": new_name})
                    if success:
                        st.success(msg)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)

        # Edit Grades Form
        with st.expander("📝 Edit Grades"):
             with st.form("edit_grades"):
                 new_grades = render_grade_inputs(t, user.get('grades', {}), key_suffix="_p")
                 
                 if st.form_submit_button("Save Grades"):
                     clean_grades = {k: v for k, v in new_grades.items() if v != t['opt_not_taken']}
                     success, msg = auth.update_profile(user['id'], {"grades": clean_grades})
                     if success:
                         st.success(msg)
                         time.sleep(1)
                         st.rerun()
                     else:
                         st.error(msg)
    
    st.markdown("---")
    if st.button("⬅️ Back to Dashboard"):
        st.session_state['view_mode'] = 'dashboard'
        st.rerun()

# --- 5c. QUIZ PAGE ---
def render_quiz_page(lang_code, user):
    st.title("🧭 Discovery Quiz")
    
    # Get Current Question
    q = quiz_manager.get_current_question(lang_code)
    total = quiz_manager.get_total_questions(lang_code)
    step = st.session_state['quiz_step']
    
    # Progress Bar
    progress = min(max(step / total, 0.0), 1.0) if total > 0 else 0
    st.progress(progress)
    
    if q:
        # Render Question Card
        with st.container():
            st.markdown(f"**Question {step + 1} of {total}**")
            st.markdown(f"### {q['prompt']}")
            st.markdown("") # Spacer
            
            # Render Options as large buttons
            for i, opt in enumerate(q['options']):
                if st.button(opt['text'], key=f"q{step}_opt{i}", use_container_width=True):
                    quiz_manager.handle_answer(opt)
                    st.rerun()
                    
            st.markdown("---")
            if step > 0:
                if st.button("⬅️ Back"):
                    quiz_manager.go_back()
                    st.rerun()
                    
    elif quiz_manager.is_complete(lang_code):
        # Quiz Complete Transition
        with st.spinner("Generating your fit..."):
            time.sleep(1.5)
            
        # Get Results
        results = quiz_manager.get_final_results()
        
        # Save to DB if User
        if user:
            try:
                auth.save_quiz_results(user['id'], results['student_signals'])
                st.toast("Results Saved!")
            except Exception as e:
                st.error(f"Could not save results: {e}")
        
        # Display Results
        st.success("Analysis Complete!")
        st.json(results)
        
        if st.button("Return to Dashboard", use_container_width=True):
            st.session_state['view_mode'] = 'dashboard'
            st.rerun()

# --- 6. MAIN ROUTER ---

# Init Session
lang_code = st.sidebar.selectbox("🌐 Language", list(LANGUAGES.keys()), format_func=lambda x: LANGUAGES[x], key="lang_code")
t = get_text(lang_code)

auth_status = auth.check_session()
user = st.session_state['user'] if auth_status else None

# Render Sidebar
st.sidebar.title(f"📝 {t['sb_title']}")

# User Badge & Profile Nav
if user:
    st.sidebar.success(f"👤 {user.get('full_name', 'Student')}")
    
    # Profile Navigation
    if st.sidebar.button("👤 My Profile", use_container_width=True):
        st.session_state['view_mode'] = 'profile'
        st.rerun()
        
    if st.sidebar.button("Log Out", use_container_width=True):
        auth.logout()

    # Quiz Button (Logged In Users Only)
    st.sidebar.markdown("---")
    if st.sidebar.button("🧭 Start Discovery Quiz", use_container_width=True):
        quiz_manager.reset_quiz()
        st.session_state['view_mode'] = 'quiz'
        st.rerun()

if not user:
    st.sidebar.info("👋 Guest Mode")
    with st.sidebar.expander("🔐 **Returning Users**"):
            l_phone = st.text_input("Phone", key="sb_phone")
            l_pin = st.text_input("PIN", type="password", key="sb_pin")
            if st.button("Login", key="sb_login"):
                success, val = auth.login_user(l_phone, l_pin)
                if success:
                    st.toast(f"Welcome back!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(val)

st.sidebar.markdown("---")

# Rest of Sidebar Logic
# GUEST ONLY: Check Eligibility Form
if not user:
    # Grades Logic
    grade_opts = [t["opt_not_taken"], "A+", "A", "A-", "B+", "B", "C+", "C", "D", "E", "G"]
    # Fallback/Session grades
    guest_grades = st.session_state.get('guest_grades', {}) 
    
    with st.sidebar.form("grades_form"):
        st.subheader(t['sb_core_subjects'])
        # Use Helper
        raw_grades = render_grade_inputs(t, guest_grades, key_suffix="_sb")

        gender = st.radio(t["sb_gender"], [t["gender_male"], t["gender_female"]])
        submitted = st.form_submit_button(f"🚀 {t['sb_btn_submit']}")
        
        # Return collected inputs
        sidebar_outputs = (submitted, raw_grades, gender)
else:
    # User is logged in, use their saved data
    # No sidebar form. Data comes from user profile.
    sidebar_outputs = (False, user.get('grades', {}), user.get('gender', 'Male'))

submitted, raw_grades, gender = sidebar_outputs

# --- ROUTER LOGIC ---
view_mode = st.session_state.get('view_mode', 'dashboard')

if view_mode == 'profile' and user:
    render_profile_page(user, t)
    st.stop() # Stop here, don't render dashboard below
    
if view_mode == 'quiz':
    render_quiz_page(lang_code, user)
    st.stop()

# --- DASHBOARD LOGIC (Below) ---
# Calculation Logic...
# Run if: 
# 1. Submitted (User clicked button)
# 2. Dash missing (First load)
# 3. User logged in BUT calculation hash/check hasn't happened for this user yet
force_calc = False
if user and 'last_calc_user' not in st.session_state:
    force_calc = True
    st.session_state['last_calc_user'] = user['id']
elif user and st.session_state.get('last_calc_user') != user['id']:
    force_calc = True
    st.session_state['last_calc_user'] = user['id']

if submitted or 'dash' not in st.session_state or force_calc:
    cleaned_grades = raw_grades # Debugging alias
    
    # Store in Session for Guest persistence (in case they reload or submit again)
    clean_grades = {k: v for k, v in raw_grades.items() if v != t['opt_not_taken']}  
    st.session_state['guest_grades'] = clean_grades 
    
    # If Logged In, AUTO-SAVE to DB
    if user and submitted:
        try:
            # Update DB
            data_payload = {
                "grades": clean_grades,
                "gender": gender,
                "last_login": "now()" # Update activity
            }
            
            # Execute Update
            res = supabase.table("student_profiles").update(data_payload).eq("id", user['id']).execute()
            
            # Update Local Session User
            user['grades'] = clean_grades
            user['gender'] = gender
            
            st.toast("Profile Saved Successfully!")
        except Exception as e:
            st.error(f"Save Failed: {str(e)}")

    # Run Engine
    student_obj = StudentProfile(clean_grades, gender, 'Warganegara', 'Tidak', 'Tidak')
    # with st.spinner("Analyzing..."): # Removed to prevent freeze
    st.session_state['dash'] = generate_dashboard_data(student_obj, df_courses, lang_code=lang_code)

dash = st.session_state.get('dash')

# --- RENDER MAIN CONTENT ---
st.title(t['header_title'])

if not dash or dash['total_matches'] == 0:
    st.info(t['landing_msg'])
    st.stop()

# 1. Summary Metrics (Always Valid)
if 'hero_eligible_dynamic' in t:
    msg = t['hero_eligible_dynamic'].format(courses=dash.get('total_unique_courses', 0), locs=dash['total_matches'])
else:
    msg = t['hero_success'].format(count=dash['total_matches'])
st.success(msg)

c1, c2, c3 = st.columns(3)
c1.metric(t['inst_poly'], dash['summary_stats'].get('inst_poly', 0))
c2.metric(t['inst_ikbn'], dash['summary_stats'].get('inst_ikbn', 0))
c3.metric(t['inst_kk'], dash['summary_stats'].get('inst_kk', 0))

# 2. Featured Matches (Teaser - Limit 3)
st.subheader("🌟 Featured Matches")
for i, pick in enumerate(dash['featured_matches'][:3]): # Limit to 3
    display_title = pick.get('headline') or pick['course_name']
    with st.expander(f"#{i+1}: {display_title}", expanded=True):
        if pick.get('synopsis'): st.info(pick['synopsis'])
        if pick.get('jobs'): st.markdown(f"**💼 Career:** {', '.join(pick['jobs'])}")
        st.markdown(f"**🏫 {pick['institution']}**")
        
        # Badge Logic
        st.markdown(f"""
        <div class="badge-container">
            <div class="badge-base badge-time">⏱️ <b>Duration:</b><br>{pick.get('duration', '-')}</div>
            <div class="badge-base badge-mode">🛠️ <b>Mode:</b><br>{pick.get('type', 'Full-time')}</div>
            <div class="badge-base badge-money">💰 <b>Fees:</b><br>{pick.get('fees', '-')}</div>
        </div>
        """, unsafe_allow_html=True)

# 3. GATED CONTENT
if auth_status:
    # --- UNLOCKED VIEW ---
    st.markdown("---")
    st.subheader(t['table_title'])
    st.info(t['unlocked_alert'])
    
    all_courses = dash.get('full_list', [])
    if all_courses:
        df_display = pd.DataFrame(all_courses)
        df_display = df_display.rename(columns={
            "course_name": t['table_col_course'],
            "institution": t['table_col_inst'],
            "type": t['table_col_cat'],
            "quality": t['table_col_status']
        })
        
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
else:
    # --- LOCKED VIEW ---
    render_auth_gate(t, raw_grades)

# Footer
st.markdown("---")
with st.expander(t['about_title']):
    st.markdown(t['about_desc'])