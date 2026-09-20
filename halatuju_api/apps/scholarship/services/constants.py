"""
Status/type constants the rest of the app reads off `services`.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""

# B40 Phase E/F (F8a): the consent a student records when they finish post-award
# onboarding (acknowledging the programme terms). A free string consent_type — no
# model migration needed (Consent.consent_type is an open CharField).
ONBOARDING_CONSENT_TYPE = 'student_onboarding_ack'


# Post-shortlist states in which the student can still edit Step 4 (add documents,
# revise narrative). Completion is NOT a freeze — the student keeps these abilities
# after confirming, and while an interview is in progress, so an admin can ask for
# more documentation. Excludes terminal states (accepted/rejected/withdrawn).
POST_SHORTLIST_EDITABLE = ('shortlisted', 'profile_complete', 'interviewing', 'interviewed')
