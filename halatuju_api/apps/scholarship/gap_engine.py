"""Phase B — Gemini interview gap-spotter.

Admin-on-demand: reads the applicant's TYPED narrative (their own words) and
suggests 3-6 interview questions ("gaps") a sponsor interviewer should probe —
the contextual / story-arc things the deterministic anomaly engine can't see.
Each gap carries its own dynamic text {code, question, why}; the code is a stable
slug so a finding-verdict can attach (InterviewSession.findings).

Reuses profile_engine's language + context helpers and vision's structured-output
Gemini seam (so both engines share one mockable call path). Soft, never blocks.
"""
import logging
import re

from .profile_engine import (
    DEFAULT_LANGUAGE, _funding, _pathway, _resolve_language,
    _siblings_studying_display, _yesno,
)

logger = logging.getLogger(__name__)

GAP_SCHEMA = {
    'type': 'object',
    'properties': {
        'gaps': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'code': {'type': 'string'},
                    'question': {'type': 'string'},
                    'why': {'type': 'string'},
                },
                'required': ['question', 'why'],
            },
        },
    },
    'required': ['gaps'],
}

GAP_PROMPT = """You are helping an interviewer prepare to interview a shortlisted \
B40 scholarship applicant. Read the applicant's OWN WORDS and context below (the \
narrative may be in Malay, English, or Tamil) and identify 3-6 things worth probing \
in the interview — vague or unexplained plans, an unclear funding need, resilience \
or support-network signals, or quiet contradictions that automated rule checks \
cannot see. Do NOT invent facts. If the narrative is thin, return fewer gaps (even \
zero). For EACH gap return: a short snake_case "code" (a slug you invent, e.g. \
unclear_funding_plan), a "question" (the actual interview question, written in \
{target_language}), and a "why" (one short line of rationale for the interviewer, \
in {target_language}). Return JSON only.

APPLICANT CONTEXT
Pathway: {pathway}
Household income (RM/month): {household_income}; household size: {household_size}
Receives STR: {receives_str}; receives JKM: {receives_jkm}
First in family to attend tertiary: {first_in_family}; siblings studying: {siblings_studying}

APPLICANT'S OWN WORDS
Aspirations: {aspirations}
Plans: {plans}
What worries them / support they want: {fears}
Daily life: {daily_life}
Family context: {family_context}
Funding note: {funding_note}
"""


def _val(v, fallback='(not provided)'):
    return v if v not in (None, '') else fallback


def _build_gap_prompt(application, target_language=DEFAULT_LANGUAGE):
    profile = application.profile
    _cats, _months, funding_note = _funding(application)
    return GAP_PROMPT.format(
        target_language=target_language,
        pathway=_pathway(application),
        household_income=_val(getattr(profile, 'household_income', None) if profile else None),
        household_size=_val(getattr(profile, 'household_size', None) if profile else None),
        receives_str=_yesno(getattr(profile, 'receives_str', None) if profile else None),
        receives_jkm=_yesno(getattr(profile, 'receives_jkm', None) if profile else None),
        first_in_family=_yesno(application.first_in_family),
        siblings_studying=_siblings_studying_display(application),
        aspirations=_val(application.aspirations),
        plans=_val(application.plans),
        fears=_val(application.fears),
        daily_life=_val(application.daily_life),
        family_context=_val(application.family_context),
        funding_note=_val(funding_note),
    )


def _slugify(s):
    return re.sub(r'[^a-z0-9]+', '_', (s or '').lower()).strip('_')[:40]


def _normalise_gaps(raw):
    """Clamp to 6, drop empties, slugify + dedupe codes (synthesising gap_<i> when
    Gemini omits/repeats a code)."""
    out, seen = [], set()
    for i, g in enumerate((raw or [])[:6]):
        if not isinstance(g, dict):
            continue
        question = (g.get('question') or '').strip()
        if not question:
            continue
        code = _slugify(g.get('code') or '') or f'gap_{i + 1}'
        if code in seen:
            code = f'{code}_{i + 1}'
        seen.add(code)
        out.append({'code': code, 'question': question, 'why': (g.get('why') or '').strip()})
    return out


def generate_interview_gaps(application, language=None):
    """Return {'gaps': [{code, question, why}]} or {'error': ...}. Never raises."""
    target_language = _resolve_language(application, language)
    prompt = _build_gap_prompt(application, target_language)
    from .vision import _call_gemini_json   # shared structured-output Gemini seam
    data = _call_gemini_json(prompt, GAP_SCHEMA)
    if '_error' in data:
        return {'error': data['_error']}
    return {'gaps': _normalise_gaps(data.get('gaps'))}
