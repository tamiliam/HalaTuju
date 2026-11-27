"""OCR-15 phase 1 (owner's yes to "way B" for parent ICs only, 27 Nov 2026): a ONE-OFF Cloud Vision capture
of the text on the live parent ICs that have none stored yet, kept only in the private store (``ocr_keep``).

Why: OCR-2 keeps the text of each new supporting-document read, and since OCR-15 the IC read keeps its Vision
text too, but the parent ICs read before that hold none and the corpus has none, so OCR-15's rules have
nothing to be tested on. This reads each one ONCE, exactly as the live IC read does (``vision.extract_mykad``:
page 1 of a PDF rasterised, one Cloud Vision DOCUMENT_TEXT_DETECTION call), and keeps the text through
``ocr_keep.keep`` (source ``vision_ocr``, reader ``capture_parent_ic_text``). The fields it parses are thrown
away.

Selected: live (``superseded_at IS NULL``) ``parent_ic`` rows with a storage path and no stored text, that are
not waiting in the read queue (``read_state='pending'``: that read keeps its own text). By id. Idempotent: a
re-run skips every document already stored, and each one is checked again just before its read.

DRY RUN BY DEFAULT: counts only (how many would be read, the Vision units, the estimated cost); no download,
no Vision call, no write. ``--run`` reads, and needs ``--limit`` (documents, at most ``MAX_LIMIT``) and
``--max-cost-usd`` (at most ``MAX_COST_USD``); it stops before the read that would pass the cap, and stops if
the first ``FAIL_FAST`` reads all fail (a missing key or permission, not a bad card).

Writes ONLY through ``ocr_keep.keep``. Never Gemini; never the document, its vision_fields, verdicts,
genuineness or statuses. The one other row is the Vision seam's own billing meter (``usage.record_usage``,
one ``UsageEvent`` per call, as every Vision call logs), tagged ``source='ocr15_parent_ic_capture'``.

PRIVATE: prints and logs counts and document ids at most; never a name, an IC number or the text. A document
that fails is counted under a reason code and never stops the run.

    python manage.py capture_parent_ic_text                                         # dry run
    python manage.py capture_parent_ic_text --run --limit 600 --max-cost-usd 1.00   # the capture
"""
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import ocr_keep, usage, vision
from apps.scholarship.models import ApplicantDocument, ApplicantDocumentOcrText

logger = logging.getLogger(__name__)

READER = 'capture_parent_ic_text'
USAGE_SOURCE = 'ocr15_parent_ic_capture'
#: Cloud Vision DOCUMENT_TEXT_DETECTION: US$1.50 per 1,000 units past the monthly free 1,000. The estimate
#: and the cap ignore the free units, so they can only over-state the cost.
UNIT_PRICE_USD = Decimal('0.0015')
MAX_LIMIT = 1000
MAX_COST_USD = Decimal('5.00')
FAIL_FAST = 5

STORED, ALREADY_STORED, GONE = 'stored', 'already_stored', 'gone'
FETCH_FAILED, READ_FAILED, NO_TEXT = 'fetch_failed', 'read_failed', 'no_text'
WRITE_FAILED, ERROR = 'write_failed', 'error'
OUTCOMES = (STORED, ALREADY_STORED, GONE, FETCH_FAILED, READ_FAILED, NO_TEXT, WRITE_FAILED, ERROR)
_FAILED = (READ_FAILED, ERROR)


def live_parent_ics():
    """The live parent ICs with a file to read."""
    return ApplicantDocument.live(ApplicantDocument.objects.filter(doc_type='parent_ic')).exclude(storage_path='')


def parent_ic_capture_ids():
    """The ids this capture would read, by id: no stored text, not waiting in the read queue."""
    stored = ApplicantDocumentOcrText.objects.values('document_id')
    return list(live_parent_ics().exclude(pk__in=stored).exclude(read_state='pending')
                .order_by('pk').values_list('pk', flat=True))


def capture_parent_ic(doc_id):
    """Read one parent IC with Cloud Vision and keep its text. ``(outcome, Vision units charged)``; never
    raises. A unit is charged whenever the file came back (an upper bound: a PDF that will not rasterise
    makes no call), so the cap can only stop early."""
    units = 0
    try:
        doc = live_parent_ics().filter(pk=doc_id).select_related('application').first()
        if doc is None:
            return GONE, 0
        if ApplicantDocumentOcrText.objects.filter(document_id=doc_id).exists():
            return ALREADY_STORED, 0   # a live read kept it since the list was made
        seen = []
        with usage.usage_context(application=doc.application, source=USAGE_SOURCE):
            image = vision._fetch_image_bytes(doc.storage_path)
            if not image:
                return FETCH_FAILED, 0
            units = 1
            result = vision.extract_mykad(image, doc.content_type, text_out=seen)
        if result.get('error'):
            return READ_FAILED, units
        text = ''.join(seen)
        if not text.strip():
            return NO_TEXT, units
        ocr_keep.keep(doc, text, source=ocr_keep.VISION_OCR, reader=READER)
        kept = ApplicantDocumentOcrText.objects.filter(document_id=doc_id, reader=READER).exists()
        return (STORED if kept else WRITE_FAILED), units
    except Exception as e:   # one document never stops the run; the type only, never the message
        logger.warning('capture_parent_ic_text: doc %s failed (%s)', doc_id, type(e).__name__)
        return ERROR, max(units, 1)


def _cost(units) -> Decimal:
    return (UNIT_PRICE_USD * units).quantize(Decimal('0.0001'))


class Command(BaseCommand):
    help = ('OCR-15: one-off Cloud Vision capture of the live parent ICs\' text into the private store. '
            'DRY RUN unless --run (which needs --limit and --max-cost-usd).')

    def add_arguments(self, parser):
        parser.add_argument('--run', action='store_true',
                            help='Read with Cloud Vision and keep the text. Without it: counts only.')
        parser.add_argument('--limit', type=int, default=None,
                            help=f'At most this many documents (1 to {MAX_LIMIT}). Required with --run.')
        parser.add_argument('--max-cost-usd', default=None,
                            help=f'Stop before the read that would pass this estimated cost (at most '
                                 f'{MAX_COST_USD}). Required with --run.')

    def handle(self, *args, **opts):
        limit, cap = self._checked(opts)
        ids = parent_ic_capture_ids()
        live = live_parent_ics()
        out = self.stdout.write
        out(f'capture_parent_ic_text: {"RUN" if opts["run"] else "DRY RUN (no download, no Vision call, no write)"}')
        out(f'  live parent ICs: {live.count()}')
        out(f'  already stored: {live.filter(pk__in=ApplicantDocumentOcrText.objects.values("document_id")).count()}')
        out(f'  waiting in the read queue (skipped): {live.filter(read_state="pending").count()}')
        out(f'  without stored text: {len(ids)}')
        todo = ids[:limit] if limit else ids
        out(f'  to read{f" (limit {limit})" if limit else ""}: {len(todo)}')
        out(f'  estimated Vision units: {len(todo)} (1 per document, page 1 only)')
        out(f'  estimated cost: up to US${_cost(len(todo))} at US$1.50 per 1,000 units '
            f'(US$0 while inside the monthly free 1,000)')
        has_key = bool(getattr(settings, 'GOOGLE_CLOUD_VISION_API_KEY', ''))
        out(f'  vision key: {"set" if has_key else "not set (Vision uses the job service account)"}')
        if not opts['run']:
            return
        self._run(todo, cap)

    def _checked(self, opts):
        limit, raw_cap = opts['limit'], opts['max_cost_usd']
        if limit is not None and not 1 <= limit <= MAX_LIMIT:
            raise CommandError(f'--limit must be 1 to {MAX_LIMIT}.')
        if not opts['run']:
            return limit, None
        if limit is None or raw_cap is None:
            raise CommandError('--run needs --limit and --max-cost-usd.')
        try:
            cap = Decimal(str(raw_cap))
        except InvalidOperation:
            raise CommandError('--max-cost-usd must be a number, e.g. 1.00.') from None
        if not (cap.is_finite() and Decimal('0') < cap <= MAX_COST_USD):
            raise CommandError(f'--max-cost-usd must be above 0 and at most {MAX_COST_USD}.')
        return limit, cap

    def _run(self, todo, cap):
        counts = dict.fromkeys(OUTCOMES, 0)
        failed_ids = {code: [] for code in OUTCOMES if code not in (STORED, ALREADY_STORED)}
        units, stopped, attempted = 0, '', 0
        for doc_id in todo:
            if _cost(units + 1) > cap:
                stopped = f'cost cap US${cap} (next read would pass it)'
                break
            code, used = capture_parent_ic(doc_id)
            units += used
            counts[code] += 1
            if code in failed_ids:
                failed_ids[code].append(doc_id)
            if used:
                attempted += 1
            if attempted == FAIL_FAST and sum(counts[c] for c in _FAILED) == FAIL_FAST:
                stopped = f'the first {FAIL_FAST} reads all failed (check the Vision key or permission)'
                break
        out = self.stdout.write
        out('capture_parent_ic_text: done' + (f' - STOPPED: {stopped}' if stopped else ''))
        for code in OUTCOMES:
            out(f'  {code}: {counts[code]}')
        out(f'  not reached: {len(todo) - sum(counts.values())}')
        out(f'  Vision units charged (upper bound): {units}; estimated cost up to US${_cost(units)}')
        for code, doc_ids in failed_ids.items():
            if doc_ids:
                out(f'  {code} ids: {", ".join(str(i) for i in doc_ids)}')
        logger.info('capture_parent_ic_text: %s', {k: v for k, v in counts.items() if v})
