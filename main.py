import streamlit as st
import re
import pandas as pd
import time
from supabase import create_client, Client
from src.engine import StudentProfile
from src.dashboard import generate_dashboard_data, group_courses_by_id
from src.ranking_engine import get_ranked_results, TAG_COUNT, sort_courses
from src.translations import get_text, LANGUAGES
from src.quiz_manager import QuizManager
from src.auth import AuthManager
from src.reports.insight_generator import InsightGenerator
from src.reports.ai_wrapper import AIReportWrapper
from src.data_manager import load_master_data
from src.reports.pdf_generator import PDFReportGenerator
from datetime import datetime

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Hala Tuju Pelajar Lepasan SPM", page_icon="🎓", layout="centered")

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
        st.success(t.get('quiz_complete', "Profil Anda Telah Disimpan!"))
        
        # Explainer Text
        st.markdown("""
        **Terima kasih!** Jawapan anda telah direkodkan.
        Kami telah menyusun semula senarai kursus berdasarkan personaliti dan minat anda.
        Kursus yang anda lihat di **Dashboard** kini telah disesuaikan khas untuk anda.
        """)
        
        # Call to Action (CTA)
        st.info("💡 **Langkah Seterusnya:** Sila kembali ke tab **Dashboard** untuk melihat cadangan kursus anda.")
        
        if st.button("Ke Halaman Dashboard ➡️", use_container_width=True, type="primary"):
            st.session_state['view_mode'] = 'dashboard'
            st.rerun()
            
        st.markdown("---")
        st.markdown("🔍 **Ingin tahu lebih lanjut?** Klik butang **✨ Deep AI Analysis (Beta)** di menu sisi / dashboard untuk mendapatkan laporan kerjaya penuh.")

        # Hide Raw Data in Expander
        with st.expander("🛠️ View Debug Data (Raw Profile)"):
            st.json(results)
        
        # Save to Session
        st.session_state['student_signals'] = results['student_signals']


# --- SIDEBAR LOGIC ---
# ...
# Inside render_sidebar or main logic:

# ... (After Profile Button) ...
# ... (Main Router) ...

def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("assets/style.css")

@st.cache_data(ttl=59) # Force new cache key
def get_data():
    return load_master_data()

# Force clear cache if data seems stale (Debug/Dev Fix)
if 'data_refreshed' not in st.session_state:
    st.cache_data.clear()
    st.session_state['data_refreshed'] = True

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
        r_name = st.text_input(t.get('lbl_preferred_name', "Preferred Name"), placeholder="Ali")
        r_phone = st.text_input(t['profile_phone'], placeholder="e.g. 012-3456789")
        r_email = st.text_input("Email (Optional)", placeholder="ali@example.com")
        r_pin = st.text_input(t['lbl_create_pin'], type="password", max_chars=6, help=t['help_pin'])
        
        if st.form_submit_button(t['btn_unlock_save']):
            # Clean Grades first
            grade_map = {k: v for k, v in current_grades.items() if v != t['opt_not_taken']} if current_grades else {}
            
            success, val = auth.register_user(r_name, r_phone, r_pin, grades=grade_map, gender=gender, colorblind=cb, disability=disability, email=r_email)
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
            st.markdown(f"**Preferred Name:**\n\n{user.get('full_name', '-')}")
        with c2:
            st.markdown(f"**{t['profile_phone']}:**\n\n{user.get('phone', '-')}")
            
        st.markdown("---")
        
        # Edit Form
        with st.expander(t['header_edit_details'], expanded=True):
            with st.form("edit_profile"):
                new_name = st.text_input(t['lbl_preferred_name'], value=user.get('full_name', ''))
                new_email = st.text_input(t['lbl_email'], value=user.get('email', ''))
                
                # Location & logistics
                c_city, c_state = st.columns(2)
                
                # Fetch existing extras from student_signals (softly)
                user_signals = user.get('student_signals') or {}
                
                with c_city:
                    new_city = st.text_input(t['lbl_city'], value=user_signals.get('city', ''))
                with c_state:
                    state_opts = ["Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", "Pahang", "Perak", "Perlis", "Pulau Pinang", "Sabah", "Sarawak", "Selangor", "Terengganu", "WP Kuala Lumpur", "WP Labuan", "WP Putrajaya"]
                    curr_state = user_signals.get('state')
                    state_idx = state_opts.index(curr_state) if curr_state in state_opts else 0
                    new_state = st.selectbox(t['lbl_state'], state_opts, index=state_idx)
                    
                st.markdown("---")
                st.markdown(f"### {t['lbl_financial']}")
                
                # Financial Slider
                # Map using translated strings - Bold only the label, not the description
                def bold_label(full_str):
                    parts = full_str.split(" (", 1)
                    if len(parts) == 2:
                        return f"**{parts[0]}** ({parts[1]}"
                    return f"**{full_str}**"
                
                fin_map = {
                    0: bold_label(t['fin_low']), 
                    50: bold_label(t['fin_med']), 
                    100: bold_label(t['fin_high'])
                }
                
                # Reverse lookup needs to handle potentially non-bold stored values from previous saves
                curr_fin_raw = user_signals.get('financial_pressure', t['fin_med'])
                
                # Heuristic to find position
                slider_val = 50
                if "Low" in curr_fin_raw or "Rendah" in curr_fin_raw or "குறைவு" in curr_fin_raw: slider_val = 0
                elif "High" in curr_fin_raw or "Tinggi" in curr_fin_raw or "அதிகம்" in curr_fin_raw: slider_val = 100
                
                new_fin_val = st.select_slider(
                    t['lbl_financial'],
                    options=[0, 50, 100],
                    value=slider_val,
                    format_func=lambda x: fin_map[x],
                    label_visibility="collapsed"
                )
                new_fin_str = fin_map[new_fin_val].replace("**", "") # Store clean text
                
                # Travel Willingness
                travel_opts = [t['travel_near'], t['travel_state'], t['travel_peninsula'], t['travel_any']]
                
                # Map stored value to current language option
                travel_idx = 2
                curr_travel = user_signals.get('travel_willingness', '')
                if curr_travel:
                    if curr_travel in travel_opts:
                        travel_idx = travel_opts.index(curr_travel)
                
                new_travel = st.selectbox(t['lbl_travel'], travel_opts, index=travel_idx)
                
                st.markdown("---")
                
                new_gender = st.radio(t['lbl_gender'], [t["gender_male"], t["gender_female"]], index=0 if user.get('gender') == "Male" else 1, horizontal=True)
                
                # Health
                cb_val = user.get('colorblind', t['opt_no'])
                cb_idx = 1 if cb_val == t['opt_yes'] or cb_val == 'Ya' or cb_val == 'Yes' or cb_val == 'ஆம்' else 0
                new_cb = st.radio(t['lbl_colorblind'], [t['opt_no'], t['opt_yes']], index=cb_idx, key="p_cb", horizontal=True)
                
                dis_val = user.get('disability', t['opt_no'])
                dis_idx = 1 if dis_val == t['opt_yes'] or dis_val == 'Ya' or dis_val == 'Yes' or dis_val == 'ஆம்' else 0
                new_dis = st.radio(t['lbl_disability'], [t['opt_no'], t['opt_yes']], index=dis_idx, key="p_dis", horizontal=True)
                
                if st.form_submit_button(t['btn_update_profile']):
                    # Validate Email
                    valid_email = True
                    if new_email:
                         if not re.match(r"[^@]+@[^@]+\.[^@]+", new_email):
                             st.error(t['err_email_invalid'])
                             valid_email = False
                    
                    # Validate City (Alphabets/Spaces only)
                    if new_city:
                         if not re.match(r"^[a-zA-Z\s]+$", new_city):
                             st.error("❌ City: Only alphabets and spaces allowed.")
                             valid_email = False
                    
                    if valid_email:
                        updated_signals = user_signals.copy()
                        updated_signals.update({
                            "city": new_city,
                            "state": new_state,
                            "financial_pressure": new_fin_str,
                            "travel_willingness": new_travel
                        })
                    
                        success, msg = auth.update_profile(user['id'], {
                            "full_name": new_name,
                            "email": new_email,
                            "gender": new_gender,
                            "colorblind": new_cb,
                            "disability": new_dis,
                            "student_signals": updated_signals
                        })
                        if success:
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
                
            except Exception as e:
                st.error(f"Could not save results: {e}")
            
            # AUTO-GENERATE AI COUNSELLOR REPORT (BACKGROUND THREAD)
            # Run only once per quiz session
            if not st.session_state.get('ai_gen_done'):
                # WE WANT TO HIDE EVERYTHING ELSE WHILE THIS RUNS
                # So we use a big empty container or just run this *before* printing the success messages below.
                
                from concurrent.futures import ThreadPoolExecutor
                
                progress_messages = [
                    "🔍 Menganalisis keputusan SPM & kekuatan akademik...",
                    "🧠 Memadankan gaya pembelajaran & minat kerjaya...",
                    "🏢 Menyemak ketersediaan kampus & lokasi...",
                    "✨ Menyusun strategi laluan terbaik anda...",
                    "✅ Laporan hampir siap..."
                ]
                
                status_container = st.empty()
                
                # Helper to run AI (Blocking Function)
                def run_ai_task(user_profile, dash_data):
                    try:
                        # Wrapper must be instantiated inside or passed explicitly?
                        # Be safe: Init here to ensure thread has access (though secrets are global)
                        from src.reports.ai_wrapper import AIReportWrapper
                        wrapper = AIReportWrapper()
                        top_matches = dash_data.get('featured_matches', [])[:5]
                        return wrapper.generate_narrative_report(user_profile, top_matches)
                    except Exception as e:
                        return {"error": str(e)}

                # Prepare Data
                ai_dash = st.session_state.get('dash', {})
                ai_profile = {
                    "full_name": user.get('full_name', ''),
                    "grades": user.get('grades', {}),
                    "student_signals": results['student_signals']
                }
                
                # Execute in Background
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_ai_task, ai_profile, ai_dash)
                    
                    # UI Loop: Rotate messages while waiting
                    idx = 0
                    while not future.done():
                        # CLAMP index to last message
                        # Message holds at "Almost ready..." until done
                        msg_idx = min(idx, len(progress_messages) - 1)
                        msg = progress_messages[msg_idx]
                        
                        status_container.info(f"🤖 {msg}")
                        time.sleep(4) # Wait 4s per message
                        idx += 1
                    
                    # Get Result
                    report = future.result()
                
                # Clear Status
                status_container.empty()
                
                # Process Report
                if "error" not in report and "markdown" in report:
                     st.session_state['ai_report'] = report
                     
                     # Save to DB
                     try:
                         import json
                         report_json = json.dumps(report)
                         auth.update_profile(user['id'], {"ai_report": report_json})
                         if 'user' in st.session_state:
                             st.session_state['user']['ai_report'] = report_json
                     except Exception:
                         pass
                else:
                     print(f"AI Gen Error: {report.get('error')}")

                # Set flags
                st.session_state['dashboard_visited_post_quiz'] = False
                st.session_state['report_just_unlocked'] = False # Reset unlock flag
                st.session_state['ai_gen_done'] = True # MARK DONE


        
        # Display Results - Focus on Course Ranking Update
        st.success(t.get('quiz_ranking_updated', "✅ Ranking updated!"))

        # Explainer Text
        st.markdown(t.get('quiz_view_dashboard_msg', "📊 **Please view Dashboard.**"))
        st.markdown(t.get('quiz_courses_ranked_msg', "Courses have been ranked."))

        # Call to Action (CTA)
        if st.button(t.get('btn_view_dashboard', "📊 View Dashboard"), use_container_width=True, type="primary"):
            # UPDATE SESSION WITH NEW RESULTS
            st.session_state['student_signals'] = results['student_signals']
            
            # Cleanup volatile scores before returning
            if 'quiz_scores' in st.session_state:
                del st.session_state['quiz_scores']
                
            st.session_state['view_mode'] = 'dashboard'
            st.rerun()

        # Hide Raw Data in Expander
        with st.expander(t.get('quiz_debug_label', "Debug Data")):
            st.json(results)


# --- 5d. AI REPORT PAGE ---
def render_ai_report_page(user, t):
    """Render the AI-generated career counseling report in full-page view"""
    report = st.session_state.get('ai_report', {})
    
    if not report or "markdown" not in report:
        st.error("No report available. Please generate a report first.")
        if st.button("⬅️ Back to Dashboard"):
            st.session_state['view_mode'] = 'dashboard'
            st.rerun()
        return
    
    # Add print-friendly CSS
    st.markdown("""
    <style>
    @media print {
        /* 1. Global Reset to ensure scrolling works/printing works */
        html, body, .stApp {
            height: auto !important;
            width: 100% !important;
            overflow: visible !important;
            background-color: white !important;
        }

        /* 2. Hide Streamlit Chrome (Header, Footer, Sidebar, Buttons) */
        header, 
        [data-testid="stHeader"],
        footer, 
        .stApp > header, 
        [data-testid="stSidebar"],
        .stDeployButton,
        [data-testid="stToolbar"],
        button, 
        .stButton,
        .stDownloadButton {
            display: none !important;
        }

        /* 3. Force Main Content to be Visible & Full Width */
        .main .block-container {
            max-width: 100% !important;
            padding: 2rem 1rem !important;
            margin: 0 !important;
            box-shadow: none !important;
            border: none !important;
        }
        
        /* 4. Ensure Text is Black (Fixes Dark Mode Issues) */
        .stMarkdown, p, h1, h2, h3, h4, h5, h6, li, span, div {
            color: black !important;
            color-adjust: exact !important;
            -webkit-print-color-adjust: exact !important;
        }
        
        /* 5. Page Break Controls */
        h1, h2, h3 {
            page-break-after: avoid;
            page-break-inside: avoid;
        }
        p, li {
            page-break-inside: avoid;
        }
        
        /* 6. Hide Action Buttons Row specifically if it leaks */
        [data-testid="stHorizontalBlock"] button {
             display: none !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Display the AI report
    st.markdown(report['markdown'])
    
    st.markdown("---")
    
    # Action Buttons Row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # PDF Download Button
        try:
            from src.reports.pdf_generator import PDFReportGenerator
            from datetime import datetime
            
            # Reconstruct profile for PDF
            ai_signals = st.session_state.get('student_signals', {})
            if not ai_signals and user and user.get('student_signals'):
                ai_signals = user['student_signals']
                
            ai_profile = {
                "full_name": user.get('full_name', '') if user else '',
                "grades": user.get('grades', {}) if user else {},
                "student_signals": ai_signals
            }
            
            pdf_gen = PDFReportGenerator()
            c_name = report.get('counsellor_name', "HalaTuju (AI)")
            pdf_buffer = pdf_gen.generate_pdf(ai_profile, report['markdown'], counsellor_name=c_name)
            
            curr_year = datetime.now().year
            anon_id = str(user.get('id', 'Guest'))[-6:] if user else "Guest"
            fname = f"Laporan_Kerjaya_SPM_{curr_year}_{anon_id}.pdf"
            
            st.download_button(
                label="📄 Download PDF",
                data=pdf_buffer,
                file_name=fname,
                mime="application/pdf",
                key="btn_pdf_dl_page",
                use_container_width=True
            )
        except Exception as e:
            print(f"PDF Error: {e}")
            st.button("📄 Download PDF", disabled=True, use_container_width=True)
    
    with col2:
        # WhatsApp Share Button
        
        # Get Top 3 Courses for the message
        top_courses_msg = ""
        
        # Try to get courses from ranked_courses (if available) or from dashboard data
        ranked_courses = st.session_state.get('ranked_courses', [])
        
        if not ranked_courses:
            # Fallback 1: Check 'dash' session state (featured_matches)
            dash_data = st.session_state.get('dash', {})
            ranked_courses = dash_data.get('featured_matches', [])
            
        if not ranked_courses:
            # Fallback 2: Check full list from 'dash'
            dash_data = st.session_state.get('dash', {})
            ranked_courses = dash_data.get('full_list', [])[:3]

        if ranked_courses:
            for i, course in enumerate(ranked_courses[:3]):
                # Use correct key: 'course_name' (lowercase with underscore)
                c_name = course.get('course_name', course.get('Course Name', 'Unknown'))
                top_courses_msg += f"{i+1}. {c_name}\n" # Newline for list
        
        # Get localized message template
        # Need to ensure 't' is available here. It usually is passed or defined.
        # If not, fetch it.
        from src.translations import get_text
        t_local = get_text(st.session_state.get('lang_code', 'en'))
        
        msg_template = t_local.get('wa_share_msg', "")
        
        # Create a shareable message
        try:
            whatsapp_text = msg_template.format(courses=top_courses_msg)
        except Exception:
            # Fallback if format fails
            whatsapp_text = f"Hala Tuju Report:\n\n{top_courses_msg}\nhttps://halatuju.streamlit.app"
        
        # URL encode properly
        from urllib.parse import quote
        whatsapp_url = f"https://wa.me/?text={quote(whatsapp_text)}"
        
        st.link_button(
            label="📲 Share with Parent",
            url=whatsapp_url,
            use_container_width=True
        )
    
    with col3:
        # Print Button (uses browser print dialog)
        if st.button("🖨️ Print Report", use_container_width=True, key="btn_print"):
            import streamlit.components.v1 as components
            components.html(
                """
                <script>
                window.print();
                </script>
                """,
                height=0,
            )
    
    st.markdown("---")
    # Back to Dashboard button
    if st.button("⬅️ Back to Dashboard", use_container_width=True, type="primary"):
        st.session_state['view_mode'] = 'dashboard'
        st.rerun()

    # Model Attribution Footer (for quality comparison)
    model_name = report.get('model_used', 'Unknown Model')
    c_name = report.get('counsellor_name', 'Unknown Counselor')
    st.markdown(f"<div style='text-align: center; color: #888; font-size: 0.8em; margin-top: 20px;'>Generated by {c_name} • Engine: {model_name}</div>", unsafe_allow_html=True)


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
        # Reset Gen Flag
        if 'ai_gen_done' in st.session_state: del st.session_state['ai_gen_done']
        st.rerun()

    # --- AI COUNSELLOR (SIDEBAR) ---
    # Show if student has completed the quiz (has student_signals)
    has_completed_quiz = bool(user.get('student_signals'))
    if has_completed_quiz:
        
        # Check if report exists (in session or database)
        report = st.session_state.get('ai_report')
        if not report and user.get('ai_report'):
            # Load from database if not in session
            import json
            try:
                # Parse JSON string from database
                if isinstance(user['ai_report'], str):
                    report = json.loads(user['ai_report'])
                else:
                    report = user['ai_report']
                st.session_state['ai_report'] = report
            except json.JSONDecodeError as e:
                print(f"Failed to parse AI report from database: {e}")
                report = None
        
        # Check if dashboard has been visited after quiz completion
        dashboard_visited = st.session_state.get('dashboard_visited_post_quiz', True)  # Default True for existing users
        
        if not dashboard_visited:
            # Show prompt to view dashboard first
            st.sidebar.info("💡 **Explore courses to unlock report**")
            # Optionally show a greyed out button?
            st.sidebar.button("🔒 Counselor Report", disabled=True, use_container_width=True)
        else:
            # Dashboard has been visited - show unlock message if just unlocked
            if st.session_state.get('report_just_unlocked', False):
                st.sidebar.success(t.get('report_unlock_msg', "💡 **Report available!**"))
                # Don't clear the flag immediately - let it persist for this session
            
            # Always show button when dashboard has been visited
            if st.sidebar.button("📋 Counselor Report", key="btn_ai_access_sb", use_container_width=True):
                if report and "markdown" in report:
                    # Clear the unlock flag when accessing report
                    st.session_state['report_just_unlocked'] = False
                    # Switch to AI report view
                    st.session_state['view_mode'] = 'ai_report'
                    st.rerun()
                else:
                    st.sidebar.warning("Report not available. Please retake the Discovery Quiz.")


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

if view_mode == 'ai_report':
    render_ai_report_page(user, t)
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

# 2. Resolve Signals (Priority: Session > Quiz Manager > User DB)
# Check Quiz Manager first (Most fresh)
# CRITICAL: Only if quiz_scores has actual data. On refresh, it's empty dict {}.
if 'quiz_scores' in st.session_state and st.session_state['quiz_scores']:
    try:
        # Re-derive signals from raw quiz scores
        results = quiz_manager.get_final_results()
        signals = results.get('student_signals')
        st.session_state['student_signals'] = signals
    except Exception as e:
        print(f"Error regenerating signals: {e}")

# If still no signals, check Session Storage directly
if not signals and 'student_signals' in st.session_state:
    signals = st.session_state['student_signals']

# If still no signals, check User DB (Persistence)
if not signals and user and user.get('student_signals'):
    signals = user['student_signals']
    st.session_state['student_signals'] = signals # Restore to session

# 3. Execute Ranking
# We run this if we have Dashboard Data AND Signals
if dash and signals:
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
        
    except Exception as e:
        print(f"RANKING ERROR: {e}")
        # Fallback: Don't crash app, just show default list



if auth_status:
    # --- UNLOCKED VIEW ---
    st.markdown("---")
    # ...


# --- RENDER MAIN CONTENT ---
st.title(t['header_title'])

# Track dashboard visit for report unlocking
# Logic: Defaults to False if key doesn't exist
# If False, we hide the button.
# We only flip to True if user INTERACTS.


if not dash or dash['total_matches'] == 0:
    st.info(t['landing_msg'])
    st.stop()

# 1. Summary Metrics (Always Valid)
if 'hero_eligible_dynamic' in t:
    msg = t['hero_eligible_dynamic'].format(courses=dash.get('total_unique_courses', 0), locs=dash['total_matches'])
else:
    msg = t['hero_success'].format(count=dash['total_matches'])
st.success(msg)

c1, c2, c3, c4 = st.columns(4)
c1.metric(t['inst_poly'], dash['summary_stats'].get('inst_poly', 0))
c2.metric(t['inst_kk'], dash['summary_stats'].get('inst_kk', 0))
c3.metric(t['inst_iljtm'], dash['summary_stats'].get('inst_iljtm', 0))
c4.metric(t['inst_ilkbs'], dash['summary_stats'].get('inst_ilkbs', 0))

# 2. Featured Matches (Teaser - Limit 3)
# 2. Featured Matches (Teaser - Dynamic Limit)
# --- TIERED DISPLAY LOGIC ---
    # 1. Group all eligible courses
    # Note: We group the ENTIRE eligible list, not just top 5, to get the full picture.
    # The 'ranked' result has split top_5/rest, but for grouping we want to re-merge and group properly.
    # Use robust sorting logic (Score > Credential > Institution > Name)
all_ranked = sort_courses(dash['full_list'])
grouped_courses = group_courses_by_id(all_ranked)

# 2. Slice Tiers
# LOGIC UPDATE: Guests only see Top 3. Users see Top 5 + Tier 2 + Tier 3.
if not auth_status:
    # --- GUEST MODE ---
    tier1_featured = grouped_courses[:3] # Strictly Top 3
    tier2_good = [] # Hide
    tier3_rest = [] # Hide
else:
    # --- USER MODE ---
    tier1_featured = grouped_courses[:5]
    tier2_good = grouped_courses[5:25]
    tier3_rest = grouped_courses[25:]

# --- REPORTING LAYER ---
# [DISABLED] Per user request
# if signals and tier1_featured:
#     st.markdown("---")
#     st.subheader("📊 Your Personal Insight")
#     
#     # Reconstruct profile for report
#     profile_for_report = {
#         "grades": user.get('grades', {}) if user else {},
#         "student_signals": signals
#     }
#     
#     # 1. Deterministic Report
#     insights = InsightGenerator.generate_report(profile_for_report, tier1_featured)
#     
#     # Display Compact
#     rc1, rc2 = st.columns(2)
#     with rc1:
#         st.info(f"**Academic:** {insights['academic_snapshot']}")
#         st.success(f"**Style:** {insights['learning_style']}")
#     with rc2:
#         st.warning(f"**Note:** {insights['caution']}")
        

# --- RENDER TIER 1: FEATURED MATCHES ---
st.markdown(f"### :star: {t.get('lbl_featured', 'Featured Matches')}")

# Import UI Component (Lazy import or move to top)
from src.dashboard import display_course_card

for pick in tier1_featured:
    # Use the new Refactored Card
    # It returns TRUE if the user clicked the interaction button
    # Logic: Show Trigger Button ONLY if dashboard is "locked" (not yet visited post quiz)
    is_locked = not st.session_state.get('dashboard_visited_post_quiz', True)
    
    interacted = display_course_card(pick, t, show_trigger=is_locked)
    
    if interacted:
        # User engaged with the content!
        # Unlock the report
        if not st.session_state.get('dashboard_visited_post_quiz', False):
             st.session_state['dashboard_visited_post_quiz'] = True
             st.session_state['report_just_unlocked'] = True
             st.rerun() # Refresh to show the sidebar button


# --- RENDER TIER 2: GOOD OPTIONS ---
if tier2_good:
    st.markdown("---")
    st.subheader("👍 Worth Considering")
    for pick in tier2_good:
         # Compact Card
        display_title = f"{pick['course_name']}" # Remove Score from header
        with st.expander(display_title, expanded=False):
             # Reuse RICH Card Layout
             # We pass show_trigger logic here too: if report locked, show button.
             # This means unlocking works from Tier 2 as well!
             is_locked_t2 = not st.session_state.get('dashboard_visited_post_quiz', True)
             # Hide redundant title inside card
             clicked_t2 = display_course_card(pick, t, show_trigger=is_locked_t2, show_title=False)
             
             if clicked_t2:
                 if not st.session_state.get('dashboard_visited_post_quiz', False):
                     st.session_state['dashboard_visited_post_quiz'] = True
                     st.session_state['report_just_unlocked'] = True
                     st.rerun()

# --- RENDER TIER 3: THE REST ---
# --- RENDER TIER 3: THE REST ---
# [DISABLED] Per user request
# if tier3_rest:
#     st.markdown("---")
#     count_rest = len(tier3_rest)
#     if st.button(f"🔍 Explore {count_rest} Other Qualified Courses"):
#         # Simple toggle state handling or just expand a table
#         st.session_state['show_all_rest'] = not st.session_state.get('show_all_rest', False)
#         
#     if st.session_state.get('show_all_rest'):
#         # Table View of the rest
#         rest_data = []
#         for g in tier3_rest:
#             rest_data.append({
#                 "Course": g['course_name'],
#                 "Score": g['max_score'],
#                 "Locations": len(g['locations'])
#             })
#         st.dataframe(pd.DataFrame(rest_data), hide_index=True)


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
        
        # --- SEARCH BAR ---
        search_term = st.text_input(f"🔍 {t.get('lbl_search', 'Search Courses')}", placeholder="Type course name or institution...", key="search_term").strip().lower()
        
        # --- FILTER POPOVER ---
        # Robustness: Ensure columns exist (Handle Stale Session State)
        if "frontend_label" not in df_display.columns:
            df_display["frontend_label"] = "General"
            
        if "level" not in df_display.columns:
            # If missing, it implies stale data. We should probably force refresh, 
            # but for now, prevent crash.
            df_display["level"] = "Certificate"

        # Option 1: Clean Popover UI with Blue Pills
        with st.popover("🌪️ Filter Options", use_container_width=False):
            st.markdown("### Filter")
            
            # 1. Institution Type (Expanded)
            # Custom Sort Order: Poly, KK, ILJTM, ILKBS
            inst_order = [t.get('inst_poly'), t.get('inst_kk'), t.get('inst_iljtm'), t.get('inst_ilkbs')]
            def sort_inst(x):
                try: return inst_order.index(x)
                except ValueError: return 999

            cat_col = t['table_col_cat']
            cat_opts = sorted(df_display[cat_col].unique(), key=sort_inst)
            
            with st.expander("By Institution Type", expanded=True):
                cat_filter = st.pills("Select Type", options=cat_opts, selection_mode="multi", default=cat_opts, key="pill_cat", label_visibility="collapsed")
            
            # 2. Location (Collapsed)
            state_priority = [
                "WP Kuala Lumpur", "Selangor", "Kedah", "Pulau Pinang", "Perak", 
                "Negeri Sembilan", "Melaka", "Johor", "Pahang", "Perlis", 
                "Kelantan", "Terengganu", "Sabah", "Sarawak", "WP Labuan"
            ]
            def sort_state(x):
                try: return state_priority.index(x)
                except ValueError: return 999
            
            with st.expander("By State", expanded=False):
                 state_raw = [str(x) for x in df_display["state"].unique() if x]
                 state_opts = sorted(state_raw, key=sort_state)
                 state_filter = st.pills("Select States", options=state_opts, selection_mode="multi", default=state_opts, key="pill_state", label_visibility="collapsed")
            
            # 3. Field of Study (Collapsed)
            field_raw = [str(x) for x in df_display["frontend_label"].unique() if x]
            field_opts = sorted(field_raw)
            with st.expander("By Field of Education", expanded=False):
                field_filter = st.pills("Select Fields", options=field_opts, selection_mode="multi", default=field_opts, key="pill_field", label_visibility="collapsed")

            # 4. Level of Education (New)
            level_raw = [str(x) for x in df_display["level"].unique() if x]
            level_opts = sorted(level_raw)
            with st.expander("By Level of Education", expanded=False):
                level_filter = st.pills("Select Level", options=level_opts, selection_mode="multi", default=level_opts, key="pill_level", label_visibility="collapsed")
            
            # Course Category (Placeholder / WIP)
        
        # Apply Filter
        mask = (df_display[cat_col].isin(cat_filter)) & (df_display["state"].isin(state_filter))
        df_filtered = df_display[mask]
        
        # Convert to list for rendering
        results = df_filtered.to_dict('records')
        
        if not results:
            st.warning(t['hero_fail'])
        else:
 # --- PAGINATED LIST VIEW ---
            from src.dashboard import render_pagination, BATCH_SIZE
            
            # Use 'grouped_courses' which is the raw list of all courses
            # Re-apply filters manually because we cannot use the DataFrame for 'display_course_card'
            
            filtered_raw = []
            
            # Helper: Check if item matches filters
            # Filters: cat_filter (Type), state_filter (State)
            # cat_filter/state_filter are lists of selected strings
            
            # Use 'grouped_courses' (Aggregated by Course ID)
            # This ensures we display 1 card per course with multiple locations inside.
            
            filtered_raw = []
            
            # Helper: Check if item matches filters
            # Filters: cat_filter (Type), state_filter (State), field_filter (Label), level_filter (Level)
            
            for group in grouped_courses:
                 # 0a. Check Field Filter
                 c_field = str(group.get('frontend_label', 'General'))
                 if c_field not in field_filter:
                     continue
                 
                 # 0b. Check Level Filter
                 c_level = str(group.get('level', 'Certificate'))
                 if c_level not in level_filter:
                     continue

                 # Check Search Term (Course Level)
                 c_name = str(group.get('course_name', '')).lower()
                 c_head = str(group.get('headline', '')).lower()
                 c_syn = str(group.get('synopsis', '')).lower()
                 
                 course_matches_search = (search_term in c_name or search_term in c_head or search_term in c_syn)
                 
                 # Check Filters & Locations Search
                 valid_locs = []
                 original_locs = group.get('locations', [])
                 
                 loc_matches_search = False
                 
                 for loc in original_locs:
                      # Check Type
                      l_type = loc.get('type')
                      
                      # Check State
                      l_state = str(loc.get('state')) if loc.get('state') else None
                      
                      # Check Search (Location Level)
                      l_inst = str(loc.get('institution_name', '')).lower()
                      if search_term in l_inst:
                           loc_matches_search = True
                      
                      # Filter Logic
                      if l_type in cat_filter and l_state in state_filter:
                           valid_locs.append(loc)
                 
                 # Final Decision:
                 # 1. Must match standard CAT/STATE filters (by having at least 1 valid location)
                 # 2. Must match SEARCH (either course text OR at least one institution/location name)
                 
                 # Wait, if search matches "University X", we should probably show the course even if only that location matches?
                 # But we also applied CAT/STATE filters.
                 # Let's say SEARCH acts as an additional AND filter on top of the list.
                 # If I search "Johor", but the state filter excludes Johor, it won't show. That's fine.
                 
                 # Logic:
                 # If valid_locs is empty, it's filtered out by Cat/State. Skip.
                 # If valid_locs is NOT empty, we check Search.
                 # Is Match = course_matches_search OR (search_term in any of the valid_locs institution names)
                 
                 if valid_locs:
                      # Check Search
                      if search_term:
                           # Does any of the VALID locations match?
                           any_loc_match = any(search_term in str(l.get('institution_name','')).lower() for l in valid_locs)
                           if not (course_matches_search or any_loc_match):
                                continue
                                
                      # Create a display copy to avoid mutating the original global cache
                      # Shallow copy is fine for the dict, but we need to replace the list
                      display_copy = group.copy()
                      display_copy['locations'] = valid_locs
                      
                      filtered_raw.append(display_copy)
            
            if not filtered_raw:
                 st.info(f"No courses match the selected filters. (Filters: {len(cat_filter)} Cats, {len(state_filter)} Locs)")
            else:
                # Show Result Count
                st.caption(f"Showing {len(filtered_raw)} result{'s' if len(filtered_raw) != 1 else ''}")

                # 1. Init Pagination (Only calculate page, don't render controls yet if user wants bottom only)
                # But we need 'render_pagination' to get the current page state and handle logic.
                # So we call it but HIDE the output? Or modify render_pagination to have 'render=False'?
                # Modifying dashboard.py is cleaner.
                # OR: Just call it with unique_id="hidden" and maybe use CSS to hide it? No, that's hacky.
                # Better: Allow 'render_pagination' to just return state.
                
                # Let's check 'src/dashboard.py'. It renders headers/buttons immediately.
                # Quick fix: Just let it render at bottom. 
                # But we need the current page number BEFORE slicing.
                
                # We can manually get the page number from session state.
                pg_key = "list_page"
                if pg_key not in st.session_state: st.session_state[pg_key] = 1
                
                # Ensure page is valid
                from src.dashboard import BATCH_SIZE
                import math
                total_items = len(filtered_raw)
                total_pages = math.ceil(total_items / BATCH_SIZE)
                if st.session_state[pg_key] > total_pages: st.session_state[pg_key] = 1
                
                current_page = st.session_state[pg_key]
                
                # 2. Slice Data
                start = (current_page - 1) * BATCH_SIZE
                end = start + BATCH_SIZE
                batch_raw = filtered_raw[start:end]
                
                # 3. Render Batch using Rich Cards
                st.markdown("---")
                
                for pick in batch_raw:
                     # Render Card (No trigger needed)
                     # Now 'pick' is a GROUPED object with 'locations' list.
                     # display_course_card handles this perfectly.
                     display_course_card(pick, t, show_trigger=False, show_title=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # 4. Render Pagination Controls at Bottom
                # This will render the buttons and update state on click
                render_pagination(total_items, BATCH_SIZE, pg_key, unique_id="bottom")

else:
    # --- LOCKED VIEW ---
    if dash and dash.get('total_matches', 0) > 0:
        render_auth_gate(t, raw_grades, gender, cb, disability)

# Footer
st.markdown("---")
with st.expander(t['about_title']):
    st.markdown(t['about_desc'])