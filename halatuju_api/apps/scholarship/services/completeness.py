"""
⛔ `application_completeness` — DO NOT CHANGE IT, IN ANY DIRECTION.
Its legacy document-type arm is deliberately more permissive; replacing it
un-submits students and nulls their `requirements_snapshot` (H8 ruling).
It was MOVED here byte-identically at H15 and not touched.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from .. import requirements
from ..models import FundingNeed
from .blockers import income_doc_blockers


def application_completeness(application):
    """
    Report STEP 1A / STEP 2 progress for a (typically shortlisted) application:
    quiz done (the linked profile has quiz signals), story done (incl. address),
    funding done, documents done, consent done, guardian docs done.
    The sponsor stage (Phase 2) will gate on ``complete``.

    funding_done (S3 redesign + S23): at least one category ticked AND
    programme_months set.
    documents_done (gate v2, 2026-06-05): route-aware + STRICT for a not-yet-
    submitted app — ic + results_slip + offer_letter + the route's compulsory
    income docs (income_doc_blockers). An ALREADY-submitted app keeps the old
    looser bar (grandfathered; see the inline note).
    consent_done (S5): an active Consent row exists.
    address_done (S14): profile has street + postal_code + city (state already
    came from /apply). Stored on the profile, captured in the Story tab.
    guardian_docs_done: always True now — the guardianship letter (non-parent
    guardian of a minor) is optional, not required. (parent_ic stays compulsory
    for everyone via documents_done.)
    complete (S17 finalise): all seven parts done.
    """
    profile = application.profile
    quiz_done = bool(profile and profile.student_signals)
    # Layer 0 Sprint 4: WHICH questions this programme asks now comes from the catalogue
    # (`requirements.py`), exactly as Sprint 3a did for the documents. Only a question resolved
    # 'required' gates; 'optional' or 'off' makes its part vacuously true (the front end reads
    # the same resolution off the payload, so an off question is not drawn either). For every
    # programme today the resolved set reproduces the literals this function used to spell out —
    # the catalogue defaults are those literals by construction — so nothing moves, and the
    # existing suite passing unmodified is the evidence. A question resolved 'optional' still
    # ACCEPTS an answer; it just cannot block. The per-part rules below (which fields, which
    # FundingNeed columns) stay this function's own — the catalogue only says whether they run.
    asked = requirements.resolve(application, 'question')
    # Story narrative: the four "your story" questions, each on its own catalogue row (all
    # default to required; an organisation may switch any of them off). The question codes ARE
    # the model field names for these four.
    story_required = [f for f in ('aspirations', 'plans', 'daily_life', 'fears')
                      if asked.get(f) == 'required']
    details_done = all(bool(getattr(application, f).strip()) for f in story_required)
    if asked.get('funding') != 'required':
        # The programme does not require the funding questions — the part cannot gate. (An
        # inactive/removed catalogue item also lands here: deactivating an item is the
        # platform's deliberate withdrawal of the question, not a missing configuration —
        # the unconfigured case is already handled inside `requirements.resolve`.)
        funding_done = True
    else:
        try:
            fn = application.funding_need
            # S23: programme_months is now compulsory too (the radio group on the
            # Funding tab). The exact figure isn't load-bearing; what matters is
            # the student picked one — otherwise admin can't size the assistance.
            funding_done = bool(fn.categories) and fn.programme_months is not None
        except FundingNeed.DoesNotExist:
            funding_done = False
    present = set(application.documents.filter(superseded_at__isnull=True)
                  .values_list('doc_type', flat=True))
    # Gate v2 (2026-06-05): the documents bar is route-aware and STRICT for a not-yet-
    # submitted application — ic + results_slip + offer_letter (now compulsory for all)
    # + the route's compulsory income docs (income_doc_blockers, sourced from the wizard
    # requirement engine). GRANDFATHER: an already-submitted app (profile_completed_at
    # set) keeps the OLD, looser bar (any one of str/salary/epf, OR income shown the
    # 25-July-2026 way; no offer letter) so a later edit never trips
    # revert_if_profile_incomplete on the new rules — those 6 are resolved at Check 2 /
    # interview instead.
    # ⚠ THE GRANDFATHERED BAR IS A FROZEN COPY AND IT DRIFTS. Freezing a rule protects
    # already-submitted students from a TIGHTENING; it also blinds them to a LOOSENING,
    # and a loosening is exactly what "income shown any one way" was. Whenever the live
    # income bar widens, ask whether this copy needs the same arm.
    if application.profile_completed_at is None:
        # A results slip in a different name is unusable (we can't attribute the results
        # to the student), so it does NOT satisfy the bar — the student must re-upload the
        # correct slip before submitting. 'pending'/'unreadable'/'match' all pass here;
        # only a positive name MISMATCH blocks.
        from ..academic_engine import _slip_name_status
        slip = (application.documents.filter(doc_type='results_slip', superseded_at__isnull=True)
                .order_by('-uploaded_at').first())
        slip_name_ok = slip is None or _slip_name_status(slip) != 'mismatch'
        # Layer 0: WHICH documents this programme asks for now comes from the catalogue
        # (`requirements.py`), not from a literal here. For every programme today the answer is
        # the same set this line used to spell out — ic + results_slip + offer_letter, plus the
        # income route — because the catalogue defaults reproduce it by construction. Nothing
        # about the route ENGINE moves: `income_proof` is one switch over the whole of
        # `income_doc_blockers`, never a way to take it apart.
        required = requirements.required_documents(application)
        required_types = required - requirements.DOCUMENT_AGGREGATES
        documents_done = (
            required_types.issubset(present)
            # A results slip in a different name only matters if we asked for one.
            and (slip_name_ok or 'results_slip' not in required)
            and not income_doc_blockers(application)
        )
    else:
        # ⚠ THE SECOND INCOME ARM IS AN OR, AND IT MUST STAY ONE — DO NOT "TIDY" IT INTO ONE CALL.
        # The literal three-document set is the bar this branch has enforced since 5 June 2026 and
        # every already-submitted application was judged against it; dropping it would newly FAIL a
        # household that had passed, and `revert_if_profile_incomplete` un-submits on a fail. So the
        # arm can only ADD. What it adds is the fourth way income has been showable since 25 July
        # 2026 — a declared amount backed by a support letter — which has no document type of its
        # own and so is invisible to a set of doc_types (BrightPath #21; see
        # `income_engine.any_member_income_evidenced` for the whole story).
        # Local import, like every other income_engine caller in this module (circular at import time).
        from ..income_engine import any_member_income_evidenced
        income_shown = (bool(present & {'str', 'salary_slip', 'epf'})
                        or any_member_income_evidenced(application))
        documents_done = (
            {'ic', 'results_slip', 'parent_ic'}.issubset(present)
            and income_shown
        )
    # `consent` is a CORE catalogue item (a legal requirement, not a programme preference):
    # `requirements.resolve` floors it at 'required' whatever an organisation writes, so
    # reading the seam here could only ever return 'required'. The literal stays.
    consent_done = application.consents.filter(is_active=True).exists()
    if asked.get('address') != 'required':
        address_done = True
    else:
        address_done = bool(
            profile
            and (profile.address or '').strip()
            and (profile.postal_code or '').strip()
            and (profile.city or '').strip()
        )
    guardian_docs_done = _guardian_docs_done(application, profile, present)
    family_done = _family_done(application)
    return {
        'quiz_done': quiz_done,
        'details_done': details_done,
        'funding_done': funding_done,
        'documents_done': documents_done,
        'consent_done': consent_done,
        'address_done': address_done,
        'guardian_docs_done': guardian_docs_done,
        'family_done': family_done,
        'complete': (quiz_done and details_done and funding_done
                     and documents_done and consent_done and address_done
                     and guardian_docs_done and family_done),
    }


def _family_done(application):
    """`family_roster` is a CORE catalogue item (the family/income block, per the owner's
    2026-07-28 policy floor) — `requirements.resolve` floors it at 'required', so no
    organisation can switch it off and this function is unconditionally the gate.

    Redesign 2026-06: the structured family roster is compulsory. Father + mother
    profession set; their name set UNLESS the profession is deceased/no_contact (an
    absent parent can't always be named); and both sibling counts answered (not None,
    so "0" is a deliberate answer). Already-submitted apps are grandfathered (they
    carry the legacy free-text answers) — mirrors the documents-gate grandfather."""
    if application.profile_completed_at is not None:
        return True
    f_occ = application.father_occupation
    m_occ = application.mother_occupation
    if not f_occ or not m_occ:
        return False
    name_exempt = {'deceased', 'no_contact'}
    if f_occ not in name_exempt and not (application.father_name or '').strip():
        return False
    if m_occ not in name_exempt and not (application.mother_name or '').strip():
        return False
    if application.siblings_in_school is None or application.siblings_in_tertiary is None:
        return False
    return True


def _guardian_docs_done(application, profile, present_doc_types):
    """Always True now. The guardianship letter (for non-parent guardians of a
    minor) used to be a hard requirement, but it is no longer required — a student
    MAY upload one optionally. Kept as a function (and a completeness key) so the
    shape of `application_completeness` is unchanged for the frontend.
    """
    return True
