"""The payment-run SIGN-OFF chain: who signs a run, in what order, and cancelling it.

Moved VERBATIM out of `payments.py` (moves-only, staff permissions Sprint 2, request #39) because
`payments.py` sits at its size line and Sprint 2 rewrites exactly this part. Every name below is
re-exported from `payments.py`, so `payments.sign(...)`, `payments.cancel(...)` and
`payments.finance_check_required(...)` keep working for every caller and every test.

⚠ `payments` is imported INSIDE each function, never at the top: `payments.py` imports this module
at its bottom (the re-export), so a top-level import here would be circular whichever module loads
first. It also keeps `mock.patch('apps.scholarship.payments.complete')` reaching `sign`.
"""
from django.db import transaction
from django.utils import timezone


def finance_check_required(organisation):
    """Does this organisation's payment chain include the finance CHECK step?

    True iff it has at least one ACTIVE ``finance`` PartnerAdmin. Evaluated LIVE at every sign
    attempt and **never persisted on the run** — deliberately, because the owner's rule runs in
    both directions:

      * activating a finance admin while a run sits at ``admin_signed`` DOES arm the check for
        that run (the approver is blocked with ``finance_check_required`` until finance signs);
      * revoking the last finance admin mid-run degrades the chain back to two steps, and an
        already-collected finance signature is never treated as a blocker.

    A stored flag would freeze the shape at creation and get the first case wrong. The cost is
    one cheap indexed EXISTS per sign attempt, which is a rare operation.
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


@transaction.atomic
def sign(run, admin, typed_name):
    """The maker→[finance]→approver sign-off (D2 + Sprint 14).

      * DRAFT → the MAKER (role ``admin``, or super) signs → ``admin_signed``.
      * ADMIN_SIGNED, finance ACTIVE → only the CHECKER (role ``finance``, or super) may sign
        → ``finance_checked``. An org_admin trying to countersign here gets
        ``finance_check_required``.
      * ADMIN_SIGNED, finance DORMANT → the APPROVER (``org_admin``, or super) countersigns →
        ``complete(run)`` → ``completed``. This is the original path, unchanged.
      * FINANCE_CHECKED → the APPROVER countersigns → ``complete(run)`` → ``completed``.

    Guards: ``bad_state``; ``name_mismatch`` (typed name vs PartnerAdmin.name); ``wrong_role``;
    and ``same_signer`` — now PAIRWISE distinctness across every signature already collected,
    which is what confines a ``super`` to one slot per run without a special case for supers.
    Returns the run."""
    from .payments import PaymentsError, _name_matches, complete
    if run.status not in ('draft', 'admin_signed', 'finance_checked'):
        raise PaymentsError('bad_state')
    if not _name_matches(admin, typed_name):
        raise PaymentsError('name_mismatch')
    is_super = bool(getattr(admin, 'is_super', False))
    email = (admin.email or '').strip().casefold()
    now = timezone.now()
    needs_finance = finance_check_required(run.organisation)

    if run.status == 'draft':
        if not (is_super or admin.role == 'admin'):
            raise PaymentsError('wrong_role')
        run.admin_signed_name = (admin.name or '').strip()[:200]
        run.admin_signed_email = (admin.email or '')[:254]
        run.admin_signed_at = now
        run.status = 'admin_signed'
        run.save(update_fields=[
            'admin_signed_name', 'admin_signed_email', 'admin_signed_at', 'status', 'updated_at'])
        # Route the "your turn" email to whoever is actually next: the finance checker when the
        # org has one, else the org admins who countersign. Best-effort — neither raises.
        from . import emails
        if needs_finance:
            emails.send_payment_finance_check_email(run)
        else:
            emails.send_payment_countersign_email(run)
        return run

    if run.status == 'admin_signed' and needs_finance:
        # The check is armed. Only finance (or super) passes here — an org_admin is told WHY
        # rather than getting a bare wrong_role, because from their seat nothing looks amiss.
        if not (is_super or admin.role == 'finance'):
            if admin.role == 'org_admin':
                raise PaymentsError('finance_check_required')
            raise PaymentsError('wrong_role')
        if email in _collected_signer_emails(run):
            raise PaymentsError('same_signer')
        run.finance_signed_name = (admin.name or '').strip()[:200]
        run.finance_signed_email = (admin.email or '')[:254]
        run.finance_signed_at = now
        run.status = 'finance_checked'
        run.save(update_fields=[
            'finance_signed_name', 'finance_signed_email', 'finance_signed_at',
            'status', 'updated_at'])
        from . import emails
        emails.send_payment_countersign_email(run)
        return run

    # admin_signed (finance dormant) or finance_checked → the approver countersigns.
    # A `finance` caller reaching here means the org has no active finance admin (dormant) or the
    # check is already done — either way countersigning is not their step: wrong_role.
    if not (is_super or admin.role == 'org_admin'):
        raise PaymentsError('wrong_role')
    if email in _collected_signer_emails(run):
        raise PaymentsError('same_signer')
    run.org_admin_signed_name = (admin.name or '').strip()[:200]
    run.org_admin_signed_email = (admin.email or '')[:254]
    run.org_admin_signed_at = now
    run.status = 'completed'
    run.save(update_fields=[
        'org_admin_signed_name', 'org_admin_signed_email', 'org_admin_signed_at',
        'status', 'updated_at'])
    complete(run)
    return run


def cancel(run, by=''):
    """Cancel a run at any pre-completion status (never a completed one). Cancelling stays an
    admin / org_admin power — finance checks a run, it does not withdraw one."""
    from .payments import EDITABLE_STATUSES, PaymentsError
    if run.status not in EDITABLE_STATUSES:
        raise PaymentsError('bad_state')
    run.status = 'cancelled'
    run.note = (run.note or '')
    run.save(update_fields=['status', 'updated_at'])
    return run
