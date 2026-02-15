"""
Stateless quiz engine — answers in, signals out.

Takes a list of answers (one per question) and returns the accumulated
student signals in the 5-category taxonomy used by the ranking engine.

Ported from src/quiz_manager.py (Streamlit era). All session state removed.
"""
from typing import Any

from .quiz_data import get_quiz_questions, QUESTION_IDS


# Canonical 5-category taxonomy — defines which signals belong where.
# Any signal not in this map is flagged as unknown.
SIGNAL_TAXONOMY = {
    'work_preference_signals': [
        'hands_on',
        'problem_solving',
        'people_helping',
        'creative',
        'organising',
    ],
    'learning_tolerance_signals': [
        'learning_by_doing',
        'concept_first',
        'rote_tolerant',
        'project_based',
        'exam_sensitive',
    ],
    'environment_signals': [
        'workshop_environment',
        'office_environment',
        'high_people_environment',
        'field_environment',
        'no_preference',
    ],
    'value_tradeoff_signals': [
        'stability_priority',
        'income_risk_tolerant',
        'pathway_priority',
        'meaning_priority',
        'fast_employment_priority',
        'proximity_priority',
        'allowance_priority',
        'employment_guarantee',
    ],
    'energy_sensitivity_signals': [
        'low_people_tolerance',
        'mental_fatigue_sensitive',
        'physical_fatigue_sensitive',
        'time_pressure_sensitive',
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
            - question_id: str (e.g. 'q1_modality')
            - option_index: int (0-based index of chosen option)
        lang: Language code for looking up question data ('en', 'bm', 'ta').

    Returns:
        {
            'student_signals': {
                'work_preference_signals': {'hands_on': 2, ...},
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
        ValueError: If question_id is unknown or option_index is out of range.
    """
    questions = get_quiz_questions(lang)
    questions_by_id = {q['id']: q for q in questions}

    # Accumulate raw signals (flat dict: signal_name → total score)
    raw_scores: dict[str, int] = {}

    for answer in answers:
        qid = answer.get('question_id')
        option_idx = answer.get('option_index')

        if qid not in questions_by_id:
            raise ValueError(f'Unknown question_id: {qid}')

        question = questions_by_id[qid]
        options = question['options']

        if not isinstance(option_idx, int) or option_idx < 0 or option_idx >= len(options):
            raise ValueError(
                f'option_index {option_idx} out of range for {qid} '
                f'(expected 0-{len(options) - 1})'
            )

        chosen = options[option_idx]
        for sig, weight in chosen.get('signals', {}).items():
            raw_scores[sig] = raw_scores.get(sig, 0) + weight

    # Categorise into 5-bucket taxonomy
    student_signals = {cat: {} for cat in SIGNAL_TAXONOMY}
    signal_strength = {}
    unknown_signals = []

    for sig, score in raw_scores.items():
        if score <= 0:
            continue

        category = _SIGNAL_TO_CATEGORY.get(sig)
        if category:
            student_signals[category][sig] = score
            signal_strength[sig] = 'strong' if score >= 2 else 'moderate'
        else:
            unknown_signals.append(sig)

    return {
        'student_signals': student_signals,
        'signal_strength': signal_strength,
    }
