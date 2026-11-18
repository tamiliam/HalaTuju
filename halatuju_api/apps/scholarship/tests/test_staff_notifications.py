"""Request #73 (2026-11-16) — two-way org admin and reviewer notes, and the staff notifications behind them.

Pinned here:
  * WRITE both ways: org admins and a super (students.edit) and the ASSIGNED reviewer; QC, another reviewer and
    everyone else read only (or nothing); another organisation 404. The side is recorded on the note.
  * The WINDOW stays #55's: from Awaiting review until the reviewer records a decision, for both sides.
  * Reassignment: the new reviewer reads every note and replies; the old one loses the case, its notes and
    its unseen rows — after an unassign and a fresh assign too (`sweep`, #73 review). The sweep reads the
    holder inside its DELETE and drops an org admin holder's reviewer-note rows (#73 re-check L5, L6); a
    failed sweep never holds up the assignment emails (M3).
  * AT ASSIGNMENT (#73 re-check L7) the holder gets a mark for each org admin note no reviewer has read.
  * WHO HEARS (#73 review): the OTHER side only, rows and email alike; never a fellow org admin for their own
    side's note; with no reviewer, an org admin's note reaches nobody until assignment. The email never carries
    the text, is billed to the case's organisation and cools down over bursts (one per person per case per ten
    minutes while the earlier one is unseen; #73 re-check L4).
  * Per-person unread: the "New note" mark on the list and the bell count, cleared when THAT person opens
    the notes or replies; the bell count fenced to the caller's own organisation; the list reads no extra
    query for the mark.
  * ONE WRITER of `StaffNotification`: `apps/scholarship/staff_notifications.py`.
"""
import os
import re
from unittest import mock

from datetime import timedelta

from django.core import mail
from django.db import DatabaseError, connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.scholarship import assign_notify, reviewer_notes, staff_notifications, usage
from apps.scholarship.emails.staff_note_mail import build_staff_note_email
from apps.scholarship.models import ReviewerNote, StaffNotification
from apps.scholarship.pool import pool_ref
from apps.scholarship.services import assignment
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)

MARK = 'ZQX-two-way-note-marker'
LIST = '/api/v1/admin/scholarship/applications/'
COUNT = '/api/v1/admin/scholarship/staff-notifications/count/'


def _url(pk):
    return f'/api/v1/admin/scholarship/applications/{pk}/reviewer-notes/'


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.org = make_org()
        self.cohort = make_cohort(owning_organisation=self.org)
        self.reviewer = make_admin('reviewer', owning_org=self.org, email='rev73@example.test',
                                   first_seen_at=timezone.now())
        self.org_admin = make_admin('org_admin', owning_org=self.org, email='oa73@example.test')
        self.org_admin2 = make_admin('org_admin', owning_org=self.org, email='oa73b@example.test')
        self.app = make_application('assigned', cohort=self.cohort, reviewer=self.reviewer)

    def _post(self, who, body=MARK, app=None):
        with self.captureOnCommitCallbacks(execute=True):
            return authed_client(who).post(_url((app or self.app).pk), {'body': body}, format='json')

    def _get(self, who, app=None):
        return authed_client(who).get(_url((app or self.app).pk))

    def _marked(self, who):
        """The application ids `who` sees with the "New note" mark on the applications table."""
        r = authed_client(who).get(LIST)
        self.assertEqual(r.status_code, 200, r.content)
        return {row['id'] for row in r.data['applications'] if row['new_note']}

    def _rows(self, who):
        return StaffNotification.objects.filter(recipient=who, seen_at__isnull=True).count()


class WhoMayWriteBothWaysTest(_Base):
    def test_the_assigned_reviewer_replies_and_the_side_is_recorded(self):
        self.assertEqual(self._post(self.org_admin, 'from the org admin').status_code, 201)
        r = self._post(self.reviewer, 'from the reviewer')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(list(ReviewerNote.objects.order_by('id').values_list('author_role', flat=True)),
                         ['org_admin', 'reviewer'])
        notes = r.data['notes']
        self.assertEqual([n['body'] for n in notes], ['from the org admin', 'from the reviewer'])   # oldest first
        self.assertEqual([n['author_role'] for n in notes], ['org_admin', 'reviewer'])
        self.assertEqual([n['is_you'] for n in notes], [False, True])
        self.assertEqual(r.data['viewer'], 'reviewer')
        self.assertTrue(r.data['can_add'])

    def test_a_super_writes_on_the_org_admin_side(self):
        sup = make_admin('reviewer', super_admin=True)
        self.assertEqual(self._post(sup).status_code, 201)
        self.assertEqual(ReviewerNote.objects.get().author_role, 'org_admin')
        self.assertEqual(self._get(sup).data['viewer'], 'org_admin')

    def test_qc_and_another_reviewer_cannot_write(self):
        for label, who in {'qc': make_admin('qc', owning_org=self.org),
                           'another reviewer': make_admin('reviewer', owning_org=self.org)}.items():
            with self.subTest(label):
                r = self._post(who)
                self.assertEqual(r.status_code, 403, label)
                self.assertEqual(r.data['code'], 'writer_only')
        self.assertFalse(ReviewerNote.objects.exists())

    def test_qc_reads_as_a_reader(self):
        self._post(self.reviewer)
        r = self._get(make_admin('qc', owning_org=self.org))
        self.assertEqual((r.data['viewer'], r.data['can_add']), ('reader', False))
        self.assertEqual([n['author_role'] for n in r.data['notes']], ['reviewer'])

    def test_another_organisation_is_refused(self):
        other_org = make_org()
        self.assertEqual(self._post(make_admin('org_admin', owning_org=other_org)).status_code, 404)
        # A reviewer not on the case is refused before the fence, as #55 refused every non-writer.
        self.assertEqual(self._post(make_admin('reviewer', owning_org=other_org)).status_code, 403)
        self.assertFalse(ReviewerNote.objects.exists())

    def test_the_side_is_decided_on_the_locked_row(self):
        stale = type(self.app).objects.get(pk=self.app.pk)        # still shows the reviewer as assigned
        type(self.app).objects.filter(pk=self.app.pk).update(
            assigned_to=make_admin('reviewer', owning_org=self.org))
        with self.assertRaises(reviewer_notes.ReviewerNoteError) as caught:
            reviewer_notes.add_note(stale, MARK, author=self.reviewer)
        self.assertEqual(caught.exception.code, 'writer_only')
        self.assertFalse(ReviewerNote.objects.exists())


class WindowBothWaysTest(_Base):
    def test_the_reviewer_cannot_add_once_they_have_recommended(self):
        app = make_application('verdict_recorded', outcome='recommend', cohort=self.cohort, reviewer=self.reviewer)
        r = self._post(self.reviewer, app=app)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'notes_closed')
        r = self._get(self.reviewer, app=app)
        self.assertEqual((r.data['viewer'], r.data['window_open'], r.data['can_add']), ('reviewer', False, False))

    def test_open_at_interviewing_for_the_reviewer(self):
        app = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        self.assertEqual(self._post(self.reviewer, app=app).status_code, 201)


class ReassignmentTest(_Base):
    def setUp(self):
        super().setUp()
        self.app = make_application('profile_complete', cohort=self.cohort)
        self.super = make_admin(super_admin=True)
        self.new_reviewer = make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now())
        assignment.assign_reviewer(self.app, reviewer=self.reviewer, by_admin=self.super)
        self.app.refresh_from_db()

    def _reassign(self):
        assignment.assign_reviewer(self.app, reviewer=self.new_reviewer, by_admin=self.super)
        self.app.refresh_from_db()

    def test_the_new_reviewer_reads_every_note_and_replies(self):
        self._post(self.org_admin, 'to the first reviewer')
        self._post(self.reviewer, 'the first reviewer answers')
        self._reassign()
        r = self._get(self.new_reviewer)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([n['body'] for n in r.data['notes']], ['to the first reviewer', 'the first reviewer answers'])
        self.assertEqual(self._post(self.new_reviewer, 'the new reviewer').status_code, 201)
        self.assertEqual(ReviewerNote.objects.order_by('-id').first().author_role, 'reviewer')

    def test_the_old_reviewer_loses_the_case_and_its_new_note_rows(self):
        self._post(self.org_admin)
        self.assertEqual(staff_notifications.unseen_counts(self.reviewer)['from_org_admin'], 1)
        self._reassign()
        self.assertEqual(self._post(self.reviewer).data['code'], 'writer_only')
        # Hidden at once (the reads ask who holds the case now), deleted by the assign-emails cron.
        self.assertEqual(staff_notifications.unseen_counts(self.reviewer)['from_org_admin'], 0)
        self.assertEqual(self._rows(self.reviewer), 1)
        with mock.patch('apps.scholarship.emails.send_reviewer_assigned_email'), \
                mock.patch('apps.scholarship.emails.send_student_assigned_reviewer_email'):
            assign_notify.send_pending()
        self.assertEqual(self._rows(self.reviewer), 0)

    def _cron(self):
        with mock.patch('apps.scholarship.emails.send_reviewer_assigned_email'), \
                mock.patch('apps.scholarship.emails.send_student_assigned_reviewer_email'):
            assign_notify.send_pending()

    def test_an_unassign_then_a_fresh_assign_sweeps_the_old_reviewers_rows(self):
        """#73 review: the fresh assign's event has no `from_admin`, so a sweep by "who lost it" missed A."""
        self._cron()                                   # the first assignment's emails are out of the way
        self._post(self.org_admin)
        self.assertEqual(self._rows(self.reviewer), 1)
        assignment.assign_reviewer(self.app, reviewer=None, by_admin=self.super)
        self.app.refresh_from_db()
        self._reassign()
        self._cron()
        self.assertEqual(self._rows(self.reviewer), 0)
        self.assertEqual(self._rows(self.new_reviewer), 1)   # no reviewer read the note: marked (#73 re-check L7)
        self._post(self.org_admin, 'to the new reviewer')
        self.assertEqual(self._rows(self.new_reviewer), 2)   # the holder's own rows are never swept

    def test_a_new_note_sweeps_its_case(self):
        self._post(self.org_admin)
        assignment.assign_reviewer(self.app, reviewer=None, by_admin=self.super)
        self.app.refresh_from_db()
        self.assertEqual(self._rows(self.reviewer), 1)   # an unassign writes no queued event: no cron sweep
        self._post(self.org_admin, 'while nobody holds it')
        self.assertEqual(self._rows(self.reviewer), 0)

    def test_the_sweep_keeps_the_org_admin_sides_rows(self):
        self._post(self.reviewer)
        staff_notifications.sweep(self.app.id)
        self.assertEqual((self._rows(self.org_admin), self._rows(self.org_admin2)), (1, 1))

    def test_the_sweep_reads_the_holder_inside_its_delete(self):
        """#73 re-check L5: a holder assigned after the cron read its event never loses a row."""
        self._post(self.org_admin)
        type(self.app).objects.filter(pk=self.app.pk).update(assigned_to=self.new_reviewer)   # behind its back
        StaffNotification.objects.create(recipient=self.new_reviewer, org_id=self.org.id, application=self.app,
                                         kind='reviewer_note', source_id=ReviewerNote.objects.get().id)
        self.assertEqual(staff_notifications.sweep(self.app.id), 1)    # the old reviewer's row only
        self.assertEqual((self._rows(self.reviewer), self._rows(self.new_reviewer)), (0, 1))

    def test_an_org_admin_who_becomes_the_holder_loses_their_reviewer_note_rows(self):
        """#73 re-check L6: holding the case, they read it as the reviewer, so a reviewer note's row is stale."""
        self._post(self.reviewer)
        self.assertEqual(self._rows(self.org_admin), 1)
        type(self.app).objects.filter(pk=self.app.pk).update(assigned_to=self.org_admin)
        staff_notifications.sweep(self.app.id)
        self.assertEqual((self._rows(self.org_admin), self._rows(self.org_admin2)), (0, 1))

    def test_a_failed_sweep_never_holds_up_the_assignment_emails(self):
        """#73 re-check M3: housekeeping is logged and the mail still goes, on the first attempt."""
        with mock.patch.object(staff_notifications, 'sweep', side_effect=RuntimeError('db')), \
                mock.patch('apps.scholarship.emails.send_reviewer_assigned_email') as to_reviewer, \
                mock.patch('apps.scholarship.emails.send_student_assigned_reviewer_email'), \
                self.assertLogs('apps.scholarship.assign_notify', level='WARNING') as logs:
            counts = assign_notify.send_pending()
        self.assertEqual(counts['sent'], 1)
        to_reviewer.assert_called_once()
        self.assertIn('new-note housekeeping failed', '\n'.join(logs.output))

    def test_a_real_database_error_in_the_sweep_leaves_the_mail_and_the_connection_working(self):
        """#73 re-check 2 L-D: the savepoint rolls the broken statement back, so the cron carries on."""
        def broken(_application_id):
            with connection.cursor() as cursor:
                cursor.execute('SELECT * FROM no_such_table_req73')
        with mock.patch.object(staff_notifications, 'sweep', side_effect=broken), \
                mock.patch('apps.scholarship.emails.send_reviewer_assigned_email') as to_reviewer, \
                mock.patch('apps.scholarship.emails.send_student_assigned_reviewer_email'), \
                self.assertLogs('apps.scholarship.assign_notify', level='WARNING') as logs:
            counts = assign_notify.send_pending()
        self.assertEqual(counts['sent'], 1)
        to_reviewer.assert_called_once()
        failed = [r for r in logs.records if 'housekeeping failed' in r.getMessage()]
        self.assertEqual(len(failed), 1)
        self.assertTrue(issubclass(failed[0].exc_info[0], DatabaseError))   # a real one, not a mock's
        self.assertEqual(StaffNotification.objects.count(), 0)           # the connection still answers
        self.assertEqual(self._post(self.org_admin).status_code, 201)


class MarkAtAssignmentTest(_Base):
    """#73 re-check L7: a note written while nobody held the case reaches nobody until the case is assigned;
    the assign-emails cron then gives the holder a mark for it. No extra email."""

    def setUp(self):
        super().setUp()
        self.app = make_application('profile_complete', cohort=self.cohort)
        self.super = make_admin(super_admin=True)

    def _assign(self, who):
        assignment.assign_reviewer(self.app, reviewer=who, by_admin=self.super)
        self.app.refresh_from_db()

    def _cron(self):
        with mock.patch('apps.scholarship.emails.send_reviewer_assigned_email'), \
                mock.patch('apps.scholarship.emails.send_student_assigned_reviewer_email'):
            assign_notify.send_pending()

    def test_a_note_written_before_anyone_holds_the_case_marks_the_holder_at_assignment(self):
        self.assertEqual(self._post(self.org_admin, 'before anyone holds it').status_code, 201)
        self.assertFalse(StaffNotification.objects.exists())      # reaches nobody yet
        self._assign(self.reviewer)
        self._cron()
        self.assertEqual(self._rows(self.reviewer), 1)
        self.assertEqual(self._marked(self.reviewer), {self.app.id})
        self.assertEqual(staff_notifications.unseen_counts(self.reviewer)['from_org_admin'], 1)
        self.assertEqual(mail.outbox, [])                          # no new-note email: the assignment email goes
        self._cron()                                               # a second run adds nothing
        self.assertEqual(StaffNotification.objects.count(), 1)

    def test_after_assignment_twice_marks_once(self):
        """#73 re-check 2 L-D: the housekeeping itself is idempotent, not just the cron's claim."""
        self._post(self.org_admin, 'before anyone holds it')
        type(self.app).objects.filter(pk=self.app.pk).update(assigned_to=self.reviewer)
        staff_notifications.after_assignment(self.app.id)
        staff_notifications.after_assignment(self.app.id)
        self.assertEqual(StaffNotification.objects.filter(recipient=self.reviewer).count(), 1)

    def test_the_mark_never_silences_the_next_real_email(self):
        """#73 re-check 2 M-A: the cool-down asks whether the NOTE is recent, so a fresh mark for an older note
        does not hold back the first email the holder should get; nor does a note from before they held it."""
        self._post(self.org_admin, 'before anyone holds it')                # moments before, not ten minutes
        self._assign(self.reviewer)
        self._cron()
        self.assertEqual(self._rows(self.reviewer), 1)
        self._post(self.org_admin, 'a new note, a minute after the assignment')
        self.assertEqual([m.to for m in mail.outbox], [[self.reviewer.email]])

    def test_a_note_an_earlier_reviewer_read_is_not_marked_again(self):
        self._assign(self.reviewer)
        self._cron()
        self._post(self.org_admin, 'read by the first reviewer')
        self._get(self.reviewer)                                   # seen
        self._post(self.org_admin, 'never read')
        self._assign(make_admin('reviewer', owning_org=self.org, first_seen_at=timezone.now()))
        self._cron()
        holder = self.app.assigned_to
        marked = StaffNotification.objects.filter(recipient=holder, seen_at__isnull=True)
        self.assertEqual([ReviewerNote.objects.get(pk=r.source_id).body for r in marked], ['never read'])
        self.assertEqual(self._rows(self.reviewer), 0)             # the old reviewer's unseen row is swept

    def test_the_holders_own_note_is_never_marked(self):
        self._post(self.org_admin, 'my own note')
        self._post(self.org_admin2, 'a colleague')
        type(self.app).objects.filter(pk=self.app.pk).update(assigned_to=self.org_admin)   # an org admin holds it
        staff_notifications.after_assignment(self.app.id)
        marked = StaffNotification.objects.filter(recipient=self.org_admin, seen_at__isnull=True)
        self.assertEqual([ReviewerNote.objects.get(pk=r.source_id).body for r in marked], ['a colleague'])


class WhoHearsTest(_Base):
    def test_an_org_admin_note_reaches_the_reviewer_by_email_without_the_text(self):
        self._post(self.org_admin)
        self.assertEqual(self._rows(self.reviewer), 1)
        self.assertEqual(self._rows(self.org_admin2), 0)   # #73 review: their own side wrote it, as the email
        self.assertEqual(self._rows(self.org_admin), 0)    # never the writer
        self.assertEqual([m.to for m in mail.outbox], [[self.reviewer.email]])
        sent = mail.outbox[0]
        self.assertNotIn(MARK, sent.subject + sent.body)
        self.assertIn(pool_ref(self.app.id), sent.subject)
        self.assertIn(f'/admin/scholarship/{self.app.id}', sent.body)

    def test_a_reviewer_note_reaches_the_org_admin_side_by_email_without_the_text(self):
        self._post(self.reviewer)
        self.assertEqual(self._rows(self.reviewer), 0)
        self.assertEqual((self._rows(self.org_admin), self._rows(self.org_admin2)), (1, 1))
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([self.org_admin.email, self.org_admin2.email]))
        for sent in mail.outbox:
            self.assertNotIn(MARK, sent.subject + sent.body)

    def test_no_reviewer_yet_an_org_admin_note_reaches_nobody_until_assignment(self):
        app = make_application('profile_complete', cohort=self.cohort)
        self.assertEqual(self._post(self.org_admin, app=app).status_code, 201)
        self.assertFalse(StaffNotification.objects.exists())
        self.assertEqual(mail.outbox, [])
        # ...then the holder gets a mark from the assign-emails cron (#73 re-check L7, `MarkAtAssignmentTest`).

    def test_the_email_is_billed_to_the_cases_organisation(self):
        seen = []
        with mock.patch('apps.scholarship.emails.send_staff_note_email',
                        side_effect=lambda *a, **k: seen.append(dict(usage.current_context()))):
            self._post(self.org_admin)
        self.assertEqual(len(seen), 1)
        self.assertEqual((seen[0]['org_id'], seen[0]['app_id']), (self.org.id, self.app.id))

    def test_one_email_per_person_per_case_per_ten_minutes(self):
        self._post(self.org_admin, 'one')
        self._post(self.org_admin2, 'two')               # a minute later in effect: rows, no second email
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self._rows(self.reviewer), 2)    # the mark still counts both
        ReviewerNote.objects.update(   # the cool-down asks the NOTE's age (#73 re-check 2 M-A)
            created_at=timezone.now() - staff_notifications.EMAIL_COOL_DOWN - timedelta(minutes=1))
        self._post(self.org_admin, 'three')
        self.assertEqual(len(mail.outbox), 2)
        other = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        self._post(self.org_admin, 'another case', app=other)   # per case: another student emails at once
        self.assertEqual(len(mail.outbox), 3)

    def test_someone_who_read_and_replied_is_emailed_for_the_next_turn(self):
        """#73 re-check L4: the cool-down counts UNSEEN rows only; it is for bursts, not for a conversation."""
        self._post(self.org_admin, 'one')
        self.assertEqual(len(mail.outbox), 1)
        self._get(self.reviewer)                          # the reviewer reads it
        self._post(self.reviewer, 'an answer')
        mail.outbox.clear()
        self._post(self.org_admin, 'the next turn')       # inside ten minutes of 'one'
        self.assertEqual([m.to for m in mail.outbox], [[self.reviewer.email]])

    def test_qc_never_gets_a_row(self):
        qc = make_admin('qc', owning_org=self.org)
        self._post(self.org_admin)
        self._post(self.reviewer)
        self.assertEqual(self._rows(qc), 0)

    def test_a_failed_email_never_undoes_the_note(self):
        with mock.patch('apps.scholarship.emails.send_staff_note_email', side_effect=RuntimeError('smtp')):
            self.assertEqual(self._post(self.org_admin).status_code, 201)
        self.assertEqual(ReviewerNote.objects.count(), 1)


class UnreadPerPersonTest(_Base):
    def test_the_mark_shows_to_the_other_side_and_clears_when_that_person_opens_the_notes(self):
        self._post(self.org_admin)
        self.assertEqual(self._marked(self.reviewer), {self.app.id})
        self.assertEqual(self._marked(self.org_admin2), set())   # their own side wrote it
        self.assertEqual(self._get(self.reviewer).status_code, 200)
        self.assertEqual(self._marked(self.reviewer), set())

    def test_each_org_admin_clears_only_their_own_mark(self):
        self._post(self.reviewer)
        self.assertEqual(self._marked(self.org_admin), {self.app.id})
        self.assertEqual(self._marked(self.org_admin2), {self.app.id})
        self._get(self.org_admin)
        self.assertEqual(self._marked(self.org_admin), set())
        self.assertEqual(self._marked(self.org_admin2), {self.app.id})

    def test_opening_one_case_clears_only_that_case_and_only_the_opener(self):
        second = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        self._post(self.reviewer)
        self._post(self.reviewer, app=second)
        self.assertEqual(self._marked(self.org_admin), {self.app.id, second.id})
        self._get(self.org_admin)
        self.assertEqual(self._marked(self.org_admin), {second.id})
        self.assertEqual(self._marked(self.org_admin2), {self.app.id, second.id})

    def test_replying_clears_the_repliers_own_mark(self):
        """#73 review: the reviewer replies without a fresh GET; the org admin's note is no longer new to her."""
        self._post(self.org_admin)
        self.assertEqual(self._marked(self.reviewer), {self.app.id})
        self.assertEqual(self._post(self.reviewer, 'reply').status_code, 201)
        self.assertEqual(self._marked(self.reviewer), set())
        self.assertEqual(self._marked(self.org_admin), {self.app.id})   # the reply is new to the other side

    def test_the_list_reads_no_extra_query_with_notes_present(self):
        def queries():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(authed_client(self.reviewer).get(LIST).status_code, 200)
            return len(ctx.captured_queries)
        before = queries()
        self._post(self.org_admin)
        self._post(self.org_admin2, 'two')
        self.assertEqual(self._marked(self.reviewer), {self.app.id})
        self.assertEqual(queries(), before)


class BellCountTest(_Base):
    def test_counts_students_not_notes_from_the_other_side(self):
        second = make_application('interviewing', cohort=self.cohort, reviewer=self.reviewer)
        self._post(self.reviewer)
        self._post(self.reviewer, 'again')
        self._post(self.reviewer, app=second)
        r = authed_client(self.org_admin).get(COUNT)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, {'from_reviewer': 2, 'from_org_admin': 0})
        self.assertEqual(authed_client(self.reviewer).get(COUNT).data, {'from_reviewer': 0, 'from_org_admin': 0})
        self._post(self.org_admin)
        self.assertEqual(authed_client(self.reviewer).get(COUNT).data, {'from_reviewer': 0, 'from_org_admin': 1})

    def test_opening_the_notes_takes_the_student_off_the_count(self):
        self._post(self.reviewer)
        self._get(self.org_admin)
        self.assertEqual(authed_client(self.org_admin).get(COUNT).data['from_reviewer'], 0)

    def test_fenced_to_the_callers_own_organisation(self):
        """#73 review: a row filed under another organisation never reaches this caller's bell."""
        other_app = make_application('interviewing', cohort=make_cohort(owning_organisation=make_org()))
        note = ReviewerNote.objects.create(application=other_app, body='x', author=self.reviewer,
                                           author_role='reviewer', author_email='')
        staff_notifications.notify(other_app, kind='reviewer_note', source_id=note.id, recipients=[self.org_admin])
        self.assertEqual(self._rows(self.org_admin), 1)
        self.assertEqual(staff_notifications.unseen_counts(self.org_admin)['from_reviewer'], 0)
        self._post(self.reviewer)
        self.assertEqual(staff_notifications.unseen_counts(self.org_admin)['from_reviewer'], 1)

    def test_a_holder_with_no_organisation_counts_their_own_case(self):
        """#73 re-check 2 L-A: a super who held a case before T1 keeps it (T1-d); their bell counts it."""
        sup = make_admin('reviewer', super_admin=True, email='sup73@example.test')
        held = make_application('interviewing', cohort=self.cohort, reviewer=sup)
        self.assertIsNone(sup.owning_organisation_id)
        self._post(self.org_admin, app=held)
        self.assertEqual(staff_notifications.unseen_counts(sup), {'from_reviewer': 0, 'from_org_admin': 1})
        self.assertEqual(authed_client(sup).get(COUNT).data, {'from_reviewer': 0, 'from_org_admin': 1})

    def test_one_query(self):
        self._post(self.reviewer)
        with self.assertNumQueries(1):
            staff_notifications.unseen_counts(self.org_admin)

    def test_signed_out_and_a_student_are_refused(self):
        from rest_framework.test import APIClient
        self.assertIn(APIClient().get(COUNT).status_code, (401, 403))
        self.assertEqual(authed_client(self.app.profile).get(COUNT).status_code, 403)


class EmailWordingTest(TestCase):
    def test_both_sides_in_all_three_languages_with_the_link_and_the_ref(self):
        for side, words in (('reviewer', ('The reviewer added', 'Penyemak telah menambah', 'மதிப்பாய்வாளர் உங்கள்')),
                            ('org_admin', ('Your org admin added', 'Pentadbir organisasi anda',
                                           'உங்கள் நிறுவன நிர்வாகி'))):
            with self.subTest(side):
                subject, body = build_staff_note_email(from_side=side, ref='BP-7', application_id=42)
                self.assertTrue(subject.endswith('— BP-7'))
                for w in words:
                    self.assertIn(w, body)
                self.assertEqual(body.count('/admin/scholarship/42'), 3)
                self.assertLess(body.index(words[0]), body.index(words[1]))
                self.assertLess(body.index(words[1]), body.index(words[2]))


class OneWriterTest(TestCase):
    """Only these modules may name `StaffNotification`; the service module is the one that writes."""

    ALLOWED = {
        'scholarship/models/__init__.py',
        'scholarship/models/staff_notifications.py',
        'scholarship/staff_notifications.py',
    }
    PATTERN = re.compile(r'\bStaffNotification\b')

    def test_nothing_else_names_the_model(self):
        apps_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        found = set()
        for root, dirs, files in os.walk(apps_dir):
            dirs[:] = [d for d in dirs if d not in ('tests', 'migrations', '__pycache__')]
            for name in files:
                if name.endswith('.py'):
                    path = os.path.join(root, name)
                    with open(path, encoding='utf-8') as fh:
                        if self.PATTERN.search(fh.read()):
                            found.add(os.path.relpath(path, apps_dir).replace(os.sep, '/'))
        self.assertEqual(found, self.ALLOWED)
