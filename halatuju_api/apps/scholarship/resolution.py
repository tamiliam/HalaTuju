"""
Resolution tickets (Sprint 3) — turn the verification verdict's unresolved items
into discrete, self-serviceable actions (the IBKR model; see
docs/scholarship/verification-verdict-plan.md).

``sync_resolution_items(application)`` is idempotent: at most one
``source='system'`` ResolutionItem per (application, code), created once and
auto-resolved the moment its code leaves ``verdict.unresolved`` (e.g. the student
uploads the STR letter → the income gap clears → the ticket closes). It never
re-nags an answered item and never touches officer-raised items. The one re-ask is the
student's own deletion of the document (``after_document_deleted``, TD-079).

``CODE_TO_TICKET`` maps the *ticketable* verdict codes → ``{fact, kind, doc_type}``.
Codes NOT in the map are deliberately excluded from the student queue (confirmed
with the user 2026-06-02):
  - ``ic_service_down``        — transient OCR-service failure; auto-retries, and
                                 escalates to ``ic_unreadable`` (a doc ticket) if
                                 persistent. Not the student's to fix.
  - ``grades_unverified``      — a machine "not read yet" state; on re-OCR it
                                 becomes a green or a concrete ticket
                                 (missing-subjects / grade-mismatch). Officer
                                 eyeball meanwhile.
  - ``str_present_unverified`` — the student has already uploaded STR; the officer
                                 confirms the household match (officer-side).
"""
from django.db import IntegrityError
from django.utils import timezone

from .genuineness.offer_issuers import hold_for_officer, officer_must_close, release_not_checked_holds
from .income_str_ownership import hold_if_str_unmatched, str_upload_unmatched
from .higher_results import TICKETS as _HIGHER_TICKETS, match_verdict as _higher_match_verdict  # S3a
from .models import ResolutionItem
from .resolution_doc_match import DOC_MATCH_CHECKS   # one check per document type (A3.4)
from .results_requests import answers as results_answers      # S4 (#37)
# The post-award tasks (bank details, Vircle) moved to `resolution_postaward` in S4; re-exported.
from .resolution_postaward import (
    BANK_CAPTURE_STATES, BANK_DETAILS_CODE, VIRCLE_CODE, VIRCLE_SETUP_STATES,
    sync_bank_details_item, sync_vircle_item,
)
from .verdict_engine import build_verdict

CODE_TO_TICKET = {
    # Identity
    'ic_missing':             {'fact': 'identity', 'kind': 'doc', 'doc_type': 'ic'},
    'ic_unreadable':          {'fact': 'identity', 'kind': 'doc', 'doc_type': 'ic'},
    'nric_mismatch':          {'fact': 'identity', 'kind': 'confirm'},
    'name_mismatch':          {'fact': 'identity', 'kind': 'confirm'},
    # NB: address_state_mismatch is deliberately NOT ticketable — the IC's registered state is the
    # least-current address on file, not an identity caveat (see verdict_engine._verdict_identity).
    # It is only a pre-interview flag ("ask which is current"), never a caveat the student resolves.
    # Academic
    'results_slip_missing':       {'fact': 'academic', 'kind': 'doc', 'doc_type': 'results_slip'},
    'results_slip_unreadable':    {'fact': 'academic', 'kind': 'doc', 'doc_type': 'results_slip'},
    'results_slip_name_mismatch': {'fact': 'academic', 'kind': 'doc', 'doc_type': 'results_slip'},
    'academic_missing_subjects':  {'fact': 'academic', 'kind': 'confirm'},
    'academic_extra_subjects':    {'fact': 'academic', 'kind': 'confirm'},   # request #62
    'academic_grade_mismatch':    {'fact': 'academic', 'kind': 'confirm'},
    # #71 (owner 2026-07-08): letter + Malay band AGREE → the typed grade is confidently wrong.
    'academic_grade_band_mismatch': {'fact': 'academic', 'kind': 'confirm'},
    **_HIGHER_TICKETS,
    # Income
    'income_proof_missing': {'fact': 'income', 'kind': 'doc', 'doc_type': 'str'},
    # Income Check-1 (item 3: earner identity + relationship). `income_unverified_needs_interview`
    # is deliberately ABSENT — it's an officer/interview flag, not a student to-do.
    'income_earner_undeclared':     {'fact': 'income', 'kind': 'confirm'},
    'earner_ic_missing':            {'fact': 'income', 'kind': 'doc', 'doc_type': 'parent_ic'},
    'earner_ic_unreadable':         {'fact': 'income', 'kind': 'doc', 'doc_type': 'parent_ic'},
    'birth_cert_missing':           {'fact': 'income', 'kind': 'doc', 'doc_type': 'birth_certificate'},
    # #27 (owner 2026-07-08): the doc in the BC/letter slot is NOT that kind of document (wrong-type
    # genuineness) — a required relationship proof is effectively absent → auto-ask a re-upload.
    'birth_cert_not_genuine':       {'fact': 'income', 'kind': 'doc', 'doc_type': 'birth_certificate'},
    'guardianship_letter_not_genuine': {'fact': 'income', 'kind': 'doc', 'doc_type': 'guardianship_letter'},
    # #23 (owner 2026-09-08): the doc IS on file and the right kind, but nothing could be read off it
    # (it used to score like a document that checked out). Not *_not_genuine: "we could not read
    # yours". The `_unreadable` suffix puts both in STUDENT_DOC_REQUEST_CODES automatically.
    'birth_cert_unreadable':           {'fact': 'income', 'kind': 'doc', 'doc_type': 'birth_certificate'},
    'guardianship_letter_unreadable':  {'fact': 'income', 'kind': 'doc', 'doc_type': 'guardianship_letter'},
    'birth_cert_mismatch':          {'fact': 'income', 'kind': 'confirm'},
    'father_patronymic_mismatch':   {'fact': 'income', 'kind': 'confirm'},
    'guardianship_letter_missing':  {'fact': 'income', 'kind': 'doc', 'doc_type': 'guardianship_letter'},
    # STR document checks (Check-1 income, STR route): a stale/rejected STR no longer
    # proves B40 (upload a current one or explain); a recipient that isn't the earner.
    'str_not_current':              {'fact': 'income', 'kind': 'doc', 'doc_type': 'str'},
    'str_recipient_mismatch':       {'fact': 'income', 'kind': 'confirm'},
    # Pathway
    'offer_letter_missing': {'fact': 'pathway', 'kind': 'doc', 'doc_type': 'offer_letter'},
    'offer_not_official':  {'fact': 'pathway', 'kind': 'doc', 'doc_type': 'offer_letter'},
    'offer_unreadable':    {'fact': 'pathway', 'kind': 'doc', 'doc_type': 'offer_letter'},
    'offer_no_identity':   {'fact': 'pathway', 'kind': 'doc', 'doc_type': 'offer_letter'},
    'offer_name_mismatch': {'fact': 'pathway', 'kind': 'doc', 'doc_type': 'offer_letter'},
    # NOTE: 'pathway_confirm' AND 'pathway_undeclared' are intentionally NOT here. Both are STUDENT
    # queries routed through Check 2 (source='check2', CHECK2_STUDENT_QUERIES_ENABLED) that ride the
    # query email — see check2_queries._sync_pathway_confirm. 'pathway_confirm' = the one-tap "is this
    # offer your final chosen pathway?"; 'pathway_undeclared' = an offer we can't pin (a PISMP offer
    # with no aliran) → the student picks the exact course on the profile page (owner 2026-07-15).
    # As a 'system' item either would be hidden from the student queue; only the officer would see it.
}

# The "review assistant" (Check 2) asks the STUDENT to upload a compulsory document straight
# in the Action Centre (flag-gated, with an Upload button). This matters because a post-submit
# student is form-LOCKED — the Action Centre is their ONLY surface, so anything hidden here is
# something they literally cannot fix. Two classes qualify:
#   - MISSING (`*_missing`): the doc was never uploaded.
#   - UN-USABLE but re-uploadable (`*_unreadable`, plus `offer_no_identity` = readable but shows
#     no name/IC, and `str_not_current` = a stale STR): the system genuinely couldn't read/accept
#     it, so the student replaces it with a clearer / correct / current copy.
# The NAME-MISMATCH doc class (`offer_name_mismatch` / `results_slip_name_mismatch`) is
# deliberately EXCLUDED — that's a verification JUDGEMENT (often a romanisation false positive,
# and not something to auto-coach a wrong-doc uploader on), so the reviewer raises it explicitly
# when warranted. (Supersedes the 2026-06-10 "hide all bad-doc tickets" rule, which left a
# form-locked student with no way to replace a doc the system couldn't read — the inline Gopal
# coaching it deferred to lives on the now-unreachable Documents tab.)
_STUDENT_DOC_FIXABLE_EXTRA = frozenset({'offer_no_identity', 'str_not_current'})
STUDENT_DOC_REQUEST_CODES = frozenset(
    code for code, spec in CODE_TO_TICKET.items()
    if spec.get('kind') == 'doc' and (
        code.endswith('_missing') or code.endswith('_unreadable')
        or code in _STUDENT_DOC_FIXABLE_EXTRA))


def _ticketable_unresolved(application):
    """{code: {fact, params}} for every unresolved verdict item that maps to a
    student ticket (i.e. is in CODE_TO_TICKET)."""
    out = {}
    for fact in build_verdict(application):
        for item in fact['unresolved']:
            code = item['code']
            if code in CODE_TO_TICKET:
                out[code] = {'fact': fact['fact'], 'params': item.get('params', {})}
    # #388: while Check 2's ask for owed higher results is open it is the ONE Action-Centre card for
    # that document — S3's higher-results tickets are not raised beside it (an open one auto-resolves).
    from .higher_owed import ask_owns_higher_tickets
    if any(CODE_TO_TICKET[c].get('doc_type') == 'higher_results' for c in out)             and ask_owns_higher_tickets(application):
        out = {c: v for c, v in out.items() if CODE_TO_TICKET[c].get('doc_type') != 'higher_results'}
    return out


def open_items(application):
    return list(application.resolution_items.filter(status='open').order_by('-created_at'))


def sync_resolution_items(application):
    """Reconcile SYSTEM items with the current verdict; return the open items
    (system + officer). Idempotent and race-safe.

      - ticketable code with no system item yet  → create an open item
      - OPEN system item whose code has cleared   → auto-resolve it
      - already-resolved system items             → left as-is (no re-nag; a document
        DELETION re-opens its own ticket — ``after_document_deleted``, TD-079)
      - officer items                             → untouched

    **Check 2 gate:** student-facing queries only exist AFTER the student submits
    their post-shortlist ``/application`` (consent = ``profile_completed_at``).
    Before that (just shortlisted, still filling in Step-4) there are NO queries —
    the student works through the tabs normally. This enforces the intended
    pipeline ``Apply → Shortlist → Consent → Check 2 → Query`` (not the premature
    ``Apply → Shortlist → Query``). The officer still sees gaps via the verdict;
    officer-raised items also wait for completion. See
    ``docs/scholarship/application-processing-pipeline-plan.md``.
    """
    if application.profile_completed_at is None:
        return ResolutionItem.objects.none()
    # The MACHINE may only ask during the Completed stage (owner, 2026-07-13). From `interviewing`
    # onward the case belongs to a human — the reviewer asks, the system doesn't. Was gated on
    # `querying_locked`, which only closed at `interviewed`, so a student mid-interview could still
    # be sent fresh auto-generated questions while their reviewer was working the case.
    # Only the CREATE is gated: the housekeeping below still auto-resolves an open item once its
    # gap clears, at EVERY stage, and an item already open stays open and answerable.
    from .services import auto_queries_allowed
    may_ask = auto_queries_allowed(application)
    wanted = _ticketable_unresolved(application)
    existing = {r.code: r for r in application.resolution_items.filter(source='system')}
    now = timezone.now()

    raised_student_visible = False
    for code, info in wanted.items():
        if code in existing or not may_ask:
            continue
        spec = CODE_TO_TICKET[code]
        try:
            ResolutionItem.objects.create(
                application=application, source='system', code=code,
                fact=info['fact'], params=info['params'],
                kind=spec['kind'], doc_type=spec.get('doc_type', ''),
            )
            # A system item is shown to the student only if it's a doc-request in
            # STUDENT_DOC_REQUEST_CODES (see views.ResolutionItemListView._student_visible) —
            # so only those should trigger a re-notify.
            if code in STUDENT_DOC_REQUEST_CODES:
                raised_student_visible = True
        except IntegrityError:
            pass  # created concurrently by another request — fine

    for code, item in existing.items():
        # ONLY verdict-derived tickets (codes in CODE_TO_TICKET) auto-resolve when their gap
        # clears. Other source='system' items — notably the post-award bank-details task,
        # which is owned by sync_bank_details_item and is NOT a verdict gap — must never be
        # swept here, or every Action-Centre reload would silently mark the bank task "done"
        # (it isn't in `wanted`, which only holds CODE_TO_TICKET codes). (Bug fix 2026-06-29.)
        if item.status == 'open' and code in CODE_TO_TICKET and code not in wanted \
                and not hold_if_str_unmatched(application, item):    # TD-409, ruling A
            item.status = 'resolved'
            item.resolved_by = 'system'
            item.resolved_at = now
            item.save(update_fields=['status', 'resolved_by', 'resolved_at'])

    if raised_student_visible:
        # A new student-visible doc-request appeared after the one-time notify → re-announce it
        # (local import: services imports this module, so avoid a circular import at module load).
        from .services import bump_query_notify_on_new_item
        bump_query_notify_on_new_item(application)

    return open_items(application)


def after_document_deleted(application, doc_type):
    """TD-079 (2026-10-04): the student REMOVED a document — re-ask for it, then reconcile.

    The no-re-nag rule keeps a RESOLVED system ticket resolved when its gap returns, so deleting
    the offer letter that closed ``offer_letter_missing`` left the gap on the officer's verdict and
    nothing in the student's queue. (A document the submitted bar holds — the IC, say — un-submits
    her instead, and the form asks: ``revert_if_profile_incomplete``.) A deletion is the student's own act on that very slot, so here — and only
    here, never on a read — a RESOLVED (not waived, not officer-resolved) student-visible document ticket of that
    ``doc_type`` whose gap is back is RE-OPENED and re-notified, exactly as Check 2 re-opens a gap
    that re-fires. Gated like a create (``auto_queries_allowed``): past Completed nobody is asked."""
    from .services import auto_queries_allowed
    if auto_queries_allowed(application):
        back = [c for c in _ticketable_unresolved(application)
                if c in STUDENT_DOC_REQUEST_CODES and CODE_TO_TICKET[c].get('doc_type') == doc_type]
        # Only a ticket the SYSTEM or the STUDENT closed: an officer's hand resolution is a
        # decision ("awaiting UPU"), and its typed reason is the audit trail — kept (review fix).
        reopened = application.resolution_items.filter(
            source='system', status='resolved', resolved_by__in=('system', 'student'),
            code__in=back,
        ).update(status='open', resolved_by='', resolved_at=None, resolution_doc=None)
        if reopened:
            from .services import bump_query_notify_on_new_item
            bump_query_notify_on_new_item(application)
    sync_resolution_items(application)


def resolve_item(item, *, text='', doc=None, by='student'):
    """Close an item by the student's response — a typed explanation/confirmation
    and/or an uploaded document. (For 'doc' items the upload usually clears the
    verdict gap and sync would auto-resolve anyway; recording the explicit
    response keeps the audit trail and closes confirm/explanation items whose
    underlying verdict signal legitimately persists — e.g. the OCR still
    mismatches but the student has confirmed their NRIC.) Idempotent."""
    item.status = 'resolved'
    if text:
        item.resolution_text = text
    if doc is not None:
        item.resolution_doc = doc
    item.resolved_by = by
    item.resolved_at = timezone.now()
    item.save(update_fields=['status', 'resolution_text', 'resolution_doc',
                             'resolved_by', 'resolved_at'])
    return item


def add_officer_item(application, *, kind, prompt, admin_email, doc_type='', fact='other',
                     household_member='', actor=None):
    """Officer raises a manual ticket — the structured successor to
    ``info_request_note``. Codes are synthetic ``officer_<n>``. For a per-person
    document request (e.g. the father's salary slip), ``household_member`` is stashed
    in ``params`` so the student's upload tags the right (doc_type, member) slot —
    closing the salary-route Action-Centre tagging gap without a schema change.

    ``actor`` (the officer; the view passes it) gets a `query_raised` row on their own activity list
    (common profile S3) — the item's id and kind, never its prompt."""
    n = application.resolution_items.filter(source='officer').count() + 1
    params = {'household_member': household_member} if household_member else {}
    item = ResolutionItem.objects.create(
        application=application, source='officer', code=f'officer_{n}',
        fact=fact or 'other', kind=kind, doc_type=doc_type, prompt=prompt or '',
        params=params, created_by=admin_email or '',
    )
    from . import staff_activity
    staff_activity.record(actor, staff_activity.QUERY_RAISED, application,
                          meta=lambda: {'item': item, 'kind': kind})
    return item


def doc_match_verdict(doc):
    """The Action Centre's per-document verdict for an uploaded file:
    ``'mismatch'`` (a confirmed red), ``'unreadable'`` (a bad/blurry scan),
    ``'pending'`` (not scanned yet — hold the task), or ``'ok'`` (accept — resolve
    the task).

    Reads the same person-red keys as the consent gate (``services.document_red_blockers``) from
    ``doc_red_keys.PERSON_RED_KEYS`` (TD-110); where the two deliberately differ — the slip's grade
    row, the IC-number chain, EPF, a non-official offer — ``test_doc_red_keys_drift`` pins it.

    **Race fix (2026-06-12):** a document that has NOT yet been read — the scan was
    deferred or skipped under the hourly doc-assist cap, so its fields are still
    blank/``review_manually`` — now returns ``'pending'`` (keep the task open),
    NOT ``'ok'``. Previously an unread upload greenlit and auto-closed the task
    before its scan finished, so a wrong/blurry re-upload could satisfy an officer's
    "this is unclear, send a better one" request. The interactive upload now forces
    the read first (see ``views._maybe_extract_fields(force=True)``), so 'pending'
    only persists on a genuine read failure — where holding the task (reviewer is the
    backstop) is safer than greenlighting an unverified doc. A true OCR-service outage
    on an IC (ran-but-errored) still accepts, so we don't trap a student behind our
    own broken scanner. Everything else — 'uncertain', soft signals, utilities — is
    accepted (D1). Reads the SAME stored verification the student sees in Documents;
    runs no new OCR.

    Each document type's checks live in ``resolution_doc_match`` (one function per type, moved there
    whole by audit sprint A3.4); this function picks the check for the type.
    """
    dt = doc.doc_type

    if dt == 'higher_results':                       # third route S3a (D13: a note never blocks)
        return _higher_match_verdict(doc)
    check = DOC_MATCH_CHECKS.get(dt)
    verdict = check(doc, dt) if check else None
    # NB `str` has no unreadable branch (its currency states cover bad reads; unread/unmatched → 'pending').
    # salary_slip / epf / birth_certificate / guardianship_letter / income_support_doc HOLD an unread/blank
    # file (V2 #4 + V1): a Gemini error must not resolve the request unverified; the upload forces the read
    # first (views._maybe_extract_fields force=True). Bills / statement_of_intent / photo / soft → accept.
    return verdict or 'ok'


def resolve_doc_items_for_upload(application, doc):
    """A student uploaded ``doc`` via the Action Centre — clear any OPEN ``doc``-kind task for that
    ``doc_type`` IF the file scans clean (``doc_match_verdict == 'ok'``). This is what resolves
    **officer** document requests on upload (system items clear via ``sync_resolution_items``; here
    it is idempotent). On a mismatch/unreadable the task stays open for a re-upload. Returns the
    verdict for the frontend. An officer's offer request a NOT CHECKED offer cannot close is held
    for the officer (`hold_for_officer`: the "our team is checking" card), the upload still 'ok' (C2).
    """
    # The bank-details task is upload-THEN-CONFIRM: the upload only pre-fills the three
    # fields (account numbers are high-stakes — the student reviews/corrects before saving),
    # so it never auto-resolves here. ``sync_bank_details_item`` closes it once a BankAccount
    # is confirmed. Still return the verdict so the FE can surface Gopal's advice on a weak read.
    if doc.doc_type == 'bank_statement':
        return doc_match_verdict(doc)
    from . import income_engine
    verdict = doc_match_verdict(doc)
    # TD-409, ruling A: an STR no card matched never closes a request — it is held for the officer (the
    # "our team is checking" card, never "still checking — refresh"), and the upload answers 'ok'.
    held_str = verdict == 'pending' and doc.doc_type == 'str' and str_upload_unmatched(doc)
    held_any = False
    if verdict != 'ok' and not held_str:
        release_not_checked_holds(application, doc)    # TD-406
    if verdict == 'ok' or held_str:
        qs = application.resolution_items.filter(status='open', kind='doc')
        rc = getattr(doc, 'request_code', '') or ''
        # A request-keyed upload (an Action-Centre officer request) resolves EXACTLY that
        # request by code — so two open 'other' requests don't BOTH clear on one upload.
        # A plain upload (no request_code) resolves by doc_type, as before.
        qs = qs.filter(code=rc) if rc else qs.filter(doc_type=doc.doc_type)
        upload_member = (getattr(doc, 'household_member', '') or '').strip()
        str_still_insufficient = False
        str_ic_named = None          # TD-316: read once, and only if an STR-IC ask is in `qs`
        for item in qs:
            # V2 (#4): MEMBER-AWARE. A member-tagged request (V1.3 now writes
            # params.household_member on the check2 per-member proof items) clears ONLY on an
            # upload for THAT member — a mother's payslip no longer resolves the father's request.
            # An untagged request (no member) or an untagged upload keeps the old doc_type match.
            item_member = ((item.params or {}).get('household_member') or '').strip()
            if item_member and upload_member and item_member != upload_member:
                continue
            # V2 (#4): CRITERION-AWARE for income_doc_stale — re-check recency before clearing, so a fresh
            # but STILL-stale salary slip can't silence the "send a current one" ask (the gap persists).
            if item.code == 'income_doc_stale' and income_engine.stale_income_proof(application):
                continue
            # TD-316: ONE FACT DECIDES THE ASK, THE OFFER AND THE RESOLUTION. An IC whose NAME read is 'ok'
            # here even when the field the STR needs did not; it clears once `str_ic_slots` drops the member.
            if '_ic_for_str_' in item.code:
                if str_ic_named is None:
                    from .income_str_ownership import str_owner_ic_asks
                    str_ic_named = {m for ms in str_owner_ic_asks(application).values() for m in ms}
                if item.code.split('_ic_for_str_')[0] in str_ic_named:
                    continue
            # CRITERION-AWARE for str_not_current: this Action-Centre ask is specifically "confirm the
            # STR is approved AND being paid (current cycle)". A re-uploaded but STILL not-current STR
            # (dateless 'unconfirmed', unreadable) scans 'ok' and is fine for SUBMISSION (the gate is
            # deliberately lenient — Probable evidence), but must NOT satisfy the ask: keep it open and
            # coach the student on the detail. Pre-consent has no str_not_current item, so this strictness
            # is scoped to the Action Centre by construction (sync_resolution_items gates on submit).
            if item.code == 'str_not_current' and not income_engine.str_confirmed_current(application):
                str_still_insufficient = True
                continue
            if not results_answers(doc, item):     # S4 (#37): SPM asked, STPM sent (or the reverse)
                continue
            if held_str or officer_must_close(doc, item):   # TD-409 / an unchecked TVET offer (C2)
                hold_for_officer(item)
                held_any = True
                continue
            resolve_item(item, doc=doc, by='student')
        if str_still_insufficient:
            # A valid-but-still-not-current STR: non-'ok' so the FE surfaces the Action-Centre coach's
            # detail advice, while the task stays open. NOT 'mismatch'/'unreadable' — the scan was fine.
            return 'insufficient'
    return 'ok' if held_str and held_any else verdict
