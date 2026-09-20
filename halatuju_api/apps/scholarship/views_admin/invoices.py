"""Tenant invoices, receipts and build hours — moved verbatim from `views_admin.py` at H11.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from .. import money
from .base import _AdminBase, _MONTH_RE, _org_or_none


# ── Tenant invoices and receipts (2026-09-14) ─────────────────────────────────

def _invoice_money(v):
    # Money crosses as a STRING. A bare Decimal in a nested dict renders as a float (sponsor-card
    # lesson), and a float in an invoice payload is how RM30.00 becomes RM30.0 on a bill.
    # ⚠ Same rule, same parameters, as the platform-cost payload's own formatter further up this
    # file — code health H7 found the two were byte-identical copies written four days apart and
    # routed both through `money.format_money` rather than leaving a third to appear next.
    return money.format_money(v, blank=None, blank_when=money.BLANK_NONE,
                              quantize=False, coerce=False)


def _invoice_payload(inv, *, for_super):
    """ONE invoice as the API returns it. An allowlist, typed out by hand.

    ⚠ The tenant shape carries no issuing email, no override reason and no recipient list: the
    override reason quotes internal warnings ("Supabase has nothing recorded") that describe the
    platform's own cost ledger, which is super-only everywhere else.
    """
    receipts = list(inv.receipts.all())
    out = {
        'id': inv.id,
        'number': inv.number,
        'organisation_id': inv.organisation_id,
        'organisation': inv.organisation.name,
        'period_month': inv.period_month,
        'issued_on': inv.issued_on.isoformat(),
        'due_on': inv.due_on.isoformat(),
        'status': inv.status,
        'currency': inv.currency,
        'subtotal_myr': _invoice_money(inv.subtotal_myr),
        'discount_pct': _invoice_money(inv.discount_pct),
        'discount_myr': _invoice_money(inv.discount_myr),
        'discount_reason': inv.discount_reason,
        'total_myr': _invoice_money(inv.total_myr),
        'amount_paid_myr': _invoice_money(inv.amount_paid()),
        'balance_myr': _invoice_money(inv.balance()),
        'sent_at': inv.sent_at.isoformat() if inv.sent_at else None,
        'voided_at': inv.voided_at.isoformat() if inv.voided_at else None,
        'void_reason': inv.void_reason,
        'bill_to_name': (inv.bill_to_snapshot or {}).get('bill_to_name', ''),
        'lines': [{
            'position': ln.position,
            'category': ln.category,
            'description': ln.description,
            'quantity': _invoice_money(ln.quantity),
            'unit_amount_myr': _invoice_money(ln.unit_amount_myr),
            'amount_myr': _invoice_money(ln.amount_myr),
        } for ln in inv.lines.all()],
        'receipts': [{
            'id': r.id,
            'number': r.number,
            'received_on': r.received_on.isoformat(),
            'amount_myr': _invoice_money(r.amount_myr),
            'method': r.method,
            'reference': r.reference,
        } for r in receipts],
    }
    if for_super:
        out.update({
            'issued_by_email': inv.issued_by_email,
            'override_reason': inv.override_reason,
            'sent_by_email': inv.sent_by_email,
            'sent_to': list(inv.sent_to or []),
            # Where Send WILL deliver — the frozen bill-to inboxes — so the confirm step can name
            # them before anything leaves the building.
            'bill_to_emails': list((inv.bill_to_snapshot or {}).get('emails', [])),
            'voided_by_email': inv.voided_by_email,
            'replaces_number': inv.replaces.number if inv.replaces_id else '',
        })
    return out


class _InvoiceBase(_AdminBase):
    """Shared door for the invoice endpoints: who is asking, and which invoice they may see."""

    def _caller(self, request):
        """→ (admin, is_super, error_response). Super, or org_admin while billing is live."""
        admin = self.get_admin(request)
        if not admin:
            return None, False, self._deny()
        is_super = self.has_role(admin, 'super')
        # Same 404-first gate as the usage screen: every non-super keeps getting the dark 404
        # while `BILLING_USAGE_ENABLED` is off, so the invoices route adds no existence signal.
        if not is_super and not getattr(settings, 'BILLING_USAGE_ENABLED', False):
            return None, False, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        if not (is_super or admin.role == 'org_admin'):
            return None, False, self._deny_role()
        return admin, is_super, None

    def _visible_invoices(self, admin, is_super):
        """THE FENCE, in one place. A tenant sees its OWN invoices, and only those that were SENT.

        ⚠ "Sent" is part of the fence, not a display filter. The owner's ruling is that nothing
        leaves the building until a super presses Send; an issued invoice appearing on the
        tenant's screen before then would be sending it by a second door.
        """
        from ..models import Invoice
        qs = Invoice.objects.select_related('organisation', 'replaces').prefetch_related(  # org-fence: narrowed below for every non-super
            'lines', 'receipts')
        if is_super:
            return qs
        if not admin.owning_organisation_id:
            return qs.none()
        return qs.filter(organisation_id=admin.owning_organisation_id, sent_at__isnull=False)

    @staticmethod
    def _error(exc):
        from .. import invoicing
        if isinstance(exc, invoicing.InvoiceRefused):
            return Response({'error': exc.code, 'code': exc.code, 'problems': exc.problems},
                            status=status.HTTP_409_CONFLICT)
        return Response({'error': exc.code, 'code': exc.code, 'message': exc.message},
                        status=status.HTTP_400_BAD_REQUEST)


class AdminInvoicesView(_InvoiceBase):
    """GET the invoices a caller may see; POST (super) issues one.

    Super's GET also carries `readiness` — for each tenant, whether the chosen month (default: the
    previous one) can be issued and every reason it cannot — so the screen can offer Issue, or
    Issue anyway with a reason, without a second round trip.
    """

    def get(self, request):
        admin, is_super, err = self._caller(request)
        if err:
            return err
        from .. import invoicing

        invoices = [_invoice_payload(i, for_super=is_super)
                    for i in self._visible_invoices(admin, is_super)]
        payload = {'invoices': invoices}
        if is_super:
            from apps.courses.models import PartnerOrganisation
            month = (request.query_params.get('month') or '').strip() or invoicing.previous_month()
            if not invoicing.MONTH_RE.match(month):
                return Response({'error': 'bad_month', 'code': 'bad_month'},
                                status=status.HTTP_400_BAD_REQUEST)
            payload['month'] = month
            payload['issue_day'] = invoicing.ISSUE_DAY
            payload['readiness'] = [{
                'organisation_id': org.id,
                'organisation': org.name,
                'problems': invoicing.readiness(org, month),
            } for org in PartnerOrganisation.objects.tenants().order_by('name')]
        return Response(payload)

    def post(self, request):
        admin, is_super, err = self._caller(request)
        if err:
            return err
        if not is_super:
            return self._deny_role()
        from apps.courses.models import PartnerOrganisation

        from .. import invoicing

        month = (request.data.get('period_month') or '').strip()
        if not invoicing.MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)
        org = PartnerOrganisation.objects.filter(pk=request.data.get('organisation_id')).first()
        if org is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            inv = invoicing.issue_invoice(
                org, month, issued_by_email=admin.email or '',
                override_reason=request.data.get('override_reason') or '')
        except invoicing.InvoicingError as exc:
            return self._error(exc)
        inv = self._visible_invoices(admin, True).get(pk=inv.pk)
        return Response(_invoice_payload(inv, for_super=True), status=status.HTTP_201_CREATED)


class AdminInvoiceActionView(_InvoiceBase):
    """SUPER-ONLY actions on one invoice: `send`, `void`, `receipt`."""

    def post(self, request, pk, action):
        admin, is_super, err = self._caller(request)
        if err:
            return err
        if not is_super:
            return self._deny_role()
        from .. import invoicing

        inv = self._visible_invoices(admin, True).filter(pk=pk).first()
        if inv is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        by = admin.email or ''
        try:
            if action == 'send':
                invoicing.send_invoice(inv, sent_by_email=by)
            elif action == 'void':
                invoicing.void_invoice(inv, reason=request.data.get('reason'), voided_by_email=by)
            elif action == 'receipt':
                invoicing.record_receipt(
                    inv,
                    received_on=(request.data.get('received_on') or '').strip(),
                    amount_myr=request.data.get('amount_myr'),
                    reference=request.data.get('reference'),
                    method=(request.data.get('method') or 'bank_transfer').strip(),
                    note=request.data.get('note') or '',
                    recorded_by_email=by)
            else:
                return Response({'error': 'not_found', 'code': 'not_found'},
                                status=status.HTTP_404_NOT_FOUND)
        except invoicing.InvoicingError as exc:
            return self._error(exc)
        inv = self._visible_invoices(admin, True).get(pk=pk)
        return Response(_invoice_payload(inv, for_super=True))


class AdminInvoicePdfView(_InvoiceBase):
    """GET an invoice PDF (`kind='invoice'`) or a receipt PDF (`kind='receipt'`).

    Fenced through `_visible_invoices` for BOTH: a receipt is reachable only through an invoice the
    caller may see, so a tenant naming another tenant's receipt id gets the same 404 as a missing one.
    """

    def get(self, request, pk, kind):
        admin, is_super, err = self._caller(request)
        if err:
            return err
        from django.http import HttpResponse

        from .. import invoice_pdf, invoicing
        from ..models import InvoiceReceipt

        visible = self._visible_invoices(admin, is_super)
        not_found = Response({'error': 'not_found', 'code': 'not_found'},
                             status=status.HTTP_404_NOT_FOUND)
        try:
            if kind == 'invoice':
                inv = visible.filter(pk=pk).first()
                if inv is None:
                    return not_found
                pdf, name = invoice_pdf.invoice_pdf(inv), inv.number
            elif kind == 'receipt':
                receipt = (InvoiceReceipt.objects.select_related('invoice')  # org-fence: through the fenced invoice set
                           .filter(pk=pk, invoice__in=visible).first())
                if receipt is None:
                    return not_found
                pdf, name = invoice_pdf.receipt_pdf(receipt), receipt.number
            else:
                return not_found
        except invoicing.InvoicingError as exc:
            return self._error(exc)
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{name}.pdf"'
        return resp


class AdminInvoiceSettingsView(_InvoiceBase):
    """SUPER-ONLY: who bills (the issuer) and who is billed (each tenant's billing details).

    GET returns both. POST saves ONE of them: `{"issuer": {...}}` or
    `{"organisation_id": N, "bill_to_name": ..., "address": ..., "emails": [...]}`. Saving changes
    the NEXT invoice only — every issued invoice holds its own snapshot.
    """

    ISSUER_FIELDS = ('legal_name', 'registration_no', 'address', 'email', 'phone', 'bank_name',
                     'bank_account_name', 'bank_account_no')

    def _payload(self):
        from apps.courses.models import PartnerOrganisation

        from .. import invoicing
        who = invoicing.issuer()
        tenants = []
        for org in PartnerOrganisation.objects.tenants().order_by('name'):
            d = invoicing.billing_details(org)
            tenants.append({'organisation_id': org.id, 'organisation': org.name,
                            'bill_to_name': d.bill_to_name, 'address': d.address,
                            'emails': d.clean_emails(), 'missing': d.missing()})
        return {
            'issuer': {**{f: getattr(who, f) for f in self.ISSUER_FIELDS},
                       'payment_terms_days': who.payment_terms_days,
                       'missing': who.missing()},
            'tenants': tenants,
        }

    def get(self, request):
        admin, is_super, err = self._caller(request)
        if err:
            return err
        if not is_super:
            return self._deny_role()
        return Response(self._payload())

    def post(self, request):
        admin, is_super, err = self._caller(request)
        if err:
            return err
        if not is_super:
            return self._deny_role()
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email

        from apps.courses.models import PartnerOrganisation

        from .. import invoicing
        from ..models import InvoiceIssuer, OrgBillingDetails

        def bad(code):
            return Response({'error': code, 'code': code}, status=status.HTTP_400_BAD_REQUEST)

        data = request.data or {}
        if isinstance(data.get('issuer'), dict):
            src = data['issuer']
            who = invoicing.issuer()
            if who.pk is None:
                who = InvoiceIssuer()
            for f in self.ISSUER_FIELDS:
                if f in src:
                    setattr(who, f, str(src.get(f) or '').strip())
            if who.email:
                try:
                    validate_email(who.email)
                except ValidationError:
                    return bad('bad_email')
            if 'payment_terms_days' in src:
                try:
                    days = int(src.get('payment_terms_days'))
                except (TypeError, ValueError):
                    return bad('bad_terms')
                if not 0 <= days <= 365:
                    return bad('bad_terms')
                who.payment_terms_days = days
            who.updated_by_email = admin.email or ''
            who.save()
            return Response(self._payload())

        org = (PartnerOrganisation.objects.tenants()
               .filter(pk=data.get('organisation_id')).first())
        if org is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        emails = data.get('emails') or []
        if isinstance(emails, str):
            emails = [e for e in (x.strip() for x in emails.replace(';', ',').split(',')) if e]
        if not isinstance(emails, list):
            return bad('bad_email')
        emails = [str(e).strip() for e in emails if str(e).strip()]
        for e in emails:
            try:
                validate_email(e)
            except ValidationError:
                return bad('bad_email')
        details, _ = OrgBillingDetails.objects.get_or_create(organisation=org)
        details.bill_to_name = str(data.get('bill_to_name') or '').strip()
        details.address = str(data.get('address') or '').strip()
        details.emails = list(dict.fromkeys(emails))
        details.updated_by_email = admin.email or ''
        details.save()
        return Response(self._payload())


class AdminOrgBuildHoursView(_AdminBase):
    """Build hours for ONE organisation's modules. Super writes; org_admin reads its own.

    The org side of the owner's 2026-07-27 design. Fenced on `organisation_id` like every other
    org-scoped surface: an org_admin sees only its own hours, and a cross-org id is a **404**,
    never a 403 — consistent with the rest of the admin API, so the route leaks no existence.

    Only a super may RECORD hours: it is a charge against a tenant, and a tenant recording what
    it will be billed for is not a control anyone would accept.
    """

    def get(self, request, org_id):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        is_super = self.has_role(admin, 'super')
        if not (is_super or admin.role == 'org_admin'):
            return self._deny_role()
        if not is_super and admin.owning_organisation_id != int(org_id):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        month = (request.query_params.get('month') or '').strip()
        if month and not _MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)

        from ..models import OrgBuildHours
        qs = OrgBuildHours.objects.filter(organisation_id=org_id)  # org-fence: explicit filter
        if month:
            qs = qs.filter(period_month=month)
        payload = {'organisation_id': int(org_id), 'lines': [{
            'id': r.id, 'period_month': r.period_month, 'module': r.module,
            'hours': str(r.hours), 'basis': r.basis,
        } for r in qs]}

        # The charge is only computed when a month is asked for AND its rates are set. A
        # missing rate is reported as such, never silently rendered as RM0.00.
        if month:
            from .. import platform_cost
            try:
                charge = platform_cost.development_charge(
                    admin.owning_organisation if not is_super else _org_or_none(org_id), month)
                payload['charge'] = {k: (str(v) if v is not None else None)
                                     for k, v in charge.items() if k != 'lines'}
            except platform_cost.RateMissing as exc:
                payload['charge'] = None
                payload['charge_blocked'] = str(exc)
        return Response(payload)

    def post(self, request, org_id):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()

        from decimal import Decimal, InvalidOperation

        from ..models import OrgBuildHours

        month = (request.data.get('period_month') or '').strip()
        if not _MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)
        module = (request.data.get('module') or '').strip()
        basis = (request.data.get('basis') or '').strip()
        if not module:
            return Response({'error': 'module_required', 'code': 'module_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not basis:
            # The whole point of the model: an hours figure with no stated reconstruction is
            # not auditable, and this is the only place that can insist on one.
            return Response({'error': 'basis_required', 'code': 'basis_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            hours = Decimal(str(request.data.get('hours')))
        except (InvalidOperation, TypeError):
            return Response({'error': 'bad_hours', 'code': 'bad_hours'},
                            status=status.HTTP_400_BAD_REQUEST)
        if hours <= 0:
            return Response({'error': 'bad_hours', 'code': 'bad_hours'},
                            status=status.HTTP_400_BAD_REQUEST)

        org = _org_or_none(org_id)
        if org is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        row = OrgBuildHours.objects.create(
            organisation=org, period_month=month, module=module, hours=hours,
            basis=basis, recorded_by_email=(admin.email or ''))
        return Response({'id': row.id, 'period_month': row.period_month,
                         'module': row.module, 'hours': str(row.hours)},
                        status=status.HTTP_201_CREATED)
