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

The prompt TEXT lives in `profile_prompts.py` and the per-line INPUT readers in
`profile_inputs.py` (audit sprint A3.6, moved verbatim); both are re-exported below, so every
`from apps.scholarship.profile_engine import ...` and every `mock.patch` of a name here still
works. The prose seam, the cascades, `PROMPT_VERSION`, the claim gates, `_build_prompt` and the
entry points stay here.
"""
import logging
import time

from django.conf import settings

from apps.courses.public import held_summary

from .document_snapshot import SNAPSHOT_ORDER
from .gemini import cascade_failure, document_failure
from .read_errors import UNPARSEABLE_RESPONSE, model_rejected_document
from .shortlisting import count_spm_a_grades
from .profile_inputs import (  # re-exports (A3.6)
    _GROUP_ORDER, _OFFICER_FACT_LABELS, _SIGNAL_CATEGORIES, _SIGNAL_LABELS, _SUBJECT_GROUP,
    _VERDICT_LABELS, _alias, _deliberation, _funding, _grades_summary, _help_wanted,
    _income_evidence, _join_human, _merit, _other_scholarships, _pathway, _pronouns,
    _quiz_interests, _region, _render_interview, _render_officer_decision, _render_qa,
    _reporting_date, _siblings_studying_display, _today_str, _top_choices, _yesno,
)
from .profile_prompts import (  # re-exports (A3.6)
    PROFILE_PROMPT, REFINE_PROMPT, _ABOVE_LINE_EMPHASIS, _ASSISTANCE_NATURE, _BELOW_LINE_AFFIRM,
    _BUCKET_LABELS, _BUCKET_ORDER, _COVERAGE, _EVERGREEN, _REDACTION, _STYLE,
)

logger = logging.getLogger(__name__)

MODEL_CASCADE = ['gemini-2.5-flash', 'gemini-2.5-flash-lite']   # 2.0-flash retired (404), 2026-10-24
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
#   2026-07-08.2 — Owner fixes: (a) WHAT THE ASSISTANCE IS guardrail in both prompts — the support is
#                  a modest FIXED monthly living-cost bursary, never framed as buying a laptop / paying
#                  fees (#110: "enabling her to secure a laptop"). (b) A below-B40-line case now gets a
#                  positive B40-VERIFIED income context (_BELOW_LINE_AFFIRM) so the model can't invent
#                  an "above the standard B40 threshold" claim (#20, RM4,064 < RM5,860 ceiling).
#   2026-07-21.1 — EVERGREEN + sense-of-time (both prompts). Gemini has no innate "now" and read
#                  mid-2026 as the future, writing a live date countdown + wrong relative timing
#                  ("is due to report on 12 July 2026"; "applications open only after her course
#                  begins"). Now (a) TODAY'S date is passed in (`_today_str` → `_EVERGREEN`) so tense/
#                  ordering is correct, and (b) a TIME & DATES rule requires date-proof phrasing — a
#                  reporting/intake date stated as a plain fact of WHEN the place begins, never a
#                  countdown or cross-event relative timing — so a profile doesn't age between reads.
#   2026-10-04.1 — TD-325 (an INPUT change): `Qualification:` is `exam_questions.results_held` (the
#                  results HELD; owner ruling TD-324), not the declared exam — a Form Six explorer
#                  read 'stpm' with nothing behind it.
#   2026-10-25.1 — Third results route S1 (an INPUT change): `Merit score:` is one 0-100 figure on
#                  every route (`exam_questions.merit_100`) — an STPM holder's was the raw PNGK
#                  (3.7), now overall CGPA / 4 x 100 (92.5); the line is labelled "out of 100".
#                  SPM merits are unchanged.
#   2026-10-26.1 — Third results route S2b (route open): `Qualification:` = `held_summary` (S2a), e.g.
#                  "Matriculation (STPM-equivalent), overall CGPA 3.47"; SPM / STPM unchanged.
#   2026-10-28.1 — STPM CGPA C2 (INPUT, STPM only): `STPM PNGK:` = PA + best three; `Merit score:` = overall_from(PNGK, koko) / 4 x 100 (decisions.md 2026-10-28)
PROMPT_VERSION = '2026-10-28.1'   # ⚠ A BUMP RE-DRAFTS EVERY ASSIGNED UNEDITED PROFILE via the daily 04:00 backfill (paid calls) - ask the owner first. 28.1 STPM CGPA C2 (INPUT, STPM only): `STPM PNGK:` = PA + best three; `Merit score:` = overall_from(PNGK, koko) / 4 x 100 (decisions.md 2026-10-28); #62 (2026-11-06) changed the tertiary `SPM grades:` line (the SPM prereq only) WITHOUT a bump, by owner decision


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
    ours, rejected = [], []          # the same split as vision._call_gemini_json (2026-10-24)
    for model_name in (models or MODEL_CASCADE):
        try:
            start = time.time()
            response = client.models.generate_content(model=model_name, contents=prompt)
            elapsed = int((time.time() - start) * 1000)
            from . import usage   # billable Gemini prose call — best-effort meter
            _it, _ot = usage.gemini_tokens(response)
            usage.record_usage(usage.GEMINI, model=model_name, input_tokens=_it, output_tokens=_ot)
            if not (response.text or '').strip():   # answered (billed) with nothing: try the next
                rejected.append((model_name, f'{UNPARSEABLE_RESPONSE}: empty text'))
                continue
            return {
                'markdown': response.text, 'model_used': model_name,
                'language': target_language, 'generation_time_ms': elapsed,
            }
        except Exception as e:
            (rejected if model_rejected_document(e) else ours).append((model_name, str(e)))
            logger.warning('Gemini text generation failed with %s: %s', model_name, e)
            continue
    return {'error': cascade_failure(ours + rejected) if ours else document_failure(rejected)}


def _resolve_language(application, language):
    """Resolve the output language NAME. Accepts a locale code ('en'/'ms') or a
    full name; falls back to the applicant's locale, then English."""
    if language:
        return LANGUAGE_NAMES.get(language, language)
    return LANGUAGE_NAMES.get(getattr(application, 'locale', '') or '', DEFAULT_LANGUAGE)


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
    doc = (application.documents.filter(doc_type='str', superseded_at__isnull=True)
           .order_by(*SNAPSHOT_ORDER).first())
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


def _statement_of_intent(application):
    """The OCR'd plain text of the student's uploaded Statement of Intent letter, if any
    (read on upload into vision_fields['text']). Capped so it informs the draft without
    dominating the prompt; normal PII redaction still applies. 'not provided' when none."""
    doc = (application.documents.filter(doc_type='statement_of_intent', superseded_at__isnull=True)
           .order_by(*SNAPSHOT_ORDER).first())
    text = ''
    if doc is not None and isinstance(getattr(doc, 'vision_fields', None), dict):
        text = (doc.vision_fields.get('text') or '').strip()
    if not text:
        return 'not provided'
    cap = 2000
    return text if len(text) <= cap else text[:cap].rstrip() + ' …'


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
        evergreen=_EVERGREEN.format(today=_today_str()),
        coverage=_COVERAGE,
        assistance_nature=_ASSISTANCE_NATURE,
        target_language=target_language,
        do_not_claim=_DO_NOT_CLAIM,
        alias=alias,
        pronouns=_pronouns(application),
        school=pval('school'),
        # The results we HOLD, not the exam declared (TD-325; owner ruling TD-324: results held =
        # the highest completed qualification). A Form Six explorer is 'spm' here, not 'stpm'.
        qualification=(held_summary(profile) or 'n/a'),
        merit=_merit(application),
        grades_summary=_grades_summary(profile),
        stpm_pngk=pval('stpm_pngk', 'n/a'),     # CGPA sprint C2: from the grades
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


def _with_version(result):
    """Tag a successful generation result with the current PROMPT_VERSION so callers can
    persist it on the SponsorProfile (stale-draft detection)."""
    if isinstance(result, dict) and 'error' not in result:
        result['prompt_version'] = PROMPT_VERSION
    return result


def _income_above_line(application):
    """True when the deterministic verdict flags household income ABOVE the B40 line
    (`income_above_b40_line`) — the signal that gates the extenuating-circumstances emphasis in
    the FINAL profile. Best-effort: any failure to compute the verdict returns False (no emphasis,
    never a crash in the generation path)."""
    try:
        from .verdict_engine import build_verdict
        for fact in (build_verdict(application) or []):
            for item in (fact.get('unresolved') or []):
                if item.get('code') == 'income_above_b40_line':
                    return True
    except Exception:
        pass
    return False


def _income_context(application):
    """The income NOTE fed to the FINAL profile: the extenuating-circumstances emphasis when the
    household reads ABOVE the B40 line, else a positive B40-VERIFIED affirmation (owner 2026-07-08,
    #20) so the model never invents an 'above the B40 threshold' claim for a genuine B40 household."""
    return _ABOVE_LINE_EMPHASIS if _income_above_line(application) else _BELOW_LINE_AFFIRM


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
        evergreen=_EVERGREEN.format(today=_today_str()),
        coverage=_COVERAGE,
        assistance_nature=_ASSISTANCE_NATURE,
        pronouns=_pronouns(application),
        target_language=target_language,
        draft=(draft or '').strip() or 'not provided',
        qa=_render_qa(application),
        findings=findings_str, rubric=rubric_str, overall_note=note,
        officer_decision=_render_officer_decision(application),
        income_context=_income_context(application),
    )
    from . import usage
    with usage.usage_context(application=application, source='profile_refine'):
        return _with_version(_call_gemini_text(prompt, target_language, models=PRO_CASCADE))


def generate_sponsor_profile(application, language=None):
    """The DRAFT profile (Gemini Flash). Returns {'markdown', 'model_used', 'language',
    …} or {'error': …}. ``language`` may be a locale code ('en'/'ms') or a name; it
    defaults to the applicant's locale."""
    target_language = _resolve_language(application, language)
    prompt = _build_prompt(application, target_language=target_language)
    from . import usage
    with usage.usage_context(application=application, source='profile_draft'):
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
    from . import usage
    with usage.usage_context(application=application, source='anon_blurb'):
        res = _call_gemini_text(_build_anon_blurb_prompt(source), 'English')
    if not isinstance(res, dict) or res.get('error'):
        return ''
    return _clip_words((res.get('markdown') or '').strip(), ANON_BLURB_MAX_WORDS)
