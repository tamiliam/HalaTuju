"""Interview scheduling service (in-app booking + Google Meet).

Model (owner's design): the assigned reviewer PROPOSES a few times
(``InterviewSlot`` rows); the student BOOKS one, which sets the booking state on
``ScholarshipApplication`` and creates a Google Meet event (best-effort). The
student can self-reschedule (book a different proposed slot) or cancel, up to a
cutoff (``settings.INTERVIEW_RESCHEDULE_CUTOFF_HOURS`` before the start).

All Google Meet calls go through ``meeting.py`` and are best-effort, so a booking
never fails because of Google. Every email is best-effort too. The whole surface
is dark behind ``settings.INTERVIEW_SCHEDULING_ENABLED`` (enforced at the views).
"""
from __future__ import annotations

import functools
import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from . import emails, meeting, pool, services, usage, whatsapp
from .models import InterviewSlot

logger = logging.getLogger(__name__)


def _bills_to_application(fn):
    """Attribute every metered call inside ``fn`` to the application's owning organisation.

    Each public entry point below takes the application FIRST, so one decorator covers the
    email + WhatsApp the call fans out — including the ones sent to the REVIEWER, which are
    still work done on that tenant's behalf and belong on that tenant's bill.

    Without this the meter falls back to whatever ambient context happens to be set (a cron
    or a shell has none) and silently records org-NULL, which under-charges the tenant.
    ``usage_context`` never raises, so this cannot break a booking.
    """
    @functools.wraps(fn)
    def wrapper(application, *args, **kwargs):
        with usage.usage_context(application=application):
            return fn(application, *args, **kwargs)
    return wrapper

# Interview slot rule: a proposed time must be MYT, on the organisation's step boundary,
# inside its booking window. Times are stored UTC; we compare in MYT.
#
# ⚠ THESE FOUR CONSTANTS ARE THE PLATFORM DEFAULT, NOT THE RULE (Org Config Sprint D). The
# rule is `org_config.value(organisation, 'interview_window_start_min')` and friends, which
# DELEGATE here for an organisation that has tuned nothing. The browser no longer keeps a
# lock-step copy: `interview_schedule_payload` SERVES the resolved four to the picker, so
# there is nothing left to keep in step.
_MYT = ZoneInfo('Asia/Kuala_Lumpur')
SLOT_WINDOW_START_MIN = 8 * 60        # 08:00
SLOT_WINDOW_END_MIN = 21 * 60 + 30    # 21:30 (latest start)
SLOT_STEP_MIN = 30
# Minimum scheduling notice: the earliest proposable slot is this far ahead, so the student
# has time to see + pick + prepare.
SLOT_MIN_LEAD_HOURS = 24


def slot_rules(organisation=None):
    """The four booking-grid values for one organisation, resolved once.

    Returned as a dict so a caller that needs several of them (the propose endpoint, the
    payload) pays for one registry read per value and no more.
    """
    from apps.courses import org_config
    return {
        'window_start_min': org_config.value(organisation, 'interview_window_start_min'),
        'window_end_min': org_config.value(organisation, 'interview_window_end_min'),
        'step_min': org_config.value(organisation, 'interview_slot_step_min'),
        'min_lead_hours': org_config.value(organisation, 'interview_min_lead_hours'),
    }


def meets_min_lead(dt, now, organisation=None) -> bool:
    """True if a proposed start is at least the organisation's minimum notice ahead of ``now``."""
    from apps.courses import org_config
    hours = org_config.value(organisation, 'interview_min_lead_hours')
    return dt >= now + timedelta(hours=hours)


def slot_in_window(dt, organisation=None) -> bool:
    """True if a tz-aware datetime falls on an allowed interview slot for this organisation
    (MYT, on its step boundary, inside its window). Enforced at the propose endpoint."""
    rules = slot_rules(organisation)
    step = rules['step_min']
    local = dt.astimezone(_MYT)
    if local.second or local.microsecond or local.minute % step:
        return False
    mins = local.hour * 60 + local.minute
    return rules['window_start_min'] <= mins <= rules['window_end_min']


class SchedulingError(Exception):
    """Raised with a stable string code the views map to a 400 response."""


def scheduling_enabled() -> bool:
    return bool(getattr(settings, 'INTERVIEW_SCHEDULING_ENABLED', False))


def _can_review(admin):
    """Mirror services._can_review: an active review target (reviewer/admin/qc/super) may propose
    slots. Uses the SHARED services.REVIEW_ROLES so this can't drift from the assignment/write gate
    again — the per-application assignment check below is what actually scopes WHO can propose.

    ⚠ **ONE DELIBERATE DIFFERENCE: this does NOT refuse a PAUSED reviewer** (request #10,
    2026-08-02). Pause stops NEW assignment; it does not confiscate the cases somebody is already
    holding, and proposing interview times is how they finish one. Adding the paused check here
    would strand every in-flight interview the moment a volunteer stepped back — the opposite of
    what pause is for. `test_reviewer_pause.py` asserts this stays permissive."""
    if admin is None or not getattr(admin, 'is_active', False):
        return False
    return bool(getattr(admin, 'is_super_admin', False)) or getattr(admin, 'role', '') in services.REVIEW_ROLES


def _student_identity(application):
    """Return (email, name) for the applicant, mirroring assign_reviewer."""
    profile = application.profile
    email = (application.notify_email or getattr(profile, 'contact_email', '') or '')
    name = getattr(profile, 'name', '') if profile else ''
    return email, name


def _reviewer_phone(reviewer):
    """The reviewer's phone iff they share it (opt-out aware), else ''."""
    try:
        rp = reviewer.reviewer_profile
    except Exception:
        rp = None
    return rp.phone if (rp and rp.share_phone_with_students) else ''


def _cutoff_ok(start, now, organisation=None):
    """True if we're still outside the reschedule/cancel cutoff window.

    ⚠ The SAME value is printed to the student in the booked-interview email ("you can change
    or cancel up to N hours before"). Resolve it per organisation at both, or the promise and
    the refusal disagree — see `emails.send_interview_booked_email`.
    """
    from apps.courses import org_config
    hours = org_config.value(organisation, 'interview_reschedule_cutoff_hours')
    return now < (start - timedelta(hours=hours))


def held_intervals(reviewer, *, exclude_application=None, booked_only=False):
    """The BLOCKS of time this reviewer genuinely holds — the single source of truth for
    conflict-blocking (propose grid, propose guard, book guard, student re-pick menu).

    Returns ``[(start, end), ...]``, where ``end`` is the slot's OWN stored ``duration_min``
    past its start. That column is written at propose time from the organisation's
    `interview_duration_min` and is the value every booking path puts on the calendar
    invite and the .ics — so it is what the reviewer is really committed to.

    ⚠ **This answers "is this time free?" for all five call sites; do not write a second
    one.** It replaced `held_starts`, which returned bare start times and so compared only
    starts (TD-233): with an interview LONGER than the step — length 45 on a 30-minute grid,
    which the owner ruled the correct configuration on 2026-09-08, because a 60 step cannot
    reach 11:30 and a 45 step drifts — a hold at 10:00 runs to 10:45 and 10:30 has a
    different start, so both were offered and the reviewer was double-booked for 15 minutes.
    The step is a GRID TO PLACE A BLOCK ON, not a cadence to fill, so refusing
    `duration > step` at the registry was rejected: it forbids the configuration people want.

    Hold semantics (owner's design, 2026-07-02) are UNCHANGED — only the comparison moved:
      - an UNBOOKED application's active proposals all hold the reviewer's time (the
        student may pick any of them);
      - once an application is BOOKED, only its booked slot holds — the unpicked
        siblings are RELEASED (they stay active as the student's re-pick menu, but no
        longer block the reviewer offering those times to someone else; first to book
        wins, and a released time re-offered elsewhere disappears from the original
        student's re-pick menu).

    ``booked_only`` keeps the deliberately WEAKER rule on a first booking: only a confirmed
    booking elsewhere blocks, never a mere proposal to another student (first to book wins).
    """
    if reviewer is None:
        return []
    from django.db.models import F, Q
    qs = InterviewSlot.objects.filter(reviewer=reviewer, is_active=True)
    if exclude_application is not None:
        qs = qs.exclude(application=exclude_application)
    if booked_only:
        # Confirmed bookings only — the slot that IS its application's booked slot.
        qs = qs.filter(application__interview_status='booked',
                       application__interview_slot_id=F('id'))
    else:
        # Drop the released siblings: slots of a BOOKED application that are not its
        # booked slot. Everything else (unbooked proposals + booked slots) holds.
        qs = qs.exclude(Q(application__interview_status='booked')
                        & ~Q(application__interview_slot_id=F('id')))
    # A non-positive duration would make a block that contains nothing and could never
    # clash; floor it at a minute so such a row still holds its own start, as before.
    return [(s, s + timedelta(minutes=max(int(d or 0), 1)))
            for s, d in qs.values_list('start', 'duration_min')]


def overlaps(start, duration_min, intervals) -> bool:
    """True if an interview of ``duration_min`` beginning at ``start`` would run into any
    of ``intervals`` (from `held_intervals`). Half-open: a block ending at 10:45 does not
    clash with one starting at 10:45."""
    end = start + timedelta(minutes=max(int(duration_min or 0), 1))
    return any(start < h_end and end > h_start for h_start, h_end in intervals)


def blocked_starts(intervals, *, duration_min, step_min):
    """The grid starts at which a NEW interview of ``duration_min`` would overlap a held
    block — i.e. exactly the times the reviewer's picker must grey out.

    This is the SERVE-DON'T-MIRROR half of the fix (the standing Org Config Sprint D rule):
    the browser keeps doing `reviewerBusy.has(slotValue)` and knows nothing about lengths,
    because the server hands it the already-expanded set. With length 45, step 30 and a hold
    at 10:00–10:45 that set is {09:30, 10:00, 10:30} — 09:30 + 45 minutes lands inside the
    hold — where the old start-only answer greyed 10:00 alone.

    Derived from the blocks themselves, so it needs no knowledge of which days the picker is
    showing, and is bounded at (duration + block length) / step starts per block. Starts are
    on the grid already (`slot_in_window` enforces it at propose), so stepping from each
    block's own start stays on it.
    """
    step = max(int(step_min or 0), 1)
    dur = max(int(duration_min or 0), 1)
    blocked = set()
    for h_start, h_end in intervals:
        # Earlier grid starts whose interview would still be running when the block opens.
        k = 1
        while k * step < dur:
            blocked.add(h_start - timedelta(minutes=k * step))
            k += 1
        # The block's own start, and every grid start before it closes.
        cur = h_start
        while cur < h_end:
            blocked.add(cur)
            cur += timedelta(minutes=step)
    return blocked


# ── Reviewer side: propose / withdraw ─────────────────────────────────────────

def _send_wa_proposed(application, student_name, reviewer=None):
    """Best-effort WhatsApp 'your interview times are ready — pick one' nudge (roadmap S2, TD-138).

    Opt-in gated. Uses the approved template (``TWILIO_WHATSAPP_PROPOSED_CONTENT_SID``) in prod;
    free text in the Twilio sandbox. **Dark in prod until that template SID is set** — a real sender
    can't free-text a business-initiated message, so with no template + not-sandbox we send nothing.
    Best-effort: ``send_whatsapp`` never raises into the caller."""
    profile = getattr(application, 'profile', None)
    if not getattr(profile, 'whatsapp_opt_in', True):
        return
    # Variant by language preference — EN-only or EN+BM (both reuse {1}name {2}reviewer {3}link);
    # fall back to the legacy single SID. Same english_only standard as the emails/reminder.
    en_only = emails.english_only_email(application)
    _en = getattr(settings, 'TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_EN', '')
    _bm = getattr(settings, 'TWILIO_WHATSAPP_PROPOSED_CONTENT_SID_BM', '')
    content_sid = (_en if en_only else (_bm or _en)) or getattr(settings, 'TWILIO_WHATSAPP_PROPOSED_CONTENT_SID', '')
    if not content_sid and not whatsapp.is_sandbox_sender():
        return  # no approved template yet + not sandbox → don't attempt a forbidden free-text send
    phone = getattr(profile, 'contact_phone', '')
    student_name = (student_name or '').strip().split(' ')[0] or 'there'   # first name, like the assignment email
    reviewer_name = (getattr(reviewer, 'name', '') or '').strip() or 'your interviewer'
    frontend = getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz').rstrip('/')
    link = f'{frontend}/scholarship/application'
    if content_sid:
        whatsapp.send_whatsapp(
            phone, application=application, kind='interview_proposed', content_sid=content_sid,
            content_variables={'1': student_name, '2': reviewer_name, '3': link})
        return
    # Sandbox free-text (bilingual unless the student is English-only). Names the interviewer +
    # the 3 proposed times; mirrors the assignment email's "pick one → Meet link + reminder" voice.
    en = (f'Hi {student_name} — your assigned interviewer, {reviewer_name}, has proposed three times '
          f'for your B40 Assistance interview. Please pick the one that suits you: {link}. Once you '
          f'choose, we’ll send the Google Meet link and, if necessary, reminders.')
    if en_only:
        body = en
    else:
        bm = (f'Salam {student_name} — penemu duga anda, {reviewer_name}, telah mencadangkan tiga masa '
              f'untuk temu duga Bantuan B40 anda. Sila pilih yang sesuai untuk anda: {link}. Setelah '
              f'anda memilih, kami akan menghantar pautan Google Meet dan, jika perlu, peringatan.')
        body = f'{en}\n\n{bm}'
    whatsapp.send_whatsapp(phone, body, application=application, kind='interview_proposed')


@_bills_to_application
def propose_slots(application, *, reviewer, starts, duration_min=None, now=None,
                  release_booking=False):
    """The assigned reviewer (or a super) proposes interview times.

    ``starts`` is a list of tz-aware datetimes. Existing *unbooked* active slots are
    withdrawn (a fresh proposal replaces the old menu); the booked slot, if any, is
    untouched. Returns the list of created InterviewSlot rows.

    ``release_booking=True`` is the reviewer-RESCHEDULE path: when the interview is already
    booked, the reviewer is MOVING it — so we release the held booking (drop the slot + the
    Meet/calendar event, clear the booking fields) before offering the fresh menu, and the
    student's "pick a time" email carries a moved-the-time preface. There is deliberately no
    reviewer self-cancel; an emergency reschedules (keeps the candidate) and a true hand-off
    goes through admin reassignment.
    """
    now = now or timezone.now()
    if duration_min is None:
        from apps.courses import org_config
        duration_min = org_config.value(application.owning_organisation, 'interview_duration_min')

    if not _can_review(reviewer):
        raise SchedulingError('not_reviewer')
    # Slots ARE the assigned reviewer's calendar — proposing on an UNASSIGNED application is
    # incoherent, and (being the forward trigger to 'interviewing') would flip a case into the
    # interview funnel with no accountable owner. Refuse regardless of role — this closes the
    # super-admin bypass (a plain reviewer is already assignment-scoped below + by _require_app_write).
    if application.assigned_to_id is None:
        raise SchedulingError('not_assigned')
    is_super = bool(getattr(reviewer, 'is_super_admin', False)) or getattr(reviewer, 'role', '') == 'super'
    if not is_super and application.assigned_to_id != getattr(reviewer, 'id', None):
        raise SchedulingError('not_assigned')

    future = [s for s in starts if s and s > now]
    if not future:
        raise SchedulingError('no_future_slots')

    # Reviewer-wide conflict: never offer a time that would RUN INTO something this reviewer
    # already holds for ANOTHER applicant — keeps one reviewer from being double-booked. A
    # booked application's released siblings no longer hold (see held_intervals), so those
    # times are re-offerable. The UI greys held times out; this is the server guard / race
    # backstop. Compares blocks, not starts, so a 45-minute interview on a 30-minute grid
    # cannot be proposed half an hour after another one (TD-233).
    held = held_intervals(reviewer, exclude_application=application)
    if any(overlaps(s, duration_min, held) for s in future):
        raise SchedulingError('reviewer_conflict')

    # Reviewer reschedule: release the held booking (slot + Meet event + fields) so the new
    # menu fully replaces it and the student must re-pick.
    rescheduling = bool(release_booking and application.interview_status == 'booked')
    if rescheduling:
        if application.interview_calendar_event_id:
            meeting.cancel_event(application.interview_calendar_event_id)
        if application.interview_slot_id:
            (InterviewSlot.objects
                .filter(id=application.interview_slot_id)
                .update(is_active=False, updated_at=now))
        application.interview_status = ''
        application.interview_slot = None
        application.interview_start = None
        application.interview_meeting_url = ''
        application.interview_calendar_event_id = ''
        application.interview_meeting_provider = ''
        application.interview_reminded_1d_at = None
        application.interview_reminded_1h_at = None
        application.save(update_fields=[
            'interview_status', 'interview_slot', 'interview_start', 'interview_meeting_url',
            'interview_calendar_event_id', 'interview_meeting_provider',
            'interview_reminded_1d_at', 'interview_reminded_1h_at',
        ])

    booked_id = application.interview_slot_id if application.interview_status == 'booked' else None
    # The menu the student was last shown — to decide whether to re-notify.
    prev_menu = set(
        InterviewSlot.objects
        .filter(application=application, is_active=True)
        .exclude(id=booked_id)
        .values_list('start', flat=True))

    # Withdraw the previous unbooked menu (keep the booked slot, if any).
    (InterviewSlot.objects
        .filter(application=application, is_active=True)
        .exclude(id=booked_id)
        .update(is_active=False, updated_at=now))

    created = [
        InterviewSlot.objects.create(
            application=application, reviewer=reviewer, start=s, duration_min=duration_min)
        for s in sorted(future)
    ]
    # A fresh menu resets the application back to "awaiting a pick": clear any outstanding
    # "these don't work" request, and lift a prior cancellation (otherwise the 'cancelled'
    # state sticks and the student never sees the new times).
    reset_fields = []
    if application.interview_status == 'cancelled':
        application.interview_status = ''
        application.interview_cancelled_at = None
        application.interview_slot = None
        application.interview_start = None
        reset_fields += ['interview_status', 'interview_cancelled_at',
                         'interview_slot', 'interview_start']
    if application.interview_alternatives_requested_at:
        application.interview_alternatives_requested_at = None
        application.interview_alternatives_note = ''
        reset_fields += ['interview_alternatives_requested_at', 'interview_alternatives_note']
    if application.interview_cancel_reason:        # fresh menu → the prior cancel reason is stale
        application.interview_cancel_reason = ''
        reset_fields.append('interview_cancel_reason')
    if reset_fields:
        application.save(update_fields=reset_fields)
    # Tell the student their times are ready to pick — but ONLY when the menu actually
    # changed (re-proposing the same set must not re-spam them), or when we just released a
    # booking to reschedule (they MUST re-pick, so always notify).
    if set(future) != prev_menu or rescheduling:
        student_email, student_name = _student_identity(application)
        if student_email:
            emails.send_interview_slots_proposed_email(
                student_email, student_name=student_name,
                english_only=emails.english_only_email(application),
                rescheduled=rescheduling)
        # Nudge on WhatsApp too (opt-in gated) so students who don't check email still respond.
        _send_wa_proposed(application, student_name, reviewer)
    # The interview process has begun — times are out, the first interview@ email goes to the
    # student — so advance the application to 'interviewing' to reflect reality on the board.
    # (The old trigger, creating the Interview-Stage capture draft, fired too late: reviewers
    # schedule + conduct the interview first and fill the capture form last, so cases sat at
    # 'profile_complete' through a booked/concluded interview.) Only ever advances FROM
    # profile_complete — never pulls a later or decided case backward.
    if application.status == 'profile_complete':
        application.status = 'interviewing'
        application.save(update_fields=['status'])
    return created


def withdraw_slot(slot, *, now=None):
    """Withdraw a single proposed slot (cannot withdraw the booked one)."""
    now = now or timezone.now()
    app = slot.application
    if app.interview_status == 'booked' and app.interview_slot_id == slot.id:
        raise SchedulingError('booked_slot')
    slot.is_active = False
    slot.save(update_fields=['is_active', 'updated_at'])
    return slot


# ── Student side: book / reschedule / cancel ──────────────────────────────────

@_bills_to_application
def book_slot(application, *, slot_id, now=None):
    """Student books (or reschedules to) a proposed slot.

    First booking: no cutoff. Reschedule (already booked): enforce the cutoff on the
    CURRENT booked time. Creates/updates the Meet event best-effort, sends a bilingual
    confirmation to the student and a notice to the reviewer, and resets the reminder
    stamps. Returns the application.
    """
    now = now or timezone.now()
    slot = (InterviewSlot.objects
            .filter(application=application, id=slot_id, is_active=True)
            .select_related('reviewer').first())
    if slot is None:
        raise SchedulingError('bad_slot')
    if slot.start <= now:
        raise SchedulingError('past_slot')

    rescheduling = application.interview_status == 'booked' and application.interview_start
    if rescheduling and not _cutoff_ok(application.interview_start, now,
                                       application.owning_organisation):
        raise SchedulingError('too_late')

    reviewer = slot.reviewer or application.assigned_to

    # Race backstop, in two strengths:
    #  - FIRST booking: only a confirmed BOOKING elsewhere blocks (first to book wins —
    #    a mere proposal to another student must not stop the student who acts first).
    #  - RE-PICK (reschedule): anything the reviewer now HOLDS elsewhere blocks, incl.
    #    a released time re-offered to another student — that option is hidden from the
    #    re-pick menu, but a stale page could still POST it.
    #
    # Both strengths compare BLOCKS, not starts (TD-233) — a 45-minute interview booked at
    # 10:00 blocks 10:30 even though no interview STARTS at 10:30.
    #
    # The first-booking branch used to hand-write its own query over ScholarshipApplication
    # (`assigned_to=reviewer, interview_start=...`) rather than call the shared helper — which
    # is why it was nearly missed here. It now reads the same slot rows as the other four call
    # sites, so "whose calendar is this?" is answered once. One consequence, deliberate: the
    # subject is the SLOT's reviewer, not the application's current `assigned_to`. They differ
    # only when a case is reassigned AFTER its interview is booked, and the person holding the
    # calendar invite is the one who must not be double-booked.
    if reviewer is not None:
        held = held_intervals(reviewer, exclude_application=application,
                              booked_only=not rescheduling)
        if overlaps(slot.start, slot.duration_min, held):
            raise SchedulingError('reviewer_conflict')

    student_email, student_name = _student_identity(application)
    reviewer_email = getattr(reviewer, 'email', '') if reviewer else ''
    reviewer_name = getattr(reviewer, 'name', '') if reviewer else ''

    # Meet: reuse + move the existing event on reschedule, else create a fresh one.
    prev_event = application.interview_calendar_event_id
    result = None
    if prev_event and meeting.meet_enabled():
        if meeting.update_event(prev_event, start=slot.start, duration_min=slot.duration_min):
            result = {'url': application.interview_meeting_url, 'event_id': prev_event}
    if result is None:
        if prev_event:
            meeting.cancel_event(prev_event)  # best-effort: drop the stale event
        result = meeting.create_event(
            summary=f'B40 interview — {student_name or "applicant"}',
            description='B40 Assistance Programme interview.',
            start=slot.start, duration_min=slot.duration_min,
            attendee_emails=[e for e in (student_email, reviewer_email) if e],
        )

    application.interview_slot = slot
    application.interview_start = slot.start
    application.interview_status = 'booked'
    application.interview_cancelled_at = None
    if result is not None:
        application.interview_meeting_url = result.get('url', '') or application.interview_meeting_url
        application.interview_calendar_event_id = result.get('event_id', '') or application.interview_calendar_event_id
        if result.get('url'):
            application.interview_meeting_provider = 'google_meet'
    # Set on EVERY (re)booking so reminder-notice (interview_start − interview_booked_at) reflects
    # the CURRENT slot — a reschedule to a sooner time then correctly re-gates the 24h/1h reminders.
    application.interview_booked_at = now
    application.interview_confirmation_sent_at = now
    application.interview_reminded_1d_at = None
    application.interview_reminded_1h_at = None
    application.save(update_fields=[
        'interview_slot', 'interview_start', 'interview_status', 'interview_cancelled_at',
        'interview_meeting_url', 'interview_calendar_event_id', 'interview_meeting_provider',
        'interview_booked_at', 'interview_confirmation_sent_at',
        'interview_reminded_1d_at', 'interview_reminded_1h_at',
    ])

    # Confirmations (best-effort). The cutoff is resolved HERE, where the organisation is in
    # hand, and passed in — `emails` takes an address and a time, never a tenant.
    from apps.courses import org_config
    emails.send_interview_booked_email(
        student_email, student_name=student_name, reviewer_name=reviewer_name,
        start=slot.start, meeting_url=application.interview_meeting_url,
        duration_min=slot.duration_min, english_only=emails.english_only_email(application),
        reschedule_cutoff_hours=org_config.value(application.owning_organisation,
                                                 'interview_reschedule_cutoff_hours'))
    if reviewer_email:
        emails.send_reviewer_interview_booked_email(
            reviewer_email, reviewer_name=reviewer_name, applicant_name=student_name,
            start=slot.start, meeting_url=application.interview_meeting_url,
            ref=pool.pool_ref(application.id), duration_min=slot.duration_min,
            calendar_invite_sent=bool(application.interview_calendar_event_id))
    return application


@_bills_to_application
def cancel(application, *, by='student', reason='', now=None):
    """Cancel the booked interview. A student cancel is subject to the cutoff. ``reason`` is the
    student's optional 'why I'm cancelling' — stored + passed to the reviewer's notice."""
    now = now or timezone.now()
    if application.interview_status != 'booked':
        raise SchedulingError('not_booked')
    if (by == 'student' and application.interview_start
            and not _cutoff_ok(application.interview_start, now,
                               application.owning_organisation)):
        raise SchedulingError('too_late')

    reviewer = application.assigned_to
    student_email, student_name = _student_identity(application)
    reason = (reason or '').strip()[:1000]

    if application.interview_calendar_event_id:
        meeting.cancel_event(application.interview_calendar_event_id)

    # The proposed menu is void once cancelled — withdraw every active slot so the cockpit
    # shows a clean "propose fresh times" state and no stale slots are offered.
    InterviewSlot.objects.filter(application=application, is_active=True).update(
        is_active=False, updated_at=now)
    application.interview_status = 'cancelled'
    application.interview_cancelled_at = now
    application.interview_slot = None
    application.interview_start = None
    application.interview_meeting_url = ''
    application.interview_calendar_event_id = ''
    application.interview_meeting_provider = ''
    application.interview_reminded_1d_at = None
    application.interview_reminded_1h_at = None
    application.interview_cancel_reason = reason
    application.save(update_fields=[
        'interview_status', 'interview_cancelled_at', 'interview_slot', 'interview_start',
        'interview_meeting_url', 'interview_calendar_event_id', 'interview_meeting_provider',
        'interview_reminded_1d_at', 'interview_reminded_1h_at', 'interview_cancel_reason',
    ])

    emails.send_interview_cancelled_email(student_email, student_name=student_name,
                                          english_only=emails.english_only_email(application))
    if reviewer is not None and getattr(reviewer, 'email', ''):
        emails.send_reviewer_interview_cancelled_email(
            reviewer.email, reviewer_name=getattr(reviewer, 'name', ''),
            applicant_name=student_name, ref=pool.pool_ref(application.id), reason=reason)
    return application


@_bills_to_application
def release_for_unassign(application, *, now=None):
    """Tear down interview artefacts when the assigned reviewer is REMOVED
    (services.assign_reviewer with reviewer=None). Mirrors cancel()'s teardown but is
    reviewer-initiated: a BOOKED interview is voided (Meet cancelled, booking cleared) and
    both the student and the OUTGOING reviewer are notified; if times were only PROPOSED
    (active slots, nothing booked) they are withdrawn quietly (the student never committed,
    so no notice). Any pending 'ask for other times' request is cleared. Best-effort on the
    Google/email side — never blocks the unassignment. MUST run BEFORE application.assigned_to
    is cleared so the outgoing reviewer still receives the notice. Returns the application."""
    now = now or timezone.now()
    reviewer = application.assigned_to
    was_booked = application.interview_status == 'booked'
    student_email, student_name = _student_identity(application)

    if was_booked and application.interview_calendar_event_id:
        meeting.cancel_event(application.interview_calendar_event_id)

    # The proposed menu is void either way — withdraw every active slot.
    InterviewSlot.objects.filter(application=application, is_active=True).update(
        is_active=False, updated_at=now)
    fields = []
    if was_booked:
        # Same booking-state reset as cancel() (kept in step with it).
        application.interview_status = 'cancelled'
        application.interview_cancelled_at = now
        application.interview_slot = None
        application.interview_start = None
        application.interview_meeting_url = ''
        application.interview_calendar_event_id = ''
        application.interview_meeting_provider = ''
        application.interview_reminded_1d_at = None
        application.interview_reminded_1h_at = None
        application.interview_cancel_reason = 'Reviewer unassigned — interview released'
        fields += [
            'interview_status', 'interview_cancelled_at', 'interview_slot', 'interview_start',
            'interview_meeting_url', 'interview_calendar_event_id', 'interview_meeting_provider',
            'interview_reminded_1d_at', 'interview_reminded_1h_at', 'interview_cancel_reason']
    if application.interview_alternatives_requested_at is not None:
        application.interview_alternatives_requested_at = None
        application.interview_alternatives_note = ''
        fields += ['interview_alternatives_requested_at', 'interview_alternatives_note']
    if fields:
        application.save(update_fields=fields)

    # Only notify when there was a BOOKED interview the student was expecting to attend.
    if was_booked:
        if student_email:
            emails.send_interview_released_email(
                student_email, student_name=student_name,
                english_only=emails.english_only_email(application))
        if reviewer is not None and getattr(reviewer, 'email', ''):
            emails.send_reviewer_interview_cancelled_email(
                reviewer.email, reviewer_name=getattr(reviewer, 'name', ''),
                applicant_name=student_name, ref=pool.pool_ref(application.id),
                reason='You were unassigned from this applicant.')
    return application


@_bills_to_application
def request_alternatives(application, *, note='', now=None):
    """The student says none of the proposed times work and asks for different ones. Records
    the request + an optional note and notifies the ASSIGNED reviewer directly (the proposed
    menu stays put until they propose a fresh one). Refused once an interview is booked
    (the student should reschedule/cancel instead). Best-effort email. Returns the application."""
    now = now or timezone.now()
    if application.interview_status == 'booked':
        raise SchedulingError('already_booked')
    application.interview_alternatives_requested_at = now
    application.interview_alternatives_note = (note or '').strip()[:1000]
    application.save(update_fields=[
        'interview_alternatives_requested_at', 'interview_alternatives_note'])

    reviewer = application.assigned_to
    _student_email, student_name = _student_identity(application)
    if reviewer is not None and getattr(reviewer, 'email', ''):
        emails.send_reviewer_alternatives_requested_email(
            reviewer.email, reviewer_name=getattr(reviewer, 'name', ''),
            applicant_name=student_name, note=application.interview_alternatives_note,
            ref=pool.pool_ref(application.id))
    return application


# ── Student → reviewer message channel ────────────────────────────────────────

MESSAGE_MAX_LEN = 1000
MESSAGE_RATE_LIMIT_PER_HOUR = 5


@_bills_to_application
def send_student_message(application, *, text, now=None):
    """The student sends a short free-text note to their assigned reviewer.

    Deliberately available in EVERY interview state and with NO cutoff — this is the
    pressure valve for "I'm running late" / "I'm sick" when reschedule/cancel are
    already locked (inside the 12h window, even one hour before the call). Stored on
    the application (cockpit thread + audit) and emailed to the assigned reviewer
    best-effort; the student never sees the reviewer's contact details.
    """
    now = now or timezone.now()
    text = (text or '').strip()
    if not text:
        raise SchedulingError('empty_message')
    text = text[:MESSAGE_MAX_LEN]
    reviewer = application.assigned_to
    if reviewer is None:
        raise SchedulingError('no_reviewer')

    from .models import InterviewMessage
    recent = (InterviewMessage.objects
              .filter(application=application, created_at__gte=now - timedelta(hours=1))
              .count())
    if recent >= MESSAGE_RATE_LIMIT_PER_HOUR:
        raise SchedulingError('rate_limited')

    message = InterviewMessage.objects.create(application=application, text=text)
    _student_email, student_name = _student_identity(application)
    if getattr(reviewer, 'email', ''):
        emails.send_reviewer_student_message_email(
            reviewer.email, reviewer_name=getattr(reviewer, 'name', ''),
            applicant_name=student_name, message=text,
            ref=pool.pool_ref(application.id),
            interview_start=application.interview_start)
    return message
