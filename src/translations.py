# src/translations.py

# Language Definitions
LANGUAGES = {
    "en": "English",
    "bm": "Bahasa Melayu",
    "ta": "தமிழ் (Tamil)"
}

# The Dictionary
TEXTS = {
    "en": {
        # Sidebar
        "sb_title": "SPM Results",
        "sb_caption": "Enter your actual or trial results.",
        "sb_btn_submit": "Check Eligibility",
        "sb_opt_subject": "Optional Subjects",
        "sb_gender": "Gender",
        
        # Landing Page
        "header_title": "Hala Tuju SPM",
        "header_subtitle": "See which Polytechnic, IKBN, and Community College courses you qualify for.",
        "landing_msg": "👈 Please enter your exam results on the left to start.",
        
        # Processing
        "spinner_msg": "Checking official entry requirements...",
        
        # Results - Hero
        "hero_success": "🎉 Good news! You meet the entry requirements for **{count} Courses**.",
        "hero_fail": "No direct matches found yet.",
        "hero_tip": "Tip: Ensure you entered a pass for Bahasa Melayu/History if required.",
        
        # Results - Stats
        "stat_poly": "Politeknik",
        "stat_ikbn": "IKBN / Skills",
        "stat_kk": "Comm. College",
        
        # Results - Teaser
        "teaser_title": "🌟 Your Top 3 Strategic Options",
        "teaser_subtitle": "Based on your results, these are solid pathways for you:",
        "btn_save_course": "Shortlist ❤️",
        "btn_saved_toast": "Saved: {course}",
        
        # The Nudge (Locked)
        "locked_count": "...and {remaining} other courses.",
        "locked_cta_title": "Save your results to see the full list",
        "locked_cta_desc": "Don't lose your progress. Create a free profile to view all options and download your strategy guide.",
        "form_name": "Full Name",
        "form_phone": "WhatsApp Number",
        "form_email": "Email Address",
        "btn_unlock": "Save & View Full List",
        "toast_success": "Success! Profile saved.",
        "err_missing_info": "Please fill in your Name and Phone number.",
        
        # Unlocked View
        "unlocked_alert": "🔓 Full Report Unlocked! Explore your options below.",
        "table_title": "📋 Your Complete Course List",
        "table_col_course": "Course Name",
        "table_col_inst": "Institution",
        "table_col_cat": "Category",
        "table_col_status": "Status",
        "filter_label": "Filter by Category:",
        "filter_count": "Showing {shown} of {total} courses.",
        "contact_counselor": "Contact our counselors for application help."
    },
    
    "bm": {
        # Sidebar
        "sb_title": "Keputusan SPM",
        "sb_caption": "Masukkan gred percubaan atau sebenar.",
        "sb_btn_submit": "Semak Kelayakan",
        "sb_opt_subject": "Subjek Elektif",
        "sb_gender": "Jantina",
        
        # Landing Page
        "header_title": "Hala Tuju SPM",
        "header_subtitle": "Semak kelayakan anda untuk Politeknik, IKBN, dan Kolej Komuniti.",
        "landing_msg": "👈 Sila masukkan keputusan di sebelah kiri untuk bermula.",
        
        # Processing
        "spinner_msg": "Sedang menyemak syarat kemasukan rasmi...",
        
        # Results - Hero
        "hero_success": "🎉 Berita baik! Anda memenuhi syarat untuk **{count} Kursus**.",
        "hero_fail": "Tiada padanan ditemui buat masa ini.",
        "hero_tip": "Tip: Pastikan anda lulus Bahasa Melayu/Sejarah jika perlu.",
        
        # Results - Stats (Keep acronyms)
        "stat_poly": "Politeknik",
        "stat_ikbn": "IKBN / Kemahiran",
        "stat_kk": "Kolej Komuniti",
        
        # Results - Teaser
        "teaser_title": "🌟 3 Pilihan Strategik Anda",
        "teaser_subtitle": "Berdasarkan keputusan anda, laluan ini mungkin sesuai:",
        "btn_save_course": "Simpan ❤️",
        "btn_saved_toast": "Disimpan: {course}",
        
        # The Nudge
        "locked_count": "...dan {remaining} lagi kursus.",
        "locked_cta_title": "Simpan keputusan untuk lihat senarai penuh",
        "locked_cta_desc": "Jangan hilang data anda. Bina profil percuma untuk lihat semua pilihan.",
        "form_name": "Nama Penuh",
        "form_phone": "No. WhatsApp",
        "form_email": "Alamat Emel",
        "btn_unlock": "Simpan & Lihat Semua",
        "toast_success": "Berjaya! Profil disimpan.",
        "err_missing_info": "Sila isi Nama dan No. Telefon.",
        
        # Unlocked View
        "unlocked_alert": "🔓 Laporan Penuh Dibuka! Lihat senarai di bawah.",
        "table_title": "📋 Senarai Lengkap Kursus Anda",
        "table_col_course": "Nama Kursus",
        "table_col_inst": "Institusi",
        "table_col_cat": "Kategori",
        "table_col_status": "Status",
        "filter_label": "Tapis Kategori:",
        "filter_count": "Menunjukkan {shown} daripada {total} kursus.",
        "contact_counselor": "Hubungi kaunselor kami untuk bantuan."
    },

    "ta": {
        # Sidebar
        "sb_title": "SPM முடிவுகள்",
        "sb_caption": "உங்கள் தேர்வு முடிவுகளை உள்ளிடவும்.",
        "sb_btn_submit": "தகுதியை சரிபார்க்கவும்",
        "sb_opt_subject": "கூடுதல் பாடங்கள்",
        "sb_gender": "பாலினம்",
        
        # Landing Page
        "header_title": "Hala Tuju SPM (மேற்படிப்பு வழிகாட்டி)",
        "header_subtitle": "பாலிடெக்னிக், IKBN மற்றும் சமூகக் கல்லூரிகளில் உங்களுக்கான வாய்ப்புகளைக் கண்டறியுங்கள்.",
        "landing_msg": "👈 தொடங்க, இடதுபுறத்தில் உங்கள் தேர்வு முடிவுகளை உள்ளிடவும்.",
        
        # Processing
        "spinner_msg": "அதிகாரப்பூர்வ தகுதித் தேவைகளை சரிபார்க்கிறது...",
        
        # Results - Hero
        "hero_success": "🎉 மகிழ்ச்சியான செய்தி! நீங்கள் **{count} படிப்புகளுக்கு** தகுதி பெற்றுள்ளீர்கள்.",
        "hero_fail": "தற்போதைக்கு பொருத்தமான படிப்புகள் இல்லை.",
        "hero_tip": "குறிப்பு: மலாய் மொழி/வரலாற்றில் தேர்ச்சி பெற்றுள்ளீர்களா என்பதை உறுதிப்படுத்தவும்.",
        
        # Results - Stats
        "stat_poly": "பாலிடெக்னிக்",
        "stat_ikbn": "IKBN / திறன் பயிற்சி",
        "stat_kk": "சமூகக் கல்லூரி",
        
        # Results - Teaser
        "teaser_title": "🌟 உங்களுக்கான சிறந்த 3 வாய்ப்புகள்",
        "teaser_subtitle": "உங்கள் முடிவுகளின் அடிப்படையில், இவை சிறந்த தேர்வுகள்:",
        "btn_save_course": "விருப்பப் பட்டியலில் சேர் ❤️",
        "btn_saved_toast": "சேமிக்கப்பட்டது: {course}",
        
        # The Nudge
        "locked_count": "...மேலும் {remaining} படிப்புகள் உள்ளன.",
        "locked_cta_title": "முழு பட்டியலை பார்க்க முடிவுகளை சேமிக்கவும்",
        "locked_cta_desc": "உங்கள் தகவல்களை இழக்காதீர்கள். அனைத்து வாய்ப்புகளையும் பார்க்க இலவசமாக பதிவு செய்யுங்கள்.",
        "form_name": "முழு பெயர்",
        "form_phone": "வாட்ஸ்அப் எண்",
        "form_email": "மின்னஞ்சல் முகவரி",
        "btn_unlock": "சேமி & பட்டியலை பார்",
        "toast_success": "வெற்றி! சுயவிவரம் சேமிக்கப்பட்டது.",
        "err_missing_info": "பெயர் மற்றும் தொலைபேசி எண்ணை நிரப்பவும்.",
        
        # Unlocked View
        "unlocked_alert": "🔓 முழு அறிக்கை திறக்கப்பட்டது! கீழே உள்ள பட்டியலை ஆராயுங்கள்.",
        "table_title": "📋 உங்கள் முழு படிப்புகளின் பட்டியல்",
        "table_col_course": "படிப்பு",
        "table_col_inst": "கல்வி நிறுவனம்",
        "table_col_cat": "வகை",
        "table_col_status": "நிலை",
        "filter_label": "வகை வாரியாக வடிகட்டவும்:",
        "filter_count": "{total} இல் {shown} படிப்புகள் காட்டப்படுகின்றன.",
        "contact_counselor": "விண்ணப்ப உதவிக்கு எங்கள் ஆலோசகர்களைத் தொடர்பு கொள்ளவும்."
    }
}

def get_text(lang_code):
    return TEXTS.get(lang_code, TEXTS["en"])