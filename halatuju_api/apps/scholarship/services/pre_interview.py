"""Request #75 (analysis 172, 2026-11-16): reject a student BEFORE interview.

A student at Awaiting review (`profile_complete`) with NO reviewer, whose documents already show
they do not qualify, can be declined without an interview. The organisation asked for the QC
reject's shape (decisions.md 2026-11-16), so this is a thin door onto the machinery that already
exists, never a second one:

* the decision is recorded at once by `decline._record_reject` in its own bucket, `pre_interview`
  ("Rejected before interview"), with the person's note on `rejection_comments` and the main reason
  on `rejection_reason`. Both are INTERNAL: the student gets the warm reviewed-applicant decline
  (`student_decisions._DECLINE_TEMPLATES['pre_interview']` is the 'interview' copy), never the note;
* the email is held for the organisation's QC decline hold (`qc_decline_hold_hours`), the same
  cool-off and markers the QC decision uses (`admin_reject`, which refuses this bucket itself). The release cron sends it; `cancel_pending_decline` undoes it and
  puts the student back at Awaiting review with no reviewer. No second timer;
* who: whoever holds the `qc` permission key (QC, org admins, super; never a reviewer). The view
  checks the key; this module checks the case.

It never counts against a reviewer: the case has none, and every reviewer figure reads
`assigned_to` (`views_admin/reviewers._reviewer_workloads`).
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import ScholarshipApplication

CATEGORY = 'pre_interview'
#: The one stage this door works at. Served (`offer_for`), so the cockpit keeps no copy.
PRE_INTERVIEW_FROM = ('profile_complete',)
REASONS = tuple(code for code, _ in ScholarshipApplication.REJECTION_REASONS)
#: The note's limit; the panel counts against the same number.
NOTE_MAX = 2000


def hold_for(application):
    """The QC decline hold for this case's organisation (platform 24 h)."""
    from apps.courses import public as courses_public
    hours = courses_public.org_config.value(application.owning_organisation, 'qc_decline_hold_hours') or 0
    return timedelta(hours=hours)


def is_open_for(application):
    """Is the case where this door works: Awaiting review, nobody assigned?"""
    return application.status in PRE_INTERVIEW_FROM and application.assigned_to_id is None


def offer_for(application, admin):
    """What the cockpit needs to offer the door, or None when it is not offered to this viewer.
    `hold_hours`: how long the decline email is held (the confirm step adds it to the moment of
    confirming; a timestamp here would make two reads of the same case differ, and the detail GET
    is pinned byte-for-byte); `reasons` and `note_max`: the panel's list and limit, served so the
    browser keeps no copy.
    Offered with a reviewer on the case too: the cockpit then says to unassign first."""
    # The stage first: at every other stage this costs no query (the detail GET's pin).
    if application.status not in PRE_INTERVIEW_FROM or admin is None or not admin.has_perm('qc'):
        return None
    return {'hold_hours': hold_for(application).total_seconds() / 3600,
            'reasons': list(REASONS), 'note_max': NOTE_MAX}


def _checked_note(reason, comments):
    if (reason or '') not in REASONS:
        raise ValueError('reason_required')
    comments = (comments or '').strip()
    if not comments:
        raise ValueError('comments_required')
    if len(comments) > NOTE_MAX:
        raise ValueError('comments_too_long')
    return comments


def reject_before_interview(application, admin, reason, comments):
    """Record the decline now and hold its email for the QC hold. Raises ValueError with
    'bad_status' (not Awaiting review), 'has_reviewer', 'reason_required', 'comments_required' or
    'comments_too_long'. The stage and the reviewer are read again under the row lock, so an
    assignment that committed a moment ago wins. Returns True."""
    from .. import staff_activity
    from ..status_lock import StatusRefused, lock_application_for
    from .decline import _record_reject, _send_decline_for
    if application.status not in PRE_INTERVIEW_FROM:
        raise ValueError('bad_status')
    if application.assigned_to_id is not None:
        raise ValueError('has_reviewer')
    comments = _checked_note(reason, comments)
    hold = hold_for(application)
    with transaction.atomic():
        try:
            lock_application_for(application, PRE_INTERVIEW_FROM)
        except StatusRefused:
            raise ValueError('bad_status')
        if application.assigned_to_id is not None:
            raise ValueError('has_reviewer')
        by = getattr(admin, 'email', '') or ''
        _record_reject(application, CATEGORY, by, comments=comments)   # the decision is immediate
        application.rejection_reason = reason
        fields = ['rejection_reason']
        if hold.total_seconds() > 0:
            # `admin_reject`'s embargo, written out: that function refuses this bucket on purpose,
            # so its `/reject/` door (open to the assignee) can never reach this one.
            application.pending_rejection_category = CATEGORY
            application.decline_due_at = timezone.now() + hold
            application.pending_decline_by = by
            fields += ['pending_rejection_category', 'decline_due_at', 'pending_decline_by']
        application.save(update_fields=fields)
    if hold.total_seconds() <= 0:
        _send_decline_for(application)
    staff_activity.record(admin, staff_activity.DECLINED, application,
                          meta={'category': CATEGORY, 'reason': reason})
    return True


def counts(scope):
    """The Programme overview's count of rejections before interview, and by reason (#75).

    Every reason is listed, zero-filled, in the panel's order, like the funnel beside it. A
    cancelled one is not counted: cancel clears the bucket."""
    rows = scope.filter(status='rejected', rejection_category=CATEGORY).values_list(
        'rejection_reason', flat=True)
    by_reason = {code: 0 for code in REASONS}
    total = 0
    for code in rows:
        total += 1
        by_reason[code if code in by_reason else 'other'] += 1
    return {'total': total, 'by_reason': by_reason}
