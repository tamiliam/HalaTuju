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


def eligible(login):
    """May this STAFF login mentor (be added, or mentor again)? See the module docstring."""
    return (login is not None and login.is_active and not login.is_super
            and login.role in STAFF_MENTOR_ROLES and login.owning_organisation_id is not None)


def candidates(organisation_ids=None):
    """The staff the "Add a staff member as mentor" sheet may offer: eligible, not a mentor yet, of
    ``organisation_ids`` (None = every organisation, a super with no narrowing). Name order."""
    qs = PartnerAdmin.objects.filter(role__in=STAFF_MENTOR_ROLES, is_active=True,
                                     mentor__isnull=True, owning_organisation__isnull=False)
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


def _end_mentoring(mentor, by):
    """Stamp ``mentor`` deactivated and end every open assignment — inside the caller's transaction.
    Returns ``(stamped, ended)``; `stamped` is False when it was already deactivated (ends anyway)."""
    stamped = bool(Mentor.objects.filter(pk=mentor.pk, deactivated_at__isnull=True).update(
        deactivated_at=timezone.now(), deactivated_by_email=by))
    ended = mentoring.end_for_mentor(mentor, by=by, reason=mentoring.REASON_STOPPED,
                                     cause=mentoring.CAUSE_STOPPED)
    return stamped, ended


def stop(caller, mentor, login):
    """Mentors page → "Stop mentoring" for a STAFF mentor. ``(ended, error)``: `not_staff` (a pure
    mentor: Deactivate is theirs), `not_active` (already stopped). The staff login is not touched."""
    if login is None or not login.is_staff_mentor:
        return 0, 'not_staff'
    by = (getattr(caller, 'email', '') or '')[:254]
    with transaction.atomic():
        # T3 review: the LOGIN row is locked and judged again — the lock Team -> Remove
        # (`staff_tables_admin.change`) takes. A Remove that made them a mentor login first wins: their
        # mentoring is then Deactivate's (`not_staff`), never a stamp that leaves a live mentor login with a
        # deactivated mentor sitting in no table.
        row = PartnerAdmin.objects.select_for_update().filter(pk=login.pk).first()
        if row is None or not row.is_staff_mentor or row.mentor_id != mentor.pk:
            return 0, 'not_staff'
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
