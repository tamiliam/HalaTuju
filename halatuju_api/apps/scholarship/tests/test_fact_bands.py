"""F2 (fix plan): the AI Prediction band of each fact, ONE home on the server (`fact_bands`).

1. Parity: every case the web's jest suite pinned for `factTileTone` / `factBandKey` (officerCockpit
   .test.ts, verdictTileHigherResults.test.ts) before F2 deleted them, plus every confident
   disqualifier and every display override, read through `fact_band`.
2. The SOFT drift guard (was the web's soft-evidence-drift.test.ts): `SOFT_EVIDENCE` equals the
   `# SOFT` markers in `verdict_engine.py`, both ways.
3. The case detail serves `ai_fact_bands` and `qc_floor_facts` from the same verdict as `verdict`.
4. I-10 (owner D1 = A): a QC accept of a Recommend stops on a Rule-not-met fact even when its status
   is not 'gap'; a recorded reason passes it; 'gap' still stops; a decline is unaffected; a case with
   no AI verdict behaves as before.
All data is made up; only fact names, statuses and codes.
"""
import re
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import fact_bands as fb
from apps.scholarship.award import CONFIDENT_DISQUALIFIERS
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_student,
)

VIEW_ENGINE = 'apps.scholarship.views_admin.verdict.build_verdict'
DETAIL_ENGINE = 'apps.scholarship.verdict_engine.build_verdict'


def fact(name, status, evidence=(), unresolved=()):
    return {'fact': name, 'status': status,
            'evidence': [{'code': c, 'params': {}} for c in evidence],
            'unresolved': [{'code': c, 'params': {}} for c in unresolved]}


# (case, fact dict, expected band). The first block is the jest suite's own cases, line for line.
PARITY = [
    # officerCockpit.test.ts - factTileTone
    ('verified is Certain', fact('identity', 'verified'), 'certain'),
    ('review backed by a verified value is Probable', fact('identity', 'review', ['nric_match']), 'probable'),
    ('review with no verified value is Unsure', fact('income', 'review'), 'unsure'),
    ('declared-only review is Unsure', fact('pathway', 'review', ['pathway_declared']), 'unsure'),
    ('soft-signal-only review is Unsure', fact('income', 'review', ['utility_percapita_b40']), 'unsure'),
    ('recommend is Unsure', fact('income', 'recommend'), 'unsure'),
    ('gap is Cant verify', fact('identity', 'gap'), 'unverifiable'),
    # officerCockpit.test.ts - red tile reason
    ('review + offer_not_official is Rule not met',
     fact('pathway', 'review', ['nric_match'], ['offer_not_official']), 'ruleNotMet'),
    ('review, no evidence + offer_not_official is Rule not met',
     fact('pathway', 'review', [], ['offer_not_official']), 'ruleNotMet'),
    ('a disqualifier listed second still wins',
     fact('pathway', 'review', ['nric_match'], ['pathway_declared', 'pathway_start_year_outside']), 'ruleNotMet'),
    ('gap + pathway_funded_or_abroad is Rule not met',
     fact('pathway', 'gap', [], ['pathway_funded_or_abroad']), 'ruleNotMet'),
    ('review + higher_results_unreadable stays Cant verify',
     fact('pathway', 'review', [], ['higher_results_unreadable']), 'unverifiable'),
    # verdictTileHigherResults.test.ts
    ('#548 only the not-checked note is not proof',
     fact('academic', 'review', ['higher_results_not_checked']), 'unsure'),
    ('#548 not-checked + unreadable is red',
     fact('academic', 'review', ['higher_results_not_checked'], ['higher_results_unreadable']), 'unverifiable'),
    ('unreadable beats evidence that would be Probable',
     fact('academic', 'review', ['name_ok', 'higher_results_not_checked'], ['higher_results_unreadable']),
     'unverifiable'),
    ('#170 kind differs caps review at Unsure',
     fact('academic', 'review', ['name_ok', 'higher_results_not_checked'], ['higher_results_kind_differs']),
     'unsure'),
    ('#170 an SPM slip caps review at Unsure',
     fact('academic', 'review', ['name_ok'], ['higher_results_is_spm']), 'unsure'),
    ('#745 real proof + not-checked, nothing unresolved, is Probable',
     fact('academic', 'review', ['name_ok', 'kind_ok', 'cgpa_ok', 'higher_results_not_checked']), 'probable'),
    ('a verified academic tile is Certain', fact('academic', 'verified', ['name_ok']), 'certain'),
    ('verified + unreadable is red', fact('academic', 'verified', ['name_ok'], ['higher_results_unreadable']),
     'unverifiable'),
    ('verified + kind differs is Unsure',
     fact('academic', 'verified', ['name_ok'], ['higher_results_kind_differs']), 'unsure'),
    ('academic gap is Cant verify', fact('academic', 'gap'), 'unverifiable'),
    # Added in F2: every soft code alone, the other soft codes the old jest suite never named
    ('utility_percapita_high alone is Unsure', fact('income', 'review', ['utility_percapita_high']), 'unsure'),
    ('utility_hardship alone is Unsure', fact('income', 'review', ['utility_hardship']), 'unsure'),
    ('unemployment_epf_corroborated alone is Unsure',
     fact('income', 'review', ['unemployment_epf_corroborated']), 'unsure'),
    ('household_size_confirm alone is Unsure', fact('income', 'review', ['household_size_confirm']), 'unsure'),
    ('soft + one real value is Probable',
     fact('income', 'review', ['utility_hardship', 'str_verified']), 'probable'),
    # Added in F2: the overrides at every status
    ('gap + unreadable is Cant verify', fact('academic', 'gap', [], ['higher_results_unreadable']),
     'unverifiable'),
    ('recommend + unreadable is red', fact('academic', 'recommend', [], ['higher_results_unreadable']),
     'unverifiable'),
    ('recommend + kind differs is Unsure', fact('academic', 'recommend', [], ['higher_results_kind_differs']),
     'unsure'),
    ('verified + an SPM slip is Unsure', fact('academic', 'verified', ['name_ok'], ['higher_results_is_spm']),
     'unsure'),
    ('a disqualifier beats unreadable',
     fact('academic', 'review', [], ['higher_results_unreadable', 'offer_not_official']), 'ruleNotMet'),
    ('a disqualifier beats kind differs',
     fact('academic', 'verified', [], ['higher_results_kind_differs', 'income_above_b40_line']), 'ruleNotMet'),
    ('a code in EVIDENCE is not a disqualifier', fact('pathway', 'verified', ['offer_not_official']), 'certain'),
    ('an unknown status reads as Cant verify', fact('identity', 'pending'), 'unverifiable'),
    ('a missing status reads as Cant verify', {'fact': 'identity'}, 'unverifiable'),
    ('an evidence item with no code counts as real (as the web did)',
     {'fact': 'identity', 'status': 'review', 'evidence': [{}], 'unresolved': []}, 'probable'),
]

# Every confident disqualifier at every status reads Rule not met.
for _code in CONFIDENT_DISQUALIFIERS:
    for _status in ('verified', 'review', 'recommend', 'gap'):
        PARITY.append((f'{_code} at {_status} is Rule not met',
                       fact('pathway', _status, ['nric_match'], [_code]), 'ruleNotMet'))


class TestParity(SimpleTestCase):
    def test_every_case(self):
        for name, f, want in PARITY:
            with self.subTest(name):
                self.assertEqual(fb.fact_band(f), want)

    def test_the_five_disqualifiers_are_the_award_list(self):
        self.assertEqual(sorted(CONFIDENT_DISQUALIFIERS), sorted([
            'offer_not_official', 'income_above_b40_line', 'pathway_funded_or_abroad',
            'pathway_start_year_outside', 'pathway_offer_private']))

    def test_every_band_is_a_known_key(self):
        self.assertEqual({want for _, _, want in PARITY}, set(fb.BANDS))

    def test_fact_bands_maps_a_verdict(self):
        verdict = [fact('identity', 'verified'), fact('academic', 'review', ['name_ok']),
                   fact('pathway', 'review', [], ['pathway_offer_private']), fact('income', 'recommend')]
        self.assertEqual(fb.fact_bands(verdict), {
            'identity': 'certain', 'academic': 'probable', 'pathway': 'ruleNotMet', 'income': 'unsure'})
        self.assertEqual(fb.fact_bands(None), {})
        self.assertEqual(fb.fact_bands([]), {})

    def test_floor_facts_is_gap_or_rule_not_met(self):
        verdict = [fact('identity', 'gap'), fact('academic', 'review', [], ['higher_results_unreadable']),
                   fact('pathway', 'review', ['offer_programme'], ['pathway_start_year_outside']),
                   fact('income', 'verified')]
        # academic is red (Cant verify) but NOT a floor fact: only gap and Rule not met stop QC.
        self.assertEqual(fb.floor_facts(verdict), ['identity', 'pathway'])
        self.assertEqual(fb.floor_facts([]), [])

    def test_application_fact_bands_runs_the_engine(self):
        with mock.patch(DETAIL_ENGINE, return_value=[fact('identity', 'verified')]) as engine:
            self.assertEqual(fb.application_fact_bands(object()), {'identity': 'certain'})
        engine.assert_called_once()


class TestSoftEvidenceDrift(SimpleTestCase):
    """`SOFT_EVIDENCE` mirrors the `# SOFT` markers in the engine, both ways ("blue needs a green")."""

    def _engine_soft(self):
        src = (Path(__file__).resolve().parents[1] / 'verdict_engine.py').read_text(encoding='utf-8')
        codes = []
        for line in src.splitlines():
            if re.search(r'#\s*SOFT\b', line):
                m = re.search(r"_item\(\s*'([a-z0-9_]+)'", line)
                if m:
                    codes.append(m.group(1))
        return codes

    def test_the_parse_found_the_markers(self):
        self.assertGreaterEqual(len(self._engine_soft()), 6)

    def test_the_set_equals_the_markers(self):
        self.assertEqual(set(self._engine_soft()), set(fb.SOFT_EVIDENCE))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestDetailServesTheBands(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='fb', name='B40', year=2026)
        cls.qc = make_admin('qc', uid='fb-qc', owning_org=cls.cohort.owning_organisation,
                            name='QC', email='fbqc@example.com')

    def test_the_detail_serves_bands_and_floor_from_the_same_verdict(self):
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort)
        verdict = [fact('identity', 'verified'), fact('academic', 'review', ['name_ok']),
                   fact('pathway', 'review', ['offer_programme'], ['pathway_offer_private']),
                   fact('income', 'gap')]
        with mock.patch(DETAIL_ENGINE, return_value=verdict):
            body = authed_client(self.qc).get(f'/api/v1/admin/scholarship/applications/{app.pk}/').json()
        self.assertEqual(body['ai_fact_bands'], {
            'identity': 'certain', 'academic': 'probable', 'pathway': 'ruleNotMet', 'income': 'unverifiable'})
        self.assertEqual(body['qc_floor_facts'], ['pathway', 'income'])
        self.assertEqual(body['verdict'], verdict)

    def test_a_real_case_with_no_documents_reads_red_everywhere(self):
        app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort)
        body = authed_client(self.qc).get(f'/api/v1/admin/scholarship/applications/{app.pk}/').json()
        self.assertEqual(body['ai_fact_bands'], fb.fact_bands(body['verdict']))
        self.assertEqual(body['qc_floor_facts'], fb.floor_facts(body['verdict']))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestQcFloorRuleNotMet(TestCase):
    """I-10 (owner D1 = A, 2026-11-21): Rule not met stops a QC accept of a Recommend whatever the status."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(code='rnm', name='B40', year=2026)
        org = cls.cohort.owning_organisation
        cls.qc = make_admin('qc', uid='rnm-qc', owning_org=org, name='QC', email='rnmqc@example.com')
        cls.superadmin = make_admin('super', uid='rnm-super', super_admin=True,
                                    name='Super', email='rnmsuper@example.com')
        cls.reviewer = make_admin('reviewer', uid='rnm-rev', owning_org=org,
                                  name='Reviewer', email='rnmrev@example.com')

    def setUp(self):
        p = make_student(supabase_user_id='srnm', nric='030101-14-0077', name='Kavi')
        self.app = make_application('awaiting_qc', outcome='recommend', cohort=self.cohort, student=p,
                                    reviewer=self.reviewer)

    def _qc(self, body, who=None):
        return authed_client(who or self.qc).post(
            f'/api/v1/admin/scholarship/applications/{self.app.pk}/qc-decision/', body, format='json')

    def _clean_but(self, *extra):
        facts = {f['fact']: f for f in (fact('identity', 'verified'), fact('academic', 'verified'),
                                         fact('pathway', 'verified'), fact('income', 'verified'))}
        for f in extra:
            facts[f['fact']] = f
        return list(facts.values())

    def test_rule_not_met_on_a_review_fact_blocks(self):
        verdict = self._clean_but(fact('pathway', 'review', ['offer_programme'], ['pathway_start_year_outside']))
        with mock.patch(VIEW_ENGINE, return_value=verdict):
            r = self._qc({'decision': 'accept'})
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.json()['code'], 'verdict_gap_floor')
        self.assertEqual(r.json()['facts'], ['pathway'])
        self.assertEqual(ScholarshipApplication.objects.get(pk=self.app.pk).status, 'interviewed')

    def test_every_disqualifier_on_a_verified_fact_blocks(self):
        for code in CONFIDENT_DISQUALIFIERS:
            with self.subTest(code), mock.patch(VIEW_ENGINE, return_value=self._clean_but(
                    fact('income', 'verified', ['str_verified'], [code]))):
                r = self._qc({'decision': 'accept'})
                self.assertEqual(r.status_code, 400, r.content)
                self.assertEqual(r.json()['facts'], ['income'])

    def test_a_recorded_reason_passes_and_is_recorded(self):
        verdict = self._clean_but(fact('pathway', 'recommend', [], ['pathway_offer_private']))
        with mock.patch(VIEW_ENGINE, return_value=verdict), self.assertLogs(
                'apps.scholarship.views_admin', level='INFO') as logs:
            r = self._qc({'decision': 'accept', 'override_reason': 'Public wing confirmed by phone.'})
        self.assertEqual(r.status_code, 200, r.content)
        app = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertEqual(app.status, 'recommended')
        self.assertEqual(app.qc_override_reason, 'Public wing confirmed by phone.')
        self.assertEqual(app.qc_override_by, 'rnmqc@example.com')
        self.assertIsNotNone(app.qc_override_at)
        self.assertTrue(any('qc_gap_override' in m and 'facts=pathway' in m for m in logs.output))

    def test_a_blank_reason_is_refused(self):
        verdict = self._clean_but(fact('pathway', 'review', ['x'], ['offer_not_official']))
        with mock.patch(VIEW_ENGINE, return_value=verdict):
            r = self._qc({'decision': 'accept', 'override_reason': '   '}, who=self.superadmin)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'verdict_gap_floor')

    def test_gap_still_blocks_alongside(self):
        verdict = self._clean_but(fact('identity', 'gap'),
                                  fact('pathway', 'review', ['x'], ['pathway_funded_or_abroad']))
        with mock.patch(VIEW_ENGINE, return_value=verdict):
            r = self._qc({'decision': 'accept'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['facts'], ['identity', 'pathway'])

    def test_red_but_not_rule_not_met_does_not_block(self):
        # Higher results unreadable on a review fact is red (Cant verify) but not a floor fact.
        verdict = self._clean_but(fact('academic', 'review', ['name_ok'], ['higher_results_unreadable']))
        with mock.patch(VIEW_ENGINE, return_value=verdict):
            r = self._qc({'decision': 'accept'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ScholarshipApplication.objects.get(pk=self.app.pk).qc_override_reason, '')

    def test_a_case_with_no_ai_verdict_behaves_as_before(self):
        with mock.patch(VIEW_ENGINE, return_value=[]):
            r = self._qc({'decision': 'accept'})
        self.assertEqual(r.status_code, 200, r.content)
        app = ScholarshipApplication.objects.get(pk=self.app.pk)
        self.assertEqual(app.status, 'recommended')
        self.assertEqual(app.qc_override_reason, '')

    def test_a_decline_is_unaffected(self):
        p = make_student(supabase_user_id='srnm-d', nric='030101-14-0078', name='Nila')
        self.app = make_application('awaiting_qc', outcome='decline', cohort=self.cohort, student=p,
                                    reviewer=self.reviewer)
        verdict = self._clean_but(fact('pathway', 'review', ['x'], ['pathway_start_year_outside']))
        with mock.patch(VIEW_ENGINE, return_value=verdict):
            r = self._qc({'decision': 'accept'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ScholarshipApplication.objects.get(pk=self.app.pk).status, 'rejected')
