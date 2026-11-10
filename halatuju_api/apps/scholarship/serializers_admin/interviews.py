"""Interview session and slot serializers, and the interview schedule payload."""

from rest_framework import serializers
from ..models import InterviewSession, InterviewSlot


class InterviewSessionSerializer(serializers.ModelSerializer):
    interviewer_name = serializers.CharField(source='interviewer.name', read_only=True, default=None)

    class Meta:
        model = InterviewSession
        fields = [
            'id', 'status', 'findings', 'rubric', 'overall_note',
            'interviewer_name', 'started_at', 'submitted_at', 'updated_at',
        ]


class InterviewSlotSerializer(serializers.ModelSerializer):
    """One proposed interview time. Times are ISO (UTC); the FE renders them in MYT."""
    class Meta:
        model = InterviewSlot
        fields = ['id', 'start', 'duration_min', 'is_active']


def interview_schedule_payload(application, *, include_reviewer_busy=False):
    """The interview-scheduling block shared by the admin + student responses:
    the booking state + the active proposed slots. Used by both serializers so the
    cockpit and the student portal read identical data.

    ``include_reviewer_busy`` (reviewer/admin context ONLY) adds the start times this
    reviewer already holds for OTHER applicants, so the propose grid can grey them out
    to avoid double-booking. Never sent to students (it would leak other interviews)."""
    from django.conf import settings

    from .. import scheduling
    active = [s for s in application.interview_slots.all() if s.is_active]
    active.sort(key=lambda s: s.start)
    # A BOOKED application's unpicked siblings are RELEASED (scheduling.held_intervals):
    # the reviewer may re-offer those times to other students, first to book wins. So
    # the re-pick menu must drop any released time the reviewer has since re-offered
    # or re-booked elsewhere — otherwise the student books into a conflict. Overlap, not
    # exact start (TD-233): with an interview longer than the step, a released 10:30 is
    # unpickable once the reviewer books someone else at 10:00.
    if application.interview_status == 'booked' and application.assigned_to_id:
        taken = scheduling.held_intervals(application.assigned_to,
                                          exclude_application=application)
        active = [s for s in active
                  if s.id == application.interview_slot_id
                  or not scheduling.overlaps(s.start, s.duration_min, taken)]
    payload = {
        'enabled': bool(getattr(settings, 'INTERVIEW_SCHEDULING_ENABLED', False)),
        'status': application.interview_status or '',
        'start': application.interview_start,
        'meeting_url': application.interview_meeting_url or '',
        'meeting_provider': application.interview_meeting_provider or '',
        'booked_slot_id': application.interview_slot_id,
        'slots': InterviewSlotSerializer(active, many=True).data,
        # ⚠ THE BOOKING RULES ARE SERVED, NEVER MIRRORED (Org Config Sprint D). The picker
        # used to hold its own copy of the window/step/lead in `interviewSlots.ts` under a
        # "keep in lock-step" comment; they are the ORGANISATION's now, so the only honest
        # copy is the one that travels with the data. This payload feeds BOTH the reviewer's
        # propose grid and the student's booking panel, so one seam serves both.
        **_slot_rules_payload(application),
        # Student asked for different times (none of the proposed slots worked).
        'alternatives_requested': application.interview_alternatives_requested_at is not None,
        'alternatives_note': application.interview_alternatives_note or '',
        # Why the student cancelled their booked interview (if they gave a reason).
        'cancel_reason': application.interview_cancel_reason or '',
        # The student's messages to their reviewer (always-open channel) — newest last,
        # bounded so a chatty thread can't bloat the payload.
        'messages': [
            {'text': m.text, 'created_at': m.created_at}
            for m in application.interview_messages.order_by('-created_at')[:20][::-1]
        ],
    }
    if include_reviewer_busy:
        # The grid starts the reviewer CANNOT begin a new interview at — not merely the ones
        # she already holds (TD-233). The server expands her held blocks against this
        # organisation's own length and step, so the picker keeps doing a plain set-membership
        # test and never learns what a duration is: serve, don't mirror. With length 45 and
        # step 30, a booking at 10:00 greys out 09:30, 10:00 and 10:30.
        # (A booked application's released siblings no longer block — see
        # scheduling.held_intervals for the hold semantics.)
        payload['reviewer_busy'] = sorted(scheduling.blocked_starts(
            scheduling.held_intervals(application.assigned_to,
                                      exclude_application=application),
            duration_min=payload['interview_duration_min'],
            step_min=payload['slot_step_min'],
        ))
    return payload


def _slot_rules_payload(application):
    """The five interview numbers the browser needs, resolved for this application's
    organisation. `reschedule_cutoff_hours` keeps its existing name — it was already served
    (and already read by the student panel); Sprint D only made it per-organisation."""
    from apps.courses import org_config
    from .. import scheduling
    org = application.owning_organisation
    rules = scheduling.slot_rules(org)
    return {
        'reschedule_cutoff_hours': org_config.value(org, 'interview_reschedule_cutoff_hours'),
        'interview_duration_min': org_config.value(org, 'interview_duration_min'),
        'slot_window_start_min': rules['window_start_min'],
        'slot_window_end_min': rules['window_end_min'],
        'slot_step_min': rules['step_min'],
        'slot_min_lead_hours': rules['min_lead_hours'],
    }
