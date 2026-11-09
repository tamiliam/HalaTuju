"""Check-2 document requests that wait while OUR outage has a document unread.

2026-10-24 (the AI-outage sprint, round-3 review): a document whose read our service deferred
(`read_errors.deferred_by_us`: `review_manually`, no fields) is on file but NOT judged. For the
requests below, both of the sync's moves would then be wrong — RAISING one asks the student again
for something she sent, and RESOLVING one counts an unscanned document as a pass (and past the
Completed stage, or after the sweep's 72 hours, nothing would re-open it). So while such a copy is
live the sync leaves the request exactly as it is; once the read lands the normal rule applies.

The gap readers themselves are untouched (a deferred read does not satisfy them): only the sync's
create / re-open / resolve step consults this. Lives outside `check2_queries.py`, which sits at its
line allowance on the oversize ledger.

Owner ruling 2A (2026-10-28, #374): an INFORMAL income document read before the approver rule existed
(`income_declaration.approval_unchecked`) is the same kind of "ours to finish" — it does not count, and
the income asks wait for its live re-read rather than ask the family again for what she sent.

A2.8a (2026-11-09):
* TD-397 — a deferred copy's hold ENDS when the sweep gives up: it holds only while the sweep's window
  is open (`read_errors.service_retry_open`). After that the request falls back to the ordinary ask or
  the officer, exactly as if the copy were any other unjudged document. An UNCHECKED informal document
  keeps holding (lead ruling B, A2.8a review): once the sweep's one approval re-read is past its window
  (`income_declaration.approval_sweep_gave_up`) the family is not asked again for what she sent; the
  officer's drawer reason says to check it by eye instead.
* TD-398 — an income ask's RESOLVE is not held when a live letter in its slots (that member's, for a
  member's ask) READ FINE (`_read_fine`): the income readers count only read documents, so the resolve
  comes from that letter, and the deferred one can only add to it. A raise or re-open is still held.
"""
from .document_snapshot import live_docs
from .read_errors import deferred_by_us, service_retry_open

#: The income asks an UNCHECKED informal document holds — on either income slot, whichever the spec names.
_INCOME_ASKS = ('father_income_proof_missing', 'mother_income_proof_missing', 'guardian_income_proof_missing',
                'brother_income_proof_missing', 'sister_income_proof_missing',
                'declared_income_evidence_missing')
_INCOME_SLOTS = ('salary_slip', 'income_support_doc')

#: The Check-2 doc requests a deferred read holds. Each one's document type is read from the sync's
#: own `DOC_SPECS`, never restated here.
HELD_WHILE_DEFERRED = ('water_bill_recheck', 'electricity_bill_recheck', 'school_leaving_cert_missing',
                       'semester_result_missing', 'higher_results_requested',     # #388 (`higher_owed.ASK_CODE`)
                       'higher_results_declare_requested',                        # `higher_owed.DECLARE_ASK_CODE`
                       *_INCOME_ASKS)


def held_doc_requests(application, doc_specs, existing, wanted):
    """The codes in `HELD_WHILE_DEFERRED` the sync would CHANGE this pass (raise, re-open or
    resolve — read off `existing` items and the `wanted` set exactly as the sync reads them) and
    whose document type has a live copy our outage deferred. ⚠ Both callers are query-budgeted
    (`test_query_budgets`): it reads nothing unless such a change is pending, and then reads the
    live documents once, through the document snapshot when one is open (the cockpit's)."""
    def changes(code):
        item = existing.get(code)
        if code in wanted:
            return item is None or item.status == 'resolved'
        return item is not None and item.status == 'open'
    from .income_declaration import approval_unchecked
    codes = [c for c in HELD_WHILE_DEFERRED if changes(c)]
    if not codes:
        return set()

    def slots(code):
        return {doc_specs[code]['doc_type'], *(_INCOME_SLOTS if code in _INCOME_ASKS else ())}

    def holds(d):
        vf = getattr(d, 'vision_fields', None)
        if deferred_by_us(vf):                       # TD-397: only while the sweep will still read it
            return service_retry_open(vf)
        return approval_unchecked(d)                 # ruling B: past the sweep, the officer, not the family

    def _read_fine(d):
        vf = getattr(d, 'vision_fields', None)
        return (isinstance(vf, dict) and bool(vf.get('fields')) and vf.get('student_verdict') != 'unreadable'
                and not approval_unchecked(d))

    def read_letter(code, docs):                     # TD-398: a resolve that a letter already read for
        member = doc_specs[code].get('member')
        return (code in _INCOME_ASKS and code not in wanted
                and any(d.doc_type in slots(code) and _read_fine(d)
                        and (not member or getattr(d, 'household_member', '') == member) for d in docs))
    types = tuple(set().union(*(slots(c) for c in codes)))
    docs = list(live_docs(application, doc_types=types))   # snapshot-aware
    deferred = {d.doc_type for d in docs if holds(d)}
    return {c for c in codes if slots(c) & deferred and not read_letter(c, docs)}
