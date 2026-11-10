"""A mentor login's Delete-as-archive and its re-invite (Sprint M1a, 2026-11-10; owner O7, TD-484).

The mentor half of `apps.courses.staff_archive` (read its docstring first): the same `archive_locked`
and the same `restore`, behind the mentor doors (`AdminMentorDetailView.delete`, the mentor invite).

  archive   `DELETE admin/mentors/<id>/` with `{"archive": true}` on a mentor login WITH records (any
            assignment ever, any session, any stamp — `mentor_invite.mentor_work`): the login archived,
            the mentor stamped deactivated and KEPT (its name stays on every scholar's history). With
            no records, `delete_mentor` erases, as today. A staff member who also mentors is never
            this door's (`staff_mentor`, as today): they are deleted from the Staff list.
  restore   the mentor invite of an archived address: an archived MENTOR LOGIN of this organisation
            comes back on the same row and the same mentor (a new login, `first_seen_at` NULL, the
            mentor switched on, the invite's gifts, a NEW invitation, the letter). An archived STAFF row
            of this organisation answers `use_staff_invite` (staff come back through the staff invite,
            brief §5); another organisation's archived address keeps `already_staff`.
"""
from django.db import transaction

from apps.courses import staff_archive, staff_reinvite
from apps.courses.models import PartnerAdmin

from . import invitations, mentor_gift
from .models import Mentor


def archive(caller, mentor, login):
    """``(refusal, detail)`` — ``('archived', <login word>)`` when archived; `has_unfinished_work` with the
    counts or `login_cleanup_failed`; None when this is not an archive (no records, a staff mentor, gone):
    `delete_mentor` then answers exactly as today."""
    from . import mentor_invite, staff_lifecycle
    if mentor_invite.is_staff_login(login):
        return None
    with transaction.atomic():
        locked = Mentor.objects.select_for_update().filter(pk=mentor.pk).first()
        row = (PartnerAdmin.objects.select_for_update().filter(mentor=locked).order_by('id').first()
               if locked is not None else None)
        if row is None or mentor_invite.is_staff_login(row) or not mentor_invite.mentor_work(row, locked):
            return None
        done = staff_archive.archive_locked(caller, row)
        if done.error:
            return done.error, done.work
    return 'archived', staff_lifecycle.retire_login(done.uid, done.plan, done.account)


def reinvite(caller, existing, *, organisation, email, name, gifts=()):
    """The mentor invite's answer for an ARCHIVED ``existing`` (an `mentor_invite.Invited`)."""
    from .mentor_invite import AUDIENCE, MENTOR_ROLE, Invited, send
    refused = Invited('already_staff', None, None, None, False, False, False)
    if organisation is None or existing.owning_organisation_id != organisation.pk:
        return refused
    if not existing.is_mentor:
        return Invited('use_staff_invite', None, None, None, False, False, False)
    mentor = existing.mentor
    if mentor is None or mentor.organisation_id != organisation.pk:
        return refused
    with transaction.atomic():
        made = staff_reinvite.provision_for_invite(
            existing, email=email, name=name, role=MENTOR_ROLE, org=None, owning_org=organisation,
            mentor=mentor)
        if made.error:
            transaction.set_rollback(True)
            return Invited('already_staff' if made.error == 'not_reusable' else 'create_failed',
                           None, None, None, False, False, False)
        Mentor.objects.filter(pk=mentor.pk).update(deactivated_at=None, deactivated_by_email='')
        mentor.refresh_from_db()
        mentor_gift.set_gifts(mentor, gifts, check_open=False)   # a switched-off mentor holds no scholar
        inv = invitations.create_or_refresh(
            audience=AUDIENCE, email=email, name=name, role=MENTOR_ROLE, organisation=organisation,
            invited_by=caller, partner_admin=made.account, credential_issued=bool(made.temp_password),
            mentor=mentor)
    emailed = send(inv, made.account, organisation, made.temp_password, made.google, actor=caller)
    return Invited(None, mentor, made.account, inv, made.google, made.already_registered, emailed)
