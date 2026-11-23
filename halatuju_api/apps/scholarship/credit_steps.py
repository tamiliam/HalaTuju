"""Whose signature a wallet credit waits for — the ONE home of the credit chain's step rule
(T5c P5b S1, 2026-11-05).

`sponsorship.sign_admin_credit` asks `step_refusal` before it writes a signature; the Overview's
`wallet_credits` card (`my_pending`) asks the same function to count the credits waiting for THIS
person. Pulled out of `sign_admin_credit` so the two can never disagree, and into a module of its
own because `sponsorship.py` sits at its `oversize_files` allowance.

The chain (see `sign_admin_credit`'s docstring for the why). S3 / M4b (owner rulings Q-A to Q-C, 23 Nov):
every seat is a switch, never a role label.

  * DRAFT -> the MAKER (`may_record`): a team member with Sponsors: edit stored in their own seat, or a
    super. An organisation admin never records or signs first;
  * ADMIN_SIGNED with the check ARMED -> only the CHECKER (`holds_checker_seat`: `sponsors.check`, which
    Payments Approve brings), or a super; an approver who is not a checker is told
    ``finance_check_required``;
  * ADMIN_SIGNED with the check dormant, or FINANCE_CHECKED -> the APPROVER (`may_approve`): Organisation
    admin powers or Payments Approve, or a super;
  * and nobody signs twice (``same_signer``, by email) — except the maker's step, which has no earlier
    signature to collide with. So nobody approves a credit they recorded or checked.

TD-475 (A1.10a): the check is armed PER CREDIT, only while a signed-in holder who has not signed it
exists (`payments_chain.credit_check_required`), so a keyed maker never strands their own credit.
"""
from apps.courses.public import staff_permissions, staff_tables
from .models import Donation

#: The statuses still waiting for a signature (`sign_admin_credit`'s ``bad_state`` is everything else).
SIGNING = (Donation.STATUS_DRAFT, Donation.STATUS_ADMIN_SIGNED, Donation.STATUS_FINANCE_CHECKED)

#: S3 / M4b: the Payments switch an approver may hold instead of Organisation admin powers (owner Q-C).
APPROVE_KEY = 'payments_approve'


def may_record(admin):
    """RECORD a credit and sign it FIRST (S3 / M4b, owner Q-A, 23 Nov): a super, or a team member (never
    the organisation admin) with Sponsors: edit stored in their own seat — the `credits_write` door, which
    a team member opens only through a stored `sponsors.edit` (the v2 module's `effective_v2`)."""
    return bool(admin is not None and (
        admin.is_super or (not staff_permissions.is_lead_tier(admin)
                           and staff_tables.opens_door(admin, 'credits_write'))))


def may_cancel(admin):
    """VOID a credit before it is confirmed (owner Q-B, 23 Nov): Sponsors: edit, as the door asks."""
    return staff_tables.opens_door(admin, 'credits_write')


def holds_checker_seat(admin):
    """The CHECKER seat (`credits_check` = `sponsors.check`, which `payments_approve` means through
    `ALIASES`): a team member or an organisation admin, never a super (a super passes the step but is
    never a holder, so never arms it)."""
    return bool(admin is not None and not admin.is_super and staff_tables.opens_door(admin, 'credits_check'))


def may_approve(admin):
    """COUNTERSIGN a credit (owner Q-C, 23 Nov): a super, Organisation admin powers, or the Payments
    Approve switch. Never a credit they recorded or checked (`same_signer`, in `step_refusal`). An inactive
    row never approves, whoever calls (M4b review nit: not left to the caller)."""
    return bool(admin is not None and getattr(admin, 'is_active', True) and (
        admin.is_super or staff_permissions.holds_org_admin_powers(admin)
        or staff_permissions.holds(admin, APPROVE_KEY)))


def opens_check(old_keys):
    """Do these OLD keys (an editor's before / after list) hold the checker seat? Read through the
    aliases, as the door reads them, so no reader names the key that means it."""
    return staff_tables.old_keys_open(old_keys, 'credits_check')


def checker_holders(organisation, staff=None):
    """The organisation's ACTIVE staff in the checker seat (never a super), as a list. `staff` is that
    organisation's `staff_permissions.org_staff`, when a caller has it already."""
    if organisation is None:
        return []
    if staff is None:
        staff = staff_permissions.org_staff(organisation)
    return [a for a in staff if holds_checker_seat(a)]


def collected_signer_emails(credit):
    """Every email that has already signed this credit, casefolded — the basis of the
    three-distinct-signers rule. Keyed on EMAIL, never on the displayed name: prod has two
    active admins sharing the name "Ve. Elanjelian", so a name key would be wrong in both
    directions (see the 0125 migration docstring). Mirrors
    ``payments._collected_signer_emails``."""
    return {
        (e or '').strip().casefold()
        for e in (credit.recorded_by_email, credit.finance_checked_by_email,
                  credit.confirmed_by_email)
        if (e or '').strip()
    }


def step_refusal(credit, admin, needs_finance):
    """Why `admin` may NOT sign `credit`'s next step — ``'wrong_role'``, ``'finance_check_required'``,
    ``'same_signer'`` — or None when they may. `credit` must be in `SIGNING` (the caller checks
    ``bad_state`` first); `needs_finance` is ``payments.credit_check_required(<the credit's org>,
    credit)`` — armed only while a holder who has NOT signed this credit exists (A1.10a review fix)."""
    if credit.status == Donation.STATUS_DRAFT:
        return None if may_record(admin) else 'wrong_role'
    if credit.status == Donation.STATUS_ADMIN_SIGNED and needs_finance:
        if not (admin.is_super or holds_checker_seat(admin)):
            return 'finance_check_required' if may_approve(admin) else 'wrong_role'
    elif not may_approve(admin):
        return 'wrong_role'
    if (admin.email or '').strip().casefold() in collected_signer_emails(credit):
        return 'same_signer'
    return None


def checks_credits(admin):
    """Could a credit wait for this person (TD-503, S3 / M4b): a team member or organisation admin in the
    maker, checker or approver seat? The Overview's `wallet_credits` card is theirs (was: the checker
    only). A super is no seat-holder here, as before: their Overview counts no credits. An inactive row
    holds no seat (M4b review nit)."""
    return bool(admin is not None and not admin.is_super and getattr(admin, 'is_active', True)
                and (may_record(admin) or holds_checker_seat(admin) or may_approve(admin)))


def served(credit, admin, armed):
    """What the sponsor page may draw for `credit` and this person (S3 / M4b; the web derives none of it):
    ``can_sign`` (the next step is theirs, `step_refusal`, `same_signer` included), ``blocked`` (
    ``'awaiting_finance'`` when they would approve but the check comes first) and ``can_void``
    (`may_cancel`, before the money is spendable). `armed` is the credit's own `credit_check_required`."""
    if credit.status not in SIGNING:
        return {'can_sign': False, 'blocked': None, 'can_void': False}
    refusal = step_refusal(credit, admin, armed)
    return {'can_sign': refusal is None,
            'blocked': 'awaiting_finance' if refusal == 'finance_check_required' else None,
            'can_void': may_cancel(admin)}


def waiting_for(admin, credits, cache=None):
    """How many of `credits` (in `SIGNING`, each with ``programme__organisation`` selected) wait for
    `admin`'s signature now. The checker holders are read once per organisation; whether the check is
    armed is per credit (a holder who signed it does not count, `credit_check_required`). `cache` is a
    `payments_chain` staff cache, so the Overview reads each organisation's staff once for both cards."""
    from . import payments, payments_chain
    held = {}
    n = 0
    for credit in credits:
        org = credit.programme.organisation if credit.programme_id else None
        key = getattr(org, 'pk', None)
        if key not in held:
            held[key] = checker_holders(org, None if (org is None or cache is None)
                                        else payments_chain._staff(key, cache))
        needs = payments.credit_check_required(org, credit, held[key])
        if step_refusal(credit, admin, needs) is None:
            n += 1
    return n
