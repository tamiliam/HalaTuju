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
from datetime import timedelta

from django.utils import timezone

from .profile_engine import (
    DEFAULT_LANGUAGE, _funding, _pathway, _quiz_interests, _resolve_language,
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
                    'bucket': {'type': 'string'},
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
B40 scholarship applicant. Today's date is {today} (Asia/Kuala Lumpur) — use it to judge \
whether any date the applicant mentions is in the past or the future; NEVER describe a date \
earlier than today as being "in the future". Read EVERYTHING below — the applicant's own words (which \
may be in Malay, English, or Tamil), their academic record, the automated \
verification verdict, the pre-interview flags, and any questions they have already \
answered.

The sponsor funds the most DESERVING and RESILIENT students, and judges every interview \
against THREE things it needs to know. Target your questions at whichever of these the \
record leaves genuinely UNANSWERED (skip a bucket the data already settles):

  1. ACADEMIC COMMITMENT & RESILIENCE — does this student have the determination to \
     finish a degree? Good probes when unevidenced: their favourite vs hardest subject \
     (does it fit their results?), whether they sought help / had tuition when a subject \
     was hard, and how they pushed through setbacks. (Frame as warm curiosity, never a test.)
  2. FINANCIAL NEED (the FULL household) — is the family genuinely B40, and can they keep \
     this student in the programme? IMPORTANT — what the assistance IS: a MODEST, FIXED \
     monthly living-cost bursary (on the order of RM200 a month). It is a small top-up, NOT \
     a scholarship that covers fees, a laptop, or the full cost of study, and its amount is \
     fixed — never negotiated up or down for an individual, and never "partial funding" of a \
     specific purchase. So NEVER ask the student to "bridge the gap" between the bursary and a \
     cost, never imply the sponsor might cover a laptop/fees/equipment partially or fully, and \
     never present a ringgit figure as what the sponsor offers toward a specific expense. \
     Good probes when unevidenced: the household circumstance behind the numbers, what other \
     support the family relies on (relatives, part-time work, other aid) to sustain the \
     student's studies, and how they are coping. (Show empathy; never interrogate.)
  3. PATHWAY & ENROLMENT CONFIDENCE — will they actually enrol in and complete the \
     government programme they hold an offer for? Good probes when unevidenced: their \
     first choice vs what they were offered, and any practical obstacle to reporting.

Identify the THREE most important things still worth probing — prefer the buckets the \
verdict/flags/answers show are genuinely unresolved, and do NOT re-ask anything already \
answered below. Do NOT invent facts. If the student's INTEREST-QUIZ signals clearly diverge \
from their chosen pathway, you MAY include ONE exploratory question to understand how they \
arrived at that pathway given those interests — the student has already chosen and holds an \
offer letter, so frame it as genuine curiosity ("help me understand…"), NEVER as doubt, \
criticism, or a suggestion they chose wrongly. If little is left to probe, return fewer than \
three (even zero). For EACH gap return: a short snake_case "code" (a slug you invent, e.g. \
unclear_funding_plan), a "bucket" (one of: academic_resilience, financial_need, \
pathway_confidence, other), a "question" (the actual interview question, written in \
{target_language}), and a "why" (one short line of rationale for the interviewer, \
in {target_language}). Return at most 3. Return JSON only.

APPLICANT CONTEXT
Pathway: {pathway}
Interest-quiz signals (strongest interests + work style): {quiz_interests}
Household income (RM/month): {household_income}; household size: {household_size}
Receives STR: {receives_str}; receives JKM: {receives_jkm}
First in family to attend tertiary: {first_in_family}; siblings studying: {siblings_studying}

ACADEMIC RECORD
{academic}

AUTOMATED VERIFICATION VERDICT (per fact — status + any unresolved codes)
{verdict}

PRE-INTERVIEW FLAGS (automated; a conversation should settle these)
{flags}

ALREADY ANSWERED (do NOT re-ask these)
{answered}

APPLICANT'S OWN WORDS
Aspirations: {aspirations}
Plans: {plans}
What worries them / support they want: {fears}
Daily life: {daily_life}
Family context: {family_context}
Funding note: {funding_note}
{avoid}"""

MAX_GAPS = 3   # 3 at a time; the reviewer can "generate more" to append further sets.


def _val(v, fallback='(not provided)'):
    return v if v not in (None, '') else fallback


def _academic_summary(application):
    """Compact grade summary + A-grade count for the prompt (best-effort)."""
    profile = application.profile
    grades = getattr(profile, 'grades', None) if profile else None
    if not grades:
        return '(not provided)'
    try:
        from .profile_engine import count_spm_a_grades
        a_count = count_spm_a_grades(grades)
    except Exception:
        a_count = 0
    try:
        parts = ', '.join(f'{k}: {v}' for k, v in grades.items())
    except Exception:
        parts = str(grades)
    return f'{parts}  (A-grade count: {a_count})'


def _verdict_summary(application):
    """Render the deterministic four-fact verdict: status + unresolved codes."""
    try:
        from .verdict_engine import build_verdict
        facts = build_verdict(application)
    except Exception:
        return '(unavailable)'
    lines = []
    for f in (facts or []):
        if not isinstance(f, dict):
            continue
        unresolved = [u.get('code', '') for u in (f.get('unresolved') or []) if isinstance(u, dict)]
        tail = f"; unresolved: {', '.join(c for c in unresolved if c)}" if any(unresolved) else ''
        lines.append(f"- {f.get('fact', '?')}: {f.get('status', '?')}{tail}")
    return '\n'.join(lines) if lines else '(none)'


def _flags_summary(application):
    """Render the deterministic pre-interview flags (anomaly codes + key params)."""
    try:
        from .anomaly_engine import detect_anomalies
        flags = detect_anomalies(application)
    except Exception:
        return '(unavailable)'
    lines = []
    for a in (flags or []):
        if not isinstance(a, dict):
            continue
        params = a.get('params') or {}
        hint = ', '.join(f'{k}={v}' for k, v in params.items()) if isinstance(params, dict) else ''
        lines.append(f"- {a.get('code', '?')}" + (f" ({hint})" if hint else ''))
    return '\n'.join(lines) if lines else '(none)'


def _answered_summary(application):
    """Render Check-2 / officer queries the student has already answered, so the
    model builds on them rather than re-asking."""
    try:
        items = application.resolution_items.filter(
            status='resolved', resolved_by='student').exclude(resolution_text='')
    except Exception:
        return '(none)'
    lines = []
    for it in items:
        q = (it.prompt or it.code or '').strip()
        ans = (it.resolution_text or '').strip()
        if ans:
            lines.append(f'- Q: {q or "(query)"}  A: {ans}')
    return '\n'.join(lines) if lines else '(none)'


def _build_gap_prompt(application, target_language=DEFAULT_LANGUAGE, existing=None):
    profile = application.profile
    _cats, _months, funding_note = _funding(application)
    existing_qs = [str(q).strip() for q in (existing or []) if str(q).strip()]
    avoid = ''
    if existing_qs:
        avoid = ('\n\nALREADY SUGGESTED (return DIFFERENT, NEW questions; do not repeat these):\n'
                 + '\n'.join(f'- {q}' for q in existing_qs))
    return GAP_PROMPT.format(
        today=(timezone.now() + timedelta(hours=8)).strftime('%d %B %Y'),  # MYT (UTC+8)
        target_language=target_language,
        pathway=_pathway(application),
        quiz_interests=_quiz_interests(application),
        household_income=_val(getattr(profile, 'household_income', None) if profile else None),
        household_size=_val(getattr(profile, 'household_size', None) if profile else None),
        receives_str=_yesno(getattr(profile, 'receives_str', None) if profile else None),
        receives_jkm=_yesno(getattr(profile, 'receives_jkm', None) if profile else None),
        first_in_family=_yesno(application.first_in_family),
        siblings_studying=_siblings_studying_display(application),
        academic=_academic_summary(application),
        verdict=_verdict_summary(application),
        flags=_flags_summary(application),
        answered=_answered_summary(application),
        aspirations=_val(application.aspirations),
        plans=_val(application.plans),
        fears=_val(application.fears),
        daily_life=_val(application.daily_life),
        family_context=_val(application.family_context),
        funding_note=_val(funding_note),
        avoid=avoid,
    )


def _slugify(s):
    return re.sub(r'[^a-z0-9]+', '_', (s or '').lower()).strip('_')[:40]


def _normalise_gaps(raw, seen_codes=None, seen_questions=None):
    """Clamp to MAX_GAPS, drop empties, slugify + dedupe codes (synthesising gap_<i>
    when Gemini omits/repeats a code). ``seen_codes``/``seen_questions`` carry codes
    and questions already on the application so a 'generate more' run doesn't repeat."""
    out = []
    seen = set(seen_codes or set())
    seen_q = {str(q).strip().lower() for q in (seen_questions or set())}
    for i, g in enumerate(raw or []):
        if len(out) >= MAX_GAPS:
            break
        if not isinstance(g, dict):
            continue
        question = (g.get('question') or '').strip()
        if not question or question.lower() in seen_q:
            continue
        code = _slugify(g.get('code') or '') or f'gap_{i + 1}'
        if code in seen:
            code = f'{code}_{i + 1}'
        seen.add(code)
        seen_q.add(question.lower())
        bucket = (g.get('bucket') or '').strip().lower()
        if bucket not in ('academic_resilience', 'financial_need', 'pathway_confidence'):
            bucket = 'other'
        out.append({'code': code, 'bucket': bucket, 'question': question,
                    'why': (g.get('why') or '').strip()})
    return out


def generate_interview_gaps(application, language=None, existing=None):
    """Return {'gaps': [{code, question, why}]} (≤ MAX_GAPS) or {'error': ...}. Never
    raises. ``existing`` is the list of already-suggested gaps (dicts or questions);
    when given, the new set avoids repeating them ('generate more')."""
    target_language = _resolve_language(application, language)
    existing = existing or []
    existing_qs = [g.get('question', '') if isinstance(g, dict) else str(g) for g in existing]
    existing_codes = {g.get('code', '') for g in existing if isinstance(g, dict)}
    prompt = _build_gap_prompt(application, target_language, existing=existing_qs)
    from .vision import _call_gemini_json   # shared structured-output Gemini seam
    data = _call_gemini_json(prompt, GAP_SCHEMA)
    if '_error' in data:
        return {'error': data['_error']}
    return {'gaps': _normalise_gaps(data.get('gaps'), seen_codes=existing_codes,
                                    seen_questions=set(existing_qs))}
