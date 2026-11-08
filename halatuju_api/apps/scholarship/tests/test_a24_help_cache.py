"""A2.4 / SP-06 - a repeat coach GET is answered from the cache: no second model call.

The Gemini prose seam is mocked (no billable call). Pinned: a repeat open costs no model call; a
different student, a different verdict and a failed call are never served from another's entry.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_student,
)

SEAM = 'apps.scholarship.profile_engine._call_gemini_text'
OK = {'markdown': 'No worries, let me help.', 'model_used': 'gemini-test'}
MISMATCH = {'fields': {}, 'warnings': [], 'student_verdict': 'name_mismatch', 'error': ''}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheCoachRepeatReadCostsNoModelCall(TestCase):

    def _case(self):
        app = make_application('shortlisted', cohort=make_cohort(), student=make_student())
        doc = ApplicantDocument.objects.create(
            application=app, doc_type='salary_slip', storage_path=f'{app.id}/x/abc',
            vision_fields=MISMATCH)
        return app, doc, authed_client(app.profile.supabase_user_id)

    def test_a_repeat_open_makes_no_second_model_call(self):
        _app, doc, client = self._case()
        url = f'/api/v1/scholarship/documents/{doc.id}/help/'
        with patch(SEAM, return_value=OK) as model:
            first = client.get(url).json()
            second = client.get(url).json()
        self.assertEqual(model.call_count, 1)
        self.assertEqual((first['source'], second['source']), ('ai', 'ai'))
        self.assertEqual(first['message'], second['message'])
        self.assertEqual(second['verdict'], 'name_mismatch')

    def test_another_student_is_never_served_this_students_entry(self):
        _a, doc_a, client_a = self._case()
        _b, doc_b, client_b = self._case()
        with patch(SEAM, return_value=OK) as model:
            client_a.get(f'/api/v1/scholarship/documents/{doc_a.id}/help/')
            client_b.get(f'/api/v1/scholarship/documents/{doc_b.id}/help/')
        self.assertEqual(model.call_count, 2)

    def test_a_failed_call_is_not_cached_and_is_retried(self):
        _app, doc, client = self._case()
        url = f'/api/v1/scholarship/documents/{doc.id}/help/'
        with patch(SEAM, return_value={'error': 'down'}) as model:
            self.assertEqual(client.get(url).json()['source'], 'fallback')
        with patch(SEAM, return_value=OK) as model2:
            self.assertEqual(client.get(url).json()['source'], 'ai')
        self.assertEqual((model.call_count, model2.call_count), (1, 1))

    def test_a_changed_verdict_asks_the_model_again(self):
        _app, doc, client = self._case()
        url = f'/api/v1/scholarship/documents/{doc.id}/help/'
        with patch(SEAM, return_value=OK) as model:
            client.get(url)
            doc.vision_fields = {**MISMATCH, 'student_verdict': 'unreadable'}
            doc.save(update_fields=['vision_fields'])
            client.get(url)
        self.assertEqual(model.call_count, 2)
