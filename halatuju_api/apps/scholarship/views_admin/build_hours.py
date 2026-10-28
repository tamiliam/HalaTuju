"""Build hours for ONE organisation's modules — the org side of the 2026-07-27 billing design.

Moved VERBATIM out of `views_admin/invoices.py` on 2026-10-28. Moves only: not a line of the view
changed, so the fence, the roles and the payload are the ones already in production. The reason is
size — `invoices.py` reached 591 of the 600-line standard while the back-issue sprint was adding to
it, and build hours were never invoices: they are what an invoice's development line is BUILT from.

Part of the `views_admin` package; re-exported from `views_admin/__init__.py`, so `urls.py` and
every importer are unchanged.
"""
from rest_framework import status
from rest_framework.response import Response

from .base import _AdminBase, _MONTH_RE, _org_or_none


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
