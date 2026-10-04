"""TD-079 (2026-10-04) — reading a case must not change its to-do list; deleting a document must.

Two halves, one rule: the ticket queue moves on what the STUDENT does, never on somebody LOOKING.

1. **A deletion re-asks.** The no-re-nag rule kept a RESOLVED system ticket resolved when its gap
   came back, so a student who removed the IC that had closed ``ic_missing`` left the gap on the
   officer's verdict and nothing in her own queue. ``resolution.after_document_deleted`` re-opens
   that ticket (resolved only — a WAIVED one is the officer's decision and stays), re-notifies, and
   is gated like a create: past the Completed stage nobody is asked.
2. **A read in steady state writes nothing.** The officer's detail GET and the student's Action
   Centre GET both reconcile the queue against the live verdict — that is how a gap that moves with
   no document event (a re-read, a stage, the calendar) reaches the queue, and why the reconcile
   stays on the read (decided 2026-10-04, TD-079). What is pinned here is that it is a RECONCILE:
   once the queue matches the verdict, opening the case again issues no INSERT, UPDATE or DELETE
   and sends no mail.
"""
from unittest.mock import patch

from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.resolution import sync_resolution_items
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_student,
)

_WRITES = ('INSERT', 'UPDATE', 'DELETE')


def _writes(captured):
    return [q['sql'] for q in captured.captured_queries
            if q['sql'].lstrip().upper().startswith(_WRITES)]


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   CHECK2_STUDENT_QUERIES_ENABLED=True)
class _Case(TestCase):
    def setUp(self):
        self.org = make_org()
        cohort = make_cohort(programme=make_programme(organisation=self.org),
                             owning_organisation=self.org)
        self.student = make_student(name='THERESA ARUL MARY A/P A.PHILIPS',
                                    nric='080115-05-0132')
        self.app = make_application('profile_complete', cohort=cohort, student=self.student)
        self.client = authed_client(self.student)

    def _ticket(self, code):
        return self.app.resolution_items.get(source='system', code=code)

    def _delete(self, doc):
        with patch('apps.scholarship.storage.delete_objects', return_value=True):
            r = self.client.delete(f'/api/v1/scholarship/documents/{doc.id}/')
        self.assertEqual(r.status_code, 200, r.content[:200])


class TestADeletionReAsks(_Case):
    """The OFFER LETTER, deliberately: it became compulsory after the first cohort submitted, so the
    grandfathered completeness bar of a SUBMITTED application does not hold it and deleting one
    leaves her submitted — the "now-compulsory document" of the entry. (Deleting an IC instead
    un-submits her: `revert_if_profile_incomplete` returns her to the form, whose Documents tab
    asks for it — pinned last below.)"""

    def setUp(self):
        super().setUp()
        # A GENUINELY complete submission (the `test_phase_c._complete` pattern), so a deletion
        # that the grandfathered bar does not hold leaves her submitted. Its documents are the
        # bar's own: ic, results slip, parent IC and one income proof.
        from apps.courses.models import StudentProfile
        from apps.scholarship.models import Consent, FundingNeed, ScholarshipApplication
        from apps.scholarship.tests.factories import SHORTLISTABLE_PROFILE
        StudentProfile.objects.filter(pk=self.student.pk).update(**SHORTLISTABLE_PROFILE)
        FundingNeed.objects.create(application=self.app, categories=['living'],
                                   programme_months=36)
        Consent.objects.create(application=self.app, version='t', is_active=True)
        ScholarshipApplication.objects.filter(pk=self.app.pk).update(
            income_route='str', income_earner='father', father_name='AROON',
            father_occupation='driver', mother_name='KOMATHI', mother_occupation='homemaker',
            siblings_in_school=1, siblings_in_tertiary=0, aspirations='a', plans='p',
            daily_life='d', fears='f')
        self.app.refresh_from_db()
        self.on_file = {t: ApplicantDocument.objects.create(
            application=self.app, doc_type=t, storage_path=f'{self.app.id}/{t}/x')
            for t in ('ic', 'results_slip', 'parent_ic', 'str')}
        from apps.scholarship.services import application_completeness
        self.assertTrue(application_completeness(self.app)['complete'])   # the shape, not assumed

    def _closed_by_an_upload(self, doc_type='offer_letter', code='offer_letter_missing'):
        if doc_type in self.on_file:
            self.on_file.pop(doc_type).delete()
        sync_resolution_items(self.app)
        self.assertEqual(self._ticket(code).status, 'open')
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type=doc_type, storage_path=f'{self.app.id}/{doc_type}/x',
            vision_run_at=timezone.now())
        sync_resolution_items(self.app)
        self.assertEqual(self._ticket(code).status, 'resolved')   # the shape, not assumed
        return doc

    def test_removing_the_document_re_opens_its_ticket_and_re_notifies(self):
        doc = self._closed_by_an_upload()
        self.app.query_raised_notified_at = timezone.now()
        self.app.save(update_fields=['query_raised_notified_at'])
        self._delete(doc)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'profile_complete')    # still submitted
        t = self._ticket('offer_letter_missing')
        self.assertEqual((t.status, t.resolved_by, t.resolved_at), ('open', '', None))
        self.assertEqual(self.app.resolution_items.filter(code='offer_letter_missing').count(), 1)
        self.assertIsNone(self.app.query_raised_notified_at)

    def test_the_student_sees_it_in_her_queue_again(self):
        doc = self._closed_by_an_upload()
        self._delete(doc)
        r = self.client.get('/api/v1/scholarship/resolution-items/')
        self.assertIn('offer_letter_missing', [i['code'] for i in r.json()['open']])

    def test_a_resolved_ticket_whose_gap_persists_is_not_re_nagged(self):
        # The no-re-nag rule still holds for everything the deletion did not bring back: a
        # CONFIRM ticket she answered stays answered although its gap is still on the verdict.
        doc = self._closed_by_an_upload()
        other = self.app.resolution_items.filter(source='system', status='open').exclude(
            code='offer_letter_missing').first()
        self.assertIsNotNone(other, 'the fixture holds no second open ticket to answer')
        other.status, other.resolved_by = 'resolved', 'student'
        other.save(update_fields=['status', 'resolved_by'])
        self._delete(doc)
        other.refresh_from_db()
        self.assertEqual(other.status, 'resolved')
        self.assertEqual(self._ticket('offer_letter_missing').status, 'open')   # the positive

    def test_a_waived_ticket_stays_waived(self):
        doc = self._closed_by_an_upload()
        t = self._ticket('offer_letter_missing')
        t.status = 'waived'
        t.save(update_fields=['status'])
        self._delete(doc)
        self.assertEqual(self._ticket('offer_letter_missing').status, 'waived')

    def test_an_officers_hand_resolution_stays_closed_with_its_reason(self):
        # Review fix (2026-10-04): an officer closed the ask by hand with a reason; the student
        # then uploads and deletes a letter. The officer's decision and its text are kept.
        sync_resolution_items(self.app)
        t = self._ticket('offer_letter_missing')
        t.status, t.resolved_by, t.resolution_text = 'resolved', 'officer@x.org', 'awaiting UPU'
        t.save(update_fields=['status', 'resolved_by', 'resolution_text'])
        doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter',
            storage_path=f'{self.app.id}/offer_letter/x', vision_run_at=timezone.now())
        sync_resolution_items(self.app)
        self._delete(doc)
        t.refresh_from_db()
        self.assertEqual((t.status, t.resolved_by, t.resolution_text),
                         ('resolved', 'officer@x.org', 'awaiting UPU'))

    def test_a_reopened_ticket_keeps_its_text(self):
        doc = self._closed_by_an_upload()
        self.app.resolution_items.filter(code='offer_letter_missing').update(resolution_text='note')
        self._delete(doc)
        t = self._ticket('offer_letter_missing')
        self.assertEqual((t.status, t.resolution_text), ('open', 'note'))

    def test_past_the_completed_stage_nobody_is_asked(self):
        doc = self._closed_by_an_upload()
        self.app.status = 'interviewing'
        self.app.save(update_fields=['status'])
        self._delete(doc)
        self.assertEqual(self._ticket('offer_letter_missing').status, 'resolved')

    def test_deleting_an_ic_returns_her_to_the_form_instead(self):
        doc = self._closed_by_an_upload('ic', 'ic_missing')
        self._delete(doc)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, 'shortlisted')          # un-submitted: the form asks
        self.assertEqual(self._ticket('ic_missing').status, 'resolved')


class TestAReadInSteadyStateWritesNothing(_Case):
    def test_the_officers_second_open_writes_nothing_and_sends_nothing(self):
        officer = authed_client(make_admin('org_admin', owning_org=self.org))
        url = f'/api/v1/admin/scholarship/applications/{self.app.id}/'
        self.assertEqual(officer.get(url).status_code, 200)       # the first open reconciles
        self.assertTrue(self.app.resolution_items.filter(source='system').exists())
        mail.outbox.clear()
        with CaptureQueriesContext(connection) as captured:
            self.assertEqual(officer.get(url).status_code, 200)
        self.assertGreater(len(captured.captured_queries), 0)       # it did read
        self.assertEqual(_writes(captured), [])
        self.assertEqual(mail.outbox, [])

    def test_the_students_second_read_of_her_queue_writes_nothing(self):
        url = '/api/v1/scholarship/resolution-items/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(self.app.resolution_items.exists())
        mail.outbox.clear()
        with CaptureQueriesContext(connection) as captured:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertGreater(len(captured.captured_queries), 0)
        self.assertEqual(_writes(captured), [])
        self.assertEqual(mail.outbox, [])
