"""
STPM Quiz Engine — subjects in, branch questions out, answers in, signals out.

Subject-seeded branching quiz. The student's STPM subjects determine their
RIASEC seed and quiz branch (Science, Arts, or Mixed). The engine assembles
the correct 10-question sequence, fills in grade-adaptive Q4, filters
cross-domain Q5 options, and accumulates signals.

See docs/plans/2026-03-18-stpm-quiz-design.md for full design rationale.
"""
from typing import Any

from .stpm_quiz_data import (
    SUBJECT_RIASEC_MAP,
    SCIENCE_SUBJECTS,
    ARTS_SUBJECTS,
    EXCLUDED_SUBJECTS,
    STPM_SIGNAL_TAXONOMY,
    SUPPORTED_LANGUAGES,
    # Questions
    Q1_READINESS,
    SCIENCE_Q2, ARTS_Q2, MIXED_Q2,
    SCIENCE_Q3_VARIANTS, ARTS_Q3_VARIANTS, MIXED_Q3_VARIANTS,
    Q4_CONFIDENCE_WEAK, Q4_CONFIDENCE_STRONG,
    Q5_CROSS_DOMAIN_OPTIONS,
    Q7_CHALLENGE, Q8_MOTIVATION, Q9_CAREER, Q10_FAMILY,
    # Lookup tables
    FIELD_TO_SUBJECT,
    WEAK_GRADE_THRESHOLD,
    STPM_GRADE_POINTS,
    FIELD_DISPLAY_NAMES,
    SUBJECT_DISPLAY_NAMES,
    ALL_QUESTION_IDS,
)

# Build reverse lookup: signal_name → category_name
_SIGNAL_TO_CATEGORY = {}
for _cat, _signals in STPM_SIGNAL_TAXONOMY.items():
    for _sig in _signals:
        _SIGNAL_TO_CATEGORY[_sig] = _cat


def calculate_riasec_seed(subjects: list[str]) -> dict[str, int]:
    """
    Calculate RIASEC scores from STPM subjects.

    Args:
        subjects: List of subject keys (e.g. ['physics', 'chemistry', 'mathematics_t']).
                  PA (pengajian_am) is excluded automatically.

    Returns:
        Dict of RIASEC type → total score, e.g. {'R': 3, 'I': 5, 'C': 1}.
        Only types with score > 0 are included.
    """
    scores: dict[str, int] = {}
    for subj in subjects:
        if subj in EXCLUDED_SUBJECTS:
            continue
        mapping = SUBJECT_RIASEC_MAP.get(subj)
        if not mapping:
            continue
        for riasec_type, points in mapping.items():
            scores[riasec_type] = scores.get(riasec_type, 0) + points

    return {k: v for k, v in scores.items() if v > 0}


def get_primary_seed(riasec_scores: dict[str, int]) -> list[str]:
    """
    Return the primary RIASEC type(s) — the highest-scoring one(s).
    Ties are preserved (returns multiple types if scores are equal).
    """
    if not riasec_scores:
        return []
    max_score = max(riasec_scores.values())
    return [t for t, s in riasec_scores.items() if s == max_score]


def determine_branch(subjects: list[str]) -> str:
    """
    Determine quiz branch based on STPM subjects.

    Returns: 'science', 'arts', or 'mixed'.
    """
    filtered = [s for s in subjects if s not in EXCLUDED_SUBJECTS]
    science_count = sum(1 for s in filtered if s in SCIENCE_SUBJECTS)
    arts_count = sum(1 for s in filtered if s in ARTS_SUBJECTS)

    if science_count >= 2 and arts_count == 0:
        return 'science'
    if arts_count >= 2 and science_count == 0:
        return 'arts'
    return 'mixed'


def has_extra_cross_stream_subject(subjects: list[str], branch: str) -> bool:
    """
    Check if a student took an extra subject from the opposite stream.
    E.g. a science student who also took Economics.
    """
    filtered = [s for s in subjects if s not in EXCLUDED_SUBJECTS]
    if branch == 'science':
        return any(s in ARTS_SUBJECTS for s in filtered)
    if branch == 'arts':
        return any(s in SCIENCE_SUBJECTS for s in filtered)
    return False


def _resolve_q4(field_signal: str, grades: dict[str, str],
                lang: str) -> dict | None:
    """
    Build the grade-adaptive Q4 question based on the student's
    field interest and actual grades.

    Returns a question dict with interpolated prompt text, or None
    if no relevant subject grades exist.
    """
    relevant_subjects = FIELD_TO_SUBJECT.get(field_signal, [])
    if not relevant_subjects:
        # For fields with no subject tie (e.g. education), use the strong variant
        # with generic prompt
        return _build_q4(Q4_CONFIDENCE_STRONG, field_signal, '', '', lang)

    # Find the most relevant subject grade
    best_subject = None
    best_grade = None
    best_gpa = None
    for subj in relevant_subjects:
        grade = grades.get(subj)
        if grade and grade in STPM_GRADE_POINTS:
            gpa = STPM_GRADE_POINTS[grade]
            if best_gpa is None or gpa > best_gpa:
                best_subject = subj
                best_grade = grade
                best_gpa = gpa

    if best_subject is None:
        # No relevant grade found — use strong variant with neutral framing
        return _build_q4(Q4_CONFIDENCE_STRONG, field_signal, '', '', lang)

    if best_gpa <= WEAK_GRADE_THRESHOLD:
        template = Q4_CONFIDENCE_WEAK
    else:
        template = Q4_CONFIDENCE_STRONG

    return _build_q4(template, field_signal, best_subject, best_grade, lang)


def _build_q4(template: dict, field_signal: str,
              subject_key: str, grade: str, lang: str) -> dict:
    """Interpolate Q4 template with field/subject/grade context."""
    field_name = FIELD_DISPLAY_NAMES.get(field_signal, {}).get(lang, field_signal)
    subject_name = SUBJECT_DISPLAY_NAMES.get(subject_key, {}).get(lang, subject_key)

    # Deep copy to avoid mutating the template
    q4 = {
        'id': template['id'],
        'branch': 'adaptive',
        'position': 4,
        'prompt': template['prompt'][lang].format(
            field=field_name, subject=subject_name, grade=grade
        ),
        'options': [],
    }
    for opt in template['options']:
        text = opt['text'][lang]
        if '{subject}' in text:
            text = text.format(subject=subject_name)
        if '{field}' in text:
            text = text.format(field=field_name)
        q4['options'].append({
            'text': text,
            'icon': opt['icon'],
            'signals': dict(opt['signals']),
        })
    return q4


def _resolve_q5(branch: str, subjects: list[str], lang: str) -> dict:
    """
    Build the cross-domain Q5 question, filtering options by stream.
    Science students see all cross-domain options.
    Arts students see only achievable options (no science prerequisites).
    """
    all_opts = Q5_CROSS_DOMAIN_OPTIONS['all_options']
    filtered_options = []

    for key, opt_data in all_opts.items():
        if branch in opt_data['available_to']:
            filtered_options.append({
                'text': opt_data['text'][lang],
                'icon': opt_data['icon'],
                'signals': dict(opt_data['signals']),
            })

    return {
        'id': 'q5_cross_domain',
        'branch': 'trunk',
        'position': 5,
        'prompt': Q5_CROSS_DOMAIN_OPTIONS['prompt'][lang],
        'options': filtered_options,
    }


def _localise_question(question: dict, lang: str) -> dict:
    """Convert a trilingual question dict to single-language for API response."""
    prompt = question['prompt']
    if isinstance(prompt, dict):
        prompt = prompt.get(lang, prompt.get('en', ''))

    options = []
    for opt in question['options']:
        text = opt['text']
        if isinstance(text, dict):
            text = text.get(lang, text.get('en', ''))
        options.append({
            'text': text,
            'icon': opt['icon'],
            'signals': dict(opt['signals']),
        })

    result = {
        'id': question['id'],
        'prompt': prompt,
        'options': options,
    }
    if question.get('select_mode'):
        result['select_mode'] = question['select_mode']
    if question.get('max_select'):
        result['max_select'] = question['max_select']
    return result


def get_stpm_quiz_questions(
    subjects: list[str],
    grades: dict[str, str],
    lang: str = 'en',
) -> dict:
    """
    Return the 10-question sequence for a student, based on their subjects.

    This returns the INITIAL question set. Q3 and Q4 depend on Q2 answers,
    so they are placeholders until the student answers Q2.

    Args:
        subjects: Student's STPM subjects (e.g. ['physics', 'chemistry', 'mathematics_t'])
        grades: Subject → grade mapping (e.g. {'physics': 'A', 'chemistry': 'B+'})
        lang: Language code ('en', 'bm', 'ta')

    Returns:
        {
            'branch': 'science' | 'arts' | 'mixed',
            'riasec_seed': {'R': 3, 'I': 5, ...},
            'primary_seed': ['I'],
            'has_cross_stream': True/False,
            'questions': [
                {id, prompt, options, ...},  # Q1
                {id, prompt, options, ...},  # Q2 (branch-specific)
                # Q3, Q4 will be resolved after Q2 answer
            ],
            'q3_variants': {field_signal: {id, prompt, options}},
            'q5': {id, prompt, options},
            'trunk_remaining': [{id, prompt, options}, ...],  # Q7–Q10
        }
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = 'en'

    branch = determine_branch(subjects)
    riasec_scores = calculate_riasec_seed(subjects)
    primary = get_primary_seed(riasec_scores)
    cross_stream = has_extra_cross_stream_subject(subjects, branch)

    # Q1 — always first
    q1 = _localise_question(Q1_READINESS, lang)

    # Q2 — branch-specific
    if branch == 'science':
        q2 = _localise_question(SCIENCE_Q2, lang)
        q3_map = SCIENCE_Q3_VARIANTS
    elif branch == 'arts':
        q2 = _localise_question(ARTS_Q2, lang)
        q3_map = ARTS_Q3_VARIANTS
    else:
        q2 = _localise_question(MIXED_Q2, lang)
        q3_map = MIXED_Q3_VARIANTS

    # Pre-localise Q3 variants so frontend can display them after Q2 answer
    q3_variants = {}
    for field_signal, q3 in q3_map.items():
        q3_variants[field_signal] = _localise_question(q3, lang)

    # Q5 — cross-domain (filtered by stream)
    q5 = _resolve_q5(branch, subjects, lang)

    # Trunk questions Q7–Q10
    trunk_remaining = [
        _localise_question(q, lang)
        for q in [Q7_CHALLENGE, Q8_MOTIVATION, Q9_CAREER, Q10_FAMILY]
    ]

    return {
        'branch': branch,
        'riasec_seed': riasec_scores,
        'primary_seed': primary,
        'has_cross_stream': cross_stream,
        'questions': [q1, q2],
        'q3_variants': q3_variants,
        'q5': q5,
        'trunk_remaining': trunk_remaining,
        'grades': grades,
    }


def resolve_q3_and_q4(
    field_signal: str,
    branch: str,
    grades: dict[str, str],
    lang: str = 'en',
) -> dict:
    """
    After the student answers Q2, resolve Q3 and Q4 for their chosen field.

    Args:
        field_signal: The field signal from Q2 answer (e.g. 'field_engineering')
        branch: The student's branch ('science', 'arts', 'mixed')
        grades: Subject → grade mapping
        lang: Language code

    Returns:
        {
            'q3': {id, prompt, options} or None,
            'q4': {id, prompt, options} or None,
        }
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = 'en'

    # Resolve Q3
    if branch == 'science':
        q3_map = SCIENCE_Q3_VARIANTS
    elif branch == 'arts':
        q3_map = ARTS_Q3_VARIANTS
    else:
        q3_map = MIXED_Q3_VARIANTS

    q3_template = q3_map.get(field_signal)
    q3 = _localise_question(q3_template, lang) if q3_template else None

    # Resolve Q4 (grade-adaptive)
    q4 = _resolve_q4(field_signal, grades, lang)

    return {'q3': q3, 'q4': q4}


def process_stpm_quiz(
    answers: list[dict[str, Any]],
    subjects: list[str],
    grades: dict[str, str],
    lang: str = 'en',
) -> dict:
    """
    Process STPM quiz answers and return categorised signals.

    Args:
        answers: List of {question_id, option_index} dicts (10 answers).
        subjects: Student's STPM subjects.
        grades: Subject → grade mapping.
        lang: Language code.

    Returns:
        {
            'student_signals': {
                'riasec_seed': {'riasec_I': 5, 'riasec_R': 3, ...},
                'field_interest': {'field_engineering': 3, ...},
                'field_key': {'field_key_mekanikal': 2, ...},
                'cross_domain': {...},
                'efficacy': {...},
                'resilience': {...},
                'motivation': {...},
                'career_goal': {...},
                'context': {...},
            },
            'signal_strength': {
                'field_engineering': 'strong',
                ...
            },
            'branch': 'science',
            'riasec_seed': {'R': 3, 'I': 5},
        }
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = 'en'

    branch = determine_branch(subjects)
    riasec_scores = calculate_riasec_seed(subjects)

    # Step 1: Accumulate RIASEC seed signals from subjects (pre-quiz)
    raw_scores: dict[str, int] = {}
    for riasec_type, score in riasec_scores.items():
        sig = f'riasec_{riasec_type}'
        raw_scores[sig] = score

    # Step 2: Build question lookup for answer validation
    # We need to reconstruct what questions the student was shown
    questions_shown = _reconstruct_questions(answers, branch, grades, lang)
    questions_by_id = {q['id']: q for q in questions_shown}

    # Step 3: Accumulate signals from answers
    for answer in answers:
        qid = answer.get('question_id')
        if not qid:
            raise ValueError('Missing question_id in answer')

        question = questions_by_id.get(qid)
        if not question:
            raise ValueError(f'Unknown question_id: {qid}')

        idx = answer.get('option_index')
        if idx is None:
            raise ValueError(f'Missing option_index for {qid}')

        options = question['options']
        if not isinstance(idx, int) or idx < 0 or idx >= len(options):
            raise ValueError(
                f'option_index {idx} out of range for {qid} '
                f'(expected 0-{len(options) - 1})'
            )

        chosen = options[idx]
        for sig, weight in chosen.get('signals', {}).items():
            raw_scores[sig] = raw_scores.get(sig, 0) + weight

    # Step 4: Categorise into taxonomy
    student_signals = {cat: {} for cat in STPM_SIGNAL_TAXONOMY}
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
        'branch': branch,
        'riasec_seed': riasec_scores,
    }


def _reconstruct_questions(
    answers: list[dict],
    branch: str,
    grades: dict[str, str],
    lang: str,
) -> list[dict]:
    """
    Reconstruct the set of questions shown to the student, based on
    their answers. Needed for answer validation.
    """
    questions = []

    # Q1 — always shown
    questions.append(_localise_question(Q1_READINESS, lang))

    # Q2 — branch-specific
    if branch == 'science':
        q2 = _localise_question(SCIENCE_Q2, lang)
        q3_map = SCIENCE_Q3_VARIANTS
    elif branch == 'arts':
        q2 = _localise_question(ARTS_Q2, lang)
        q3_map = ARTS_Q3_VARIANTS
    else:
        q2 = _localise_question(MIXED_Q2, lang)
        q3_map = MIXED_Q3_VARIANTS
    questions.append(q2)

    # Find Q2 answer to determine Q3 variant
    q2_answer = next(
        (a for a in answers if a.get('question_id') == q2['id']),
        None
    )
    field_signal = None
    if q2_answer is not None:
        idx = q2_answer.get('option_index', 0)
        if 0 <= idx < len(q2['options']):
            signals = q2['options'][idx].get('signals', {})
            # The field signal is the first key (each Q2 option has exactly one)
            field_signal = next(iter(signals), None)

    # Q3 — based on Q2 answer
    if field_signal and field_signal in q3_map:
        q3 = _localise_question(q3_map[field_signal], lang)
        questions.append(q3)

    # Q4 — grade-adaptive
    if field_signal:
        q4 = _resolve_q4(field_signal, grades, lang)
        if q4:
            questions.append(q4)

    # Q5 — cross-domain
    q5 = _resolve_q5(branch, [], lang)
    questions.append(q5)

    # Trunk Q7–Q10
    for q in [Q7_CHALLENGE, Q8_MOTIVATION, Q9_CAREER, Q10_FAMILY]:
        questions.append(_localise_question(q, lang))

    return questions
