"""Tenant invoices and receipts — moved verbatim from `views_admin.py` at H11.

Build hours left for `build_hours.py` on 2026-10-28, moves only: this file had reached 591 of the
600-line standard, and hours were never invoices — they are what a development line is BUILT from.

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


def _declaration(d):
    """ONE payment declaration, for either audience. An allowlist, like its invoice.

    `state` is derived and sent as a word rather than three timestamps, because every reader of
    this payload asks the same question — open, confirmed or not matched? — and three nullable
    stamps is an invitation to answer it three different ways on three screens.
    """
    return {
        'id': d.id,
        'paid_on': d.paid_on.isoformat(),
        'reference': d.reference,
        'declared_at': d.declared_at.isoformat() if d.declared_at else None,
        'declared_by_email': d.declared_by_email,
        'state': 'open' if d.is_open else ('confirmed' if d.confirmed_at else 'rejected'),
        'reject_reason': d.reject_reason,
        # The receipt the owner raised on confirming. The NUMBER, not the id: it is what both
        # sides quote at each other, and the receipt row itself is already in `receipts`.
        'receipt_number': d.receipt.number if d.receipt_id else '',
    }


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
        # ⚠ FROZEN, and read from the SNAPSHOT, never from the live correction rows. A document
        # already sent must keep saying what it said. Both audiences get it: a tenant charged for
        # an earlier month's mistake is entitled to read why, in the same words we wrote.
        'corrections_myr': _invoice_money(inv.corrections_myr),
        'corrections': [{
            'amount_myr': str(c.get('amount_myr') or '0.00'),
            'reason': str(c.get('reason') or ''),
            'corrects_invoice': str(c.get('corrects_invoice') or ''),
        } for c in (inv.corrections_snapshot or [])],
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
            # ⚠ A BOOLEAN, not the parent's id. The screen only ever needs to know whether to
            # indent a row, and `position` already puts a child straight after its parent. Sending
            # the id would invite the screen to rebuild a tree it has no reason to hold, and the
            # ids are database keys a tenant-facing payload has no business carrying.
            'is_sub_item': ln.parent_id is not None,
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
            # ⚠ WHETHER IT REACHED THE CUSTOMER, for BOTH audiences. Null means it was not sent —
            # stated, never assumed. The recipient LIST is super-only, like `sent_to` above: the
            # tenant knows its own inboxes, and the owner is the one who needs to check them.
            'emailed_at': r.emailed_at.isoformat() if r.emailed_at else None,
            **({'emailed_to': list(r.emailed_to or [])} if for_super else {}),
        } for r in receipts],
        # ⚠ BOTH AUDIENCES SEE THESE, and that is the point. The tenant needs to know its claim
        # was received and, if it was not matched, why; the owner needs something to check against
        # the statement. Nothing here is money — see `payment_declarations` for why a claim must
        # never look like a receipt. No amount is carried because none is ever asked for.
        'payment_declarations': [_declaration(d) for d in inv.payment_declarations.all()],
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
        # ⚠ `payment_declarations` IS PREFETCHED BECAUSE `Invoice.status` READS IT. Without it,
        # rendering a list of invoices fires one extra query per row just to work out the chip.
        # `receipt` comes along so `_declaration` can print its number without another query each.
        qs = Invoice.objects.select_related('organisation', 'replaces').prefetch_related(  # org-fence: narrowed below for every non-super
            'lines', 'receipts', 'payment_declarations__receipt')
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
                # The CODE, so a "fix this" link can open THAT organisation's settings rather than
                # landing on a picker. One tenant today; the link is wrong the day there are two.
                'organisation_code': org.code,
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

        # A JSON ARRAY body has no `.get`, so reading one off `request.data` is a 500 (the fault an
        # adversarial review found on the bill-to endpoint on 2026-10-28). Same guard here.
        body = request.data if isinstance(request.data, dict) else {}
        month = (body.get('period_month') or '').strip()
        if not invoicing.MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)
        # ⚠ DIGITS ONLY, not `int(...)`. `filter(pk='abc')` raises — a 500 — so the id must be
        # refused before the query; but `int()` is the wrong refusal, because it ACCEPTS things
        # that are not this id: `int(1.5)` is 1 and `int(True)` is 1, so a float or a boolean
        # would quietly issue a bill against organisation 1. A money document does not get to
        # guess which organisation was meant.
        raw = body.get('organisation_id')
        text = '' if raw is None else str(raw).strip()
        if isinstance(raw, bool) or not text.isdigit():
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        org = PartnerOrganisation.objects.filter(pk=int(text)).first()
        if org is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            inv = invoicing.issue_invoice(
                org, month, issued_by_email=admin.email or '',
                override_reason=body.get('override_reason') or '',
                # Blank = today, the ordinary case. A value BACK-DATES the printed issue date and
                # the due date with it; `invoicing.issue_date_for` holds the bounds.
                issued_on=str(body.get('issued_on') or '').strip())
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
                receipt = invoicing.record_receipt(
                    inv,
                    received_on=(request.data.get('received_on') or '').strip(),
                    amount_myr=request.data.get('amount_myr'),
                    reference=request.data.get('reference'),
                    method=(request.data.get('method') or 'bank_transfer').strip(),
                    note=request.data.get('note') or '',
                    recorded_by_email=by)
                # AFTER the money is recorded, never before — see `invoicing.email_receipt`. The
                # result is not checked here on purpose: the receipt exists either way, and
                # whether it went is read off `emailed_at` in the payload below.
                invoicing.email_receipt(receipt)
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


class AdminInvoiceIssuerView(_InvoiceBase):
    """SUPER-ONLY, PLATFORM-WIDE: who is billing — the block printed atop every invoice.

    Lives beside the rates (Platform -> Billing) because its SCOPE is the platform: there is exactly
    one issuer row for every organisation that will ever be billed, and what it says is commercial.
    It used to sit on Billing & usage, grouped by the task you were doing (issuing) rather than by
    the scope it has — which is why the owner went hunting for a bank field on a page about usage
    (2026-10-28). Who is BILLED moved the other way, to that organisation's own settings.

    Saving changes the NEXT invoice only: every issued invoice holds its own frozen snapshot.
    """

    ISSUER_FIELDS = ('legal_name', 'registration_no', 'address', 'email', 'phone', 'bank_name',
                     'bank_account_name', 'bank_account_no')

    def _payload(self):
        from .. import invoicing
        who = invoicing.issuer()
        return {'issuer': {**{f: getattr(who, f) for f in self.ISSUER_FIELDS},
                           'payment_terms_days': who.payment_terms_days,
                           'missing': who.missing()}}

    def _super_only(self, request):
        admin, is_super, err = self._caller(request)
        if err:
            return None, err
        if not is_super:
            return None, self._deny_role()
        return admin, None

    def get(self, request):
        admin, err = self._super_only(request)
        return err or Response(self._payload())

    def post(self, request):
        admin, err = self._super_only(request)
        if err:
            return err
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email

        from .. import invoicing
        from ..models import InvoiceIssuer

        def bad(code):
            return Response({'error': code, 'code': code}, status=status.HTTP_400_BAD_REQUEST)

        src = request.data.get('issuer')
        if not isinstance(src, dict):
            return bad('bad_issuer')
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


class AdminOrgBillingDetailsView(_InvoiceBase):
    """Where ONE organisation's invoices are addressed and sent. Super, or that org's own org_admin.

    WARNING - **THE TENANT MAY WRITE THIS, AND THAT IS A DELIBERATE LINE** (owner, 2026-10-28). The
    sibling `AdminOrgBuildHoursView` says only a super may record hours, because *"a tenant
    recording what it will be billed for is not a control anyone would accept"* — and that line is
    kept. This is the other side of it: not what the tenant is billed FOR, nor what it is billed AT,
    but WHERE the bill is addressed and which inbox it reaches. That is their own name and staff.

    Three things make it safe, and all three are structural rather than trusted:
      * the debt is recorded against `organisation_id`, which no tenant can reach from here;
      * an issued invoice carries a FROZEN `bill_to_snapshot`, so editing this cannot alter a bill
        already issued or sent — only the next one;
      * a super reads the printed name at Send, the one moment a bill leaves the building.

    WARNING - "who may act" and "who may see" look identical at a call site and answer different
    questions (People actions, 2026-09-09). This is a who-may-ACT surface: `admin`, `finance`, `qc`
    and `reviewer` are refused even though some of them may READ the organisation page this tab
    sits on. `_InvoiceBase._caller` is the one place that decides it.

    Cross-organisation is a **404**, never a 403 — consistent with every sibling, so the route
    leaks no existence.
    """

    #: How many inboxes one organisation may list. See the comment at the check.
    MAX_EMAILS = 10

    #: ⚠ THE ROLE GATE IS `_InvoiceBase._caller`, WHICH ADMITS ONLY `super` AND `org_admin`.
    #: This class carried its own `ROLES = ('org_admin',)` check until a bite-check deleted that
    #: check and nothing failed: `_caller` had already refused every other role one call earlier.
    #: A second guard that cannot fire is worse than none, because its presence invites the next
    #: reader to trust it and to copy the pattern somewhere it IS the only gate (this codebase's
    #: dead-safeguard lesson, twice in September). The behaviour is unchanged and still proven
    #: through the door by `test_who_may_act_is_not_who_may_see`.

    def _org(self, request):
        """-> (admin, organisation, error). The organisation this caller may act on.

        Keyed on `?organisation=<code>`, NOT an id, because this is the third tab of ORGANISATION ->
        Settings and its two siblings (Colours, Configuration) resolve exactly this way — a reader
        of the page should recognise the third from the first. Mirrors
        `AdminOrganisationConfigurationView._organisation_for`, which in turn mirrors
        `AdminOrganisationThemeView`; three copies is the signal to unify them (TD raised).

        With no code: the sole tenant, or `organisation_required` naming the choices. Never a
        silent pick — guessing which organisation a bill is addressed to is the one thing this
        endpoint must not do.
        """
        from apps.courses.models import PartnerOrganisation

        admin, is_super, err = self._caller(request)
        if err:
            return None, None, err

        # ⚠ `request.data` is whatever JSON arrived — a LIST for `[1,2]`, on which `.get`
        # raises and the client sees a 500 instead of a refusal. Read it only when it is an object.
        body = request.data if isinstance(request.data, dict) else {}
        code = (request.query_params.get('organisation')
                or body.get('organisation') or '').strip()
        qs = PartnerOrganisation.objects.tenants().filter(is_active=True)
        if not is_super:
            # org-fence: a tenant's queryset is narrowed to its OWN organisation before the code is
            # even read, so a code naming another tenant finds nothing and answers 404.
            qs = qs.filter(id=admin.owning_organisation_id) if admin.owning_organisation_id else qs.none()
        not_found = Response({'error': 'not_found', 'code': 'not_found'},
                             status=status.HTTP_404_NOT_FOUND)
        if code:
            org = qs.filter(code=code).first()
            return (None, None, not_found) if org is None else (admin, org, None)
        orgs = list(qs.order_by('code')[:2])
        if not orgs:
            return None, None, not_found
        if len(orgs) > 1:
            return None, None, Response(
                {'error': 'organisation_required', 'code': 'organisation_required',
                 'organisations': [o.code for o in qs.order_by('code')]},
                status=status.HTTP_400_BAD_REQUEST)
        return admin, orgs[0], None

    def _payload(self, org):
        from .. import invoicing
        d = invoicing.billing_details(org)
        # The CODE travels back so a save names the same organisation the read resolved —
        # never a second guess from an empty query string.
        return {'organisation_id': org.id, 'organisation': org.name,
                'organisation_code': org.code,
                'bill_to_name': d.bill_to_name, 'address': d.address,
                'emails': d.clean_emails(), 'missing': d.missing()}

    def get(self, request):
        admin, org, err = self._org(request)
        return err or Response(self._payload(org))

    def post(self, request):
        admin, org, err = self._org(request)
        if err:
            return err
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email

        from ..models import OrgBillingDetails

        def bad():
            return Response({'error': 'bad_email', 'code': 'bad_email'},
                            status=status.HTTP_400_BAD_REQUEST)

        data = request.data if isinstance(request.data, dict) else {}
        emails = data.get('emails') or []
        if isinstance(emails, str):
            emails = [e for e in (x.strip() for x in emails.replace(';', ',').split(',')) if e]
        if not isinstance(emails, list):
            return bad()
        emails = [str(e).strip() for e in emails if str(e).strip()]
        # ⚠ A CAP, because the sending quota is the PLATFORM's, not this tenant's. Every address
        # here gets a copy of every invoice, and Brevo's allowance is shared across the whole
        # platform — so an unbounded list is one tenant able to spend everyone else's mail.
        # Ten is far above any real finance team and far below anything that costs us a day.
        if len(emails) > self.MAX_EMAILS:
            return Response({'error': 'too_many_emails', 'code': 'too_many_emails',
                             'limit': self.MAX_EMAILS}, status=status.HTTP_400_BAD_REQUEST)
        for e in emails:
            try:
                validate_email(e)
            except ValidationError:
                return bad()
        name = str(data.get('bill_to_name') or '').strip()
        # `bill_to_name` is a 200-char column; a longer value is a database error, which reaches
        # the caller as a 500. Refuse it in words rather than crashing on a save.
        if len(name) > OrgBillingDetails._meta.get_field('bill_to_name').max_length:
            return Response({'error': 'name_too_long', 'code': 'name_too_long'},
                            status=status.HTTP_400_BAD_REQUEST)
        # org-fence: keyed on the organisation resolved above, never on anything in the body.
        details, _ = OrgBillingDetails.objects.get_or_create(organisation=org)
        details.bill_to_name = name
        details.address = str(data.get('address') or '').strip()
        details.emails = list(dict.fromkeys(emails))
        details.updated_by_email = admin.email or ''
        details.save()
        return Response(self._payload(org))
