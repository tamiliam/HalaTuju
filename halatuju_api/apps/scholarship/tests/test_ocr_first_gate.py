"""OCR-first Gate 1 (`ocr_first_gate.lane_gate`): the edges of the threshold rule (S0, 2026-11-18)."""
from django.test import SimpleTestCase

from apps.scholarship.ocr_first_gate import GUARDED_FIELDS, MIN_DOCS, lane_gate


class LaneGateTests(SimpleTestCase):
    def gate(self, **over):
        args = {'docs': 20, 'core_right': 1000, 'core_total': 1000, 'wrong': {}, 'course_match_wrong': 0}
        args.update(over)
        return lane_gate(**args)

    def test_clean_lane_passes(self):
        result = self.gate()
        self.assertTrue(result.passed)
        self.assertEqual(result.reasons, ())

    def test_twenty_documents_pass_nineteen_fail(self):
        self.assertTrue(self.gate(docs=MIN_DOCS).passed)
        result = self.gate(docs=MIN_DOCS - 1)
        self.assertFalse(result.passed)
        self.assertIn('only 19 held-out documents', result.reasons[0])

    def test_agreement_98_0_passes_97_9_fails(self):
        self.assertTrue(self.gate(core_right=980).passed)
        result = self.gate(core_right=979)
        self.assertFalse(result.passed)
        self.assertIn('97.9%', result.reasons[0])

    def test_one_wrong_in_each_guarded_field_fails(self):
        for field in GUARDED_FIELDS:
            with self.subTest(field=field):
                result = self.gate(wrong={field: 1})
                self.assertFalse(result.passed)
                self.assertEqual(result.reasons, (f'1 wrong {field}',))

    def test_wrong_in_unguarded_field_does_not_gate(self):
        self.assertTrue(self.gate(wrong={'intake': 3, 'reporting_date': 2}).passed)

    def test_wrong_course_match_fails(self):
        result = self.gate(course_match_wrong=1)
        self.assertFalse(result.passed)
        self.assertEqual(result.reasons, ('1 wrong course match',))

    def test_no_core_answered_fails(self):
        result = self.gate(core_right=0, core_total=0)
        self.assertFalse(result.passed)
        self.assertIn('answered no core field', result.reasons[0])

    def test_every_reason_is_listed(self):
        result = self.gate(docs=5, core_right=90, core_total=100, wrong={'name': 1}, course_match_wrong=2)
        self.assertEqual(len(result.reasons), 4)
