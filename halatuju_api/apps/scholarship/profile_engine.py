"""
AI sponsor-profile drafting for the B40 Assistance Programme.

Builds a sponsor-ready narrative from an application's **profile-canonical** data
(academic + financial live on ``StudentProfile``), the "Your story" guided
narrative, the simplified funding need, and any referees — via the Gemini model
cascade. The student's own words may be written in **Malay, English, or Tamil**;
the model understands all three and writes the profile in the requested target
language (defaults to the applicant's locale → English/Malay). Mocked in tests;
degrades gracefully to an error dict when the AI is unavailable.
"""
import logging
import time

from django.conf import settings

from .models import FundingNeed
from .shortlisting import count_spm_a_grades

logger = logging.getLogger(__name__)

MODEL_CASCADE = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash']

# Applicant locale code → output language name used in the prompt.
LANGUAGE_NAMES = {'en': 'English', 'ms': 'Malay (Bahasa Melayu)'}
DEFAULT_LANGUAGE = 'English'

PROFILE_PROMPT = """You are writing a confidential, sponsor-ready profile for a B40 student \
applying for education financial assistance in Malaysia.

LANGUAGE — read carefully:
- The student's own words below (their aspirations, plans, family situation, daily life, \
funding note) may be written in Malay, English, or Tamil — or a mix. Understand them \
whichever language they are in; do not translate them literally, capture their meaning.
- Write the FINAL profile in {target_language}, regardless of the language the student wrote in.

Write factual, warm, and concise prose (~300-400 words) in Markdown with these sections: \
Background, Academic record, Pathway plan, Funding need, Why support matters. Use ONLY the \
information given below; do not invent facts. Where information is missing, say so briefly \
rather than guessing.

VERIFICATION — do not over-claim:
- Some fields are marked "{do_not_claim}". Those are NOT verified. Do NOT assert them as fact; \
omit them rather than hedge.
- Report grades as the actual band mix given (e.g. "ten distinctions across A+/A/A−"); never \
round up or imply a uniform top grade.

TONE — honest and dignified:
- Factual warmth, not fundraising melodrama. Do NOT mine hardship for sympathy and do NOT use \
clichés like "breaking the cycle" or "ripple effect". Let the facts carry the case.
- Do not invent specifics (an age, a number of children, a relationship) that are not stated below.

Student: {name}
School: {school}
Qualification: {qualification}    SPM A-count: {spm_a_count}    STPM PNGK: {stpm_pngk}
Household income (RM/month): {household_income}    Household size: {household_size}
Receives STR: {receives_str}    Receives JKM: {receives_jkm}
First in family to university: {first_in_family}
Parents'/guardians' occupation: {parents_occupation}
Siblings currently studying: {siblings_studying}

Pathway / programme: {pathway}

Aspirations (student's words): {aspirations}
Plan to get there (student's words): {plans}
Family situation (student's words): {family_context}
Daily life & responsibilities (student's words): {daily_life}

Funding — what the support would help with: {funding_categories}
Programme length (months): {programme_months}
Anything else about funding (student's words): {funding_note}

Referee(s): {referees}
"""


def _call_gemini_text(prompt, target_language):
    """Shared seam: run ``prompt`` through the model cascade and return
    {'markdown', 'model_used', 'language', ...} or {'error': ...}. Both the draft
    and the Phase-D refine go through this one function — tests patch it (no
    billable call in CI), mirroring vision._call_gemini_json for the JSON engines."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        return {'error': 'AI service not configured (missing API key)'}
    try:
        from google import genai
    except ImportError:
        return {'error': 'AI module not installed'}

    client = genai.Client(api_key=api_key)
    last_error = None
    for model_name in MODEL_CASCADE:
        try:
            start = time.time()
            response = client.models.generate_content(model=model_name, contents=prompt)
            elapsed = int((time.time() - start) * 1000)
            return {
                'markdown': response.text, 'model_used': model_name,
                'language': target_language, 'generation_time_ms': elapsed,
            }
        except Exception as e:
            last_error = str(e)
            logger.warning('Gemini text generation failed with %s: %s', model_name, e)
            continue
    return {'error': f'All AI models failed: {last_error}'}


def _resolve_language(application, language):
    """Resolve the output language NAME. Accepts a locale code ('en'/'ms') or a
    full name; falls back to the applicant's locale, then English."""
    if language:
        return LANGUAGE_NAMES.get(language, language)
    return LANGUAGE_NAMES.get(getattr(application, 'locale', '') or '', DEFAULT_LANGUAGE)


def _yesno(v):
    if v is None:
        return 'not provided'
    return 'yes' if v else 'no'


# ── Check 2 §6: claim-gating ─────────────────────────────────────────────────
# The generator must assert ONLY claims the deterministic layer verifies — the fix
# for the live bug where the profile asserted "first-generation" while it was merely
# an unverified flag. The STEP-1 facts ledger (submission_review) is the source of
# truth for what's verified; this gates the one assertion the form lets a student make
# about themselves that we can independently check (first-to-university, via the
# sibling split). Other unverified narrative is already attributed to "the student".
_DO_NOT_CLAIM = 'not established — do not claim'


def _ledger_verification(application):
    """{claim: verification} from the STEP-1 facts ledger (verified/reported/…)."""
    from .submission_review import build_facts_ledger
    return {row['claim']: row['verification'] for row in build_facts_ledger(application)}


def _gated_first_in_family(application, ledger):
    """'yes' only when the sibling split VERIFIES first-to-university; 'no' when the
    student didn't claim it; otherwise the do-not-claim sentinel so the model never
    asserts an unverified flag as fact (Check 2 §6)."""
    if not application.first_in_family:
        return 'no'
    return 'yes' if ledger.get('first_in_family') == 'verified' else _DO_NOT_CLAIM


def _pathway(application):
    bits = []
    if application.field_of_study:
        bits.append(str(application.field_of_study))
    pc = application.pathways_considered
    if isinstance(pc, list) and pc:
        bits.append('pathways considered: ' + ', '.join(str(x) for x in pc))
    return '; '.join(bits) or 'not specified'


def _siblings_studying_display(application):
    """Render the siblings-studying signal for the prompt: the count (S15) of
    how many siblings are studying — tells the AI how much education burden the
    family carries. Blank when unknown. (TD-061 dropped the legacy boolean.)"""
    count = getattr(application, 'siblings_studying_count', None)
    return str(count) if count is not None else ''


def _funding(application):
    """(categories_str, programme_months, funding_note) from the simplified FundingNeed."""
    try:
        fn = application.funding_need
    except FundingNeed.DoesNotExist:
        return 'not provided', 'not provided', 'not provided'
    cats = fn.categories if isinstance(fn.categories, list) else []
    cats_str = ', '.join(str(c) for c in cats) if cats else 'not provided'
    months = fn.programme_months if fn.programme_months else 'not provided'
    note = fn.funding_note.strip() if fn.funding_note else 'not provided'
    return cats_str, months, note


def _build_prompt(application, target_language=DEFAULT_LANGUAGE):
    profile = application.profile

    def val(v, fallback='not provided'):
        return v if v not in (None, '') else fallback

    def pval(attr, fallback='not provided'):
        return val(getattr(profile, attr, None) if profile else None, fallback)

    spm_a_count = count_spm_a_grades(getattr(profile, 'grades', None)) if profile else 0
    cats_str, months, note = _funding(application)
    ledger = _ledger_verification(application)

    return PROFILE_PROMPT.format(
        target_language=target_language,
        do_not_claim=_DO_NOT_CLAIM,
        name=pval('name', 'the applicant'),
        school=pval('school'),
        qualification=(pval('exam_type', 'n/a') or 'n/a'),
        spm_a_count=spm_a_count,
        stpm_pngk=pval('stpm_cgpa', 'n/a'),
        household_income=pval('household_income'),
        household_size=pval('household_size'),
        receives_str=_yesno(getattr(profile, 'receives_str', None) if profile else None),
        receives_jkm=_yesno(getattr(profile, 'receives_jkm', None) if profile else None),
        first_in_family=_gated_first_in_family(application, ledger),
        parents_occupation=val(application.parents_occupation),
        siblings_studying=_siblings_studying_display(application),
        pathway=_pathway(application),
        aspirations=val(application.aspirations),
        plans=val(application.plans),
        family_context=val(application.family_context),
        daily_life=val(application.daily_life),
        funding_categories=cats_str,
        programme_months=months,
        funding_note=note,
        referees=', '.join(
            f'{r.name} ({r.role})' if r.role else r.name
            for r in application.referees.all()
        ) or 'none provided',
    )


REFINE_PROMPT = """You are refining a confidential, sponsor-ready profile for a B40 student \
applying for education financial assistance in Malaysia.

You are given (1) a DRAFT profile written from the application form, and (2) the findings of a \
real interview an officer conducted with the student. Produce a REFINED FINAL profile that folds \
the interview's findings into the draft.

LANGUAGE — read carefully:
- The interview findings below may be written in Malay, English, or Tamil — or a mix. Understand \
them whichever language they are in.
- Write the FINAL profile in {target_language}, regardless of the language the findings are in.

Rules:
- Keep the same sections and warm, factual, concise tone (~300-400 words) as the draft, in Markdown.
- Where the interview CONFIRMED or CLARIFIED something, update the profile to reflect what was learned.
- Where the interview raised a NEW CONCERN, reflect it honestly and proportionately — do not hide it, \
do not exaggerate it.
- Use ONLY the draft and the interview findings below. Do NOT invent facts. If the interview did not \
touch a section, keep the draft's wording for it.
- This is the version a sponsor will read, so it must read as one coherent profile, not a draft with \
notes bolted on.

=== DRAFT PROFILE ===
{draft}

=== INTERVIEW FINDINGS ===
{findings}

Interviewer's rubric scores (1-5): {rubric}
Interviewer's overall note: {overall_note}
"""

_VERDICT_LABELS = {
    'resolved': 'resolved at interview',
    'still_unclear': 'still unclear after interview',
    'new_concern': 'new concern raised at interview',
}


def _render_interview(application, session):
    """Render a submitted InterviewSession's findings/rubric/note as plain text for
    the refine prompt. The interviewer's free-text rationale carries the meaning, so
    anomaly codes need no i18n resolution; gap codes get their question for context."""
    gaps_by_code = {}
    for g in (application.interview_gaps or []):
        if isinstance(g, dict) and g.get('code'):
            gaps_by_code[g['code']] = g.get('question', '')

    lines = []
    for code, val in (session.findings or {}).items():
        if not isinstance(val, dict):
            continue
        verdict = _VERDICT_LABELS.get(val.get('verdict', ''), val.get('verdict', '') or 'noted')
        rationale = (val.get('rationale') or '').strip()
        context = gaps_by_code.get(code, '')
        prefix = f'On "{context}" — ' if context else ''
        lines.append(f'- [{verdict}] {prefix}{rationale}'.rstrip())
    findings_str = '\n'.join(lines) if lines else 'No specific findings recorded.'

    rubric = session.rubric if isinstance(session.rubric, dict) else {}
    rubric_str = ', '.join(f'{k}: {v}' for k, v in rubric.items()) or 'not scored'
    note = (session.overall_note or '').strip() or 'none'
    return findings_str, rubric_str, note


def refine_sponsor_profile(application, draft, session, language=None):
    """Second Gemini pass: refine ``draft`` with the submitted interview ``session``.
    Returns {'markdown', 'model_used', 'language', ...} or {'error': ...}. Mirrors
    generate_sponsor_profile (same cascade, same graceful-error contract)."""
    target_language = _resolve_language(application, language)
    findings_str, rubric_str, note = _render_interview(application, session)
    prompt = REFINE_PROMPT.format(
        target_language=target_language,
        draft=(draft or '').strip() or 'not provided',
        findings=findings_str, rubric=rubric_str, overall_note=note,
    )
    return _call_gemini_text(prompt, target_language)


def generate_sponsor_profile(application, language=None):
    """Return {'markdown', 'model_used', 'language', ...} or {'error': ...}.

    ``language`` may be a locale code ('en'/'ms') or a language name; it defaults
    to the applicant's locale. The student's narrative may be in Malay, English,
    or Tamil — the model is told to understand all three.
    """
    target_language = _resolve_language(application, language)
    prompt = _build_prompt(application, target_language=target_language)
    return _call_gemini_text(prompt, target_language)


# ── Phase E2: the ANONYMOUS, sponsor-pool-facing profile ──────────────────────
# A *generated* (not scrubbed) non-identifying profile. It is fed ONLY
# non-identifying inputs — note there is no `name`, `school`, or `referees`
# placeholder below — and is firmly instructed never to surface any identifier.
# A human (admin) reviews + publishes it before it ever reaches a sponsor; the
# deterministic allowlist card is the hard boundary, this blurb is the soft one.
ANON_PROMPT = """You are writing a CONFIDENTIAL, ANONYMOUS profile of a B40 student for a \
prospective sponsor on a permanently-anonymous giving platform in Malaysia. The sponsor must \
NEVER be able to identify the student.

ABSOLUTE ANONYMITY RULES — follow exactly:
- Refer to the person only as "the student". Never invent or include a name.
- NEVER include any identifying detail: no person's name, no school/college name, no town/city/\
street/address, no phone, no email, no IC number. If the student's own words below mention any \
such detail, OMIT it — do not repeat it.
- State-level region and field of study are fine; anything more specific is not.

LANGUAGE — the student's own words may be in Malay, English, or Tamil (or a mix); understand them \
whichever language they are in, and write the FINAL profile in {target_language}.

Write factual, warm, concise prose (~250-350 words) in Markdown with these sections: Background, \
Academic record, Pathway plan, Funding need, Why support matters. Use ONLY the information below; \
do not invent facts. Where information is missing, say so briefly.

VERIFICATION — do not over-claim:
- Some fields are marked "{do_not_claim}". Those are NOT verified. Do NOT assert them as fact; \
omit them rather than hedge.
- Report grades as the actual band mix given; never round up or imply a uniform top grade.

TONE — honest and dignified:
- Factual warmth, not fundraising melodrama. Do NOT mine hardship for sympathy and do NOT use \
clichés like "breaking the cycle" or "ripple effect". Let the facts carry the case.
- Do not invent specifics (an age, a number of children, a relationship) that are not stated below.

Qualification: {qualification}    SPM A-count: {spm_a_count}    STPM PNGK: {stpm_pngk}
Home state: {state}
Household income (RM/month): {household_income}    Household size: {household_size}
Receives STR: {receives_str}    Receives JKM: {receives_jkm}
First in family to university: {first_in_family}
Parents'/guardians' occupation: {parents_occupation}
Siblings currently studying: {siblings_studying}

Pathway / field: {pathway}

Aspirations (student's words): {aspirations}
Plan to get there (student's words): {plans}
Family situation (student's words): {family_context}
Daily life & responsibilities (student's words): {daily_life}

Funding — what the support would help with: {funding_categories}
Programme length (months): {programme_months}
Anything else about funding (student's words): {funding_note}
"""


def _build_anon_prompt(application, target_language=DEFAULT_LANGUAGE):
    """Build the anonymous-profile prompt. Deliberately omits name/school/referees."""
    profile = application.profile

    def val(v, fallback='not provided'):
        return v if v not in (None, '') else fallback

    def pval(attr, fallback='not provided'):
        return val(getattr(profile, attr, None) if profile else None, fallback)

    spm_a_count = count_spm_a_grades(getattr(profile, 'grades', None)) if profile else 0
    cats_str, months, note = _funding(application)
    ledger = _ledger_verification(application)

    return ANON_PROMPT.format(
        target_language=target_language,
        do_not_claim=_DO_NOT_CLAIM,
        qualification=(pval('exam_type', 'n/a') or 'n/a'),
        spm_a_count=spm_a_count,
        stpm_pngk=pval('stpm_cgpa', 'n/a'),
        state=pval('preferred_state'),
        household_income=pval('household_income'),
        household_size=pval('household_size'),
        receives_str=_yesno(getattr(profile, 'receives_str', None) if profile else None),
        receives_jkm=_yesno(getattr(profile, 'receives_jkm', None) if profile else None),
        first_in_family=_gated_first_in_family(application, ledger),
        parents_occupation=val(application.parents_occupation),
        siblings_studying=_siblings_studying_display(application),
        pathway=_pathway(application),
        aspirations=val(application.aspirations),
        plans=val(application.plans),
        family_context=val(application.family_context),
        daily_life=val(application.daily_life),
        funding_categories=cats_str,
        programme_months=months,
        funding_note=note,
    )


def generate_anonymous_profile(application, language=None):
    """Generate the ANONYMOUS sponsor-pool profile. Same cascade + graceful-error
    contract as generate_sponsor_profile, but fed only non-identifying inputs.
    Returns {'markdown', 'model_used', 'language', ...} or {'error': ...}."""
    target_language = _resolve_language(application, language)
    prompt = _build_anon_prompt(application, target_language=target_language)
    return _call_gemini_text(prompt, target_language)
