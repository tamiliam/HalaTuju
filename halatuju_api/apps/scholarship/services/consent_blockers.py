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

#: H6 fix round 4: the consent-gate codes that NO document upload clears, so they never open a slot. The
#: profile steps (she fills a form, not a slot) and our own "still checking / try later" (a read of ours
#: finishes it; `STR_PENDING_OUR_READ` is this same code). EVERY other code the gate can give is a document
#: code: it is mapped to its slots below, or, unmapped, it opens every slot (`EVERY_SLOT`). A new gate code
#: therefore opens slots by default; `test_document_replace_blocker` walks the gate's source to prove it.
NOT_DOCUMENT_CODES = ('quiz_incomplete', 'story_incomplete', 'family_incomplete', 'address_incomplete',
                      'funding_incomplete', 'income_incomplete')
OUR_WAIT_CODES = ('ic_service_down',)

#: The safety net, in `missing`: a document code the map below could not tie to a slot holds the gate,
#: so every document slot of the case counts as blocking (still at most `HARD_LIMIT` uploads each).
EVERY_SLOT = ('*', None)

#: `income_evidence_missing:<member>`: any one way of showing that member's income would do.
_INCOME_EVIDENCE_TYPES = ('salary_slip', 'epf', 'income_support_doc')


def consent_blocking_slots(application):
    """H6 fix rounds 3 and 4 (owner 2026-11-17): the document slots the consent gate is holding this
    student on, as (slots, missing). `slots` is {(doc_type, household_member, request_code)}: each LIVE copy
    whose own check puts a code into `consent_blockers` right now (a red, an unreadable copy, a
    not-an-offer-letter offer, her own IC's identity reds, a stranger's STR, an STR that needs its
    recipient's IC number, an unsigned income letter, an STR no card could be matched to), plus the slot
    keys those codes name even when empty. `missing` is {(doc_type, member or None)} for each `<type>_missing`
    code (`parent_ic_missing:<member>` names its member), so a slot emptied by Remove counts too.

    BY CONSTRUCTION, not by list: any code that is not in `NOT_DOCUMENT_CODES` / `OUR_WAIT_CODES` and that
    this map did not tie to at least one slot adds `EVERY_SLOT` to `missing`, so no document code can leave
    a pre-consent student with a shut slot and nobody able to ask. Read only before consent; empty sets
    when nothing blocks. The documents' reads are shared through one snapshot."""
    from ..document_replace import slot_members
    from ..document_snapshot import latest_doc, live_docs, snapshot_unless_open
    from ..income_declaration import UNAPPROVED
    from ..income_str_ownership import STR_NEEDS_RECIPIENT_IC, STR_NOT_HOUSEHOLD
    from ..models import ApplicantDocument
    types = {t for t, _label in ApplicantDocument.DOC_TYPES}
    slots, missing, tied = set(), set(), set()
    str_slot = slot_members(application, 'str', '', '')

    def tie(code, docs=(), keys=(), absent=()):
        """Record what `code` holds; it counts as mapped only when it names at least one slot."""
        found = {(d.doc_type, d.household_member or '', d.request_code or '') for d in docs if d is not None}
        found |= set(keys)
        if any(t == 'str' and not rc for t, _m, rc in found):
            # The STR that holds the gate may carry an earlier earner's tag; her next STR goes into the
            # CURRENT earner's slot (`slot_members`), so that slot is the one that must stay open.
            found |= {('str', m, '') for m in str_slot}
        slots.update(found)
        missing.update(absent)
        if found or absent:
            tied.add(code)

    with snapshot_unless_open(application):
        codes = set(consent_blockers(application))
        if not codes:
            return set(), set()
        for d, c in document_red_blockers(application, per_doc=True):
            if c in codes:
                tie(c, [d])
        for d, c in document_unreadable_blockers(application, per_doc=True):
            if c in codes:
                tie(c, [d])
        if 'offer_not_official' in codes:
            tie('offer_not_official', [latest_doc(application, 'offer_letter')])
        for c in codes.intersection(_OWN_IC_REDO):
            tie(c, [latest_doc(application, 'ic')])
        if STR_NOT_HOUSEHOLD in codes:
            tie(STR_NOT_HOUSEHOLD, live_docs(application, 'str'))
        if 'income_document_unreadable' in codes:
            # `_unmatched_str_asks`: every card is on file and none matched the STR's recipient: a clearer
            # STR or a clearer card. (`document_unreadable_blockers` ties its own copies above.)
            tie('income_document_unreadable', live_docs(application, doc_types=('str', 'parent_ic')))
        for code in codes:
            head, _sep, member = code.partition(':')
            if head == STR_NEEDS_RECIPIENT_IC and member:
                # The STR read fine but shows no IC number: the STR page that carries it, or the card.
                tie(code, live_docs(application, 'str'), keys=[('parent_ic', member, '')])
            elif head == UNAPPROVED and member:
                # An informal income letter (or a salary-route slip) with no issuer / approver: send it signed.
                tie(code, live_docs(application, doc_types=('income_support_doc', 'salary_slip'),
                                    members=[member, '']),
                    keys=[('income_support_doc', member, ''), ('salary_slip', member, '')])
            elif head == 'income_evidence_missing' and member:
                tie(code, absent=[(t, member) for t in _INCOME_EVIDENCE_TYPES])
            elif head.endswith('_missing') and head[:-len('_missing')] in types:
                tie(code, absent=[(head[:-len('_missing')], member or None)])
    exempt = NOT_DOCUMENT_CODES + OUR_WAIT_CODES
    if any(c.partition(':')[0] not in exempt for c in codes - tied):
        missing.add(EVERY_SLOT)
    return slots, missing
