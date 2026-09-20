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
    outcome — they are NOT the anonymity boundary."""

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
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
            'application', 'application__profile', 'witness_org').filter(application_id=pk).first()


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
        bursary.countersign_foundation(agreement, by_name=getattr(admin, 'name', '') or '')
        return Response(BursaryAgreementSerializer(agreement).data)


class AdminBursaryWitnessView(_BursaryAdminBase):
    """POST — the partner organisation's (non-blocking) witness attestation. Allowed for
    a PartnerAdmin whose org == the application's referring org (else 403); a super may
    also witness. This NEVER blocks the award lifecycle — it is a record only."""

    def post(self, request, pk):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        agreement = self._agreement(pk)
        if agreement is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        profile = agreement.application.profile
        # tenancy: GRANDFATHERED exception — witness authority is REFERRAL semantics
        # (the org that referred the student attests), which is orthogonal to the
        # ownership fence. This is the ONE place `admin.org`/`referred_by_org` is
        # intentionally used for authorisation. A non-blocking record only.
        org = getattr(profile, 'referred_by_org', None) if profile else None
        is_super = bool(admin.is_super_admin or self.has_role(admin, 'super'))
        is_referring_partner = bool(
            org is not None and admin.org_id is not None and admin.org_id == org.id)
        if not (is_super or is_referring_partner):
            return self._deny_role()
        from .. import bursary
        from ..serializers import BursaryAgreementSerializer
        bursary.record_witness(
            agreement, org=org,
            by_name=getattr(admin, 'name', '') or '',
            witness_name=request.data.get('witness_name', '') or '')
        return Response(BursaryAgreementSerializer(agreement).data)
