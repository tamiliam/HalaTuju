"""
Tests for the ranking engine and ranking API endpoint.

Covers:
- calculate_fit_score: score calculation with various signal/tag combos
- Category cap enforcement (scores clamped to +-CATEGORY_CAP)
- Global cap enforcement (total adjustment clamped to +-GLOBAL_CAP)
- Institution modifier scoring (urban, cultural_safety_net)
- Merit penalty application (High/Fair/Low)
- sort_courses: tie-breaking hierarchy (score > credential > institution > merit > name)
- Sort stability: equal items preserve relative order
- get_ranked_results: single ranked list, end-to-end ranking
- get_credential_priority: credential level ordering
- RankingView API endpoint: validation, success, empty input
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.ranking_engine import (
    BASE_SCORE,
    CATEGORY_CAP,
    FIELD_INTEREST_CAP,
    GLOBAL_CAP,
    INSTITUTION_CAP,
    MERIT_PENALTY,
    WORK_PREFERENCE_CAP,
    calculate_fit_score,
    calculate_matric_stpm_fit_score,
    get_credential_priority,
    get_ranked_results,
    sort_courses,
)


# --- Helpers ---

def make_signals(**kwargs):
    """Build a student_signals dict with specified signal values."""
    base = {
        'field_interest': {},
        'work_preference_signals': {},
        'learning_tolerance_signals': {},
        'environment_signals': {},
        'value_tradeoff_signals': {},
        'energy_sensitivity_signals': {},
    }
    for key, val in kwargs.items():
        # key format: "category.signal_name"
        parts = key.split('.')
        if len(parts) == 2:
            base[parts[0]][parts[1]] = val
    return base


EMPTY_SIGNALS = make_signals()

HANDS_ON_TAGS = {
    'work_modality': 'hands_on',
    'people_interaction': 'low_people',
    'cognitive_type': 'procedural',
    'learning_style': ['project_based'],
    'load': 'physically_demanding',
    'outcome': 'employment_first',
    'environment': 'workshop',
    'credential_status': 'unregulated',
    'creative_output': 'none',
    'service_orientation': 'neutral',
    'interaction_type': 'mixed',
    'career_structure': 'stable',
}


class TestCalculateFitScore(TestCase):
    """Unit tests for calculate_fit_score."""

    def test_base_score_with_empty_signals(self):
        """No signals → base score (minus hands_on penalty for hands_on tag)."""
        # With empty signals and hands_on tag, sig_hands_on == 0 triggers -3
        score, reasons = calculate_fit_score(
            {'student_signals': EMPTY_SIGNALS},
            'C001', 'I001',
            {'C001': HANDS_ON_TAGS},
            {},
        )
        # -3 from hands_on penalty when sig is 0 and tag is hands_on
        self.assertEqual(score, BASE_SCORE - 3)

    def test_base_score_with_no_tags(self):
        """No tags at all → exactly base score."""
        score, reasons = calculate_fit_score(
            {'student_signals': EMPTY_SIGNALS},
            'C001', 'I001',
            {},  # no tags
            {},
        )
        self.assertEqual(score, BASE_SCORE)
        self.assertEqual(reasons, [])

    def test_hands_on_match_boosts_score(self):
        """Hands-on signal + hands_on tag → +5 raw, capped at WORK_PREFERENCE_CAP (4)."""
        signals = make_signals(**{
            'work_preference_signals.hands_on': 2,
        })
        score, reasons = calculate_fit_score(
            {'student_signals': signals},
            'C001', 'I001',
            {'C001': {'work_modality': 'hands_on'}},
            {},
        )
        self.assertEqual(score, BASE_SCORE + WORK_PREFERENCE_CAP)
        self.assertIn("hands-on work preference", reasons[0])

    def test_environment_workshop_match(self):
        """Workshop signal + workshop tag → +4 environment."""
        signals = make_signals(**{
            'environment_signals.workshop_environment': 1,
        })
        score, reasons = calculate_fit_score(
            {'student_signals': signals},
            'C001', 'I001',
            {'C001': {'environment': 'workshop'}},
            {},
        )
        self.assertEqual(score, BASE_SCORE + 4)

    def test_energy_penalty_physically_demanding(self):
        """Fatigue signal + physically_demanding load → -6 energy."""
        signals = make_signals(**{
            'energy_sensitivity_signals.physical_fatigue_sensitive': 1,
        })
        score, reasons = calculate_fit_score(
            {'student_signals': signals},
            'C001', 'I001',
            {'C001': {'load': 'physically_demanding'}},
            {},
        )
        self.assertEqual(score, BASE_SCORE - 6)
        self.assertTrue(any("physically demanding" in r for r in reasons))

    def test_category_cap_enforced(self):
        """Stacking many signals in one category should be capped at its cap."""
        # Stack work_preference: hands_on(+5) + people_helping(+4) + creative project_based(+4)
        # = 13, but should be capped at WORK_PREFERENCE_CAP (4)
        signals = make_signals(**{
            'work_preference_signals.hands_on': 2,
            'work_preference_signals.people_helping': 2,
            'work_preference_signals.creative': 2,
        })
        tags = {
            'work_modality': 'hands_on',
            'people_interaction': 'high_people',
            'learning_style': ['project_based'],
            'cognitive_type': 'abstract',
        }
        score, reasons = calculate_fit_score(
            {'student_signals': signals},
            'C001', 'I001',
            {'C001': tags},
            {},
        )
        # Work preference cap = 4, so max boost from work_preference is 4
        self.assertEqual(score, BASE_SCORE + WORK_PREFERENCE_CAP)

    def test_negative_category_cap(self):
        """Negative energy scores should be capped at -CATEGORY_CAP."""
        signals = make_signals(**{
            'energy_sensitivity_signals.low_people_tolerance': 1,
            'energy_sensitivity_signals.physical_fatigue_sensitive': 1,
            'energy_sensitivity_signals.mental_fatigue_sensitive': 1,
        })
        tags = {
            'people_interaction': 'high_people',
            'load': 'physically_demanding',
            'service_orientation': 'service',
            'interaction_type': 'transactional',
        }
        score, reasons = calculate_fit_score(
            {'student_signals': signals},
            'C001', 'I001',
            {'C001': tags},
            {},
        )
        # -6 (low_people) -6 (fatigue) -6 (mental) -2 (transactional) -2 (service) = -22
        # Capped at -CATEGORY_CAP = -6
        self.assertEqual(score, BASE_SCORE - CATEGORY_CAP)


class TestInstitutionModifiers(TestCase):
    """Tests for institution modifier scoring."""

    def test_urban_income_boost(self):
        """Urban institution + income_risk_tolerant → +2 inst boost."""
        signals = make_signals(**{
            'value_tradeoff_signals.income_risk_tolerant': 1,
        })
        # Provide explicit tags to avoid default career_structure='volatile' side effect
        tags = {'C001': {'career_structure': 'stable'}}
        score, _ = calculate_fit_score(
            {'student_signals': signals},
            'C001', 'I001',
            tags,
            {'I001': {'urban': True}},
        )
        self.assertEqual(score, BASE_SCORE + 2)

    def test_cultural_safety_net_high(self):
        """High cultural_safety_net + proximity → +4."""
        signals = make_signals(**{
            'value_tradeoff_signals.proximity_priority': 1,
        })
        score, reasons = calculate_fit_score(
            {'student_signals': signals},
            'C001', 'I001',
            {},
            {'I001': {'cultural_safety_net': 'high'}},
        )
        self.assertEqual(score, BASE_SCORE + 4)
        self.assertIn("high community support", reasons[0])

    def test_cultural_safety_net_low_penalty(self):
        """Low cultural_safety_net + proximity → -2."""
        signals = make_signals(**{
            'value_tradeoff_signals.proximity_priority': 1,
        })
        score, reasons = calculate_fit_score(
            {'student_signals': signals},
            'C001', 'I001',
            {},
            {'I001': {'cultural_safety_net': 'low'}},
        )
        self.assertEqual(score, BASE_SCORE - 2)

    def test_institution_cap_enforced(self):
        """Stacked institution modifiers should be capped at INSTITUTION_CAP."""
        signals = make_signals(**{
            'value_tradeoff_signals.income_risk_tolerant': 1,
            'value_tradeoff_signals.proximity_priority': 1,
            'value_tradeoff_signals.fast_employment_priority': 1,
        })
        # Use career_structure that doesn't match any scoring rule
        tags = {'C001': {'career_structure': 'neutral'}}
        score, _ = calculate_fit_score(
            {'student_signals': signals},
            'C001', 'I001',
            tags,
            {'I001': {'urban': True, 'cultural_safety_net': 'high'}},
        )
        # urban(+2) + safety_high(+4) + fast_emp_proximity(+2) = 8
        # Capped at INSTITUTION_CAP = 5
        self.assertEqual(score, BASE_SCORE + INSTITUTION_CAP)


class TestMeritPenalty(TestCase):
    """Tests for merit-based ranking penalty in get_ranked_results."""

    def test_high_merit_no_penalty(self):
        """Student above cutoff → no penalty."""
        courses = [{
            'course_id': 'C001',
            'institution_id': 'I001',
            'course_name': 'Diploma Test',
            'merit_cutoff': 40.0,
            'student_merit': 50.0,
        }]
        result = get_ranked_results(
            courses,
            {'student_signals': EMPTY_SIGNALS},
            {}, {}, {},
        )
        item = result['ranked'][0]
        # No tags → base score, no merit penalty
        self.assertEqual(item['fit_score'], BASE_SCORE)

    def test_fair_merit_minus_5(self):
        """Student 3 points below cutoff → Fair → -5 penalty."""
        courses = [{
            'course_id': 'C001',
            'institution_id': 'I001',
            'course_name': 'Diploma Test',
            'merit_cutoff': 50.0,
            'student_merit': 47.0,
        }]
        result = get_ranked_results(
            courses,
            {'student_signals': EMPTY_SIGNALS},
            {}, {}, {},
        )
        self.assertEqual(result['ranked'][0]['fit_score'], BASE_SCORE + MERIT_PENALTY['Fair'])

    def test_low_merit_minus_15(self):
        """Student 10 points below cutoff → Low → -15 penalty."""
        courses = [{
            'course_id': 'C001',
            'institution_id': 'I001',
            'course_name': 'Diploma Test',
            'merit_cutoff': 50.0,
            'student_merit': 30.0,
        }]
        result = get_ranked_results(
            courses,
            {'student_signals': EMPTY_SIGNALS},
            {}, {}, {},
        )
        self.assertEqual(result['ranked'][0]['fit_score'], BASE_SCORE + MERIT_PENALTY['Low'])


class TestSortCourses(TestCase):
    """Tests for sort_courses tie-breaking hierarchy."""

    def test_score_descending(self):
        """Higher score should come first."""
        courses = [
            {'fit_score': 90, 'course_name': 'B', 'institution_id': ''},
            {'fit_score': 110, 'course_name': 'A', 'institution_id': ''},
        ]
        result = sort_courses(courses, {})
        self.assertEqual(result[0]['fit_score'], 110)
        self.assertEqual(result[1]['fit_score'], 90)

    def test_credential_tiebreak(self):
        """Same score → Diploma beats Sijil."""
        courses = [
            {'fit_score': 100, 'course_name': 'Sijil Welding', 'institution_id': ''},
            {'fit_score': 100, 'course_name': 'Diploma Kejuruteraan', 'institution_id': ''},
        ]
        result = sort_courses(courses, {})
        self.assertEqual(result[0]['course_name'], 'Diploma Kejuruteraan')

    def test_institution_tiebreak(self):
        """Same score, same credential → Premier beats Konvensional."""
        courses = [
            {'fit_score': 100, 'course_name': 'Diploma A', 'institution_id': 'I1'},
            {'fit_score': 100, 'course_name': 'Diploma B', 'institution_id': 'I2'},
        ]
        subcats = {'I1': 'Konvensional', 'I2': 'Premier'}
        result = sort_courses(courses, subcats)
        self.assertEqual(result[0]['institution_id'], 'I2')  # Premier = 10

    def test_merit_delta_tiebreak(self):
        """Same score, credential, institution → smaller gap to cutoff wins."""
        courses = [
            {'fit_score': 100, 'course_name': 'Diploma A',
             'institution_id': '', 'merit_cutoff': 80, 'student_merit': 54,
             'merit_label': 'Low'},  # delta = -26
            {'fit_score': 100, 'course_name': 'Diploma B',
             'institution_id': '', 'merit_cutoff': 60, 'student_merit': 54,
             'merit_label': 'Low'},  # delta = -6
        ]
        result = sort_courses(courses, {})
        self.assertEqual(result[0]['course_name'], 'Diploma B')  # closer to cutoff

    def test_name_alphabetical_tiebreak(self):
        """All else equal → alphabetical by name."""
        courses = [
            {'fit_score': 100, 'course_name': 'Diploma Zebra', 'institution_id': ''},
            {'fit_score': 100, 'course_name': 'Diploma Alpha', 'institution_id': ''},
        ]
        result = sort_courses(courses, {})
        self.assertEqual(result[0]['course_name'], 'Diploma Alpha')

    def test_sort_stability(self):
        """Identical items should preserve insertion order."""
        courses = [
            {'fit_score': 100, 'course_name': 'Diploma Same', 'institution_id': '', 'idx': 1},
            {'fit_score': 100, 'course_name': 'Diploma Same', 'institution_id': '', 'idx': 2},
        ]
        result = sort_courses(courses, {})
        self.assertEqual(result[0]['idx'], 1)
        self.assertEqual(result[1]['idx'], 2)


class TestGetCredentialPriority(TestCase):
    """Tests for credential priority ordering."""

    def test_asasi_highest(self):
        self.assertEqual(get_credential_priority("Asasi Sains"), 5)

    def test_foundation_highest(self):
        self.assertEqual(get_credential_priority("Something Foundation"), 5)

    def test_pismp_below_diploma_above_sijil(self):
        """PISMP sorts below Poly Diploma but above KKOM Sijil."""
        pismp = get_credential_priority("Matematik Pendidikan Rendah", source_type='pismp')
        diploma = get_credential_priority("Diploma Kejuruteraan")
        sijil = get_credential_priority("Sijil Kemahiran")
        self.assertLess(pismp, diploma)
        self.assertGreater(pismp, sijil)

    def test_pismp_below_asasi(self):
        self.assertGreater(
            get_credential_priority("Asasi Sains"),
            get_credential_priority("Matematik Pendidikan Rendah", source_type='pismp'),
        )

    def test_diploma(self):
        self.assertEqual(get_credential_priority("Diploma Kejuruteraan"), 3)

    def test_sijil_lanjutan(self):
        self.assertEqual(get_credential_priority("Sijil Lanjutan Kimpalan"), 2)

    def test_sijil(self):
        self.assertEqual(get_credential_priority("Sijil Kimpalan"), 1)

    def test_unknown(self):
        self.assertEqual(get_credential_priority("Something Else"), 0)


class TestGetRankedResults(TestCase):
    """Tests for the main get_ranked_results entry point."""

    def test_all_courses_in_ranked(self):
        """All courses returned in single ranked list."""
        courses = [
            {'course_id': f'C{i}', 'institution_id': 'I001',
             'course_name': f'Diploma {i}'}
            for i in range(8)
        ]
        result = get_ranked_results(
            courses,
            {'student_signals': EMPTY_SIGNALS},
            {}, {}, {},
        )
        self.assertEqual(len(result['ranked']), 8)

    def test_fit_reasons_populated(self):
        """Matching signals should produce fit_reasons."""
        courses = [{
            'course_id': 'C001',
            'institution_id': 'I001',
            'course_name': 'Diploma Test',
        }]
        signals = make_signals(**{
            'work_preference_signals.hands_on': 2,
        })
        tags = {'C001': {'work_modality': 'hands_on'}}
        result = get_ranked_results(
            courses,
            {'student_signals': signals},
            tags, {}, {},
        )
        item = result['ranked'][0]
        self.assertGreater(len(item['fit_reasons']), 0)
        self.assertIn("hands-on", item['fit_reasons'][0])


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestRankingEndpoint(TestCase):
    """POST /api/v1/ranking/ endpoint tests."""

    def setUp(self):
        self.client = APIClient()

    def test_ranking_success(self):
        """Valid request returns 200 with ranked list."""
        response = self.client.post(
            '/api/v1/ranking/',
            data={
                'eligible_courses': [
                    {'course_id': 'C001', 'course_name': 'Diploma Test',
                     'institution_id': 'I001'},
                ],
                'student_signals': {
                    'work_preference_signals': {'hands_on': 2},
                    'environment_signals': {},
                    'learning_tolerance_signals': {},
                    'value_tradeoff_signals': {},
                    'energy_sensitivity_signals': {},
                },
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('ranked', response.data)
        self.assertIn('total_ranked', response.data)
        self.assertEqual(response.data['total_ranked'], 1)

    def test_ranking_missing_eligible_courses(self):
        """Missing eligible_courses → 400."""
        response = self.client.post(
            '/api/v1/ranking/',
            data={'student_signals': {}},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_ranking_missing_student_signals(self):
        """Missing student_signals → 400."""
        response = self.client.post(
            '/api/v1/ranking/',
            data={'eligible_courses': [{'course_id': 'C001'}]},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_ranking_empty_courses_400(self):
        """Empty eligible_courses list → 400."""
        response = self.client.post(
            '/api/v1/ranking/',
            data={
                'eligible_courses': [],
                'student_signals': {},
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_ranking_course_missing_id_400(self):
        """Course without course_id → 400."""
        response = self.client.post(
            '/api/v1/ranking/',
            data={
                'eligible_courses': [{'course_name': 'No ID'}],
                'student_signals': {},
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)


class TestFieldInterestMatching(TestCase):
    """Tests for field interest → field_key matching."""

    def test_primary_field_match_gives_boost(self):
        """Student with field_mechanical=3 + course with mekanikal field_key → score > BASE."""
        signals = make_signals(**{'field_interest.field_mechanical': 3})
        score, reasons = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {}, {},
            field_key='mekanikal')
        self.assertGreater(score, BASE_SCORE)

    def test_no_field_match_no_penalty(self):
        """Student interested in digital, course is mekanikal → no field penalty, score = BASE."""
        signals = make_signals(**{'field_interest.field_digital': 3})
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {}, {},
            field_key='mekanikal')
        self.assertEqual(score, BASE_SCORE)

    def test_field_interest_capped_at_8(self):
        """Even with double match, field interest capped at FIELD_INTEREST_CAP (8)."""
        signals = make_signals(**{
            'field_interest.field_health': 3,
            'field_interest.field_agriculture': 3,
        })
        # Both field_health and field_agriculture have 'pertanian' in their key lists
        # — but field_health maps to perubatan/farmasi/sains-hayat, not pertanian.
        # Only field_agriculture matches pertanian → single match → +8 → capped at 8
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {}, {},
            field_key='pertanian')
        self.assertLessEqual(score, BASE_SCORE + FIELD_INTEREST_CAP)

    def test_heavy_industry_sub_signal_matches(self):
        """field_electrical signal matches elektrik field_key."""
        signals = make_signals(**{'field_interest.field_electrical': 3})
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {}, {},
            field_key='elektrik')
        self.assertGreater(score, BASE_SCORE)

    def test_no_field_key_no_field_score(self):
        """Course with no field_key → field interest contributes 0."""
        signals = make_signals(**{'field_interest.field_mechanical': 3})
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {}, {},
            field_key='')
        self.assertEqual(score, BASE_SCORE)

    def test_double_match_gives_bonus(self):
        """Two signals matching the same field_key → primary +8 and secondary +4, capped at 8."""
        signals = make_signals(**{
            'field_interest.field_mechanical': 3,
            'field_interest.field_heavy_industry': 2,
        })
        # Both field_mechanical and field_heavy_industry include 'mekanikal'
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {}, {},
            field_key='mekanikal')
        # +8 primary + 4 secondary = 12, capped at FIELD_INTEREST_CAP (8)
        self.assertEqual(score, BASE_SCORE + FIELD_INTEREST_CAP)


class TestHighStaminaSignal(TestCase):
    def test_high_stamina_boosts_physically_demanding(self):
        signals = make_signals(**{'energy_sensitivity_signals.high_stamina': 1})
        tags = {'load': 'physically_demanding'}
        score, reasons = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertGreater(score, BASE_SCORE)
        self.assertTrue(any('stamina' in r for r in reasons))

    def test_high_stamina_boosts_mentally_demanding(self):
        signals = make_signals(**{'energy_sensitivity_signals.high_stamina': 1})
        tags = {'load': 'mentally_demanding'}
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertGreater(score, BASE_SCORE)

    def test_high_stamina_no_effect_normal_load(self):
        signals = make_signals(**{'energy_sensitivity_signals.high_stamina': 1})
        tags = {'load': 'normal'}
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertEqual(score, BASE_SCORE)


class TestRoteTolerantSignal(TestCase):
    def test_rote_tolerant_boosts_assessment_heavy(self):
        signals = make_signals(**{'learning_tolerance_signals.rote_tolerant': 1})
        tags = {'learning_style': ['assessment_heavy']}
        score, reasons = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertGreater(score, BASE_SCORE)
        self.assertTrue(any('assessment' in r for r in reasons))

    def test_rote_tolerant_no_effect_without_tag(self):
        signals = make_signals(**{'learning_tolerance_signals.rote_tolerant': 1})
        tags = {'learning_style': ['project_based']}
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertEqual(score, BASE_SCORE)


class TestQualityPrioritySignal(TestCase):
    def test_quality_priority_boosts_pathway_friendly(self):
        signals = make_signals(**{'value_tradeoff_signals.quality_priority': 1})
        tags = {'outcome': 'pathway_friendly'}
        score, reasons = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertGreater(score, BASE_SCORE)

    def test_quality_priority_boosts_regulated(self):
        signals = make_signals(**{'value_tradeoff_signals.quality_priority': 1})
        tags = {'outcome': 'regulated_profession'}
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertGreater(score, BASE_SCORE)

    def test_quality_priority_no_effect_employment_first(self):
        signals = make_signals(**{'value_tradeoff_signals.quality_priority': 1})
        tags = {'outcome': 'employment_first'}
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertEqual(score, BASE_SCORE)


class TestWorkPreferenceCap(TestCase):
    def test_work_preference_capped_at_4(self):
        """Raw work preference score can exceed 4 but is capped."""
        signals = make_signals(**{
            'work_preference_signals.hands_on': 2,
            'work_preference_signals.creative': 2,
        })
        # Tags that would match BOTH hands_on AND creative for maximum score
        tags = {
            'work_modality': 'hands_on',
            'learning_style': ['project_based'],
            'creative_output': 'expressive',
            'cognitive_type': 'abstract',
        }
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        # Work preference is capped at 4, so total from work alone ≤ 4
        # Other categories might contribute, but work cannot exceed 4
        self.assertLessEqual(score, BASE_SCORE + GLOBAL_CAP)


class TestPreUScoring(TestCase):
    """Tests for Matric/STPM unified pre-U scoring."""

    def test_matric_base_plus_prestige(self):
        """Matric gets base(100) + prestige(8) = 108."""
        item = {'pathway_type': 'matric', 'source_type': 'matric',
                'field': 'Foundation Studies', 'student_merit': 80,
                'track_id': 'sains'}
        score, _ = calculate_matric_stpm_fit_score(item, {})
        self.assertEqual(score, 108)  # 100 + 8 + 0(academic) + 0(field) + 0(signal)

    def test_stpm_base_plus_prestige(self):
        """STPM gets base(100) + prestige(5) = 105."""
        item = {'pathway_type': 'stpm', 'source_type': 'stpm',
                'field': 'Form 6', 'track_id': 'sains', 'mata_gred': 15}
        score, _ = calculate_matric_stpm_fit_score(item, {})
        self.assertEqual(score, 105)

    def test_matric_academic_bonus_high(self):
        """Matric merit >= 94 → +8 academic bonus."""
        item = {'pathway_type': 'matric', 'source_type': 'matric',
                'field': 'Foundation Studies', 'student_merit': 95,
                'track_id': 'sains'}
        score, _ = calculate_matric_stpm_fit_score(item, {})
        self.assertEqual(score, 116)  # 100 + 8 + 8

    def test_matric_academic_bonus_mid(self):
        """Matric merit >= 89 → +4 academic bonus."""
        item = {'pathway_type': 'matric', 'source_type': 'matric',
                'field': 'Foundation Studies', 'student_merit': 90,
                'track_id': 'sains'}
        score, _ = calculate_matric_stpm_fit_score(item, {})
        self.assertEqual(score, 112)  # 100 + 8 + 4

    def test_stpm_academic_bonus_high(self):
        """STPM mata gred <= 4 → +8 academic bonus."""
        item = {'pathway_type': 'stpm', 'source_type': 'stpm',
                'field': 'Form 6', 'track_id': 'sains', 'mata_gred': 3}
        score, _ = calculate_matric_stpm_fit_score(item, {})
        self.assertEqual(score, 113)  # 100 + 5 + 8

    def test_stpm_academic_bonus_mid(self):
        """STPM mata gred <= 10 → +4 academic bonus."""
        item = {'pathway_type': 'stpm', 'source_type': 'stpm',
                'field': 'Form 6', 'track_id': 'sains', 'mata_gred': 8}
        score, _ = calculate_matric_stpm_fit_score(item, {})
        self.assertEqual(score, 109)  # 100 + 5 + 4

    def test_matric_field_preference_engineering(self):
        """Matric Engineering + field_mechanical signal → +3."""
        item = {'pathway_type': 'matric', 'source_type': 'matric',
                'field': 'Foundation Studies', 'student_merit': 80,
                'track_id': 'kejuruteraan'}
        signals = {'field_interest': {'field_mechanical': 2}}
        score, _ = calculate_matric_stpm_fit_score(item, {'student_signals': signals})
        self.assertEqual(score, 111)  # 100 + 8 + 0 + 3

    def test_stpm_socsci_creative_boost(self):
        """STPM Social Science + creative signal → +3 field preference."""
        item = {'pathway_type': 'stpm', 'source_type': 'stpm',
                'field': 'Form 6', 'track_id': 'sains_sosial', 'mata_gred': 10}
        signals = {'work_preference_signals': {'creative': 2}}
        score, _ = calculate_matric_stpm_fit_score(item, {'student_signals': signals})
        # 100 + 5 + 4(acad) + 3(field) + 1(creative socsci signal adj) = 113
        self.assertEqual(score, 113)

    def test_signal_pathway_priority(self):
        """pathway_priority signal → +3 adjustment."""
        item = {'pathway_type': 'matric', 'source_type': 'matric',
                'field': 'Foundation Studies', 'student_merit': 80,
                'track_id': 'sains'}
        signals = {'value_tradeoff_signals': {'pathway_priority': 2}}
        score, _ = calculate_matric_stpm_fit_score(item, {'student_signals': signals})
        self.assertEqual(score, 111)  # 100 + 8 + 0 + 0 + 3

    def test_signal_cap(self):
        """Signal adjustment capped at ±6."""
        item = {'pathway_type': 'matric', 'source_type': 'matric',
                'field': 'Foundation Studies', 'student_merit': 80,
                'track_id': 'sains'}
        # Stack many positive signals to exceed cap
        signals = {
            'work_preference_signals': {'problem_solving': 2},  # +2
            'learning_tolerance_signals': {'concept_first': 2, 'rote_tolerant': 2},  # +2+1
            'value_tradeoff_signals': {'pathway_priority': 2, 'quality_priority': 2},  # +3+2
        }
        score, _ = calculate_matric_stpm_fit_score(item, {'student_signals': signals})
        # Raw: 2+2+1+3+2 = 10, capped at 6
        self.assertEqual(score, 114)  # 100 + 8 + 0 + 0 + 6

    def test_ranking_routes_matric(self):
        """get_ranked_results routes matric to pre-U scorer."""
        courses = [{'course_id': 'pathway-matric-sains', 'pathway_type': 'matric',
                     'source_type': 'matric', 'field': 'Foundation Studies',
                     'student_merit': 95, 'course_name': 'Matriculation — Science',
                     'track_id': 'sains', 'merit_cutoff': 94, 'merit_label': 'High'}]
        result = get_ranked_results(courses, {'student_signals': {}}, {}, {}, {})
        self.assertEqual(len(result['ranked']), 1)
        self.assertGreaterEqual(result['ranked'][0]['fit_score'], 108)

    def test_ranking_routes_stpm(self):
        """get_ranked_results routes stpm to pre-U scorer."""
        courses = [{'course_id': 'pathway-stpm-sains', 'pathway_type': 'stpm',
                     'source_type': 'stpm', 'field': 'Form 6',
                     'student_merit': 50, 'course_name': 'Form 6 (STPM) — Science',
                     'track_id': 'sains', 'mata_gred': 6, 'merit_cutoff': 38,
                     'merit_label': 'High'}]
        result = get_ranked_results(courses, {'student_signals': {}}, {}, {}, {})
        self.assertEqual(len(result['ranked']), 1)
        self.assertGreaterEqual(result['ranked'][0]['fit_score'], 105)
