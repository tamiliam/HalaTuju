"""Inviting a SOURCE's person to sign in, and taking it away — source sign-in S2 (2026-10-30).

Roadmap: `docs/plans/2026-10-30-source-sign-in-roadmap.md` (Doors list). S1 made the role and the
fence (`PartnerAdmin.source`, deny-by-default `get_admin`, `source_access`); this module is every
door S2 opens or closes. The HTTP shapes are in `views_admin/source_users.py`.

⚠ ONE ACCOUNT PATH, NOT A FORK. A source user's account is provisioned by the staff invite's own
three branches (`staff_reinvite.provision_for_invite`: Google → no password; anything else → a login
we create with a temporary password; an address that already has a login keeps it), and a Resend
rotates the password through the staff Resend's own `staff_reinvite.reissue_credential`. Only the
LETTER differs (`emails.send_source_invitation_email`) and who may act (`manageable`).

⚠ ONE EMAIL, ONE ROW (roadmap C7). An address that already has ANY `PartnerAdmin` row is refused
(`already_staff`) — a referral partner, a colleague, a source user of another source, a revoked one —
with ONE exception: a switched-off source user of the SAME source, which is brought back. So a
source can never be turned into staff, nor a staff row into a source, by inviting.

⚠ SEVERAL PEOPLE PER SOURCE (decided 2026-10-30, like several reviewers per organisation). A source
is an organisation with a team, and the roadmap's lock is "any JOINED user", not "the user".
"""
import logging
from collections import namedtuple

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.courses import staff_reinvite
from apps.courses.models import PartnerAdmin

from . import invitations

logger = logging.getLogger(__name__)

SOURCE_ROLE = PartnerAdmin.SOURCE_ROLE
AUDIENCE = 'source_partner'

#: What `invite` did. ``error`` is None or one of `already_staff` / `code_taken` /
#: `create_failed`; the rest describe the account, the invitation and the letter.
Invited = namedtuple('Invited', 'error account invitation source google already_registered '
                                'reactivated emailed')


def _refused(error):
    return Invited(error, None, None, None, False, False, False, False)


# ── who may act, and on what ─────────────────────────────────────────────────────
def may_invite(caller):
    """A super, or an organisation admin. Never an admin, finance, reviewer, QC or source user."""
    return caller is not None and (caller.is_super or caller.role == 'org_admin')


def manageable(caller, target):
    """Whether ``caller`` may resend, cancel or revoke the source user ``target`` — the source twin
    of `_staff_target_manageable`, which refuses every source user since S1. A super manages any;
    an organisation admin only the source users of its OWN organisation (`PartnerAdmin.save`
    holds a source user's organisation equal to its source's). Anything else: no, and the views
    answer that as 404, never 403, so another organisation's id confirms nothing."""
    if caller is None or target is None or not target.is_source_user:
        return False
    if caller.is_super:
        return True
    return (caller.role == 'org_admin' and caller.owning_organisation_id is not None
            and target.owning_organisation_id == caller.owning_organisation_id)


# ── what the Sources page reads ──────────────────────────────────────────────────
def sign_in_states(source_ids):
    """`{source id: (state, active people)}` in ONE query; a source absent here is `('none', 0)`.

    `joined` = at least one ACTIVE source user has signed in (`first_seen_at`); `invited` = active
    users, none signed in yet. A revoked user counts for nothing: their source reads as if they
    were never asked, which is what the organisation can then do (invite again)."""
    rows = (PartnerAdmin.objects.filter(role=SOURCE_ROLE, is_active=True, source_id__in=source_ids)
            .values('source_id')
            .annotate(n=Count('pk'), joined=Count('pk', filter=Q(first_seen_at__isnull=False))))
    return {r['source_id']: ('joined' if r['joined'] else 'invited', r['n']) for r in rows}


def has_joined(source):
    """The lock on the Sources page (owner ruling 2026-10-30): an ACTIVE user of this source has
    signed in, so its details are now its own."""
    return PartnerAdmin.objects.filter(role=SOURCE_ROLE, source=source, is_active=True,
                                       first_seen_at__isnull=False).exists()


# ── inviting ─────────────────────────────────────────────────────────────────────
def reusable_row(existing, source):
    """The row a re-invite brings back, or None (then any ``existing`` row is a 409): ONLY a
    switched-off source user of THIS source (re-invite after a cancel or a revoke). Another
    source's, another role's — and every active row — stays refused."""
    if (existing is not None and existing.is_source_user and not existing.is_active
            and source is not None and existing.source_id == source.pk):
        return existing
    return None


def invite(caller, *, email, name, source=None, make_source=None):
    """Invite ``email`` to sign in for ``source`` (or for the NEW source ``make_source()`` creates,
    inside the same transaction, so a refused or failed invite leaves no source behind).

    The caller has already checked who may invite and which source they may name; this decides
    the account, records the invitation and sends the letter. The source's `contact_email` is
    filled with the invitee's address when it is blank (never overwritten), so the partner emails
    reach somebody from the start.

    ⚠ A RE-INVITE OF SOMEBODY WHO HAD SIGNED IN (revoked since) is a REACTIVATION: their login is
    theirs, so nothing is issued, the letter says "sign in as you always do", and the invitation is
    filed as accepted at once — there is no first sign-in left to close it (`_touch_seen` fires once
    in a row's life), and an invitation that can never close would sit in Waiting for ever.
    """
    existing = PartnerAdmin.objects.filter(email__iexact=email).order_by('id').first()
    reuse = reusable_row(existing, source)
    if existing is not None and reuse is None:
        return _refused('already_staff')
    with transaction.atomic():
        if make_source is not None:
            try:
                with transaction.atomic():
                    source = make_source()
            except IntegrityError:
                # Its code was taken between the check and the write (unique per organisation).
                return _refused('code_taken')
        if reuse is not None and reuse.first_seen_at is not None:
            account, made = _reactivate(reuse, source, name), None
            if account is None:
                transaction.set_rollback(True)
                return _refused('already_staff')
        else:
            made = staff_reinvite.provision_for_invite(
                reuse, email=email, name=name, role=SOURCE_ROLE, org=None,
                owning_org=source.organisation, source=source)
            if made.error:
                transaction.set_rollback(True)
                return _refused('already_staff' if made.error == 'not_reusable'
                                else 'create_failed')
            account = made.account
        type(source).objects.filter(pk=source.pk, contact_email='').update(contact_email=email)
        inv = invitations.create_or_refresh(
            audience=AUDIENCE, email=email, name=name, role=SOURCE_ROLE,
            organisation=source.organisation, invited_by=caller, partner_admin=account,
            credential_issued=bool(made and made.temp_password), referral_source=source)
        if made is None:
            now = timezone.now()
            type(inv).objects.filter(pk=inv.pk).update(accepted_at=now, updated_at=now)
            inv.accepted_at = now
    source.refresh_from_db()
    emailed = send(inv, account, source, made.temp_password if made else None,
                   bool(made and made.google), actor=caller)
    return Invited(None, account, inv, source, bool(made and made.google),
                   made is None or made.already_registered, reuse is not None, emailed)


def _reactivate(row, source, name):
    """Switch a revoked, once-signed-in source user of ``source`` back on. A conditional UPDATE, so a
    concurrent change (a second re-invite, the row moving) wins and this answers None."""
    done = PartnerAdmin.objects.filter(
        pk=row.pk, role=SOURCE_ROLE, source_id=source.pk, is_active=False,
    ).update(is_active=True, name=name, paused_at=None)
    if not done:
        return None
    row.refresh_from_db()
    return row


def send(inv, account, source, temp_password, google, actor=None):
    """Send the source letter for ``inv`` and record whether it went. Returns ``emailed``. ``actor``
    (who pressed Invite / Resend) gets the activity row (`invitations.record_send`)."""
    from .emails import send_source_invitation_email
    ok, error = send_source_invitation_email(
        account.email, name=account.name, source_name=source.name,
        temp_password=temp_password, google=google)
    invitations.record_send(inv, ok, error, actor=actor)
    return ok


# ── resend, revoke ───────────────────────────────────────────────────────────────
def resend(caller, target):
    """Re-send a WAITING source user's invitation: ``(emailed, error)``.

    Refused once they have signed in (`already_joined` — their password is their own, and a
    Resend would replace it) or while switched off (`not_active` — the letter would open nothing).
    A fresh temporary password and a fresh TTL clock where we issued one; the "sign in as you always
    do" note where we did not (no UID: Google, or an address that already had a login)."""
    from apps.courses.views_admin import is_google_email
    if not target.is_active:
        return False, 'not_active'
    if target.first_seen_at is not None:
        return False, 'already_joined'
    temp_password, err = staff_reinvite.reissue_credential(target)
    if err:
        return False, err
    source = target.source
    inv = invitations.create_or_refresh(
        audience=AUDIENCE, email=target.email, name=target.name, role=SOURCE_ROLE,
        organisation=source.organisation, invited_by=caller, partner_admin=target,
        credential_issued=bool(temp_password), referral_source=source)
    google = temp_password is None and is_google_email(target.email)
    return send(inv, target, source, temp_password, google, actor=caller), None


def revoke(target):
    """Switch a source user OFF: ``(done, error)``. They see nothing from the next request
    (`get_admin` reads active rows only, and `source_access.source_of` answers None for an inactive
    one). An invitation still waiting is withdrawn with it and its emailed password killed, exactly
    as Cancel does (`staff_lifecycle.kill_for_cancel`) — a revoked person must not be left holding a
    live password or a row in Waiting. The way back is to invite them again (same source)."""
    from . import staff_lifecycle
    from .models import Invitation
    now = timezone.now()
    with transaction.atomic():
        if not PartnerAdmin.objects.filter(pk=target.pk, is_active=True).update(is_active=False):
            return False, 'not_active'
        waiting = list(invitations.open_only(
            Invitation.objects.filter(audience=AUDIENCE, partner_admin=target)))
        Invitation.objects.filter(pk__in=[i.pk for i in waiting]).update(
            revoked_at=now, updated_at=now)
    target.is_active = False
    for inv in waiting:
        staff_lifecycle.kill_for_cancel(target, inv)
    return True, None
