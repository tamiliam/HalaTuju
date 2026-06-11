"""Mirror the private b40-documents Storage bucket to GCS (off-platform backup).

Daily Supabase DB backups do NOT include Storage objects, so the uploaded
ID/income/STR scans — the most sensitive files in the system — have no backup;
a bucket wipe or a bad delete would lose them irrecoverably. This command walks
the whole private bucket and mirrors every object into a GCS bucket in the same
GCP project, so the documents are recoverable off-platform.

Run weekly via the internal cron endpoint (CronRunView job 'backup-documents').

Config: ``settings.DOCUMENT_BACKUP_BUCKET`` (destination GCS bucket). Auth to GCS
is via the runtime service account (ADC); Supabase access uses the service key
(see scholarship/storage.py). Empty config → explicit no-op (never crashes cron).

PII-safe: logs object COUNTS only, never paths or bytes (paths embed app ids).

Incremental + resumable: skips objects already backed up at the same size, so a
run that hits the Cloud Run request timeout still makes progress and the next run
continues where it left off. The initial backfill of a large vault may therefore
span a few runs; steady-state copies only new/changed files. (If the vault grows
into the thousands, move to a Cloud Run Job — no request timeout — or parallelise.)
"""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.scholarship import storage

logger = logging.getLogger(__name__)

GCS_PREFIX = 'b40-documents'  # namespace inside the destination bucket


def _walk_files(prefix=''):
    """Yield (object_path, content_type, size) for every file in the private bucket.

    Supabase ``list`` returns one level: files carry a non-null ``id`` (+ a
    ``metadata`` with mimetype/size); folders have ``id`` = None. Recurse.
    """
    for item in storage.list_objects(prefix):
        name = item.get('name')
        if not name:
            continue
        full = f'{prefix}/{name}' if prefix else name
        if item.get('id'):
            meta = item.get('metadata') or {}
            yield full, (meta.get('mimetype') or 'application/octet-stream'), meta.get('size')
        else:
            yield from _walk_files(full)


def _upload_to_gcs(bucket_name, blob_path, data, content_type):
    """Upload bytes to GCS via the runtime service account (ADC). Isolated in its
    own function so tests can mock it without google-cloud-storage installed."""
    from google.cloud import storage as gcs  # lazy import — prod-only dependency
    client = gcs.Client()
    blob = client.bucket(bucket_name).blob(blob_path)
    blob.upload_from_string(data, content_type=content_type)


def _existing_gcs(bucket_name):
    """{blob_name: size_bytes} already in the backup bucket, so a re-run skips
    unchanged objects (the incremental/resumable behaviour). Isolated for mocking."""
    from google.cloud import storage as gcs  # lazy import — prod-only dependency
    client = gcs.Client()
    return {b.name: b.size for b in client.list_blobs(bucket_name, prefix=f'{GCS_PREFIX}/')}


class Command(BaseCommand):
    help = "Mirror the private b40-documents Storage bucket to the GCS backup bucket (incremental)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help="Walk + count objects without downloading or uploading.")

    def handle(self, *args, **options):
        dry = options['dry_run']
        dest = getattr(settings, 'DOCUMENT_BACKUP_BUCKET', '') or ''
        if not dest:
            self.stdout.write(self.style.WARNING(
                'DOCUMENT_BACKUP_BUCKET not set — skipping document backup (no-op).'))
            return
        if not getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', ''):
            self.stdout.write(self.style.WARNING(
                'Supabase service key not configured — skipping document backup (no-op).'))
            return

        existing = {} if dry else _existing_gcs(dest)
        seen = backed = skipped = failed = 0
        for path, ctype, size in _walk_files():
            seen += 1
            blob_path = f'{GCS_PREFIX}/{path}'
            if not dry and size is not None and existing.get(blob_path) == size:
                skipped += 1  # already backed up at the same size
                continue
            if dry:
                continue
            data = storage.download_object(path)
            if data is None:
                failed += 1
                logger.warning('Backup: could not download object #%d', seen)
                continue
            try:
                _upload_to_gcs(dest, blob_path, data, ctype)
                backed += 1
            except Exception:  # noqa: BLE001 — never crash the weekly cron
                failed += 1
                logger.warning('Backup: GCS upload failed for object #%d', seen, exc_info=True)

        if dry:
            self.stdout.write(self.style.SUCCESS(
                f'DRY RUN — {seen} objects under gs://{dest}/{GCS_PREFIX}/'))
        else:
            style = self.style.SUCCESS if failed == 0 else self.style.WARNING
            self.stdout.write(style(
                f'Document backup → gs://{dest}/{GCS_PREFIX}/ : {backed} copied, '
                f'{skipped} unchanged, {seen} total' + (f', {failed} FAILED' if failed else '')))
