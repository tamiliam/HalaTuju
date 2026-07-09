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

from . import emails, meeting, pool, whatsapp
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


def held_starts(reviewer, *, exclude_application=None):
    """The start times this reviewer genuinely HOLDS — the single source of truth for
    conflict-blocking (propose grid, propose guard, book guard, student re-pick menu).

    Hold semantics (owner's design, 2026-07-02):
      - an UNBOOKED application's active proposals all hold the reviewer's time (the
        student may pick any of them);
      - once an application is BOOKED, only its booked slot holds — the unpicked
        siblings are RELEASED (they stay active as the student's re-pick menu, but no
        longer block the reviewer offering those times to someone else; first to book
        wins, and a released time re-offered elsewhere disappears from the original
        student's re-pick menu).
    """
    if reviewer is None:
        return set()
    from django.db.models import F, Q
    qs = InterviewSlot.objects.filter(reviewer=reviewer, is_active=True)
    if exclude_application is not None:
        qs = qs.exclude(application=exclude_application)
    # Drop the released siblings: slots of a BOOKED application that are not its
    # booked slot. Everything else (unbooked proposals + booked slots) holds.
    qs = qs.exclude(Q(application__interview_status='booked')
                    & ~Q(application__interview_slot_id=F('id')))
    return set(qs.values_list('start', flat=True))


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

    # Reviewer-wide conflict: never offer a time this reviewer already HOLDS for ANOTHER
    # applicant — keeps one reviewer from being double-booked. A booked application's
    # released siblings no longer hold (see held_starts), so those times are re-offerable.
    # The UI greys held times out; this is the server guard / race backstop.
    held = held_starts(reviewer, exclude_application=application)
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

    # Race backstop, in two strengths:
    #  - FIRST booking: only a confirmed BOOKING elsewhere blocks (first to book wins —
    #    a mere proposal to another student must not stop the student who acts first).
    #  - RE-PICK (reschedule): anything the reviewer now HOLDS elsewhere blocks, incl.
    #    a released time re-offered to another student — that option is hidden from the
    #    re-pick menu, but a stale page could still POST it.
    if reviewer is not None:
        if rescheduling:
            conflict = slot.start in held_starts(reviewer, exclude_application=application)
        else:
            from .models import ScholarshipApplication
            conflict = (ScholarshipApplication.objects
                        .filter(assigned_to=reviewer, interview_status='booked',
                                interview_start=slot.start)
                        .exclude(id=application.id).exists())
        if conflict:
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


def cancel(application, *, by='student', reason='', now=None):
    """Cancel the booked interview. A student cancel is subject to the cutoff. ``reason`` is the
    student's optional 'why I'm cancelling' — stored + passed to the reviewer's notice."""
    now = now or timezone.now()
    if application.interview_status != 'booked':
        raise SchedulingError('not_booked')
    if by == 'student' and application.interview_start and not _cutoff_ok(application.interview_start, now):
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
