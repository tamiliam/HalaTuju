"""
AI student profile for the B40 Assistance Programme.

There is ONE profile, common to the reviewer and (once the student is approved) the
sponsor — generated twice by the system, never by a human clicking "generate":
  • DRAFT  — at the Check 2 → reviewer handoff (Gemini Flash), so the reviewer opens a
             ready narrative to understand the student and verify the claims.
  • FINAL  — when the reviewer saves the verdict (Gemini Pro). It folds in the student's
             answers to our questions, the interview findings, the verdict, the
             recommended assistance amount and the reviewer's conclusion, and REPLACES
             the draft. This final IS the profile a sponsor reads.

It is **PII-redacted, not strictly anonymous**: the student is referred to by a stable
alias and the only details withheld — for the student AND any parent/guardian — are
name, NRIC, photo, phone, email and street address. Everything else (school, town/state,
institution, occupations) may be used.

The student's own words may be in Malay, English, or Tamil; the model understands all
three and writes in the requested target language. Mocked in tests; degrades gracefully
to an error dict when the AI is unavailable.
"""
import logging
import re
import time

from django.conf import settings

from .models import FundingNeed
from .shortlisting import count_spm_a_grades

logger = logging.getLogger(__name__)

MODEL_CASCADE = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash']
# The FINAL profile is the conclusive document a sponsor reads, generated rarely (once
# per accepted student) — so it runs on Pro for the best prose, falling back to the
# Flash cascade if Pro is unavailable. The high-volume DRAFT stays on the Flash cascade.
PRO_CASCADE = ['gemini-2.5-pro'] + MODEL_CASCADE

# Applicant locale code → output language name used in the prompt.
LANGUAGE_NAMES = {'en': 'English', 'ms': 'Malay (Bahasa Melayu)'}
DEFAULT_LANGUAGE = 'English'

# Shared narrative + privacy instructions (the same single profile for reviewer + sponsor).
_STYLE = (
    "Write warm, factual, flowing prose: about three short paragraphs, roughly 220-320 "
    "words, with NO section headings and NO bullet lists. Tell the story so a reader "
    "understands, in turn, who the student is and the family's situation; the student's "
    "academic standing and pathway; and what the student is worried about and how the "
    "support would help. Refer to the student as 'he' or 'she' using the pronouns given "
    "below; NEVER use 'they' for the student (most people write he/she). Use em-dashes very "
    "sparingly, at most one in the whole profile; prefer commas, full stops or brackets. Let "
    "the facts carry the case: do NOT use fundraising clichés such as 'breaking the cycle', "
    "'ripple effect' or 'pioneering spirit', and do NOT invent specifics (an age, a "
    "relationship, a figure) not given below. Where a fact is missing, leave it out rather "
    "than guess."
)

_REDACTION = (
    "PRIVACY — this single profile is read by the reviewer AND, once the student is "
    "approved, by external sponsors, so it must never expose contact or identity details. "
    "Refer to the student ONLY by the alias \"{alias}\"; never invent or include a name. For "
    "the student AND any parent or guardian, NEVER include their name, NRIC/IC number, "
    "photograph, phone number, email address, or street address — if any appears in the "
    "inputs below, omit it. Everything else may be used: the school or college name, the "
    "town and state, the institution, and occupations."
)

PROFILE_PROMPT = """You are writing the profile of a B40 student applying for education \
financial assistance in Malaysia. It is read first by the reviewer assessing the application, \
and later by a prospective sponsor.

{redaction}

LANGUAGE — the student's own words below may be in Malay, English, or Tamil (or a mix); \
understand their meaning whichever language they are in, and write the profile in {target_language}.

{style}

VERIFICATION — do not over-claim:
- Some fields are marked "{do_not_claim}" — NOT verified. Do not assert them; omit them.
- Report grades as the actual band mix (e.g. "ten A-grade subjects across A+/A/A−") and name the \
subject areas they span; never round up or imply a uniform top grade. If a merit score is given, \
you may cite it.
- INCOME & WELFARE — be precise. "Receives STR"/"Receives JKM" mean the family is registered as \
B40 / receives government welfare; they do NOT verify the income AMOUNT (STR confirms B40 status, \
not a figure). If "Documented income (payslip/EPF)" below lists one or more figures, you MAY state \
those AUTHORITATIVELY, naming the document and whose income it is (this can happen on either track). \
For any income NOT documented there, present it as what the family REPORTS (e.g. "the family reports \
about RM…"), never as "confirmed", and do NOT attribute a reported figure to a specific earner or \
invent a breakdown. If who earns what is unclear, describe the situation (a single earner, a parent \
unable to work) without inventing numbers. Do not make up a story to reconcile the figures.

THE STUDENT (alias {alias})
Pronouns (use these for the student, never "they"): {pronouns}
School / college: {school}
Qualification: {qualification}    Merit score: {merit}
SPM grades: {grades_summary}    STPM PNGK: {stpm_pngk}
Home town / state: {region}
Household income (RM/month, as reported): {household_income}    Household size: {household_size}
Documented income (payslip/EPF — use authoritatively if present): {income_evidence}
Receives STR (B40 status, not an income figure): {receives_str}    Receives JKM: {receives_jkm}
First in family to university: {first_in_family}
Parents'/guardians' occupation: {parents_occupation}
Siblings currently studying: {siblings_studying}

Pathway / programme (use the confirmed place when present): {pathway}
Top course choices (student's ranking): {top_choices}
While still deciding (student's words): {deliberation}
Other scholarships applied for / held: {other_scholarships}
Help the student asked us for: {help_wanted}
Interest-quiz signals (the student's strongest interests + work style): {quiz_interests}

Aspirations (student's words): {aspirations}
Plan to get there (student's words): {plans}
Why assistance is needed (student's words): {justification}
Worries / concerns (student's words): {fears}
Family situation (student's words): {family_context}
Daily life & responsibilities (student's words): {daily_life}
Anything else the student wants us to know (student's words): {anything_else}

Funding — what the support would help with: {funding_categories}
Anything else about funding (student's words): {funding_note}

The student's answers to our clarifying questions:
{qa}

Draw on ALL of the student's own words above and distil them into the narrative where they add \
meaning — their aspirations, plan, reasons, worries, deliberation and anything-else. Do not ignore \
a field the student took the trouble to fill in; equally, do not pad with a field left blank \
("not provided"/"none"/"not applicable" means say nothing about it).

The interest-quiz signals are ACCRETIVE ONLY: use them to add positive colour about the student's \
interests and strengths (e.g. how their pathway plays to what energises them). NEVER use the quiz to \
question, doubt, cast as a mismatch, or otherwise weaken the student's chosen pathway or case. If the \
quiz does not obviously add something supportive, simply leave it out.
"""


def _call_gemini_text(prompt, target_language, models=None):
    """Shared seam: run ``prompt`` through a model cascade and return
    {'markdown', 'model_used', 'language', ...} or {'error': ...}. Both the draft
    and the refine go through this one function — tests patch it (no billable call
    in CI). ``models`` overrides the cascade (the final refine passes PRO_CASCADE)."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        return {'error': 'AI service not configured (missing API key)'}
    try:
        from google import genai
    except ImportError:
        return {'error': 'AI module not installed'}

    client = genai.Client(api_key=api_key)
    last_error = None
    for model_name in (models or MODEL_CASCADE):
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


def _alias(application):
    """The stable, non-identifying handle used everywhere this profile is read (the
    same alias the sponsor pool uses), e.g. 'S-A3F9C1'."""
    from .pool import pool_ref
    return pool_ref(application.id)


def _pronouns(application):
    """'she/her' or 'he/him' for the student, from the recorded gender (falling back to
    the Malaysian NRIC last digit: odd = male, even = female). 'not provided' if unknown —
    the model is told to avoid 'they', so it picks a sensible default rather than hedge."""
    profile = getattr(application, 'profile', None)
    g = (getattr(profile, 'gender', '') or '').strip().lower() if profile else ''
    if g in ('female', 'f', 'perempuan'):
        return 'she/her'
    if g in ('male', 'm', 'lelaki'):
        return 'he/him'
    nric = re.sub(r'\D', '', getattr(profile, 'nric', '') or '') if profile else ''
    if nric:
        return 'he/him' if int(nric[-1]) % 2 else 'she/her'
    return 'not provided'


# ── Check 2 §6: claim-gating ─────────────────────────────────────────────────
# The generator must assert ONLY claims the deterministic layer verifies — the fix
# for the live bug where the profile asserted "first-generation" while it was merely
# an unverified flag. The STEP-1 facts ledger (submission_review) is the source of truth.
_DO_NOT_CLAIM = 'not established — do not claim'


def _ledger_verification(application):
    """{claim: verification} from the STEP-1 facts ledger (verified/reported/…)."""
    from .submission_review import build_facts_ledger
    return {row['claim']: row['verification'] for row in build_facts_ledger(application)}


def _gated_first_in_family(application, ledger):
    """'yes' only when the sibling split VERIFIES first-to-university; 'no' when the
    student didn't claim it; otherwise the do-not-claim sentinel (Check 2 §6)."""
    if not application.first_in_family:
        return 'no'
    return 'yes' if ledger.get('first_in_family') == 'verified' else _DO_NOT_CLAIM


def _pathway(application):
    """Describe the pathway, preferring the CONCRETE chosen programme + institution and
    whether it's confirmed (an offer the student holds), so the profile can name the real
    place rather than a vague 'pre-university'."""
    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    bits = []
    programme = (cp.get('course_name') or '').strip()
    if programme:
        bits.append(programme)
    elif application.field_of_study:
        bits.append(str(application.field_of_study))
    institution = (cp.get('institution') or getattr(application, 'pre_u_institution', '') or '').strip()
    if institution:
        bits.append(f'at {institution}')
    if getattr(application, 'pathway_confirmed_at', None) or cp.get('source', '').startswith('offer_letter'):
        bits.append('(confirmed place — the student holds the offer)')
    track = (getattr(application, 'pre_u_track', '') or '').strip()
    if track:
        bits.append(f'stream/track: {track}')
    pc = application.pathways_considered
    if not programme and isinstance(pc, list) and pc:
        bits.append('pathways considered: ' + ', '.join(str(x) for x in pc))
    return ' '.join(bits).strip() or 'not specified'


def _siblings_studying_display(application):
    count = getattr(application, 'siblings_studying_count', None)
    return str(count) if count is not None else ''


def _income_evidence(application):
    """Documented monthly income read from any salary slip / EPF on file — usable
    authoritatively even on the STR track (a student may submit payslips/EPF as extra
    proof). Covers the salary-route members AND the STR-route earner. 'none on file' when
    no readable income document exists, so the model falls back to the reported figure."""
    from .income_engine import working_members, earner_monthly_income
    members = list(working_members(application))
    earner = (getattr(application, 'income_earner', '') or '').strip()
    if earner and earner not in members:
        members.append(earner)
    lines = []
    for m in members:
        amt, src = earner_monthly_income(application, m)
        if amt:
            label = {'salary': 'salary slip', 'epf_estimate': 'EPF statement'}.get(src, 'document')
            lines.append(f"{m}'s {label} shows about RM{int(round(amt))}/month")
    return '; '.join(lines) if lines else 'none on file'


def _merit(application):
    """The course-guide merit score (0-100 for SPM; PNGK for STPM), or 'not provided'."""
    from .serializers_admin import _application_merit_score
    m = _application_merit_score(application)
    return 'not provided' if m in (None, '') else str(m)


_GRADE_LABELS = {
    'bm': 'BM', 'eng': 'English', 'math': 'Mathematics', 'addmath': 'Add Maths',
    'science': 'Science', 'phy': 'Physics', 'chem': 'Chemistry', 'bio': 'Biology',
    'hist': 'History', 'history': 'History', 'geo': 'Geography', 'econ': 'Economics',
    'acc': 'Accounting', 'moral': 'Moral', 'agama': 'Islamic Studies',
}


def _grades_summary(profile):
    """A readable 'BM: A+, English: A, Mathematics: A−, …' string so the model can name
    the subject areas the A's span. Empty when no grades."""
    grades = getattr(profile, 'grades', None) if profile else None
    if not isinstance(grades, dict) or not grades:
        return 'not provided'
    parts = []
    for key, grade in grades.items():
        if not grade:
            continue
        label = _GRADE_LABELS.get(str(key).lower(), str(key).upper())
        parts.append(f'{label}: {grade}')
    return ', '.join(parts) or 'not provided'


def _region(profile):
    """Town + state where available (both allowed under the redaction policy)."""
    if not profile:
        return 'not provided'
    city = (getattr(profile, 'city', '') or '').strip()
    state = (getattr(profile, 'preferred_state', '') or '').strip()
    region = ', '.join(p for p in (city, state) if p)
    return region or 'not provided'


# Human labels for the interest-quiz signals (profile.student_signals). Only the two most
# communicative categories — what FIELDS interest the student, and their WORK STYLE.
_SIGNAL_LABELS = {
    'field_mechanical': 'building & fixing', 'field_digital': 'technology & digital',
    'field_business': 'business', 'field_health': 'health & care',
    'field_creative': 'creative & design', 'field_hospitality': 'hospitality & service',
    'field_agriculture': 'agriculture', 'field_heavy_industry': 'heavy industry',
    'field_electrical': 'electrical', 'field_civil': 'civil & construction',
    'field_aero_marine': 'aeronautical & marine', 'field_oil_gas': 'oil & gas',
    'hands_on': 'hands-on work', 'problem_solving': 'problem-solving',
    'people_helping': 'helping people', 'creative': 'creative work',
}
_SIGNAL_CATEGORIES = ('field_interest', 'work_preference_signals')


def _quiz_interests(application):
    """A short, POSITIVE read of the student's interest-quiz result (profile.student_signals):
    their strongest field interests + work-style. Accretive context only — never used to doubt
    a pathway. '' when no quiz on file."""
    profile = application.profile
    signals = getattr(profile, 'student_signals', None) if profile else None
    if not isinstance(signals, dict) or not signals:
        return 'not provided'
    labels = []
    for cat in _SIGNAL_CATEGORIES:
        bucket = signals.get(cat)
        if not isinstance(bucket, dict):
            continue
        # strongest first (score desc), keep the meaningful ones (score >= 1), cap at 3/category
        ranked = sorted(((s, sc) for s, sc in bucket.items() if isinstance(sc, (int, float)) and sc > 0),
                        key=lambda kv: kv[1], reverse=True)
        for sig, _score in ranked[:3]:
            lbl = _SIGNAL_LABELS.get(sig)
            if lbl and lbl not in labels:
                labels.append(lbl)
    return ', '.join(labels) if labels else 'not provided'


def _render_qa(application):
    """The student's answers to clarifying questions — the answered Check-2 + reviewer
    resolution items (those carrying a typed response). Question = the officer-written
    prompt if present, else the item code; answer = the student's resolution_text.
    Empty marker when none, so the prompt block is never blank."""
    lines = []
    items = (application.resolution_items
             .exclude(resolution_text='')
             .order_by('resolved_at', 'created_at'))
    for it in items:
        ans = (it.resolution_text or '').strip()
        if not ans:
            continue
        q = (it.prompt or '').strip() or it.code
        lines.append(f'- Q ({it.fact}): {q}\n  A: {ans}')
    return '\n'.join(lines) if lines else 'none recorded'


def _funding(application):
    """(categories_str, programme_months, funding_note) from the simplified FundingNeed.
    (programme_months is unused by the profile prose but kept in the tuple — gap_engine
    shares this helper.)"""
    try:
        fn = application.funding_need
    except FundingNeed.DoesNotExist:
        return 'not provided', 'not provided', 'not provided'
    cats = fn.categories if isinstance(fn.categories, list) else []
    cats_str = ', '.join(str(c) for c in cats) if cats else 'not provided'
    months = fn.programme_months if fn.programme_months else 'not provided'
    note = fn.funding_note.strip() if fn.funding_note else 'not provided'
    return cats_str, months, note


def _top_choices(application):
    """The student's ranked top course choices (apply form) — 'Course at Institution (choice 1)'."""
    tc = application.top_choices if isinstance(application.top_choices, list) else []
    bits = []
    for c in tc:
        if not isinstance(c, dict):
            continue
        name = (c.get('course_name') or '').strip()
        if not name:
            continue
        inst = (c.get('institution') or '').strip()
        rank = c.get('rank')
        label = name + (f' at {inst}' if inst else '')
        if rank:
            label += f' (choice {rank})'
        bits.append(label)
    return '; '.join(bits) if bits else 'not provided'


def _other_scholarships(application):
    """Other scholarships the student has applied for / holds (keys + their free text)."""
    keys = application.other_scholarships if isinstance(application.other_scholarships, list) else []
    parts = [str(k) for k in keys if k]
    txt = (getattr(application, 'other_scholarships_text', '') or '').strip()
    if txt:
        parts.append(txt)
    return ', '.join(parts) if parts else 'none mentioned'


def _help_wanted(application):
    """What support the student asked us for on the apply form ('help with…')."""
    wants = []
    if (getattr(application, 'help_university', '') or '') == 'yes':
        wants.append('university applications')
    if (getattr(application, 'help_scholarship', '') or '') == 'yes':
        wants.append('scholarship applications & interviews')
    return ', '.join(wants) if wants else 'none indicated'


def _deliberation(application):
    """When the student is still deciding their pathway — their reasons + their own words."""
    reasons = application.uncertainty_reasons if isinstance(application.uncertainty_reasons, list) else []
    note = (getattr(application, 'uncertainty_note', '') or '').strip()
    bits = []
    if reasons:
        bits.append('reasons: ' + ', '.join(str(r) for r in reasons))
    if note:
        bits.append(note)
    return ' — '.join(bits) if bits else 'not applicable'


def _build_prompt(application, target_language=DEFAULT_LANGUAGE):
    profile = application.profile
    alias = _alias(application)

    def val(v, fallback='not provided'):
        return v if v not in (None, '') else fallback

    def pval(attr, fallback='not provided'):
        return val(getattr(profile, attr, None) if profile else None, fallback)

    cats_str, _months, note = _funding(application)
    ledger = _ledger_verification(application)

    return PROFILE_PROMPT.format(
        redaction=_REDACTION.format(alias=alias),
        style=_STYLE,
        target_language=target_language,
        do_not_claim=_DO_NOT_CLAIM,
        alias=alias,
        pronouns=_pronouns(application),
        school=pval('school'),
        qualification=(pval('exam_type', 'n/a') or 'n/a'),
        merit=_merit(application),
        grades_summary=_grades_summary(profile),
        stpm_pngk=pval('stpm_cgpa', 'n/a'),
        region=_region(profile),
        household_income=pval('household_income'),
        income_evidence=_income_evidence(application),
        household_size=pval('household_size'),
        receives_str=_yesno(getattr(profile, 'receives_str', None) if profile else None),
        receives_jkm=_yesno(getattr(profile, 'receives_jkm', None) if profile else None),
        first_in_family=_gated_first_in_family(application, ledger),
        parents_occupation=val(application.parents_occupation),
        siblings_studying=_siblings_studying_display(application),
        pathway=_pathway(application),
        top_choices=_top_choices(application),
        deliberation=_deliberation(application),
        other_scholarships=_other_scholarships(application),
        help_wanted=_help_wanted(application),
        quiz_interests=_quiz_interests(application),
        aspirations=val(application.aspirations),
        plans=val(application.plans),
        justification=val(application.justification),
        fears=val(application.fears),
        family_context=val(application.family_context),
        daily_life=val(application.daily_life),
        anything_else=val(application.anything_else),
        funding_categories=cats_str,
        funding_note=note,
        qa=_render_qa(application),
    )


REFINE_PROMPT = """You are writing the FINAL profile of a B40 student applying for education \
financial assistance in Malaysia — the conclusive version a sponsor will read.

You are given (1) a DRAFT written from the application, (2) the student's answers to our \
clarifying questions, (3) the officer's interview findings, and (4) the officer's decision. \
Produce ONE coherent final profile that folds them all together.

{redaction}

LANGUAGE — the inputs may be in Malay, English, or Tamil (or a mix); understand their meaning \
and write the profile in {target_language}.

{style}

Pronouns (use these for the student, never "they"): {pronouns}

Rules:
- INCOME: STR/JKM indicate B40 / welfare status, NOT an income amount. State an income figure as
confirmed ONLY if a payslip/EPF or the officer's verdict verified it; otherwise present it as what the
family reports, and never invent who earns what.
- Fold in what the student's answers and the interview CONFIRMED or CLARIFIED; reflect any NEW \
CONCERN honestly and proportionately — do not hide it, do not exaggerate it.
- The officer's decision is the considered outcome of a real review. Present each area with \
confidence matching the four-fact verdict; weave the officer's written conclusion into the close. \
If a recommended assistance amount is set, state it plainly (e.g. "a sponsorship of RM3,000 would \
cover…"). Do NOT print a raw pass/fail list and never contradict the verdict.
- Use ONLY the inputs below; do not invent facts. It must read as one final profile, not a draft \
with notes bolted on.

=== DRAFT PROFILE ===
{draft}

=== THE STUDENT'S ANSWERS TO OUR QUESTIONS ===
{qa}

=== OFFICER'S INTERVIEW FINDINGS ===
{findings}
Interviewer's rubric scores (1-5): {rubric}
Interviewer's overall note: {overall_note}

=== OFFICER'S DECISION ===
{officer_decision}
"""

_VERDICT_LABELS = {
    'resolved': 'resolved at interview',
    'still_unclear': 'still unclear after interview',
    'new_concern': 'new concern raised at interview',
}


def _render_interview(application, session):
    """Render a submitted InterviewSession's findings/rubric/note as plain text for the
    refine prompt. The interviewer's free-text rationale carries the meaning."""
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


_OFFICER_FACT_LABELS = {
    'identity': 'Identity',
    'academic': 'Academic record',
    'pathway': 'Pathway / offer',
    'income': 'Household income (B40 need)',
}


def _render_officer_decision(application):
    """Render the officer's four-fact verdict, written conclusion, and recommended
    assistance amount as plain text — so the FINAL reflects the actual decision."""
    ov = application.officer_verdict if isinstance(application.officer_verdict, dict) else {}
    lines = []
    for fact in ('identity', 'academic', 'pathway', 'income'):
        val = (ov.get(fact) or '').strip()
        if val:
            lines.append(f'- {_OFFICER_FACT_LABELS[fact]}: {val}')
    verdict_str = '\n'.join(lines) if lines else '- not recorded'

    conclusion = (getattr(application, 'verdict_reason', '') or '').strip() or 'none recorded'

    amount = getattr(application, 'award_amount', None)
    if amount in (None, ''):
        assistance = 'not set'
    else:
        try:
            assistance = f'RM{int(round(float(amount)))}'
        except (TypeError, ValueError):
            assistance = str(amount)

    return (
        f'Four-fact verification verdict:\n{verdict_str}\n'
        f'Officer\'s conclusion: {conclusion}\n'
        f'Recommended assistance: {assistance}'
    )


def refine_sponsor_profile(application, draft, session, language=None):
    """Second pass: the FINAL profile, folding the student's answers, the submitted
    interview ``session``, the officer's four-fact verdict, conclusion and recommended
    assistance into ``draft``. Runs on PRO_CASCADE. Returns {'markdown', …} or
    {'error': …}; same graceful-error contract as generate_sponsor_profile."""
    target_language = _resolve_language(application, language)
    findings_str, rubric_str, note = _render_interview(application, session)
    prompt = REFINE_PROMPT.format(
        redaction=_REDACTION.format(alias=_alias(application)),
        style=_STYLE,
        pronouns=_pronouns(application),
        target_language=target_language,
        draft=(draft or '').strip() or 'not provided',
        qa=_render_qa(application),
        findings=findings_str, rubric=rubric_str, overall_note=note,
        officer_decision=_render_officer_decision(application),
    )
    return _call_gemini_text(prompt, target_language, models=PRO_CASCADE)


def generate_sponsor_profile(application, language=None):
    """The DRAFT profile (Gemini Flash). Returns {'markdown', 'model_used', 'language',
    …} or {'error': …}. ``language`` may be a locale code ('en'/'ms') or a name; it
    defaults to the applicant's locale."""
    target_language = _resolve_language(application, language)
    prompt = _build_prompt(application, target_language=target_language)
    return _call_gemini_text(prompt, target_language)
