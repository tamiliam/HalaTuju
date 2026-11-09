"""The re-ask circuit-breaker: stamp a failed attempt on the open doc-request items."""
import logging

from ..models import ApplicantDocument
from ..read_errors import is_ai_service_error


def _note_unresolved_attempts(app, doc, stale_ids, kept_previous):
    """Human-aware re-ask (#83, owner 2026-07-08). After an upload has had its chance to resolve
    things (sync + resolve_doc_items_for_upload ran), any doc-request for THIS doc type that is
    STILL OPEN means the upload didn't do the job — the student re-sent the same file, or a
    different-but-still-wrong one. Stamp the attempt onto the open items' params so the Action
    Centre acknowledges it like a human would, instead of repeating the original ask verbatim:
      attempts            — how many uploads have failed to clear this request
      attempt_same_file   — the latest one was byte-identical-looking (same name + size) to a copy
                            already superseded in this slot
      attempt_rejected    — the STR keep-better guard kept the previous proof live
    Best-effort; never blocks the upload response. OUR outage deferring the read is no attempt."""
    if is_ai_service_error((doc.vision_fields or {}).get('error')):
        return
    try:
        same_file = bool(
            stale_ids and (doc.original_filename or '')
            and ApplicantDocument.objects.filter(
                id__in=stale_ids, original_filename=doc.original_filename,
                size=doc.size or 0).exists())
        for item in _open_doc_request_items(app, doc.doc_type):   # the circuit-breaker's own set
            p = dict(item.params or {})
            p['attempts'] = int(p.get('attempts') or 0) + 1
            p['attempt_same_file'] = same_file
            p['attempt_rejected'] = bool(kept_previous)
            item.params = p
            item.save(update_fields=['params'])
    except Exception:  # noqa: BLE001 — a stamping failure must never break the upload
        logging.getLogger(__name__).warning(
            'attempt-stamping failed for app %s doc %s', app.id, doc.id, exc_info=True)


def _open_doc_request_items(app, doc_type):
    """The OPEN doc-request resolution items for this ``doc_type`` — matched by CODE via
    ``CODE_TO_TICKET`` + ``DOC_SPECS`` (the same way ``_note_unresolved_attempts`` finds them, so the
    circuit-breaker reads/writes exactly the items the attempt counter lives on)."""
    from ..resolution import CODE_TO_TICKET
    from ..check2_queries import DOC_SPECS
    codes = {c for c, s in CODE_TO_TICKET.items() if s.get('doc_type') == doc_type}
    codes |= {c for c, s in DOC_SPECS.items() if s.get('doc_type') == doc_type}
    return app.resolution_items.filter(code__in=codes, status='open')


def _stage_attempts_exhausted(app, doc, settings):
    """True when THIS not-usable upload is the K-th failed attempt for this doc_type — time to
    stop looping the student. Reads the PRE-increment count (``_note_unresolved_attempts`` stamps
    the +1 AFTER the decision, so we count prior failures).

    K is the APPLICATION's organisation's `doc_stage_max_attempts` (Org Config Sprint E). The
    `settings` argument is kept — callers pass it and it still carries the doc-assist knobs —
    but it is no longer where this number comes from.
    """
    if is_ai_service_error((doc.vision_fields or {}).get('error')):
        return False                    # OUR outage deferred the read — not the student's attempt
    from apps.courses import org_config
    k = org_config.value(app.owning_organisation, 'doc_stage_max_attempts')
    prior = max((int((i.params or {}).get('attempts') or 0)
                 for i in _open_doc_request_items(app, doc.doc_type)), default=0)
    return (prior + 1) >= k


def _flag_needs_officer_eye(app, doc):
    """Stamp ``needs_officer_eye`` on the open doc-request items for this doc_type (``params``
    JSONField — NO migration) so the Action Centre swaps the re-upload loop for a calm "we're
    reviewing this with our team" and the cockpit shows a hold chip. A HOLD-for-human, never an
    auto-resolve. Best-effort; never breaks the upload."""
    try:
        from django.utils import timezone as _tz
        for it in _open_doc_request_items(app, doc.doc_type):
            p = dict(it.params or {})
            p['needs_officer_eye'] = True
            p.setdefault('escalated_at', _tz.now().isoformat())
            it.params = p
            it.save(update_fields=['params'])
    except Exception:  # noqa: BLE001 — never break the upload
        logging.getLogger(__name__).warning(
            'needs_officer_eye flag failed for app %s doc %s', app.id, doc.id, exc_info=True)
