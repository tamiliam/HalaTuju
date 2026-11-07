"""A reviewer RESCHEDULE may offer times inside the organisation's notice (TD-137).

Regression for 2026-11-07: an interviewer moving a booked 1:30 pm interview to later the same day
picked 3, 5 and 6 pm — the web picker offered them (2-hour reschedule floor) but the server checked
the organisation's 24-hour floor regardless, refused with ``too_soon``, and the screen said only
"Could not save". The short floor applies ONLY when the interview is booked; a first proposal sent
with ``reschedule: true`` still meets the full notice.
"""
from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin
from apps.scholarship import scheduling
from apps.scholarship.constants import RESCHEDULE_MIN_LEAD_HOURS, SLOT_MIN_LEAD_HOURS
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
_MYT = ZoneInfo('Asia/Kuala_Lumpur')


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _next_valid_slot(after):
    """The first on-grid, in-window MYT slot (08:00–21:30, 30-min steps) at or after ``after``.

    Within 11 hours of any moment there is one, so ``hours=3`` lands well inside 24 hours —
    the test never depends on the time of day it runs.
    """
    t = after.astimezone(_MYT).replace(second=0, microsecond=0)
    t += timedelta(minutes=(-t.minute) % 30)
    while not (8 * 60 <= t.hour * 60 + t.minute <= 21 * 60 + 30):
        t += timedelta(minutes=30)
    return t


class MeetsMinLeadTests(TestCase):
    def test_reschedule_uses_the_short_floor(self):
        now = timezone.now()
        three_hours = now + timedelta(hours=3)
        self.assertFalse(scheduling.meets_min_lead(three_hours, now))
        self.assertTrue(scheduling.meets_min_lead(three_hours, now, reschedule=True))

    def test_reschedule_still_refuses_inside_the_short_floor(self):
        now = timezone.now()
        self.assertFalse(scheduling.meets_min_lead(now + timedelta(hours=1), now, reschedule=True))

    def test_the_short_floor_is_shorter(self):
        self.assertLess(RESCHEDULE_MIN_LEAD_HOURS, SLOT_MIN_LEAD_HOURS)


@override_settings(INTERVIEW_SCHEDULING_ENABLED=True, SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ReviewerRescheduleLeadEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='c', name='B40', year=2026)
        cls.reviewer = PartnerAdmin.objects.create(
            supabase_user_id='rev-uid', role='reviewer', is_active=True,
            owning_organisation=cls.cohort.owning_organisation, name='Rohini',
            email='rohini@example.com')
        cls.profile = make_student(supabase_user_id='stud', nric='030101-14-1234', name='Priya')

    def setUp(self):
        self.client = APIClient()
        self.app = make_application(
            'interviewing', cohort=self.cohort, student=self.profile,
            notify_email='priya@example.com', assigned_to=self.reviewer)
        self.url = f'/api/v1/admin/scholarship/applications/{self.app.id}/interview-slots/'

    def _as(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _book(self):
        """Reviewer proposes a time four days out; the student books it."""
        far = _next_valid_slot(timezone.now() + timedelta(days=4)).isoformat()
        self._as('rev-uid')
        r = self.client.post(self.url, {'slots': [far]}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self._as('stud')
        r = self.client.post(f'/api/v1/scholarship/applications/{self.app.id}/interview/book/',
                             {'slot_id': r.json()['slots'][0]['id']}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'booked')

    def _near(self, hours):
        return _next_valid_slot(timezone.now() + timedelta(hours=hours)).isoformat()

    @patch('apps.scholarship.meeting.cancel_event', return_value=True)
    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_booked_interview_can_move_to_later_the_same_day(self, _create, _cancel):
        self._book()
        self._as('rev-uid')
        r = self.client.post(self.url, {'slots': [self._near(3)], 'reschedule': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, '')   # booking released, student re-picks

    @patch('apps.scholarship.meeting.cancel_event', return_value=True)
    @patch('apps.scholarship.meeting.create_event', return_value=None)
    def test_reschedule_inside_the_short_floor_is_still_too_soon(self, _create, _cancel):
        self._book()
        self._as('rev-uid')
        soon = (timezone.now() + timedelta(minutes=30)).isoformat()
        r = self.client.post(self.url, {'slots': [soon], 'reschedule': True}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'too_soon')
        self.app.refresh_from_db()
        self.assertEqual(self.app.interview_status, 'booked')   # nothing released

    def test_the_flag_on_an_unbooked_case_does_not_shorten_the_notice(self):
        self._as('rev-uid')
        r = self.client.post(self.url, {'slots': [self._near(3)], 'reschedule': True}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'too_soon')
