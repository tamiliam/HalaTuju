"""Check-2 case summary (verdict_narrative). The LLM seam is mocked — no billable call.
Covers: the band label mirrors officerCockpit.factTileTone; item gloss + interpolation;
the generator's flag gate, all-Certain short-circuit, caching, and error passthrough."""
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.scholarship import verdict_narrative as vn


def _fact(fact, status, evidence=None, unresolved=None):
    return {'fact': fact, 'status': status,
            'evidence': evidence or [], 'unresolved': unresolved or []}


def _item(code, **params):
    return {'code': code, 'params': params}


class TestFactBand(SimpleTestCase):
    """Must mirror halatuju-web officerCockpit.factTileTone + TONE_BAND_KEY."""
    def test_verified_is_certain(self):
        self.assertEqual(vn._fact_band(_fact('income', 'verified')), 'Certain')

    def test_recommend_is_unsure(self):
        self.assertEqual(vn._fact_band(_fact('income', 'recommend')), 'Unsure')

    def test_gap_is_cant_verify(self):
        self.assertEqual(vn._fact_band(_fact('income', 'gap')), "Can't verify")

    def test_review_with_a_green_is_probable(self):
        f = _fact('income', 'review', evidence=[_item('relationship_confirmed')])
        self.assertEqual(vn._fact_band(f), 'Probable')

    def test_review_with_only_soft_evidence_is_unsure(self):
        # A review backed only by a soft signal (utility_hardship) is Unsure, not Probable.
        f = _fact('income', 'review', evidence=[_item('utility_hardship')])
        self.assertEqual(vn._fact_band(f), 'Unsure')


class TestRenderItem(SimpleTestCase):
    def test_interpolates_amount(self):
        self.assertIn('RM688', vn._render_item(_item('income_salary_probable', amount='688')))

    def test_str_not_current_is_status_specific(self):
        self.assertIn('NOT an STR', vn._render_item(_item('str_not_current', status='wrong_type')))
        self.assertIn('PRIOR cycle', vn._render_item(_item('str_not_current', status='stale')))

    def test_members_list_joins(self):
        self.assertIn('father', vn._render_item(_item('earner_ic_missing', members=['father'])))

    def test_unknown_code_falls_back_to_humanised(self):
        self.assertEqual(vn._render_item(_item('some_new_code')), 'some new code')


@override_settings(VERDICT_CASE_SUMMARY_ENABLED=True)
class TestVerdictCaseSummary(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.app = SimpleNamespace(id=102)
        # An income fact that isn't Certain (wrong_type STR → salary probable).
        self.facts = [
            _fact('identity', 'verified'),
            _fact('income', 'review',
                  evidence=[_item('relationship_confirmed'),
                            _item('income_salary_probable', amount='688')],
                  unresolved=[_item('str_not_current', status='wrong_type')]),
        ]

    def test_flag_off_returns_disabled(self):
        with override_settings(VERDICT_CASE_SUMMARY_ENABLED=False):
            self.assertEqual(vn.verdict_case_summary(self.app), {'enabled': False})

    def test_generates_and_caches(self):
        with mock.patch.object(vn, 'build_verdict', return_value=self.facts), \
             mock.patch.object(vn, '_call_gemini_text',
                               return_value={'markdown': 'Probable B40, on the salary route.',
                                             'model_used': 'gemini-2.5-flash'}) as gem:
            first = vn.verdict_case_summary(self.app)
            self.assertEqual(first['summary'], 'Probable B40, on the salary route.')
            self.assertFalse(first['cached'])
            second = vn.verdict_case_summary(self.app)          # same verdict → cache hit
            self.assertTrue(second['cached'])
            self.assertEqual(gem.call_count, 1)                 # not re-called per open

    def test_all_certain_returns_empty(self):
        with mock.patch.object(vn, 'build_verdict', return_value=[_fact('income', 'verified')]), \
             mock.patch.object(vn, '_call_gemini_text') as gem:
            res = vn.verdict_case_summary(self.app)
            self.assertEqual(res['summary'], '')
            gem.assert_not_called()

    def test_gemini_error_is_passed_through(self):
        with mock.patch.object(vn, 'build_verdict', return_value=self.facts), \
             mock.patch.object(vn, '_call_gemini_text', return_value={'error': 'boom'}):
            self.assertEqual(vn.verdict_case_summary(self.app).get('error'), 'boom')

    def test_prompt_carries_grounding_and_rules(self):
        captured = {}
        def _fake(prompt, lang, models=None):
            captured['prompt'] = prompt
            return {'markdown': 'ok'}
        with mock.patch.object(vn, 'build_verdict', return_value=self.facts), \
             mock.patch.object(vn, '_call_gemini_text', side_effect=_fake):
            vn.verdict_case_summary(self.app)
        p = captured['prompt']
        self.assertIn('verdict band: Probable', p)         # the ported band
        self.assertIn('NOT an STR', p)                      # glossed open finding
        self.assertIn('GROSS', p)                           # the gross/per-capita rule
        self.assertIn('never', p.lower())                   # the "never invent / never take-home" rules
