"""Audit sprint A2.8a (TD-400) — a parent's typed details are not called a mismatch against a parent IC
our outage left half-read.

Before A2.8a the minor's consent and the bursary guarantor compared the typed name / NRIC with a
parent IC whose REQUIRED second opinion our outage skipped (TD-390) and answered "doesn't match, check
both". Now, inside the TD-390 window, a DIFFERING value is "try later" (`parent_ic_service_down`). A
match still passes, as before; after the window the read counts as complete and a mismatch shows.
Synthetic data only.
"""
import time
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scholarship import read_errors
from apps.scholarship.bursary import guarantor_identity_check
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import TEST_JWT_SECRET, auth_token, make_application, make_student

NAME, NRIC = 'IBU CONTOH', '750101-14-5678'
_OPEN, _GONE = int(time.time()) + 3600, int(time.time()) - 60


def _parent_ic(app, until=None):
    vf = {} if until is None else {read_errors.IC_SECOND_OPINION_ERROR: 'All AI models failed: 402',
                                   read_errors.IC_SECOND_OPINION_UNTIL: until}
    return ApplicantDocument.objects.create(
        application=app, doc_type='parent_ic', storage_path=f'test/pic/{app.id}', vision_name=NAME,
        vision_nric=NRIC, vision_run_at=timezone.now(), vision_error='', vision_fields=vf)


class TheGuarantorCheck(TestCase):

    def setUp(self):
        self.app = make_application('shortlisted')

    def test_inside_the_window_a_differing_value_is_try_later(self):
        _parent_ic(self.app, until=_OPEN)
        self.assertEqual(guarantor_identity_check(self.app, NAME, '750101-14-0000'), 'parent_ic_service_down')
        self.assertEqual(guarantor_identity_check(self.app, 'SOMEONE ELSE', NRIC), 'parent_ic_service_down')

    def test_a_match_still_passes(self):
        _parent_ic(self.app, until=_OPEN)
        self.assertEqual(guarantor_identity_check(self.app, NAME, NRIC), 'ok')

    def test_after_the_window_a_mismatch_shows_as_before(self):
        _parent_ic(self.app, until=_GONE)
        self.assertEqual(guarantor_identity_check(self.app, NAME, '750101-14-0000'), 'parent_ic_nric_mismatch')
        self.assertEqual(guarantor_identity_check(self.app, 'SOMEONE ELSE', NRIC), 'parent_ic_name_mismatch')

    def test_a_fully_read_card_is_unchanged(self):
        _parent_ic(self.app)
        self.assertEqual(guarantor_identity_check(self.app, NAME, '750101-14-0000'), 'parent_ic_nric_mismatch')
        self.assertEqual(guarantor_identity_check(self.app, NAME, NRIC), 'ok')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TheMinorsConsent(TestCase):

    def setUp(self):
        self.app = make_application('shortlisted', student=make_student(supabase_user_id='guarantor-pending',
                                                                        nric='110101-14-5678'))
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {auth_token("guarantor-pending")}')

    def _post(self, nric):
        with patch('apps.scholarship.views.consent.consent_blockers', return_value=[]):
            return self.client.post('/api/v1/scholarship/consent/', {
                'granted_by': 'guardian', 'guardian_name': NAME, 'guardian_relationship': 'mother',
                'guardian_nric': nric}, format='json')

    def test_a_differing_nric_against_a_half_read_card_is_try_later(self):
        _parent_ic(self.app, until=_OPEN)
        resp = self._post('750101-14-0000')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'parent_ic_service_down')

    def test_after_the_window_it_is_a_mismatch_again(self):
        _parent_ic(self.app, until=_GONE)
        resp = self._post('750101-14-0000')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['error'], 'parent_ic_nric_mismatch')

    def test_a_match_on_a_half_read_card_gives_consent(self):
        _parent_ic(self.app, until=_OPEN)
        self.assertEqual(self._post(NRIC).status_code, 201)

    def test_the_screen_gets_no_live_mismatch_values_from_a_half_read_card(self):
        card = _parent_ic(self.app, until=_OPEN)
        body = self.client.get('/api/v1/scholarship/consent/').json()
        self.assertEqual((body['parent_ic_vision_nric'], body['parent_ic_vision_name']), ('', ''))
        card.vision_fields = {}
        card.save(update_fields=['vision_fields'])
        body = self.client.get('/api/v1/scholarship/consent/').json()
        self.assertEqual(body['parent_ic_vision_nric'], NRIC)
