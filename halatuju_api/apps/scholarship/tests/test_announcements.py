"""Student maintenance S8 (2026-11-01): announcements — every door into "a scholar sees it", every staff door,
and the hourly email.

Doors, each driven through the real endpoints (or the job's real command):

- WHO SEES ONE: published only (never a draft, a scheduled one before its time, a withdrawn one); a scheduled
  one past its time WITHOUT the job having run; the same organisation; the audience (everyone / the scholar's
  own gift, by the application's gift OR its round's); a file in maintenance, or closed AFTER it went out;
  never another organisation's scholar, a student who is not a scholar, a sponsor, a partner or a source.
- HER TAB: the unread count matches; mark-read only for what she may see (a guessed id is ignored); idempotent.
- STAFF: super / org_admin / admin post; every other role is refused; another organisation is 404; delete
  only a draft or a scheduled one; an edit after publishing changes text and pin only, stamps "edited";
  withdraw only a published one; a super with no organisation names a gift.
- THE EMAIL: switch off -> nobody, recorded, never later; no address; two runs -> once each; metered once
  each; an edit never re-emails; a withdraw stops the rest; scheduled -> sent once out; closed / other
  organisation never.
"""
import datetime
import json
import pathlib
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import announcements, student_email_catalogue
from apps.scholarship.models import (
    Announcement, AnnouncementEmail, AnnouncementRead, StudentEmailLog, UsageEvent,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme, make_student,
)

STAFF = '/api/v1/admin/scholarship/announcements/'
NEWS = '/api/v1/scholarship/bursary/news/'
SUMMARY = '/api/v1/scholarship/bursary/summary/'
LOCMEM = override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
HOUR = datetime.timedelta(hours=1)


def _scholar(cohort=None, **over):
    return make_application('maintenance', cohort=cohort, active_at=timezone.now() - datetime.timedelta(days=90),
                            **over)


def _post(org, title='Results are due', **kw):
    kw.setdefault('body', 'Upload your slip by 15 December.')
    kw.setdefault('status', 'published')
    if kw['status'] == 'published':
        kw.setdefault('published_at', timezone.now() - HOUR)
    return Announcement.objects.create(organisation=org, title=title, **kw)


def _run_job():
    out = StringIO()
    call_command('send_announcement_emails', stdout=out)
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

    def news(self, student=None):
        return authed_client((student or self.student).supabase_user_id).get(NEWS)

    def ids(self, student=None):
        r = self.news(student)
        self.assertEqual(r.status_code, 200, r.content)
        return [a['id'] for a in r.json()['announcements']]

    def create(self, caller=None, **body):
        body.setdefault('title', 'Career talk')
        body.setdefault('body', 'Join us at 8 pm: https://meet.example/brightpath')
        body.setdefault('action', 'publish')
        return authed_client(caller or self.org_admin).post(STAFF, body, format='json')


class TestWhoSeesIt(_Base):
    def test_only_a_live_one_of_her_organisation_and_audience(self):
        now = timezone.now()
        everyone = _post(self.org, 'Everyone')
        mine = _post(self.org, 'Mine', programme=self.gift_a)
        theirs = _post(self.org, 'Their gift', programme=self.gift_b)
        _post(self.org, 'Draft', status='draft')
        _post(self.org, 'Later', status='scheduled', publish_at=now + HOUR)
        due = _post(self.org, 'Due', status='scheduled', publish_at=now - HOUR)   # the job has NOT run
        _post(self.org, 'Gone', withdrawn_at=now)
        Announcement.objects.filter(title='Gone').update(status='withdrawn')
        _post(_scholar().owning_organisation, 'Elsewhere')
        self.assertEqual(set(self.ids()), {everyone.id, mine.id, due.id})
        self.assertNotIn(theirs.id, self.ids())
        self.assertEqual(set(self.ids(self.other.profile)), {everyone.id, theirs.id, due.id})

    def test_the_gift_reaches_through_the_round_as_the_applications_rule_does(self):
        mine = _post(self.org, 'Mine', programme=self.gift_a)
        # `programme` is set once; a round moved to another gift keeps the old one on the application.
        type(self.app).objects.filter(pk=self.app.pk).update(programme=self.gift_b)
        self.assertIn(mine.id, self.ids())

    def test_pinned_first_then_newest(self):
        old_pin = _post(self.org, 'Pinned', pinned=True, published_at=timezone.now() - 10 * HOUR)
        newest = _post(self.org, 'Newest', published_at=timezone.now() - HOUR)
        older = _post(self.org, 'Older', published_at=timezone.now() - 5 * HOUR)
        self.assertEqual(self.ids(), [old_pin.id, newest.id, older.id])

    def test_a_closed_file_keeps_only_what_went_out_before_it_closed(self):
        before = _post(self.org, 'Before', published_at=timezone.now() - 48 * HOUR)
        closed = make_application('closed', cohort=make_cohort(programme=self.gift_a),
                                  active_at=timezone.now() - datetime.timedelta(days=200),
                                  closed_at=timezone.now() - 24 * HOUR)
        after = _post(self.org, 'After')
        got = self.ids(closed.profile)
        self.assertIn(before.id, got)
        self.assertNotIn(after.id, got)

    def test_a_student_who_is_not_a_scholar_has_no_news(self):
        _post(self.org)
        applicant = make_application('submitted', cohort=make_cohort(programme=self.gift_a))
        self.assertEqual(self.news(applicant.profile).status_code, 404)

    def test_the_payload_is_an_allowlist(self):
        a = _post(self.org, created_by_email='siti@example.test', email_requested=True, edited_at=timezone.now())
        item = self.news().json()['announcements'][0]
        self.assertEqual(set(item), {'id', 'title', 'body', 'pinned', 'published_at', 'edited_at', 'new'})
        self.assertNotIn('siti@example.test', json.dumps(self.news().json()))
        self.assertEqual(item['id'], a.id)


class TestHerTab(_Base):
    def test_summary_shows_the_tab_and_the_unread_count(self):
        body = authed_client(self.student.supabase_user_id).get(SUMMARY).json()
        self.assertEqual((body['news_tab'], body['news_unread']), (False, 0))
        a, b = _post(self.org, 'A'), _post(self.org, 'B')
        body = authed_client(self.student.supabase_user_id).get(SUMMARY).json()
        self.assertEqual((body['news_tab'], body['news_unread']), (True, 2))
        r = authed_client(self.student.supabase_user_id).post(NEWS + 'read/', {'ids': [a.id]}, format='json')
        self.assertEqual(r.json(), {'marked': 1, 'unread': 1})
        self.assertEqual([x['new'] for x in self.news().json()['announcements'] if x['id'] in (a.id, b.id)],
                         [True, False])   # newest (b) first: still new; a was read
        self.assertEqual(authed_client(self.student.supabase_user_id).get(SUMMARY).json()['news_unread'], 1)

    def test_mark_read_ignores_what_she_cannot_see_and_is_idempotent(self):
        mine = _post(self.org)
        draft = _post(self.org, 'Draft', status='draft')
        theirs = _post(self.org, 'Theirs', programme=self.gift_b)
        foreign = _post(_scholar().owning_organisation, 'Foreign')
        client = authed_client(self.student.supabase_user_id)
        for _ in range(2):
            r = client.post(NEWS + 'read/', {'ids': [mine.id, draft.id, theirs.id, foreign.id, 999999]}, format='json')
            self.assertEqual(r.status_code, 200)
        self.assertEqual(list(AnnouncementRead.objects.values_list('announcement_id', 'application_id')),
                         [(mine.id, self.app.id)])
        self.assertEqual(client.post(NEWS + 'read/', {'ids': 'all'}, format='json').status_code, 400)


class TestStaffDoors(_Base):
    def test_org_admin_admin_and_super_post_everyone_else_is_refused(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create(self.officer).status_code, 201)
        sup = make_admin('super', super_admin=True, owning_org=self.org)
        self.assertEqual(self.create(sup).status_code, 201)
        reviewer = make_admin('reviewer', owning_org=self.org)
        for who in (reviewer, make_admin('qc', owning_org=self.org), make_admin('finance', owning_org=self.org),
                    make_admin('source_partner', owning_org=self.org), make_admin('mentor', owning_org=self.org),
                    make_admin('partner', owning_org=self.org)):
            with self.subTest(role=who.role):
                self.assertEqual(authed_client(who).get(STAFF).status_code, 403)
                self.assertEqual(self.create(who).status_code, 403)
        self.assertEqual(Announcement.objects.count(), 3)

    def test_another_organisation_is_404_everywhere(self):
        a = _post(self.org)
        draft = _post(self.org, 'Draft', status='draft')
        stranger = make_admin('org_admin', owning_org=_scholar().owning_organisation)
        c = authed_client(stranger)
        self.assertEqual(c.patch(f'{STAFF}{a.id}/', {'title': 'X'}, format='json').status_code, 404)
        self.assertEqual(c.post(f'{STAFF}{a.id}/withdraw/').status_code, 404)
        self.assertEqual(c.delete(f'{STAFF}{draft.id}/').status_code, 404)
        self.assertEqual(c.get(STAFF, {'programme': self.gift_a.code}).status_code, 404)
        # Another organisation's gift as the audience reads exactly like an unknown code.
        r = self.create(stranger, programme=self.gift_a.code)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_audience'))
        self.assertNotIn(a.id, [r['id'] for r in c.get(STAFF).json()['announcements']])

    def test_a_super_without_an_organisation_names_a_gift(self):
        sup = make_admin('super', super_admin=True)
        self.assertEqual(authed_client(sup).get(STAFF).json()['code'], 'programme_required')
        r = authed_client(sup).get(STAFF, {'programme': self.gift_a.code})
        self.assertEqual(r.json()['organisation']['code'], self.org.code)

    def test_the_list_counts_reads_and_the_audience(self):
        r = self.create(programme=self.gift_a.code)
        self.assertEqual(r.status_code, 201, r.content)
        row = r.json()
        self.assertEqual((row['status'], row['audience_count'], row['read_count'], row['programme']['code']),
                         ('published', 1, 0, self.gift_a.code))
        authed_client(self.student.supabase_user_id).post(NEWS + 'read/', {'ids': [row['id']]}, format='json')
        body = authed_client(self.org_admin).get(STAFF).json()
        self.assertEqual(body['announcements'][0]['read_count'], 1)
        self.assertEqual(body['counts'], {'published': 1, 'scheduled': 0, 'draft': 0, 'withdrawn': 0})
        self.assertEqual([(a['programme'], a['count']) for a in body['audiences']],
                         [(None, 2), (self.gift_a.code, 1), (self.gift_b.code, 1)])
        self.assertEqual(body['announcements'][0]['author']['email'], self.org_admin.email)

    def test_validation(self):
        cases = {'title_required': {'title': '  '}, 'title_too_long': {'title': 'x' * 151},
                 'title_newline': {'title': 'a\nb'}, 'body_required': {'body': ''},
                 'body_too_long': {'body': 'x' * 5001}, 'bad_audience': {'programme': 'nope'},
                 'bad_action': {'action': 'shout'}, 'bad_publish_at': {'action': 'schedule', 'publish_at': 'soon'},
                 'publish_at_past': {'action': 'schedule',
                                     'publish_at': (timezone.now() - HOUR).isoformat()}}
        for code, body in cases.items():
            with self.subTest(code=code):
                r = self.create(**body)
                self.assertEqual((r.status_code, r.json()['code']), (400, code))
        self.assertEqual(Announcement.objects.count(), 0)

    def test_schedule_draft_then_publish_and_delete(self):
        when = (timezone.now() + 2 * HOUR).isoformat()
        r = self.create(action='schedule', publish_at=when)
        self.assertEqual(r.json()['status'], 'scheduled')
        sid = r.json()['id']
        self.assertNotIn(sid, self.ids())
        d = self.create(action='draft').json()
        c = authed_client(self.org_admin)
        self.assertEqual(c.patch(f'{STAFF}{d["id"]}/', {'action': 'publish'}, format='json').json()['status'], 'published')
        self.assertIn(d['id'], self.ids())
        self.assertEqual(c.delete(f'{STAFF}{sid}/').status_code, 204)
        r = c.delete(f'{STAFF}{d["id"]}/')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'withdraw_instead'))

    def test_a_scheduled_one_past_its_time_is_out_for_staff_too(self):
        a = _post(self.org, status='scheduled', publish_at=timezone.now() - HOUR, published_at=None)
        c = authed_client(self.org_admin)
        self.assertEqual(c.delete(f'{STAFF}{a.id}/').json()['code'], 'withdraw_instead')
        self.assertEqual(c.get(STAFF).json()['announcements'][0]['status'], 'published')

    def test_edit_after_publishing_changes_text_and_pin_only(self):
        a = self.create().json()
        c = authed_client(self.org_admin)
        r = c.patch(f'{STAFF}{a["id"]}/', {'title': 'Career talk moved', 'pinned': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['edited_at'] and r.json()['pinned'])
        for body in ({'programme': self.gift_b.code}, {'email': True}, {'action': 'draft'},
                     {'publish_at': (timezone.now() + HOUR).isoformat()}):
            with self.subTest(body=body):
                r = c.patch(f'{STAFF}{a["id"]}/', {'title': 'Y', **body}, format='json')
                self.assertEqual((r.status_code, r.json()['code']), (409, 'published_locked'))
        self.assertEqual(Announcement.objects.get(pk=a['id']).title, 'Career talk moved')
        # Sending the unchanged values is not a change.
        r = c.patch(f'{STAFF}{a["id"]}/', {'body': 'New text', 'programme': None, 'email': False}, format='json')
        self.assertEqual(r.status_code, 200)
        news = self.news().json()['announcements'][0]
        self.assertEqual((news['title'], news['body'], bool(news['edited_at'])), ('Career talk moved', 'New text', True))

    def test_withdraw_hides_it_and_is_final(self):
        a = self.create().json()
        draft = self.create(action='draft').json()
        c = authed_client(self.org_admin)
        self.assertEqual(c.post(f'{STAFF}{draft["id"]}/withdraw/').json()['code'], 'not_published')
        r = c.post(f'{STAFF}{a["id"]}/withdraw/')
        self.assertEqual(r.json()['status'], 'withdrawn')
        self.assertNotIn(a['id'], self.ids())
        self.assertEqual(c.patch(f'{STAFF}{a["id"]}/', {'title': 'Z'}, format='json').json()['code'], 'withdrawn')
        self.assertEqual(c.delete(f'{STAFF}{a["id"]}/').json()['code'], 'withdraw_instead')
        self.assertTrue(Announcement.objects.filter(pk=a['id']).exists())


class TestTheEmail(_Base):
    def setUp(self):
        super().setUp()
        self.third = _scholar(make_cohort(programme=self.gift_a))

    def test_once_per_scholar_metered_and_logged_even_when_run_twice(self):
        a = _post(self.org, email_requested=True)
        _run_job()
        _run_job()
        self.assertEqual(sorted(m.to[0] for m in mail.outbox),
                         sorted([self.app.notify_email, self.other.notify_email, self.third.notify_email]))
        letter = next(m for m in mail.outbox if m.to == [self.app.notify_email])
        self.assertIn('Results are due', letter.subject)
        self.assertIn('Upload your slip by 15 December.', letter.body)
        self.assertIn('/scholarship/bursary?tab=news', letter.body)
        self.assertEqual(AnnouncementEmail.objects.filter(announcement=a, outcome='sent').count(), 3)
        self.assertEqual(UsageEvent.objects.filter(source='send_student_email').count(), 3)
        self.assertEqual(StudentEmailLog.objects.filter(key='announcement', ok=True).count(), 3)
        a.refresh_from_db()
        self.assertIsNotNone(a.emailed_at)
        row = authed_client(self.org_admin).get(STAFF).json()['announcements'][0]
        self.assertEqual(row['emailed_count'], 3)

    def test_only_its_audience_never_closed_or_another_organisation(self):
        _post(self.org, email_requested=True, programme=self.gift_a)
        make_application('closed', cohort=make_cohort(programme=self.gift_a),
                         active_at=timezone.now() - datetime.timedelta(days=200))
        _scholar()   # another organisation
        _run_job()
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([self.app.notify_email, self.third.notify_email]))

    def test_not_asked_draft_or_future_sends_nothing(self):
        _post(self.org)
        _post(self.org, 'Draft', status='draft', email_requested=True)
        _post(self.org, 'Later', status='scheduled', publish_at=timezone.now() + HOUR, email_requested=True,
              published_at=None)
        _run_job()
        self.assertEqual(mail.outbox, [])

    def test_a_scheduled_one_is_emailed_once_it_is_out(self):
        a = _post(self.org, status='scheduled', publish_at=timezone.now() - HOUR, published_at=None,
                  email_requested=True)
        _run_job()
        a.refresh_from_db()
        self.assertEqual((a.status, a.published_at), ('published', a.publish_at))
        self.assertEqual(len(mail.outbox), 3)

    def test_switched_off_nobody_is_emailed_and_never_later(self):
        a = _post(self.org, email_requested=True)
        student_email_catalogue.set_switch(self.org, 'announcement', False)
        _run_job()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(AnnouncementEmail.objects.filter(announcement=a, outcome='switched_off').count(), 3)
        student_email_catalogue.set_switch(self.org, 'announcement', True)
        _run_job()
        self.assertEqual(mail.outbox, [])
        row = authed_client(self.org_admin).get(STAFF).json()
        self.assertTrue(row['announcements'][0]['email_switched_off'])
        self.assertTrue(row['email_switch_on'])

    def test_a_scholar_without_an_address_is_recorded_and_the_rest_go(self):
        type(self.app).objects.filter(pk=self.app.pk).update(notify_email='')
        a = _post(self.org, email_requested=True)
        _run_job()
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(AnnouncementEmail.objects.get(announcement=a, application=self.app).outcome, 'no_address')

    def test_an_edit_never_emails_again(self):
        a = self.create(email=True).json()
        _run_job()
        self.assertEqual(len(mail.outbox), 3)
        authed_client(self.org_admin).patch(f'{STAFF}{a["id"]}/', {'body': 'Corrected.'}, format='json')
        _run_job()
        self.assertEqual(len(mail.outbox), 3)

    def test_a_withdraw_stops_the_scholars_not_yet_reached(self):
        a = _post(self.org, email_requested=True)
        real = __import__('apps.scholarship.student_comms', fromlist=['x']).send_student_email

        def send_then_withdraw(app, kind, **values):
            ok = real(app, kind, **values)
            Announcement.objects.filter(pk=a.pk).update(status='withdrawn', withdrawn_at=timezone.now())
            return ok
        with patch('apps.scholarship.student_comms.send_student_email', side_effect=send_then_withdraw):
            _run_job()
        self.assertEqual(len(mail.outbox), 1)
        _run_job()
        self.assertEqual(len(mail.outbox), 1)

    def test_withdrawn_before_the_job_sends_nothing(self):
        a = self.create(email=True).json()
        authed_client(self.org_admin).post(f'{STAFF}{a["id"]}/withdraw/')
        _run_job()
        self.assertEqual(mail.outbox, [])

    def test_the_job_is_registered_and_watched(self):
        from apps.scholarship.cron_health import EXPECTED_CADENCE, HOURLY
        from apps.scholarship.views import CronRunView
        self.assertEqual(CronRunView.JOBS['announcement-emails'], 'send_announcement_emails')
        self.assertEqual(EXPECTED_CADENCE['announcement-emails'], HOURLY)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, SPONSOR_POOL_ENABLED=True)
class TestNeverASponsorPartnerOrSourceReader(_Base):
    def test_the_sponsors_own_student_and_the_partners_student_carry_nothing(self):
        from apps.courses.serializers_admin import PartnerStudentDetailSerializer
        from apps.scholarship.models import Sponsor, Sponsorship
        _post(self.org, 'SECRET NEWS TITLE', body='SECRET NEWS BODY')
        sponsor = Sponsor.objects.create(supabase_user_id='spon-mine', email='s@example.test', name='S',
                                         phone='0123', source='friend', consent_at=timezone.now(), status='approved')
        Sponsorship.objects.create(sponsor=sponsor, application=self.app, amount=Decimal('2000'), status='active')
        r = authed_client('spon-mine').get(f'/api/v1/sponsor/my-students/{self.app.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        partner = json.dumps(PartnerStudentDetailSerializer(self.app.profile).data, default=str)
        for text in (json.dumps(r.json()), partner):
            for needle in ('SECRET NEWS', 'announcement'):
                self.assertNotIn(needle, text)

    def test_no_sponsor_partner_or_source_module_reads_announcements(self):
        root = pathlib.Path(announcements.__file__).parent
        for rel in ('views_sponsor.py', 'spend_sponsor.py', 'sponsor_feed.py', 'sponsor_notify.py',
                    'sponsor_comms.py', 'partner_comms.py', 'partner_notify.py', 'source_console.py',
                    'views_admin/source_console.py', 'views_admin/sponsors.py', 'views_admin/sources.py',
                    'pool.py'):
            path = root / rel
            if not path.exists():
                continue
            with self.subTest(module=rel):
                text = path.read_text(encoding='utf-8')
                for needle in ('Announcement', 'announcement_reads', 'import announcements', 'from .announcements',
                               'from ..announcements'):
                    self.assertNotIn(needle, text)
