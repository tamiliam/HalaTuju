"""A STAFF member may ALSO be a mentor, on the same login (student maintenance Sprint 7d, 2026-11-01; owner
rulings and the lead's two data rulings in docs/decisions.md the same day). The HTTP shapes are in
`views_admin/mentors.py`.

- WHO MAY BE ADDED (`eligible`): an ACTIVE staff member of the organisation in role org_admin, admin,
  reviewer or qc (`PartnerAdmin.STAFF_MENTOR_ROLES`), not a mentor yet. Never finance, a super, a partner,
  a source user, a pure `mentor` login or a revoked / switched-off row. WHO ADDS: a super or the
  organisation admin of that organisation (`mentor_invite.may_invite` / `manageable` — the 7a actors).
- ADDING (`add`) makes a `Mentor` for the staff member's organisation and links their login to it
  (`PartnerAdmin.mentor`). The person keeps role, permissions and every page; they gain My students (the
  7c desk, `mentor_desk.mentor_of`) and the profile's mentoring bits. NO EMAIL ("tell them yourself").
  An EXISTING profile's "share my phone with students" is set OFF unless they already held `review`
  (whose switch they were shown and set): they gave the number for staff use (owner ruling).
- THE STAFF LOGIN IS NEVER THIS MODULE'S. No door here sets `is_active`, kills a password, or touches an
  invitation; 7a's mentor doors refuse a staff mentor (`mentor_invite.is_staff_login`).
- WAYS OUT, each ending every open assignment (reason "Mentor stopped mentoring", cause
  `mentor_stopped`, an activity line on each file, no email) and stamping the mentor deactivated:
  `stop` (Team → Mentors "Remove from Mentors") and `leave` — called by the staff doors: People → Revoke
  (`courses.views_staff.AdminRevokeView`), a staff invitation's Cancel (it switches the account off,
  `views_admin/invitations.py`), People → Delete (`AdminDeleteView`; refused anyway once they have
  mentored anybody — `staff_footprint` counts it, lead ruling) and a role change to a role that may not
  mentor (Admin → Finance, `staff_lifecycle.change_role`). The LINK IS KEPT on every way out (lead ruling
  2026-11-01: the mentor's name lives on this login and every scholar's history reads it; courses 0091
  lets a finance row keep it). Nothing brings mentoring back by itself — not a Restore, not a role change
  back: only `resume` (Team → Mentors → Add Mentor, which offers a removed staff mentor as "Mentored
  before", 2026-11-08), and only for an eligible, active login.
- SPRINT M1a (2026-11-10, owner O5/O6): Remove from Mentors (`stop`) is REFUSED `has_scholars` while they
  mentor anybody; it no longer ends assignments (each scholar is moved first, from their Mentoring card:
  `mentoring.assign` / `mentoring.end`). A MENTOR LOGIN removed from Mentors (`remove_mentor_login`) becomes
  "No group" (role `member`, the link kept, the Mentor deactivated). A member joins Mentors through
  `add_member` (the kept Mentor reactivated, or a new one) and becomes a mentor login (T3's shape).
- A FINANCE ROW IS NEVER AN ACTIVE MENTOR: `add` and `resume` refuse it, the role change deactivates, and
  every reader asks `PartnerAdmin.mentors_now` (never "mentor_id is set").
"""
import logging

from django.db import transaction
from django.utils import timezone

from apps.courses.models import PartnerAdmin

from . import mentoring
from .models import Mentor

# ⚠ THE PACKAGE'S name, never `__name__` — an audit line must stay on the scrape metric (H11).
logger = logging.getLogger('apps.scholarship.views_admin')

STAFF_MENTOR_ROLES = PartnerAdmin.STAFF_MENTOR_ROLES

#: M1a: the refusal a Remove from Mentors meets while they mentor somebody (owner O5).
HAS_SCHOLARS = 'has_scholars'


def has_scholars_message(name, n):
    return (f'{name} mentors {n} scholar(s) now. Move each scholar to another mentor from the scholar\'s '
            'Mentoring card first.')


def eligible(login):
    """May this STAFF login mentor (be added, or mentor again)? See the module docstring."""
    return (login is not None and login.is_active and not login.is_super
            and login.role in STAFF_MENTOR_ROLES and login.owning_organisation_id is not None)


def candidates(organisation_ids=None):
    """The staff the "Add a staff member as mentor" sheet may offer: eligible, not a mentor yet, of
    ``organisation_ids`` (None = every organisation, a super with no narrowing) — and (M1a) every active,
    signed-in "No group" member, link kept or not (`add_member`). Name order."""
    from django.db.models import Q
    qs = PartnerAdmin.objects.filter(
        Q(role__in=STAFF_MENTOR_ROLES, mentor__isnull=True)
        | Q(role=PartnerAdmin.MEMBER_ROLE, first_seen_at__isnull=False),
        is_active=True, owning_organisation__isnull=False)
    if organisation_ids is not None:
        qs = qs.filter(owning_organisation_id__in=list(organisation_ids))
    return list(qs.select_related('owning_organisation').order_by('name', 'id'))


def add(caller, target):
    """Make ``target`` (a staff login, already fenced by the view) a mentor of its own organisation.
    ``(mentor, error)``: `not_eligible`, `already_mentor`. Under a row lock; nothing is emailed."""
    from . import staff_contact
    from .models import ReviewerProfile
    by = (getattr(caller, 'email', '') or '')[:254]
    with transaction.atomic():
        row = PartnerAdmin.objects.select_for_update().filter(pk=target.pk).first()
        if row is None or row.is_mentor:
            return None, 'not_eligible'
        if row.mentor_id is not None:
            return None, 'already_mentor'
        if not eligible(row):
            return None, 'not_eligible'
        mentor = Mentor.objects.create(organisation_id=row.owning_organisation_id, created_by_email=by)
        PartnerAdmin.objects.filter(pk=row.pk, mentor__isnull=True).update(mentor=mentor)
        if not staff_contact.reviews_cases(row):
            # They gave this number for staff use (owner ruling): their students do not see it until
            # they switch it on. A `review` holder already chose for the students they interview.
            ReviewerProfile.objects.filter(partner_admin=row).update(share_phone_with_students=False)
    target.mentor_id, target.mentor = mentor.pk, mentor
    logger.info('AUDIT staff_mentor_added mentor=%s account=%s org=%s by=%s',
                mentor.pk, row.pk, mentor.organisation_id, by)
    return mentor, None


def add_member(caller, target):
    """M1a (brief §2 item 8): a "No group" member joins Mentors and becomes a MENTOR LOGIN (role `mentor`,
    NULL keys, the T3 shape): their kept Mentor is reactivated, or a new one made. ``(mentor, error)``:
    `not_eligible` (not an active, signed-in member of an organisation). Under the row lock; no email."""
    by = (getattr(caller, 'email', '') or '')[:254]
    with transaction.atomic():
        row = PartnerAdmin.objects.select_for_update().filter(pk=target.pk).first()
        if (row is None or not row.is_member or not row.is_active or row.first_seen_at is None
                or row.owning_organisation_id is None):
            return None, 'not_eligible'
        mentor = Mentor.objects.filter(pk=row.mentor_id).first() if row.mentor_id else None
        if mentor is not None and mentor.organisation_id == row.owning_organisation_id:
            Mentor.objects.filter(pk=mentor.pk).update(deactivated_at=None, deactivated_by_email='')
        else:
            mentor = Mentor.objects.create(organisation_id=row.owning_organisation_id, created_by_email=by)
        if not PartnerAdmin.objects.filter(pk=row.pk, role=PartnerAdmin.MEMBER_ROLE, is_active=True).update(
                role=PartnerAdmin.MENTOR_ROLE, mentor=mentor, permissions=None):
            return None, 'not_eligible'
    mentor.refresh_from_db()
    target.role, target.mentor_id, target.mentor, target.permissions = 'mentor', mentor.pk, mentor, None
    logger.info('AUDIT staff_mentor_member_added mentor=%s account=%s org=%s by=%s',
                mentor.pk, row.pk, mentor.organisation_id, by)
    return mentor, None


def remove_mentor_login(caller, mentor, login):
    """M1a: Team → Mentors → Remove for a MENTOR LOGIN (its only group): it becomes "No group" (role
    `member`, the link kept, the Mentor stamped deactivated; sign-in kept). ``(scholars, error)``:
    `not_active` (switched off, or the mentor already deactivated), `not_arrived` (never signed in — the
    invitation is Revoke's), `has_scholars` (with the count). Under the login lock `stop` takes."""
    by = (getattr(caller, 'email', '') or '')[:254]
    with transaction.atomic():
        row = PartnerAdmin.objects.select_for_update().filter(pk=getattr(login, 'pk', None)).first()
        if row is None or not row.is_mentor or row.mentor_id != mentor.pk:
            return 0, 'not_active'
        if not row.is_active or Mentor.objects.filter(pk=mentor.pk, deactivated_at__isnull=False).exists():
            return 0, 'not_active'
        if row.first_seen_at is None:
            return 0, 'not_arrived'
        n = mentoring.scholars_now([mentor.pk]).get(mentor.pk, 0)
        if n:
            return n, HAS_SCHOLARS
        Mentor.objects.filter(pk=mentor.pk).update(deactivated_at=timezone.now(), deactivated_by_email=by)
        PartnerAdmin.objects.filter(pk=row.pk).update(role=PartnerAdmin.MEMBER_ROLE, permissions=None)
    mentor.refresh_from_db()
    login.role = PartnerAdmin.MEMBER_ROLE
    logger.info('AUDIT mentor_login_to_member mentor=%s account=%s by=%s', mentor.pk, login.pk, by)
    return 0, None


def _end_mentoring(mentor, by):
    """Stamp ``mentor`` deactivated and end every open assignment — inside the caller's transaction.
    Returns ``(stamped, ended)``; `stamped` is False when it was already deactivated (ends anyway)."""
    stamped = bool(Mentor.objects.filter(pk=mentor.pk, deactivated_at__isnull=True).update(
        deactivated_at=timezone.now(), deactivated_by_email=by))
    ended = mentoring.end_for_mentor(mentor, by=by, reason=mentoring.REASON_STOPPED,
                                     cause=mentoring.CAUSE_STOPPED)
    return stamped, ended


def stop(caller, mentor, login):
    """Mentors page → "Remove from Mentors" for a STAFF mentor. ``(n, error)``: `not_staff` (a pure
    mentor: its own doors), `not_active` (already stopped), `has_scholars` (M1a, owner O5: ``n`` is how
    many they mentor now; nothing is ended). The staff login is not touched; ``n`` is 0 on success."""
    if login is None or not login.is_staff_mentor:
        return 0, 'not_staff'
    by = (getattr(caller, 'email', '') or '')[:254]
    with transaction.atomic():
        # T3 review: the LOGIN row is locked and judged again — the lock Team -> Remove
        # (`staff_tables_admin.change`) takes. A Remove that made them a mentor login first wins: their
        # mentoring is then Deactivate's (`not_staff`), never a stamp that leaves a live mentor login with a
        # deactivated mentor sitting in no table.
        row = PartnerAdmin.objects.select_for_update().filter(pk=login.pk, archived_at=None).first()
        if row is None or not row.is_staff_mentor or row.mentor_id != mentor.pk:
            return 0, 'not_staff'
        n = mentoring.scholars_now([mentor.pk]).get(mentor.pk, 0)
        if n:
            return n, HAS_SCHOLARS
        stamped, ended = _end_mentoring(mentor, by)
        if not stamped:
            return 0, 'not_active'
    mentor.refresh_from_db()
    logger.info('AUDIT staff_mentor_stopped mentor=%s account=%s ended=%s by=%s',
                mentor.pk, login.pk, ended, by)
    return ended, None


def resume(caller, mentor, login):
    """Team → Mentors → Add Mentor → a "Mentored before" staff member. ``error`` or None: `not_staff`, `active` (not stopped),
    `not_eligible` (the login is revoked, or its role may not mentor — finance). No email; the staff
    login untouched; no assignment comes back."""
    if login is None or not login.is_staff_mentor:
        return 'not_staff'
    with transaction.atomic():
        row = PartnerAdmin.objects.select_for_update().filter(pk=login.pk).first()
        if not eligible(row):
            return 'not_eligible'   # judged first: a login that is off is never "already active"
        if mentor.deactivated_at is None:
            return 'active'
        if not Mentor.objects.filter(pk=mentor.pk, deactivated_at__isnull=False).update(
                deactivated_at=None, deactivated_by_email=''):
            return 'active'
    mentor.refresh_from_db()
    logger.info('AUDIT staff_mentor_resumed mentor=%s account=%s by=%s', mentor.pk, login.pk,
                getattr(caller, 'email', '') or '')
    return None


def leave(login, by=''):
    """A STAFF door has taken ``login`` out of mentoring (revoked, switched off, about to be deleted, or a
    role that may not mentor): the mentor is stamped deactivated and every open assignment ends, inside
    the caller's transaction (a savepoint). The login itself is the caller's business. Returns how many
    assignments ended; 0 and nothing written for a login that is not a staff mentor.

    ⚠ S7d REVIEW FIX 2: DECIDED ON THE ROW AS IT IS NOW, never on the caller's copy. The row is re-read
    UNDER A LOCK (`mentor_id`, `role`) inside this transaction, so an Add that committed after the
    caller read the row (a Revoke or a Cancel racing it) is still caught: its mentor is stamped too."""
    if login is None:
        return 0
    by = (by or '')[:254]
    with transaction.atomic():
        row = PartnerAdmin.objects.select_for_update().filter(pk=login.pk).first()
        if row is None or not row.is_staff_mentor:
            return 0
        mentor = Mentor.objects.filter(pk=row.mentor_id).first()
        if mentor is None:
            return 0
        _, ended = _end_mentoring(mentor, by)
    login.mentor_id = row.mentor_id
    logger.info('AUDIT staff_mentor_left mentor=%s account=%s ended=%s by=%s', mentor.pk, login.pk, ended, by)
    return ended
