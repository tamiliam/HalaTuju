"""The ONE writer of a staff member's activity list (common profile S3, 2026-10-31; D9).

Roadmap `docs/plans/2026-10-31-common-profile-roadmap.md`. The table is `models/staff_activity.py`
(`staff_activity`); this module writes it and nothing else does. S4 adds the reader and the back-fill.

    record(actor, verb, subject=None, meta=None, *, organisation=None)

⚠ BEST-EFFORT, AND THAT IS THE WHOLE CONTRACT (D9). Writing the list must never break the action it
describes:
  * it NEVER RAISES — every failure, the arguments included, is caught and logged as a WARNING;
  * it writes inside its own SAVEPOINT (`transaction.atomic()`), so a database error of its own is
    rolled back to the savepoint and the caller's transaction stays usable;
  * it is written INSIDE the caller's transaction, not on commit — so when the action rolls back the
    row rolls back with it, because the action did not happen;
  * ``meta`` (and only ``meta``) may be a zero-argument callable, evaluated INSIDE the guard, so a
    call site that has to compute something never computes it unguarded (lessons.md 2026-06-13:
    guard the whole block, arguments included). A model instance anywhere in ``meta`` is stored as
    its id.

⚠ WHO IS THE ACTOR. The person who PRESSED the button — the caller of the service, passed in
explicitly — never a stored column that names somebody else (lessons.md 2026-08-02: whoever clicked
"submit" is not always whoever did the interview). A ``None`` actor is a cron or a system path and
writes NOTHING, quietly. Anything that is not a saved `PartnerAdmin` writes nothing either (logged).

⚠ NO FREE TEXT. ``meta`` keys are a closed list (`META_KEYS`), each with a type: an id, a boolean, a
number, or an ENUM CODE — lower-case letters, digits and underscores, at most 40 characters, so it
can carry ``'payments_approve'`` or ``'graduated'`` but never a sentence, a name with a space or an
email address. Anything else is logged and DROPPED (the row is still written without it).

⚠ ONE CLICK, ONE ROW. Each verb is recorded where the action truly happens — the service when there
is one, the view when the view IS the action — so every door reaches it once. Where one action is
made of others (the QC's reject runs a reopen and a decline), the outer action records and asks the
inner services not to (their ``activity=False``). `S3_WIRED` names every writer; the drift test reads
it against the source.
"""
import logging
import re

from django.db import transaction

from .models.staff_activity import StaffActivity, StaffActivitySubject, StaffActivityVerb

logger = logging.getLogger(__name__)

V = StaffActivityVerb
VERBS = frozenset(V.values)
SUBJECT_TYPES = frozenset(StaffActivitySubject.values)

# The names call sites use. `V.X` works too; these keep the call sites short.
INVITATION_SENT = V.INVITATION_SENT
INVITATION_ACCEPTED = V.INVITATION_ACCEPTED
FIRST_SIGN_IN = V.FIRST_SIGN_IN
PROFILE_UPDATED = V.PROFILE_UPDATED
PERMISSIONS_CHANGED = V.PERMISSIONS_CHANGED
ASSIGNED = V.ASSIGNED
UNASSIGNED = V.UNASSIGNED
QUERY_RAISED = V.QUERY_RAISED
QUERY_RESOLVED = V.QUERY_RESOLVED
INTERVIEW_SUBMITTED = V.INTERVIEW_SUBMITTED
VERDICT_RECORDED = V.VERDICT_RECORDED
VERIFY_ACCEPT = V.VERIFY_ACCEPT
DECLINE_SENT_TO_QC = V.DECLINE_SENT_TO_QC
DECLINED = V.DECLINED
QC_DECISION = V.QC_DECISION
DECISION_REOPENED = V.DECISION_REOPENED
CASE_CLOSED = V.CASE_CLOSED
CONTRACT_WITNESSED = V.CONTRACT_WITNESSED

#: Every S3 verb and the function(s) that write it — `path:qualname`, paths under `apps/`. The drift
#: test (`tests/test_staff_activity.py`) reads the source: the functions that name each verb must be
#: EXACTLY these — a writer missing here, or one listed here that no longer writes, fails it.
S3_WIRED = {
    INVITATION_SENT: ('scholarship/invitations.py:record_send',),
    INVITATION_ACCEPTED: ('scholarship/invitations.py:accept_for_admin',),
    FIRST_SIGN_IN: ('courses/views_admin.py:AdminRoleView.get',),
    PROFILE_UPDATED: ('scholarship/views_admin/me.py:AdminMeView.patch',
                      'scholarship/views_admin/me.py:AdminMePhotoView.post',
                      'scholarship/views_admin/me.py:AdminMePhotoView.delete',
                      'scholarship/views_admin/me.py:AdminMePasswordView.post',
                      'scholarship/views_admin/reviewers.py:ReviewerProfileView.patch',
                      'scholarship/views_admin/source_console.py:AdminSourceProfileView.patch',
                      'courses/views_profile.py:AdminProfileView.put'),
    PERMISSIONS_CHANGED: ('scholarship/staff_permissions_admin.py:record',),
    ASSIGNED: ('scholarship/services/assignment.py:_record_assignment',),
    UNASSIGNED: ('scholarship/services/assignment.py:_record_assignment',),
    QUERY_RAISED: ('scholarship/resolution.py:add_officer_item',
                   'scholarship/views_admin/resolution.py:AdminRequestInfoView.post',
                   'scholarship/views_admin/resolution.py:AdminResolutionItemActionView.post'),
    QUERY_RESOLVED: ('scholarship/views_admin/resolution.py:AdminResolutionItemActionView.post',),
    INTERVIEW_SUBMITTED: ('scholarship/services/querying.py:submit_interview',),
    VERDICT_RECORDED: ('scholarship/views_admin/verdict.py:_save_verdict',),
    VERIFY_ACCEPT: ('scholarship/views_admin/applications.py:AdminVerifyAcceptView.post',),
    DECLINE_SENT_TO_QC: ('scholarship/views_admin/verdict.py:AdminSubmitDeclineView.post',),
    DECLINED: ('scholarship/services/decline.py:admin_reject',
               'scholarship/services/decline.py:org_admin_reject'),
    QC_DECISION: ('scholarship/views_admin/verdict.py:_record_qc',),
    DECISION_REOPENED: ('scholarship/reopen.py:reopen_decision',),
    CASE_CLOSED: ('scholarship/closure.py:close_application',),
    CONTRACT_WITNESSED: ('scholarship/source_witness.py:record_once',),
}

#: Declared in the closed list now, written from S4 (money, contracts, requests) — ON PURPOSE unwired
#: in S3. The drift test asserts `S3_WIRED` and this set are disjoint and together are every verb.
S4_VERBS = frozenset({
    V.PAYMENT_RUN_CREATED, V.PAYMENT_RUN_SIGNED, V.TRANCHE_RELEASED, V.TRANCHE_WITHHELD,
    V.TRANCHE_RETURNED, V.CREDIT_RECORDED, V.CREDIT_CHECKED, V.CREDIT_CONFIRMED,
    V.CONTRACT_TEMPLATE_CREATED, V.CONTRACT_TEMPLATE_VETTED, V.CONTRACT_TEMPLATE_SUBMITTED,
    V.CONTRACT_TEMPLATE_DEPLOYED, V.CONTRACT_COUNTERSIGNED, V.BENEFACTOR_VETTED,
    V.INVOICE_ISSUED, V.INVOICE_SENT, V.INVOICE_VOIDED, V.PAYMENT_DECLARED, V.PAYMENT_CONFIRMED,
    V.PAYMENT_REJECTED, V.ORG_REQUEST_RAISED, V.ORG_REQUEST_APPROVED, V.ORG_REQUEST_DECLINED,
    V.MERCHANT_FLAG_OPENED, V.MERCHANT_FLAG_CLOSED,
})

# ── meta: the closed key list ──────────────────────────────────────────────────────────────────
ID, BOOL, NUMBER, CODE, CODES = 'id', 'bool', 'number', 'code', 'codes'
#: Every key a row's ``meta`` may hold, and its type. Add a key here before a call site uses it.
META_KEYS = {
    # ids of other rows
    'from_admin': ID, 'to_admin': ID, 'target': ID, 'item': ID, 'session': ID,
    'agreement': ID, 'interviewer': ID, 'invitation': ID,
    # booleans
    'emailed': BOOL, 'resend': BOOL, 'finalised': BOOL, 'override': BOOL, 'asked_again': BOOL,
    # numbers
    'count': NUMBER,
    # enum codes
    'audience': CODE, 'overall': CODE, 'decision': CODE, 'outcome': CODE, 'category': CODE,
    'reason': CODE, 'from_status': CODE, 'kind': CODE, 'action': CODE, 'by': CODE,
    'role': CODE,
    # lists of enum codes
    'fields': CODES, 'added': CODES, 'removed': CODES,
}
_CODE = re.compile(r'^[a-z0-9][a-z0-9_]{0,39}$')
#: The longest list a CODES value may hold (the permission catalogue has 8 keys).
CODES_MAX = 20


def _is_code(value):
    return isinstance(value, str) and bool(_CODE.match(value))


def _as_id(value):
    """A model instance becomes its id; anything else is returned as it is."""
    pk = getattr(value, 'pk', None)
    return pk if pk is not None and hasattr(value, '_meta') else value


def _allowed(kind, value):
    if value is None:
        return True
    if kind == ID:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == BOOL:
        return isinstance(value, bool)
    if kind == NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == CODE:
        return _is_code(value)
    if kind == CODES:
        return (isinstance(value, (list, tuple)) and len(value) <= CODES_MAX
                and all(_is_code(v) for v in value))
    return False


def clean_meta(meta):
    """``meta`` with every key or value that is not allowed DROPPED (each logged). Never raises."""
    if not meta:
        return {}
    if not isinstance(meta, dict):
        logger.warning('staff_activity: meta of type %s dropped', type(meta).__name__)
        return {}
    out = {}
    for key, value in meta.items():
        kind = META_KEYS.get(key) if isinstance(key, str) else None
        value = _as_id(value)
        if kind is None or not _allowed(kind, value):
            logger.warning('staff_activity: meta key %r dropped (not allowed)', key)
            continue
        out[key] = list(value) if kind == CODES and value is not None else value
    return out


# ── subjects ───────────────────────────────────────────────────────────────────────────────────
#: Model label -> subject type. A subject of any other model is recorded with no subject (logged).
_SUBJECT_OF_MODEL = {
    'scholarship.scholarshipapplication': StaffActivitySubject.APPLICATION,
    'courses.partneradmin': StaffActivitySubject.STAFF,
    'scholarship.invitation': StaffActivitySubject.INVITATION,
}


def _subject(subject):
    """``(subject_type, subject_id, organisation_id or None)`` for a model instance or a
    ``(type, id)`` pair; ``('', None, None)`` for none."""
    if subject is None:
        return '', None, None
    if isinstance(subject, tuple):
        kind, pk = subject
        if kind not in SUBJECT_TYPES or not isinstance(pk, int) or isinstance(pk, bool):
            raise ValueError(f'bad subject {subject!r}')
        return kind, pk, None
    label = subject._meta.label_lower
    kind = _SUBJECT_OF_MODEL.get(label)
    if kind is None or subject.pk is None:
        raise ValueError(f'no subject type for {label}')
    org_id = (getattr(subject, 'owning_organisation_id', None)
              if kind != StaffActivitySubject.INVITATION else getattr(subject, 'organisation_id', None))
    return kind, subject.pk, org_id


def _is_staff_row(actor):
    meta = getattr(actor, '_meta', None)
    return meta is not None and meta.label_lower == 'courses.partneradmin' and actor.pk is not None


# ── the writer ─────────────────────────────────────────────────────────────────────────────────
def record(actor, verb, subject=None, meta=None, *, organisation=None):
    """Write ONE row saying ``actor`` did ``verb`` to ``subject``. Returns the row, or None.

    ``subject``: a `ScholarshipApplication`, a `PartnerAdmin` (the person acted on) or an
    `Invitation` — or a ``(subject_type, id)`` pair. ``organisation``: an organisation or its id;
    by default the subject's own, else the actor's. See the module docstring for the guarantees."""
    try:
        if actor is None:
            return None                 # a cron / system path: nobody pressed a button
        if not _is_staff_row(actor):
            logger.warning('staff_activity: actor %r is not a saved staff row; nothing written',
                           type(actor).__name__)
            return None
        if verb not in VERBS:
            logger.warning('staff_activity: unknown verb %r; nothing written', verb)
            return None
        kind, subject_id, subject_org = _subject(subject)
        clean = clean_meta(meta() if callable(meta) else meta)
        org_id = _as_id(organisation)
        if org_id is None:
            org_id = subject_org if subject_org is not None else actor.owning_organisation_id
        with transaction.atomic():      # a savepoint inside the caller's transaction
            return StaffActivity.objects.create(
                actor=actor, organisation_id=org_id, verb=str(verb), subject_type=kind,
                subject_id=subject_id, meta=clean)
    except Exception:   # D9: the activity list never breaks the action (no `noqa`: budget full)
        logger.warning('staff_activity: could not record %r', verb, exc_info=True)
        return None
