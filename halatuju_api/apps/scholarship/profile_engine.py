"""
AI student profile for the BrightPath Bursary Programme.

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

# Prompt version — BUMP on any meaningful change to PROFILE_PROMPT / REFINE_PROMPT or the
# inputs fed to them. Stored on each generated SponsorProfile (`prompt_version`) so a stale
# draft is detectable by VERSION, not by date heuristics (the #18 trap). Generations made
# before versioning existed carry '' (empty) and count as stale.
#   2026-06-16.1 — grades summarised by GROUP (no per-subject list; no ethnicity-revealing
#                  language/literature subjects); prompt versioning introduced.
#   2026-06-16.2 — generalise ethnicity in the NARRATIVE too (keep the motivation, drop the
#                  ethnic label, e.g. "her mother tongue" not "Tamil"; "a teacher" not
#                  "her Tamil teacher").
#   2026-06-18.1 — Income honesty, both directions (documented = certain; self-reported = a claim).
#                  (a) STR/JKM asserted ONLY when a welfare DOCUMENT is on file — fixes #21 (profile
#                  asserted STR "affirming B40 status" off a self-declared tick, salary route, no STR
#                  doc; see _gated_str / _gated_jkm). (b) A DOCUMENTED salary (payslip/EPF) MUST be
#                  stated as documented, not buried behind the softer reported figure — fixes #10
#                  (payslip gross RM3,049 ignored in favour of the reported RM1,700).
#   2026-06-29.1 — Sponsor-framework restructure (reviewer-query automation S5). Both the draft and
#                  the refine now organise the prose around the sponsor's three "need to know" areas —
#                  FINANCIAL NEED / ACADEMIC COMMITMENT & RESILIENCE / PATHWAY & ENROLMENT CONFIDENCE
#                  (the same buckets gap_engine tags interview gaps with) — woven into the narrative,
#                  still no headings/lists. The refine groups the interview findings by their bucket
#                  so each lands in the matching area, so the profile a sponsor reads checks the boxes.
#   2026-06-29.2 — Owner polish on the sponsor-facing read: (a) feed the offer's REPORTING DATE into
#                  the pathway block so it can appear in the enrolment-confidence part; (b) the profile
#                  no longer states any monetary AMOUNT (the recommended sum is shown separately as a
#                  header figure) and no longer ADVOCATES ("strongly recommended", "deserving") — a
#                  sponsor skims many profiles, so it just describes factually what the support helps
#                  with. Amount dropped from the refine inputs + instruction; no-amount/no-advocacy in
#                  the shared style.
PROMPT_VERSION = '2026-06-29.2'

# Shared narrative + privacy instructions (the same single profile for reviewer + sponsor).
_STYLE = (
    "Write warm, factual, flowing prose: about three short paragraphs, roughly 220-320 "
    "words, with NO section headings and NO bullet lists. Tell the story so a reader "
    "understands, in turn: the family's situation and why the assistance is genuinely "
    "needed; the student's academic standing and the commitment and resilience behind it; "
    "and the pathway ahead, including the confirmed place, when the student is due to report, "
    "and how ready and committed they are to take it up. Refer to the student as 'he' or 'she' "
    "using the pronouns given "
    "below; NEVER use 'they' for the student (most people write he/she). Use em-dashes very "
    "sparingly, at most one in the whole profile; prefer commas, full stops or brackets. Let "
    "the facts carry the case: do NOT use fundraising clichés such as 'breaking the cycle', "
    "'ripple effect' or 'pioneering spirit', and do NOT invent specifics (an age, a "
    "relationship, a figure) not given below. Where a fact is missing, leave it out rather "
    "than guess. "
    "Do NOT state any monetary amount or recommended sum — that figure is shown separately to "
    "the reader; instead describe concretely and factually what the support would help the "
    "student with. Do NOT advocate or editorialise (no 'strongly recommended', 'a deserving "
    "candidate', 'we urge you to support'); the reader reviews many profiles, so let the facts "
    "speak for themselves."
)

_REDACTION = (
    "PRIVACY — this single profile is read by the reviewer AND, once the student is "
    "approved, by external sponsors, so it must never expose contact or identity details. "
    "Refer to the student ONLY by the alias \"{alias}\"; never invent or include a name. For "
    "the student AND any parent or guardian, NEVER include their name, NRIC/IC number, "
    "photograph, phone number, email address, or street address — if any appears in the "
    "inputs below, omit it. Everything else may be used: the school or college name, the "
    "town and state, the institution, and occupations. "
    "ETHNICITY — do NOT reveal or imply the student's ethnicity, race or religion, even when "
    "the student's own words do. KEEP the meaning but GENERALISE any ethnic/cultural specific: "
    "write \"her mother tongue\" or \"her community's language and culture\" rather than naming "
    "a language (e.g. Tamil, Mandarin/Chinese), and \"a teacher who inspired her\" rather than "
    "\"her Tamil teacher\". Never name a vernacular-language or literature subject. A culturally "
    "specific aspiration (e.g. to teach her mother tongue) is kept as a motivation, just "
    "without the ethnic label."
)

# The sponsor's three "need to know" areas — the same buckets gap_engine tags interview gaps
# with. The profile must answer all three; the refine groups interview findings under these so
# each lands in the matching part of the narrative. Output stays prose (no headings/lists) — this
# is a COVERAGE instruction, not a layout one.
_BUCKET_LABELS = {
    'financial_need': 'Financial need',
    'academic_resilience': 'Academic commitment & resilience',
    'pathway_confidence': 'Pathway & enrolment confidence',
    'other': 'Other points raised',
}
_BUCKET_ORDER = ['financial_need', 'academic_resilience', 'pathway_confidence', 'other']

_COVERAGE = (
    "WHAT A SPONSOR NEEDS TO KNOW — this profile must answer, across its flowing paragraphs "
    "(still NO headings and NO lists), the three things a sponsor weighs. Give EACH its due and "
    "weave it into the story rather than labelling it:\n"
    "1. FINANCIAL NEED — the family's circumstances and why the assistance genuinely matters: who "
    "earns and who does not, the reported and any documented household income, the dependants, and "
    "the specific costs the support would meet.\n"
    "2. ACADEMIC COMMITMENT & RESILIENCE — how the student has performed and persevered: the "
    "results, the effort and obstacles behind them, and the drive they show.\n"
    "3. PATHWAY & ENROLMENT CONFIDENCE — that the next step is clear and within reach: the "
    "programme and institution, whether a place is held, the reporting date if known, and how ready "
    "and committed the student is to take it up.\n"
    "Where the inputs leave one area thin, state honestly what IS known and do not invent — but do "
    "not silently drop a whole area the sponsor is counting on."
)

PROFILE_PROMPT = """You are writing the profile of a B40 student applying for education \
financial assistance in Malaysia. It is read first by the reviewer assessing the application, \
and later by a prospective sponsor.

{redaction}

LANGUAGE — the student's own words below may be in Malay, English, or Tamil (or a mix); \
understand their meaning whichever language they are in, and write the profile in {target_language}.

{style}

{coverage}

VERIFICATION — do not over-claim:
- Some fields are marked "{do_not_claim}" — NOT verified. Do not assert them; omit them.
- ACADEMICS — give a brief SUMMARY only, never a list. State the number of A-grade subjects, the \
band mix, and the broad subject GROUPS they span exactly as provided below (e.g. "ten A-grade \
subjects across A+/A/A−, spanning the sciences, mathematics and languages"). Do NOT enumerate \
individual subjects or per-subject grades — a reader skips a long list. NEVER name a specific \
language or literature subject (e.g. Bahasa Tamil, Bahasa Cina, Kesusasteraan Tamil/Cina), and do \
NOT state or imply the student's ethnicity or race. Never round up or imply a uniform top grade. If \
a merit score is given, you may cite it.
- INCOME & WELFARE — DOCUMENTED is certain; everything self-reported is a CLAIM. If "Documented \
income (payslip/EPF)" below lists one or more figures, you MUST state them AUTHORITATIVELY as the \
documented income, naming the document and whose income it is — do NOT omit a documented figure or \
bury it behind the softer reported household figure. EVERY other income figure — including the \
household income below — is only what the family REPORTS: present it as such (e.g. "the family \
reports about RM…") and you MAY give it as context alongside the documented figure (e.g. base pay \
vs a month with overtime), but never as "confirmed", and do NOT attribute a reported figure to a \
specific earner or invent a breakdown. STR/JKM are gated the SAME way: a value of "yes" means a welfare DOCUMENT is on file, so \
you MAY state the family receives it (this confirms B40 status, NOT an income figure). Any other \
value ("no" or "not established — do not claim") means there is NO proof on file — do NOT mention \
STR/JKM at all and do NOT use it to affirm B40 status. If who earns what is unclear, describe the \
situation (a single earner, a parent unable to work) without inventing numbers. Do not make up a \
story to reconcile the figures.

THE STUDENT (alias {alias})
Pronouns (use these for the student, never "they"): {pronouns}
School / college: {school}
Qualification: {qualification}    Merit score: {merit}
SPM grades: {grades_summary}    STPM PNGK: {stpm_pngk}
Home town / state: {region}
Household income (RM/month, as reported): {household_income}    Household size: {household_size}
Documented income (payslip/EPF — use authoritatively if present): {income_evidence}
Receives STR ('yes' only when a current STR document is on file; else do not claim): {receives_str}    Receives JKM (same rule): {receives_jkm}
First in family to university: {first_in_family}
Parents'/guardians' occupation: {parents_occupation}
Siblings currently studying: {siblings_studying}

Pathway / programme (use the confirmed place when present): {pathway}
Reporting / enrolment date (when the student must report to begin; state it if given): {reporting_date}
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
Statement of Intent letter (student's uploaded letter, OCR'd — distil its substance): {statement_of_intent}

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


def _gated_str(application):
    """STR receipt is asserted as fact ONLY when a CURRENT STR document is on file —
    documented = certain. A self-declared STR tick with no document (e.g. a salary-route
    applicant who never uploaded an STR), or a stale/rejected one, is NOT established:
    the writer must not claim it (the live #21 bug — the profile asserted STR while the
    student was on the salary route with no STR doc on file)."""
    profile = getattr(application, 'profile', None)
    if not (profile and getattr(profile, 'receives_str', None)):
        return 'no'
    from .income_engine import student_str_check
    doc = application.documents.filter(doc_type='str').order_by('-uploaded_at').first()
    if not doc:
        return _DO_NOT_CLAIM
    chk = student_str_check(doc)
    return 'yes' if chk and chk.get('current_status') == 'current' else _DO_NOT_CLAIM


def _gated_jkm(application):
    """JKM receipt: no JKM document is collected anywhere in the flow, so a self-declared
    JKM tick can never be independently documented. By the documented = certain rule it is
    NOT established — the writer must not assert it as fact."""
    profile = getattr(application, 'profile', None)
    if not (profile and getattr(profile, 'receives_jkm', None)):
        return 'no'
    return _DO_NOT_CLAIM


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


def _reporting_date(application):
    """The offer's normalised reporting/enrolment date (S3 `reporting_date`), as
    '13 May 2026'. Lets the profile state when the student is due to report — part of the
    pathway & enrolment-confidence picture a sponsor weighs. 'not provided' when unknown."""
    d = getattr(application, 'reporting_date', None)
    if not d:
        return 'not provided'
    try:
        return f'{d.day} {d:%B %Y}'
    except (AttributeError, ValueError):
        return 'not provided'


def _siblings_studying_display(application):
    count = getattr(application, 'siblings_studying_count', None)
    return str(count) if count is not None else ''


def _income_evidence(application):
    """Documented monthly income read from any salary slip / EPF on file — usable
    authoritatively even on the STR track (a student may submit payslips/EPF as extra
    proof). Covers the salary-route members AND the STR-route earner. 'none on file' when
    no readable income document exists, so the model falls back to the reported figure."""
    # Code-health S4 #16: use effective_working_members — the #90 fix (prefill accepted
    # but never persisted leaves income_working_members empty while the docs exist) was
    # applied to verdict_engine + the blockers but this call site was missed, so the
    # sponsor/reviewer profile said "Documented income: none on file" over a readable slip.
    from .income_engine import effective_working_members, earner_monthly_income
    members = list(effective_working_members(application))
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


# Subject key → broad GROUP. We summarise results by group, never by individual subject:
# it keeps the profile readable AND avoids revealing ethnicity via a vernacular-language or
# literature subject (Bahasa Tamil/Cina, Kesusasteraan Tamil/Cina all fold into "languages"/
# "humanities"). Keys mirror the canonical list in halatuju-web/src/lib/subjects.ts. Any key
# not listed falls back to the generic "other subjects" — a raw key can never reach the prompt.
_SUBJECT_GROUP = {
    'math': 'mathematics', 'addmath': 'mathematics',
    'sci': 'sciences', 'science': 'sciences', 'addsci': 'sciences', 'phy': 'sciences',
    'chem': 'sciences', 'bio': 'sciences', 'comp_sci': 'sciences', 'sports_sci': 'sciences',
    'srt': 'sciences',
    'bm': 'languages', 'eng': 'languages', 'b_cina': 'languages', 'b_tamil': 'languages',
    'bahasa_cina': 'languages', 'bahasa_tamil': 'languages', 'bahasa_arab': 'languages',
    'bahasa_arab_tinggi': 'languages', 'bahasa_iban': 'languages',
    'bahasa_kadazandusun': 'languages', 'bahasa_semai': 'languages',
    'bahasa_punjabi': 'languages', 'bahasa_perancis': 'languages', 'bahasa_jepun': 'languages',
    'bahasa_jerman': 'languages',
    'hist': 'humanities', 'history': 'humanities', 'moral': 'humanities',
    'lit_bm': 'humanities', 'lit_eng': 'humanities', 'lit_cina': 'humanities',
    'lit_tamil': 'humanities', 'sejarah_seni': 'humanities', 'islam': 'humanities',
    'agama': 'humanities', 'pqs': 'humanities', 'psi': 'humanities',
    'tasawwur_islam': 'humanities', 'usul_aldin': 'humanities', 'al_syariah': 'humanities',
    'manahij': 'humanities', 'bible_knowledge': 'humanities',
    'geo': 'social sciences', 'ekonomi': 'social sciences', 'econ': 'social sciences',
    'poa': 'social sciences', 'acc': 'social sciences', 'business': 'social sciences',
    'keusahawanan': 'social sciences',
    'psv': 'the arts', 'music': 'the arts', 'lukisan': 'the arts', 'multimedia': 'the arts',
    'digital_gfx': 'the arts', 'reka_cipta': 'the arts', 'gkt': 'the arts',
    'eng_civil': 'technical subjects', 'eng_mech': 'technical subjects',
    'eng_elec': 'technical subjects', 'eng_draw': 'technical subjects',
    'lukisan_kejuruteraan': 'technical subjects', 'kelestarian': 'technical subjects',
    'pertanian': 'technical subjects',
}
_GROUP_ORDER = ['sciences', 'mathematics', 'languages', 'social sciences', 'humanities',
                'the arts', 'technical subjects', 'other subjects']


def _join_human(items):
    """['a','b','c'] -> 'a, b and c'."""
    items = list(items)
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def _grades_summary(profile):
    """Summarise SPM results WITHOUT naming individual subjects: the count of A-grade
    subjects, the band mix, and the broad subject GROUPS they span. Keeps the profile
    readable and avoids revealing ethnicity via vernacular-language/literature subjects.
    'not provided' when no grades."""
    grades = getattr(profile, 'grades', None) if profile else None
    if not isinstance(grades, dict) or not grades:
        return 'not provided'
    bands = {'A+': 0, 'A': 0, 'A-': 0}
    total = 0
    groups_seen = set()
    for key, grade in grades.items():
        if not grade:
            continue
        total += 1
        g = str(grade).strip().upper().replace('−', '-')   # normalise unicode minus
        if g in bands:
            bands[g] += 1
            groups_seen.add(_SUBJECT_GROUP.get(str(key).lower(), 'other subjects'))
    a_count = bands['A+'] + bands['A'] + bands['A-']
    if a_count == 0:
        return f'{total} subjects sat; no A-grade subjects recorded'
    band_bits = [f'{bands[b]} {b.replace("-", "−")}' for b in ('A+', 'A', 'A-') if bands[b]]
    groups = _join_human([g for g in _GROUP_ORDER if g in groups_seen])
    spanning = f' spanning {groups}' if groups else ''
    return f'{a_count} A-grade subjects out of {total} ({", ".join(band_bits)}){spanning}'


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


def _statement_of_intent(application):
    """The OCR'd plain text of the student's uploaded Statement of Intent letter, if any
    (read on upload into vision_fields['text']). Capped so it informs the draft without
    dominating the prompt; normal PII redaction still applies. 'not provided' when none."""
    doc = (application.documents.filter(doc_type='statement_of_intent')
           .order_by('-uploaded_at').first())
    text = ''
    if doc is not None and isinstance(getattr(doc, 'vision_fields', None), dict):
        text = (doc.vision_fields.get('text') or '').strip()
    if not text:
        return 'not provided'
    cap = 2000
    return text if len(text) <= cap else text[:cap].rstrip() + ' …'


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
        coverage=_COVERAGE,
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
        receives_str=_gated_str(application),
        receives_jkm=_gated_jkm(application),
        first_in_family=_gated_first_in_family(application, ledger),
        parents_occupation=val(application.parents_occupation),
        siblings_studying=_siblings_studying_display(application),
        pathway=_pathway(application),
        reporting_date=_reporting_date(application),
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
        statement_of_intent=_statement_of_intent(application),
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

{coverage}

Pronouns (use these for the student, never "they"): {pronouns}

Rules:
- INCOME: documented = certain, self-reported = a claim. When the draft or the officer's findings
state a DOCUMENTED income (payslip/EPF), keep it and state it as documented — do not soften it into a
mere report. State any OTHER income figure as confirmed ONLY if the officer's verdict verified it;
otherwise present it as what the family reports, and never invent who earns what. Do NOT assert the
family receives STR/JKM unless the DRAFT or the officer's findings establish it from a document —
never re-introduce a welfare claim the draft omitted.
- Fold in what the student's answers and the interview CONFIRMED or CLARIFIED; reflect any NEW \
CONCERN honestly and proportionately — do not hide it, do not exaggerate it. The interview findings \
below are grouped under the three sponsor areas (financial need / academic commitment & resilience / \
pathway & enrolment confidence) — weave each finding into the matching part of the narrative.
- The officer's decision is the considered outcome of a real review. Present each area with \
confidence matching the four-fact verdict; weave the officer's written conclusion into the close. \
Do NOT state any monetary amount or recommended sum — that figure is shown separately to the sponsor; \
instead describe concretely what the support would help the student with. Do NOT advocate or use \
recommendation language ("strongly recommended", "a deserving candidate"). Do NOT print a raw \
pass/fail list and never contradict the verdict.
- If the draft states a reporting / enrolment date, keep it in the pathway part of the narrative.
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
    refine prompt, GROUPED under the sponsor's three areas (the S4 gap `bucket`) so each
    finding lands in the matching part of the narrative. The interviewer's free-text
    rationale carries the meaning; a finding whose gap has no bucket falls under 'other'."""
    gaps_by_code, bucket_by_code = {}, {}
    for g in (application.interview_gaps or []):
        if isinstance(g, dict) and g.get('code'):
            gaps_by_code[g['code']] = g.get('question', '')
            bucket_by_code[g['code']] = (g.get('bucket') or 'other')

    grouped = {}
    for code, val in (session.findings or {}).items():
        if not isinstance(val, dict):
            continue
        verdict = _VERDICT_LABELS.get(val.get('verdict', ''), val.get('verdict', '') or 'noted')
        rationale = (val.get('rationale') or '').strip()
        context = gaps_by_code.get(code, '')
        prefix = f'On "{context}" — ' if context else ''
        bucket = bucket_by_code.get(code, 'other')
        if bucket not in _BUCKET_LABELS:
            bucket = 'other'
        grouped.setdefault(bucket, []).append(f'- [{verdict}] {prefix}{rationale}'.rstrip())

    if grouped:
        sections = [f'{_BUCKET_LABELS[b]}:\n' + '\n'.join(grouped[b])
                    for b in _BUCKET_ORDER if grouped.get(b)]
        findings_str = '\n'.join(sections)
    else:
        findings_str = 'No specific findings recorded.'

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
    """Render the officer's four-fact verdict and written conclusion as plain text — so the
    FINAL reflects the actual decision. The monetary amount is deliberately NOT included: the
    recommended sum is shown to the sponsor separately (a header figure), and the profile prose
    must not state it or advocate (owner decision 2026-06-29)."""
    ov = application.officer_verdict if isinstance(application.officer_verdict, dict) else {}
    lines = []
    for fact in ('identity', 'academic', 'pathway', 'income'):
        val = (ov.get(fact) or '').strip()
        if val:
            lines.append(f'- {_OFFICER_FACT_LABELS[fact]}: {val}')
    verdict_str = '\n'.join(lines) if lines else '- not recorded'

    conclusion = (getattr(application, 'verdict_reason', '') or '').strip() or 'none recorded'

    return (
        f'Four-fact verification verdict:\n{verdict_str}\n'
        f"Officer's conclusion: {conclusion}"
    )


def _with_version(result):
    """Tag a successful generation result with the current PROMPT_VERSION so callers can
    persist it on the SponsorProfile (stale-draft detection)."""
    if isinstance(result, dict) and 'error' not in result:
        result['prompt_version'] = PROMPT_VERSION
    return result


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
        coverage=_COVERAGE,
        pronouns=_pronouns(application),
        target_language=target_language,
        draft=(draft or '').strip() or 'not provided',
        qa=_render_qa(application),
        findings=findings_str, rubric=rubric_str, overall_note=note,
        officer_decision=_render_officer_decision(application),
    )
    return _with_version(_call_gemini_text(prompt, target_language, models=PRO_CASCADE))


def generate_sponsor_profile(application, language=None):
    """The DRAFT profile (Gemini Flash). Returns {'markdown', 'model_used', 'language',
    …} or {'error': …}. ``language`` may be a locale code ('en'/'ms') or a name; it
    defaults to the applicant's locale."""
    target_language = _resolve_language(application, language)
    prompt = _build_prompt(application, target_language=target_language)
    return _with_version(_call_gemini_text(prompt, target_language))


# ── Sponsor-pool CARD blurb (card-strict: stricter than the profile) ──────────
ANON_BLURB_MAX_WORDS = 20


def _clip_words(text, n):
    """Collapse whitespace, drop stray wrapping quotes, and cap to ``n`` words."""
    text = ' '.join((text or '').split()).strip('"“”‘’\'')
    words = text.split(' ')
    if len(words) <= n:
        return text
    return ' '.join(words[:n]).rstrip(',;:') + '…'


def _build_anon_blurb_prompt(source):
    return (
        'You write a one-line card summary for a donor browsing students to support.\n\n'
        f'From the anonymous profile below, write ONE plain sentence of AT MOST {ANON_BLURB_MAX_WORDS} '
        "words, in English, third person, capturing the student's circumstances and what the support "
        'helps with.\n'
        'STRICT RULES:\n'
        '- NEVER include any name, alias, code, school, town, city, state, institution, or any number.\n'
        '- No markdown, no quotes, no labels — output only the sentence.\n'
        '- Warm but factual; never invent anything beyond the profile.\n\n'
        f'PROFILE:\n{source}\n'
    )


def generate_anon_blurb(application, anon_markdown=''):
    """A ≤20-word, CARD-STRICT donor-facing one-liner for the sponsor-pool card, derived
    from the already-anonymous ``anon_markdown``. Returns '' on any engine error or empty
    input (the card then falls back to course-only). The CALLER must still backstop the
    result with ``pool.scan_anon_for_identifiers`` before persisting — this is generation,
    not the safety boundary."""
    source = (anon_markdown or '').strip()
    if not source:
        return ''
    res = _call_gemini_text(_build_anon_blurb_prompt(source), 'English')
    if not isinstance(res, dict) or res.get('error'):
        return ''
    return _clip_words((res.get('markdown') or '').strip(), ANON_BLURB_MAX_WORDS)
