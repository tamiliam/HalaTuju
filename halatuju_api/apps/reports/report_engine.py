"""
AI report generation engine for HalaTuju.

Takes structured student data + deterministic insights and generates
a narrative counselor report via Gemini.

Usage:
    from apps.reports.report_engine import generate_report

    result = generate_report(
        grades={'bm': 'A', 'math': 'B', ...},
        eligible_courses=[...],
        insights={...},
        student_signals={...},
        lang='bm',
    )
    # result = {'markdown': '...', 'model_used': 'gemini-2.5-flash'}
    # OR
    # result = {'error': 'AI service unavailable'}
"""
import logging
import time

from django.conf import settings

from .prompts import get_prompt

logger = logging.getLogger(__name__)

# Gemini model cascade — try in order until one succeeds
MODEL_CASCADE = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.0-flash',
]

# SPM subject display names for prompt formatting
# Keys MUST match engine keys (lowercase) — same as subjects.ts ids
SUBJECT_LABELS = {
    'bm': 'Bahasa Melayu',
    'eng': 'Bahasa Inggeris',
    'math': 'Matematik',
    'sci': 'Sains',
    'hist': 'Sejarah',
    'addmath': 'Matematik Tambahan',
    'phy': 'Fizik',
    'chem': 'Kimia',
    'bio': 'Biologi',
    'poa': 'Prinsip Perakaunan',
    'ekonomi': 'Ekonomi',
    'business': 'Perniagaan',
    'geo': 'Geografi',
    'moral': 'Pendidikan Moral',
    'islam': 'Pendidikan Islam',
    'psv': 'Pendidikan Seni Visual',
    'music': 'Pendidikan Muzik',
    'sports_sci': 'Sains Sukan',
    'comp_sci': 'Sains Komputer',
    'lit_bm': 'Kesusasteraan Melayu',
    'tasawwur_islam': 'Tasawwur Islam',
    'pertanian': 'Pertanian',
    'srt': 'Sains Rumah Tangga',
    'addsci': 'Sains Tambahan',
    'b_cina': 'Bahasa Cina',
    'b_tamil': 'Bahasa Tamil',
    'keusahawanan': 'Keusahawanan',
    'lukisan': 'Lukisan',
    'eng_civil': 'Kejuruteraan Awam',
    'eng_mech': 'Kejuruteraan Mekanikal',
    'eng_elec': 'Kejuruteraan Elektrik',
    'eng_draw': 'Lukisan Kejuruteraan',
    'gkt': 'Grafik Komunikasi Teknikal',
    'multimedia': 'Multimedia',
    'reka_cipta': 'Reka Cipta',
}


# STPM subject display names for prompt formatting
STPM_SUBJECT_LABELS = {
    'PA': 'Pengajian Am',
    'MATH_T': 'Matematik T',
    'MATH_M': 'Matematik M',
    'PHYSICS': 'Fizik',
    'CHEMISTRY': 'Kimia',
    'BIOLOGY': 'Biologi',
    'ECONOMICS': 'Ekonomi',
    'ACCOUNTING': 'Perakaunan',
    'BUSINESS': 'Perniagaan',
    'BAHASA_MELAYU': 'Bahasa Melayu',
    'BAHASA_CINA': 'Bahasa Cina',
    'BAHASA_TAMIL': 'Bahasa Tamil',
    'BAHASA_ARAB': 'Bahasa Arab',
    'SEJARAH': 'Sejarah',
    'GEOGRAFI': 'Geografi',
    'KESUSASTERAAN_MELAYU': 'Kesusasteraan Melayu',
    'LITERATURE_IN_ENGLISH': 'Literature in English',
    'SENI_VISUAL': 'Seni Visual',
    'SAINS_SUKAN': 'Sains Sukan',
    'ICT': 'ICT',
    'SYARIAH': 'Syariah',
    'USULUDDIN': 'Usuluddin',
    'TAHFIZ_AL_QURAN': 'Tahfiz Al-Quran',
}


SIGNAL_LABELS = {
    'field_mechanical': ('Mekanikal & Automotif', 'Mechanical & Automotive'),
    'field_digital': ('Teknologi Digital', 'Digital Technology'),
    'field_business': ('Perniagaan & Pengurusan', 'Business & Management'),
    'field_health': ('Kesihatan & Perubatan', 'Health & Medical'),
    'field_creative': ('Seni & Kreatif', 'Arts & Creative'),
    'field_hospitality': ('Hospitaliti & Pelancongan', 'Hospitality & Tourism'),
    'field_agriculture': ('Pertanian & Alam Sekitar', 'Agriculture & Environment'),
    'field_heavy_industry': ('Industri Berat', 'Heavy Industry'),
    'field_electrical': ('Elektrik & Elektronik', 'Electrical & Electronics'),
    'field_civil': ('Kejuruteraan Awam', 'Civil Engineering'),
    'field_aero_marine': ('Aero & Marin', 'Aerospace & Marine'),
    'field_oil_gas': ('Minyak & Gas', 'Oil & Gas'),
    'hands_on': ('Kerja Amali', 'Hands-on Work'),
    'problem_solving': ('Penyelesaian Masalah', 'Problem Solving'),
    'people_helping': ('Bantu Orang', 'Helping People'),
    'creative': ('Kreatif', 'Creative'),
    'workshop_environment': ('Persekitaran Bengkel', 'Workshop Environment'),
    'office_environment': ('Persekitaran Pejabat', 'Office Environment'),
    'high_people_environment': ('Ramai Orang', 'High People Environment'),
    'field_environment': ('Kerja Luar', 'Fieldwork'),
    'high_stamina': ('Stamina Tinggi', 'High Stamina'),
    'mental_fatigue_sensitive': ('Sensitif Penat Mental', 'Mentally Sensitive'),
    'physical_fatigue_sensitive': ('Sensitif Penat Fizikal', 'Physically Sensitive'),
    'low_people_tolerance': ('Kurang Selesa Ramai Orang', 'Low People Tolerance'),
    'learning_by_doing': ('Belajar Sambil Buat', 'Learning by Doing'),
    'concept_first': ('Konsep Dahulu', 'Concept First'),
    'rote_tolerant': ('Boleh Hafal', 'Rote Tolerant'),
    'project_based': ('Berasaskan Projek', 'Project-based'),
    'stability_priority': ('Keutamaan Kestabilan', 'Stability Priority'),
    'quality_priority': ('Keutamaan Kualiti', 'Quality Priority'),
    'fast_employment_priority': ('Nak Kerja Cepat', 'Fast Employment'),
    'income_risk_tolerant': ('Sanggup Risiko Gaji', 'Income Risk Tolerant'),
    'pathway_priority': ('Laluan Kerjaya', 'Career Pathway'),
    'proximity_priority': ('Dekat Rumah', 'Proximity'),
    'allowance_priority': ('Elaun Penting', 'Allowance Priority'),
    'employment_guarantee': ('Jaminan Kerja', 'Employment Guarantee'),
}

STRENGTH_LABELS = {
    'bm': {2: 'kuat', 1: 'sederhana'},
    'en': {2: 'strong', 1: 'moderate'},
}


def _format_stpm_grades(stpm_grades, cgpa=None, muet_band=None):
    """Format STPM grades + CGPA + MUET for the prompt."""
    if not stpm_grades and cgpa is None:
        return 'Tiada maklumat gred STPM.'

    lines = []
    for subj, grade in (stpm_grades or {}).items():
        label = STPM_SUBJECT_LABELS.get(subj, subj)
        lines.append(f'- {label}: {grade}')

    if cgpa is not None:
        lines.append(f'- CGPA: {cgpa}')
    if muet_band is not None:
        lines.append(f'- MUET: Band {muet_band}')

    return '\n'.join(lines) if lines else 'Tiada maklumat gred STPM.'


def _format_grades(grades):
    """Format SPM grades into a readable string for the prompt."""
    if not grades:
        return 'Tiada maklumat gred.'

    lines = []
    for subj, grade in grades.items():
        label = SUBJECT_LABELS.get(subj, subj.upper())
        lines.append(f'- {label}: {grade}')
    return '\n'.join(lines)


def _format_signals(student_signals, lang='bm'):
    """Format quiz signals into human-readable personality summary."""
    if not student_signals:
        return 'Tiada maklumat kecenderungan (kuiz belum diambil).' if lang == 'bm' \
            else 'No inclination data (quiz not taken).'

    lang_idx = 0 if lang == 'bm' else 1
    strength = STRENGTH_LABELS.get(lang, STRENGTH_LABELS['bm'])
    lines = []

    for category, sig_dict in student_signals.items():
        if not isinstance(sig_dict, dict):
            continue
        for key, score in sig_dict.items():
            if not score or score <= 0:
                continue
            label_pair = SIGNAL_LABELS.get(key)
            label = label_pair[lang_idx] if label_pair else key
            level = strength.get(2, 'kuat') if score >= 2 else strength.get(1, 'sederhana')
            lines.append(f'- {label} ({level})')

    if not lines:
        return 'Tiada kecenderungan dominan dikesan.' if lang == 'bm' \
            else 'No dominant inclinations detected.'

    header = 'Kecenderungan pelajar:' if lang == 'bm' else 'Student inclinations:'
    return header + '\n' + '\n'.join(lines)


def _format_courses(eligible_courses, limit=5):
    """Format top courses for the prompt, sorted by fit_score descending."""
    if not eligible_courses:
        return 'Tiada kursus layak.'

    sorted_courses = sorted(
        eligible_courses,
        key=lambda c: c.get('fit_score', 0),
        reverse=True,
    )

    lines = []
    for i, c in enumerate(sorted_courses[:limit]):
        name = c.get('course_name', c.get('course_id', '?'))
        field = c.get('field_display', c.get('field', ''))
        source = c.get('source_type', '')
        merit = c.get('merit_label', '')
        fit = c.get('fit_score')
        line = f'{i + 1}. {name}'
        if field:
            line += f' (Bidang: {field})'
        if source:
            line += f' [{source.upper()}]'
        if merit:
            line += f' — Peluang: {merit}'
        if fit is not None:
            line += f' [Skor Kesesuaian: {fit}]'
        lines.append(line)
    return '\n'.join(lines)


def _format_insights(insights):
    """Format deterministic insights into a summary string for the prompt."""
    if not insights:
        return ''

    parts = []

    summary = insights.get('summary_text', '')
    if summary:
        parts.append(summary)

    merit = insights.get('merit_summary', {})
    if merit:
        parts.append(
            f'Merit: {merit.get("high", 0)} tinggi, '
            f'{merit.get("fair", 0)} sederhana, '
            f'{merit.get("low", 0)} rendah'
        )

    top_fields = insights.get('top_fields', [])
    if top_fields:
        field_names = ', '.join(f['field'] for f in top_fields[:3])
        parts.append(f'Bidang utama: {field_names}')

    return '\n'.join(parts)


def generate_report(grades, eligible_courses, insights,
                    student_signals=None, student_name='pelajar',
                    lang='bm'):
    """
    Generate an AI counselor report using Gemini.

    Args:
        grades: dict of SPM grades {'bm': 'A', 'math': 'B', ...}
        eligible_courses: list of eligible course dicts
        insights: dict from generate_insights()
        student_signals: optional quiz signals dict
        student_name: student display name (default 'pelajar')
        lang: 'bm' or 'en'

    Returns:
        dict with either:
            {'markdown': '...', 'model_used': '...'}
        or:
            {'error': '...'}
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        logger.warning('GEMINI_API_KEY not configured')
        return {'error': 'AI service not configured (missing API key)'}

    try:
        from google import genai
    except ImportError:
        logger.error('google-genai not installed')
        return {'error': 'AI module not installed'}

    client = genai.Client(api_key=api_key)

    # Format data for prompt
    academic_context = _format_grades(grades)
    student_profile = _format_signals(student_signals, lang=lang)
    recommended_courses = _format_courses(eligible_courses)
    insights_summary = _format_insights(insights)

    prompt_template = get_prompt(lang)

    # Try models in cascade
    last_error = None
    for model_name in MODEL_CASCADE:
        try:
            full_prompt = prompt_template.format(
                student_name=student_name,
                student_profile=student_profile,
                academic_context=academic_context,
                recommended_courses=recommended_courses,
                insights_summary=insights_summary,
            )
        except (KeyError, IndexError) as e:
            logger.error(f'Prompt formatting error: {e}')
            last_error = str(e)
            continue

        try:
            start_ms = time.time()
            response = client.models.generate_content(
                model=model_name, contents=full_prompt
            )
            elapsed_ms = int((time.time() - start_ms) * 1000)

            text = response.text
            logger.info(
                f'Report generated with {model_name} in {elapsed_ms}ms '
                f'({len(text)} chars)'
            )

            return {
                'markdown': text,
                'model_used': model_name,
                'generation_time_ms': elapsed_ms,
            }

        except Exception as e:
            last_error = str(e)
            logger.warning(f'Generation failed with {model_name}: {e}')
            continue

    logger.error(f'All Gemini models failed. Last error: {last_error}')
    return {'error': f'All AI models failed: {last_error}'}
