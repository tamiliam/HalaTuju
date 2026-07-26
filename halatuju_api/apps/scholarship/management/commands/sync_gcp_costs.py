"""Pull one month of GCP cost, by SKU, into the platform cost ledger.

    python manage.py sync_gcp_costs --month 2026-06            # report only
    python manage.py sync_gcp_costs --month 2026-06 --apply    # write the ledger

Reads the BigQuery billing export that has been enabled since 2026-03-20. Idempotent: rows
UPSERT on (period_month, source, service, sku), so re-running a month corrects it rather than
doubling it — which matters because a month is not final until Google closes it.

**Scoped to the HalaTuju project by default.** The export covers the whole billing account and
other products sit under it (Lentera billed RM0.30 in June). The owner's ruling of 2026-07-26
is that HalaTuju carries ~99.7% of GCP — verified against the June bill — but the filter stays
because the filter is what KEEPS that true if a sibling product ever grows.

Auth: Application Default Credentials, i.e. whatever `gcloud auth` the operator holds. This is
an owner-run reporting tool, not a request path — it never runs on the service.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import platform_cost
from apps.scholarship.models import PlatformCost

DEFAULT_PROJECT = 'gen-lang-client-0871147736'
BILLING_TABLE = ('billing_export.gcp_billing_export_v1_01D44F_1CA89B_18AB53')


class Command(BaseCommand):
    help = 'Sync one month of GCP cost (by SKU) into the platform cost ledger.'

    def add_arguments(self, parser):
        parser.add_argument('--month', required=True,
                            help="Billing month, 'YYYY-MM' (e.g. 2026-06).")
        parser.add_argument('--project', default=DEFAULT_PROJECT,
                            help='GCP project id to scope to. Pass "" for the whole billing '
                                 'account — which mixes other products in, so do it only to '
                                 'investigate, never to feed the ledger.')
        parser.add_argument('--apply', action='store_true',
                            help='Write to the ledger. Without it this only reports.')

    def handle(self, *args, **opts):
        month = (opts['month'] or '').strip()
        if len(month) != 7 or month[4] != '-':
            raise CommandError("--month must look like 'YYYY-MM'")
        project = (opts['project'] or '').strip()
        apply = opts['apply']

        rows = self._query(month, project)
        if not rows:
            self.stdout.write(self.style.WARNING(
                f'No billing rows for {month}'
                + (f' in project {project}' if project else '')
                + '. Either the month has not been exported yet, or the filter is wrong — '
                  'an empty result is NOT the same as a zero bill.'))
            return

        total = Decimal('0.00')
        attributable = Decimal('0.00')
        tax = Decimal('0.00')
        written = 0
        self.stdout.write(f'{"service":26} {"sku":46} {"MYR":>8}  tenant?')
        for service, sku, amount in rows:
            is_attr = platform_cost.classify_sku(service, sku)
            is_tax = platform_cost.is_tax(service, sku)
            total += amount
            # Three mutually exclusive buckets, matching platform_cost.month_totals exactly —
            # the same figure must not read differently in the sync and in the report.
            if is_tax:
                tax += amount
            elif is_attr:
                attributable += amount
            flag = 'tax' if is_tax else ('TENANT' if is_attr else 'platform')
            self.stdout.write(f'{service[:25]:26} {sku[:45]:46} {amount:8.2f}  {flag}')

            if apply:
                PlatformCost.objects.update_or_create(
                    period_month=month, source='gcp', service=service, sku=sku,
                    defaults={
                        'amount_myr': amount,
                        'attributable': is_attr,
                        'provenance': 'measured',
                        'note': (f'BigQuery billing export, project={project or "ALL"}. '
                                 f'Synced by sync_gcp_costs.'),
                    })
                written += 1

        platform = total - attributable - tax
        pct = f' ({attributable / total * 100:.0f}%)' if total else ''
        self.stdout.write('')
        self.stdout.write(f'TOTAL           RM{total:,.2f}')
        self.stdout.write(f'  tenant-driven RM{attributable:,.2f}{pct}')
        self.stdout.write(f'  platform      RM{platform:,.2f}')
        self.stdout.write(f'  tax           RM{tax:,.2f}')
        if apply:
            self.stdout.write(self.style.SUCCESS(f'\nWrote {written} ledger lines for {month}.'))
        else:
            # Plain ASCII: this runs in a Windows console whose default codepage mangles
            # an em dash into a replacement character.
            self.stdout.write(self.style.WARNING(
                '\nReport only - re-run with --apply to write.'))

    def _query(self, month, project):
        """Return [(service, sku, Decimal amount)] for the month, largest first."""
        try:
            from google.cloud import bigquery
        except ImportError as exc:      # pragma: no cover - environment-dependent
            raise CommandError(
                'google-cloud-bigquery is not installed in this environment. This command is '
                'an owner-run reporting tool; install it locally rather than adding it to the '
                'service image.') from exc

        where = ['DATE(usage_start_time) BETWEEN @start AND @end']
        params = [
            bigquery.ScalarQueryParameter('start', 'DATE', f'{month}-01'),
            bigquery.ScalarQueryParameter('end', 'DATE', _month_end(month)),
        ]
        if project:
            where.append('project.id = @project')
            params.append(bigquery.ScalarQueryParameter('project', 'STRING', project))

        sql = f"""
            SELECT service.description AS service,
                   sku.description     AS sku,
                   ROUND(SUM(cost), 2) AS myr
            FROM `{BILLING_TABLE}`
            WHERE {' AND '.join(where)}
            GROUP BY 1, 2
            HAVING myr > 0.005
            ORDER BY 3 DESC
        """
        client = bigquery.Client(project=DEFAULT_PROJECT)
        job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
        return [(r['service'] or '', r['sku'] or '', Decimal(str(r['myr'])))
                for r in job.result()]


def _month_end(month):
    """Last day of 'YYYY-MM'. Cheap and exact — no calendar library needed."""
    year, mon = (int(x) for x in month.split('-'))
    if mon == 12:
        year, mon = year + 1, 1
    else:
        mon += 1
    from datetime import date, timedelta
    return (date(year, mon, 1) - timedelta(days=1)).isoformat()
