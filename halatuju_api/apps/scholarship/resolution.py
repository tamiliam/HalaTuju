"""
Resolution tickets (Sprint 3) — turn the verification verdict's unresolved items
into discrete, self-serviceable actions (the IBKR model; see
docs/scholarship/verification-verdict-plan.md).

``sync_resolution_items(application)`` is idempotent: at most one
``source='system'`` ResolutionItem per (application, code), created once and
auto-resolved the moment its code leaves ``verdict.unresolved`` (e.g. the student
uploads the STR letter → the income gap clears → the ticket closes). It never
re-nags an answered item and never touches officer-raised items.

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

from .models import ResolutionItem
from .verdict_engine import build_verdict

CODE_TO_TICKET = {
    # Identity
    'ic_missing':             {'fact': 'identity', 'kind': 'doc', 'doc_type': 'ic'},
    'ic_unreadable':          {'fact': 'identity', 'kind': 'doc', 'doc_type': 'ic'},
    'nric_mismatch':          {'fact': 'identity', 'kind': 'confirm'},
    'name_mismatch':          {'fact': 'identity', 'kind': 'confirm'},
    # NB: address_state_mismatch is deliberately NOT ticketable — the IC's registered
    # state is the least-current address on file, not an identity caveat (see
    # verdict_engine._verdict_identity). It surfaces only as a pre-interview flag
    # ("ask which is current"), so it never becomes a caveat the student must resolve.
    # Academic
    'results_slip_missing':       {'fact': 'academic', 'kind': 'doc', 'doc_type': 'results_slip'},
    'results_slip_unreadable':    {'fact': 'academic', 'kind': 'doc', 'doc_type': 'results_slip'},
    'results_slip_name_mismatch': {'fact': 'academic', 'kind': 'doc', 'doc_type': 'results_slip'},
    'academic_missing_subjects':  {'fact': 'academic', 'kind': 'confirm'},
    'academic_grade_mismatch':    {'fact': 'academic', 'kind': 'confirm'},
    # Income
    'income_proof_missing': {'fact': 'income', 'kind': 'doc', 'doc_type': 'str'},
    # Income Check-1 (item 3: earner identity + relationship). `income_unverified_needs_interview`
    # is deliberately ABSENT — it's an officer/interview flag, not a student to-do.
    'income_earner_undeclared':     {'fact': 'income', 'kind': 'confirm'},
    'earner_ic_missing':            {'fact': 'income', 'kind': 'doc', 'doc_type': 'parent_ic'},
    'earner_ic_unreadable':         {'fact': 'income', 'kind': 'doc', 'doc_type': 'parent_ic'},
    'birth_cert_missing':           {'fact': 'income', 'kind': 'doc', 'doc_type': 'birth_certificate'},
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
    'pathway_undeclared':  {'fact': 'pathway', 'kind': 'explanation'},
    # NOTE: 'pathway_confirm' is intentionally NOT here. The "is this offer your final
    # chosen pathway?" confirmation is a STUDENT query, routed through Check 2
    # (source='check2') so CHECK2_STUDENT_QUERIES_ENABLED governs it + it rides the query
    # email — see check2_queries._sync_pathway_confirm. (As a 'system' item it was hidden
    # from the student queue, so only the officer ever saw it.)
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
    return out


def open_items(application):
    return list(application.resolution_items.filter(status='open').order_by('-created_at'))


def sync_resolution_items(application):
    """Reconcile SYSTEM items with the current verdict; return the open items
    (system + officer). Idempotent and race-safe.

      - ticketable code with no system item yet  → create an open item
      - OPEN system item whose code has cleared   → auto-resolve it
      - already-resolved system items             → left as-is (no re-nag)
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
    wanted = _ticketable_unresolved(application)
    existing = {r.code: r for r in application.resolution_items.filter(source='system')}
    now = timezone.now()

    raised_student_visible = False
    for code, info in wanted.items():
        if code in existing:
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
        if item.status == 'open' and code in CODE_TO_TICKET and code not in wanted:
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
                     household_member=''):
    """Officer raises a manual ticket — the structured successor to
    ``info_request_note``. Codes are synthetic ``officer_<n>``. For a per-person
    document request (e.g. the father's salary slip), ``household_member`` is stashed
    in ``params`` so the student's upload tags the right (doc_type, member) slot —
    closing the salary-route Action-Centre tagging gap without a schema change."""
    n = application.resolution_items.filter(source='officer').count() + 1
    params = {'household_member': household_member} if household_member else {}
    return ResolutionItem.objects.create(
        application=application, source='officer', code=f'officer_{n}',
        fact=fact or 'other', kind=kind, doc_type=doc_type, prompt=prompt or '',
        params=params, created_by=admin_email or '',
    )


def doc_match_verdict(doc):
    """The Action Centre's per-document verdict for an uploaded file:
    ``'mismatch'`` (a confirmed red), ``'unreadable'`` (a bad/blurry scan),
    ``'pending'`` (not scanned yet — hold the task), or ``'ok'`` (accept — resolve
    the task).

    Mirrors the consent-gate per-document classification
    (``services.document_red_blockers`` / ``document_unreadable_blockers``) so the
    Action Centre and the gate never disagree: a CONFIRMED ``mismatch`` (or an STR
    rejected/stale) or an UNREADABLE scan keeps a task open.

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
    """
    from . import income_engine
    from .academic_engine import student_slip_check
    from .pathway_engine import student_offer_check
    from .services import is_ic_decode_error

    dt = doc.doc_type

    def red(chk, *keys):
        return any((chk or {}).get(k) == 'mismatch' for k in keys)

    if dt == 'results_slip':
        chk = student_slip_check(doc) or {}
        # NOTE: 'subjects' is deliberately NOT a doc mismatch. A slip 'subjects' mismatch means
        # the OFFICIAL slip lists a subject the student didn't enter in their /profile — the slip
        # is genuine, the profile is just incomplete. That is a SOFT discrepancy: Gopal nudges the
        # student to add the subject(s) at /profile (help_engine 'slip_subjects_missing'), the
        # Academic tile shows it as 'review' (academic_missing_subjects), and Check 2 follows up —
        # but it must NOT block submission or red the document. A NAME or GRADE (results) mismatch
        # still does.
        if red(chk, 'name', 'results'):
            return 'mismatch'
        # An unreadable scan keeps the task open — and it's unreadable whether the NAME
        # or the SUBJECT TABLE couldn't be read (a blurry slip whose name happens to
        # read but whose grades don't is still a re-upload). Previously only the name
        # was checked, so such a slip slipped through as 'ok'.
        if chk.get('name') == 'unreadable' or chk.get('subjects') == 'unreadable':
            return 'unreadable'
        # Not scanned yet (extraction deferred/skipped) → hold, don't greenlight. Keyed
        # on name/subjects, NOT results: results=='pending' also means "no grades on file
        # to compare against" (the slip itself read fine), which must still accept.
        if chk.get('name') == 'pending' or chk.get('subjects') == 'pending':
            return 'pending'
    elif dt == 'offer_letter':
        chk = student_offer_check(doc) or {}
        if red(chk, 'name', 'ic'):
            return 'mismatch'
        if chk.get('name') == 'unreadable':
            return 'unreadable'
        if chk.get('name') == 'pending':
            return 'pending'          # not read yet — hold the task
    elif dt == 'parent_ic':
        chk = income_engine.student_income_ic_check(doc) or {}
        # IC-number chain verified the earner from the BC↔proof number match (#9) — a card that's
        # the wrong family member's is then a soft note, not a red block.
        if not chk.get('chain_verified') and red(chk, 'name_status', 'proof_name_status', 'proof_nric_status'):
            return 'mismatch'
        ran = bool(getattr(doc, 'vision_run_at', None))
        err = getattr(doc, 'vision_error', '') or ''
        if not ran:
            return 'pending'          # not scanned yet — don't greenlight an unread IC
        # An OCR-service outage is not the student's fault — don't call it unreadable.
        if (not err or is_ic_decode_error(err)) and not chk.get('readable'):
            return 'unreadable'
    elif dt in ('salary_slip', 'epf'):
        if red(income_engine.student_income_proof_check(doc), 'name_status', 'nric_status'):
            return 'mismatch'
    elif dt == 'str':
        chk = income_engine.student_str_check(doc) or {}
        if red(chk, 'name_status', 'nric_status') or chk.get('current_status') in income_engine.STR_RED_STATES:
            return 'mismatch'
    elif dt == 'birth_certificate':
        if red(income_engine.student_bc_check(doc), 'child_status', 'mother_status', 'father_status'):
            return 'mismatch'
    elif dt == 'guardianship_letter':
        if red(income_engine.student_guardianship_check(doc), 'guardian_status', 'ward_status'):
            return 'mismatch'
    elif dt == 'bank_statement':
        # Reads the doc-assist verdict (holder==student + all 3 fields present), computed
        # deterministically from the Gemini-extracted fields. 'name_mismatch' = the account
        # is in someone else's name (a HARD problem → mismatch); 'incomplete'/'wrong_doc' =
        # a field couldn't be read clearly (re-upload → unreadable). Not yet scanned → hold.
        sv = (getattr(doc, 'vision_fields', None) or {}).get('student_verdict', '')
        if sv in ('', 'read', 'review_manually'):
            return 'pending'
        if sv == 'name_mismatch':
            return 'mismatch'
        if sv in ('incomplete', 'wrong_doc', 'unreadable'):
            return 'unreadable'
    elif dt == 'ic':
        ran = bool(getattr(doc, 'vision_run_at', None))
        if not ran:
            return 'pending'          # not scanned yet — don't greenlight an unread IC
        err = getattr(doc, 'vision_error', '') or ''
        service_down = bool(err) and not is_ic_decode_error(err)
        if not service_down:
            from .vision import nric_match, name_match
            prof = getattr(doc.application, 'profile', None)
            if not doc.vision_nric or not doc.vision_name:
                return 'unreadable'
            if not nric_match(doc.vision_nric, getattr(prof, 'nric', '') or ''):
                return 'mismatch'
            if name_match(doc.vision_name, getattr(prof, 'name', '') or '') == 'mismatch':
                return 'mismatch'
    # NB income docs (str / salary_slip / epf / birth_certificate / guardianship_letter)
    # have no 'pending' branch here: the interactive upload forces their read first
    # (views._maybe_extract_fields force=True), so they're scanned by the time this runs.
    # water_bill / electricity_bill / statement_of_intent / photo, and every
    # 'uncertain'/soft outcome above → accept.
    return 'ok'


def resolve_doc_items_for_upload(application, doc):
    """A student uploaded ``doc`` via the Action Centre — clear any OPEN ``doc``-kind
    task for that ``doc_type`` IF the file scans clean (``doc_match_verdict == 'ok'``).

    This is what finally resolves **officer** document requests on upload (system doc
    items already clear via ``sync_resolution_items`` when their verdict gap closes;
    re-resolving them here is idempotent). On a mismatch/unreadable the task stays open
    so the student re-uploads (the caller surfaces Cikgu Gopal's advice). Returns the
    verdict so the caller can tell the frontend.
    """
    # The bank-details task is upload-THEN-CONFIRM: the upload only pre-fills the three
    # fields (account numbers are high-stakes — the student reviews/corrects before saving),
    # so it never auto-resolves here. ``sync_bank_details_item`` closes it once a BankAccount
    # is confirmed. Still return the verdict so the FE can surface Gopal's advice on a weak read.
    if doc.doc_type == 'bank_statement':
        return doc_match_verdict(doc)
    verdict = doc_match_verdict(doc)
    if verdict == 'ok':
        qs = application.resolution_items.filter(status='open', kind='doc')
        rc = getattr(doc, 'request_code', '') or ''
        # A request-keyed upload (an Action-Centre officer request) resolves EXACTLY that
        # request by code — so two open 'other' requests don't BOTH clear on one upload.
        # A plain upload (no request_code) resolves by doc_type, as before.
        qs = qs.filter(code=rc) if rc else qs.filter(doc_type=doc.doc_type)
        for item in qs:
            resolve_item(item, doc=doc, by='student')
    return verdict


# Post-award bank-details capture. A dedicated task (NOT verdict-derived — it's a
# post-award operational step, not a verification gap), so it lives outside CODE_TO_TICKET
# and is ALWAYS visible to the student (see views.ResolutionItemListView._student_visible),
# independent of the Check-2 query flag.
BANK_DETAILS_CODE = 'bank_details_missing'
# The student needs a payout account while AWARDED (signing) or ACTIVE (executed, awaiting
# the first payout). It leaves the Action Centre once they confirm one, or the award ends.
BANK_CAPTURE_STATES = frozenset({'awarded', 'active'})


def sync_bank_details_item(application):
    """Reconcile the post-award bank-details task: ensure ONE open ``bank_details_missing``
    item while the student is awarded/active with no confirmed payout account, and resolve
    it once a ``BankAccount`` is confirmed (or the award leaves those states). Idempotent.

    Gated by ``BANK_DETAILS_CAPTURE_ENABLED`` (default OFF — feature being deprecated): while
    OFF, ``wanted`` is forced False, so no task is ever created and any existing open one is
    swept to resolved (it drops out of the Action Centre)."""
    from django.conf import settings
    from .models import BankAccount, ResolutionItem
    enabled = getattr(settings, 'BANK_DETAILS_CAPTURE_ENABLED', False)
    has_account = BankAccount.objects.filter(application=application).exists()
    wanted = enabled and application.status in BANK_CAPTURE_STATES and not has_account
    existing = application.resolution_items.filter(code=BANK_DETAILS_CODE).first()
    if wanted and existing is None:
        try:
            ResolutionItem.objects.create(
                application=application, source='system', code=BANK_DETAILS_CODE,
                fact='other', kind='doc', doc_type='bank_statement', params={},
            )
        except IntegrityError:
            pass  # created concurrently — fine
    elif wanted and existing is not None and existing.status != 'open':
        # Self-heal: the task is still needed (awarded/active, no account) but was resolved —
        # e.g. wrongly swept by a verdict sync, or the status bounced. RE-OPEN it so an
        # un-uploaded bank task can never silently read as "done". (Bug fix 2026-06-29.)
        existing.status = 'open'
        existing.resolved_by = ''
        existing.resolved_at = None
        existing.save(update_fields=['status', 'resolved_by', 'resolved_at'])
    elif existing is not None and existing.status == 'open' and not wanted:
        existing.status = 'resolved'
        existing.resolved_by = 'system'
        existing.resolved_at = timezone.now()
        existing.save(update_fields=['status', 'resolved_by', 'resolved_at'])
