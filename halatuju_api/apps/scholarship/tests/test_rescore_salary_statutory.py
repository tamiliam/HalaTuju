"""#85 — `rescore_salary_statutory`: re-writes the live 1.2.x payslips called not_salary although they show
>=2 statutory deductions — from stored OCR text when there is some (whole-word rule), from stored markers
only after an eye check (`--include-no-text`). Synthetic rows and text only — no PII."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.genuineness.salary_doc import MODEL_VERSION
from apps.scholarship.income_shown import proof_flagged
from apps.scholarship.management.commands import rescore_salary_statutory as cmd
from apps.scholarship.models import ApplicantDocumentOcrText
from apps.scholarship.tests.factories import create_document, make_application

_NO_FIELDS = 'no recognisable payslip fields (wage/deduction labels absent)'
_MYKAD = 'MyKad markers, no payslip fields — not a salary slip'
_GOOD_TEXT = 'KWSP 308.00\nPERKESO 12.75\nPCB 40.00\nMac 2026'
_LEISURE_TEXT = 'KWSP i-Akaun\nLeisure'                      # 2 by substring, 1 as whole words


class RescoreSalaryStatutoryTest(TestCase):
    def setUp(self):
        self.app = make_application('submitted')
        self.n = 0

    def _slip(self, statutory=2, wage=0, kwsp=True, version='1.2.0', reason=_NO_FIELDS,
              status='not_salary', doc_type='salary_slip', text=None, **kw):
        self.n += 1
        markers = {'statutory': statutory, 'wage': wage}
        if kwsp is not None:
            markers['kwsp'] = kwsp
        auth = {'status': status, 'doc_seen': status, 'probability': 0.10, 'reason': reason,
                'model_version': version, 'markers': markers}
        doc = create_document(application=self.app, doc_type=doc_type, household_member='mother',
                              storage_path=f'x/{self.n}', vision_fields={'authenticity': auth},
                              request_code=f'r{self.n}', **kw)
        if text is not None:
            ApplicantDocumentOcrText.objects.create(document=doc, text=text, source='vision_ocr',
                                                    stored_at=timezone.now())
        return doc

    def _run(self, *args):
        out = StringIO()
        call_command('rescore_salary_statutory', *args, stdout=out)
        return out.getvalue()

    # ── the selector ────────────────────────────────────────────────────────────
    def test_selects_only_1_2_rows_the_old_order_got_wrong(self):
        hit2, hit3 = self._slip(statutory=2), self._slip(statutory=3, version='1.2.5')
        self._slip(statutory=1)                                    # one deduction: still not a payslip
        self._slip(reason=_MYKAD)                                  # the MyKad reject stands
        self._slip(version=MODEL_VERSION)                          # already scored by the fixed model
        self._slip(version='')                                     # no version: not ours to guess
        self._slip(kwsp=None)                                      # pre-1.1.0 markers: incomplete
        self._slip(wage=1)                                         # not the old reject's shape
        self._slip(status='genuine')                               # not a not_salary row
        self._slip(doc_type='income_support_doc')                  # not a payslip slot
        self._slip(statutory=4, superseded_at=timezone.now())      # replaced: not live
        old_11, old_10 = self._slip(version='1.1.0'), self._slip(version='1.0.0', kwsp=None)
        docs, older = cmd.rescore_candidates()
        self.assertEqual([d.id for d in docs], [hit2.id, hit3.id])
        self.assertEqual([d.id for d in older], [old_11.id, old_10.id])

    def test_an_older_model_row_is_listed_and_never_written(self):
        """Fix 1: a 1.1.0 not_salary may be a statutory declaration (recognised from 1.2.0); a fresh read
        would make it suspect/declaration, so it is only counted — even with --include-no-text."""
        doc = self._slip(version='1.1.0', text='AKUAN BERKANUN\nKWSP dan PERKESO')
        out = self._run('--apply', '--include-no-text')
        self.assertIn('selected=0', out)
        self.assertIn(f'older model (< 1.2.0, never written): count=1 ids=[{doc.id}]', out)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'not_salary')

    # ── stored OCR text: the whole-word rule decides ─────────────────────────────
    def test_text_that_passes_is_rescored_from_the_text(self):
        doc = self._slip(text=_GOOD_TEXT)
        outcome, auth = cmd.rescored_authenticity(doc, _GOOD_TEXT)
        self.assertEqual(outcome, cmd.TEXT_OK)
        self.assertEqual((auth['status'], auth['doc_seen'], auth['probability']), ('genuine', 'private', 0.9))
        self.assertEqual(auth['model_version'], MODEL_VERSION)
        self.assertEqual(auth['rescored']['basis'], 'stored_ocr_text')
        self.assertEqual(auth['rescored']['from_model_version'], '1.2.0')

    def test_text_that_fails_the_whole_word_rule_is_left_alone(self):
        doc = self._slip(text=_LEISURE_TEXT)
        out = self._run('--apply', '--include-no-text')
        self.assertIn(f'document {doc.id} case {self.app.id} model 1.2.0: stays not_salary', out)
        self.assertIn('text_ok=0 text_fails=1 needs_eye_check=0 written=0', out)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'not_salary')

    # ── no stored text: eye check first ─────────────────────────────────────────
    def test_no_text_is_listed_for_an_eye_check_and_not_written_by_default(self):
        doc = self._slip()
        out = self._run('--apply')
        self.assertIn(f'document {doc.id} case {self.app.id} model 1.2.0: needs eye check', out)
        self.assertIn(f'needs eye check (written only with --include-no-text): ids=[{doc.id}]', out)
        self.assertIn('needs_eye_check=1 written=0', out)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'not_salary')

    def test_include_no_text_writes_from_the_stored_markers(self):
        doc = self._slip(statutory=2, kwsp=False)
        self.assertIn('written=1', self._run('--apply', '--include-no-text'))
        doc.refresh_from_db()
        auth = doc.vision_fields['authenticity']
        self.assertEqual((auth['status'], auth['doc_seen'], auth['probability']), ('genuine', 'private', 0.8))
        self.assertEqual(auth['markers'], {'statutory': 2, 'wage': 0, 'kwsp': False})
        self.assertEqual(auth['rescored']['basis'], 'stored_markers_eye_checked')

    # ── dry run and apply ───────────────────────────────────────────────────────
    def test_dry_run_prints_ids_and_counts_and_writes_nothing(self):
        doc = self._slip(statutory=3, text=_GOOD_TEXT)
        before = dict(doc.vision_fields)
        out = self._run('--include-no-text')
        self.assertIn('DRY-RUN', out)
        self.assertIn(f'document {doc.id} case {self.app.id} model 1.2.0: not_salary -> genuine/private', out)
        self.assertIn('selected=1 text_ok=1 text_fails=0 needs_eye_check=0 written=0', out)
        self.assertNotIn('PERKESO 12.75', out)                     # the text itself is never printed
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields, before)
        self.assertTrue(proof_flagged(doc, 'salary_slip'))

    def test_apply_writes_and_the_slip_counts_again(self):
        doc = self._slip(statutory=2, text=_GOOD_TEXT)
        out = self._run('--apply')
        self.assertIn('APPLIED', out)
        self.assertIn('text_ok=1 text_fails=0 needs_eye_check=0 written=1', out)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'genuine')
        self.assertFalse(proof_flagged(doc, 'salary_slip'))       # the income-evidence blocker lifts
        self.assertIn('selected=0', self._run('--apply'))          # idempotent

    def test_a_row_that_changed_before_the_lock_is_not_written(self):
        """The write re-fetches the row under a lock and re-checks it: a re-read since selection wins."""
        doc = self._slip(text=_GOOD_TEXT)
        docs, _ = cmd.rescore_candidates()
        self.assertEqual([d.id for d in docs], [doc.id])
        reread = dict(doc.vision_fields['authenticity'], status='suspect', model_version=MODEL_VERSION)
        type(doc).objects.filter(pk=doc.pk).update(vision_fields={'authenticity': reread})
        self.assertFalse(cmd._write(doc.id, include_no_text=False))
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity'], reread)
