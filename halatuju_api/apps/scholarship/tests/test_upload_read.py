"""A2.3 / TD-519 — the upload no longer reads the document inside the request.

An upload whose type has a paid read (Vision OCR / Gemini field extraction) is recorded queued
(``read_state='pending'``) and answered at once; the read runs on ``documents/<id>/read/`` (which
the web sends straight after) or on the ``read-documents`` cron. These tests pin the queue: no
inline read, the claim, retries, the superseded rule, owner scoping, the cron and the GET count.
All paid calls are mocked; no real document is read.
"""
import io
from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import patch

import jwt
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scholarship import upload_read
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.services import blockers
from apps.scholarship.tests.doc_keys import issued_key as _key
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
DOCS = '/api/v1/scholarship/documents/'
USER_A = 'ur-user-a'
USER_B = 'ur-user-b'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


class _Reads:
    """Every paid read the upload pipeline can make, mocked, so a test can assert none ran."""

    def __enter__(self):
        self._stack = ExitStack()
        p = lambda target, **kw: self._stack.enter_context(patch(target, **kw))  # noqa: E731 — short local helper in a test
        self.ic = p('apps.scholarship.vision.run_vision_for_document', return_value=None)
        self.ocr = p('apps.scholarship.vision.ocr_document_full',
                     return_value={'text': '', 'error': None})
        self.match = p('apps.scholarship.vision.run_vision_match_for_document', return_value=None)
        self.text = p('apps.scholarship.vision.read_text_document', return_value=None)
        self.fields = p('apps.scholarship.views.DocumentListCreateView._maybe_extract_fields',
                        return_value=None)
        p('apps.scholarship.storage.object_exists', return_value=True)
        return self

    def __exit__(self, *exc):
        return self._stack.__exit__(*exc)

    def any_called(self):
        return any(m.called for m in (self.ic, self.ocr, self.match, self.text, self.fields))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestUploadQueue(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='ur', name='B40', year=2026)
        cls.app_a = make_application('shortlisted', cohort=cls.cohort,
                                     student=make_student(supabase_user_id=USER_A, nric='030101-14-1111'))
        cls.app_b = make_application('shortlisted', cohort=cls.cohort,
                                     student=make_student(supabase_user_id=USER_B, nric='040101-14-2222'))

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(USER_A)}')

    def _upload(self, doc_type='ic', tag='a', client=None, app=None):
        return (client or self.client).post(DOCS, {
            'doc_type': doc_type, 'storage_path': _key(app or self.app_a, doc_type, tag),
            'original_filename': f'{tag}.pdf', 'size': 1000}, format='json')

    # --- the upload request ---------------------------------------------------

    def test_an_ic_upload_answers_at_once_with_no_read(self):
        with _Reads() as reads:
            r = self._upload('ic')
            self.assertFalse(reads.any_called())       # no Vision inside the request
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertEqual((body['reading'], body['match_verdict'], body['kept_previous']),
                         (True, 'pending', False))
        doc = ApplicantDocument.objects.get(pk=body['id'])
        self.assertEqual(doc.read_state, upload_read.PENDING)
        self.assertEqual(sorted(doc.read_plan), ['existing_live', 'staged', 'stale_ids'])
        self.assertIsNone(doc.vision_run_at)

    def test_a_supporting_upload_makes_no_ocr_or_gemini_call(self):
        with _Reads() as reads:
            r = self._upload('epf')
            self.assertFalse(reads.any_called())
        self.assertEqual((r.status_code, r.json()['reading']), (201, True))

    def test_a_type_with_no_read_is_still_judged_inline(self):
        self.assertFalse(upload_read.needs_read('other'))
        with _Reads() as reads:
            r = self.client.post(DOCS, {'doc_type': 'other', 'request_code': 'r1',
                                        'storage_path': _key(self.app_a, 'other', 'r1'),
                                        'original_filename': 'o.pdf', 'size': 10}, format='json')
            self.assertFalse(reads.any_called())
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotIn('reading', r.json())
        self.assertEqual(ApplicantDocument.objects.get(pk=r.json()['id']).read_state, '')

    # --- the read endpoint ----------------------------------------------------

    def test_the_read_endpoint_runs_the_read_once(self):
        with _Reads() as reads:
            doc_id = self._upload('ic').json()['id']
            r = self.client.post(f'{DOCS}{doc_id}/read/', format='json')
            self.assertEqual(reads.ic.call_count, 1)
            again = self.client.post(f'{DOCS}{doc_id}/read/', format='json')
            self.assertEqual(reads.ic.call_count, 1)   # already read: the row as it stands
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['reading'])
        self.assertEqual((again.status_code, again.json()['reading']), (200, False))
        doc = ApplicantDocument.objects.get(pk=doc_id)
        self.assertEqual((doc.read_state, doc.read_claimed_at, doc.read_attempts), ('', None, 1))

    def test_another_students_document_is_not_found(self):
        with _Reads() as reads:
            doc_id = self._upload('ic').json()['id']
            other = APIClient()
            other.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(USER_B)}')
            r = other.post(f'{DOCS}{doc_id}/read/', format='json')
            self.assertFalse(reads.any_called())
        self.assertEqual(r.status_code, 404)
        self.assertEqual(ApplicantDocument.objects.get(pk=doc_id).read_state, upload_read.PENDING)

    def test_a_document_being_read_elsewhere_answers_reading(self):
        with _Reads() as reads:
            doc_id = self._upload('ic').json()['id']
            ApplicantDocument.objects.filter(pk=doc_id).update(read_claimed_at=timezone.now())
            r = self.client.post(f'{DOCS}{doc_id}/read/', format='json')
            self.assertFalse(reads.any_called())
        self.assertEqual((r.status_code, r.json()['reading'], r.json()['match_verdict']),
                         (200, True, 'pending'))

    def test_the_list_counts_uploads_still_reading(self):
        with _Reads():
            self._upload('ic', 'a')
            self._upload('epf', 'b')
        r = self.client.get(DOCS)
        self.assertEqual(r.json()['reading'], 2)

    # --- the claim, retries, failure -----------------------------------------

    def _pending(self, doc_type='ic', tag='q'):
        with _Reads():
            return ApplicantDocument.objects.get(pk=self._upload(doc_type, tag).json()['id'])

    def test_one_claim_wins_and_a_stale_claim_is_claimable_again(self):
        doc = self._pending()
        now = timezone.now()
        self.assertTrue(upload_read._claim_read(doc.id, now))
        self.assertFalse(upload_read._claim_read(doc.id, now))
        self.assertTrue(upload_read._claim_read(doc.id, now + upload_read.STALE_CLAIM + timedelta(seconds=1)))
        self.assertEqual(ApplicantDocument.objects.get(pk=doc.id).read_attempts, 2)

    def test_a_failed_read_retries_then_is_marked_failed(self):
        doc = self._pending()
        with patch('apps.scholarship.upload_read.read_and_judge', side_effect=RuntimeError('boom')):
            outcomes = [upload_read.run_read(doc.id)[0] for _ in range(upload_read.MAX_ATTEMPTS)]
            self.assertEqual(upload_read.run_read(doc.id)[0], 'not_claimed')
        self.assertEqual(outcomes, ['retry', 'retry', 'failed'])
        doc.refresh_from_db()
        self.assertEqual((doc.read_state, doc.read_claimed_at), (upload_read.FAILED, None))

    def test_a_read_killed_on_its_last_attempt_is_closed_by_the_cron(self):
        doc = self._pending()
        ApplicantDocument.objects.filter(pk=doc.id).update(
            read_attempts=upload_read.MAX_ATTEMPTS,
            read_claimed_at=timezone.now() - upload_read.STALE_CLAIM - timedelta(minutes=1))
        with _Reads() as reads:
            counts = upload_read.run_pending()
            self.assertFalse(reads.any_called())
        self.assertEqual(counts['failed'], 1)
        self.assertEqual(ApplicantDocument.objects.get(pk=doc.id).read_state, upload_read.FAILED)

    # --- the superseded rule --------------------------------------------------

    def test_an_older_upload_never_overrides_a_newer_decided_one(self):
        older = self._pending('ic', 'old')
        newer = self._pending('ic', 'new')
        with _Reads() as reads:
            self.assertEqual(upload_read.run_read(newer.id)[0], 'done')
            self.assertEqual(reads.ic.call_count, 1)
            self.assertEqual(upload_read.run_read(older.id)[0], 'superseded')
            self.assertEqual(reads.ic.call_count, 1)   # the older one is not read at all
        older.refresh_from_db()
        newer.refresh_from_db()
        self.assertEqual(older.read_state, '')
        self.assertIsNotNone(older.superseded_at)
        self.assertIsNone(newer.superseded_at)

    def test_an_older_upload_is_read_while_the_newer_still_waits(self):
        older = self._pending('ic', 'old')
        self._pending('ic', 'new')
        with _Reads() as reads:
            self.assertEqual(upload_read.run_read(older.id)[0], 'done')
            self.assertEqual(reads.ic.call_count, 1)

    def test_a_later_read_is_judged_against_the_slot_as_it_is_now(self):
        # A2.3 review: IC slot empty; A then B uploaded, both staged with no copy to compare; both
        # web read calls lost. The cron reads A (good) → live. B (a mismatch) must be judged
        # against A, not the "nothing" its plan saw, so A keeps the slot and B stays staged.
        a = self._pending('ic', 'good')
        b = self._pending('ic', 'bad')
        self.assertEqual((a.read_plan['existing_live'], b.read_plan['existing_live']), (None, None))
        verdict = lambda d: 'mismatch' if d.id == b.id else 'ok'  # noqa: E731 — short local helper in a test
        with _Reads(), patch('apps.scholarship.resolution.doc_match_verdict', side_effect=verdict):
            self.assertEqual(upload_read.run_read(a.id)[0], 'done')
            outcome, data = upload_read.run_read(b.id)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(outcome, 'done')
        self.assertIsNone(a.superseded_at)               # the good copy stays live
        self.assertIsNotNone(b.superseded_at)            # the mismatch is never promoted
        self.assertTrue(data['kept_previous'])

    def test_a_planned_copy_moved_out_before_the_read_is_not_the_comparison(self):
        # The upload saw a live copy; it was then moved out of the slot (collapse/dedupe), so the
        # slot is empty at read time. The upload is judged against nothing and promotes, even as a
        # mismatch, rather than against the dead copy (and staying staged over an empty slot).
        with _Reads():
            first = self._pending('ic', 'first')
            self.assertEqual(upload_read.run_read(first.id)[0], 'done')
        second = self._pending('ic', 'second')
        self.assertEqual(second.read_plan['existing_live'], first.id)
        ApplicantDocument.objects.filter(pk=first.id).update(superseded_at=timezone.now())
        with _Reads(), patch('apps.scholarship.resolution.doc_match_verdict', return_value='mismatch'):
            outcome, data = upload_read.run_read(second.id)
        second.refresh_from_db()
        self.assertEqual(outcome, 'done')
        self.assertIsNone(second.superseded_at)          # promoted: nothing to compare against
        self.assertFalse(data['kept_previous'])

    # --- the cron -------------------------------------------------------------

    def test_the_cron_reads_queued_uploads_oldest_first(self):
        first = self._pending('ic', 'a')
        second = self._pending('epf', 'b')
        with _Reads() as reads:
            out = io.StringIO()
            call_command('run_pending_reads', stdout=out)
            self.assertEqual(reads.ic.call_count, 1)
        self.assertIn('done=2', out.getvalue())
        self.assertEqual(
            list(ApplicantDocument.objects.filter(pk__in=[first.id, second.id])
                 .values_list('read_state', flat=True)), ['', ''])
        self.assertEqual(upload_read.run_pending(), {'done': 0, 'retry': 0, 'failed': 0,
                                                     'superseded': 0, 'not_claimed': 0, 'error': 0})

    def test_the_cron_never_raises(self):
        self._pending()
        with patch('apps.scholarship.upload_read.run_read', side_effect=RuntimeError('db')):
            self.assertEqual(upload_read.run_pending()['error'], 1)

    def test_the_stuck_document_sweep_leaves_queued_uploads_to_the_queue(self):
        doc = self._pending('ic')
        self.assertNotIn(doc.id, [d.id for d in blockers._stuck_unread_documents(50)])
        ApplicantDocument.objects.filter(pk=doc.id).update(read_state=upload_read.FAILED)
        self.assertIn(doc.id, [d.id for d in blockers._stuck_unread_documents(50)])
