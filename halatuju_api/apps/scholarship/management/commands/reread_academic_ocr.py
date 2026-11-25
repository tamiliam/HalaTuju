"""TD-741: fill the two academic-reads keys on documents read BEFORE that code existed — OCR ONLY.

WHAT IT FILLS (academic reads B1/B2, TD-733 / TD-735; both DISPLAY ONLY):
  * ``slip_school`` — an SPM ``results_slip`` whose stored read shows no school
    (``academic_compare.slip_school`` reads nothing: an old Gemini read keeps no page text). The page is
    re-OCR'd and read by the SAME path a new upload takes (``spm_cert_parse.parse_spm_cert`` first, then
    ``vision._extract_slip_deterministic`` -> ``academic_engine.parse_spm_slip``); when that locks and
    its rows print ``SEKOLAH :``, ONLY the school string is stored, BESIDE the read, as
    ``vision_fields.slip_school_read`` (``academic_compare.SLIP_SCHOOL_READ``). Its one reader is
    ``slip_school``. The rows themselves (``_debug_rows``) are NOT written: they feed the printed subject
    count and the printed lines that the Academic fact, the slip check and the verdict read, and a
    display backfill must never move a verdict input (review round 1).
  * ``transcript_year`` — a Matriculation / Asasi / Diploma ``higher_results`` read (not the STPM exact
    read) with no ``vision_fields.exam_year_read``: the page's OCR text is read by
    ``exam_years.read_transcript_year`` (the call ``higher_results.extract`` makes on a new upload) and
    stored as ``vision_fields.exam_year_read`` — only when it reads a year. Only the merit's year label
    reads it (`higher_results.student_higher_check`).

WHAT IT NEVER DOES. No Gemini; never ``reextract_document`` / ``run_field_extraction_for_document``. One
Cloud Vision ``document_text_detection`` per document at most (a digital PDF's text layer is free). It
writes ONE key per document, merged into the stored JSON under a row lock and only if the stored read is
still the one it classified; fields, verdicts, genuineness, authenticity, ``student_verdict``, the run
stamps and MODEL_VERSION are untouched. It does not keep the OCR text (the private OCR store is never
read or written).

SAFETY (the 2026-10 clobber incident: a run without Storage read every blob as "no text"). A blob that
cannot be fetched, an OCR error or an empty OCR text SKIPS the document and counts it — nothing is
written. An empty value (no school, no year) is never written. Already-filled documents are skipped, so
a re-run is idempotent.

KNOWN SKIPS, decided from the stored read WITHOUT a Vision call, so a re-run does not pay for them again:
a higher result in the slip slot (``wrong_slip.higher_kind``), a slip whose stored page text prints no
school, a certificate read, a non-SPM title, and a higher document whose detected kind is not the held
one. A document that is read and skipped for another reason (no year, a slip that does not lock) stays
a target: ``--after-id`` (the ``resume_after_id`` a run prints last) starts past it.

USAGE (dry run is the DEFAULT: counts only, no OCR, no write, no spend):
    python manage.py reread_academic_ocr                               # dry run: fresh / known-skip counts
    python manage.py reread_academic_ocr --apply --limit 20            # the 20-document pilot
    python manage.py reread_academic_ocr --apply --ids 3020,3615       # named documents only
    python manage.py reread_academic_ocr --apply --after-id 4100       # resume past the last run
    python manage.py reread_academic_ocr --apply                       # the rest, up to --max-cost-usd
``--max-cost-usd`` (default 2.0): each read is estimated at one page x US$0.0015 and the run stops
before the next read would pass the cap; the running spend is printed per document. Output is counts
and document ids only — never a name, IC, school, college or OCR text.

RUN IT SERVICE-SIDE, NEVER FROM A LOCAL CHECKOUT (a laptop has no Storage access: every blob would
skip). A one-off command runs through the ``release-decisions`` Cloud Run job with an args override
(docs/deployment.md items 11-12). EACH COMMAND BELOW IS ONE LINE: paste it whole. A first line pasted
alone would run the job with its STORED args (send_pending_decision_emails).

    1. Dry run (reads nothing, spends nothing; read the execution log for the counts):
gcloud run jobs execute release-decisions --region asia-southeast1 --wait --account tamiliam@gmail.com --project gen-lang-client-0871147736 --args=manage.py,reread_academic_ocr

    2. Pilot, 20 documents (check the log: written / skipped counts and ids; spot-check a few rows):
gcloud run jobs execute release-decisions --region asia-southeast1 --wait --account tamiliam@gmail.com --project gen-lang-client-0871147736 --task-timeout=3600s --update-env-vars=BILLING_USAGE_ENABLED=true --args=manage.py,reread_academic_ocr,--apply,--limit,20

    3. The rest, resuming past the last id the previous run printed (``resume_after_id=N``):
gcloud run jobs execute release-decisions --region asia-southeast1 --wait --account tamiliam@gmail.com --project gen-lang-client-0871147736 --task-timeout=3600s --update-env-vars=BILLING_USAGE_ENABLED=true --args=manage.py,reread_academic_ocr,--apply,--after-id,N,--max-cost-usd,2

RETRIES. The ``release-decisions`` job is configured with ``maxRetries: 1`` (run_cron_job.py,
docs/technical-debt.md; not re-read off the live job here), and ``gcloud run jobs execute`` has no
``--max-retries`` override. A failed task is therefore re-run ONCE with the same args. That is safe (the
run is idempotent: what was written is skipped), but the retry has its own cost cap, so a failed run
can spend up to TWICE ``--max-cost-usd``. Do not lower the job's retries for this (the cron uses them).

Env the job needs, by name: ``SUPABASE_URL`` and ``SUPABASE_SERVICE_ROLE_KEY`` (Storage; on the job),
the database env (on the job), Cloud Vision through the job's service account (or
``GOOGLE_CLOUD_VISION_API_KEY`` if the service sets one), and ``BILLING_USAGE_ENABLED=true`` so the reads
are metered (it only warns when off). ``DOC_GENUINENESS_CHECK_ENABLED`` is NOT needed: nothing is scored
and the stored ``authenticity`` is never touched. If the pilot shows every read as ``blob_missing`` or
``ocr_error``, stop: the job cannot reach Storage or Vision (nothing was written).
"""
import copy

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.scholarship import vision as _v
from apps.scholarship.academic_compare import SLIP_SCHOOL_READ, slip_school
from apps.scholarship.models import ApplicantDocument

#: The estimate of one Cloud Vision page (document_text_detection), US dollars.
VISION_PAGE_USD = 0.0015
SLIP, HIGHER = 'slip_school', 'transcript_year'
#: A target's state before any read: filled, fresh (to read), or else a known-skip reason.
FILLED, FRESH = 'filled', 'fresh'
#: The higher kinds whose merit shows a transcript year (`higher_results.student_higher_check`).
THIRD_ROUTE_KINDS = ('matric', 'asasi', 'diploma')
#: A stored read that is not a usable read: nothing is served from it, so nothing is filled.
_NOT_READ = ('', 'review_manually', 'unreadable', 'wrong_doc')
#: Why `_extract_slip_deterministic` gave no read -> the skip it counts as.
_SLIP_REASONS = {'vision_error': 'ocr_error', 'no_words': 'ocr_empty', 'no_image': 'blob_missing'}


def _acad_slip_state(doc, vf, f) -> str:
    """FILLED | FRESH | a known-skip reason for a results slip, from the stored read alone."""
    if slip_school(f, vf):
        return FILLED
    from apps.scholarship.vision.field_extraction import slip_not_spm_kind
    from apps.scholarship.wrong_slip import higher_kind
    if higher_kind(doc):
        return 'higher_kind'            # a higher result in the SPM slot: its card shows no SPM school
    diag = f.get('_slip_ocr_diag') if isinstance(f.get('_slip_ocr_diag'), dict) else {}
    if isinstance(f.get('_debug_rows'), list) or isinstance(diag.get('capture'), list):
        return 'stored_no_school'       # the page text is kept already and prints no school
    if vf.get('capture') == 'deterministic' and 'nric' in f and 'skew_angle' not in f:
        return 'certificate'            # a `parse_spm_cert` read: a certificate keeps no slip rows
    title = str(f.get('exam') or '')
    if diag.get('reason') == 'not_spm_exam' or (title and slip_not_spm_kind(title, title=title)):
        return 'not_spm_exam'           # the slip gate refuses this page
    return FRESH


def _acad_reread_kind(doc):
    """``(SLIP | HIGHER, state)`` for a document this command looks at, else ``None`` (out of scope)."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    f = vf.get('fields') if isinstance(vf.get('fields'), dict) else {}
    if not f or vf.get('error') or (vf.get('student_verdict') or '') in _NOT_READ:
        return None
    if doc.doc_type == 'results_slip':
        return SLIP, _acad_slip_state(doc, vf, f)
    if doc.doc_type != 'higher_results':
        return None
    from apps.courses import public as courses_public
    from apps.scholarship.higher_results import _exact_stpm
    if _exact_stpm(vf):
        return None
    held = courses_public.results_held(getattr(getattr(doc, 'application', None), 'profile', None))
    kind_held = held if courses_public.is_tertiary(held) else (doc.results_kind or '')
    kind = (f.get('results_kind_detected') or '') or kind_held   # as student_higher_check serves it
    if kind not in THIRD_ROUTE_KINDS:
        return None
    if kind_held and kind != kind_held:
        return HIGHER, 'kind_mismatch'  # student_higher_check serves no year for it
    return HIGHER, FILLED if isinstance(vf.get('exam_year_read'), dict) else FRESH


def _acad_page_read(doc):
    """``(read | None, skip reason, Vision pages billed)``: the page as `vision.ocr_document_full` reads it
    on an upload (a digital PDF's usable text layer, else one Vision call for text + word boxes) WITHOUT
    keeping the text (keeping it is the upload's job, not a backfill's). Never raises."""
    from apps.scholarship.pdf_pages import MIN_TEXT_LAYER_CHARS, usable_text_layer
    image = _v._fetch_image_bytes(doc.storage_path)
    if not image:
        return None, 'blob_missing', 0
    if _v._is_pdf(doc.content_type, image):
        layer = usable_text_layer(_v._pdf_text_layer(image))
        if len(layer) >= MIN_TEXT_LAYER_CHARS:
            return {'text': layer, 'words': None, 'image': image}, '', 0
    r = _v._vision_words(image, doc.content_type)
    if r.get('error'):
        return None, 'ocr_error', 1
    if not (r.get('text') or '').strip():
        return None, 'ocr_empty', 1
    return {'text': r['text'], 'words': r.get('words'), 'image': image}, '', 1


def _acad_slip_rows(doc, page):
    """``(rows | None, skip reason)``: a new upload's slip read on this page — the certificate first, then
    the deterministic slip read (its gate and `parse_spm_slip`) — and the rows that read keeps."""
    from apps.scholarship.spm_cert_parse import parse_spm_cert
    if parse_spm_cert(page['text'], page['words'], page['image']) is not None:
        return None, 'certificate'
    ex, diag = _v._extract_slip_deterministic(doc, page['image'], words=page['words'], text=page['text'])
    if ex is None:
        reason = (diag or {}).get('reason') or 'parse_none'
        return None, _SLIP_REASONS.get(reason, reason)
    rows = (ex.get('fields') or {}).get('_debug_rows')
    if not isinstance(rows, list) or not any(isinstance(r, str) and r.strip() for r in rows):
        return None, 'no_rows'
    return rows, ''


def _acad_value(doc, kind):
    """``(value | None, skip reason, Vision pages billed)`` for one target. Any failure is a skip. The
    pages are counted HIGH, never low: a slip counts one page even on a digital PDF (its slip read still
    buys word boxes), and a failure counts one."""
    from apps.scholarship import usage
    try:
        with usage.usage_context(application=getattr(doc, 'application', None), source='academic_reread'):
            page, why, pages = _acad_page_read(doc)
            if page is None:
                return None, why, pages
            if kind == SLIP:
                rows, why = _acad_slip_rows(doc, page)
                if rows is None:
                    return None, why, 1
                school = slip_school({'_debug_rows': rows})   # the school string only; never the rows
                return (school, '', 1) if school else (None, 'no_school', 1)
            from apps.scholarship.exam_years import read_transcript_year
            f = doc.vision_fields.get('fields') or {}
            read = read_transcript_year(page['text'], f.get('exam'))
            return (read, '', pages) if read.get('year') else (None, 'no_year', pages)
    except Exception as exc:   # a backfill must never stop on one document; the doc is left untouched
        return None, f'error_{type(exc).__name__}', 1


def _acad_write(doc, kind, value) -> str:
    """Merge ONE key into the stored read, under a row lock, only if the stored read is still EQUAL to
    the one classified (any concurrent write wins). 'written' | 'changed'."""
    if not value:
        return 'changed'           # never an empty value (defence in depth; callers already skip)
    with transaction.atomic():
        row = ApplicantDocument.objects.select_for_update().only('id', 'vision_fields').get(pk=doc.pk)
        if row.vision_fields != doc.vision_fields:
            return 'changed'
        new = copy.deepcopy(row.vision_fields)
        if kind == SLIP:
            if slip_school(new.get('fields') or {}, new):
                return 'changed'
            new[SLIP_SCHOOL_READ] = value
        else:
            if isinstance(new.get('exam_year_read'), dict):
                return 'changed'
            new['exam_year_read'] = value
        ApplicantDocument.objects.filter(pk=row.pk).update(vision_fields=new)
    return 'written'


class Command(BaseCommand):
    help = ('TD-741: OCR-only backfill of the SPM slip school (display only) and the Matriculation/Asasi/'
            'Diploma transcript year on old reads. Dry run unless --apply. Run on the release-decisions job.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Read and write (default: dry run).')
        parser.add_argument('--limit', type=int, default=0, help='Read at most N documents (0 = no limit).')
        parser.add_argument('--ids', default='', help='Comma-separated document ids (only these).')
        parser.add_argument('--after-id', type=int, default=0,
                            help='Only documents with an id above this (resume past the last run).')
        parser.add_argument('--max-cost-usd', type=float, default=2.0,
                            help=f'Stop before the estimated Vision spend (pages x US${VISION_PAGE_USD}) '
                                 'passes this cap.')

    def _targets(self, opts):
        qs = ApplicantDocument.objects.filter(doc_type__in=('results_slip', 'higher_results'),
                                              superseded_at__isnull=True)
        if opts['ids']:
            try:
                ids = [int(x) for x in opts['ids'].split(',') if x.strip()]
            except ValueError:
                raise CommandError('reread_academic_ocr: --ids takes comma-separated integers.')
            qs = qs.filter(pk__in=ids)
        if opts['after_id']:
            qs = qs.filter(pk__gt=opts['after_id'])
        counts = {SLIP: {}, HIGHER: {}}                   # kind -> {state: n}
        targets = []
        for doc in qs.select_related('application__profile').order_by('pk'):
            got = _acad_reread_kind(doc)
            if got is None:
                continue
            kind, state = got
            counts[kind][state] = counts[kind].get(state, 0) + 1
            if state == FRESH:
                targets.append((doc, kind))
        return targets, counts

    def handle(self, *args, **opts):
        from django.conf import settings
        cap, limit = max(0.0, opts['max_cost_usd']), max(0, opts['limit'] or 0)
        targets, counts = self._targets(opts)
        out = self.stdout.write
        for kind in (SLIP, HIGHER):
            c = counts[kind]
            known = {k: n for k, n in c.items() if k not in (FILLED, FRESH)}
            out(f'{kind}: fresh={c.get(FRESH, 0)} known_skip={sum(known.values())} '
                f'already_filled={c.get(FILLED, 0)}')
            for why in sorted(known):
                out(f'{kind} known_skip {why}={known[why]}')
        planned = targets[:limit] if limit else targets
        affordable = min(len(planned), int(round(cap / VISION_PAGE_USD, 6)))
        if not opts['apply']:
            out(f'DRY RUN: nothing read, nothing written. would_read={affordable} '
                f'est_cost_usd={affordable * VISION_PAGE_USD:.4f} cap_usd={cap:.4f}'
                + (f' (cap stops {len(planned) - affordable} more)' if affordable < len(planned) else ''))
            return
        if not getattr(settings, 'BILLING_USAGE_ENABLED', False):
            self.stderr.write('reread_academic_ocr: BILLING_USAGE_ENABLED is off - these Vision reads will '
                              'not be metered (set BILLING_USAGE_ENABLED=true on the job).')
        self._apply(planned, cap, opts['after_id'] or 0)

    def _apply(self, planned, cap, after_id):
        out = self.stdout.write
        spend, written, skipped, stopped, last = 0.0, {SLIP: [], HIGHER: []}, {}, False, after_id
        for doc, kind in planned:
            if spend + VISION_PAGE_USD > cap + 1e-9:
                stopped = True
                break
            value, why, pages = _acad_value(doc, kind)
            spend += pages * VISION_PAGE_USD
            try:
                result = _acad_write(doc, kind, value) if value else why
            except Exception as exc:    # a DB error on one row: counted, and the summary still prints
                result = f'write_error_{type(exc).__name__}'
            if result == 'written':
                written[kind].append(doc.pk)
            else:
                skipped.setdefault(result, []).append(doc.pk)
            last = doc.pk
            out(f'doc {doc.pk} {kind} {result} spend_usd={spend:.4f}')
        for kind in (SLIP, HIGHER):
            out(f'{kind}: written={len(written[kind])} ids={written[kind]}')
        for why in sorted(skipped):
            out(f'skipped {why}={len(skipped[why])} ids={skipped[why]}')
        if stopped:
            out(f'STOPPED at the cost cap (US${cap:.4f}); run again with --after-id {last} to continue.')
        out(f'APPLIED: written={sum(len(v) for v in written.values())} '
            f'skipped={sum(len(v) for v in skipped.values())} spend_usd={spend:.4f}')
        out(f'resume_after_id={last}')
