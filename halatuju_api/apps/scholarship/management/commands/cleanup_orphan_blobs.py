"""Find (and optionally delete) orphan blobs in the B40 document vault.

TD-062: before S15, clicking "Remove" on a document deleted the DB row but not
the Supabase Storage object, leaking blobs. S15 fixed the live path; this command
sweeps the historical orphans. An orphan = a file in the `b40-documents` bucket
whose path is not referenced by any ``ApplicantDocument.storage_path`` row.

The bucket is laid out as ``{application_id}/{doc_type}/{uuid}`` (see
DocumentSignUploadView), so we walk three levels with the Storage list API and
diff the leaf paths against the DB.

Usage:
    python manage.py cleanup_orphan_blobs            # dry run (lists orphans)
    python manage.py cleanup_orphan_blobs --apply    # actually delete them

Safe by default: without --apply it only reports. Best-effort against Storage —
if the bucket is unreachable it lists nothing rather than erroring.
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ApplicantDocument
from apps.scholarship import storage


def _is_folder(item):
    # Supabase returns folders with id=None and no file metadata.
    return item.get('id') is None


def _walk_bucket():
    """Yield every leaf object path ``{app}/{doc_type}/{name}`` in the bucket."""
    for lvl1 in storage.list_objects(prefix=''):
        if not _is_folder(lvl1):
            # A stray file at the root — surface it as its own path.
            yield lvl1['name']
            continue
        app_prefix = lvl1['name']
        for lvl2 in storage.list_objects(prefix=f'{app_prefix}/'):
            if not _is_folder(lvl2):
                yield f'{app_prefix}/{lvl2["name"]}'
                continue
            doc_prefix = f'{app_prefix}/{lvl2["name"]}'
            for leaf in storage.list_objects(prefix=f'{doc_prefix}/'):
                # At this depth everything should be a file; include regardless.
                yield f'{doc_prefix}/{leaf["name"]}'


class Command(BaseCommand):
    help = 'Find/delete orphan blobs in the b40-documents bucket (TD-062).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually delete the orphan blobs (default: dry run).',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        known = set(
            ApplicantDocument.objects
            .exclude(storage_path='')
            .values_list('storage_path', flat=True)
        )
        self.stdout.write(f'DB references {len(known)} document blob(s).')

        all_paths = list(_walk_bucket())
        self.stdout.write(f'Bucket holds {len(all_paths)} object(s).')

        orphans = sorted(p for p in all_paths if p not in known)
        if not orphans:
            self.stdout.write(self.style.SUCCESS('No orphan blobs. Nothing to do.'))
            return

        self.stdout.write(self.style.WARNING(f'{len(orphans)} orphan blob(s):'))
        for p in orphans:
            self.stdout.write(f'  {p}')

        if not apply:
            self.stdout.write(self.style.NOTICE(
                '\nDry run — nothing deleted. Re-run with --apply to delete these.'))
            return

        ok = storage.delete_objects(orphans)
        if ok:
            self.stdout.write(self.style.SUCCESS(f'Deleted {len(orphans)} orphan blob(s).'))
        else:
            self.stdout.write(self.style.ERROR(
                'Delete failed (Storage unreachable or unconfigured). Nothing removed.'))
