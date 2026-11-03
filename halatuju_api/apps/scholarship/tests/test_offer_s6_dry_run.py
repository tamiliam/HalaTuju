"""The S6 production dry run (`eval/offer_s6_dry_run.py`, run as `offer_s4_dry_run.py --s6`): the deploy
pass (old rules vs new on STORED data), the re-score pass (the S7 preview), the GO / STOP rules, the same
read-only rolled-back session, ids and outcomes only.

Synthetic twins only (`test_no_gitignored_corpus.py`): invented people and letters in a temp corpus; the
"database" is the test SQLite (`--allow-sqlite`). Never production."""
import json
import os
import tempfile

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship.eval import offer_s4_dry_run as dr
from apps.scholarship.eval import offer_s6_dry_run as s6
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_rulings import IKM


class RunTest(TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        snap = os.path.join(self._tmp.name, 'snapshots')
        os.makedirs(snap)
        self.app = make_application('shortlisted', chosen_pathway='ilkbs')
        prof = self.app.profile
        self.fields = {'candidate_name': prof.name, 'candidate_nric': prof.nric.replace('-', ''),
                       'programme': 'DIPLOMA KEMAHIRAN CONTOH', 'institution': 'INSTITUT KEMAHIRAN MARA CONTOH',
                       'reporting_date': ''}
        self.doc = ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter', storage_path=f'{self.app.id}/offer/x',
            vision_fields={'fields': dict(self.fields), 'student_verdict': 'ok', 'warnings': [], 'error': '',
                           'authenticity': {'status': 'suspect', 'doc_seen': 'polytechnic', 'probability': 0.4}},
            vision_run_at=timezone.now())
        self.key = f'offer_letter__a{self.app.id}__d{self.doc.id}'
        with open(os.path.join(snap, self.key + '.offer_expect.json'), 'w', encoding='utf-8') as fh:
            json.dump({'is_offer_letter': 'yes'}, fh)
        with open(os.path.join(snap, self.key + '.ocr.meta.json'), 'w', encoding='utf-8') as fh:
            json.dump({'path': 'text_layer'}, fh)
        with open(os.path.join(snap, self.key + '.ocr.txt'), 'w', encoding='utf-8') as fh:
            fh.write(IKM)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *extra):
        lines = []
        rc = dr.main(['--s6', '--eval-dir', self._tmp.name, '--allow-sqlite', *extra], out=lines.append)
        return rc, lines

    def test_a_suspect_offer_is_unblocked_the_chips_follow_the_table_and_nothing_is_written(self):
        rc, lines = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(lines[-1], 'verdict: GO')
        text = '\n'.join(lines)
        self.assertIn(f'unblocked=[{self.app.id}]', text)                      # ruling 8, for the owner
        self.assertIn('chip:pathway:not->partial', text)                       # never red
        self.assertIn('band:', text)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.vision_fields['authenticity']['status'], 'suspect')   # untouched
        for secret in (self.app.profile.name.upper(), self.app.profile.nric.replace('-', ''), 'KEMAHIRAN'):
            self.assertNotIn(secret, text.upper())

    def test_the_rescore_pass_previews_s7(self):
        rc, lines = self._run('--keys', self.key)
        rescore = [x for x in lines if x.strip().startswith('RESCORE')]
        self.assertEqual(len(rescore), 1)
        self.assertIn('suspect->genuine (polytechnic->tvet_mara)', rescore[0])
        self.assertIn("'official': 'verified'", rescore[0])
        self.assertIn('fails=False', rescore[0])


class JudgeTest(SimpleTestCase):
    def _row(self, **o):
        r = {'app': 1, 'doc': 2, 'stored': 'suspect', 'open': True, 'band_old': 'Unsure', 'band_new': 'Probable',
             'blocked_old': True, 'blocked_new': False, 'chips_old': {'name': 'verified', 'pathway': 'not'},
             'chips_new': {'name': 'verified', 'pathway': 'partial'}, 'set_by_offer': False}
        r.update(o)
        return r

    def test_go_on_an_unblocked_suspect(self):
        verdict, stop, review, _t = s6.judge([self._row()])
        self.assertEqual((verdict, stop, review['unblocked']), ('GO', [], [1]))

    def test_stop_on_a_falling_band(self):
        self.assertEqual(s6.judge([self._row(band_old='Certain', band_new='Probable')])[0], 'STOP')

    def test_stop_on_a_new_block_that_is_not_a_fail(self):
        self.assertEqual(s6.judge([self._row(blocked_old=False, blocked_new=True)])[0], 'STOP')

    def test_a_new_block_on_a_fail_is_review_not_stop(self):
        verdict, _stop, review, _t = s6.judge([self._row(stored='not_offer_letter', blocked_old=False,
                                                          blocked_new=True)])
        self.assertEqual((verdict, review['newly_blocked_not_offer']), ('GO', [1]))

    def test_stop_on_an_unblock_that_is_not_a_suspect(self):
        self.assertEqual(s6.judge([self._row(stored='genuine')])[0], 'STOP')

    def test_stop_on_a_new_red_identity_chip_or_a_red_pathway_chip(self):
        self.assertEqual(s6.judge([self._row(chips_new={'name': 'not', 'pathway': 'partial'})])[0], 'STOP')
        self.assertEqual(s6.judge([self._row(chips_new={'name': 'verified', 'pathway': 'not'})])[0], 'STOP')

    def test_the_chip_mirrors_follow_the_owner_table(self):
        chk = {'name': 'unreadable', 'ic': 'mismatch', 'pathway': 'mismatch', 'reporting_date': ''}
        self.assertEqual(s6.new_chips(chk, 'suspect'),
                         {'name': 'partial', 'ic': 'not', 'pathway': 'partial', 'official': 'partial',
                          'reportingDate': 'partial'})
        self.assertEqual(s6.old_chips(chk, 'suspect'),
                         {'name': 'not', 'ic': 'not', 'pathway': 'not', 'official': 'partial'})
