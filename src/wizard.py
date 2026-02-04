# wizard.py
"""
Step-by-step onboarding wizard for new users.
Replaces sidebar-based grade entry with a guided flow.

Flow:
1. Welcome → 2. Stream → 3. Grades → 4. Profile → 5. Results (Dashboard)
"""

import streamlit as st

# --- CONSTANTS ---
WIZARD_STEPS = ['welcome', 'stream', 'grades', 'profile', 'complete']
STEP_LABELS = {
    'welcome': ('👋', 'Mula'),
    'stream': ('📚', 'Aliran'),
    'grades': ('📝', 'Keputusan'),
    'profile': ('👤', 'Profil'),
    'complete': ('✅', 'Selesai')
}

SLIDER_GRADES = ["G", "E", "D", "C", "C+", "B", "B+", "A-", "A", "A+"]

# Core subjects all students take
CORE_SUBJECTS = [
    ('bm', 'Bahasa Melayu'),
    ('eng', 'English'),
    ('math', 'Mathematics'),
    ('hist', 'Sejarah'),
    ('sci', 'Science')
]

# Stream-specific subjects
STREAM_SUBJECTS = {
    'STEM A': [
        ('addmath', 'Additional Maths'),
        ('phy', 'Physics'),
        ('chem', 'Chemistry'),
        ('bio', 'Biology')
    ],
    'Arts': [
        ('ekonomi', 'Ekonomi'),
        ('geo', 'Geografi'),
        ('poa', 'Prinsip Perakaunan'),
        ('business', 'Perniagaan')
    ],
    'STEM B/C': [
        ('addmath', 'Additional Maths'),
        ('phy', 'Physics'),
        ('chem', 'Chemistry'),
        ('tech', 'Technical/Vocational')
    ]
}


def get_wizard_step():
    """Get current wizard step from session state."""
    return st.session_state.get('wizard_step', 'welcome')


def set_wizard_step(step):
    """Set wizard step in session state."""
    st.session_state['wizard_step'] = step


def get_step_index(step):
    """Get numeric index of step."""
    return WIZARD_STEPS.index(step) if step in WIZARD_STEPS else 0


def render_progress_bar(current_step):
    """Render visual progress indicator."""
    current_idx = get_step_index(current_step)
    total_steps = len(WIZARD_STEPS) - 1  # Exclude 'complete'

    # Build progress dots
    dots_html = ""
    for i, step in enumerate(WIZARD_STEPS[:-1]):  # Exclude 'complete'
        icon, label = STEP_LABELS[step]

        if i < current_idx:
            # Completed step
            dot_style = "background: #10B981; color: white;"
            line_style = "background: #10B981;"
        elif i == current_idx:
            # Current step
            dot_style = "background: #6366F1; color: white; box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.3);"
            line_style = "background: #E5E7EB;"
        else:
            # Future step
            dot_style = "background: #E5E7EB; color: #9CA3AF;"
            line_style = "background: #E5E7EB;"

        dots_html += f'''
            <div style="display: flex; flex-direction: column; align-items: center; z-index: 1;">
                <div style="width: 40px; height: 40px; border-radius: 50%; display: flex;
                            align-items: center; justify-content: center; font-size: 18px; {dot_style}">
                    {icon}
                </div>
                <span style="font-size: 11px; margin-top: 4px; color: {'#374151' if i <= current_idx else '#9CA3AF'};">
                    {label}
                </span>
            </div>
        '''

        # Add connecting line (except after last step)
        if i < len(WIZARD_STEPS) - 2:
            dots_html += f'''
                <div style="flex: 1; height: 3px; {line_style} margin: 0 -5px; margin-top: -20px;"></div>
            '''

    st.markdown(f'''
        <div style="display: flex; align-items: flex-start; justify-content: space-between;
                    padding: 20px 10px; margin-bottom: 20px;">
            {dots_html}
        </div>
    ''', unsafe_allow_html=True)


def render_step_welcome(t):
    """Step 1: Welcome screen with value proposition and language selection."""

    # Language selection at top
    st.markdown("""
        <div style="text-align: center; margin-bottom: 10px;">
            <span style="color: #6B7280; font-size: 0.9em;">🌐 Pilih Bahasa / Choose Language</span>
        </div>
    """, unsafe_allow_html=True)

    # Language buttons
    lang_col1, lang_col2, lang_col3 = st.columns(3)

    current_lang = st.session_state.get('lang_code', 'bm')

    with lang_col1:
        bm_style = "primary" if current_lang == 'bm' else "secondary"
        if st.button("🇲🇾 Bahasa Melayu", key="lang_bm", use_container_width=True,
                     type=bm_style if current_lang == 'bm' else "secondary"):
            st.session_state['lang_code'] = 'bm'
            st.rerun()

    with lang_col2:
        en_style = "primary" if current_lang == 'en' else "secondary"
        if st.button("🇬🇧 English", key="lang_en", use_container_width=True,
                     type=en_style if current_lang == 'en' else "secondary"):
            st.session_state['lang_code'] = 'en'
            st.rerun()

    with lang_col3:
        ta_style = "primary" if current_lang == 'ta' else "secondary"
        if st.button("🇮🇳 தமிழ்", key="lang_ta", use_container_width=True,
                     type=ta_style if current_lang == 'ta' else "secondary"):
            st.session_state['lang_code'] = 'ta'
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Welcome header - localized
    welcome_headers = {
        'bm': ("🎓 Hala Tuju", "Cari kursus terbaik untuk anda selepas SPM"),
        'en': ("🎓 Hala Tuju", "Find the best courses for you after SPM"),
        'ta': ("🎓 ஹாலா துஜு", "SPM பிறகு உங்களுக்கான சிறந்த படிப்புகளைக் கண்டறியுங்கள்")
    }

    title, subtitle = welcome_headers.get(current_lang, welcome_headers['bm'])

    st.markdown(f"""
        <div style="text-align: center; padding: 20px 20px 40px 20px;">
            <h1 style="font-size: 2.5em; margin-bottom: 10px;">{title}</h1>
            <p style="font-size: 1.3em; color: #6B7280; margin-bottom: 30px;">
                {subtitle}
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Value proposition cards - localized
    card_texts = {
        'bm': [
            ("13,000+ Kursus", "Politeknik, Kolej Komuniti, TVET, Universiti"),
            ("Padanan Tepat", "Berdasarkan keputusan SPM anda"),
            ("Percuma", "Tiada yuran, tiada pendaftaran")
        ],
        'en': [
            ("13,000+ Courses", "Polytechnic, Community College, TVET, University"),
            ("Accurate Matching", "Based on your SPM results"),
            ("Free", "No fees, no registration")
        ],
        'ta': [
            ("13,000+ படிப்புகள்", "பாலிடெக்னிக், சமூகக் கல்லூரி, TVET, பல்கலைக்கழகம்"),
            ("துல்லியமான பொருத்தம்", "உங்கள் SPM முடிவுகளின் அடிப்படையில்"),
            ("இலவசம்", "கட்டணம் இல்லை, பதிவு இல்லை")
        ]
    }

    cards = card_texts.get(current_lang, card_texts['bm'])
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
            <div style="text-align: center; padding: 20px; background: #F0FDF4; border-radius: 12px;">
                <div style="font-size: 2em;">📊</div>
                <h4 style="margin: 10px 0 5px 0;">{cards[0][0]}</h4>
                <p style="font-size: 0.9em; color: #6B7280; margin: 0;">{cards[0][1]}</p>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div style="text-align: center; padding: 20px; background: #EEF2FF; border-radius: 12px;">
                <div style="font-size: 2em;">🎯</div>
                <h4 style="margin: 10px 0 5px 0;">{cards[1][0]}</h4>
                <p style="font-size: 0.9em; color: #6B7280; margin: 0;">{cards[1][1]}</p>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
            <div style="text-align: center; padding: 20px; background: #FEF3C7; border-radius: 12px;">
                <div style="font-size: 2em;">⚡</div>
                <h4 style="margin: 10px 0 5px 0;">{cards[2][0]}</h4>
                <p style="font-size: 0.9em; color: #6B7280; margin: 0;">{cards[2][1]}</p>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # CTA Button - localized
    cta_texts = {
        'bm': "🚀 Mula Sekarang",
        'en': "🚀 Start Now",
        'ta': "🚀 இப்போது தொடங்கு"
    }
    cta_text = cta_texts.get(current_lang, cta_texts['bm'])

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(cta_text, use_container_width=True, type="primary", key="btn_start_wizard"):
            set_wizard_step('stream')
            st.rerun()


def render_step_stream(t):
    """Step 2: Stream selection with visual cards."""

    st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <h2>📚 Pilih Aliran SPM Anda</h2>
            <p style="color: #6B7280;">Ini membantu kami tunjukkan subjek yang berkaitan</p>
        </div>
    """, unsafe_allow_html=True)

    # Stream cards
    col1, col2, col3 = st.columns(3)

    streams = [
        ('STEM A', '🔬', 'Sains Tulen', 'Physics, Chemistry, Biology, Add Maths', col1),
        ('Arts', '📖', 'Sastera/Perdagangan', 'Ekonomi, Geografi, Akaun, Perniagaan', col2),
        ('STEM B/C', '⚙️', 'Teknikal/Vokasional', 'Physics, Chemistry, Technical subjects', col3)
    ]

    selected_stream = st.session_state.get('wizard_stream', None)

    for stream_id, icon, title, subjects, col in streams:
        with col:
            is_selected = selected_stream == stream_id
            border_color = "#6366F1" if is_selected else "#E5E7EB"
            bg_color = "#EEF2FF" if is_selected else "#FFFFFF"

            st.markdown(f"""
                <div style="border: 2px solid {border_color}; border-radius: 12px; padding: 20px;
                            text-align: center; background: {bg_color}; min-height: 180px;
                            cursor: pointer; transition: all 0.2s;">
                    <div style="font-size: 2.5em;">{icon}</div>
                    <h3 style="margin: 10px 0 5px 0;">{title}</h3>
                    <p style="font-size: 0.85em; color: #6B7280; margin: 0;">{subjects}</p>
                </div>
            """, unsafe_allow_html=True)

            if st.button(f"Pilih {stream_id}", key=f"btn_stream_{stream_id}", use_container_width=True):
                st.session_state['wizard_stream'] = stream_id
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Navigation
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("← Kembali", key="btn_back_stream"):
            set_wizard_step('welcome')
            st.rerun()

    with col3:
        if selected_stream:
            if st.button("Seterusnya →", key="btn_next_stream", type="primary"):
                set_wizard_step('grades')
                st.rerun()


def render_step_grades(t):
    """Step 3: Grade entry with sliders."""

    stream = st.session_state.get('wizard_stream', 'STEM A')

    st.markdown(f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <h2>📝 Masukkan Keputusan SPM</h2>
            <p style="color: #6B7280;">Aliran: <b>{stream}</b> • Seret slider ke gred anda</p>
        </div>
    """, unsafe_allow_html=True)

    # Initialize grades in session
    if 'wizard_grades' not in st.session_state:
        st.session_state['wizard_grades'] = {}

    grades = st.session_state['wizard_grades']

    # Core subjects
    st.markdown("### Subjek Teras")

    for key, label in CORE_SUBJECTS:
        current = grades.get(key, 'C')
        if current not in SLIDER_GRADES:
            current = 'C'

        grades[key] = st.select_slider(
            label,
            options=SLIDER_GRADES,
            value=current,
            key=f"grade_{key}"
        )

    # Stream-specific subjects
    st.markdown(f"### Subjek Elektif ({stream})")

    stream_subjects = STREAM_SUBJECTS.get(stream, [])
    for key, label in stream_subjects:
        current = grades.get(key, 'C')
        if current not in SLIDER_GRADES:
            current = 'C'

        grades[key] = st.select_slider(
            label,
            options=SLIDER_GRADES,
            value=current,
            key=f"grade_{key}"
        )

    # Save grades
    st.session_state['wizard_grades'] = grades

    st.markdown("<br>", unsafe_allow_html=True)

    # Navigation
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("← Kembali", key="btn_back_grades"):
            set_wizard_step('stream')
            st.rerun()

    with col3:
        if st.button("Seterusnya →", key="btn_next_grades", type="primary"):
            set_wizard_step('profile')
            st.rerun()


def render_step_profile(t):
    """Step 4: Profile details (gender, health)."""

    st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <h2>👤 Maklumat Profil</h2>
            <p style="color: #6B7280;">Beberapa kursus mempunyai syarat khas</p>
        </div>
    """, unsafe_allow_html=True)

    # Gender
    st.markdown("### Jantina")
    gender = st.radio(
        "Pilih jantina anda",
        ["Lelaki", "Perempuan"],
        horizontal=True,
        key="wizard_gender",
        label_visibility="collapsed"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Colorblindness
    st.markdown("### Buta Warna")
    st.markdown("*Sesetengah kursus teknikal memerlukan penglihatan warna normal*")
    colorblind = st.radio(
        "Adakah anda buta warna?",
        ["Tidak", "Ya"],
        horizontal=True,
        key="wizard_colorblind",
        label_visibility="collapsed"
    )
    st.markdown("[🔗 Ujian buta warna percuma](https://www.colorlitelens.com/color-blind-test)", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Disability
    st.markdown("### OKU (Orang Kurang Upaya)")
    st.markdown("*Sesetengah kursus fizikal memerlukan kecergasan*")
    disability = st.radio(
        "Adakah anda OKU?",
        ["Tidak", "Ya"],
        horizontal=True,
        key="wizard_disability",
        label_visibility="collapsed"
    )

    # Store in session
    st.session_state['wizard_profile'] = {
        'gender': gender,
        'colorblind': colorblind,
        'disability': disability
    }

    st.markdown("<br>", unsafe_allow_html=True)

    # Navigation
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("← Kembali", key="btn_back_profile"):
            set_wizard_step('grades')
            st.rerun()

    with col3:
        if st.button("🔍 Lihat Kursus", key="btn_complete_wizard", type="primary"):
            # Mark wizard as complete
            st.session_state['wizard_complete'] = True
            set_wizard_step('complete')
            st.rerun()


def render_wizard(t):
    """Main wizard renderer - dispatches to current step."""

    current_step = get_wizard_step()

    # Inject CSS for mobile swipe prevention
    st.markdown("""
        <style>
            /* Prevent horizontal swipe on wizard */
            .wizard-container {
                touch-action: pan-y !important;
                overscroll-behavior-x: none !important;
            }

            /* Make buttons more touch-friendly */
            .stButton > button {
                min-height: 48px !important;
                font-size: 1.1em !important;
            }

            /* Progress bar responsive */
            @media (max-width: 768px) {
                .stColumns > div {
                    padding: 5px !important;
                }
            }
        </style>
        <div class="wizard-container">
    """, unsafe_allow_html=True)

    # Only show progress bar if past welcome
    if current_step != 'welcome':
        render_progress_bar(current_step)

    # Dispatch to current step
    if current_step == 'welcome':
        render_step_welcome(t)
    elif current_step == 'stream':
        render_step_stream(t)
    elif current_step == 'grades':
        render_step_grades(t)
    elif current_step == 'profile':
        render_step_profile(t)
    elif current_step == 'complete':
        # This should not render - main.py will take over
        pass

    st.markdown("</div>", unsafe_allow_html=True)


def get_wizard_results():
    """Get collected data from wizard for dashboard calculation."""
    return {
        'grades': st.session_state.get('wizard_grades', {}),
        'stream': st.session_state.get('wizard_stream', 'STEM A'),
        'profile': st.session_state.get('wizard_profile', {
            'gender': 'Lelaki',
            'colorblind': 'Tidak',
            'disability': 'Tidak'
        })
    }


def is_wizard_complete():
    """Check if wizard has been completed."""
    return st.session_state.get('wizard_complete', False)


def reset_wizard():
    """Reset wizard state."""
    keys_to_clear = ['wizard_step', 'wizard_stream', 'wizard_grades',
                     'wizard_profile', 'wizard_complete']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
