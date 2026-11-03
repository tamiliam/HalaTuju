"""Team tables T5b (2026-11-03): QC never decides their own — the separation-of-duties half of the QC gate.

Roadmap `docs/plans/2026-11-01-team-tables-roadmap.md` T5 (owner "approve all"): *"QC implicitly sees ALL students
and may decide on any except those they reviewed / interviewed / were assigned."* `_AdminBase._require_qc` asks
`refusal` after the permission, the org fence and the stage; it is the ONE answer to "may this person QC this case?".

WHY IT WIDENED. A `qc` holder WRITES on any case in their organisation (`_AdminBase._can_review_app`), so the current
`assigned_to` alone never proved who worked a case. Until T5b the guard read only that and the verdict recorder: a
reassign laundered self-QC, and an interview or a verify-accept on an unassigned case did not count. It now refuses
the caller when they:
  * are the CURRENT assignee                                     -> `self_qc_forbidden` (as before)
  * RECORDED the verdict (`verdict_decided_by`, by email)          -> `self_verdict_qc_forbidden` (as before)
  * were EVER assigned it (`AssignmentEvent` to / from them)       -> `self_assigned_qc_forbidden`
  * are the interviewer on ANY session, a DRAFT included, or proposed its interview times
    (`InterviewSession.interviewer`, `InterviewSlot.reviewer`)     -> `self_interview_qc_forbidden`
  * did other review work on it: the verify-accept (`verified_by`), or an activity row for a verdict, a
    verify-accept, a decline sent to QC or an interview submitted (`StaffActivity`; a verdict re-recorded by
    somebody else overwrites `verdict_decided_by`, the row does not)  -> `self_review_qc_forbidden`
The first two keep their order and codes, so a case that meets several answers as it did before.

⚠ A DRAFT INTERVIEW COUNTS (lead ruling 2026-11-03): sitting in the interview is the work, whether or not it was
submitted. ⚠ A QUERY to the student does NOT count: a QC may ask for a missing document while checking.
⚠ A SUPER IS EXEMPT — the owner's override, as before. The organisation admin (who holds `qc`) is not.
⚠ ADD A NEW KIND OF REVIEW WORK HERE (and a test in `tests/test_qc_self_sufficient.py`), never beside a QC door.
"""
from django.db.models import Q

SELF_ASSIGNED_NOW = 'self_qc_forbidden'
SELF_VERDICT = 'self_verdict_qc_forbidden'
SELF_ASSIGNED_BEFORE = 'self_assigned_qc_forbidden'
SELF_INTERVIEW = 'self_interview_qc_forbidden'
SELF_REVIEW = 'self_review_qc_forbidden'

MESSAGES = {
    SELF_ASSIGNED_NOW: 'You reviewed this case — it must be QC-checked by someone else.',
    SELF_VERDICT: 'You recorded this verdict — it must be QC-checked by someone else.',
    SELF_ASSIGNED_BEFORE: 'You were assigned this case before — it must be QC-checked by someone else.',
    SELF_INTERVIEW: 'You interviewed this student — the case must be QC-checked by someone else.',
    SELF_REVIEW: 'You worked on this review — it must be QC-checked by someone else.',
}

#: The activity verbs that are REVIEW work on a case (the actor is whoever pressed the button).
REVIEW_VERBS = ('verdict_recorded', 'verify_accept', 'decline_sent_to_qc', 'interview_submitted')


def _same_email(stamp, admin):
    mine = (getattr(admin, 'email', '') or '').strip().lower()
    return bool(mine) and (stamp or '').strip().lower() == mine


def refusal(admin, app):
    """``None`` when ``admin`` may QC ``app`` as far as separation of duties goes, else the refusal
    ``code`` (a key of `MESSAGES`). The permission, the fence and the stage are the caller's."""
    from .models import AssignmentEvent, InterviewSession, InterviewSlot, StaffActivity
    if admin is None or app is None:
        return SELF_ASSIGNED_NOW            # never reached by the view; fail closed
    if admin.is_super:
        return None
    if app.assigned_to_id == admin.id:
        return SELF_ASSIGNED_NOW
    if _same_email(getattr(app, 'verdict_decided_by', ''), admin):
        return SELF_VERDICT
    if _same_email(getattr(app, 'verified_by', ''), admin):
        return SELF_REVIEW
    pk = getattr(app, 'pk', None)
    if pk is None:
        return None                         # an unsaved case has no history to read (test doubles)
    if AssignmentEvent.objects.filter(application_id=pk).filter(
            Q(to_admin=admin) | Q(from_admin=admin)).exists():
        return SELF_ASSIGNED_BEFORE
    if (InterviewSession.objects.filter(application_id=pk, interviewer=admin).exists()
            or InterviewSlot.objects.filter(application_id=pk, reviewer=admin).exists()):
        return SELF_INTERVIEW
    if StaffActivity.objects.filter(actor=admin, subject_type='application', subject_id=pk,
                                    verb__in=REVIEW_VERBS).exists():
        return SELF_REVIEW
    return None
