"""Self-heal stuck IC / parent_ic OCR (silent upload-time Vision failures).

A transient failure in the Vision MyKad pipeline at upload can leave an IC / parent_ic with
``vision_run_at=NULL`` and no error — never retried — which strands the student behind a false
``ic_service_down`` ("document-check service temporarily unavailable") consent block and a
"couldn't read the IC" cockpit verdict, even though Vision is up. This re-runs Vision on every
such document so the gate / verdict reflect the real read.

Run via the internal cron endpoint job ``reprocess-ic-vision`` (e.g. every 15-30 min), or
manually: ``python manage.py reprocess_unread_ic``. Billable (one Vision read per stuck doc);
each doc is picked up only while it has no run, so the cost is bounded and one-off per doc.
TD-151 (2026-10-02): the sweep also re-reads the slip, offer, income proofs and relationship
documents stuck with no read at all (`services.blockers._SELF_HEAL_READ_TYPES`); `--dry-run` counts.
"""
from django.core.management.base import BaseCommand

from apps.scholarship.services import reprocess_unread_ic_documents


class Command(BaseCommand):
    help = 'Re-run Vision on IC/parent_ic documents stuck unprocessed (silent upload failures).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=200,
                            help='Max documents to re-process in one run.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Count the stuck documents per type and read nothing (TD-151).')

    def handle(self, *args, **opts):
        if opts['dry_run']:
            r = reprocess_unread_ic_documents(limit=opts['limit'], dry_run=True)
            self.stdout.write(f"reprocess_unread_ic DRY-RUN: would re-read {r['scanned']} "
                              f"(by type {r['by_type']}); nothing was read")
            return
        r = reprocess_unread_ic_documents(limit=opts['limit'])
        self.stdout.write(self.style.SUCCESS(
            f"reprocess_unread_ic: scanned={r['scanned']} processed={r['processed']} "
            f"errored={r['errored']}"))
