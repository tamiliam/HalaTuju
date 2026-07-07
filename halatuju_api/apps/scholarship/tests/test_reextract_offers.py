"""The targeted offer re-score batch (reextract_offers): selection = offers with missing OR
below-genuine (<0.70) authenticity; genuine offers skipped; idempotent per pass; reuses
reextract_document (mocked here — the billable read runs only on the service)."""
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from io import StringIO

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort, ApplicantDocument
from apps.scholarship.management.commands.reextract_offers import _below_genuine, PASS_MARKER


def _app(suffix):
    cohort = ScholarshipCohort.objects.create(code=f'c{suffix}', name='B40', year=2026)
    p = StudentProfile.objects.create(supabase_user_id=f're-{suffix}', grades={'bm': 'A'}, exam_type='spm')
    return ScholarshipApplication.objects.create(cohort=cohort, profile=p, status='shortlisted')


def _offer(app, auth=None, doc_type='offer_letter'):
    vf = {'fields': {'candidate_name': 'X'}}
    if auth is not None:
        vf['authenticity'] = auth
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, storage_path=f'{app.id}/of/x',
        vision_fields=vf, vision_run_at=timezone.now())


class TestBelowGenuine(TestCase):
    def test_targets_missing_and_low_skips_genuine(self):
        app = _app('1')
        no_auth = _offer(app)                                            # no authenticity → target
        no_status = _offer(app, {'probability': 0.9})                   # dict but no status → target
        suspect = _offer(app, {'status': 'suspect', 'probability': 0.4})  # < 0.70 → target
        fake = _offer(app, {'status': 'not_offer_letter', 'probability': 0.05})  # < 0.70 → target
        genuine = _offer(app, {'status': 'genuine', 'probability': 0.70})  # >= 0.70 → skip
        genuine_hi = _offer(app, {'status': 'genuine', 'probability': 0.86})  # skip
        garbled = _offer(app, {'status': 'suspect', 'probability': None})  # no probability → target
        self.assertTrue(_below_genuine(no_auth))
        self.assertTrue(_below_genuine(no_status))
        self.assertTrue(_below_genuine(suspect))
        self.assertTrue(_below_genuine(fake))
        self.assertFalse(_below_genuine(genuine))
        self.assertFalse(_below_genuine(genuine_hi))
        self.assertTrue(_below_genuine(garbled))


class TestReextractOffersCommand(TestCase):
    def _run(self, **kw):
        out = StringIO()
        call_command('reextract_offers', stdout=out, **kw)
        return out.getvalue()

    def test_dry_run_lists_only_targets_no_reads(self):
        app = _app('d')
        low = _offer(app, {'status': 'suspect', 'probability': 0.3})
        _offer(app, {'status': 'genuine', 'probability': 0.8})            # skipped
        with patch('apps.scholarship.management.commands.reextract_offers.reextract_document') as m:
            out = self._run(dry_run=True)
        m.assert_not_called()
        self.assertIn(f'doc{low.id}', out)
        self.assertIn('1 would be processed', out)

    def test_processes_targets_marks_pass_and_is_idempotent(self):
        app = _app('p')
        low = _offer(app, {'status': 'suspect', 'probability': 0.3})
        genuine = _offer(app, {'status': 'genuine', 'probability': 0.8})

        def _touch(doc):
            # Simulate a successful re-read: advance the stamp so the clobber-guard check passes.
            doc.vision_run_at = timezone.now()
            doc.save(update_fields=['vision_run_at'])

        with patch('apps.scholarship.management.commands.reextract_offers.reextract_document',
                   side_effect=_touch) as m:
            self._run(limit=20)
            self.assertEqual(m.call_count, 1)                              # only the low one
            low.refresh_from_db(); genuine.refresh_from_db()
            self.assertEqual(low.vision_fields.get(PASS_MARKER), True)
            self.assertNotIn(PASS_MARKER, genuine.vision_fields)
            # Second run: the low offer is marked done → nothing left.
            m.reset_mock()
            out2 = self._run(limit=20)
            m.assert_not_called()
            self.assertIn('nothing left', out2)

    def test_failed_read_marked_error_not_done(self):
        app = _app('e')
        low = _offer(app, {'status': 'suspect', 'probability': 0.3})
        with patch('apps.scholarship.management.commands.reextract_offers.reextract_document',
                   side_effect=RuntimeError('boom')):
            out = self._run(limit=20)
        low.refresh_from_db()
        self.assertEqual(low.vision_fields.get(PASS_MARKER), 'error')
        self.assertIn('1 errors this run', out)
