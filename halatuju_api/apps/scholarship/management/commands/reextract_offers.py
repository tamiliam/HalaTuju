"""Re-extract offer letters whose genuineness is MISSING or BELOW the genuine band, so they
re-score under the CURRENT model (results_doc.MODEL_VERSION). Owner-triggered after a model bump
(e.g. 1.4.0 dropped the offer anchor → a recognised-issuer offer below the suspect floor now reads
`not_offer_letter` (fake), and 31 offers uploaded before the scorer shipped carry no score at all).

Targets `offer_letter` docs where `vision_fields.authenticity` is absent OR its probability
< GENUINE_MIN (0.70). A genuine (>= 0.70) offer is SKIPPED — its read is already current-enough.

Self-batching + idempotent: each run processes the next `--limit` (default 20) targeted docs not yet
touched by THIS pass (a marker in `vision_fields`), so it can be called repeatedly (cron-driven) and
observed batch by batch. Reuses `reextract_document` — the SAME core as the cockpit's per-doc 'Re-run'
and the bulk `reextract_documents` command — so the per-doc and batch reads can't drift. A re-extract
re-reads the fields (may recover an OCR-missed candidate IC → clears a red chip) AND re-scores
genuineness under the current MODEL_VERSION. FORCES billable Gemini reads — run deliberately.
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.reextract import reextract_document
from apps.scholarship.genuineness.bands import GENUINE_MIN

# Bump for a future targeted offer-rescore pass (e.g. after the next MODEL_VERSION change).
PASS_MARKER = 'reextract_offers_2026_07'


def _below_genuine(doc) -> bool:
    """True when this offer needs a re-score: no stored genuineness, or a probability under the
    genuine band. A genuine (>= GENUINE_MIN) offer returns False (skipped)."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    auth = vf.get('authenticity')
    if not isinstance(auth, dict) or auth.get('status') is None:
        return True                       # never scored → target
    try:
        return float(auth.get('probability')) < GENUINE_MIN
    except (TypeError, ValueError):
        return True                       # scored but no/garbled probability → target


class Command(BaseCommand):
    help = 'Re-extract offer letters with missing or below-genuine (< 0.70) genuineness (batched).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20, help='Docs to process this run.')
        parser.add_argument('--retry-errors', action='store_true',
                            help="Also re-attempt docs whose last pass run FAILED (marked 'error').")
        parser.add_argument('--dry-run', action='store_true',
                            help='List the targeted docs without running any (billable) read.')

    def handle(self, *args, **opts):
        limit = max(1, opts['limit'])
        retry_errors = opts['retry_errors']
        dry_run = opts['dry_run']

        def unprocessed(doc):
            mark = (doc.vision_fields or {}).get(PASS_MARKER)
            return not mark or (retry_errors and mark == 'error')

        base = ApplicantDocument.objects.filter(
            doc_type='offer_letter', superseded_at__isnull=True).order_by('id')
        batch = []
        for doc in base.iterator():
            if _below_genuine(doc) and unprocessed(doc):
                batch.append(doc)
            if len(batch) >= limit:
                break
        if not batch:
            self.stdout.write('reextract_offers: nothing left — every targeted offer is re-scored.')
            return

        if dry_run:
            for doc in batch:
                self.stdout.write(f'DRY app#{doc.application_id} doc{doc.id}')
            self.stdout.write(f'reextract_offers: {len(batch)} would be processed (dry-run, no reads).')
            return

        done = errors = 0
        for doc in batch:
            stamps_before = (doc.vision_fields_run_at, doc.vision_run_at)
            ok = True
            try:
                reextract_document(doc)
                doc.refresh_from_db()
                a = (doc.vision_fields or {}).get('authenticity') or {}
                after = f"status={a.get('status')} p={a.get('probability')}"
                # The clobber guard preserves the stored read (no timestamp advance) when the re-run
                # itself failed — treat that as an ERROR of this run, not a completed re-extraction.
                if (doc.vision_fields_run_at, doc.vision_run_at) == stamps_before:
                    ok = False
                    after = f'STALE-KEPT [{after}] (re-run failed; stored read preserved)'
            except Exception as e:  # noqa: BLE001 — mark + report so one broken doc never wedges the pass
                ok = False
                after = f'ERROR {str(e)[:55]}'
                doc.refresh_from_db()
            vf = doc.vision_fields or {}
            vf[PASS_MARKER] = True if ok else 'error'
            doc.vision_fields = vf
            doc.save(update_fields=['vision_fields'])
            done += 1
            if not ok:
                errors += 1
            self.stdout.write(f'app#{doc.application_id} doc{doc.id}: -> [{after}]')

        remaining = sum(
            1 for d in base.only('vision_fields', 'doc_type', 'superseded_at',
                                 'vision_fields_run_at', 'vision_run_at')
            if _below_genuine(d) and unprocessed(d))
        error_total = sum(
            1 for d in base.only('vision_fields', 'doc_type', 'superseded_at')
            if (d.vision_fields or {}).get(PASS_MARKER) == 'error')
        self.stdout.write(
            f'reextract_offers: processed {done} ({errors} errors this run), {remaining} remaining, '
            f'{error_total} marked error total — re-attempt those with --retry-errors.')
