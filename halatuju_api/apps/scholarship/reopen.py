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

from .models import DecisionReopen, SponsorProfile


class ReopenError(Exception):
    """Raised with a stable .code for the view to surface (e.g. 'not_decided')."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def open_reopen(app):
    """The currently-OPEN reopen row for an application, or None."""
    return app.decision_reopens.filter(closed_at__isnull=True).order_by('-created_at').first()


def reopen_decision(app, *, by_admin, reason):
    """Reopen a recorded decision: hold the sponsor profile, open an audit row.

    Validates a decision exists and isn't already reopened, and that a reason was
    given (a reopen asserts a reviewer error — it must be justified). Returns the
    new DecisionReopen row.
    """
    reason = (reason or '').strip()
    if app.verdict_decided_at is None:
        raise ReopenError('not_decided')
    if app.decision_reopened_at is not None:
        raise ReopenError('already_reopened')
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
        # A pending (cool-off) decline is part of the decision being reversed — clear it so the
        # reopened case is a clean slate (the reviewer re-decides from 'interviewed').
        if app.decline_due_at or app.pending_rejection_category:
            app.pending_rejection_category = ''
            app.decline_due_at = None
            app.pending_decline_by = ''
            fields += ['pending_rejection_category', 'decline_due_at', 'pending_decline_by']
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
    """
    row = open_reopen(app)
    if row is None:
        raise ReopenError('not_reopened')

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
