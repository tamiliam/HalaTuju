"""Load full MASCO 2020 dataset (4,854 jobs) into MascoOccupation table."""
import csv
import os
from django.core.management.base import BaseCommand
from apps.courses.models import MascoOccupation

EMASCO_BASE = 'https://emasco.mohr.gov.my/masco'


class Command(BaseCommand):
    help = 'Load full MASCO 2020 occupations from masco_full.csv'

    def handle(self, *args, **options):
        csv_path = os.path.join(
            os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'masco_full.csv'
        )
        csv_path = os.path.normpath(csv_path)

        if not os.path.exists(csv_path):
            self.stderr.write(f'CSV not found: {csv_path}')
            return

        # Read all rows, deduplicating by kod_masco (keep first civilian entry)
        seen = {}
        with open(csv_path, encoding='latin-1') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row['kod_masco'].strip()
                title = row['tajuk_pekerjaan'].strip()
                if code and code not in seen:
                    seen[code] = title

        # Bulk create/update
        created = 0
        updated = 0
        for code, title in seen.items():
            url = f'{EMASCO_BASE}/{code}'
            obj, was_created = MascoOccupation.objects.update_or_create(
                masco_code=code,
                defaults={'job_title': title, 'emasco_url': url},
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            f'Loaded {created + updated} MASCO occupations '
            f'({created} created, {updated} updated)'
        )
