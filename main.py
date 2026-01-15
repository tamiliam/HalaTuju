import streamlit as st
import pandas as pd
import os
import time
from src.engine import StudentProfile, load_and_clean_data
from src.dashboard import generate_dashboard_data

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Hala Tuju SPM",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS for the "Locked" blur effect
st.markdown("""
<style>
    .locked-blur {
        filter: blur(5px);
        opacity: 0.6;
        pointer-events: none;
        user-select: none;
    }
    .stButton button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA LOADER ---
@st.cache_data
def get_data():
    """Loads and cleans data once. Cached for performance."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(project_root, 'data')
    
    dfs = []
    # Attempt to load both files
    for f in ['requirements.csv', 'tvet_requirements.csv']:
        path = os.path.join(data_folder, f)
        if os.path.exists(path):
            try:
                dfs.append(load_and_clean_data(path))
            except Exception as e:
                st.error(f"Error loading {f}: {e}")
    
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()

df_courses = get_data()

# --- 3. SIDEBAR (The Input) ---
st.sidebar.title("📝 Keputusan SPM")
st.sidebar.caption("Masukkan gred percubaan atau sebenar anda.")

grade_opts = ["A+", "A", "A-", "B+", "B", "C+", "C", "D", "E", "G", "Tidak Ambil"]

with st.sidebar.form("grades_form"):
    # Core Subjects
    bm = st.selectbox("Bahasa Melayu", grade_opts, index=5)
    eng = st.selectbox("Bahasa Inggeris", grade_opts, index=5)
    hist = st.selectbox("Sejarah", grade_opts, index=6)
    math = st.selectbox("Matematik", grade_opts, index=5)
    sci = st.selectbox("Sains", grade_opts, index=5)
    
    # Optional / Stream Subjects
    st.markdown("---")
    st.caption("Subjek Elektif (Jika ada)")
    addmath = st.selectbox("Matematik Tambahan", ["Tidak Ambil"] + grade_opts, index=0)
    phy = st.selectbox("Fizik", ["Tidak Ambil"] + grade_opts, index=0)
    chem = st.selectbox("Kimia", ["Tidak Ambil"] + grade_opts, index=0)
    bio = st.selectbox("Biologi", ["Tidak Ambil"] + grade_opts, index=0)
    
    # Basic Demographics (Hardcoded for MVP Phase 1)
    gender = st.radio("Jantina", ["Lelaki", "Perempuan"], horizontal=True)
    
    submitted = st.form_submit_button("🚀 Semak Kelayakan")

# --- 4. MAIN PAGE ---
st.title("🎓 Hala Tuju SPM")
st.write("Temui haluan pendidikan anda di **Politeknik, IKBN, dan Kolej Komuniti**.")

if submitted:
    # A. Build Profile
    grades = {
        'bm': bm, 'eng': eng, 'hist': hist, 'math': math, 'sci': sci,
        'addmath': addmath, 'phy': phy, 'chem': chem, 'bio': bio
    }
    # Filter out "Tidak Ambil"
    grades = {k: v for k, v in grades.items() if v != "Tidak Ambil"}
    
    student = StudentProfile(
        grades=grades,
        gender=gender,
        nationality='Warganegara', # Default
        colorblind='Tidak',        # Default
        disability='Tidak'         # Default
    )

    # B. The Magic Wait (Psychology)
    with st.spinner("Sedang menganalisis 1,000+ kursus..."):
        time.sleep(0.6)
        dash = generate_dashboard_data(student, df_courses)

    # C. The Reveal
    if dash['total_matches'] > 0:
        # Hero Section
        st.success(f"🎉 Tahniah! Anda layak memohon **{dash['total_matches']} Kursus**.")
        
        # Summary Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Politeknik", dash['summary_stats'].get('Politeknik', 0))
        c2.metric("IKBN / ILP", dash['summary_stats'].get('IKBN / ILP (Skills)', 0))
        c3.metric("Kolej Komuniti", dash['summary_stats'].get('Kolej Komuniti', 0))
        
        st.markdown("---")
        st.subheader("🌟 3 Pilihan Strategik Anda")
        st.write("Berdasarkan keputusan anda, ini adalah pilihan terbaik:")
        
        # Top 3 Cards
        for i, pick in enumerate(dash['featured_matches']):
            with st.expander(f"#{i+1}: {pick['course_name']} ({pick['quality']})", expanded=True):
                c_left, c_right = st.columns([3, 1])
                with c_left:
                    st.write(f"🏫 **{pick['institution']}**")
                    st.caption(f"Kategori: {pick['type']}")
                with c_right:
                    # Functional Button (Stateful)
                    if st.button("Simpan ❤️", key=f"save_{i}"):
                        st.toast(f"Disimpan: {pick['course_name']}")

        # The Nudge (Blurred List)
        st.markdown("---")
        st.write(f"**...dan {dash['total_matches'] - 3} lagi kursus yang sepadan.**")
        
        # Visual Fake Blur HTML
        st.markdown("""
        <div class='locked-blur'>
            <p>4. Diploma Kejuruteraan Mekanikal (Poli)</p>
            <p>5. Sijil Teknologi Elektrik (IKBN)</p>
            <p>6. Diploma Akauntansi (Poli)</p>
            <p>7. Sijil Pastri (KK)</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.warning("🔒 **Daftar Akaun Percuma** untuk melihat senarai penuh dan muat turun panduan strategi UPU anda.")
        
        c_btn1, c_btn2 = st.columns([1,2])
        with c_btn2:
            st.button("🔓 Buka Senarai Penuh", type="primary")

    else:
        st.error("Tiada padanan ditemui buat masa ini.")
        st.info("💡 **Tip:** Cuba semak semula gred anda. Pastikan anda memilih 'Lulus' untuk subjek Bahasa Melayu dan Sejarah jika berkenaan.")

else:
    # Landing Page State (Before Submit)
    st.info("👈 Sila masukkan keputusan peperiksaan anda di sebelah kiri untuk bermula.")