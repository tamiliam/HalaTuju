"""TD-335 — inviting an address again after its invitation was cancelled (staff lifecycle, 2026-10-09).

A cancel switches the never-used account OFF and keeps the row (a status, never a delete), so the
invite's "Admin with this email already exists" 409 used to refuse the address until somebody
pressed People → Restore, which brought back the OLD account and sent nothing. Now a re-invite
REUSES that row, exactly as a first invite would provision one: the role, name and organisation
the new invite chose; a FRESH temporary password onto the same login; a NEW invitation row.

⚠ **ONLY A SWITCHED-OFF ACCOUNT THAT NEVER SIGNED IN** (`is_active=False`, `first_seen_at` NULL),
and only one the caller could manage anyway (`_staff_target_manageable` — an org_admin cannot reach
another organisation's row or an organisation admin's). Anything else keeps the 409: an active
colleague is not re-invited, and somebody who has arrived is revoked and restored on People.

⚠ **A PASSWORD THE PERSON CHOSE IS NEVER OVERWRITTEN.** `first_seen_at` NULL also means "not
recorded" for staff predating 2026-08-03, so the login itself is asked: a fresh temporary password
is issued only while one is still owed or the login has never been used; a login somebody signed
in to and set their own password on means they arrived, so the 409 stands (review H1, 2026-10-09).
A row with any work on record is never brought back either (`may_reuse`).
"""
from django.db import transaction

from . import password_change_flag, supabase_admin
from .models import PartnerAdmin


def is_withdrawn(sub, supabase_user):
    """True when the CALLER'S OWN login has a switched-off staff account — revoked, or a cancelled
    invitation — so the sign-in page can say "your access has been withdrawn" (2026-10-09).

    ⚠ Only ever about the authenticated holder: by the JWT subject, or — for a Google invitee
    cancelled before their first sign-in, whose row has no UID yet — by their VERIFIED email,
    exactly the two ways `get_admin` itself links a caller to a row. A stranger learns nothing
    about any address but their own."""
    if sub and PartnerAdmin.objects.filter(supabase_user_id=sub, is_active=False).exists():
        return True
    su = supabase_user or {}
    email = (su.get('email') or '').strip().lower()
    return bool(email and su.get('email_verified') and PartnerAdmin.objects.filter(
        email=email, supabase_user_id__isnull=True, is_active=False).exists())


def may_reuse(caller, existing):
    """Whether a re-invite of ``existing``'s address may bring the row back instead of a 409.

    ⚠ NEVER A REVOKED WORKER (review H1). `first_seen_at` NULL is "not recorded" for everybody
    predating 2026-08-03, so on its own it let a re-invite resurrect a revoked colleague under a
    new role and name — skipping Restore, the role pairs and the Finance refusals. So the row must
    also carry NO footprint (assigned cases, slots, runs, verdicts…: a never-signed-in invitee can
    hold assigned cases, since a cancel unassigns nothing), and `bring_back` refuses a login that
    has been used with its own password, and a Google row that already has a login."""
    from .views_admin import _staff_target_manageable, scholarship_staff
    if not (existing is not None and not existing.is_active and existing.first_seen_at is None
            and not existing.is_super and _staff_target_manageable(caller, existing)):
        return False
    staff_footprint, _ = scholarship_staff()
    return not staff_footprint.has_footprint(existing)


def _login_for(row, name, temp_password):
    """``(user_id, already_registered, error)`` — the same triple `_create_supabase_user` returns,
    plus the error ``'not_reusable'`` (the caller's 409) for a login somebody has really used."""
    uid = row.supabase_user_id
    if uid:
        account = supabase_admin.read_auth_user(uid)
        if isinstance(account, dict):
            from .views_admin import scholarship_staff
            _, staff_lifecycle = scholarship_staff()
            owes = password_change_flag.rotation_state(account)[0] is not None
            fresh = owes and staff_lifecycle.login_untouched(account)
            if account.get('last_sign_in_at') and not fresh:
                # Signed in AND chose their own password — here, or elsewhere after the temp one
                # expired (round 2, N1): this person arrived, whatever `first_seen_at` says.
                # Restore is the way back, never a re-invite (H1).
                return None, False, 'not_reusable'
            if supabase_admin.issue_temp_password(uid, name, temp_password):
                return uid, False, None
            return None, False, 'create_failed'
        if account != supabase_admin.GONE:
            return None, False, 'create_failed'
        # The login was removed at Supabase: provision a new one, as a first invite does.
    return _new_login(row.email, name, temp_password)


def _new_login(email, name, temp_password):
    """Create the login, or ADOPT an orphaned one of ours at this address (review M2): a staff login
    whose row was deleted while the login survived would otherwise answer "already registered", and
    the invitee would be sent no password. `staff_lifecycle.adoptable_login` says when it is ours."""
    from .views_admin import scholarship_staff
    url, key = supabase_admin.supabase_config() or ('', '')
    uid, already, err = supabase_admin._create_supabase_user(url, key, email, name, temp_password)
    if err or not already:
        return uid, already, err
    found = supabase_admin._read_back_user_id(url, key, email)
    account = supabase_admin.read_auth_user(found) if found else None
    _, staff_lifecycle = scholarship_staff()
    if staff_lifecycle.adoptable_login(account):
        if supabase_admin.issue_temp_password(found, name, temp_password):
            return found, False, None
        return None, False, 'create_failed'
    return None, True, None


def provision(reuse, *, email, name, role, org, owning_org, temp_password=None):
    """The account a staff invite lands on. Returns ``(account, already_registered, error)``.

    ``reuse`` set → that switched-off row is brought back (`bring_back`). Otherwise a NEW row,
    with — unless this is a Google address (``temp_password`` None) — a Supabase login we create
    ourselves (`_create_supabase_user` says why). The UID is stored at creation; it is None on the
    already-registered path, whose existing account links by verified email on next sign-in.
    `is_super_admin` is kept in lockstep with the role (expand-contract: several call sites still
    gate on it directly). Moved here from `AdminInviteView.post` so that function stays inside its
    long-function allowance.
    """
    if reuse is not None:
        return bring_back(reuse, name=name, role=role, org=org, owning_org=owning_org,
                          temp_password=temp_password)
    uid, already = None, False
    if temp_password is not None:
        uid, already, err = _new_login(email, name, temp_password)
        if err:
            return None, False, err
    created = PartnerAdmin.objects.create(
        email=email, name=name, org=org, role=role, owning_organisation=owning_org,
        supabase_user_id=uid, is_super_admin=(role == 'super'))
    return created, already, None


def bring_back(existing, *, name, role, org, owning_org, temp_password=None):
    """Reactivate ``existing`` for a re-invite. Returns ``(account, already_registered, error)``.

    ``temp_password`` None = a Google address: no password is ever issued (owner 2026-07-14), so
    the login is not touched. The row is LOCKED and re-checked, so a Restore or a second re-invite
    landing in between wins and this answers ``'not_reusable'`` (the caller's 409). A Supabase
    failure writes nothing (``'create_failed'``, the caller's 502).
    """
    with transaction.atomic():
        row = (PartnerAdmin.objects.select_for_update()
               .filter(pk=existing.pk, is_active=False, first_seen_at__isnull=True).first())
        if row is None:
            return None, False, 'not_reusable'
        if temp_password is None and row.supabase_user_id:
            # A Google row gets its UID on its first Google sign-in — so one carrying a UID has
            # been in, and comes back through Restore, never a re-invite (review H1).
            return None, False, 'not_reusable'
        uid, already = row.supabase_user_id, temp_password is None
        if temp_password is not None:
            uid, already, err = _login_for(row, name, temp_password)
            if err:
                return None, False, err
        row.name, row.role, row.org, row.owning_organisation = name, role, org, owning_org
        row.is_super_admin = (role == 'super')
        row.is_active, row.paused_at, row.programme = True, None, None
        # ⚠ Written even when None: a login that was removed at Supabase and could not be
        # re-created (the address now belongs to another account) must not leave a dead UID on the
        # row, or `get_admin`'s email backfill — which links only a row with NO UID — never fires.
        row.supabase_user_id = uid
        row.save(update_fields=['name', 'role', 'org', 'owning_organisation', 'is_super_admin',
                                'is_active', 'paused_at', 'programme', 'supabase_user_id'])
    return row, already, None
