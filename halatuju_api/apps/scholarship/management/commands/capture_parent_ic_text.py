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
``--max-cost-usd`` (at most ``MAX_COST_USD``); it stops before the read that would pass the cap. It also stops
when ``FAIL_FAST`` reads in a row fail with a Vision SERVICE error (``read_errors.is_ocr_service_error``: the
key, quota, permission or network, not the file), ``FAIL_FAST`` fetches in a row fail (a Storage outage), or
``FAIL_FAST`` saves in a row fail (``write_failed`` or ``error``: a broken private store would otherwise spend
the whole cap and keep nothing; a stored document resets it, skips and bad files leave it). An ordinary bad
file (a PDF that will not rasterise, a HEIC, a blank photo) never stops it. Every
``PROGRESS_EVERY`` documents it prints and logs a progress line (counts only), so a killed task leaves a record.

Writes ONLY through ``ocr_keep.keep``, and asks which documents already have text only through
``ocr_keep.ids_with_kept_text`` (ids, never text). Never Gemini; never the document, its vision_fields, verdicts,
genuineness or statuses. The one other row is the Vision seam's own billing meter (``usage.record_usage``,
one ``UsageEvent`` per call, as every Vision call logs), tagged ``source='ocr15_parent_ic_capture'``. That row
is a PLATFORM row (no organisation, no application): this is the platform's own research, so it must not land
in a partner organisation's monthly usage (``usage.monthly_usage``) for its admins to see.

PRIVATE: prints and logs counts and document ids at most; never a name, an IC number or the text. A document
that fails is counted under a reason code and, short of the three stops above, never stops the run.

    python manage.py capture_parent_ic_text                                         # dry run
    python manage.py capture_parent_ic_text --run --limit 600 --max-cost-usd 1.00   # the capture
"""
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import ocr_keep, usage, vision
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.read_errors import is_ocr_service_error

logger = logging.getLogger(__name__)

READER = 'capture_parent_ic_text'
USAGE_SOURCE = 'ocr15_parent_ic_capture'
#: Cloud Vision DOCUMENT_TEXT_DETECTION: US$1.50 per 1,000 units past the monthly free 1,000. The estimate
#: and the cap ignore the free units, so they can only over-state the cost.
UNIT_PRICE_USD = Decimal('0.0015')
MAX_LIMIT = 1000
MAX_COST_USD = Decimal('5.00')
FAIL_FAST = 5          # this many service errors, fetch failures or failed saves in a row stop the run
PROGRESS_EVERY = 50    # a progress line (counts only) every this many documents

STORED, ALREADY_STORED, GONE = 'stored', 'already_stored', 'gone'
FETCH_FAILED, READ_FAILED, NO_TEXT = 'fetch_failed', 'read_failed', 'no_text'
SERVICE_FAILED = 'service_error'   # Vision itself failed (key, quota, permission, network), not the file
WRITE_FAILED, ERROR = 'write_failed', 'error'
SAVE_FAILURES = (WRITE_FAILED, ERROR)   # a billed read whose text was not kept; streak key WRITE_FAILED
OUTCOMES = (STORED, ALREADY_STORED, GONE, FETCH_FAILED, READ_FAILED, SERVICE_FAILED, NO_TEXT, WRITE_FAILED,
            ERROR)


def live_parent_ics():
    """The live parent ICs with a file to read."""
    return ApplicantDocument.live(ApplicantDocument.objects.filter(doc_type='parent_ic')).exclude(storage_path='')


def parent_ic_capture_ids():
    """The ids this capture would read, by id: no stored text, not waiting in the read queue."""
    stored = ocr_keep.ids_with_kept_text(live_parent_ics().values('pk'))
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
        if ocr_keep.ids_with_kept_text([doc_id]):
            return ALREADY_STORED, 0   # a live read kept it since the list was made
        seen = []
        # A PLATFORM meter row: no application and no organisation, so this research never reaches a
        # partner's monthly usage. Nothing encloses this call to inherit an organisation from.
        with usage.usage_context(source=USAGE_SOURCE):
            image = vision._fetch_image_bytes(doc.storage_path)
            if not image:
                return FETCH_FAILED, 0
            units = 1
            result = vision.extract_mykad(image, doc.content_type, text_out=seen)
        err = result.get('error')
        if err:
            return (SERVICE_FAILED if is_ocr_service_error(err) else READ_FAILED), units
        text = ''.join(seen)
        if not text.strip():
            return NO_TEXT, units
        ocr_keep.keep(doc, text, source=ocr_keep.VISION_OCR, reader=READER)
        kept = bool(ocr_keep.ids_with_kept_text([doc_id], reader=READER))
        return (STORED if kept else WRITE_FAILED), units
    except Exception as e:   # one document never stops the run; the type only, never the message
        logger.warning('capture_parent_ic_text: doc %s failed (%s)', doc_id, type(e).__name__)
        return ERROR, max(units, 1)


def _cost(units) -> Decimal:
    return (UNIT_PRICE_USD * units).quantize(Decimal('0.0001'))


def _streak_stop(streak, code, used):
    """Move the three in-a-row counters on one outcome; the reason to stop, or ''. A fetch failure counts
    toward the Storage streak and a Vision service error toward the service streak; a document that was
    fetched (``used``) and read any other way resets the streak it broke. A failed save (``write_failed``
    or ``error``) counts toward the save streak and only a stored document resets it. A skipped document
    (gone, already stored) moves none, and an ordinary bad file never counts."""
    if code == FETCH_FAILED:
        streak[FETCH_FAILED] += 1
    elif used:
        streak[FETCH_FAILED] = 0
        streak[SERVICE_FAILED] = streak[SERVICE_FAILED] + 1 if code == SERVICE_FAILED else 0
    if code in SAVE_FAILURES:
        streak[WRITE_FAILED] += 1
    elif code == STORED:
        streak[WRITE_FAILED] = 0
    if streak[SERVICE_FAILED] >= FAIL_FAST:
        return f'{FAIL_FAST} reads in a row failed with a Vision service error (check the key, quota or permission)'
    if streak[FETCH_FAILED] >= FAIL_FAST:
        return f'{FAIL_FAST} fetches in a row failed (check Storage)'
    if streak[WRITE_FAILED] >= FAIL_FAST:
        return f'{FAIL_FAST} saves in a row failed (check the private text store)'
    return ''


def _counts_line(counts) -> str:
    return ', '.join(f'{code} {n}' for code, n in counts.items() if n) or 'none'


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
        out(f'  already stored: {len(ocr_keep.ids_with_kept_text(live.values("pk")))}')
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
        units, stopped = 0, ''
        streak = {FETCH_FAILED: 0, SERVICE_FAILED: 0, WRITE_FAILED: 0}
        for done, doc_id in enumerate(todo, 1):
            if _cost(units + 1) > cap:
                stopped = f'cost cap US${cap} (next read would pass it)'
                break
            code, used = capture_parent_ic(doc_id)
            units += used
            counts[code] += 1
            if code in failed_ids:
                failed_ids[code].append(doc_id)
            stopped = _streak_stop(streak, code, used)
            if done % PROGRESS_EVERY == 0:
                self._progress(done, len(todo), counts, units)
            if stopped:
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

    def _progress(self, done, total, counts, units):
        """Counts only: a task killed mid-run (timeout, OOM) still leaves how far it got in the log."""
        line = f'capture_parent_ic_text: progress {done} of {total}: {_counts_line(counts)}; units {units}'
        self.stdout.write(line)
        self.stdout.flush()
        logger.info(line)
