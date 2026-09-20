"""Interview slots — the times an officer offers and the student books.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
from rest_framework import status
from rest_framework.response import Response
from ..models import InterviewSlot
from .. import scheduling
from ..serializers_admin import interview_schedule_payload

from .base import _AdminBase


def _parse_slot_starts(raw):
    """Parse the proposed-slot times from the request body into tz-aware datetimes.
    Accepts a list of ISO strings, or of objects with a 'start' key. A naive value
    (e.g. a browser datetime-local '2026-06-20T20:00') is read as Malaysia time."""
    from zoneinfo import ZoneInfo
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone as _tz
    out = []
    for item in (raw or []):
        s = item.get('start') if isinstance(item, dict) else item
        if not s:
            continue
        dt = parse_datetime(s)
        if dt is None:
            continue
        if _tz.is_naive(dt):
            dt = dt.replace(tzinfo=ZoneInfo('Asia/Kuala_Lumpur'))
        out.append(dt)
    return out


class AdminInterviewSlotsView(_AdminBase):
    """GET  .../applications/<pk>/interview-slots/ — booking state + proposed slots.
    POST .../applications/<pk>/interview-slots/ — the assigned reviewer (or super)
         proposes interview times. Body {slots: [<iso>, ...]} (or [{start}]). Dark
         behind INTERVIEW_SCHEDULING_ENABLED (404 when off)."""

    def get(self, request, pk):
        if not scheduling.scheduling_enabled():
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        app, err = self._scoped_application(request, pk)
        if err:
            return err
        return Response(interview_schedule_payload(app, include_reviewer_busy=True))

    def post(self, request, pk):
        if not scheduling.scheduling_enabled():
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        starts = _parse_slot_starts(request.data.get('slots'))
        # Minimum scheduling notice — reject any slot sooner than the lead window (checked
        # first so a too-soon time reads as 'too_soon', not 'invalid_slot_time').
        from django.utils import timezone as _tz
        _org = app.owning_organisation
        if any(s and not scheduling.meets_min_lead(s, _tz.now(), _org) for s in starts):
            return Response({'error': 'too_soon', 'code': 'too_soon'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Enforce the interview-slot rule (MYT, on the organisation's step, inside its booking
        # window) at the input boundary — the UI only offers valid chips, but reject anything
        # else too. Both checks read the SAME organisation the picker was served from.
        if any(s and not scheduling.slot_in_window(s, _org) for s in starts):
            return Response({'error': 'invalid_slot_time', 'code': 'invalid_slot_time'},
                            status=status.HTTP_400_BAD_REQUEST)
        # reschedule=True: the reviewer is MOVING an already-booked interview — release the
        # held booking, then offer the fresh menu (student is asked to re-pick).
        reschedule = bool(request.data.get('reschedule'))
        try:
            scheduling.propose_slots(app, reviewer=admin, starts=starts, release_booking=reschedule)
        except scheduling.SchedulingError as e:
            return Response({'error': str(e), 'code': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(interview_schedule_payload(app, include_reviewer_busy=True))


class AdminInterviewSlotDetailView(_AdminBase):
    """DELETE .../applications/<pk>/interview-slots/<slot_id>/ — withdraw a proposed
    (unbooked) slot. Reviewer/super, assignment-scoped."""

    def delete(self, request, pk, slot_id):
        if not scheduling.scheduling_enabled():
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        slot = InterviewSlot.objects.filter(application=app, pk=slot_id).first()
        if slot is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            scheduling.withdraw_slot(slot)
        except scheduling.SchedulingError as e:
            return Response({'error': str(e), 'code': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(interview_schedule_payload(app, include_reviewer_busy=True))
