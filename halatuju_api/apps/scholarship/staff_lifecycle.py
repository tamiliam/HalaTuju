"""A staff member's lifecycle after the invitation: changing their role, and what a CANCEL or a
DELETE does to their sign-in (staff lifecycle sprint, 2026-10-09).

⚠ **A ROLE CHANGES ONLY WITHIN ITS PAIR** (owner, 2026-10-09): Admin ↔ Finance and Reviewer ↔ QC.
Never to or from `org_admin`, `super` or `partner` — those are appointments (a super installs an
organisation admin; a partner is the course selector's referral world), and a role switch that
could reach one would be a privilege path that skips the invite. Same-role and cross-pair requests
are refused with the same code, because both are "not a switch this screen makes".

⚠ **A SWITCH MAY NOT STRAND WORK.** `finance` has no B40 scope at all (`_b40_scope` → 'none') and is
not a review target (`services.is_review_target`), so an admin with cases assigned to them would leave
those cases with an owner who cannot open them. Refused while they hold any in-play case
(`OPEN_CASE_STATUSES` — a case stops being open once the student is awarded, R5 M2c) and while a
payment run they made or signed is still waiting (as finance they would be its APPROVER and could
not sign it again: the three-distinct-signers rule). Reviewer ↔ QC strands nothing — both are review roles and keep their
assigned cases; the QC self-check guard still stops anybody QC-ing a verdict they recorded.

⚠ **THE FINANCE PERSON CHANGES TWO CHAINS, LIVE** (#39 Sprint 2). Finance APPROVES payment runs
(the preset holds `payments_approve`), so appointing the first one makes them the approver and the
organisation admin stops approving (`payments.approver_fallback` goes off); and since TD-475 (A1.10a,
2026-11-07) the wallet credit check turns on the same KEY (`payments.credit_check_required`: an active
holder of `payments_approve`), so the same appointment arms the credit check. A switch KEEPS the keys
(T2, below), so a switch no longer moves either chain; adding or removing the key on Team does, and
`staff_tables_admin.plan_table_change` says so (`finance_check_off`, code kept for the screen).

⚠ **A SWITCH TO A ROLE THAT MAY NOT MENTOR ENDS MENTORING** (S7d, 2026-11-01): a staff member who also
mentors and is switched Admin → Finance stops mentoring in the same transaction (`staff_mentor.leave`:
the mentor stamped deactivated, every open assignment ended, the link kept); the dry run says so first
(`stops_mentoring`). Reviewer ↔ QC keeps it. Switching back never brings it back (Mentor again does).

⚠ **A SWITCH KEEPS THE PERSON'S KEYS EXACTLY** (Team tables T2, lead ruling 2026-11-03; it RESET a custom set
to the new preset in #39 Sprint 4): `change_role` writes the resolved keys back (NULL only when they equal the
new role's preset), so no switch gives or takes a key. And no switch goes INTO `finance` or `qc` any more
(`RETIRED_LABELS`, 409 `label_retired`): those are permissions on Team now.

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

#: Team tables T2 (lead ruling, review 2026-11-03): "Finance" and "QC" are no longer labels anybody is
#: switched INTO (owner rulings 4, 8). A switch OUT (finance -> admin, qc -> reviewer) stays, and keeps the
#: person's resolved keys EXACTLY — no gain, no loss.
RETIRED_LABELS = ('finance', 'qc')

FINANCE_CHECK_ON = 'finance_check_on'
FINANCE_CHECK_OFF = 'finance_check_off'


class RoleChangeRefused(Exception):
    """A refusal the view turns into a response: ``code``, ``status``, a sentence, extra fields."""

    def __init__(self, code, status, message, **extra):
        super().__init__(code)
        self.code, self.status, self.message, self.extra = code, status, message, extra


def team_cards(admins):
    """`{admin_id: {photo_url, phone}}` for the People list — `staff_photo.team_cards` (one query, one
    batch signing call). Here so `apps.courses.views_staff` reaches it through its ONE scholarship
    door (`views_admin.scholarship_staff()`), adding no cross-app import (common profile S2)."""
    from . import staff_photo
    return staff_photo.team_cards(admins)


def team_table_fields(caller, admins):
    """Team tables T2: `staff_tables_admin.row_fields` — here so `apps.courses.views_staff` reaches it
    through its ONE scholarship door (`views_admin.scholarship_staff()`), as `team_cards` does. M1b (TD-606):
    with each row's unfinished payment runs (`staff_work.runs_counts`, one query for the page), served as
    `runs_in_progress` and read by the Admins Remove (`run_in_progress`)."""
    from . import staff_tables_admin, staff_work
    return staff_tables_admin.row_fields(caller, admins, runs=staff_work.runs_counts(admins))


def staff_list_rows(caller, admins):
    """Sprint M1a: the Staff list's rows (`staff_list.list_rows`) — here for the ONE courses door, as `team_cards`."""
    from . import staff_list
    return staff_list.list_rows(caller, admins)


def has_signed_in(admin):
    """Has this person EVER opened the console (`first_seen_at`, stamped by `get_admin` on their first
    request)? THE ONE HOME of "signed in" (sprint M2d A1, owner 2026-11-13). Two rules read it:
      - a payment run's step holder (`payments_chain`, review fix 4, 2026-10-19): somebody who has never
        signed in cannot sign a run, so they must not take the step away from somebody who can;
      - a NEW case (`services.assignment`): a reviewer who has never signed in is not given one — the
        picker leaves them out and `assign_reviewer` refuses `not_signed_in`. A case they already hold
        is untouched.
    The moment they sign in, both rules let them in."""
    return getattr(admin, 'first_seen_at', None) is not None


#: A case still OPEN for the officer who holds it (owner R5, sprint M2c): every status before the award
#: (`models/applications.py` status order). An awarded student stays `assigned_to` their reviewer, who still
#: sees them, but the case no longer blocks a Remove, a role switch or a Delete. NOT `IN_PLAY_STATUSES`
#: (`apply_gate`), which means "an application still in play" for the gate, closure and reminders.
OPEN_CASE_STATUSES = ('submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed',
                      'recommended')


def is_open_case(status, reopened_at):
    """One case row against the rule `open_cases` counts in SQL (a reopened decision is open at any status)."""
    return status in OPEN_CASE_STATUSES or reopened_at is not None


def open_cases(admin):
    """How many cases ``admin`` still HOLDS: pre-award applications assigned to them, and — #39 S4
    review fix 5 — any assigned case whose decision has been REOPENED (`decision_reopened_at`), which
    can sit at `rejected` while it waits for the assigned officer to decide again. Both the
    permission editor's stranding rule and Admin → Finance read this one count."""
    from .models import ScholarshipApplication
    return ScholarshipApplication.objects.filter(assigned_to=admin).filter(
        Q(status__in=OPEN_CASE_STATUSES) | Q(decision_reopened_at__isnull=False)).count()


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


def other_active_checker(target):
    """Another ACTIVE holder of the credit CHECKER key (`credit_steps.CHECKER_KEY`) in the target's
    organisation? TD-475 (A1.10a): the credit check turns on the KEY now, not the finance ROLE."""
    from apps.courses import staff_permissions
    from .credit_steps import CHECKER_KEY
    if target.owning_organisation_id is None:
        return False
    return any(a.pk != target.pk for a in staff_permissions.holders(target.owning_organisation, CHECKER_KEY))


def plan_role_change(target, new_role):
    """What switching ``target`` to ``new_role`` would do, or `RoleChangeRefused`.

    Returns ``{'from', 'to', 'consequence', 'permissions_reset'}`` where consequence is
    `FINANCE_CHECK_ON`, `FINANCE_CHECK_OFF` or None, and ``permissions_reset`` says a saved CUSTOM set
    of permissions (#39 Sprint 4) goes back to the new role's preset. Pure apart from reads, so a dry
    run and the real change share it.
    """
    from apps.courses import staff_permissions
    old = target.role
    if target.is_super or ROLE_PAIRS.get(old) != new_role:
        raise RoleChangeRefused(
            'role_not_switchable', 400,
            'That role change is not available. Admin and Finance switch with each other, and '
            'Reviewer and QC switch with each other.')
    if new_role in RETIRED_LABELS:
        raise RoleChangeRefused(
            'label_retired', 409,
            '"Finance" and "QC" are no longer roles. Give the person "Approve payment runs" or "Quality '
            'check" on Team instead.')
    if not target.is_active:
        raise RoleChangeRefused(
            'not_active', 400,
            f"{target.name}'s access is revoked. Restore them before changing their role.")
    # ⚠ Unreachable since T2 (`RETIRED_LABELS` refuses a switch INTO finance above); kept, with its
    # consequences below, should the owner ever bring the label back.
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
                'admin approves runs and cannot approve their own, so finish it first.')
    # TD-475 (A1.10a): the wallet credit check turns on the KEY `payments_approve`, which a switch KEEPS
    # (T2), so no switch arms or disarms it any more: the consequence is always None. Kept in the plan
    # (and `FINANCE_CHECK_ON` / `FINANCE_CHECK_OFF` kept as codes) because the screen reads it; a key
    # change says it through `staff_tables_admin.plan_table_change` and the editor's consequences.
    consequence = None
    # #39 S4 review fix 4: what the switch does to the PERMISSIONS — the editor's own consequences,
    # from the set they hold now to the new role's preset (a reset included), so the approval
    # fallback and the check step are said from the same rule.
    from . import staff_permissions_admin
    from apps.courses.models import PartnerAdmin
    return {'from': old, 'to': new_role, 'consequence': consequence,
            # S7d: the switch ends this person's mentoring (a role that may not mentor).
            'stops_mentoring': bool(target.mentors_now and new_role not in PartnerAdmin.STAFF_MENTOR_ROLES),
            # T2: the keys are KEPT across a switch out (materialised; NULL only when equal to the new
            # preset), so nothing is reset and the key consequences are none.
            'permissions_reset': False,
            'keeps': list(staff_permissions.resolve(target)),
            'consequences': staff_permissions_admin.consequences(
                target, staff_permissions.resolve(target), staff_permissions.resolve(target))}


def change_role(target_id, new_role, *, dry_run=False, by=None):
    """Plan, and unless ``dry_run`` apply, the switch. Returns ``(target, plan)``.

    The row is LOCKED for the plan and the write, so a revoke or another switch landing in between
    cannot be overwritten; the UPDATE also carries the role it expects, belt and braces. Writes
    `role` (the only super marker since TD-064; never 'super' here) and, moving to finance, clears
    `paused_at` (pause is meaningless for a role that is never assigned work, and a
    "Paused" pill on a finance admin would be a control that lies — `set_paused`'s own rule). An
    OPEN invitation for this person carries the new role too: the Invitations page shows the role
    from it, and a Resend reads the account's.

    ⚠ `permissions` KEEPS THE RESOLVED KEYS (Team tables T2; #39 S4 reset them to the new preset). Only the
    two switches OUT of a retired label remain (finance -> admin, qc -> reviewer), and the keys are
    materialised so the person neither gains nor loses one; `permissions_reset` is always False now.
    """
    from apps.courses import staff_permissions
    from apps.courses.models import PartnerAdmin
    from . import invitations, staff_permissions_admin
    from .models import Invitation
    with transaction.atomic():
        target = PartnerAdmin.objects.select_for_update().filter(pk=target_id, archived_at=None).first()
        if target is None:
            raise RoleChangeRefused('not_found', 404, 'Admin not found')
        plan = plan_role_change(target, new_role)
        if dry_run:
            return target, plan
        before = staff_permissions.resolve(target)
        # T2 (review 2026-11-03): the person's resolved keys are KEPT exactly — stored NULL only when they
        # equal the new role's preset. A switch never gives or takes a key.
        # M2b: the stored v2 keys are kept too, and a switch TO `admin` stores `ADMIN_PRESET_V2` — the
        # admin work pages the `admin` label opened by itself before M2b, so the switch does what it did.
        v2 = staff_permissions_admin._v2()
        v2_before = v2.stored_v2(target)
        v2_after = v2.v2_order({*v2_before, *(v2.ADMIN_PRESET_V2 if new_role == 'admin' else ())})
        kept = (None if tuple(before) == staff_permissions.preset_for(new_role) and not v2_after
                else [*before, *v2_after])
        fields = {'role': new_role, 'permissions': kept}
        # ⚠ A pause is KEPT between reviewer and QC on purpose: both are review roles that can be
        # assigned work, so "no new work for now" still means something; only Finance clears it.
        if new_role == 'finance':
            fields['paused_at'] = None
        PartnerAdmin.objects.filter(pk=target.pk, role=plan['from'], is_active=True).update(**fields)
        invitations.open_only(Invitation.objects.filter(
            audience='staff', partner_admin=target)).update(role=new_role)
        for k, v in fields.items():
            setattr(target, k, v)
        if target.is_staff_mentor and new_role not in PartnerAdmin.STAFF_MENTOR_ROLES:
            from . import staff_mentor
            staff_mentor.leave(target, by=getattr(by, 'email', '') or '')
        if plan['permissions_reset'] or v2_after != v2_before:
            staff_permissions_admin.record(target, [*before, *v2_before],
                                           [*staff_permissions.resolve(target), *v2_after],
                                           by=by, kind='role_change')
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


def credential_was_issued(admin):
    """True when the NEWEST invitation for this login row issued a temporary password — then its UID
    is a login WE made. False (no invitation, or one that issued none) means the UID came with the
    person: a Google sign-in or a login they already had, linked by `get_admin` on a verified email.
    TD-440 (2026-10-31): a Resend rotates a password only on the first."""
    from .models import Invitation
    inv = (Invitation.objects.filter(partner_admin=admin).order_by('-created_at', '-id')
           .only('credential_issued').first())
    return bool(inv and inv.credential_issued)


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
