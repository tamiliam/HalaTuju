"""Synthetic self-test for the document-recognition eval harness — no Gemini, no real
files, no PII. Proves the Layer-B scorer drives the real `doc_match_verdict` and scores
pass / fail / skip correctly against a temp eval set."""
import json
import os
import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

_RAN = '2026-06-15T00:00:00+00:00'


class EvalDocRecognitionHarnessTest(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='eval_test_')
        os.makedirs(os.path.join(self.dir, 'snapshots'))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def _write(self, name, obj):
        with open(os.path.join(self.dir, name), 'w', encoding='utf-8') as f:
            json.dump(obj, f)

    def _snapshot(self, key, obj):
        with open(os.path.join(self.dir, 'snapshots', f'{key}.json'), 'w', encoding='utf-8') as f:
            json.dump(obj, f)

    def _run(self):
        out = StringIO()
        call_command('eval_doc_recognition', '--eval-dir', self.dir, '--json', stdout=out)
        return json.loads(out.getvalue())

    def test_scores_pass_fail_against_doc_match_verdict(self):
        nric, name = '030101-14-1234', 'PRIYA DEVI'
        # 1) clean IC matching the profile → verdict 'ok'; label expects 'ok' → PASS
        self._snapshot('ic_match', {'vision_nric': nric, 'vision_name': name, 'vision_run_at': _RAN, 'vision_fields': {}})
        # 2) IC whose NRIC differs from the profile → verdict 'mismatch'; label expects 'mismatch' → PASS
        self._snapshot('ic_mismatch', {'vision_nric': '999999-99-9999', 'vision_name': name, 'vision_run_at': _RAN, 'vision_fields': {}})
        # 3) clean IC but the label WRONGLY expects 'mismatch' → harness must catch it as FAIL
        self._snapshot('ic_wronglabel', {'vision_nric': nric, 'vision_name': name, 'vision_run_at': _RAN, 'vision_fields': {}})
        self._write('context.json', {
            'ic_match': {'profile_name': name, 'profile_nric': nric},
            'ic_mismatch': {'profile_name': name, 'profile_nric': nric},
            'ic_wronglabel': {'profile_name': name, 'profile_nric': nric},
        })
        self._write('labels.json', {'docs': {
            'ic_match': {'doc_type': 'ic', 'expect_verdict': 'ok'},
            'ic_mismatch': {'doc_type': 'ic', 'expect_verdict': 'mismatch'},
            'ic_wronglabel': {'doc_type': 'ic', 'expect_verdict': 'mismatch'},
        }})

        report = self._run()
        self.assertEqual(report['total'], 3)
        self.assertEqual(report['passed'], 2)
        self.assertEqual(report['failed'], 1)
        by_key = {r['key']: r for r in report['results']}
        self.assertEqual((by_key['ic_match']['status'], by_key['ic_match']['actual']), ('pass', 'ok'))
        self.assertEqual((by_key['ic_mismatch']['status'], by_key['ic_mismatch']['actual']), ('pass', 'mismatch'))
        self.assertEqual((by_key['ic_wronglabel']['status'], by_key['ic_wronglabel']['actual']), ('fail', 'ok'))

    def test_missing_snapshot_is_skipped_not_crash(self):
        self._write('labels.json', {'docs': {'missing': {'doc_type': 'ic', 'expect_verdict': 'ok'}}})
        report = self._run()
        self.assertEqual(report['results'][0]['status'], 'no_snapshot')

    def test_fixtures_are_not_persisted(self):
        """Every fixture is built inside a rolled-back transaction → nothing leaks to the DB."""
        from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
        self._snapshot('ic_match', {'vision_nric': '030101-14-1234', 'vision_name': 'X', 'vision_run_at': _RAN, 'vision_fields': {}})
        self._write('context.json', {'ic_match': {'profile_name': 'X', 'profile_nric': '030101-14-1234'}})
        self._write('labels.json', {'docs': {'ic_match': {'doc_type': 'ic', 'expect_verdict': 'ok'}}})
        self._run()
        self.assertEqual(ApplicantDocument.objects.count(), 0)
        self.assertEqual(ScholarshipApplication.objects.count(), 0)


class EvalCorpusGenuinenessTest(TestCase):
    """TD-121 (Sprint A2.8b): the ``--auto-ok`` corpus scorecard reads the STORED genuineness too, walks
    only real ``<doc_type>/`` folders, and honours the labels.json corpus notes. Synthetic, no model call."""
    NRIC, NAME = '030101-14-1234', 'PRIYA DEVI'

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='eval_corpus_')
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        os.makedirs(os.path.join(self.dir, 'snapshots'))
        self.context = {}

    def _file(self, *parts):
        path = os.path.join(self.dir, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').close()

    def _ic(self, where, key, status=None, app=1):
        """A clean IC read (content matches the profile) filed under fixtures/ or counter_examples/."""
        vf = {'authenticity': {'status': status}} if status else {}
        with open(os.path.join(self.dir, 'snapshots', f'{key}.json'), 'w', encoding='utf-8') as f:
            json.dump({'vision_nric': self.NRIC, 'vision_name': self.NAME, 'vision_run_at': _RAN,
                       'vision_fields': vf}, f)
        self._file(where, 'ic', f'{key}.jpg')
        self.context[key] = {'_app_id': app, 'profile_name': self.NAME, 'profile_nric': self.NRIC}

    def _run(self, labels=None):
        with open(os.path.join(self.dir, 'context.json'), 'w', encoding='utf-8') as f:
            json.dump(self.context, f)
        with open(os.path.join(self.dir, 'labels.json'), 'w', encoding='utf-8') as f:
            json.dump(labels or {}, f)
        out = StringIO()
        call_command('eval_doc_recognition', '--eval-dir', self.dir, '--auto-ok', '--json', stdout=out)
        return json.loads(out.getvalue())

    def test_a_counter_example_is_caught_by_its_stored_genuineness(self):
        """The typed-fake class (a16): the content matches, but the stored score says suspect."""
        self._ic('counter_examples', 'ic__fake', status='suspect', app=1)
        self._ic('counter_examples', 'ic__unscored', app=2)
        report = self._run()
        by = {r['key']: r for r in report['results']}
        self.assertEqual((by['ic__fake']['verdict'], by['ic__fake']['correct'], by['ic__fake']['caught_by']),
                         ('ok', True, 'genuineness'))
        self.assertFalse(by['ic__unscored']['correct'])          # nothing flags it: a false negative
        self.assertEqual(report['genuineness']['counter'], {'flagged': 1, 'genuine': 0, 'unscored': 1})
        self.assertEqual(report['genuineness']['counter_caught_by_genuineness_only'], 1)

    def test_genuine_docs_report_their_stored_score(self):
        self._ic('fixtures', 'ic__good', status='likely_genuine', app=1)   # legacy value folds to genuine
        self._ic('fixtures', 'ic__unread', app=2)
        report = self._run()
        self.assertEqual((report['genuine'], report['false_positives']), (2, 0))
        self.assertEqual(report['genuineness']['genuine_docs'], {'genuine': 1, 'flagged': 0, 'unscored': 1})

    def test_only_doc_type_folders_are_walked(self):
        """The old walk recursed into the nested corpora and scored their files as a type called
        'snapshots', and a same-stem nested copy overwrote the real document."""
        self._ic('fixtures', 'ic__good', app=1)
        self._file('fixtures', 'offer_letters_2026-11-01', 'snapshots', 'ic__good.json')
        self._file('fixtures', 'results_split', 'x.json')
        report = self._run()
        self.assertEqual([(r['key'], r['doc_type']) for r in report['results']], [('ic__good', 'ic')])
        self.assertEqual(report['skipped_folders'], ['offer_letters_2026-11-01', 'results_split'])

    def test_corpus_relabels_and_known_notes(self):
        self._ic('fixtures', 'ic__ruled_red', app=1)
        self._ic('fixtures', 'ic__good', app=2)
        report = self._run({'corpus_relabels': {'ic__ruled_red': {'expect': 'flag', 'why': 'owner ruling'}},
                            'corpus_known': {'ic__ruled_red': {'why': 'a note'}}})
        by = {r['key']: r for r in report['results']}
        self.assertEqual((by['ic__ruled_red']['expect'], by['ic__ruled_red']['relabelled'],
                          by['ic__ruled_red']['known']), ('flag', True, 'a note'))
        self.assertEqual(by['ic__good']['expect'], 'ok')

    def test_owner_offer_rulings_are_read_from_their_one_home(self):
        """A letter the owner ruled not genuine is expected FLAGGED; a genuine ruling moves nothing."""
        with open(os.path.join(self.dir, 'offer_genuineness_expect.json'), 'w', encoding='utf-8') as f:
            json.dump({'expect': {'ic__ruled': 'suspect', 'ic__good': 'genuine'}}, f)
        self._ic('fixtures', 'ic__ruled', app=1)
        self._ic('fixtures', 'ic__good', app=2)
        by = {r['key']: r for r in self._run()['results']}
        self.assertEqual((by['ic__ruled']['expect'], by['ic__good']['expect']), ('flag', 'ok'))


class EvalFixtureSameSlotTest(TestCase):
    def test_two_same_slot_corpus_docs_build_without_error(self):
        from apps.scholarship._test_fixtures import build_application_with_docs
        built = build_application_with_docs(
            {}, [{'doc_type': 'ic', 'snapshot': {}}, {'doc_type': 'ic', 'snapshot': {}}])
        self.assertEqual(len(built), 2)
        self.assertTrue(all(d.superseded_at is None for d in built))
