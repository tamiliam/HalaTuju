"""Contract module — deploy validation (T / C / Q / S / P rules + W warnings).

Every rule has a failing→passing test: start from a deployable draft (the seeded
BrightPath fixture + test counterparty + attestation, which passes cleanly),
break exactly one thing → the rule's code appears; fix it → the code is gone.
"""
from decimal import Decimal

from django.test import TestCase

from apps.scholarship import contracts
from apps.scholarship.tests.contract_helpers import make_deployable

VALID_QUIZ = {'tag': 't', 'plain': 'p', 'question': 'q',
              'options': ['a', 'b', 'c'], 'correct': 1, 'why': 'w'}


def errors(template):
    return contracts.validate_for_deployment(template).errors


def warnings(template):
    return contracts.validate_for_deployment(template).warnings


class TestBaselineIsDeployable(TestCase):
    def test_seeded_draft_with_counterparty_and_attestation_passes(self):
        result = contracts.validate_for_deployment(make_deployable())
        self.assertTrue(result.ok, f'unexpected errors: {result.errors}')


class TestTemplateRules(TestCase):
    def test_T1_counterparty_required(self):
        t = make_deployable()
        self.assertNotIn('T1', errors(t))
        t.counterparty_nric = ''
        t.save(update_fields=['counterparty_nric'])
        self.assertIn('T1', errors(t))
        t.counterparty_nric = '000000-00-0000'
        t.save(update_fields=['counterparty_nric'])
        self.assertNotIn('T1', errors(t))

    def test_T2_attestation_required(self):
        t = make_deployable()
        self.assertNotIn('T2', errors(t))
        t.vetted_by_name = ''
        t.save(update_fields=['vetted_by_name'])
        self.assertIn('T2', errors(t))


class TestClauseRules(TestCase):
    def test_C1_clauses_must_be_contiguous(self):
        t = make_deployable()
        self.assertNotIn('C1', errors(t))
        # Delete a MIDDLE clause → a gap in the 1..N ordering.
        t.clauses.get(order=8).delete()
        self.assertIn('C1', errors(t))

    def test_C2_english_must_be_complete(self):
        t = make_deployable()
        self.assertNotIn('C2', errors(t))
        c = t.clauses.get(order=3)
        c.body_en = ''
        c.save(update_fields=['body_en'])
        self.assertIn('C2', errors(t))


class TestQuizRules(TestCase):
    def test_Q1_at_least_one_quiz_candidate(self):
        t = make_deployable()
        self.assertNotIn('Q1', errors(t))
        for c in t.clauses.all():
            c.is_quiz_candidate = False
            c.quiz_en, c.quiz_ms, c.quiz_ta = {}, {}, {}
            c.save()
        errs = errors(t)
        self.assertIn('Q1', errs)
        self.assertNotIn('Q3', errs)  # cleared payloads → Q3 does not fire

    def test_Q2_quiz_en_must_be_structurally_valid(self):
        t = make_deployable()
        self.assertNotIn('Q2', errors(t))
        c = t.clauses.filter(is_quiz_candidate=True).first()
        c.quiz_en = {'options': ['a', 'b'], 'correct': 0}  # only 2 options
        c.save(update_fields=['quiz_en'])
        self.assertIn('Q2', errors(t))

    def test_Q3_no_quiz_on_a_non_candidate(self):
        t = make_deployable()
        self.assertNotIn('Q3', errors(t))
        c = t.clauses.filter(is_quiz_candidate=False).first()
        c.quiz_en = dict(VALID_QUIZ)
        c.save(update_fields=['quiz_en'])
        self.assertIn('Q3', errors(t))

    def test_Q4_per_language_correct_index_must_match(self):
        t = make_deployable()
        self.assertNotIn('Q4', errors(t))
        c = t.clauses.filter(is_quiz_candidate=True).first()
        mismatched = dict(VALID_QUIZ)
        mismatched['correct'] = 0  # en base is 1
        c.quiz_ms = mismatched
        c.save(update_fields=['quiz_ms'])
        self.assertIn('Q4', errors(t))


class TestScheduleRules(TestCase):
    def test_S1_default_row_required(self):
        t = make_deployable()
        self.assertNotIn('S1', errors(t))
        t.schedule_rows.get(pathway='default', variant='').delete()
        self.assertIn('S1', errors(t))

    def test_S2_row_shape_must_be_valid(self):
        t = make_deployable()
        self.assertNotIn('S2', errors(t))
        r = t.schedule_rows.get(pathway='matric', variant='')
        r.start_month = 0  # out of 1..12
        r.save(update_fields=['start_month'])
        self.assertIn('S2', errors(t))

    def test_S3_total_must_be_an_allowed_amount(self):
        t = make_deployable()
        self.assertNotIn('S3', errors(t))
        r = t.schedule_rows.get(pathway='default', variant='')
        r.paid_offsets = [0, 1, 2]  # 3 × 200 = 600, not in ALLOWED_AMOUNTS
        r.save(update_fields=['paid_offsets'])
        self.assertIn('S3', errors(t))

    def test_S4_total_must_cross_check_award(self):
        t = make_deployable()
        self.assertNotIn('S4', errors(t))
        r = t.schedule_rows.get(pathway='default', variant='')
        r.paid_offsets = [0, 1, 2, 3, 4]  # 5 × 200 = 1000 (allowed) but default expects 2000
        r.save(update_fields=['paid_offsets'])
        errs = errors(t)
        self.assertIn('S4', errs)
        self.assertNotIn('S3', errs)  # 1000 IS an allowed amount → only the cross-check fails


class TestV1FenceRule(TestCase):
    def test_P1_minor_only_unsupported(self):
        t = make_deployable()
        self.assertNotIn('P1', errors(t))
        t.parent_role = 'minor_only'
        t.save(update_fields=['parent_role'])
        self.assertIn('P1', errors(t))

    def test_P1_witness_required_unsupported(self):
        t = make_deployable()
        t.witness_policy = 'required'
        t.save(update_fields=['witness_policy'])
        self.assertIn('P1', errors(t))


class TestWarnings(TestCase):
    def test_W1_guarantor_term_while_co_signer_all(self):
        # The seeded preamble says "surety/guarantor" while parent_role=co_signer_all.
        self.assertIn('W1', warnings(make_deployable()))

    def test_W2_incomplete_translations(self):
        # ms lacks a Malay progress standard; ta clauses are blank → neither fully available.
        self.assertIn('W2', warnings(make_deployable()))

    def test_W3_rm_literal_in_clause_body(self):
        t = make_deployable()
        self.assertNotIn('W3', warnings(t))
        c = t.clauses.get(order=1)
        c.body_en = c.body_en + ' You will receive RM200 per month.'
        c.save(update_fields=['body_en'])
        self.assertIn('W3', warnings(t))
