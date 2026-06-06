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
    # The student's OWN IC where the NAME matched but only the IC NUMBER did not — because
    # the name agreed, this is almost always the camera misreading the digits (glare), not
    # the wrong card. Reassure on the name, ask for a clean re-upload.
    'ic_nric_misread': "the NAME on this IC matched the applicant's name, but the IC NUMBER we read did not match the IC number registered on the applicant's account — and because the name matched, this is most likely the camera misreading the number (glare or blur across the card) rather than the wrong card",
    'address_mismatch': "the home address on this bill did not match the address on file",
    'wrong_doc':       "this file did not look like the kind of document expected in this slot",
    'unreadable':      "we could not read this document clearly — it may be blurry, dark, or low-resolution",
    'review_manually': "we could not auto-check this one right now; a reviewer will look at it by hand",
    # Results-slip specific (the three academic checks: name / subjects / results).
    'slip_name_mismatch':    "the name on this results slip is not the applicant's — it looks like it may be someone else's slip",
    'slip_subjects_missing': "the results slip lists one or more subjects that were not entered in the applicant's profile",
    'slip_grade_mismatch':   "one or more grades on the results slip differ from the grades the applicant typed into their profile",
    # Results-slip — a grade that could NOT be read with full confidence (a faint +/- or
    # slight blur). Not a confident mismatch — we only ask the student to double-check.
    'slip_grade_uncertain':  "we read the results slip, but one or more grades could not be read with full confidence (a faint +/- mark or a slight blur), so we could not be sure they match what the applicant typed",
    # Results-slip — the photo was taken at an angle (skewed) AND that left part of it hard
    # to read. The fix is a flat, straight-on retake — NOT a profile edit.
    'slip_skewed_unclear':   "the results slip was photographed at an angle (skewed), which left part of it hard to read clearly",
    # Offer-letter (pathway): the name and/or IC on the letter are not the applicant's.
    'offer_name_mismatch':   "the name and/or IC number on this offer letter are not the applicant's — it looks like it may be someone else's offer letter",
    # Offer-letter (pathway): the offer is for a different college/programme than declared.
    'offer_pathway_mismatch': "the college or programme on this offer letter looks different from the study choice the applicant entered earlier when they applied",
    # Income earner IC: the name on this IC does not link to the student's family — for a
    # father/brother/sister the family name (patronymic) in the student's OWN IC did not
    # appear on this IC; for a mother/guardian the birth certificate / letter did not agree.
    'income_relationship_mismatch': "the name on this family member's IC did not match the family name in the applicant's own IC (or the birth certificate / guardianship letter did not agree), so we could not confirm this earner is the applicant's family",
    # A member-tagged salary slip / EPF whose name or IC number did NOT match the IC the
    # student uploaded for THAT same household member (e.g. the father's payslip but not
    # the father's IC). The fix is about the EARNER's document, never the student's name.
    'income_proof_person_mismatch': "the name or IC number on this income document did not match the IC uploaded for the same household member, so the income document and that person's IC do not appear to be for the same person",
    # An income document was uploaded for a household member but that member's IC has not
    # been uploaded yet, so we cannot confirm the two are the same person. The IC is a
    # REQUIRED document — the application cannot be submitted until it is uploaded.
    'income_ic_needed': "an income document has been uploaded for this household member, but that person's identity card (IC/MyKad) has not been uploaded yet — and it is required, so the application cannot be completed until it is added; we use it to confirm the income document really belongs to that person",
    # The earner's IC is in and matches the income document, but the relationship-proof
    # document (a birth certificate for a mother, a guardianship letter for a guardian) is
    # still needed to LINK that earner to the student — and it is required to complete.
    'income_rel_doc_needed': "the earner's identity card is uploaded and matches the income document — the last required step is the document that links that earner to the student (a birth certificate for a mother, or a guardianship letter for a guardian), which has not been uploaded yet, so the application cannot be completed until it is added",
    # The relationship-proof document HAS been uploaded, but we could not read the names that
    # establish the link (e.g. it was unclear, or the wrong document — an IC sent as a birth
    # certificate). It must be re-uploaded as a clear copy of the correct document.
    'income_rel_doc_unreadable': "the document that should link the earner to the student (a birth certificate for a mother, or a guardianship letter for a guardian) has been uploaded, but we could not read the names on it that prove the link — either the photo was unclear or it was the wrong document — so it must be re-uploaded as a clear copy of the correct document before the application can be completed",
    # The STR document is for an older year, or its status is not 'approved' — STR is
    # awarded annually, so an out-of-date STR no longer proves the family's current need.
    'str_not_current': "the STR document is for an earlier year or its status is not approved, and STR is awarded annually — so this one no longer proves the family's CURRENT financial need",
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
    'ic_nric_misread': (
        'State that the name matched but the IC number did not — so this is very likely just '
        'the photo being misread, not the wrong card. Tell them to re-upload a clear, '
        'straight-on photo of the IC with no glare or shadow across the number. Add that if the '
        'number still does not match after a clean photo, the IC number they typed when '
        'registering may have a small typo they can correct on their Profile page. Do NOT ask '
        'them to change their name.'
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
    'slip_grade_uncertain': (
        'Reassure them that nothing is wrong and nothing is blocked — we just could not be '
        '100% sure of one grade. Kindly ask them to glance at their slip and confirm the '
        'grades they entered match it: if a grade truly differs they can tidy it on their '
        'Profile page, and if the photo was a little unclear a clearer, straight-on photo '
        'helps. Do NOT assert that any grade is wrong — we are only asking them to '
        'double-check.'
    ),
    'slip_skewed_unclear': (
        'Kindly explain that a flat, straight-on, well-lit photo reads most accurately, and '
        'suggest they retake the slip that way — lay it flat on a table, fill the frame, and '
        'photograph it straight from above. Make clear nothing is blocked and they have done '
        'nothing wrong (phones tilt the page all the time). Do NOT tell them to edit their '
        'profile — the fix here is simply a straighter photo.'
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
    'income_relationship_mismatch': (
        'This usually means the WRONG IC was uploaded for this family member: kindly suggest '
        'they double-check they uploaded the right person\'s MyKad in this slot (for example, '
        'their father\'s card under "Father", not someone else\'s), and that the photo is clear '
        'enough to read the full name. Reassure them nothing is blocked. Do NOT tell them to '
        'edit their profile — the fix here is the correct, clear IC photo for this person.'
    ),
    'income_proof_person_mismatch': (
        'This income document (salary slip / EPF) does not seem to belong to the SAME person '
        'as the IC uploaded for that household member. Kindly suggest they check that the '
        'salary slip / EPF and that person\'s IC are for the SAME individual (for example, the '
        'father\'s payslip together with the father\'s IC), and re-upload the matching one if a '
        'wrong file slipped in. This is about the EARNER\'s documents — do NOT tell them to '
        'edit their OWN name or profile. Reassure them nothing is blocked.'
    ),
    'income_ic_needed': (
        'They added an income document for this household member but not that person\'s IC yet. '
        'Tell them to upload THAT person\'s MyKad (use the exact family member and income document '
        'from the SPECIFICS) so we can confirm it belongs to the right person. The IC is a '
        'required document — say plainly that it is needed to complete the application; do NOT '
        'say it is optional or "not blocked". Do NOT name a different family member or document '
        'than the SPECIFICS give.'
    ),
    'income_rel_doc_needed': (
        'The earner\'s IC is in and matches the income document — only the relationship document '
        'is left. Tell them to upload the exact document named in the SPECIFICS (a birth '
        'certificate for a mother, or a guardianship letter for a guardian) to finish, because '
        'it links that earner to them. This is the LAST required step — frame it as "to '
        'complete your application", warmly. Do NOT ask them to re-upload the IC or edit their '
        'profile, and do NOT name a different document than the SPECIFICS give.'
    ),
    'income_rel_doc_unreadable': (
        'They DID upload the relationship document (the one named in the SPECIFICS — a birth '
        'certificate for a mother, a guardianship letter for a guardian), but we could not read '
        'the names that prove the link. Tell them to check it is a clear photo or PDF of the '
        'CORRECT document (the actual birth certificate / letter, not an IC or another file) and '
        're-upload it. Be specific that we need to see the names on it. Do NOT ask them to edit '
        'their profile or re-upload the IC, and do NOT name a different document than the '
        'SPECIFICS give.'
    ),
    'str_not_current': (
        'Gently explain that STR is given out fresh each year, so we need the CURRENT year\'s '
        'STR to show the family qualifies now. Kindly ask them to upload this year\'s STR — a '
        'recent screenshot of the MySTR "Semakan Status" portal showing "Lulus", or the latest '
        'STR letter. If they do not have a current STR, reassure them it is fine: they can '
        'instead show the family\'s income with a salary slip / EPF (the other route). Do NOT '
        'imply they did anything wrong.'
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
    # The whole household-income cluster for one earner (IC + income proof + relationship
    # doc) — the anchor for the single per-earner cluster coach.
    'income_cluster': "household income documents for this family member",
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
student's chances; a clearer or corrected re-upload usually resolves it. Some documents (the IC, \
results slip, offer letter, and the income documents for the chosen route) are REQUIRED — the \
application is completed once those are in, so for a missing required document say plainly that it \
is needed, not that it is optional."""

HELP_PROMPT = """You are {persona}, a clear, practical Malaysian teacher ("cikgu") helping a \
student fix a document for their B40 Assistance Programme application. A good cikgu reads the \
situation, names the problem, and says exactly what to do — briefly. Warm in wording, but you \
spend your words on the diagnosis and the fix, NOT on motivation.

{programme_briefing}

THE SITUATION RIGHT NOW:
- The student just uploaded their {doc_label}.
- Our automatic check found that {cause}.
- The student's first name is: {first_name}
{specifics}
YOUR REPLY — diagnose, then advise:
- Write 1-3 short, plain sentences in {target_language}. Say the student's first name once at the \
start, then go straight to the point — no warm-up line.
- First state plainly WHAT our check found (the diagnosis); then tell them exactly WHAT TO DO about \
it (the action). Lead with the finding.
- {fix_hint}

TONE — economical, not cheerful:
- Do NOT pad with motivational filler or cheerleading. Ban these and anything like them: "don't \
worry", "no worries", "this happens a lot", "you've got this", "you're doing great", "great job", \
"almost there", "well done", "nice work", and any encouraging sign-off.
- At MOST one short reassuring clause, and ONLY when it carries real information (for example, that \
nothing is blocked). Never open or close with reassurance for its own sake.

HARD RULES (these override everything else):
- Address the student by their FIRST NAME only. Do NOT use pet names or endearments \
(no "dear", "sayang", "my dear", "sweetheart", etc.).
- You are a COACH, not a ghost-writer. NEVER write, draft, compose, or suggest the wording of the \
student's application answers, essays, personal statements, or any field they must fill in \
themselves. If they ask you to write something for them, kindly decline and tell them to write it \
in their own words.
- You do NOT have access to any scores, rankings, reviewers' notes, or the application's outcome, \
and you must NEVER reveal, guess, or invent them. If asked "what's my score?" or "will I get it?", \
plainly explain you cannot see that and steer back to the document.
- Use ONLY the situation above. Do not invent facts about the student or the document.
- Plain text only (no Markdown headings, no lists). Just the short, clear message."""


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
    # The student's OWN IC → identity match against the profile (name + NRIC).
    if doc.doc_type == 'ic':
        if doc.vision_run_at is None:
            return ''
        if doc.vision_error or not doc.vision_nric:
            return 'unreadable'
        from .vision import name_match, nric_match
        profile = getattr(doc.application, 'profile', None)
        if not nric_match(doc.vision_nric, getattr(profile, 'nric', '') or ''):
            # IC number didn't match the account. If the NAME we read still matches, it is
            # almost always an OCR misread of the digits (glare) — reassure + ask for a clean
            # re-upload. If the name ALSO fails (or none was read), fall back to the generic
            # number-mismatch note (it could be the wrong card entirely).
            name_ok = doc.vision_name and name_match(doc.vision_name, getattr(profile, 'name', '') or '') != 'mismatch'
            return 'ic_nric_misread' if name_ok else 'nric_mismatch'
        if doc.vision_name and name_match(doc.vision_name, getattr(profile, 'name', '') or '') == 'mismatch':
            return 'name_mismatch'
        return ''
    # An earner's IC (parent_ic) → the CLUSTER verdict for that member (their IC anchor +
    # income proofs), so Gopal speaks ONCE per person. Income is a cluster, unlike the
    # single-document Identity/Academic/Pathway facts. The NRIC is the EARNER's — never
    # matched to the student.
    if doc.doc_type == 'parent_ic':
        if doc.vision_run_at is None:
            return ''
        member = (getattr(doc, 'household_member', '') or '').strip() \
            or (getattr(doc.application, 'income_earner', '') or '').strip()
        from .income_engine import income_cluster_advice
        if member:
            return income_cluster_advice(doc.application, member)
        # A non-income parent_ic (e.g. minor consent) — just flag an unreadable card.
        if doc.vision_error or not (doc.vision_name or '').strip():
            return 'unreadable'
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
        # A grade we could not read with full confidence → ask the student to double-check
        # (never a confident "you're wrong"). If the photo was also SKEWED, blame the photo
        # and ask for a straight retake; otherwise just ask them to confirm the value.
        if chk['results'] == 'uncertain':
            return 'slip_skewed_unclear' if chk.get('was_skewed') else 'slip_grade_uncertain'
        # The subject table couldn't be pulled → ask for a clearer copy; a straight retake if
        # the slip was skewed, else the generic clearer-photo nudge.
        if chk['subjects'] == 'unreadable' or chk['results'] == 'unreadable':
            return 'slip_skewed_unclear' if chk.get('was_skewed') else 'unreadable'
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
    # A salary slip / EPF in an income context (salary route = member-tagged; STR route =
    # the single earner) — part of that earner's cluster. The coherence (slip vs IC) is
    # voiced by the cluster coach anchored on the IC, so here we only speak when there is
    # NO IC to anchor on: nudge the student to add this person's IC. (Skips the generic
    # "your name isn't on this" check below, which is wrong for an earner's document.)
    if doc.doc_type in ('salary_slip', 'epf', 'str'):
        from .income_engine import _proof_member, _member_ic_doc, student_str_check
        # An STR whose currency itself is the problem (stale / rejected) speaks here —
        # the earner-IC cluster coach can't say "this STR is out of date".
        if doc.doc_type == 'str':
            sc = student_str_check(doc)
            if sc and sc['current_status'] in ('stale', 'rejected'):
                return 'str_not_current'
        member = _proof_member(doc) if doc.doc_type != 'str' else \
            ((doc.application.income_earner or '').strip()
             if (doc.application.income_route or '') == 'str' else '')
        if member:
            return '' if _member_ic_doc(doc.application, member) else 'income_ic_needed'
    # Utility bill (water / electricity) — the meaningful check is the HOME ADDRESS (these
    # confirm where the family lives). The bill is in a PARENT's name, so we deliberately do
    # NOT flag a name mismatch (that's the wrong "edit your profile name" nudge). Coach only
    # when the address couldn't be matched.
    if doc.doc_type in ('water_bill', 'electricity_bill'):
        if doc.vision_run_at is None:
            return ''
        return 'address_mismatch' if doc.vision_address_match == 'not_found' else ''
    # Relationship-proof docs (birth cert / guardianship letter) — any problem (the names
    # don't link to the family) is voiced by the earner-IC cluster coach, and the per-row
    # checklist shows the detail. So the doc itself stays quiet (no wrong generic nudge).
    if doc.doc_type in ('birth_certificate', 'guardianship_letter'):
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


# Non-sensitive specifics the cluster coach can supply so the message names the RIGHT family
# member + document (e.g. "your mother's MyKad alongside her STR document"), instead of the
# generic example in the fix-hint. Household structure only — never any score/admin data.
def _specifics_block(context):
    if not context:
        return ''
    lines = []
    if context.get('member'):
        lines.append(f"- The household member is the {context['member']}.")
    if context.get('income_doc'):
        lines.append(f"- The income document they already uploaded is the {context['income_doc']}.")
    if context.get('rel_doc'):
        lines.append(f"- The relationship document still needed is the {context['rel_doc']}.")
    if not lines:
        return ''
    return ('SPECIFICS (use these EXACT details — do not substitute a different family member or '
            'document):\n' + '\n'.join(lines) + '\n')


def _build_help_prompt(doc_type, verdict, first_name, target_language=DEFAULT_LANGUAGE, context=None):
    """Pure prompt builder — unit-tested directly (the guardrail/firewall assertions read this
    string). ``context`` carries only non-sensitive household specifics (member + document
    names) so no admin/score data can appear in it."""
    return HELP_PROMPT.format(
        persona=PERSONA,
        programme_briefing=PROGRAMME_BRIEFING,
        doc_label=_doc_label(doc_type),
        cause=VERDICT_GUIDANCE.get(verdict, ''),
        fix_hint=VERDICT_FIX_HINT.get(verdict, DEFAULT_FIX_HINT),
        first_name=(first_name or '').strip() or 'there',
        target_language=target_language,
        specifics=_specifics_block(context),
    )


def generate_document_help(doc_type, verdict, *, first_name='', target_language=DEFAULT_LANGUAGE, context=None):
    """Return {'message', 'source', ...}. ``source`` is:
    - 'none'     — nothing to help with (good/absent verdict); no Gemini call made.
    - 'ai'       — a warm message from Gemini (also returns 'model_used').
    - 'fallback' — Gemini was unavailable/empty; caller should use pre-written i18n copy.

    ``context`` (optional) supplies non-sensitive household specifics so the message names the
    right family member + document. Never raises. Soft by construction."""
    verdict = (verdict or '').strip()
    if verdict not in VERDICT_GUIDANCE:
        return {'message': '', 'source': 'none'}

    prompt = _build_help_prompt(doc_type, verdict, first_name, target_language, context)
    from .profile_engine import _call_gemini_text  # shared, mockable Gemini prose seam
    data = _call_gemini_text(prompt, target_language)
    if 'error' in data:
        return {'message': '', 'source': 'fallback', 'error': data['error']}
    message = (data.get('markdown') or '').strip()
    if not message:
        return {'message': '', 'source': 'fallback', 'error': 'empty response'}
    return {'message': message, 'source': 'ai', 'model_used': data.get('model_used', '')}
