"""
The reviewer -> QC hand-off check: which completeness parts must still be done before
``verify-accept`` may move a case to AWAITING QC.

Owner ruling 28 Nov 2026 ("1"): the hand-off re-checks only what can still be FIXED at that stage.

Once an application has been SUBMITTED (``profile_completed_at`` set) and is at ``interviewing`` or
``interviewed``, the student no longer sees the wizard (quiz, story, address, family, funding show
only at ``shortlisted``) — only the Action Centre, which can still take documents and consent. So a
gap in the quiz, the story, the address, the family roster or the funding answers can be fixed by
nobody, and re-checking it only strands the case. Case 513 is the instance: its quiz was wiped by
sign-in bug #81 and can never come back, so the case could never reach QC.

For those applications the hand-off counts ONLY ``HANDOFF_PARTS_LATE``. Every other application
(``shortlisted``, ``profile_complete``, or one never submitted) keeps the FULL
``application_completeness()['complete']`` check, exactly as before.

⛔ This module READS ``application_completeness`` and never changes it. Its answer still drives
every other screen and gate (the student's wizard, the consent gate, ``revert_if_profile_incomplete``).
"""
from .completeness import application_completeness

# The statuses at which a submitted application is past the wizard (Action Centre only).
HANDOFF_LATE_STATUSES = ('interviewing', 'interviewed')

# What the hand-off still re-checks for such an application: the parts the Action Centre can fix.
HANDOFF_PARTS_LATE = ('documents_done', 'consent_done', 'guardian_docs_done')

# Every part of the full check, in `application_completeness`'s own order.
HANDOFF_PARTS_FULL = (
    'quiz_done', 'details_done', 'funding_done', 'documents_done', 'consent_done',
    'address_done', 'guardian_docs_done', 'family_done',
)


def handoff_parts(application):
    """The completeness parts the hand-off counts for this application (a tuple of keys)."""
    if (application.profile_completed_at is not None
            and application.status in HANDOFF_LATE_STATUSES):
        return HANDOFF_PARTS_LATE
    return HANDOFF_PARTS_FULL


def handoff_ready(application, completeness=None):
    """``(ready, missing)``: may the case be handed to QC, and which counted parts are not done.

    ``completeness`` is the caller's ``application_completeness(application)`` when it already has
    one (the cockpit payload computes it once); otherwise it is computed here. For the full check
    ``ready`` equals ``completeness['complete']`` (that value is the AND of the same eight parts).
    """
    if completeness is None:
        completeness = application_completeness(application)
    missing = [part for part in handoff_parts(application) if not completeness.get(part)]
    return (not missing), missing


def handoff_payload(application, completeness=None):
    """The served form: ``{'ready': bool, 'missing': [part keys]}`` (the cockpit reads this)."""
    ready, missing = handoff_ready(application, completeness)
    return {'ready': ready, 'missing': missing}
