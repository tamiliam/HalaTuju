"""A reviewer's request for RESULTS, by name (third results route S4, 2026-10-27; org request #37).

#37: "I can ask for the student to upload their SPM results but not … STPM or metrikulasi or assasi
results." The reviewer's "Request a document" now offers "SPM results slip" and "STPM /
Matriculation / Asasi / Diploma results" (one choice per kind). The request travels as an ordinary
officer ResolutionItem (`resolution.add_officer_item`) with `doc_type` 'results_slip' or
'higher_results'; a higher-results request also carries the kind in `params['results_kind']`, so:

* the student's Action-Centre upload for it lands in the `higher_results` slot WITH that kind
  (`results_route.upload_kind`, keyed on the upload's `request_code`) — even for a student whose
  results page holds only SPM, whose own uploads would carry no kind;
* the upload closes the request (`resolution.resolve_doc_items_for_upload`) only when it ANSWERS it
  (`answers`): an STPM result put into an "SPM results slip" request, or an SPM slip put into a
  higher-results request, scans clean and is kept, but the request stays open for the reviewer.

⚠ NO AUTOMATIC SPM ASK (owner ruling D9): nothing here raises a request by itself. The one system
Check-2 ask for RESULTS is for owed HIGHER results (`higher_owed`, #388, owner option A,
2026-10-27) — never for an SPM slip. And the officer's own gate is unchanged:
a request is accepted only while `services.officer_requests_state` is 'open' (request #40).
"""
from __future__ import annotations

from .wrong_slip import HIGHER_KINDS


def request_params(application, doc_type, results_kind):
    """``(extra_params, error_code)`` for an officer document request. A `higher_results` request
    needs a kind: the one the reviewer chose, else the one the application already shows (the
    results held, when tertiary; else the kind detected on the SPM card's document). ``({}, '')``
    for every other document type — a kind sent with one is ignored, as before."""
    if doc_type != 'higher_results':
        return {}, ''
    kind = (results_kind or '').strip().lower()
    if not kind:
        from . import results_route
        from .verdict_engine import _latest_doc
        from .wrong_slip import higher_kind
        kind = results_route.held_kind(application) or higher_kind(
            _latest_doc(application, 'results_slip'))
    if kind not in HIGHER_KINDS:
        return {}, 'results_kind_required'
    return {'results_kind': kind}, ''


def requested_kind(application, request_code) -> str:
    """The kind an OPEN officer higher-results request named, or '' (no such open request, or none
    named). A resolved or waived request carries no kind onto a later upload (review finding 5)."""
    if not request_code or application is None:
        return ''
    item = application.resolution_items.filter(source='officer', code=request_code, status='open').first()
    kind = ((item.params or {}).get('results_kind') or '') if item is not None else ''
    return kind if kind in HIGHER_KINDS else ''


def answers(doc, item) -> bool:
    """Does this clean upload answer this RESULTS item? A 'results_slip' item — the officer's OR the
    system's (`results_slip_missing`, review finding 2) — is not answered by a higher result, nor an
    officer's higher-results request by an SPM slip (each document is kept where it was put; the
    reviewer sees it and the item stays open), nor a higher-results ask by a non-final page (M4b ruling
B: a semester slip, the portal page). The system's Check-2 ask for owed higher results
    (`higher_owed.ASK_CODE`, #388) follows the officer's rule. Every other item → True (unchanged)."""
    if item.doc_type == 'results_slip':
        from .wrong_slip import fills_spm_slot
        return fills_spm_slot(doc)
    if getattr(item, 'source', '') not in ('officer', 'check2'):   # check2: #388's ask (higher_owed)
        return True
    if item.doc_type == 'higher_results' and doc.doc_type == 'higher_results':
        from .higher_results import answers_higher_ask      # not an SPM slip, and the FINAL result (SF3)
        return answers_higher_ask(doc)
    return True
