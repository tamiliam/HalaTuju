import streamlit as st
import pandas as pd
import time
from supabase import create_client, Client
from src.engine import StudentProfile
from src.dashboard import generate_dashboard_data, group_courses_by_id
from src.ranking_engine import get_ranked_results, TAG_COUNT
from src.translations import get_text, LANGUAGES
from src.quiz_manager import QuizManager
from src.auth import AuthManager
from src.data_manager import load_master_data

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
    t = get_text(lang_code)
    st.title(t['quiz_title'])
    
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
            st.markdown(f"**{t['quiz_question_count'].format(step=step+1, total=total)}**")
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
                if st.button(t['btn_back']):
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
                    st.toast(t['quiz_saved'])
                    
                    # CRITICAL: Clear volatile quiz scores after saving to DB
                    if 'quiz_scores' in st.session_state:
                        del st.session_state['quiz_scores']
                else:
                    st.error(f"Save Failed: {msg}")
            except Exception as e:
                st.error(f"Could not save results: {e}")
        
        # Display Results
        st.success(t['quiz_complete'])
        st.json(results)
        
        # Save to Session
        st.session_state['student_signals'] = results['student_signals']
        
        if st.button(t['quiz_return'], use_container_width=True):
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
    
    # 1. CORE
    st.markdown(f"**{t['sb_core_subjects']}**")
    bm = st.selectbox(t['subj_bm'], grade_opts, index=get_grade_index('bm', grade_opts, current_grades), key=f"bm{key_suffix}")
    eng = st.selectbox(t['subj_eng'], grade_opts, index=get_grade_index('eng', grade_opts, current_grades), key=f"eng{key_suffix}")
    hist = st.selectbox(t['subj_hist'], grade_opts, index=get_grade_index('hist', grade_opts, current_grades), key=f"hist{key_suffix}")
    math = st.selectbox(t['subj_math'], grade_opts, index=get_grade_index('math', grade_opts, current_grades), key=f"math{key_suffix}")
    moral = st.selectbox(t['subj_moral'], grade_opts, index=get_grade_index('moral', grade_opts, current_grades), key=f"moral{key_suffix}")
    
    # 2. SCIENCE STREAM
    with st.expander(t['sb_science_stream'], expanded=False):
        addmath = st.selectbox(t['subj_addmath'], grade_opts, index=get_grade_index('addmath', grade_opts, current_grades), key=f"addmath{key_suffix}")
        phy = st.selectbox(t['subj_phy'], grade_opts, index=get_grade_index('phy', grade_opts, current_grades), key=f"phy{key_suffix}")
        chem = st.selectbox(t['subj_chem'], grade_opts, index=get_grade_index('chem', grade_opts, current_grades), key=f"chem{key_suffix}")
        bio = st.selectbox(t['subj_bio'], grade_opts, index=get_grade_index('bio', grade_opts, current_grades), key=f"bio{key_suffix}")
    
    # 3. COMMERCE STREAM
    with st.expander(t['sb_commerce_stream'], expanded=False):
        sci = st.selectbox(t['subj_sci'], grade_opts, index=get_grade_index('sci', grade_opts, current_grades), key=f"sci{key_suffix}")
        ekonomi = st.selectbox(t['subj_ekonomi'], grade_opts, index=get_grade_index('ekonomi', grade_opts, current_grades), key=f"ekonomi{key_suffix}")
        poa = st.selectbox(t['subj_poa'], grade_opts, index=get_grade_index('poa', grade_opts, current_grades), key=f"poa{key_suffix}")
        business = st.selectbox(t['subj_business'], grade_opts, index=get_grade_index('business', grade_opts, current_grades), key=f"business{key_suffix}")
        geo = st.selectbox(t['subj_geo'], grade_opts, index=get_grade_index('geo', grade_opts, current_grades), key=f"geo{key_suffix}")

    # 4. ARTS & LANG ELECTIVES
    with st.expander(t['sb_arts_electives'], expanded=False):
        lang3 = st.selectbox(t['subj_3rd_lang'], grade_opts, index=get_grade_index('lang3', grade_opts, current_grades), key=f"3l{key_suffix}")
        lit = st.selectbox(t['subj_lit'], grade_opts, index=get_grade_index('lit', grade_opts, current_grades), key=f"lit{key_suffix}")
        psv = st.selectbox(t['subj_psv'], grade_opts, index=get_grade_index('psv', grade_opts, current_grades), key=f"psv{key_suffix}")

    # 5. TECHNICAL & VOCATIONAL
    with st.expander(t['sb_tech_voc_stream'], expanded=False):
        tech = st.selectbox(t['subj_tech'], grade_opts, index=get_grade_index('tech', grade_opts, current_grades), key=f"tech{key_suffix}")
        voc = st.selectbox(t['subj_voc'], grade_opts, index=get_grade_index('voc', grade_opts, current_grades), key=f"voc{key_suffix}")

    return {
        'bm': bm, 'eng': eng, 'hist': hist, 'math': math, 'moral': moral, 'sci': sci,
        'addmath': addmath, 'phy': phy, 'chem': chem, 'bio': bio,
        'ekonomi': ekonomi, 'poa': poa, 'business': business, 'geo': geo,
        'lang3': lang3, 'lit': lit, 'psv': psv,
        'tech': tech, 'voc': voc
    }

# --- 5. AUTH BLOCK (THE GATE) ---
def render_auth_gate(t, current_grades, gender, cb, disability):
    st.markdown("---")
    st.warning(f"🔒 **{t['locked_cta_title']}**")
    st.write(t['gate_subtitle'])
    
    st.write("Ready to see everything? Unlock your full report now.")
    
    with st.form("reg_form"):
        st.write(t['gate_pin_instr'])
        r_name = st.text_input(t['profile_name'], placeholder="Ali Bin Abu")
        r_phone = st.text_input(t['profile_phone'], placeholder="e.g. 012-3456789")
        r_pin = st.text_input(t['lbl_create_pin'], type="password", max_chars=6, help=t['help_pin'])
        
        if st.form_submit_button(t['btn_unlock_save']):
            # Clean Grades first
            grade_map = {k: v for k, v in current_grades.items() if v != t['opt_not_taken']} if current_grades else {}
            
            success, val = auth.register_user(r_name, r_phone, r_pin, grades=grade_map, gender=gender, colorblind=cb, disability=disability)
            if success:
                st.success(t['msg_account_created'])
                time.sleep(1)
                st.rerun()
            else:
                st.error(val)

# ... (skip to main logic)



# --- 5b. PROFILE PAGE ---
def render_profile_page(user, t):
    st.title(t['profile_title'])
    
    with st.container():
        # Read-Only Section
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown(f"**{t['profile_name']}:**\n\n{user.get('full_name', '-')}")
        with c2:
            st.markdown(f"**{t['profile_phone']}:**\n\n{user.get('phone', '-')}")
            
        st.markdown("---")
        
        # Edit Form
        with st.expander(t['header_edit_details']):
            with st.form("edit_profile"):
                new_name = st.text_input(t['lbl_fullname'], value=user.get('full_name', ''))
                new_gender = st.radio(t['lbl_gender'], [t["gender_male"], t["gender_female"]], index=0 if user.get('gender') == "Male" else 1, horizontal=True)
                
                # Health
                # Map stored value (Tidak/Ya) to index
                cb_val = user.get('colorblind', t['opt_no'])
                # Handle language mismatch by checking if value is known 'Yes' or 'No', otherwise default 0
                cb_idx = 1 if cb_val == t['opt_yes'] or cb_val == 'Ya' or cb_val == 'Yes' or cb_val == 'ஆம்' else 0
                new_cb = st.radio(t['lbl_colorblind'], [t['opt_no'], t['opt_yes']], index=cb_idx, key="p_cb", horizontal=True)
                
                dis_val = user.get('disability', t['opt_no'])
                dis_idx = 1 if dis_val == t['opt_yes'] or dis_val == 'Ya' or dis_val == 'Yes' or dis_val == 'ஆம்' else 0
                new_dis = st.radio(t['lbl_disability'], [t['opt_no'], t['opt_yes']], index=dis_idx, key="p_dis", horizontal=True)
                
                if st.form_submit_button(t['btn_save_changes']):
                    success, msg = auth.update_profile(user['id'], {
                        "full_name": new_name, 
                        "gender": new_gender,
                        "colorblind": new_cb,
                        "disability": new_dis
                    })
                    if success:
                        st.success(msg)
                        # Invalid Cache to force refresh
                        if 'dash' in st.session_state: del st.session_state['dash']
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)

        # Edit Grades Form
        with st.expander(t['header_edit_grades']):
             with st.form("edit_grades"):
                 new_grades = render_grade_inputs(t, user.get('grades', {}), key_suffix="_p")
                 
                 if st.form_submit_button(t['btn_save_grades']):
                     clean_grades = {k: v for k, v in new_grades.items() if v != t['opt_not_taken']}
                     success, msg = auth.update_profile(user['id'], {"grades": clean_grades})
                     if success:
                         st.success(msg)
                         # Invalid Cache to force refresh
                         if 'dash' in st.session_state: del st.session_state['dash']
                         time.sleep(1)
                         st.rerun()
                     else:
                         st.error(msg)
    
    st.markdown("---")
    st.markdown("---")
    if st.button(t['btn_back_dash']):
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
                
                # CRITICAL: Clear volatile quiz scores after saving to DB
                # This prevents stale scores from overriding DB signals on refresh
                if 'quiz_scores' in st.session_state:
                    del st.session_state['quiz_scores']
                    
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
if 'lang_code' not in st.session_state:
    st.session_state['lang_code'] = 'en'
    
current_lang = st.session_state['lang_code']
t_temp = get_text(current_lang)

lang_code = st.sidebar.selectbox(t_temp['sb_lang'], list(LANGUAGES.keys()), format_func=lambda x: LANGUAGES[x], key="lang_code")
t = get_text(lang_code)

auth_status = auth.check_session()
user = st.session_state['user'] if auth_status else None

# DEBUG: Check if user has signals in DB
if user:
    has_signals_in_db = bool(user.get('student_signals'))
    has_signals_in_session = 'student_signals' in st.session_state
    st.warning(f"🔍 DEBUG - User Found | DB Signals: {has_signals_in_db} | Session Signals: {has_signals_in_session}")
    if has_signals_in_db and user.get('student_signals'):
        st.write(f"DB Signal Keys: {list(user.get('student_signals', {}).keys())}")
else:
    st.error("🔍 DEBUG - No User Found")

# IMMEDIATE RESTORATION: If user just logged in (cookie found), restore signals NOW
if user and 'student_signals' not in st.session_state and user.get('student_signals'):
    st.session_state['student_signals'] = user.get('student_signals')
    st.success("🔄 Early Restoration Triggered - Rerunning...")
    # Force Rerun to ensure the whole script sees the signals (prevents "flicker" of unranked state)
    st.rerun()

# Render Sidebar
st.sidebar.title(f"📝 {t['sb_title']}")

# User Badge & Profile Nav
if user:
    st.sidebar.success(f"👤 {user.get('full_name', 'Student')}")
    
    # Profile Navigation
    if st.sidebar.button(t['profile_title'], use_container_width=True):
        st.session_state['view_mode'] = 'profile'
        st.rerun()
        
    if st.sidebar.button(t['sb_logout'], use_container_width=True):
        auth.logout()

    # Quiz Button (Logged In Users Only)
    st.sidebar.markdown("---")
    
    # Determine Label
    has_results = bool(user.get('student_signals'))
    quiz_btn_label = t['sb_retake_quiz'] if has_results else t['sb_start_quiz']
    
    if st.sidebar.button(quiz_btn_label, use_container_width=True):
        quiz_manager.reset_quiz()
        st.session_state['view_mode'] = 'quiz'
        st.rerun()

if not user:
    st.sidebar.info(t['sb_guest_mode'])
    with st.sidebar.expander(t['sb_returning_user']):
            l_phone = st.text_input(t['profile_phone'], key="sb_phone")
            l_pin = st.text_input("PIN", type="password", key="sb_pin")
            if st.button(t['sb_login'], key="sb_login"):
                success, val = auth.login_user(l_phone, l_pin)
                if success:
                    st.toast(t['sb_welcome'])
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
        # st.subheader(t['sb_core_subjects']) # REMOVED DUPLICATE
        # Use Helper
        raw_grades = render_grade_inputs(t, guest_grades, key_suffix="_sb")


        gender = st.radio(t["sb_gender"], [t["gender_male"], t["gender_female"]], horizontal=True)
        
        # Health Checks
        cb = st.radio(t['sb_colorblind'], [t['opt_no'], t['opt_yes']], index=0, key="sb_cb", horizontal=True)
        st.markdown(f"[{t['link_cb_test']}]({t['cb_test_url']})")
        
        disability = st.radio(t['sb_disability'], [t['opt_no'], t['opt_yes']], index=0, key="sb_dis", horizontal=True)

        st.markdown("---")
        submitted = st.form_submit_button(f"🚀 {t['sb_btn_submit']}")
        
        # Return collected inputs
        sidebar_outputs = (submitted, raw_grades, gender, cb, disability)
else:
    # User is logged in, use their saved data
    # No sidebar form. Data comes from user profile.
    # Default to 'Tidak' if not set
    sidebar_outputs = (False, user.get('grades', {}), user.get('gender', 'Male'), user.get('colorblind', 'Tidak'), user.get('disability', 'Tidak'))

submitted, raw_grades, gender, cb, disability = sidebar_outputs

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

if submitted or (user and ('dash' not in st.session_state or force_calc)):
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
                "colorblind": cb,
                "disability": disability,
                "last_login": "now()" # Update activity
            }
            
            # Execute Update
            res = supabase.table("student_profiles").update(data_payload).eq("id", user['id']).execute()
            
            # Update Local Session User
            user['grades'] = clean_grades
            user['gender'] = gender
            user['colorblind'] = cb
            user['disability'] = disability
            
            st.toast(t['toast_profile_saved'])
        except Exception as e:
            st.error(t['err_save_failed'].format(error=str(e)))

    # Determine other_tech/voc flags
    # We consider it "True" if the student has attempted (or passed? Engine checks boolean).
    # Usually "Technical Stream" implies taking the subject.
    # Let's say if they have a grade better than 'Not Taken', it counts as being in that stream? 
    # Or should we require a Pass? Engine.py checks "req['pass_stv']" -> "cond = has_pass(all_sci) or has_pass(tech_subjs) or student.other_voc".
    # So if we map 'tech'/'voc' grades to 'other_tech'/'other_voc' flags, let's treat "Pass" as the trigger for safety.
    from src.engine import is_pass # Ensure import if needed, or re-implement simplistic check
    PASS_SET = {"A+", "A", "A-", "B+", "B", "C+", "C", "D", "E"} # Local check
    
    is_tech = clean_grades.get('tech') in PASS_SET
    is_voc = clean_grades.get('voc') in PASS_SET

    # Normalization for Engine (Expects 'Tidak' for healthy)
    def normalize_no(val):
        if val in ['Tidak', 'No', 'இல்லை', 'False', 0]: return 'Tidak'
        return 'Ya'

    norm_cb = normalize_no(cb)
    norm_dis = normalize_no(disability)

    # Run Engine
    student_obj = StudentProfile(clean_grades, gender, 'Warganegara', norm_cb, norm_dis, other_tech=is_tech, other_voc=is_voc)
    # with st.spinner("Analyzing..."): # Removed to prevent freeze
    st.session_state['dash'] = generate_dashboard_data(student_obj, df_courses, lang_code=lang_code)
    
    # --- NEW: APPLY RANKING IF QUIZ RESULTS EXIST ---
    # ... (skipping render code) ...


# --- 6. RANKING LOGIC (ROBUST FIX) ---
dash = st.session_state.get('dash')
signals = None  # 1. Initialize to avoid UnboundLocalError

# DEBUG: Track state
st.warning(f"🔍 RANK CHECK - Dash exists: {dash is not None}, Quiz scores in session: {'quiz_scores' in st.session_state}")

# 2. Resolve Signals (Priority: Session > Quiz Manager > User DB)
# Check Quiz Manager first (Most fresh)
if 'quiz_scores' in st.session_state:
    try:
        # Re-derive signals from raw quiz scores
        results = quiz_manager.get_final_results()
        signals = results.get('student_signals')
        st.session_state['student_signals'] = signals
        st.info("✅ Signals from Quiz Manager")
    except Exception as e:
        print(f"Error regenerating signals: {e}")

# If still no signals, check Session Storage directly
if not signals and 'student_signals' in st.session_state:
    signals = st.session_state['student_signals']
    st.info("✅ Signals from Session Storage")

# If still no signals, check User DB (Persistence)
if not signals and user and user.get('student_signals'):
    signals = user['student_signals']
    st.session_state['student_signals'] = signals # Restore to session
    st.info("✅ Signals from User DB (Restored)")

# DEBUG: Final state
if signals:
    st.success(f"🎯 SIGNALS READY - Categories: {list(signals.keys())}")
else:
    st.error("❌ NO SIGNALS AVAILABLE")

# 3. Execute Ranking
# We run this if we have Dashboard Data AND Signals
if dash and signals:
    st.info("🚀 EXECUTING RANKING...")
    # Validation
    if not isinstance(signals, dict):
        print(f"CRITICAL: Signals corrupted. Resetting.")
        signals = {}
    
    try:
        # Perform Ranking
        ranked = get_ranked_results(dash['full_list'], signals)
        
        # Update Dashboard Data
        dash['featured_matches'] = ranked['top_5']
        dash['full_list'] = ranked['top_5'] + ranked['rest']
        dash['is_ranked'] = True
        
        # Persist Update
        st.session_state['dash'] = dash
        
        # DEBUG: Show top score
        if ranked['top_5']:
            top_score = ranked['top_5'][0].get('fit_score', 'N/A')
            top_name = ranked['top_5'][0].get('course_name', 'Unknown')
            st.success(f"✅ RANKING APPLIED - Top: {top_name} (Score: {top_score})")
        
    except Exception as e:
        st.error(f"RANKING ERROR: {e}")
        print(f"RANKING ERROR: {e}")
        # Fallback: Don't crash app, just show default list
elif not dash:
    st.error("❌ RANKING SKIPPED - No Dashboard Data")
elif not signals:
    st.error("❌ RANKING SKIPPED - No Signals")
else:
    st.error("❌ RANKING SKIPPED - Unknown Reason")



if auth_status:
    # --- UNLOCKED VIEW ---
    st.markdown("---")
    # ...


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
# 2. Featured Matches (Teaser - Dynamic Limit)
# --- TIERED DISPLAY LOGIC ---
    # 1. Group all eligible courses
    # Note: We group the ENTIRE eligible list, not just top 5, to get the full picture.
    # The 'ranked' result has split top_5/rest, but for grouping we want to re-merge and group properly.
all_ranked = sorted(dash['full_list'], key=lambda x: int(x.get('fit_score', 0)), reverse=True)
grouped_courses = group_courses_by_id(all_ranked)

# 2. Slice Tiers
tier1_featured = grouped_courses[:5]
tier2_good = grouped_courses[5:25]
tier3_rest = grouped_courses[25:]

# --- RENDER TIER 1: FEATURED MATCHES ---
st.markdown(f"### :star: {t.get('lbl_featured', 'Featured Matches')}")

for pick in tier1_featured:
    # Display Title with Score
    display_title = f"{pick['course_name']} [Score: {pick['max_score']}]"
    
    with st.expander(display_title, expanded=True):
        # REASONS
        if pick.get('fit_reasons'):
            reason_text = " ".join(pick['fit_reasons'])
            st.markdown(f"**Why:** {reason_text}")
        
        # DESCRIPTION
        if pick.get('headline'):
            st.markdown(f"*{pick['headline']}*")
        if pick.get('synopsis'):
            st.markdown(pick['synopsis'])
        if pick.get('jobs'):
            st.markdown(f"💼 **Career:** {', '.join(pick['jobs'])}")
            
        # LOCATIONS (Nested Table)
        loc_count = len(pick['locations'])
        st.markdown(f"**Available at {loc_count} Location{'s' if loc_count>1 else ''}:**")
        
        # Simple dataframe for cleaner look than raw JSON
        import pandas as pd
        df_loc = pd.DataFrame(pick['locations'])
        # Filter/Rename cols for display
        if not df_loc.empty:
            df_view = df_loc[['institution_name', 'state', 'fees']].rename(columns={
                'institution_name': 'Institution', 
                'state': 'State', 
                'fees': 'Fees'
            })
            st.dataframe(df_view, hide_index=True, use_container_width=True)

# --- RENDER TIER 2: GOOD OPTIONS ---
if tier2_good:
    st.markdown("---")
    st.subheader("👍 Worth Considering")
    for pick in tier2_good:
         # Compact Card
        display_title = f"{pick['course_name']} [Score: {pick['max_score']}]"
        with st.expander(display_title, expanded=False):
             # Reuse similar layout
            if pick.get('fit_reasons'):
                st.markdown(f"**Why:** {' '.join(pick['fit_reasons'])}")
            if pick.get('headline'):
                st.markdown(f"*{pick['headline']}*")
            
            # Locations
            loc_count = len(pick['locations'])
            st.caption(f"Available at {loc_count} Locations (e.g., {pick['locations'][0]['institution_name']})")
            
            # Check Availability Button (could expand list)
            df_loc = pd.DataFrame(pick['locations'])
            if not df_loc.empty:
                st.dataframe(df_loc[['institution_name', 'state']].head(5), hide_index=True, use_container_width=True)
                if loc_count > 5:
                    st.caption(f"...and {loc_count-5} more.")

# --- RENDER TIER 3: THE REST ---
if tier3_rest:
    st.markdown("---")
    count_rest = len(tier3_rest)
    if st.button(f"🔍 Explore {count_rest} Other Qualified Courses"):
        # Simple toggle state handling or just expand a table
        st.session_state['show_all_rest'] = not st.session_state.get('show_all_rest', False)
        
    if st.session_state.get('show_all_rest'):
        # Table View of the rest
        rest_data = []
        for g in tier3_rest:
            rest_data.append({
                "Course": g['course_name'],
                "Score": g['max_score'],
                "Locations": len(g['locations'])
            })
        st.dataframe(pd.DataFrame(rest_data), hide_index=True)


# 3. GATED CONTENT
if auth_status:
    # --- UNLOCKED VIEW ---
    st.markdown("---")
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
        
        c_filter1, c_filter2 = st.columns(2)
        cat_col = t['table_col_cat']
        cat_filter = c_filter1.multiselect(t['filter_label'], options=df_display[cat_col].unique(), default=df_display[cat_col].unique())
        state_opts = sorted([str(x) for x in df_display["state"].unique() if x])
        state_filter = c_filter2.multiselect(f"📍 {t.get('filter_state', 'Filter Location:')}", options=state_opts, default=state_opts)
        
        # Apply Filter
        mask = (df_display[cat_col].isin(cat_filter)) & (df_display["state"].isin(state_filter))
        df_filtered = df_display[mask]
        
        # Convert to list for rendering
        results = df_filtered.to_dict('records')
        
        if not results:
            st.warning(t['hero_fail'])
        else:
            # Show the filtered results as a table (Legacy Filter Support)
            # This allows users to use the bottom "Filter" widgets if they want.
            st.dataframe(df_filtered, hide_index=True)
else:
    # --- LOCKED VIEW ---
    if dash and dash.get('total_matches', 0) > 0:
        render_auth_gate(t, raw_grades, gender, cb, disability)

# Footer
st.markdown("---")
with st.expander(t['about_title']):
    st.markdown(t['about_desc'])