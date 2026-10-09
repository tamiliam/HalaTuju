"""A staff member's lifecycle after the invitation: changing their role, and what a CANCEL or a
DELETE does to their sign-in (staff lifecycle sprint, 2026-10-09).

⚠ **A ROLE CHANGES ONLY WITHIN ITS PAIR** (owner, 2026-10-09): Admin ↔ Finance and Reviewer ↔ QC.
Never to or from `org_admin`, `super` or `partner` — those are appointments (a super installs an
organisation admin; a partner is the course selector's referral world), and a role switch that
could reach one would be a privilege path that skips the invite. Same-role and cross-pair requests
are refused with the same code, because both are "not a switch this screen makes".

⚠ **A SWITCH MAY NOT STRAND WORK.** `finance` has no B40 scope at all (`_b40_scope` → 'none') and is
not a review role (`services.REVIEW_ROLES`), so an admin with cases assigned to them would leave
those cases with an owner who cannot open them. Refused while they hold any in-play case
(`apply_gate.IN_PLAY_STATUSES` — the assigned reviewer still acts after an award, S6) and while a
payment run they made or signed is still waiting (as finance they could not sign it again: the
three-distinct-signers rule). Reviewer ↔ QC strands nothing — both are review roles and keep their
assigned cases; the QC self-check guard still stops anybody QC-ing a verdict they recorded.

⚠ **THE FINANCE STEP FOLLOWS THE ROLE, LIVE.** `payments.finance_check_required` reads "an active
finance admin exists" at every sign attempt, so appointing the first one switches the payment
check ON and moving the last one switches it OFF. The plan names that consequence so the screen
can say it BEFORE the click.

⚠ **A LOGIN IS ONLY EVER REMOVED WHEN IT IS OURS AND UNUSED.** `retire_login` deletes the Supabase
user only when nothing else rides on it (no student profile, profile alias or sponsor account),
it has only an email identity, and it either never signed in or never chose its own password.
In doubt it never deletes: it kills a still-owed temporary password and otherwise leaves the
login alone, so the person keeps an account that simply no longer opens the console.
"""
from django.db import transaction
from django.db.models import Q

#: The only switches this screen makes. Symmetric by construction.
ROLE_PAIRS = {'admin': 'finance', 'finance': 'admin', 'reviewer': 'qc', 'qc': 'reviewer'}

FINANCE_CHECK_ON = 'finance_check_on'
FINANCE_CHECK_OFF = 'finance_check_off'


class RoleChangeRefused(Exception):
    """A refusal the view turns into a response: ``code``, ``status``, a sentence, extra fields."""

    def __init__(self, code, status, message, **extra):
        super().__init__(code)
        self.code, self.status, self.message, self.extra = code, status, message, extra


def open_cases(admin):
    """How many in-play applications are assigned to ``admin``."""
    from .models import ScholarshipApplication
    from .services.apply_gate import IN_PLAY_STATUSES
    return ScholarshipApplication.objects.filter(
        assigned_to=admin, status__in=IN_PLAY_STATUSES).count()


#: A payment run still on its way — anything short of `completed` / `cancelled`.
RUN_IN_PROGRESS = ('draft', 'admin_signed', 'finance_checked')


def runs_in_progress(admin):
    """Unfinished payment runs that ``admin`` MADE (whoever has signed it since — review L3) or
    signed as maker."""
    from .models import PaymentRun
    email = (admin.email or '').strip()
    if not email:
        return 0
    return PaymentRun.objects.filter(status__in=RUN_IN_PROGRESS).filter(
        Q(created_by__iexact=email) | Q(admin_signed_email__iexact=email)).count()


def _other_active_finance(target):
    from apps.courses.models import PartnerAdmin
    return (PartnerAdmin.objects.filter(owning_organisation_id=target.owning_organisation_id,
                                        role='finance', is_active=True)
            .exclude(pk=target.pk).exists())


def plan_role_change(target, new_role):
    """What switching ``target`` to ``new_role`` would do, or `RoleChangeRefused`.

    Returns ``{'from', 'to', 'consequence'}`` where consequence is `FINANCE_CHECK_ON`,
    `FINANCE_CHECK_OFF` or None. Pure apart from reads, so a dry run and the real change share it.
    """
    old = target.role
    if target.is_super or ROLE_PAIRS.get(old) != new_role:
        raise RoleChangeRefused(
            'role_not_switchable', 400,
            'That role change is not available. Admin and Finance switch with each other, and '
            'Reviewer and QC switch with each other.')
    if not target.is_active:
        raise RoleChangeRefused(
            'not_active', 400,
            f"{target.name}'s access is revoked. Restore them before changing their role.")
    if new_role == 'finance':
        n = open_cases(target)
        if n:
            raise RoleChangeRefused(
                'has_open_cases', 409,
                f'{target.name} has {n} open case(s) assigned. A finance admin cannot work on '
                'cases, so hand them to someone else first.', open_cases=n)
        if runs_in_progress(target):
            raise RoleChangeRefused(
                'run_in_progress', 409,
                f'{target.name} made or signed a payment run that is not finished. A finance '
                'admin cannot check their own run, so finish it first.')
    consequence = None
    if target.owning_organisation_id is not None:
        if new_role == 'finance' and not _other_active_finance(target):
            consequence = FINANCE_CHECK_ON
        elif old == 'finance' and not _other_active_finance(target):
            consequence = FINANCE_CHECK_OFF
    return {'from': old, 'to': new_role, 'consequence': consequence}


def change_role(target_id, new_role, *, dry_run=False):
    """Plan, and unless ``dry_run`` apply, the switch. Returns ``(target, plan)``.

    The row is LOCKED for the plan and the write, so a revoke or another switch landing in between
    cannot be overwritten; the UPDATE also carries the role it expects, belt and braces. Writes
    `role`, `is_super_admin` (kept in lockstep, as the invite does — never true here) and, moving to
    finance, clears `paused_at` (pause is meaningless for a role that is never assigned work, and a
    "Paused" pill on a finance admin would be a control that lies — `set_paused`'s own rule). An
    OPEN invitation for this person carries the new role too: the Invitations page shows the role
    from it, and a Resend reads the account's.
    """
    from apps.courses.models import PartnerAdmin
    from . import invitations
    from .models import Invitation
    with transaction.atomic():
        target = PartnerAdmin.objects.select_for_update().filter(pk=target_id).first()
        if target is None:
            raise RoleChangeRefused('not_found', 404, 'Admin not found')
        plan = plan_role_change(target, new_role)
        if dry_run:
            return target, plan
        fields = {'role': new_role, 'is_super_admin': False}
        # ⚠ A pause is KEPT between reviewer and QC on purpose: both are review roles that can be
        # assigned work, so "no new work for now" still means something; only Finance clears it.
        if new_role == 'finance':
            fields['paused_at'] = None
        PartnerAdmin.objects.filter(pk=target.pk, role=plan['from'], is_active=True).update(**fields)
        invitations.open_only(Invitation.objects.filter(
            audience='staff', partner_admin=target)).update(role=new_role)
        for k, v in fields.items():
            setattr(target, k, v)
    return target, plan


# ── the login ─────────────────────────────────────────────────────────────────────────────────
def login_used_elsewhere(uid):
    """True when this Supabase login is ALSO somebody's student profile, profile alias or sponsor
    account — then it is theirs, and staff housekeeping never touches it."""
    from apps.courses.models import StudentProfile
    from apps.courses.models_claim import ProfileLoginAlias
    from .models import Sponsor
    return (StudentProfile.objects.filter(supabase_user_id=uid).exists()
            or ProfileLoginAlias.objects.filter(alias_uid=uid).exists()
            or Sponsor.objects.filter(supabase_user_id=uid).exists())


def kill_for_cancel(account, inv):
    """After a staff invitation is cancelled: make the emailed temporary password stop working.

    ⚠ ROTATED, NOT DELETED. The account row stays (a cancel is a status), and a re-invite brings it
    back and issues a FRESH password onto the same login (TD-335) — so the cleanest re-invite keeps
    one identity rather than recreating and relinking one. Only when this invitation issued a
    password, and only while that password is still unchanged (`kill_temp_password`). Best-effort:
    the account is already switched off, so a failure here leaves a password that cannot open the
    console, and the daily expiry job now sweeps switched-off accounts too. Returns a word for the
    AUDIT line."""
    from apps.courses import supabase_admin
    uid = getattr(account, 'supabase_user_id', None)
    if account is None or not uid or not inv.credential_issued:
        return 'skipped'
    if login_used_elsewhere(uid):
        return 'kept'
    return supabase_admin.kill_temp_password(uid)


def _identity_providers(account):
    found = {(i or {}).get('provider') for i in (account.get('identities') or [])}
    found |= set((account.get('app_metadata') or {}).get('providers') or [])
    return {p for p in found if p}


def plan_login_retirement(admin):
    """What a staff DELETE should do to this person's Supabase login — decided, not yet done.

    Returns ``(word, account)``: 'delete' (ours and unused — remove it so a re-invite is a
    brand-new person), 'kill' (used, but a temporary password is still owed — rotate it dead),
    'kept', 'none' (no login linked), or `GONE` / `INERT` / `FAILED` from the read. Only `FAILED`
    should stop the delete. Read-only: the caller acts AFTER the row is gone (`retire_login`), so a
    failure deleting the row can never leave it pointing at a removed login (review M2)."""
    from apps.courses import password_change_flag, supabase_admin
    uid = admin.supabase_user_id
    if not uid:
        return 'none', None
    if login_used_elsewhere(uid):
        return 'kept', None
    account = supabase_admin.read_auth_user(uid)
    if not isinstance(account, dict):
        return account, None
    if (account.get('email') or '').strip().lower() != (admin.email or '').strip().lower():
        return 'kept', None
    owes = password_change_flag.rotation_state(account)[0] is not None
    never_signed_in = not account.get('last_sign_in_at')
    if _identity_providers(account) <= {'email'} and (never_signed_in or owes):
        return 'delete', account
    if owes:
        return 'kill', account
    return 'kept', None


def retire_login(uid, plan, account):
    """Carry out `plan_login_retirement`'s answer once the staff row is gone. Returns a word for
    the AUDIT line; never raises. A failure is logged loudly: what is left is an unused login with
    a dead or owed temporary password, which a re-invite adopts (`adoptable_login`)."""
    import logging
    from apps.courses import supabase_admin
    if plan == 'delete':
        done = supabase_admin.delete_auth_user(uid)
    elif plan == 'kill':
        done = supabase_admin.kill_temp_password(uid, account)
    else:
        return plan
    if done == supabase_admin.FAILED:
        # ⚠ THE ONLY TRACE once the row is gone (review round 2, N3): no staff row points at this
        # login any more, so the daily expiry job cannot find it. Search the logs for this line.
        logging.getLogger('apps.scholarship.staff_lifecycle').error(
            'STAFF_LOGIN_ORPHANED uid=%s action=%s: the row is gone but its Supabase login could '
            'not be %s — remove it by hand in Supabase Auth', uid, plan,
            'deleted' if plan == 'delete' else 'rotated (a temporary password may still work)')
    return done


def adoptable_login(account):
    """True when an EXISTING Supabase login at an address being invited is one WE provisioned and
    nobody uses — a staff login whose row was deleted while its login survived (before this sprint,
    or when the delete's Supabase call failed). Then the invite issues a fresh temporary password
    onto it instead of the "sign in as you always do" note that left a real invitee with no
    password.

    ⚠ ONLY OUR OWN MARK COUNTS: `must_change_password` still owed in `app_metadata`, which only the
    service role writes (TD-322) — never the browser-writable `user_metadata` copy. A student's or
    a sponsor's login never carries it; and nothing else may ride on the login (no student profile,
    alias or sponsor), with only an email identity. Anything else is somebody's own account."""
    from apps.courses import password_change_flag
    from apps.courses.models import PartnerAdmin
    if not isinstance(account, dict) or not account.get('id'):
        return False
    app = account.get('app_metadata') or {}
    if not (bool(app.get(password_change_flag.FLAG)) and _identity_providers(account) <= {'email'}
            and _untouched_since_issue(account, app)):
        return False
    # Another staff row already owns this login (review round 2, N2): resetting its password would
    # take over that colleague's sign-in, and storing the UID again breaks the unique constraint.
    return (not PartnerAdmin.objects.filter(supabase_user_id=account['id']).exists()
            and not login_used_elsewhere(account['id']))


def _parse_time(value):
    import datetime
    try:
        return datetime.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None


def login_untouched(account):
    """`_untouched_since_issue` for a whole admin-API user object — what the TD-335 re-invite asks
    too before it puts a fresh temporary password on a kept login."""
    return isinstance(account, dict) and _untouched_since_issue(
        account, account.get('app_metadata') or {})


def _untouched_since_issue(account, app):
    """Nobody has used this login since our temporary password was issued (review round 2, N1).

    ⚠ The flag alone is not enough: only `AdminSetPasswordView` clears it, and a person can choose
    their own password elsewhere (a reset link, the sponsor portal) after the expiry job rotated the
    temp password dead. So adopt only a login that was NEVER signed in, or whose last sign-in came
    no later than the issue of a temp password that has not been expired since. Anything we cannot
    read is treated as used."""
    from apps.courses import password_change_flag
    last = account.get('last_sign_in_at')
    if not last:
        return True
    if app.get(password_change_flag.EXPIRED):
        return False
    signed, issued = _parse_time(last), _parse_time(app.get(password_change_flag.ISSUED))
    return signed is not None and issued is not None and signed <= issued
