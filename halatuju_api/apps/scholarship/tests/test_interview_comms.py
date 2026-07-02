"""Tests for the 2026-07-02 interview-scheduling follow-ups:

- SLOT RELEASE (TD-151): a booked application's unpicked siblings are released —
  re-offerable to other students (first to book wins), while remaining the original
  student's re-pick menu wherever the time is still free.
- STUDENT → REVIEWER MESSAGES: the always-open channel (no state gate, no cutoff),
  stored + emailed to the assigned reviewer, rate-limited.
"""
from datetime import timedelta

import jwt
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import scheduling
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.serializers_admin import interview_schedule_payload

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            name='Rohini', email='rohini@example.com')
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)
        cls.profile = StudentProfile.objects.create(
            supabase_user_id='stud', nric='030101-14-1234', name='Priya')

    def setUp(self):
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='interviewing',
            notify_email='priya@example.com', assigned_to=self.reviewer)

    def _other_app(self, uid='stud2'):
        p = StudentProfile.objects.create(
            supabase_user_id=uid, nric='800101-14-5678', name='Bala Jr')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status='interviewing',
            notify_email=f'{uid}@example.com', assigned_to=self.reviewer)


@override_settings(INTERVIEW_SCHEDULING_ENABLED=True)
class SlotReleaseTests(_Base):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.t1 = now + timedelta(days=3)
        self.t2 = now + timedelta(days=3, minutes=30)
        self.t3 = now + timedelta(days=3, minutes=60)
        self.slots = scheduling.propose_slots(
            self.app, reviewer=self.reviewer, starts=[self.t1, self.t2, self.t3])

    def test_unbooked_menu_still_blocks_other_proposals(self):
        # Before any booking, all three proposed times hold the reviewer.
        other = self._other_app()
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.propose_slots(other, reviewer=self.reviewer, starts=[self.t2])
        self.assertEqual(str(cm.exception), 'reviewer_conflict')

    def test_booking_releases_siblings_for_other_students(self):
        scheduling.book_slot(self.app, slot_id=self.slots[0].id)      # books t1
        other = self._other_app()
        created = scheduling.propose_slots(other, reviewer=self.reviewer, starts=[self.t2])
        self.assertEqual(len(created), 1)                              # t2 released -> offerable

    def test_booked_time_still_blocks_other_proposals(self):
        scheduling.book_slot(self.app, slot_id=self.slots[0].id)      # books t1
        other = self._other_app()
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.propose_slots(other, reviewer=self.reviewer, starts=[self.t1])
        self.assertEqual(str(cm.exception), 'reviewer_conflict')

    def test_repick_menu_hides_a_reoffered_sibling(self):
        scheduling.book_slot(self.app, slot_id=self.slots[0].id)      # books t1
        other = self._other_app()
        scheduling.propose_slots(other, reviewer=self.reviewer, starts=[self.t2])
        payload = interview_schedule_payload(self.app)
        self.assertEqual(len(payload['slots']), 2)                     # booked t1 + free t3
        ids = {s['id'] for s in payload['slots']}
        self.assertNotIn(self.slots[1].id, ids)                        # t2 hidden

    def test_repick_onto_a_reoffered_time_is_blocked(self):
        scheduling.book_slot(self.app, slot_id=self.slots[0].id)      # books t1
        other = self._other_app()
        scheduling.propose_slots(other, reviewer=self.reviewer, starts=[self.t2])
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.book_slot(self.app, slot_id=self.slots[1].id)  # stale-page re-pick of t2
        self.assertEqual(str(cm.exception), 'reviewer_conflict')

    def test_repick_onto_a_free_sibling_still_works(self):
        scheduling.book_slot(self.app, slot_id=self.slots[0].id)      # books t1
        scheduling.book_slot(self.app, slot_id=self.slots[2].id)      # re-pick t3 (untouched)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_start, self.t3)

    def test_reviewer_busy_excludes_released_siblings(self):
        scheduling.book_slot(self.app, slot_id=self.slots[0].id)      # books t1
        other = self._other_app()
        payload = interview_schedule_payload(other, include_reviewer_busy=True)
        self.assertEqual(payload['reviewer_busy'], [self.t1])          # only the booking holds


@override_settings(INTERVIEW_SCHEDULING_ENABLED=True)
class StudentMessageTests(_Base):
    def test_message_stores_and_emails_reviewer(self):
        mail.outbox.clear()
        msg = scheduling.send_student_message(self.app, text='I might be 10 minutes late.')
        self.assertEqual(msg.text, 'I might be 10 minutes late.')
        self.assertEqual(self.app.interview_messages.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['rohini@example.com'])
        self.assertIn('Message from applicant', sent.subject)
        self.assertIn('I might be 10 minutes late.', sent.body)

    def test_message_allowed_inside_cutoff_one_hour_before(self):
        # The whole point: reschedule/cancel are locked inside the 12h cutoff, but the
        # message channel must stay open — even one hour before the call.
        self.app.interview_status = 'booked'
        self.app.interview_start = timezone.now() + timedelta(hours=1)
        self.app.save(update_fields=['interview_status', 'interview_start'])
        msg = scheduling.send_student_message(self.app, text='Connection is down, joining by phone.')
        self.assertIsNotNone(msg.id)

    def test_message_includes_booked_time_for_reviewer(self):
        self.app.interview_status = 'booked'
        self.app.interview_start = timezone.now() + timedelta(hours=1)
        self.app.save(update_fields=['interview_status', 'interview_start'])
        mail.outbox.clear()
        scheduling.send_student_message(self.app, text='Running late')
        self.assertIn('booked for', mail.outbox[0].body)

    def test_empty_message_rejected(self):
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.send_student_message(self.app, text='   ')
        self.assertEqual(str(cm.exception), 'empty_message')

    def test_message_without_reviewer_rejected(self):
        self.app.assigned_to = None
        self.app.save(update_fields=['assigned_to'])
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.send_student_message(self.app, text='hello?')
        self.assertEqual(str(cm.exception), 'no_reviewer')

    def test_message_rate_limited(self):
        for i in range(scheduling.MESSAGE_RATE_LIMIT_PER_HOUR):
            scheduling.send_student_message(self.app, text=f'msg {i}')
        with self.assertRaises(scheduling.SchedulingError) as cm:
            scheduling.send_student_message(self.app, text='one too many')
        self.assertEqual(str(cm.exception), 'rate_limited')

    def test_message_capped_at_max_len(self):
        msg = scheduling.send_student_message(self.app, text='x' * 5000)
        self.assertEqual(len(msg.text), scheduling.MESSAGE_MAX_LEN)

    def test_messages_in_schedule_payload(self):
        scheduling.send_student_message(self.app, text='first')
        scheduling.send_student_message(self.app, text='second')
        payload = interview_schedule_payload(self.app)
        self.assertEqual([m['text'] for m in payload['messages']], ['first', 'second'])

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_message_endpoint_own_application_only(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("stud")}')
        r = client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/interview/message/',
            {'text': 'hello'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['messages']), 1)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("intruder")}')
        r2 = client.post(
            f'/api/v1/scholarship/applications/{self.app.id}/interview/message/',
            {'text': 'hax'}, format='json')
        # A stranger is denied — 403 from the NRIC gate (no profile) before the view's
        # own-application 404 can even fire. Either way, never a 200.
        self.assertIn(r2.status_code, (403, 404))
