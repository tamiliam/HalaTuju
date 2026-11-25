"""#85 — `rescore_salary_statutory`: re-writes, from STORED markers only, the live payslips an older salary
model called not_salary although they show >=2 statutory deductions. Synthetic rows only — no PII."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.scholarship.genuineness.salary_doc import MODEL_VERSION
from apps.scholarship.income_shown import proof_flagged
from apps.scholarship.management.commands import rescore_salary_statutory as cmd
from apps.scholarship.tests.factories import create_document, make_application

_NO_FIELDS = 'no recognisable payslip fields (wage/deduction labels absent)'
_MYKAD = 'MyKad markers, no payslip fields — not a salary slip'


class RescoreSalaryStatutoryTest(TestCase):
    def setUp(self):
        self.app = make_application('submitted')
        self.n = 0

    def _slip(self, statutory=2, wage=0, kwsp=True, version='1.2.0', reason=_NO_FIELDS,
              status='not_salary', doc_type='salary_slip', **kw):
        self.n += 1
        markers = {'statutory': statutory, 'wage': wage}
        if kwsp is not None:
            markers['kwsp'] = kwsp
        auth = {'status': status, 'doc_seen': status, 'probability': 0.10, 'reason': reason,
                'model_version': version, 'markers': markers}
        return create_document(application=self.app, doc_type=doc_type, household_member='mother',
                               storage_path=f'x/{self.n}', vision_fields={'authenticity': auth},
                               request_code=f'r{self.n}', **kw)

    def _run(self, *args):
        out = StringIO()
        call_command('rescore_salary_statutory', *args, stdout=out)
        return out.getvalue()

    # ── the selector ────────────────────────────────────────────────────────────
    def test_selects_only_the_rows_the_old_order_got_wrong(self):
        hit2, hit3 = self._slip(statutory=2), self._slip(statutory=3)
        self._slip(statutory=1)                                    # one deduction: still not a payslip
        self._slip(reason=_MYKAD)                                  # the MyKad reject stands
        self._slip(version=MODEL_VERSION)                          # already scored by the fixed model
        self._slip(version='')                                     # no version: not ours to guess
        self._slip(kwsp=None)                                      # pre-1.1.0 markers: incomplete
        self._slip(wage=1)                                         # not the old reject's shape
        self._slip(status='genuine')                               # not a not_salary row
        self._slip(doc_type='income_support_doc')                  # not a payslip slot
        self._slip(statutory=4, superseded_at=timezone.now())      # replaced: not live
        self.assertEqual([d.id for d in cmd.rescore_candidates()], [hit2.id, hit3.id])

    def test_the_new_result_is_the_fixed_scorers_answer(self):
        doc = self._slip(statutory=2, kwsp=False)
        auth = cmd.rescored_authenticity(doc)
        self.assertEqual((auth['status'], auth['doc_seen'], auth['probability']), ('genuine', 'private', 0.8))
        self.assertEqual(auth['model_version'], MODEL_VERSION)
        self.assertEqual(auth['markers'], {'statutory': 2, 'wage': 0, 'kwsp': False})
        self.assertEqual(auth['rescored']['basis'], 'stored_markers')
        self.assertEqual(auth['rescored']['from_model_version'], '1.2.0')

    # ── dry run and apply ───────────────────────────────────────────────────────
    def test_dry_run_prints_ids_and_counts_and_writes_nothing(self):
        doc = self._slip(statutory=3)
        before = dict(doc.vision_fields)
        out = self._run()
        self.assertIn('DRY-RUN', out)
        self.assertIn(f'document {doc.id} case {self.app.id}: not_salary -> genuine/private', out)
        self.assertIn('selected=1 written=0', out)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields, before)
        self.assertTrue(proof_flagged(doc, 'salary_slip'))

    def test_apply_writes_and_the_slip_counts_again(self):
        doc = self._slip(statutory=2)
        out = self._run('--apply')
        self.assertIn('APPLIED', out)
        self.assertIn('selected=1 written=1', out)
        doc.refresh_from_db()
        self.assertEqual(doc.vision_fields['authenticity']['status'], 'genuine')
        self.assertFalse(proof_flagged(doc, 'salary_slip'))       # the income-evidence blocker lifts
        self.assertIn('selected=0 written=0', self._run('--apply'))   # idempotent
