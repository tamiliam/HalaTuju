# src/translations.py

LANGUAGES = {
    "en": "English",
    "bm": "Bahasa Melayu",
    "ta": "தமிழ் (Tamil)"
}

TEXTS = {
    "en": {
        # Core UI
        "sb_title": "SPM Results",
        "sb_caption": "Enter your actual or trial results.",
        "sb_btn_submit": "Check Eligibility",
        "sb_core_subjects": "Core Subjects",
        "sb_science_stream": "Science Stream",
        "sb_commerce_stream": "Commerce Stream",
        "sb_arts_electives": "Arts & Language Electives",
        "sb_tech_voc_stream": "Technical & Vocational",
        "sb_opt_subject": "Optional Subjects",
        "sb_gender": "Gender",
        "sb_colorblind": "Color Blind?",
        "sb_disability": "Physical Disability?",
        "link_cb_test": "Not sure? Test here (Free)",
        "cb_test_url": "https://www.colorblindnesstest.org/",
        
        # Options & Inputs
        "opt_not_taken": "Not Taken",
        "gender_male": "Male",
        "gender_female": "Female",
        "opt_yes": "Yes",
        "opt_no": "No",

        # Profile Labels
        "lbl_colorblind": "Color Blind",
        "lbl_disability": "Physical Disability",
        "lbl_fullname": "Full Name",
        "lbl_gender": "Gender",
        "lbl_phone": "Phone",
        "header_edit_details": "✏️ Edit Details",
        "header_edit_grades": "📝 Edit Grades",
        "btn_save_changes": "Save Changes",
        "btn_save_grades": "Save Grades",
        "btn_update_profile": "Update Profile",
        
        # New Logistics Labels
        "lbl_preferred_name": "Preferred Name",
        "lbl_email": "Email (Optional)",
        "lbl_city": "City",
        "lbl_state": "State",
        "lbl_financial": "Financial Pressure",
        "lbl_travel": "Willingness to travel for education",
        
        # Financial Options
        "fin_low": "Low (family can support)",
        "fin_med": "Medium (some help, but careful)",
        "fin_high": "High (need lowest-cost option)",
        
        # Travel Options
        "travel_near": "Near home only",
        "travel_state": "Same state",
        "travel_peninsula": "Anywhere in Semenanjung Malaysia",
        "travel_any": "No restrictions",
        
        # Subject Names
        "subj_bm": "Malay Language",
        "subj_eng": "English",
        "subj_hist": "History",
        "subj_math": "Mathematics",
        "subj_moral": "Islam/Moral",
        "subj_sci": "Science",
        
        "subj_addmath": "Add Maths",
        "subj_phy": "Physics",
        "subj_chem": "Chemistry",
        "subj_bio": "Biology",

        "subj_ekonomi": "Economics",
        "subj_business": "Business",
        "subj_poa": "Accounting (POA)",
        "subj_geo": "Geography",
        
        "subj_3rd_lang": "Tamil/Chinese/Arabic",
        "subj_lit": "Lit (BM/Eng/Chi/Tam)",
        "subj_psv": "Visual Arts (Seni)",
        
        "subj_tech": "Engineering/Others",
        "subj_voc": "Catering/Auto/Vocational",

        # Technical/Engineering Subjects (NEW)
        "subj_eng_civil": "Civil Engineering Studies",
        "subj_eng_mech": "Mechanical Engineering Studies",
        "subj_eng_elec": "Electrical & Electronic Eng.",
        "subj_eng_draw": "Engineering Drawing",
        "subj_gkt": "Technical Communication Graphics",
        "subj_kelestarian": "Sustainability Basics",
        "subj_reka_cipta": "Design & Innovation",

        # IT/Computing Subjects (NEW)
        "subj_comp_sci": "Computer Science",
        "subj_multimedia": "Multimedia Production",
        "subj_digital_gfx": "Digital Graphics Design",

        # Vocational Subjects - MPV (NEW)
        "subj_voc_construct": "Domestic Construction",
        "subj_voc_plumb": "Domestic Plumbing",
        "subj_voc_wiring": "Domestic Wiring",
        "subj_voc_weld": "Arc Welding",
        "subj_voc_auto": "Automobile Servicing",
        "subj_voc_elec_serv": "Electrical Equipment Servicing",
        "subj_voc_food": "Food Crops",
        "subj_voc_landscape": "Landscape & Nursery",
        "subj_voc_catering": "Catering & Serving",
        "subj_voc_tailoring": "Tailoring & Fashion Design",

        # Other Electives (NEW)
        "subj_sports_sci": "Sports Science",
        "subj_music": "Music Education",

        # Landing & Processing
        "header_title": "Hala Tuju Pelajar Lepasan SPM",
        "header_subtitle": "See which Polytechnic, IKBN, and Community College courses you qualify for.",
        "landing_msg": """Welcome!

HalaTuju was created for post-SPM students. It helps you explore study pathways based on your results and preferences, step by step.

How it works:

**1. Enter Your Results**  
👈 Enter your SPM results in side panel. Click on >> symbol at top left-hand corner if side panel is not visible.

**2. See What You’re Eligible For**  
We’ll instantly show you courses where you meet the minimum requirements.

**3. Explore Your Best Matches**  
Answer a short 1-minute quiz. We’ll rank eligible courses based on how well they fit you — not just your grades.

**4. Understand the Rankings (Optional)**  
If you want deeper clarity, unlock a personalised Counsellor’s Report that explains why certain courses rise to the top and what you should consider next.

Ready to explore your options?
Start by entering your results — you can decide the next steps as you go. 🚀""",
        "spinner_msg": "Checking official entry requirements...",
        
        # Results
        "hero_success": "🎉 Good news! You meet the entry requirements for **{count} Courses**.",
        'hero_eligible_dynamic': '🎉 Good news! You qualify for **{courses} Courses** across **{locs} Locations**.',
        "hero_fail": "No direct matches found yet.",
        "hero_tip": "Tip: Ensure you entered a pass for Malay/History if required.",
        
        # Stats & Tables
        "teaser_title": "🌟 Your Top 3 Strategic Options",
        "teaser_subtitle": "Based on your results, these are solid pathways for you:",
        "btn_save_course": "Shortlist ❤️",
        "btn_saved_toast": "Saved: {course}",
        "locked_count": "...and {remaining} other courses.",
        "locked_cta_title": "Save your results to see the full list",
        "locked_cta_desc": "Don't lose your progress. Create a free profile to view all options.",
        "form_name": "Full Name",
        "form_phone": "WhatsApp Number",
        "form_email": "Email Address",
        "btn_unlock": "Save & View Full List",
        "toast_success": "Success! Profile saved.",
        "err_missing_info": "Please fill in your Name and Phone number.",
        
        # VALIDATION ERRORS
        "err_name_short": "❌ Name is too short.",
        "err_name_invalid": "❌ Invalid characters in Name.",
        "err_email_invalid": "❌ Invalid Email Address format.",
        "err_phone_short": "❌ Phone number is too short.",
        "err_phone_invalid": "❌ Invalid Malaysia Phone Number (e.g. 012-3456789).",
        
        "header_top_matches": "🏆 Top 5 Recommendations",
        "header_other_matches": "📋 Other Eligible Courses",
        "lbl_duration": "Duration",
        "lbl_fees": "Fees",
        "lbl_mode": "Mode",

        "unlocked_alert": "🔓 Full Report Unlocked! Explore your options below.",
        "table_title": "📋 Your Complete Course List",
        "table_col_course": "Course Name",
        "table_col_inst": "Institution",
        "table_col_cat": "Category",
        "table_col_status": "Status",
        "filter_label": "Filter by Category:",
        "filter_count": "Showing {shown} of {total} courses.",
        "contact_counselor": "Contact our counselors for application help.",
        
        # About / Trust Section (NEW)
        "about_title": "ℹ️ About & Methodology",
        "about_desc": """
        **How does this work?**
        We use the official entry requirements published by the Ministry of Higher Education (UPU) and TVET agencies. 
        We match your grades against the specific minimum requirements for over 1,000 courses.
        
        **Disclaimer:**
        This tool is a guidance calculator, not an official application. Meeting the minimum requirements does not guarantee admission, as competition for seats varies every year.
        """,
        "footer_credits": "Built with ❤️ for Malaysian Students.",
        
        # Admin Section (NEW)
        "admin_login": "Admin Access",
        "admin_success": "Welcome back, Commander.",
        "admin_view_leads": "View Student Leads",
        "admin_download": "Download CSV",
        
        # Dashboard Specific (New)
        "quality_safe": "Safe Bet 🟢",
        "quality_good": "Good Match 🔵",
        "quality_reach": "Reach 🟡",
        "help_pin": "Remember this PIN!",
        "toast_profile_saved": "Profile Saved Successfully!",
        "err_save_failed": "Save Failed: {error}",
        "inst_poly": "Polytechnic",
        "inst_kk": "Community College",
        "inst_iljtm": "ILJTM",
        "inst_ilkbs": "ILKBS",
        "inst_other": "TVET / Other",
        "inst_ipg": "IPG (Teacher Training)",
        "inst_form6": "Form 6 (STPM)",
        "inst_matrik": "Matriculation",
        "inst_uni": "Public University",
        "unknown_course": "Unknown Course",
        "unknown_inst": "Unknown Inst",
        "unknown_state": "Malaysia",
        "status_eligible": "Eligible",
        "status_not_eligible": "Not Eligible",
        "status_eligible": "Eligible",
        "status_eligible": "Eligible",
        "status_not_eligible": "Not Eligible",
        "filter_state": "Filter Location:",
        
        # Quiz
        "quiz_title": "🧭 Discovery Quiz",
        "quiz_question_count": "Question {step} of {total}",
        "quiz_generating": "Generating your fit...",
        "quiz_saved": "Results Saved!",
        "quiz_complete": "Analysis Complete!",
        "quiz_msg_success": """**Thank you!** Your answers have been recorded.
        We have re-ranked the course list based on your personality and interests.
        The courses you see on the **Dashboard** are now personalized just for you.""",
        "quiz_cta_intro": "💡 **Next Step:** Return to the **Dashboard** tab to view your personalized recommendations.",
        "quiz_btn_dashboard": "Go to Dashboard ➡️",
        "quiz_cta_ai": "🔍 **Want to know more?** Click **✨ Deep AI Analysis (Beta)** on the sidebar/dashboard for a full career report.",
        "quiz_debug_label": "🛠️ View Debug Data (Raw Profile)",
        "quiz_return": "Return to Dashboard",
        "btn_back": "⬅️ Back",

        # Auth/Gate
        "gate_subtitle": "Ready to see everything? Unlock your full report now.",
        "gate_pin_instr": "Create a secure PIN to save your results.",
        "lbl_create_pin": "Create 6-Digit PIN",
        "btn_unlock_save": "Unlock & Save Results",
        "msg_account_created": "Account Created! Unlocking...",

        # Profile
        "profile_title": "👤 My Profile",
        "profile_name": "Name",
        "profile_phone": "Phone",
        "btn_back_dash": "⬅️ Back to Dashboard",

        # Sidebar
        "sb_lang": "🌐 Language",
        "sb_logout": "Log Out",
        "sb_retake_quiz": "🔄 Retake Discovery Quiz",
        "sb_start_quiz": "🧭 Start Discovery Quiz",
        "sb_guest_mode": "👋 Guest Mode",
        "sb_returning_user": "🔐 **Returning Users**",
        "sb_login": "Login",
        "sb_welcome": "Welcome back!",
        
        # Post-Quiz Progress Messages
        "progress_analyzing_spm": "📊 Analyzing your SPM results...",
        "progress_understanding_style": "🧠 Understanding your learning style...",
        "progress_finding_courses": "🎯 Finding suitable courses...",
        "progress_ranking_courses": "🔄 Ranking courses...",
        "progress_almost_ready": "✨ Almost ready...",
        
        # Post-Quiz Success
        "quiz_ranking_updated": "✅ Course ranking has been updated!",
        "quiz_view_dashboard_msg": "📊 **Please go to Dashboard to view your recommendations.**",
        "quiz_courses_ranked_msg": "Courses have been arranged according to your suitability based on the Discovery Quiz results.",
        "btn_view_dashboard": "📊 View Dashboard",
        
        # Report Gating
        "report_prompt_explore": "📊 **View the recommended courses in the main page.**\n\nNotice the ranking order.",
        "report_unlock_msg": "💡 **Wondering why these courses are ranked this way?**\n\nCounseling report now available.",

        # Featured Matches
        "feat_title": "🌟 Featured Matches",
        "feat_career": "💼 Career",
        "badge_dur": "Duration",
        "badge_mode": "Mode",
        "badge_fees": "Fees",

        # Engine Audit Messages (Labels & Reasons)
        "chk_malaysian": "Citizen",
        "fail_malaysian": "Malaysian Citizens Only",
        "chk_male": "Gender (Male)",
        "fail_male": "Males Only",
        "chk_female": "Gender (Female)",
        "fail_female": "Females Only",
        "chk_colorblind": "Free from Colorblindness",
        "fail_colorblind": "Cannot be Colorblind",
        "chk_disability": "Physical Health",
        "fail_disability": "Physical Requirements Not Met",
        
        "chk_3m": "3M Condition",
        "fail_3m": "Must Attempt BM and Math (Min Grade G)",
        
        "chk_pass_bm": "Pass BM",
        "fail_pass_bm": "Failed Bahasa Melayu",
        "chk_credit_bm": "Credit BM",
        "fail_credit_bm": "No Credit in Bahasa Melayu",
        "chk_pass_hist": "Pass History",
        "fail_pass_hist": "Failed History",
        "chk_pass_eng": "Pass English",
        "fail_pass_eng": "Failed English",
        "chk_credit_eng": "Credit English",
        "fail_credit_eng": "No Credit in English",
        
        "chk_pass_math": "Pass Math",
        "fail_pass_math": "Failed Mathematics",
        "chk_pass_math_addmath": "Pass Math/AddMath",
        "fail_pass_math_addmath": "Failed Math & Add Math",
        "chk_credit_math": "Credit Math",
        "fail_credit_math": "No Credit in Math or Add Math",
        
        "chk_pass_math_sci_nb": "Pass Math OR Science (No Bio)",
        "fail_pass_math_sci_nb": "Need Pass in Math/Science (No Bio)",
        "chk_pass_sci_tech": "Pass Science (No Bio) OR Technical",
        "fail_pass_sci_tech": "Need Pass in Science (No Bio)/Technical",
        "chk_credit_math_sci": "Credit Math OR Science",
        "fail_credit_math_sci": "Need Credit in Math/Science",
        "chk_credit_math_sci_tech": "Credit Math/Sci/Tech",
        "fail_credit_math_sci_tech": "Need Credit in Math/Sci/Tech",
        
        "chk_credit_bmbi": "Credit BM OR English",
        "fail_credit_bmbi": "Need Credit in BM or English",
        "chk_credit_stv": "Credit Science/Vocational",
        "fail_credit_stv": "Need Credit in Science/Vocational",
        "chk_pass_stv": "Science/Vocational Stream",
        "fail_pass_stv": "Need Pass in Science/Vocational",
        
        "chk_credit_sf": "Credit Science/Physics",
        "fail_credit_sf": "Need Credit in Science or Physics",
        "chk_credit_sfmt": "Credit Science/Physics/AddMath",
        "fail_credit_sfmt": "Need Credit in Science/Physics/AddMath",
        
        "chk_min_credit": "Minimum {min_c} Credits",
        "fail_min_credit": "Only {credits} Credits (Need {min_c})",
        "chk_min_pass": "Minimum {min_p} Passes",
        "fail_min_pass": "Only {passes} Passes",
        
        # New Requirement Flags
        "req_interview_note": "📋 Candidates are required to appear for an interview.",
        "req_single_note": "💍 Only open to unmarried applicants (IKTBN Termeloh).",
        
        # WhatsApp Share
        "wa_share_msg": """Hi Mum/Dad,

I just checked my options after SPM on this app called Hala Tuju. It suggested a few courses that might fit my results:

{courses}
I’m not sure yet, but these look okay. Can we discuss this later?
https://halatuju.streamlit.app""",
        "counselor_report": "Counselor Report",
        "more_details": "More details ↗",
        "worth_considering": "👍 Worth Considering",
        "filter_options": "🌪️ Filter Options",
        "lbl_search": "Search Courses",
        "search_placeholder": "Type course name or institution...",
        "filter_by_inst_type": "By Institution Type",
        "filter_by_state": "By State",
        "filter_by_field": "By Field of Education",
        "filter_by_level": "By Level of Education",
        "lbl_institution": "Institution",
        "lbl_course": "Course",
        "lbl_state": "State",
        "lbl_page_count": "Page <b>{current}</b> of <b>{total}</b>",
        "btn_download_pdf": "📄 Download PDF",
        "btn_share_wa": "📲 Share with Parent",
        "btn_print_report": "🖨️ Print Report",
        "btn_print_report": "🖨️ Print Report",
        "lbl_generated_by": "Generated by {counsellor} • Engine: {model}",
        "err_report_unavailable": "Report not available. Please retake the Discovery Quiz.",
        "lbl_preferred_name_display": "Preferred Name:",
        "err_city_invalid": "❌ City: Only alphabets and spaces allowed.",
        "msg_explore_unlock": "💡 **Explore courses to unlock report**",
        "btn_counselor_lock": "🔒 Counselor Report",
        "lbl_key_factors": "✨ Key Matching Factors ({count})",
        "err_pin_length": "❌ PIN must be 6 digits",
        "ph_phone": "e.g. 012-3456789",
        "progress_messages": [
            "🔍 Analyzing SPM results & academic strengths...",
            "🧠 Matching learning style & career interests...",
            "🏢 Checking campus availability & locations...",
            "✨ Strategizing your best pathways...",
            "✅ Report almost ready..."
        ]
    },
    
    "bm": {
        # Core UI
        "sb_title": "Keputusan SPM",
        "sb_caption": "Masukkan gred percubaan atau sebenar.",
        "sb_btn_submit": "Semak Kelayakan",
        "sb_core_subjects": "Subject Teras",
        "sb_science_stream": "Aliran Sains",
        "sb_commerce_stream": "Aliran Perdagangan",
        "sb_arts_electives": "Elektif Sastera & Bahasa",
        "sb_tech_voc_stream": "Teknikal & Vokasional",
        "sb_opt_subject": "Subjek Elektif",
        "sb_gender": "Jantina",
        "sb_colorblind": "Buta Warna?",
        "sb_disability": "Kecacatan Fizikal?",
        "link_cb_test": "Tidak pasti? Uji di sini (Percuma)",
        "cb_test_url": "https://www.colorblindnesstest.org/",
        
        # Options & Inputs
        "opt_not_taken": "Tidak Ambil",
        "gender_male": "Lelaki",
        "gender_female": "Perempuan",
        "opt_yes": "Ya",
        "opt_no": "Tidak",

        # Profile Labels
        "lbl_colorblind": "Buta Warna",
        "lbl_disability": "Kecacatan Fizikal",
        "lbl_fullname": "Nama Penuh",
        "lbl_gender": "Jantina",
        "lbl_phone": "Telefon",
        "header_edit_details": "✏️ Kemaskini Butiran",
        "header_edit_grades": "📝 Kemaskini Gred",
        "btn_save_changes": "Simpan Perubahan",
        "btn_save_grades": "Simpan Gred",
        "btn_update_profile": "Kemaskini Profil",
        
        # New Logistics Labels
        "lbl_preferred_name": "Nama Pilihan",
        "lbl_email": "Emel (Pilihan)",
        "lbl_city": "Bandar",
        "lbl_state": "Negei",
        "lbl_financial": "Tekanan Kewangan",
        "lbl_travel": "Kesanggupan Berjauhan",
        
        # Financial Options
        "fin_low": "Rendah (Keluarga boleh tampung)",
        "fin_med": "Sederhana (Perlu bantuan, berjimat)",
        "fin_high": "Tinggi (Perlu kos paling rendah)",
        
        # Travel Options
        "travel_near": "Berdekatan rumah sahaja",
        "travel_state": "Dalam negeri yang sama",
        "travel_peninsula": "Semenanjung Malaysia sahaja",
        "travel_any": "Tiada halangan (Borneo/Semenanjung)",
        
        # Subject Names
        "subj_bm": "Bahasa Melayu",
        "subj_eng": "Bahasa Inggeris",
        "subj_hist": "Sejarah",
        "subj_math": "Matematik",
        "subj_moral": "P. Islam/Moral",
        
        "subj_addmath": "Matematik Tambahan",
        "subj_phy": "Fizik",
        "subj_chem": "Kimia",
        "subj_bio": "Biologi",

        "subj_sci": "Sains",
        "subj_ekonomi": "Ekonomi",
        "subj_business": "Perniagaan",
        "subj_poa": "Prinsip Perakaunan",
        "subj_geo": "Geografi",
        
        "subj_3rd_lang": "B. Tamil/Cina/Arab",
        "subj_lit": "Kesusasteraan",
        "subj_psv": "Pendidikan Seni Visual",
        
        "subj_tech": "Kejuruteraan/Lain-lain",
        "subj_voc": "Katering/Auto/Vokasional",

        # Technical/Engineering Subjects (NEW)
        "subj_eng_civil": "Pengajian Kejuruteraan Awam",
        "subj_eng_mech": "Pengajian Kejuruteraan Mekanikal",
        "subj_eng_elec": "Peng. Kejuruteraan Elektrik & Elektronik",
        "subj_eng_draw": "Lukisan Kejuruteraan",
        "subj_gkt": "Grafik Komunikasi Teknikal",
        "subj_kelestarian": "Asas Kelestarian",
        "subj_reka_cipta": "Reka Cipta",

        # IT/Computing Subjects (NEW)
        "subj_comp_sci": "Sains Komputer",
        "subj_multimedia": "Produksi Multimedia",
        "subj_digital_gfx": "Reka Bentuk Grafik Digital",

        # Vocational Subjects - MPV (NEW)
        "subj_voc_construct": "Pembinaan Domestik",
        "subj_voc_plumb": "Kerja Paip Domestik",
        "subj_voc_wiring": "Pendawaian Domestik",
        "subj_voc_weld": "Kimpalan Arka",
        "subj_voc_auto": "Menservis Automobil",
        "subj_voc_elec_serv": "Menservis Peralatan Elektrik Domestik",
        "subj_voc_food": "Tanaman Makanan",
        "subj_voc_landscape": "Landskap dan Nurseri",
        "subj_voc_catering": "Katering dan Penyajian",
        "subj_voc_tailoring": "Jahitan dan Rekaan Pakaian",

        # Other Electives (NEW)
        "subj_sports_sci": "Sains Sukan",
        "subj_music": "Pendidikan Muzik",

        # Landing & Processing
        "header_title": "Hala Tuju Pelajar Lepasan SPM",
        "header_subtitle": "Semak kelayakan anda untuk Politeknik, IKBN, dan Kolej Komuniti.",
        "landing_msg": """Selamat Datang! 🎓

HalaTuju dicipta untuk pelajar lepasan SPM. Ia membantu anda meneroka laluan pengajian yang realistik berdasarkan keputusan dan pilihan anda, langkah demi langkah.

Cara ia berfungsi:

**1. Masukkan Keputusan Anda**  
👈 Klik pada >> simbol di sudut kiri atas dan memasukkan keputusan SPM anda (percubaan atau sebenar).

**2. Lihat Layak Ke Tidak**  
Kami akan tunjukkan serta-merta kursus yang anda melepasi syarat minimum.

**3. Terokai Padanan Terbaik Anda**  
Jawab kuiz pendek 1 minit. Kami akan menyusun kursus yang layak berdasarkan kesesuaian dengan anda — bukan sekadar gred semata-mata.

**4. Fahamkan Kedudukan (Pilihan)**  
Jika anda mahukan penjelasan lebih mendalam, dapatkan Laporan Kaunselor yang diperibadikan yang menjelaskan mengapa kursus tertentu berada di kedudukan teratas dan apa yang patut anda pertimbangkan seterusnya.

Bersedia untuk meneroka pilihan anda?
Mula dengan memasukkan keputusan anda — anda boleh tentukan langkah seterusnya sambil berjalan. 🚀""",
        "spinner_msg": "Sedang menyemak syarat kemasukan rasmi...",
        
        # Results
        "hero_success": "🎉 Berita baik! Anda memenuhi syarat untuk **{count} Kursus**.",
        'hero_eligible_dynamic': '🎉 Berita baik! Anda layak untuk **{courses} Kursus** di **{locs} Lokasi**.',
        "hero_fail": "Tiada padanan ditemui buat masa ini.",
        "hero_tip": "Tip: Pastikan anda lulus Bahasa Melayu/Sejarah jika perlu.",
        
        # Stats & Tables
        "teaser_title": "🌟 3 Pilihan Strategik Anda",
        "teaser_subtitle": "Berdasarkan keputusan anda, laluan ini mungkin sesuai:",
        "btn_save_course": "Simpan ❤️",
        "btn_saved_toast": "Disimpan: {course}",
        "locked_count": "...dan {remaining} lagi kursus.",
        "locked_cta_title": "Simpan keputusan untuk lihat senarai penuh",
        "locked_cta_desc": "Jangan hilang data anda. Bina profil percuma untuk lihat semua pilihan.",
        "form_name": "Nama Penuh",
        "form_phone": "No. WhatsApp",
        "form_email": "Alamat Emel",
        "btn_unlock": "Simpan & Lihat Semua",
        "toast_success": "Berjaya! Profil disimpan.",
        "err_missing_info": "Sila isi Nama dan No. Telefon.",
        # VALIDATION ERRORS
        "err_name_short": "❌ Nama terlalu pendek.",
        "err_email_invalid": "❌ Format emel tidak sah.",
        "header_top_matches": "🏆 5 Pilihan Utama",
        "header_other_matches": "📋 Kursus Lain Yang Layak",
        "lbl_duration": "Tempoh",
        "lbl_fees": "Yuran",
        "lbl_mode": "Mod",
        
        "unlocked_alert": "🔓 Laporan Penuh Dibuka! Lihat senarai di bawah.",
        "table_title": "📋 Senarai Lengkap Kursus Anda",
        "table_col_course": "Nama Kursus",
        "table_col_inst": "Institusi",
        "table_col_cat": "Kategori",
        "table_col_status": "Status",
        "filter_label": "Tapis Kategori:",
        "filter_count": "Menunjukkan {shown} daripada {total} kursus.",
        "contact_counselor": "Hubungi kaunselor kami untuk bantuan.",
        
        # About / Trust Section (NEW)
        "about_title": "ℹ️ Mengenai & Metodologi",
        "about_desc": """
        **Bagaimana alat ini berfungsi?**
        Kami menggunakan syarat kemasukan rasmi yang diterbitkan oleh Kementerian Pengajian Tinggi (UPU) dan agensi TVET.
        Kami memadankan gred anda dengan syarat minimum khusus untuk lebih 1,000 kursus.
        
        **Penafian:**
        Alat ini adalah panduan semata-mata, bukan permohonan rasmi. Memenuhi syarat minimum tidak menjamin tempat, kerana persaingan berbeza setiap tahun.
        """,
        "footer_credits": "Dibina dengan ❤️ untuk Pelajar Malaysia.",
        
        # Admin Section (NEW)
        "admin_login": "Akses Admin",
        "admin_success": "Selamat kembali, Tuan.",
        "admin_view_leads": "Lihat Senarai Pelajar",
        "admin_download": "Muat Turun CSV",

        # Dashboard Specific (New)
        "quality_safe": "Pilihan Selamat 🟢",
        "quality_good": "Padanan Baik 🔵",
        "quality_reach": "Cabaran 🟡",
        "help_pin": "Ingat PIN ini!",
        "toast_profile_saved": "Profil Berjaya Disimpan!",
        "err_save_failed": "Gagal Simpan: {error}",
        "inst_poly": "Politeknik",
        "inst_kk": "Kolej Komuniti",
        "inst_iljtm": "ILJTM",
        "inst_ilkbs": "ILKBS",
        "inst_other": "TVET / Lain-lain",
        "inst_ipg": "IPG (Institut Pendidikan Guru)",
        "inst_form6": "Tingkatan 6 (STPM)",
        "inst_matrik": "Matrikulasi",
        "inst_uni": "Universiti Awam",
        "unknown_course": "Kursus Tidak Diketahui",
        "unknown_inst": "Institusi Tidak Diketahui",
        "unknown_state": "Malaysia",
        "status_eligible": "Layak",
        "status_not_eligible": "Tidak Layak",
        "status_eligible": "Layak",
        "status_not_eligible": "Tidak Layak",
        "filter_state": "Tapis Lokasi:",
        
        # Quiz
        "quiz_title": "🧭 Kuiz Penemuan",
        "quiz_question_count": "Soalan {step} dari {total}",
        "quiz_generating": "Sedang menganalisis...",
        "quiz_saved": "Keputusan Disimpan!",
        "quiz_complete": "Analisis Selesai!",
        "quiz_msg_success": """**Terima kasih!** Jawapan anda telah direkodkan.
        Kami telah menyusun semula senarai kursus berdasarkan personaliti dan minat anda.
        Kursus yang anda lihat di **Dashboard** kini telah disesuaikan khas untuk anda.""",
        "quiz_cta_intro": "💡 **Langkah Seterusnya:** Sila kembali ke tab **Dashboard** untuk melihat cadangan kursus anda.",
        "quiz_btn_dashboard": "Ke Halaman Dashboard ➡️",
        "quiz_cta_ai": "🔍 **Ingin tahu lebih lanjut?** Klik **✨ Deep AI Analysis (Beta)** di menu sisi / dashboard untuk mendapatkan laporan kerjaya penuh.",
        "quiz_debug_label": "🛠️ Lihat Data Debug (Profil Mentah)",
        "quiz_return": "Kembali ke Dashboard",
        "btn_back": "⬅️ Kembali",

        # Auth/Gate
        "gate_subtitle": "Sedia untuk lihat semua? Buka laporan penuh anda sekarang.",
        "gate_pin_instr": "Cipda PIN keselamatan untuk simpan keputusan.",
        "lbl_create_pin": "Cipta PIN 6-Digit",
        "btn_unlock_save": "Buka & Simpan Keputusan",
        "msg_account_created": "Akaun Dicipta! Sedang membuka...",

        # Profile
        "profile_title": "👤 Profil Saya",
        "profile_name": "Nama",
        "profile_phone": "Telefon",
        "btn_back_dash": "⬅️ Kembali ke Dashboard",

        # Sidebar
        "sb_lang": "🌐 Bahasa",
        "sb_logout": "Log Keluar",
        "sb_retake_quiz": "🔄 Ambil Semula Kuiz",
        "sb_start_quiz": "🧭 Mula Kuiz Discovery",
        "sb_guest_mode": "👋 Mod Tetamu",
        "sb_returning_user": "🔐 **Pengguna Sedia Ada**",
        "sb_login": "Log Masuk",
        "sb_welcome": "Selamat kembali!",
        
        # Post-Quiz Progress Messages
        "progress_analyzing_spm": "📊 Menganalisis keputusan SPM anda...",
        "progress_understanding_style": "🧠 Memahami gaya pembelajaran anda...",
        "progress_finding_courses": "🎯 Mencari kursus yang sesuai...",
        "progress_ranking_courses": "🔄 Menyusun ranking kursus...",
        "progress_almost_ready": "✨ Hampir siap...",
        
        # Post-Quiz Success
        "quiz_ranking_updated": "✅ Ranking kursus telah dikemas kini!",
        "quiz_view_dashboard_msg": "📊 **Sila ke Dashboard untuk melihat cadangan anda.**",
        "quiz_courses_ranked_msg": "Kursus telah disusun mengikut kesesuaian anda berdasarkan keputusan Discovery Quiz.",
        "btn_view_dashboard": "📊 Lihat Dashboard",
        
        # Report Gating
        "report_prompt_explore": "📊 **Lihat kursus yang dicadangkan di halaman utama.**\n\nPerhatikan susunan ranking.",
        "report_unlock_msg": "💡 **Tertanya-tanya kenapa kursus ini di atas?**\n\nLaporan kaunseling kini tersedia.",

        # Featured Matches
        "feat_title": "🌟 Pilihan Utama",
        "feat_career": "💼 Kerjaya",
        "badge_dur": "Tempoh",
        "badge_mode": "Mod",
        "badge_fees": "Yuran",

        # Engine Audit Messages (Labels & Reasons)
        "chk_malaysian": "Warganegara",
        "fail_malaysian": "Hanya untuk Warganegara",
        "chk_male": "Jantina (Lelaki)",
        "fail_male": "Lelaki Sahaja",
        "chk_female": "Jantina (Wanita)",
        "fail_female": "Wanita Sahaja",
        "chk_colorblind": "Bebas Buta Warna",
        "fail_colorblind": "Tidak boleh rabun warna",
        "chk_disability": "Sihat Tubuh Badan",
        "fail_disability": "Syarat fizikal tidak dipenuhi",
        
        "chk_3m": "Syarat 3M",
        "fail_3m": "Perlu sekurang-kurangnya Gred G dalam BM dan Matematik",
        
        "chk_pass_bm": "Lulus BM",
        "fail_pass_bm": "Gagal Bahasa Melayu",
        "chk_credit_bm": "Kredit BM",
        "fail_credit_bm": "Tiada Kredit Bahasa Melayu",
        "chk_pass_hist": "Lulus Sejarah",
        "fail_pass_hist": "Gagal Sejarah",
        "chk_pass_eng": "Lulus BI",
        "fail_pass_eng": "Gagal Bahasa Inggeris",
        "chk_credit_eng": "Kredit BI",
        "fail_credit_eng": "Tiada Kredit Bahasa Inggeris",
        
        "chk_pass_math": "Lulus Matematik",
        "fail_pass_math": "Gagal Matematik",
        "chk_pass_math_addmath": "Lulus Matematik/AddMath",
        "fail_pass_math_addmath": "Gagal Matematik & Add Math",
        "chk_credit_math": "Kredit Matematik",
        "fail_credit_math": "Tiada Kredit Matematik atau Add Math",
        
        "chk_pass_math_sci_nb": "Lulus Matemaik ATAU Sains (No Bio)",
        "fail_pass_math_sci_nb": "Perlu Lulus Math/Sains (Tiada Bio)",
        "chk_pass_sci_tech": "Lulus Sains (No Bio) ATAU Teknikal",
        "fail_pass_sci_tech": "Perlu Lulus Sains (Tiada Bio)/Teknikal",
        "chk_credit_math_sci": "Kredit Matematik ATAU Sains",
        "fail_credit_math_sci": "Perlu Kredit Math/Sains",
        "chk_credit_math_sci_tech": "Kredit Math/Sains/Teknikal",
        "fail_credit_math_sci_tech": "Perlu Kredit Math/Sains/Teknikal",
        
        "chk_credit_bmbi": "Kredit BM ATAU BI",
        "fail_credit_bmbi": "Perlu Kredit BM atau BI",
        "chk_credit_stv": "Kredit Sains/Vokasional",
        "fail_credit_stv": "Perlu Kredit Sains/Vokasional",
        "chk_pass_stv": "Aliran Sains/Vokasional",
        "fail_pass_stv": "Perlu Lulus Sains/Vokasional",
        
        "chk_credit_sf": "Kredit Sains/Fizik",
        "fail_credit_sf": "Perlu Kredit Sains atau Fizik",
        "chk_credit_sfmt": "Kredit Sains/Fizik/Add Math",
        "fail_credit_sfmt": "Perlu Kredit Sains/Fizik/Add Math",
        
        "chk_min_credit": "Minimum {min_c} Kredit",
        "fail_min_credit": "Hanya {credits} Kredit (Perlu {min_c})",
        "chk_min_pass": "Minimum {min_p} Lulus",
        "fail_min_pass": "Hanya {passes} Lulus",
        
        # New Requirement Flags
        "req_interview_label": "⚠️ Temuduga Diperlukan",
        "req_single_label": "⚠️ Bujang Sahaja",
        "req_interview_note": "📋 Calon dikehendaki menghadiri temuduga.",
        "req_single_note": "💍 Terbuka kepada calon bujang sahaja (IKTBN Termeloh).",
        
        # WhatsApp Share
        "wa_share_msg": """Salam Mak/Ayah,

Saya baru check peluang sambung belajar kat Hala Tuju. Sistem tu ada cadangkan beberapa kursus untuk saya, contohnya:

{courses}
Nampak macam menarik. Nanti bila free, boleh tak kita tengok sama-sama?
https://halatuju.streamlit.app""",
        "counselor_report": "Laporan Kaunselor",
        "more_details": "Maklumat Lanjut ↗",
        "worth_considering": "👍 Boleh Dipertimbangkan",
        "filter_options": "🌪️ Pilihan Tapisan",
        "lbl_search": "Cari Kursus",
        "search_placeholder": "Taip nama kursus atau institusi...",
        "filter_by_inst_type": "Ikut Jenis Institusi",
        "filter_by_state": "Ikut Negeri",
        "filter_by_field": "Ikut Bidang Pengajian",
        "filter_by_level": "Ikut Tahap Pengajian",
        "lbl_institution": "Institusi",
        "lbl_course": "Kursus",
        "lbl_state": "Negeri",
        "lbl_page_count": "Muka Surat <b>{current}</b> dari <b>{total}</b>",
        "btn_download_pdf": "📄 Muat Turun PDF",
        "btn_share_wa": "📲 Kongsi dengan Ibu Bapa",
        "btn_print_report": "🖨️ Cetak Laporan",
        "btn_print_report": "🖨️ Cetak Laporan",
        "lbl_generated_by": "Dijana oleh {counsellor} • Enjin: {model}",
        "err_report_unavailable": "Laporan tidak tersedia. Sila ambil semula Kuiz Penemuan.",
        "lbl_preferred_name_display": "Nama Pilihan:",
        "err_city_invalid": "❌ Bandar: Hanya huruf dan ruang dibenarkan.",
        "msg_explore_unlock": "💡 **Teroka kursus untuk membuka laporan**",
        "btn_counselor_lock": "🔒 Laporan Kaunselor",
        "lbl_key_factors": "✨ Faktor Padanan Utama ({count})",
        "err_pin_length": "❌ PIN mestilah 6 digit",
        "ph_phone": "contoh: 012-3456789",
        "progress_messages": [
            "🔍 Menganalisis keputusan SPM & kekuatan akademik...",
            "🧠 Memadankan gaya pembelajaran & minat kerjaya...",
            "🏢 Menyemak ketersediaan kampus & lokasi...",
            "✨ Menyusun strategi laluan terbaik anda...",
            "✅ Laporan hampir siap..."
        ]
    },

    "ta": {
        # Core UI
        "sb_title": "SPM முடிவுகள்",
        "sb_caption": "உங்கள் தேர்வு முடிவுகளை உள்ளிடவும்.",
        "sb_btn_submit": "தகுதியை சரிபார்க்கவும்",
        "sb_core_subjects": "முதன்மை பாடங்கள்",
        "sb_science_stream": "அறிவியல் பிரிவு",
        "sb_commerce_stream": "வணிகப் பிரிவு",
        "sb_arts_electives": "கலை மற்றும் மொழிப் பாடங்கள்",
        "sb_tech_voc_stream": "தொழில்நுட்பம் & தொழிற்கல்வி",
        "sb_opt_subject": "கூடுதல் பாடங்கள்",
        "sb_gender": "பாலினம்",
        "sb_colorblind": "நிறக்குருடு?",
        "sb_disability": "உடல் ஊனமுற்றவரா?",
        "link_cb_test": "உறுதியாக தெரியவில்லையா? இங்கே சோதிக்கவும் (இலவசம்)",
        "cb_test_url": "https://www.colorblindnesstest.org/",
        
        # Options & Inputs
        "opt_not_taken": "எடுக்கவில்லை",
        "gender_male": "ஆண்",
        "gender_female": "பெண்",
        "opt_yes": "ஆம்",
        "opt_no": "இல்லை",

        # Profile Labels
        "lbl_colorblind": "நிறக்குருடு",
        "lbl_disability": "உடல் ஊனமுற்றவர்",
        "lbl_fullname": "முழு பெயர்",
        "lbl_gender": "பாலினம்",
        "lbl_phone": "தொலைபேசி",
        "header_edit_details": "✏️ விவரங்களைத் திருத்து",
        "header_edit_grades": "📝 தரங்களைத் திருத்து",
        "btn_save_changes": "மாற்றங்களைச் சேமி",
        "btn_save_grades": "தரங்களைச் சேமி",
        "btn_update_profile": "சுயவிவரத்தைப் புதுப்பிக்கவும்", # Update Profile
        
        # New Logistics Labels
        "lbl_preferred_name": "விருப்பமான பெயர்",
        "lbl_email": "மின்னஞ்சல் (விருப்பத் தேர்வு)",
        "lbl_city": "நகரம்",
        "lbl_state": "மாநிலம்",
        "lbl_financial": "நிதி நிலைமை",
        "lbl_travel": "கல்விக்காக பயணம் செய்ய விருப்பம்",
        
        # Financial Options
        "fin_low": "குறைவு (குடும்ப ஆதரவு உள்ளது)",
        "fin_med": "நடுத்தரம் (சில உதவிகள் தேவை)",
        "fin_high": "அதிகம் (குறைந்த செலவு தேவை)",
        
        # Travel Options
        "travel_near": "வீட்டின் அருகில் மட்டும்",
        "travel_state": "அதே மாநிலத்தில்",
        "travel_peninsula": "தீபகற்ப மலேசியாவில் எங்கு வேண்டுமானாலும்",
        "travel_any": "எந்த கட்டுப்பாடுகளும் இல்லை",
        
        # Subject Names
        "subj_bm": "மலாய் மொழி",
        "subj_eng": "ஆங்கிலம்",
        "subj_hist": "வரலாறு",
        "subj_math": "கணிதம்",
        "subj_moral": "இஸ்லாம்/நெறிமுறை",
        
        "subj_addmath": "கூடுதல் கணிதம்",
        "subj_phy": "இயற்பியல்",
        "subj_chem": "வேதியியல்",
        "subj_bio": "உயிரியல்",

        "subj_sci": "அறிவியல்",
        "subj_ekonomi": "பொருளாதாரம்",
        "subj_business": "வணிகம்",
        "subj_poa": "கணக்கியல் (POA)",
        "subj_geo": "புவியியல்",
        
        "subj_3rd_lang": "தமிழ்/சீன/அரபு மொழி",
        "subj_lit": "இலக்கியம்",
        "subj_psv": "காட்சி கலைகள் (Seni)",
        
        "subj_tech": "பொறியியல்/பிற",
        "subj_voc": "கேட்டரிங்/ஆட்டோ/தொழிற்கல்வி",

        # Technical/Engineering Subjects (NEW)
        "subj_eng_civil": "சிவில் பொறியியல் படிப்பு",
        "subj_eng_mech": "இயந்திரப் பொறியியல் படிப்பு",
        "subj_eng_elec": "மின்னணுப் பொறியியல் படிப்பு",
        "subj_eng_draw": "பொறியியல் வரைபடம்",
        "subj_gkt": "தொழில்நுட்ப தகவல் வரைகலை",
        "subj_kelestarian": "நிலைத்தன்மை அடிப்படைகள்",
        "subj_reka_cipta": "வடிவமைப்பு மற்றும் புத்தாக்கம்",

        # IT/Computing Subjects (NEW)
        "subj_comp_sci": "கணினி அறிவியல்",
        "subj_multimedia": "மல்டிமீடியா தயாரிப்பு",
        "subj_digital_gfx": "டிஜிட்டல் கிராஃபிக்ஸ் வடிவமைப்பு",

        # Vocational Subjects - MPV (NEW)
        "subj_voc_construct": "உள்நாட்டு கட்டுமானம்",
        "subj_voc_plumb": "உள்நாட்டு குழாய் வேலை",
        "subj_voc_wiring": "உள்நாட்டு மின்கம்பி வேலை",
        "subj_voc_weld": "ஆர்க் வெல்டிங்",
        "subj_voc_auto": "வாகன சேவை",
        "subj_voc_elec_serv": "மின் சாதன சேவை",
        "subj_voc_food": "உணவுப் பயிர்கள்",
        "subj_voc_landscape": "நிலப்பரப்பு மற்றும் நர்சரி",
        "subj_voc_catering": "கேட்டரிங் மற்றும் பரிமாறல்",
        "subj_voc_tailoring": "தையல் மற்றும் ஆடை வடிவமைப்பு",

        # Other Electives (NEW)
        "subj_sports_sci": "விளையாட்டு அறிவியல்",
        "subj_music": "இசைக் கல்வி",

        # Landing & Processing
        "header_title": "Hala Tuju Pelajar Lepasan SPM (மேற்படிப்பு வழிகாட்டி)",
        "header_subtitle": "பாலிடெக்னிக், IKBN மற்றும் சமூகக் கல்லூரிகளில் உங்களுக்கான வாய்ப்புகளைக் கண்டறியுங்கள்.",
        "landing_msg": """நல்வரவு! 🎓

SPM-க்குப் பிறகு என்ன செய்வது என்று தெரியவில்லையா? நீங்கள் தனியாக இல்லை — இதை நீங்களே கண்டுபிடிக்க வேண்டிய அவசியமும் இல்லை. உங்கள் முடிவுகள், விருப்பங்கள் ஆகியவற்றின் அடிப்படையில் நடைமுறைக்கு ஏற்ற உயர்கல்விப் பாதைகளை, ஒவ்வொரு படியாகக் கண்டறிய 'HalaTuju' உதவுகிறது.

என்ன செய்வது:

**1. உங்கள் முடிவுகளை உள்ளிடவும்**  
👈 மேல் இடது மூலையில் உள்ள >> சின்னத்தைத் தட்டி, உங்கள் SPM முடிவுகளை (மாதிரி அல்லது அசல்) உள்ளிடவும்.

**2. நீங்கள் எதற்கெல்லாம் தகுதியானவர் என்று பாருங்கள்**  
குறைந்தபட்சத் தகுதிகளை நீங்கள் பூர்த்தி செய்யும் படிப்புகளை நாங்கள் உடனடியாகக் காட்டுவோம்.

**3. உங்களுக்குப் பொருத்தமானவற்றைத் தேர்ந்தெடுக்கவும்**  
ஒரு நிமிட வினாடி வினாவிற்குப் பதிலளிக்கவும். தகுதியான படிப்புகளை, உங்கள் மதிப்பெண்களை மட்டும் பார்க்காமல், அவை உங்களுக்கு எவ்வளவு பொருத்தமானவை என்பதை அடிப்படையாகக் கொண்டு நாங்கள் வரிசைப்படுத்துவோம்.

**4. தரவரிசையைப் புரிந்துகொள்ளுங்கள் (விருப்பத் தேர்வு)**  
உங்களுக்குத் தெளிவான வழிகாட்டுதல் தேவைப்பட்டால், குறிப்பிட்ட படிப்புகள் ஏன் முதலிடத்தில் உள்ளன என்பதையும், அடுத்து நீங்கள் என்ன செய்ய வேண்டும் என்பதையும் விளக்கும் தனிப்பயனாக்கப்பட்ட ஆலோசகர் அறிக்கையைப் (Counsellor’s Report) பெறுங்கள்.

உங்கள் விருப்பங்களை ஆராயத் தயாரா?
உங்கள் முடிவுகளை உள்ளிடுவதன் வழி தொடங்குங்கள் — அடுத்த கட்டங்களைப் போகப்போகத் தீர்மானித்துக் கொள்ளலாம். 🚀""",
        "spinner_msg": "அதிகாரப்பூர்வ தகுதித் தேவைகளை சரிபார்க்கிறது...",
        
        # Results
        "hero_success": "🎉 மகிழ்ச்சியான செய்தி! நீங்கள் **{count} படிப்புகளுக்கு** தகுதி பெற்றுள்ளீர்கள்.",
        "hero_eligible_dynamic": "🎉 நற்செய்தி! நீங்கள் **{locs} இடங்களிலுள்ள** **{courses} படிப்புகளுக்குத்** தகுதி பெற்றுள்ளீர்கள்.",
        "hero_fail": "தற்போதைக்கு பொருத்தமான படிப்புகள் இல்லை.",
        "hero_tip": "குறிப்பு: மலாய் மொழி/வரலாற்றில் தேர்ச்சி பெற்றுள்ளீர்களா என்பதை உறுதிப்படுத்தவும்.",
        
        # Stats & Tables
        "teaser_title": "🌟 உங்களுக்கான சிறந்த 3 வாய்ப்புகள்",
        "teaser_subtitle": "உங்கள் முடிவுகளின் அடிப்படையில், இவை சிறந்த தேர்வுகள்:",
        "btn_save_course": "விருப்பப் பட்டியலில் சேர் ❤️",
        "btn_saved_toast": "சேமிக்கப்பட்டது: {course}",
        "locked_count": "...மேலும் {remaining} படிப்புகள் உள்ளன.",
        "locked_cta_title": "முழு பட்டியலை பார்க்க முடிவுகளை சேமிக்கவும்",
        "locked_cta_desc": "உங்கள் தகவல்களை இழக்காதீர்கள். அனைத்து வாய்ப்புகளையும் பார்க்க இலவசமாக பதிவு செய்யுங்கள்.",
        "form_name": "முழு பெயர்",
        "form_phone": "வாட்ஸ்அப் எண்",
        "form_email": "மின்னஞ்சல் முகவரி",
        "btn_unlock": "சேமி & பட்டியலை பார்",
        "toast_success": "வெற்றி! சுயவிவரம் சேமிக்கப்பட்டது.",
        "err_missing_info": "பெயர் மற்றும் தொலைபேசி எண்ணை நிரப்பவும்.",
        # VALIDATION ERRORS
        "err_name_short": "❌ பெயர் மிகவும் குறுகியது.",
        "err_email_invalid": "❌ மின்னஞ்சல் வடிவம் செல்லுபடியாகாது.",
        "err_phone_short": "❌ தொலைபேசி எண் மிகவும் குறுகியது.",
        
        "unlocked_alert": "🔓 முழு அறிக்கை திறக்கப்பட்டது! கீழே உள்ள பட்டியலை ஆராயுங்கள்.",
        "table_title": "📋 உங்கள் முழு படிப்புகளின் பட்டியல்",
        "table_col_course": "படிப்பு",
        "table_col_inst": "கல்வி நிறுவனம்",
        "table_col_cat": "வகை",
        "table_col_status": "நிலை",
        "filter_label": "வகை வாரியாக வடிகட்டவும்:",
        "filter_count": "{total} இல் {shown} படிப்புகள் காட்டப்படுகின்றன.",
        "contact_counselor": "விண்ணப்ப உதவிக்கு எங்கள் ஆலோசகர்களைத் தொடர்பு கொள்ளவும்.",
        
        # About / Trust Section (NEW)
        "about_title": "ℹ️ எங்களை பற்றி & செயல்முறை",
        "about_desc": """
        **இது எப்படி வேலை செய்கிறது?**
        உயர் கல்வி அமைச்சு (UPU) மற்றும் TVET முகமைகளால் வெளியிடப்பட்ட அதிகாரப்பூர்வ தகுதித் தேவைகளை நாங்கள் பயன்படுத்துகிறோம்.
        1,000 க்கும் மேற்பட்ட படிப்புகளுக்கான குறைந்தபட்ச தேவைகளுடன் உங்கள் தரங்களை நாங்கள் ஒப்பிடுகிறோம்.
        
        **பொறுப்புத் துறப்பு (Disclaimer):**
        இது ஒரு வழிகாட்டி கருவி மட்டுமே, அதிகாரப்பூர்வ விண்ணப்பம் அல்ல. குறைந்தபட்ச தேவைகளைப் பூர்த்தி செய்வது சேர்க்கையை உறுதிப்படுத்தாது, ஏனெனில் ஒவ்வொரு ஆண்டும் இடங்களுக்கான போட்டி மாறுபடும்.
        """,
        "footer_credits": "மலேசிய மாணவர்களுக்காக ❤️ உடன் உருவாக்கப்பட்டது.",
        
        
        "header_top_matches": "🏆 5 சிறந்த தேர்வுகள்",
        "header_other_matches": "📋 தகுதியுள்ள பிற படிப்புகள்",
        "lbl_duration": "கால அளவு",
        "lbl_fees": "கட்டணம்",
        "lbl_mode": "முறை",
        
        # Admin Section (NEW)
        "admin_login": "நிர்வாக அணுகல்",
        "admin_success": "மீண்டும் வருக.",
        "admin_view_leads": "மாணவர் பட்டியலைப் பாருங்கள்",
        "admin_download": "CSV தரவிறக்கம்",

        # Dashboard Specific (New)
        "quality_safe": "பாதுகாப்பான தேர்வு 🟢",
        "quality_good": "நல்ல பொருத்தம் 🔵",
        "quality_reach": "முயற்சி செய்யலாம் 🟡",
        "help_pin": "இந்த PIN ஐ நினைவில் கொள்க!",
        "toast_profile_saved": "சுயவிவரம் வெற்றிகரமாக சேமிக்கப்பட்டது!",
        "err_save_failed": "சேமிக்க முடியவில்லை: {error}",
        "inst_poly": "பாலிடெக்னிக்",
        "inst_kk": "கமூனிடி காலேஜ்",
        "inst_iljtm": "ILJTM",
        "inst_ilkbs": "ILKBS",
        "inst_other": "டிவெட் / பிற",
        "inst_ipg": "ஐபிஜி (ஆசிரியர் பயிற்சி)",
        "inst_form6": "படிவம் 6 (STPM)",
        "inst_matrik": "மெட்ரிகுலேஷன்",
        "inst_uni": "பொது பல்கலைக்கழகம்",
        "unknown_course": "தெரியாத படிப்பு",
        "unknown_inst": "தெரியாத நிறுவனம்",
        "unknown_state": "மலேசியா",
        "status_eligible": "தகுதியுடையவர்",
        "status_not_eligible": "தகுதியற்றவர்",
        "filter_state": "இடத்தை வடிகட்டவும்:",
        
        # Quiz
        "quiz_title": "🧭 கண்டுபிடிப்பு வினாடி வினா",
        "quiz_question_count": "கேள்வி {step} / {total}",
        "quiz_generating": "பகுப்பாய்வு செய்கிறது...",
        "quiz_saved": "முடிவுகள் சேமிக்கப்பட்டன!",
        "quiz_complete": "சுயவிவரம் சேமிக்கப்பட்டது!",
        "quiz_msg_success": """**நன்றி!** உங்கள் பதில்கள் பதிவு செய்யப்பட்டுள்ளன.
        உங்கள் ஆளுமை மற்றும் ஆர்வங்களின் அடிப்படையில் படிப்புகளின் பட்டியலை மறுவரிசைப்படுத்தியுள்ளோம்.
        **Dashboard**-இல் நீங்கள் பார்க்கும் படிப்புகள் இப்போது உங்களுக்கானவே பிரத்யேகமாகத் தனிப்பயனாக்கப்பட்டுள்ளன.""",
        "quiz_cta_intro": "💡 **அடுத்த படி:** உங்கள் பரிந்துரைக்கப்பட்ட படிப்புகளைக் காண **Dashboard** தாவலுக்குத் திரும்பவும்.",
        "quiz_btn_dashboard": "Dashboard-க்குச் செல்க ➡️",
        "quiz_cta_ai": "🔍 **மேலும் அறிய வேண்டுமா?** முழுமையான தொழில் அறிக்கையைப் பெற பக்கப்பட்டியில் உள்ள **✨ Deep AI Analysis (Beta)** பொத்தானைக் கிளிக் செய்யவும்.",
        "quiz_debug_label": "🛠️ Debug தரவை பார்க்க (Raw Profile)",
        "quiz_return": "முகப்புக்குத் திரும்பு",
        "btn_back": "⬅️ பின்னால்",

        # Auth/Gate
        "gate_subtitle": "எல்லாவற்றையும் பார்க்க தயாரா? முழு அறிக்கையைத் திறக்கவும்.",
        "gate_pin_instr": "முடிவுகளைச் சேமிக்க பாதுகாப்பான PIN ஐ உருவாக்கவும்.",
        "lbl_create_pin": "6-இலக்க PIN ஐ உருவாக்கவும்",
        "btn_unlock_save": "சேமி & திற",
        "msg_account_created": "கணக்கு உருவாக்கப்பட்டது!",

        # Profile
        "profile_title": "👤 என் சுயவிவரம்",
        "profile_phone": "தொலைபேசி",
        "btn_back_dash": "⬅️ முகப்புக்குத் திரும்பு",
        "counselor_report": "ஆலோசகர் அறிக்கை",
        "more_details": "மேல் விவரங்கள் ↗",
        "worth_considering": "👍 பரிசீலிக்கத்தக்கது",
        "filter_options": "🌪️ வடிகட்டி விருப்பங்கள்",
        "lbl_search": "படிப்புகளைத் தேடுங்கள்",
        "search_placeholder": "பாடம் அல்லது கல்லூரியின் பெயரை உள்ளிடவும்...",
        "filter_by_inst_type": "கல்லூரி வகை மூலம்",
        "filter_by_state": "மாநிலம் மூலம்",
        "filter_by_field": "கல்வித் துறை மூலம்",
        "filter_by_level": "கல்வி நிலை மூலம்",
        "lbl_institution": "கல்லூரி",
        "lbl_course": "பாடம்",
        "lbl_state": "மாநிலம்",
        "lbl_page_count": "பக்கம் <b>{current}</b> / <b>{total}</b>",
        "btn_download_pdf": "📄 PDF பதிவிறக்கம்",
        "btn_share_wa": "📲 பெற்றோருடன் பகிரவும்",
        "btn_print_report": "🖨️ அறிக்கையை அச்சிடுங்கள்",
        "lbl_generated_by": "{counsellor} ஆல் உருவாக்கப்பட்டது • என்ஜின்: {model}",
        "err_report_unavailable": "அறிக்கை கிடைக்கவில்லை. தயவுசெய்து கண்டுபிடிப்பு வினாடி வினாவை மீண்டும் எடுக்கவும்.",
        "lbl_preferred_name_display": "விருப்பமான பெயர்:",
        "err_city_invalid": "❌ நகரம்: எழுத்துக்கள் மற்றும் இடைவெளிகள் மட்டுமே அனுமதிக்கப்படும்.",
        "msg_explore_unlock": "💡 **அறிக்கையைத் திறக்க பாடங்களை ஆராயுங்கள்**",
        "btn_counselor_lock": "🔒 ஆலோசகர் அறிக்கை",
        "lbl_key_factors": "✨ முக்கிய காரணிகள் ({count})",
        "err_pin_length": "❌ PIN கண்டிப்பாக 6 இலக்கங்கள் இருக்க வேண்டும்",
        "ph_phone": "உ.ம். 012-3456789",
        "progress_messages": [
            "🔍 SPM முடிவுகள் மற்றும் கல்வி வலிமையை பகுப்பாய்வு செய்கிறது...",
            "🧠 கற்றல் முறை மற்றும் தொழில் ஆர்வங்களை பொருத்துகிறது...",
            "🏢 வளாக இருப்பு மற்றும் இடங்களை சரிபார்க்கிறது...",
            "✨ உங்களுக்கான சிறந்த பாதைகளை வகுக்கிறது...",
            "✅ அறிக்கை கிட்டத்தட்ட தயாராக உள்ளது..."
        ],

        # Sidebar
        "sb_lang": "🌐 மொழி",
        "sb_logout": "வெளியேறு",
        "sb_retake_quiz": "🔄 மறுபரிசோதனை",
        "sb_start_quiz": "🧭 கண்டுபிடிப்பு வினாடி வினா",
        "sb_guest_mode": "👋 விருந்தினர் முறை",
        "sb_returning_user": "🔐 **திரும்பும் பயனர்கள்**",
        "sb_login": "உள்நுழை",
        "sb_welcome": "மீண்டும் வரவேற்கிறோம்!",
        
        # Post-Quiz Progress Messages
        "progress_analyzing_spm": "📊 உங்கள் SPM முடிவுகளைப் பகுப்பாய்வு செய்கிறது...",
        "progress_understanding_style": "🧠 உங்கள் கற்றல் பாணியை புரிந்துகொள்கிறது...",
        "progress_finding_courses": "🎯 பொருத்தமான படிப்புகளைக் கண்டறிகிறது...",
        "progress_ranking_courses": "🔄 படிப்புகளை வரிசைப்படுத்துகிறது...",
        "progress_almost_ready": "✨ கிட்டத்தட்ட தயார்...",
        
        # Post-Quiz Success
        "quiz_ranking_updated": "✅ படிப்பு வரிசை புதுப்பிக்கப்பட்டது!",
        "quiz_view_dashboard_msg": "📊 **உங்கள் பரிந்துரைகளைப் பார்க்க டாஷ்போர்டுக்குச் செல்லவும்.**",
        "quiz_courses_ranked_msg": "கண்டுபிடிப்பு வினாடி வினா முடிவுகளின் அடிப்படையில் படிப்புகள் உங்கள் பொருத்தத்திற்கு ஏற்ப ஏற்பாடு செய்யப்பட்டுள்ளன.",
        "btn_view_dashboard": "📊 டாஷ்போர்டைப் பார்க்கவும்",
        
        # Report Gating
        "report_prompt_explore": "📊 **பிரதான பக்கத்தில் பரிந்துரைக்கப்பட்ட படிப்புகளைப் பார்க்கவும்.**\n\nவரிசை வரிசையை கவனியுங்கள்.",
        "report_unlock_msg": "💡 **இந்த படிப்புகள் ஏன் இவ்வாறு வரிசைப்படுத்தப்பட்டுள்ளன என்று ஆச்சரியமாக உள்ளதா?**\n\nஆலோசனை அறிக்கை இப்போது கிடைக்கிறது.",

        # Featured Matches
        "feat_title": "🌟 சிறப்புத் தேர்வுகள்",
        "feat_career": "💼 தொழில்",
        "badge_dur": "காலம்",
        "badge_mode": "முறை",
        "badge_fees": "கட்டணம்",

        # New Requirement Flags
        "req_interview_label": "⚠️ Interview Required",
        "req_single_label": "⚠️ Unmarried Only",
        "req_interview_note": "📋 விண்ணப்பதாரர்கள் நேர்காணலுக்கு வர வேண்டும்.",
        "req_single_note": "💍 திருமணமாகாதவர்களுக்கு மட்டுமே (IKTBN Termeloh).",
        
        # WhatsApp Share
        "wa_share_msg": """வணக்கம் அம்மா/அப்பா,

Hala Tuju என்ற இணையத்தளத்தில் என் மேல் படிப்புக்கான வாய்ப்புகளைத் தேடினேன். அது எனக்குச் சில படிப்பங்களைப் பரிந்துரைத்தது:

{courses}
இது பற்றி உங்கள் ஆலோசனையைக் கேட்க விரும்புகிறேன். நேரம் கிடைக்கும்போது நாம் இதைப் பற்றிப் பேசலாமா?
https://halatuju.streamlit.app"""
    }
}

def get_text(lang_code):
    return TEXTS.get(lang_code, TEXTS["en"])