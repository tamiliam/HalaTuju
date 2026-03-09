"""
Stateless quiz engine — answers in, signals out.

Takes a list of answers (one per question) and returns the accumulated
student signals in the 6-category taxonomy used by the ranking engine.

Supports both single-select (option_index) and multi-select (option_indices)
answer formats. Multi-select answers split signal weights when more than one
option is chosen. Conditional questions (e.g. Q2.5) are skipped silently
if the prerequisite signal was not accumulated.

Ported from src/quiz_manager.py (Streamlit era). All session state removed.
"""
from typing import Any

from .quiz_data import get_quiz_questions, QUESTION_IDS


# Canonical 6-category taxonomy — defines which signals belong where.
# Any signal not in this map is flagged as unknown.
SIGNAL_TAXONOMY = {
    'field_interest': [
        'field_mechanical', 'field_digital', 'field_business', 'field_health',
        'field_creative', 'field_hospitality', 'field_agriculture',
        'field_heavy_industry',
        'field_electrical', 'field_civil', 'field_aero_marine', 'field_oil_gas',
    ],
    'work_preference_signals': [
        'hands_on', 'problem_solving', 'people_helping', 'creative',
    ],
    'learning_tolerance_signals': [
        'learning_by_doing', 'concept_first', 'rote_tolerant', 'project_based',
    ],
    'environment_signals': [
        'workshop_environment', 'office_environment',
        'high_people_environment', 'field_environment',
    ],
    'value_tradeoff_signals': [
        'stability_priority', 'income_risk_tolerant', 'pathway_priority',
        'fast_employment_priority',
        'proximity_priority', 'allowance_priority', 'employment_guarantee',
        'quality_priority',
    ],
    'energy_sensitivity_signals': [
        'low_people_tolerance', 'mental_fatigue_sensitive',
        'physical_fatigue_sensitive', 'high_stamina',
    ],
}

# Build reverse lookup: signal_name → category_name
_SIGNAL_TO_CATEGORY = {}
for _cat, _signals in SIGNAL_TAXONOMY.items():
    for _sig in _signals:
        _SIGNAL_TO_CATEGORY[_sig] = _cat


def process_quiz_answers(answers: list[dict[str, Any]], lang: str = 'en') -> dict:
    """
    Process quiz answers and return categorised student signals.

    Args:
        answers: List of dicts, one per question. Each must have:
            - question_id: str (e.g. 'q1_field1')
            - option_index: int (0-based, single-select) OR
            - option_indices: list[int] (0-based, multi-select)
        lang: Language code for looking up question data ('en', 'bm', 'ta').

    Returns:
        {
            'student_signals': {
                'field_interest': {'field_mechanical': 3, ...},
                'work_preference_signals': {...},
                'learning_tolerance_signals': {...},
                'environment_signals': {...},
                'value_tradeoff_signals': {...},
                'energy_sensitivity_signals': {...},
            },
            'signal_strength': {
                'hands_on': 'strong',  # score >= 2
                'workshop_environment': 'moderate',  # score == 1
                ...
            },
        }

    Raises:
        ValueError: If question_id is unknown, option indices are out of range,
            or "Not Sure Yet" is combined with other selections.
    """
    questions = get_quiz_questions(lang)
    questions_by_id = {q['id']: q for q in questions}

    # Accumulate raw signals (flat dict: signal_name → total score)
    raw_scores: dict[str, int] = {}
    # Track all selected signals for conditional question checks
    all_selected_signals: set[str] = set()

    for answer in answers:
        qid = answer.get('question_id')

        if qid not in questions_by_id:
            raise ValueError(f'Unknown question_id: {qid}')

        question = questions_by_id[qid]
        options = question['options']

        # Check conditional question — skip if prerequisite signal not present
        condition = question.get('condition')
        if condition:
            required_signal = condition.get('option_signal')
            if required_signal and required_signal not in all_selected_signals:
                continue

        # Resolve selected indices — support both single and multi-select
        if 'option_indices' in answer:
            indices = answer['option_indices']
            if not isinstance(indices, list) or not indices:
                raise ValueError(
                    f'option_indices must be a non-empty list for {qid}'
                )
        elif 'option_index' in answer:
            # Backward-compatible single-select
            indices = [answer['option_index']]
        else:
            raise ValueError(
                f'Answer for {qid} must have option_index or option_indices'
            )

        # Validate all indices
        for idx in indices:
            if not isinstance(idx, int) or idx < 0 or idx >= len(options):
                raise ValueError(
                    f'option index {idx} out of range for {qid} '
                    f'(expected 0-{len(options) - 1})'
                )

        chosen_options = [options[idx] for idx in indices]

        # "Not Sure Yet" exclusivity — must be only selection
        not_sure_selected = any(opt.get('not_sure') for opt in chosen_options)
        if not_sure_selected and len(chosen_options) > 1:
            raise ValueError(
                f'"Not Sure Yet" must be the only selection for {qid}'
            )

        # Multi-select weight splitting:
        # 1 pick → original weight, 2 picks → each weight reduces by 1 (min 1)
        # "Not Sure Yet" options never get weight-split
        num_selected = len(chosen_options)

        for opt in chosen_options:
            is_not_sure = opt.get('not_sure', False)
            for sig, weight in opt.get('signals', {}).items():
                if num_selected > 1 and not is_not_sure:
                    adjusted_weight = max(1, weight - 1)
                else:
                    adjusted_weight = weight
                raw_scores[sig] = raw_scores.get(sig, 0) + adjusted_weight
                all_selected_signals.add(sig)

    # Categorise into 6-bucket taxonomy
    student_signals = {cat: {} for cat in SIGNAL_TAXONOMY}
    signal_strength = {}

    for sig, score in raw_scores.items():
        if score <= 0:
            continue

        category = _SIGNAL_TO_CATEGORY.get(sig)
        if category:
            student_signals[category][sig] = score
            signal_strength[sig] = 'strong' if score >= 2 else 'moderate'

    return {
        'student_signals': student_signals,
        'signal_strength': signal_strength,
    }
