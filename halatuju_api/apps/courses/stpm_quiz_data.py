"""
STPM Quiz question data — ~35 questions × 3 languages (EN, BM, TA).

Subject-seeded branching design grounded in Holland's RIASEC, SCCT, SDT,
and Super's Career Development Theory. See docs/plans/2026-03-18-stpm-quiz-design.md.

Structure:
  - TRUNK questions (Q1, Q5, Q7–Q10): shown to all students
  - SCIENCE branch (Q2s, Q3s variants, Q4s): shown to science-stream students
  - ARTS branch (Q2a, Q3a variants, Q4a): shown to arts-stream students
  - MIXED branch (Q2m, Q3m, Q4m): shown to students with mixed subjects

Each question has:
  - id: stable identifier
  - prompt: question text (dict with en/bm/ta)
  - options: list of {text, icon, signals}
  - branch: which branch this belongs to ('trunk', 'science', 'arts', 'mixed')
  - position: display order (1–10)
  - condition: (optional) which Q2/Q2a/Q2m answer triggers this Q3 variant
  - adaptive: (optional) True for Q4/Q6 — engine must fill in grade context

This is pure data — no logic, no state, no imports.
"""

# --- STPM Subject → RIASEC Seed Mapping ---
# Primary = 2 points, Secondary = 1 point

SUBJECT_RIASEC_MAP = {
    'mathematics_t': {'I': 2, 'C': 1},
    'mathematics_m': {'C': 2, 'I': 1},
    'physics': {'R': 2, 'I': 1},
    'chemistry': {'I': 2, 'R': 1},
    'biology': {'I': 2, 'S': 1},
    'ict': {'I': 2, 'C': 1},
    'economics': {'E': 2, 'C': 1},
    'accounting': {'C': 2, 'E': 1},
    'business_studies': {'E': 2, 'S': 1},
    'literature_english': {'A': 2, 'S': 1},
    'geography': {'I': 2, 'R': 1},
    'history': {'S': 2, 'A': 1},
    'visual_arts': {'A': 2, 'R': 1},
    'syariah': {'S': 2, 'C': 1},
}

# Subjects that indicate science stream
SCIENCE_SUBJECTS = {
    'physics', 'chemistry', 'biology', 'mathematics_t', 'ict',
}

# Subjects that indicate arts stream
ARTS_SUBJECTS = {
    'economics', 'accounting', 'business_studies', 'literature_english',
    'geography', 'history', 'visual_arts', 'syariah', 'mathematics_m',
}

# PA is excluded from seed calculation (all students take it)
EXCLUDED_SUBJECTS = {'pengajian_am'}

SUPPORTED_LANGUAGES = ['en', 'bm', 'ta']


# --- STPM Signal Taxonomy ---
STPM_SIGNAL_TAXONOMY = {
    'riasec_seed': [
        'riasec_R', 'riasec_I', 'riasec_A',
        'riasec_S', 'riasec_E', 'riasec_C',
    ],
    'field_interest': [
        'field_engineering', 'field_health', 'field_pure_science',
        'field_tech', 'field_business', 'field_education',
        'field_law', 'field_creative', 'field_finance',
    ],
    'field_key': [
        'field_key_mekanikal', 'field_key_elektrik', 'field_key_sivil',
        'field_key_kimia', 'field_key_aero',
        'field_key_perubatan', 'field_key_farmasi', 'field_key_allied',
        'field_key_health_admin',
        'field_key_sains_fizik', 'field_key_sains_kimia',
        'field_key_sains_bio', 'field_key_alam',
        'field_key_it_sw', 'field_key_it_net', 'field_key_it_data',
        'field_key_multimedia',
        'field_key_pemasaran', 'field_key_hr', 'field_key_intl',
        'field_key_entrepren',
        'field_key_law', 'field_key_admin', 'field_key_ir',
        'field_key_pendidikan', 'field_key_kaunseling', 'field_key_sosial',
        'field_key_media', 'field_key_senireka', 'field_key_digital',
        'field_key_pr',
        'field_key_perakaunan', 'field_key_kewangan', 'field_key_aktuari',
        'field_key_fin_plan',
    ],
    'cross_domain': [
        'cross_R', 'cross_I', 'cross_A',
        'cross_S', 'cross_E', 'cross_C',
    ],
    'efficacy': [
        'efficacy_confirmed', 'efficacy_confident',
        'efficacy_open', 'efficacy_redirect',
        'efficacy_uncertain', 'efficacy_mismatch',
    ],
    'resilience': [
        'resilience_high', 'resilience_supported',
        'resilience_redirect', 'resilience_interest',
    ],
    'motivation': [
        'motivation_autonomous', 'motivation_career',
        'motivation_family', 'motivation_prestige',
    ],
    'career_goal': [
        'goal_professional', 'goal_employment',
        'goal_postgrad', 'goal_entrepreneurial',
    ],
    'context': [
        'family_influence_high', 'family_influence_moderate',
        'family_influence_low',
        'crystallisation_high', 'crystallisation_moderate',
        'crystallisation_low',
    ],
}

# --- STPM Field Key → FieldTaxonomy mapping ---
# Maps quiz field_key signals to FieldTaxonomy keys used by ranking engine
STPM_FIELD_KEY_MAP = {
    'field_key_mekanikal': ['mekanikal', 'automotif'],
    'field_key_elektrik': ['elektrik', 'mekatronik'],
    'field_key_sivil': ['sivil', 'senibina'],
    'field_key_kimia': ['kimia-proses'],
    'field_key_aero': ['aero', 'marin'],
    'field_key_perubatan': ['perubatan'],
    'field_key_farmasi': ['farmasi', 'bioteknologi'],
    'field_key_allied': ['sains-hayat'],
    'field_key_health_admin': ['pengurusan', 'sains-hayat'],
    'field_key_sains_fizik': ['sains-tulen'],
    'field_key_sains_kimia': ['sains-tulen', 'kimia-proses'],
    'field_key_sains_bio': ['bioteknologi', 'sains-hayat'],
    'field_key_alam': ['alam-sekitar', 'pertanian'],
    'field_key_it_sw': ['it-perisian'],
    'field_key_it_net': ['it-rangkaian'],
    'field_key_it_data': ['it-perisian', 'sains-tulen'],
    'field_key_multimedia': ['multimedia', 'senireka'],
    'field_key_pemasaran': ['pemasaran'],
    'field_key_hr': ['pengurusan'],
    'field_key_intl': ['perniagaan'],
    'field_key_entrepren': ['perniagaan', 'pengurusan'],
    'field_key_law': ['undang-undang'],
    'field_key_admin': ['pentadbiran'],
    'field_key_ir': ['pentadbiran', 'undang-undang'],
    'field_key_pendidikan': ['pendidikan'],
    'field_key_kaunseling': ['kaunseling'],
    'field_key_sosial': ['kaunseling', 'pendidikan'],
    'field_key_media': ['multimedia'],
    'field_key_senireka': ['senireka'],
    'field_key_digital': ['multimedia', 'senireka'],
    'field_key_pr': ['pemasaran', 'multimedia'],
    'field_key_perakaunan': ['perakaunan'],
    'field_key_kewangan': ['kewangan'],
    'field_key_aktuari': ['sains-aktuari'],
    'field_key_fin_plan': ['kewangan', 'perakaunan'],
}


# ============================================================
# QUESTIONS
# ============================================================
# All questions use trilingual text dicts: {'en': ..., 'bm': ..., 'ta': ...}

# --- Q1: Decision readiness (Super's theory) — all students ---
Q1_READINESS = {
    'id': 'q1_readiness',
    'branch': 'trunk',
    'position': 1,
    'prompt': {
        'en': 'Where are you in choosing what to study at university?',
        'bm': 'Di mana anda dalam memilih apa untuk dipelajari di universiti?',
        'ta': 'பல்கலைக்கழகத்தில் என்ன படிக்க வேண்டும் என்பதில் நீங்கள் எந்த நிலையில் உள்ளீர்கள்?',
    },
    'options': [
        {
            'text': {
                'en': 'I know exactly what I want',
                'bm': 'Saya tahu tepat apa yang saya mahu',
                'ta': 'எனக்கு என்ன வேண்டும் என்று சரியாகத் தெரியும்',
            },
            'icon': 'target_bullseye',
            'signals': {'crystallisation_high': 2},
        },
        {
            'text': {
                'en': 'I have a general direction',
                'bm': 'Saya ada hala tuju umum',
                'ta': 'எனக்கு ஒரு பொது திசை உள்ளது',
            },
            'icon': 'compass_arrow',
            'signals': {'crystallisation_moderate': 2},
        },
        {
            'text': {
                'en': "I'm still figuring it out",
                'bm': 'Saya masih mencari',
                'ta': 'நான் இன்னும் கண்டுபிடித்துக் கொண்டிருக்கிறேன்',
            },
            'icon': 'magnifying_question',
            'signals': {'crystallisation_low': 2},
        },
    ],
}

# --- Q2s: Science branch — primary field direction ---
Q2_SCIENCE = {
    'id': 'q2s_field',
    'branch': 'science',
    'position': 2,
    'prompt': {
        'en': "You've studied science — which direction excites you most?",
        'bm': 'Anda telah belajar sains — arah mana yang paling menarik?',
        'ta': 'நீங்கள் அறிவியல் படித்துள்ளீர்கள் — எந்தத் திசை உங்களை மிகவும் ஈர்க்கிறது?',
    },
    'options': [
        {
            'text': {
                'en': 'Engineering — designing and building systems',
                'bm': 'Kejuruteraan — mereka dan membina sistem',
                'ta': 'பொறியியல் — அமைப்புகளை வடிவமைத்து உருவாக்குதல்',
            },
            'icon': 'gear_blueprint',
            'signals': {'field_engineering': 3},
        },
        {
            'text': {
                'en': "Medicine & Health — caring for people's wellbeing",
                'bm': 'Perubatan & Kesihatan — menjaga kesejahteraan orang',
                'ta': 'மருத்துவம் & சுகாதாரம் — மக்களின் நலனைப் பேணுதல்',
            },
            'icon': 'heart_stethoscope',
            'signals': {'field_health': 3},
        },
        {
            'text': {
                'en': 'Pure & Applied Science — understanding how the world works',
                'bm': 'Sains Tulen & Gunaan — memahami cara dunia berfungsi',
                'ta': 'தூய & பயன்பாட்டு அறிவியல் — உலகம் எப்படி செயல்படுகிறது என்று புரிந்துகொள்ளல்',
            },
            'icon': 'atom_microscope',
            'signals': {'field_pure_science': 3},
        },
        {
            'text': {
                'en': 'Technology & Computing — building digital solutions',
                'bm': 'Teknologi & Pengkomputeran — membina penyelesaian digital',
                'ta': 'தொழில்நுட்பம் & கணினி — டிஜிட்டல் தீர்வுகளை உருவாக்குதல்',
            },
            'icon': 'laptop_code',
            'signals': {'field_tech': 3},
        },
        {
            'text': {
                'en': "Business & Management — I'm more interested in the business side",
                'bm': 'Perniagaan & Pengurusan — saya lebih berminat di bidang perniagaan',
                'ta': 'வணிகம் & மேலாண்மை — நான் வணிகத் தரப்பில் அதிக ஆர்வம் கொண்டுள்ளேன்',
            },
            'icon': 'handshake_chart',
            'signals': {'field_business': 3},
        },
        {
            'text': {
                'en': 'Education — I want to teach or work with people',
                'bm': 'Pendidikan — saya ingin mengajar atau bekerja dengan orang',
                'ta': 'கல்வி — நான் கற்பிக்க அல்லது மக்களுடன் பணியாற்ற விரும்புகிறேன்',
            },
            'icon': 'gradcap_people',
            'signals': {'field_education': 3},
        },
    ],
}

# --- Q3s variants: Science sub-field refinement ---

Q3S_ENGINEERING = {
    'id': 'q3s_engineering',
    'branch': 'science',
    'position': 3,
    'condition': {'requires': 'q2s_field', 'field': 'field_engineering'},
    'prompt': {
        'en': 'What kind of engineering appeals to you?',
        'bm': 'Jenis kejuruteraan apa yang menarik minat anda?',
        'ta': 'எந்த வகை பொறியியல் உங்களை ஈர்க்கிறது?',
    },
    'options': [
        {
            'text': {
                'en': 'Mechanical — machines, vehicles, manufacturing',
                'bm': 'Mekanikal — mesin, kenderaan, pembuatan',
                'ta': 'இயந்திரவியல் — இயந்திரங்கள், வாகனங்கள், உற்பத்தி',
            },
            'icon': 'gear_wrench',
            'signals': {'field_key_mekanikal': 2},
        },
        {
            'text': {
                'en': 'Electrical & Electronics — circuits, power, telecoms',
                'bm': 'Elektrik & Elektronik — litar, kuasa, telekomunikasi',
                'ta': 'மின் & மின்னணு — மின்சுற்றுகள், மின்சாரம், தொலைத்தொடர்பு',
            },
            'icon': 'lightning_bolt',
            'signals': {'field_key_elektrik': 2},
        },
        {
            'text': {
                'en': 'Civil & Architecture — buildings, infrastructure, design',
                'bm': 'Sivil & Senibina — bangunan, infrastruktur, reka bentuk',
                'ta': 'சிவில் & கட்டிடக்கலை — கட்டிடங்கள், உள்கட்டமைப்பு, வடிவமைப்பு',
            },
            'icon': 'hardhat_crane',
            'signals': {'field_key_sivil': 2},
        },
        {
            'text': {
                'en': 'Chemical & Process — reactions, materials, energy',
                'bm': 'Kimia & Proses — tindak balas, bahan, tenaga',
                'ta': 'வேதியியல் & செயல்முறை — வினைகள், பொருட்கள், ஆற்றல்',
            },
            'icon': 'flask_fire',
            'signals': {'field_key_kimia': 2},
        },
        {
            'text': {
                'en': 'Aerospace & Marine — flight, ships, defence',
                'bm': 'Aeroangkasa & Marin — penerbangan, kapal, pertahanan',
                'ta': 'விண்வெளி & கடல் — விமானம், கப்பல், பாதுகாப்பு',
            },
            'icon': 'airplane_ship',
            'signals': {'field_key_aero': 2},
        },
    ],
}

Q3S_HEALTH = {
    'id': 'q3s_health',
    'branch': 'science',
    'position': 3,
    'condition': {'requires': 'q2s_field', 'field': 'field_health'},
    'prompt': {
        'en': 'Which part of healthcare draws you?',
        'bm': 'Bahagian penjagaan kesihatan mana yang menarik anda?',
        'ta': 'சுகாதாரத்தின் எந்தப் பகுதி உங்களை ஈர்க்கிறது?',
    },
    'options': [
        {
            'text': {
                'en': 'Becoming a doctor or dentist',
                'bm': 'Menjadi doktor atau doktor gigi',
                'ta': 'மருத்துவர் அல்லது பல் மருத்துவர் ஆவது',
            },
            'icon': 'stethoscope',
            'signals': {'field_key_perubatan': 2},
        },
        {
            'text': {
                'en': 'Pharmacy or biomedical science',
                'bm': 'Farmasi atau sains bioperubatan',
                'ta': 'மருந்தகவியல் அல்லது உயிரி மருத்துவ அறிவியல்',
            },
            'icon': 'pill_microscope',
            'signals': {'field_key_farmasi': 2},
        },
        {
            'text': {
                'en': 'Allied health — physiotherapy, dietetics, lab science',
                'bm': 'Kesihatan bersekutu — fisioterapi, dietetik, sains makmal',
                'ta': 'துணை சுகாதாரம் — இயன்முறை மருத்துவம், உணவியல், ஆய்வக அறிவியல்',
            },
            'icon': 'hands_heart',
            'signals': {'field_key_allied': 2},
        },
        {
            'text': {
                'en': 'Health administration or public health',
                'bm': 'Pentadbiran kesihatan atau kesihatan awam',
                'ta': 'சுகாதார நிர்வாகம் அல்லது பொது சுகாதாரம்',
            },
            'icon': 'clipboard_heart',
            'signals': {'field_key_health_admin': 2},
        },
    ],
}

Q3S_PURE_SCIENCE = {
    'id': 'q3s_pure_science',
    'branch': 'science',
    'position': 3,
    'condition': {'requires': 'q2s_field', 'field': 'field_pure_science'},
    'prompt': {
        'en': 'Which science excites you most?',
        'bm': 'Sains mana yang paling menarik minat anda?',
        'ta': 'எந்த அறிவியல் உங்களை மிகவும் ஈர்க்கிறது?',
    },
    'options': [
        {
            'text': {
                'en': 'Physics or Mathematics — theory and modelling',
                'bm': 'Fizik atau Matematik — teori dan pemodelan',
                'ta': 'இயற்பியல் அல்லது கணிதம் — கோட்பாடு மற்றும் மாதிரியாக்கம்',
            },
            'icon': 'atom_formula',
            'signals': {'field_key_sains_fizik': 2},
        },
        {
            'text': {
                'en': 'Chemistry or Materials — substances and reactions',
                'bm': 'Kimia atau Bahan — bahan dan tindak balas',
                'ta': 'வேதியியல் அல்லது பொருட்கள் — பொருட்கள் மற்றும் வினைகள்',
            },
            'icon': 'flask_bubbles',
            'signals': {'field_key_sains_kimia': 2},
        },
        {
            'text': {
                'en': 'Biology or Biotechnology — life and living systems',
                'bm': 'Biologi atau Bioteknologi — kehidupan dan sistem hidup',
                'ta': 'உயிரியல் அல்லது உயிர்தொழில்நுட்பம் — வாழ்க்கை மற்றும் உயிர் அமைப்புகள்',
            },
            'icon': 'dna_leaf',
            'signals': {'field_key_sains_bio': 2},
        },
        {
            'text': {
                'en': 'Environmental Science or Agriculture',
                'bm': 'Sains Alam Sekitar atau Pertanian',
                'ta': 'சுற்றுச்சூழல் அறிவியல் அல்லது வேளாண்மை',
            },
            'icon': 'leaf_tractor',
            'signals': {'field_key_alam': 2},
        },
    ],
}

Q3S_TECH = {
    'id': 'q3s_tech',
    'branch': 'science',
    'position': 3,
    'condition': {'requires': 'q2s_field', 'field': 'field_tech'},
    'prompt': {
        'en': 'What kind of tech work interests you?',
        'bm': 'Jenis kerja teknologi apa yang menarik minat anda?',
        'ta': 'எந்த வகை தொழில்நுட்ப வேலை உங்களுக்கு ஆர்வமாக உள்ளது?',
    },
    'options': [
        {
            'text': {
                'en': 'Software development — building apps and systems',
                'bm': 'Pembangunan perisian — membina aplikasi dan sistem',
                'ta': 'மென்பொருள் மேம்பாடு — செயலிகள் மற்றும் அமைப்புகளை உருவாக்குதல்',
            },
            'icon': 'laptop_code',
            'signals': {'field_key_it_sw': 2},
        },
        {
            'text': {
                'en': 'Networking & cybersecurity — infrastructure and protection',
                'bm': 'Rangkaian & keselamatan siber — infrastruktur dan perlindungan',
                'ta': 'வலையமைப்பு & இணையப் பாதுகாப்பு — உள்கட்டமைப்பு மற்றும் பாதுகாப்பு',
            },
            'icon': 'shield_network',
            'signals': {'field_key_it_net': 2},
        },
        {
            'text': {
                'en': 'Data science & AI — making sense of information',
                'bm': 'Sains data & AI — memahami maklumat',
                'ta': 'தரவு அறிவியல் & AI — தகவல்களைப் புரிந்துகொள்ளல்',
            },
            'icon': 'brain_chart',
            'signals': {'field_key_it_data': 2},
        },
        {
            'text': {
                'en': 'Creative tech — multimedia, games, digital design',
                'bm': 'Teknologi kreatif — multimedia, permainan, reka bentuk digital',
                'ta': 'படைப்பு தொழில்நுட்பம் — பல்லூடகம், விளையாட்டுகள், டிஜிட்டல் வடிவமைப்பு',
            },
            'icon': 'paintbrush_screen',
            'signals': {'field_key_multimedia': 2},
        },
    ],
}

# Science students who pick Business or Education in Q2s
# get redirected to the appropriate arts Q3 variant.
# This is handled by the engine, not by data structure.

# --- Q2a: Arts branch — primary field direction ---
Q2_ARTS = {
    'id': 'q2a_field',
    'branch': 'arts',
    'position': 2,
    'prompt': {
        'en': "You've studied the arts — which direction excites you most?",
        'bm': 'Anda telah belajar sastera — arah mana yang paling menarik?',
        'ta': 'நீங்கள் கலைப் பாடங்கள் படித்துள்ளீர்கள் — எந்தத் திசை உங்களை மிகவும் ஈர்க்கிறது?',
    },
    'options': [
        {
            'text': {
                'en': 'Business & Management — running organisations',
                'bm': 'Perniagaan & Pengurusan — menguruskan organisasi',
                'ta': 'வணிகம் & மேலாண்மை — நிறுவனங்களை நடத்துதல்',
            },
            'icon': 'handshake_chart',
            'signals': {'field_business': 3},
        },
        {
            'text': {
                'en': 'Law & Public Policy — justice and governance',
                'bm': 'Undang-undang & Dasar Awam — keadilan dan pentadbiran',
                'ta': 'சட்டம் & பொதுக் கொள்கை — நீதி மற்றும் ஆட்சி',
            },
            'icon': 'scales_document',
            'signals': {'field_law': 3},
        },
        {
            'text': {
                'en': 'Education & Social Work — shaping lives',
                'bm': 'Pendidikan & Kerja Sosial — membentuk kehidupan',
                'ta': 'கல்வி & சமூகப் பணி — வாழ்க்கைகளை வடிவமைத்தல்',
            },
            'icon': 'gradcap_people',
            'signals': {'field_education': 3},
        },
        {
            'text': {
                'en': 'Communications & Creative — media, writing, design',
                'bm': 'Komunikasi & Kreatif — media, penulisan, reka bentuk',
                'ta': 'தகவல் தொடர்பு & படைப்பு — ஊடகம், எழுத்து, வடிவமைப்பு',
            },
            'icon': 'paintbrush_mic',
            'signals': {'field_creative': 3},
        },
        {
            'text': {
                'en': 'Accounting & Finance — numbers and analysis',
                'bm': 'Perakaunan & Kewangan — nombor dan analisis',
                'ta': 'கணக்கியல் & நிதி — எண்கள் மற்றும் பகுப்பாய்வு',
            },
            'icon': 'calculator_chart',
            'signals': {'field_finance': 3},
        },
    ],
}

# --- Q3a variants: Arts sub-field refinement ---

Q3A_BUSINESS = {
    'id': 'q3a_business',
    'branch': 'arts',
    'position': 3,
    'condition': {'requires': 'q2a_field', 'field': 'field_business'},
    'prompt': {
        'en': 'What kind of business work interests you?',
        'bm': 'Jenis kerja perniagaan apa yang menarik minat anda?',
        'ta': 'எந்த வகை வணிகப் பணி உங்களுக்கு ஆர்வமாக உள்ளது?',
    },
    'options': [
        {
            'text': {
                'en': 'Marketing & branding — understanding people and markets',
                'bm': 'Pemasaran & penjenamaan — memahami orang dan pasaran',
                'ta': 'சந்தையியல் & வர்த்தகமுத்திரை — மக்களையும் சந்தைகளையும் புரிந்துகொள்ளல்',
            },
            'icon': 'megaphone_chart',
            'signals': {'field_key_pemasaran': 2},
        },
        {
            'text': {
                'en': 'Human resources — managing and developing talent',
                'bm': 'Sumber manusia — mengurus dan membangunkan bakat',
                'ta': 'மனிதவளம் — திறமைகளை நிர்வகித்தல் மற்றும் மேம்படுத்தல்',
            },
            'icon': 'people_gear',
            'signals': {'field_key_hr': 2},
        },
        {
            'text': {
                'en': 'International business — trade, logistics, global markets',
                'bm': 'Perniagaan antarabangsa — perdagangan, logistik, pasaran global',
                'ta': 'சர்வதேச வணிகம் — வர்த்தகம், தளவாடம், உலகச் சந்தைகள்',
            },
            'icon': 'globe_handshake',
            'signals': {'field_key_intl': 2},
        },
        {
            'text': {
                'en': 'Entrepreneurship — building something of my own',
                'bm': 'Keusahawanan — membina sesuatu milik sendiri',
                'ta': 'தொழில் முனைவு — என் சொந்தமாக ஒன்றை உருவாக்குதல்',
            },
            'icon': 'rocket_star',
            'signals': {'field_key_entrepren': 2},
        },
    ],
}

Q3A_LAW = {
    'id': 'q3a_law',
    'branch': 'arts',
    'position': 3,
    'condition': {'requires': 'q2a_field', 'field': 'field_law'},
    'prompt': {
        'en': 'What draws you to this field?',
        'bm': 'Apa yang menarik anda ke bidang ini?',
        'ta': 'இந்தத் துறையில் உங்களை ஈர்ப்பது என்ன?',
    },
    'options': [
        {
            'text': {
                'en': 'Practising law — advocacy and litigation',
                'bm': 'Mengamalkan undang-undang — peguambela dan litigasi',
                'ta': 'சட்ட நடைமுறை — வாதாடுதல் மற்றும் வழக்காடுதல்',
            },
            'icon': 'scales_gavel',
            'signals': {'field_key_law': 2},
        },
        {
            'text': {
                'en': 'Public administration — government and policy',
                'bm': 'Pentadbiran awam — kerajaan dan dasar',
                'ta': 'பொது நிர்வாகம் — அரசு மற்றும் கொள்கை',
            },
            'icon': 'building_flag',
            'signals': {'field_key_admin': 2},
        },
        {
            'text': {
                'en': 'International relations — diplomacy and global affairs',
                'bm': 'Hubungan antarabangsa — diplomasi dan hal ehwal global',
                'ta': 'சர்வதேச உறவுகள் — இராஜதந்திரம் மற்றும் உலக விவகாரங்கள்',
            },
            'icon': 'globe_handshake',
            'signals': {'field_key_ir': 2},
        },
    ],
}

Q3A_EDUCATION = {
    'id': 'q3a_education',
    'branch': 'arts',
    'position': 3,
    'condition': {'requires': 'q2a_field', 'field': 'field_education'},
    'prompt': {
        'en': 'How do you want to make a difference?',
        'bm': 'Bagaimana anda mahu membuat perubahan?',
        'ta': 'நீங்கள் எப்படி மாற்றத்தை ஏற்படுத்த விரும்புகிறீர்கள்?',
    },
    'options': [
        {
            'text': {
                'en': 'Teaching — classroom, school, inspiring students',
                'bm': 'Mengajar — bilik darjah, sekolah, menginspirasi pelajar',
                'ta': 'கற்பித்தல் — வகுப்பறை, பள்ளி, மாணவர்களை ஊக்குவித்தல்',
            },
            'icon': 'chalkboard_apple',
            'signals': {'field_key_pendidikan': 2},
        },
        {
            'text': {
                'en': 'Counselling & psychology — one-to-one support',
                'bm': 'Kaunseling & psikologi — sokongan satu lawan satu',
                'ta': 'ஆலோசனை & உளவியல் — தனிநபர் ஆதரவு',
            },
            'icon': 'brain_heart',
            'signals': {'field_key_kaunseling': 2},
        },
        {
            'text': {
                'en': 'Community development — programmes and social impact',
                'bm': 'Pembangunan komuniti — program dan impak sosial',
                'ta': 'சமூக மேம்பாடு — திட்டங்கள் மற்றும் சமூக தாக்கம்',
            },
            'icon': 'people_tree',
            'signals': {'field_key_sosial': 2},
        },
    ],
}

Q3A_CREATIVE = {
    'id': 'q3a_creative',
    'branch': 'arts',
    'position': 3,
    'condition': {'requires': 'q2a_field', 'field': 'field_creative'},
    'prompt': {
        'en': 'What kind of creative work excites you?',
        'bm': 'Jenis kerja kreatif apa yang menarik minat anda?',
        'ta': 'எந்த வகை படைப்பு வேலை உங்களை ஈர்க்கிறது?',
    },
    'options': [
        {
            'text': {
                'en': 'Journalism & media — telling stories that matter',
                'bm': 'Kewartawanan & media — menceritakan kisah yang penting',
                'ta': 'பத்திரிகையியல் & ஊடகம் — முக்கியமான கதைகளைச் சொல்லுதல்',
            },
            'icon': 'newspaper_mic',
            'signals': {'field_key_media': 2},
        },
        {
            'text': {
                'en': 'Graphic design & visual arts — making things look right',
                'bm': 'Reka bentuk grafik & seni visual — membuat sesuatu kelihatan betul',
                'ta': 'வரைகலை வடிவமைப்பு & காட்சிக் கலை — பொருட்களை அழகாகச் செய்தல்',
            },
            'icon': 'paintbrush_ruler',
            'signals': {'field_key_senireka': 2},
        },
        {
            'text': {
                'en': 'Film, animation, or digital content',
                'bm': 'Filem, animasi, atau kandungan digital',
                'ta': 'திரைப்படம், அனிமேஷன், அல்லது டிஜிட்டல் உள்ளடக்கம்',
            },
            'icon': 'camera_sparkle',
            'signals': {'field_key_digital': 2},
        },
        {
            'text': {
                'en': 'Advertising & PR — persuading and positioning',
                'bm': 'Pengiklanan & PR — memujuk dan meletakkan kedudukan',
                'ta': 'விளம்பரம் & PR — வற்புறுத்துதல் மற்றும் நிலைப்படுத்துதல்',
            },
            'icon': 'megaphone_star',
            'signals': {'field_key_pr': 2},
        },
    ],
}

Q3A_FINANCE = {
    'id': 'q3a_finance',
    'branch': 'arts',
    'position': 3,
    'condition': {'requires': 'q2a_field', 'field': 'field_finance'},
    'prompt': {
        'en': 'What interests you about this field?',
        'bm': 'Apa yang menarik minat anda tentang bidang ini?',
        'ta': 'இந்தத் துறையில் உங்களுக்கு ஆர்வமானது என்ன?',
    },
    'options': [
        {
            'text': {
                'en': 'Auditing & accounting — accuracy and compliance',
                'bm': 'Pengauditan & perakaunan — ketepatan dan pematuhan',
                'ta': 'தணிக்கை & கணக்கியல் — துல்லியம் மற்றும் இணக்கம்',
            },
            'icon': 'calculator_check',
            'signals': {'field_key_perakaunan': 2},
        },
        {
            'text': {
                'en': 'Investment & banking — markets and money',
                'bm': 'Pelaburan & perbankan — pasaran dan wang',
                'ta': 'முதலீடு & வங்கியியல் — சந்தைகள் மற்றும் பணம்',
            },
            'icon': 'chart_money',
            'signals': {'field_key_kewangan': 2},
        },
        {
            'text': {
                'en': 'Actuarial science — risk and statistics',
                'bm': 'Sains aktuari — risiko dan statistik',
                'ta': 'காப்பீட்டுக் கணிதம் — இடர் மற்றும் புள்ளியியல்',
            },
            'icon': 'graph_shield',
            'signals': {'field_key_aktuari': 2},
        },
        {
            'text': {
                'en': 'Financial planning — helping people manage money',
                'bm': 'Perancangan kewangan — membantu orang mengurus wang',
                'ta': 'நிதி திட்டமிடல் — மக்களின் பண நிர்வாகத்திற்கு உதவுதல்',
            },
            'icon': 'wallet_people',
            'signals': {'field_key_fin_plan': 2},
        },
    ],
}

# --- Q2m: Mixed branch — broad exploration ---
Q2_MIXED = {
    'id': 'q2m_field',
    'branch': 'mixed',
    'position': 2,
    'prompt': {
        'en': 'Your subjects cross different areas. Which direction appeals to you most?',
        'bm': 'Mata pelajaran anda merentasi pelbagai bidang. Arah mana yang paling menarik?',
        'ta': 'உங்கள் பாடங்கள் வெவ்வேறு துறைகளை உள்ளடக்குகின்றன. எந்தத் திசை உங்களை மிகவும் ஈர்க்கிறது?',
    },
    'options': [
        {
            'text': {
                'en': 'Science & Technology',
                'bm': 'Sains & Teknologi',
                'ta': 'அறிவியல் & தொழில்நுட்பம்',
            },
            'icon': 'atom_laptop',
            'signals': {'field_pure_science': 2, 'field_tech': 1},
        },
        {
            'text': {
                'en': 'Health & Life Sciences',
                'bm': 'Kesihatan & Sains Hayat',
                'ta': 'சுகாதாரம் & உயிர் அறிவியல்',
            },
            'icon': 'heart_dna',
            'signals': {'field_health': 3},
        },
        {
            'text': {
                'en': 'Business & Finance',
                'bm': 'Perniagaan & Kewangan',
                'ta': 'வணிகம் & நிதி',
            },
            'icon': 'handshake_chart',
            'signals': {'field_business': 2, 'field_finance': 1},
        },
        {
            'text': {
                'en': 'Education & Social Services',
                'bm': 'Pendidikan & Perkhidmatan Sosial',
                'ta': 'கல்வி & சமூக சேவைகள்',
            },
            'icon': 'gradcap_people',
            'signals': {'field_education': 3},
        },
        {
            'text': {
                'en': 'Law & Public Administration',
                'bm': 'Undang-undang & Pentadbiran Awam',
                'ta': 'சட்டம் & பொது நிர்வாகம்',
            },
            'icon': 'scales_document',
            'signals': {'field_law': 3},
        },
        {
            'text': {
                'en': 'Creative & Communications',
                'bm': 'Kreatif & Komunikasi',
                'ta': 'படைப்பு & தகவல் தொடர்பு',
            },
            'icon': 'paintbrush_mic',
            'signals': {'field_creative': 3},
        },
    ],
}

# Q3m uses the same sub-field questions as Science and Arts branches.
# The engine routes to the appropriate Q3 variant based on Q2m answer.

# --- Q4: Confidence check (adaptive — uses actual grades) ---
# The engine dynamically selects the right Q4 variant based on:
# 1. The student's Q2/Q3 field choice
# 2. Their actual STPM grades in the relevant subject
# Two templates: one for when grades are WEAK, one for STRONG.

Q4_CONFIDENCE_WEAK = {
    'id': 'q4_confidence_weak',
    'branch': 'adaptive',
    'position': 4,
    'adaptive': True,
    'prompt': {
        'en': "You're drawn to {field}, but your {subject} grade is {grade}. How do you feel about that?",
        'bm': 'Anda tertarik dengan {field}, tetapi gred {subject} anda ialah {grade}. Bagaimana perasaan anda?',
        'ta': 'நீங்கள் {field} துறையில் ஆர்வமாக உள்ளீர்கள், ஆனால் உங்கள் {subject} தரம் {grade}. அதைப் பற்றி எப்படி உணர்கிறீர்கள்?',
    },
    'options': [
        {
            'text': {
                'en': "I'll work harder — I know I can improve",
                'bm': 'Saya akan berusaha lebih keras — saya tahu saya boleh',
                'ta': 'நான் கடினமாக உழைப்பேன் — என்னால் சிறப்பாகச் செய்ய முடியும் என்று தெரியும்',
            },
            'icon': 'flexed_arm_star',
            'signals': {'efficacy_confident': 2},
        },
        {
            'text': {
                'en': "I'd prefer a related field that's less demanding in {subject}",
                'bm': 'Saya lebih suka bidang berkaitan yang kurang menuntut dalam {subject}',
                'ta': '{subject} இல் குறைவான கோரிக்கை கொண்ட தொடர்புடைய துறையை விரும்புவேன்',
            },
            'icon': 'compass_arrow',
            'signals': {'efficacy_redirect': 1},
        },
        {
            'text': {
                'en': 'Maybe I should explore other options too',
                'bm': 'Mungkin saya perlu meneroka pilihan lain juga',
                'ta': 'ஒருவேளை நான் வேறு வாய்ப்புகளையும் ஆராய வேண்டும்',
            },
            'icon': 'magnifying_question',
            'signals': {'efficacy_uncertain': 0},
        },
    ],
}

Q4_CONFIDENCE_STRONG = {
    'id': 'q4_confidence_strong',
    'branch': 'adaptive',
    'position': 4,
    'adaptive': True,
    'prompt': {
        'en': 'Your {subject} results are strong. Are you confident you\'d enjoy 4 years of {field} study?',
        'bm': 'Keputusan {subject} anda cemerlang. Adakah anda yakin anda akan menikmati 4 tahun pengajian {field}?',
        'ta': 'உங்கள் {subject} முடிவுகள் சிறப்பாக உள்ளன. 4 ஆண்டுகள் {field} படிப்பை நீங்கள் ரசிப்பீர்கள் என்று நம்புகிறீர்களா?',
    },
    'options': [
        {
            'text': {
                'en': 'Absolutely — this is what I want',
                'bm': 'Sudah tentu — inilah yang saya mahu',
                'ta': 'நிச்சயமாக — இதுதான் நான் விரும்புவது',
            },
            'icon': 'target_bullseye',
            'signals': {'efficacy_confirmed': 2},
        },
        {
            'text': {
                'en': "Mostly, but I'd like to keep my options open",
                'bm': 'Kebanyakannya ya, tetapi saya ingin buka pilihan lain',
                'ta': 'பெரும்பாலும் ஆம், ஆனால் என் வாய்ப்புகளைத் திறந்து வைக்க விரும்புகிறேன்',
            },
            'icon': 'compass_arrow',
            'signals': {'efficacy_open': 1},
        },
        {
            'text': {
                'en': "Actually, I'm not sure {field} is right for me",
                'bm': 'Sebenarnya, saya tidak pasti {field} sesuai untuk saya',
                'ta': 'உண்மையில், {field} எனக்கு சரியானதா என்று தெரியவில்லை',
            },
            'icon': 'magnifying_question',
            'signals': {'efficacy_mismatch': 0},
        },
    ],
}

# --- Q5: Cross-domain interest (Holland's hexagon) ---
# Options are dynamically filtered by the engine based on stream.
# Science students see all options; arts students see only achievable ones.

Q5_CROSS_DOMAIN_OPTIONS = {
    'id': 'q5_cross_domain',
    'branch': 'trunk',
    'position': 5,
    'prompt': {
        'en': 'Is there an area outside your main subjects that also appeals to you?',
        'bm': 'Adakah bidang di luar mata pelajaran utama anda yang turut menarik minat anda?',
        'ta': 'உங்கள் முக்கிய பாடங்களுக்கு வெளியே உங்களை ஈர்க்கும் வேறு ஏதேனும் துறை உள்ளதா?',
    },
    # Full option pool — engine filters based on stream
    'all_options': {
        'business': {
            'text': {
                'en': 'Business & entrepreneurship',
                'bm': 'Perniagaan & keusahawanan',
                'ta': 'வணிகம் & தொழில் முனைவு',
            },
            'icon': 'rocket_chart',
            'signals': {'cross_E': 1},
            'available_to': ['science', 'mixed'],
        },
        'teaching': {
            'text': {
                'en': 'Teaching & counselling',
                'bm': 'Pengajaran & kaunseling',
                'ta': 'கற்பித்தல் & ஆலோசனை',
            },
            'icon': 'gradcap_heart',
            'signals': {'cross_S': 1},
            'available_to': ['science', 'mixed'],
        },
        'creative': {
            'text': {
                'en': 'Design & creative arts',
                'bm': 'Reka bentuk & seni kreatif',
                'ta': 'வடிவமைப்பு & படைப்புக் கலைகள்',
            },
            'icon': 'paintbrush_star',
            'signals': {'cross_A': 1},
            'available_to': ['science', 'mixed'],
        },
        'law': {
            'text': {
                'en': 'Law & policy',
                'bm': 'Undang-undang & dasar',
                'ta': 'சட்டம் & கொள்கை',
            },
            'icon': 'scales_document',
            'signals': {'cross_E': 1},
            'available_to': ['science', 'mixed'],
        },
        'data_systems': {
            'text': {
                'en': 'Data & systems',
                'bm': 'Data & sistem',
                'ta': 'தரவு & அமைப்புகள்',
            },
            'icon': 'brain_chart',
            'signals': {'cross_C': 1},
            'available_to': ['science', 'mixed'],
        },
        'health_admin': {
            'text': {
                'en': 'Health administration',
                'bm': 'Pentadbiran kesihatan',
                'ta': 'சுகாதார நிர்வாகம்',
            },
            'icon': 'clipboard_heart',
            'signals': {'cross_S': 1, 'cross_I': 1},
            'available_to': ['arts', 'mixed'],
        },
        'it_management': {
            'text': {
                'en': 'IT management',
                'bm': 'Pengurusan IT',
                'ta': 'IT மேலாண்மை',
            },
            'icon': 'laptop_gear',
            'signals': {'cross_C': 1, 'cross_I': 1},
            'available_to': ['arts', 'mixed'],
        },
        'environment': {
            'text': {
                'en': 'Environmental studies',
                'bm': 'Pengajian alam sekitar',
                'ta': 'சுற்றுச்சூழல் ஆய்வுகள்',
            },
            'icon': 'leaf_globe',
            'signals': {'cross_R': 1},
            'available_to': ['arts', 'mixed'],
        },
        'education_arts': {
            'text': {
                'en': 'Education',
                'bm': 'Pendidikan',
                'ta': 'கல்வி',
            },
            'icon': 'gradcap_people',
            'signals': {'cross_S': 1},
            'available_to': ['arts'],
        },
        'stay_in_lane': {
            'text': {
                'en': "No — I want to stay in my lane",
                'bm': 'Tidak — saya mahu kekal dalam bidang saya',
                'ta': 'இல்லை — என் துறையிலேயே இருக்க விரும்புகிறேன்',
            },
            'icon': 'target_bullseye',
            'signals': {},
            'available_to': ['science', 'arts', 'mixed'],
        },
    },
}

# --- Q6: Confidence for cross-domain (adaptive, same as Q4 pattern) ---
# Skipped if Q5 = "stay in my lane". Engine handles this.
# Not a separate data structure — the engine reuses Q4 templates if needed.
# For simplicity in v1, Q6 is omitted and its position is used by Q7.

# --- Q7: Challenge appetite (SCCT — coping efficacy) ---
Q7_CHALLENGE = {
    'id': 'q7_challenge',
    'branch': 'trunk',
    'position': 6,
    'prompt': {
        'en': 'When a subject is really hard, what do you do?',
        'bm': 'Apabila sesuatu subjek sangat sukar, apa yang anda lakukan?',
        'ta': 'ஒரு பாடம் மிகவும் கடினமாக இருக்கும்போது, நீங்கள் என்ன செய்வீர்கள்?',
    },
    'options': [
        {
            'text': {
                'en': 'Dig in harder — I like the challenge',
                'bm': 'Usaha lebih keras — saya suka cabaran',
                'ta': 'இன்னும் கடினமாக உழைப்பேன் — எனக்கு சவால் பிடிக்கும்',
            },
            'icon': 'flexed_arm_fire',
            'signals': {'resilience_high': 2},
        },
        {
            'text': {
                'en': 'Get help and push through',
                'bm': 'Dapatkan bantuan dan teruskan',
                'ta': 'உதவி பெற்று தொடர்வேன்',
            },
            'icon': 'hands_up',
            'signals': {'resilience_supported': 1},
        },
        {
            'text': {
                'en': "Switch focus to what I'm better at",
                'bm': 'Tukar fokus kepada apa yang saya lebih baik',
                'ta': 'நான் சிறந்த துறைக்கு கவனத்தை மாற்றுவேன்',
            },
            'icon': 'arrow_turn',
            'signals': {'resilience_redirect': 1},
        },
        {
            'text': {
                'en': "Depends — if I care about it, I'll fight for it",
                'bm': 'Bergantung — kalau saya kisah, saya akan berusaha',
                'ta': 'பொறுத்தது — எனக்கு அக்கறை இருந்தால், போராடுவேன்',
            },
            'icon': 'heart_shield',
            'signals': {'resilience_interest': 1},
        },
    ],
}

# --- Q8: Motivation source (SDT) ---
Q8_MOTIVATION = {
    'id': 'q8_motivation',
    'branch': 'trunk',
    'position': 7,
    'prompt': {
        'en': 'What matters most when choosing what to study?',
        'bm': 'Apa yang paling penting apabila memilih apa untuk dipelajari?',
        'ta': 'என்ன படிக்க வேண்டும் என்று தேர்ந்தெடுக்கும்போது எது மிக முக்கியம்?',
    },
    'options': [
        {
            'text': {
                'en': 'I want to love what I study',
                'bm': 'Saya mahu menyukai apa yang saya pelajari',
                'ta': 'நான் படிப்பதை நேசிக்க விரும்புகிறேன்',
            },
            'icon': 'heart_book',
            'signals': {'motivation_autonomous': 2},
        },
        {
            'text': {
                'en': 'I want a stable, well-paying career',
                'bm': 'Saya mahu kerjaya yang stabil dan bergaji baik',
                'ta': 'நிலையான, நல்ல ஊதியமுள்ள தொழிலை விரும்புகிறேன்',
            },
            'icon': 'shield_money',
            'signals': {'motivation_career': 2},
        },
        {
            'text': {
                'en': 'I want to make my family proud',
                'bm': 'Saya mahu membanggakan keluarga saya',
                'ta': 'என் குடும்பத்தைப் பெருமைப்படுத்த விரும்புகிறேன்',
            },
            'icon': 'family_star',
            'signals': {'motivation_family': 2},
        },
        {
            'text': {
                'en': 'I want a respected qualification',
                'bm': 'Saya mahu kelayakan yang dihormati',
                'ta': 'மதிக்கப்படும் தகுதியை விரும்புகிறேன்',
            },
            'icon': 'certificate_crown',
            'signals': {'motivation_prestige': 2},
        },
    ],
}

# --- Q9: Career horizon (SCCT — outcome expectations) ---
Q9_CAREER = {
    'id': 'q9_career',
    'branch': 'trunk',
    'position': 8,
    'prompt': {
        'en': "What's your goal after graduating?",
        'bm': 'Apa matlamat anda selepas bergraduasi?',
        'ta': 'பட்டம் பெற்ற பிறகு உங்கள் இலக்கு என்ன?',
    },
    'options': [
        {
            'text': {
                'en': 'Practise a specific profession (doctor, engineer, lawyer, etc.)',
                'bm': 'Mengamalkan profesion tertentu (doktor, jurutera, peguam, dll.)',
                'ta': 'ஒரு குறிப்பிட்ட தொழிலைப் பயிற்சி செய்தல் (மருத்துவர், பொறியாளர், வழக்கறிஞர், முதலியவை)',
            },
            'icon': 'briefcase_star',
            'signals': {'goal_professional': 2},
        },
        {
            'text': {
                'en': 'Get a good job in any well-paying field',
                'bm': 'Mendapat kerja yang baik dalam mana-mana bidang bergaji tinggi',
                'ta': 'நல்ல ஊதியம் தரும் எந்தத் துறையிலும் நல்ல வேலை பெறுதல்',
            },
            'icon': 'money_briefcase',
            'signals': {'goal_employment': 2},
        },
        {
            'text': {
                'en': 'Continue to postgraduate study (Masters, PhD)',
                'bm': 'Melanjutkan pengajian pascasiswazah (Sarjana, PhD)',
                'ta': 'முதுகலை படிப்பைத் தொடர்தல் (முதுநிலை, முனைவர்)',
            },
            'icon': 'gradcap_arrow',
            'signals': {'goal_postgrad': 2},
        },
        {
            'text': {
                'en': 'Start my own business or venture',
                'bm': 'Memulakan perniagaan atau usaha sendiri',
                'ta': 'சொந்த தொழிலை அல்லது முயற்சியைத் தொடங்குதல்',
            },
            'icon': 'rocket_star',
            'signals': {'goal_entrepreneurial': 2},
        },
    ],
}

# --- Q10: Family influence (SCCT — collectivist adaptation) ---
Q10_FAMILY = {
    'id': 'q10_family',
    'branch': 'trunk',
    'position': 9,
    'prompt': {
        'en': "How much does your family's opinion influence your course choice?",
        'bm': 'Sejauh mana pendapat keluarga anda mempengaruhi pilihan kursus anda?',
        'ta': 'உங்கள் குடும்பத்தின் கருத்து உங்கள் படிப்பு தேர்வை எவ்வளவு பாதிக்கிறது?',
    },
    'options': [
        {
            'text': {
                'en': 'A lot — their guidance is very important to me',
                'bm': 'Sangat banyak — bimbingan mereka sangat penting bagi saya',
                'ta': 'மிகவும் — அவர்களின் வழிகாட்டுதல் எனக்கு மிக முக்கியம்',
            },
            'icon': 'family_heart',
            'signals': {'family_influence_high': 2},
        },
        {
            'text': {
                'en': 'Somewhat — I consider their views but decide myself',
                'bm': 'Sedikit sebanyak — saya pertimbangkan pandangan mereka tetapi membuat keputusan sendiri',
                'ta': 'ஓரளவு — அவர்கள் கருத்துகளைக் கருதுகிறேன் ஆனால் நானே முடிவு செய்கிறேன்',
            },
            'icon': 'people_scale',
            'signals': {'family_influence_moderate': 1},
        },
        {
            'text': {
                'en': 'Not much — this is fully my decision',
                'bm': 'Tidak banyak — ini sepenuhnya keputusan saya',
                'ta': 'அதிகம் இல்லை — இது முழுமையாக என் முடிவு',
            },
            'icon': 'person_arrow',
            'signals': {'family_influence_low': 0},
        },
    ],
}


# --- Organised collections for engine use ---

TRUNK_QUESTIONS = [Q1_READINESS, Q7_CHALLENGE, Q8_MOTIVATION, Q9_CAREER, Q10_FAMILY]
SCIENCE_Q2 = Q2_SCIENCE
ARTS_Q2 = Q2_ARTS
MIXED_Q2 = Q2_MIXED

SCIENCE_Q3_VARIANTS = {
    'field_engineering': Q3S_ENGINEERING,
    'field_health': Q3S_HEALTH,
    'field_pure_science': Q3S_PURE_SCIENCE,
    'field_tech': Q3S_TECH,
    # Science students who pick business/education get the arts Q3 variant
    'field_business': Q3A_BUSINESS,
    'field_education': Q3A_EDUCATION,
}

ARTS_Q3_VARIANTS = {
    'field_business': Q3A_BUSINESS,
    'field_law': Q3A_LAW,
    'field_education': Q3A_EDUCATION,
    'field_creative': Q3A_CREATIVE,
    'field_finance': Q3A_FINANCE,
}

# Mixed branch reuses variants from both science and arts
MIXED_Q3_VARIANTS = {
    **SCIENCE_Q3_VARIANTS,
    **ARTS_Q3_VARIANTS,
}

ALL_QUESTION_IDS = [
    'q1_readiness',
    'q2s_field', 'q2a_field', 'q2m_field',
    'q3s_engineering', 'q3s_health', 'q3s_pure_science', 'q3s_tech',
    'q3a_business', 'q3a_law', 'q3a_education', 'q3a_creative', 'q3a_finance',
    'q4_confidence_weak', 'q4_confidence_strong',
    'q5_cross_domain',
    'q7_challenge', 'q8_motivation', 'q9_career', 'q10_family',
]

# Field → relevant STPM subject mapping (for grade-adaptive Q4)
FIELD_TO_SUBJECT = {
    'field_engineering': ['physics', 'mathematics_t'],
    'field_health': ['biology', 'chemistry'],
    'field_pure_science': ['physics', 'chemistry', 'biology', 'mathematics_t'],
    'field_tech': ['mathematics_t', 'ict', 'physics'],
    'field_business': ['economics', 'business_studies'],
    'field_education': [],  # No specific subject tie
    'field_law': ['economics', 'history'],
    'field_creative': ['literature_english', 'visual_arts'],
    'field_finance': ['accounting', 'economics', 'mathematics_m'],
}

# Grade threshold for "weak" vs "strong" in adaptive Q4
# B- (2.67) or lower is considered weak for the target field
WEAK_GRADE_THRESHOLD = 2.67

# STPM grade → GPA points (for Q4 threshold check)
STPM_GRADE_POINTS = {
    'A': 4.00, 'A-': 3.67,
    'B+': 3.33, 'B': 3.00, 'B-': 2.67,
    'C+': 2.33, 'C': 2.00, 'C-': 1.67,
    'D+': 1.33, 'D': 1.00,
    'F': 0.00,
}

# Field display names for Q4 prompt interpolation
FIELD_DISPLAY_NAMES = {
    'field_engineering': {
        'en': 'engineering', 'bm': 'kejuruteraan', 'ta': 'பொறியியல்',
    },
    'field_health': {
        'en': 'healthcare', 'bm': 'penjagaan kesihatan', 'ta': 'சுகாதாரம்',
    },
    'field_pure_science': {
        'en': 'science', 'bm': 'sains', 'ta': 'அறிவியல்',
    },
    'field_tech': {
        'en': 'technology', 'bm': 'teknologi', 'ta': 'தொழில்நுட்பம்',
    },
    'field_business': {
        'en': 'business', 'bm': 'perniagaan', 'ta': 'வணிகம்',
    },
    'field_education': {
        'en': 'education', 'bm': 'pendidikan', 'ta': 'கல்வி',
    },
    'field_law': {
        'en': 'law', 'bm': 'undang-undang', 'ta': 'சட்டம்',
    },
    'field_creative': {
        'en': 'creative arts', 'bm': 'seni kreatif', 'ta': 'படைப்புக் கலைகள்',
    },
    'field_finance': {
        'en': 'finance', 'bm': 'kewangan', 'ta': 'நிதி',
    },
}

# Subject display names for Q4 prompt interpolation
SUBJECT_DISPLAY_NAMES = {
    'physics': {'en': 'Physics', 'bm': 'Fizik', 'ta': 'இயற்பியல்'},
    'chemistry': {'en': 'Chemistry', 'bm': 'Kimia', 'ta': 'வேதியியல்'},
    'biology': {'en': 'Biology', 'bm': 'Biologi', 'ta': 'உயிரியல்'},
    'mathematics_t': {'en': 'Mathematics T', 'bm': 'Matematik T', 'ta': 'கணிதம் T'},
    'mathematics_m': {'en': 'Mathematics M', 'bm': 'Matematik M', 'ta': 'கணிதம் M'},
    'ict': {'en': 'ICT', 'bm': 'ICT', 'ta': 'ICT'},
    'economics': {'en': 'Economics', 'bm': 'Ekonomi', 'ta': 'பொருளாதாரம்'},
    'accounting': {'en': 'Accounting', 'bm': 'Perakaunan', 'ta': 'கணக்கியல்'},
    'business_studies': {'en': 'Business Studies', 'bm': 'Pengajian Perniagaan', 'ta': 'வணிகவியல்'},
    'literature_english': {'en': 'Literature in English', 'bm': 'Kesusasteraan Inggeris', 'ta': 'ஆங்கில இலக்கியம்'},
    'geography': {'en': 'Geography', 'bm': 'Geografi', 'ta': 'புவியியல்'},
    'history': {'en': 'History', 'bm': 'Sejarah', 'ta': 'வரலாறு'},
    'visual_arts': {'en': 'Visual Arts', 'bm': 'Seni Visual', 'ta': 'காட்சிக் கலை'},
    'syariah': {'en': 'Syariah', 'bm': 'Syariah', 'ta': 'ஷரீஆ'},
}
