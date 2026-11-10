"""Sprint S1, owner ruling A (2026-11-10): a MENTOR reading a student's file sees staff by NAME, never by
email address — on every tab, after staff have done real work on the file (a note, a reviewed result, a
letter issued and withdrawn with no name kept, mentoring assigned / ended / logged, a handled concern,
and a row by a writer nobody knows any more). Staff still see the addresses (their tab is unchanged).
"""
from unittest.mock import patch

from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import activity, mentoring, results_review
from apps.scholarship.models import Letter, MentoringSession
from apps.scholarship.models.activity import EVENT_RESULT_REVIEWED
from apps.scholarship.tests.factories import authed_client, record_result
from apps.scholarship.tests.test_mentor_scholars import API, _Base, tabs

UPLOAD = 'apps.scholarship.storage.upload_object'
GONE = 'gone.officer@example.invalid'


class TestMentorsSeeNamesNotAddresses(_Base):
    def setUp(self):
        super().setUp()
        lead = self.lead
        PartnerAdmin.objects.filter(pk=lead.pk).update(name='Lead Officer')
        lead.refresh_from_db()
        activity.add_entry(self.app, 'note', 'Called about the slip.', actor_email=lead.email)
        activity.log_event(self.app, EVENT_RESULT_REVIEWED, actor_email=GONE,
                           meta={'by': GONE, 'semester': '2026 S1'})
        result = record_result(self.app, semester='2026 S1', cgpa='3.4')
        results_review.review(result, decision='accepted', by_email=lead.email)
        with patch(UPLOAD, return_value=True), self.captureOnCommitCallbacks(execute=True):
            r = authed_client(lead).post(f'{API}{self.app.id}/letters/', {
                'kind': 'general', 'language': 'en', 'note': 'Your payment date moves.'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        Letter.objects.filter(application=self.app).update(
            issued_by_name='', withdrawn_at=timezone.now(), withdrawn_by_email=lead.email, withdrawn_by_name='')
        mentoring.end(lead, self.app, reason='swap')
        mentoring.assign(lead, self.app, self.kavitha, email_student=False)
        mentoring.log_session(lead, self.app, met_on=timezone.localdate(),
                              mode='video', minutes=30, notes='Planned the term.')
        MentoringSession.objects.filter(application=self.app).update(
            concern=True, concern_handled_at=timezone.now(), concern_handled_by_email=lead.email)

    def addresses(self):
        return [e for e in PartnerAdmin.objects.values_list('email', flat=True) if e] + [GONE]

    def test_no_staff_address_on_any_tab_a_mentor_reads(self):
        client = self.client_for()
        for url in tabs(self.app.id):
            r = client.get(url)
            self.assertEqual(r.status_code, 200, url)
            body = r.content.decode().lower()
            for address in self.addresses():
                with self.subTest(url=url, address=address):
                    self.assertNotIn(address.lower(), body)

    def test_their_names_still_show(self):
        client = self.client_for()
        tab = client.get(f'{API}{self.app.id}/mentoring/').json()
        self.assertEqual(tab['history'][0]['ended_by']['name'], 'Lead Officer')
        self.assertEqual(tab['meetings'][0]['logged_by'], {'email': '', 'name': 'Lead Officer', 'role': 'org_admin'})
        self.assertEqual(tab['current']['email'], '')
        results = client.get(f'{API}{self.app.id}/results/').json()['results']
        self.assertEqual(results[0]['reviewed_by'], 'Lead Officer')

    def test_staff_still_see_the_addresses(self):
        client = authed_client(self.lead)
        tab = client.get(f'{API}{self.app.id}/mentoring/').json()
        self.assertEqual(tab['meetings'][0]['logged_by']['email'], self.lead.email)
        self.assertEqual(client.get(f'{API}{self.app.id}/results/').json()['results'][0]['reviewed_by'],
                         self.lead.email)
        log = client.get(f'{API}{self.app.id}/activity/').content.decode()
        self.assertIn(GONE, log)
        letters = client.get(f'{API}{self.app.id}/letters/').json()['letters']
        self.assertEqual(letters[0]['issued_by_name'], self.lead.email)

    def test_a_staff_mentor_sees_names_only_too(self):
        person = self.staff_mentor()
        body = authed_client(person).get(f'{API}{self.app.id}/mentoring/').content.decode().lower()
        for address in self.addresses():
            with self.subTest(address=address):
                self.assertNotIn(address.lower(), body)
