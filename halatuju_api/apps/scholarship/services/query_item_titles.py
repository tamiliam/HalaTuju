"""The student-facing TITLE of each Action Centre item, in en / ms / ta, for the query emails.

The Action Centre paints these from `halatuju-web/src/messages/{en,ms,ta}.json`
(`scholarship.actionCentre.item.<code>.title`); the API deploys without those files, so the
email reads this copy. `tests/test_query_email_items.py` pins it to the message files (drift fails
the build). Titles only: no description, no document content.

Four titles carry a household-member / results-kind placeholder in the app. The email has no
member or kind words in Python, so those four read as the placeholder-free form below.
"""

TITLES = {
    'ic_missing': (
        'Upload your IC',
        'Muat naik IC anda',
        'உங்கள் அடையாள அட்டையைப் பதிவேற்றவும்'),
    'ic_unreadable': (
        'Re-upload a clearer IC',
        'Muat naik semula IC yang lebih jelas',
        'தெளிவான அடையாள அட்டையை மீண்டும் பதிவேற்றவும்'),
    'nric_mismatch': (
        'Check your IC number',
        'Semak nombor IC anda',
        'உங்கள் அடையாள அட்டை எண்ணைச் சரிபார்க்கவும்'),
    'name_mismatch': (
        'Check your name',
        'Semak nama anda',
        'உங்கள் பெயரைச் சரிபார்க்கவும்'),
    'address_state_mismatch': (
        'Check your home state',
        'Semak negeri rumah anda',
        'உங்கள் வீட்டு மாநிலத்தைச் சரிபார்க்கவும்'),
    'results_slip_missing': (
        'Upload your results slip',
        'Muat naik slip keputusan',
        'உங்கள் முடிவு சீட்டைப் பதிவேற்றவும்'),
    'results_slip_unreadable': (
        'Re-upload a clearer results slip',
        'Muat naik semula slip keputusan yang lebih jelas',
        'தெளிவான முடிவு சீட்டை மீண்டும் பதிவேற்றவும்'),
    'results_slip_name_mismatch': (
        'Check the name on your results slip',
        'Semak nama pada slip keputusan',
        'முடிவு சீட்டில் உள்ள பெயரைச் சரிபார்க்கவும்'),
    'academic_missing_subjects': (
        'Add your missing subjects: {subjects}',
        'Tambah mata pelajaran yang tiada: {subjects}',
        'விடுபட்ட பாடங்களைச் சேர்க்கவும்: {subjects}'),
    'academic_extra_subjects': (
        'Check your subjects: {subjects}',
        'Semak mata pelajaran anda: {subjects}',
        'உங்கள் பாடங்களைச் சரிபார்க்கவும்: {subjects}'),
    'academic_grade_mismatch': (
        'Check your grade for {subject}',
        'Semak gred anda untuk {subject}',
        '{subject} பாடத்திற்கான தரத்தைச் சரிபார்க்கவும்'),
    'academic_grade_band_mismatch': (
        'Fix your grade for {subject}',
        'Betulkan gred anda untuk {subject}',
        '{subject} பாடத்திற்கான தரத்தைத் திருத்தவும்'),
    'income_proof_missing': (
        'Upload your STR document',
        'Muat naik dokumen STR anda',
        'உங்கள் STR ஆவணத்தைப் பதிவேற்றவும்'),
    'income_earner_undeclared': (
        "Tell us about your family's income",
        'Beritahu kami tentang pendapatan keluarga anda',
        'உங்கள் குடும்ப வருமானம் பற்றி எங்களிடம் கூறுங்கள்'),
    'earner_ic_missing': (
        "Upload a family member's IC",
        'Muat naik KP ahli keluarga',
        'குடும்ப உறுப்பினரின் அடையாள அட்டையைப் பதிவேற்றவும்'),
    'earner_ic_unreadable': (
        'Upload a clearer IC photo for a family member',
        'Muat naik gambar KP ahli keluarga yang lebih jelas',
        'குடும்ப உறுப்பினரின் அடையாள அட்டையின் தெளிவான படத்தைப் பதிவேற்றவும்'),
    'birth_cert_missing': (
        'Upload your birth certificate',
        'Muat naik sijil kelahiran anda',
        'உங்கள் பிறப்புச் சான்றிதழைப் பதிவேற்றவும்'),
    'birth_cert_not_genuine': (
        'Upload your full birth certificate',
        'Muat naik sijil kelahiran penuh anda',
        'உங்கள் முழு பிறப்புச் சான்றிதழைப் பதிவேற்றவும்'),
    'birth_cert_unreadable': (
        'Send your birth certificate again',
        'Hantar semula sijil kelahiran anda',
        'உங்கள் பிறப்புச் சான்றிதழை மீண்டும் அனுப்புங்கள்'),
    'birth_cert_mismatch': (
        'Check your birth certificate',
        'Semak sijil kelahiran anda',
        'உங்கள் பிறப்புச் சான்றிதழைச் சரிபார்க்கவும்'),
    'father_patronymic_mismatch': (
        "Check a family member's IC",
        'Semak KP ahli keluarga',
        'குடும்ப உறுப்பினரின் அடையாள அட்டையைச் சரிபார்க்கவும்'),
    'guardianship_letter_missing': (
        'Upload your guardianship letter',
        'Muat naik surat penjagaan anda',
        'உங்கள் பாதுகாவல் கடிதத்தைப் பதிவேற்றவும்'),
    'guardianship_letter_not_genuine': (
        'Upload the full guardianship letter',
        'Muat naik surat penjagaan penuh',
        'முழு பாதுகாவலர் கடிதத்தைப் பதிவேற்றவும்'),
    'guardianship_letter_unreadable': (
        'Send your guardianship letter again',
        'Hantar semula surat penjagaan anda',
        'உங்கள் பாதுகாவலர் கடிதத்தை மீண்டும் அனுப்புங்கள்'),
    'str_not_current': (
        'Confirm your STR is approved and being paid',
        'Sahkan STR anda diluluskan dan sedang dibayar',
        'உங்கள் STR அங்கீகரிக்கப்பட்டு பணம் செலுத்தப்படுவதை உறுதிப்படுத்துங்கள்'),
    'str_recipient_mismatch': (
        'Check your STR document',
        'Semak dokumen STR anda',
        'உங்கள் STR ஆவணத்தைச் சரிபார்க்கவும்'),
    'offer_unreadable': (
        'Your offer letter was hard to read',
        'Surat tawaran sukar dibaca',
        'உங்கள் வாய்ப்பு கடிதம் படிக்க கடினமாக இருந்தது'),
    'offer_no_identity': (
        'Upload your personal offer letter',
        'Muat naik surat tawaran peribadi anda',
        'உங்கள் தனிப்பட்ட வாய்ப்பு கடிதத்தைப் பதிவேற்றவும்'),
    'offer_name_mismatch': (
        'Check the name on your offer letter',
        'Semak nama pada surat tawaran',
        'வாய்ப்பு கடிதத்தில் உள்ள பெயரைச் சரிபார்க்கவும்'),
    'pathway_undeclared': (
        'Choose your course',
        'Pilih kursus anda',
        'உங்கள் படிப்பைத் தேர்ந்தெடுக்கவும்'),
    'pathway_confirm': (
        "Is this where you're going?",
        'Ini tempat anda akan pergi?',
        'நீங்கள் செல்லும் இடம் இதுதானா?'),
    'offer_letter_missing': (
        'Upload your offer letter',
        'Muat naik surat tawaran anda',
        'உங்கள் வாய்ப்பு கடிதத்தைப் பதிவேற்றுங்கள்'),
    'offer_not_official': (
        'Upload your offer letter from a public institution',
        'Muat naik surat tawaran anda daripada institusi awam',
        'அரசுக் கல்வி நிறுவனத்தின் சேர்க்கைக் கடிதத்தைப் பதிவேற்றுங்கள்'),
    'course_unspecified': (
        'What do you plan to study?',
        'Apakah yang anda rancang untuk belajar?',
        'நீங்கள் என்ன படிக்கத் திட்டமிட்டுள்ளீர்கள்?'),
    'sibling_level_unknown': (
        'Are your siblings in school or further study?',
        'Adik-beradik anda di sekolah atau pengajian lanjut?',
        'உங்கள் உடன்பிறப்புகள் பள்ளியிலா அல்லது உயர்கல்வியிலா?'),
    'device_status_unknown': (
        'Do you have a device to study on?',
        'Adakah anda mempunyai peranti untuk belajar?',
        'படிப்பதற்கு உங்களிடம் சாதனம் உள்ளதா?'),
    'transport_cost_unknown': (
        'How do you get to your studies?',
        'Bagaimana anda pergi ke tempat pengajian?',
        'உங்கள் படிப்புக்கு எப்படிச் செல்கிறீர்கள்?'),
    'utility_holder_unknown': (
        'Whose name is on your utility bill?',
        'Nama siapa pada bil utiliti anda?',
        'உங்கள் பயன்பாட்டு பில்லில் யாருடைய பெயர் உள்ளது?'),
    'utility_address_mismatch': (
        'Is your utility bill for your current home?',
        'Adakah bil utiliti anda untuk rumah semasa anda?',
        'உங்கள் பயன்பாட்டு பில் உங்கள் தற்போதைய வீட்டுக்கானதா?'),
    'father_income_proof_missing': (
        "Upload your father's income proof",
        'Muat naik bukti pendapatan bapa anda',
        'உங்கள் தந்தையின் வருமானச் சான்றை பதிவேற்றவும்'),
    'mother_income_proof_missing': (
        "Upload your mother's income proof",
        'Muat naik bukti pendapatan ibu anda',
        'உங்கள் தாயின் வருமானச் சான்றை பதிவேற்றவும்'),
    'guardian_income_proof_missing': (
        "Upload your guardian's income proof",
        'Muat naik bukti pendapatan penjaga anda',
        'உங்கள் பாதுகாவலரின் வருமானச் சான்றை பதிவேற்றவும்'),
    'brother_income_proof_missing': (
        "Upload your elder brother's income proof",
        'Muat naik bukti pendapatan abang anda',
        'உங்கள் அண்ணனின் வருமானச் சான்றை பதிவேற்றவும்'),
    'sister_income_proof_missing': (
        "Upload your elder sister's income proof",
        'Muat naik bukti pendapatan kakak anda',
        'உங்கள் அக்காவின் வருமானச் சான்றை பதிவேற்றவும்'),
    'father_status_unknown': (
        'Tell us about your father',
        'Beritahu kami tentang bapa anda',
        'உங்கள் தந்தையைப் பற்றி எங்களிடம் கூறுங்கள்'),
    'mother_status_unknown': (
        'Tell us about your mother',
        'Beritahu kami tentang ibu anda',
        'உங்கள் தாயைப் பற்றி எங்களிடம் கூறுங்கள்'),
    'income_doc_stale': (
        'Upload a recent salary slip',
        'Muat naik slip gaji terkini',
        'சமீபத்திய சம்பளச் சீட்டை பதிவேற்றவும்'),
    'sibling_tertiary_funding': (
        'Tell us about your sibling in further study',
        'Ceritakan tentang adik-beradik anda dalam pengajian lanjutan',
        'உயர்படிப்பில் உள்ள உங்கள் உடன்பிறந்தவர் பற்றிக் கூறுங்கள்'),
    'sibling_school_detail': (
        'Tell us about your sibling in school',
        'Ceritakan tentang adik-beradik anda yang masih bersekolah',
        'பள்ளியில் படிக்கும் உங்கள் உடன்பிறந்தவர் பற்றிக் கூறுங்கள்'),
    'informal_income_detail': (
        "Tell us about your family's informal income",
        'Ceritakan tentang pendapatan tidak formal keluarga anda',
        'உங்கள் குடும்பத்தின் முறைசாரா வருமானம் பற்றிக் கூறுங்கள்'),
    'spm_year_unknown': (
        'Which year did you sit SPM?',
        'Tahun berapakah anda mengambil SPM?',
        'எந்த ஆண்டு SPM எழுதினீர்கள்?'),
    'reporting_date_unknown': (
        'When do you report to your institution?',
        'Bila anda perlu melapor diri ke institusi anda?',
        'உங்கள் நிறுவனத்தில் எப்போது அறிக்கை செய்ய வேண்டும்?'),
    'declared_income_evidence_missing': (
        "Upload proof of your family's income",
        'Muat naik bukti pendapatan keluarga anda',
        'உங்கள் குடும்ப வருமானத்திற்கான ஆதாரத்தைப் பதிவேற்றவும்'),
    'unemployment_detail_unknown': (
        "Tell us about the family member who isn't working",
        'Beritahu kami tentang ahli keluarga yang tidak bekerja',
        'வேலை செய்யாத குடும்ப உறுப்பினரைப் பற்றி எங்களிடம் தெரிவிக்கவும்'),
    'unemployment_epf_missing': (
        'Upload their EPF statement (optional)',
        'Muat naik penyata KWSP mereka (pilihan)',
        'அவர்களின் EPF அறிக்கையைப் பதிவேற்றவும் (விருப்பம்)'),
    'school_leaving_cert_missing': (
        'Upload your school-leaving certificate',
        'Muat naik sijil berhenti sekolah anda',
        'உங்கள் பள்ளி விடுப்புச் சான்றிதழைப் பதிவேற்றவும்'),
    'semester_result_missing': (
        'Upload your latest semester result',
        'Muat naik keputusan semester terkini anda',
        'உங்கள் சமீபத்திய செமஸ்டர் முடிவைப் பதிவேற்றவும்'),
    'stpm_grades_incomplete': (
        'Add the rest of your STPM subjects',
        'Tambah subjek STPM anda yang lain',
        'உங்கள் மற்ற STPM பாடங்களைச் சேர்க்கவும்'),
    'stpm_koko_confirm': (
        'Please confirm your co-curriculum score',
        'Sila sahkan markah kokurikulum anda',
        'உங்கள் இணைப்பாடவிதான மதிப்பெண்ணை உறுதிப்படுத்தவும்'),
    'epf_statement_missing': (
        "Upload your parent's EPF statement (optional)",
        'Muat naik penyata KWSP ibu/bapa anda (pilihan)',
        'உங்கள் பெற்றோரின் EPF அறிக்கையைப் பதிவேற்றவும் (விருப்பம்)'),
    'father_epf_missing': (
        "Upload your father's EPF statement (optional)",
        'Muat naik penyata KWSP bapa anda (pilihan)',
        'உங்கள் தந்தையின் EPF அறிக்கையைப் பதிவேற்றவும் (விருப்பம்)'),
    'mother_epf_missing': (
        "Upload your mother's EPF statement (optional)",
        'Muat naik penyata KWSP ibu anda (pilihan)',
        'உங்கள் தாயின் EPF அறிக்கையைப் பதிவேற்றவும் (விருப்பம்)'),
    'guardian_epf_missing': (
        "Upload your guardian's EPF statement (optional)",
        'Muat naik penyata KWSP penjaga anda (pilihan)',
        'உங்கள் பாதுகாவலரின் EPF அறிக்கையைப் பதிவேற்றவும் (விருப்பம்)'),
    'brother_epf_missing': (
        "Upload your elder brother's EPF statement (optional)",
        'Muat naik penyata KWSP abang anda (pilihan)',
        'உங்கள் அண்ணனின் EPF அறிக்கையைப் பதிவேற்றவும் (விருப்பம்)'),
    'sister_epf_missing': (
        "Upload your elder sister's EPF statement (optional)",
        'Muat naik penyata KWSP kakak anda (pilihan)',
        'உங்கள் அக்காவின் EPF அறிக்கையைப் பதிவேற்றவும் (விருப்பம்)'),
    'father_ic_for_str_missing': (
        "Upload your father's IC",
        'Muat naik kad pengenalan bapa anda',
        'உங்கள் தந்தையின் அடையாள அட்டையைப் பதிவேற்றவும்'),
    'mother_ic_for_str_missing': (
        "Upload your mother's IC",
        'Muat naik kad pengenalan ibu anda',
        'உங்கள் தாயின் அடையாள அட்டையைப் பதிவேற்றவும்'),
    'guardian_ic_for_str_missing': (
        "Upload your guardian's IC",
        'Muat naik kad pengenalan penjaga anda',
        'உங்கள் பாதுகாவலரின் அடையாள அட்டையைப் பதிவேற்றவும்'),
    'brother_ic_for_str_missing': (
        "Upload your elder brother's IC",
        'Muat naik kad pengenalan abang anda',
        'உங்கள் அண்ணனின் அடையாள அட்டையைப் பதிவேற்றவும்'),
    'sister_ic_for_str_missing': (
        "Upload your elder sister's IC",
        'Muat naik kad pengenalan kakak anda',
        'உங்கள் அக்காவின் அடையாள அட்டையைப் பதிவேற்றவும்'),
    'father_ic_for_str_unreadable': (
        "Re-upload your father's IC",
        'Muat naik semula kad pengenalan bapa anda',
        'உங்கள் தந்தையின் அடையாள அட்டையை மீண்டும் பதிவேற்றவும்'),
    'mother_ic_for_str_unreadable': (
        "Re-upload your mother's IC",
        'Muat naik semula kad pengenalan ibu anda',
        'உங்கள் தாயின் அடையாள அட்டையை மீண்டும் பதிவேற்றவும்'),
    'guardian_ic_for_str_unreadable': (
        "Re-upload your guardian's IC",
        'Muat naik semula kad pengenalan penjaga anda',
        'உங்கள் பாதுகாவலரின் அடையாள அட்டையை மீண்டும் பதிவேற்றவும்'),
    'brother_ic_for_str_unreadable': (
        "Re-upload your elder brother's IC",
        'Muat naik semula kad pengenalan abang anda',
        'உங்கள் அண்ணனின் அடையாள அட்டையை மீண்டும் பதிவேற்றவும்'),
    'sister_ic_for_str_unreadable': (
        "Re-upload your elder sister's IC",
        'Muat naik semula kad pengenalan kakak anda',
        'உங்கள் அக்காவின் அடையாள அட்டையை மீண்டும் பதிவேற்றவும்'),
    'str_needs_recipient_ic': (
        "Upload the STR page with the recipient's IC number",
        'Muat naik halaman STR yang menunjukkan nombor IC penerima',
        'பெறுநரின் IC எண் உள்ள STR பக்கத்தைப் பதிவேற்றவும்'),
    'utility_bill_missing': (
        'Upload a utility bill',
        'Muat naik bil utiliti',
        'பயன்பாட்டு பில் ஒன்றைப் பதிவேற்றவும்'),
    'water_bill_recheck': (
        'Upload a clear, recent water bill',
        'Muat naik bil air yang jelas dan terkini',
        'தெளிவான, சமீபத்திய தண்ணீர் பில்லைப் பதிவேற்றவும்'),
    'electricity_bill_recheck': (
        'Upload a clear, recent electricity bill',
        'Muat naik bil elektrik yang jelas dan terkini',
        'தெளிவான, சமீபத்திய மின்சார பில்லைப் பதிவேற்றவும்'),
    'deceased_parent_detail': (
        'Tell us about your late parent',
        'Beritahu kami tentang ibu/bapa anda yang telah meninggal',
        'உங்கள் மறைந்த பெற்றோர் பற்றி எங்களிடம் கூறுங்கள்'),
    'informal_work_detail': (
        'Tell us about the informal work',
        'Beritahu kami tentang kerja tidak formal itu',
        'முறைசாரா வேலை பற்றி எங்களிடம் கூறுங்கள்'),
    'household_size_confirm': (
        'Is this your household size?',
        'Adakah ini saiz isi rumah anda?',
        'இது உங்கள் குடும்ப அளவா?'),
    'household_roster_undercount': (
        'Who else lives in your household?',
        'Siapa lagi yang tinggal dalam isi rumah anda?',
        'உங்கள் வீட்டில் வேறு யார் வசிக்கிறார்கள்?'),
    'other_scholarships_followup': (
        'Tell us about your other scholarships',
        'Beritahu kami tentang biasiswa anda yang lain',
        'உங்கள் மற்ற உதவித்தொகைகள் பற்றி எங்களிடம் கூறுங்கள்'),
    'high_utility_expense': (
        'Why are your utility bills this high?',
        'Mengapa bil utiliti anda setinggi ini?',
        'உங்கள் பயன்பாட்டு பில்கள் ஏன் இவ்வளவு அதிகம்?'),
    'high_utility_expense_noincome': (
        'Why are your utility bills this high?',
        'Mengapa bil utiliti anda setinggi ini?',
        'உங்கள் பயன்பாட்டு பில்கள் ஏன் இவ்வளவு அதிகம்?'),
    'high_utility_expense_str': (
        'Why are your utility bills this high?',
        'Mengapa bil utiliti anda setinggi ini?',
        'உங்கள் பயன்பாட்டு பில்கள் ஏன் இவ்வளவு அதிகம்?'),
    'vircle_setup_pending': (
        'Set up your Vircle eWallet',
        'Sediakan eWallet Vircle anda',
        'உங்கள் Vircle eWallet-ஐ அமைக்கவும்'),
    'pension_amount_unknown': (
        "Tell us about your parent's pension",
        'Beritahu kami tentang pencen ibu bapa anda',
        'உங்கள் பெற்றோரின் ஓய்வூதியம் பற்றி எங்களிடம் கூறுங்கள்'),
    'father_pension_proof_missing': (
        "Upload your father's pension statement",
        'Muat naik penyata pencen bapa anda',
        'உங்கள் தந்தையின் ஓய்வூதிய அறிக்கையைப் பதிவேற்றுங்கள்'),
    'mother_pension_proof_missing': (
        "Upload your mother's pension statement",
        'Muat naik penyata pencen ibu anda',
        'உங்கள் தாயின் ஓய்வூதிய அறிக்கையைப் பதிவேற்றுங்கள்'),
    'pathway_type_switch': (
        'Confirm your pathway change',
        'Sahkan perubahan laluan anda',
        'உங்கள் பாதை மாற்றத்தை உறுதிப்படுத்தவும்'),
    'higher_results_missing': (
        'Upload your STPM, Matriculation, Asasi or Diploma results',
        'Muat naik keputusan STPM, Matrikulasi, Asasi atau Diploma anda',
        'உங்கள் STPM, மெட்ரிகுலேஷன், அசாசி அல்லது டிப்ளோமா முடிவுகளைப் பதிவேற்றவும்'),
    'higher_results_unreadable': (
        'Re-upload a clearer copy of your results',
        'Muat naik semula salinan keputusan yang lebih jelas',
        'உங்கள் முடிவுகளின் தெளிவான நகலை மீண்டும் பதிவேற்றவும்'),
    'higher_results_name_mismatch': (
        'Check the name on your results',
        'Semak nama pada keputusan anda',
        'உங்கள் முடிவுகளில் உள்ள பெயரைச் சரிபார்க்கவும்'),
    'higher_results_requested': (
        'Please upload your final results',
        'Sila muat naik keputusan akhir anda',
        'உங்கள் இறுதி முடிவுகளைப் பதிவேற்றவும்'),
    'higher_results_declare_requested': (
        'Enter and upload your STPM, Matriculation, Asasi or Diploma results',
        'Isi dan muat naik keputusan STPM, Matrikulasi, Asasi atau Diploma anda',
        'உங்கள் STPM, மெட்ரிகுலேஷன், அசாசி அல்லது டிப்ளோமா முடிவுகளைப் பதிவுசெய்து பதிவேற்றவும்'),
}

# The app title has a {placeholder}: this module holds the placeholder-free form instead.
PLACEHOLDER_FREE = frozenset(('earner_ic_missing', 'earner_ic_unreadable', 'father_patronymic_mismatch', 'higher_results_requested'))

# Any code not above (an unknown or future code): never a raw key, never a blank line.
GENERIC = (
    'Something we need from you',
    'Sesuatu yang kami perlukan daripada anda',
    'உங்களிடமிருந்து எங்களுக்குத் தேவையான ஒன்று',
)

# SUP1 privacy (owner, 2026-11-14): an email can be read by someone else in the family, so items
# about a parent's death or status, guardianship, the family's income, STR or a sibling's funding
# are NAMED by this plain title in the email (the Action Centre, behind the sign-in, still shows
# the full title). A reviewer's own typed prompt also reads as this title, never its free text.
TEAM_QUESTION = (
    'A question from our team',
    'Satu soalan daripada pasukan kami',
    'எங்கள் குழுவின் ஒரு கேள்வி',
)
SENSITIVE_CODES = frozenset((
    'deceased_parent_detail', 'father_status_unknown', 'mother_status_unknown',
    'guardianship_letter_missing', 'guardianship_letter_not_genuine',
    'guardianship_letter_unreadable', 'father_patronymic_mismatch',
    'str_not_current', 'str_recipient_mismatch',
    'income_proof_missing', 'income_earner_undeclared', 'income_doc_stale',
    'father_income_proof_missing', 'mother_income_proof_missing', 'guardian_income_proof_missing',
    'brother_income_proof_missing', 'sister_income_proof_missing',
    'informal_income_detail', 'informal_work_detail', 'declared_income_evidence_missing',
    'unemployment_detail_unknown', 'unemployment_epf_missing',
    'pension_amount_unknown', 'father_pension_proof_missing', 'mother_pension_proof_missing',
    'sibling_tertiary_funding', 'sibling_school_detail',
    # Review round: the same families, closed off (STR, EPF, an earner's IC, household spending).
    'str_needs_recipient_ic', 'earner_ic_missing', 'earner_ic_unreadable',
    'epf_statement_missing', 'father_epf_missing', 'mother_epf_missing', 'guardian_epf_missing',
    'brother_epf_missing', 'sister_epf_missing',
    'father_ic_for_str_missing', 'mother_ic_for_str_missing', 'guardian_ic_for_str_missing',
    'brother_ic_for_str_missing', 'sister_ic_for_str_missing',
    'father_ic_for_str_unreadable', 'mother_ic_for_str_unreadable',
    'guardian_ic_for_str_unreadable', 'brother_ic_for_str_unreadable',
    'sister_ic_for_str_unreadable',
    'household_roster_undercount', 'high_utility_expense', 'high_utility_expense_noincome',
    'high_utility_expense_str', 'sibling_level_unknown',
))
# The word families above, by prefix or part: a NEW code in one of them is private too
# (`test_query_email_items` fails a code that matches one of these and is not listed).
SENSITIVE_MARKERS = ('str_', '_str', 'epf', 'income', 'pension', 'guardian', 'sibling',
                     'deceased', 'father_', 'mother_', 'brother_', 'sister_', 'earner_',
                     'high_utility', 'household_roster')
