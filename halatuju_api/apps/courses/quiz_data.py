"""
Quiz question data — 8+1 questions × 3 languages (EN, BM, TA).

Each question has:
- id: stable identifier (used as key in answer submission)
- prompt: the question text
- options: list of {text, icon, signals} where signals is a dict of signal_name → weight
- select_mode / max_select: (optional) for multi-select questions
- condition: (optional) for conditional questions (e.g. Q2.5)
- not_sure: (optional) True on "Not Sure Yet" options

This is pure data — no logic, no state, no imports.
"""

QUIZ_QUESTIONS = {
    'en': [
        {
            'id': 'q1_field1',
            'prompt': 'What catches your eye?',
            'select_mode': 'multi',
            'max_select': 2,
            'options': [
                {'text': 'Build & Fix', 'icon': 'wrench_gears', 'signals': {'field_mechanical': 3}},
                {'text': 'Tech & Digital', 'icon': 'laptop_code', 'signals': {'field_digital': 3}},
                {'text': 'Business & Money', 'icon': 'handshake_chart', 'signals': {'field_business': 3}},
                {'text': 'Health & Care', 'icon': 'heart_stethoscope', 'signals': {'field_health': 3}},
                {'text': 'Not Sure Yet', 'icon': 'question_sparkle', 'not_sure': True, 'signals': {'field_mechanical': 1, 'field_digital': 1, 'field_business': 1, 'field_health': 1}},
            ],
        },
        {
            'id': 'q2_field2',
            'prompt': 'And this?',
            'select_mode': 'multi',
            'max_select': 2,
            'options': [
                {'text': 'Design & Create', 'icon': 'paintbrush_ruler', 'signals': {'field_creative': 3}},
                {'text': 'Food & Travel', 'icon': 'chef_suitcase', 'signals': {'field_hospitality': 3}},
                {'text': 'Nature & Farm', 'icon': 'leaf_tractor', 'signals': {'field_agriculture': 3}},
                {'text': 'Big Machines', 'icon': 'bolt_ship', 'signals': {'field_heavy_industry': 3}},
                {'text': 'Not Sure Yet', 'icon': 'question_sparkle', 'not_sure': True, 'signals': {'field_creative': 1, 'field_hospitality': 1, 'field_agriculture': 1, 'field_heavy_industry': 1}},
            ],
        },
        {
            'id': 'q2_5_heavy',
            'prompt': 'Which kind?',
            'condition': {'requires': 'q2_field2', 'option_signal': 'field_heavy_industry'},
            'options': [
                {'text': 'Electrical', 'icon': 'lightning_bolt', 'signals': {'field_electrical': 3}},
                {'text': 'Construction', 'icon': 'hardhat_crane', 'signals': {'field_civil': 3}},
                {'text': 'Aero & Marine', 'icon': 'airplane_ship', 'signals': {'field_aero_marine': 3}},
                {'text': 'Oil & Gas', 'icon': 'oil_rig_flame', 'signals': {'field_oil_gas': 3}},
            ],
        },
        {
            'id': 'q3_work',
            'prompt': 'Your ideal day at work',
            'options': [
                {'text': 'Hands-On', 'icon': 'hands_tools', 'signals': {'hands_on': 2}},
                {'text': 'Problem Solving', 'icon': 'brain_lightbulb', 'signals': {'problem_solving': 2}},
                {'text': 'With People', 'icon': 'people_bubbles', 'signals': {'people_helping': 2}},
                {'text': 'Creating Things', 'icon': 'pencil_star', 'signals': {'creative': 2}},
            ],
        },
        {
            'id': 'q4_environment',
            'prompt': 'Where would you work?',
            'options': [
                {'text': 'Workshop', 'icon': 'workshop_garage', 'signals': {'workshop_environment': 1}},
                {'text': 'Office', 'icon': 'desk_monitor', 'signals': {'office_environment': 1}},
                {'text': 'Outdoors', 'icon': 'trees_sun', 'signals': {'field_environment': 1}},
                {'text': 'With Crowds', 'icon': 'building_people', 'signals': {'high_people_environment': 1}},
                {'text': 'Not Sure Yet', 'icon': 'question_sparkle', 'not_sure': True, 'signals': {}},
            ],
        },
        {
            'id': 'q5_learning',
            'prompt': 'How do you learn best?',
            'options': [
                {'text': 'Do & Practise', 'icon': 'hammer_check', 'signals': {'learning_by_doing': 1}},
                {'text': 'Read & Understand', 'icon': 'book_magnifier', 'signals': {'concept_first': 1}},
                {'text': 'Projects & Teamwork', 'icon': 'clipboard_group', 'signals': {'project_based': 1}},
                {'text': 'Drill & Memorise', 'icon': 'loop_arrows', 'signals': {'rote_tolerant': 1}},
            ],
        },
        {
            'id': 'q6_values',
            'prompt': 'After SPM, what matters most?',
            'options': [
                {'text': 'Stable Job', 'icon': 'shield_check', 'signals': {'stability_priority': 2}},
                {'text': 'Good Pay', 'icon': 'money_rocket', 'signals': {'income_risk_tolerant': 2}},
                {'text': 'Continue Degree', 'icon': 'gradcap_arrow', 'signals': {'pathway_priority': 2}},
                {'text': 'Work Fast', 'icon': 'lightning_briefcase', 'signals': {'fast_employment_priority': 2}},
            ],
        },
        {
            'id': 'q7_energy',
            'prompt': 'What tires you out?',
            'options': [
                {'text': 'Too Many People', 'icon': 'crowd_sweat', 'signals': {'low_people_tolerance': 1}},
                {'text': 'Heavy Thinking', 'icon': 'brain_weight', 'signals': {'mental_fatigue_sensitive': 1}},
                {'text': 'Physical Work', 'icon': 'arm_weight', 'signals': {'physical_fatigue_sensitive': 1}},
                {'text': 'I Can Handle Anything', 'icon': 'flexed_arm_star', 'signals': {'high_stamina': 1}},
            ],
        },
        {
            'id': 'q8_practical',
            'prompt': 'What would help you keep studying?',
            'options': [
                {'text': 'Pocket Money', 'icon': 'wallet_coins', 'signals': {'allowance_priority': 3}},
                {'text': 'Near Home', 'icon': 'house_heart', 'signals': {'proximity_priority': 3}},
                {'text': 'Job Guarantee', 'icon': 'handshake_door', 'signals': {'employment_guarantee': 2}},
                {'text': 'Best Programme', 'icon': 'trophy_star', 'signals': {'quality_priority': 1}},
            ],
        },
    ],
    'bm': [
        {
            'id': 'q1_field1',
            'prompt': 'Apa yang menarik perhatian anda?',
            'select_mode': 'multi',
            'max_select': 2,
            'options': [
                {'text': 'Bina & Baiki', 'icon': 'wrench_gears', 'signals': {'field_mechanical': 3}},
                {'text': 'Teknologi & Digital', 'icon': 'laptop_code', 'signals': {'field_digital': 3}},
                {'text': 'Perniagaan & Wang', 'icon': 'handshake_chart', 'signals': {'field_business': 3}},
                {'text': 'Kesihatan & Penjagaan', 'icon': 'heart_stethoscope', 'signals': {'field_health': 3}},
                {'text': 'Belum Pasti', 'icon': 'question_sparkle', 'not_sure': True, 'signals': {'field_mechanical': 1, 'field_digital': 1, 'field_business': 1, 'field_health': 1}},
            ],
        },
        {
            'id': 'q2_field2',
            'prompt': 'Dan ini?',
            'select_mode': 'multi',
            'max_select': 2,
            'options': [
                {'text': 'Reka & Cipta', 'icon': 'paintbrush_ruler', 'signals': {'field_creative': 3}},
                {'text': 'Makanan & Pelancongan', 'icon': 'chef_suitcase', 'signals': {'field_hospitality': 3}},
                {'text': 'Alam & Pertanian', 'icon': 'leaf_tractor', 'signals': {'field_agriculture': 3}},
                {'text': 'Mesin Besar', 'icon': 'bolt_ship', 'signals': {'field_heavy_industry': 3}},
                {'text': 'Belum Pasti', 'icon': 'question_sparkle', 'not_sure': True, 'signals': {'field_creative': 1, 'field_hospitality': 1, 'field_agriculture': 1, 'field_heavy_industry': 1}},
            ],
        },
        {
            'id': 'q2_5_heavy',
            'prompt': 'Jenis yang mana?',
            'condition': {'requires': 'q2_field2', 'option_signal': 'field_heavy_industry'},
            'options': [
                {'text': 'Elektrikal', 'icon': 'lightning_bolt', 'signals': {'field_electrical': 3}},
                {'text': 'Pembinaan', 'icon': 'hardhat_crane', 'signals': {'field_civil': 3}},
                {'text': 'Aero & Marin', 'icon': 'airplane_ship', 'signals': {'field_aero_marine': 3}},
                {'text': 'Minyak & Gas', 'icon': 'oil_rig_flame', 'signals': {'field_oil_gas': 3}},
            ],
        },
        {
            'id': 'q3_work',
            'prompt': 'Hari ideal anda bekerja',
            'options': [
                {'text': 'Kerja Tangan', 'icon': 'hands_tools', 'signals': {'hands_on': 2}},
                {'text': 'Selesai Masalah', 'icon': 'brain_lightbulb', 'signals': {'problem_solving': 2}},
                {'text': 'Bersama Orang', 'icon': 'people_bubbles', 'signals': {'people_helping': 2}},
                {'text': 'Mencipta Sesuatu', 'icon': 'pencil_star', 'signals': {'creative': 2}},
            ],
        },
        {
            'id': 'q4_environment',
            'prompt': 'Di mana anda mahu bekerja?',
            'options': [
                {'text': 'Bengkel', 'icon': 'workshop_garage', 'signals': {'workshop_environment': 1}},
                {'text': 'Pejabat', 'icon': 'desk_monitor', 'signals': {'office_environment': 1}},
                {'text': 'Luar', 'icon': 'trees_sun', 'signals': {'field_environment': 1}},
                {'text': 'Ramai Orang', 'icon': 'building_people', 'signals': {'high_people_environment': 1}},
                {'text': 'Belum Pasti', 'icon': 'question_sparkle', 'not_sure': True, 'signals': {}},
            ],
        },
        {
            'id': 'q5_learning',
            'prompt': 'Bagaimana anda belajar terbaik?',
            'options': [
                {'text': 'Buat & Praktik', 'icon': 'hammer_check', 'signals': {'learning_by_doing': 1}},
                {'text': 'Baca & Faham', 'icon': 'book_magnifier', 'signals': {'concept_first': 1}},
                {'text': 'Projek & Kerja Pasukan', 'icon': 'clipboard_group', 'signals': {'project_based': 1}},
                {'text': 'Latih & Hafal', 'icon': 'loop_arrows', 'signals': {'rote_tolerant': 1}},
            ],
        },
        {
            'id': 'q6_values',
            'prompt': 'Selepas SPM, apa yang paling penting?',
            'options': [
                {'text': 'Kerja Stabil', 'icon': 'shield_check', 'signals': {'stability_priority': 2}},
                {'text': 'Gaji Baik', 'icon': 'money_rocket', 'signals': {'income_risk_tolerant': 2}},
                {'text': 'Sambung Ijazah', 'icon': 'gradcap_arrow', 'signals': {'pathway_priority': 2}},
                {'text': 'Kerja Cepat', 'icon': 'lightning_briefcase', 'signals': {'fast_employment_priority': 2}},
            ],
        },
        {
            'id': 'q7_energy',
            'prompt': 'Apa yang meletihkan anda?',
            'options': [
                {'text': 'Terlalu Ramai Orang', 'icon': 'crowd_sweat', 'signals': {'low_people_tolerance': 1}},
                {'text': 'Banyak Berfikir', 'icon': 'brain_weight', 'signals': {'mental_fatigue_sensitive': 1}},
                {'text': 'Kerja Fizikal', 'icon': 'arm_weight', 'signals': {'physical_fatigue_sensitive': 1}},
                {'text': 'Saya Boleh Tahan Semua', 'icon': 'flexed_arm_star', 'signals': {'high_stamina': 1}},
            ],
        },
        {
            'id': 'q8_practical',
            'prompt': 'Apa yang membantu anda terus belajar?',
            'options': [
                {'text': 'Duit Poket', 'icon': 'wallet_coins', 'signals': {'allowance_priority': 3}},
                {'text': 'Dekat Rumah', 'icon': 'house_heart', 'signals': {'proximity_priority': 3}},
                {'text': 'Jaminan Kerja', 'icon': 'handshake_door', 'signals': {'employment_guarantee': 2}},
                {'text': 'Program Terbaik', 'icon': 'trophy_star', 'signals': {'quality_priority': 1}},
            ],
        },
    ],
    'ta': [
        {
            'id': 'q1_field1',
            'prompt': 'உங்கள் கவனத்தை ஈர்ப்பது எது?',
            'select_mode': 'multi',
            'max_select': 2,
            'options': [
                {'text': 'உருவாக்கு & சரிசெய்', 'icon': 'wrench_gears', 'signals': {'field_mechanical': 3}},
                {'text': 'தொழில்நுட்பம் & டிஜிட்டல்', 'icon': 'laptop_code', 'signals': {'field_digital': 3}},
                {'text': 'வணிகம் & பணம்', 'icon': 'handshake_chart', 'signals': {'field_business': 3}},
                {'text': 'சுகாதாரம் & பராமரிப்பு', 'icon': 'heart_stethoscope', 'signals': {'field_health': 3}},
                {'text': 'இன்னும் தெரியவில்லை', 'icon': 'question_sparkle', 'not_sure': True, 'signals': {'field_mechanical': 1, 'field_digital': 1, 'field_business': 1, 'field_health': 1}},
            ],
        },
        {
            'id': 'q2_field2',
            'prompt': 'இதுவும்?',
            'select_mode': 'multi',
            'max_select': 2,
            'options': [
                {'text': 'வடிவமைப்பு & படைப்பு', 'icon': 'paintbrush_ruler', 'signals': {'field_creative': 3}},
                {'text': 'உணவு & சுற்றுலா', 'icon': 'chef_suitcase', 'signals': {'field_hospitality': 3}},
                {'text': 'இயற்கை & விவசாயம்', 'icon': 'leaf_tractor', 'signals': {'field_agriculture': 3}},
                {'text': 'பெரிய இயந்திரங்கள்', 'icon': 'bolt_ship', 'signals': {'field_heavy_industry': 3}},
                {'text': 'இன்னும் தெரியவில்லை', 'icon': 'question_sparkle', 'not_sure': True, 'signals': {'field_creative': 1, 'field_hospitality': 1, 'field_agriculture': 1, 'field_heavy_industry': 1}},
            ],
        },
        {
            'id': 'q2_5_heavy',
            'prompt': 'எந்த வகை?',
            'condition': {'requires': 'q2_field2', 'option_signal': 'field_heavy_industry'},
            'options': [
                {'text': 'மின்சாரம்', 'icon': 'lightning_bolt', 'signals': {'field_electrical': 3}},
                {'text': 'கட்டுமானம்', 'icon': 'hardhat_crane', 'signals': {'field_civil': 3}},
                {'text': 'விமானம் & கப்பல்', 'icon': 'airplane_ship', 'signals': {'field_aero_marine': 3}},
                {'text': 'எண்ணெய் & எரிவாயு', 'icon': 'oil_rig_flame', 'signals': {'field_oil_gas': 3}},
            ],
        },
        {
            'id': 'q3_work',
            'prompt': 'உங்கள் சிறந்த வேலை நாள்',
            'options': [
                {'text': 'கைவேலை', 'icon': 'hands_tools', 'signals': {'hands_on': 2}},
                {'text': 'சிக்கல் தீர்ப்பு', 'icon': 'brain_lightbulb', 'signals': {'problem_solving': 2}},
                {'text': 'மக்களுடன்', 'icon': 'people_bubbles', 'signals': {'people_helping': 2}},
                {'text': 'படைப்பாற்றல்', 'icon': 'pencil_star', 'signals': {'creative': 2}},
            ],
        },
        {
            'id': 'q4_environment',
            'prompt': 'எங்கே வேலை செய்வீர்கள்?',
            'options': [
                {'text': 'பட்டறை', 'icon': 'workshop_garage', 'signals': {'workshop_environment': 1}},
                {'text': 'அலுவலகம்', 'icon': 'desk_monitor', 'signals': {'office_environment': 1}},
                {'text': 'வெளியே', 'icon': 'trees_sun', 'signals': {'field_environment': 1}},
                {'text': 'கூட்டத்துடன்', 'icon': 'building_people', 'signals': {'high_people_environment': 1}},
                {'text': 'இன்னும் தெரியவில்லை', 'icon': 'question_sparkle', 'not_sure': True, 'signals': {}},
            ],
        },
        {
            'id': 'q5_learning',
            'prompt': 'எப்படி கற்றுக்கொள்வீர்கள்?',
            'options': [
                {'text': 'செய்து பழகு', 'icon': 'hammer_check', 'signals': {'learning_by_doing': 1}},
                {'text': 'படித்து புரிந்துகொள்', 'icon': 'book_magnifier', 'signals': {'concept_first': 1}},
                {'text': 'திட்டம் & குழுப்பணி', 'icon': 'clipboard_group', 'signals': {'project_based': 1}},
                {'text': 'பயிற்சி & மனப்பாடம்', 'icon': 'loop_arrows', 'signals': {'rote_tolerant': 1}},
            ],
        },
        {
            'id': 'q6_values',
            'prompt': 'SPM பிறகு, எது முக்கியம்?',
            'options': [
                {'text': 'நிலையான வேலை', 'icon': 'shield_check', 'signals': {'stability_priority': 2}},
                {'text': 'நல்ல சம்பளம்', 'icon': 'money_rocket', 'signals': {'income_risk_tolerant': 2}},
                {'text': 'பட்டப்படிப்பு தொடர', 'icon': 'gradcap_arrow', 'signals': {'pathway_priority': 2}},
                {'text': 'விரைவாக வேலை', 'icon': 'lightning_briefcase', 'signals': {'fast_employment_priority': 2}},
            ],
        },
        {
            'id': 'q7_energy',
            'prompt': 'எது உங்களை சோர்வடையச் செய்கிறது?',
            'options': [
                {'text': 'அதிக மக்கள்', 'icon': 'crowd_sweat', 'signals': {'low_people_tolerance': 1}},
                {'text': 'அதிக சிந்தனை', 'icon': 'brain_weight', 'signals': {'mental_fatigue_sensitive': 1}},
                {'text': 'உடல் உழைப்பு', 'icon': 'arm_weight', 'signals': {'physical_fatigue_sensitive': 1}},
                {'text': 'எதையும் தாங்குவேன்', 'icon': 'flexed_arm_star', 'signals': {'high_stamina': 1}},
            ],
        },
        {
            'id': 'q8_practical',
            'prompt': 'படிப்பைத் தொடர எது உதவும்?',
            'options': [
                {'text': 'பாக்கெட் மணி', 'icon': 'wallet_coins', 'signals': {'allowance_priority': 3}},
                {'text': 'வீட்டுக்கு அருகில்', 'icon': 'house_heart', 'signals': {'proximity_priority': 3}},
                {'text': 'வேலை உத்தரவாதம்', 'icon': 'handshake_door', 'signals': {'employment_guarantee': 2}},
                {'text': 'சிறந்த திட்டம்', 'icon': 'trophy_star', 'signals': {'quality_priority': 1}},
            ],
        },
    ],
}

# Valid question IDs (for input validation)
QUESTION_IDS = [
    'q1_field1', 'q2_field2', 'q2_5_heavy',
    'q3_work', 'q4_environment', 'q5_learning',
    'q6_values', 'q7_energy', 'q8_practical',
]

# Supported languages
SUPPORTED_LANGUAGES = ['en', 'bm', 'ta']


def get_quiz_questions(lang: str = 'en') -> list[dict]:
    """Return quiz questions for the given language. Defaults to English."""
    return QUIZ_QUESTIONS.get(lang, QUIZ_QUESTIONS['en'])
