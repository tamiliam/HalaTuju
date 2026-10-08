"""Decision reopen / cancel-reopen — reversing a finalised decision.

A superadmin REOPENS a recorded decision when they find an error on the assigned
reviewer's part. Reopening UNPUBLISHES the sponsor profile (held in abeyance) and
opens a ``DecisionReopen`` audit row. Then either:

  - ``cancel_reopen(app)`` — no change was needed → restore the prior published
    state exactly; the row closes with ``resulted_in_change=False`` (does NOT count
    against the reviewer).
  - the officer re-records the decision (record-verdict / reject) — the view calls
    ``close_reopen_with_change(app)`` which closes the open row with
    ``resulted_in_change=True`` (a real correction → COUNTS); the finalise path
    re-publishes per the new decision.

The per-reviewer "corrections" count = ``DecisionReopen`` rows with
``resulted_in_change=True`` (counting model B, the owner's call 2026-06-18).
"""
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from . import birth_state
from .models import DecisionReopen, SponsorProfile


#: TD-371: the refusal when a cancel would restore `recommended` with an IC that fails the
#: intake's "Born in" rule. It names the WHOLE route, because the refusal is strict even for a
#: case QC already accepted with a recorded override (a super reopening it about income, say):
#: QC accept again — recording the reason again — then cancel the reopen to clear it, at once:
#: QC accept publishes the sponsor profile and clears its alert stamp, and the cancel re-publishes
#: it and clears the stamp again, so a realtime sweep that runs between the two alerts sponsors
#: about the same student twice.
BIRTH_STATE_RULE_FAILED = (
    "The student's IC does not meet this intake's \"Born in\" rule now, so cancelling cannot "
    'put the case back to Recommended unchecked. Accept it through QC instead, recording the '
    'override reason again if the student should still be accepted (an earlier override does '
    'not carry over); then cancel this reopen to clear it STRAIGHT AWAY — the QC accept '
    'publishes the profile to sponsors again, and if the new-student alert runs before the '
    'cancel, sponsors are alerted twice.')

#: The sentence a view shows for a code; any other code is shown as itself (as before).
REOPEN_MESSAGES = {
    'decline_pending': ('This decline has not been sent to the student yet. Cancel the '
                        'pending decline instead — it returns the case to where it was.'),
    'birth_state_rule_failed': BIRTH_STATE_RULE_FAILED,
    birth_state.IC_UNLOCKED: birth_state.IC_UNLOCKED_MESSAGE,
}


class ReopenError(Exception):
    """Raised with a stable .code for the view to surface (e.g. 'not_decided') and a
    .message for its `error` field."""
    def __init__(self, code):
        self.code = code
        self.message = REOPEN_MESSAGES.get(code, code)
        super().__init__(code)


def open_reopen(app):
    """The currently-OPEN reopen row for an application, or None."""
    return app.decision_reopens.filter(closed_at__isnull=True).order_by('-created_at').first()


def latest_reopen(app):
    """The most recent reopen row (open OR closed), or None — the audit anchor for the
    decision-history trail on a decided case. A closed reopen that led to a change is how a
    QC override shows up: reviewer recommended → QC reopened (with a reason) → re-decided."""
    return app.decision_reopens.order_by('-created_at').first()


def reopen_decision(app, *, by_admin, reason):
    """Reopen a recorded decision: hold the sponsor profile, open an audit row.

    Validates a decision exists and isn't already reopened, and that a reason was
    given (a reopen asserts a reviewer error — it must be justified). Returns the
    new DecisionReopen row.

    ⚠ AN EMBARGOED DECLINE IS REFUSED — `decline_pending` (TD-349, lead decision 2026-10-06).
    While the decline's email has not gone, the way to re-decide is
    `services.decline.cancel_pending_decline` (the cockpit's "cancel the pending decline"):
    it restores the snapshot status, the award amount and a lapsed sponsorship, leaves no
    reopen flag, and what the student sees does not move. Two earlier designs were wrong:
      - clearing the pending markers here (the original code) left the case 'rejected' with
        nothing masking it — she saw the decline at once and the email never went;
      - reversing the decline here (TD-349 round 1) reopened INTO the funnel: a funded
        student landed at active/maintenance with the reopen flag (where Decline + Save
        clears the award of a sponsored student), a failed sponsorship reinstatement showed
        only in a log, the cancel's award audit line was attributed to a reopen, and a
        decline from 'interviewing' reached AWAITING QC through cancel_reopen (TD-356).
    The refusal comes before any write. A decline whose email HAS gone is reopened as before:
    the case stays 'rejected', reopened, for the verdict to be re-recorded.
    """
    # Only text is a reason: a number or a list (a hand-made request) is read as none, so the
    # `reason_required` refusal answers it rather than a 500 at `.strip()` (TD-375's review).
    reason = reason.strip() if isinstance(reason, str) else ''
    if app.verdict_decided_at is None:
        raise ReopenError('not_decided')
    if app.decision_reopened_at is not None:
        raise ReopenError('already_reopened')
    if app.decline_due_at or app.pending_rejection_category:
        raise ReopenError('decline_pending')
    if not reason:
        raise ReopenError('reason_required')

    sp = SponsorProfile.objects.filter(application=app).first()
    was_published = bool(sp and sp.anon_published)

    with transaction.atomic():
        if was_published:
            # Hold the profile from the pool. Reset realtime_notified_at so a later
            # re-publish alerts sponsors again (mirrors AdminPublishAnonProfileView).
            sp.anon_published = False
            sp.anon_published_at = None
            sp.realtime_notified_at = None
            sp.save(update_fields=['anon_published', 'anon_published_at',
                                   'realtime_notified_at', 'updated_at'])
        app.decision_reopened_at = timezone.now()
        fields = ['decision_reopened_at']
        # Reopening returns the case one step toward the reviewer so it can be re-decided.
        # QC (2026-07) two-step mapping (kept invertible by cancel_reopen — the current status
        # uniquely identifies where it came from):
        #   recommended  → interviewed   (super revisits a QC-cleared case → back to AWAITING QC)
        #   interviewed  → interviewing  (QC 'reopen' sends the awaiting-QC case back to the reviewer)
        # A subsequent decline is still bucketed as 'interview' (both interviewed & interviewing are
        # in INTERVIEW_REJECT_FROM). A 'sponsored' (funded) case is post-award and stays put.
        if app.status == 'recommended':
            app.status = 'interviewed'
            fields.append('status')
        elif app.status == 'interviewed':
            app.status = 'interviewing'
            fields.append('status')
        app.save(update_fields=fields)
        row = DecisionReopen.objects.create(
            application=app,
            reviewer=app.assigned_to,
            reopened_by=getattr(by_admin, 'email', '') or '',
            reason=reason,
            was_published=was_published,
        )
    return row


def cancel_reopen(app):
    """Close a reopen with NO change: restore the prior published state exactly.

    The decision is unchanged, so we simply re-publish the profile iff it was
    published before (the same already-vetted text), clear the reopened flag, and
    close the audit row with resulted_in_change=False (no reviewer correction).

    ⚠ TD-371: A CANCEL THAT WOULD RESTORE `recommended` RE-READS THE "BORN IN" RULE. That restore
    skips QC accept, the one place the rule is re-checked after submit, and the IC may have
    changed while the case was reopened (a super's lock release). When the CURRENT IC fails the
    intake's CURRENT rule the cancel is refused before any write (`birth_state_rule_failed`):
    QC accept is the way back, where the floor applies and an override is recorded. Every other
    cancel is untouched.

    ⚠ And such a cancel needs a LOCKED IC on a ruled intake (`birth_state_ic_unlocked`, checked
    first, no override — `birth_state.ic_unlocked_for_rule`): a lock released while the case was
    reopened would otherwise ride back into `recommended`, where the student can still change it.
    """
    row = open_reopen(app)
    if row is None:
        raise ReopenError('not_reopened')
    if app.status == 'interviewed' and birth_state.ic_unlocked_for_rule(
            app.profile, getattr(app.cohort, 'allowed_birth_states', None)):
        raise ReopenError(birth_state.IC_UNLOCKED)
    if app.status == 'interviewed' and birth_state.meets_rule(
            getattr(app.profile, 'nric', '') if app.profile else '',
            getattr(app.cohort, 'allowed_birth_states', None)) is False:
        raise ReopenError('birth_state_rule_failed')

    with transaction.atomic():
        if row.was_published:
            sp = SponsorProfile.objects.filter(application=app).first()
            if sp is not None:
                sp.anon_published = True
                sp.anon_published_at = timezone.now()
                sp.realtime_notified_at = None
                sp.save(update_fields=['anon_published', 'anon_published_at',
                                       'realtime_notified_at', 'updated_at'])
        app.decision_reopened_at = None
        restore = ['decision_reopened_at']
        # Mirror of reopen (invert the two-step mapping by current status):
        #   interviewed  → recommended  (undo a super reopen of a QC-cleared case)
        #   interviewing → interviewed  (undo a QC 'reopen' — restore to AWAITING QC)
        if app.status == 'interviewed':
            app.status = 'recommended'
            restore.append('status')
            if app.stamp_first('recommended_at'):
                restore.append('recommended_at')
        elif app.status == 'interviewing':
            app.status = 'interviewed'
            restore.append('status')
        app.save(update_fields=restore)
        row.resulted_in_change = False
        row.closed_at = timezone.now()
        row.save(update_fields=['resulted_in_change', 'closed_at'])
    return row


def close_reopen_with_change(app):
    """Close an open reopen as a REAL correction (counts against the reviewer).

    Called from the decision-recording views (record-verdict / reject) when the
    application was in a reopened state — the officer re-saved the decision, which
    is a correction under counting model B. The re-publish (on accept) is handled by
    the finalise path in the calling view; here we only close the audit row and
    clear the reopened flag. No-op if the app isn't reopened.
    """
    if app.decision_reopened_at is None:
        return None
    row = open_reopen(app)
    if row is not None:
        row.resulted_in_change = True
        row.closed_at = timezone.now()
        row.save(update_fields=['resulted_in_change', 'closed_at'])
    app.decision_reopened_at = None
    app.save(update_fields=['decision_reopened_at'])
    return row


def reviewer_correction_counts():
    """Map {reviewer_id: corrections} across all reviewers (one query).

    corrections = reopens that led to a real change (resulted_in_change=True).
    """
    rows = (DecisionReopen.objects
            .filter(resulted_in_change=True, reviewer__isnull=False)
            .values('reviewer')
            .annotate(c=Count('id')))
    return {r['reviewer']: r['c'] for r in rows}


def reviewer_correction_count(admin):
    """corrections attributed to a single reviewer (0 if none / None)."""
    if admin is None:
        return 0
    return DecisionReopen.objects.filter(
        resulted_in_change=True, reviewer=admin).count()


def reviewer_reopens(admin, *, organisation_id=None):
    """One reviewer's corrections AS ROWS — newest first — with the reason recorded at the time.

    ⚠ The count alone is not a fair thing to show. 17 of BrightPath's 65 decisions carry a reopen and
    several were caused by OUR OWN defects, not by the reviewer's judgement; a bare number beside a
    volunteer's name reads as a competence score to whoever hands out the next case. The reason is
    what distinguishes "the merit band was misread" from "our pathway engine was wrong that week", so
    the reasons travel WITH the number and the reviewers table deliberately carries neither.

    ⚠ `organisation_id` FENCES the read. `reviewer_correction_counts()` is deliberately unfenced (it
    feeds the assignment dropdown, which is already fenced by its own queryset); this one is read by
    a per-reviewer surface an org_admin opens, so it must not reach across tenants.
    """
    if admin is None:
        return []
    qs = DecisionReopen.objects.filter(resulted_in_change=True, reviewer=admin)
    if organisation_id is not None:
        qs = qs.filter(application__owning_organisation_id=organisation_id)
    return list(qs.select_related('application').order_by('-id'))
