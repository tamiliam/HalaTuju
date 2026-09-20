"""Billing and usage v1 — the tenant usage screen, the platform cost ledger and the rate card.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from .. import money

from .base import _AdminBase, _MONTH_RE, _org_or_none


# ── Billing & usage v1 (Sprint 13a) — the super/org_admin usage screen ────────────
# GET /api/v1/admin/scholarship/billing/usage/?month=YYYY-MM. Dual audience:
#   * org_admin — its OWN organisation's metered usage + document-storage snapshot,
#     org-fenced BY CONSTRUCTION (usage.monthly_usage(restrict_org_id=own org) can build
#     no other org and no platform/NULL row);
#   * super — every organisation PLUS the platform (NULL-org) reconciliation row.
# The platform section is SUPER-ONLY (never in an org_admin payload). Ships DARK behind
# BILLING_USAGE_ENABLED — 404-FIRST while the flag is off (no existence leak, same shape
# as the Requests dark ship). Reads through the plain allowlist dict in
# apps.scholarship.usage (no model passthrough); units/tokens ONLY, NO prices in v1.
# The aggregate is deliberately super-global (no tenant scope for a super) — the metering
# UsageEvent.objects query lives in usage.py, not in a raw views_admin query, so the
# org-fence static guard has nothing to police here. Classified in test_org_fence.py.

class AdminBillingUsageView(_AdminBase):
    """Super + org_admin usage readout. The flag darkens the ORG-FACING screen only.

    `BILLING_USAGE_ENABLED` gates what the TENANT sees, not what the platform operator sees
    (owner, 2026-07-26). A super is the person who runs the meter: they need to read the numbers
    before an organisation is shown them, which is precisely the check a dark-until-a-date rollout
    is supposed to allow. So super passes whatever the flag says; org_admin keeps 404-ing until
    the 1 Aug flip, and their experience is byte-identical to before.

    Ordering matters: the flag check sits BEFORE the role check so every non-super role keeps
    getting the same **404** it got while dark (no new existence signal), and only becomes a 403
    once the feature is live for everyone. Unauthenticated callers never reach here — DRF's auth
    layer 401s first.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        is_super = self.has_role(admin, 'super')
        if not is_super and not getattr(settings, 'BILLING_USAGE_ENABLED', False):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        if not (is_super or admin.role == 'org_admin'):
            return self._deny_role()

        month = (request.query_params.get('month') or '').strip()
        if month and not _MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not month:
            # TD-209: LOCALTIME, not now(). `timezone.now()` is an aware UTC instant and
            # `strftime` prints it WITHOUT converting, so this defaulted to the UTC month while
            # every other month computation on this screen is Malaysian — `available_months()`
            # groups with `.dates()` and `monthly_usage` filters on `__year`/`__month`, both of
            # which Postgres evaluates under TIME_ZONE='Asia/Kuala_Lumpur'. The two therefore
            # disagreed for the eight hours between Malaysian midnight and 08:00 on the 1st, and
            # the page opened on a month the data had already left. No figure was ever wrong; the
            # default was. A test pins the two computations to the same clock.
            month = timezone.localtime().strftime('%Y-%m')

        from .. import usage
        if is_super:
            # super: every organisation + the platform (NULL-org) reconciliation row.
            payload = usage.monthly_usage(month, include_platform=True)
        else:
            # org_admin: its OWN organisation only — fenced by construction (no platform,
            # no other org can appear). A misconfigured org_admin with no org sees nothing.
            payload = usage.monthly_usage(month, restrict_org_id=admin.owning_organisation_id)

        # ⚠ **THE JOB → MODEL LIST IS SUPER-ONLY, and that is the same call as the platform row
        # above.** Which AI version a job is set to is a PLATFORM fact: every organisation runs
        # the same models, and a tenant cannot change one (owner, 2026-09-11 — see
        # `docs/decisions.md`). Showing a tenant a list they can only look at would be furniture.
        # What a tenant DOES get is the per-model split of their own usage, which is theirs.
        #
        # Read-only, and cheap: a few `getattr`s over Django settings plus three lazy imports.
        # It RESOLVES rather than remembers, so it cannot disagree with the engine.
        if is_super:
            from halatuju import ai_registry
            payload['ai_jobs'] = ai_registry.snapshot()
            payload['ai_models_in_use'] = ai_registry.models_in_use()
        return Response(payload)


class AdminPlatformCostsView(_AdminBase):
    """SUPER-ONLY: what the platform PAID this month, and what each tenant is charged.

    The gap the owner found on 2026-09-11: the ledger, the BigQuery sync, the reconciliation
    maths and the rates endpoint were all built in July 2026 and then starved. Nothing fed the
    ledger after June and **no endpoint ever read it**, so real invoices — GCP, Supabase,
    Workspace, Twilio — reached no screen at all.

    **Super-only, 403 not 404**, matching `AdminBillingRatesView`: what the platform pays and
    what margin sits on top is a commercial disclosure, but there is nothing to hide about the
    route existing. Unlike the usage screen there is no dark-ship flag — this never had one.

    ⚠ The payload carries `month_totals`' truthfulness flags verbatim — `entered_sources`,
    `is_complete`, `period_caveats` — and the screen renders them. **A total that mixes measured
    and hand-typed figures without saying so is not an audit** (the module's own words). That is
    the reason this calls `reconcile()` rather than re-summing rows in the view: a second summing
    would be a second place for those flags to be forgotten.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()

        month = (request.query_params.get('month') or '').strip()
        if month and not _MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not month:
            # TD-209: localtime, never `timezone.now()`. See AdminBillingUsageView's note —
            # the same eight-hour window would open this page on the wrong month.
            month = timezone.localtime().strftime('%Y-%m')

        from apps.courses.models import PartnerOrganisation

        from .. import platform_cost
        from ..models import PlatformCost

        costs = platform_cost.reconcile(month)

        def _money(v):
            # ⚠ `None` SURVIVES, and nothing is quantised. This payload distinguishes "no figure
            # entered for that source yet" from "the figure is zero", and the only job here is to
            # stop DRF rendering a bare `Decimal` inside a nested dict as a float.
            return money.format_money(v, blank=None, blank_when=money.BLANK_NONE,
                                      quantize=False, coerce=False)

        payload = {
            'month': month,
            # Every month the ledger holds anything for, newest first — the picker's options.
            # Read from the LEDGER, not generated from a range: a month with no rows is a month
            # nobody has entered yet, and offering it would look like "we paid nothing".
            'months': list(PlatformCost.objects.order_by('-period_month')
                           .values_list('period_month', flat=True).distinct()),
            'costs': {
                'lines': costs['lines'],
                'total_myr': _money(costs['total_myr']),
                'attributable_myr': _money(costs['attributable_myr']),
                'platform_myr': _money(costs['platform_myr']),
                'development_myr': _money(costs['development_myr']),
                'tax_myr': _money(costs['tax_myr']),
                'by_source': {k: _money(v) for k, v in costs['by_source'].items()},
                'entered_sources': costs['entered_sources'],
                'extracted_sources': costs['extracted_sources'],
                'is_complete': costs['is_complete'],
                'unconverted': [{**u, 'amount_original': _money(u['amount_original'])}
                                for u in costs['unconverted']],
                'period_caveats': costs['period_caveats'],
                'metered_events': costs['metered_events'],
                'metered_org_null': costs['metered_org_null'],
                'metered_org_null_pct': costs['metered_org_null_pct'],
            },
            'charges': [],
            # ⚠ NOT filtered to the month being viewed. Outstanding work is outstanding whatever
            # month you happen to be looking at, and each row carries the month IT belongs to —
            # `worked_month` — so the reader sees everything unbilled and records each against
            # the month we actually worked.
            'unbilled_requests': [{**u,
                                   'hours': _money(u['hours']),
                                   'worked_on': u['worked_on'].isoformat()}
                                  for u in platform_cost.unbilled_request_hours()],
        }

        # ⚠ `.tenants()`, never `.filter(is_active=True)`. This table is dual-role: ten rows on
        # production, exactly one of them a tenant. The plain queryset would put a bill against
        # nine schools and NGOs that have never been customers.
        for org in PartnerOrganisation.objects.tenants().order_by('name'):
            c = platform_cost.charge_for(org, month)
            payload['charges'].append({
                'organisation_id': org.id,
                'organisation': org.name,
                'lines': [{**ln,
                           'hours': _money(ln.get('hours')),
                           'rate_myr': _money(ln.get('rate_myr')),
                           'margin_pct': _money(ln.get('margin_pct')),
                           'cost_myr': _money(ln.get('cost_myr')),
                           'tool_cost_myr': _money(ln.get('tool_cost_myr')),
                           'share_pct': _money(ln.get('share_pct')),
                           'amount_myr': _money(ln.get('amount_myr')),
                           'billed_rate_myr': _money(ln.get('billed_rate_myr')),
                           # ⚠ `amount_myr` is money inside a nested dict — DRF renders a bare
                           # Decimal there as a FLOAT (the sponsor-card lesson), so it is
                           # stringified here like every other figure on this payload.
                           'detail': [{**d, 'hours': _money(d['hours']),
                                       'amount_myr': _money(d.get('amount_myr'))}
                                      for d in ln.get('detail', [])]}
                          for ln in c['lines']],
                'subtotal_myr': _money(c['subtotal_myr']),
                'discount_pct': _money(c['discount_pct']),
                'discount_myr': _money(c['discount_myr']),
                'discount_reason': c['discount_reason'],
                'discount_set_by': c['discount_set_by'],
                'charged_myr': _money(c['charged_myr']),
                'blocked': c['blocked'],
            })
        return Response(payload)

    def post(self, request):
        """Record a discount for one organisation and one month.

        The owner's July instruction — *"we do not bill anything for July. 100% discount. But
        show the values."* A row here is what makes that a decision rather than a gap.

        `reason` is REQUIRED and refused when blank, exactly as `OrgBuildHours.basis` is: a
        waived month with no stated reason is indistinguishable from a bug, and this endpoint
        is the only place that can insist.
        """
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()

        from decimal import Decimal, InvalidOperation

        from ..models import OrgBillingAdjustment

        month = (request.data.get('period_month') or '').strip()
        if not _MONTH_RE.match(month):
            return Response({'error': 'bad_month', 'code': 'bad_month'},
                            status=status.HTTP_400_BAD_REQUEST)
        org = _org_or_none(request.data.get('organisation_id'))
        if org is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            pct = Decimal(str(request.data.get('discount_pct')))
        except (InvalidOperation, TypeError):
            return Response({'error': 'bad_value', 'code': 'bad_value'},
                            status=status.HTTP_400_BAD_REQUEST)
        if pct < 0 or pct > 100:
            return Response({'error': 'bad_value', 'code': 'bad_value'},
                            status=status.HTTP_400_BAD_REQUEST)
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'error': 'reason_required', 'code': 'reason_required'},
                            status=status.HTTP_400_BAD_REQUEST)

        row, _created = OrgBillingAdjustment.objects.update_or_create(
            organisation=org, period_month=month,
            defaults={'discount_pct': pct, 'reason': reason,
                      'set_by_email': (admin.email or '')})
        return Response({'id': row.id, 'organisation_id': org.id,
                         'period_month': row.period_month,
                         'discount_pct': str(row.discount_pct),
                         'reason': row.reason},
                        status=status.HTTP_201_CREATED)


class AdminBillingRatesView(_AdminBase):
    """SUPER-ONLY: read + set the conversion rate and per-category margins.

    Owner design 2026-07-27: the rate and margins are PLATFORM-side editable values, while
    hours sit on the org side. This is the platform side.

    **Super-only, with no flag and no org_admin path — on purpose.** These numbers decide what
    every tenant is charged. A tenant being able to read (let alone set) the margin applied to
    them is a commercial disclosure, not a feature; org_admin gets a **403**, not a 404, because
    unlike the dark usage screen there is nothing to hide about this route's existence — only
    about its contents.

    POST never updates in place. It writes a NEW effective-dated row, so changing a rate cannot
    retroactively re-price a month that has already been billed. The history IS the audit trail.
    """

    def get(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()

        from ..models import BillingRate
        rows = BillingRate.objects.all()   # org-fence: platform-level config, no tenant data
        return Response({'rates': [{
            'id': r.id,
            'category': r.category,
            'kind': r.kind,
            'value': str(r.value),
            'effective_from': r.effective_from.isoformat(),
            'updated_by_email': r.updated_by_email,
            'note': r.note,
        } for r in rows]})

    def post(self, request):
        admin = self.get_admin(request)
        if not admin:
            return self._deny()
        if not self.has_role(admin, 'super'):
            return self._deny_role()

        from datetime import date
        from decimal import Decimal, InvalidOperation

        from ..models import BillingRate

        category = (request.data.get('category') or '').strip()
        kind = (request.data.get('kind') or '').strip()
        if category not in dict(BillingRate.CATEGORY_CHOICES):
            return Response({'error': 'bad_category', 'code': 'bad_category'},
                            status=status.HTTP_400_BAD_REQUEST)
        if kind not in dict(BillingRate.KIND_CHOICES):
            return Response({'error': 'bad_kind', 'code': 'bad_kind'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            value = Decimal(str(request.data.get('value')))
        except (InvalidOperation, TypeError):
            return Response({'error': 'bad_value', 'code': 'bad_value'},
                            status=status.HTTP_400_BAD_REQUEST)
        if value < 0:
            # A negative margin or rate is almost certainly a typo, and it would silently
            # produce a credit note rather than an invoice.
            return Response({'error': 'negative_value', 'code': 'negative_value'},
                            status=status.HTTP_400_BAD_REQUEST)

        raw_from = (request.data.get('effective_from') or '').strip()
        try:
            effective_from = (date.fromisoformat(raw_from) if raw_from
                              else timezone.now().date().replace(day=1))
        except ValueError:
            return Response({'error': 'bad_effective_from', 'code': 'bad_effective_from'},
                            status=status.HTTP_400_BAD_REQUEST)

        row, _created = BillingRate.objects.update_or_create(
            category=category, kind=kind, effective_from=effective_from,
            defaults={'value': value,
                      'updated_by_email': (admin.email or ''),
                      'note': (request.data.get('note') or '')})
        return Response({'id': row.id, 'category': row.category, 'kind': row.kind,
                         'value': str(row.value),
                         'effective_from': row.effective_from.isoformat()},
                        status=status.HTTP_201_CREATED)
