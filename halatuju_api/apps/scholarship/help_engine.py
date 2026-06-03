"""Document-help coach — "Cikgu Gopal".

A warm, encouraging helper for the student on the /application **Documents** tab. When an
uploaded document comes back with a soft mismatch (the deterministic matchers / Vision OCR
already decided the verdict), Cikgu Gopal explains — in 2-3 kind sentences — *why* the document
needs what it needs and nudges the student to try again.

Design guarantees (see docs/decisions.md + the sprint plan):
- **Coach, never ghostwriter.** The prompt forbids drafting the student's application answers.
- **Never leaks admin data.** The engine receives ONLY a doc type + the already-decided verdict
  code + the student's first name. There is NO parameter through which a score, sponsor profile,
  interview, or reviewer note could reach it — the firewall is *structural*, not prompt-trust.
- **Only phrases, never decides.** The verdict is computed upstream by the deterministic matchers
  (vision.doc_student_verdict / the IC nric/name matchers); this module just puts a kind voice on it.
- **Soft, never blocks.** On any AI failure / throttle the caller falls back to pre-written i18n
  copy keyed by the verdict — the student is never left with a cold, silent chip.

Reuses ``profile_engine._call_gemini_text`` (the single mockable Gemini prose seam) — every test
patches that one function, so CI runs with zero billable calls.
"""
import logging

from .profile_engine import DEFAULT_LANGUAGE  # noqa: F401  (re-exported for callers/tests)

logger = logging.getLogger(__name__)

PERSONA = 'Cikgu Gopal'

# The factual cause hint fed to the model per verdict code. The verdict itself is decided
# upstream (deterministic); this only tells Cikgu Gopal what to talk about. The set of keys
# IS the contract the frontend shares (its fallback copy is keyed by the same codes).
VERDICT_GUIDANCE = {
    'name_mismatch':   "the name we read on this document did not match the name saved in the applicant's profile",
    'nric_mismatch':   "the IC number we read did not match the IC number in the applicant's profile",
    'address_mismatch': "the home address on this bill did not match the address on file",
    'wrong_doc':       "this file did not look like the kind of document expected in this slot",
    'unreadable':      "we could not read this document clearly — it may be blurry, dark, or low-resolution",
    'review_manually': "we could not auto-check this one right now; a reviewer will look at it by hand",
    # Results-slip specific (the three academic checks: name / subjects / results).
    'slip_name_mismatch':    "the name on this results slip is not the applicant's — it looks like it may be someone else's slip",
    'slip_subjects_missing': "the results slip lists one or more subjects that were not entered in the applicant's profile",
    'slip_grade_mismatch':   "one or more grades on the results slip differ from the grades the applicant typed into their profile",
    # Offer-letter (pathway): the name and/or IC on the letter are not the applicant's.
    'offer_name_mismatch':   "the name and/or IC number on this offer letter are not the applicant's — it looks like it may be someone else's offer letter",
    # Offer-letter (pathway): the offer is for a different college/programme than declared.
    'offer_pathway_mismatch': "the college or programme on this offer letter looks different from the study choice the applicant entered earlier when they applied",
}

# Per-verdict fix advice. Most verdicts just need a re-upload; a NAME mismatch is
# bidirectional — either the photo was misread OR the student typed their name
# slightly differently when they registered — so Cikgu Gopal must offer BOTH paths.
DEFAULT_FIX_HINT = ('Gently suggest the likely fix (for example, check you uploaded the '
                    'right page/details clearly, then upload again).')
VERDICT_FIX_HINT = {
    'name_mismatch': (
        'A name mismatch can happen TWO ways, so kindly offer BOTH fixes and let the '
        'student decide which is right: (1) if the photo is blurry, dark, or cut off, '
        'they should upload a clearer one; (2) if the name printed on the card is actually '
        'correct, then the name they typed when registering may have a small spelling '
        'difference — they can fix it on their Profile page. Do NOT assume which one is '
        "wrong — the card might be right and the typed name wrong, or the other way round."
    ),
    'slip_name_mismatch': (
        'This is almost always the WRONG FILE: kindly suggest they check they uploaded '
        'THEIR OWN results slip (not a sibling\'s or friend\'s) — the name on the slip must '
        'match their own name. Ask them to re-upload their own slip.'
    ),
    'slip_subjects_missing': (
        'The fix is to make their profile match the slip: kindly tell them to add the '
        'missing subject(s) on their Profile page so their entered subjects match the '
        'results slip. (If the slip itself is the wrong file, they can re-upload instead.)'
    ),
    'slip_grade_mismatch': (
        'The results slip is the official record, so the fix is to make the PROFILE match '
        'the slip: kindly tell them to update the differing grade(s) on their Profile page '
        'so they match the slip. Only if the photo is blurry should they upload a clearer '
        'slip instead. Never suggest changing the slip itself.'
    ),
    'offer_name_mismatch': (
        'This is almost always the WRONG FILE: kindly suggest they check they uploaded '
        'THEIR OWN offer letter (not a sibling\'s or friend\'s) — the name and IC number on '
        'the letter must be their own. Ask them to re-upload their own offer letter.'
    ),
    'offer_pathway_mismatch': (
        'This is NOT a problem and never blocks the application — reassure them firmly. '
        'It is completely normal for plans to change. Explain gently that if THIS offer is '
        'the path they are really taking, that is absolutely fine — they do not need to do '
        'anything now; when they submit, we will simply ask them to confirm it and we will '
        'update their record to match the offer. Do NOT tell them to re-upload or to edit '
        'anything, and do NOT imply they made a mistake.'
    ),
}

# Friendly, plain-language label per document type (only the types that can get a coach note).
READABLE_DOC = {
    'ic': 'identity card (IC)',
    'parent_ic': "parent or guardian's identity card (IC)",
    'results_slip': 'examination results slip',
    'str': 'STR / financial-aid document',
    'salary_slip': 'salary slip',
    'epf': 'EPF statement',
    'water_bill': 'water bill',
    'electricity_bill': 'electricity bill',
    'offer_letter': 'university/college offer letter',
    'statement_of_intent': 'statement of intent',
    'guardianship_letter': 'guardianship letter',
}

# Plain-language briefing so Cikgu Gopal "knows the programme" — the same public information
# already on the page. NO admin/reviewer detail (deliberately — see the structural firewall).
PROGRAMME_BRIEFING = """ABOUT THE PROGRAMME (so you can explain it kindly):
- The programme is the **B40 Assistance Programme** — a financial-assistance scheme for Malaysian \
school-leavers. Always call it the "B40 Assistance Programme"; never call it "HalaTuju" or a "scholarship".
- The student's journey: apply -> they may be shortlisted -> they complete their profile, upload \
documents, and give consent -> a person reviews it -> a decision is sent by email.
- Why documents are needed: the identity card (IC) proves who the student is; the results slip \
shows their achievement; income documents (salary slip, EPF, STR) and utility bills (water, \
electricity) help show the family's financial need so support reaches those who need it most.
- A document mismatch is normal and easily fixed — it is NOT a rejection and does NOT lower the \
student's chances. Uploads are never blocked; the student can simply re-upload a clearer or \
correct file."""

HELP_PROMPT = """You are {persona}, a clear and friendly Malaysian teacher ("cikgu") helping a \
student upload their documents for their B40 Assistance Programme application. Be warm but \
matter-of-fact — a calm, practical cikgu, not a fussing parent.

{programme_briefing}

THE SITUATION RIGHT NOW:
- The student just uploaded their {doc_label}.
- Our automatic check found that {cause}.
- The student's first name is: {first_name}

YOUR REPLY:
- Write 2-3 short, plain, friendly sentences in {target_language}, addressed to the student by their first name.
- Reassure them this is common and fixable, and explain simply WHY this document needs what it needs.
- {fix_hint}
- End on an encouraging note.

HARD RULES (these override everything else):
- Address the student by their FIRST NAME only. Do NOT use pet names or endearments \
(no "dear", "sayang", "my dear", "sweetheart", etc.).
- You are a COACH, not a ghost-writer. NEVER write, draft, compose, or suggest the wording of the \
student's application answers, essays, personal statements, or any field they must fill in \
themselves. If they ask you to write something for them, kindly decline and encourage them to \
write it in their own words.
- You do NOT have access to any scores, rankings, reviewers' notes, or the application's outcome, \
and you must NEVER reveal, guess, or invent them. If asked "what's my score?" or "will I get it?", \
warmly explain you cannot see that and steer back to the document.
- Use ONLY the situation above. Do not invent facts about the student or the document.
- Plain text only (no Markdown headings, no lists). Just the kind little message."""


def first_name_of(doc):
    """The applicant's first name for a warm greeting — their OWN data (not admin)."""
    name = (getattr(getattr(doc.application, 'profile', None), 'name', '') or '').strip()
    return name.split()[0] if name else ''


def verdict_for_document(doc):
    """Map a document's already-computed signals to a single help-verdict code, or ''
    when there is nothing to help with. Reads ONLY the student's own document + profile
    (never admin data) and re-uses the same deterministic matchers the chip/serializer
    use — this module phrases the verdict, it does not invent one. Mirrors the frontend
    chip precedence."""
    if doc.doc_type in ('ic', 'parent_ic'):
        if doc.vision_run_at is None:
            return ''
        if doc.vision_error or not doc.vision_nric:
            return 'unreadable'
        from .vision import name_match, nric_match
        profile = getattr(doc.application, 'profile', None)
        if not nric_match(doc.vision_nric, getattr(profile, 'nric', '') or ''):
            return 'nric_mismatch'
        if doc.vision_name and name_match(doc.vision_name, getattr(profile, 'name', '') or '') == 'mismatch':
            return 'name_mismatch'
        return ''
    # Results slip — the three clinical checks (name / subjects / results), most
    # important first: a wrong-person slip, then a missing subject, then a grade that
    # disagrees with the typed profile. Computed by the SAME engine the FE checklist
    # uses (academic_engine.student_slip_check) so the coach and the checklist agree.
    if doc.doc_type == 'results_slip':
        fields = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
        sv = fields.get('student_verdict')
        if not sv:
            return ''                        # not field-extracted yet → no coach
        if sv == 'wrong_doc':
            return 'wrong_doc'
        if sv in ('unreadable', 'review_manually'):
            return sv
        from .academic_engine import student_slip_check
        chk = student_slip_check(doc)
        if chk['name'] == 'mismatch':
            return 'slip_name_mismatch'
        if chk['name'] == 'unreadable':
            return 'unreadable'
        if chk['subjects'] == 'mismatch':
            return 'slip_subjects_missing'
        if chk['results'] == 'mismatch':
            return 'slip_grade_mismatch'
        # Gemini read the slip but couldn't pull the subject table → ask for a clearer copy.
        if chk['subjects'] == 'unreadable' or chk['results'] == 'unreadable':
            return 'unreadable'
        return ''
    # Offer letter (pathway) — name + IC are the identity checks; a mismatch on either
    # means a wrong-person letter. (Richer pathway-aware coaching is a later pass.)
    if doc.doc_type == 'offer_letter':
        fields = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
        sv = fields.get('student_verdict')
        if not sv:
            return ''
        if sv == 'wrong_doc':
            return 'wrong_doc'
        if sv in ('unreadable', 'review_manually'):
            return sv
        from .pathway_engine import student_offer_check
        chk = student_offer_check(doc)
        if chk['ic'] == 'mismatch' or chk['name'] == 'mismatch':
            return 'offer_name_mismatch'
        # Identity is fine but the offer is for a different college/programme than
        # declared — a SOFT nudge (never a block): "you may confirm this when you submit".
        if chk['pathway'] == 'mismatch':
            return 'offer_pathway_mismatch'
        return ''
    # Other supporting docs — the Gemini doc-assist verdict takes precedence (it is the
    # chip the frontend shows); fall back to the older soft full-text checks when it never ran.
    fields = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    sv = fields.get('student_verdict')
    if sv:
        return '' if sv == 'ok' else (sv if sv in VERDICT_GUIDANCE else '')
    if doc.vision_name_match == 'not_found':
        return 'name_mismatch'
    if doc.vision_address_match == 'not_found':
        return 'address_mismatch'
    if 'unreadable' in (doc.vision_name_match, doc.vision_address_match):
        return 'unreadable'
    return ''


def _doc_label(doc_type):
    return READABLE_DOC.get(doc_type, (doc_type or 'document').replace('_', ' '))


def _build_help_prompt(doc_type, verdict, first_name, target_language=DEFAULT_LANGUAGE):
    """Pure prompt builder — unit-tested directly (the guardrail/firewall assertions read this
    string). It can ONLY see the four arguments, so no admin data can appear in it."""
    return HELP_PROMPT.format(
        persona=PERSONA,
        programme_briefing=PROGRAMME_BRIEFING,
        doc_label=_doc_label(doc_type),
        cause=VERDICT_GUIDANCE.get(verdict, ''),
        fix_hint=VERDICT_FIX_HINT.get(verdict, DEFAULT_FIX_HINT),
        first_name=(first_name or '').strip() or 'there',
        target_language=target_language,
    )


def generate_document_help(doc_type, verdict, *, first_name='', target_language=DEFAULT_LANGUAGE):
    """Return {'message', 'source', ...}. ``source`` is:
    - 'none'     — nothing to help with (good/absent verdict); no Gemini call made.
    - 'ai'       — a warm message from Gemini (also returns 'model_used').
    - 'fallback' — Gemini was unavailable/empty; caller should use pre-written i18n copy.

    Never raises. Soft by construction."""
    verdict = (verdict or '').strip()
    if verdict not in VERDICT_GUIDANCE:
        return {'message': '', 'source': 'none'}

    prompt = _build_help_prompt(doc_type, verdict, first_name, target_language)
    from .profile_engine import _call_gemini_text  # shared, mockable Gemini prose seam
    data = _call_gemini_text(prompt, target_language)
    if 'error' in data:
        return {'message': '', 'source': 'fallback', 'error': data['error']}
    message = (data.get('markdown') or '').strip()
    if not message:
        return {'message': '', 'source': 'fallback', 'error': 'empty response'}
    return {'message': message, 'source': 'ai', 'model_used': data.get('model_used', '')}
