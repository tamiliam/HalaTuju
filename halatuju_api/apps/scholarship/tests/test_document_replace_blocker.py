"""H6 fix round 3 (owner 2026-11-17): the blocker allowance before consent.

Before consent nobody can ask (a reviewer's request is refused until she consents), so a slot whose live copy
stops consent would be a dead end at four uploads. While the copy (or the slot's empty type) holds the consent
gate and `profile_completed_at` is unset, the slot takes up to four more, eight in all; the 409 at eight sends
her to support (`replace_limit_support`), never to a reviewer. After the copy passes, after consent, or for a
copy that does not hold the gate, the normal four stand.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.scholarship import branding
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.services.consent_blockers import consent_blocking_slots
from apps.scholarship.tests.doc_keys import issued_key as _key
from apps.scholarship.tests.factories import TEST_JWT_SECRET, authed_client, make_application, make_cohort, make_student

DOCS = '/api/v1/scholarship/documents/'
_UNREADABLE = {'fields': {}, 'warnings': [], 'student_verdict': 'unreadable', 'service_error': False, 'error': ''}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, CHECK2_STUDENT_QUERIES_ENABLED=True)
@patch('apps.scholarship.storage.delete_own_doc_objects', return_value=None)
@patch('apps.scholarship.upload_read.needs_read', return_value=True)    # recorded queued: no paid read
@patch('apps.scholarship.storage.object_exists', return_value=True)
class TestBlockerAllowance(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='rb', name='Blocker', year=2026)

    def _case(self, stage='shortlisted'):
        student = make_student()
        app = make_application(stage, cohort=self.cohort, student=student)
        return app, authed_client(student.supabase_user_id)

    def _post(self, client, app, doc_type='offer_letter'):
        return client.post(DOCS, {'doc_type': doc_type, 'storage_path': _key(app, doc_type, 'x'),
                                  'original_filename': 'a.pdf', 'size': 1000, 'household_member': '',
                                  'request_code': '', 'replace': True}, format='json')

    def _blocking_offer(self, app):
        """The first upload: an offer letter the read could not make out, which holds the consent gate."""
        return ApplicantDocument.objects.create(application=app, doc_type='offer_letter', storage_path='first',
                                                vision_fields=_UNREADABLE)

    def _listed(self, client, doc_type='offer_letter'):
        return [(d['replaces_left'], d['replace_support'])
                for d in client.get(DOCS).json()['documents'] if d['doc_type'] == doc_type]

    def _codes(self, client, app, n, doc_type='offer_letter'):
        return [self._post(client, app, doc_type).status_code for _i in range(n)]

    def test_the_signal_is_the_live_copy_the_gate_reads(self, *_):
        app, _c = self._case()
        doc = self._blocking_offer(app)
        slots, _missing = consent_blocking_slots(app)
        self.assertIn(('offer_letter', '', ''), slots)
        doc.delete()                                                      # emptied: its type is asked for
        _slots, missing = consent_blocking_slots(app)
        self.assertIn(('offer_letter', None), missing)

    def test_a_blocking_copy_before_consent_gets_uploads_five_to_eight_then_support(self, *_):
        app, client = self._case()
        self._blocking_offer(app)
        self.assertEqual(self._codes(client, app, 3), [201, 201, 201])    # uploads 2 to 4: the normal cap
        self.assertEqual(self._listed(client), [(4, False)])               # the server's count: four more
        self.assertEqual(self._codes(client, app, 4), [201, 201, 201, 201])   # uploads 5 to 8
        self.assertEqual(self._listed(client), [(0, True)])
        resp = self._post(client, app)                                     # the 9th
        body = resp.json()
        self.assertEqual((resp.status_code, body['error'], body['code']),
                         (409, 'replace_limit_reached', 'replace_limit_support'))
        email = branding.for_application(app).email_support
        self.assertEqual(body['support_email'], email)
        self.assertIn(f'write to us at {email}', body['message'])
        self.assertNotIn('reviewer', body['message'])
        self.assertEqual(ApplicantDocument.objects.filter(application=app).count(), 8)   # nothing recorded

    def test_an_emptied_blocking_slot_still_gets_the_allowance_and_no_more(self, *_):
        app, client = self._case()
        self._blocking_offer(app)
        self.assertEqual(self._codes(client, app, 3), [201, 201, 201])
        ApplicantDocument.objects.filter(application=app).delete()        # as Remove leaves it: the count stays
        self.assertEqual(self._codes(client, app, 5), [201, 201, 201, 201, 409])

    def test_once_the_copy_passes_the_normal_cap_applies(self, *_):
        app, client = self._case()
        self._blocking_offer(app)
        self.assertEqual(self._codes(client, app, 4), [201, 201, 201, 201])   # the 5th: allowance
        with patch('apps.scholarship.services.consent_blockers.consent_blocking_slots',
                   return_value=(set(), set())):                          # the copy now passes the gate
            self.assertEqual(self._listed(client), [(0, False)])
            resp = self._post(client, app)
            self.assertEqual((resp.status_code, resp.json()['code']), (409, 'replace_limit_reached'))

    def test_after_consent_the_normal_cap_applies(self, *_):
        app, client = self._case('profile_complete')
        self.assertIsNotNone(app.profile_completed_at)
        self._blocking_offer(app)
        self.assertEqual(self._codes(client, app, 4), [201, 201, 201, 409])
        resp = self._post(client, app)
        self.assertEqual((resp.json()['code'], self._listed(client)), ('replace_limit_reached', [(0, False)]))

    def test_a_copy_that_does_not_hold_the_gate_gets_no_extra_tries(self, *_):
        app, client = self._case()
        self.assertTrue(consent_blocking_slots(app) != (set(), set()))    # the gate holds her, elsewhere
        ApplicantDocument.objects.create(application=app, doc_type='bank_statement', storage_path='first',
                                         vision_fields=_UNREADABLE)
        self.assertEqual(self._codes(client, app, 4, 'bank_statement'), [201, 201, 201, 409])
        resp = self._post(client, app, 'bank_statement')
        self.assertEqual(resp.json()['code'], 'replace_limit_reached')
        self.assertEqual(self._listed(client, 'bank_statement'), [(0, False)])
