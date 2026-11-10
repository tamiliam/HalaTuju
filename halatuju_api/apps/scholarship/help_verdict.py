"""Which Cikgu Gopal note a document gets: the per-type checks behind
``help_engine.verdict_for_document``.

⚠ WHY THIS IS A MODULE (audit sprint A3.4, 2026-11-10). ``verdict_for_document`` was a 162-line
chain of ``if doc.doc_type ...`` blocks on the long-function ledger. Each block moved here whole,
as one function, in the same order and with the same lines and comments; ``help_engine`` keeps
the function's name and docstring (callers and tests import it from there) and calls
``verdict_for_document`` below, which picks the check for the type. Only the salary-slip / EPF /
STR block could fall through to the generic checks at the end; it now says so by returning
``_FALLS_THROUGH``, and the picker then runs ``_help_other_document`` exactly as the old chain did.

Every collaborator a test patches at its source (``income_engine.*``, ``academic_engine.*``,
``pathway_engine.*``, ``vision.*``) is still imported INSIDE the function that calls it, as it was.
"""
from .help_engine import VERDICT_GUIDANCE
from .income_declaration import approval_coach   # #374: an informal income document needs its approver
from .read_errors import ic_second_opinion_deferred

#: The salary-slip / EPF / STR block found no member: carry on to the generic checks.
_FALLS_THROUGH = object()


def _help_student_ic(doc):
    """The student's OWN IC: identity against the profile (name + NRIC)."""
    # The student's OWN IC → identity match against the profile (name + NRIC).
    if doc.vision_run_at is None:
        return ''
    if ic_second_opinion_deferred(doc):
        return 'review_manually'     # TD-390: our outage owes this card a second look — no re-upload
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


def _help_parent_ic(doc):
    """An earner's IC: that member's income-cluster verdict, else a consent-card read."""
    # An earner's IC (parent_ic) → the CLUSTER verdict for that member (their IC anchor +
    # income proofs), so Gopal speaks ONCE per person. Income is a cluster, unlike the
    # single-document Identity/Academic/Pathway facts. The NRIC is the EARNER's — never
    # matched to the student.
    if doc.vision_run_at is None:
        return ''
    member = (getattr(doc, 'household_member', '') or '').strip() \
        or (getattr(doc.application, 'income_earner', '') or '').strip()
    from .income_engine import income_cluster_advice
    if member:
        return income_cluster_advice(doc.application, member)
    # A non-income parent_ic (e.g. minor consent) — just flag an unreadable card.
    if ic_second_opinion_deferred(doc):
        return 'review_manually'     # TD-390, as for the student's own IC above
    if doc.vision_error or not (doc.vision_name or '').strip():
        return 'unreadable'
    return ''


def _help_higher_results(doc):
    """The higher-results card: fixed deterministic notes, never the coach."""
    # Third route S3b (D13): the higher-results card speaks in fixed, deterministic notes with one
    # link each (`higher_results.student_higher_check`), never an AI coach — nothing to phrase here.
    return ''


def _help_results_slip(doc):
    """The results slip: the three clinical checks, most important first."""
    # Results slip — the three clinical checks (name / subjects / results), most
    # important first: a wrong-person slip, then a missing subject, then a grade that
    # disagrees with the typed profile. Computed by the SAME engine the FE checklist
    # uses (academic_engine.student_slip_check) so the coach and the checklist agree.
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
    if chk['subjects'] == 'mismatch':      # missing first; else a typed subject not on it (#62)
        return 'slip_subjects_missing' if chk.get('missing') else 'slip_subjects_extra'
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


def _help_offer_letter(doc):
    """The offer letter: identity, then a soft pathway nudge."""
    # Offer letter (pathway) — name + IC are the identity checks; a mismatch on either
    # means a wrong-person letter. (Richer pathway-aware coaching is a later pass.)
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


def _help_income_proof(doc):
    """A salary slip / EPF / STR in an income context; _FALLS_THROUGH where the old branch fell through to the generic checks."""
    # A salary slip / EPF in an income context (salary route = member-tagged; STR route =
    # the single earner) — part of that earner's cluster. The coherence (slip vs IC) is
    # voiced by the cluster coach anchored on the IC, so here we only speak when there is
    # NO IC to anchor on: nudge the student to add this person's IC. (Skips the generic
    # "your name isn't on this" check below, which is wrong for an earner's document.)
    from .income_engine import _proof_member, _member_ic_doc, student_str_check, STR_COACH_STATES
    # An STR whose currency itself is the problem speaks here — the earner-IC cluster coach
    # can't say "this STR is out of date". V2 (#16): use the SHARED STR_COACH_STATES (the S4
    # unification), so a wrong_type/unreadable/unconfirmed STR re-upload also gets the
    # doc-anchored coach — not just stale/rejected (which left the two worst states silent).
    if doc.doc_type == 'str':
        sc = student_str_check(doc)
        if sc and sc['current_status'] in STR_COACH_STATES:
            return 'str_not_current'
    member = _proof_member(doc) if doc.doc_type != 'str' else \
        ((doc.application.income_earner or '').strip()
         if (doc.application.income_route or '') == 'str' else '')
    if member:
        return approval_coach(doc) if _member_ic_doc(doc.application, member) else 'income_ic_needed'
    return _FALLS_THROUGH      # no member: the old chain fell through to the generic checks


def _help_utility_bill(doc):
    """A water / electricity bill: the home address only, never the name."""
    # Utility bill (water / electricity) — the meaningful check is the HOME ADDRESS (these
    # confirm where the family lives). The bill is in a PARENT's name, so we deliberately do
    # NOT flag a name mismatch (that's the wrong "edit your profile name" nudge). Coach only
    # when the address couldn't be matched.
    if doc.vision_run_at is None:
        return ''
    return 'address_mismatch' if doc.vision_address_match == 'mismatch' else ''


def _help_relationship_proof(doc):
    """A birth certificate / guardianship letter: the cluster coach speaks."""
    # Relationship-proof docs (birth cert / guardianship letter) — any problem (the names
    # don't link to the family) is voiced by the earner-IC cluster coach, and the per-row
    # checklist shows the detail. So the doc itself stays quiet (no wrong generic nudge).
    return ''


def _help_bank_statement(doc):
    """The bank statement: the doc-assist verdict on the holder and the fields."""
    # Bank statement (post-award payout) — the doc-assist verdict checks all three fields are
    # present AND the holder is the student. 'name_mismatch' = not the student's account (a
    # hard problem); 'incomplete'/'wrong_doc'/'unreadable' = a field couldn't be read clearly.
    fields = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    sv = fields.get('student_verdict')
    if not sv:
        return ''
    if sv == 'name_mismatch':
        return 'bank_holder_mismatch'
    if sv == 'review_manually':
        return sv                   # not read yet (TD-392b) — a reviewer checks it, no re-upload
    if sv in ('incomplete', 'wrong_doc', 'unreadable'):
        return 'bank_details_unclear'
    return ''


def _help_other_document(doc):
    """Every other document: the doc-assist verdict, else the soft full-text checks."""
    # Other supporting docs — the Gemini doc-assist verdict takes precedence (it is the
    # chip the frontend shows); fall back to the older soft full-text checks when it never ran.
    fields = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    sv = fields.get('student_verdict')
    if sv:
        return '' if sv == 'ok' else (sv if sv in VERDICT_GUIDANCE else '')
    if doc.vision_name_match == 'not_found':
        return 'name_mismatch'
    if doc.vision_address_match == 'mismatch':
        return 'address_mismatch'
    if 'unreadable' in (doc.vision_name_match, doc.vision_address_match):
        return 'unreadable'
    return ''


#: document type → its check, in the order the old chain tested them. Any other type gets the
#: generic checks (``_help_other_document``).
HELP_VERDICT_CHECKS = {
    'ic': _help_student_ic,
    'parent_ic': _help_parent_ic,
    'higher_results': _help_higher_results,
    'results_slip': _help_results_slip,
    'offer_letter': _help_offer_letter,
    'salary_slip': _help_income_proof,
    'epf': _help_income_proof,
    'str': _help_income_proof,
    'water_bill': _help_utility_bill,
    'electricity_bill': _help_utility_bill,
    'birth_certificate': _help_relationship_proof,
    'guardianship_letter': _help_relationship_proof,
    'bank_statement': _help_bank_statement,
}


def verdict_for_document(doc):
    """The help-verdict code for ``doc`` (see ``help_engine.verdict_for_document``)."""
    check = HELP_VERDICT_CHECKS.get(doc.doc_type)
    code = check(doc) if check else _FALLS_THROUGH
    return _help_other_document(doc) if code is _FALLS_THROUGH else code
