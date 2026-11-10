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
- ONE EMAIL, ONE ADMIN SIGN-IN: an address that already has ANY `PartnerAdmin` row (staff, source,
  another mentor) is refused `already_staff` — with ONE exception, the source pattern's
  (`source_invite.reusable_row`; S7b follow-up review, owner 2026-11-01): a SWITCHED-OFF mentor of THIS
  organisation who NEVER SIGNED IN (revoked or deactivated before arriving) is brought back by inviting
  the same address again on Invitations → Mentor (`reusable_row`): reactivated, a fresh invitation and
  letter, a fresh password only where we issue one (`staff_reinvite.reissue_credential`).
- A STUDENT'S OR SPONSOR'S LOGIN MAY BE A MENTOR (owner ruling 2026-10-31, replacing the review's
  "any existing sign-in is refused"): the admin side and the student/sponsor side are separate
  domains, as for staff. Such an address keeps its own login — `provision_*` answers
  `already_registered`, the row is written with NO UID and is never issued a password, the letter
  says "sign in the way you normally do", and `get_admin` links the row on their next verified-email
  sign-in. Every later door then treats it as somebody's own login (`has_signed_in` below).
- STAFF EDIT NAME AND EMAIL ONLY UNTIL THE FIRST SIGN-IN (`edit`): after it, 409 `managed_by_mentor` —
  the mentor keeps their own details up to date. Staff never write the mentor's profile.
- DEACTIVATE switches the login off (`is_active=False`, the source user's revoke), withdraws a waiting
  invitation and kills its emailed password, and stamps `deactivated_at/_by_email`. REACTIVATE
  reverses it for a mentor who has signed in, and sends nothing (see the Mentors-page rule below).
  S7b: Deactivate (and Revoke, the same switch-off) also ENDS every open mentoring assignment of
  theirs (`mentoring.end_for_mentor`); Reactivate restores none.
- THE MENTORS PAGE NEVER INVITES (S7b follow-up review, owner 2026-11-01): it manages mentors who have
  ARRIVED, like People. Reactivate is only for a mentor who has signed in, and sends nothing; a mentor
  who never signed in is refused `not_arrived` there — they come back by a re-invite (above).

STATUS IS DERIVED (`status_of`), never stored: `inactive` when deactivated; `invited` until the login's
first sign-in (`has_signed_in`); else `active`.

⚠ S7d (2026-11-01): A STAFF MEMBER MAY ALSO BE A MENTOR (`staff_mentor.py`) — their mentor record's login
is their STAFF login. NOTHING HERE MAY TOUCH IT: Resend, Revoke, Deactivate, Reactivate and the name /
email edit refuse a staff mentor (`staff_mentor`, via `is_staff_login`), and `_switch_off` (which switches
the login off and kills a password) refuses one again at its own door. A staff mentor's status is
`inactive` (stopped) or `active` — their sign-in is People's business.

⚠ REVIEW FIX (2026-10-31, adversarial review of 7a):
- "SIGNED IN" IS NOT ONLY `first_seen_at`. `get_admin` links a row with no UID to a caller's VERIFIED
  email on ANY admin request — a refused one too — without stamping `first_seen_at` (only
  `admin/role/` does). A mentor login we never issued a password for (the newest invitation's
  `credential_issued` is false: a Google address, or a student's or sponsor's own login) that carries
  a UID was linked that way, so it has signed in: Resend, Revoke, the email move and Reactivate's
  letter all treat it so, and a password is only ever reissued when the newest invitation issued one.
  Before that link the row has no UID, so nothing can reset, kill or delete the person's own login.
"""
import logging
from collections import namedtuple

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.courses import staff_reinvite
from apps.courses.models import PartnerAdmin

from . import invitations, mentor_gift
from .models import Invitation, Mentor

# ⚠ THE PACKAGE'S name, never `__name__` — an audit line must stay on the scrape metric (H11).
logger = logging.getLogger('apps.scholarship.views_admin')

MENTOR_ROLE = PartnerAdmin.MENTOR_ROLE
AUDIENCE = invitations.MENTOR_AUDIENCE

ACTIVE, INVITED, INACTIVE = 'active', 'invited', 'inactive'


STATUSES = (ACTIVE, INVITED, INACTIVE)

#: What `invite` did. ``error`` is None, `already_staff` or `create_failed`.
Invited = namedtuple('Invited', 'error mentor account invitation google already_registered emailed')


# ── who may act, and on what ─────────────────────────────────────────────────────
def may_invite(caller):
    """The v2 key `invitations.edit` (Team tables T5c; lead-only, no preset grants it): a super, or an
    organisation admin. Never an admin, finance, reviewer, QC, source or mentor."""
    from apps.courses import staff_tables
    return staff_tables.opens_door(caller, 'invitations')


def may_read(caller):
    """Who may open the Mentors page: a super, an organisation admin, an admin (read-only).

    A1.10a (TD-497, lead's call): the door `mentors_read` = `mentoring.view`. NOT `team.view` (ruling 2's
    filing): finance and a person at Admins by a key hold `team.view`, so it would OPEN the page to them.
    `mentoring.view` is held by exactly T1's admin-work holders (super, org_admin, the `admin` label), so
    nobody gains or loses the page."""
    from apps.courses import staff_tables
    return staff_tables.opens_door(caller, 'mentors_read')


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


def is_staff_login(login):
    """S7d: True when ``login`` is a STAFF member's (who also mentors) — never this module's to touch."""
    return login is not None and login.is_staff_mentor


def status_of(mentor, login, credential_issued=None):
    """`inactive` / `invited` / `active` — see the module docstring."""
    if mentor.deactivated_at is not None:
        return INACTIVE
    if is_staff_login(login):
        # S7d review fix 2: a staff mentor whose login is off (revoked, switched off) or whose role may
        # not mentor reads inactive, whatever a race left on the mentor record.
        return ACTIVE if login.mentors_now else INACTIVE
    if not has_signed_in(login, credential_issued):
        return INVITED
    return ACTIVE


# ── inviting ─────────────────────────────────────────────────────────────────────
def reusable_row(existing, organisation):
    """The mentor login a re-invite brings back, or None (then ``existing`` is a 409): ONLY a
    switched-off mentor of THIS organisation who never signed in. Any other row stays refused."""
    if (existing is None or not existing.is_mentor or organisation is None
            or existing.mentor.organisation_id != organisation.pk
            or existing.mentor.deactivated_at is None or has_signed_in(existing)):
        return None
    return existing


def _reinvite(caller, login, *, organisation, email, name, gifts=()):
    """Bring ``login``'s switched-off, never-signed-in mentor back: a fresh credential where we issued
    one (never onto a login the person brought — `reissue_credential`), the mentor and login switched
    on, a fresh invitation, the letter. Nothing is written when the credential cannot be issued."""
    from apps.courses.views_admin import is_google_email
    mentor = login.mentor
    temp_password, err = staff_reinvite.reissue_credential(login)
    if err:
        return Invited('create_failed', None, None, None, False, False, False)
    with transaction.atomic():
        if not Mentor.objects.filter(pk=mentor.pk, deactivated_at__isnull=False).update(
                deactivated_at=None, deactivated_by_email=''):
            return Invited('already_staff', None, None, None, False, False, False)
        PartnerAdmin.objects.filter(pk=login.pk).update(is_active=True, paused_at=None, name=name)
        login.refresh_from_db()
        mentor.refresh_from_db()
        # I4: the new invite's gifts. A switched-off mentor holds no open assignment (`_switch_off`
        # ended them), so nothing can stand outside the new gifts.
        mentor_gift.set_gifts(mentor, gifts, check_open=False)
        inv = invitations.create_or_refresh(
            audience=AUDIENCE, email=login.email, name=name, role=MENTOR_ROLE,
            organisation=organisation, invited_by=caller, partner_admin=login,
            credential_issued=bool(temp_password), mentor=mentor)
    google = temp_password is None and is_google_email(login.email)
    emailed = send(inv, login, organisation, temp_password, google, actor=caller)
    return Invited(None, mentor, login, inv, google, temp_password is None and not google, emailed)


def invite(caller, *, organisation, email, name, gifts=()):
    """Make ``organisation``'s new mentor, their login and their invitation, then send the letter.

    The caller has already checked who may invite and resolved the organisation (inside its fence).
    Nothing is left behind by a refusal or a failure: the mentor, the login row and the invitation
    are written in ONE transaction, and the letter goes only after it commits. A switched-off mentor
    of this organisation who never signed in is brought back instead (`reusable_row`).

    I4 (2026-11-08): ``gifts`` are the gifts they will mentor in (``[]`` = every gift), already chosen
    inside ``organisation`` (`mentor_gift.choose`); written on the mentor in the same transaction. A
    resend never touches them."""
    existing = PartnerAdmin.objects.select_related('mentor').filter(email__iexact=email).order_by('id').first()
    if existing is not None and existing.is_archived:   # M1a: the same row back (`mentor_archive`)
        from . import mentor_archive
        return mentor_archive.reinvite(caller, existing, organisation=organisation, email=email, name=name,
                                       gifts=gifts)
    if existing is not None:
        reuse = reusable_row(existing, organisation)
        if reuse is None:
            return Invited('already_staff', None, None, None, False, False, False)
        return _reinvite(caller, reuse, organisation=organisation, email=email, name=name, gifts=gifts)
    try:
        with transaction.atomic():
            mentor = Mentor.objects.create(organisation=organisation,
                                           created_by_email=caller.email or '')
            mentor_gift.set_gifts(mentor, gifts, check_open=False)   # I4: a new mentor mentors nobody yet
            made = staff_reinvite.provision_for_invite(
                None, email=email, name=name, role=MENTOR_ROLE, org=None,
                owning_org=organisation, mentor=mentor)
            if made.error:
                transaction.set_rollback(True)
                return Invited('create_failed', None, None, None, False, False, False)
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
    error)``. The Resend's (Invitations → Mentor)."""
    from apps.courses.views_admin import is_google_email
    # A password is reissued ONLY onto a login we issued one for — never onto one somebody brought
    # with them: `reissue_credential` holds that rule for every Resend since TD-440.
    temp_password, err = staff_reinvite.reissue_credential(login)
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
    (`already_joined` — their password is their own) or while deactivated (`not_active`); a staff
    mentor (S7d) is `staff_mentor`."""
    if is_staff_login(login):
        return False, 'staff_mentor'
    state = status_of(mentor, login)
    if state == INACTIVE or login is None or not login.is_active:
        return False, 'not_active'
    if state == ACTIVE:
        return False, 'already_joined'
    return _send_again(caller, mentor, login)


# ── switching off and on ─────────────────────────────────────────────────────────
def _switch_off(caller, mentor, login):
    """Login off, waiting invitation withdrawn, mentor stamped — in ONE transaction, each write
    conditional so a concurrent change wins. Then the emailed password is killed. ``(done, error)``.
    ⚠ NEVER FOR A STAFF MENTOR (S7d): it would switch their STAFF login off — refused `staff_mentor`."""
    if is_staff_login(login):
        return False, 'staff_mentor'
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
        # S7b: their open assignments end with them ("Mentor deactivated", a line on each file, no
        # email), in this transaction. Reactivate restores none of them.
        from . import mentoring
        mentoring.end_for_mentor(mentor, by=caller.email or '')
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
    Deactivate), `not_active` when already off, `staff_mentor` for a staff member (S7d)."""
    if is_staff_login(login):
        return False, 'staff_mentor'
    state = status_of(mentor, login)
    if state == INACTIVE:
        return False, 'not_active'
    if state == ACTIVE:
        return False, 'already_joined'
    return _switch_off(caller, mentor, login)


def deactivate(caller, mentor, login):
    """Switch a mentor OFF — never a delete. ``(done, error)``; `not_active` when already off;
    `staff_mentor` for a staff member (S7d: Stop mentoring is theirs, `staff_mentor.stop`)."""
    if is_staff_login(login):
        return False, 'staff_mentor'
    if status_of(mentor, login) == INACTIVE:
        return False, 'not_active'
    return _switch_off(caller, mentor, login)


def reactivate(caller, mentor, login):
    """Switch a deactivated mentor back ON: ``(done, emailed, error)``. Their login is switched on and
    the stamp cleared; nothing is sent — their login is theirs. ONLY for a mentor who has signed in
    (S7b follow-up review: the Mentors page never invites): one who never did is refused
    `not_arrived` and comes back by a re-invite on Invitations → Mentor (`reusable_row`).
    `active` when not deactivated; `staff_mentor` for a staff member (S7d: Mentor again,
    `staff_mentor.resume`)."""
    if is_staff_login(login):
        return False, False, 'staff_mentor'
    if status_of(mentor, login) != INACTIVE:
        return False, False, 'active'
    if login is None:
        return False, False, 'no_login'
    if not has_signed_in(login):
        return False, False, 'not_arrived'
    with transaction.atomic():
        if not Mentor.objects.filter(pk=mentor.pk, deactivated_at__isnull=False).update(
                deactivated_at=None, deactivated_by_email=''):
            return False, False, 'active'
        PartnerAdmin.objects.filter(pk=login.pk).update(is_active=True, paused_at=None)
    mentor.deactivated_at, mentor.deactivated_by_email = None, ''
    login.is_active = True
    return True, False, None


# ── staff editing name and email, until the first sign-in ────────────────────────
def edit(caller, mentor, login, *, name=None, email=None):
    """Correct a mentor's NAME or EMAIL before they have signed in: ``(changed, emailed, error)``.

    `managed_by_mentor` once they have signed in (their details are theirs from then on);
    `not_active` while deactivated. A new EMAIL is a new sign-in: the old address's waiting invitation
    is withdrawn and its login retired the way a staff delete retires one (`staff_lifecycle`: removed
    only when ours and unused, else its temporary password killed, else left alone and unlinked), a
    login is provisioned for the new address by the invite's own branches, and the invitation is sent
    there. `already_staff` when the new address already has an admin sign-in (a student's or sponsor's
    login is kept, as at invite); `create_failed` / `retire_failed` when Supabase could not be asked
    (nothing changes). A staff mentor (S7d) is `staff_mentor`: their details are their staff account's."""
    if is_staff_login(login):
        return False, False, 'staff_mentor'
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
    old_uid = login.supabase_user_id
    plan, account = staff_lifecycle.plan_login_retirement(login)   # BEFORE the address changes
    if plan == supabase_admin.FAILED:
        return False, False, 'retire_failed'
    now = timezone.now()
    new_login = staff_reinvite.provision_login(email, name)
    if new_login.error:
        return False, False, 'create_failed'
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
    # S7b review fix 1: the new address may be a scholar's own — an assignment to that scholar ends.
    from . import mentoring
    mentoring.end_if_self(mentor, by=caller.email or '')
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


# ── deleting (D6, Sprint T2, 2026-11-08) ─────────────────────────────────────────
def mentor_work(row, mentor):
    """A mentor's records: the login's footprint, else the mentor's own assignments and sessions (the
    Delete's test; M1a: also whether a Delete archives, `mentor_archive.archive`)."""
    from . import staff_footprint
    from .models import MentorAssignment, MentoringSession
    work = staff_footprint.footprint(row) if row is not None else {}
    if not work and (MentorAssignment.objects.filter(mentor=mentor).exists()
                     or MentoringSession.objects.filter(mentor=mentor).exists()):
        counts = {'scholars_mentored': MentorAssignment.objects.filter(mentor=mentor).count(),
                  'mentoring_sessions': MentoringSession.objects.filter(mentor=mentor).count()}
        work = {k: n for k, n in counts.items() if n}
    return work


def delete_mentor(caller, mentor, login):
    """DELETE a mentor who has NO work: their invitations, their login and the mentor record, in ONE
    transaction; the Supabase login is retired after (`staff_lifecycle.retire_login`), as for staff.

    ``(error, detail)``: on success ``(None, <the login word for the AUDIT line>)``; else `staff_mentor`
    (a staff member who also mentors — deleted from Team -> Admins / Reviewers, where their mentoring
    counts as work), `not_found`, `has_work` with the footprint counts, or `login_cleanup_failed`.

    ⚠ THE FOOTPRINT REFUSES FIRST. Any mentoring assignment ever (ended too), any session, any concern —
    `staff_footprint.MENTOR_TRACES`, keyed on the mentor itself — and every email stamp of the login.
    `MentorAssignment.mentor` / `MentoringSession.mentor` stay PROTECT as the database's backstop. The
    mentor row is LOCKED first: in Postgres a new assignment's foreign key waits on that lock, so work
    landing between the check and the delete cannot slip through."""
    from apps.courses import supabase_admin
    from . import staff_lifecycle
    if is_staff_login(login):
        return 'staff_mentor', None
    with transaction.atomic():
        locked = Mentor.objects.select_for_update().filter(pk=mentor.pk).first()
        if locked is None:
            return 'not_found', None
        row = PartnerAdmin.objects.select_for_update().filter(mentor=locked).order_by('id').first()
        if is_staff_login(row):
            return 'staff_mentor', None
        if row is not None and row.is_archived:   # M1a: out of reach by id (the scope hides it too)
            return 'not_found', None
        work = mentor_work(row, locked)
        if work:
            return 'has_work', work
        plan, account = (staff_lifecycle.plan_login_retirement(row) if row is not None
                         else ('none', None))
        if plan == supabase_admin.FAILED:
            return 'login_cleanup_failed', None
        uid = row.supabase_user_id if row is not None else None
        Invitation.objects.filter(mentor=locked).delete()   # PROTECT on the mentor: theirs go first
        if row is not None:
            row.delete()
        locked.delete()
    done = staff_lifecycle.retire_login(uid, plan, account)
    logger.info('AUDIT mentor_deleted mentor=%s account=%s login=%s by=%s', mentor.pk,
                login.pk if login else '-', done, caller.email or '')
    return None, done
