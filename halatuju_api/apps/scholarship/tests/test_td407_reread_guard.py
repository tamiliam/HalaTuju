"""TD-407 — a re-read never overwrites a genuineness score with silence, and the bulk re-read commands
refuse to start without the service's genuineness flag.

Corpus C4's first live re-read ran through a Cloud Run JOB that carried only core env: with
`DOC_GENUINENESS_CHECK_ENABLED` off, the read pipeline rebuilt `vision_fields` with no `authenticity`
and wiped 16 stored scores (and 16 more on 2026-10-24, unnoticed). Every read is mocked here — no
Vision, no Gemini.
"""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.scholarship import vision
from apps.scholarship.genuineness.bands import NOT_CHECKED
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_corpus_gaps_c2 import UITM_OFFER

STORED = {
    'genuine':          {'status': 'genuine', 'probability': 0.9, 'doc_seen': 'ua_offer', 'model_version': '1.9.0'},
    'suspect':          {'status': 'suspect', 'probability': 0.4, 'doc_seen': 'ua_offer', 'model_version': '1.9.0'},
    'not_offer_letter': {'status': 'not_offer_letter', 'probability': 0.1, 'doc_seen': 'ua_offer',
                         'model_version': '1.9.0'},
    NOT_CHECKED:        {'status': NOT_CHECKED, 'probability': 0.4, 'doc_seen': 'tvet_belia_sukan',
                         'model_version': '1.9.0'},
}
_FIELDS = {'fields': {'candidate_name': 'X', 'programme': 'Diploma'}, 'warnings': [], 'error': ''}


def _offer(app, auth):
    return ApplicantDocument.objects.create(
        application=app, doc_type='offer_letter', storage_path=f'{app.id}/of/{auth["status"]}',
        vision_fields={'fields': {'candidate_name': 'X'}, 'student_verdict': 'ok', 'authenticity': dict(auth)})


def _reread_offer(doc, text):
    """The cockpit Re-run / reextract core (`reextract.reextract_document`) with every read mocked."""
    from apps.scholarship.reextract import reextract_document
    with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None), \
         patch('apps.scholarship.vision.ocr_document_full', return_value={'text': text, 'error': None}), \
         patch('apps.scholarship.vision.ocr_document', return_value={'text': text, 'error': None}), \
         patch('apps.scholarship.vision.run_vision_match_for_document'), \
         patch('apps.scholarship.vision.extract_document_fields', return_value=dict(_FIELDS)):
        reextract_document(doc)
    doc.refresh_from_db()
    return doc.vision_fields


class AReReadKeepsTheStoredScore(TestCase):

    def setUp(self):
        self.app = make_application('profile_complete')

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_flag_off_keeps_every_stored_status(self):
        for status, auth in STORED.items():
            with self.subTest(status):
                doc = _offer(self.app, auth)
                with self.assertLogs('apps.scholarship.vision', 'WARNING') as logs:
                    vf = _reread_offer(doc, UITM_OFFER)
                self.assertEqual(vf['authenticity'], auth)
                self.assertEqual(vf['fields'], _FIELDS['fields'])          # the read itself did land
                self.assertTrue(any('DOC_GENUINENESS_CHECK_ENABLED is off' in m and str(doc.id) in m
                                    for m in logs.output), logs.output)

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_flag_on_re_scores(self):
        doc = _offer(self.app, STORED['suspect'])
        vf = _reread_offer(doc, UITM_OFFER)
        self.assertEqual((vf['authenticity']['status'], vf['authenticity']['probability']), ('genuine', 0.9))

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_flag_on_but_no_signal_this_time_keeps_the_score_too(self):
        doc = _offer(self.app, STORED['genuine'])
        with self.assertLogs('apps.scholarship.vision', 'WARNING') as logs:
            vf = _reread_offer(doc, '')                                       # our OCR came back empty
        self.assertEqual(vf['authenticity'], STORED['genuine'])
        self.assertTrue(any('gave no genuineness signal' in m for m in logs.output), logs.output)

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_a_first_read_stores_nothing_new(self):
        doc = ApplicantDocument.objects.create(application=self.app, doc_type='offer_letter',
                                               storage_path=f'{self.app.id}/of/new')
        self.assertNotIn('authenticity', _reread_offer(doc, UITM_OFFER))


class TheICPath(TestCase):

    def setUp(self):
        self.app = make_application('profile_complete')
        self.stored = {'status': 'genuine', 'reason': 'mykad markers'}
        self.ic = ApplicantDocument.objects.create(
            application=self.app, doc_type='ic', storage_path=f'{self.app.id}/ic/x',
            vision_fields={'capture': 'deterministic', 'authenticity': dict(self.stored)})

    def _reread(self, fresh=None):
        read = {'nric': '080808-10-5566', 'name': 'A', 'address': '', 'error': ''}
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'img'), \
             patch('apps.scholarship.vision.extract_mykad', return_value=read), \
             patch('apps.scholarship.vision._should_gemini_ic', return_value=False), \
             patch('apps.scholarship.vision.ic_genuineness', return_value=fresh or {}):
            vision.run_vision_for_document(self.ic)
        self.ic.refresh_from_db()
        return self.ic.vision_fields

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_flag_off_keeps_the_stored_score_and_says_so(self):
        with self.assertLogs('apps.scholarship.vision', 'WARNING') as logs:
            vf = self._reread()
        self.assertEqual(vf['authenticity'], self.stored)
        self.assertTrue(any('TD-407' in m for m in logs.output))

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_flag_on_replaces_it(self):
        vf = self._reread(fresh={'status': 'suspect', 'reason': 'printout'})
        self.assertEqual(vf['authenticity']['status'], 'suspect')


class TheCronSweep(TestCase):
    """`services.read_retry` runs inside the service (flag on); it re-reads through the same core, so a
    re-read that gives no signal this time still keeps the stored score."""

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_the_sweep_keeps_the_score(self):
        from apps.scholarship.services.read_retry import _reread
        app = make_application('profile_complete')
        doc = _offer(app, STORED['genuine'])
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None), \
             patch('apps.scholarship.vision.ocr_document_full', return_value={'text': '', 'error': None}), \
             patch('apps.scholarship.vision.ocr_document', return_value={'text': '', 'error': None}), \
             patch('apps.scholarship.vision.run_vision_match_for_document'), \
             patch('apps.scholarship.vision.extract_document_fields', return_value=dict(_FIELDS)):
            _reread(doc)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity'], STORED['genuine'])


class TheCommandsPreFlight(TestCase):
    """Each HAND-RUN bulk re-read command refuses to start without the genuineness flag (non-zero exit),
    runs with it or with `--allow-without-genuineness`, and only WARNS when billing is off. The HOURLY
    self-heal (`reprocess_unread_ic`) only warns — see `TheHourlySelfHeal`."""

    COMMANDS = (('reextract_documents', 'apps.scholarship.management.commands.reextract_documents.reextract_document'),
                ('reextract_offers', 'apps.scholarship.management.commands.reextract_offers.reextract_document'))
    HOURLY = ('reprocess_unread_ic', 'apps.scholarship.management.commands.reprocess_unread_ic.'
                                     'reprocess_unread_ic_documents')

    def _run(self, name, target, **kw):
        out, err = StringIO(), StringIO()
        ret = {'scanned': 0, 'processed': 0, 'errored': 0, 'by_type': {}}
        with patch(target, return_value=ret if name == 'reprocess_unread_ic' else True) as m:
            call_command(name, stdout=out, stderr=err, **kw)
        self.ran = m.called
        self.out = out.getvalue()
        return err.getvalue()

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_each_command_refuses_without_the_flag(self):
        for name, target in self.COMMANDS:
            with self.subTest(name), self.assertRaisesMessage(CommandError, 'DOC_GENUINENESS_CHECK_ENABLED'):
                self._run(name, target)

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, BILLING_USAGE_ENABLED=True)
    def test_each_command_runs_when_told_to(self):
        for name, target in self.COMMANDS:
            with self.subTest(name):
                self._run(name, target, allow_without_genuineness=True)

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True, BILLING_USAGE_ENABLED=True)
    def test_each_command_runs_with_the_flag_and_says_nothing(self):
        for name, target in self.COMMANDS + (self.HOURLY,):
            with self.subTest(name):
                self.assertEqual(self._run(name, target), '')

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True, BILLING_USAGE_ENABLED=False)
    def test_billing_off_is_a_warning_not_a_refusal(self):
        for name, target in self.COMMANDS + (self.HOURLY,):
            with self.subTest(name):
                self.assertIn('BILLING_USAGE_ENABLED is off', self._run(name, target))

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
    def test_a_dry_run_reads_nothing_so_it_is_never_refused(self):
        for name, target in (self.COMMANDS[1], self.HOURLY):
            with self.subTest(name):
                self._run(name, target, dry_run=True)


class TheHourlySelfHeal(TestCase):
    """TD-407 review: `reprocess_unread_ic` runs HOURLY from the cron endpoint, which swallows a raised
    error as a logged warning and a 200 — a refusal would stop the AI-outage self-heal quietly. A
    flag-off re-read is already safe (stored scores kept), so it WARNS (log + stdout) and runs."""

    HOURLY = TheCommandsPreFlight.HOURLY
    _run = TheCommandsPreFlight._run

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=False, BILLING_USAGE_ENABLED=True)
    def test_it_warns_and_still_runs_without_the_flag(self):
        name, target = self.HOURLY
        with self.assertLogs('apps.scholarship.reextract', 'WARNING') as logs:
            self._run(name, target)
        self.assertTrue(self.ran)
        self.assertIn('DOC_GENUINENESS_CHECK_ENABLED is off', self.out)
        self.assertTrue(any('re-reading anyway' in m for m in logs.output), logs.output)
