"""Mentors sign in — inviting one, and every door that opens or closes their sign-in (student
maintenance Sprint 7a, 2026-10-31; owner rulings in docs/decisions.md the same day).

THE SOURCE-PARTNER PATTERN (`source_invite.py`), with the mentor's own rules. The HTTP shapes are in
`views_admin/mentors.py`.

- WHO ACTS: a super, or an organisation admin of the mentor's OWN organisation (`may_invite`,
  `manageable`). An admin READS the Mentors page (`may_read`) and acts on nothing. Anybody else, and
  another organisation's mentor, is refused (the views answer 404 for the second, never 403).
- ONE ACCOUNT PATH, NOT A FORK: the account is provisioned by the staff invite's own three branches
  (`staff_reinvite.provision_for_invite`), a Resend rotates the password through the staff Resend's
  `staff_reinvite.reissue_credential`. Only the LETTER differs (`emails.send_mentor_invitation_email`)
  — and ⚠ it is the ONLY email a mentor is ever sent (owner ruling), with its resend.
- ONE EMAIL, ONE LOGIN: an address that already has ANY `PartnerAdmin` row is refused `already_staff`.
  There is no re-invite: a mentor is NEVER DELETED, so the way back is Reactivate.
- STAFF EDIT NAME AND EMAIL ONLY UNTIL THE FIRST SIGN-IN (`edit`): after it, 409 `managed_by_mentor` —
  the mentor keeps their own details up to date. Staff never write the mentor's profile.
- DEACTIVATE switches the login off (`is_active=False`, the source user's revoke), withdraws a waiting
  invitation and kills its emailed password, and stamps `deactivated_at/_by_email`. REACTIVATE
  reverses it; a mentor who never signed in is sent their invitation again (its resend).

STATUS IS DERIVED (`status_of`), never stored: `inactive` when deactivated; `invited` until the login's
first sign-in (`has_signed_in`); else `active`.

⚠ REVIEW FIXES (2026-10-31, adversarial review of 7a):
- ANY EXISTING SIGN-IN IS REFUSED (owner rule): an address the login side already knows (a student, a
  sponsor — `provision_*` answers `already_registered`) is `already_staff`, at invite and at an email
  move, never a mentor row that `get_admin` would later attach to that person's own login.
- "SIGNED IN" IS NOT ONLY `first_seen_at`. `get_admin` links a row with no UID to a caller's VERIFIED
  email on ANY admin request — a refused one too — without stamping `first_seen_at` (only
  `admin/role/` does). A mentor login we never issued a password for (the newest invitation's
  `credential_issued` is false: a Google address) that carries a UID was linked that way, so it has
  signed in: Resend, Revoke, the email move and Reactivate's letter all treat it so, and a password is
  only ever reissued when the newest invitation issued one.
"""
import logging
from collections import namedtuple

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.courses import staff_reinvite
from apps.courses.models import PartnerAdmin

from . import invitations
from .models import Invitation, Mentor

# ⚠ THE PACKAGE'S name, never `__name__` — an audit line must stay on the scrape metric (H11).
logger = logging.getLogger('apps.scholarship.views_admin')

MENTOR_ROLE = PartnerAdmin.MENTOR_ROLE
AUDIENCE = invitations.MENTOR_AUDIENCE

ACTIVE, INVITED, INACTIVE = 'active', 'invited', 'inactive'


def google_address_refusal(email):
    """`already_staff` / `create_failed` / None for a GOOGLE address (lead check of the review fix,
    2026-10-31). A Google address is never provisioned, so `already_registered` is never seen for it:
    Supabase Auth is ASKED whether it already holds a login there (a student's who signs in with
    Google), and one that does is refused. A lookup that fails refuses too (fail closed, nothing kept).
    Any other address is checked by provisioning itself (`already_registered`)."""
    from apps.courses import supabase_admin
    from apps.courses.views_admin import is_google_email
    if not is_google_email(email):
        return None
    found = supabase_admin.auth_user_exists(email)
    if found is True:
        return 'already_staff'
    if found is not False:
        return 'create_failed'
    return None
STATUSES = (ACTIVE, INVITED, INACTIVE)

#: What `invite` did. ``error`` is None, `already_staff` or `create_failed`.
Invited = namedtuple('Invited', 'error mentor account invitation google already_registered emailed')


# ── who may act, and on what ─────────────────────────────────────────────────────
def may_invite(caller):
    """A super, or an organisation admin. Never an admin, finance, reviewer, QC, source or mentor."""
    return caller is not None and (caller.is_super or caller.role == 'org_admin')


def may_read(caller):
    """Who may open the Mentors page: a super, an organisation admin, an admin (read-only)."""
    return caller is not None and (caller.is_super or caller.role in ('org_admin', 'admin'))


def manageable(caller, mentor):
    """Whether ``caller`` may invite again, resend, revoke, deactivate, reactivate or edit ``mentor``.
    A super: any. An organisation admin: only its OWN organisation's. Else no."""
    if caller is None or mentor is None:
        return False
    if caller.is_super:
        return True
    return (caller.role == 'org_admin' and caller.owning_organisation_id is not None
            and mentor.organisation_id == caller.owning_organisation_id)


def login_of(mentor):
    """The mentor's sign-in row (exactly one: the invite writes it with the mentor)."""
    return PartnerAdmin.objects.filter(mentor=mentor).order_by('id').first()


def _newest_invitation(login):
    return (Invitation.objects.filter(audience=AUDIENCE, partner_admin=login)
            .order_by('-created_at', '-id').first())


def has_signed_in(login, credential_issued=None):
    """True once this mentor login has been used: `first_seen_at` (the console stamped it), OR a UID on
    a login we never issued a password for — `get_admin` put it there on a verified-email sign-in (see
    the module docstring). ``credential_issued``: the newest mentor invitation's, when the caller has
    it (the list does, for every row in one query); else it is read. No invitation at all and a UID:
    signed in (the safe reading — nothing will then reset that login)."""
    if login is None:
        return False
    if login.first_seen_at is not None:
        return True
    if not login.supabase_user_id:
        return False
    if credential_issued is None:
        inv = _newest_invitation(login)
        credential_issued = bool(inv and inv.credential_issued)
    return not credential_issued


def status_of(mentor, login, credential_issued=None):
    """`inactive` / `invited` / `active` — see the module docstring."""
    if mentor.deactivated_at is not None:
        return INACTIVE
    if not has_signed_in(login, credential_issued):
        return INVITED
    return ACTIVE


# ── inviting ─────────────────────────────────────────────────────────────────────
def invite(caller, *, organisation, email, name):
    """Make ``organisation``'s new mentor, their login and their invitation, then send the letter.

    The caller has already checked who may invite and resolved the organisation (inside its fence).
    Nothing is left behind by a refusal or a failure: the mentor, the login row and the invitation
    are written in ONE transaction, and the letter goes only after it commits."""
    if PartnerAdmin.objects.filter(email__iexact=email).exists():
        return Invited('already_staff', None, None, None, False, False, False)
    taken = google_address_refusal(email)
    if taken:
        return Invited(taken, None, None, None, False, False, False)
    try:
        with transaction.atomic():
            mentor = Mentor.objects.create(organisation=organisation,
                                           created_by_email=caller.email or '')
            made = staff_reinvite.provision_for_invite(
                None, email=email, name=name, role=MENTOR_ROLE, org=None,
                owning_org=organisation, mentor=mentor)
            if made.error:
                transaction.set_rollback(True)
                return Invited('create_failed', None, None, None, False, False, False)
            if made.already_registered:
                # Review fix (owner rule): the address already has a sign-in — a student's, a
                # sponsor's. Refused; nothing is kept (no login was created for it).
                transaction.set_rollback(True)
                return Invited('already_staff', None, None, None, False, False, False)
            inv = invitations.create_or_refresh(
                audience=AUDIENCE, email=email, name=name, role=MENTOR_ROLE,
                organisation=organisation, invited_by=caller, partner_admin=made.account,
                credential_issued=bool(made.temp_password), mentor=mentor)
    except IntegrityError:
        # The address was taken between the check and the write (`PartnerAdmin.email` is unique).
        return Invited('already_staff', None, None, None, False, False, False)
    emailed = send(inv, made.account, organisation, made.temp_password, made.google, actor=caller)
    return Invited(None, mentor, made.account, inv, made.google, made.already_registered, emailed)


def send(inv, account, organisation, temp_password, google, *, actor=None):
    """Send the mentor letter for ``inv`` and record whether it went. Returns ``emailed``.
    ``actor`` (the staff member who pressed Invite / Resend / changed the address) gets the
    `invitation_sent` row on their own activity list (common profile S3)."""
    from .emails import send_mentor_invitation_email
    ok, error = send_mentor_invitation_email(
        account.email, name=account.name, org_name=getattr(organisation, 'name', ''),
        temp_password=temp_password, google=google)
    invitations.record_send(inv, ok, error, actor=actor)
    return ok


def _send_again(caller, mentor, login):
    """A fresh credential (where we issued one) on a fresh invitation, and the letter: ``(emailed,
    error)``. Shared by Resend and by Reactivate of a mentor who never signed in."""
    from apps.courses.views_admin import is_google_email
    # Review fix: a password is reissued ONLY onto a login we issued one for (the newest invitation
    # says so) — never onto a login somebody brought with them.
    newest = _newest_invitation(login)
    temp_password, err = (staff_reinvite.reissue_credential(login)
                          if newest is not None and newest.credential_issued else (None, None))
    if err:
        return False, err
    inv = invitations.create_or_refresh(
        audience=AUDIENCE, email=login.email, name=login.name, role=MENTOR_ROLE,
        organisation=mentor.organisation, invited_by=caller, partner_admin=login,
        credential_issued=bool(temp_password), mentor=mentor)
    google = temp_password is None and is_google_email(login.email)
    return send(inv, login, mentor.organisation, temp_password, google, actor=caller), None


def resend_invite(caller, mentor, login):
    """Re-send an INVITED mentor's invitation: ``(emailed, error)``. Refused once they have signed in
    (`already_joined` — their password is their own) or while deactivated (`not_active`)."""
    state = status_of(mentor, login)
    if state == INACTIVE or login is None or not login.is_active:
        return False, 'not_active'
    if state == ACTIVE:
        return False, 'already_joined'
    return _send_again(caller, mentor, login)


# ── switching off and on ─────────────────────────────────────────────────────────
def _switch_off(caller, mentor, login):
    """Login off, waiting invitation withdrawn, mentor stamped — in ONE transaction, each write
    conditional so a concurrent change wins. Then the emailed password is killed. ``(done, error)``."""
    now = timezone.now()
    with transaction.atomic():
        if not Mentor.objects.filter(pk=mentor.pk, deactivated_at__isnull=True).update(
                deactivated_at=now, deactivated_by_email=caller.email or ''):
            return False, 'not_active'
        waiting = []
        if login is not None:
            PartnerAdmin.objects.filter(pk=login.pk).update(is_active=False)
            waiting = list(invitations.open_only(
                Invitation.objects.filter(audience=AUDIENCE, partner_admin=login)))
            Invitation.objects.filter(pk__in=[i.pk for i in waiting]).update(
                revoked_at=now, updated_at=now)
    mentor.deactivated_at, mentor.deactivated_by_email = now, caller.email or ''
    if login is not None:
        login.is_active = False
        from . import staff_lifecycle
        for inv in waiting:
            staff_lifecycle.kill_for_cancel(login, inv)
    return True, None


def revoke_invite(caller, mentor, login):
    """Withdraw an INVITED mentor's invitation: the login off and its emailed password killed, the
    mentor stamped inactive. ``(done, error)``: `already_joined` once they have signed in (use
    Deactivate), `not_active` when already off."""
    state = status_of(mentor, login)
    if state == INACTIVE:
        return False, 'not_active'
    if state == ACTIVE:
        return False, 'already_joined'
    return _switch_off(caller, mentor, login)


def deactivate(caller, mentor, login):
    """Switch a mentor OFF — never a delete. ``(done, error)``; `not_active` when already off."""
    if status_of(mentor, login) == INACTIVE:
        return False, 'not_active'
    return _switch_off(caller, mentor, login)


def reactivate(caller, mentor, login):
    """Switch a deactivated mentor back ON: ``(done, emailed, error)``. Their login is switched on and
    the stamp cleared; a mentor who NEVER signed in is sent their invitation again (a fresh password
    where we issued one — the old one was killed), the only other email a mentor may get. A mentor
    who has signed in is sent nothing: their login is theirs. `active` when not deactivated."""
    if status_of(mentor, login) != INACTIVE:
        return False, False, 'active'
    if login is None:
        return False, False, 'no_login'
    with transaction.atomic():
        if not Mentor.objects.filter(pk=mentor.pk, deactivated_at__isnull=False).update(
                deactivated_at=None, deactivated_by_email=''):
            return False, False, 'active'
        PartnerAdmin.objects.filter(pk=login.pk).update(is_active=True, paused_at=None)
    mentor.deactivated_at, mentor.deactivated_by_email = None, ''
    login.is_active = True
    if has_signed_in(login):
        return True, False, None
    emailed, err = _send_again(caller, mentor, login)
    return True, emailed, err


# ── staff editing name and email, until the first sign-in ────────────────────────
def edit(caller, mentor, login, *, name=None, email=None):
    """Correct a mentor's NAME or EMAIL before they have signed in: ``(changed, emailed, error)``.

    `managed_by_mentor` once they have signed in (their details are theirs from then on);
    `not_active` while deactivated. A new EMAIL is a new sign-in: the old address's waiting invitation
    is withdrawn and its login retired the way a staff delete retires one (`staff_lifecycle`: removed
    only when ours and unused, else its temporary password killed, else left alone and unlinked), a
    login is provisioned for the new address by the invite's own branches, and the invitation is sent
    there. `already_staff` when the new address already has a sign-in; `create_failed` / `retire_failed`
    when Supabase could not be asked (nothing changes)."""
    if login is None or has_signed_in(login):
        return False, False, 'managed_by_mentor'
    if status_of(mentor, login) == INACTIVE:
        return False, False, 'not_active'
    name = name if name is not None else login.name
    if email is None or email == (login.email or '').lower():
        if name == login.name:
            return False, False, None
        with transaction.atomic():
            PartnerAdmin.objects.filter(pk=login.pk).update(name=name)
            invitations.open_only(Invitation.objects.filter(
                audience=AUDIENCE, partner_admin=login)).update(name=name)
        login.name = name
        return True, False, None
    return _move_address(caller, mentor, login, name, email)


def _move_address(caller, mentor, login, name, email):
    """`edit`'s new-address branch. See `edit`."""
    from apps.courses import supabase_admin
    from . import staff_lifecycle
    if PartnerAdmin.objects.filter(email__iexact=email).exclude(pk=login.pk).exists():
        return False, False, 'already_staff'
    if supabase_admin.supabase_config() is None:
        return False, False, 'not_configured'
    taken = google_address_refusal(email)
    if taken:
        return False, False, taken
    old_uid = login.supabase_user_id
    plan, account = staff_lifecycle.plan_login_retirement(login)   # BEFORE the address changes
    if plan == supabase_admin.FAILED:
        return False, False, 'retire_failed'
    now = timezone.now()
    new_login = staff_reinvite.provision_login(email, name)
    if new_login.error:
        return False, False, 'create_failed'
    if new_login.already_registered:
        return False, False, 'already_staff'   # review fix: an address with a sign-in is refused
    try:
        with transaction.atomic():
            # Review fix: COMPARE-AND-SET. The row moves only if, in the database, nobody has signed
            # in since it was read: no `first_seen_at`, and the UID it was read with (a verified-email
            # sign-in would have linked one) — else 409 `managed_by_mentor`, nothing written.
            moved = PartnerAdmin.objects.filter(
                Q(supabase_user_id=old_uid) if old_uid else Q(supabase_user_id__isnull=True),
                pk=login.pk, first_seen_at__isnull=True, is_active=True,
            ).update(email=email, name=name, supabase_user_id=new_login.uid)
            if moved != 1:
                raise _MoveLost()
            invitations.open_only(Invitation.objects.filter(
                audience=AUDIENCE, partner_admin=login)).update(revoked_at=now, updated_at=now)
            login.email, login.name, login.supabase_user_id = email, name, new_login.uid
            inv = invitations.create_or_refresh(
                audience=AUDIENCE, email=email, name=name, role=MENTOR_ROLE,
                organisation=mentor.organisation, invited_by=caller, partner_admin=login,
                credential_issued=bool(new_login.temp_password), mentor=mentor)
    except (IntegrityError, _MoveLost) as lost:
        login.refresh_from_db()
        _drop_new_login(new_login.uid)
        return False, False, ('managed_by_mentor' if isinstance(lost, _MoveLost) else 'already_staff')
    if old_uid and old_uid != new_login.uid and plan in ('delete', 'kill'):
        staff_lifecycle.retire_login(old_uid, plan, account)
    emailed = send(inv, login, mentor.organisation, new_login.temp_password, new_login.google,
                   actor=caller)
    return True, emailed, None


class _MoveLost(Exception):
    """The compare-and-set in `_move_address` found the row changed (signed in, linked, switched off)."""


def _drop_new_login(uid):
    """Best effort: remove the login `_move_address` just created when its database step failed, so no
    unused login with a live temporary password is left behind. Logged loudly when it cannot."""
    if not uid:
        return None
    from apps.courses import supabase_admin
    done = supabase_admin.delete_auth_user(uid)
    if done == supabase_admin.FAILED:
        logger.error('MENTOR_LOGIN_ORPHANED uid=%s: an email move failed after its new login was '
                     'made, and the login could not be removed - remove it by hand in Supabase Auth',
                     uid)
    return done
