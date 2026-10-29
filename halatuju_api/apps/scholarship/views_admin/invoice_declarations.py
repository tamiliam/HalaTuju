"""Payment declarations: the tenant declares, the owner confirms or cannot find it (2026-10-29).

⚠ **ITS OWN DOOR, ON PURPOSE.** `AdminInvoiceActionView` denies every non-super at the top, which
is right for `send`, `void` and `receipt` — those are the platform's acts. Declaring is the
TENANT'S act, and the only one in this whole space an org_admin may perform. Bolting it onto the
super-only view would mean loosening that view's gate for one branch, which is exactly how a fence
stops being a fence. Two doors, two gates, each reading as what it is.

Part of the `views_admin` package. Every name below is re-exported from `views_admin/__init__.py`.
"""
from rest_framework import status
from rest_framework.response import Response

from .invoices import _InvoiceBase, _invoice_payload


class AdminInvoiceDeclarationView(_InvoiceBase):
    """`declare` (the tenant), `confirm` and `reject` (the owner), on one invoice.

    The `_InvoiceBase` fence is unchanged and does the work: an org_admin reaches only its own
    organisation's invoices, and only those that have been SENT. A tenant naming another tenant's
    invoice gets the same 404 as one that does not exist.
    """

    def post(self, request, pk, action):
        admin, is_super, err = self._caller(request)
        if err:
            return err
        from .. import invoicing, payment_declarations
        from ..models import InvoicePaymentDeclaration

        inv = self._visible_invoices(admin, is_super).filter(pk=pk).first()
        if inv is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)
        # A JSON ARRAY body has no `.get`, so reading one off `request.data` is a 500 — the fault
        # an adversarial review found on the bill-to endpoint. Same guard here.
        body = request.data if isinstance(request.data, dict) else {}
        by = admin.email or ''
        try:
            if action == 'declare':
                # ⚠ THE TENANT'S ACT, AND ONLY THE TENANT'S. A super must not declare on a
                # customer's behalf: it would put words in their mouth on a money document, and
                # the super already has the honest route — look at the bank, record the receipt.
                if is_super:
                    return self._deny_role()
                payment_declarations.declare_payment(
                    inv,
                    paid_on=(body.get('paid_on') or '').strip(),
                    reference=body.get('reference'),
                    declared_by_email=by)
            elif action in ('confirm', 'reject'):
                if not is_super:
                    return self._deny_role()
                # org-fence: the declaration is reached THROUGH the invoice already resolved
                # above, never by its own id, so a bare id cannot cross organisations.
                declaration = (InvoicePaymentDeclaration.objects
                               .filter(invoice=inv, pk=self._digits(body.get('declaration_id')))
                               .first())
                if declaration is None:
                    return Response({'error': 'not_found', 'code': 'not_found'},
                                    status=status.HTTP_404_NOT_FOUND)
                if action == 'confirm':
                    payment_declarations.confirm_payment(
                        declaration,
                        amount_myr=body.get('amount_myr'),
                        received_on=(body.get('received_on') or '').strip() or None,
                        reference=body.get('reference') or '',
                        method=(body.get('method') or 'bank_transfer').strip(),
                        note=body.get('note') or '',
                        confirmed_by_email=by)
                else:
                    payment_declarations.reject_declaration(
                        declaration, reason=body.get('reason'), rejected_by_email=by)
            else:
                return Response({'error': 'not_found', 'code': 'not_found'},
                                status=status.HTTP_404_NOT_FOUND)
        except invoicing.InvoicingError as exc:
            return self._error(exc)
        inv = self._visible_invoices(admin, is_super).get(pk=pk)
        return Response(_invoice_payload(inv, for_super=is_super))

    @staticmethod
    def _digits(raw):
        """An id, or -1 for anything that is not one — which matches no row.

        The rule itself moved to `base._id_or_no_match` on 2026-10-29, when the billing
        corrections endpoint needed the same check: two spellings of "is this an id?" eventually
        disagree about `True`. This stays as the name this class's callers already use.
        """
        from .base import _id_or_no_match
        return _id_or_no_match(raw)
