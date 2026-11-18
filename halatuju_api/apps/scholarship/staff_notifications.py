"""Staff notifications (request #73, 2026-11-16): THE ONE WRITER of `staff_notifications`, and its reads.

A row says "this person has something new on this case they have not seen". Today the only kind is a note in
the two-way org admin and reviewer notes. The rows drive:

  * the "New note" mark on the applications table (`with_new_note`, one EXISTS column on the list query);
  * the bell line (`unseen_counts`, one query, served by `GET admin/scholarship/staff-notifications/count/`);
  * the email to the OTHER side of the conversation (`alert_by_email`, after the commit).

⚠ WHO GETS A ROW: the OTHER side of the conversation only, as the email (#73 review): the reviewer assigned to
the case when the org admin side writes; the organisation's org admin side (its active staff who may work
students, `surface_gates.may_work_students`, the same key that lets them write) when the reviewer writes. A
fellow org admin never gets a row for their own side's note. A platform super is never on an organisation's
staff list, so never gets one.

⚠ WHAT SHOWS: only a note from the OTHER side, asked of the case as it is NOW: the reviewer assigned to it sees
the org admin side's notes; everyone else sees the reviewer's. So an earlier reviewer's leftover rows stop
showing the moment the case changes hands, and `sweep` then deletes them: the assign-emails cron
(`assign_notify.send_one`, through `after_assignment`) sweeps after every assignment, and every new note
sweeps its case. The sweep reads who holds the case INSIDE its own DELETE, never who lost it, so an unassign
followed by a fresh assign is swept too, and a holder assigned a moment ago never loses a row (#73 re-check
L5). It also drops the holder's own rows for reviewer-side notes: an org admin who now holds the case reads
it as the reviewer (L6). The assignment writer itself is not touched: its query budget is pinned.

⚠ AT ASSIGNMENT (#73 re-check L7) the holder gets a mark for every org admin side note on the case that no
reviewer has read yet, so a note written while nobody held the case is not lost. No email: the assignment
email already goes. A note an earlier reviewer read is not marked again.

⚠ THE EMAIL is billed to the case's organisation (`usage.usage_context(application=...)`) and cools down
over bursts: a person who still has an UNSEEN row on the case from the last `EMAIL_COOL_DOWN` gets the row
and the mark, but no second email. Someone who read the note and replied is emailed for the next turn
(#73 re-check L4).

⚠ THE BELL COUNT is fenced to the caller's own organisation (`org_id`), on top of the recipient.

⚠ NO TEXT. A row holds ids only; the email says only that there is a new note, and links to the student page.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.utils import timezone

from apps.courses import staff_permissions
from . import surface_gates, usage
from .models import ReviewerNote, ScholarshipApplication, StaffNotification
from .models.reviewer_notes import ORG_ADMIN, REVIEWER
from .models.staff_notifications import REVIEWER_NOTE

logger = logging.getLogger(__name__)

#: One new-note email per person per case in this window (#73 review): a burst of notes is one email.
EMAIL_COOL_DOWN = timedelta(minutes=10)


def org_admin_side(application):
    """The organisation's people on the org admin side: its active staff who may work students."""
    if not application.owning_organisation_id:
        return []
    staff = staff_permissions.org_staff(application.owning_organisation_id)
    return [a for a in staff if surface_gates.may_work_students(a)]


def the_other_side(application, *, side, writer):
    """Who hears of a note ``writer`` wrote on ``side``: the assigned reviewer (if active) when the org admin
    side wrote; the org admin side when the reviewer wrote. Never the writer."""
    if side == REVIEWER:
        people = org_admin_side(application)
    else:
        reviewer = application.assigned_to if application.assigned_to_id else None
        people = [reviewer] if reviewer is not None and reviewer.is_active else []
    writer_id = getattr(writer, 'id', None)
    return [p for p in people if p.id != writer_id]


def notify(application, *, kind, source_id, recipients):
    """One unseen row per recipient. Called INSIDE the writer's transaction; a repeat is ignored."""
    StaffNotification.objects.bulk_create([
        StaffNotification(recipient=person, org_id=application.owning_organisation_id,
                          application=application, kind=kind, source_id=source_id)
        for person in recipients
    ], ignore_conflicts=True)


def alert_by_email(application, *, author_role, recipients, source_id):
    """After the commit, email ``recipients`` (the other side, `the_other_side`) that there is a new note on
    the case. Never the text. Billed to the case's organisation. Cools down: nobody who still has another
    UNSEEN row on this case from the last `EMAIL_COOL_DOWN` is emailed again. Best-effort, never raises."""
    ids = [p.id for p in recipients if p.email]
    if not ids:
        return
    recent = set(StaffNotification.objects.filter(
        application_id=application.id, recipient_id__in=ids, kind=REVIEWER_NOTE, seen_at__isnull=True,
        created_at__gte=timezone.now() - EMAIL_COOL_DOWN,
    ).exclude(source_id=source_id).values_list('recipient_id', flat=True))
    to = [p.email for p in recipients if p.email and p.id not in recent]
    if not to:
        return

    def send():
        from .emails import send_staff_note_email
        from .pool import pool_ref
        with usage.usage_context(application=application):
            for email in to:
                try:
                    send_staff_note_email(email, from_side=author_role, ref=pool_ref(application.id),
                                          application_id=application.id)
                except Exception:   # one failed alert never stops the rest
                    logger.warning('staff note email failed app=%s', application.id, exc_info=True)
    transaction.on_commit(send)


def mark_seen(recipient, application, kinds=None):
    """``recipient`` has the case's notes on screen: their unseen rows for it are seen now."""
    rows = StaffNotification.objects.filter(
        recipient_id=recipient.id, application_id=application.id, seen_at__isnull=True)
    if kinds:
        rows = rows.filter(kind__in=kinds)
    return rows.update(seen_at=timezone.now())


def sweep(application_id):
    """Delete the unseen rows on the case that no longer show: rows for an org admin side note held by anyone
    but the reviewer holding the case now, and the holder's own rows for a reviewer side note (an org admin
    who has since become the holder). Who holds the case is read INSIDE the DELETE, so a holder assigned a
    moment ago is never swept, and an unassign and then a fresh assign is swept as surely as a reassign."""
    notes = ReviewerNote.objects.filter(application_id=application_id)
    holds = Exists(ScholarshipApplication.objects.filter(
        pk=application_id, assigned_to_id=OuterRef('recipient_id')))
    rows = StaffNotification.objects.filter(
        application_id=application_id, kind=REVIEWER_NOTE, seen_at__isnull=True,
    ).filter((~holds & Q(source_id__in=notes.filter(author_role=ORG_ADMIN).values('pk')))
             | (holds & Q(source_id__in=notes.filter(author_role=REVIEWER).values('pk'))))
    return rows.delete()[0]


def mark_unread_for_the_holder(application_id):
    """At assignment (#73 re-check L7): the reviewer holding the case gets an unseen row for every org admin
    side note on it that no reviewer has read yet (a note written while nobody held the case reached
    nobody). Never their own note. No email: the assignment email already goes."""
    case = ScholarshipApplication.objects.filter(pk=application_id).select_related('assigned_to').first()
    person = case.assigned_to if case is not None else None
    if person is None or not person.is_active:
        return 0
    read = StaffNotification.objects.filter(kind=REVIEWER_NOTE, source_id=OuterRef('pk'), seen_at__isnull=False)
    unread = list(ReviewerNote.objects.filter(application_id=application_id, author_role=ORG_ADMIN)
                  .exclude(author_id=person.id).filter(~Exists(read)).values_list('pk', flat=True))
    StaffNotification.objects.bulk_create([
        StaffNotification(recipient=person, org_id=case.owning_organisation_id, application_id=application_id,
                          kind=REVIEWER_NOTE, source_id=pk)
        for pk in unread
    ], ignore_conflicts=True)
    return len(unread)


def after_assignment(application_id):
    """The assign-emails cron's housekeeping for one case: `sweep`, then `mark_unread_for_the_holder`.
    In its own savepoint; the caller logs and carries on if it raises (it must never hold up the mail)."""
    with transaction.atomic():
        sweep(application_id)
        mark_unread_for_the_holder(application_id)


def _unseen_from_the_other_side(admin):
    """``admin``'s unseen note rows whose note came from the other side of the case, as it is now."""
    note_role = Subquery(ReviewerNote.objects.filter(pk=OuterRef('source_id')).values('author_role')[:1])
    theirs = Q(application__assigned_to_id=admin.id)
    return (StaffNotification.objects
            .filter(recipient_id=admin.id, kind=REVIEWER_NOTE, seen_at__isnull=True)
            .annotate(note_role=note_role)
            .filter(Q(theirs, note_role=ORG_ADMIN) | Q(~theirs, note_role=REVIEWER)))


def with_new_note(queryset, admin):
    """The applications ``queryset`` with ``new_note``: does ``admin`` have an unseen note from the other side
    on the row? One EXISTS column on the list's own query, so the list reads no extra query."""
    if admin is None:
        return queryset
    return queryset.annotate(new_note=Exists(
        _unseen_from_the_other_side(admin).filter(application_id=OuterRef('pk'))))


def unseen_counts(admin):
    """The bell line's numbers, in one query: how many STUDENTS have a new note from a reviewer, and how many
    from the org admin side (the second is a reviewer's own cases)."""
    # org-fence: the caller's own organisation, on top of their own rows (#73 review).
    counts = _unseen_from_the_other_side(admin).filter(org_id=admin.owning_organisation_id).aggregate(
        from_reviewer=Count('application_id', distinct=True, filter=Q(note_role=REVIEWER)),
        from_org_admin=Count('application_id', distinct=True, filter=Q(note_role=ORG_ADMIN)))
    return {k: v or 0 for k, v in counts.items()}
