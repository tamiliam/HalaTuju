"""A2.2 / TD-518: the hourly reprocess sweep stops cleanly at its time budget and the next run resumes.
Mocked reads only; a fake clock that each mocked read advances (no sleeping, no paid call)."""
from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.services import reprocess_unread_ic_documents
from apps.scholarship.services.read_retry import APPROVAL_CURSOR_KEY
from apps.scholarship.tests.factories import make_application


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


class TestReprocessTimeBudget(TestCase):
    def setUp(self):
        cache.delete(APPROVAL_CURSOR_KEY)
        self.app = make_application('submitted')
        self.clock = Clock()

    def _stuck(self, n):
        return [ApplicantDocument.objects.create(application=self.app, doc_type='parent_ic',
                                                 household_member=f'm{i}', storage_path=f'ic-{i}',
                                                 vision_run_at=None) for i in range(n)]

    def _run(self, seen, cost=40, **kw):
        """One run; every mocked read costs ``cost`` fake seconds and records which doc it read."""
        def read(doc):
            seen.append(doc.id)
            self.clock.now += cost
            return {'error': ''}
        with patch('time.monotonic', self.clock), \
                patch('apps.scholarship.vision.run_vision_for_document', side_effect=read):
            return reprocess_unread_ic_documents(**kw)

    def test_stops_at_the_budget_then_resumes_with_none_skipped_or_read_twice(self):
        docs = self._stuck(7)
        seen = []
        r1 = self._run(seen, time_budget=100, limit=50)       # 40 s each: reads 3 (0,40,80 < 100), then stops
        self.assertEqual(len(seen), 3)
        self.assertEqual((r1['scanned'], r1['processed']), (3, 3))
        self.assertTrue(r1['stopped_early'])
        self.assertEqual(r1['left'], 4)
        r2 = self._run(seen, time_budget=100, limit=50)
        self.assertEqual(len(seen), 6)
        self.assertTrue(r2['stopped_early'])
        r3 = self._run(seen, time_budget=100, limit=50)
        self.assertEqual(r3, {'scanned': 1, 'processed': 1, 'errored': 0})   # finished: no stop keys
        self.assertEqual(seen, [d.id for d in docs])            # every doc once, oldest first, no repeats
        r4 = self._run(seen, time_budget=100, limit=50)
        self.assertEqual(r4['scanned'], 0)
        self.assertEqual(len(seen), 7)

    def test_without_a_budget_the_run_is_unchanged(self):
        self._stuck(5)
        seen = []
        r = self._run(seen, cost=1000, limit=50)
        self.assertEqual(r, {'scanned': 5, 'processed': 5, 'errored': 0})

    def test_the_batch_limit_still_caps_a_run(self):
        self._stuck(5)
        seen = []
        r = self._run(seen, cost=1, time_budget=100, limit=2)
        self.assertEqual(r['scanned'], 2)
        self.assertNotIn('stopped_early', r)

    def test_a_stop_in_the_retry_half_resumes_after_the_documents_it_reached(self):
        def doc(i):
            return ApplicantDocument.objects.create(
                application=self.app, doc_type='salary_slip', household_member=f'm{i}', storage_path=f's-{i}',
                vision_fields={'fields': {'a': 'b'}, 'authenticity': {'doc_seen': 'informal'}},
                vision_fields_run_at=timezone.now())
        docs = [doc(i) for i in range(4)]
        seen = []

        def reread(d):
            seen.append(d.id)
            self.clock.now += 60
            return ''
        with patch('time.monotonic', self.clock), \
                patch('apps.scholarship.services.read_retry._reread', side_effect=reread), \
                patch('apps.scholarship.services.outage.gemini_reads_down', return_value=False), \
                patch('apps.scholarship.services.read_retry.approval_unchecked_documents',
                      wraps=__import__('apps.scholarship.services.read_retry', fromlist=['x']
                                       ).approval_unchecked_documents):
            r1 = reprocess_unread_ic_documents(limit=50, time_budget=100)
            self.assertEqual(len(seen), 2)
            self.assertTrue(r1['stopped_early'])
            self.assertEqual(r1['left'], 2)
            # the real sweep stamps what it reads (so it leaves the pool); mimic that for the mocked read
            for i in seen:
                ApplicantDocument.objects.filter(id=i).update(
                    vision_fields={'fields': {'a': 'b'}, 'approval_tried': 1,
                                   'authenticity': {'doc_seen': 'informal'}})
            r2 = reprocess_unread_ic_documents(limit=50, time_budget=1000)
        self.assertEqual(seen, [d.id for d in docs])
        self.assertNotIn('stopped_early', r2)

    @override_settings(REPROCESS_TIME_BUDGET_SECONDS=100, REPROCESS_BATCH_LIMIT=100)
    def test_the_command_reports_the_stop_and_takes_its_defaults_from_settings(self):
        self._stuck(2)
        out = StringIO()
        with patch('apps.scholarship.management.commands.reprocess_unread_ic.reprocess_unread_ic_documents',
                   return_value={'scanned': 2, 'processed': 2, 'errored': 0,
                                 'stopped_early': True, 'left': 9}) as m, \
                patch('apps.scholarship.management.commands.reprocess_unread_ic.reread_preflight'):
            call_command('reprocess_unread_ic', stdout=out)
        m.assert_called_once_with(limit=100, time_budget=100)
        self.assertIn('STOPPED-AT-TIME-BUDGET(100s) left=9', out.getvalue())
