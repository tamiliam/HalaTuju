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
    'offer_unreadable':    {'fact': 'pathway', 'kind': 'doc', 'doc_type': 'offer_letter'},
    'offer_no_identity':   {'fact': 'pathway', 'kind': 'doc', 'doc_type': 'offer_letter'},
    'offer_name_mismatch': {'fact': 'pathway', 'kind': 'doc', 'doc_type': 'offer_letter'},
    'pathway_undeclared':  {'fact': 'pathway', 'kind': 'explanation'},
    # The AI-raised "is this offer your final chosen pathway?" confirmation. A 'confirm'
    # kind: the student answers Yes (no officer), which writes the offer's programme to
    # chosen_programme + stamps pathway_confirmed_at (see services.confirm_pathway).
    'pathway_confirm':     {'fact': 'pathway', 'kind': 'confirm'},
}


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
        except IntegrityError:
            pass  # created concurrently by another request — fine

    for code, item in existing.items():
        if item.status == 'open' and code not in wanted:
            item.status = 'resolved'
            item.resolved_by = 'system'
            item.resolved_at = now
            item.save(update_fields=['status', 'resolved_by', 'resolved_at'])

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


def add_officer_item(application, *, kind, prompt, admin_email, doc_type='', fact='other'):
    """Officer raises a manual ticket — the structured successor to
    ``info_request_note``. Codes are synthetic ``officer_<n>``."""
    n = application.resolution_items.filter(source='officer').count() + 1
    return ResolutionItem.objects.create(
        application=application, source='officer', code=f'officer_{n}',
        fact=fact or 'other', kind=kind, doc_type=doc_type, prompt=prompt or '',
        created_by=admin_email or '',
    )
