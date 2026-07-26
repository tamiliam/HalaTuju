"""Record a platform cost line BY HAND, and show the month's reconciliation.

    # enter a figure read off an invoice
    python manage.py record_platform_cost --month 2026-06 --source supabase \\
        --service "Pro plan" --amount 118.00 --note "Invoice #8, USD25 @ 4.72"

    # what does the ledger say for a month, and does the meter agree?
    python manage.py record_platform_cost --month 2026-06 --report

Why this exists: Supabase has **no supported billing API**. The Management API returns the
plan (`pro`) and nothing else; the figures live in a dashboard and a PDF. So one half of the
ledger is measured (GCP, via `sync_gcp_costs`) and one half is typed by a human — and every
row this command writes is stamped ``provenance='entered'`` so a later reader can tell which
is which. A reconciliation that mixes them silently is not an audit.

Owner ruling (2026-07-26): Supabase cost is attributed **100% to HalaTuju**. The Pro
subscription is org-level and covers three projects, but the other two — Lentera and
tamilnadai — are INACTIVE, so HalaTuju is what the money buys. Recorded in docs/decisions.md.
"""
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import platform_cost
from apps.scholarship.models import PlatformCost


class Command(BaseCommand):
    help = 'Record a platform cost line by hand, or report a month with its reconciliation.'

    def add_arguments(self, parser):
        parser.add_argument('--month', required=True, help="Billing month, 'YYYY-MM'.")
        parser.add_argument('--report', action='store_true',
                            help='Show the month + reconciliation instead of writing.')
        parser.add_argument('--source', choices=[c[0] for c in PlatformCost.SOURCE_CHOICES])
        parser.add_argument('--service', default='')
        parser.add_argument('--sku', default='')
        parser.add_argument('--amount', help='The figure ON the invoice, e.g. 25.00')
        parser.add_argument('--currency', default='MYR',
                            help="ISO code the invoice is denominated in. Supabase = USD.")
        parser.add_argument('--fx-rate', dest='fx_rate',
                            help='Rate to convert --amount into MYR. Prefer the rate your CARD '
                                 'was actually charged at — that is the real cost. Omit it and '
                                 'the row is held with no ringgit figure rather than a guess.')
        parser.add_argument('--invoice-ref', dest='invoice_ref', default='',
                            help="Provider invoice number, e.g. TPTHYS-00007.")
        parser.add_argument('--period-note', dest='period_note', default='',
                            help='Set when the billing period is not the calendar month, e.g. '
                                 '"Supabase cycle 08 Jun - 08 Jul 2026".')
        parser.add_argument('--attributable', action='store_true',
                            help='Mark this line as moving with TENANT activity. Default is '
                                 'platform — the safe direction: an unbilled tenant is a '
                                 'pricing conversation, an over-billed one is a refund.')
        parser.add_argument('--note', default='',
                            help='Invoice number, FX rate, what was excluded. Whatever a '
                                 'future reader needs in order to trust the figure.')

    def handle(self, *args, **opts):
        month = (opts['month'] or '').strip()
        if len(month) != 7 or month[4] != '-':
            raise CommandError("--month must look like 'YYYY-MM'")

        if opts['report']:
            return self._report(month)

        if not opts['source'] or opts['amount'] is None:
            raise CommandError('--source and --amount are required unless --report is given.')
        try:
            amount = Decimal(str(opts['amount']))
        except (InvalidOperation, TypeError) as exc:
            raise CommandError(f'--amount is not a number: {opts["amount"]!r}') from exc

        currency = (opts['currency'] or 'MYR').upper()
        rate = None
        if opts['fx_rate']:
            try:
                rate = Decimal(str(opts['fx_rate']))
            except InvalidOperation as exc:
                raise CommandError(f'--fx-rate is not a number: {opts["fx_rate"]!r}') from exc

        # Three cases, and the middle one is the point of this design:
        #   MYR invoice          -> amount IS the ringgit figure.
        #   foreign + rate       -> convert, and keep BOTH figures plus the rate.
        #   foreign, no rate     -> hold the invoice with NO ringgit figure. Honest, and the
        #                           month reports itself incomplete until somebody supplies it.
        if currency == 'MYR':
            amount_myr, amount_original = amount, None
        elif rate is not None:
            amount_myr, amount_original = (amount * rate).quantize(Decimal('0.01')), amount
        else:
            amount_myr, amount_original = None, amount

        obj, created = PlatformCost.objects.update_or_create(
            period_month=month, source=opts['source'],
            service=opts['service'], sku=opts['sku'],
            defaults={
                'currency': currency,
                'amount_original': amount_original,
                'fx_rate': rate,
                'amount_myr': amount_myr,
                'attributable': opts['attributable'],
                'provenance': 'entered',
                'invoice_ref': opts['invoice_ref'],
                'period_note': opts['period_note'],
                'note': opts['note'],
            })
        verb = 'Recorded' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(f'{verb}: {obj}'))
        if amount_myr is None:
            self.stdout.write(self.style.WARNING(
                f'  HELD WITHOUT A RINGGIT FIGURE: {currency} {amount} with no --fx-rate. '
                'This is deliberate, not a failure — the month will report itself incomplete '
                'until you re-run with the rate your card was charged at.'))
        if not opts['invoice_ref']:
            self.stdout.write(self.style.WARNING(
                '  No --invoice-ref. A hand-entered figure that cannot be traced back to a '
                'document is hard to trust in three months.'))
        self.stdout.write('')
        self._report(month)

    def _report(self, month):
        data = platform_cost.reconcile(month)
        if not data['lines']:
            self.stdout.write(self.style.WARNING(f'No ledger lines for {month}.'))
            return

        w = self.stdout.write
        w(f'-- Platform cost, {month} ' + '-' * 34)
        w(f'  lines                {data["lines"]}')
        if not data['is_complete']:
            # Say it BEFORE the number, so the number is never read on its own.
            w(self.style.ERROR(
                f'  INCOMPLETE - {len(data["unconverted"])} invoice(s) held with no ringgit '
                'figure. The total below is a FLOOR, not a total:'))
            for u in data['unconverted']:
                ref = u['invoice_ref'] or '(no ref)'
                w(self.style.ERROR(
                    f'    {u["source"]:10} {ref:16} {u["currency"]} {u["amount_original"]} '
                    '- needs --fx-rate'))
        w(f'  TOTAL                RM{data["total_myr"]:>10,.2f}'
          + ('   <- FLOOR ONLY' if not data['is_complete'] else ''))
        w(f'    tenant-driven      RM{data["attributable_myr"]:>10,.2f}')
        w(f'    platform-driven    RM{data["platform_myr"]:>10,.2f}')
        w(f'    tax                RM{data["tax_myr"]:>10,.2f}')
        w('  by source:')
        for src, amt in sorted(data['by_source'].items(), key=lambda kv: -kv[1]):
            w(f'    {src:18} RM{amt:>10,.2f}')
        if data['entered_sources']:
            w(self.style.WARNING(
                '  hand-entered (not re-derivable): ' + ', '.join(data['entered_sources'])))
        for caveat in data['period_caveats']:
            # A cross-provider total that silently mixes billing windows is a wrong number
            # wearing a right number's clothes.
            w(self.style.WARNING(f'  period caveat: {caveat}'))

        w('')
        w('-- Reconciliation vs the meter ' + '-' * 29)
        w(f'  metered events       {data["metered_events"]}')
        for svc, n in sorted(data['metered_by_service'].items(), key=lambda kv: -kv[1]):
            w(f'    {svc:18} {n}')
        w(f'  unattributed events  {data["metered_org_null"]} '
          f'({data["metered_org_null_pct"]}%)')
        w('')
        w('  The meter counts EVENTS; the ledger counts MONEY. v1 deliberately computes no')
        w('  implied unit price — there is no price table yet, and a number invented here')
        w('  would end up being quoted. Read the two side by side: if tenant-driven cost')
        w('  moves and metered events do not, a billable seam is missing from the meter.')
