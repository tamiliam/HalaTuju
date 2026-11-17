"""
The one blocker that reads BOTH completeness and the other blockers.

It has a module of its own for exactly that reason: it is the single edge that
would otherwise make `completeness` and `blockers` import each other.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .. import requirements
from .blockers import (
    _offer_blocks, document_red_blockers, document_unreadable_blockers,
    ic_identity_blockers, income_doc_blockers,
)
from ..document_snapshot import present_doc_types
from .completeness import application_completeness

def consent_blockers(application):
    """Every gate that must pass BEFORE consent can be given, as a list of blocker
    codes (empty list = ready). Consent is the final step: the profile must be
    complete, the required documents uploaded (route-aware income docs + a compulsory
    offer letter), and the uploaded IC must be machine-readable AND match the student's
    name + NRIC. Each code has a matching i18n label on the frontend, so the student
    sees ALL outstanding items at once and can fix them in one pass. The ConsentView
    POST enforces this list; the minor guardian-field checks (typed name/NRIC vs the
    parent's IC) are separate and run on the submitted consent data.
    """
    c = application_completeness(application)
    blockers = []
    if not c['quiz_done']:
        blockers.append('quiz_incomplete')
    if not c['details_done']:
        blockers.append('story_incomplete')
    if not c['family_done']:                          # structured family roster (Your Story)
        blockers.append('family_incomplete')
    if not c['address_done']:
        blockers.append('address_incomplete')
    if not c['funding_done']:
        blockers.append('funding_incomplete')
    present = present_doc_types(application)   # A2.4: from the open snapshot, else the same query
    # Layer 0: only chase what this programme actually asks for. A document that is not asked for
    # must not appear as outstanding — the student would be looking for something nobody wants.
    # The default catalogue makes all three required, so this reads identically today.
    required = requirements.required_documents(application)
    if 'ic' in required and 'ic' not in present:
        blockers.append('ic_missing')
    if 'results_slip' in required and 'results_slip' not in present:
        blockers.append('results_slip_missing')
    # Third results route S3a (D12): the higher-results upload, when it is the one required.
    if 'higher_results' in required and 'higher_results' not in present:
        blockers.append('higher_results_missing')
    if 'offer_letter' not in required:
        pass                                          # not asked for — neither missing nor checked
    elif 'offer_letter' not in present:               # gate v2: compulsory for everyone
        blockers.append('offer_letter_missing')
    elif application.profile_completed_at is None and _offer_blocks(application):
        # Owner 2026-07-08: the offer gate follows the PATHWAY VERDICT the officer sees — we accept
        # "blue and above" (Probable/Certain) and only block Unsure/Can't-verify. This aligns the
        # gate with the card (the reporting-date bonus / genuineness ladder can legitimately lift a
        # cropped-official offer to Certain — #56 — which the old raw offer_official_status gate
        # wrongly still blocked). GRANDFATHER: only for a NOT-yet-submitted app (profile_completed_at
        # is None) so an already-submitted student is NEVER reverted.
        blockers.append('offer_not_official')
    blockers.extend(income_doc_blockers(application))  # route-aware (replaces parent_ic + income_proof)
    # Identity check only once the IC is actually uploaded (else 'ic_missing' leads).
    if 'ic' in present:
        blockers.extend(ic_identity_blockers(application))
    # POLICY (owner): do not receive applications with ANY red document check — every
    # "Doesn't match" the student sees in the Documents tab must clear before consent.
    blockers.extend(document_red_blockers(application))
    # …and a COMPULSORY doc that's present but UNREADABLE (a bad photo the student can
    # re-take) must be re-uploaded too — but never block on OUR OCR-service outages.
    blockers.extend(document_unreadable_blockers(application))
    # One line per code: the income gate and the identity gate can both say "try later" (TD-390).
    return list(dict.fromkeys(blockers))


#: The student's own IC codes she clears by sending the card again (never 'ic_service_down': ours).
_OWN_IC_REDO = ('ic_unreadable', 'ic_nric_mismatch', 'ic_name_mismatch')


def consent_blocking_slots(application):
    """H6 fix round 3 (owner 2026-11-17): the document slots the consent gate is holding this student on,
    as (slots, missing). `slots` is {(doc_type, household_member, request_code)} of each LIVE copy whose own
    check puts a code into `consent_blockers` right now: a red (`document_red_blockers`), an unreadable
    copy (`document_unreadable_blockers`), a not-an-offer-letter offer, her own IC's identity reds, a
    stranger's STR. `missing` is {(doc_type, member or None)} for each `<type>_missing` code the gate
    gives (`parent_ic_missing:<member>` names its member), so a slot emptied by Remove counts too. Our own
    outages and "still checking" codes never count. Read only before consent; empty sets when nothing
    blocks. The documents' reads are shared through one snapshot."""
    from ..document_snapshot import latest_doc, live_docs, snapshot_unless_open
    from ..income_str_ownership import STR_NOT_HOUSEHOLD
    from ..models import ApplicantDocument
    with snapshot_unless_open(application):
        codes = set(consent_blockers(application))
        if not codes:
            return set(), set()
        docs = [d for d, c in document_red_blockers(application, per_doc=True) if c in codes]
        docs += [d for d, c in document_unreadable_blockers(application, per_doc=True) if c in codes]
        if 'offer_not_official' in codes:
            docs.append(latest_doc(application, 'offer_letter'))
        if codes.intersection(_OWN_IC_REDO):
            docs.append(latest_doc(application, 'ic'))
        if STR_NOT_HOUSEHOLD in codes:
            docs += list(live_docs(application, 'str'))
    slots = {(d.doc_type, d.household_member or '', d.request_code or '') for d in docs if d is not None}
    types = {t for t, _label in ApplicantDocument.DOC_TYPES}
    missing = set()
    for code in codes:
        head, _sep, member = code.partition(':')
        if head.endswith('_missing') and head[:-len('_missing')] in types:
            missing.add((head[:-len('_missing')], member or None))
    return slots, missing
