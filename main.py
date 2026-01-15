import streamlit as st
import pandas as pd
import os
import time
from supabase import create_client, Client
from src.engine import StudentProfile, load_and_clean_data
from src.dashboard import generate_dashboard_data

# --- 1. CONFIGURATION & SECRETS ---
st.set_page_config(page_title="Hala Tuju SPM", page_icon="🎓", layout="centered")

# Initialize Supabase Connection
# We wrap this in try-except to handle local dev vs cloud smoothly
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    DB_CONNECTED = True
except Exception:
    DB_CONNECTED = False
    # Only show warning if we are mostly sure we should be connected
    # st.warning("Database not connected. Data will not be saved.")

# Custom CSS
st.markdown("""
<style>
    .locked-blur { filter: blur(5px); opacity: 0.6; pointer-events: none; user-select: none; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)

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
    if not DB_CONNECTED:
        return False
    
    data = {
        "name": name,
        "email": email,
        "phone": phone,
        "gender": student.gender,
        "grades": student.grades, # Stores as JSON
        "eligible_count": eligible_count
    }
    
    try:
        supabase.table("student_profiles").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Error saving: {e}")
        return False

# --- 4. SIDEBAR ---
st.sidebar.title("📝 Keputusan SPM")
grade_opts = ["A+", "A", "A-", "B+", "B", "C+", "C", "D", "E", "G", "Tidak Ambil"]

with st.sidebar.form("grades_form"):
    bm = st.selectbox("Bahasa Melayu", grade_opts, index=5)
    eng = st.selectbox("Bahasa Inggeris", grade_opts, index=5)
    hist = st.selectbox("Sejarah", grade_opts, index=6)
    math = st.selectbox("Matematik", grade_opts, index=5)
    sci = st.selectbox("Sains", grade_opts, index=5)
    st.markdown("---")
    addmath = st.selectbox("Matematik Tambahan", ["Tidak Ambil"] + grade_opts, index=0)
    phy = st.selectbox("Fizik", ["Tidak Ambil"] + grade_opts, index=0)
    chem = st.selectbox("Kimia", ["Tidak Ambil"] + grade_opts, index=0)
    bio = st.selectbox("Biologi", ["Tidak Ambil"] + grade_opts, index=0)
    gender = st.radio("Jantina", ["Lelaki", "Perempuan"], horizontal=True)
    
    submitted = st.form_submit_button("🚀 Semak Kelayakan")

# --- 5. MAIN PAGE ---
st.title("🎓 Hala Tuju SPM")

# Initialize Session State for "Unlocked" status
if 'unlocked' not in st.session_state:
    st.session_state['unlocked'] = False

if submitted:
    # Reset unlock state on new search
    st.session_state['unlocked'] = False 
    
    grades = {'bm': bm, 'eng': eng, 'hist': hist, 'math': math, 'sci': sci,
              'addmath': addmath, 'phy': phy, 'chem': chem, 'bio': bio}
    grades = {k: v for k, v in grades.items() if v != "Tidak Ambil"}
    
    student = StudentProfile(grades, gender, 'Warganegara', 'Tidak', 'Tidak')
    
    # Store in session state so we can access it in the form later
    st.session_state['current_student'] = student
    
    with st.spinner("Menganalisis..."):
        time.sleep(0.5)
        st.session_state['dash'] = generate_dashboard_data(student, df_courses)

# Display Logic
if 'dash' in st.session_state:
    dash = st.session_state['dash']
    
    if dash['total_matches'] > 0:
        st.success(f"🎉 Tahniah! Anda layak memohon **{dash['total_matches']} Kursus**.")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Politeknik", dash['summary_stats'].get('Politeknik', 0))
        c2.metric("IKBN / ILP", dash['summary_stats'].get('IKBN / ILP (Skills)', 0))
        c3.metric("Kolej Komuniti", dash['summary_stats'].get('Kolej Komuniti', 0))
        
        st.markdown("---")
        
        # IF UNLOCKED: Show Everything
        if st.session_state['unlocked']:
            st.info("🔓 Laporan Penuh Dibuka!")
            st.subheader("📋 Senarai Penuh Kursus Anda")
            
            # Simple Table View for now
            # Convert list of dicts to DataFrame for display
            if dash.get('featured_matches'):
                # Combine featured and others into one list if needed, or just show all
                # For Phase 1, let's just show a clear list
                st.write("Hubungi kaunselor kami untuk bantuan permohonan.")
                
        else:
            # LOCKED VIEW (Teaser)
            st.subheader("🌟 3 Pilihan Strategik")
            for i, pick in enumerate(dash['featured_matches']):
                with st.expander(f"#{i+1}: {pick['course_name']} ({pick['quality']})", expanded=True):
                    st.write(f"🏫 **{pick['institution']}**")
                    st.caption(f"Kategori: {pick['type']}")

            st.markdown("---")
            st.write(f"**...dan {dash['total_matches'] - 3} lagi kursus.**")
            st.markdown('<div class="locked-blur">1. Diploma Kejuruteraan...<br>2. Sijil Teknologi...</div>', unsafe_allow_html=True)
            
            # THE GATEKEEPER FORM
            st.warning("🔒 Masukkan butiran untuk membuka senarai penuh (Percuma).")
            
            with st.form("lead_capture"):
                c_name, c_phone = st.columns(2)
                name = c_name.text_input("Nama Penuh")
                phone = c_phone.text_input("No. WhatsApp (Contoh: 0123456789)")
                email = st.text_input("Alamat Emel")
                
                confirm = st.form_submit_button("🔓 Buka Laporan Penuh")
                
                if confirm:
                    if name and phone:
                        # Save to Supabase
                        saved = save_profile(name, email, phone, st.session_state['current_student'], dash['total_matches'])
                        if saved:
                            st.session_state['unlocked'] = True
                            st.toast("Berjaya! Data disimpan.")
                            st.rerun()
                    else:
                        st.error("Sila isi Nama dan No. Telefon.")

    else:
        st.error("Tiada padanan ditemui.")