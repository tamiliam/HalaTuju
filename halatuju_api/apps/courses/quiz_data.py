"""
Quiz question data — 6 questions × 3 languages (EN, BM, TA).

Each question has:
- id: stable identifier (used as key in answer submission)
- prompt: the question text
- options: list of {text, signals} where signals is a dict of signal_name → weight

This is pure data — no logic, no state, no imports.
Ported from src/quiz_data.py (Streamlit era).
"""

QUIZ_QUESTIONS = {
    'en': [
        {
            'id': 'q1_modality',
            'prompt': 'Which type of work sounds least tiring to you?',
            'options': [
                {'text': 'Working with tools, machines, or equipment', 'signals': {'hands_on': 2}},
                {'text': 'Solving problems, calculations, or technical tasks', 'signals': {'problem_solving': 2}},
                {'text': 'Helping, teaching, or assisting people', 'signals': {'people_helping': 2}},
                {'text': 'Creating or designing things', 'signals': {'creative': 2}},
                {'text': 'Organising, coordinating, or managing tasks', 'signals': {'organising': 2}},
            ],
        },
        {
            'id': 'q2_environment',
            'prompt': "On most days, you'd rather be working in:",
            'options': [
                {'text': 'A workshop, lab, or technical space', 'signals': {'workshop_environment': 1}},
                {'text': 'An office or computer-based setting', 'signals': {'office_environment': 1}},
                {'text': 'A place where you interact with many people', 'signals': {'high_people_environment': 1}},
                {'text': 'Different locations (field work, site visits)', 'signals': {'field_environment': 1}},
                {'text': 'No strong preference', 'signals': {'no_preference': 1}},
            ],
        },
        {
            'id': 'q3_learning',
            'prompt': 'Which describes you better as a student?',
            'options': [
                {'text': 'I learn best by doing and practising', 'signals': {'learning_by_doing': 1}},
                {'text': 'I prefer understanding concepts before applying them', 'signals': {'concept_first': 1}},
                {'text': "I'm okay memorising if expectations are clear", 'signals': {'rote_tolerant': 1}},
                {'text': 'I do better with projects than exams', 'signals': {'project_based': 1}},
                {'text': 'I struggle with exams under time pressure', 'signals': {'exam_sensitive': 1}},
            ],
        },
        {
            'id': 'q4_values',
            'prompt': 'Right now, which matters more to you?',
            'options': [
                {'text': 'Job stability after graduation', 'signals': {'stability_priority': 2}},
                {'text': 'Income potential, even if risky', 'signals': {'income_risk_tolerant': 2}},
                {'text': 'Opportunities to continue to a degree', 'signals': {'pathway_priority': 2}},
                {'text': 'Doing work that feels meaningful', 'signals': {'meaning_priority': 2}},
                {'text': 'Finishing studies quickly to start working', 'signals': {'fast_employment_priority': 2}},
            ],
        },
        {
            'id': 'q5_energy',
            'prompt': 'After a full day, what usually drains you more?',
            'options': [
                {'text': 'Dealing with many people', 'signals': {'low_people_tolerance': 1}},
                {'text': 'Concentrating on technical or detailed work', 'signals': {'mental_fatigue_sensitive': 1}},
                {'text': 'Physical or hands-on work', 'signals': {'physical_fatigue_sensitive': 1}},
                {'text': 'Being under time pressure', 'signals': {'time_pressure_sensitive': 1}},
                {'text': 'Nothing in particular', 'signals': {}},
            ],
        },
        {
            'id': 'q6_survival',
            'prompt': 'Which of these would make it easiest for you to continue your studies?',
            'options': [
                {'text': 'Receiving a monthly allowance (pocket money)', 'signals': {'allowance_priority': 3}},
                {'text': 'Staying as close to my home and family as possible', 'signals': {'proximity_priority': 3}},
                {'text': 'Having a guaranteed job interview after I graduate', 'signals': {'employment_guarantee': 2}},
                {'text': 'No strong preference', 'signals': {}},
            ],
        },
    ],
    'bm': [
        {
            'id': 'q1_modality',
            'prompt': 'Jenis kerja manakah yang anda rasa paling kurang memenatkan?',
            'options': [
                {'text': 'Bekerja dengan peralatan, mesin, atau alatan tangan', 'signals': {'hands_on': 2}},
                {'text': 'Menelesaikan masalah, pengiraan, atau tugasan teknikal', 'signals': {'problem_solving': 2}},
                {'text': 'Membantu, mengajar, atau melayan orang ramai', 'signals': {'people_helping': 2}},
                {'text': 'Mencipta atau mereka bentuk sesuatu', 'signals': {'creative': 2}},
                {'text': 'Mengurus, menyelaras, atau mentadbir tugasan', 'signals': {'organising': 2}},
            ],
        },
        {
            'id': 'q2_environment',
            'prompt': 'Pada kebanyakan hari, anda lebih suka bekerja di:',
            'options': [
                {'text': 'Bengkel, makmal, atau ruang teknikal', 'signals': {'workshop_environment': 1}},
                {'text': 'Pejabat atau persekitaran berasaskan komputer', 'signals': {'office_environment': 1}},
                {'text': 'Tempat di mana anda berinteraksi dengan ramai orang', 'signals': {'high_people_environment': 1}},
                {'text': 'Lokasi berbeza (kerja lapangan, lawatan tapak)', 'signals': {'field_environment': 1}},
                {'text': 'Tiada keutamaan khusus', 'signals': {'no_preference': 1}},
            ],
        },
        {
            'id': 'q3_learning',
            'prompt': 'Yang manakah menerangkan diri anda sebagai pelajar?',
            'options': [
                {'text': 'Saya belajar terbaik dengan melakukan dan mempraktikkan', 'signals': {'learning_by_doing': 1}},
                {'text': 'Saya lebih suka memahami konsep sebelum mengaplikasikannya', 'signals': {'concept_first': 1}},
                {'text': 'Saya okay menghafal jika jangkaannya jelas', 'signals': {'rote_tolerant': 1}},
                {'text': 'Saya lebih baik dengan projek berbanding peperiksaan', 'signals': {'project_based': 1}},
                {'text': 'Saya sukar menghadapi peperiksaan di bawah tekanan masa', 'signals': {'exam_sensitive': 1}},
            ],
        },
        {
            'id': 'q4_values',
            'prompt': 'Buat masa ini, apakah yang lebih penting bagi anda?',
            'options': [
                {'text': 'Kestabilan kerja selepas tamat pengajian', 'signals': {'stability_priority': 2}},
                {'text': 'Potensi pendapatan, walaupun berisiko', 'signals': {'income_risk_tolerant': 2}},
                {'text': 'Peluang untuk menyambung ke ijazah', 'signals': {'pathway_priority': 2}},
                {'text': 'Melakukan kerja yang rasa bermakna', 'signals': {'meaning_priority': 2}},
                {'text': 'Menamatkan pengajian dengan cepat untuk mula bekerja', 'signals': {'fast_employment_priority': 2}},
            ],
        },
        {
            'id': 'q5_energy',
            'prompt': 'Selepas seharian, apa yang biasanya paling meletihkan anda?',
            'options': [
                {'text': 'Berurusan dengan ramai orang', 'signals': {'low_people_tolerance': 1}},
                {'text': 'Menumpukan pada kerja teknikal atau terperinci', 'signals': {'mental_fatigue_sensitive': 1}},
                {'text': "Kerja fizikal atau 'hands-on'", 'signals': {'physical_fatigue_sensitive': 1}},
                {'text': 'Berada di bawah tekanan masa', 'signals': {'time_pressure_sensitive': 1}},
                {'text': 'Tiada apa-apa secara khusus', 'signals': {}},
            ],
        },
        {
            'id': 'q6_survival',
            'prompt': 'Antara berikut, yang manakah akan memudahkan anda untuk menyambung pelajaran?',
            'options': [
                {'text': 'Menerima elaun bulanan (duit poket)', 'signals': {'allowance_priority': 3}},
                {'text': 'Kekal sedekat mungkin dengan rumah dan keluarga', 'signals': {'proximity_priority': 3}},
                {'text': 'Mempunyai jaminan temuduga kerja selepas tamat pengajian', 'signals': {'employment_guarantee': 2}},
                {'text': 'Tiada keutamaan khusus', 'signals': {}},
            ],
        },
    ],
    'ta': [
        {
            'id': 'q1_modality',
            'prompt': 'எந்த வகையான வேலை உங்களுக்கு குறைவாக சோர்வை ஏற்படுத்தும்?',
            'options': [
                {'text': 'கருவிகள், இயந்திரங்கள் அல்லது உபகரணங்களுடன் வேலை செய்தல்', 'signals': {'hands_on': 2}},
                {'text': 'சிக்கல்களைத் தீர்ப்பது, கணக்கீடுகள் அல்லது தொழில்நுட்பப் பணிகள்', 'signals': {'problem_solving': 2}},
                {'text': 'மக்களுக்கு உதவுதல், கற்பித்தல் அல்லது சேவை செய்தல்', 'signals': {'people_helping': 2}},
                {'text': 'எதையாவது உருவாக்குதல் அல்லது வடிவமைத்தல்', 'signals': {'creative': 2}},
                {'text': 'பணிகளை ஒழுங்கமைத்தல், ஒருங்கிணைத்தல் அல்லது நிர்வகித்தல்', 'signals': {'organising': 2}},
            ],
        },
        {
            'id': 'q2_environment',
            'prompt': 'பெரும்பாலான நாட்களில், நீங்கள் எங்கே வேலை செய்ய விரும்புகிறீர்கள்?',
            'options': [
                {'text': 'ஒரு பட்டறை, ஆய்வகம் அல்லது தொழில்நுட்ப இடம்', 'signals': {'workshop_environment': 1}},
                {'text': 'ஒரு அலுவலகம் அல்லது கணினி சார்ந்த சூழல்', 'signals': {'office_environment': 1}},
                {'text': 'பலருடன் பழகும் அல்லது சந்திக்கும் இடம்', 'signals': {'high_people_environment': 1}},
                {'text': 'வெவ்வேறு இடங்கள் (களப்பணி, தள வருகைகள்)', 'signals': {'field_environment': 1}},
                {'text': 'குறிப்பிட்ட விருப்பம் இல்லை', 'signals': {'no_preference': 1}},
            ],
        },
        {
            'id': 'q3_learning',
            'prompt': 'ஒரு மாணவராக உங்களை எது சிறப்பாக விவரிக்கிறது?',
            'options': [
                {'text': 'செய்து பார்ப்பதன் மூலமே நான் சிறப்பாகக் கற்றுக்கொள்கிறேன்', 'signals': {'learning_by_doing': 1}},
                {'text': 'செயல்படுத்தும் முன் கருத்துகளைப் புரிந்து கொள்ள விரும்புகிறேன்', 'signals': {'concept_first': 1}},
                {'text': 'எதிர்பார்ப்புகள் தெளிவாக இருந்தால் படம் பிப்பது எனக்கு ஓகே', 'signals': {'rote_tolerant': 1}},
                {'text': 'தேர்வுகளை விட செயல்முறை (Projects) எனக்கு பிடிக்கும்', 'signals': {'project_based': 1}},
                {'text': 'நேரக் கட்டுப்பாட்டுடன் கூடிய தேர்வுகளில் நான் சிரமப்படுகிறேன்', 'signals': {'exam_sensitive': 1}},
            ],
        },
        {
            'id': 'q4_values',
            'prompt': 'தற்போது, உங்களுக்கு எது முக்கியம்?',
            'options': [
                {'text': 'பட்டம் பெற்ற பிறகு நிலையான வேலை', 'signals': {'stability_priority': 2}},
                {'text': 'அதிக வருமானம், ஆபத்து இருந்தாலும் பரவாயில்லை', 'signals': {'income_risk_tolerant': 2}},
                {'text': 'மேற்படிப்பு (Degree) செல்ல வாய்ப்பு', 'signals': {'pathway_priority': 2}},
                {'text': 'அர்த்தமுள்ளதாகத் தோன்றும் வேலையைச் செய்வது', 'signals': {'meaning_priority': 2}},
                {'text': 'விரைவாக படித்து முடித்து வேலைக்குச் செல்ல வேண்டும்', 'signals': {'fast_employment_priority': 2}},
            ],
        },
        {
            'id': 'q5_energy',
            'prompt': 'ஒரு முழு நாளுக்குப் பிறகு, எது உங்களை வழக்கமாக அதிகம் சோர்வடையச் செய்கிறது?',
            'options': [
                {'text': 'பலருடன் கையாள்வது', 'signals': {'low_people_tolerance': 1}},
                {'text': 'தொழில்நுட்ப அல்லது நுணுக்கமான வேலையில் கவனம் செலுத்துவது', 'signals': {'mental_fatigue_sensitive': 1}},
                {'text': 'உடல் உழைப்பு அல்லது கடினமான வேலை', 'signals': {'physical_fatigue_sensitive': 1}},
                {'text': 'நேர நெருக்கடியில் இருப்பது', 'signals': {'time_pressure_sensitive': 1}},
                {'text': 'குறிப்பிட்ட எதுவும் இல்லை', 'signals': {}},
            ],
        },
        {
            'id': 'q6_survival',
            'prompt': 'இவற்றில் எது உங்கள் கல்வியைத் தொடர்வதை எளிதாக்கும்?',
            'options': [
                {'text': 'மாதாந்திர உதவித்தொகை (Pocket money) பெறுவது', 'signals': {'allowance_priority': 3}},
                {'text': 'வீடு மற்றும் குடும்பத்திற்கு மிக அருகில் இருப்பது', 'signals': {'proximity_priority': 3}},
                {'text': 'பட்டம் பெற்ற பிறகு உத்தரவாதமான வேலை நேர்காணல்', 'signals': {'employment_guarantee': 2}},
                {'text': 'குறிப்பிட்ட விருப்பம் இல்லை', 'signals': {}},
            ],
        },
    ],
}

# Valid question IDs (for input validation)
QUESTION_IDS = ['q1_modality', 'q2_environment', 'q3_learning', 'q4_values', 'q5_energy', 'q6_survival']

# Supported languages
SUPPORTED_LANGUAGES = ['en', 'bm', 'ta']


def get_quiz_questions(lang: str = 'en') -> list[dict]:
    """Return quiz questions for the given language. Defaults to English."""
    return QUIZ_QUESTIONS.get(lang, QUIZ_QUESTIONS['en'])
