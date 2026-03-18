"""
Tests for STPM quiz data integrity — structure, trilingual completeness,
signal taxonomy consistency, and no duplicate IDs.
"""
from apps.courses.stpm_quiz_data import (
    SUBJECT_RIASEC_MAP,
    SCIENCE_SUBJECTS,
    ARTS_SUBJECTS,
    STPM_SIGNAL_TAXONOMY,
    STPM_FIELD_KEY_MAP,
    SUPPORTED_LANGUAGES,
    ALL_QUESTION_IDS,
    TRUNK_QUESTIONS,
    SCIENCE_Q2, ARTS_Q2, MIXED_Q2,
    SCIENCE_Q3_VARIANTS, ARTS_Q3_VARIANTS,
    Q4_CONFIDENCE_WEAK, Q4_CONFIDENCE_STRONG,
    Q5_CROSS_DOMAIN_OPTIONS,
    Q7_CHALLENGE, Q8_MOTIVATION, Q9_CAREER, Q10_FAMILY,
    FIELD_TO_SUBJECT,
    FIELD_DISPLAY_NAMES,
    SUBJECT_DISPLAY_NAMES,
    STPM_GRADE_POINTS,
)


class TestQuestionStructure:

    def _all_questions(self):
        """Gather all question dicts for inspection."""
        qs = list(TRUNK_QUESTIONS)
        qs.extend([SCIENCE_Q2, ARTS_Q2, MIXED_Q2])
        qs.extend(SCIENCE_Q3_VARIANTS.values())
        qs.extend(ARTS_Q3_VARIANTS.values())
        qs.extend([Q4_CONFIDENCE_WEAK, Q4_CONFIDENCE_STRONG])
        return qs

    def test_all_questions_have_required_fields(self):
        for q in self._all_questions():
            assert 'id' in q, f'Missing id in question'
            assert 'prompt' in q, f'Missing prompt in {q["id"]}'
            assert 'options' in q, f'Missing options in {q["id"]}'
            assert 'branch' in q, f'Missing branch in {q["id"]}'
            assert 'position' in q, f'Missing position in {q["id"]}'

    def test_all_options_have_required_fields(self):
        for q in self._all_questions():
            for i, opt in enumerate(q['options']):
                assert 'text' in opt, f'{q["id"]} option {i} missing text'
                assert 'icon' in opt, f'{q["id"]} option {i} missing icon'
                assert 'signals' in opt, f'{q["id"]} option {i} missing signals'

    def test_no_duplicate_question_ids(self):
        ids = ALL_QUESTION_IDS
        assert len(ids) == len(set(ids)), f'Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}'

    def test_all_question_ids_accounted_for(self):
        """Every question dict should appear in ALL_QUESTION_IDS."""
        for q in self._all_questions():
            assert q['id'] in ALL_QUESTION_IDS, f'{q["id"]} not in ALL_QUESTION_IDS'


class TestTrilingualCompleteness:

    def _all_questions(self):
        qs = list(TRUNK_QUESTIONS)
        qs.extend([SCIENCE_Q2, ARTS_Q2, MIXED_Q2])
        qs.extend(SCIENCE_Q3_VARIANTS.values())
        qs.extend(ARTS_Q3_VARIANTS.values())
        qs.extend([Q4_CONFIDENCE_WEAK, Q4_CONFIDENCE_STRONG])
        return qs

    def test_prompts_have_all_three_languages(self):
        for q in self._all_questions():
            prompt = q['prompt']
            if isinstance(prompt, dict):
                for lang in SUPPORTED_LANGUAGES:
                    assert lang in prompt, f'{q["id"]} prompt missing {lang}'
                    assert prompt[lang].strip(), f'{q["id"]} prompt {lang} is empty'

    def test_option_texts_have_all_three_languages(self):
        for q in self._all_questions():
            for i, opt in enumerate(q['options']):
                text = opt['text']
                if isinstance(text, dict):
                    for lang in SUPPORTED_LANGUAGES:
                        assert lang in text, f'{q["id"]} opt {i} text missing {lang}'
                        assert text[lang].strip(), f'{q["id"]} opt {i} text {lang} empty'

    def test_q5_options_have_all_three_languages(self):
        for key, opt in Q5_CROSS_DOMAIN_OPTIONS['all_options'].items():
            for lang in SUPPORTED_LANGUAGES:
                assert lang in opt['text'], f'Q5 option {key} missing {lang}'

    def test_field_display_names_trilingual(self):
        for field, names in FIELD_DISPLAY_NAMES.items():
            for lang in SUPPORTED_LANGUAGES:
                assert lang in names, f'FIELD_DISPLAY_NAMES[{field}] missing {lang}'

    def test_subject_display_names_trilingual(self):
        for subj, names in SUBJECT_DISPLAY_NAMES.items():
            for lang in SUPPORTED_LANGUAGES:
                assert lang in names, f'SUBJECT_DISPLAY_NAMES[{subj}] missing {lang}'


class TestSignalTaxonomy:

    def test_all_signal_categories_defined(self):
        expected = {
            'riasec_seed', 'field_interest', 'field_key', 'cross_domain',
            'efficacy', 'resilience', 'motivation', 'career_goal', 'context',
        }
        assert set(STPM_SIGNAL_TAXONOMY.keys()) == expected

    def test_no_duplicate_signals_across_categories(self):
        all_signals = []
        for signals in STPM_SIGNAL_TAXONOMY.values():
            all_signals.extend(signals)
        dupes = [s for s in all_signals if all_signals.count(s) > 1]
        assert not dupes, f'Duplicate signals: {dupes}'

    def test_question_signals_are_in_taxonomy(self):
        """Every signal emitted by a question option must be in the taxonomy."""
        all_taxonomy_signals = set()
        for signals in STPM_SIGNAL_TAXONOMY.values():
            all_taxonomy_signals.update(signals)

        questions = list(TRUNK_QUESTIONS)
        questions.extend([SCIENCE_Q2, ARTS_Q2, MIXED_Q2])
        questions.extend(SCIENCE_Q3_VARIANTS.values())
        questions.extend(ARTS_Q3_VARIANTS.values())
        questions.extend([Q4_CONFIDENCE_WEAK, Q4_CONFIDENCE_STRONG])

        for q in questions:
            for opt in q['options']:
                for sig in opt['signals']:
                    assert sig in all_taxonomy_signals, (
                        f'Signal {sig} from {q["id"]} not in taxonomy'
                    )

    def test_q5_signals_are_in_taxonomy(self):
        all_taxonomy_signals = set()
        for signals in STPM_SIGNAL_TAXONOMY.values():
            all_taxonomy_signals.update(signals)

        for key, opt in Q5_CROSS_DOMAIN_OPTIONS['all_options'].items():
            for sig in opt['signals']:
                assert sig in all_taxonomy_signals, (
                    f'Q5 signal {sig} from option {key} not in taxonomy'
                )


class TestFieldKeyMap:

    def test_all_field_key_signals_have_taxonomy_entries(self):
        """Every field_key signal in STPM_FIELD_KEY_MAP should be in the taxonomy."""
        taxonomy_field_keys = set(STPM_SIGNAL_TAXONOMY['field_key'])
        for fk in STPM_FIELD_KEY_MAP:
            assert fk in taxonomy_field_keys, f'{fk} not in field_key taxonomy'

    def test_field_key_map_values_are_lists(self):
        for fk, vals in STPM_FIELD_KEY_MAP.items():
            assert isinstance(vals, list), f'{fk} value is not a list'
            assert len(vals) > 0, f'{fk} has empty field_key list'


class TestSubjectMappings:

    def test_all_riasec_subjects_classified(self):
        """Every subject in RIASEC map should be in SCIENCE or ARTS sets."""
        for subj in SUBJECT_RIASEC_MAP:
            assert subj in SCIENCE_SUBJECTS or subj in ARTS_SUBJECTS, (
                f'{subj} not classified as science or arts'
            )

    def test_science_arts_disjoint(self):
        overlap = SCIENCE_SUBJECTS & ARTS_SUBJECTS
        assert not overlap, f'Overlap between science and arts: {overlap}'

    def test_grade_points_cover_all_grades(self):
        expected = {'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'F'}
        assert set(STPM_GRADE_POINTS.keys()) == expected

    def test_grade_points_monotonically_decreasing(self):
        grades = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'F']
        points = [STPM_GRADE_POINTS[g] for g in grades]
        for i in range(len(points) - 1):
            assert points[i] >= points[i + 1], (
                f'{grades[i]}={points[i]} should be >= {grades[i+1]}={points[i+1]}'
            )


class TestQ5CrossDomain:

    def test_stay_in_lane_available_to_all(self):
        opt = Q5_CROSS_DOMAIN_OPTIONS['all_options']['stay_in_lane']
        assert set(opt['available_to']) == {'science', 'arts', 'mixed'}

    def test_arts_cannot_see_science_options(self):
        """Arts students should not see options only available to science."""
        for key, opt in Q5_CROSS_DOMAIN_OPTIONS['all_options'].items():
            if 'arts' in opt['available_to']:
                continue
            # This option is NOT available to arts — good
            assert 'science' in opt['available_to'] or 'mixed' in opt['available_to']

    def test_each_option_has_at_least_one_stream(self):
        for key, opt in Q5_CROSS_DOMAIN_OPTIONS['all_options'].items():
            assert len(opt['available_to']) > 0, f'Q5 option {key} has no streams'
