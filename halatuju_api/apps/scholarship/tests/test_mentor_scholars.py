"""Sprint S1 (owner 2026-11-09, decision S1-h): a MENTOR reads the Scholars page and the full file of their
CURRENT students, read-only.

Brief `docs/plans/2026-11-09-s1-scholars-access.md`; decisions.md "S1". Pinned through the real endpoints:
  * the list is their current students only (another mentor's, an ended assignment: absent);
  * every tab of their student's file answers 200, with every control off and nothing to assign or issue;
  * ONE 404 for an ended assignment, another mentor's student, another organisation's file, their own
    application and an unknown id;
  * every write is refused — for a mentor login (`get_admin`) and for staff who mentor (`_file_for`);
  * no "Staff only" activity row reaches them, and the counts leave those rows out;
  * a mentor who also holds `scholars` reads the whole organisation (`scholars_scope` 'all' wins).
The sweep of every other admin route is `test_mentor_denied_everywhere.py`.
"""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models_claim import ProfileLoginAlias
from apps.scholarship import activity, mentoring
from apps.scholarship.models import Mentor, MentorAssignment, ModuleProgress
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_admin, make_student
from apps.scholarship.tests.test_development import _module
from apps.scholarship.tests.test_mentoring import _scholar, make_mentor
from apps.scholarship.views_admin.base import scholars_scope

API = '/api/v1/admin/scholarship/scholars/'
NO_ROW = 999999
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


def tabs(pk):
    return (f'{API}{pk}/', f'{API}{pk}/activity/', f'{API}{pk}/results/', f'{API}{pk}/money/',
            f'{API}{pk}/contract/', f'{API}{pk}/letters/', f'{API}{pk}/development/', f'{API}{pk}/surveys/',
            f'{API}{pk}/mentoring/')


def writes(pk):
    return ((f'{API}{pk}/activity/', {'kind': 'note', 'body': 'x'}),
            (f'{API}{pk}/results/{NO_ROW}/review/', {'decision': 'accepted'}),
            (f'{API}{pk}/letters/', {'kind': 'general', 'language': 'en'}),
            (f'{API}{pk}/letters/preview/', {'kind': 'general', 'language': 'en'}),
            (f'{API}{pk}/letters/{NO_ROW}/resend/', {}),
            (f'{API}{pk}/mentoring/assign/', {'mentor_id': NO_ROW}),
            (f'{API}{pk}/mentoring/end/', {'reason': 'x'}),
            (f'{API}{pk}/mentoring/handle-concern/', {}),
            (f'{API}{pk}/mentoring/sessions/', {'met_on': '2026-11-01', 'mode': 'video', 'notes': 'x'}))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
@LOCMEM
class _Base(TestCase):
    def setUp(self):
        self.app = _scholar(student=make_student(name='NUR AISYAH', contact_email='aisyah@example.invalid'))
        self.org = self.app.owning_organisation
        self.lead = make_admin('org_admin', owning_org=self.org)
        self.kavitha = make_mentor(self.org, email='kavitha@example.invalid')
        self.faizal = make_mentor(self.org, 'Faizal Hamid', email='faizal@example.invalid')
        self.login = mentoring._login(self.kavitha)
        mentoring.assign(self.lead, self.app, self.kavitha, email_student=False)
        self.theirs = _scholar(cohort=self.app.cohort)
        mentoring.assign(self.lead, self.theirs, self.faizal, email_student=False)
        mail.outbox.clear()

    def client_for(self, who=None):
        return authed_client(who or self.login)

    def staff_mentor(self, role='reviewer', **kw):
        """A STAFF member who also mentors this scholar (S7d), without the `scholars` key by default."""
        person = make_admin(role, owning_org=self.org, **kw)
        person.mentor = Mentor.objects.create(organisation=self.org)
        person.save(update_fields=['mentor'])
        mentoring.end(self.lead, self.app)
        mentoring.assign(self.lead, self.app, person.mentor, email_student=False)
        mail.outbox.clear()
        return person


class TestTheMentorReadsTheirStudents(_Base):
    def test_the_list_is_their_current_students_only(self):
        ended = _scholar(cohort=self.app.cohort)
        mentoring.assign(self.lead, ended, self.kavitha, email_student=False)
        mentoring.end(self.lead, ended)
        self.assertEqual(scholars_scope(self.login), 'mentor')
        r = self.client_for().get(API)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([row['id'] for row in r.json()['results']], [self.app.id])

    def test_every_tab_of_their_student_reads(self):
        client = self.client_for()
        for url in tabs(self.app.id):
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 200, url)

    def test_the_file_is_read_only_to_them(self):
        client = self.client_for()
        body = client.get(f'{API}{self.app.id}/').json()
        controls = body['controls']
        self.assertIs(body['mentor_view'], True)
        self.assertIs(authed_client(self.lead).get(f'{API}{self.app.id}/').json()['mentor_view'], False)
        self.assertFalse(controls['can_review_results'])
        self.assertFalse(controls['can_set_substate'])
        self.assertFalse(controls['can_hold'])
        letters = client.get(f'{API}{self.app.id}/letters/').json()
        self.assertEqual((letters['can_issue'], letters['can_withdraw']), ([], False))
        tab = client.get(f'{API}{self.app.id}/mentoring/').json()
        self.assertEqual((tab['can_act'], tab['assignable']), (False, []))

    def test_every_write_is_refused(self):
        client = self.client_for()
        for url, body in writes(self.app.id):
            with self.subTest(url=url):
                self.assertEqual(client.post(url, body, format='json').status_code, 403)


class TestOneAnswerForEveryoneElse(_Base):
    def test_ended_another_mentors_foreign_own_and_unknown_are_404(self):
        foreign = _scholar()
        mentoring.assign(make_admin('org_admin', owning_org=foreign.owning_organisation), foreign,
                         make_mentor(foreign.owning_organisation, 'Stranger', email='stranger@example.invalid'),
                         email_student=False)
        client = self.client_for()
        for pk in (self.theirs.id, foreign.id, NO_ROW):
            for url in tabs(pk):
                with self.subTest(pk=pk, url=url):
                    self.assertEqual(client.get(url).status_code, 404)
        ProfileLoginAlias.objects.create(alias_uid=self.login.supabase_user_id, profile=self.app.profile)
        self.assertEqual(client.get(f'{API}{self.app.id}/').status_code, 404)        # their own application
        self.assertEqual(client.get(API).json()['results'], [])

    def test_access_ends_when_the_mentoring_ends(self):
        mentoring.end(self.lead, self.app)
        client = self.client_for()
        self.assertEqual(client.get(API).json()['results'], [])
        for url in tabs(self.app.id):
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 404)


class TestStaffOnlyRowsStayWithStaff(_Base):
    def test_no_staff_only_row_or_count(self):
        activity.add_entry(self.app, 'note', 'For the team only.', actor_email=self.lead.email, internal=True)
        activity.add_entry(self.app, 'note', 'Called the student.', actor_email=self.lead.email)
        staff = authed_client(self.lead).get(f'{API}{self.app.id}/activity/').json()
        mine = self.client_for().get(f'{API}{self.app.id}/activity/').json()
        self.assertIn('For the team only.', [r['body'] for r in staff['results']])
        self.assertNotIn('For the team only.', [r['body'] for r in mine['results']])
        self.assertIn('Called the student.', [r['body'] for r in mine['results']])
        self.assertTrue(all(r['internal'] is False for r in mine['results']))
        self.assertEqual(mine['counts']['notes'], staff['counts']['notes'] - 1)
        self.assertEqual(mine['counts']['all'], mine['count'])
        side = self.client_for().get(f'{API}{self.app.id}/activity/', {'counts': '0'}).json()
        self.assertEqual(side['count'], len([r for r in side['results']]))
        # P1: a known person is served by name, never by email
        self.assertTrue(all(r['actor_email'] == '' for r in mine['results'] if r['actor']))


class TestStaffWhoMentor(_Base):
    def test_a_reviewer_who_mentors_reads_their_student_and_writes_nothing(self):
        person = self.staff_mentor()
        self.assertEqual(scholars_scope(person), 'mentor')
        client = authed_client(person)
        self.assertEqual([r['id'] for r in client.get(API).json()['results']], [self.app.id])
        for url in tabs(self.app.id):
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 200)
        for url, body in writes(self.app.id):
            with self.subTest(url=url):
                self.assertEqual(client.post(url, body, format='json').status_code, 403)
        for url, body in writes(self.theirs.id):
            with self.subTest(other=url):
                self.assertEqual(client.post(url, body, format='json').status_code, 404)

    def test_a_mentor_holding_scholars_reads_the_whole_organisation(self):
        person = self.staff_mentor('admin', permissions=['scholars'])
        self.assertEqual(scholars_scope(person), 'all')
        ids = {r['id'] for r in authed_client(person).get(API).json()['results']}
        self.assertTrue({self.app.id, self.theirs.id} <= ids)
        self.assertEqual(authed_client(person).get(f'{API}{self.theirs.id}/').status_code, 200)


class TestTheGrowthTaskFile(_Base):
    """S1 review should-fix 1: the Growth tab's "open the task" goes through the FILE's door
    (`scholars/<pk>/development/<module>/file/`), so a mentor reaches their current student's upload — and
    only theirs — instead of the module makers' door, which refused them."""
    SIGN = 'apps.scholarship.storage.create_signed_download_url'

    def setUp(self):
        super().setUp()
        self.m = _module(self.org, task_kind='upload', task_prompt='Upload your CV')
        ModuleProgress.objects.create(module=self.m, application=self.app, task_file_path='1/2/growth-3/' + 'e' * 32,
                                      task_file_name='cv.pdf', task_sent_at=timezone.now())

    def url(self, mid=None, pk=None):
        return f'{API}{pk or self.app.id}/development/{mid or self.m.id}/file/'

    def test_their_current_student_opens_and_staff_still_do(self):
        with patch(self.SIGN, return_value='https://storage.test/m') as sign:
            r = self.client_for().get(self.url())
            self.assertEqual((r.status_code, r.json()['url']), (200, 'https://storage.test/m'))
            sign.assert_called_once_with('1/2/growth-3/' + 'e' * 32, expires_in=300)
            self.assertEqual(authed_client(self.lead).get(self.url()).status_code, 200)

    def test_another_mentors_student_an_ended_assignment_or_no_upload_is_404(self):
        with patch(self.SIGN, return_value='https://storage.test/m'):
            self.assertEqual(self.client_for(mentoring._login(self.faizal)).get(self.url()).status_code, 404)
            self.assertEqual(self.client_for().get(self.url(pk=self.theirs.id)).status_code, 404)
            self.assertEqual(self.client_for().get(self.url(mid=NO_ROW)).status_code, 404)
            MentorAssignment.objects.filter(application=self.app, ended_at__isnull=True).update(
                ended_at=timezone.now())
            self.assertEqual(self.client_for().get(self.url()).status_code, 404)
