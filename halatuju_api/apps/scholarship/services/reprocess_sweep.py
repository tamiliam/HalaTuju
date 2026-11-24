"""
The hourly self-heal sweep: re-read documents whose upload-time read never ran.

Moved here VERBATIM from `services/blockers.py` at sprint #78 (2026-11-23), moves only, so the gate
file had room for the owed-line split. `blockers` re-exports every name, so
`services.blockers.<name>` and `services.<name>` still resolve as before.
"""
from django.utils import timezone

from ..models import ApplicantDocument


#: TD-151 (3), 2026-10-02 — the READ documents the submission gates and the verdict depend on, swept
#: like the IC when an upload's read never ran: the slip and offer (identity / academic / pathway
#: blockers), the income-cluster proofs (`member_income_evidenced`, `usable_salary_slip`) and the two
#: relationship documents. Stuck = BOTH run stamps NULL (`run_vision_match_for_document` always stamps
#: `vision_run_at`, field extraction `vision_fields_run_at`) AND `vision_fields` EMPTY — a document
#: that carries any stored read (one made before either stamp existed included) is never re-read by
#: the sweep, so nothing it holds can be overwritten (review F1) — and never a superseded one.
_SELF_HEAL_READ_TYPES = ('results_slip', 'higher_results', 'offer_letter', 'salary_slip', 'epf', 'str',
                         'birth_certificate', 'guardianship_letter', 'income_support_doc')
#: Written on a row BEFORE the sweep reads it; a completed read overwrites it. Left on a row, it
#: means the process died mid-read — the sweep will not try again; an officer's Re-run can.
REPROCESS_ATTEMPTED = 'reprocess_attempted'


def _stuck_unread_documents(limit):
    from django.db.models import Exists, F, OuterRef, Q
    from ..results_review import SLIP_REQUEST_CODE
    # A2.3 review: an IC that is superseded AND has a later document over it (it was replaced, or
    # its read was dropped because a newer upload in the slot was decided) is not stuck — reading
    # it would be a paid Vision call nobody's verdict uses. A staged IC still the slot's newest
    # attempt keeps its sweep, as before.
    later_in_slot = ApplicantDocument.objects.filter(
        application_id=OuterRef('application_id'), doc_type=OuterRef('doc_type'),
        household_member=OuterRef('household_member'), request_code=OuterRef('request_code'),
        id__gt=OuterRef('id'))
    replaced_ic = Q(doc_type__in=('ic', 'parent_ic'), superseded_at__isnull=False) & (
        Q(superseded_by_id__gt=F('id')) | Q(Exists(later_in_slot)))
    return list(ApplicantDocument.objects
                .filter(Q(doc_type__in=('ic', 'parent_ic'), vision_run_at__isnull=True)
                        | Q(doc_type__in=_SELF_HEAL_READ_TYPES, vision_run_at__isnull=True,
                            vision_fields_run_at__isnull=True, superseded_at__isnull=True,
                            vision_fields={}))
                .exclude(request_code=SLIP_REQUEST_CODE)   # S4a: a results slip is never machine-read
                # A2.3: a queued upload is not stuck — the read-documents queue owns it (a 'failed'
                # one, read three times without finishing, is the sweep's again).
                .exclude(read_state='pending')
                .exclude(replaced_ic)
                .order_by('uploaded_at')[:limit])


def reprocess_unread_ic_documents(limit=100, dry_run=False, time_budget=None):
    """Self-heal IC / parent_ic documents stuck UN-PROCESSED (``vision_run_at`` is NULL).

    ``run_vision_for_document`` never raises and ALWAYS stamps ``vision_run_at``, so a NULL
    means Vision was never run on the doc — a silent upload-time pipeline failure with no
    retry. That strands the student behind a false ``ic_service_down`` ("document-check
    service unavailable") consent block (``ic_identity_blockers`` line ~1170) and a "couldn't
    read the IC" cockpit verdict, even though the service is up. This re-runs Vision on every
    such doc — once each: after a run, ``vision_run_at`` is set, so it's never re-picked (cost
    is one Vision read per stuck doc). Defensive: if a run ever does raise, we stamp an outcome
    so it can't loop. Returns ``{scanned, processed, errored}``.

    TD-151 (3): the same sweep now covers the other read documents a submission gate depends on
    (``_SELF_HEAL_READ_TYPES``), re-read through ``reextract.reextract_document`` — the one
    dispatcher the cockpit's Re-run uses. ``dry_run`` counts what WOULD be re-read, per type, and
    reads nothing (``{scanned, by_type}``) — run it before the first deploy to size the backlog.

    2026-10-24: the remaining batch room also re-reads live documents whose stored read is OUR
    service failing (``read_retry``: same Re-run core, each at most once per run — the list is
    taken BEFORE any read, so a read that fails in this run is not retried in it).

    A2.2 / TD-518 (2026-11-07): ``time_budget`` (seconds; None = no budget) stops the run CLEANLY between
    documents once it is spent, so one run never meets the service's 300 s request limit. The queue IS the
    cursor: every document is stamped BEFORE it is read (above; ``read_retry`` stamps its own), so a stamped
    one leaves its pool and the next run starts at the first one not yet reached — none skipped, none read
    twice. The one pool that could re-pick its own failures (approval reads inside their 72-hour window)
    resumes after the last document it reached (``read_retry.approval_cursor``). A stop adds
    ``stopped_early`` and ``left`` to the result; a full run returns the three counts as before.
    """
    import time
    from ..vision import run_vision_for_document
    from ..reextract import reextract_document
    from .read_retry import (approval_unchecked_documents, run_service_retries, service_error_documents,
                             approval_cursor_save)
    deadline = None if time_budget is None else time.monotonic() + time_budget
    stuck = _stuck_unread_documents(limit)
    retry = service_error_documents(limit - len(stuck))
    n_service = len(retry)
    retry += approval_unchecked_documents(limit - len(stuck) - len(retry))   # #374 / ruling 2A
    if dry_run:
        by_type = {}
        for doc in stuck + retry:
            by_type[doc.doc_type] = by_type.get(doc.doc_type, 0) + 1
        return {'scanned': len(stuck) + len(retry), 'by_type': by_type}
    scanned = processed = errored = 0
    stopped = False
    for doc in stuck:
        if deadline is not None and time.monotonic() >= deadline:
            stopped = True
            break
        scanned += 1
        # STAMP BEFORE READING (2026-10-02). A memory kill is not an exception: one 2 MB PDF took
        # the instance past 2 GiB mid-read, nothing below ran, and the same row was re-picked every
        # hour. Only the two stamp/error columns — never `vision_fields` (F1 above).
        prior_error = doc.vision_error or ''
        doc.vision_error, doc.vision_run_at = REPROCESS_ATTEMPTED, timezone.now()
        doc.save(update_fields=['vision_error', 'vision_run_at'])
        try:
            if doc.doc_type in ('ic', 'parent_ic'):
                err = run_vision_for_document(doc).get('error')
            else:
                reextract_document(doc)
                err = None
            if doc.vision_error == REPROCESS_ATTEMPTED:   # a read that wrote no outcome of its own
                doc.vision_error = prior_error
                doc.save(update_fields=['vision_error'])
            err = err if err is not None else doc.vision_error
            errored += 1 if err else 0
            processed += 0 if err else 1
        except Exception:
            errored += 1
            if doc.vision_error in ('', REPROCESS_ATTEMPTED):
                doc.vision_error = 'reprocess_failed'
            doc.vision_run_at = timezone.now()
            doc.save(update_fields=['vision_error', 'vision_run_at'])
    left = len(stuck) - scanned
    if stopped:
        s = p = e = 0                    # out of time: the retries wait for the next run, untouched
        left += len(retry)
    else:
        out = {}
        s, p, e = run_service_retries(retry, deadline=deadline, out=out)
        if out.get('stopped'):
            stopped, left = True, left + len(retry) - out['reached']
        approval_cursor_save(retry[n_service:][:max(s - n_service, 0)], stopped)
    result = {'scanned': scanned + s, 'processed': processed + p, 'errored': errored + e}
    if stopped:
        result.update(stopped_early=True, left=left)
    return result
