"""TD-322 — where "this account still owes a password change" is kept, and who may believe it.

`AdminSetPasswordView` sets a password with the SERVICE ROLE and no current password, so the flag
that opens it is a key to the account. It used to live in Supabase `user_metadata`, which the
account's own browser session may rewrite at will: `supabase.auth.updateUser({ data: {
must_change_password: true } })` needs no password, so whoever held a stolen ORDINARY admin
session could switch it on and then choose a new password through `admin/set-password/`.

The flag now lives in `app_metadata`, which only the service role can write. Every server writer
— the invite (`supabase_admin._create_supabase_user`), Resend (`AdminResendView`), the daily
`expire_temp_passwords` rotation and the set-password clear — goes through `issued_fields` /
`cleared_fields` below, and every reader goes through `pending_state` / `owes_password_change`.

⚠ ONE-RELEASE FALLBACK, AND THE ONLY PLACE `user_metadata` IS STILL BELIEVED. Partners invited
before this release carry the flag in `user_metadata` only, and refusing them would strand every
invite still in its first week. So when `app_metadata` has NO `must_change_password` key at all
(an account no server writer has touched since this release), a `user_metadata` flag is honoured
ONLY while the server's OWN record of that invitation says it is live: the newest staff
`Invitation` for this admin issued a password (`credential_issued`), is not revoked, and its
`expires_at` — the server-side copy of the temp-password TTL clock, moved by invite and Resend
together with `temp_password_issued_at` — has not passed. The `user_metadata` timestamp is NOT
consulted for that: the attacker writes it in the same call as the flag.

What the fallback still allows, said plainly: an account invited before this release, within its
TTL, whose password was ALREADY set under the old code (which cleared only `user_metadata`). Its
exposure ends when that invitation expires, at most `temp_password_ttl_days` (max 30, org_config)
after the last pre-release invite or Resend.

REMOVE BOTH FALLBACKS (the `user_metadata` branches of `pending_state` and `rotation_state`, and
their tests) once `LEGACY_FALLBACK_UNTIL` has passed — by then no invitation written before this
release can still be live, so the set-password branch can only ever answer "no", and the cron's
branch already answers "no" by date (review F2).
"""
import datetime

from django.utils import timezone

FLAG = 'must_change_password'
ISSUED = 'temp_password_issued_at'
EXPIRED = 'temp_password_expired'

#: This release (2026-10-02) + the longest TTL an organisation may configure (30 days).
LEGACY_FALLBACK_UNTIL = datetime.date(2026, 11, 1)


def issued_fields(now=None):
    """The `app_metadata` a server writer sends when it issues a temporary password."""
    return {FLAG: True, ISSUED: (now or timezone.now()).isoformat(), EXPIRED: None}


def cleared_fields():
    """The `app_metadata` sent once the account's own password is set (null clears on merge)."""
    return {FLAG: False, ISSUED: None, EXPIRED: None}


def scrubbed_user_metadata(user_meta):
    """`user_metadata` with the legacy, browser-writable copies nulled (Supabase merges, so a key
    is cleared by sending null, never by omitting it). Every other key — `name` — is kept."""
    return {**(user_meta or {}), FLAG: None, ISSUED: None, EXPIRED: None}


def _invitation_live(invitation, now):
    return (invitation is not None and bool(getattr(invitation, 'credential_issued', False))
            and getattr(invitation, 'revoked_at', None) is None
            and getattr(invitation, 'expires_at', None) is not None
            and invitation.expires_at > now)


def pending_state(account, invitation_lookup=None, now=None):
    """`(source, fields)` for an admin-API user object, or `(None, {})` when nothing is owed.

    ``source`` is the metadata key the flag was read from — `'app_metadata'`, or
    `'user_metadata'` through the one-release fallback — so a writer can answer in the same place.
    ``invitation_lookup`` is a zero-argument callable returning the admin's newest staff
    `Invitation` (or None); it is called only when the fallback is actually in question.
    """
    account = account or {}
    app = account.get('app_metadata') or {}
    if FLAG in app:
        return ('app_metadata', app) if app.get(FLAG) else (None, {})
    user = account.get('user_metadata') or {}
    if not user.get(FLAG) or invitation_lookup is None:
        return None, {}
    now = now or timezone.now()
    if _invitation_live(invitation_lookup(), now):
        return 'user_metadata', user
    return None, {}


def rotation_state(account):
    """`(source, fields)` for the daily expiry cron, which ROTATES a stale temp password dead.

    WITHOUT the invitation check (the cron rotates exactly when the invitation has expired, so the
    check could never pass), so a pre-release account whose flag is still in `user_metadata` keeps
    being expired as before. `app_metadata` wins whenever it carries the key.

    ⚠ The `user_metadata` branch is ALSO forgeable (review F2): a stolen session can write the flag
    plus an old clock and have the cron rotate the owner's password — a lockout, not a takeover.
    So it is bounded by the same date as the set-password fallback: after `LEGACY_FALLBACK_UNTIL`
    it answers "nothing owed", and it is removed with that fallback.
    """
    account = account or {}
    app = account.get('app_metadata') or {}
    if FLAG in app:
        return ('app_metadata', app) if app.get(FLAG) else (None, {})
    if _today() > LEGACY_FALLBACK_UNTIL:
        return None, {}
    user = account.get('user_metadata') or {}
    return ('user_metadata', user) if user.get(FLAG) else (None, {})


def _today():
    return timezone.localdate()


def owes_password_change(account, invitation_lookup=None, now=None):
    """True when the server's record (or, for one release, a live pre-release invite) says this
    account still has to choose its own password. See the module docstring."""
    return pending_state(account, invitation_lookup, now)[0] is not None
