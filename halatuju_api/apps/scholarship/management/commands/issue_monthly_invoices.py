"""Issue last month's invoice for every tenant that is ready — the 15th's run (2026-09-14).

    python manage.py issue_monthly_invoices                  # what the scheduler does
    python manage.py issue_monthly_invoices --dry-run        # readiness only, writes nothing
    python manage.py issue_monthly_invoices --month 2026-08  # a specific closed month

Door: `CronRunView.JOBS['issue-monthly-invoices']`, fired by Cloud Scheduler at 09:00 on the
15th, Asia/Kuala_Lumpur. ⚠ The door passes NO arguments, so the no-argument run IS the real run —
it issues. That is deliberate and safe: issuing sends nothing to anybody (a super presses Send),
a wrong invoice is voided rather than lost, and the run is idempotent, so a second call the same
day skips every tenant already invoiced.

⚠ **IT NEVER OVERRIDES A READINESS PROBLEM.** A missing supplier bill, a missing exchange rate or
unrecorded request hours stop that tenant's invoice, and the reason is LOGGED and EMAILED — not
printed. Under cron, stdout goes into an HTTP response body that Cloud Scheduler discards (the
September-blackout lesson), so a refusal written only to stdout would reach nobody.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import emails, invoicing


class Command(BaseCommand):
    help = "Issue the previous month's invoice for every tenant that is ready."

    def add_arguments(self, parser):
        parser.add_argument('--month', default='',
                            help="Bill this closed month ('YYYY-MM') instead of the previous one.")
        parser.add_argument('--dry-run', action='store_true',
                            help='Report readiness for each tenant and write nothing.')

    def handle(self, *args, **opts):
        month = (opts['month'] or '').strip() or invoicing.previous_month()
        if not invoicing.MONTH_RE.match(month):
            raise CommandError(f"--month must look like 2026-08, not {month!r}")

        if opts['dry_run']:
            from apps.courses.models import PartnerOrganisation
            for org in PartnerOrganisation.objects.tenants().order_by('name'):
                problems = invoicing.readiness(org, month)
                state = 'READY' if not problems else 'NOT READY'
                self.stdout.write(f'{org.name} — {invoicing.month_label(month)}: {state}')
                for p in problems:
                    tag = 'can override' if p['overridable'] else 'blocks'
                    self.stdout.write(f'  - [{tag}] {p["message"]}')
            self.stdout.write('DRY RUN — nothing issued.')
            return

        report = invoicing.issue_month(month)
        for i in report['issued']:
            invoicing.logger.info('issue_monthly_invoices: issued %s for %s (RM%s)',
                                  i['number'], i['organisation'], i['total_myr'])
        for s in report['skipped']:
            invoicing.logger.info('issue_monthly_invoices: %s already invoiced for %s',
                                  s['organisation'], month)
        for r in report['refused']:
            invoicing.logger.warning('issue_monthly_invoices: NOT issued for %s (%s): %s',
                                     r['organisation'], month, ' | '.join(r['problems']))
        if report['refused']:
            emails.send_invoicing_alert_email(report)
        self.stdout.write(
            f"{invoicing.month_label(month)}: issued {len(report['issued'])}, "
            f"already invoiced {len(report['skipped'])}, not issued {len(report['refused'])}.")
