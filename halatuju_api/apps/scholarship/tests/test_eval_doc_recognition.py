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
