"""Student maintenance S9 (2026-11-02): surveys — every door into "a scholar sees / answers it", every staff
door, the results and CSV, and the hourly email.

Doors, each driven through the real endpoints (or the job's real command):

- WHO SEES ONE: published and opened only (never a draft or a scheduled one); open, or already answered (a
  closed survey / a closed file keeps a read-only sight of its own answers); the same organisation; the
  audience (everyone / her gift, by the application's gift OR its round's); never another organisation's
  scholar, a student who is not a scholar, a sponsor, a partner or a source.
- ANSWERING: only while open and in maintenance (closed -> 409, read-only view kept); a guessed id -> 404;
  each type validated (choice in options, rating 1-5, yes/no, lengths, required); a mentor-only question
  only with a mentor; changing replaces cleanly; one response row per survey x application.
- STAFF: super / org_admin / admin; every other role refused; another organisation is 404 on every door
  incl. the CSV; the questions lock at the first answer (closing date, title, intro still change); delete
  only while nobody answered; close now; results never show another organisation's responses.
- THE EMAIL: switch off -> nobody, recorded, never later; once per scholar per kind; two runs; the reminder
  skips those who answered; no address; closed / draft surveys send nothing; the button and the job never
  double.
- CSV: one row per response, one column per question; cells starting = + - @ are escaped.
"""
import datetime
import json
import pathlib
from decimal import Decimal
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import student_email_catalogue, survey_results, surveys
from apps.scholarship.models import (
    MentorAssignment, StudentEmailLog, Survey, SurveyAnswer, SurveyEmail, SurveyQuestion, SurveyResponse,
    UsageEvent,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme, make_student,
)

STAFF = '/api/v1/admin/scholarship/surveys/'
MINE = '/api/v1/scholarship/bursary/surveys/'
SUMMARY = '/api/v1/scholarship/bursary/summary/'
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
HOUR = datetime.timedelta(hours=1)
DAY = datetime.timedelta(days=1)

QUESTIONS = [
    {'kind': 'one', 'text': 'How are your studies going?', 'options': ['Very well', 'Well', 'OK', 'Struggling']},
    {'kind': 'many', 'text': 'What would help?', 'options': ['Study skills', 'Money advice', 'Career talks'],
     'required': False},
    {'kind': 'rating', 'text': 'How useful is your mentor?', 'hint': '1 = not useful, 5 = very useful',
     'mentor_only': True},
    {'kind': 'yes_no', 'text': 'Are you in a hostel?'},
    {'kind': 'short', 'text': 'How many subjects?', 'required': False},
    {'kind': 'long', 'text': 'Anything else?', 'required': False},
]


def _scholar(cohort=None, **over):
    return make_application('maintenance', cohort=cohort, active_at=timezone.now() - datetime.timedelta(days=90),
                            **over)


def _survey(org, title='Semester 1 check-in', questions=QUESTIONS, **kw):
    now = timezone.now()
    kw.setdefault('status', 'published')
    kw.setdefault('opens_at', now - HOUR)
    kw.setdefault('closes_at', now + 10 * DAY)
    s = Survey.objects.create(organisation=org, title=title, **kw)
    surveys._replace_questions(s, surveys.clean_questions(questions))
    return s


def _q(s, kind):
    return s.questions.get(kind=kind)


def _answers(s, **over):
    out = {str(_q(s, 'one').id): 'Well', str(_q(s, 'yes_no').id): True}
    out.update(over)
    return out


def _run_job():
    out = StringIO()
    call_command('send_survey_emails', stdout=out)
    return out.getvalue()


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@LOCMEM
class _Base(TestCase):
    def setUp(self):
        self.gift_a = make_programme(name_en='Flagship 2026')
        self.org = self.gift_a.organisation
        self.gift_b = make_programme(organisation=self.org, name_en='Sabah Bursary')
        self.student = make_student(name='NUR AISYAH')
        self.app = _scholar(make_cohort(programme=self.gift_a), student=self.student)
        self.other = _scholar(make_cohort(programme=self.gift_b))
        self.org_admin = make_admin('org_admin', owning_org=self.org)
        self.officer = make_admin('admin', owning_org=self.org)

    def mine(self, student=None):
        return authed_client((student or self.student).supabase_user_id).get(MINE)

    def ids(self, student=None):
        r = self.mine(student)
        self.assertEqual(r.status_code, 200, r.content)
        return [s['id'] for s in r.json()['surveys']]

    def answer(self, s, answers, student=None):
        return authed_client((student or self.student).supabase_user_id).post(
            f'{MINE}{s.id}/answers/', {'answers': answers}, format='json')

    def create(self, caller=None, **body):
        body.setdefault('title', 'Check-in')
        body.setdefault('closes_at', (timezone.now() + 5 * DAY).isoformat())
        body.setdefault('questions', QUESTIONS)
        body.setdefault('action', 'publish')
        return authed_client(caller or self.org_admin).post(STAFF, body, format='json')


class TestWhoSeesIt(_Base):
    def test_only_an_opened_published_one_of_her_organisation_and_audience(self):
        now = timezone.now()
        everyone = _survey(self.org, 'Everyone')
        mine = _survey(self.org, 'Mine', programme=self.gift_a)
        theirs = _survey(self.org, 'Their gift', programme=self.gift_b)
        _survey(self.org, 'Draft', status='draft')
        _survey(self.org, 'Later', opens_at=now + HOUR, closes_at=now + DAY)
        _survey(self.org, 'Closed, unanswered', opens_at=now - 3 * DAY, closes_at=now - DAY)
        _survey(_scholar().owning_organisation, 'Elsewhere')
        self.assertEqual(set(self.ids()), {everyone.id, mine.id})
        self.assertEqual(set(self.ids(self.other.profile)), {everyone.id, theirs.id})

    def test_the_gift_reaches_through_the_round(self):
        mine = _survey(self.org, 'Mine', programme=self.gift_a)
        type(self.app).objects.filter(pk=self.app.pk).update(programme=self.gift_b)
        self.assertIn(mine.id, self.ids())

    def test_a_closed_survey_she_answered_stays_read_only(self):
        s = _survey(self.org)
        self.assertEqual(self.answer(s, _answers(s)).status_code, 200)
        Survey.objects.filter(pk=s.pk).update(closes_at=timezone.now() - HOUR)
        item = next(x for x in self.mine().json()['surveys'] if x['id'] == s.id)
        self.assertEqual((item['status'], item['can_answer']), ('closed', False))
        self.assertEqual(item['answers'][str(_q(s, 'one').id)], 'Well')
        r = self.answer(s, _answers(s))
        self.assertEqual((r.status_code, r.json()['code']), (409, 'survey_closed'))

    def test_a_closed_file_keeps_only_what_it_answered_and_cannot_answer(self):
        answered, fresh = _survey(self.org, 'Answered'), _survey(self.org, 'Fresh')
        self.answer(answered, _answers(answered))
        type(self.app).objects.filter(pk=self.app.pk).update(status='closed', closed_at=timezone.now())
        self.assertEqual(self.ids(), [answered.id])
        item = self.mine().json()['surveys'][0]
        self.assertFalse(item['can_answer'])
        self.assertEqual(self.answer(answered, _answers(answered)).json()['code'], 'survey_closed')
        self.assertEqual(self.answer(fresh, _answers(fresh)).status_code, 404)

    def test_a_student_who_is_not_a_scholar_has_none(self):
        _survey(self.org)
        applicant = make_application('submitted', cohort=make_cohort(programme=self.gift_a))
        self.assertEqual(self.mine(applicant.profile).status_code, 404)

    def test_the_payload_is_an_allowlist(self):
        _survey(self.org, created_by_email='siti@example.test', email_on_open=True)
        body = self.mine().json()
        item = body['surveys'][0]
        self.assertEqual(set(item), {'id', 'title', 'intro', 'status', 'opens_at', 'closes_at', 'can_answer',
                                     'answered_at', 'updated_at', 'questions', 'answers'})
        self.assertEqual(set(item['questions'][0]), {'id', 'kind', 'text', 'hint', 'required', 'options'})
        self.assertNotIn('siti@example.test', json.dumps(body))

    def test_the_mentor_question_only_with_a_mentor(self):
        s = _survey(self.org)
        kinds = [q['kind'] for q in self.mine().json()['surveys'][0]['questions']]
        self.assertNotIn('rating', kinds)
        rating = str(_q(s, 'rating').id)
        self.assertEqual(self.answer(s, _answers(s, **{rating: 4})).json()['code'], 'bad_question')
        mentor = make_admin('mentor', owning_org=self.org).mentor
        MentorAssignment.objects.create(application=self.app, mentor=mentor)
        kinds = [q['kind'] for q in self.mine().json()['surveys'][0]['questions']]
        self.assertIn('rating', kinds)
        r = self.answer(s, _answers(s))
        self.assertEqual((r.status_code, r.json()['code'], r.json()['detail']), (400, 'required', int(rating)))
        self.assertEqual(self.answer(s, _answers(s, **{rating: 4})).status_code, 200)


class TestHerAnswers(_Base):
    def test_summary_tab_and_count(self):
        client = authed_client(self.student.supabase_user_id)
        self.assertEqual((client.get(SUMMARY).json()['surveys_tab'], client.get(SUMMARY).json()['surveys_to_answer']),
                         (False, 0))
        a, b = _survey(self.org, 'A'), _survey(self.org, 'B')
        body = client.get(SUMMARY).json()
        self.assertEqual((body['surveys_tab'], body['surveys_to_answer']), (True, 2))
        r = self.answer(a, _answers(a))
        self.assertEqual(r.json()['to_answer'], 1)
        self.assertEqual(client.get(SUMMARY).json()['surveys_to_answer'], 1)
        self.assertTrue(r.json()['survey']['answered_at'])
        del b

    def test_each_type_is_validated(self):
        s = _survey(self.org)
        one, many, yn = str(_q(s, 'one').id), str(_q(s, 'many').id), str(_q(s, 'yes_no').id)
        short, long_ = str(_q(s, 'short').id), str(_q(s, 'long').id)
        cases = {
            'bad_answer': [{one: 'Brilliant'}, {one: 3}, {many: ['Study skills', 'Nope']}, {many: 'Study skills'},
                           {many: ['Study skills', 'Study skills']}, {yn: 'yes'}],
            'answer_too_long': [{short: 'x' * 301}, {long_: 'x' * 3001}],
            'bad_question': [{'999999': 'x'}],
        }
        for code, bodies in cases.items():
            for over in bodies:
                with self.subTest(code=code, over=over):
                    r = self.answer(s, _answers(s, **over))
                    self.assertEqual((r.status_code, r.json()['code']), (400, code))
        r = self.answer(s, {yn: True})
        self.assertEqual((r.json()['code'], r.json()['detail']), ('required', int(one)))
        self.assertEqual(self.answer(s, 'all').json()['code'], 'bad_answers')
        self.assertFalse(SurveyResponse.objects.exists())

    def test_rating_is_one_to_five(self):
        s = _survey(self.org, questions=[{'kind': 'rating', 'text': 'Rate'}])
        q = str(s.questions.get().id)
        for bad in (0, 6, True, '4', 4.5):
            with self.subTest(bad=bad):
                self.assertEqual(self.answer(s, {q: bad}).json()['code'], 'bad_answer')
        self.assertEqual(self.answer(s, {q: 5}).status_code, 200)

    def test_changing_replaces_cleanly_one_row(self):
        s = _survey(self.org)
        many, long_ = str(_q(s, 'many').id), str(_q(s, 'long').id)
        self.assertEqual(self.answer(s, _answers(s, **{many: ['Career talks', 'Study skills'], long_: 'Hi'})).status_code, 200)
        resp = SurveyResponse.objects.get()
        self.assertEqual(SurveyAnswer.objects.get(response=resp, question_id=int(many)).value,
                         ['Study skills', 'Career talks'])   # the options' own order
        self.assertEqual(self.answer(s, _answers(s, **{str(_q(s, 'one').id): 'OK'})).status_code, 200)
        self.assertEqual(SurveyResponse.objects.count(), 1)
        values = dict(SurveyAnswer.objects.values_list('question__kind', 'value'))
        self.assertEqual(values, {'one': 'OK', 'yes_no': True})   # the optional ones dropped are gone

    def test_another_organisations_or_a_guessed_id_is_404(self):
        foreign = _survey(_scholar().owning_organisation)
        theirs = _survey(self.org, programme=self.gift_b)
        draft = _survey(self.org, status='draft')
        later = _survey(self.org, opens_at=timezone.now() + HOUR)
        for s in (foreign, theirs, draft, later):
            with self.subTest(s=s.title):
                self.assertEqual(self.answer(s, {}).status_code, 404)
        r = authed_client(self.student.supabase_user_id).post(f'{MINE}999999/answers/', {'answers': {}}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertFalse(SurveyResponse.objects.exists())

    def test_a_race_of_two_submits_leaves_one_row(self):
        s = _survey(self.org)
        surveys.submit(self.app, s.id, _answers(s))
        surveys.submit(self.app, s.id, _answers(s, **{str(_q(s, 'one').id): 'OK'}))
        self.assertEqual(SurveyResponse.objects.filter(survey=s, application=self.app).count(), 1)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            SurveyResponse.objects.create(survey=s, application=self.app)


class TestStaffDoors(_Base):
    def test_org_admin_admin_and_super_make_everyone_else_is_refused(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create(self.officer).status_code, 201)
        sup = make_admin('super', super_admin=True, owning_org=self.org)
        self.assertEqual(self.create(sup).status_code, 201)
        s = Survey.objects.first()
        for who in (make_admin('reviewer', owning_org=self.org), make_admin('qc', owning_org=self.org),
                    make_admin('finance', owning_org=self.org), make_admin('source_partner', owning_org=self.org),
                    make_admin('mentor', owning_org=self.org), make_admin('partner', owning_org=self.org)):
            with self.subTest(role=who.role):
                c = authed_client(who)
                self.assertEqual(c.get(STAFF).status_code, 403)
                self.assertEqual(self.create(who).status_code, 403)
                self.assertEqual(c.get(f'{STAFF}{s.id}/results/').status_code, 403)
                self.assertEqual(c.get(f'{STAFF}{s.id}/csv/').status_code, 403)
                self.assertIn(c.get(f'/api/v1/admin/scholarship/scholars/{self.app.id}/surveys/').status_code,
                              (403, 404))
        self.assertEqual(Survey.objects.count(), 3)

    def test_another_organisation_is_404_everywhere_and_sees_nothing(self):
        s = _survey(self.org)
        self.answer(s, _answers(s))
        stranger = make_admin('org_admin', owning_org=_scholar().owning_organisation)
        c = authed_client(stranger)
        for method, url in (('patch', f'{STAFF}{s.id}/'), ('delete', f'{STAFF}{s.id}/'),
                            ('get', f'{STAFF}{s.id}/results/'), ('get', f'{STAFF}{s.id}/csv/'),
                            ('post', f'{STAFF}{s.id}/close/'), ('post', f'{STAFF}{s.id}/remind/'),
                            ('get', f'/api/v1/admin/scholarship/scholars/{self.app.id}/surveys/')):
            with self.subTest(url=url, method=method):
                self.assertEqual(getattr(c, method)(url, {'title': 'X'}, format='json').status_code, 404)
        self.assertEqual(c.get(STAFF, {'programme': self.gift_a.code}).status_code, 404)
        self.assertEqual(self.create(stranger, programme=self.gift_a.code).json()['code'], 'bad_audience')
        self.assertEqual(c.get(STAFF).json()['surveys'], [])

    def test_a_super_without_an_organisation_names_a_gift(self):
        sup = make_admin('super', super_admin=True)
        self.assertEqual(authed_client(sup).get(STAFF).json()['code'], 'programme_required')
        self.assertEqual(authed_client(sup).get(STAFF, {'programme': self.gift_a.code}).json()['organisation']['code'],
                         self.org.code)

    def test_validation(self):
        past = (timezone.now() - HOUR).isoformat()
        q = QUESTIONS[0]
        cases = {
            'title_required': {'title': ' '}, 'title_too_long': {'title': 'x' * 151}, 'title_newline': {'title': 'a\nb'},
            'intro_too_long': {'intro': 'x' * 1001}, 'bad_audience': {'programme': 'nope'},
            'bad_action': {'action': 'shout'}, 'bad_closes_at': {'closes_at': 'soon'},
            'closes_at_past': {'closes_at': past},
            'closes_before_opens': {'opens_at': (timezone.now() + 9 * DAY).isoformat()},
            'no_questions': {'questions': []}, 'too_many_questions': {'questions': [q] * 31},
            'bad_question_kind': {'questions': [{'kind': 'essay', 'text': 'x'}]},
            'question_required': {'questions': [{'kind': 'short', 'text': ''}]},
            'question_too_long': {'questions': [{'kind': 'short', 'text': 'x' * 301}]},
            'options_count': {'questions': [{'kind': 'one', 'text': 'x', 'options': ['a']}]},
            'option_duplicate': {'questions': [{'kind': 'many', 'text': 'x', 'options': ['a', 'a']}]},
            'option_too_long': {'questions': [{'kind': 'one', 'text': 'x', 'options': ['a', 'b' * 121]}]},
            'bad_options': {'questions': [{'kind': 'one', 'text': 'x'}]},
        }
        for code, body in cases.items():
            with self.subTest(code=code):
                r = self.create(**body)
                self.assertEqual((r.status_code, r.json()['code']), (400, code))
        self.assertEqual(self.create(questions=[{'kind': 'one', 'text': 'x', 'options': ['a'] * 13}]).json()['code'],
                         'options_count')
        self.assertEqual(Survey.objects.count(), 0)

    def test_statuses_from_the_dates_and_close_now(self):
        later = self.create(opens_at=(timezone.now() + DAY).isoformat()).json()
        self.assertEqual(later['status'], 'scheduled')
        draft = self.create(action='draft').json()
        self.assertEqual(draft['status'], 'draft')
        open_ = self.create().json()
        self.assertEqual(open_['status'], 'open')
        c = authed_client(self.org_admin)
        self.assertEqual(c.post(f'{STAFF}{later["id"]}/close/').json()['code'], 'not_open')
        self.assertEqual(c.post(f'{STAFF}{open_["id"]}/close/').json()['status'], 'closed')
        self.assertNotIn(open_['id'], self.ids())
        r = c.patch(f'{STAFF}{draft["id"]}/', {'action': 'publish'}, format='json')
        self.assertEqual(r.json()['status'], 'open')
        body = c.get(STAFF).json()
        self.assertEqual(body['counts'], {'open': 1, 'scheduled': 1, 'draft': 0, 'closed': 1})

    def test_questions_lock_at_the_first_answer(self):
        s = self.create().json()
        c = authed_client(self.org_admin)
        changed = QUESTIONS[:2]
        self.assertEqual(c.patch(f'{STAFF}{s["id"]}/', {'questions': changed}, format='json').status_code, 200)
        survey = Survey.objects.get(pk=s['id'])
        self.answer(survey, {str(survey.questions.get(kind='one').id): 'OK'})
        for body, code in (({'questions': QUESTIONS}, 'questions_locked'),
                           ({'programme': self.gift_a.code}, 'answered_locked'),
                           ({'opens_at': (timezone.now() + HOUR).isoformat()}, 'answered_locked'),
                           ({'action': 'draft'}, 'answered_locked')):
            with self.subTest(body=body):
                r = c.patch(f'{STAFF}{s["id"]}/', body, format='json')
                self.assertEqual((r.status_code, r.json()['code']), (409, code))
        # The same questions sent back are not a change; the closing date, title and intro still move.
        new_close = (timezone.now() + 20 * DAY).isoformat()
        r = c.patch(f'{STAFF}{s["id"]}/', {'questions': changed, 'title': 'Renamed', 'intro': 'Hello',
                                            'closes_at': new_close}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()['title'], r.json()['intro'], r.json()['locked']), ('Renamed', 'Hello', True))
        self.assertEqual(SurveyQuestion.objects.filter(survey_id=s['id']).count(), 2)

    def test_delete_only_while_nobody_answered(self):
        c = authed_client(self.org_admin)
        draft = self.create(action='draft').json()
        unanswered = self.create().json()
        answered = self.create().json()
        survey = Survey.objects.get(pk=answered['id'])
        self.answer(survey, _answers(survey))
        self.assertEqual(c.delete(f'{STAFF}{draft["id"]}/').status_code, 204)
        self.assertEqual(c.delete(f'{STAFF}{unanswered["id"]}/').status_code, 204)
        r = c.delete(f'{STAFF}{answered["id"]}/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'close_instead'))
        self.assertTrue(Survey.objects.filter(pk=answered['id']).exists())

    def test_results_summary_each_and_not_answered(self):
        s = _survey(self.org)
        third = _scholar(make_cohort(programme=self.gift_a))
        self.answer(s, _answers(s, **{str(_q(s, 'many').id): ['Money advice'], str(_q(s, 'long').id): 'Bus is late'}))
        self.answer(s, _answers(s, **{str(_q(s, 'one').id): 'Struggling'}), student=self.other.profile)
        foreign_org_app = _scholar()
        foreign = _survey(foreign_org_app.owning_organisation)
        self.answer(foreign, _answers(foreign), student=foreign_org_app.profile)
        body = authed_client(self.org_admin).get(f'{STAFF}{s.id}/results/').json()
        self.assertEqual(body['survey']['answered_count'], 2)
        one = next(x for x in body['summary'] if x['question_id'] == _q(s, 'one').id)
        counts = {o['option']: o['count'] for o in one['options']}
        self.assertEqual(counts, {'Very well': 0, 'Well': 1, 'OK': 0, 'Struggling': 1})
        struggling = next(o for o in one['options'] if o['option'] == 'Struggling')
        self.assertEqual(struggling['who'], [{'application_id': self.other.id, 'name': self.other.profile.name}])
        yn = next(x for x in body['summary'] if x['question_id'] == _q(s, 'yes_no').id)
        self.assertEqual([(o['option'], o['count']) for o in yn['options']], [(True, 2), (False, 0)])
        long_ = next(x for x in body['summary'] if x['question_id'] == _q(s, 'long').id)
        self.assertEqual(long_['written'], [{'application_id': self.app.id, 'name': 'NUR AISYAH', 'text': 'Bus is late'}])
        self.assertEqual(sorted(r['application_id'] for r in body['responses']), sorted([self.app.id, self.other.id]))
        self.assertEqual([p['application_id'] for p in body['not_answered']], [third.id])
        self.assertTrue(body['can_remind'])
        self.assertNotIn(foreign_org_app.id, [r['application_id'] for r in body['responses']])

    def test_the_scholar_file_tab(self):
        s = _survey(self.org)
        waiting = _survey(self.org, 'Waiting')
        self.answer(s, _answers(s))
        body = authed_client(self.officer).get(f'/api/v1/admin/scholarship/scholars/{self.app.id}/surveys/').json()
        self.assertEqual([a['id'] for a in body['answered']], [s.id])
        self.assertEqual({a['text']: a['value'] for a in body['answered'][0]['answers']},
                         {'How are your studies going?': 'Well', 'Are you in a hostel?': True})
        self.assertEqual([w['id'] for w in body['waiting']], [waiting.id])
        reviewer = make_admin('reviewer', owning_org=self.org)
        r = authed_client(reviewer).get(f'/api/v1/admin/scholarship/scholars/{self.app.id}/surveys/')
        self.assertIn(r.status_code, (403, 404))


class TestCsv(_Base):
    def test_one_row_per_response_and_injection_escaped(self):
        s = _survey(self.org, questions=[{'kind': 'short', 'text': '=Total?'},
                                         {'kind': 'many', 'text': 'Pick', 'options': ['a', 'b'], 'required': False}])
        short = str(s.questions.get(kind='short').id)
        many = str(s.questions.get(kind='many').id)
        self.answer(s, {short: '=HYPERLINK("http://x")', many: ['a', 'b']})
        self.answer(s, {short: '@SUM(1)'}, student=self.other.profile)
        type(self.student).objects.filter(pk=self.student.pk).update(name='+60123')
        r = authed_client(self.org_admin).get(f'{STAFF}{s.id}/csv/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        lines = r.content.decode('utf-8').strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn('1. =Total?', lines[0])
        text = r.content.decode('utf-8')
        self.assertIn("'=HYPERLINK", text)
        self.assertIn("'@SUM(1)", text)
        self.assertIn("'+60123", text)
        self.assertIn('a; b', text)
        self.assertEqual(survey_results._cell('-1'), "'-1")
        self.assertEqual(survey_results._cell('ok'), 'ok')


class TestTheEmail(_Base):
    def setUp(self):
        super().setUp()
        self.third = _scholar(make_cohort(programme=self.gift_a))

    def test_open_once_per_scholar_metered_and_logged_even_when_run_twice(self):
        s = _survey(self.org, email_on_open=True)
        _run_job()
        _run_job()
        self.assertEqual(sorted(m.to[0] for m in mail.outbox),
                         sorted([self.app.notify_email, self.other.notify_email, self.third.notify_email]))
        letter = next(m for m in mail.outbox if m.to == [self.app.notify_email])
        self.assertIn('Semester 1 check-in', letter.subject)
        self.assertIn('A new survey is open', letter.body)
        self.assertIn('/scholarship/bursary?tab=surveys', letter.body)
        self.assertEqual(SurveyEmail.objects.filter(survey=s, kind='open', outcome='sent').count(), 3)
        self.assertEqual(UsageEvent.objects.filter(source='send_student_email').count(), 3)
        self.assertEqual(StudentEmailLog.objects.filter(key='survey_open', ok=True).count(), 3)
        s.refresh_from_db()
        self.assertIsNotNone(s.opened_emailed_at)

    def test_only_its_audience_never_closed_files_or_another_organisation(self):
        _survey(self.org, email_on_open=True, programme=self.gift_a)
        make_application('closed', cohort=make_cohort(programme=self.gift_a),
                         active_at=timezone.now() - datetime.timedelta(days=200))
        _scholar()
        _run_job()
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([self.app.notify_email, self.third.notify_email]))

    def test_draft_scheduled_closed_or_not_asked_send_nothing(self):
        now = timezone.now()
        _survey(self.org)
        _survey(self.org, 'Draft', status='draft', email_on_open=True, remind_before_close=True)
        _survey(self.org, 'Later', opens_at=now + HOUR, email_on_open=True)
        closed = _survey(self.org, 'Closed', opens_at=now - 3 * DAY, closes_at=now - HOUR, email_on_open=True,
                         remind_before_close=True)
        _run_job()
        self.assertEqual(mail.outbox, [])
        closed.refresh_from_db()
        self.assertIsNotNone(closed.opened_emailed_at)   # done with, never sent later

    def test_the_reminder_skips_those_who_answered_and_waits_for_the_window(self):
        s = _survey(self.org, remind_before_close=True)   # closes in 10 days: not yet
        _run_job()
        self.assertEqual(mail.outbox, [])
        Survey.objects.filter(pk=s.pk).update(closes_at=timezone.now() + 2 * DAY)
        self.answer(s, _answers(s))
        _run_job()
        _run_job()
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([self.other.notify_email, self.third.notify_email]))
        self.assertIn('you have not answered this survey yet', mail.outbox[0].body)
        self.assertFalse(SurveyEmail.objects.filter(application=self.app).exists())

    def test_the_button_and_the_job_never_double(self):
        s = _survey(self.org, remind_before_close=True, closes_at=timezone.now() + 2 * DAY)
        c = authed_client(self.org_admin)
        r = c.post(f'{STAFF}{s.id}/remind/')
        self.assertEqual((r.status_code, r.json()['sent']), (200, 3))
        self.assertFalse(r.json()['can_remind'])
        self.assertEqual(c.post(f'{STAFF}{s.id}/remind/').json()['sent'], 0)
        _run_job()
        self.assertEqual(len(mail.outbox), 3)
        Survey.objects.filter(pk=s.pk).update(closes_at=timezone.now() - HOUR)
        self.assertEqual(c.post(f'{STAFF}{s.id}/remind/').json()['code'], 'not_open')

    def test_switched_off_nobody_is_emailed_and_never_later(self):
        s = _survey(self.org, email_on_open=True)
        student_email_catalogue.set_switch(self.org, 'survey_open', False)
        _run_job()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(SurveyEmail.objects.filter(survey=s, outcome='switched_off').count(), 3)
        student_email_catalogue.set_switch(self.org, 'survey_open', True)
        _run_job()
        self.assertEqual(mail.outbox, [])
        self.assertTrue(authed_client(self.org_admin).get(STAFF).json()['email_switch_on'])

    def test_a_scholar_without_an_address_is_recorded_and_the_rest_go(self):
        type(self.app).objects.filter(pk=self.app.pk).update(notify_email='')
        s = _survey(self.org, email_on_open=True)
        _run_job()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(SurveyEmail.objects.get(survey=s, application=self.app).outcome, 'no_address')

    def test_closed_mid_run_stops_the_rest(self):
        s = _survey(self.org, email_on_open=True)
        from unittest.mock import patch
        real = __import__('apps.scholarship.student_comms', fromlist=['x']).send_student_email

        def send_then_close(app, kind, **values):
            ok = real(app, kind, **values)
            Survey.objects.filter(pk=s.pk).update(closes_at=timezone.now() - HOUR)
            return ok
        with patch('apps.scholarship.student_comms.send_student_email', side_effect=send_then_close):
            _run_job()
        self.assertEqual(len(mail.outbox), 1)

    def test_the_job_is_registered_and_watched(self):
        from apps.scholarship.cron_health import EXPECTED_CADENCE, HOURLY
        from apps.scholarship.views import CronRunView
        self.assertEqual(CronRunView.JOBS['survey-emails'], 'send_survey_emails')
        self.assertEqual(EXPECTED_CADENCE['survey-emails'], HOURLY)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, SPONSOR_POOL_ENABLED=True)
class TestNeverASponsorPartnerOrSourceReader(_Base):
    def test_the_sponsors_own_student_and_the_partners_student_carry_nothing(self):
        from apps.courses.serializers_admin import PartnerStudentDetailSerializer
        from apps.scholarship.models import Sponsor, Sponsorship
        s = _survey(self.org, 'SECRET SURVEY TITLE')
        self.answer(s, _answers(s, **{str(_q(s, 'long').id): 'SECRET ANSWER'}))
        sponsor = Sponsor.objects.create(supabase_user_id='spon-mine', email='s@example.test', name='S',
                                         phone='0123', source='friend', consent_at=timezone.now(), status='approved')
        Sponsorship.objects.create(sponsor=sponsor, application=self.app, amount=Decimal('2000'), status='active')
        r = authed_client('spon-mine').get(f'/api/v1/sponsor/my-students/{self.app.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        partner = json.dumps(PartnerStudentDetailSerializer(self.app.profile).data, default=str)
        for text in (json.dumps(r.json()), partner):
            for needle in ('SECRET', 'survey'):
                self.assertNotIn(needle, text)

    def test_no_sponsor_partner_or_source_module_reads_surveys(self):
        root = pathlib.Path(surveys.__file__).parent
        for rel in ('views_sponsor.py', 'spend_sponsor.py', 'sponsor_feed.py', 'sponsor_notify.py',
                    'sponsor_comms.py', 'partner_comms.py', 'partner_notify.py', 'source_console.py',
                    'views_admin/source_console.py', 'views_admin/sponsors.py', 'views_admin/sources.py',
                    'pool.py'):
            path = root / rel
            if not path.exists():
                continue
            with self.subTest(module=rel):
                text = path.read_text(encoding='utf-8')
                for needle in ('SurveyResponse', 'SurveyAnswer', 'import surveys', 'from .surveys', 'from ..surveys',
                               'survey_results', 'survey_emails'):
                    self.assertNotIn(needle, text)
