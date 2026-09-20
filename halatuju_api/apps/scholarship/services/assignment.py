"""
Assigning a reviewer, pausing one, and the income-route switch.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
import logging

from django.utils import timezone

from .errors import AssignmentError, PauseError
from .queries_sla import is_ready_for_assignment
from .ready_profiles import generate_ready_profile

#: ⚠ THE PACKAGE NAME, WRITTEN OUT. Never `__name__`: in a submodule that reads
#: `apps.scholarship.services.<module>`, and the one `assertLogs('apps.scholarship.services')`
#: site would still pass (a parent logger records its children) while the name on every line
#: changed underneath it. H11 met exactly this in `views_admin`.
logger = logging.getLogger('apps.scholarship.services')



# The roles that may be assigned to review an application (and therefore act on it — record a
# verdict, propose interview times, etc.). SINGLE SOURCE OF TRUTH: scheduling._can_review imports
# this so the interview surface can never drift out of step with the rest of the review surface
# again (a stale copy here silently blocked a 'qc' reviewer from proposing interview times —
# 2026-07-10). A 'partner' (org rep) is never a review target — and neither is a 'finance' admin
# (Sprint 14, 2026-07-23): finance has NO B40 scope at all, so assigning it a case would hand a
# write on an application it cannot even read. Its absence here is a decision, not an oversight;
# tests in test_org_gates.py assert finance is refused review and never appears in the
# assignable-admins dropdown.
REVIEW_ROLES = ('reviewer', 'super', 'admin', 'qc', 'org_admin')


def _can_review(admin):
    """A valid assignment target is an active reviewer, admin, qc, or super. Assignment grants
    selective WRITE access: a view-all 'admin' or the senior 'qc' role sees every application
    read-only but can only ACT on those assigned to them (2026-07). The 'qc' role can ALSO review
    its assigned cases (a senior QC who reviews + oversees); its own reviewed cases are then QC'd
    by someone else (the self-QC guard in _require_qc). A 'partner' (org rep) cannot be assigned.

    ⚠ **PAUSED people are refused HERE and nowhere else** (request #10, 2026-08-02). Pause means
    "no NEW work", so it belongs on the one gate that hands work out. It must NOT be copied into
    `scheduling._can_review`: that gates writes on cases somebody is ALREADY holding, and a paused
    reviewer has to be able to finish the interviews they started (owner's ruling). The two
    functions look like mirrors and this is the one place they legitimately differ — which is
    exactly why it is written down in both."""
    if admin is None or not getattr(admin, 'is_active', False):
        return False
    if getattr(admin, 'paused_at', None) is not None:
        return False
    return bool(getattr(admin, 'is_super_admin', False)) or admin.role in REVIEW_ROLES





def set_paused(admin, paused, *, now=None):
    """Step a reviewer back from NEW work, or bring them back. Returns the admin row.

    ONE setter for both routes — the reviewer's own profile and an org_admin acting for them —
    because "pause" that means two slightly different things depending on who pressed it is how
    the two drift. Idempotent: pausing an already-paused person keeps the ORIGINAL timestamp, so
    a stray second click cannot rewrite when they stepped back.

    ⚠ It does NOT touch `is_active`, and nothing here is allowed to start doing so. Pause and
    revoke are different answers to different questions; see the field docstring on `PartnerAdmin`.

    ⚠ Pause is only meaningful for somebody who can be ASSIGNED work. Pausing a `finance` admin or
    a referral `partner` would set a flag that changes nothing and shows a "Paused" pill on a
    person who was never in the queue — a control that lies. Refused as 'not_reviewable'.
    """
    if admin is None:
        raise PauseError('not_found')
    if not getattr(admin, 'is_active', False):
        # A revoked account has no work coming either way; pausing it would imply it might.
        raise PauseError('not_active')
    is_target = (bool(getattr(admin, 'is_super_admin', False))
                 or getattr(admin, 'role', '') in REVIEW_ROLES)
    if not is_target:
        raise PauseError('not_reviewable')

    want = bool(paused)
    if want == (admin.paused_at is not None):
        return admin                       # idempotent — keep the original stamp
    admin.paused_at = (now or timezone.now()) if want else None
    admin.save(update_fields=['paused_at'])
    return admin


# Unassigning must not orphan a case whose reviewer has already done the work. Once
# findings are submitted (status 'interviewed') or a decision is recorded (recommended and
# the post-award chain), a plain unassign is refused — the super must Reopen first (which
# walks the status back a step) so a completed verdict is never silently detached.
_UNASSIGN_BLOCKED_STATUSES = frozenset({
    'interviewed', 'recommended', 'awarded', 'active', 'maintenance', 'closed',
})

# WHEN A CASE MAY CHANGE HANDS AT ALL (owner, 2026-07-13). A reviewer is assigned to DO the
# review, so assignment only makes sense while there is a review to do:
#
#   shortlisted / rejected  —  not ready, or never will be. Nothing to review.
#   Completed               —  the case is waiting for a reviewer. ASSIGNABLE.
#   interviewing            —  a reviewer is working it; a super may hand it to someone else.
#   Awaiting QC onward      —  the review is OVER. The verdict is in; retargeting it would
#                              detach a completed piece of work from the person who did it.
#
# This gates EVERY change — assign, reassign AND unassign. Before this, only the FIRST assignment
# of an unassigned app was gated (on is_ready_for_assignment), and reassignment was explicitly
# allowed at any status — so all 31 awarded and 26 rejected students were silently retargetable
# from the list dropdown. `is_ready_for_assignment` still applies ON TOP for a first assignment,
# so this can only ever be stricter, never looser.
ASSIGNABLE_STATUSES = frozenset({'profile_complete', 'interviewing'})


def is_assignable(application):
    """May this application's reviewer be changed at all right now? See ASSIGNABLE_STATUSES."""
    return application.status in ASSIGNABLE_STATUSES


def assign_reviewer(application, *, reviewer, by_admin, now=None):
    """F7: (re)assign an application to a reviewer, audited. The caller must already
    have checked the actor is a super-admin. Rules:
      - a non-null target must be an active reviewer/super (else AssignmentError
        'not_reviewer');
      - the FIRST assignment of an unassigned app is gated on is_ready_for_assignment
        (else 'not_ready'); a reassignment/unassignment of an already-assigned app is
        allowed any time (a super may redistribute work mid-flight);
      - UNASSIGN (reviewer=None) of a case still in interview is refused once findings are
        in (status in _UNASSIGN_BLOCKED_STATUSES → 'findings_submitted'); otherwise it tears
        down the interview (releases any booking/proposed slots + notifies) and walks status
        'interviewing' → 'profile_complete', preserving the invariant "interviewing ⇒
        assigned_to set" and returning the case to the assignable pool;
      - every change writes an AssignmentEvent (from -> to, by whom) and stamps
        assigned_at (null on unassign). A no-op (target unchanged) writes nothing.
    Returns the application.
    """
    from ..models import AssignmentEvent
    from .. import usage as _usage
    now = now or timezone.now()

    if reviewer is not None and not _can_review(reviewer):
        # ⚠ SAY WHICH REFUSAL. `_can_review` folds three different facts into one False, and
        # telling an org_admin that a paused volunteer "is not a reviewer" is simply untrue — she
        # is one, she has stepped back. Found by walking pause end-to-end on production
        # (2026-08-03); the dropdown disables a paused option, so this is reached from a page that
        # loaded BEFORE somebody was paused, which is precisely when a wrong reason misleads most.
        # Revoked is checked first: a revoked account is a bigger fact than a pause on top of it.
        raise AssignmentError(
            'not_reviewer' if not getattr(reviewer, 'is_active', False)
            else 'reviewer_paused' if getattr(reviewer, 'paused_at', None) is not None
            else 'not_reviewer')

    current = application.assigned_to
    if (current.id if current else None) == (reviewer.id if reviewer else None):
        return application  # no-op

    unassigning = reviewer is None and current is not None

    # Checked FIRST, ahead of the general stage gate: an unassign at 'interviewed' or beyond is
    # also not-assignable, but 'findings_submitted' tells the super what to DO about it (reopen the
    # decision), where 'not_assignable' would only tell them they can't. The more specific,
    # more actionable refusal wins.
    if unassigning and application.status in _UNASSIGN_BLOCKED_STATUSES:
        raise AssignmentError('findings_submitted')

    # A case may only change hands while there is a review to do (Completed / interviewing).
    # Gates assign, REASSIGN and unassign alike — a rejected or awarded student has no live
    # review, and retargeting one would detach finished work from the person who did it.
    if not is_assignable(application):
        raise AssignmentError('not_assignable')

    # Ready-gate applies only to the first assignment of an unassigned application.
    if current is None and reviewer is not None and not is_ready_for_assignment(application, now):
        raise AssignmentError('not_ready')

    AssignmentEvent.objects.create(
        application=application, from_admin=current, to_admin=reviewer,
        by_email=getattr(by_admin, 'email', '') or '',
    )
    status_reverted = False
    if unassigning:
        # Release the outgoing reviewer's interview artefacts BEFORE we clear assigned_to
        # (the teardown notifies that reviewer). Best-effort — never block the unassignment.
        from .. import scheduling
        try:
            scheduling.release_for_unassign(application, now=now)
        except Exception:
            logger.exception('release_for_unassign failed for application %s', application.id)
        if application.status == 'interviewing':
            application.status = 'profile_complete'
            status_reverted = True
    application.assigned_to = reviewer
    application.assigned_at = now if reviewer is not None else None
    # Reset the verdict-SLA nudge stamps (TD-131) so the new reviewer's clock starts clean —
    # otherwise a prior owner's stamps would suppress nudges for the new assignee.
    application.review_nudged_soon_at = None
    application.review_nudged_overdue_at = None
    application.review_escalated_at = None
    _fields = ['assigned_to', 'assigned_at',
               'review_nudged_soon_at', 'review_nudged_overdue_at', 'review_escalated_at']
    if status_reverted:
        _fields.append('status')
    application.save(update_fields=_fields)

    # Notify the reviewer they have a new applicant to review. Only on an actual
    # assignment (not an unassign); the no-op short-circuit above means an unchanged
    # assignee never reaches here, so we never re-send. Best-effort.
    if reviewer is not None and getattr(reviewer, 'email', ''):
        from .. import review_sla
        from ..emails import send_reviewer_assigned_email
        from ..pool import pool_ref
        # Per-organisation SLA (Org Config Sprint C). This read used to carry its own dead
        # default of 7 against the sweep's 10 — base.py always defined the setting so it never
        # fired, but the review-by date in this email and the nudge sweep's due date now come
        # from the ONE delegation and cannot drift.
        # ⚠ AND SINCE 2026-09-15 THE ARITHMETIC IS SHARED TOO, not just the number: `review_sla`
        # is the one home for `assigned_at + sla`, so the date a reviewer is promised here is
        # computed by the same line the nudge sweep and the Overview's bands use.
        review_by = review_sla.review_due(
            application.assigned_at or now, application.owning_organisation).date()
        with _usage.usage_context(application=application):
            send_reviewer_assigned_email(
                to_email=reviewer.email,
                reviewer_name=getattr(reviewer, 'name', ''),
                ref=pool_ref(application.id),
                programme=getattr(application.cohort, 'name', '') if application.cohort else '',
                review_by=review_by.strftime('%d %b %Y'),
            )

    # F7: advance notice to the STUDENT — who will interview them + how, so they expect the
    # call and pick up. Gated by STUDENT_ASSIGNMENT_EMAIL_ENABLED (OFF until reviewers give
    # non-objection to sharing their contact). The reviewer's phone is included unless they
    # opted out (ReviewerProfile.share_phone_with_students). Best-effort; never blocks assignment.
    if reviewer is not None:
        from django.conf import settings as _settings
        if getattr(_settings, 'STUDENT_ASSIGNMENT_EMAIL_ENABLED', False):
            from ..emails import english_only_email, send_student_assigned_reviewer_email
            profile = application.profile
            student_email = (application.notify_email
                             or getattr(profile, 'contact_email', '') or '')
            with _usage.usage_context(application=application):
                send_student_assigned_reviewer_email(
                    student_email,
                    student_name=getattr(profile, 'name', '') if profile else '',
                    reviewer_name=getattr(reviewer, 'name', ''),
                    english_only=english_only_email(application),
                )

    # Check-2 → Reviewer handoff: auto-draft the sponsor profile so the reviewer lands on
    # a ready profile to orient from (the owner's design). Fires only on the FIRST
    # assignment, reuses the STEP-3 generator (idempotent; omits unresolved claims), and is
    # gated behind the SAME CHECK2_AUTO_GENERATE flag as the sweep — so it stays dark (no
    # billable Gemini calls) until deliberately switched on, and never re-drafts an existing
    # profile. Best-effort: a generation failure or AI outage must never block the handoff.
    if reviewer is not None and current is None:
        from django.conf import settings as _settings
        if getattr(_settings, 'CHECK2_AUTO_GENERATE', False):
            sp = getattr(application, 'sponsor_profile', None)
            if sp is None or sp.generated_at is None:
                try:
                    generate_ready_profile(application)
                except Exception:
                    pass  # never let profile drafting break the assignment
    return application


def switch_income_route(application, *, route, earner='', members=None, by='student'):
    """Student self-serve income route switch (post-submit, Action Centre). Writes
    ``income_route`` + the route's identifying fields, audits the change to the
    structured log, and recomputes the resolution queue so the new route's missing-doc
    tickets appear and the old route's gap auto-resolves.

    Deliberately does NOT touch submission status or call ``revert_if_profile_incomplete``:
    a submitted student is NEVER re-blocked (consent-gate-v2) — the new route's missing
    documents become Check-2 Action-Centre tickets, not a submission block. (Routing the
    switch through the broad details PATCH would revert profile_complete → shortlisted the
    moment the salary route's new docs are unmet — the trap this endpoint avoids.)

      route='str'    → income_earner set, income_working_members cleared.
      route='salary' → income_working_members set, income_earner cleared.
    """
    members = list(members or [])
    from_route = (getattr(application, 'income_route', '') or '').strip()
    if route == 'str':
        application.income_route = 'str'
        application.income_earner = earner or ''
        application.income_working_members = []
    elif route == 'salary':
        application.income_route = 'salary'
        application.income_working_members = members
        application.income_earner = ''
    else:
        raise ValueError(f'switch_income_route: bad route {route!r}')
    application.save(update_fields=['income_route', 'income_earner', 'income_working_members'])
    # Audit (owner's call: audit-log only, no officer pre-interview flag). Cloud Logging
    # is the durable trail; no in-app surface + no migration.
    logger.info('income_route_switch app=%s from=%s to=%s earner=%s members=%s by=%s',
                application.id, from_route or '(none)', route, earner or '-', members or '-', by)
    from ..resolution import sync_resolution_items
    sync_resolution_items(application)
    return application


def reconcile_income_route(application, *, by='auto'):
    """Silently align ``income_route`` with whichever evidence ACTUALLY cleared the income gate,
    called at consent (income is established by then, or consent would have been blocked). Fixes
    the route-vs-evidence mismatch at the source so the officer's verdict reads the correct route
    — a student who declared STR but documented salary (or vice versa) is relabelled here instead
    of surfacing a red route-mismatch downstream.

      STR route  + no valid STR + a complete salary cluster → switch to 'salary'.
      salary route + no complete salary cluster + a valid STR → switch to 'str'.
      both hold, or the declared route already matches the evidence → no change.

    Reuses ``switch_income_route`` (which audit-logs and recomputes the resolution queue without
    ever re-blocking a submission). Idempotent + no-op-safe. Returns the resulting route."""
    from ..income_engine import (household_str_status, salary_income_satisfied,
                                 effective_working_members, member_cluster_complete)
    route = (getattr(application, 'income_route', '') or '').strip()
    str_grade, str_member = household_str_status(application)
    str_ok = str_grade is not None
    salary_ok = salary_income_satisfied(application)
    if route == 'str' and not str_ok and salary_ok:
        members = [m for m in effective_working_members(application, any_route=True)
                   if member_cluster_complete(application, m)]
        switch_income_route(application, route='salary', members=members, by=by)
        return 'salary'
    if route == 'salary' and not salary_ok and str_ok:
        switch_income_route(application, route='str', earner=str_member or '', by=by)
        return 'str'
    return route
