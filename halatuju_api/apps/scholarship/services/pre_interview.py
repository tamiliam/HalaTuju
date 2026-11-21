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


def checked_assessment(raw_facts, raw_reasons):
    """F3 (I-4): the four facts as the reviewer's assessment stores them (`officer_verdict`), with the
    same Why-on-every-Fail rule (`fail_reasons.keep`). Raises ValueError 'assessment_incomplete' when
    any fact is not Pass or Fail, and 'bad_fail_reasons' for a malformed or unknown reason code."""
    from .. import fail_reasons
    from ..audit import FACTS
    raw_facts = raw_facts if isinstance(raw_facts, dict) else {}
    facts = {f: raw_facts.get(f) for f in FACTS}
    if any(v not in ('pass', 'fail') for v in facts.values()):
        raise ValueError('assessment_incomplete')
    try:
        reasons = fail_reasons.validate(raw_reasons)
    except fail_reasons.BadFailReasons:
        raise ValueError('bad_fail_reasons')
    return {**facts, fail_reasons.KEY: fail_reasons.keep(reasons, facts)}


def _assessment_fields(application, assessment):
    """The assessment goes where a reviewer's does: `officer_verdict`, beside the AI's snapshot of the
    same moment (engine version and LL4 context too), so a later comparison reads one shape. NOT
    `verdict_decided_at`: that stamp means a reviewer's recorded decision, and a held decline that is
    cancelled puts the case back at Awaiting review with no reviewer. Read BEFORE the reject changes
    the case; returns ``{field: value}`` to write with it."""
    from ..verdict_context import verdict_context_or_empty
    from ..verdict_engine import VERDICT_ENGINE_VERSION, build_verdict
    return {'officer_verdict': assessment,
            'ai_verdict_snapshot': build_verdict(application),
            'ai_verdict_engine_version': VERDICT_ENGINE_VERSION,
            'ai_verdict_context': verdict_context_or_empty(application)}


#: F3 review fix 2: the fields the reject writes from the four facts, and a cancel takes back, with
#: the empty value each starts at (the model defaults).
ASSESSMENT_DEFAULTS = (('officer_verdict', dict), ('ai_verdict_snapshot', list),
                       ('ai_verdict_engine_version', str), ('ai_verdict_context', dict))


def has_recorded_assessment(application):
    """Is a reviewer's (or a super's) own assessment already on the case? `record-verdict` always
    stamps `verdict_decided_at` with it; this door never does. It can be true at Awaiting review
    with no reviewer: a super records at any open stage, and an unassign keeps what was recorded.
    Such an assessment is KEPT: the reject does not write over it, so a cancel has nothing to undo."""
    return application.verdict_decided_at is not None


def take_back_assessment(application):
    """F3 review fix 2: a CANCELLED reject before interview takes its four facts (and the AI snapshot
    beside them) back off the case, so the next reviewer meets an empty assessment ("Complete your
    assessment") instead of facts she never rated. Called by `decline._cancel_pending_decline_locked`
    while it restores the case, BEFORE it clears `rejection_category`. Only this bucket, and only
    when no recorded assessment is on the case (then the facts are the reject's own: see
    `has_recorded_assessment`). No migration: nothing older is kept, because the reject wrote over
    nothing. Returns the fields it changed."""
    if application.rejection_category != CATEGORY or has_recorded_assessment(application):
        return []
    for field, empty in ASSESSMENT_DEFAULTS:
        setattr(application, field, empty())
    return [field for field, _ in ASSESSMENT_DEFAULTS]


def reject_before_interview(application, admin, reason, comments, facts=None, fail_reasons=None):
    """Record the decline now and hold its email for the QC hold. Raises ValueError with
    'bad_status' (not Awaiting review), 'has_reviewer', 'reason_required', 'comments_required',
    'comments_too_long', 'assessment_incomplete' (F3 I-4: all four facts Pass or Fail first) or
    'bad_fail_reasons'. The stage and the reviewer are read again under the row lock, so an
    assignment that committed a moment ago wins. Returns True."""
    from .. import staff_activity
    from ..status_lock import StatusRefused, lock_application_for
    from .decline import _record_reject, _send_decline_for
    if application.status not in PRE_INTERVIEW_FROM:
        raise ValueError('bad_status')
    if application.assigned_to_id is not None:
        raise ValueError('has_reviewer')
    comments = _checked_note(reason, comments)
    assessment = checked_assessment(facts, fail_reasons)
    # Fix 2: a recorded assessment already on the case is kept, never written over.
    assessed = {} if has_recorded_assessment(application) else _assessment_fields(application, assessment)
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
        for field, value in assessed.items():   # F3 (I-4): the four facts, saved with the reject
            setattr(application, field, value)
        fields = ['rejection_reason', *assessed]
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
