"""Tests for in-app interview scheduling (propose → book → reschedule → cancel),
the reminder cron, the booking emails, and endpoint permissions.

Google Meet is mocked everywhere (``apps.scholarship.meeting.create_event`` etc.) —
never a live Google call in CI.
"""
from datetime import timedelta
from unittest.mock import patch

import jwt
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import scheduling
from apps.scholarship.models import InterviewSlot, ReviewerProfile, ScholarshipApplication, ScholarshipCohort

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(INTERVIEW_SCHEDULING_ENABLED=True)
class SchedulingServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Rohini', email='rohini@example.com')
        cls.other_reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev2-uid', role='reviewer', is_active=True,
            name='Bala', email='bala@example.com')
        cls.viewer = PartnerAdmin.objects.create(
            supabase_user_id='view-uid', role='admin', is_active=True,
            name='Viewer', email='viewer@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud', nric='030101-14-1234', name='Priya')

    def setUp(self):
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='interviewing',
            notify_email='priya@example.com', assigned_to=self.reviewer)

    def _future(self, **kw):
        return timezone.now() + timedelta(**kw)

    # ── propose ──────────────────────────────────────────────────────────────
    def test_propose_creates_active_slots(self):
        slots = scheduling.propose_slots(
            self.app, reviewer=self.reviewer,
            starts=[self._future(days=3), self._future(days=4)])
        self.assertEqual(len(slots), 2)
        self.assertEqual(InterviewSlot.objects.filter(application=self.app, is_active=True).count(), 2)

    def test_propose_emails_student_to_pick_a_time(self):
        # Proposing times must notify the student to come book — otherwise the in-app
        # scheduler is invisible to them (runs parallel to the assignment email).
        mail.outbox.clear()
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['priya@example.com'])
        self.assertIn('ready to pick', msg.subject)
        self.assertIn('/scholarship/application', msg.body)
        self.assertIn('Rohini', msg.body)   # the reviewer's name

    def test_propose_rejects_unassigned_reviewer(self):
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.propose_slots(self.app, reviewer=self.other_reviewer,
                                     starts=[self._future(days=3)])
        self.assertEqual(str(cm.exception), 'not_assigned')

    def test_propose_rejects_non_reviewer(self):
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.propose_slots(self.app, reviewer=self.viewer,
                                     starts=[self._future(days=3)])
        self.assertEqual(str(cm.exception), 'not_reviewer')

    def test_propose_drops_past_times_and_needs_one_future(self):
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                     starts=[self._future(days=-1)])
        self.assertEqual(str(cm.exception), 'no_future_slots')

    def test_slot_in_window_rule(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        myt = ZoneInfo('Asia/Kuala_Lumpur')
        def at(h, m):
            return datetime(2026, 6, 22, h, m, tzinfo=myt)
        # in-window, on 30-min boundary
        self.assertTrue(scheduling.slot_in_window(at(8, 0)))
        self.assertTrue(scheduling.slot_in_window(at(9, 30)))
        self.assertTrue(scheduling.slot_in_window(at(21, 30)))
        # off-boundary minutes
        self.assertFalse(scheduling.slot_in_window(at(9, 15)))
        # outside the 08:00–21:30 window
        self.assertFalse(scheduling.slot_in_window(at(7, 30)))
        self.assertFalse(scheduling.slot_in_window(at(22, 0)))

    def test_reproposing_withdraws_old_unbooked_slots(self):
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=3)])
        scheduling.propose_slots(self.app, reviewer=self.reviewer, starts=[self._future(days=5)])
        active = InterviewSlot.objects.filter(application=self.app, is_active=True)
        self.assertEqual(active.count(), 1)

    # ── book ─────────────────────────────────────────────────────────────────
    @patch('apps.scholarship.meeting.create_event',
           return_value={'url': 'https://meet.google.com/abc-defg-hij', 'event_id': 'evt-1'})
    def test_book_sets_state_meet_and_emails(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[self._future(days=3)])[0]
        mail.outbox.clear()
        scheduling.book_slot(self.app, slot_id=slot.id)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'booked')
        self.assertEqual(self.app.interview_slot_id, slot.id)
        self.assertEqual(self.app.interview_meeting_url, 'https://meet.google.com/abc-defg-hij')
        self.assertEqual(self.app.interview_meeting_provider, 'google_meet')
        self.assertEqual(self.app.interview_calendar_event_id, 'evt-1')
        self.assertIsNotNone(self.app.interview_confirmation_sent_at)
        # student + reviewer confirmations
        self.assertEqual(len(mail.outbox), 2)

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_book_without_meet_still_succeeds(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[self._future(days=3)])[0]
        scheduling.book_slot(self.app, slot_id=slot.id)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'booked')
        self.assertEqual(self.app.interview_meeting_url, '')

    def test_book_bad_slot(self):
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.book_slot(self.app, slot_id=999999)
        self.assertEqual(str(cm.exception), 'bad_slot')

    def test_book_past_slot(self):
        slot = InterviewSlot.objects.create(
            application=self.app, reviewer=self.reviewer, start=self._future(days=-1))
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.book_slot(self.app, slot_id=slot.id)
        self.assertEqual(str(cm.exception), 'past_slot')

    # ── reschedule ───────────────────────────────────────────────────────────
    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_reschedule_within_cutoff_ok(self, _mock):
        slots = scheduling.propose_slots(
            self.app, reviewer=self.reviewer,
            starts=[self._future(days=5), self._future(days=6)])
        scheduling.book_slot(self.app, slot_id=slots[0].id)
        scheduling.book_slot(self.app, slot_id=slots[1].id)  # reschedule
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_slot_id, slots[1].id)

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_reschedule_too_late(self, _mock):
        slots = scheduling.propose_slots(
            self.app, reviewer=self.reviewer,
            starts=[self._future(hours=2), self._future(days=6)])
        scheduling.book_slot(self.app, slot_id=slots[0].id)  # booked 2h out (inside 12h cutoff)
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.book_slot(self.app, slot_id=slots[1].id)
        self.assertEqual(str(cm.exception), 'too_late')

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_reschedule_resets_reminder_stamps(self, _mock):
        slots = scheduling.propose_slots(
            self.app, reviewer=self.reviewer,
            starts=[self._future(days=5), self._future(days=6)])
        scheduling.book_slot(self.app, slot_id=slots[0].id)
        self.app.interview_reminded_1d_at = timezone.now()
        self.app.save(update_fields=['interview_reminded_1d_at'])
        scheduling.book_slot(self.app, slot_id=slots[1].id)
        self.app.refresh_from_db()
        self.assertIsNone(self.app.interview_reminded_1d_at)

    # ── cancel ───────────────────────────────────────────────────────────────
    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_cancel_ok_and_notifies(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[self._future(days=5)])[0]
        scheduling.book_slot(self.app, slot_id=slot.id)
        mail.outbox.clear()
        scheduling.cancel(self.app, by='student')
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'cancelled')
        self.assertEqual(self.app.interview_meeting_url, '')
        self.assertEqual(len(mail.outbox), 2)  # student + reviewer

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_cancel_too_late_for_student(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[self._future(hours=2)])[0]
        scheduling.book_slot(self.app, slot_id=slot.id)
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.cancel(self.app, by='student')
        self.assertEqual(str(cm.exception), 'too_late')

    def test_cancel_when_not_booked(self):
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.cancel(self.app, by='student')
        self.assertEqual(str(cm.exception), 'not_booked')


@override_settings(INTERVIEW_SCHEDULING_ENABLED=True)
class ReminderCronTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Rohini', email='rohini@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud', nric='030101-14-1234', name='Priya')

    def _booked_app(self, start):
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='interviewing',
            notify_email='priya@example.com', assigned_to=self.reviewer,
            interview_status='booked', interview_start=start)

    def test_one_day_reminder_fires_once(self):
        app = self._booked_app(timezone.now() + timedelta(hours=20))
        mail.outbox.clear()
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNotNone(app.interview_reminded_1d_at)
        self.assertEqual(len(mail.outbox), 2)  # student + reviewer
        # idempotent: a second run sends nothing new
        mail.outbox.clear()
        call_command('send_interview_reminders')
        self.assertEqual(len(mail.outbox), 0)

    def test_one_hour_reminder_fires(self):
        app = self._booked_app(timezone.now() + timedelta(minutes=30))
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNotNone(app.interview_reminded_1h_at)
        self.assertIsNotNone(app.interview_reminded_1d_at)  # also within 24h

    def test_no_reminder_far_out(self):
        app = self._booked_app(timezone.now() + timedelta(days=3))
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNone(app.interview_reminded_1d_at)

    @override_settings(INTERVIEW_SCHEDULING_ENABLED=False)
    def test_inert_when_flag_off(self):
        app = self._booked_app(timezone.now() + timedelta(hours=20))
        call_command('send_interview_reminders')
        app.refresh_from_db()
        self.assertIsNone(app.interview_reminded_1d_at)


class BookingEmailTests(TestCase):
    def test_booked_email_bilingual_interviewer_term(self):
        start = timezone.now() + timedelta(days=2)
        from apps.scholarship.emails import send_interview_booked_email
        self.assertTrue(send_interview_booked_email(
            's@example.com', student_name='Priya', reviewer_name='Rohini',
            start=start, meeting_url='https://meet.google.com/abc', reviewer_phone='12-200 0365'))
        body = mail.outbox[-1].body
        self.assertIn('B40 Assistance Programme', body)
        self.assertIn('Program Bantuan B40', body)         # BM block present
        self.assertIn('Interviewer: Rohini', body)         # student-facing term
        self.assertIn('Penemu duga: Rohini', body)         # BM term
        self.assertIn('https://meet.google.com/abc', body)
        self.assertIn('+60 12-200 0365', body)
        self.assertNotIn('Reviewer: Rohini', body)

    def test_reminder_email_when_labels(self):
        from apps.scholarship.emails import send_interview_reminder_email
        start = timezone.now() + timedelta(days=1)
        send_interview_reminder_email('s@example.com', student_name='Priya', start=start, when='1day')
        self.assertIn('tomorrow', mail.outbox[-1].body)
        send_interview_reminder_email('s@example.com', student_name='Priya', start=start, when='1hour')
        self.assertIn('about an hour', mail.outbox[-1].body)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   INTERVIEW_SCHEDULING_ENABLED=True)
class SchedulingEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@example.com')
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Rohini', email='rohini@example.com')
        cls.other_reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev2-uid', role='reviewer', is_active=True,
            name='Bala', email='bala@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud', nric='030101-14-1234', name='Priya')

    def setUp(self):
        self.client = APIClient()
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='interviewing',
            notify_email='priya@example.com', assigned_to=self.reviewer)

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _iso(self, **kw):
        # A valid interview slot: 10:00 MYT on a future day (on-boundary, in-window).
        from zoneinfo import ZoneInfo
        base = (timezone.now() + timedelta(**kw)).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
        return base.replace(hour=10, minute=0, second=0, microsecond=0).isoformat()

    def _propose_url(self):
        return f'/api/v1/admin/scholarship/applications/{self.app.id}/interview-slots/'

    def test_assigned_reviewer_can_propose(self):
        self._auth('rev-uid')
        r = self.client.post(self._propose_url(), {'slots': [self._iso(days=3)]}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['slots']), 1)

    def test_propose_rejects_out_of_window_time(self):
        # 03:00 MYT — outside 08:00–21:30 → 400, no slots created.
        from zoneinfo import ZoneInfo
        self._auth('rev-uid')
        bad = ((timezone.now() + timedelta(days=3)).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
               .replace(hour=3, minute=0, second=0, microsecond=0).isoformat())
        r = self.client.post(self._propose_url(), {'slots': [bad]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'invalid_slot_time')

    def test_propose_rejects_off_boundary_time(self):
        # 10:15 MYT — not on a 30-minute boundary → 400.
        from zoneinfo import ZoneInfo
        self._auth('rev-uid')
        bad = ((timezone.now() + timedelta(days=3)).astimezone(ZoneInfo('Asia/Kuala_Lumpur'))
               .replace(hour=10, minute=15, second=0, microsecond=0).isoformat())
        r = self.client.post(self._propose_url(), {'slots': [bad]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'invalid_slot_time')

    def test_unassigned_reviewer_cannot_propose(self):
        self._auth('rev2-uid')
        r = self.client.post(self._propose_url(), {'slots': [self._iso(days=3)]}, format='json')
        self.assertEqual(r.status_code, 403)

    @override_settings(INTERVIEW_SCHEDULING_ENABLED=False)
    def test_propose_404_when_flag_off(self):
        self._auth('rev-uid')
        r = self.client.post(self._propose_url(), {'slots': [self._iso(days=3)]}, format='json')
        self.assertEqual(r.status_code, 404)

    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_student_books_and_cancels_own(self, _mock):
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[timezone.now() + timedelta(days=5)])[0]
        self._auth('stud')
        r = self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/interview/book/',
            {'slot_id': slot.id}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'booked')
        r2 = self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/interview/cancel/', {}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'cancelled')

    def test_student_cannot_book_others_application(self):
        other_profile = StudentProfile.objects.create(
            supabase_user_id='other', nric='040101-14-9999', name='Other')
        slot = scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                        starts=[timezone.now() + timedelta(days=5)])[0]
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("other")}')
        r = self.client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/interview/book/',
            {'slot_id': slot.id}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_student_get_interview_state(self):
        scheduling.propose_slots(self.app, reviewer=self.reviewer,
                                 starts=[timezone.now() + timedelta(days=5)])
        self._auth('stud')
        r = self.client.get(f'/api/v1/scholarship/applications/{self.app.id}/interview/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['slots']), 1)
