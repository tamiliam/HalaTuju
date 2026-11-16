"""Graduation thank-you moderation, and the bursary agreement countersignature.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.

Sprint THANKS (owner 2026-11-16): a thank-you is read and moderated from the student's CASE
PAGE by whoever holds the `review` KEY (a super holds every key). The role label decides
nothing here. The list that fed the old moderation queue was retired (TD-496, ruling B).
"""
import logging

from rest_framework import status
from rest_framework.response import Response
from ..models import GraduationMessage
from .. import in_programme as in_programme_service
from ..agreement_guard import AgreementNotCurrent
from ..serializers_admin import AdminGraduationMessageSerializer

from .base import _AdminBase

logger = logging.getLogger('apps.scholarship.views_admin')


def may_moderate_thanks(admin):
    """THE one rule for a graduation thank-you: the `review` key (owner 2026-11-16). The org fence
    (`_org_allows`, 404 cross-org) stays the caller's."""
    return admin is not None and admin.has_perm('review')


def _not_current(exc):
    """409: the agreement was withdrawn / superseded, or the case is past this step (A1.13)."""
    return Response({'error': exc.code, 'code': exc.code, 'reason': exc.reason},
                    status=status.HTTP_409_CONFLICT)


class AdminGraduationMessageReviewView(_AdminBase):
    """POST /api/v1/admin/graduation-messages/<id>/review/ — approve or reject a
    graduation thank-you (F9a). Gated on the `review` key (THANKS, owner 2026-11-16). Body:
    ``{action: 'approve'|'reject', scrubbed_text?, review_note?}``. On approve the
    ``scrubbed_text`` (defaults to the raw text) is RE-SCANNED so a staff edit can
    never reintroduce an identifier (400 `scrubbed_leak`). Only a `pending` message
    can be approved; `pending`/`blocked` can be rejected.

    THANKS review round: the message's CASE goes through the case page's own read fence
    (`_scoped_application`, the one the GET uses) BEFORE the body is read. Outside it the answer
    is 404 whatever the reason (no such message, another organisation, a case not assigned to a
    holder whose reach is assigned-only), so walking ids tells nobody which exist."""

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not may_moderate_thanks(admin):
            return self._deny_role()
        # org-fence: the message's case goes through _scoped_application (org + assignment) just below.
        message = GraduationMessage.objects.filter(pk=pk).first()
        app, err = (self._scoped_application(request, message.application_id) if message is not None
                    else (None, True))
        if err:   # no such message, or outside the case fence: one 404, never "it exists but not for you"
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        message.application = app
        action = request.data.get('action')
        action = action.strip() if isinstance(action, str) else ''
        by_email = getattr(admin, 'email', '') or ''
        try:
            if action == 'approve':
                in_programme_service.approve_graduation_message(
                    message, by_email=by_email,
                    scrubbed_text=request.data.get('scrubbed_text'),
                )
            elif action == 'reject':
                in_programme_service.reject_graduation_message(
                    message, by_email=by_email,
                    review_note=request.data.get('review_note', ''),
                )
            else:
                return Response({'error': 'action must be approve or reject',
                                 'code': 'bad_action'}, status=status.HTTP_400_BAD_REQUEST)
        except in_programme_service.InProgrammeError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminGraduationMessageSerializer(message).data)


class AdminCaseGraduationMessagesView(_AdminBase):
    """GET /api/v1/admin/scholarship/applications/<pk>/graduation-messages/ — the case's
    graduation thank-yous, newest first, for the case page's panel (THANKS). Two gates, both
    needed: the `review` key (nobody without it reads a thank-you), then the case's own read
    fence (`_scoped_application`, the detail GET's: an unassigned reviewer 403, another
    organisation 404). A separate fetch, so the applicant-detail GET keeps its pinned query
    count. The text may name the student, so no log line carries it."""

    def get(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not may_moderate_thanks(admin):
            return self._deny_role()
        app, err = self._scoped_application(request, pk)
        if err:
            return err
        logger.info('AUDIT graduation_messages_read admin_id=%s app_id=%s', admin.id, app.id)
        # org-fence: `app` came through _scoped_application (the case page's own fence) just above.
        rows = GraduationMessage.objects.filter(application=app).order_by('-created_at', '-id')
        return Response({'messages': AdminGraduationMessageSerializer(rows, many=True).data})


class _BursaryAdminBase(_AdminBase):
    """Shared lookup for the bursary-agreement admin actions."""

    def _agreement(self, pk):
        from ..models import BursaryAgreement
        return BursaryAgreement.objects.select_related(
            'application', 'application__profile', 'application__witness_org',
            'application__source', 'witness_org').filter(application_id=pk).first()


class AdminBursaryCountersignView(_BursaryAdminBase):
    """POST — the Foundation countersignature on a student's bursary agreement.
    SUPER-ONLY (the Foundation acts as counterparty). Stamps foundation_signed_by/_at
    with the acting super-admin's name and regenerates the PDF."""

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()
        agreement = self._agreement(pk)
        if agreement is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        from .. import bursary
        from ..serializers import BursaryAgreementSerializer
        try:
            bursary.countersign_foundation(agreement, by_name=getattr(admin, 'name', '') or '',
                                           actor=admin)
        except AgreementNotCurrent as exc:
            return _not_current(exc)
        return Response(BursaryAgreementSerializer(agreement).data)


class AdminBursaryWitnessView(_BursaryAdminBase):
    """POST — record the source's (non-blocking) witness attestation, as the FALLBACK. Since source
    sign-in S4 (2026-10-30) the witness source records it itself, from its console
    (`AdminSourceWitnessView`); a super may still record it here — for a source with nobody signed
    in, and (lead decision, the owner keeps the override) for one that has. SUPER-ONLY. The
    witness is the APPLICATION's witness organisation — the override, else the source that
    application named (`bursary._resolve_witness_org`) — never the referral partner. Once a
    witness is recorded — by the source or by a super — a second is refused (409
    `already_witnessed`, under the same row lock, `source_witness.record_once`). This NEVER blocks
    the award lifecycle — it is a record only."""

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        # The grandfathered "referring partner may witness" door is CLOSED: a `partner` login is a
        # REFERRAL PARTNER's, which is never the witness. A source user witnesses from its console.
        if not self.has_role(admin, 'super'):
            return self._deny_role()
        agreement = self._agreement(pk)
        if agreement is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        from .. import bursary
        from ..serializers import BursaryAgreementSerializer
        org = bursary._resolve_witness_org(agreement.application)
        if org is None:
            # No source and no override: nobody to witness (review fix) — assign one first.
            return Response({'error': 'no_witness_organisation', 'code': 'no_witness_organisation'},
                            status=status.HTTP_400_BAD_REQUEST)
        from .. import source_witness
        try:
            agreement = source_witness.record_once(
                agreement, org=org,
                by_name=getattr(admin, 'name', '') or '',
                witness_name=request.data.get('witness_name', '') or '', actor=admin)
        except source_witness.AlreadyWitnessed:
            return Response({'error': 'already_witnessed', 'code': 'already_witnessed'},
                            status=status.HTTP_409_CONFLICT)
        except source_witness.WitnessChanged:
            # The override moved between the read above and the row lock (review L2): ask again.
            return Response({'error': 'witness_changed', 'code': 'witness_changed'},
                            status=status.HTTP_409_CONFLICT)
        except AgreementNotCurrent as exc:
            return _not_current(exc)
        return Response(BursaryAgreementSerializer(agreement).data)
