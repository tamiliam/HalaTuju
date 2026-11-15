"""Sprint TD-631 (2026-11-15): Surveys, Development and Announcements — a `.view` key opens the reads, only the
`.edit` key opens the writes.

The owner's rule (2026-11-15): "there is admin, and there are permissions, which determine what the admin views
and edits." The web now opens these three screens (and the scholar file's Surveys and Growth tabs) on their read
door (`surveys_read`, `development_read`, `announcements_read`) and offers New / Edit / Delete / Close / Remind /
Archive / Withdraw / Mark reviewed only on the `.edit` door. This file pins the server half the web relies on,
through the real endpoints, for a person whose ROLE opens nothing (a reviewer) so only the keys can answer:

- every GET those screens call answers a `.view`-only holder (never 403);
- every write refuses that holder (403) and calls nothing;
- the same role WITH the `.edit` key may write (so the refusal is the key, not the label).
"""
import datetime

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import development, surveys
from apps.scholarship.models import Announcement, DevelopmentModule, Survey
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
)

API = '/api/v1/admin/scholarship/'
HOUR = datetime.timedelta(hours=1)
DAY = datetime.timedelta(days=1)
VIEW_KEYS = ['scholars', 'surveys.view', 'development.view', 'announcements.view']
EDIT_KEYS = [*VIEW_KEYS, 'surveys.edit', 'development.edit', 'announcements.edit']


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        gift = make_programme(name_en='Flagship 2026')
        cls.org = gift.organisation
        cls.app = make_application('maintenance', cohort=make_cohort(programme=gift),
                                   active_at=timezone.now() - 90 * DAY)
        now = timezone.now()
        cls.survey = Survey.objects.create(organisation=cls.org, title='Check-in', status='published',
                                           opens_at=now - HOUR, closes_at=now + 10 * DAY)
        surveys._replace_questions(cls.survey, surveys.clean_questions(
            [{'kind': 'yes_no', 'text': 'Are you in a hostel?'}]))
        cls.module = DevelopmentModule.objects.create(
            organisation=cls.org, title='Money', status='published', publish_at=now - HOUR,
            task_kind='reflection', task_prompt='Make a budget.')
        development._apply_lessons(cls.module, development.clean_lessons([{'title': 'Where', 'body': 'Write.'}]))
        cls.lesson = cls.module.lessons.first()
        cls.news = Announcement.objects.create(organisation=cls.org, title='Results', body='Upload.',
                                               status='draft')
        cls.viewer = make_admin('reviewer', owning_org=cls.org, permissions=VIEW_KEYS)
        cls.editor = make_admin('reviewer', owning_org=cls.org, permissions=EDIT_KEYS)
        cls.nobody = make_admin('reviewer', owning_org=cls.org, permissions=['scholars'])

    def call(self, who, method, path, body=None):
        return getattr(authed_client(who), method)(API + path, body or {}, format='json')


class ReadsAnswerTheViewKey(_Base):
    """Every GET the screens and tabs call: a `.view`-only holder passes the gate. A 404 here is the row's own
    answer (no uploaded file), past the gate; only 403 would be the key refused."""

    def reads(self):
        s, m, a, lid = self.survey.id, self.module.id, self.app.id, self.lesson.id
        return [
            ('surveys/', 200), (f'surveys/{s}/results/', 200), (f'surveys/{s}/csv/', 200),
            (f'scholars/{a}/surveys/', 200),
            ('development/', 200), (f'development/{m}/progress/', 200), (f'development/{m}/csv/', 200),
            (f'development/{m}/progress/{a}/file/', 404), (f'development/{m}/lessons/{lid}/file/', 404),
            (f'scholars/{a}/development/', 200), (f'scholars/{a}/development/{m}/file/', 404),
            ('announcements/', 200),
        ]

    def test_a_view_only_holder_reads_every_screen(self):
        for path, code in self.reads():
            with self.subTest(path=path):
                self.assertEqual(self.call(self.viewer, 'get', path).status_code, code)

    def test_without_the_view_key_every_read_is_refused(self):
        # The scholar tabs keep the file's own fence (`scholars`), held here, so the 403 is the page key.
        for path, _ in self.reads():
            with self.subTest(path=path):
                self.assertEqual(self.call(self.nobody, 'get', path).status_code, 403)


class WritesNeedTheEditKey(_Base):
    def writes(self):
        s, m, a, lid, n = self.survey.id, self.module.id, self.app.id, self.lesson.id, self.news.id
        return [
            ('post', 'surveys/'), ('patch', f'surveys/{s}/'), ('delete', f'surveys/{s}/'),
            ('post', f'surveys/{s}/close/'), ('post', f'surveys/{s}/remind/'),
            ('post', 'development/'), ('patch', f'development/{m}/'), ('delete', f'development/{m}/'),
            ('post', f'development/{m}/archive/'), ('post', f'development/{m}/remind/'),
            ('post', f'development/{m}/progress/{a}/review/'),
            ('post', f'development/{m}/lessons/{lid}/file/'), ('delete', f'development/{m}/lessons/{lid}/file/'),
            ('post', f'development/{m}/lessons/{lid}/file/sign/'),
            ('post', 'announcements/'), ('patch', f'announcements/{n}/'), ('delete', f'announcements/{n}/'),
            ('post', f'announcements/{n}/withdraw/'),
        ]

    def test_a_view_only_holder_is_refused_every_write_and_nothing_changes(self):
        for method, path in self.writes():
            with self.subTest(method=method, path=path):
                self.assertEqual(self.call(self.viewer, method, path, {'title': 'Changed'}).status_code, 403)
        self.assertEqual(Survey.objects.get(pk=self.survey.pk).status, 'published')
        self.assertEqual(Survey.objects.filter(organisation=self.org).count(), 1)
        self.assertEqual(DevelopmentModule.objects.get(pk=self.module.pk).status, 'published')
        self.assertEqual(Announcement.objects.get(pk=self.news.pk).title, 'Results')

    def test_the_same_role_with_the_edit_key_may_write(self):
        # Nobody has answered, started or been sent anything, so each delete is allowed by its own rule.
        for kind, path in (('survey', f'surveys/{self.survey.id}/'), ('module', f'development/{self.module.id}/'),
                           ('announcement', f'announcements/{self.news.id}/')):
            with self.subTest(kind=kind):
                self.assertEqual(self.call(self.editor, 'delete', path).status_code, 204)
        self.assertFalse(Survey.objects.filter(pk=self.survey.pk).exists())
        self.assertFalse(DevelopmentModule.objects.filter(pk=self.module.pk).exists())
        self.assertFalse(Announcement.objects.filter(pk=self.news.pk).exists())
