"""Self-heal stuck IC / parent_ic OCR (silent upload-time Vision failures).

A transient failure in the Vision MyKad pipeline at upload can leave an IC / parent_ic with
``vision_run_at=NULL`` and no error — never retried — which strands the student behind a false
``ic_service_down`` ("document-check service temporarily unavailable") consent block and a
"couldn't read the IC" cockpit verdict, even though Vision is up. This re-runs Vision on every
such document so the gate / verdict reflect the real read.

Run via the internal cron endpoint job ``reprocess-ic-vision`` (Cloud Scheduler
``halatuju-reprocess-ic-vision``, HOURLY, ``0 * * * *``), or manually:
``python manage.py reprocess_unread_ic``. Billable (one Vision read per stuck doc);
each doc is picked up only while it has no run, so the cost is bounded and one-off per doc.
TD-151 (2026-10-02): the sweep also re-reads the slip, offer, income proofs and relationship
documents stuck with no read at all (`services.blockers._SELF_HEAL_READ_TYPES`); `--dry-run` counts.
A2.2 / TD-518 (2026-11-07): each run is capped by a TIME BUDGET (default 100 s) and a smaller batch (100), so
it never meets the 300 s request limit; a stop leaves the unreached documents for the next run (the queue is
the cursor). 2026-10-24: and documents whose stored read is OUR service failing (`services.read_retry`) —
skipped while Gemini reads are down, at most 72 hours per document, never on a closed case.
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.scholarship.reextract import reread_preflight
from apps.scholarship.services import reprocess_unread_ic_documents


class Command(BaseCommand):
    help = 'Re-run Vision on IC/parent_ic documents stuck unprocessed (silent upload failures).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None,
                            help='Max documents to re-process in one run (default settings.REPROCESS_BATCH_LIMIT).')
        parser.add_argument('--time-budget', type=int, default=None,
                            help='Seconds after which the run stops cleanly between documents and the next run '
                                 'resumes (default settings.REPROCESS_TIME_BUDGET_SECONDS; 0 = no budget).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Count the stuck documents per type and read nothing (TD-151).')

    def handle(self, *args, **opts):
        limit = opts['limit'] or settings.REPROCESS_BATCH_LIMIT
        budget = settings.REPROCESS_TIME_BUDGET_SECONDS if opts['time_budget'] is None else opts['time_budget']
        if opts['dry_run']:
            r = reprocess_unread_ic_documents(limit=limit, dry_run=True)
            self.stdout.write(f"reprocess_unread_ic DRY-RUN: would re-read {r['scanned']} "
                              f"(by type {r['by_type']}); nothing was read")
            return
        # TD-407 review: HOURLY via the cron endpoint, which swallows a raised error — so WARN and run
        # (a flag-off re-read keeps stored scores) rather than stop the self-heal quietly.
        reread_preflight(self, opts, refuse=False)
        r = reprocess_unread_ic_documents(limit=limit, time_budget=budget or None)
        stop = f" STOPPED-AT-TIME-BUDGET({budget}s) left={r['left']} (next run resumes)" if r.get('stopped_early') else ''
        self.stdout.write(self.style.SUCCESS(
            f"reprocess_unread_ic: scanned={r['scanned']} processed={r['processed']} "
            f"errored={r['errored']}{stop}"))
