"""Inviting somebody, and knowing afterwards what became of it.

The sibling of `referrals.py` (sponsor-invites-sponsor), generalised to the three audiences the
platform actually asks people to join as. See the `Invitation` model docstring for why this is its
own record rather than columns on `PartnerAdmin`.

⚠ **STATUS IS DERIVED HERE AND NOWHERE ELSE.** `status_of` is the single home for the question
"where has this invitation got to?", and nothing stores its answer. A stored status needs a cron to
stay true; when the cron stops, the screen lies — exactly the failure `temp_password_expired` has
today, sitting in Supabase metadata that nothing reads back.
"""
import secrets

from django.utils import timezone

from . import staff_activity
from .models import Invitation

#: How long a staff invitation is good for. ⚠ MUST TRACK THE TEMP-PASSWORD TTL: the login gate
#: refuses an unchanged temp password past the TTL, so a different number here would let the
#: screen say "still valid" about a password the login already rejects. Derived, never copied —
#: since Org Config Sprint C the ONE home is the `temp_password_ttl_days` registry entry
#: (org-tunable; blank = the platform's `PARTNER_TEMP_PASSWORD_TTL_DAYS`), keyed on the SAME
#: organisation the invitee will belong to, which is also what the expiry cron and the login
#: gate key on for the resulting `PartnerAdmin` row.
def staff_ttl_days(organisation=None):
    from apps.courses import org_config
    return int(org_config.value(organisation, 'temp_password_ttl_days'))


#: A sponsor invitee has consented to nothing, so their name and address are PII we hold on no
#: lawful basis once the invitation is dead. Same 60 days as `referrals.py`. (A source-partner
#: invitee was on this line until source sign-in S2 gave them an account — see `purge_expired`.)
PII_RETENTION_DAYS = 60

#: How long since somebody last opened the console before the screen calls them dormant. Descriptive
#: only — it is NEVER a permission state, and it must not look like paused or revoked. Org-tunable
#: since Org Config Sprint C; `AdminListView` serves the resolved number per staff ROW (a super's
#: list spans organisations, so one number for the whole page would be wrong), and the front end
#: reads the served value instead of its old hard-coded 90.
def dormant_days(organisation=None):
    from apps.courses import org_config
    return int(org_config.value(organisation, 'admin_dormant_days'))


def _new_code():
    return secrets.token_urlsafe(9)


# ── the four kinds the Invitations page is organised by ──────────────────────────
# Owner's shape, 2026-08-03. A KIND is what sort of person you are asking to join; the ROLE is the
# specialisation within it. Reviewers and Admins are both `staff` audiences and differ only by role,
# which is why the page needs this map rather than reading `audience` alone.
#
# ⚠ **INVITABLE HERE ≠ LISTED HERE, and the difference is deliberate.** `org_admin` is LISTED under
# Admins — an organisation admin is an admin — but is NOT invitable from this page: appointing one
# is a platform act performed by a super (`_ORG_ADMIN_MANAGEABLE_ROLES` has never included it).
# Reading one list as the other would either hide organisation admins from the roster or offer an
# org_admin the power to appoint their own successor.
KIND_ADMINS = 'admins'
KIND_REVIEWERS = 'reviewers'
KIND_SOURCE = 'source'
KIND_SPONSORS = 'sponsors'
KINDS = (KIND_ADMINS, KIND_REVIEWERS, KIND_SOURCE, KIND_SPONSORS)

#: kind → the audience its invitations carry.
KIND_AUDIENCE = {
    KIND_ADMINS: 'staff',
    KIND_REVIEWERS: 'staff',
    KIND_SOURCE: 'source_partner',
    KIND_SPONSORS: 'sponsor',
}

#: kind → the roles LISTED under it. ⚠ `source` since source sign-in S2 (2026-10-30): a source
#: invitation carries the role `source_partner`, so `for_kind` lists it and the letter it is sent is
#: chosen from here (`emails.reviewer_mail._invite_kind_for_role` → `invite_source`), the same rule
#: that picks the admin and reviewer letters.
KIND_ROLES = {
    KIND_ADMINS: ('admin', 'finance', 'org_admin'),
    KIND_REVIEWERS: ('reviewer', 'qc'),
    KIND_SOURCE: ('source_partner',),
}

#: The audiences whose invitation PROVISIONS an account up front, so accepting means signing in for
#: the first time (`accept_for_admin`) and the address sits on a `PartnerAdmin` row anyway
#: (`purge_expired` leaves it alone). Staff since the start; source users since source sign-in S2;
#: mentors since student maintenance S7a (2026-10-31).
ACCOUNT_AUDIENCES = ('staff', 'source_partner', 'mentor')

#: ⚠ A MENTOR INVITATION IS NOT ON THE INVITATIONS PAGE (S7a). The Mentors page is its roster
#: (`mentor_invite`), so `kind_of` answers None for it and the counts below skip it.
MENTOR_AUDIENCE = 'mentor'

#: kind → the roles INVITABLE from this page. Note `org_admin`'s absence; see above.
KIND_INVITABLE_ROLES = {
    KIND_ADMINS: ('admin', 'finance'),
    KIND_REVIEWERS: ('reviewer', 'qc'),
    # Source sign-in S2: invited through `POST admin/invitations/` with `audience='source_partner'`
    # (`views_admin/source_users.py`), never through the staff invite.
    KIND_SOURCE: ('source_partner',),
}


def kind_of(inv):
    """Which of the four tables this invitation belongs on — None for a MENTOR invitation (S7a),
    which belongs on none of them."""
    audience = inv.audience
    if audience == MENTOR_AUDIENCE:
        return None
    if audience == 'sponsor':
        return KIND_SPONSORS
    if audience == 'source_partner':
        return KIND_SOURCE
    return KIND_REVIEWERS if inv.role in KIND_ROLES[KIND_REVIEWERS] else KIND_ADMINS


def for_kind(qs, kind):
    """Narrow a queryset to one kind."""
    audience = KIND_AUDIENCE.get(kind)
    if audience is None:
        return qs.none()
    qs = qs.filter(audience=audience)
    roles = KIND_ROLES.get(kind)
    return qs.filter(role__in=roles) if roles else qs


def open_only(qs):
    """Narrow a queryset to the invitations still AWAITING AN ANSWER.

    ⚠ **THE ONE DEFINITION OF "WAITING", AND EVERY SURFACE MUST READ IT.** The badge on each
    button, the table the Invitations page lists, and the organisation overview's tile are three
    views of this single question; before 2026-09-09 the overview answered it privately, by
    subtracting active staff from all staff, and so reported a REVOKED admin as somebody who had
    not accepted yet. `is_open` below is the per-row twin — same rule, one row at a time.
    """
    return qs.filter(accepted_at__isnull=True, revoked_at__isnull=True)


def waiting_counts(qs, now=None):
    """`{kind: n}` of invitations still unanswered, for the badge on each button.

    ⚠ It exists because only ONE table is on screen at a time (owner's shape), so an invitation
    waiting under a kind you are not looking at would otherwise be invisible — which is the exact
    thing this page was built to stop. Counted in Python off one query rather than four `COUNT`s.
    """
    now = now or timezone.now()
    out = {k: 0 for k in KINDS}
    for inv in open_only(qs):
        kind = kind_of(inv)
        if kind is not None:
            out[kind] += 1
    return out


def kind_totals(qs):
    """`{kind: n}` of EVERY invitation ever sent, answered or not.

    ⚠ It exists for one sentence. Since the table lists only the waiting ones, an empty table has
    two completely different meanings — *nobody has ever been asked* and *everyone we asked has
    arrived* — and the browser cannot tell them apart from an empty list. Without this the page
    would have to print one of them and be wrong half the time; on this tenant it would have said
    "nobody has been invited in this group yet" over thirteen reviewers who all accepted.
    """
    out = {k: 0 for k in KINDS}
    for inv in qs:
        kind = kind_of(inv)
        if kind is not None:
            out[kind] += 1
    return out


# ── the derived status ───────────────────────────────────────────────────────────
#: What an INVITATION is doing. `no_reply` is deliberately not `expired` — see below.
INVITED = 'invited'
EXPIRED = 'expired'
NO_REPLY = 'no_reply'
ACCEPTED = 'accepted'
REVOKED = 'revoked'


def status_of(inv, now=None):
    """Where this invitation has got to. Pure; reads only the row.

    ⚠ **`no_reply` IS NOT `expired`, AND THE DIFFERENCE IS NOT COSMETIC.** "Expired" means the
    thing we sent has stopped working and a re-send is required. For a Google or already-registered
    invitee no credential was ever issued, so nothing of theirs has expired — they simply have not
    come, and re-sending posts them the same note again. Telling an org_admin that Yeoh Liew Se's
    invitation "expired" would send them looking for a password that never existed.
    """
    now = now or timezone.now()
    if inv.accepted_at:
        return ACCEPTED
    if inv.revoked_at:
        return REVOKED
    if inv.expires_at and inv.expires_at <= now:
        return EXPIRED if inv.credential_issued else NO_REPLY
    return INVITED


def is_open(inv):
    """Still awaiting an answer — the per-ROW twin of `open_only`. Keep the two in step."""
    return inv.accepted_at is None and inv.revoked_at is None


# ── writing ──────────────────────────────────────────────────────────────────────
def open_invitation(audience, email):
    return open_only(Invitation.objects.filter(
        audience=audience, email=(email or '').strip().lower())).first()


def create_or_refresh(*, audience, email, name='', role='', organisation=None, invited_by=None,
                      partner_admin=None, credential_issued=False, programme=None,
                      referral_source=None, mentor=None, ttl_days=None, now=None):
    """The one way an invitation comes into being, and the one way a re-invite is handled.

    Idempotent on an OPEN invitation to the same address: a second invite finds the existing row and
    refreshes it rather than starting a rival, so the screen can never show one person twice.
    Mirrors `referrals.create_referral`, which does the same for sponsors.

    ⚠ A RE-SEND IS NOT A NEW ROW. It moves ONE clock — `expires_at` — forward, matching the fact
    that `AdminResendView` also resets the temp-password clock. Two clocks would let this screen and
    the login gate disagree about whether somebody can still get in.

    ⚠ `programme` (sponsor invitations only, S-ASSIGN) FOLLOWS THE SAME "a re-invite may correct it"
    rule as `name`, `role` and `organisation`: a truthy value overwrites, None leaves the existing
    one alone. Re-inviting somebody into a DIFFERENT gift is a real correction and must land; a
    re-send that names no gift must not silently erase the one already stated.

    `referral_source` (source invitations only, source sign-in S2) follows the same rule, and so
    does `mentor` (mentor invitations only, S7a).
    """
    now = now or timezone.now()
    from datetime import timedelta
    email = (email or '').strip().lower()
    # The invitation's expiry follows the TTL of the organisation the invitee is joining, so the
    # screen's "expired" and the login gate's refusal move together per org (Sprint C).
    days = staff_ttl_days(organisation) if ttl_days is None else ttl_days
    expires = now + timedelta(days=days)

    inv = open_invitation(audience, email)
    if inv:
        inv.name = name or inv.name
        inv.role = role or inv.role
        inv.organisation = organisation or inv.organisation
        inv.partner_admin = partner_admin or inv.partner_admin
        inv.credential_issued = credential_issued or inv.credential_issued
        inv.programme = programme or inv.programme
        inv.referral_source = referral_source or inv.referral_source
        inv.mentor = mentor or inv.mentor
        inv.expires_at = expires
        inv.save(update_fields=['name', 'role', 'organisation', 'partner_admin',
                                'credential_issued', 'programme', 'referral_source', 'mentor',
                                'expires_at', 'updated_at'])
        return inv

    return Invitation.objects.create(
        audience=audience, email=email, name=name, role=role, organisation=organisation,
        invited_by=invited_by, partner_admin=partner_admin, code=_new_code(),
        credential_issued=credential_issued, programme=programme,
        referral_source=referral_source, mentor=mentor, expires_at=expires)


def record_send(inv, ok, error='', *, actor=None):
    """Remember that we tried to email this invitation, and whether it worked.

    The answer to "invitations send email, but that is not shown to anyone". A failure is kept
    verbatim because a bounce is usually the whole explanation for an invitation nobody acted on.
    Never raises: recording the attempt must not be able to fail the attempt.

    ``actor`` — the person who pressed Invite or Resend, passed by every live door (staff, source,
    sponsor) — gets an `invitation_sent` row on their own activity list (common profile S3). This is
    the ONE place an invitation is sent from, so it is the one place that row is written; the
    historic back-fill (`backfill_invitations`) never calls it, so it writes none.
    """
    try:
        inv.send_count = (inv.send_count or 0) + 1
        inv.last_sent_at = timezone.now()
        inv.last_send_ok = bool(ok)
        inv.last_send_error = ('' if ok else (error or 'unknown'))[:300]
        inv.save(update_fields=['send_count', 'last_sent_at', 'last_send_ok',
                                'last_send_error', 'updated_at'])
    except Exception:   # noqa: BLE001
        pass
    staff_activity.record(actor, staff_activity.INVITATION_SENT, inv, meta=lambda: {
        'audience': inv.audience, 'emailed': bool(ok), 'resend': (inv.send_count or 0) > 1})
    return inv


def accept_for_admin(admin, now=None):
    """Close this person's open staff — or SOURCE — invitation, because they have just arrived.

    ⚠ A SOURCE USER'S TOO (source sign-in S2, roadmap conflict C4). Its invitation provisions a
    `PartnerAdmin` up front exactly as a staff one does, so its first sign-in is its acceptance; left
    out, a source who had arrived would sit in Waiting for ever. (`ACCOUNT_AUDIENCES`.)

    ⚠ Called from `_touch_seen`'s FIRST-ARRIVAL rowcount, which is `1` exactly once in a row's life.
    That is what makes acceptance un-repeatable: there is no second moment at which this fires, so
    an invitation cannot be re-accepted after it was superseded or revoked.

    Best-effort — somebody signing in must never be blocked by our bookkeeping about how they came
    to be here.

    Each invitation it closes is an `invitation_accepted` row on the arriving person's own activity
    list (common profile S3) — written here, the one place an invitation is accepted.
    """
    try:
        now = now or timezone.now()
        closing = list(Invitation.objects.filter(
            audience__in=ACCOUNT_AUDIENCES, partner_admin=admin,
            accepted_at__isnull=True, revoked_at__isnull=True).values_list('pk', 'organisation_id'))
        done = Invitation.objects.filter(
            pk__in=[pk for pk, _ in closing],
            accepted_at__isnull=True, revoked_at__isnull=True).update(accepted_at=now)
    except Exception:   # noqa: BLE001
        return 0
    for pk, org_id in (closing if done else ()):
        staff_activity.record(admin, staff_activity.INVITATION_ACCEPTED, ('invitation', pk),
                              organisation=org_id)
    return done


def revoke(inv, now=None):
    inv.revoked_at = now or timezone.now()
    inv.save(update_fields=['revoked_at', 'updated_at'])
    return inv


def purge_expired(now=None, days=None):
    """Scrub the name and address of a dead invitation nobody consented to give us.

    The row survives so counts stay honest; the person does not. Same rule and the same 60 days as
    `referrals.purge_expired_referrals`, and it is in from day one rather than retrofitted, because
    a retention rule added later has already failed for everyone it should have covered.

    ⚠ Staff are EXEMPT: a staff invitee is a colleague whose address the organisation holds anyway
    (they are a `PartnerAdmin` row with that email on it), so scrubbing it here would delete half a
    record while the other half stayed. Only the audiences who consented to nothing are purged.
    ⚠ SO ARE SOURCE USERS (source sign-in S2, C4): the invite provisions their `PartnerAdmin` row
    too, so the same half-a-record argument holds (`ACCOUNT_AUDIENCES`). Only sponsors are purged.
    """
    from datetime import timedelta
    now = now or timezone.now()
    cutoff = now - timedelta(days=days or PII_RETENTION_DAYS)
    stale = Invitation.objects.filter(
        accepted_at__isnull=True, pii_purged_at__isnull=True,
        expires_at__lt=cutoff).exclude(audience__in=ACCOUNT_AUDIENCES)
    return stale.update(email='', name='', pii_purged_at=now)
