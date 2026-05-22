"""
AI sponsor-profile drafting for the B40 Assistance Programme.

Builds a sponsor-ready narrative from an application's intake + deeper info +
funding need + grades + referee, via the Gemini model cascade (same pattern as
apps/reports/report_engine). Mocked in tests; degrades gracefully to an error
dict when the AI is unavailable.
"""
import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)

MODEL_CASCADE = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash']

PROFILE_PROMPT = """You are writing a confidential, sponsor-ready profile for a B40 student \
applying for education financial assistance in Malaysia. Write in clear British English — \
factual, warm, and concise (~300-400 words) — in Markdown with these sections: Background, \
Academic record, Pathway plan, Funding need, Why support matters. Use ONLY the information \
given below; do not invent facts. Where information is missing, say so briefly rather than \
guessing.

Student: {name}
School: {school}
Qualification: {qualification}
SPM A-count: {spm_a_count}    STPM PNGK: {stpm_pngk}
Household income (RM/month): {household_income}    Household size: {household_size}
Receives STR: {receives_str}    Receives JKM: {receives_jkm}
Intended pathway: {intended_pathway}

Aspirations: {aspirations}
Study plans: {plans}
Concerns/fears: {fears}
Why assistance is needed: {justification}

Funding need: {funding}
Referee(s): {referees}
"""


def _build_prompt(application):
    profile = application.profile
    try:
        fn = application.funding_need
        funding = f'RM{fn.total} total'
    except Exception:
        funding = 'not provided'
    referees = ', '.join(
        f'{r.name} ({r.role})' if r.role else r.name
        for r in application.referees.all()
    ) or 'none provided'

    def val(v, fallback='not provided'):
        return v if v not in (None, '') else fallback

    return PROFILE_PROMPT.format(
        name=val(getattr(profile, 'name', '') if profile else '', 'the applicant'),
        school=val(getattr(profile, 'school', '') if profile else ''),
        qualification=application.qualification.upper(),
        spm_a_count=val(application.spm_a_count, 'n/a'),
        stpm_pngk=val(application.stpm_pngk, 'n/a'),
        household_income=val(application.household_income),
        household_size=val(application.household_size),
        receives_str='yes' if application.receives_str else 'no',
        receives_jkm='yes' if application.receives_jkm else 'no',
        intended_pathway=val(application.intended_pathway, 'not specified'),
        aspirations=val(application.aspirations),
        plans=val(application.plans),
        fears=val(application.fears),
        justification=val(application.justification),
        funding=funding,
        referees=referees,
    )


def generate_sponsor_profile(application):
    """Return {'markdown', 'model_used', ...} or {'error': ...}."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        return {'error': 'AI service not configured (missing API key)'}
    try:
        from google import genai
    except ImportError:
        return {'error': 'AI module not installed'}

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(application)
    last_error = None
    for model_name in MODEL_CASCADE:
        try:
            start = time.time()
            response = client.models.generate_content(model=model_name, contents=prompt)
            elapsed = int((time.time() - start) * 1000)
            return {'markdown': response.text, 'model_used': model_name, 'generation_time_ms': elapsed}
        except Exception as e:
            last_error = str(e)
            logger.warning('Profile generation failed with %s: %s', model_name, e)
            continue
    return {'error': f'All AI models failed: {last_error}'}
