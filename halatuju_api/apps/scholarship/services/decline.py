"""
Rejecting a case: the admin route, the org route, and the cool-off before send.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
import logging
from datetime import timedelta

from django.db import transaction
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
# All four are statuses QUERYING_LOCKED_STATUSES already closes querying at.
#
# 'closed' JOINED 2026-10-06 (TD-352). It used to be reachable only from a FUNDED state, whose
# review had long ended; since TD-352 an officer may close a STALLED case from any in-play status
# (`closure.close_application`), so a case closed at `interviewing` would otherwise still take a
# verdict, an award amount and an interview onto a closed file. A funded closed case loses nothing:
# its writes (disbursement, closure, the thank-you relay) go through other endpoints with their own
# gates, never `_require_open_case`. This set governs the review track only: the interview
# capture, the gap suggestion and the four-fact verdict.
CASE_CLOSED_STATES = ('closed', 'rejected', 'withdrawn', 'expired')


def review_writes_closed(application):
    """True when the interview/verdict endpoints must refuse this application.

    ⚠ **A REOPENED DECISION IS STILL OPEN, whatever the status says.** `reopen.reopen_decision`
    walks most statuses back toward the reviewer, but `rejected` is NOT in its mapping — a super
    who reopens a rejected decision whose email has gone leaves the case AT 'rejected' with
    `decision_reopened_at` set, and is then expected to re-record the verdict. (One whose email
    is still embargoed cannot be reopened at all — `decline_pending`, TD-349; cancel it instead.)
    Keying on status alone would refuse the one write that reopen exists to permit.
    `officerCockpit.isCaseClosed` mirrors this exactly,
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
    committed funds to anything that sums the column. Clearing it HERE covers every path
    (admin_reject, org_admin_reject; the legacy release_pending_declines arm went with TD-349)
    because they all pass through this function; that is the whole reason to fix it here and
    not at each caller.
    """
    now = now or timezone.now()
    application.pre_decline_status = application.status
    # Snapshot BEFORE clearing, and only when there is something to snapshot, so a second
    # _record_reject on an already-cleared record cannot overwrite a real snapshot with None.
    award_was = application.award_amount   # TD-203: logged once the save has landed
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
    if award_was is not None:
        logger.info('AUDIT award_amount_set app_id=%s by=%s was=%s now=%s via=reject',
                    application.id, (by_email or '?'), award_was, '-')


def _told_of_this_decline(application):
    """Has the student been emailed about THIS decline? The one rule for both exits from the
    embargo — `cancel_pending_decline` (told → it may not reverse) and the release cron (told →
    it may not send again). TD-349 review finding 3: they used to disagree.

    Told = `decline_email_sent_at` set AND at or after `rejected_at`: a stamp from an EARLIER
    decline (declined, reopened, re-decided, declined again) is not this decline's email.
    ⚠ A row with no `rejected_at` cannot be compared; any stamp then counts as told — the rule
    before TD-349, kept for legacy rows only (`_record_reject` stamps `rejected_at` on every
    decline that can carry the embargo, so no embargoed row lacks it)."""
    sent = application.decline_email_sent_at
    if sent is None:
        return False
    return application.rejected_at is None or sent >= application.rejected_at


def _decline_address(application):
    """Where the decline email goes: the application's notify address, else the profile's."""
    return (application.notify_email
            or getattr(application.profile, 'contact_email', '') or '')


def _send_decline_for(application):
    """Send the bucket decline email for an already-rejected application + stamp when it went.
    Reads the recorded ``rejection_category`` so the right (HTML) bucket email is chosen.

    Returns True only when the email went (and was stamped). ⚠ A MAIL FAILURE DOES NOT RAISE:
    the sender logs it and answers False, so a caller that must not unmask before the email has
    gone reads this return value — an exception alone would miss Brevo being down (TD-349)."""
    now = timezone.now()
    name = getattr(application.profile, 'name', '') if application.profile else ''
    # Embargoed declines are released by a cron — attribute the send to the owning org.
    from .. import usage as _usage
    with _usage.usage_context(application=application):
        sent_decline = send_decline_email(
            to_email=_decline_address(application),
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
    return bool(sent_decline)


def _finalise_reject(application, category, by_email):
    """Immediate decline (cool-off disabled): record the rejection AND send the email now."""
    _record_reject(application, category, by_email)
    _send_decline_for(application)


def admin_reject(application, admin, category, cooloff=None):
    """Post-shortlist admin rejection (buckets 'interview' & 'contractual').

    ``cooloff`` (a ``timedelta``) overrides the organisation's day-based ``decline_hold_days``
    embargo — used by the QC-confirmed decline, whose window is the organisation's
    ``qc_decline_hold_hours`` (the decision already passed two-person QC).

    The DECISION is immediate — the application flips to ``rejected`` at once, so the cockpit and
    records reflect it straight away. With a cool-off (``decline_hold_days``, platform 7) only
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

    # Email-embargo window. An explicit `cooloff` timedelta (the QC-confirmed decline's hold) wins;
    # otherwise the ORGANISATION's `decline_hold_days` (org-timing Sprint 1; platform default
    # DECLINE_COOLOFF_DAYS). total_seconds()<=0 → email now (reachable only through a platform
    # env value of 0 — an organisation's own value has a floor of 3).
    if cooloff is not None:
        window = cooloff
    else:
        from apps.courses import org_config
        days = org_config.value(application.owning_organisation, 'decline_hold_days')
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


def cancel_pending_decline(application, by_email=''):
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
    decline made pre-verdict would land in the QC queue with no recorded verdict.

    (d) TD-349: the release cron may have sent and stamped this decline since the caller
    loaded the row, so the facts the decision rests on are RE-READ under a row lock first (on
    PostgreSQL the lock also waits out a release in flight; SQLite ignores it)."""
    with transaction.atomic():
        _reread_embargo_facts(application)
        return _cancel_pending_decline_locked(application, by_email)


#: What `cancel_pending_decline` decides on, re-read from the database (TD-349).
_EMBARGO_FACTS = ('status', 'pending_rejection_category', 'decline_due_at',
                  'decline_email_sent_at', 'rejected_at')


def _reread_embargo_facts(application):
    fresh = (ScholarshipApplication.objects.select_for_update()
             .filter(pk=application.pk).values(*_EMBARGO_FACTS).first())
    for field, value in (fresh or {}).items():
        setattr(application, field, value)


def held_decline_restore_target(application):
    """The status `cancel_pending_decline` would put this application back to, or None when it
    would restore nothing (no held decline, not rejected, or the student already told).

    ⚠ THE CANCEL'S OWN RULE, read by the cancel itself and by the IC-lock release
    (`views_admin/sponsors.py`, TD-371): while a held decline would restore `recommended` on an
    intake with a "Born in" rule, the lock may not be released, so the IC cannot change during
    the hold and the cancel needs no check of its own."""
    if not (application.decline_due_at or application.pending_rejection_category):
        return None
    # (c) "told" is THIS decline's email, by the one rule the release cron also reads (TD-349).
    if application.status != 'rejected' or _told_of_this_decline(application):
        return None
    return application.pre_decline_status or 'interviewed'


def _cancel_pending_decline_locked(application, by_email):
    if not (application.decline_due_at or application.pending_rejection_category):
        return False
    restore_to = held_decline_restore_target(application)   # read before the markers clear
    award_was = application.award_amount   # TD-203; `by_email` is the acting admin, for the log
    application.pending_rejection_category = ''
    application.decline_due_at = None
    application.pending_decline_by = ''
    fields = ['pending_rejection_category', 'decline_due_at', 'pending_decline_by']
    if restore_to is not None:
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
    if application.award_amount != award_was:
        logger.info('AUDIT award_amount_set app_id=%s by=%s was=%s now=%s via=cancel',
                    application.id, (by_email or '?'),
                    ('-' if award_was is None else award_was),
                    ('-' if application.award_amount is None else application.award_amount))
    return True


def _claim_due_decline(pk, now):
    """Lock and RE-READ one due decline right before its send (TD-349 review findings 2, 4),
    or None to skip it — silently, not counted, not an error.

    The cron read its list a moment ago; since then a cancel may have reversed the decline (the
    markers are gone) or re-declined it with a new window, and another run of this cron may be
    sending it. `skip_locked` leaves a row another run (or a cancel) holds to that holder.
    ⚠ SQLite — the test database — ignores `select_for_update`, so locally only the re-check is
    exercised; the lock itself is PostgreSQL's. Call inside `transaction.atomic()`."""
    app = (ScholarshipApplication.objects.select_for_update(skip_locked=True)
           .filter(pk=pk).first())
    if (app is None or not app.pending_rejection_category or app.decline_due_at is None
            or app.decline_due_at > now):
        return None
    if app.status != 'rejected':
        # The old "legacy row" arm recorded the decline here; every embargo since 2026-06-27 is
        # recorded first, and the only writer that left markers on a live case (the reopen) now
        # refuses. Never guess a decline at send time: say so and leave it for an officer.
        logger.warning('release_pending_declines: app %s carries a pending decline but is %r, '
                       'not rejected — skipped; cancel the pending decline.', app.pk, app.status)
        return None
    return app


def _release_one_decline(app):
    """Send one embargoed decline, THEN lift the embargo. True once released; False (markers
    left, so the decline stays masked and the next run retries) when the email did not go.

    ⚠ THE ORDER IS THE FIX (TD-349). The markers are what mask the decline from the student
    (`student_status.student_facing_status`) and what select it for this cron, so clearing them
    before the send turned a failed send into a decline she could see, with no email and no
    retry. Send first; clear only after the email has gone.
    Two edges, decided: an email already sent for THIS decline (`_told_of_this_decline`) is not
    sent again; a decline with no address at all is released without an email (nothing to retry;
    kept masked she would see her old stage for ever) and logged for an officer."""
    if not _told_of_this_decline(app):
        if not _decline_address(app):
            logger.warning('release_pending_declines: app %s has no email address — decline '
                           'released WITHOUT an email; tell the student another way.', app.id)
        elif not _send_decline_for(app):
            logger.error('release_pending_declines: app %s — the decline email did not go; the '
                         'decline stays masked and the next run retries.', app.id)
            return False
    app.pending_rejection_category = ''
    app.decline_due_at = None
    app.pending_decline_by = ''
    app.save(update_fields=['pending_rejection_category', 'decline_due_at', 'pending_decline_by'])
    return True


def release_pending_declines(now=None):
    """Send every embargoed decline email whose window has passed, then clear the email markers.
    The application is ALREADY 'rejected' (recorded at decline time) — this only lifts the email
    embargo. Intended for the scheduler. Returns the count released (a failed send is not
    counted: it is logged at ERROR and retried on the next run, and never stops the batch)."""
    now = now or timezone.now()
    due = list(ScholarshipApplication.objects
               .filter(decline_due_at__isnull=False, decline_due_at__lte=now)
               .exclude(pending_rejection_category='')
               .values_list('pk', flat=True))
    released = 0
    for pk in due:
        try:
            with transaction.atomic():      # one application, claimed, sent, cleared
                app = _claim_due_decline(pk, now)
                if app is not None and _release_one_decline(app):
                    released += 1
        except Exception:
            logger.error('release_pending_declines: app %s — the release raised; the decline '
                         'stays masked and the next run retries.', pk, exc_info=True)
    return released
