"""Rebuild the staff activity list from the records that already exist (common profile S4, 2026-10-31).

Run by `manage.py backfill_staff_activity --dry-run | --apply`. Every row it writes has
``backfilled=True`` and ``created_at`` = the moment the old record says the thing happened.

WHERE THE ROWS COME FROM. The history tables (AssignmentEvent, StaffPermissionChange, DecisionReopen,
Invitation, OrgRequest, MerchantFlagNote) and the single stamps on the records themselves (the
application's verified / verdict / recommended / rejected / closed stamps, resolution items,
interviews, payment runs and their signatures, released tranches, credits, witnesses, contract
templates, benefactor vetting, invoices, declarations and receipts, first sign-ins). `SOURCES` is the
list. The student file's own activity log adds nothing and is NOT read (it stays read only by the
staff file, `test_letters`): its staff rows (a close, a released payment) are the SAME events as the
stamps read here, which are the record, so reading both would write twins.

WHO THE ACTOR IS. A real foreign key to `PartnerAdmin` where the record has one. Otherwise an email
stamp, used ONLY when exactly one `PartnerAdmin` row has that address (case-insensitive) — an
ambiguous or unknown address is skipped and counted. A NAME-ONLY stamp (the Foundation's countersign
name, the super's witness name) is skipped and counted: a name is not a person.

⚠ NO TWIN OF A LIVE ROW — TWO RULES, BOTH NEEDED. The deploy order is migrate, then the API (live
rows start), then this. Every action after the live writers started wrote its own live row:
  1. THE CUT-OFF. Only events stamped BEFORE the earliest live row (``backfilled=False``) are
     rebuilt — that row is the moment the live writers demonstrably began. An event stamped at or
     after it is skipped ("after live start"): it has its live row, or its writer failed (D9) and no
     rebuilt guess should stand in for it. With no live row at all the cut-off is the moment the
     command started. `--before` may move it EARLIER, never later.
  2. THE TWIN CHECK. The cut-off alone is not enough, and a test proved it: an action stamps its own
     record (`AssignmentEvent.created_at`, `closed_at`, ...) and THEN writes its live row, so the very
     first live action's stamp falls a few milliseconds BEFORE the earliest live row. So an event is
     also skipped ("has a live twin") when a LIVE row with the same verb, actor, subject type and
     subject id was written within `TWIN_WINDOW` of its stamp (from a minute before to ten minutes
     after: the live row follows its stamp in the same request, sometimes after an email or a sheet
     upload). The cost is a pre-deploy act repeated by the same person on the same subject within
     minutes of the deploy, which would be counted once — a price worth paying for no twins.

⚠ IDEMPOTENT — THE KEY. A rebuilt row is the tuple (verb, actor, subject type, subject id, created_at)
and created_at is the source stamp, copied exactly, so a second run finds every row already there and
writes nothing. Checked per batch against the rows already written, never by loading the table.

FLAT MEMORY. Each source streams with `.iterator()` over `.values()`, and rows are checked and written
in batches of `BATCH`; the email index is the staff table only (hundreds of rows).
"""
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Min
from django.utils import timezone

from . import staff_activity
from .models import StaffActivity

BATCH = 500
#: How far a LIVE row may sit from the stamp of the act it records (rule 2 in the module docstring).
TWIN_BEFORE, TWIN_AFTER = timedelta(minutes=1), timedelta(minutes=10)
V = staff_activity.V

# Reasons a candidate is not written (the report counts each).
NO_ACTOR = 'no actor recorded'
NAME_ONLY = 'name-only stamp'
UNKNOWN_EMAIL = 'email matches no staff row'
AMBIGUOUS_EMAIL = 'email matches more than one staff row'
NO_TIME = 'no event time recorded'
AFTER_LIVE = 'after live start (has a live row)'
LIVE_TWIN = 'has a live twin'
ALREADY = 'already rebuilt'


class _Cand:
    """One event a source found. ``actor`` is an id (a real FK), or ``('email', address)``."""
    __slots__ = ('verb', 'actor', 'subject_type', 'subject_id', 'org_id', 'at', 'meta', 'skip')

    def __init__(self, verb, actor, subject_type='', subject_id=None, org_id=None, at=None,
                 meta=None, skip=None):
        self.verb, self.actor, self.subject_type, self.subject_id = verb, actor, subject_type, subject_id
        self.org_id, self.at, self.meta, self.skip = org_id, at, meta or {}, skip


def _email(value):
    value = (value or '').strip()
    return ('email', value.casefold()) if '@' in value else None


def _stream(qs, *fields):
    return qs.values(*fields).iterator(chunk_size=BATCH)


# ── the sources ────────────────────────────────────────────────────────────────────────────────
def _first_sign_ins():
    from apps.courses.models import PartnerAdmin
    for r in _stream(PartnerAdmin.objects.filter(first_seen_at__isnull=False),
                     'id', 'first_seen_at', 'owning_organisation_id'):
        yield _Cand(V.FIRST_SIGN_IN, r['id'], org_id=r['owning_organisation_id'],
                    at=r['first_seen_at'])


def _invitations():
    from .models import Invitation
    for r in _stream(Invitation.objects.all(), 'id', 'audience', 'organisation_id', 'invited_by_id',
                     'created_at', 'partner_admin_id', 'accepted_at'):
        yield _Cand(V.INVITATION_SENT, r['invited_by_id'], 'invitation', r['id'],
                    r['organisation_id'], r['created_at'], {'audience': r['audience']},
                    skip=None if r['invited_by_id'] else NO_ACTOR)
        if r['accepted_at'] is not None:
            yield _Cand(V.INVITATION_ACCEPTED, r['partner_admin_id'], 'invitation', r['id'],
                        r['organisation_id'], r['accepted_at'],
                        skip=None if r['partner_admin_id'] else NO_ACTOR)


def _permission_changes():
    from .models import StaffPermissionChange
    for r in _stream(StaffPermissionChange.objects.all(), 'target_id', 'organisation_id', 'kind',
                     'before', 'after', 'changed_by_email', 'created_at'):
        before, after = r['before'] or [], r['after'] or []
        yield _Cand(V.PERMISSIONS_CHANGED, _email(r['changed_by_email']),
                    'staff' if r['target_id'] else '', r['target_id'], r['organisation_id'],
                    r['created_at'], {'kind': r['kind'],
                                      'added': [k for k in after if k not in before],
                                      'removed': [k for k in before if k not in after]})


def _assignments():
    from .models import AssignmentEvent
    for r in _stream(AssignmentEvent.objects.all(), 'application_id', 'from_admin_id', 'to_admin_id',
                     'by_email', 'created_at', 'application__owning_organisation_id'):
        yield _Cand(V.ASSIGNED if r['to_admin_id'] else V.UNASSIGNED, _email(r['by_email']),
                    'application', r['application_id'], r['application__owning_organisation_id'],
                    r['created_at'], {'from_admin': r['from_admin_id'], 'to_admin': r['to_admin_id']})


def _queries():
    from .models import ResolutionItem
    org = 'application__owning_organisation_id'
    for r in _stream(ResolutionItem.objects.filter(source='officer'), 'id', 'application_id',
                     'kind', 'created_by', 'created_at', org):
        yield _Cand(V.QUERY_RAISED, _email(r['created_by']), 'application', r['application_id'],
                    r[org], r['created_at'], {'item': r['id'], 'kind': r['kind']})
    for r in _stream(ResolutionItem.objects.filter(status__in=('resolved', 'waived'),
                                                   resolved_at__isnull=False),
                     'id', 'application_id', 'status', 'resolved_by', 'resolved_at', org):
        if (r['resolved_by'] or '') in ('student', 'system', ''):
            continue        # the student, the system: not a staff action at all
        actor = _email(r['resolved_by'])        # 'officer' (an old fallback) names nobody
        yield _Cand(V.QUERY_RESOLVED, actor, 'application', r['application_id'], r[org],
                    r['resolved_at'], {'item': r['id'],
                                       'action': 'waive' if r['status'] == 'waived' else 'resolve'},
                    skip=None if actor else NO_ACTOR)


def _interviews():
    from .models import InterviewSession
    for r in _stream(InterviewSession.objects.filter(status='submitted'), 'id', 'application_id',
                     'interviewer_id', 'submitted_at', 'application__owning_organisation_id'):
        yield _Cand(V.INTERVIEW_SUBMITTED, r['interviewer_id'], 'application', r['application_id'],
                    r['application__owning_organisation_id'], r['submitted_at'],
                    {'session': r['id'], 'interviewer': r['interviewer_id']},
                    skip=None if r['interviewer_id'] else NO_ACTOR)


def _application_stamps():
    from .models import ScholarshipApplication
    for r in _stream(ScholarshipApplication.objects.all(),
                     'id', 'owning_organisation_id', 'verified_at', 'verified_by',
                     'verdict_decided_at', 'verdict_decided_by', 'officer_verdict',
                     'recommended_at', 'recommended_by', 'rejected_at', 'rejected_by',
                     'rejection_category', 'closed_at', 'closed_by', 'closure_reason'):
        org = r['owning_organisation_id']
        overall = (r['officer_verdict'] or {}).get('overall') if isinstance(
            r['officer_verdict'], dict) else None
        pairs = (
            (V.VERIFY_ACCEPT, 'verified', {}),
            (V.VERDICT_RECORDED, 'verdict_decided', {'overall': overall or 'blank'}),
            (V.QC_DECISION, 'recommended', {'decision': 'accept', 'outcome': 'recommended'}),
            (V.DECLINED, 'rejected', {'category': r['rejection_category'] or None}),
            (V.CASE_CLOSED, 'closed', {'reason': r['closure_reason'] or None}),
        )
        for verb, stem, meta in pairs:
            at = r[f'{stem}_at']
            by = r[f'{stem}_by']
            if at is None:
                continue
            if not by:          # the engine's own rejection, the expiry sweep: nobody pressed it
                yield _Cand(verb, None, 'application', r['id'], org, at, skip=NO_ACTOR)
                continue
            yield _Cand(verb, _email(by), 'application', r['id'], org, at, meta)


def _reopens():
    from .models import DecisionReopen
    for r in _stream(DecisionReopen.objects.all(), 'application_id', 'reopened_by', 'created_at',
                     'application__owning_organisation_id'):
        yield _Cand(V.DECISION_REOPENED, _email(r['reopened_by']), 'application',
                    r['application_id'], r['application__owning_organisation_id'], r['created_at'])


def _agreements():
    from .models import BursaryAgreement
    org = 'application__owning_organisation_id'
    for r in _stream(BursaryAgreement.objects.all(), 'id', 'application_id', 'witness_admin_id',
                     'witness_signed_at', 'foundation_signed_at', org):
        if r['witness_signed_at'] is not None:
            yield _Cand(V.CONTRACT_WITNESSED, r['witness_admin_id'], 'application',
                        r['application_id'], r[org], r['witness_signed_at'],
                        {'agreement': r['id'], 'by': 'source'},
                        skip=None if r['witness_admin_id'] else NAME_ONLY)
        if r['foundation_signed_at'] is not None:     # the Foundation's countersign: a name only
            yield _Cand(V.CONTRACT_COUNTERSIGNED, None, at=r['foundation_signed_at'], skip=NAME_ONLY)


def _payment_runs():
    from .models import PaymentRun
    for r in _stream(PaymentRun.objects.all(), 'id', 'organisation_id', 'created_by', 'created_at',
                     'admin_signed_email', 'admin_signed_at', 'finance_signed_email',
                     'finance_signed_at', 'org_admin_signed_email', 'org_admin_signed_at'):
        org = r['organisation_id']
        yield _Cand(V.PAYMENT_RUN_CREATED, _email(r['created_by']), 'payment_run', r['id'], org,
                    r['created_at'])
        for role, stem in (('maker', 'admin'), ('checker', 'finance'), ('approver', 'org_admin')):
            if r[f'{stem}_signed_at'] is not None:
                yield _Cand(V.PAYMENT_RUN_SIGNED, _email(r[f'{stem}_signed_email']), 'payment_run',
                            r['id'], org, r[f'{stem}_signed_at'], {'role': role})


def _tranches():
    from .models import Disbursement
    qs = Disbursement.objects.filter(status='released', released_at__isnull=False).exclude(
        reference__startswith='vircle:')     # a run's payout is the run's approval, not a tranche act
    for r in _stream(qs, 'id', 'application_id', 'actioned_by', 'released_at',
                     'application__owning_organisation_id'):
        yield _Cand(V.TRANCHE_RELEASED, _email(r['actioned_by']), 'application', r['application_id'],
                    r['application__owning_organisation_id'], r['released_at'], {'tranche': r['id']})
    # Withheld and returned tranches carry no moment of their own (only `updated_at`, which any save
    # moves — lessons.md 2026-07-26), so they cannot be dated honestly and are counted, not rebuilt.
    for _ in Disbursement.objects.filter(status__in=('withheld', 'returned')).values_list(
            'id', flat=True).iterator(chunk_size=BATCH):
        yield _Cand(V.TRANCHE_WITHHELD, None, skip=NO_TIME)


def _credits():
    from .models import Donation
    org = 'programme__organisation_id'
    # Every credit with a signature stamp (only the admin chain stamps these), never by its source
    # constant: minting one stays `record_admin_credit`'s alone (`test_wallet_credit`).
    for r in _stream(Donation.objects.all(), 'id', org,
                     'recorded_by_email', 'recorded_at', 'finance_checked_by_email',
                     'finance_checked_at', 'confirmed_by_email', 'confirmed_at'):
        for verb, stem in ((V.CREDIT_RECORDED, 'recorded'), (V.CREDIT_CHECKED, 'finance_checked'),
                           (V.CREDIT_CONFIRMED, 'confirmed')):
            if r[f'{stem}_at'] is not None:
                yield _Cand(verb, _email(r[f'{stem}_by_email']), 'credit', r['id'], r[org],
                            r[f'{stem}_at'])


def _templates():
    from .models import ContractTemplate
    for r in _stream(ContractTemplate.objects.all(), 'id', 'organisation_id', 'created_by_email',
                     'created_at', 'vetting_attested_by_email', 'vetting_attested_at',
                     'submitted_by_email', 'submitted_by_at', 'deployed_by_email', 'deployed_by_at'):
        for verb, by, at in ((V.CONTRACT_TEMPLATE_CREATED, 'created_by_email', 'created_at'),
                             (V.CONTRACT_TEMPLATE_VETTED, 'vetting_attested_by_email',
                              'vetting_attested_at'),
                             (V.CONTRACT_TEMPLATE_SUBMITTED, 'submitted_by_email', 'submitted_by_at'),
                             (V.CONTRACT_TEMPLATE_DEPLOYED, 'deployed_by_email', 'deployed_by_at')):
            if r[at] is not None:
                yield _Cand(verb, _email(r[by]), 'contract_template', r['id'], r['organisation_id'],
                            r[at])


def _benefactors():
    from .models import Sponsor, SponsorProgrammeMembership
    for r in _stream(Sponsor.objects.filter(reviewed_at__isnull=False), 'id', 'status',
                     'reviewed_by', 'reviewed_at'):
        yield _Cand(V.BENEFACTOR_VETTED, _email(r['reviewed_by']), 'sponsor', r['id'], None,
                    r['reviewed_at'], {'decision': r['status'], 'kind': 'account'})
    for r in _stream(SponsorProgrammeMembership.objects.filter(vetted_at__isnull=False),
                     'sponsor_id', 'programme_id', 'status', 'vetted_by', 'vetted_at',
                     'programme__organisation_id'):
        actor = _email(r['vetted_by'])
        yield _Cand(V.BENEFACTOR_VETTED, actor, 'sponsor', r['sponsor_id'],
                    r['programme__organisation_id'], r['vetted_at'],
                    {'decision': r['status'], 'kind': 'programme', 'programme': r['programme_id']},
                    skip=None if actor or not r['vetted_by'] else NAME_ONLY)


def _invoices():
    from .models import Invoice, InvoicePaymentDeclaration, InvoiceReceipt
    for r in _stream(Invoice.objects.all(), 'id', 'organisation_id', 'issued_by_email', 'created_at',
                     'sent_by_email', 'sent_at', 'voided_by_email', 'voided_at'):
        for verb, by, at in ((V.INVOICE_ISSUED, 'issued_by_email', 'created_at'),
                             (V.INVOICE_SENT, 'sent_by_email', 'sent_at'),
                             (V.INVOICE_VOIDED, 'voided_by_email', 'voided_at')):
            if r[at] is None:
                continue
            if not r[by]:       # the monthly cron issues with no address
                yield _Cand(verb, None, at=r[at], skip=NO_ACTOR)
                continue
            yield _Cand(verb, _email(r[by]), 'invoice', r['id'], r['organisation_id'], r[at])
    org = 'invoice__organisation_id'
    for r in _stream(InvoicePaymentDeclaration.objects.all(), 'id', 'invoice_id', org,
                     'declared_by_email', 'declared_at', 'rejected_by_email', 'rejected_at'):
        yield _Cand(V.PAYMENT_DECLARED, _email(r['declared_by_email']), 'invoice', r['invoice_id'],
                    r[org], r['declared_at'], {'declaration': r['id']})
        if r['rejected_at'] is not None:
            yield _Cand(V.PAYMENT_REJECTED, _email(r['rejected_by_email']), 'invoice',
                        r['invoice_id'], r[org], r['rejected_at'], {'declaration': r['id']})
    for r in _stream(InvoiceReceipt.objects.all(), 'id', 'invoice_id', org, 'recorded_by_email',
                     'created_at'):
        yield _Cand(V.PAYMENT_CONFIRMED, _email(r['recorded_by_email']), 'invoice', r['invoice_id'],
                    r[org], r['created_at'], {'receipt': r['id']})


def _org_requests():
    from .models import OrgRequest
    for r in _stream(OrgRequest.objects.all(), 'id', 'organisation_id', 'submitted_by_id',
                     'created_at', 'approved_by_id', 'approved_at', 'status', 'updated_at'):
        yield _Cand(V.ORG_REQUEST_RAISED, r['submitted_by_id'], 'org_request', r['id'],
                    r['organisation_id'], r['created_at'],
                    skip=None if r['submitted_by_id'] else NO_ACTOR)
        if r['approved_at'] is not None:
            yield _Cand(V.ORG_REQUEST_APPROVED, r['approved_by_id'], 'org_request', r['id'],
                        r['organisation_id'], r['approved_at'],
                        skip=None if r['approved_by_id'] else NO_ACTOR)
        if r['status'] == 'declined':       # who and when are not recorded (only the role)
            yield _Cand(V.ORG_REQUEST_DECLINED, None, skip=NO_ACTOR)


def _merchant_flags():
    from .models import MerchantFlagNote
    for r in _stream(MerchantFlagNote.objects.filter(kind__in=('open', 'close')), 'flag_id', 'kind',
                     'author_email', 'created_at', 'flag__organisation_id'):
        yield _Cand(V.MERCHANT_FLAG_OPENED if r['kind'] == 'open' else V.MERCHANT_FLAG_CLOSED,
                    _email(r['author_email']), 'merchant_flag', r['flag_id'],
                    r['flag__organisation_id'], r['created_at'])


#: Every source, in the order the report prints them.
SOURCES = (_first_sign_ins, _invitations, _permission_changes, _assignments, _queries, _interviews,
           _application_stamps, _reopens, _agreements, _payment_runs, _tranches, _credits,
           _templates, _benefactors, _invoices, _org_requests, _merchant_flags)


# ── the engine ─────────────────────────────────────────────────────────────────────────────────
def email_index():
    """``{address: id}`` for the addresses exactly ONE staff row holds, and the set of ambiguous ones."""
    from apps.courses.models import PartnerAdmin
    seen = defaultdict(list)
    for pk, email in PartnerAdmin.objects.values_list('id', 'email'):
        if email:
            seen[email.strip().casefold()].append(pk)
    return ({e: ids[0] for e, ids in seen.items() if len(ids) == 1},
            {e for e, ids in seen.items() if len(ids) > 1})


def live_cutoff():
    """The earliest LIVE row's moment, or None when there is none yet."""
    return StaffActivity.objects.filter(backfilled=False).aggregate(m=Min('created_at'))['m']


def _key(verb, actor_id, subject_type, subject_id, at):
    return (str(verb), actor_id, subject_type or '', subject_id, at)


def _existing(batch):
    """``(rebuilt keys, live moments)`` among ``batch`` — two queries. ``live`` maps (verb, actor,
    subject type, subject id) to the moments of the LIVE rows near the batch's stamps."""
    verbs = {c.verb for c in batch}
    actors = {c.actor for c in batch}
    lo, hi = min(c.at for c in batch), max(c.at for c in batch)
    near = StaffActivity.objects.filter(verb__in=verbs, actor_id__in=actors)
    rebuilt = near.filter(backfilled=True, created_at__gte=lo, created_at__lte=hi).values_list(
        'verb', 'actor_id', 'subject_type', 'subject_id', 'created_at')
    live = defaultdict(list)
    for r in near.filter(backfilled=False, created_at__gte=lo - TWIN_BEFORE,
                         created_at__lte=hi + TWIN_AFTER).values_list(
            'verb', 'actor_id', 'subject_type', 'subject_id', 'created_at'):
        live[_key(*r)[:4]].append(r[4])
    return {_key(*r) for r in rebuilt}, live


def _has_live_twin(c, live):
    return any(c.at - TWIN_BEFORE <= at <= c.at + TWIN_AFTER
               for at in live.get(_key(c.verb, c.actor, c.subject_type, c.subject_id, None)[:4], ()))


def run(*, apply, before=None, now=None):
    """Read every source; write (``apply``) or only count. Returns the report:
    ``{'cutoff', 'written': Counter(verb), 'skipped': Counter((verb, reason))}``."""
    now = now or timezone.now()
    live = live_cutoff()
    cutoff = live or now
    if before is not None and before < cutoff:
        cutoff = before
    unique, ambiguous = email_index()
    written, skipped = Counter(), Counter()
    batch = []

    def flush():
        if not batch:
            return
        have, live = _existing(batch)
        fresh, keys = [], set()
        for c in batch:
            key = _key(c.verb, c.actor, c.subject_type, c.subject_id, c.at)
            if key in have or key in keys:
                skipped[(str(c.verb), ALREADY)] += 1
                continue
            if _has_live_twin(c, live):
                skipped[(str(c.verb), LIVE_TWIN)] += 1
                continue
            keys.add(key)
            fresh.append(StaffActivity(
                actor_id=c.actor, organisation_id=c.org_id, verb=str(c.verb),
                subject_type=c.subject_type or '', subject_id=c.subject_id,
                meta=staff_activity.clean_meta({k: v for k, v in c.meta.items() if v is not None}),
                created_at=c.at, backfilled=True))
            written[str(c.verb)] += 1
        if apply and fresh:
            StaffActivity.objects.bulk_create(fresh, batch_size=BATCH)
        batch.clear()

    for source in SOURCES:
        for c in source():
            reason = c.skip
            if reason is None and c.at is None:
                reason = NO_TIME
            if reason is None and isinstance(c.actor, tuple):
                address = c.actor[1]
                if address in ambiguous:
                    reason = AMBIGUOUS_EMAIL
                elif address in unique:
                    c.actor = unique[address]
                else:
                    reason = UNKNOWN_EMAIL
            if reason is None and c.actor is None:
                reason = NO_ACTOR
            if reason is None and c.at >= cutoff:
                reason = AFTER_LIVE
            if reason is not None:
                skipped[(str(c.verb), reason)] += 1
                continue
            batch.append(c)
            if len(batch) >= BATCH:
                flush()
        flush()
    return {'cutoff': cutoff, 'live_rows_found': live is not None, 'written': written,
            'skipped': skipped, 'applied': bool(apply)}
