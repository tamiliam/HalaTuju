"""
Rejecting a case: the admin route, the org route, and the cool-off before send.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
import logging
from datetime import timedelta

from django.utils import timezone

from ..emails import send_decline_email
from ..models import ScholarshipApplication

#: ⚠ THE PACKAGE NAME, WRITTEN OUT. Never `__name__`: in a submodule that reads
#: `apps.scholarship.services.<module>`, and the one `assertLogs('apps.scholarship.services')`
#: site would still pass (a parent logger records its children) while the name on every line
#: changed underneath it. H11 met exactly this in `views_admin`.
logger = logging.getLogger('apps.scholarship.services')


# Statuses from which an admin may decline a *reviewed* application (bucket 3,
# 'interview'): anyone who cleared the engine and reached the post-shortlist funnel
# but is not yet accepted. Poor documentation is grounds — no formal interview needed.
INTERVIEW_REJECT_FROM = ('shortlisted', 'profile_complete', 'interviewing', 'interviewed')

# Statuses an ORG ADMIN may drop an applicant from (bucket 'incomplete', org_admin_reject).
# Deliberately just 'shortlisted': the student has been offered a place in the funnel but has
# not confirmed a complete profile, so nobody has reviewed them and there is no verdict to
# overturn. Past that point the case belongs to the reviewer/QC track and declines go through
# the recorded-verdict path instead. KEEP IN SYNC with the cockpit, which only renders the
# Reject card at these statuses (lessons.md: offer-set and accept-set are one unit of change).
ORG_REJECT_FROM = ('shortlisted',)

# The terminal off-ramps: the review is over and no further REVIEW write may land on the case.
# The same three statuses QUERYING_LOCKED_STATUSES already closes querying at.
#
# Deliberately NOT 'closed' — that is the successful end of a FUNDED lifecycle, and its writes
# (disbursement, closure) belong to other endpoints with their own gates. This set governs the
# review track only: the interview capture and the four-fact verdict.
CASE_CLOSED_STATES = ('rejected', 'withdrawn', 'expired')


def review_writes_closed(application):
    """True when the interview/verdict endpoints must refuse this application.

    ⚠ **A REOPENED DECISION IS STILL OPEN, whatever the status says.** `reopen.reopen_decision`
    walks most statuses back toward the reviewer, but `rejected` is NOT in its mapping — a super
    who reopens a rejected decision leaves the case AT 'rejected' with `decision_reopened_at`
    set, and is then expected to re-record the verdict. Keying on status alone would refuse the
    one write that reopen exists to permit. `officerCockpit.isCaseClosed` mirrors this exactly,
    so the cockpit cannot offer a control this refuses (lessons.md 2026-07-16: the offer-set and
    the accept-set are one unit of change).

    This is a REVIEW-track gate, not a general write gate: cancelling a pending decline,
    correcting a reporting date or re-running a document read are all still legitimate on a
    closed case and go through their own endpoints.
    """
    return (application.status in CASE_CLOSED_STATES
            and application.decision_reopened_at is None)


def _record_reject(application, category, by_email, now=None, comments=''):
    """Flip the application to rejected NOW (the decision is immediate) — status + bucket +
    when/who (+ the admin's verbatim reason, bucket 'incomplete'). Does NOT send the student
    email (that may be embargoed; see admin_reject).
    Snapshots the pre-decline status AND award_amount so cancel_pending_decline can restore
    them exactly.

    ⚠ A REJECTED APPLICATION HOLDS NO MONEY, and this is the ONE place that is enforced.
    `award_amount` was cleared only by the verdict recorder (views_admin.AdminRecordVerdictView,
    'On DECLINE, clear it'), which is one of THREE ways a case can be declined — so a student
    accepted, reopened, then declined through the `interview` bucket kept their amount. Two
    live records did (apps 21 and 71, RM5,000 between them, cleared 2026-07-30). It never
    misdirected a payment — a rejected student is not in any run — but it silently overstated
    committed funds to anything that sums the column. Clearing it HERE covers all three paths
    (admin_reject, org_admin_reject, the legacy release_pending_declines arm) because they all
    pass through this function; that is the whole reason to fix it here and not at each caller.
    """
    now = now or timezone.now()
    application.pre_decline_status = application.status
    # Snapshot BEFORE clearing, and only when there is something to snapshot, so a second
    # _record_reject on an already-cleared record cannot overwrite a real snapshot with None.
    if application.award_amount is not None:
        application.pre_decline_award_amount = application.award_amount
        application.award_amount = None
    application.status = 'rejected'
    application.rejection_category = category
    application.rejected_at = now
    application.rejected_by = by_email or ''
    application.rejection_comments = comments or ''
    application.save(update_fields=['pre_decline_status', 'pre_decline_award_amount',
                                    'award_amount', 'status', 'rejection_category',
                                    'rejected_at', 'rejected_by', 'rejection_comments'])


def _send_decline_for(application):
    """Send the bucket decline email for an already-rejected application + stamp when it went.
    Reads the recorded ``rejection_category`` so the right (HTML) bucket email is chosen."""
    now = timezone.now()
    name = getattr(application.profile, 'name', '') if application.profile else ''
    # Embargoed declines are released by a cron — attribute the send to the owning org.
    from .. import usage as _usage
    with _usage.usage_context(application=application):
        sent_decline = send_decline_email(
            to_email=(application.notify_email
                      or getattr(application.profile, 'contact_email', '') or ''),
            applicant_name=name, programme_name=application.cohort.name,
            category=application.rejection_category, lang=application.locale,
        )
    if sent_decline:
        # Both stamps: decline_email_sent_at is the authoritative "the student was told of
        # the DECLINE" marker (cancel_pending_decline keys off it); decision_email_sent_at
        # keeps its broader "a decision email went out" meaning for back-compat.
        application.decline_email_sent_at = now
        application.decision_email_sent_at = now
        application.save(update_fields=['decline_email_sent_at', 'decision_email_sent_at'])


def _finalise_reject(application, category, by_email):
    """Immediate decline (cool-off disabled): record the rejection AND send the email now."""
    _record_reject(application, category, by_email)
    _send_decline_for(application)


def admin_reject(application, admin, category, cooloff=None):
    """Post-shortlist admin rejection (buckets 'interview' & 'contractual').

    ``cooloff`` (a ``timedelta``) overrides the day-based ``DECLINE_COOLOFF_DAYS`` embargo — used
    by the QC-confirmed decline, whose window is 24h (the decision already passed two-person QC).

    The DECISION is immediate — the application flips to ``rejected`` at once, so the cockpit and
    records reflect it straight away. With a cool-off (DECLINE_COOLOFF_DAYS > 0, default 7) only
    the STUDENT EMAIL is EMBARGOED for the window: it is scheduled (``decline_due_at``) and sent
    by ``release_pending_declines`` when the window passes — softening the news. Until then the
    student does not see the rejection (``ApplicationReadSerializer`` masks an email-embargoed
    rejection as 'interviewed'), and ``cancel_pending_decline`` can undo it before the student is
    ever told. With the cool-off disabled (0) the email goes immediately.
      - 'interview'   (reviewed but not selected) — from a post-shortlist, not-yet-accepted status.
      - 'contractual' (failed post-award steps) — from 'recommended'/'sponsored'.
    Raises ValueError on a bad category/status combination. Returns True."""
    if category == 'interview':
        if application.status not in INTERVIEW_REJECT_FROM:
            raise ValueError('bad_status')
    elif category == 'contractual':
        # 'contractual' is a genuinely post-award decline — from the funded states (active/
        # maintenance). 'recommended' stays permitted for back-compat, but the normal way to
        # decline a recommended case is now reopen → 'interviewed' → 'interview'.
        #
        # ⚠ 'awarded' IS DELIBERATELY ABSENT — owner ruling, 2026-07-30: "They cannot be rejected
        # directly. It should only happen after a proper withdrawal of the award." The asymmetry
        # with active/maintenance is the point: those mean the student ACCEPTED, so a decline
        # there is a real contractual failure. 'awarded' means the offer is merely OPEN, so the
        # correct action is withdrawing the offer (sponsorship.cancel_offer / the student
        # declining / the offer expiring), which returns them to 'recommended' — and a decline
        # from there is already permitted above.
        #
        # Do NOT "fix" this by adding 'awarded'. It sits two conditions away from a genuine
        # omission of 'awarded' that WAS a bug (the cockpit sign-off, fixed the same day), so it
        # looks like the same mistake and is not. `test_reject_status_sets.py` pins it.
        if application.status not in ('recommended', 'active', 'maintenance'):
            raise ValueError('bad_status')
    else:
        raise ValueError('bad_category')

    from django.conf import settings as _settings
    # Email-embargo window. An explicit `cooloff` timedelta (the QC-confirmed decline's 24h) wins;
    # otherwise fall back to the day-based DECLINE_COOLOFF_DAYS. total_seconds()<=0 → email now.
    if cooloff is not None:
        window = cooloff
    else:
        days = getattr(_settings, 'DECLINE_COOLOFF_DAYS', 7)
        window = timedelta(days=days) if (days and days > 0) else timedelta(0)
    by = getattr(admin, 'email', '') or ''
    _record_reject(application, category, by)        # the decision is immediate, either way
    if category == 'contractual':
        # Code-health S3 #6 (owner decision 2026-07-03): rejecting a funded/offered student
        # AUTO-LAPSES their sponsorship(s) — the held amount returns to the sponsor's
        # balance and impact/statement surfaces stop reporting the student as supported.
        # (Without this the sponsorship sat HOLDING forever.) The disbursement ledger needs
        # no touch: release_tranche already refuses any non-funded status (S6). Lazy import
        # — the module dependency runs sponsorship → services.
        from ..sponsorship import lapse_holding_sponsorships
        lapse_holding_sponsorships(application)
    if window.total_seconds() > 0:
        # Embargo only the student email: schedule it; the student sees nothing until it goes.
        application.pending_rejection_category = category
        application.decline_due_at = timezone.now() + window
        application.pending_decline_by = by
        application.save(update_fields=['pending_rejection_category', 'decline_due_at',
                                        'pending_decline_by'])
    else:
        _send_decline_for(application)
    return True


def org_admin_reject(application, admin, comments):
    """Org-admin drop of a STUCK SHORTLISTED applicant (bucket 'incomplete') — owner 2026-07-21.

    Deliberately NOT a variant of the reviewer/QC decline:
      - IMMEDIATE and IRREVERSIBLE. No cool-off, no embargo, no cancel window: the owner's
        reason for the button is to STOP a stuck applicant adding documents or advancing their
        own status, and the decline email goes in the same breath. `_record_reject` freezes the
        case the instant it runs — every student write path (document upload, details PATCH,
        income-route switch, confirm-profile) and the completion-reminder cron all gate on a
        status this is no longer in, so the lockout needs no separate enforcement.
      - The reason is REQUIRED and recorded verbatim on the application (there is no verdict at
        'shortlisted', hence no DecisionReopen trail to hang it on — decisions.md 2026-07-19).
        It is INTERNAL: the student gets the generic warm decline (emails.FAIL_*), never this text.

    Callers must have already gated the ROLE (super/org_admin — views_admin.AdminOrgRejectView).
    Raises ValueError('bad_status') outside ORG_REJECT_FROM, ValueError('comments_required')
    on a blank reason. Returns True."""
    if application.status not in ORG_REJECT_FROM:
        raise ValueError('bad_status')
    comments = (comments or '').strip()
    if not comments:
        raise ValueError('comments_required')
    _record_reject(application, 'incomplete', getattr(admin, 'email', '') or '', comments=comments)
    _send_decline_for(application)
    logger.info('AUDIT org_admin_reject app_id=%s by=%s', application.id,
                getattr(admin, 'email', '') or '?')
    return True


def cancel_pending_decline(application):
    """Undo a rejection whose student email is still EMBARGOED (the student was never told):
    clear the scheduled email AND reverse the rejection back to the status it was declined
    FROM (snapshotted in ``pre_decline_status``; legacy rows without one fall back to
    'interviewed'). No-op (False) once the decline email has gone or nothing is pending.
    Returns True if cancelled.

    Two past bugs guarded here: (a) the "was the student told?" check must read
    ``decline_email_sent_at`` — NOT ``decision_email_sent_at``, which the shortlist PASS
    email already stamped for every normally-processed applicant (the restore branch never
    ran, so a "cancelled" decline stayed rejected and student-visible); (b) the restore
    target must be the snapshot — a hardcoded 'interviewed' now means AWAITING QC, so a
    decline made pre-verdict would land in the QC queue with no recorded verdict."""
    if not (application.decline_due_at or application.pending_rejection_category):
        return False
    application.pending_rejection_category = ''
    application.decline_due_at = None
    application.pending_decline_by = ''
    fields = ['pending_rejection_category', 'decline_due_at', 'pending_decline_by']
    if application.status == 'rejected' and application.decline_email_sent_at is None:
        restore_to = application.pre_decline_status or 'interviewed'
        # A cancelled CONTRACTUAL decline of a funded student: the reject auto-lapsed the
        # sponsorship (#6), so try to reinstate it — best-effort, only when the sponsor's
        # balance still covers the amount (they may have reallocated it in the window).
        # If it can't be reinstated the case still returns to its pre-decline status but
        # needs re-funding — logged for the officer.
        if application.rejection_category == 'contractual' and restore_to in ('active', 'maintenance'):
            from ..sponsorship import reinstate_lapsed_sponsorship
            since = application.rejected_at or timezone.now()
            if reinstate_lapsed_sponsorship(application, since=since) is None:
                logger.warning(
                    'cancel_pending_decline: app %s restored to %r but its lapsed sponsorship '
                    'could not be reinstated (balance reallocated?) — needs re-funding.',
                    application.id, restore_to)
        application.status = restore_to
        application.pre_decline_status = ''
        # Give the money back. The reject cleared award_amount; restoring the status without it
        # would hand back a funded student who is silently unpayable (payments.amount_due caps
        # at award − paid). Only ever restores FROM the snapshot, so it cannot invent an amount
        # for a case that never had one.
        if application.pre_decline_award_amount is not None:
            application.award_amount = application.pre_decline_award_amount
            application.pre_decline_award_amount = None
        application.rejection_category = ''
        application.rejected_at = None
        application.rejected_by = ''
        application.rejection_comments = ''
        fields += ['status', 'pre_decline_status', 'award_amount', 'pre_decline_award_amount',
                   'rejection_category', 'rejected_at', 'rejected_by', 'rejection_comments']
    application.save(update_fields=fields)
    return True


def release_pending_declines(now=None):
    """Send every embargoed decline email whose window has passed, then clear the email markers.
    The application is ALREADY 'rejected' (recorded at decline time) — this only lifts the email
    embargo. Intended for the scheduler. Returns the count of emails released."""
    now = now or timezone.now()
    qs = (ScholarshipApplication.objects
          .filter(decline_due_at__isnull=False, decline_due_at__lte=now)
          .exclude(pending_rejection_category='')
          .select_related('cohort', 'profile'))
    released = 0
    for app in qs:
        category, by = app.pending_rejection_category, app.pending_decline_by
        # Clear the email markers first so a re-run can never double-send.
        app.pending_rejection_category = ''
        app.decline_due_at = None
        app.pending_decline_by = ''
        app.save(update_fields=['pending_rejection_category', 'decline_due_at', 'pending_decline_by'])
        # Defensive: a legacy pending row whose status wasn't flipped at decline time.
        if app.status != 'rejected':
            _record_reject(app, category, by)
        _send_decline_for(app)
        released += 1
    return released
