"""Hourly partner-organisation milestone emails: awaiting review + awarded (2026-07-26).

Cron slug `partner-milestones`. A thin wrapper — every decision lives in `partner_comms`, every
send in `partner_notify`.

Why a sweep rather than an inline call at the transition: the queryset re-checks the CURRENT status
at send time, so a transition that was reverted (`revert_if_profile_incomplete`, or
`awarded → recommended`) never produces an email. It also lets several students arriving close
together share one email.

`--dry-run` prints what would go and sends nothing; it also stamps nothing, so a dry run can be
repeated.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import partner_notify


class Command(BaseCommand):
    help = 'Tell each qualifying organisation which of its students completed, or were awarded.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would be sent and send nothing (stamps nothing either).',
        )

    def handle(self, *args, **options):
        summary = partner_notify.send_partner_milestones(
            dry_run=options['dry_run'], out=self.stdout)
        for kind, row in summary.items():
            if row.get('off'):
                continue
            self.stdout.write(f'{kind}: emails={row["sent"]} stamped={row["students"]}')
