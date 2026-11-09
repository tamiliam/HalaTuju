"""`GET admin/scholarship/billing/overdue/` — the console's red overdue banner (staff nudges, sprint 3).

Brief `docs/plans/2026-11-08-staff-nudges.md`, decisions 5 and 6. Answers `{'overdue': None | {...}}`,
the caller's OWN organisation's summary from `invoice_overdue.org_summary` (the ONE rule).

⚠ ITS OWN SMALL DOOR so `views_admin/invoices.py` does not grow, but the SAME gate: `_InvoiceBase.
_caller` (`surface_gates.may_read_invoices`): a non-super gets the dark 404 while billing is off and
a 403 unless it may read invoices — the people who can open the billing page are exactly the people
the banner is for. A super has no organisation of its own and answers `None` (decision 6: not the
super). The organisation is the caller's `owning_organisation`, never a parameter, so no request can
name another tenant's bill; only SENT invoices count, as on the tenant's billing page.

Part of the `views_admin` package; re-exported from `views_admin/__init__.py`.
"""
from rest_framework.response import Response

from .invoices import _InvoiceBase


class AdminInvoiceOverdueView(_InvoiceBase):
    """The oldest overdue invoice of the caller's own organisation, and how many more there are."""

    def get(self, request):
        admin, is_super, err = self._caller(request)
        if err:
            return err
        from .. import invoice_overdue
        if is_super:
            return Response({'overdue': None})
        return Response({'overdue': invoice_overdue.org_summary(admin.owning_organisation_id)})
