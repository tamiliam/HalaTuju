"""Wallet credits (P4b) — a sponsor donation recorded, signed off, or cancelled.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
from rest_framework import status
from rest_framework.response import Response
from ..models import Donation, Sponsor

from .base import _AdminBase


# ── Wallet credits (P4b) ─────────────────────────────────────────────────────────
# The admin surface that DRIVES the P4a credit chain. Until this existed, every wallet
# credit on the platform — including the RM172,000 already recorded — was written by a
# developer touching the database, which made the sign-off chain a control on paper: the
# people it names (an `admin` maker, an `org_admin` approver) had no way to execute their
# own steps. These endpoints remove the developer from the money path.
#
# ORG FENCE: a Sponsor is a platform-level account and is deliberately NOT org-fenced (see
# AdminSponsorListView), but a CREDIT is not — it belongs to a Programme, which belongs to
# an Organisation. Every read and write below is fenced on `programme__organisation_id`, so
# one tenant can never see or sign another tenant's money.

class _CreditsBase(_AdminBase):
    """Shared gate + org-fenced credit lookup for the wallet-credit endpoints."""

    # Who may OPEN a credit screen. Mirrors the payments read gate: finance is admitted
    # because checking is its job; the per-step role logic lives in the service, so this
    # gate is deliberately broad and `sponsorship.sign_admin_credit` refuses the wrong step.
    _READ_ROLES = ('org_admin', 'admin', 'finance')

    def _credits_admin(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (admin.is_super or admin.role in self._READ_ROLES):
            return None, self._deny_role()
        return admin, None

    def _credit_qs(self, admin):
        """Every credit visible to this admin — fenced by the programme's organisation."""
        return self._org_scoped(
            Donation.objects.select_related('sponsor', 'programme'),
            admin, field='programme__organisation_id')

    def _credit_for(self, admin, pk):
        return self._credit_qs(admin).filter(pk=pk).first()


def _credit_dict(credit):
    """Allowlist view of one credit. Explicit fields only — never model passthrough — so a
    later column cannot leak onto an admin surface by accident."""
    return {
        'id': credit.id,
        'sponsor_id': credit.sponsor_id,
        'sponsor_name': getattr(credit.sponsor, 'name', '') or '',
        'programme_id': credit.programme_id,
        'programme_name': getattr(credit.programme, 'name_en', '') or '',
        'amount': str(credit.amount),
        'source': credit.source,
        'external_reference': credit.external_reference,
        'status': credit.status,
        'is_spendable': credit.is_spendable,
        'recorded_by': credit.recorded_by,
        'recorded_at': credit.recorded_at,
        'finance_checked_by': credit.finance_checked_by,
        'finance_checked_at': credit.finance_checked_at,
        'confirmed_by': credit.confirmed_by,
        'confirmed_at': credit.confirmed_at,
        'created_at': credit.created_at,
    }


class AdminWalletCreditListCreateView(_CreditsBase):
    """GET  .../admin/scholarship/credits/[?sponsor=<id>&status=<s>] — the credit ledger.
    POST .../admin/scholarship/credits/ {sponsor_id, programme_id, amount,
    external_reference} — RECORD an off-platform gift as a `draft`.

    Recording stamps no signature: it opens the chain, and the maker signs separately with
    a typed name (the same separation payments keeps between create_run and sign)."""

    def get(self, request):
        admin, err = self._credits_admin(request)
        if err:
            return err
        qs = self._credit_qs(admin)
        sponsor_id = request.query_params.get('sponsor')
        if sponsor_id:
            qs = qs.filter(sponsor_id=sponsor_id)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response({'credits': [_credit_dict(c) for c in qs.order_by('-id')]})

    def post(self, request):
        admin, err = self._credits_admin(request)
        if err:
            return err
        from decimal import Decimal, InvalidOperation
        from .. import sponsorship as sponsorship_service
        from ..models import Programme
        sponsor = Sponsor.objects.filter(pk=request.data.get('sponsor_id')).first()
        if sponsor is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # The programme must be one this admin's organisation runs — otherwise an admin
        # could credit a wallet inside another tenant's gift.
        programme = self._org_scoped(
            Programme.objects.all(), admin, field='organisation_id'
        ).filter(pk=request.data.get('programme_id')).first()
        if programme is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            amount = Decimal(str(request.data.get('amount')))
        except (InvalidOperation, TypeError, ValueError):
            return Response({'error': 'invalid_amount', 'code': 'invalid_amount'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            credit = sponsorship_service.record_admin_credit(
                sponsor=sponsor, programme=programme, amount=amount,
                external_reference=request.data.get('external_reference') or '',
                admin=admin)
        except sponsorship_service.CreditError as e:
            return Response({'error': e.code, 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(_credit_dict(credit), status=status.HTTP_201_CREATED)


class AdminWalletCreditSignView(_CreditsBase):
    """POST .../admin/scholarship/credits/<pk>/sign/ {typed_name} — maker sign, finance
    check (when the org's chain includes that step), or approver countersign, whichever is
    this credit's next step. The per-step role logic + typed-name match + pairwise
    distinctness live in `sponsorship.sign_admin_credit`; this view admits every credit role
    and lets the service refuse the wrong step (exactly as AdminPaymentRunSignView does)."""

    def post(self, request, pk):
        admin, err = self._credits_admin(request)
        if err:
            return err
        credit = self._credit_for(admin, pk)
        if credit is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from .. import sponsorship as sponsorship_service
        try:
            sponsorship_service.sign_admin_credit(
                credit, admin, request.data.get('typed_name') or '')
        except sponsorship_service.CreditError as e:
            return Response({'error': e.code, 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)
        credit.refresh_from_db()
        return Response(_credit_dict(credit))


class AdminWalletCreditCancelView(_CreditsBase):
    """POST .../admin/scholarship/credits/<pk>/cancel/ — void a credit that has not been
    confirmed (a mis-keyed amount or bank reference). The row is never deleted; a confirmed
    credit is reversed by a compensating entry, never by editing history."""

    def post(self, request, pk):
        admin, err = self._credits_admin(request)
        if err:
            return err
        credit = self._credit_for(admin, pk)
        if credit is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        from .. import sponsorship as sponsorship_service
        try:
            sponsorship_service.cancel_admin_credit(credit, admin)
        except sponsorship_service.CreditError as e:
            return Response({'error': e.code, 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)
        credit.refresh_from_db()
        return Response(_credit_dict(credit))
