"""The hourly sweep's second half: re-read documents whose stored read is OUR service failing.

2026-10-24: Gemini's prepaid credit ran out (402) for ~20 hours. Every read in that window failed on
our side and is stored as a deferred read (`review_manually` + `service_error`, see
`read_errors`) — or, for rows written before that fix, as `unreadable` with the same error. This
re-reads them through the cockpit's Re-run core (`reextract.reextract_document`) once the service
answers again, called from `blockers.reprocess_unread_ic_documents` (the `reprocess-ic-vision`
cron, hourly).

The rules, each pinned in `tests/test_ai_outage.py`:

* **Never over a real read.** Only a live document whose stored read has no fields and a
  service-error string is picked; and `vision`'s clobber guard refuses to let a service-error
  result replace any real verdict.
* **Never past the upload path's throttle.** A `rate_limited` read waits until its application is
  under `DOC_ASSIST_RATE_LIMIT_PER_HOUR` reads in the last hour, the same cap the upload uses.
* **Never while Gemini is still down, and never more than one paid probe per run.** Each re-read
  costs a Vision OCR call billed to the organisation, so the batch is skipped while
  `outage.gemini_reads_down`, and stops at the first document that still fails on our side.
* **Never for ever.** Each document gets `SERVICE_RETRY_WINDOW` from the first time the sweep
  tries it (stamped on the row BEFORE the read, with the read stamp, so a process killed mid-read
  moves to the back of the queue and still runs out of time). After that only an officer's Re-run
  reads it again; a new failed read from that Re-run starts a fresh window.
* **Never a decided case.** Applications in `decline.CASE_CLOSED_STATES` are left as they are.

#374 / owner ruling 2A (2026-10-28): the same pass also re-reads, ONCE each, live income documents whose
read predates the approver fields (`approval_unchecked_documents`), so none stays "still checking".
"""
import logging
from datetime import timedelta
from functools import reduce
from operator import or_

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from ..models import ApplicantDocument
from ..read_errors import (IC_SECOND_OPINION_ERROR, RATE_LIMITED, SERVICE_ERROR_PREFIXES,
                           is_ai_service_error)
from .blockers import _SELF_HEAL_READ_TYPES

logger = logging.getLogger('apps.scholarship.services')   # the package's name: the log metric counts by it

#: Every document type whose read a service outage can defer: the gate's read types, plus the
#: soft / post-award reads that field-extract too (`vision.GEMINI_EXTRACT_DOC_TYPES`). They are
#: retried here because a read WAS attempted and our outage broke it. They are deliberately NOT
#: added to the never-read half of the sweep: that half exists for the submission gate (TD-151), and
#: widening it would re-read every legacy unread bill and statement at one paid OCR each.
SERVICE_RETRY_TYPES = _SELF_HEAL_READ_TYPES + (
    'water_bill', 'electricity_bill', 'bank_statement', 'school_leaving_cert', 'semester_result')
SERVICE_RETRY_WINDOW = timedelta(hours=72)
#: Epoch seconds (a number, so the database compares it as one on SQLite and Postgres alike).
RETRY_UNTIL = 'service_retry_until'


def service_error_documents(limit):
    """Live documents holding a service-error read and no fields, least recently tried first.
    Never raises: a failure here must not take down the never-read half of the sweep."""
    if limit <= 0:
        return []
    try:
        from .decline import CASE_CLOSED_STATES
        errs = reduce(or_, [Q(vision_fields__error__startswith=p) for p in SERVICE_ERROR_PREFIXES],
                      Q(vision_fields__error=RATE_LIMITED))
        now = timezone.now()
        rows = (ApplicantDocument.objects
                .filter(errs, doc_type__in=SERVICE_RETRY_TYPES, superseded_at__isnull=True)
                .exclude(application__status__in=CASE_CLOSED_STATES)
                .filter(~Q(vision_fields__has_key=RETRY_UNTIL)
                        | Q(vision_fields__service_retry_until__gt=int(now.timestamp())))
                .order_by('vision_fields_run_at')[:limit])
        hour_ago = now - timedelta(hours=1)
        cap = getattr(settings, 'DOC_ASSIST_RATE_LIMIT_PER_HOUR', 15)
        fields = [d for d in rows if not d.vision_fields.get('fields')     # never re-read over a good read
                  and (d.vision_fields.get('error') != RATE_LIMITED
                       or ApplicantDocument.objects.filter(application_id=d.application_id,
                                                           vision_fields_run_at__gte=hour_ago).count() < cap)]
        # TD-390 (2026-10-25): ICs whose REQUIRED Gemini second opinion our outage skipped, in the
        # room left — same gate, same window (stamped at the failure), same open-case rule.
        ics = (ApplicantDocument.objects
               .filter(doc_type__in=('ic', 'parent_ic'), superseded_at__isnull=True,
                       vision_fields__has_key=IC_SECOND_OPINION_ERROR,
                       vision_fields__ic_second_opinion_until__gt=int(now.timestamp()))
               .exclude(application__status__in=CASE_CLOSED_STATES)
               .order_by('vision_run_at')[:max(limit - len(fields), 0)])
        return fields + list(ics)
    except Exception:                   # the never-read sweep must still run
        logger.exception('service-error retry selection failed; the never-read sweep continues')
        return []


#: #374 / ruling 2A: stamped on a row before its approval re-read, so the sweep tries each ONCE (a paid read);
#: a read that lands rebuilds `vision_fields` and drops it. After one try only an officer's Re-run reads it.
APPROVAL_TRIED = 'approval_reread_at'
#: The payslip families whose read must carry the approval fields: informal / declaration (ruling 2A), and
#: `govt` — #374's declaration forms were scored govt before salary_doc 1.2.0 and must be re-scored.
_APPROVAL_SLIP_FAMILIES = ('informal', 'declaration', 'govt')


def approval_unchecked_documents(limit):
    """#374 / owner ruling 2A (2026-10-28): live income documents on open cases whose stored read PREDATES
    the approver fields — every `income_support_doc`, and a payslip read as informal / declaration / govt —
    so the hourly sweep re-reads them even if the lead's manual re-read misses one; until then they count
    for nothing and the family is told "still checking". Only a row that HAS a read (the never-read half
    of the sweep owns the rest), never one this sweep already tried (`APPROVAL_TRIED`), oldest first.
    The re-read is the cockpit's Re-run core (`_reread`): a failed read never replaces the stored one,
    and TD-407 keeps a stored genuineness score the re-read did not freshly replace. Never raises."""
    if limit <= 0:
        return []
    try:
        from .decline import CASE_CLOSED_STATES
        rows = (ApplicantDocument.objects
                .filter(Q(doc_type='income_support_doc')
                        | Q(doc_type='salary_slip',
                            vision_fields__authenticity__doc_seen__in=_APPROVAL_SLIP_FAMILIES),
                        superseded_at__isnull=True, vision_fields__has_key='fields')
                .exclude(vision_fields__fields__has_key='has_stamp_or_signature')
                .exclude(vision_fields__has_key=APPROVAL_TRIED)
                .exclude(application__status__in=CASE_CLOSED_STATES)
                .order_by('uploaded_at')[:limit])
        return [d for d in rows if (d.vision_fields or {}).get('fields')]
    except Exception:                   # the rest of the sweep must still run
        logger.exception('approval re-read selection failed; the sweep continues')
        return []


def _reread_ic(doc):
    """TD-390: re-run the MyKad read (Vision OCR + the second opinion). Stamps the run time BEFORE
    reading so a killed read moves to the back of the queue; `vision.run_vision_for_document` never
    lets a failed second opinion replace a read one already completed. Returns the second opinion's
    error while it is still owed, else the read's own error ('' when it recovered)."""
    from ..vision import run_vision_for_document
    doc.vision_run_at = timezone.now()
    doc.save(update_fields=['vision_run_at'])
    result = run_vision_for_document(doc)
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    return vf.get(IC_SECOND_OPINION_ERROR) or result.get('error') or ''


def _reread(doc):
    """Re-read one document through the Re-run core; return the error the new read stored ('' when
    it recovered). Stamps the window and the read time BEFORE reading."""
    if doc.doc_type in ('ic', 'parent_ic'):
        return _reread_ic(doc)
    from ..reextract import reextract_document
    now = timezone.now()
    until = doc.vision_fields.get(RETRY_UNTIL) or int((now + SERVICE_RETRY_WINDOW).timestamp())
    doc.vision_fields = {**doc.vision_fields, RETRY_UNTIL: until, APPROVAL_TRIED: int(now.timestamp())}
    doc.vision_fields_run_at = now
    doc.save(update_fields=['vision_fields', 'vision_fields_run_at'])
    reextract_document(doc)
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    if is_ai_service_error(vf.get('error')) and RETRY_UNTIL not in vf:   # still down: keep the window
        doc.vision_fields = {**vf, RETRY_UNTIL: until}
        doc.save(update_fields=['vision_fields'])
    return vf.get('error') or ''


def run_service_retries(docs):
    """Re-read ``docs`` in order → ``(scanned, processed, errored)``. Skips the batch while Gemini
    reads are down, and stops at the first document that still fails on our side."""
    from .outage import gemini_reads_down
    if not docs or gemini_reads_down():
        return 0, 0, 0
    scanned = processed = errored = 0
    for doc in docs:
        scanned += 1
        try:
            err = _reread(doc)
        except Exception:               # one document must not stop the sweep
            logger.exception('service-error re-read failed for document %s', doc.id)
            err = 'reprocess_failed'
        if err:
            errored += 1
        else:
            processed += 1
        if is_ai_service_error(err):
            break                       # still down — the rest wait for the next run, unbilled
    return scanned, processed, errored
