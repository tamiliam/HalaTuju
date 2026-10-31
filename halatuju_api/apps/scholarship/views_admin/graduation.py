"""Graduation messages awaiting moderation, and the bursary agreement countersignature.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
from rest_framework import status
from rest_framework.response import Response
from halatuju.pagination import FlexiblePageNumberPagination
from ..models import GraduationMessage
from .. import in_programme as in_programme_service
from ..serializers_admin import AdminGraduationMessageSerializer

from .base import _AdminBase


class AdminGraduationMessageListView(_AdminBase):
    """GET /api/v1/admin/graduation-messages/ — the moderation queue (F9a). Reviewer +
    super (viewer is read-only staff and may also read). ``?status=pending`` (default)
    filters; ``?status=all`` returns everything. Staff see the full text + scan
    outcome — they are NOT the anonymity boundary.

    Role gate (TD-153 b, 2026-09-30): exactly the roles this docstring always named — `reviewer`
    (who moderates, via `AdminGraduationMessageReviewView`) and super — plus `admin`, which is
    what 'viewer' became when it was retired on 2026-06-09. No page calls this queue."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not (admin.is_super or admin.role in ('reviewer', 'admin')):
            return self._deny_role()
        # org-fence: _org_scoped on the application join, applied below.
        qs = GraduationMessage.objects.select_related('application').all()
        qs = self._org_scoped(qs, admin, field='application__owning_organisation_id')
        status_f = request.GET.get('status', 'pending')
        if status_f != 'all':
            qs = qs.filter(status=status_f)
        paginator = FlexiblePageNumberPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = AdminGraduationMessageSerializer(page, many=True).data
        return paginator.envelope(
            data, results_key='messages', total_count=paginator.page.paginator.count,
        )


class AdminGraduationMessageReviewView(_AdminBase):
    """POST /api/v1/admin/graduation-messages/<id>/review/ — approve or reject a
    graduation thank-you (F9a). Reviewer + super only (viewer is read-only). Body:
    ``{action: 'approve'|'reject', scrubbed_text?, review_note?}``. On approve the
    ``scrubbed_text`` (defaults to the raw text) is RE-SCANNED so a staff edit can
    never reintroduce an identifier (400 `scrubbed_leak`). Only a `pending` message
    can be approved; `pending`/`blocked` can be rejected."""

    def post(self, request, pk):
        admin, err = self._require_reviewer(request)
        if err:
            return err
        # org-fence: _org_allows(message.application) checked immediately below.
        message = GraduationMessage.objects.select_related(
            'application', 'application__profile').filter(pk=pk).first()
        if message is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if not self._org_allows(admin, message.application):
            # Cross-org write: 404, don't leak existence (Sprint 3a).
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        action = (request.data.get('action') or '').strip()
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
        if not (admin.is_super_admin or self.has_role(admin, 'super')):
            return self._deny_role()
        agreement = self._agreement(pk)
        if agreement is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        from .. import bursary
        from ..serializers import BursaryAgreementSerializer
        bursary.countersign_foundation(agreement, by_name=getattr(admin, 'name', '') or '',
                                       actor=admin)
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
        if not (admin.is_super_admin or self.has_role(admin, 'super')):
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
        return Response(BursaryAgreementSerializer(agreement).data)
