"""Request #55 (2026-11-07) — Notes for the reviewer.

The owner's rules, each pinned here:
  * WRITE: org_admin and a platform super only — and, since request #73 (2026-11-16), the ASSIGNED
    reviewer too (`test_staff_notifications.py` pins the two-way rules). READ: whoever may already open the file (the detail
    GET's fence): the assigned reviewer, QC, view-only admins, the org admin, a super. An unassigned
    reviewer, finance and partner are refused; another organisation is 404; a student or a sponsor
    reaches nothing.
  * The WINDOW: from Awaiting review until the reviewer records a decision (an Approve or a Decline;
    a hold is not one); a reopened decision hands it back while the case is at Interviewing.
  * 2,000 characters, blank refused, append-only (no edit, no delete).
  * NEVER in a student or sponsor payload, and NEVER read by an AI prompt builder: only the modules
    listed in `ALLOWED_READERS` may name the model.
"""
import json
import os
import re

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scholarship import reviewer_notes
from apps.scholarship.models import ReviewerNote, Sponsor
from apps.scholarship.models.reviewer_notes import NOTE_MAX
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
)

def _url(pk):
    return f'/api/v1/admin/scholarship/applications/{pk}/reviewer-notes/'

MARK = 'ZQX-reviewer-note-marker'


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    def setUp(self):
        self.org = make_org()
        self.cohort = make_cohort(owning_organisation=self.org)
        self.reviewer = make_admin('reviewer', owning_org=self.org)
        self.org_admin = make_admin('org_admin', owning_org=self.org)
        self.app = make_application('assigned', cohort=self.cohort, reviewer=self.reviewer)

    def _get(self, who, app=None):
        return authed_client(who).get(_url((app or self.app).pk))

    def _post(self, who, body=MARK, app=None):
        return authed_client(who).post(_url((app or self.app).pk), {'body': body}, format='json')


class WhoMayWriteTest(_Base):
    def test_org_admin_adds_a_note_and_it_is_stamped(self):
        r = self._post(self.org_admin, f'  {MARK}  ')
        self.assertEqual(r.status_code, 201, r.content)
        note = ReviewerNote.objects.get(application=self.app)
        self.assertEqual(note.body, MARK)   # stripped
        self.assertEqual(note.author, self.org_admin)
        self.assertEqual(note.author_email, self.org_admin.email)
        self.assertEqual(r.data['notes'][0]['author_name'], self.org_admin.name)
        self.assertTrue(r.data['can_add'])

    def test_super_adds_a_note(self):
        sup = make_admin('reviewer', super_admin=True)
        self.assertEqual(self._post(sup).status_code, 201)

    def test_nobody_else_writes(self):
        # Request #73 superseded the 'assigned reviewer' row here: the assigned reviewer now replies
        # (`test_staff_notifications.WhoMayWriteBothWaysTest`).
        others = {
            'qc': make_admin('qc', owning_org=self.org),
            'admin (view only)': make_admin('admin', owning_org=self.org),
            'finance': make_admin('finance', owning_org=self.org),
            'partner': make_admin('partner', owning_org=self.org),
        }
        for label, who in others.items():
            with self.subTest(label):
                r = self._post(who)
                self.assertEqual(r.status_code, 403, label)
                self.assertEqual(r.data['code'], 'writer_only')
        self.assertFalse(ReviewerNote.objects.exists())

    def test_another_organisations_org_admin_gets_404(self):
        other = make_admin('org_admin', owning_org=make_org())
        self.assertEqual(self._post(other).status_code, 404)
        self.assertEqual(self._get(other).status_code, 404)
        self.assertFalse(ReviewerNote.objects.exists())

    def test_a_student_and_a_sponsor_reach_nothing(self):
        student = self.app.profile
        sponsor = Sponsor.objects.create(supabase_user_id='spon-r55', email='s@example.test', name='S')
        for label, uid in (('student', student.supabase_user_id), ('sponsor', sponsor.supabase_user_id)):
            with self.subTest(label):
                self.assertEqual(self._post(uid).status_code, 403)
                self.assertEqual(self._get(uid).status_code, 403)
        self.assertIn(APIClient().get(_url(self.app.pk)).status_code, (401, 403))   # no sign-in


class WhoMayReadTest(_Base):
    def setUp(self):
        super().setUp()
        reviewer_notes.add_note(self.app, MARK, author=self.org_admin)

    def test_the_files_readers_see_the_notes_read_only(self):
        # Request #73: the assigned reviewer is a writer now (`can_add`), so is checked below, not here.
        readers = {
            'qc': make_admin('qc', owning_org=self.org),
            'admin (view only)': make_admin('admin', owning_org=self.org),
        }
        for label, who in readers.items():
            with self.subTest(label):
                r = self._get(who)
                self.assertEqual(r.status_code, 200, label)
                self.assertEqual([n['body'] for n in r.data['notes']], [MARK])
                self.assertFalse(r.data['can_add'])
                self.assertTrue(r.data['window_open'])
        r = self._get(self.org_admin)
        self.assertTrue(r.data['can_add'])
        self.assertEqual(r.data['max_length'], NOTE_MAX)
        r = self._get(self.reviewer)
        self.assertEqual([n['body'] for n in r.data['notes']], [MARK])
        self.assertTrue(r.data['can_add'])

    def test_unassigned_reviewer_finance_and_partner_are_refused(self):
        for label, who in {
            'unassigned reviewer': make_admin('reviewer', owning_org=self.org),
            'finance': make_admin('finance', owning_org=self.org),
            'partner': make_admin('partner', owning_org=self.org),
        }.items():
            with self.subTest(label):
                self.assertEqual(self._get(who).status_code, 403, label)

    def test_newest_last(self):
        reviewer_notes.add_note(self.app, 'second', author=self.org_admin)
        bodies = [n['body'] for n in self._get(self.reviewer).data['notes']]
        self.assertEqual(bodies, [MARK, 'second'])


class WindowTest(_Base):
    """From Awaiting review until the reviewer records a decision."""

    def _app(self, stage, **kw):
        return make_application(stage, cohort=self.cohort, reviewer=self.reviewer, **kw)

    def test_open_at_awaiting_review_and_interviewing(self):
        for app in (make_application('profile_complete', cohort=self.cohort), self._app('assigned'),
                    self._app('interviewing')):
            with self.subTest(app.status):
                self.assertEqual(self._post(self.org_admin, app=app).status_code, 201)

    def test_a_hold_is_not_a_decision(self):
        app = self._app('interviewing', officer_verdict={'overall': 'hold'},
                        verdict_decided_at=timezone.now())
        self.assertEqual(self._post(self.org_admin, app=app).status_code, 201)

    def test_closed_before_awaiting_review_says_not_yet(self):
        """#73 review: before the window the refusal and the served reason say "not yet", never "finished"."""
        for app in (make_application('submitted', cohort=self.cohort),
                    make_application('shortlisted', cohort=self.cohort)):
            with self.subTest(app.status):
                r = self._post(self.org_admin, app=app)
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.data['code'], 'notes_not_yet')
                self.assertIn('Awaiting review', r.data['error'])
                r = self._get(self.org_admin, app=app)
                self.assertEqual((r.data['can_add'], r.data['window_open'], r.data['reason']),
                                 (False, False, 'not_yet'))
        self.assertFalse(ReviewerNote.objects.exists())

    def test_closed_once_decided_says_finished(self):
        closed = [
            self._app('verdict_recorded', outcome='recommend'),
            self._app('verdict_recorded', outcome='decline'),
            self._app('awaiting_qc', outcome='recommend'),
            self._app('recommended'),
            self._app('awarded'),
            self._app('rejected'),
        ]
        for app in closed:
            with self.subTest(f'{app.status} {app.officer_verdict}'):
                r = self._post(self.org_admin, app=app)
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.data['code'], 'notes_closed')
                self.assertIn('finished', r.data['error'])
                r = self._get(self.org_admin, app=app)
                self.assertEqual((r.data['can_add'], r.data['reason']), (False, 'finished'))
        self.assertFalse(ReviewerNote.objects.exists())

    def test_open_serves_no_reason(self):
        r = self._get(self.org_admin, app=self._app('interviewing'))
        self.assertEqual((r.data['window_open'], r.data['reason']), (True, None))

    def test_the_locked_row_decides_not_yet_or_finished(self):
        """The status the lock refuses (`StatusRefused.status`) picks the code, not the stale object's."""
        for row_status, code in (('shortlisted', 'notes_not_yet'), ('recommended', 'notes_closed')):
            with self.subTest(row_status):
                app = self._app('interviewing')
                stale = type(app).objects.get(pk=app.pk)
                type(app).objects.filter(pk=app.pk).update(status=row_status)
                with self.assertRaises(reviewer_notes.ReviewerNoteError) as caught:
                    reviewer_notes.add_note(stale, MARK, author=self.org_admin)
                self.assertEqual(caught.exception.code, code)

    def test_notes_stay_readable_after_the_window_closes(self):
        reviewer_notes.add_note(self.app, MARK, author=self.org_admin)
        type(self.app).objects.filter(pk=self.app.pk).update(status='awarded')
        r = self._get(self.reviewer)
        self.assertEqual([n['body'] for n in r.data['notes']], [MARK])
        self.assertFalse(r.data['window_open'])

    def test_a_reopened_decision_reopens_the_window_only_at_interviewing(self):
        back = self._app('verdict_recorded', outcome='recommend', decision_reopened_at=timezone.now())
        self.assertEqual(self._post(self.org_admin, app=back).status_code, 201)
        at_qc = self._app('awaiting_qc', outcome='recommend', decision_reopened_at=timezone.now())
        self.assertEqual(self._post(self.org_admin, app=at_qc).status_code, 400)


class BodyRulesTest(_Base):
    def test_blank_and_whitespace_only_are_refused(self):
        for body in ('', '   ', '\n\t', '\u200b\ufeff', None, 42, ['x']):
            with self.subTest(repr(body)):
                r = self._post(self.org_admin, body)
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.data['code'], 'empty_body')

    def test_two_thousand_characters_and_no_more(self):
        self.assertEqual(self._post(self.org_admin, 'அ' * NOTE_MAX).status_code, 201)
        r = self._post(self.org_admin, 'a' * (NOTE_MAX + 1))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['code'], 'too_long')
        self.assertEqual(ReviewerNote.objects.count(), 1)

    def test_every_refusal_has_words(self):
        from apps.scholarship.views_admin.reviewer_notes import _MESSAGES
        self.assertEqual(set(_MESSAGES), {'writer_only', 'notes_not_yet', 'notes_closed', 'bad_body', 'empty_body',
                                         'too_long'})


class AppendOnlyTest(_Base):
    def test_no_edit_and_no_delete_through_the_endpoint(self):
        note = reviewer_notes.add_note(self.app, MARK, author=self.org_admin)
        c = authed_client(self.org_admin)
        for method in ('put', 'patch', 'delete'):
            with self.subTest(method):
                r = getattr(c, method)(_url(self.app.pk), {'body': 'changed'}, format='json')
                self.assertEqual(r.status_code, 405)
        note.refresh_from_db()
        self.assertEqual(note.body, MARK)

    def test_the_model_refuses_an_update(self):
        note = reviewer_notes.add_note(self.app, MARK, author=self.org_admin)
        note.body = 'changed'
        with self.assertRaises(ValueError):
            note.save()

    def test_an_author_with_a_note_has_a_footprint(self):
        from apps.scholarship.staff_footprint import footprint
        reviewer_notes.add_note(self.app, MARK, author=self.org_admin)
        self.assertEqual(footprint(self.org_admin).get('reviewer_notes'), 1)


class NeverLeavesTheStaffTest(_Base):
    def setUp(self):
        super().setUp()
        reviewer_notes.add_note(self.app, MARK, author=self.org_admin)

    def test_not_in_the_students_own_application(self):
        r = authed_client(self.app.profile).get(f'/api/v1/scholarship/applications/{self.app.pk}/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn(MARK, json.dumps(r.data, default=str))

    def test_not_in_any_sponsor_serializer(self):
        from apps.scholarship.serializers import (
            SponsorMyStudentDetailSerializer, SponsorPoolCardSerializer, SponsorPoolDetailSerializer,
        )
        app = make_application('recommended', cohort=self.cohort, reviewer=self.reviewer)
        ReviewerNote.objects.create(application=app, body=MARK, author=self.org_admin)
        for ser in (SponsorPoolCardSerializer, SponsorPoolDetailSerializer):
            with self.subTest(ser.__name__):
                self.assertNotIn(MARK, json.dumps(ser(app).data, default=str))
        self.assertNotIn('reviewer_note', json.dumps(list(SponsorMyStudentDetailSerializer().fields)))

    def test_not_in_the_admin_detail_payload(self):
        r = authed_client(self.org_admin).get(f'/api/v1/admin/scholarship/applications/{self.app.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(MARK, json.dumps(r.data, default=str))


class OnlyTheseModulesReadNotesTest(TestCase):
    """Structural, not prompt-trust: no AI prompt builder (case summary, profile generation, verdict),
    student view or sponsor view can name the table. A new reader must be added here deliberately."""

    ALLOWED_READERS = {
        'scholarship/models/__init__.py',
        'scholarship/models/reviewer_notes.py',
        'scholarship/reviewer_notes.py',
        'scholarship/views_admin/__init__.py',
        'scholarship/views_admin/reviewer_notes.py',
        'scholarship/staff_footprint.py',   # counts the author's email stamp only
        'scholarship/staff_notifications.py',   # #73: reads a note's author_role only, never its text
        'scholarship/urls.py',
    }
    PATTERN = re.compile(r'ReviewerNote|reviewer_notes|reviewer-notes')

    def test_nothing_else_names_the_notes(self):
        apps_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        found = set()
        for root, dirs, files in os.walk(apps_dir):
            dirs[:] = [d for d in dirs if d not in ('tests', 'migrations', '__pycache__')]
            for name in files:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding='utf-8') as fh:
                    if self.PATTERN.search(fh.read()):
                        found.add(os.path.relpath(path, apps_dir).replace(os.sep, '/'))
        self.assertEqual(found, self.ALLOWED_READERS)


class ReviewFixesTest(_Base):
    """The independent review of 2d1ae890 (R1 to R5)."""

    def _raw(self, payload):
        return authed_client(self.org_admin).post(
            _url(self.app.pk), payload, content_type='application/json')

    def test_r1_a_nul_or_a_lone_surrogate_is_a_coded_400_not_a_500(self):
        for raw in ('{"body": "abc\\u0000def"}', '{"body": "abc\\ud800def"}', '{"body": "\\udfff"}'):
            with self.subTest(raw):
                r = self._raw(raw)
                self.assertEqual(r.status_code, 400, r.content)
                self.assertEqual(r.json()['code'], 'bad_body')
        self.assertFalse(ReviewerNote.objects.exists())

    def test_r1_a_proper_surrogate_pair_is_kept(self):
        r = self._raw('{"body": "ok \\ud83d\\ude00"}')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(ReviewerNote.objects.get().body, 'ok \U0001F600')

    def test_r2_a_body_that_is_not_an_object_is_refused_not_a_500(self):
        for raw in ('["x"]', '"text"', '42', 'null'):
            with self.subTest(raw):
                r = self._raw(raw)
                self.assertEqual(r.status_code, 400, r.content)
                self.assertEqual(r.json()['code'], 'empty_body')

    def test_r3_the_window_is_re_read_under_the_lock(self):
        stale = type(self.app).objects.get(pk=self.app.pk)   # read while the window is open
        type(self.app).objects.filter(pk=self.app.pk).update(
            officer_verdict={'overall': 'accept'}, verdict_decided_at=timezone.now())
        with self.assertRaises(reviewer_notes.ReviewerNoteError) as caught:
            reviewer_notes.add_note(stale, MARK, author=self.org_admin)
        self.assertEqual(caught.exception.code, 'notes_closed')
        self.assertFalse(ReviewerNote.objects.exists())

    def test_r3_the_insert_runs_under_a_row_lock(self):
        from unittest import mock
        with mock.patch('apps.scholarship.reviewer_notes.lock_application_for',
                        wraps=reviewer_notes.lock_application_for) as lock:
            reviewer_notes.add_note(self.app, MARK, author=self.org_admin)
        lock.assert_called_once_with(self.app, reviewer_notes.NOTE_STATUSES)

    def test_r4_invisible_characters_alone_are_an_empty_note(self):
        for ch in ('\u00ad', '\u2800', '\u3164', '\u115f', '\u1160', '\u180e', '\u200e', '\u2060', '\uffa0'):
            with self.subTest(hex(ord(ch))):
                r = self._post(self.org_admin, f' {ch}{ch} ')
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.data['code'], 'empty_body')

    def test_r4_the_ends_are_trimmed_as_the_card_trims_them_so_2000_agrees(self):
        body = '\ufeff' + 'a' * NOTE_MAX + '\u200b\u3000'
        self.assertEqual(self._post(self.org_admin, body).status_code, 201)
        self.assertEqual(ReviewerNote.objects.get().body, 'a' * NOTE_MAX)

    def test_r5_a_read_writes_one_audit_line_with_ids_only(self):
        reviewer_notes.add_note(self.app, MARK, author=self.org_admin)
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            self.assertEqual(self._get(self.reviewer).status_code, 200)
        lines = [m for m in logs.output if 'AUDIT reviewer_notes_read' in m]
        self.assertEqual(len(lines), 1)
        self.assertIn(f'admin_id={self.reviewer.id} app_id={self.app.pk}', lines[0])
        self.assertNotIn(MARK, ' '.join(logs.output))


class TheReviewerWritesOnlyAnOpenCaseTest(_Base):
    """#73 re-check 4 (M1): the assigned reviewer's write asks the case stage, not only the notes window, so
    POST-AWARD-CUT's cut at the award holds even if `NOTE_STATUSES` is ever widened."""

    def _assigned(self, status, **kw):
        app = make_application('assigned', cohort=self.cohort, reviewer=self.reviewer)
        type(app).objects.filter(pk=app.pk).update(status=status, **kw)
        app.refresh_from_db()
        return app

    def test_past_the_award_or_after_an_ending_the_reviewer_gets_the_severed_403(self):
        from apps.scholarship.staff_lifecycle import PAST_AWARD, PRE_AWARD_END, case_stage
        cases = [
            (self._assigned('awarded', awarded_at=timezone.now()), PAST_AWARD),
            (self._assigned('active', awarded_at=timezone.now(), active_at=timezone.now()), PAST_AWARD),
            (self._assigned('rejected', pre_decline_status='interviewing'), PRE_AWARD_END),
            (self._assigned('expired'), PRE_AWARD_END),
            (self._assigned('withdrawn'), PRE_AWARD_END),
        ]
        for app, stage in cases:
            with self.subTest(app.status):
                self.assertEqual(case_stage(app), stage)
                r = self._post(self.reviewer, app=app)
                self.assertEqual(r.status_code, 403, r.content)   # not the window's 400
                self.assertEqual(r.data['code'], 'notes_closed')
        self.assertFalse(ReviewerNote.objects.exists())

    def test_the_stage_is_asked_before_the_window(self):
        """Widen the window to every status: the reviewer is still refused past the award, the org admin is not."""
        from unittest import mock
        app = self._assigned('awarded', awarded_at=timezone.now())
        with mock.patch.object(reviewer_notes, 'NOTE_STATUSES', ('awarded',)), \
                mock.patch.object(reviewer_notes, 'window_open', return_value=True):
            r = self._post(self.reviewer, app=app)
            self.assertEqual(r.status_code, 403, r.content)
            self.assertEqual(self._post(self.org_admin, app=app).status_code, 201)
        self.assertEqual(list(ReviewerNote.objects.values_list('author_id', flat=True)), [self.org_admin.id])

    def test_the_open_case_still_takes_the_reviewer_s_note(self):
        r = self._post(self.reviewer)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(ReviewerNote.objects.get().author, self.reviewer)


class TheStageIsAskedAgainUnderTheLockTest(_Base):
    """#73 re-check 5: `add_note` asks the reviewer side's case stage again on the LOCKED row (M1, L1), and the
    severed 403 answers only after the fence (L2). The window is widened to `awarded` throughout, as a future
    change might, so only the stage stands between the reviewer and an awarded case."""

    def setUp(self):
        super().setUp()
        from unittest import mock
        self.awarded = make_application('assigned', cohort=self.cohort, reviewer=self.reviewer)
        type(self.awarded).objects.filter(pk=self.awarded.pk).update(status='awarded', awarded_at=timezone.now())
        for patch in (mock.patch.object(reviewer_notes, 'NOTE_STATUSES', ('interviewing', 'awarded')),
                      mock.patch.object(reviewer_notes, 'window_open', return_value=True)):
            patch.start()
            self.addCleanup(patch.stop)

    def test_an_award_that_commits_after_the_view_s_check_still_cuts_the_reviewer(self):
        """M1: the view saw the case OPEN (interviewing); the award committed before the lock."""
        from unittest import mock
        from apps.scholarship.staff_lifecycle import OPEN
        from apps.scholarship.views_admin import reviewer_notes as view
        with mock.patch.object(view, 'case_stage', return_value=OPEN):
            r = self._post(self.reviewer, app=self.awarded)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data['code'], 'notes_closed')
        self.assertFalse(ReviewerNote.objects.exists())

    def test_an_org_admin_who_is_the_assignee_is_cut_on_the_reviewer_side_too(self):
        """L1: students.edit skips the view's stage check, but the note would be the REVIEWER's: refused."""
        type(self.awarded).objects.filter(pk=self.awarded.pk).update(assigned_to=self.org_admin)
        r = self._post(self.org_admin, app=self.awarded)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data['code'], 'notes_closed')
        self.assertFalse(ReviewerNote.objects.exists())

    def test_the_fence_answers_before_the_severed_403(self):
        """L2: an assignee who may not read the case (another organisation's reviewer) gets the fence's 404,
        not a 403 that says the case has ended."""
        stranger = make_admin('reviewer', owning_org=make_org())
        type(self.awarded).objects.filter(pk=self.awarded.pk).update(assigned_to=stranger)
        r = self._post(stranger, app=self.awarded)
        self.assertEqual(r.status_code, 404, r.content)
        self.assertNotIn('code', r.data)
        self.assertFalse(ReviewerNote.objects.exists())

    def test_the_severed_403_is_main_s_deny_role_with_a_code(self):
        """L3: built from `_deny_role`, so its message cannot drift from main's."""
        from apps.scholarship.views_admin.base import _AdminBase
        r = self._post(self.reviewer, app=self.awarded)
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(r.data, dict(_AdminBase()._deny_role().data, code='notes_closed'))
        self.assertFalse(ReviewerNote.objects.exists())
