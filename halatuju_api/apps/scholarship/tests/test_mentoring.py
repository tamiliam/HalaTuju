"""Student maintenance S7b (2026-11-01): mentoring — every door into and out of "has a mentor", every
refusal, the meetings, and every reader (staff tab, the student's tab, the Scholars list, the Mentors page,
and the sponsor / partner payloads that must never carry any of it).

Doors, each driven through the real endpoints (or the real service another door calls):

- INTO "has a mentor": assign; change (the old one ends, the new one starts — never two open); a racing
  second open row (the partial unique index, and the service's `conflict`).
- OUT of it: end; change; the mentor deactivated (and revoked); the file closed.
- REFUSED: another organisation's mentor; a deactivated mentor; the student themselves (UID, alias UID,
  contact email, notify email); a file not in maintenance (read-only); a caller role outside
  super / org_admin / admin; another organisation's application (404).
- MEETINGS: no open assignment; a future date; before the assignment started; another organisation.
- READERS: the student's payload is an allowlist; sponsor and partner payloads carry nothing; the email
  respects the switch and goes to the student only; the Scholars filters count correctly.
"""
import datetime
import json
import pathlib
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models_claim import ProfileLoginAlias
from apps.scholarship import closure, mentoring, student_email_catalogue
from apps.scholarship.models import (
    MentorAssignment, MentoringSession, ReviewerProfile, StudentActivity, StudentEmailLog,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_student,
)

SCHOLARS = '/api/v1/admin/scholarship/scholars/'
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


def tab(app_id):
    return f'{SCHOLARS}{app_id}/mentoring/'


def make_mentor(org, name='Kavitha Raman', email=None, *, phone='012-345 6789', share=True, area='Accounting',
                **login):
    """A mentor with a login and a profile (the mentor's own details)."""
    a = make_admin('mentor', owning_org=org, name=name, **({'email': email} if email else {}), **login)
    a.mentor.area = area
    a.mentor.save(update_fields=['area'])
    ReviewerProfile.objects.create(partner_admin=a, phone=phone, share_phone_with_students=share,
                                   english_fluency='fluent', bm_fluency='conversational', tamil_fluency='basic',
                                   other_language='Mandarin', other_language_fluency='fluent',
                                   about='Chartered accountant.')
    return a.mentor


def _scholar(**over):
    return make_application('maintenance', active_at=timezone.now() - datetime.timedelta(days=60), **over)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@LOCMEM
class _Base(TestCase):
    def setUp(self):
        self.app = _scholar(student=make_student(name='NUR AISYAH', contact_email='aisyah@example.test'),
                            help_university='yes')
        self.org = self.app.owning_organisation
        self.org_admin = make_admin('org_admin', owning_org=self.org)
        self.officer = make_admin('admin', owning_org=self.org)
        self.kavitha = make_mentor(self.org)
        self.faizal = make_mentor(self.org, 'Faizal Hamid', phone='019-000 0000', share=False, area='Engineering')

    def assign(self, mentor, caller=None, **body):
        body.setdefault('mentor_id', mentor.pk if mentor is not None else 999999)
        return authed_client(caller or self.org_admin).post(tab(self.app.id) + 'assign/', body, format='json')

    def end(self, caller=None, **body):
        return authed_client(caller or self.org_admin).post(tab(self.app.id) + 'end/', body, format='json')

    def meet(self, caller=None, app=None, **body):
        body.setdefault('met_on', timezone.localdate().isoformat())
        body.setdefault('mode', 'video')
        body.setdefault('minutes', 45)
        body.setdefault('notes', 'Talked about the timetable.')
        return authed_client(caller or self.org_admin).post(tab((app or self.app).id) + 'sessions/', body,
                                                             format='json')

    def open_rows(self, app=None):
        return list(MentorAssignment.objects.filter(application=app or self.app, ended_at__isnull=True))

    def events(self, app=None):
        return list(StudentActivity.objects.filter(application=app or self.app, kind='system')
                    .exclude(event='').order_by('id').values_list('event', 'meta'))


class TestIntoHasAMentor(_Base):
    def test_assign_starts_one_assignment_logs_it_and_emails_the_student_only(self):
        r = self.assign(self.kavitha)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body['emailed'])
        cur = body['current']
        self.assertEqual((cur['name'], cur['area'], cur['languages'], cur['other_language'], cur['phone'],
                          cur['meetings'], cur['emailed'], cur['assigned_by']['email']),
                         ('Kavitha Raman', 'Accounting', ['en', 'ms'], 'Mandarin', '012-345 6789', 0, True,
                          self.org_admin.email))
        [row] = self.open_rows()
        self.assertEqual((row.mentor_id, row.started_by_email, row.emailed_student),
                         (self.kavitha.pk, self.org_admin.email, True))
        self.assertEqual([e for e, _ in self.events()], ['mentor_assigned'])
        # The STUDENT only — never the mentor (the system emails a mentor only their invitation).
        self.assertEqual([m.to for m in mail.outbox], [[self.app.notify_email]])
        letter = mail.outbox[0]
        self.assertIn('Kavitha Raman', letter.subject)
        for part in ('Accounting', 'English, Malay, Mandarin', '012-345 6789'):
            self.assertIn(part, letter.body)
        self.assertEqual(StudentEmailLog.objects.filter(key='mentor_assigned', ok=True).count(), 1)

    def test_an_invited_mentor_may_be_assigned(self):
        invited = make_mentor(self.org, 'Priya Devi')
        from apps.courses.models import PartnerAdmin
        PartnerAdmin.objects.filter(mentor=invited).update(first_seen_at=None)
        self.assertEqual(self.assign(invited).status_code, 200)

    def test_change_ends_the_old_one_with_its_reason_and_starts_the_new(self):
        self.assign(self.kavitha)
        r = self.assign(self.faizal, reason='Changed course')
        self.assertEqual(r.status_code, 200, r.content)
        rows = list(MentorAssignment.objects.filter(application=self.app).order_by('id'))
        self.assertEqual(len(rows), 2)
        self.assertIsNotNone(rows[0].ended_at)
        self.assertEqual((rows[0].end_reason, rows[0].ended_by_email), ('Changed course', self.org_admin.email))
        self.assertIsNone(rows[1].ended_at)
        self.assertEqual(len(self.open_rows()), 1)
        body = r.json()
        self.assertEqual(body['current']['name'], 'Faizal Hamid')
        self.assertEqual([(h['name'], h['end_reason']) for h in body['history']], [('Kavitha Raman', 'Changed course')])
        ev = self.events()
        self.assertEqual([e for e, _ in ev], ['mentor_assigned', 'mentor_changed'])
        self.assertEqual((ev[1][1]['mentor'], ev[1][1]['was']), ('Faizal Hamid', 'Kavitha Raman'))
        # The phone line: only when the mentor shares it. Faizal does not.
        self.assertNotIn('019-000 0000', mail.outbox[-1].body)

    def test_the_same_mentor_again_is_refused(self):
        self.assign(self.kavitha)
        r = self.assign(self.kavitha)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'already_assigned'))

    def test_the_database_holds_one_open_row_per_application(self):
        MentorAssignment.objects.create(application=self.app, mentor=self.kavitha)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MentorAssignment.objects.create(application=self.app, mentor=self.faizal)

    def test_a_racing_assign_that_loses_is_refused_and_leaves_nothing(self):
        """Two requests both read "no open row" before either wrote: the second write hits the partial
        unique index and the service answers `conflict` (409) with nothing of its own kept."""
        MentorAssignment.objects.create(application=self.app, mentor=self.kavitha)
        real = mentoring._locked_open

        def stale(app):
            row, _current = real(app)
            return row, None          # what the loser read before the winner committed
        with patch.object(mentoring, '_locked_open', stale):
            r = self.assign(self.faizal)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'conflict'))
        self.assertEqual([a.mentor_id for a in self.open_rows()], [self.kavitha.pk])
        self.assertEqual(self.events(), [])
        self.assertEqual(mail.outbox, [])


class TestOutOfHasAMentor(_Base):
    def test_end_closes_it_with_the_reason_and_emails_nobody(self):
        self.assign(self.kavitha, email_student=False)
        r = self.end(reason='Asked to stop')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.open_rows(), [])
        row = MentorAssignment.objects.get(application=self.app)
        self.assertEqual(row.end_reason, 'Asked to stop')
        self.assertEqual(self.events()[-1][1]['cause'], 'staff')
        self.assertEqual(mail.outbox, [])
        self.assertIsNone(r.json()['current'])

    def test_end_with_no_mentor_is_refused(self):
        r = self.end()
        self.assertEqual((r.status_code, r.json()['code']), (409, 'no_mentor'))

    @override_settings(SUPABASE_SERVICE_ROLE_KEY='svc', SUPABASE_URL='https://x.supabase.co')
    def test_deactivating_the_mentor_ends_every_open_assignment_and_reactivating_restores_none(self):
        other = _scholar(cohort=self.app.cohort)
        self.assign(self.kavitha, email_student=False)
        mentoring.assign(self.org_admin, other, self.kavitha, email_student=False)
        mail.outbox.clear()
        with patch('apps.courses.supabase_admin.kill_temp_password', return_value='killed'):
            r = authed_client(self.org_admin).post(f'/api/v1/admin/mentors/{self.kavitha.pk}/deactivate/', {},
                                                   format='json')
        self.assertEqual(r.status_code, 200, r.content)
        for app in (self.app, other):
            self.assertEqual(self.open_rows(app), [])
            row = MentorAssignment.objects.get(application=app)
            self.assertEqual(row.end_reason, mentoring.REASON_DEACTIVATED)
            self.assertEqual(self.events(app)[-1][1]['cause'], 'mentor_deactivated')
        self.assertEqual(mail.outbox, [])
        with patch('apps.courses.supabase_admin.issue_temp_password', return_value=True), \
                patch('apps.courses.supabase_admin.read_auth_user',
                      return_value={'id': 'x', 'last_sign_in_at': None, 'app_metadata': {}}):
            authed_client(self.org_admin).post(f'/api/v1/admin/mentors/{self.kavitha.pk}/reactivate/', {},
                                               format='json')
        self.assertEqual(self.open_rows(), [])

    @override_settings(SUPABASE_SERVICE_ROLE_KEY='svc', SUPABASE_URL='https://x.supabase.co')
    def test_revoking_an_invited_mentor_ends_their_assignment_too(self):
        from apps.courses.models import PartnerAdmin
        PartnerAdmin.objects.filter(mentor=self.kavitha).update(first_seen_at=None, supabase_user_id=None)
        self.assign(self.kavitha, email_student=False)
        with patch('apps.courses.supabase_admin.kill_temp_password', return_value='killed'):
            r = authed_client(self.org_admin).post(f'/api/v1/admin/mentors/{self.kavitha.pk}/revoke/', {},
                                                   format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.open_rows(), [])

    def test_closing_the_file_ends_it(self):
        self.assign(self.kavitha, email_student=False)
        mail.outbox.clear()
        closure.close_application(self.app, closure_reason='graduated', by_email=self.org_admin.email)
        row = MentorAssignment.objects.get(application=self.app)
        self.assertEqual((row.end_reason, row.ended_by_email), (mentoring.REASON_CLOSED, self.org_admin.email))
        self.assertEqual(self.events()[-1][1]['cause'], 'file_closed')
        self.assertEqual(mail.outbox, [])


class TestRefusals(_Base):
    def test_another_organisations_mentor(self):
        stranger = make_mentor(_scholar().owning_organisation, 'Stranger')
        r = self.assign(stranger)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'mentor_not_found'))
        self.assertEqual(self.assign(None).json()['code'], 'mentor_not_found')

    def test_a_deactivated_mentor(self):
        type(self.kavitha).objects.filter(pk=self.kavitha.pk).update(deactivated_at=timezone.now())
        r = self.assign(self.kavitha)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'mentor_inactive'))

    def test_the_student_themselves_by_uid_alias_and_email(self):
        profile = self.app.profile
        cases = {
            'uid': dict(uid=profile.supabase_user_id),
            'contact email': dict(email='AISYAH@example.test'),
            'notify email': dict(email=self.app.notify_email.upper()),
        }
        for label, login in cases.items():
            with self.subTest(label):
                me = make_mentor(self.org, f'Self {label}', **login)
                r = self.assign(me)
                self.assertEqual((r.status_code, r.json()['code']), (400, 'own_application'))
                ids = [m['id'] for m in authed_client(self.org_admin).get(tab(self.app.id)).json()['assignable']]
                self.assertNotIn(me.pk, ids)
                self.assertIn(self.kavitha.pk, ids)
        alias = make_mentor(self.org, 'Self alias')
        ProfileLoginAlias.objects.create(alias_uid=mentoring._login(alias).supabase_user_id, profile=profile)
        r = self.assign(alias)
        self.assertEqual(r.json()['code'], 'own_application')
        self.assertEqual(MentorAssignment.objects.count(), 0)

    def test_a_closed_file_reads_and_refuses_every_write(self):
        self.assign(self.kavitha, email_student=False)
        closure.close_application(self.app, closure_reason='graduated', by_email='x@example.test')
        body = authed_client(self.org_admin).get(tab(self.app.id)).json()
        self.assertEqual((body['can_act'], body['file_closed'], body['assignable']), (False, True, []))
        for r in (self.assign(self.faizal), self.end(), self.meet()):
            self.assertEqual((r.status_code, r.json()['code']), (409, 'file_closed'))

    def test_not_in_maintenance_is_refused_by_the_service(self):
        pre = make_application('awarded')   # no wallet: not in maintenance, and no file
        with self.assertRaises(mentoring.MentoringError) as e:
            mentoring.assign(make_admin('super', super_admin=True), pre, make_mentor(pre.owning_organisation))
        self.assertEqual(e.exception.code, 'file_closed')

    def test_roles_outside_the_tab_are_refused_and_admin_may_act(self):
        reviewer = make_admin('reviewer', owning_org=self.org)
        self.app.assigned_to = reviewer
        self.app.save(update_fields=['assigned_to'])
        refused = [reviewer, make_admin('qc', owning_org=self.org), make_admin('finance', owning_org=self.org),
                   make_admin('source_partner', owning_org=self.org), make_admin('mentor', owning_org=self.org),
                   make_admin('partner', owning_org=self.org)]
        for who in refused:
            with self.subTest(role=who.role):
                self.assertEqual(authed_client(who).get(tab(self.app.id)).status_code, 403)
                self.assertEqual(self.assign(self.kavitha, caller=who).status_code, 403)
                self.assertEqual(self.meet(caller=who).status_code, 403)
        self.assertEqual(MentorAssignment.objects.count(), 0)
        self.assertEqual(self.assign(self.kavitha, caller=self.officer).status_code, 200)
        self.assertTrue(authed_client(self.officer).get(tab(self.app.id)).json()['can_act'])
        sup = make_admin('super', super_admin=True)
        self.assertEqual(self.meet(caller=sup).status_code, 201)

    def test_another_organisations_application_is_404(self):
        stranger = make_admin('org_admin', owning_org=_scholar().owning_organisation)
        self.assertEqual(authed_client(stranger).get(tab(self.app.id)).status_code, 404)
        self.assertEqual(self.assign(self.kavitha, caller=stranger).status_code, 404)
        self.assertEqual(self.end(caller=stranger).status_code, 404)
        self.assertEqual(self.meet(caller=stranger).status_code, 404)

    def test_a_reason_too_long_and_a_bad_mentor_id(self):
        self.assertEqual(self.assign(self.kavitha, reason='x' * 501).json()['code'], 'too_long')
        self.assertEqual(self.assign(self.kavitha, mentor_id='abc').json()['code'], 'bad_request')
        r = authed_client(self.org_admin).post(tab(self.app.id) + 'nonsense/', {}, format='json')
        self.assertEqual(r.status_code, 404)


class TestMeetings(_Base):
    def test_a_meeting_needs_an_open_assignment(self):
        r = self.meet()
        self.assertEqual((r.status_code, r.json()['code']), (409, 'no_mentor'))

    def test_a_meeting_is_logged_with_the_current_mentor(self):
        self.assign(self.kavitha, email_student=False)
        r = self.meet(next_step='Two firm contacts')
        self.assertEqual(r.status_code, 201, r.content)
        s = MentoringSession.objects.get()
        self.assertEqual((s.mentor_id, s.mode, s.minutes, s.next_step, s.logged_by_email),
                         (self.kavitha.pk, 'video', 45, 'Two firm contacts', self.org_admin.email))
        self.assertEqual(s.assignment.ended_at, None)
        body = r.json()
        self.assertEqual(body['current']['meetings'], 1)
        self.assertEqual(body['meetings'][0]['notes'], 'Talked about the timetable.')
        self.assertEqual(self.events()[-1][0], 'session_logged')

    def test_future_dates_dates_before_the_start_and_bad_values_are_refused(self):
        self.assign(self.kavitha, email_student=False)
        today = timezone.localdate()
        cases = [
            (dict(met_on=(today + datetime.timedelta(days=1)).isoformat()), 'future_date'),
            (dict(met_on=(today - datetime.timedelta(days=1)).isoformat()), 'before_assignment'),
            (dict(met_on='31/10/2026'), 'bad_date'),
            (dict(mode='letter'), 'bad_mode'),
            (dict(minutes=0), 'bad_minutes'),
            (dict(minutes='abc'), 'bad_minutes'),
            (dict(notes='  '), 'notes_required'),
            (dict(notes='x' * 5001), 'too_long'),
        ]
        for body, code in cases:
            with self.subTest(code=code):
                r = self.meet(**body)
                self.assertEqual((r.status_code, r.json()['code']), (400, code))
        self.assertEqual(MentoringSession.objects.count(), 0)

    def test_minutes_are_optional(self):
        self.assign(self.kavitha, email_student=False)
        self.assertEqual(self.meet(minutes=None).status_code, 201)
        self.assertIsNone(MentoringSession.objects.get().minutes)

    def test_another_organisations_file(self):
        self.assign(self.kavitha, email_student=False)
        stranger = make_admin('org_admin', owning_org=_scholar().owning_organisation)
        self.assertEqual(self.meet(caller=stranger).status_code, 404)


class TestTheEmail(_Base):
    def test_the_organisations_switch_off_sends_nothing_and_the_form_hides_the_option(self):
        student_email_catalogue.set_switch(self.org, 'mentor_assigned', False)
        self.assertFalse(authed_client(self.org_admin).get(tab(self.app.id)).json()['email_switch_on'])
        r = self.assign(self.kavitha)
        self.assertEqual((r.status_code, r.json()['emailed']), (200, False))
        self.assertEqual(mail.outbox, [])
        self.assertFalse(MentorAssignment.objects.get().emailed_student)

    def test_staff_may_leave_it_unsent(self):
        r = self.assign(self.kavitha, email_student=False)
        self.assertEqual((r.status_code, r.json()['emailed']), (200, False))
        self.assertEqual(mail.outbox, [])

    def test_may_send_is_asked_at_the_send_site(self):
        with patch('apps.scholarship.student_email_catalogue.may_send', return_value=False) as asked:
            self.assign(self.kavitha)
        self.assertTrue(any(c.args[1] == 'mentor_assigned' for c in asked.call_args_list))
        self.assertEqual(mail.outbox, [])

    def test_it_is_in_the_catalogue_switchable_under_mentoring_with_three_languages(self):
        entry = student_email_catalogue.BY_KEY['mentor_assigned']
        self.assertEqual((entry.group, entry.switchable, entry.editable, entry.languages),
                         ('mentoring', True, True, 'en_ms_ta'))
        from apps.scholarship import email_templates, student_comms
        for lang in ('en', 'ms', 'ta'):
            subject, body = student_comms.DEFAULTS['mentor_assigned'][lang]
            self.assertEqual(email_templates.unknown_placeholders(
                student_comms.PLACEHOLDERS['mentor_assigned'], subject, body), ())


class TestTheStudentsTab(_Base):
    def _student(self):
        return authed_client(self.app.profile.supabase_user_id)

    def test_the_payload_is_an_allowlist(self):
        self.assign(self.faizal, email_student=False)
        self.assign(self.kavitha, reason='STAFF ONLY REASON', email_student=False)
        self.meet(notes='SECRET NOTE', next_step='SECRET STEP', mode='phone')
        r = self._student().get('/api/v1/scholarship/bursary/mentoring/')
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertEqual(set(body), {'mentor', 'meetings'})
        self.assertEqual(set(body['mentor']), {'name', 'area', 'languages', 'other_language', 'about', 'email',
                                               'phone', 'since'})
        self.assertEqual((body['mentor']['name'], body['mentor']['phone'], body['mentor']['about']),
                         ('Kavitha Raman', '012-345 6789', 'Chartered accountant.'))
        self.assertEqual(body['meetings'], [{'met_on': timezone.localdate().isoformat(), 'mode': 'phone'}])
        text = json.dumps(body)
        for secret in ('SECRET NOTE', 'SECRET STEP', 'STAFF ONLY REASON', 'Faizal', 'minutes', 'photo',
                       self.org_admin.email):
            self.assertNotIn(secret, text)

    def test_a_hidden_phone_is_never_served(self):
        self.assign(self.faizal, email_student=False)
        body = self._student().get('/api/v1/scholarship/bursary/mentoring/').json()
        self.assertEqual(body['mentor']['phone'], '')
        self.assertNotIn('019-000 0000', json.dumps(body))

    def test_no_mentor_and_the_tab_rule(self):
        student = self._student()
        self.assertEqual(student.get('/api/v1/scholarship/bursary/mentoring/').json(), {'mentor': None, 'meetings': []})
        self.assertTrue(student.get('/api/v1/scholarship/bursary/summary/').json()['mentoring_tab'])
        type(self.kavitha).objects.filter(organisation=self.org).update(deactivated_at=timezone.now())
        self.assertFalse(student.get('/api/v1/scholarship/bursary/summary/').json()['mentoring_tab'])
        MentorAssignment.objects.create(application=self.app, mentor=self.kavitha, ended_at=timezone.now())
        self.assertTrue(student.get('/api/v1/scholarship/bursary/summary/').json()['mentoring_tab'])

    def test_another_student_has_no_file(self):
        r = authed_client(make_student().supabase_user_id).get('/api/v1/scholarship/bursary/mentoring/')
        self.assertEqual(r.status_code, 404)


class TestTheListsAndPages(_Base):
    def test_the_scholars_column_and_filters_count_correctly(self):
        helped = _scholar(cohort=self.app.cohort, help_scholarship='unsure')
        flagged = _scholar(cohort=self.app.cohort, mentoring_candidate=True)
        plain = _scholar(cohort=self.app.cohort, help_university='no')
        self.assign(self.kavitha, email_student=False)
        get = lambda **q: authed_client(self.org_admin).get(SCHOLARS, q).json()   # noqa: E731
        everyone = get()
        self.assertEqual((everyone['summary']['no_mentor'], everyone['summary']['asked_for_help']), (3, 3))
        rows = {r['id']: r for r in everyone['results']}
        self.assertEqual((rows[self.app.id]['mentor'], rows[self.app.id]['asked_for_help']), ('Kavitha Raman', True))
        self.assertEqual((rows[plain.id]['mentor'], rows[plain.id]['asked_for_help']), (None, False))
        self.assertEqual({r['id'] for r in get(mentoring='no_mentor')['results']}, {helped.id, flagged.id, plain.id})
        self.assertEqual({r['id'] for r in get(mentoring='asked_for_help')['results']},
                         {self.app.id, helped.id, flagged.id})

    def test_a_role_without_the_tab_sees_no_mentor_on_the_list_or_the_file(self):
        self.assign(self.kavitha, email_student=False)
        qc = make_admin('qc', owning_org=self.org)
        body = authed_client(qc).get(SCHOLARS, {'mentoring': 'no_mentor'}).json()
        self.assertNotIn('no_mentor', body['summary'])
        self.assertTrue(all('mentor' not in r for r in body['results']))
        self.assertIn(self.app.id, [r['id'] for r in body['results']])    # the filter is ignored, not obeyed
        self.assertNotIn('Kavitha', json.dumps(body))
        file_ = authed_client(qc).get(f'{SCHOLARS}{self.app.id}/').json()
        self.assertNotIn('mentor', file_)
        self.assertEqual(authed_client(self.org_admin).get(f'{SCHOLARS}{self.app.id}/').json()['mentor']['name'],
                         'Kavitha Raman')

    def test_the_mentors_page_counts_scholars_now(self):
        self.assign(self.kavitha, email_student=False)
        mentoring.assign(self.org_admin, _scholar(cohort=self.app.cohort), self.kavitha, email_student=False)
        rows = {r['id']: r for r in authed_client(self.org_admin).get('/api/v1/admin/mentors/').json()['mentors']}
        self.assertEqual((rows[self.kavitha.pk]['scholars_now'], rows[self.faizal.pk]['scholars_now']), (2, 0))
        self.end()
        rows = {r['id']: r for r in authed_client(self.org_admin).get('/api/v1/admin/mentors/').json()['mentors']}
        self.assertEqual(rows[self.kavitha.pk]['scholars_now'], 1)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, SPONSOR_POOL_ENABLED=True)
@LOCMEM
class TestNeverASponsorOrPartnerReader(_Base):
    """Mentors and meetings never reach a sponsor or a referral partner (owner ruling, 7a and 7b)."""

    def test_the_sponsors_own_student_and_the_partners_student_carry_nothing(self):
        from apps.courses.serializers_admin import PartnerStudentDetailSerializer
        from apps.scholarship.models import Sponsor, Sponsorship
        self.assign(self.kavitha, email_student=False)
        self.meet(notes='SECRET NOTE')
        sponsor = Sponsor.objects.create(supabase_user_id='spon-mine', email='s@example.test', name='S',
                                         phone='0123', source='friend', consent_at=timezone.now(), status='approved')
        Sponsorship.objects.create(sponsor=sponsor, application=self.app, amount=Decimal('2000'), status='active')
        r = authed_client('spon-mine').get(f'/api/v1/sponsor/my-students/{self.app.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        partner = json.dumps(PartnerStudentDetailSerializer(self.app.profile).data, default=str)
        for text in (json.dumps(r.json()), partner):
            for needle in ('Kavitha', 'mentor', 'SECRET NOTE', 'kavitha', 'mentoring'):
                self.assertNotIn(needle, text)

    def test_no_sponsor_partner_or_source_module_reads_mentoring(self):
        root = pathlib.Path(mentoring.__file__).parent
        for rel in ('views_sponsor.py', 'spend_sponsor.py', 'sponsor_feed.py', 'sponsor_notify.py',
                    'sponsor_comms.py', 'partner_comms.py', 'partner_notify.py', 'source_console.py',
                    'views_admin/source_console.py', 'views_admin/sponsors.py', 'views_admin/sources.py',
                    'pool.py'):
            path = root / rel
            if not path.exists():
                continue
            with self.subTest(module=rel):
                text = path.read_text(encoding='utf-8')
                for needle in ('MentorAssignment', 'MentoringSession', 'mentor_assignments', 'mentoring_sessions',
                               'import mentoring', 'from .mentoring', 'from ..mentoring'):
                    self.assertNotIn(needle, text)


# ── Adversarial review of 7b (2026-11-01) ─────────────────────────────────────────────────────────
def _verified_client(sub, email):
    """A client whose token carries a VERIFIED email — what `get_admin` links a row with no UID to."""
    import jwt
    from rest_framework.test import APIClient
    token = jwt.encode({'sub': sub, 'aud': 'authenticated', 'role': 'authenticated', 'email': email,
                        'email_verified': True}, TEST_JWT_SECRET, algorithm='HS256')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


SUPABASE = dict(SUPABASE_SERVICE_ROLE_KEY='svc-key', SUPABASE_URL='https://x.supabase.co')


class TestReviewFix1TheMentorTurnsOutToBeTheStudent(_Base):
    """The student's own SIGN-IN email is not stored, so a mentor invited at it passes the assign-time
    check with no UID. Every later door that makes it true ends the assignment; every reader guards."""

    def _invited_at(self, email):
        from apps.courses.models import PartnerAdmin
        mentor = make_mentor(self.org, 'Self Login', email=email)
        PartnerAdmin.objects.filter(mentor=mentor).update(supabase_user_id=None, first_seen_at=None)
        return mentor

    def test_signing_in_at_the_students_own_address_ends_the_assignment(self):
        mentor = self._invited_at('aisyah.signin@example.test')
        self.assertEqual(self.assign(mentor, email_student=False).status_code, 200)   # nothing matched yet
        mail.outbox.clear()
        _verified_client(self.app.profile.supabase_user_id, 'aisyah.signin@example.test').get('/api/v1/admin/role/')
        login = mentoring._login(mentor)
        self.assertEqual(login.supabase_user_id, self.app.profile.supabase_user_id)   # get_admin linked it
        self.assertEqual(self.open_rows(), [])
        row = MentorAssignment.objects.get(application=self.app)
        self.assertEqual(row.end_reason, mentoring.REASON_IS_STUDENT)
        self.assertEqual(self.events()[-1][1]['cause'], 'mentor_is_student')
        self.assertEqual(mail.outbox, [])

    def test_a_link_for_another_scholars_mentor_ends_nothing(self):
        mentor = self._invited_at('kavitha.other@example.test')
        self.assign(mentor, email_student=False)
        _verified_client('some-other-uid', 'kavitha.other@example.test').get('/api/v1/admin/role/')
        self.assertEqual([a.mentor_id for a in self.open_rows()], [mentor.pk])

    @override_settings(**SUPABASE)
    def test_moving_an_assigned_invited_mentor_onto_the_students_address_ends_it(self):
        with patch('apps.courses.staff_reinvite._new_login', return_value=('uid-new', False, None)):
            r = authed_client(self.org_admin).post('/api/v1/admin/invitations/', {
                'audience': 'mentor', 'name': 'Priya Devi', 'email': 'priya@example.org'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        mentor_id = r.json()['mentor']['id']
        from apps.scholarship.models import Mentor
        self.assertEqual(self.assign(Mentor.objects.get(pk=mentor_id), email_student=False).status_code, 200)
        account = {'id': 'uid-new', 'email': 'priya@example.org', 'last_sign_in_at': None,
                   'app_metadata': {'providers': ['email']}, 'identities': []}
        with patch('apps.courses.supabase_admin.read_auth_user', return_value=account), \
                patch('apps.courses.supabase_admin.delete_auth_user', return_value='deleted'), \
                patch('apps.courses.staff_reinvite._new_login', return_value=(None, True, None)), \
                patch('apps.scholarship.staff_lifecycle.login_used_elsewhere', return_value=False):
            r = authed_client(self.org_admin).patch(f'/api/v1/admin/mentors/{mentor_id}/',
                                                    {'email': self.app.notify_email}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.open_rows(), [])
        self.assertEqual(MentorAssignment.objects.get(application=self.app).end_reason, mentoring.REASON_IS_STUDENT)

    def test_a_later_alias_claim_hides_the_mentor_from_every_reader_and_writes_nothing(self):
        self.assign(self.kavitha, email_student=False)
        ProfileLoginAlias.objects.create(alias_uid=mentoring._login(self.kavitha).supabase_user_id,
                                         profile=self.app.profile)
        before = self.events()
        body = authed_client(self.app.profile.supabase_user_id).get('/api/v1/scholarship/bursary/mentoring/').json()
        self.assertEqual(body, {'mentor': None, 'meetings': []})
        cur = authed_client(self.org_admin).get(tab(self.app.id)).json()['current']
        self.assertTrue(cur['is_the_student'])
        self.assertEqual(len(self.open_rows()), 1)          # a read never writes
        self.assertEqual(self.events(), before)
        row = self.open_rows()[0]
        self.assertFalse(mentoring._send_you_have_a_mentor(self.app, row, self.kavitha))
        self.assertEqual(mail.outbox, [])

    def test_an_ordinary_current_mentor_is_not_flagged(self):
        self.assign(self.kavitha, email_student=False)
        self.assertFalse(authed_client(self.org_admin).get(tab(self.app.id)).json()['current']['is_the_student'])


class TestReviewFix2TheTimelineKeepsMentorsFromOtherRoles(_Base):
    def test_reviewer_and_qc_get_no_mentoring_lines_and_org_admin_does(self):
        self.assign(self.kavitha, email_student=False)
        self.meet()
        self.assign(self.faizal, email_student=False)
        self.end()
        reviewer = make_admin('reviewer', owning_org=self.org)
        self.app.assigned_to = reviewer
        self.app.save(update_fields=['assigned_to'])
        url = f'{SCHOLARS}{self.app.id}/activity/'
        for who in (reviewer, make_admin('qc', owning_org=self.org)):
            with self.subTest(role=who.role):
                body = authed_client(who).get(url).json()
                self.assertEqual([r['event'] for r in body['results'] if r['event'] in mentoring.EVENTS], [])
                self.assertEqual(body['count'], len(body['results']))
                self.assertNotIn('Kavitha', json.dumps(body))
        own = authed_client(self.org_admin).get(url).json()
        self.assertEqual(sorted({r['event'] for r in own['results']} & set(mentoring.EVENTS)),
                         sorted(mentoring.EVENTS))


class TestReviewFix3AssignRacesDeactivate(_Base):
    def test_a_mentor_deactivated_after_the_check_is_refused_inside_the_transaction(self):
        from apps.scholarship.models import Mentor
        real = mentoring._locked_open

        def deactivated_meanwhile(app):
            Mentor.objects.filter(pk=self.kavitha.pk).update(deactivated_at=timezone.now())
            return real(app)
        with patch.object(mentoring, '_locked_open', deactivated_meanwhile):
            r = self.assign(self.kavitha)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'mentor_inactive'))
        self.assertEqual(MentorAssignment.objects.count(), 0)
        self.assertEqual(self.events(), [])
        self.assertEqual(mail.outbox, [])


class TestReviewFix4AnAwardRevertedToThePool(_Base):
    def test_the_revert_ends_the_assignment_with_no_email(self):
        from apps.scholarship.award_revert import revert_to_pool
        app = make_application('awarded', cohort=self.app.cohort, vircle_activated_at=timezone.now())
        mentoring.assign(self.org_admin, app, self.kavitha, email_student=False)
        mail.outbox.clear()
        with transaction.atomic():
            revert_to_pool(app)
        app.refresh_from_db()
        self.assertNotEqual(app.status, 'awarded')
        self.assertEqual(self.open_rows(app), [])
        row = MentorAssignment.objects.get(application=app)
        self.assertEqual(row.end_reason, mentoring.REASON_REVERTED)
        self.assertEqual(self.events(app)[-1][1]['cause'], 'award_reverted')
        self.assertEqual(mail.outbox, [])
