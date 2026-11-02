"""Student maintenance S10 (2026-11-02): development modules — every door into "a scholar sees / does it", every
staff door, Progress and its CSV, the files, the mentor's sight and the hourly email.

Doors, each driven through the real endpoints (or the job's real command):

- WHO SEES ONE: published and live only (never a draft, a scheduled or an archived one she never started); the
  same organisation; the audience (everyone / her gift, by the application's gift OR its round's); a scholar
  who started keeps a read-only sight once it is archived or her file closes; never another organisation's
  scholar, a student who is not a scholar.
- HER WORK: "I have read this" is idempotent; a lesson of another module, a module of another organisation or a
  guessed id is 404; the task after every lesson (409), changeable until reviewed (409 after); a module with no
  task refuses one; the upload is typed by its BYTES, capped, and must sit under HER own path; a file link only
  to her own upload or a lesson of a module she can see.
- STAFF: super / org_admin / admin; every other role refused; another organisation is 404 on every door incl.
  the CSV, a lesson file, a scholar's upload, the review and the scholar file's tab; the task type locks at the
  first start; lessons may be added / removed after a start; delete only while nobody started; archive.
- MENTOR: the current mentor sees the student's modules on My students; an ended assignment loses sight.
- THE EMAIL: switch off -> nobody, recorded (job) / 409 and nothing written (button); once per scholar per kind;
  the reminder skips those done; no address; archived / draft send nothing; no reminder without a due date.
"""
import datetime
import json
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import development, development_files, development_progress, student_email_catalogue
from apps.scholarship.models import (
    DevelopmentModule, LessonRead, MentorAssignment, ModuleEmail, ModuleLesson, ModuleProgress, StudentEmailLog,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme, make_student,
)

STAFF = '/api/v1/admin/scholarship/development/'
MINE = '/api/v1/scholarship/bursary/growth/'
SUMMARY = '/api/v1/scholarship/bursary/summary/'
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
HOUR = datetime.timedelta(hours=1)
DAY = datetime.timedelta(days=1)
PDF = b'%PDF-1.4 a real enough pdf'
PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 40
STORAGE = 'apps.scholarship.storage.'

LESSONS = [
    {'title': 'Where does the money go?', 'body': 'Write it down.\n\nSee https://example.test/budget'},
    {'title': 'A simple monthly budget', 'body': 'Rent first.', 'video_url': 'https://youtu.be/abc123'},
]


def _scholar(cohort=None, **over):
    return make_application('maintenance', cohort=cohort, active_at=timezone.now() - datetime.timedelta(days=90),
                            **over)


def _module(org, title='Managing your money', lessons=LESSONS, **kw):
    kw.setdefault('status', 'published')
    kw.setdefault('publish_at', timezone.now() - HOUR)
    kw.setdefault('task_kind', 'reflection')
    kw.setdefault('task_prompt', 'Make your own budget. What will you change?')
    m = DevelopmentModule.objects.create(organisation=org, title=title, **kw)
    development._apply_lessons(m, development.clean_lessons(lessons))
    return m


def _run_job():
    out = StringIO()
    call_command('send_module_emails', stdout=out)
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

    def me(self, student=None):
        return authed_client((student or self.student).supabase_user_id)

    def ids(self, student=None):
        r = self.me(student).get(MINE)
        self.assertEqual(r.status_code, 200, r.content)
        return [m['id'] for m in r.json()['modules']]

    def read_all(self, m, student=None):
        for lesson in m.lessons.all():
            r = self.me(student).post(f'{MINE}{m.id}/lessons/{lesson.id}/read/')
            self.assertEqual(r.status_code, 200, r.content)
        return r

    def reflect(self, m, text='I will cook three days a week.', student=None):
        return self.me(student).post(f'{MINE}{m.id}/task/', {'text': text}, format='json')

    def create(self, caller=None, **body):
        body.setdefault('title', 'Writing your first CV')
        body.setdefault('lessons', LESSONS)
        body.setdefault('task_kind', 'reflection')
        body.setdefault('task_prompt', 'What did you learn?')
        body.setdefault('action', 'publish')
        return authed_client(caller or self.org_admin).post(STAFF, body, format='json')


class TestWhoSeesIt(_Base):
    def test_only_a_live_published_one_of_her_organisation_and_audience(self):
        everyone = _module(self.org, 'Everyone')
        mine = _module(self.org, 'Mine', programme=self.gift_a)
        theirs = _module(self.org, 'Their gift', programme=self.gift_b)
        _module(self.org, 'Draft', status='draft')
        _module(self.org, 'Later', publish_at=timezone.now() + HOUR)
        _module(self.org, 'Archived', status='archived', archived_at=timezone.now())
        _module(_scholar().owning_organisation, 'Elsewhere')
        self.assertEqual(set(self.ids()), {everyone.id, mine.id})
        self.assertEqual(set(self.ids(self.other.profile)), {everyone.id, theirs.id})

    def test_the_gift_reaches_through_the_round(self):
        mine = _module(self.org, 'Mine', programme=self.gift_a)
        type(self.app).objects.filter(pk=self.app.pk).update(programme=self.gift_b)
        self.assertIn(mine.id, self.ids())

    def test_archived_after_she_started_stays_read_only_and_hides_from_the_rest(self):
        m = _module(self.org)
        lesson = m.lessons.first()
        self.me().post(f'{MINE}{m.id}/lessons/{lesson.id}/read/')
        DevelopmentModule.objects.filter(pk=m.pk).update(status='archived', archived_at=timezone.now())
        item = self.me().get(f'{MINE}{m.id}/').json()
        self.assertFalse(item['can_act'])
        self.assertTrue(item['lessons'][0]['read'])
        r = self.me().post(f'{MINE}{m.id}/lessons/{m.lessons.last().id}/read/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'module_closed'))
        self.assertEqual(self.ids(self.other.profile), [])

    def test_a_closed_file_keeps_only_what_it_started_and_cannot_act(self):
        started, fresh = _module(self.org, 'Started'), _module(self.org, 'Fresh')
        self.me().post(f'{MINE}{started.id}/lessons/{started.lessons.first().id}/read/')
        type(self.app).objects.filter(pk=self.app.pk).update(status='closed', closed_at=timezone.now())
        self.assertEqual(self.ids(), [started.id])
        self.assertFalse(self.me().get(f'{MINE}{started.id}/').json()['can_act'])
        self.assertEqual(self.reflect(started).json()['code'], 'module_closed')
        self.assertEqual(self.me().get(f'{MINE}{fresh.id}/').status_code, 404)

    def test_a_student_who_is_not_a_scholar_has_none(self):
        _module(self.org)
        applicant = make_application('submitted', cohort=make_cohort(programme=self.gift_a))
        self.assertEqual(self.me(applicant.profile).get(MINE).status_code, 404)

    def test_the_payload_is_an_allowlist(self):
        m = _module(self.org, created_by_email='siti@example.test', email_on_publish=True)
        body = self.me().get(MINE).json()
        self.assertEqual(set(body['modules'][0]), {'id', 'title', 'summary', 'due_on', 'task_kind', 'lessons', 'read',
                                                   'done', 'started', 'can_act', 'task_sent_at', 'reviewed'})
        one = self.me().get(f'{MINE}{m.id}/').json()
        self.assertEqual(set(one), {'id', 'title', 'summary', 'due_on', 'can_act', 'done', 'lessons', 'task'})
        self.assertEqual(set(one['lessons'][0]), {'id', 'title', 'body', 'video_url', 'file', 'read'})
        self.assertEqual(set(one['task']), {'kind', 'prompt', 'text', 'file', 'sent_at', 'reviewed_at', 'comment',
                                            'can_change'})
        self.assertNotIn('siti@example.test', json.dumps(body) + json.dumps(one))


class TestHerWork(_Base):
    def test_summary_tab_and_count(self):
        body = self.me().get(SUMMARY).json()
        self.assertEqual((body['growth_tab'], body['growth_to_do']), (False, 0))
        a, b = _module(self.org, 'A'), _module(self.org, 'B', task_kind='none', task_prompt='')
        self.assertEqual(self.me().get(SUMMARY).json()['growth_to_do'], 2)
        r = self.read_all(b)
        self.assertEqual(r.json()['to_do'], 1)
        self.assertTrue(r.json()['module']['done'])
        self.read_all(a)
        self.assertEqual(self.reflect(a).json()['to_do'], 0)
        body = self.me().get(SUMMARY).json()
        self.assertEqual((body['growth_tab'], body['growth_to_do']), (True, 0))

    def test_marking_read_twice_is_one_row(self):
        m = _module(self.org)
        lesson = m.lessons.first()
        for _ in range(2):
            self.assertEqual(self.me().post(f'{MINE}{m.id}/lessons/{lesson.id}/read/').status_code, 200)
        self.assertEqual(LessonRead.objects.count(), 1)
        self.assertEqual(ModuleProgress.objects.count(), 1)

    def test_id_guessing_is_404(self):
        m = _module(self.org)
        other_module = _module(self.org, 'Other')
        foreign = _module(_scholar().owning_organisation, 'Foreign')
        draft = _module(self.org, 'Draft', status='draft')
        c = self.me()
        self.assertEqual(c.post(f'{MINE}{m.id}/lessons/{other_module.lessons.first().id}/read/').status_code, 404)
        for x in (foreign, draft):
            with self.subTest(x=x.title):
                self.assertEqual(c.get(f'{MINE}{x.id}/').status_code, 404)
                self.assertEqual(c.post(f'{MINE}{x.id}/lessons/{x.lessons.first().id}/read/').status_code, 404)
                self.assertEqual(self.reflect(x).status_code, 404)
        self.assertEqual(c.get(f'{MINE}999999/').status_code, 404)
        self.assertFalse(LessonRead.objects.exists())

    def test_the_reflection_after_the_lessons_changeable_until_reviewed(self):
        m = _module(self.org)
        self.assertEqual(self.reflect(m).json()['code'], 'lessons_first')
        self.read_all(m)
        self.assertEqual(self.reflect(m, ' ').json()['code'], 'text_required')
        self.assertEqual(self.reflect(m, 'x' * 5001).json()['code'], 'text_too_long')
        self.assertEqual(self.reflect(m).status_code, 200)
        r = self.reflect(m, 'A better plan.')
        self.assertEqual(r.json()['module']['task']['text'], 'A better plan.')
        development_progress.review(m, self.app.id, 'Good plan.', by_email='siti@example.test')
        r = self.reflect(m, 'Too late.')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'reviewed'))
        task = self.me().get(f'{MINE}{m.id}/').json()['task']
        self.assertEqual((task['text'], task['comment'], task['can_change']), ('A better plan.', 'Good plan.', False))
        self.assertNotIn('siti@example.test', json.dumps(task))

    def test_a_module_without_a_task_takes_none(self):
        m = _module(self.org, task_kind='none', task_prompt='')
        self.read_all(m)
        r = self.reflect(m)
        self.assertEqual((r.status_code, r.json()['code']), (409, 'no_task'))


@patch(STORAGE + 'delete_objects', return_value=True)
@patch(STORAGE + 'create_signed_upload_url', return_value='https://storage.test/upload')
class TestTheUpload(_Base):
    def setUp(self):
        super().setUp()
        self.m = _module(self.org, task_kind='upload', task_prompt='Upload your CV')
        self.read_all(self.m)

    def signed(self):
        r = self.me().post(f'{MINE}{self.m.id}/task/sign/', {'size': 1000}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['storage_path']

    def send(self, path, name='cv.pdf'):
        return self.me().post(f'{MINE}{self.m.id}/task/', {'storage_path': path, 'original_filename': name},
                              format='json')

    def test_the_key_is_under_her_own_path_and_the_type_comes_from_the_bytes(self, _sign, _delete):
        path = self.signed()
        self.assertTrue(path.startswith(f'{self.org.id}/{self.app.id}/growth-{self.m.id}/'))
        with patch(STORAGE + 'download_object', return_value=PNG):
            r = self.send(path, 'cv.pdf')
        self.assertEqual(r.status_code, 200, r.content)
        p = ModuleProgress.objects.get()
        self.assertEqual((p.task_file_path, p.task_file_type, p.task_file_size), (path, 'image/png', len(PNG)))

    def test_a_path_that_is_not_hers_is_refused(self, _sign, _delete):
        path = self.signed()
        other = _module(self.org, 'Other', task_kind='upload', task_prompt='x')
        for bad in (path.replace(f'/{self.app.id}/', f'/{self.other.id}/'),
                    path.replace(f'growth-{self.m.id}', f'growth-{other.id}'),
                    path + '/../x', f'{self.org.id}/{self.app.id}/ic/{"a" * 32}', 'https://evil.test/x', 7):
            with self.subTest(bad=bad), patch(STORAGE + 'download_object', return_value=PDF) as dl:
                r = self.send(bad)
                self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_path'))
                dl.assert_not_called()
        self.assertFalse(ModuleProgress.objects.exclude(task_file_path='').exists())

    def test_a_disguised_or_oversize_or_missing_file_is_refused_and_removed(self, _sign, delete):
        cases = ((b'MZ\x90\x00 an exe called cv.pdf', 'unsupported_format', True),
                 (b'%PDF-' + b'0' * development_files.MAX_BYTES, 'file_too_large', True),
                 (None, 'upload_incomplete', False))
        for data, code, removed in cases:
            with self.subTest(code=code), patch(STORAGE + 'download_object', return_value=data):
                delete.reset_mock()
                path = self.signed()
                r = self.send(path)
                self.assertEqual((r.status_code, r.json()['code']), (400, code))
                self.assertEqual(delete.called, removed)
        r = self.me().post(f'{MINE}{self.m.id}/task/sign/', {'size': development_files.MAX_BYTES + 1}, format='json')
        self.assertEqual(r.json()['code'], 'file_too_large')
        self.assertFalse(ModuleProgress.objects.exclude(task_file_path='').exists())

    def test_a_replaced_file_is_deleted_and_her_link_is_hers_alone(self, _sign, delete):
        first, second = self.signed(), self.signed()
        with patch(STORAGE + 'download_object', return_value=PDF):
            self.send(first)
            delete.reset_mock()
            self.send(second)
        delete.assert_called_once_with([first])
        with patch(STORAGE + 'create_signed_download_url', return_value='https://storage.test/signed') as sign:
            r = self.me().get(f'{MINE}{self.m.id}/task/file/')
            self.assertEqual((r.status_code, r.json()['expires_in']), (200, 300))
            sign.assert_called_once_with(second, expires_in=300)
            self.assertEqual(self.me(self.other.profile).get(f'{MINE}{self.m.id}/task/file/').status_code, 404)

    def test_a_lesson_file_link_only_for_a_module_she_can_see(self, _sign, _delete):
        hidden = _module(self.org, 'Theirs', programme=self.gift_b)
        for m in (self.m, hidden):
            ModuleLesson.objects.filter(module=m).update(file_path=f'{self.org.id}/development/{m.id}/{"b" * 32}',
                                                         video_url='')
        with patch(STORAGE + 'create_signed_download_url', return_value='https://storage.test/l'):
            lesson = self.m.lessons.first()
            self.assertEqual(self.me().get(f'{MINE}{self.m.id}/lessons/{lesson.id}/file/').status_code, 200)
            h = hidden.lessons.first()
            self.assertEqual(self.me().get(f'{MINE}{hidden.id}/lessons/{h.id}/file/').status_code, 404)
            self.assertEqual(self.me().get(f'{MINE}{self.m.id}/lessons/{h.id}/file/').status_code, 404)


class TestStaffDoors(_Base):
    def test_org_admin_admin_and_super_make_everyone_else_is_refused(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create(self.officer).status_code, 201)
        sup = make_admin('super', super_admin=True, owning_org=self.org)
        self.assertEqual(self.create(sup).status_code, 201)
        m = DevelopmentModule.objects.first()
        for who in (make_admin('reviewer', owning_org=self.org), make_admin('qc', owning_org=self.org),
                    make_admin('finance', owning_org=self.org), make_admin('source_partner', owning_org=self.org),
                    make_admin('mentor', owning_org=self.org), make_admin('partner', owning_org=self.org)):
            with self.subTest(role=who.role):
                c = authed_client(who)
                self.assertEqual(c.get(STAFF).status_code, 403)
                self.assertEqual(self.create(who).status_code, 403)
                self.assertEqual(c.get(f'{STAFF}{m.id}/progress/').status_code, 403)
                self.assertEqual(c.get(f'{STAFF}{m.id}/csv/').status_code, 403)
                self.assertIn(c.get(f'/api/v1/admin/scholarship/scholars/{self.app.id}/development/').status_code,
                              (403, 404))
        self.assertEqual(DevelopmentModule.objects.count(), 3)

    def test_another_organisation_is_404_everywhere(self):
        m = _module(self.org)
        lesson = m.lessons.first()
        stranger = make_admin('org_admin', owning_org=_scholar().owning_organisation)
        c = authed_client(stranger)
        for method, url in (('patch', f'{STAFF}{m.id}/'), ('delete', f'{STAFF}{m.id}/'),
                            ('get', f'{STAFF}{m.id}/progress/'), ('get', f'{STAFF}{m.id}/csv/'),
                            ('post', f'{STAFF}{m.id}/archive/'), ('post', f'{STAFF}{m.id}/remind/'),
                            ('get', f'{STAFF}{m.id}/progress/{self.app.id}/file/'),
                            ('post', f'{STAFF}{m.id}/progress/{self.app.id}/review/'),
                            ('get', f'{STAFF}{m.id}/lessons/{lesson.id}/file/'),
                            ('post', f'{STAFF}{m.id}/lessons/{lesson.id}/file/sign/'),
                            ('get', f'/api/v1/admin/scholarship/scholars/{self.app.id}/development/')):
            with self.subTest(url=url, method=method):
                self.assertEqual(getattr(c, method)(url, {'title': 'X'}, format='json').status_code, 404)
        self.assertEqual(c.get(STAFF, {'programme': self.gift_a.code}).status_code, 404)
        self.assertEqual(self.create(stranger, programme=self.gift_a.code).json()['code'], 'bad_audience')
        self.assertEqual(c.get(STAFF).json()['modules'], [])

    def test_a_super_without_an_organisation_names_a_gift(self):
        sup = make_admin('super', super_admin=True)
        self.assertEqual(authed_client(sup).get(STAFF).json()['code'], 'programme_required')
        body = authed_client(sup).get(STAFF, {'programme': self.gift_a.code}).json()
        self.assertEqual(body['organisation']['code'], self.org.code)

    def test_validation(self):
        past = (timezone.localdate() - DAY).isoformat()
        one = LESSONS[0]
        cases = {
            'title_required': {'title': ' '}, 'title_too_long': {'title': 'x' * 151}, 'title_newline': {'title': 'a\nb'},
            'summary_too_long': {'summary': 'x' * 501}, 'bad_audience': {'programme': 'nope'},
            'bad_action': {'action': 'shout'}, 'bad_task_kind': {'task_kind': 'essay'},
            'prompt_required': {'task_prompt': ''}, 'prompt_too_long': {'task_prompt': 'x' * 1001},
            'no_lessons': {'lessons': []}, 'too_many_lessons': {'lessons': [one] * 21},
            'lesson_title_required': {'lessons': [{'title': ''}]},
            'lesson_body_too_long': {'lessons': [{'title': 't', 'body': 'x' * 10001}]},
            'bad_due_on': {'due_on': 'soon'}, 'due_before_publish': {'due_on': past},
            'remind_needs_due': {'remind': True}, 'bad_publish_at': {'publish_at': 'later'},
            'bad_lesson': {'lessons': [{'id': 1, 'title': 't'}]},
        }
        for code, body in cases.items():
            with self.subTest(code=code):
                r = self.create(**body)
                self.assertEqual((r.status_code, r.json()['code']), (400, code))
        self.assertFalse(DevelopmentModule.objects.exists())
        self.assertEqual(self.create(action='draft', lessons=[]).status_code, 201)   # a draft may be empty

    def test_the_video_is_youtube_or_vimeo_https_only(self):
        good = ('https://www.youtube.com/watch?v=abc', 'https://youtu.be/abc', 'https://vimeo.com/123',
                'https://player.vimeo.com/video/123', 'https://m.youtube.com/watch?v=a')
        for url in good:
            self.assertEqual(development.clean_video(url), url)
        bad = ('http://youtu.be/abc', 'https://youtube.com.evil.test/x', 'https://evil.test/youtu.be',
               'https://user:pw@youtube.com/x', 'https://youtube.com:8443/x', 'javascript:alert(1)',
               'https://evil.test\\@youtube.com/', 'https://you tube.com/', 'ftp://vimeo.com/1')
        for url in bad:
            with self.subTest(url=url):
                r = self.create(lessons=[{'title': 't', 'video_url': url}])
                self.assertEqual(r.json()['code'], 'bad_video')
                self.assertEqual(r.json()['detail'], 0)

    def test_publish_now_later_and_the_tabs(self):
        later = (timezone.now() + 2 * DAY).isoformat()
        self.assertEqual(self.create().json()['status'], 'published')
        self.assertEqual(self.create(publish_at=later).json()['status'], 'scheduled')
        self.assertEqual(self.create(action='draft').json()['status'], 'draft')
        body = authed_client(self.org_admin).get(STAFF).json()
        self.assertEqual(body['counts'], {'published': 1, 'scheduled': 1, 'draft': 1, 'archived': 0})
        self.assertEqual(body['limits']['file_bytes'], 10 * 1024 * 1024)

    def test_the_task_type_locks_at_the_first_start_lessons_can_still_change(self):
        m = _module(self.org)
        c = authed_client(self.org_admin)
        self.assertEqual(c.patch(f'{STAFF}{m.id}/', {'task_kind': 'upload'}, format='json').status_code, 200)
        self.me().post(f'{MINE}{m.id}/lessons/{m.lessons.first().id}/read/')
        for body, code in (({'task_kind': 'reflection'}, 'task_locked'), ({'programme': self.gift_b.code},
                           'started_locked'), ({'action': 'draft'}, 'started_locked')):
            with self.subTest(body=body):
                r = c.patch(f'{STAFF}{m.id}/', body, format='json')
                self.assertEqual((r.status_code, r.json()['code']), (409, code))
        kept = list(m.lessons.values('id', 'title', 'body', 'video_url'))
        kept[0]['body'] = 'Fixed a typo.'
        r = c.patch(f'{STAFF}{m.id}/', {'lessons': kept + [{'title': 'New lesson'}]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([x['title'] for x in r.json()['lessons']][-1], 'New lesson')
        self.assertEqual(ModuleLesson.objects.get(pk=kept[0]['id']).body, 'Fixed a typo.')
        self.assertTrue(LessonRead.objects.filter(lesson_id=kept[0]['id']).exists())   # her read survives

    def test_done_follows_the_current_lessons(self):
        m = _module(self.org, task_kind='none', task_prompt='')
        self.read_all(m)
        self.assertTrue(self.me().get(f'{MINE}{m.id}/').json()['done'])
        c = authed_client(self.org_admin)
        kept = list(m.lessons.values('id', 'title', 'body', 'video_url'))
        c.patch(f'{STAFF}{m.id}/', {'lessons': kept + [{'title': 'One more'}]}, format='json')
        self.assertFalse(self.me().get(f'{MINE}{m.id}/').json()['done'])
        c.patch(f'{STAFF}{m.id}/', {'lessons': kept}, format='json')
        self.assertTrue(self.me().get(f'{MINE}{m.id}/').json()['done'])

    def test_delete_only_unstarted_otherwise_archive(self):
        c = authed_client(self.org_admin)
        draft, live = _module(self.org, status='draft'), _module(self.org)
        self.assertEqual(c.delete(f'{STAFF}{draft.id}/').status_code, 204)
        self.me().post(f'{MINE}{live.id}/lessons/{live.lessons.first().id}/read/')
        r = c.delete(f'{STAFF}{live.id}/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'archive_instead'))
        r = c.post(f'{STAFF}{live.id}/archive/')
        self.assertEqual(r.json()['status'], 'archived')
        self.assertEqual(c.post(f'{STAFF}{live.id}/archive/').json()['code'], 'not_published')
        self.assertEqual(c.patch(f'{STAFF}{live.id}/', {'action': 'publish'}, format='json').json()['status'],
                         'published')   # put back

    def test_a_deleted_lesson_or_module_takes_its_file(self):
        m = _module(self.org, status='draft')
        a, b = list(m.lessons.all())
        ModuleLesson.objects.filter(pk=a.pk).update(file_path=f'{self.org.id}/development/{m.id}/{"a" * 32}',
                                                    video_url='')
        c = authed_client(self.org_admin)
        with patch(STORAGE + 'delete_objects', return_value=True) as delete, \
                self.captureOnCommitCallbacks(execute=True):
            c.patch(f'{STAFF}{m.id}/', {'lessons': [{'id': b.id, 'title': b.title}]}, format='json')
        delete.assert_called_once_with([f'{self.org.id}/development/{m.id}/{"a" * 32}'])


@patch(STORAGE + 'delete_objects', return_value=True)
@patch(STORAGE + 'create_signed_upload_url', return_value='https://storage.test/upload')
class TestLessonFiles(_Base):
    def test_sign_record_by_the_bytes_replace_and_remove(self, _sign, delete):
        m = _module(self.org, lessons=[{'title': 'Worksheet'}])
        lesson = m.lessons.get()
        c = authed_client(self.org_admin)
        base = f'{STAFF}{m.id}/lessons/{lesson.id}/file/'
        path = c.post(f'{base}sign/', {'size': 2000}, format='json').json()['storage_path']
        self.assertTrue(path.startswith(f'{self.org.id}/development/{m.id}/'))
        with patch(STORAGE + 'download_object', return_value=PDF):
            r = c.post(base, {'storage_path': path, 'original_filename': 'worksheet.png'}, format='json')
        self.assertEqual(r.json()['lessons'][0]['file'], {'name': 'worksheet.png', 'type': 'application/pdf',
                                                          'size': len(PDF)})
        other = _module(self.org, 'Other')
        foreign_path = f'{self.org.id}/development/{other.id}/{"c" * 32}'
        self.assertEqual(c.post(base, {'storage_path': foreign_path}, format='json').json()['code'], 'bad_path')
        with self.captureOnCommitCallbacks(execute=True):
            c.delete(base)
        delete.assert_called_with([path])
        self.assertEqual(ModuleLesson.objects.get(pk=lesson.pk).file_path, '')

    def test_another_lessons_file_is_not_taken(self, _sign, delete):
        m = _module(self.org, lessons=[{'title': 'One'}, {'title': 'Two'}])
        one, two = list(m.lessons.all())
        taken = f'{self.org.id}/development/{m.id}/{"d" * 32}'
        ModuleLesson.objects.filter(pk=one.pk).update(file_path=taken, file_name='a.pdf')
        with patch(STORAGE + 'download_object', return_value=PDF) as dl:
            r = authed_client(self.org_admin).post(f'{STAFF}{m.id}/lessons/{two.id}/file/', {'storage_path': taken},
                                                   format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_path'))
        dl.assert_not_called()
        delete.assert_not_called()
        self.assertEqual(ModuleLesson.objects.get(pk=two.pk).file_path, '')

    def test_a_video_lesson_takes_no_file(self, _sign, _delete):
        m = _module(self.org)
        video = m.lessons.exclude(video_url='').get()
        r = authed_client(self.org_admin).post(f'{STAFF}{m.id}/lessons/{video.id}/file/sign/', {}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'video_or_file'))


class TestProgress(_Base):
    def setUp(self):
        super().setUp()
        self.m = _module(self.org, due_on=timezone.localdate() + 5 * DAY)
        self.third = _scholar(make_cohort(programme=self.gift_a))
        mentor = make_admin('mentor', owning_org=self.org, name='Ravi K.').mentor
        MentorAssignment.objects.create(application=self.app, mentor=mentor)

    def test_the_tabs_late_mentor_and_review(self):
        self.read_all(self.m)
        self.reflect(self.m, '=HYPERLINK("http://evil.test")')
        self.me(self.other.profile).post(f'{MINE}{self.m.id}/lessons/{self.m.lessons.first().id}/read/')
        c = authed_client(self.org_admin)
        body = c.get(f'{STAFF}{self.m.id}/progress/').json()
        self.assertEqual(body['counts'], {'to_review': 1, 'done': 1, 'in_progress': 1, 'not_started': 1})
        row = next(r for r in body['rows'] if r['application_id'] == self.app.id)
        self.assertEqual((row['mentor'], row['read'], row['lessons'], row['late']), ('Ravi K.', 2, 2, False))
        DevelopmentModule.objects.filter(pk=self.m.pk).update(due_on=timezone.localdate() - DAY)
        rows = {r['application_id']: r for r in c.get(f'{STAFF}{self.m.id}/progress/').json()['rows']}
        self.assertEqual((rows[self.app.id]['late'], rows[self.other.id]['late'], rows[self.third.id]['late']),
                         (False, True, True))
        r = c.post(f'{STAFF}{self.m.id}/progress/{self.other.id}/review/', {'comment': 'x'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'nothing_to_review'))
        r = c.post(f'{STAFF}{self.m.id}/progress/{self.app.id}/review/', {'comment': 'y' * 1001}, format='json')
        self.assertEqual(r.json()['code'], 'comment_too_long')
        r = c.post(f'{STAFF}{self.m.id}/progress/{self.app.id}/review/', {'comment': 'Good plan.'}, format='json')
        self.assertEqual(r.json()['counts']['to_review'], 0)
        p = ModuleProgress.objects.get(application=self.app)
        self.assertEqual((p.review_comment, p.reviewed_by_email), ('Good plan.', self.org_admin.email))

    def test_the_csv_escapes_formula_cells(self):
        self.read_all(self.m)
        self.reflect(self.m, '=SUM(1)')
        text = authed_client(self.org_admin).get(f'{STAFF}{self.m.id}/csv/').content.decode()
        self.assertIn("'=SUM(1)", text)
        self.assertIn('NUR AISYAH', text)
        self.assertEqual(development_progress._cell('\tx'), "'\tx")
        self.assertEqual(development_progress._cell('\rx'), "'\rx")

    def test_the_scholar_file_tab_and_the_upload_door(self):
        c = authed_client(self.org_admin)
        self.read_all(self.m)
        self.reflect(self.m)
        tab = c.get(f'/api/v1/admin/scholarship/scholars/{self.app.id}/development/').json()
        self.assertEqual(tab['modules'][0]['task_text'], 'I will cook three days a week.')
        self.assertEqual(c.get(f'{STAFF}{self.m.id}/progress/{self.app.id}/file/').status_code, 404)   # no file
        ModuleProgress.objects.filter(application=self.app).update(task_file_path='1/2/growth-3/' + 'a' * 32)
        with patch(STORAGE + 'create_signed_download_url', return_value='https://storage.test/s'):
            self.assertEqual(c.get(f'{STAFF}{self.m.id}/progress/{self.app.id}/file/').json()['expires_in'], 300)


class TestTheMentor(_Base):
    def test_the_current_mentor_sees_the_work_and_loses_it_when_it_ends(self):
        m = _module(self.org)
        login = make_admin('mentor', owning_org=self.org)
        assignment = MentorAssignment.objects.create(application=self.app, mentor=login.mentor)
        self.read_all(m)
        self.reflect(m)
        page = f'/api/v1/admin/mentor/students/{self.app.id}/'
        mods = authed_client(login).get(page).json()['modules']
        self.assertEqual((mods[0]['title'], mods[0]['task_text'], mods[0]['read']),
                         ('Managing your money', 'I will cook three days a week.', 2))
        self.assertNotIn('author', mods[0])
        another = make_admin('mentor', owning_org=self.org)
        self.assertEqual(authed_client(another).get(page).status_code, 404)
        MentorAssignment.objects.filter(pk=assignment.pk).update(ended_at=timezone.now())
        self.assertEqual(authed_client(login).get(page).status_code, 404)


class TestTheEmail(_Base):
    def setUp(self):
        super().setUp()
        self.third = _scholar(make_cohort(programme=self.gift_a))

    def test_published_once_per_scholar_metered_and_logged_even_when_run_twice(self):
        m = _module(self.org, email_on_publish=True, due_on=timezone.localdate() + 20 * DAY)
        _run_job()
        _run_job()
        self.assertEqual(sorted(x.to[0] for x in mail.outbox),
                         sorted([self.app.notify_email, self.other.notify_email, self.third.notify_email]))
        letter = mail.outbox[0]
        self.assertIn('Managing your money', letter.subject)
        self.assertIn('A new development module is ready', letter.body)
        self.assertIn('/scholarship/bursary?tab=growth', letter.body)
        self.assertEqual(ModuleEmail.objects.filter(module=m, kind='published', outcome='sent').count(), 3)
        self.assertEqual(StudentEmailLog.objects.filter(key='module_published', ok=True).count(), 3)

    def test_draft_scheduled_archived_or_not_asked_send_nothing(self):
        _module(self.org)
        _module(self.org, 'Draft', status='draft', email_on_publish=True)
        _module(self.org, 'Later', publish_at=timezone.now() + HOUR, email_on_publish=True)
        _module(self.org, 'Archived', status='archived', email_on_publish=True,
                due_on=timezone.localdate() + DAY, remind_before_due=True)
        _run_job()
        self.assertEqual(mail.outbox, [])

    def test_the_reminder_needs_a_due_date_waits_for_the_window_and_skips_those_done(self):
        m = _module(self.org, task_kind='none', task_prompt='', remind_before_due=True,
                    due_on=timezone.localdate() + 10 * DAY)
        _module(self.org, 'No due date', remind_before_due=False)
        _run_job()
        self.assertEqual(mail.outbox, [])
        DevelopmentModule.objects.filter(pk=m.pk).update(due_on=timezone.localdate() + 2 * DAY)
        self.read_all(m)
        _run_job()
        _run_job()
        self.assertEqual(sorted(x.to[0] for x in mail.outbox), sorted([self.other.notify_email, self.third.notify_email]))
        self.assertIn('you have not finished this module yet', mail.outbox[0].body)
        self.assertFalse(ModuleEmail.objects.filter(application=self.app).exists())

    def test_the_button_and_the_job_never_double(self):
        m = _module(self.org, remind_before_due=True, due_on=timezone.localdate() + 2 * DAY)
        c = authed_client(self.org_admin)
        r = c.post(f'{STAFF}{m.id}/remind/')
        self.assertEqual((r.status_code, r.json()['sent']), (200, 3))
        self.assertFalse(r.json()['can_remind'])   # everybody not done has been reminded
        self.assertEqual(c.post(f'{STAFF}{m.id}/remind/').json()['sent'], 0)
        _run_job()
        self.assertEqual(len(mail.outbox), 3)
        nodue = _module(self.org, 'No due')
        self.assertEqual(c.post(f'{STAFF}{nodue.id}/remind/').json()['code'], 'no_due_date')
        draft = _module(self.org, 'Draft', status='draft', due_on=timezone.localdate() + DAY)
        self.assertEqual(c.post(f'{STAFF}{draft.id}/remind/').json()['code'], 'not_live')

    def test_switched_off_the_job_records_and_the_button_writes_nothing(self):
        m = _module(self.org, email_on_publish=True, remind_before_due=True, due_on=timezone.localdate() + DAY)
        student_email_catalogue.set_switch(self.org, 'module_published', False)
        r = authed_client(self.org_admin).post(f'{STAFF}{m.id}/remind/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'switched_off'))
        self.assertFalse(ModuleEmail.objects.exists())
        _run_job()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(ModuleEmail.objects.filter(module=m, outcome='switched_off', kind='published').count(), 3)
        student_email_catalogue.set_switch(self.org, 'module_published', True)
        _run_job()
        self.assertEqual(mail.outbox, [])   # never later

    def test_a_scholar_without_an_address_is_recorded_and_the_rest_go(self):
        type(self.app).objects.filter(pk=self.app.pk).update(notify_email='')
        m = _module(self.org, email_on_publish=True)
        _run_job()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(ModuleEmail.objects.get(module=m, application=self.app).outcome, 'no_address')

    def test_archived_mid_run_stops_the_rest(self):
        m = _module(self.org, email_on_publish=True)
        real = __import__('apps.scholarship.student_comms', fromlist=['x']).send_student_email

        def send_then_archive(app, kind, **values):
            ok = real(app, kind, **values)
            DevelopmentModule.objects.filter(pk=m.pk).update(status='archived')
            return ok
        with patch('apps.scholarship.student_comms.send_student_email', side_effect=send_then_archive):
            _run_job()
        self.assertEqual(len(mail.outbox), 1)
        m.refresh_from_db()
        self.assertIsNone(m.published_emailed_at)


class TestReviewFixes(_Base):
    """The S10 safety review's four fixes, each pinned."""

    def setUp(self):
        super().setUp()
        self.m = _module(self.org, task_kind='upload', task_prompt='Upload your CV')
        self.mentor = make_admin('mentor', owning_org=self.org)
        self.assignment = MentorAssignment.objects.create(application=self.app, mentor=self.mentor.mentor)

    def file_url(self, mid=None):
        return f'/api/v1/admin/mentor/students/{self.app.id}/modules/{mid or self.m.id}/file/'

    def test_1_the_mentor_link_is_signed_on_the_tap_for_the_current_mentor_only(self):
        ModuleProgress.objects.create(module=self.m, application=self.app, task_file_path='1/2/growth-3/' + 'e' * 32,
                                      task_file_name='cv.pdf', task_sent_at=timezone.now())
        page = authed_client(self.mentor).get(f'/api/v1/admin/mentor/students/{self.app.id}/').json()
        self.assertNotIn('url', page['modules'][0]['task_file'])   # never a (stale) link in the payload
        with patch(STORAGE + 'create_signed_download_url', return_value='https://storage.test/m') as sign:
            r = authed_client(self.mentor).get(self.file_url())
            self.assertEqual((r.status_code, r.json()['url']), (200, 'https://storage.test/m'))
            sign.assert_called_once_with('1/2/growth-3/' + 'e' * 32, expires_in=300)
            hidden = _module(self.org, 'Their gift', programme=self.gift_b)
            ModuleProgress.objects.create(module=hidden, application=self.app, task_file_path='1/2/x/' + 'f' * 32)
            self.assertEqual(authed_client(self.mentor).get(self.file_url(hidden.id)).status_code, 404)
            other = make_admin('mentor', owning_org=self.org)
            self.assertEqual(authed_client(other).get(self.file_url()).status_code, 404)
            staff = make_admin('org_admin', owning_org=self.org)   # staff with no mentoring: refused like 7c's doors
            self.assertEqual(authed_client(staff).get(self.file_url()).status_code, 403)
            MentorAssignment.objects.filter(pk=self.assignment.pk).update(ended_at=timezone.now())
            self.assertEqual(authed_client(self.mentor).get(self.file_url()).status_code, 404)

    @patch(STORAGE + 'create_signed_upload_url', return_value='https://storage.test/upload')
    def test_2_the_growth_uploads_are_signed_without_upsert(self, sign):
        self.read_all(self.m)
        self.me().post(f'{MINE}{self.m.id}/task/sign/', {}, format='json')
        lesson = self.m.lessons.first()
        ModuleLesson.objects.filter(pk=lesson.pk).update(video_url='')
        authed_client(self.org_admin).post(f'{STAFF}{self.m.id}/lessons/{lesson.id}/file/sign/', {}, format='json')
        self.assertEqual([c.kwargs for c in sign.call_args_list], [{'upsert': False}, {'upsert': False}])

    def test_2_upsert_false_is_the_header_and_the_older_flows_send_none(self):
        with patch(STORAGE + '_post', return_value={'url': '/x'}) as post:
            from apps.scholarship import storage
            storage.create_signed_upload_url('a/b', upsert=False)
            storage.create_signed_upload_url('a/c')   # the older flows: unchanged
        self.assertEqual(post.call_args_list[0].kwargs['headers'], {'x-upsert': 'false'})
        self.assertIsNone(post.call_args_list[1].kwargs['headers'])

    @patch(STORAGE + 'create_signed_upload_url', return_value='https://storage.test/upload')
    def test_3_signing_her_upload_has_the_sends_own_checks(self, sign):
        sign_url = f'{MINE}{self.m.id}/task/sign/'
        r = self.me().post(sign_url, {}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'lessons_first'))
        self.read_all(self.m)
        self.assertEqual(self.me().post(sign_url, {}, format='json').status_code, 200)
        ModuleProgress.objects.filter(application=self.app).update(task_sent_at=timezone.now(),
                                                                   reviewed_at=timezone.now())
        self.assertEqual(self.me().post(sign_url, {}, format='json').json()['code'], 'reviewed')
        DevelopmentModule.objects.filter(pk=self.m.pk).update(status='archived')
        self.assertEqual(self.me().post(sign_url, {}, format='json').json()['code'], 'module_closed')
        self.assertEqual(sign.call_count, 1)

    def test_4_the_button_never_writes_switched_off_even_when_it_flips_mid_run(self):
        m = _module(self.org, 'Due', remind_before_due=True, due_on=timezone.localdate() + DAY)
        _scholar(make_cohort(programme=self.gift_a))
        # remind_not_done, the run's own check, scholar 1's check and its send: on; scholar 2's check: off.
        answers = iter([True, True, True, True] + [False] * 10)
        with patch('apps.scholarship.student_email_catalogue.may_send', side_effect=lambda *a: next(answers)):
            r = authed_client(self.org_admin).post(f'{STAFF}{m.id}/remind/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(ModuleEmail.objects.filter(outcome='switched_off').exists())
        self.assertEqual(ModuleEmail.objects.filter(module=m).count(), 1)   # one sent, then it stopped
        student_email_catalogue.set_switch(self.org, 'module_published', False)
        self.assertEqual(authed_client(self.org_admin).post(f'{STAFF}{m.id}/remind/').json()['code'], 'switched_off')
        self.assertEqual(ModuleEmail.objects.filter(module=m).count(), 1)


class TestTheOrphanSweepKnowsTheFiles(_Base):
    def test_lesson_and_task_files_are_known(self):
        from apps.scholarship.management.commands.cleanup_orphan_blobs import known_paths
        m = _module(self.org)
        ModuleLesson.objects.filter(module=m).update(file_path='1/development/2/' + 'a' * 32, video_url='')
        ModuleProgress.objects.create(module=m, application=self.app, task_file_path='1/2/growth-3/' + 'b' * 32)
        known = known_paths()
        self.assertIn('1/development/2/' + 'a' * 32, known)
        self.assertIn('1/2/growth-3/' + 'b' * 32, known)
