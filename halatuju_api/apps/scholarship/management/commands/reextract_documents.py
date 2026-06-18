"""Bulk re-extract documents in batches with the CURRENT parsers.

Most supporting docs were read by Gemini before the deterministic capture layer
(2026-06-11), so they carry weaker reads (e.g. an offer letter whose IC was never
captured). This re-reads them with the current deterministic + Gemini parsers.

Self-batching: each run processes the NEXT `--limit` (default 20) docs that this pass
hasn't touched yet — marked by a flag written into ``vision_fields`` — so it can be
called repeatedly (cron-driven) and observed batch by batch. FORCES billable reads, so
it's run deliberately. Scope = the supporting + text doc types (ic/parent_ic already
store their read in dedicated columns; photos aren't OCR'd).
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.reextract import reextract_document

# Bump this for a future re-extraction pass (e.g. after another parser change).
PASS_MARKER = 'reextract_2026_06'


def _summary(doc) -> str:
    """A compact, human-readable digest of the key extracted field(s) per type, so each
    batch's outcome is visible in the (truncated) cron output."""
    vf = doc.vision_fields or {}
    f = vf.get('fields') or {}
    cap = vf.get('capture') or '—'
    dt = doc.doc_type
    if dt == 'offer_letter':
        return f"ic={f.get('candidate_nric','') or '∅'} name={(f.get('candidate_name') or '')[:16]}"
    if dt == 'birth_certificate':
        return f"child={(f.get('bc_child_name') or '∅')[:16]} mother={(f.get('bc_mother_name') or '')[:12]}"
    if dt == 'results_slip':
        return f"name={(f.get('slip_name') or f.get('name') or '')[:16]} cap={cap}"
    if dt in ('salary_slip', 'epf', 'str', 'water_bill', 'electricity_bill'):
        return f"name={(f.get('name') or f.get('str_recipient') or '')[:16]} cap={cap}"
    return f"cap={cap}"


class Command(BaseCommand):
    help = 'Re-extract supporting documents in batches (default 20) with the current parsers.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20, help='Docs to process this run.')

    def handle(self, *args, **opts):
        from apps.scholarship.views import SUPPORTING_NAME_CHECK_TYPES, TEXT_READ_DOC_TYPES
        types = sorted(SUPPORTING_NAME_CHECK_TYPES | TEXT_READ_DOC_TYPES)
        limit = max(1, opts['limit'])

        # Filter "not yet processed this pass" in Python — a JSON-key `.exclude()` mishandles
        # rows where the key (or the whole vision_fields) is absent (SQL NULL semantics).
        def unprocessed(doc):
            return not (doc.vision_fields or {}).get(PASS_MARKER)

        all_docs = ApplicantDocument.objects.filter(doc_type__in=types).order_by('id')
        batch = []
        for doc in all_docs.iterator():
            if unprocessed(doc):
                batch.append(doc)
            if len(batch) >= limit:
                break
        if not batch:
            self.stdout.write('reextract: nothing left — every supporting doc is on the current pass.')
            return

        done = errors = 0
        for doc in batch:
            try:
                reextract_document(doc)
                doc.refresh_from_db()
                line = _summary(doc)
            except Exception as e:  # noqa: BLE001 — mark + report so a broken doc never wedges the pass
                errors += 1
                line = f'ERROR {str(e)[:70]}'
                doc.refresh_from_db()
            # Mark processed (on the freshly-written vision_fields) so the next run advances.
            vf = doc.vision_fields or {}
            vf[PASS_MARKER] = True
            doc.vision_fields = vf
            doc.save(update_fields=['vision_fields'])
            done += 1
            self.stdout.write(f'app#{doc.application_id} doc{doc.id} {doc.doc_type}: {line}')

        remaining = sum(
            1 for d in ApplicantDocument.objects.filter(doc_type__in=types).only('vision_fields', 'doc_type')
            if unprocessed(d))
        self.stdout.write(f'reextract: processed {done} ({errors} errors), {remaining} remaining.')
