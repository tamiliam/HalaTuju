"""Sponsorship: the off-platform wallet credit (record, sign, cancel). The only place an
admin-recorded credit is minted.

Moved unchanged out of ``sponsorship.py`` when audit A3.8 (2026-11-10) made it a package.
"""
from django.db import transaction
from django.utils import timezone

from ..models import Donation


class CreditError(Exception):
    """Raised by the wallet-credit chain with a machine code for the view."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


@transaction.atomic
def record_admin_credit(*, sponsor, programme, amount, external_reference, admin):
    """Record an OFF-PLATFORM gift into a sponsor's programme wallet (P4).

    **This is the sole creator of a ``source='admin_recorded'`` Donation** — a source guard
    test asserts nothing else creates one, so an unconfirmed credit can never appear by a
    side door. The row opens at ``draft`` and is NOT spendable until the chain completes.

    Context: until BrightPath's CLBG is registered every sponsor pays into a personal
    account and an org admin keys the credit in here — *"real money is off the platform,
    but the consequences aren't"*. ``external_reference`` (the bank-transfer ref) is
    therefore mandatory: it is the only thread back to the money, and it is what makes each
    credit reconcile 1:1 with a bank-statement line (owner: one row per bank transfer).

    Creates the row at ``draft`` and stamps NO signature — recording and signing are
    separate acts, exactly as ``payments.create_run`` is separate from ``payments.sign``.
    The maker's signature is collected by ``sign_admin_credit`` with a typed name.

    Role gate: the MAKER's role (``admin``) or a super — the same gate that opens the
    chain. ``org_admin`` is deliberately NOT admitted here: on prod the person who does
    this work is Poongulali Veeran, a plain ``admin`` (verified against live roles,
    2026-07-26), and the approver must stay free to countersign.
    """
    if not (getattr(admin, 'is_super', False) or getattr(admin, 'role', '') == 'admin'):
        raise CreditError('wrong_role')
    if amount is None or amount <= 0:
        raise CreditError('invalid_amount')
    if not (external_reference or '').strip():
        raise CreditError('external_reference_required')
    if programme is None:
        raise CreditError('programme_required')
    if not _is_accepted_into(sponsor, programme):
        # A credit into a gift the sponsor was never accepted into would be money they
        # could not spend — and a sign the wrong sponsor or programme was picked.
        raise CreditError('sponsor_not_in_programme')
    return Donation.objects.create(
        sponsor=sponsor, programme=programme, amount=amount,
        source=Donation.SOURCE_ADMIN, external_reference=external_reference.strip(),
        reference=external_reference.strip(),
        status=Donation.STATUS_DRAFT,
    )


def _is_accepted_into(sponsor, programme):
    from ..models import SponsorProgrammeMembership
    return SponsorProgrammeMembership.objects.filter(
        sponsor=sponsor, programme=programme, status='approved').exists()


@transaction.atomic
def sign_admin_credit(credit, admin, typed_name):
    """The maker→[finance]→approver sign-off for a wallet credit.

    **Deliberately ONE function with the same shape and the same guard names as
    ``payments.sign``** — the two chains are one design (decisions.md), and a single
    mirrored function is what stops them drifting into two subtly different controls.

      * DRAFT → the MAKER (role ``admin``, or super) signs → ``admin_signed``.
      * ADMIN_SIGNED, finance ACTIVE → only the CHECKER (``payments_approve``, TD-475; or super) may
        sign → ``finance_checked``. An org_admin trying to countersign here gets
        ``finance_check_required`` (told WHY, not a bare wrong_role — from their seat
        nothing looks amiss).
      * ADMIN_SIGNED, finance DORMANT → the APPROVER (``org_admin``, or super)
        countersigns → ``confirmed``. This is BrightPath's live path today.
      * FINANCE_CHECKED → the APPROVER countersigns → ``confirmed``.

    ``confirmed`` is the step that makes the money spendable (``Donation.is_spendable``).

    Guards: ``bad_state``; ``name_mismatch`` (typed name vs ``PartnerAdmin.name`` — this is
    what closed TD-176: before P4b the signer was a free string, so the chain enforced
    distinctness but NOT identity); ``wrong_role``; and ``same_signer`` — pairwise
    distinctness across every signature already collected, which is what confines a
    ``super`` to one slot per credit without a special case for supers.

    ``finance_check_required`` is evaluated LIVE at every attempt and never stored, so
    giving someone ``payments_approve`` ARMS the check for a credit already mid-chain, and revoking
    the last holder degrades it back to two steps. ⚠ The rule is
    ``payments.credit_check_required`` (a key since TD-475, A1.10a; a role before). WHO may sign
    which step is `credit_steps.step_refusal` since T5c P5b (the Overview counts with it). Returns the credit.
    """
    from .. import credit_steps, payments, staff_activity
    if credit.status not in credit_steps.SIGNING:
        raise CreditError('bad_state')
    if not payments._name_matches(admin, typed_name):
        raise CreditError('name_mismatch')
    now = timezone.now()
    needs_finance = payments.credit_check_required(_credit_org(credit), credit)   # TD-475; per credit
    refusal = credit_steps.step_refusal(credit, admin, needs_finance)
    if refusal:
        raise CreditError(refusal)

    if credit.status == Donation.STATUS_DRAFT:
        credit.recorded_by = (admin.name or '').strip()[:200]
        credit.recorded_by_email = (admin.email or '')[:254]
        credit.recorded_at = now
        credit.status = Donation.STATUS_ADMIN_SIGNED
        credit.save(update_fields=[
            'recorded_by', 'recorded_by_email', 'recorded_at', 'status'])
        staff_activity.record(admin, staff_activity.CREDIT_RECORDED, credit)   # common profile S4
        return credit

    if credit.status == Donation.STATUS_ADMIN_SIGNED and needs_finance:
        credit.finance_checked_by = (admin.name or '').strip()[:200]
        credit.finance_checked_by_email = (admin.email or '')[:254]
        credit.finance_checked_at = now
        credit.status = Donation.STATUS_FINANCE_CHECKED
        credit.save(update_fields=[
            'finance_checked_by', 'finance_checked_by_email', 'finance_checked_at', 'status'])
        staff_activity.record(admin, staff_activity.CREDIT_CHECKED, credit)
        return credit

    # admin_signed (finance dormant) or finance_checked → the approver countersigns.
    credit.confirmed_by = (admin.name or '').strip()[:200]
    credit.confirmed_by_email = (admin.email or '')[:254]
    credit.confirmed_at = now
    credit.status = Donation.STATUS_CONFIRMED
    credit.save(update_fields=[
        'confirmed_by', 'confirmed_by_email', 'confirmed_at', 'status'])
    staff_activity.record(admin, staff_activity.CREDIT_CONFIRMED, credit)
    # S3: tell the donor, but ONLY here — this is the single line in the chain where the money
    # becomes spendable, and it is the only point at which saying "we hold it" is true. Fired
    # from the SERVICE rather than the endpoint so a shell-driven confirmation notifies too, and
    # imported locally to keep this money module free of a hard dependency on the sending layer.
    from .. import sponsor_notify
    sponsor_notify.send_credit_confirmed(credit)
    return credit


@transaction.atomic
def cancel_admin_credit(credit, admin):
    """Void a credit that has not yet been confirmed — a mis-keyed amount or bank reference
    would otherwise be permanent (the row is never deleted; the audit trail is the point).

    Maker's role or super, and only before ``confirmed``: once money is spendable it is
    reversed by a compensating entry, never by editing history."""
    if not (getattr(admin, 'is_super', False) or getattr(admin, 'role', '') in
            ('admin', 'org_admin')):
        raise CreditError('wrong_role')
    if credit.status not in (Donation.STATUS_DRAFT, Donation.STATUS_ADMIN_SIGNED,
                             Donation.STATUS_FINANCE_CHECKED):
        raise CreditError('bad_state')
    credit.status = Donation.STATUS_CANCELLED
    credit.save(update_fields=['status'])
    return credit


def _credit_org(credit):
    """The organisation whose credit checkers govern this credit — the one running the gift."""
    return credit.programme.organisation if credit.programme_id else None
