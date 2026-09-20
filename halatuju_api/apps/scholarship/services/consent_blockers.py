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
    present = set(application.documents.filter(superseded_at__isnull=True)
                  .values_list('doc_type', flat=True))
    # Layer 0: only chase what this programme actually asks for. A document that is not asked for
    # must not appear as outstanding — the student would be looking for something nobody wants.
    # The default catalogue makes all three required, so this reads identically today.
    required = requirements.required_documents(application)
    if 'ic' in required and 'ic' not in present:
        blockers.append('ic_missing')
    if 'results_slip' in required and 'results_slip' not in present:
        blockers.append('results_slip_missing')
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
    return blockers
