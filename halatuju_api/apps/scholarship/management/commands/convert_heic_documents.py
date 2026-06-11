"""Convert any already-stored HEIC/HEIF documents to JPEG in place.

New uploads are converted automatically (DocumentListCreateView). This one-off handles the
documents uploaded before that existed. Dry-run by default; pass --apply to convert.

    python manage.py convert_heic_documents          # list what would convert
    python manage.py convert_heic_documents --apply  # convert them
"""
from django.core.management.base import BaseCommand

from apps.scholarship.imaging import convert_heic_to_jpeg, is_heic
from apps.scholarship.models import ApplicantDocument


class Command(BaseCommand):
    help = 'Convert existing HEIC/HEIF documents to JPEG (browser- and Vision-friendly).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Actually convert (otherwise a dry run).')

    def handle(self, *args, **opts):
        heic = [d for d in ApplicantDocument.objects.all() if is_heic(d)]
        self.stdout.write(f'Found {len(heic)} HEIC/HEIF document(s):')
        for d in heic:
            self.stdout.write(f'  #{d.id} app={d.application_id} {d.doc_type} '
                              f'{d.original_filename} ({d.content_type})')
        if not heic:
            return
        if not opts['apply']:
            self.stdout.write(self.style.WARNING('Dry run — pass --apply to convert.'))
            return
        ok = 0
        for d in heic:
            if convert_heic_to_jpeg(d):
                ok += 1
                self.stdout.write(self.style.SUCCESS(f'  converted #{d.id}'))
            else:
                self.stdout.write(self.style.WARNING(f'  FAILED #{d.id} (left untouched)'))
        self.stdout.write(self.style.SUCCESS(f'Converted {ok}/{len(heic)}.'))
