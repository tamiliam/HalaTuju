"""The bursary agreement countersignature.

Moved verbatim from the package root at code health H12. Part of the `views_admin` package: every
name below is re-exported from `views_admin/__init__.py`, so `urls.py` and every importer are unchanged.

Sprint THANKS-SCHOLARS (owner 2026-11-16, "Thank yous are part of the scholar maintenance process"):
the graduation thank-you views that lived here (and `may_moderate_thanks`, the `review` key) moved to
the scholar file, `views_admin/scholar_thanks.py`, under the `scholars` key's rules.
"""
from rest_framework import status
from rest_framework.response import Response
from ..agreement_guard import AgreementNotCurrent

from .base import _AdminBase


def _not_current(exc):
    """409: the agreement was withdrawn / superseded, or the case is past this step (A1.13)."""
    return Response({'error': exc.code, 'code': exc.code, 'reason': exc.reason},
                    status=status.HTTP_409_CONFLICT)


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
