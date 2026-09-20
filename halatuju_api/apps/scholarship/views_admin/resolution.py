"""Check 2 — requesting more from a student, and the resolution items that come back.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from ..emails import send_request_info_email
from ..serializers_admin import AdminApplicationDetailSerializer

from .base import _AdminBase


class AdminRequestInfoView(_AdminBase):
    """POST .../<pk>/request-info/ — the admin asks the student for more
    documentation. Records a note on the application + emails the student. Does
    NOT change status (the student keeps editing). Reviewer/super only."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        note = (request.data.get('note', '') or '').strip()
        if not note:
            return Response({'error': 'A note is required.', 'code': 'note_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        app.info_request_note = note
        app.info_requested_at = timezone.now()
        app.save(update_fields=['info_request_note', 'info_requested_at'])
        name = getattr(app.profile, 'name', '') if app.profile else ''
        send_request_info_email(to_email=app.notify_email, applicant_name=name,
                                programme_name=app.cohort.name, note=note, lang=app.locale)
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminResolutionItemView(_AdminBase):
    """POST .../<pk>/resolution-items/ — officer raises a manual resolution ticket
    (the structured successor to request-info). Body: {kind, prompt, doc_type?,
    fact?}. Reviewer/super only."""
    def post(self, request, pk):
        app, admin, err = self._require_app_write(request, pk)
        if err:
            return err
        # An officer may ask during Completed + Interviewing only (owner, 2026-07-13). Blocks
        # `shortlisted` — the Action Centre doesn't render until the student submits, so a ticket
        # raised there is invisible: a question nobody can see or answer. And blocks `interviewed`
        # onward — the interview is concluded, it's decision time. (Was gated on querying_locked,
        # which let an officer raise an unseeable ticket at `shortlisted`.)
        from ..services import officer_queries_allowed
        if not officer_queries_allowed(app):
            return Response({'error': 'querying_closed'}, status=status.HTTP_400_BAD_REQUEST)
        kind = (request.data.get('kind') or '').strip()
        prompt = (request.data.get('prompt') or '').strip()
        if kind not in ('doc', 'confirm', 'explanation'):
            return Response({'error': 'bad_kind'}, status=status.HTTP_400_BAD_REQUEST)
        if not prompt:
            return Response({'error': 'prompt_required'}, status=status.HTTP_400_BAD_REQUEST)
        member = (request.data.get('household_member') or '').strip()
        if member and member not in ('father', 'mother', 'guardian', 'brother', 'sister'):
            return Response({'error': 'bad_member'}, status=status.HTTP_400_BAD_REQUEST)
        from ..resolution import add_officer_item
        add_officer_item(app, kind=kind, prompt=prompt,
                         admin_email=getattr(admin, 'email', '') or '',
                         doc_type=(request.data.get('doc_type') or '').strip(),
                         fact=(request.data.get('fact') or 'other').strip(),
                         household_member=member)
        # Re-notify the student that there's something new for them — but DON'T email
        # per item (a reviewer raises several in one sitting → email spam + Brevo quota).
        # Instead reset the one-time notify stamp so the delayed, batched, idempotent
        # `send_due_query_emails` sweep sends ONE summary email on its next run (it now
        # counts officer items too). A re-request after the student cleared everything
        # thus re-notifies them once. Flag-gated to the student-query channel.
        from django.conf import settings as _settings
        if (getattr(_settings, 'CHECK2_STUDENT_QUERIES_ENABLED', False)
                and app.query_raised_notified_at is not None):
            app.query_raised_notified_at = None
            app.save(update_fields=['query_raised_notified_at'])
        return Response(AdminApplicationDetailSerializer(app).data)


class AdminResolutionItemActionView(_AdminBase):
    """POST .../resolution-items/<item_id>/<action>/ — officer waives or resolves
    a ticket by hand. action ∈ {waive, resolve}. Reviewer/super only."""
    def post(self, request, item_id, action):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if action not in ('waive', 'resolve', 'reopen'):
            return Response({'error': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        from ..models import ResolutionItem
        item = ResolutionItem.objects.filter(pk=item_id).select_related('application').first()
        if item is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # Assignment-based write: super, or the admin/reviewer assigned to the item's application.
        if not self._can_review_app(admin, item.application):
            return self._deny_role()
        from ..services import querying_locked
        if querying_locked(item.application):
            return Response({'error': 'querying_closed'}, status=status.HTTP_400_BAD_REQUEST)
        if action == 'reopen':
            # "Ask again" — the officer wasn't satisfied with the student's answer; send
            # the query back to the student's to-do. The typed answer stays in
            # resolution_text for the audit trail; only the answered stamp is cleared.
            item.status = 'open'
            item.resolved_by = ''
            item.resolved_at = None
        else:
            item.status = 'waived' if action == 'waive' else 'resolved'
            item.resolved_by = getattr(admin, 'email', '') or 'officer'
            item.resolved_at = timezone.now()
        item.save(update_fields=['status', 'resolved_by', 'resolved_at'])
        return Response(AdminApplicationDetailSerializer(item.application).data)
