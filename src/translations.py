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
        "sb_arts_stream": "Arts Stream",
        "sb_opt_subject": "Optional Subjects",
        "sb_gender": "Gender",
        
        # Options & Inputs
        "opt_not_taken": "Not Taken",
        "gender_male": "Male",
        "gender_female": "Female",
        
        # Subject Names
        "subj_bm": "Malay Language",
        "subj_eng": "English",
        "subj_hist": "History",
        "subj_math": "Mathematics",
        "subj_moral": "Islam/Moral",
        
        "subj_addmath": "Add Maths",
        "subj_phy": "Physics",
        "subj_chem": "Chemistry",
        "subj_bio": "Biology",

        "subj_sci": "Science",

        # Landing & Processing
        "header_title": "Hala Tuju SPM",
        "header_subtitle": "See which Polytechnic, IKBN, and Community College courses you qualify for.",
        "landing_msg": "👈 Please enter your exam results on the left to start.",
        "spinner_msg": "Checking official entry requirements...",
        
        # Results
        "hero_success": "🎉 Good news! You meet the entry requirements for **{count} Courses**.",
        'hero_eligible_dynamic': '🎉 Good news! You qualify for **{courses} Courses** across **{locs} Locations**.',
        "hero_fail": "No direct matches found yet.",
        "hero_tip": "Tip: Ensure you entered a pass for Malay/History if required.",
        
        # Stats & Tables
        "stat_poly": "Politeknik",
        "stat_kk": "Kolej Komuniti",
        "stat_ikbn": "IKBN / ILP (Skills)",
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
        "inst_poly": "stat_poly",
        "inst_ikbn": "stat_ikbn",
        "inst_kk": "stat_kk",
        "inst_other": "stat_other",
        "unknown_course": "Unknown Course",
        "unknown_inst": "Unknown Inst",
        "unknown_state": "Malaysia",
        "status_eligible": "Eligible",
        "status_not_eligible": "Not Eligible",
        "filter_state": "Filter Location:"
    },
    
    "bm": {
        # Core UI
        "sb_title": "Keputusan SPM",
        "sb_caption": "Masukkan gred percubaan atau sebenar.",
        "sb_btn_submit": "Semak Kelayakan",
        "sb_core_subjects": "Subject Teras",
        "sb_science_stream": "Aliran Sains",
        "sb_arts_stream": "Aliran Seni",
        "sb_opt_subject": "Subjek Elektif",
        "sb_gender": "Jantina",
        
        # Options & Inputs
        "opt_not_taken": "Tidak Ambil",
        "gender_male": "Lelaki",
        "gender_female": "Perempuan",
        
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
        
        # Landing & Processing
        "header_title": "Hala Tuju SPM",
        "header_subtitle": "Semak kelayakan anda untuk Politeknik, IKBN, dan Kolej Komuniti.",
        "landing_msg": "👈 Sila masukkan keputusan di sebelah kiri untuk bermula.",
        "spinner_msg": "Sedang menyemak syarat kemasukan rasmi...",
        
        # Results
        "hero_success": "🎉 Berita baik! Anda memenuhi syarat untuk **{count} Kursus**.",
        'hero_eligible_dynamic': '🎉 Berita baik! Anda layak untuk **{courses} Kursus** di **{locs} Lokasi**.',
        "hero_fail": "Tiada padanan ditemui buat masa ini.",
        "hero_tip": "Tip: Pastikan anda lulus Bahasa Melayu/Sejarah jika perlu.",
        
        # Stats & Tables
        "stat_poly": "Politeknik",
        "stat_ikbn": "IKBN / ILP (Kemahiran)",
        "stat_kk": "Kolej Komuniti",
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
        "inst_poly": "stat_poly",
        "inst_ikbn": "stat_ikbn",
        "inst_kk": "stat_kk",
        "inst_other": "stat_other",
        "unknown_course": "Kursus Tidak Diketahui",
        "unknown_inst": "Institusi Tidak Diketahui",
        "unknown_state": "Malaysia",
        "status_eligible": "Layak",
        "status_not_eligible": "Tidak Layak",
        "filter_state": "Tapis Lokasi:"
    },

    "ta": {
        # Core UI
        "sb_title": "SPM முடிவுகள்",
        "sb_caption": "உங்கள் தேர்வு முடிவுகளை உள்ளிடவும்.",
        "sb_btn_submit": "தகுதியை சரிபார்க்கவும்",
        "sb_core_subjects": "முதன்மை பாடங்கள்",
        "sb_science_stream": "அறிவியல் பிரிவு",
        "sb_arts_stream": "கலைப் பிரிவு",
        "sb_opt_subject": "கூடுதல் பாடங்கள்",
        "sb_gender": "பாலினம்",
        
        # Options & Inputs
        "opt_not_taken": "எடுக்கவில்லை",
        "gender_male": "ஆண்",
        "gender_female": "பெண்",
        
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
        
        # Landing & Processing
        "header_title": "Hala Tuju SPM (மேற்படிப்பு வழிகாட்டி)",
        "header_subtitle": "பாலிடெக்னிக், IKBN மற்றும் சமூகக் கல்லூரிகளில் உங்களுக்கான வாய்ப்புகளைக் கண்டறியுங்கள்.",
        "landing_msg": "👈 தொடங்க, இடதுபுறத்தில் உங்கள் தேர்வு முடிவுகளை உள்ளிடவும்.",
        "spinner_msg": "அதிகாரப்பூர்வ தகுதித் தேவைகளை சரிபார்க்கிறது...",
        
        # Results
        "hero_success": "🎉 மகிழ்ச்சியான செய்தி! நீங்கள் **{count} படிப்புகளுக்கு** தகுதி பெற்றுள்ளீர்கள்.",
        "hero_eligible_dynamic": "🎉 நற்செய்தி! நீங்கள் **{locs} இடங்களிலுள்ள** **{courses} படிப்புகளுக்குத்** தகுதி பெற்றுள்ளீர்கள்.",
        "hero_fail": "தற்போதைக்கு பொருத்தமான படிப்புகள் இல்லை.",
        "hero_tip": "குறிப்பு: மலாய் மொழி/வரலாற்றில் தேர்ச்சி பெற்றுள்ளீர்களா என்பதை உறுதிப்படுத்தவும்.",
        
        # Stats & Tables
        "stat_poly": "பாலிடெக்னிக்",
        "stat_ikbn": "IKBN / ILP (திறன்)",
        "stat_kk": "சமூகக் கல்லூரி",
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
        
        # Admin Section (NEW)
        "admin_login": "நிர்வாக அணுகல்",
        "admin_success": "மீண்டும் வருக.",
        "admin_view_leads": "மாணவர் பட்டியலைப் பாருங்கள்",
        "admin_download": "CSV தரவிறக்கம்",

        # Dashboard Specific (New)
        "quality_safe": "பாதுகாப்பான தேர்வு 🟢",
        "quality_good": "நல்ல பொருத்தம் 🔵",
        "quality_reach": "முயற்சி செய்யலாம் 🟡",
        "inst_poly": "stat_poly",
        "inst_ikbn": "stat_ikbn",
        "inst_kk": "stat_kk",
        "inst_other": "stat_other",
        "unknown_course": "தெரியாத படிப்பு",
        "unknown_inst": "தெரியாத நிறுவனம்",
        "unknown_state": "மலேசியா",
        "status_eligible": "தகுதியுடையவர்",
        "status_not_eligible": "தகுதியற்றவர்",
        "filter_state": "இடத்தை வடிகட்டவும்:"
    }
}

def get_text(lang_code):
    return TEXTS.get(lang_code, TEXTS["en"])