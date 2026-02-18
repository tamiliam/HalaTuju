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
    # result = {'markdown': '...', 'model_used': 'gemini-2.5-flash', 'counsellor_name': 'Cikgu Gopal'}
    # OR
    # result = {'error': 'AI service unavailable'}
"""
import json
import logging
import time

from django.conf import settings

from .prompts import get_prompt, get_persona_for_model

logger = logging.getLogger(__name__)

# Gemini model cascade — try in order until one succeeds
MODEL_CASCADE = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.0-flash',
]

# SPM subject display names for prompt formatting
SUBJECT_LABELS = {
    'bm': 'Bahasa Melayu',
    'eng': 'Bahasa Inggeris',
    'math': 'Matematik',
    'sc': 'Sains',
    'hist': 'Sejarah',
    'add_math': 'Matematik Tambahan',
    'phys': 'Fizik',
    'chem': 'Kimia',
    'bio': 'Biologi',
    'acc': 'Prinsip Perakaunan',
    'econ': 'Ekonomi',
    'perdagangan': 'Perdagangan',
    'ict': 'ICT',
    'moral': 'Pendidikan Moral',
    'pi': 'Pendidikan Islam',
    'geo': 'Geografi',
    'tasawwur': 'Tasawwur Islam',
    'bible_knowledge': 'Pengetahuan Bible',
    'lang3': 'Bahasa Ketiga',
    'art': 'Pendidikan Seni Visual',
    'music': 'Pendidikan Muzik',
    'rbt': 'Reka Bentuk & Teknologi',
    'sains_sukan': 'Sains Sukan',
    'kesusasteraan': 'Kesusasteraan Melayu',
}


def _format_grades(grades):
    """Format SPM grades into a readable string for the prompt."""
    if not grades:
        return 'Tiada maklumat gred.'

    lines = []
    for subj, grade in grades.items():
        label = SUBJECT_LABELS.get(subj, subj.upper())
        lines.append(f'- {label}: {grade}')
    return '\n'.join(lines)


def _format_signals(student_signals):
    """Format quiz signals into a personality summary string."""
    if not student_signals:
        return 'Tiada maklumat kecenderungan (kuiz belum diambil).'

    dominant = {}
    for category, sig_dict in student_signals.items():
        if isinstance(sig_dict, dict):
            for k, v in sig_dict.items():
                if v and v > 0:
                    dominant[k] = v

    if not dominant:
        return 'Tiada kecenderungan dominan dikesan.'

    return f'Kecenderungan: {json.dumps(dominant, ensure_ascii=False)}'


def _format_courses(eligible_courses, limit=3):
    """Format top courses for the prompt."""
    if not eligible_courses:
        return 'Tiada kursus layak.'

    lines = []
    for i, c in enumerate(eligible_courses[:limit]):
        name = c.get('course_name', c.get('course_id', '?'))
        field = c.get('field', '')
        source = c.get('source_type', '')
        merit = c.get('merit_label', '')
        line = f'{i + 1}. {name}'
        if field:
            line += f' (Bidang: {field})'
        if source:
            line += f' [{source.upper()}]'
        if merit:
            line += f' — Peluang: {merit}'
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
            {'markdown': '...', 'model_used': '...', 'counsellor_name': '...'}
        or:
            {'error': '...'}
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        logger.warning('GEMINI_API_KEY not configured')
        return {'error': 'AI service not configured (missing API key)'}

    try:
        import google.generativeai as genai
    except ImportError:
        logger.error('google-generativeai not installed')
        return {'error': 'AI module not installed'}

    genai.configure(api_key=api_key)

    # Format data for prompt
    academic_context = _format_grades(grades)
    student_profile = _format_signals(student_signals)
    recommended_courses = _format_courses(eligible_courses)
    insights_summary = _format_insights(insights)

    prompt_template = get_prompt(lang)

    # Try models in cascade
    last_error = None
    for model_name in MODEL_CASCADE:
        persona = get_persona_for_model(model_name)
        gender_key = 'gender_en' if lang == 'en' else 'gender'

        try:
            full_prompt = prompt_template.format(
                counsellor_name=persona['name'],
                gender_context=persona[gender_key],
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
            model = genai.GenerativeModel(model_name)
            start_ms = time.time()
            response = model.generate_content(full_prompt)
            elapsed_ms = int((time.time() - start_ms) * 1000)

            text = response.text
            logger.info(
                f'Report generated with {model_name} in {elapsed_ms}ms '
                f'({len(text)} chars)'
            )

            return {
                'markdown': text,
                'model_used': model_name,
                'counsellor_name': persona['name'],
                'generation_time_ms': elapsed_ms,
            }

        except Exception as e:
            last_error = str(e)
            logger.warning(f'Generation failed with {model_name}: {e}')
            continue

    logger.error(f'All Gemini models failed. Last error: {last_error}')
    return {'error': f'All AI models failed: {last_error}'}
