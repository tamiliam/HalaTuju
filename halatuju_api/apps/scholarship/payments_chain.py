"""The payment-run SIGN-OFF chain: who signs a run, in what order, and cancelling it.

Moved out of `payments.py` (moves-only, staff permissions Sprint 2, request #39) because `payments.py`
sits at its size line, then rewritten here. Every public name is re-exported from `payments.py`, so
`payments.sign(...)`, `payments.cancel(...)` and `payments.finance_check_required(...)` keep working.

⚠ `payments` is imported INSIDE each function, never at the top: `payments.py` imports this module
at its bottom (the re-export), so a top-level import here would be circular whichever module loads
first. It also keeps `mock.patch('apps.scholarship.payments.complete')` reaching `sign`.

THE CHAIN SINCE REQUEST #39 SPRINT 2 (owner, 2026-10-19, option A: *"Finance role currently doesn't
have clear action items. I would like the role to be able to approve payment — the work that Suresh
does today."*). It reads PERMISSIONS (`PartnerAdmin.has_perm`), not roles:

    draft         --(payments_prepare: the MAKER signs)----------------------------> admin_signed
    admin_signed  --(payments_check, ONLY while an active member holds it)---------> finance_checked
    admin_signed / finance_checked --(payments_approve: the APPROVER signs)--------> completed
                                                                                     -> complete(run)

* **The approver, with a per-run fallback.** The approvers of a run are the organisation's active
  `payments_approve` holders who have NOT already signed it. If there are none, the organisation
  admin (the lead tier) approves, exactly as before the change. So an organisation with no Finance
  person works as it always did, BrightPath's Suresh drops out as soon as a Finance person exists,
  and no run can strand (the sole approver who is also its maker; the last approver revoked or
  switched mid-run; a run already `finance_checked` by the only Finance person).
* **The check stays live and is never stored** (decision 2026-07-23, kept): armed while an active
  member holds `payments_check`. No preset holds it after Sprint 2, so the chain is two steps
  everywhere until somebody is given it — a third signer is one permission away.
* **Pairwise-distinct signers, unchanged:** nobody signs one run twice in any two slots; a super
  passes every permission and still fills only ONE slot.
* **Wallet credits keep TODAY's rule** (question 6): `credit_check_required` below, a role rule,
  deliberately NOT the re-keyed run predicate. The old shared predicate would otherwise have
  silently switched OFF Finance's check on sponsor credits the day Finance stopped holding the check.
* `next_step_for` is the ONE predicate behind both the gate (`sign`) and the screen (`your_step`,
  the "Waiting for you" list, the menu badge), so the list and the gate cannot disagree.

The three signature triples are reused (no migration): maker -> `admin_signed_*`, check ->
`finance_signed_*`, approver -> `org_admin_signed_*` (a misnomer now, kept: renaming a column on a
live money table costs a cutover and changes no behaviour).
"""
from django.db import transaction
from django.utils import timezone

#: The step a person may take on a run now — `next_step_for`'s answers, served as `your_step`.
STEP_SIGN, STEP_CHECK, STEP_APPROVE = 'sign', 'check', 'approve'
_IN_FLIGHT = ('draft', 'admin_signed', 'finance_checked')


def _org_id(run):
    """The run's organisation id WITHOUT loading the organisation (a list asks this once per run).
    Falls back to `run.organisation.id` for a duck-typed run that only carries the object."""
    org_id = getattr(run, 'organisation_id', None)
    if org_id is None:
        org_id = getattr(getattr(run, 'organisation', None), 'id', None)
    return org_id


def _holders(organisation_id, key, cache=None):
    """`staff_permissions.holders`, memoised per call site (a list page asks once per organisation)."""
    if organisation_id is None:
        return []
    from apps.courses import staff_permissions
    if cache is None:
        return staff_permissions.holders(organisation_id, key)
    slot = (organisation_id, key)
    if slot not in cache:
        cache[slot] = staff_permissions.holders(organisation_id, key)
    return cache[slot]


def _signed_in(admin):
    """Has this person EVER opened the console (`first_seen_at`, stamped by `get_admin` on their first
    request)? Review fix 4 (2026-10-19): a holder who has never signed in cannot sign a run, so they
    must not take the step away from somebody who can. Production that day: BrightPath's only Finance
    person had never signed in — counting them would have left every run waiting for nobody. The
    moment they sign in, they become eligible. A super never needs this (supers are never holders)."""
    return getattr(admin, 'first_seen_at', None) is not None


def _is_lead_tier(admin):
    from apps.courses import staff_permissions
    return staff_permissions.is_lead_tier(admin)


def finance_check_required(organisation, cache=None):
    """Could this ORGANISATION's run chain include the CHECK step at all? True iff an ACTIVE member who
    has signed in holds `payments_check` (`staff_permissions.holders`, never a super). Live, never
    stored (decision 2026-07-23, kept).

    ⚠ Whether a given RUN needs the check is `check_required_for(run)` (review fix 2: per run, like the
    approval) — `sign`, `next_step_for` and the payload all ask that. This organisation-level reading is
    kept for the golden table and for callers that have no run. ⚠ Until #39 Sprint 2 this read "an
    active `finance` person exists"; Finance now APPROVES and no preset holds the check, so on deploy
    it is False everywhere. ⚠ Wallet credits do NOT read this — see `credit_check_required`.
    """
    org_id = getattr(organisation, 'id', organisation)
    return any(_signed_in(a) for a in _holders(org_id, 'payments_check', cache))


#: The same organisation-level predicate under the name the screen will keep.
check_step_required = finance_check_required


def credit_check_required(organisation):
    """Does this organisation's WALLET-CREDIT chain include the finance check? TODAY's rule, unchanged.

    True iff it has at least one ACTIVE `finance` PartnerAdmin. Live, never stored. This is the body
    `finance_check_required` had before #39 Sprint 2, split out so sponsor credits keep Admin
    records -> Finance checks -> the organisation admin countersigns (owner question 6: accepting money
    is the organisation's act). A DELIBERATE divergence from the 2026-07-26 "one chain" decision;
    moving credits onto permissions later is about 3 h.
    """
    if organisation is None:
        return False
    from apps.courses.models import PartnerAdmin
    return PartnerAdmin.objects.filter(
        owning_organisation=organisation, role='finance', is_active=True).exists()


def _collected_signer_emails(run):
    """Every email that has already signed this run, casefolded — the basis of the
    three-distinct-signers rule (generalised from the old maker-vs-approver `same_signer`)."""
    return {
        (e or '').strip().casefold()
        for e in (run.admin_signed_email, run.finance_signed_email, run.org_admin_signed_email)
        if (e or '').strip()
    }


def _email(admin):
    return (getattr(admin, 'email', '') or '').strip().casefold()


def eligible_checkers(run, cache=None):
    """Active `payments_check` holders of the run's organisation who have signed in and have NOT
    signed this run."""
    signed = _collected_signer_emails(run)
    return [a for a in _holders(_org_id(run), 'payments_check', cache)
            if _signed_in(a) and _email(a) not in signed]


def check_required_for(run, cache=None):
    """Does THIS run need the check? Review fix 2 (2026-10-19): per run, like the approval — only if
    somebody ELIGIBLE for this run could take it. So a person holding Prepare + Check who prepared a
    run can never strand it: with nobody else to check, it goes straight to approval."""
    return bool(eligible_checkers(run, cache))


def eligible_approvers(run, cache=None):
    """Active `payments_approve` holders of the run's organisation who have signed in and have NOT
    signed this run."""
    signed = _collected_signer_emails(run)
    return [a for a in _holders(_org_id(run), 'payments_approve', cache)
            if _signed_in(a) and _email(a) not in signed]


def approver_fallback(run, cache=None):
    """True when NOBODY eligible holds the approval for this run, so the organisation admin approves
    (today's path). Re-asked live, per run: it switches on and off with the people, never stored."""
    return not eligible_approvers(run, cache)


def fallback_approvers(run):
    """The organisation admins who approve under the fallback: active, not already a signer."""
    from apps.courses.models import PartnerAdmin
    signed = _collected_signer_emails(run)
    return [a for a in PartnerAdmin.objects.filter(
                owning_organisation_id=_org_id(run), role='org_admin', is_active=True,
                is_super_admin=False).order_by('id')
            if _email(a) not in signed]


def _in_organisation(run, admin):
    """A super acts anywhere (one slot per run); everybody else only on their own organisation's run.
    The view's fence already answers a cross-organisation run with 404; this is the service's own."""
    if getattr(admin, 'is_super', False):
        return True
    org_id = _org_id(run)
    return org_id is not None and getattr(admin, 'owning_organisation_id', None) == org_id


def _holds_eligibly(admin, key):
    """Holds `key` and could use it: a super always; anybody else once they have signed in."""
    return admin.has_perm(key) and (getattr(admin, 'is_super', False) or _signed_in(admin))


def _may_approve(run, admin, cache=None):
    if _holds_eligibly(admin, 'payments_approve'):
        return True
    return _is_lead_tier(admin) and approver_fallback(run, cache)


def may_read(admin):
    """Who opens Payments at all (list, run, CSV, funding summary): any `payments_*` key, or the lead
    tier (the organisation admin creates, edits and cancels runs and is the fallback approver)."""
    return admin is not None and (
        any(admin.has_perm(k) for k in ('payments_prepare', 'payments_check', 'payments_approve'))
        or _is_lead_tier(admin))


def may_prepare(admin):
    """Who creates, edits and cancels a run: `payments_prepare`, or the lead tier (who never signs as
    maker). Finance does not: approving a run is not authoring or withdrawing one."""
    return admin is not None and (admin.has_perm('payments_prepare') or _is_lead_tier(admin))


def next_step_for(run, admin, cache=None):
    """The step `admin` may take on `run` NOW — `'sign'`, `'check'`, `'approve'` — or None.

    THE ONE PREDICATE behind `sign` (the gate) and `your_step` (the list, the "Waiting for you" block
    and the menu badge), so the screen can never offer a step the server refuses, or hide one it
    would allow. Pure apart from reads."""
    if admin is None or run.status not in _IN_FLIGHT or not _in_organisation(run, admin):
        return None
    if _email(admin) in _collected_signer_emails(run):
        return None
    if run.status == 'draft':
        return STEP_SIGN if admin.has_perm('payments_prepare') else None
    if run.status == 'admin_signed' and check_required_for(run, cache):
        return STEP_CHECK if _holds_eligibly(admin, 'payments_check') else None
    return STEP_APPROVE if _may_approve(run, admin, cache) else None


def _refusal(run, admin):
    """WHY `next_step_for` said no — the codes the screen already knows (`wrong_role`, `same_signer`,
    `finance_check_required`), so an operator learns no new vocabulary.

    `finance_check_required` is said ONLY to somebody who would be the approver once the check is in
    (review nit, 2026-10-19): an organisation admin while a Finance person can approve is not waiting
    for the check, he is simply not the approver — `wrong_role`."""
    if not _in_organisation(run, admin) or run.status == 'draft':
        return 'wrong_role'
    if _email(admin) in _collected_signer_emails(run):
        return 'same_signer'
    if run.status == 'admin_signed' and check_required_for(run):
        if _may_approve(run, admin):
            return 'finance_check_required'      # told WHY: from his seat nothing looks amiss
        return 'wrong_role'
    return 'wrong_role'


def _lock(run):
    """Re-read the run's state UNDER A ROW LOCK, so two people acting on one run at once cannot both
    pass on what they last saw. `sign`, `set_item` and `cancel` all start here (review fix 1: an edit
    or a cancel racing the approval could otherwise reopen — and re-pay — a completed run)."""
    from .models import PaymentRun
    if not isinstance(run, PaymentRun) or run.pk is None:
        return
    fields = ('status', 'admin_signed_name', 'admin_signed_email', 'admin_signed_at',
              'finance_signed_name', 'finance_signed_email', 'finance_signed_at',
              'org_admin_signed_name', 'org_admin_signed_email', 'org_admin_signed_at')
    row = PaymentRun.objects.select_for_update().filter(pk=run.pk).values(*fields).first()
    for k, v in (row or {}).items():
        setattr(run, k, v)


@transaction.atomic
def sign(run, admin, typed_name):
    """The maker -> [check] -> approver sign-off (D2, Sprint 14, #39 Sprint 2). The step is
    `next_step_for(run, admin)`; see the module docstring for the chain and the fallback.

    Guards: `bad_state`; `name_mismatch` (typed name vs `PartnerAdmin.name`); then `_refusal`'s
    `wrong_role` / `same_signer` / `finance_check_required`. Emails, best-effort (never raise): after
    the maker, the checkers when the check is armed, else the approvers (else the organisation admins
    under the fallback); after the check, the approvers. Returns the run."""
    from .payments import PaymentsError, _name_matches, complete
    _lock(run)
    if run.status not in _IN_FLIGHT:
        raise PaymentsError('bad_state')
    if not _name_matches(admin, typed_name):
        raise PaymentsError('name_mismatch')
    step = next_step_for(run, admin)
    if step is None:
        raise PaymentsError(_refusal(run, admin))
    now = timezone.now()
    from . import emails

    if step == STEP_SIGN:
        run.admin_signed_name = (admin.name or '').strip()[:200]
        run.admin_signed_email = (admin.email or '')[:254]
        run.admin_signed_at = now
        run.status = 'admin_signed'
        run.save(update_fields=[
            'admin_signed_name', 'admin_signed_email', 'admin_signed_at', 'status', 'updated_at'])
        if check_required_for(run):
            emails.send_payment_finance_check_email(run)
        else:
            emails.send_payment_countersign_email(run)
        return run

    if step == STEP_CHECK:
        run.finance_signed_name = (admin.name or '').strip()[:200]
        run.finance_signed_email = (admin.email or '')[:254]
        run.finance_signed_at = now
        run.status = 'finance_checked'
        run.save(update_fields=[
            'finance_signed_name', 'finance_signed_email', 'finance_signed_at',
            'status', 'updated_at'])
        emails.send_payment_countersign_email(run)
        return run

    # STEP_APPROVE: the final signature completes the run and releases the money.
    run.org_admin_signed_name = (admin.name or '').strip()[:200]
    run.org_admin_signed_email = (admin.email or '')[:254]
    run.org_admin_signed_at = now
    run.status = 'completed'
    run.save(update_fields=[
        'org_admin_signed_name', 'org_admin_signed_email', 'org_admin_signed_at',
        'status', 'updated_at'])
    complete(run)
    return run


@transaction.atomic
def cancel(run, by=''):
    """Cancel a run at any pre-completion status (never a completed one). Who may is the view's
    gate (`may_prepare`: Prepare, or the organisation admin) — Finance approves a run, it does not
    withdraw one."""
    from .payments import EDITABLE_STATUSES, PaymentsError
    _lock(run)        # review fix 1: a stale copy must never cancel a run completed since it was read
    if run.status not in EDITABLE_STATUSES:
        raise PaymentsError('bad_state')
    run.status = 'cancelled'
    run.note = (run.note or '')
    run.save(update_fields=['status', 'updated_at'])
    return run
