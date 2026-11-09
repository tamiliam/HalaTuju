"""Student maintenance S7c (2026-11-01): a MENTOR sees their current students and logs meetings; a concern
reaches staff, who mark it handled.

Doors, each driven through the real endpoints:

- READ: the list is the caller's OPEN assignments only; the per-student page and the log answer 404 for
  another mentor's student, an ended assignment, another organisation's file, an unknown id and the
  mentor's own application; a deactivated mentor and every non-mentor are refused.
- WHAT IS SERVED is an allowlist (money, documents, letters, family, staff notes never), and a meeting
  staff logged carries no notes, next step or minutes.
- WRITE: 7b's validation, the file in maintenance, the assignment re-checked under the lock (a staff End
  racing the log wins and nothing is written); no email to anyone.
- CONCERN: raised only by the mentor's log; handled only by staff of the organisation; twice is
  idempotent; a later concern re-raises; the Scholars chip, filter and count agree; reviewer / QC see no
  concern line, chip or count; the student's own tab is unchanged (date + how).
- `mentor_methods`: the three new views are the only 7c additions (sprint S1 adds the Scholars reads).
"""
import datetime
import json
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import get_resolver
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.courses.models_claim import ProfileLoginAlias
from apps.scholarship import closure, mentor_desk, mentoring
from apps.scholarship.models import MentorAssignment, MentoringSession, SemesterResult, StudentActivity
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_student,
)
from apps.scholarship.tests.test_mentoring import _scholar, make_mentor

DESK = '/api/v1/admin/mentor/students/'
SCHOLARS = '/api/v1/admin/scholarship/scholars/'
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


def page(app_id):
    return f'{DESK}{app_id}/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@LOCMEM
class _Base(TestCase):
    def setUp(self):
        self.app = _scholar(student=make_student(name='NUR AISYAH', contact_email='aisyah@example.test',
                                                 contact_phone='0172223344'),
                            help_university='yes', chosen_programme={'course_name': 'Diploma in Accounting',
                                                                     'institution': 'Politeknik Ungku Omar'})
        self.org = self.app.owning_organisation
        self.org_admin = make_admin('org_admin', owning_org=self.org)
        self.kavitha = make_mentor(self.org)
        self.faizal = make_mentor(self.org, 'Faizal Hamid', area='Engineering')
        self.login = mentoring._login(self.kavitha)
        mentoring.assign(self.org_admin, self.app, self.kavitha, email_student=False)
        mail.outbox.clear()

    def mentor(self, login=None):
        return authed_client(login or self.login)

    def log(self, app=None, login=None, **body):
        body.setdefault('met_on', timezone.localdate().isoformat())
        body.setdefault('mode', 'video')
        body.setdefault('minutes', 45)
        body.setdefault('notes', 'Went through the timetable.')
        return self.mentor(login).post(f'{DESK}{(app or self.app).id}/sessions/', body, format='json')

    def staff_meet(self, **body):
        body.setdefault('met_on', timezone.localdate().isoformat())
        body.setdefault('mode', 'in_person')
        body.setdefault('minutes', 60)
        body.setdefault('notes', 'STAFF SECRET NOTE')
        body.setdefault('next_step', 'STAFF SECRET STEP')
        return authed_client(self.org_admin).post(f'{SCHOLARS}{self.app.id}/mentoring/sessions/', body,
                                                  format='json')

    def events(self, app=None):
        return list(StudentActivity.objects.filter(application=app or self.app, kind='system')
                    .exclude(event='').order_by('id').values_list('event', 'meta', 'internal'))


class TestTheMentorSeesOnlyCurrentStudents(_Base):
    def test_the_list_is_their_open_assignments_only(self):
        other = _scholar(cohort=self.app.cohort)
        mentoring.assign(self.org_admin, other, self.faizal, email_student=False)          # someone else's
        ended = _scholar(cohort=self.app.cohort)
        mentoring.assign(self.org_admin, ended, self.kavitha, email_student=False)
        mentoring.end(self.org_admin, ended)                                                 # mentoring ended
        r = self.mentor().get(DESK)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual([s['id'] for s in body['students']], [self.app.id])
        self.assertEqual(body['organisation'], self.org.name)
        self.assertEqual(set(body['students'][0]), {
            'id', 'name', 'course', 'institution', 'email', 'phone', 'since', 'meetings', 'last_meeting',
            'latest_result', 'standing', 'asked_for_help'})
        row = body['students'][0]
        self.assertEqual((row['name'], row['latest_result'], row['standing'], row['meetings']),
                         ('NUR AISYAH', None, 'no_result_yet', 0))
        self.assertTrue(row['asked_for_help']['university'])

    def test_when_mentoring_ends_the_student_leaves_and_every_door_is_404(self):
        self.assertEqual(self.mentor().get(page(self.app.id)).status_code, 200)
        mentoring.end(self.org_admin, self.app)
        self.assertEqual(self.mentor().get(DESK).json()['students'], [])
        self.assertEqual(self.mentor().get(page(self.app.id)).status_code, 404)
        self.assertEqual(self.log().status_code, 404)
        self.assertEqual(MentoringSession.objects.count(), 0)

    def test_another_mentors_another_orgs_and_an_unknown_student_are_404(self):
        theirs = _scholar(cohort=self.app.cohort)
        mentoring.assign(self.org_admin, theirs, self.faizal, email_student=False)
        foreign = _scholar()
        foreign_admin = make_admin('org_admin', owning_org=foreign.owning_organisation)
        mentoring.assign(foreign_admin, foreign, make_mentor(foreign.owning_organisation, 'Stranger'),
                         email_student=False)
        for app_id in (theirs.id, foreign.id, 999999):
            with self.subTest(app_id=app_id):
                self.assertEqual(self.mentor().get(page(app_id)).status_code, 404)
                r = self.mentor().post(f'{page(app_id)}sessions/', {
                    'met_on': timezone.localdate().isoformat(), 'mode': 'video', 'notes': 'x'}, format='json')
                self.assertEqual(r.status_code, 404)
        self.assertEqual(MentoringSession.objects.count(), 0)

    def test_the_mentor_who_is_the_student_has_no_access(self):
        ProfileLoginAlias.objects.create(alias_uid=self.login.supabase_user_id, profile=self.app.profile)
        self.assertEqual(self.mentor().get(DESK).json()['students'], [])
        self.assertEqual(self.mentor().get(page(self.app.id)).status_code, 404)
        self.assertEqual(self.log().status_code, 404)
        self.assertEqual(MentoringSession.objects.count(), 0)

    def test_a_closed_file_leaves_the_list(self):
        closure.close_application(self.app, closure_reason='graduated', by_email=self.org_admin.email)
        self.assertEqual(self.mentor().get(DESK).json()['students'], [])
        self.assertEqual(self.log().status_code, 404)

    def test_an_open_assignment_on_a_file_out_of_maintenance_is_not_served(self):
        """Belt and braces: the read requires the maintenance predicate, not only an open row."""
        type(self.app).objects.filter(pk=self.app.pk).update(status='recommended')
        self.assertEqual(self.mentor().get(DESK).json()['students'], [])
        self.assertEqual(self.mentor().get(page(self.app.id)).status_code, 404)

    def test_a_deactivated_mentor_is_refused(self):
        PartnerAdmin.objects.filter(pk=self.login.pk).update(is_active=False)
        type(self.kavitha).objects.filter(pk=self.kavitha.pk).update(deactivated_at=timezone.now())
        for r in (self.mentor().get(DESK), self.mentor().get(page(self.app.id)), self.log()):
            self.assertIn(r.status_code, (401, 403))

    def test_a_deactivated_mentor_with_a_live_login_still_reads_nothing(self):
        type(self.kavitha).objects.filter(pk=self.kavitha.pk).update(deactivated_at=timezone.now())
        self.assertEqual(self.mentor().get(DESK).status_code, 403)
        self.assertEqual(self.log().status_code, 403)

    def test_staff_sources_and_students_are_refused(self):
        callers = [self.org_admin, make_admin('super', super_admin=True), make_admin('admin', owning_org=self.org),
                   make_admin('source_partner', owning_org=self.org), self.app.profile.supabase_user_id]
        for who in callers:
            with self.subTest(who=getattr(who, 'role', 'student')):
                c = authed_client(who)
                self.assertIn(c.get(DESK).status_code, (401, 403))
                self.assertIn(c.get(page(self.app.id)).status_code, (401, 403))
                r = c.post(f'{page(self.app.id)}sessions/', {
                    'met_on': timezone.localdate().isoformat(), 'mode': 'video', 'notes': 'x'}, format='json')
                self.assertIn(r.status_code, (401, 403))
        self.assertEqual(MentoringSession.objects.count(), 0)


class TestWhatTheMentorIsServed(_Base):
    FORBIDDEN = ('award', 'paid', 'remaining', 'disburs', 'contract', 'letter', 'document', 'slip', 'income',
                 'household', 'guardian', 'family', 'photo', 'substate', 'on_hold', 'history', 'activity',
                 'nric', 'STAFF SECRET', 'end_reason', 'logged_by_email', 'Faizal')

    def test_the_student_page_is_an_allowlist(self):
        SemesterResult.objects.create(application=self.app, semester='Sem 1', cgpa=Decimal('2.50'),
                                      review_status='accepted')
        SemesterResult.objects.create(application=self.app, semester='Sem 2', cgpa=Decimal('3.21'),
                                      review_status='accepted')
        SemesterResult.objects.create(application=self.app, semester='Sem 3', cgpa=Decimal('1.00'),
                                      review_status='pending')
        self.staff_meet()
        r = self.mentor().get(page(self.app.id))
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(set(body), {'id', 'name', 'course', 'institution', 'email', 'phone', 'since',
                                     'asked_for_help', 'latest_result', 'standing', 'organisation', 'meetings',
                                     'modules'})   # S10: their development modules (read-only)
        self.assertEqual((body['email'], body['phone'], body['since']),
                         ('aisyah@example.test', '0172223344', timezone.localdate().isoformat()))
        # The LATEST accepted result only, with its term; a pending one never shows.
        self.assertEqual(body['latest_result'], {'cgpa': '3.21', 'semester': 'Sem 2'})
        self.assertEqual(body['standing'], 'performing')
        text = json.dumps(body)
        for needle in self.FORBIDDEN + ('2.50', '1.00', 'Sem 1'):
            self.assertNotIn(needle, text)

    def test_a_staff_logged_meeting_is_date_and_how_only_and_theirs_is_in_full(self):
        self.staff_meet()
        self.assertEqual(self.log(notes='MY NOTE', next_step='MY STEP', minutes=30).status_code, 201)
        meetings = self.mentor().get(page(self.app.id)).json()['meetings']
        self.assertEqual(len(meetings), 2)
        staff = next(m for m in meetings if not m['by_you'])
        mine = next(m for m in meetings if m['by_you'])
        self.assertEqual(set(staff), {'id', 'met_on', 'mode', 'by_you'})
        self.assertEqual(staff['mode'], 'in_person')
        self.assertEqual((mine['notes'], mine['next_step'], mine['minutes'], mine['concern']),
                         ('MY NOTE', 'MY STEP', 30, False))

    def test_a_meeting_logged_under_an_earlier_assignment_is_not_shown(self):
        self.log(notes='FIRST TIME ROUND')
        mentoring.assign(self.org_admin, self.app, self.faizal, email_student=False)
        mentoring.assign(self.org_admin, self.app, self.kavitha, email_student=False)
        meetings = self.mentor().get(page(self.app.id)).json()['meetings']
        self.assertEqual(meetings, [])


class TestTheStudentEmailIsTheCurrentOne(_Base):
    """7c review: the mentor reaches the student's CURRENT contact address, never the copy taken at
    submit; that copy is used only when the profile has none."""

    def test_contact_email_first_then_the_submit_copy(self):
        from apps.scholarship.models import ScholarshipApplication
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(notify_email='old@example.test')
        self.assertEqual(self.mentor().get(page(self.app.id)).json()['email'], 'aisyah@example.test')
        type(self.app.profile).objects.filter(pk=self.app.profile.pk).update(contact_email='')
        self.assertEqual(self.mentor().get(page(self.app.id)).json()['email'], 'old@example.test')


class TestTheMentorLogsAMeeting(_Base):
    def test_a_log_is_saved_as_the_mentors_logged_and_emails_nobody(self):
        r = self.log(next_step='Study group')
        self.assertEqual(r.status_code, 201, r.content)
        s = MentoringSession.objects.get()
        self.assertEqual((s.mentor_id, s.assignment.mentor_id, s.logged_by_mentor, s.logged_by_email, s.concern),
                         (self.kavitha.pk, self.kavitha.pk, True, self.login.email, False))
        [(event, meta, internal)] = self.events()[-1:]
        self.assertEqual((event, meta['by_mentor'], meta['mentor']), ('session_logged', True, 'Kavitha Raman'))
        self.assertEqual(mail.outbox, [])
        self.assertEqual(r.json()['meetings'][0]['notes'], 'Went through the timetable.')

    def test_the_same_validation_as_staff(self):
        today = timezone.localdate()
        cases = [
            (dict(met_on=(today + datetime.timedelta(days=1)).isoformat()), 'future_date'),
            (dict(met_on=(today - datetime.timedelta(days=1)).isoformat()), 'before_assignment'),
            (dict(met_on='31/10/2026'), 'bad_date'),
            (dict(mode='letter'), 'bad_mode'),
            (dict(minutes=0), 'bad_minutes'),
            (dict(minutes=1441), 'bad_minutes'),
            (dict(minutes=True), 'bad_minutes'),
            (dict(notes='  '), 'notes_required'),
            (dict(notes='x' * 5001), 'too_long'),
            (dict(next_step='x' * 501), 'too_long'),
        ]
        for body, code in cases:
            with self.subTest(code=code):
                r = self.log(**body)
                self.assertEqual((r.status_code, r.json()['code']), (400, code))
        self.assertEqual(self.log(minutes=1440).status_code, 201)
        self.assertEqual(self.log(minutes=None, next_step='').status_code, 201)
        self.assertEqual(MentoringSession.objects.count(), 2)

    def test_a_staff_end_racing_the_log_wins_and_nothing_is_written(self):
        real = mentoring._locked_open

        def ended_meanwhile(app):
            MentorAssignment.objects.filter(application=app, ended_at__isnull=True).update(ended_at=timezone.now())
            return real(app)
        with patch.object(mentoring, '_locked_open', ended_meanwhile):
            r = self.log()
        self.assertEqual(r.status_code, 404)
        self.assertEqual(MentoringSession.objects.count(), 0)

    def test_a_change_to_another_mentor_racing_the_log_is_refused(self):
        real = mentoring._locked_open

        def changed_meanwhile(app):
            MentorAssignment.objects.filter(application=app, ended_at__isnull=True).update(ended_at=timezone.now())
            MentorAssignment.objects.create(application=app, mentor=self.faizal)
            return real(app)
        with patch.object(mentoring, '_locked_open', changed_meanwhile):
            r = self.log()
        self.assertEqual(r.status_code, 404)
        self.assertEqual(MentoringSession.objects.count(), 0)

    def test_a_file_closed_under_the_lock_is_refused(self):
        real = mentoring._locked_open

        def closed_meanwhile(app):
            row, current = real(app)
            row.status = 'closed'
            return row, current
        with patch.object(mentoring, '_locked_open', closed_meanwhile):
            r = self.log()
        self.assertEqual((r.status_code, r.json()['code']), (409, 'file_closed'))
        self.assertEqual(MentoringSession.objects.count(), 0)

    def test_saved_meetings_cannot_be_edited(self):
        self.log()
        s = MentoringSession.objects.get()
        url = f'{page(self.app.id)}sessions/'
        for method in ('put', 'patch', 'delete'):
            with self.subTest(method=method):
                r = getattr(self.mentor(), method)(url, {'notes': 'changed'}, format='json')
                self.assertIn(r.status_code, (403, 405))
        s.refresh_from_db()
        self.assertEqual(s.notes, 'Went through the timetable.')

    def test_staff_see_the_mentors_meeting_logged_by_the_mentor(self):
        self.log(notes='MENTOR NOTE')
        tab = authed_client(self.org_admin).get(f'{SCHOLARS}{self.app.id}/mentoring/').json()
        [m] = tab['meetings']
        self.assertEqual((m['logged_by_mentor'], m['mentor_name'], m['notes'], m['logged_by']['name']),
                         (True, 'Kavitha Raman', 'MENTOR NOTE', 'Kavitha Raman'))
        self.assertEqual(tab['current']['meetings'], 1)

    def test_the_students_own_tab_is_unchanged_date_and_how_only(self):
        self.log(notes='MENTOR NOTE', next_step='MENTOR STEP', mode='phone')
        body = authed_client(self.app.profile.supabase_user_id).get('/api/v1/scholarship/bursary/mentoring/').json()
        self.assertEqual(body['meetings'], [{'met_on': timezone.localdate().isoformat(), 'mode': 'phone'}])
        text = json.dumps(body)
        for needle in ('MENTOR NOTE', 'MENTOR STEP', 'concern', 'by_mentor', 'minutes'):
            self.assertNotIn(needle, text)


class TestTheConcern(_Base):
    def tab(self, who=None):
        return authed_client(who or self.org_admin).get(f'{SCHOLARS}{self.app.id}/mentoring/').json()

    def handle(self, who=None, app=None):
        return authed_client(who or self.org_admin).post(
            f'{SCHOLARS}{(app or self.app).id}/mentoring/handle-concern/', {}, format='json')

    def scholars(self, who=None, **q):
        return authed_client(who or self.org_admin).get(SCHOLARS, q).json()

    def test_only_true_raises_it_and_it_logs_a_staff_only_line(self):
        self.log(concern='true')
        self.log(concern=1)
        self.assertFalse(MentoringSession.objects.filter(concern=True).exists())
        self.assertIsNone(self.tab()['concern'])
        self.log(concern=True)
        self.assertEqual(MentoringSession.objects.filter(concern=True).count(), 1)
        event, meta, internal = self.events()[-1]
        self.assertEqual((event, meta['mentor'], internal), ('mentor_concern_raised', 'Kavitha Raman', True))
        self.assertEqual(mail.outbox, [])
        tab = self.tab()
        self.assertEqual(tab['concern']['count'], 1)
        self.assertTrue(tab['meetings'][0]['concern'])
        self.assertIsNone(tab['meetings'][0]['concern_handled_at'])
        mine = self.mentor().get(page(self.app.id)).json()['meetings'][0]
        self.assertTrue(mine['concern'])

    def test_staff_cannot_raise_one(self):
        self.staff_meet(concern=True)
        self.assertFalse(MentoringSession.objects.filter(concern=True).exists())

    def test_the_scholars_chip_filter_and_count_agree(self):
        calm = _scholar(cohort=self.app.cohort)
        mentoring.assign(self.org_admin, calm, self.kavitha, email_student=False)
        self.log(app=calm)
        self.log(concern=True)
        self.log(concern=True)              # two concerns, one student
        body = self.scholars()
        self.assertEqual(body['summary']['mentor_concerned'], 1)
        rows = {r['id']: r for r in body['results']}
        self.assertEqual((rows[self.app.id]['mentor_concerned'], rows[calm.id]['mentor_concerned']), (True, False))
        filtered = self.scholars(mentoring='mentor_concerned')
        self.assertEqual([r['id'] for r in filtered['results']], [self.app.id])
        self.assertEqual(filtered['count'], body['summary']['mentor_concerned'])

    def test_mark_as_handled_clears_every_open_one_once_and_a_later_concern_raises_it_again(self):
        self.log(concern=True)
        self.log(concern=True)
        r = self.handle()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()['concern'])
        for s in MentoringSession.objects.filter(concern=True):
            self.assertIsNotNone(s.concern_handled_at)
            self.assertEqual(s.concern_handled_by_email, self.org_admin.email)
        handled = [e for e in self.events() if e[0] == 'mentor_concern_handled']
        self.assertEqual([(m['count'], internal) for _e, m, internal in handled], [(2, True)])
        self.assertEqual(r.json()['meetings'][0]['concern_handled_by']['email'], self.org_admin.email)
        # Twice: idempotent — 200, nothing written.
        self.assertEqual(self.handle().status_code, 200)
        self.assertEqual(len([e for e in self.events() if e[0] == 'mentor_concern_handled']), 1)
        self.assertEqual(self.scholars()['summary']['mentor_concerned'], 0)
        # A later concern raises it again.
        self.log(concern=True)
        self.assertEqual(self.tab()['concern']['count'], 1)
        self.assertEqual(self.scholars()['summary']['mentor_concerned'], 1)

    def test_only_the_organisations_staff_actors_may_handle_it(self):
        self.log(concern=True)
        reviewer = make_admin('reviewer', owning_org=self.org)
        self.app.assigned_to = reviewer
        self.app.save(update_fields=['assigned_to'])
        for who in (reviewer, make_admin('qc', owning_org=self.org), make_admin('finance', owning_org=self.org)):
            with self.subTest(role=who.role):
                self.assertEqual(self.handle(who).status_code, 403)
        self.assertIn(self.handle(self.login).status_code, (401, 403))       # the mentor
        stranger = make_admin('org_admin', owning_org=_scholar().owning_organisation)
        self.assertEqual(self.handle(stranger).status_code, 404)
        self.assertEqual(MentoringSession.objects.filter(concern_handled_at__isnull=False).count(), 0)
        self.assertEqual(self.handle(make_admin('admin', owning_org=self.org)).status_code, 200)

    def test_reviewer_and_qc_see_no_concern_line_chip_or_count(self):
        self.log(concern=True)
        self.handle()
        # Sprint S1: only `scholars` opens the file; these two hold it beside their hat.
        reviewer = make_admin('reviewer', owning_org=self.org, permissions=['review', 'see_all', 'scholars'])
        self.app.assigned_to = reviewer
        self.app.save(update_fields=['assigned_to'])
        for who in (reviewer, make_admin('qc', owning_org=self.org, permissions=['see_all', 'qc', 'scholars'])):
            with self.subTest(role=who.role):
                log = authed_client(who).get(f'{SCHOLARS}{self.app.id}/activity/').json()
                events = {r['event'] for r in log['results']}
                self.assertFalse(events & {'mentor_concern_raised', 'mentor_concern_handled', 'session_logged'})
                body = self.scholars(who, mentoring='mentor_concerned')
                self.assertNotIn('mentor_concerned', body['summary'])
                self.assertTrue(all('mentor_concerned' not in r for r in body['results']))
                self.assertEqual(authed_client(who).get(f'{SCHOLARS}{self.app.id}/mentoring/').status_code, 403)

    def test_a_closed_file_refuses_mark_as_handled(self):
        self.log(concern=True)
        closure.close_application(self.app, closure_reason='graduated', by_email=self.org_admin.email)
        r = self.handle()
        self.assertEqual((r.status_code, r.json()['code']), (409, 'file_closed'))
        # 7c review: a concern that can no longer be handled shows no chip on the Closed list.
        closed = self.scholars(closed='1')
        rows = {r['id']: r for r in closed['results']}
        self.assertIs(rows[self.app.id]['mentor_concerned'], False)
        self.assertEqual(self.scholars(mentoring='mentor_concerned')['results'], [])


class TestTheMentorMethodsAreTheListedOnes(TestCase):
    """Every view a mentor may call — the 7a / 7b own-account doors and the three 7c doors, nothing else."""

    EXPECTED = {
        'AdminRoleView': ('get',), 'AdminSetPasswordView': ('post',),
        'AdminMeView': ('get', 'patch'), 'AdminMePhotoView': ('post', 'delete'),
        'AdminMeActivityView': ('get',), 'AdminMePasswordView': ('post',),
        'ReviewerProfileView': ('get', 'patch'),
        # S7c — the mentor's own students.
        'AdminMentorStudentsView': ('get',), 'AdminMentorStudentView': ('get',),
        'AdminMentorStudentSessionsView': ('post',),
        # S10 review 1 — the student's uploaded module task, signed on the tap.
        'AdminMentorStudentModuleFileView': ('get',),
        # Team tables T5c P5 — the Programmes landing: the gifts of the mentor's own current students.
        'AdminMyProgrammesView': ('get',),
        # Team tables T5c P5b S1 — the Overview's pending cards: the mentor's own mentee counts.
        'AdminMyPendingView': ('get',),
        # Sprint S1 (S1-h) — the Scholars READS, for the mentor's own current students only (the writes none).
        **dict.fromkeys(('AdminScholarListView', 'AdminScholarFileView', 'AdminScholarResultsView',
                         'AdminScholarMoneyView', 'AdminScholarContractView', 'AdminScholarActivityView',
                         'AdminScholarLettersView', 'AdminScholarLetterPdfView', 'AdminScholarSurveysView',
                         'AdminScholarGrowthView', 'AdminScholarMentoringView'), ('get',)),
    }

    def test_the_closed_list(self):
        found = {}

        def walk(patterns):
            for p in patterns:
                if hasattr(p, 'url_patterns'):
                    walk(p.url_patterns)
                    continue
                cls = getattr(p.callback, 'view_class', None)
                methods = tuple(getattr(cls, 'mentor_methods', ()) or ())
                if cls is not None and methods:
                    found[cls.__name__] = methods
        walk(get_resolver('halatuju.urls').url_patterns)
        self.assertEqual(found, self.EXPECTED)

    def test_the_desk_reads_through_one_door(self):
        self.assertIs(mentor_desk.mentoring.clean_meeting, mentoring.clean_meeting)
