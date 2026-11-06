"""List the reviewer rows whose gift was never chosen (TD-501 / SEC-17, audit fix A1.3, decision D5).

    python manage.py staff_gift_report

⚠ READ-ONLY. It writes nothing and changes no row. A NULL gift reads as "every gift", but for these
rows nobody is known to have chosen that: they predate the rule that a reviewer invite names its
gift. The OWNER decides each row (one gift, or every gift) and sets it on Team → Reviewers.

"Reviewer" here means everyone who REVIEWS: the reviewer role plus any team member given `review`
(`staff_gift.unchosen_rows`, the assignable list's rule). It prints the row id, the role, the organisation code, whether the account is switched on, whether
a first sign-in is on record, and how many gifts the organisation runs. No name and no email.
"""
from django.apps import apps
from django.core.management.base import BaseCommand

from apps.courses import staff_gift


class Command(BaseCommand):
    help = 'Read-only: list reviewer rows with no gift chosen (TD-501). Writes nothing.'

    def handle(self, *args, **options):
        Programme = apps.get_model('scholarship', 'Programme')
        rows = list(staff_gift.unchosen_rows())
        gifts = {}
        for row in rows:
            org_id = row.owning_organisation_id
            if org_id not in gifts:
                gifts[org_id] = Programme.objects.filter(organisation_id=org_id).count() if org_id else 0
        self.stdout.write(f'Reviewer rows with no gift chosen: {len(rows)}')
        if not rows:
            return
        self.stdout.write('id\trole\torg\tactive\tsigned_in\tgifts_in_org')
        for row in rows:
            org = row.owning_organisation.code if row.owning_organisation_id else '-'
            self.stdout.write('\t'.join([
                str(row.id), row.role, org,
                'yes' if row.is_active else 'no',
                'yes' if row.first_seen_at else 'not recorded',
                str(gifts[row.owning_organisation_id]),
            ]))
