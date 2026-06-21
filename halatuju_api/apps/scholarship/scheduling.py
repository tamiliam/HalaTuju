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

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from . import emails, meeting, pool
from .models import InterviewSlot

logger = logging.getLogger(__name__)

# Interview slot rule (mirrored in halatuju-web/src/lib/interviewSlots.ts — keep in
# lock-step): a proposed time must be MYT, on a 30-minute boundary, between 08:00 and
# 21:30 (latest start). Times are stored UTC; we compare in MYT.
_MYT = ZoneInfo('Asia/Kuala_Lumpur')
SLOT_WINDOW_START_MIN = 8 * 60        # 08:00
SLOT_WINDOW_END_MIN = 21 * 60 + 30    # 21:30 (latest start)
SLOT_STEP_MIN = 30
# Minimum scheduling notice (mirrored in halatuju-web/src/lib/interviewSlots.ts): the earliest
# proposable slot is this far ahead, so the student has time to see + pick + prepare.
SLOT_MIN_LEAD_HOURS = 24


def meets_min_lead(dt, now) -> bool:
    """True if a proposed start is at least SLOT_MIN_LEAD_HOURS ahead of ``now``."""
    return dt >= now + timedelta(hours=SLOT_MIN_LEAD_HOURS)


def slot_in_window(dt) -> bool:
    """True if a tz-aware datetime falls on an allowed interview slot (MYT, 30-min
    boundary, inside the 08:00–21:30 window). Enforced at the propose endpoint."""
    local = dt.astimezone(_MYT)
    if local.second or local.microsecond or local.minute % SLOT_STEP_MIN:
        return False
    mins = local.hour * 60 + local.minute
    return SLOT_WINDOW_START_MIN <= mins <= SLOT_WINDOW_END_MIN


class SchedulingError(Exception):
    """Raised with a stable string code the views map to a 400 response."""


def scheduling_enabled() -> bool:
    return bool(getattr(settings, 'INTERVIEW_SCHEDULING_ENABLED', False))


def _can_review(admin):
    """Mirror services._can_review: an active reviewer/super may propose slots."""
    if admin is None or not getattr(admin, 'is_active', False):
        return False
    return bool(getattr(admin, 'is_super_admin', False)) or getattr(admin, 'role', '') in ('reviewer', 'super')


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


def _cutoff_ok(start, now):
    """True if we're still outside the reschedule/cancel cutoff window."""
    hours = getattr(settings, 'INTERVIEW_RESCHEDULE_CUTOFF_HOURS', 12)
    return now < (start - timedelta(hours=hours))


# ── Reviewer side: propose / withdraw ─────────────────────────────────────────

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
    duration_min = duration_min or getattr(settings, 'INTERVIEW_DURATION_MIN', 45)

    if not _can_review(reviewer):
        raise SchedulingError('not_reviewer')
    is_super = bool(getattr(reviewer, 'is_super_admin', False)) or getattr(reviewer, 'role', '') == 'super'
    if not is_super and application.assigned_to_id != getattr(reviewer, 'id', None):
        raise SchedulingError('not_assigned')

    future = [s for s in starts if s and s > now]
    if not future:
        raise SchedulingError('no_future_slots')

    # Reviewer-wide conflict: never offer a time this reviewer already holds (proposed or
    # booked) for ANOTHER applicant — keeps one reviewer from being double-booked. The UI
    # greys these out; this is the server guard / race backstop.
    held = set(
        InterviewSlot.objects
        .filter(reviewer=reviewer, is_active=True)
        .exclude(application=application)
        .values_list('start', flat=True))
    if any(s in held for s in future):
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
    if rescheduling and not _cutoff_ok(application.interview_start, now):
        raise SchedulingError('too_late')

    reviewer = slot.reviewer or application.assigned_to

    # Race backstop: don't let two students land the same reviewer at the same time. (The
    # propose grid already greys a reviewer's held times, but a concurrent book could slip
    # through.) Self-reschedule is exempt via the exclude.
    if reviewer is not None:
        from .models import ScholarshipApplication
        clash = (ScholarshipApplication.objects
                 .filter(assigned_to=reviewer, interview_status='booked', interview_start=slot.start)
                 .exclude(id=application.id).exists())
        if clash:
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

    # Confirmations (best-effort).
    emails.send_interview_booked_email(
        student_email, student_name=student_name, reviewer_name=reviewer_name,
        start=slot.start, meeting_url=application.interview_meeting_url,
        duration_min=slot.duration_min, english_only=emails.english_only_email(application))
    if reviewer_email:
        emails.send_reviewer_interview_booked_email(
            reviewer_email, reviewer_name=reviewer_name, applicant_name=student_name,
            start=slot.start, meeting_url=application.interview_meeting_url,
            ref=pool.pool_ref(application.id), duration_min=slot.duration_min,
            calendar_invite_sent=bool(application.interview_calendar_event_id))
    return application


def cancel(application, *, by='student', now=None):
    """Cancel the booked interview. A student cancel is subject to the cutoff."""
    now = now or timezone.now()
    if application.interview_status != 'booked':
        raise SchedulingError('not_booked')
    if by == 'student' and application.interview_start and not _cutoff_ok(application.interview_start, now):
        raise SchedulingError('too_late')

    reviewer = application.assigned_to
    student_email, student_name = _student_identity(application)

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
    application.save(update_fields=[
        'interview_status', 'interview_cancelled_at', 'interview_slot', 'interview_start',
        'interview_meeting_url', 'interview_calendar_event_id', 'interview_meeting_provider',
        'interview_reminded_1d_at', 'interview_reminded_1h_at',
    ])

    emails.send_interview_cancelled_email(student_email, student_name=student_name,
                                          english_only=emails.english_only_email(application))
    if reviewer is not None and getattr(reviewer, 'email', ''):
        emails.send_reviewer_interview_cancelled_email(
            reviewer.email, reviewer_name=getattr(reviewer, 'name', ''),
            applicant_name=student_name, ref=pool.pool_ref(application.id))
    return application


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
